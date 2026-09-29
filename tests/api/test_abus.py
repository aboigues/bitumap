"""Protection contre les abus (US2, SC-006, SC-010) : antibot, quotas, budget.

Aucune génération ni aucun e-mail sans preuve valide ou au-delà des quotas.
"""

import base64
import json
from datetime import UTC, datetime, timedelta

import altcha
import pytest

from bitumap.api import quotas
from bitumap.config import reglages
from bitumap.db import connexion
from tests.conftest import connecter, demander_lien, preuve

JSON = {"accept": "application/json"}


def _nb(table: str) -> int:
    with connexion() as conn:
        return conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]  # noqa: S608


def _demander(client, csrf, insee="92026", charge=None):
    charge = preuve(client) if charge is None else charge
    return client.post(
        "/demandes",
        data={"insee": insee, "csrf": csrf, "altcha": charge},
        headers=JSON,
        follow_redirects=False,
    )


def _fixer_compteur(prefixe: str, duree, valeur: int) -> None:
    nom, fin = quotas.cle(prefixe, duree)
    with connexion() as conn:
        conn.execute(
            "INSERT INTO compteur_quota (cle, valeur, expire_le) VALUES (%s, %s, %s)"
            " ON CONFLICT (cle) DO UPDATE SET valeur = excluded.valeur",
            (nom, valeur, fin),
        )


def _compte_id(email: str) -> str:
    with connexion() as conn:
        return str(
            conn.execute("SELECT id FROM compte WHERE email = %s", (email,)).fetchone()["id"]
        )


# --- Antibot -------------------------------------------------------------------------


def test_defi_signe_et_valable_10_minutes(client):
    reponse = client.get("/altcha/defi")
    assert reponse.status_code == 200
    assert reponse.headers["cache-control"] == "no-store"
    defi = reponse.json()
    assert defi["signature"]
    reste = defi["parameters"]["expiresAt"] - datetime.now(UTC).timestamp()
    assert 9 * 60 < reste <= 10 * 60


@pytest.mark.parametrize("charge", ["", "pas-du-base64", base64.b64encode(b"{}").decode()])
def test_connexion_sans_preuve_valide(client, courriels, charge):
    reponse = client.post(
        "/connexion", data={"email": "a@exemple.fr", "altcha": charge}, headers=JSON
    )
    assert reponse.status_code == 400
    assert reponse.json()["erreur"] == "antibot_invalide"
    assert courriels == [] and _nb("lien_connexion") == 0


def test_preuve_rejouee_refusee(client, courriels):
    charge = preuve(client)
    assert client.post("/connexion", data={"email": "a@exemple.fr", "altcha": charge}).is_success
    rejouee = client.post(
        "/connexion", data={"email": "b@exemple.fr", "altcha": charge}, headers=JSON
    )
    assert rejouee.status_code == 400 and rejouee.json()["erreur"] == "antibot_invalide"
    assert len(courriels) == 1


def test_preuve_expiree_refusee(client, courriels, monkeypatch):
    monkeypatch.setattr(reglages(), "altcha_validite_min", -1)
    reponse = demander_lien(client, "a@exemple.fr")
    assert reponse.status_code == 400 and courriels == []


def test_preuve_signee_par_une_autre_cle_refusee(client, courriels):
    defi = altcha.create_challenge(
        "PBKDF2/SHA-256",
        1,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        hmac_secret="une-autre-cle",
    )
    charge = altcha.Payload(defi, altcha.solve_challenge(defi)).to_base64()
    reponse = client.post("/connexion", data={"email": "a@exemple.fr", "altcha": charge})
    assert reponse.status_code == 400 and courriels == []


def test_solution_falsifiee_refusee(client, courriels):
    charge = json.loads(base64.b64decode(preuve(client)))
    charge["solution"]["counter"] += 1
    charge["solution"]["derivedKey"] = "00" * 32
    falsifiee = base64.b64encode(json.dumps(charge).encode()).decode()
    reponse = client.post("/connexion", data={"email": "a@exemple.fr", "altcha": falsifiee})
    assert reponse.status_code == 400 and courriels == []


def test_demande_sans_preuve_refusee(client, courriels, territoire, s3):
    csrf = connecter(client, courriels)
    reponse = _demander(client, csrf, charge="")
    assert reponse.status_code == 400 and reponse.json()["erreur"] == "antibot_invalide"
    assert _nb("demande") == 0


def test_61e_defi_de_l_heure_refuse(client):
    _fixer_compteur(quotas.defi_origine(_requete_de_test()), quotas.HEURE, 60)
    reponse = client.get("/altcha/defi", headers=JSON)
    assert reponse.status_code == 429 and reponse.json()["erreur"] == "trop_de_demandes"


# --- Liens de connexion ----------------------------------------------------------------


def test_4e_lien_de_l_heure_pour_une_adresse(client, courriels):
    for _ in range(3):
        assert demander_lien(client, "a@exemple.fr").status_code == 200
    reponse = demander_lien(client, "a@exemple.fr")
    assert reponse.status_code == 429
    assert len(courriels) == 3


