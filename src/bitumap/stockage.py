"""Stockage objet (compatible S3) : rapports immuables et cache des sources (data-model.md)."""

from __future__ import annotations

from functools import lru_cache

import boto3
from botocore.exceptions import ClientError

from bitumap.config import reglages


@lru_cache
def _client():
    r = reglages()
    return boto3.client(
        "s3",
        endpoint_url=r.s3_endpoint,
        region_name=r.s3_region,
        aws_access_key_id=r.s3_cle_acces.get_secret_value() if r.s3_cle_acces else None,
        aws_secret_access_key=r.s3_cle_secrete.get_secret_value() if r.s3_cle_secrete else None,
    )


def ecrire(bucket: str, cle: str, contenu: bytes, type_contenu: str) -> None:
    _client().put_object(Bucket=bucket, Key=cle, Body=contenu, ContentType=type_contenu)


def lire(bucket: str, cle: str) -> bytes | None:
    try:
        return _client().get_object(Bucket=bucket, Key=cle)["Body"].read()
    except ClientError as erreur:
        if erreur.response["Error"]["Code"] in {"NoSuchKey", "404"}:
            return None
        raise


def existe(bucket: str, cle: str) -> bool:
    try:
        _client().head_object(Bucket=bucket, Key=cle)
        return True
    except ClientError as erreur:
        if erreur.response["Error"]["Code"] in {"NoSuchKey", "404"}:
            return False
        raise


def prefixe_rapport(insee: str, empreinte: str) -> str:
    return f"communes/{insee}/{empreinte}/"


def ecrire_rapport(insee: str, empreinte: str, fichiers: dict[str, tuple[bytes, str]]) -> None:
    """Écrit les fichiers d'un rapport ; ``rapport.html`` en dernier (contracts/lot-job.md) :
    sa présence signifie « rapport complet »."""
    bucket = reglages().bucket_rapports
    prefixe = prefixe_rapport(insee, empreinte)
    for nom, (contenu, type_contenu) in fichiers.items():
        if nom != "rapport.html":
            ecrire(bucket, prefixe + nom, contenu, type_contenu)
    if "rapport.html" in fichiers:
        contenu, type_contenu = fichiers["rapport.html"]
        ecrire(bucket, prefixe + "rapport.html", contenu, type_contenu)


def rapport_complet(insee: str, empreinte: str) -> bool:
    return existe(reglages().bucket_rapports, prefixe_rapport(insee, empreinte) + "rapport.html")


def reinitialiser_client() -> None:
    """Pour les tests : force la relecture de la configuration."""
    _client.cache_clear()
