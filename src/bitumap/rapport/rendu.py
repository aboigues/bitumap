"""Rendu d'un rapport : ``rapport.html`` autonome + fichiers associés (report-bundle.md)."""

from __future__ import annotations

import base64
import hashlib
import json
from collections import Counter
from datetime import date
from html.parser import HTMLParser
from importlib import resources

from jinja2 import Environment, PackageLoader, select_autoescape

from bitumap.calcul import ResultatCommune
from bitumap.facteurs.voirie import libelle
from bitumap.journal import JournalGeneration
from bitumap.points import direction
from bitumap.rapport import carte_svg
from bitumap.score.methode import LIBELLES_GROUPES

SCRIPT = (resources.files("bitumap.rapport") / "interactions.js").read_text("utf-8")
# Empreinte du seul script autorisé dans les rapports (CSP servie par l'API).
EMPREINTE_SCRIPT = "sha256-" + base64.b64encode(hashlib.sha256(SCRIPT.encode()).digest()).decode()
CSP_RAPPORT = (
    "default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
    f"script-src '{EMPREINTE_SCRIPT}'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)


# Vérification hors Panoramax : comparaison des photos aériennes de l'IGN (« Remonter le
# temps »), aujourd'hui contre 2016-2020 ; une réfection ou un réaménagement récent s'y voit.
# L'application désigne les couches par leur numéro (vérifié dans un navigateur le
# 2026-09-30, LL-007) : 10 = aujourd'hui, 11 = 2016-2020.
REMONTER_LE_TEMPS = (
    "https://remonterletemps.ign.fr/comparer/?lon={lon:.6f}&lat={lat:.6f}&z=19"
    "&layer1=10&layer2=11&mode=split-h"
)


def lien_photos_aeriennes(lon: float, lat: float) -> str:
    return REMONTER_LE_TEMPS.format(lon=lon, lat=lat)


class _ScriptsEnLigne(HTMLParser):
    """Scripts exécutables en ligne d'un document (les blocs de données JSON exclus)."""

    def __init__(self):
        super().__init__()
        self.scripts: list[str] = []
        self._courant: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            type_ = (dict(attrs).get("type") or "").lower()
            self._courant = None if type_ == "application/json" else []

    def handle_data(self, data):
        if self._courant is not None:
            self._courant.append(data)

    def handle_endtag(self, tag):
        if tag == "script":
            if self._courant is not None:
                self.scripts.append("".join(self._courant))
            self._courant = None


def csp_du_document(html: str) -> str:
    """CSP d'un rapport servi : n'autorise que les scripts en ligne **de ce document**.

    Un rapport encore en cache, produit avant une modification du script, garde ainsi son
    interactivité (003 R2) ; le document vient du bucket privé, écrit par le job de lot.
    """
    analyse = _ScriptsEnLigne()
    analyse.feed(html)
    empreintes = sorted(
        {
            "'sha256-" + base64.b64encode(hashlib.sha256(s.encode()).digest()).decode() + "'"
            for s in analyse.scripts
        }
    )
    scripts = " ".join(empreintes) or "'none'"
    return (
        "default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
        f"script-src {scripts}; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    )


_env = Environment(
    loader=PackageLoader("bitumap.rapport", "gabarits"),
    autoescape=select_autoescape(["html", "j2"]),
    trim_blocks=True,
    lstrip_blocks=True,
)
_env.filters["route"] = libelle
_env.filters["designation"] = direction.designation
_env.filters["identifiant"] = direction.identifiant
_env.globals["libelles_groupes"] = LIBELLES_GROUPES


def json_dans_html(donnees) -> str:
    """JSON sûr dans un bloc <script type="application/json"> (aucune sortie de balise)."""
    texte = json.dumps(donnees, ensure_ascii=False, default=str)
    return texte.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _synthese(resultat: ResultatCommune) -> dict:
    points = resultat.points
    priorites = Counter(p.priorite for p in points)
    groupes = Counter(p.groupe for p in points)
    synthese = {
        "priorites": {k: priorites.get(k, 0) for k in ("P1", "P2", "P3")},
        "groupes": {k: groupes.get(k, 0) for k in ("P1a", "P1b", "P1c", "P2", "P3")},
        "types": dict(Counter(p.libelle_type for p in points)),
        "routes": dict(Counter(libelle(p.route.classement) for p in points).most_common()),
        "classements": [(c, libelle(c)) for c in sorted({p.route.classement for p in points})],
    }
    # Méthode 2.0 (004 FR-010) : part des points couverts par un comptage de poids lourds.
    # Méthode 2.0 (004 FR-007) : été de référence et jours de forte chaleur.
    if resultat.ete_reference is not None:
        synthese["ete_reference"] = resultat.ete_reference
    pl = [f for p in points if (f := p.facteur("poids_lourds")) is not None]
    if pl:
        evalues = sum(f.statut == "evalue" for f in pl)
        synthese["couverture_poids_lourds"] = round(100 * evalues / len(points))
    return synthese


def rendre(
    resultat: ResultatCommune, journal: JournalGeneration, bruts_ia: dict | None = None
) -> dict[str, tuple[bytes, str]]:
    """Fichiers du rapport : {nom: (contenu, type)} ; ``rapport.html`` en dernier à l'écriture."""
    sources = [p.en_dict() for p in resultat.provenances]
    points_dict = [
        {**p.en_dict(), "photos_aeriennes": lien_photos_aeriennes(p.lon, p.lat)}
        for p in resultat.points
    ]
    html = _env.get_template("rapport.html.j2").render(
        commune=resultat.nom,
        date=date.today().isoformat(),
        version_methode=journal.version_methode,
        points=resultat.points,
        synthese=_synthese(resultat),
        carte=carte_svg.dessiner(resultat.contour, resultat.voies_bus, resultat.points),
        sources=sources,
        avertissements=resultat.avertissements,
        ia=journal.ia if journal.ia.modele else None,
        donnees_json=json_dans_html({"points": points_dict}),
        script=SCRIPT,
    )
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [p.lon, p.lat]},
                "properties": {k: v for k, v in d.items() if k not in ("lon", "lat", "score_brut")},
            }
            for p, d in zip(resultat.points, points_dict, strict=True)
        ],
    }
    fichiers = {
        "points.geojson": (
            json.dumps(geojson, ensure_ascii=False, default=str).encode(),
            "application/geo+json",
        ),
        "sources.json": (json.dumps(sources, ensure_ascii=False).encode(), "application/json"),
        "journal.json": (journal.en_json(), "application/json"),
    }
    for point_id, brut in (bruts_ia or {}).items():
        fichiers[f"ia/{point_id}.json"] = (
            json.dumps(brut, ensure_ascii=False).encode(),
            "application/json",
        )
    fichiers["rapport.html"] = (html.encode(), "text/html; charset=utf-8")
    return fichiers