def test_refus_identique_adresse_connue_ou_inconnue(client, courriels):
    connecter(client, courriels, "connu@exemple.fr")
    client.cookies.clear()
    for _ in range(2):
        demander_lien(client, "connu@exemple.fr")
    for _ in range(3):
        demander_lien(client, "inconnu@exemple.fr")
    connu = demander_lien(client, "connu@exemple.fr")
    inconnu = demander_lien(client, "inconnu@exemple.fr")
    assert connu.status_code == inconnu.status_code == 429
    assert connu.text == inconnu.text


def test_11e_lien_de_l_heure_pour_une_origine(client, courriels):
    for i in range(10):
        assert demander_lien(client, f"u{i}@exemple.fr").status_code == 200
    assert demander_lien(client, "u10@exemple.fr").status_code == 429
    assert len(courriels) == 10


# --- Générations -----------------------------------------------------------------------


def test_6e_demande_du_jour_d_un_compte(client, courriels, territoire, s3):
    csrf = connecter(client, courriels)
    for insee in territoire:  # 5 communes distinctes
        assert _demander(client, csrf, insee).status_code == 303
    with connexion() as conn:  # libère la file : la 6ᵉ est bien une nouvelle génération
        conn.execute("UPDATE demande SET etat = 'en_echec'")
    reponse = _demander(client, csrf, "92026")
    assert reponse.status_code == 429 and reponse.json()["erreur"] == "quota_compte"
    assert _nb("demande") == 5


def test_51e_demande_globale_du_jour(client, courriels, territoire, s3):
    _fixer_compteur(quotas.GENERATION_GLOBALE, quotas.JOUR, 50)
    csrf = connecter(client, courriels)
    reponse = _demander(client, csrf)
    assert reponse.status_code == 429 and reponse.json()["erreur"] == "quota_global"
    assert _nb("demande") == 0
    # la transaction annulée ne décompte pas le quota du compte
    nom, _ = quotas.cle(quotas.generation_compte(_compte_id("agent@exemple.fr")), quotas.JOUR)
    with connexion() as conn:
        ligne = conn.execute("SELECT 1 FROM compteur_quota WHERE cle = %s", (nom,)).fetchone()
    assert ligne is None


def test_rattachement_sans_quota(client, courriels, territoire, s3):
    csrf = connecter(client, courriels, "a@exemple.fr")
    premiere = _demander(client, csrf).headers["location"]
    client.cookies.clear()
    csrf = connecter(client, courriels, "b@exemple.fr")
    _fixer_compteur(quotas.generation_compte(_compte_id("b@exemple.fr")), quotas.JOUR, 5)
    _fixer_compteur(quotas.GENERATION_GLOBALE, quotas.JOUR, 50)
    reponse = _demander(client, csrf)
    assert reponse.status_code == 303 and reponse.headers["location"] == premiere


def test_budget_ia_du_jour_epuise(client, courriels, territoire, s3):
    with connexion() as conn:
        conn.execute(
            "INSERT INTO cout_ia_jour (jour, montant_eur) VALUES (current_date, %s)",
            (reglages().ia_plafond_jour_eur,),
        )
    csrf = connecter(client, courriels)
    reponse = _demander(client, csrf)
    assert reponse.status_code == 429 and reponse.json()["erreur"] == "budget_ia_epuise"
    assert _nb("demande") == 0


def test_rapport_inaccessible_sans_session(client):
    reponse = client.get("/rapports/92026/0123456789abcdef", headers=JSON)
    assert reponse.status_code == 401


# --- Minimisation (FR-026) -------------------------------------------------------------


def test_aucune_adresse_en_clair_dans_les_compteurs(client, courriels):
    demander_lien(client, "a@exemple.fr")
    with connexion() as conn:
        cles = [x["cle"] for x in conn.execute("SELECT cle, expire_le FROM compteur_quota")]
        expirations = [x["expire_le"] for x in conn.execute("SELECT expire_le FROM compteur_quota")]
    assert cles and not any("testclient" in c or "exemple" in c for c in cles)
    assert all(e <= datetime.now(UTC) + timedelta(hours=24) for e in expirations)


def test_sel_renouvele_chaque_jour():
    jour = datetime(2026, 9, 29, 12, tzinfo=UTC)
    assert quotas.empreinte_salee("192.0.2.1", jour) == quotas.empreinte_salee("192.0.2.1", jour)
    assert quotas.empreinte_salee("192.0.2.1", jour) != quotas.empreinte_salee(
        "192.0.2.1", jour + timedelta(days=1)
    )


def test_origine_derriere_le_proxy(monkeypatch):
    monkeypatch.setattr(reglages(), "origine_via_proxy", True)
    requete = _requete_de_test({"x-forwarded-for": "203.0.113.9, 198.51.100.7"})
    assert quotas.adresse_origine(requete) == "198.51.100.7"  # ajoutée par le proxy


def _requete_de_test(en_tetes: dict | None = None):
    from starlette.requests import Request

    return Request(
        {
            "type": "http",
            "headers": [(k.encode(), v.encode()) for k, v in (en_tetes or {}).items()],
            "client": ("testclient", 50000),
        }
    )
