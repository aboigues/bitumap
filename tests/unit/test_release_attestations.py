"""Structure du job d'attestation du workflow release.

L'attestation n'est produite qu'au push d'un tag : ces tests empêchent de la casser sans le
voir avant la version suivante, quand scripts/deploiement/digests.sh refuserait de reporter
les digests. Ils ne prouvent pas que l'attestation fonctionne ; seul un tag le montre.
"""

import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
RELEASE = REPO / ".github" / "workflows" / "release.yml"


@pytest.fixture(scope="module")
def jobs():
    return yaml.safe_load(RELEASE.read_text())["jobs"]


def _etape_attest(job):
    etapes = [e for e in job["steps"] if e.get("uses", "").startswith("actions/attest@")]
    assert len(etapes) == 1, "une et une seule étape actions/attest attendue"
    return etapes[0]


def test_attestation_de_chaque_image(jobs):
    job = jobs["attestations"]
    assert job["needs"] == "images"
    assert job["strategy"]["matrix"]["nom"] == ["api", "job"]


def test_droits_minimaux_et_aucun_secret(jobs):
    job = jobs["attestations"]
    assert job["permissions"] == {"id-token": "write", "attestations": "write"}
    assert "secrets." not in yaml.safe_dump(job), "le job d'attestation ne lit aucun secret"
    # Le jeton OIDC n'est jamais disponible là où se trouve la clé du registre.
    assert "id-token" not in jobs["images"]["permissions"]


def test_action_epinglee_par_sha(jobs):
    uses = _etape_attest(jobs["attestations"])["uses"]
    assert re.fullmatch(r"actions/attest@[0-9a-f]{40}", uses), uses


def test_digest_atteste_est_celui_publie(jobs):
    images = jobs["images"]
    sorties = images["outputs"]
    assert sorties["digest-api"] == "${{ steps.publication.outputs.digest-api }}"
    assert sorties["digest-job"] == "${{ steps.publication.outputs.digest-job }}"
    publication = next(e for e in images["steps"] if e.get("id") == "publication")
    assert 'echo "digest-${nom}=${digest##*@}" >> "$GITHUB_OUTPUT"' in publication["run"]

    entrees = _etape_attest(jobs["attestations"])["with"]
    assert entrees["subject-name"] == "${{ vars.BITUMAP_REGISTRE }}/${{ matrix.nom }}"
    digest = entrees["subject-digest"]
    assert "matrix.nom == 'api'" in digest
    assert "needs.images.outputs.digest-api" in digest
    assert "needs.images.outputs.digest-job" in digest


def test_version_creee_apres_les_attestations(jobs):
    assert "attestations" in jobs["publish"]["needs"]
