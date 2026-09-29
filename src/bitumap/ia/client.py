"""Client vision Scaleway Generative APIs (API compatible OpenAI, hébergée en France)."""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass

from openai import OpenAI
from PIL import Image
from pydantic import BaseModel, Field

from bitumap.config import reglages


class ReponseAge(BaseModel):
    derniere_refection_debut: int | None = Field(default=None, ge=1990, le=2100)
    derniere_refection_fin: int | None = Field(default=None, ge=1990, le=2100)
    statut: str = Field(pattern="^(visible|marquage|indetermine)$")
    confiance: float = Field(ge=0, le=1)
    justification: str = Field(max_length=300)


@dataclass
class Appel:
    reponse: ReponseAge | None
    brut: str
    jetons_entree: int
    jetons_sortie: int


def _image_en_url(img: Image.Image) -> str:
    tampon = io.BytesIO()
    img.save(tampon, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(tampon.getvalue()).decode()


def analyser(
    prompt: str,
    vignettes: list[tuple[int, Image.Image]],
    client: OpenAI | None = None,
    modele: str | None = None,
) -> Appel:
    """Un appel au modèle configuré (``modele`` le remplace, pour l'évaluation T072)."""
    r = reglages()
    client = client or OpenAI(
        base_url=r.ia_url, api_key=r.genai_cle.get_secret_value() if r.genai_cle else "absente"
    )
    contenu: list[dict] = [{"type": "text", "text": prompt}]
    for annee, img in vignettes:
        contenu.append({"type": "text", "text": f"Année {annee} :"})
        contenu.append({"type": "image_url", "image_url": {"url": _image_en_url(img)}})
    reponse = client.chat.completions.create(
        model=modele or r.ia_modele,
        messages=[{"role": "user", "content": contenu}],
        temperature=0,
        max_tokens=MAX_JETONS_SORTIE,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "age_enrobe", "schema": ReponseAge.model_json_schema()},
        },
        timeout=60,
    )
    brut = reponse.choices[0].message.content or ""
    try:
        valide = ReponseAge.model_validate_json(brut)
    except ValueError:
        valide = None  # réponse hors schéma : point « non évalué »
    usage = reponse.usage
    return Appel(
        valide, brut, getattr(usage, "prompt_tokens", 0), getattr(usage, "completion_tokens", 0)
    )


MAX_JETONS_SORTIE = 300
