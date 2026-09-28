"""Calcul d'une commune : sources → points → facteurs → priorités (méthode 1.0).

Fonction déterministe à sources identiques (principe IV) ; le seul appel non déterministe,
l'âge de l'enrobé par IA, est injecté (``analyse_ia``) et mis en cache ailleurs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import geopandas as gpd
from shapely.geometry import Point as PointGeo
from shapely.geometry import mapping

from bitumap.facteurs import chaleur, charge, ensoleillement, site, sollicitation, voirie
from bitumap.modele import Facteur, Point
from bitumap.points import construction as c
from bitumap.score import combinaison
from bitumap.sources import idfm, osm
from bitumap.sources.base import Provenance
from bitumap.sources.fournisseur import Fournisseur

MARGE_EMPRISE_DEG = 0.003  # ≈ 250 m autour de la commune
DISTANCE_PENTE_M = 30
DISTANCE_CHAUSSEE_M = 30  # au-delà, le point est gardé tel quel
RAYON_TRONCON_M = 25


@dataclass
class ResultatCommune:
    insee: str
    nom: str
    points: list[Point]
    voies_bus: list[dict]  # [{"coords": [[lon, lat], …], "charge": float}]
    contour: dict
    provenances: list[Provenance]
    avertissements: list[str] = field(default_factory=list)


def _emprise(commune) -> tuple[float, float, float, float]:
    minx, miny, maxx, maxy = commune.bounds
    m = MARGE_EMPRISE_DEG
    return (minx - m, miny - m, maxx + m, maxy + m)


def _voie_la_plus_proche(reseau: c.Reseau, geo_l93):
    if reseau.voies.empty:
        return None
    distances = reseau.voies.distance(geo_l93)
    return reseau.voies.loc[distances.idxmin()]


def _points_pente(ligne, geo_l93) -> tuple[tuple[float, float], tuple[float, float]]:
    s = ligne.project(geo_l93)
    a = ligne.interpolate(max(0.0, s - DISTANCE_PENTE_M))
    b = ligne.interpolate(min(ligne.length, s + DISTANCE_PENTE_M))
    return (a.x, a.y), (b.x, b.y)


def _normaliser_nom(nom) -> str:
    texte = "" if nom is None or nom != nom else str(nom)
    return "".join(ch for ch in texte.lower() if ch.isalnum())


def _troncon_de_la_voie(troncons_l93, chaussee, voie):
    """Tronçon IGN de la voie empruntée par le bus : parmi les tronçons à moins de 25 m de la
    chaussée, celui qui porte le nom de la voie bus (OSM), sinon le plus proche."""
    distances = troncons_l93.distance(chaussee)
    proches = troncons_l93[distances <= RAYON_TRONCON_M]
    nom = _normaliser_nom(voie.nom) if voie is not None else ""
    if nom and not proches.empty:
        memes = proches[
            proches.get("nom_voie_ban_gauche", "").map(_normaliser_nom).eq(nom)
            | proches.get("nom_voie_ban_droite", "").map(_normaliser_nom).eq(nom)
        ]
        if not memes.empty:
            return memes.loc[memes.distance(chaussee).idxmin()]
    return troncons_l93.loc[distances.idxmin()]


def calculer_commune(
    f: Fournisseur,
    nom_commune: str,
    analyse_ia: Callable[[list[Point]], None] | None = None,
) -> ResultatCommune:
    avertissements: list[str] = []
    contour = f.contour()
    commune = c.polygone_commune(contour)
    commune_l93 = gpd.GeoSeries([commune], crs="EPSG:4326").to_crs(c.L93).iloc[0]
    emprise = _emprise(commune)

    prov_offre, lignes_offre = f.offre()
    offre = idfm.agreger(lignes_offre)
    prov_osm, donnees_osm = f.osm(emprise)
    reseau = c.reseau_bus(donnees_osm.voies_bus, commune, c.charge_des_lignes(offre))

    points = (
        c.arrets(offre, reseau, commune_l93)
        + c.carrefours_a_feux(donnees_osm.feux, reseau, commune_l93)
        + c.giratoires(donnees_osm.giratoires, reseau, commune_l93)
    )
    provenances = [prov_offre, prov_osm]
    if not points:
        avertissements.append("Aucun point à relever : aucune ligne de bus desservant la commune.")
        return ResultatCommune(f.insee, nom_commune, [], [], contour, provenances, avertissements)

    distances_feux = c.distance_carrefour_le_plus_proche(points)
    geos = gpd.GeoSeries([PointGeo(p.lon, p.lat) for p in points], crs="EPSG:4326")
    geos_l93 = geos.to_crs(c.L93)

    # BD TOPO : type de route (tronçon le plus proche) et bâtiments (ombres).
    try:
        prov_bdtopo, bdtopo = f.bdtopo(emprise)
        provenances.append(prov_bdtopo)
        troncons_l93 = bdtopo["troncons"].to_crs(c.L93)
        batiments_l93 = bdtopo["batiments"].to_crs(c.L93)
    except Exception as erreur:  # source optionnelle pour l'ensoleillement
        avertissements.append(f"BD TOPO indisponible : {type(erreur).__name__}")
        troncons_l93 = batiments_l93 = None

    # Îlots de chaleur.
    try:
        prov_chaleur, icu = f.chaleur(emprise)
        provenances.append(prov_chaleur)
        # Un arrêt sur la chaussée tombe souvent entre deux îlots (la voirie en est exclue) :
        # îlot le plus proche à moins de 50 m, comme le prototype.
        jointure = (
            gpd.sjoin_nearest(
                gpd.GeoDataFrame(geometry=geos_l93),
                icu.to_crs(c.L93),
                how="left",
                max_distance=50,
            )
            .groupby(level=0)
            .first()
        )
    except Exception as erreur:
        avertissements.append(f"Îlots de chaleur indisponibles : {type(erreur).__name__}")
        jointure = None

    # Pentes : altitude à ±30 m le long de la voie bus la plus proche.
    voies_proches = [_voie_la_plus_proche(reseau, g) for g in geos_l93]
    extremites = []
    for voie, g in zip(voies_proches, geos_l93, strict=True):
        extremites += (
            list(_points_pente(voie.geometry, g))
            if voie is not None
            else [
                (g.x, g.y),
                (g.x, g.y),
            ]
        )
    extremites_wgs = gpd.GeoSeries([PointGeo(x, y) for x, y in extremites], crs=c.L93).to_crs(
        "EPSG:4326"
    )
    try:
        altitudes = f.altitudes([(round(p.x, 6), round(p.y, 6)) for p in extremites_wgs])
    except Exception as erreur:
        avertissements.append(f"Altimétrie indisponible : {type(erreur).__name__}")
        altitudes = [None] * len(extremites)

    for i, (p, g, voie) in enumerate(zip(points, geos_l93, voies_proches, strict=True)):
        p.facteurs.append(charge.calculer(p))
        p.facteurs += sollicitation.calculer(p, distances_feux.get(p.id))

        z1, z2 = altitudes[2 * i], altitudes[2 * i + 1]
        longueur = PointGeo(extremites[2 * i]).distance(PointGeo(extremites[2 * i + 1]))
        pente = abs(z2 - z1) / longueur * 100 if None not in (z1, z2) and longueur > 10 else None
        p.facteurs.append(site.pente(pente))
        surface = str(voie.surface) if voie is not None else ""
        p.facteurs.append(site.revetement(surface, osm.est_rigide(surface)))
        if voie is not None and (ouvrage := site.ouvrage(bool(voie.pont))):
            p.facteurs.append(ouvrage)

        vegetation = None
        try:
            vegetation = f.vegetation(round(p.lon, 6), round(p.lat, 6))
        except Exception:
            avertissements.append(f"Infrarouge indisponible pour {p.id}")
        # Ensoleillement mesuré sur la chaussée (voie bus la plus proche), pas au poteau.
        chaussee = g
        if voie is not None and voie.geometry.distance(g) <= DISTANCE_CHAUSSEE_M:
            chaussee = voie.geometry.interpolate(voie.geometry.project(g))
        vegetation = ensoleillement.decaler(vegetation, chaussee.x - g.x, chaussee.y - g.y)
        p.facteurs.append(
            ensoleillement.calculer(p.lon, p.lat, chaussee.x, chaussee.y, batiments_l93, vegetation)
        )

        if jointure is not None:
            ligne = jointure.loc[i]
            alea = ligne.get("aleaj_note")
            alea = None if alea is None or alea != alea else float(alea)  # NaN → None
            p.facteurs.append(chaleur.calculer(alea, ligne.get("type_lcz")))
        else:
            p.facteurs.append(chaleur.calculer(None, None))

        if troncons_l93 is not None and not troncons_l93.empty:
            t = _troncon_de_la_voie(troncons_l93, chaussee, voie)
            p.route = voirie.determiner(
                t.get("cpx_classement_administratif"),
                t.get("cpx_gestionnaire"),
                t.get("cpx_numero"),
                str(voie.ref) if voie is not None and voie.ref else None,
                nom_commune,
            )
        try:
            photo = f.panoramax(round(p.lon, 6), round(p.lat, 6))
            p.panoramax = None if photo is None else photo.__dict__
        except Exception:
            avertissements.append(f"Panoramax indisponible pour {p.id}")

    points = combinaison.prioriser(points)
    if analyse_ia is not None:
        analyse_ia([p for p in points if p.priorite == "P1"])
    else:
        for p in points:
            if p.priorite == "P1":
                p.facteurs.append(
                    Facteur(
                        combinaison.FACTEUR_IA,
                        None,
                        1.0,
                        provenance="ia",
                        statut="non_evalue",
                        explication="Âge de l'enrobé non évalué",
                    )
                )
    points = combinaison.finaliser(points)

    geometries = reseau.voies.to_crs("EPSG:4326").geometry
    voies = [
        {"coords": [list(pt) for pt in mapping(g)["coordinates"]], "charge": round(ch)}
        for g, ch in zip(geometries, reseau.voies.charge, strict=True)
        if ch > 0
    ]
    provenances += f.provenances_ponctuelles()
    return ResultatCommune(
        f.insee, nom_commune, points, voies, contour, provenances, avertissements
    )
