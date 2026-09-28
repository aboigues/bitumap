"""Rendu d'un rapport : ``rapport.html`` autonome + fichiers associés (report-bundle.md)."""

from __future__ import annotations

import base64
import hashlib
import json
from collections import Counter
from datetime import date
from importlib import resources

from jinja2 import Environment, PackageLoader, select_autoescape

from bitumap.calcul import ResultatCommune
from bitumap.facteurs.voirie import libelle
from bitumap.journal import JournalGeneration
from bitumap.rapport import carte_svg
from bitumap.score.methode import VERSION_METHODE

SCRIPT = (resources.files("bitumap.rapport") / "interactions.js").read_text("utf-8")
# Empreinte du seul script autorisé dans les rapports (CSP servie par l'API).
EMPREINTE_SCRIPT = "sha256-" + base64.b64encode(hashlib.sha256(SCRIPT.encode()).digest()).decode()
CSP_RAPPORT = (
    "default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
    f"script-src '{EMPREINTE_SCRIPT}'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)

_env = Environment(
    loader=PackageLoader("bitumap.rapport", "gabarits"),
    autoescape=select_autoescape(["html", "j2"]),
    trim_blocks=True,
    lstrip_blocks=True,
)
_env.filters["route"] = libelle


def _json_dans_html(donnees) -> str:
    """JSON sûr dans un bloc <script type="application/json"> (aucune sortie de balise)."""
    texte = json.dumps(donnees, ensure_ascii=False, default=str)
    return texte.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _synthese(resultat: ResultatCommune) -> dict:
    points = resultat.points
    priorites = Counter(p.priorite for p in points)
    return {
        "priorites": {k: priorites.get(k, 0) for k in ("P1", "P2", "P3")},
        "types": dict(Counter(p.libelle_type for p in points)),
        "routes": dict(Counter(libelle(p.route.classement) for p in points).most_common()),
        "classements": [(c, libelle(c)) for c in sorted({p.route.classement for p in points})],
    }


def rendre(
    resultat: ResultatCommune, journal: JournalGeneration, bruts_ia: dict | None = None
) -> dict[str, tuple[bytes, str]]:
    """Fichiers du rapport : {nom: (contenu, type)} ; ``rapport.html`` en dernier à l'écriture."""
    sources = [p.en_dict() for p in resultat.provenances]
    points_dict = [p.en_dict() for p in resultat.points]
    html = _env.get_template("rapport.html.j2").render(
        commune=resultat.nom,
        date=date.today().isoformat(),
        version_methode=VERSION_METHODE,
        points=resultat.points,
        synthese=_synthese(resultat),
        carte=carte_svg.dessiner(resultat.contour, resultat.voies_bus, resultat.points),
        sources=sources,
        avertissements=resultat.avertissements,
        ia=journal.ia if journal.ia.modele else None,
        donnees_json=_json_dans_html({"points": points_dict}),
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
