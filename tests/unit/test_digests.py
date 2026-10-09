"""Report vérifié des digests dans terraform.tfvars (scripts/deploiement/digests.sh).

gh et scw sont remplacés par de faux outils qui servent les réponses d'un dossier ; chaque
appel à « gh attestation verify » est journalisé pour contrôler les identités exigées.
"""

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "deploiement" / "digests.sh"

DEPOT = "exemple/bitumap"
TAG = "v9.9.9"
COMMIT = "c" * 40
API = "sha256:" + "a" * 64
JOB = "sha256:" + "b" * 64
ANCIEN_API = "sha256:" + "1" * 64
ANCIEN_JOB = "sha256:" + "2" * 64
SECRET = 'cle_secrete = "ne-doit-jamais-etre-affiche"'

FAUX_GH = r"""#!/usr/bin/env bash
d="$FAUX_DIR"
case "$1 $2" in
  "repo view") cat "$d/depot" ;;
  "release view") cat "$d/release.json" ;;
  "run list") cat "$d/run.json" ;;
  "attestation verify") echo "$*" >> "$d/attestations.log"; exit "$(cat "$d/attestation_code")" ;;
  *)
    if [ "$1" = api ]; then
      case "$2" in
        */git/ref/tags/*) cat "$d/ref.json" ;;
        */git/tags/*) cat "$d/tag_annote" ;;
      esac
    else
      echo "gh inattendu : $*" >&2; exit 2
    fi ;;
esac
"""

FAUX_SCW = r"""#!/usr/bin/env bash
d="$FAUX_DIR"
shift 2   # -p <profil>
case "$1 $2 $3" in
  "registry namespace list") cat "$d/namespace.json" ;;
  "registry image list")
    for a in "$@"; do case "$a" in name=*) cat "$d/image_${a#name=}.json" ;; esac; done ;;
  "registry tag list")
    for a in "$@"; do case "$a" in image-id=*) cat "$d/tags_${a#image-id=}.json" ;; esac; done ;;
  *) echo "scw inattendu : $*" >&2; exit 2 ;;
esac
"""


def _executable(chemin: Path, contenu: str) -> None:
    chemin.write_text(contenu)
    chemin.chmod(chemin.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def faux(tmp_path):
    """Dossier de réponses cohérentes (version valide) et terraform.tfvars d'origine."""
    d = tmp_path / "faux"
    d.mkdir()
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    _executable(bin_ / "gh", FAUX_GH)
    _executable(bin_ / "scw", FAUX_SCW)

    (d / "depot").write_text(DEPOT + "\n")
    notes = f"## Images\n\n- api : `bitumap-api@{API}`\n- job : `bitumap-job@{JOB}`\n"
    (d / "release.json").write_text(json.dumps({"isDraft": False, "body": notes}))
    (d / "ref.json").write_text(json.dumps({"object": {"sha": COMMIT, "type": "commit"}}))
    (d / "run.json").write_text(
        json.dumps({"conclusion": "success", "headSha": COMMIT, "databaseId": 1})
    )
    (d / "attestation_code").write_text("0")
    (d / "namespace.json").write_text(
        json.dumps([{"id": "ns", "name": "bitumap", "endpoint": "rg.exemple/bitumap"}])
    )
    for nom, digest in (("api", API), ("job", JOB)):
        (d / f"image_{nom}.json").write_text(json.dumps([{"id": f"id-{nom}", "name": nom}]))
        (d / f"tags_id-{nom}.json").write_text(
            json.dumps([{"name": TAG, "digest": digest, "status": "ready"}])
        )

    tfvars = tmp_path / "terraform.tfvars"
    tfvars.write_text(
        f'projet = "x"\ndigest_api = "{ANCIEN_API}"\ndigest_job = "{ANCIEN_JOB}"\n{SECRET}\n'
    )
    tfvars.chmod(0o600)

    env = {
        "PATH": f"{bin_}{os.pathsep}{os.environ['PATH']}",
        "HOME": str(tmp_path),
        "FAUX_DIR": str(d),
        "BITUMAP_TFVARS": str(tfvars),
    }
    return d, tfvars, env


def lancer(env, *args):
    bash = shutil.which("bash")
    if not bash or not shutil.which("jq"):
        pytest.skip("bash ou jq absent")
    return subprocess.run(
        [bash, str(SCRIPT), *args], env=env, capture_output=True, text=True, check=False
    )


def test_digests_reportes_apres_verification(faux):
    _, tfvars, env = faux
    r = lancer(env, TAG)
    assert r.returncode == 0, r.stderr
    contenu = tfvars.read_text()
    assert f'digest_api = "{API}"' in contenu
    assert f'digest_job = "{JOB}"' in contenu
    assert SECRET in contenu and 'projet = "x"' in contenu
    assert stat.S_IMODE(tfvars.stat().st_mode) == 0o600
    sauvegarde = tfvars.with_name("terraform.tfvars.sauvegarde")
    assert ANCIEN_API in sauvegarde.read_text()
    assert "ne-doit-jamais-etre-affiche" not in r.stdout + r.stderr


def test_provenance_exigee_du_workflow_du_tag(faux):
    d, _, env = faux
    assert lancer(env, TAG).returncode == 0
    appels = (d / "attestations.log").read_text().splitlines()
    assert len(appels) == 2
    for nom, digest, appel in zip(("api", "job"), (API, JOB), appels, strict=True):
        assert f"oci://rg.exemple/bitumap/{nom}@{digest}" in appel
        assert f"--repo {DEPOT}" in appel
        assert f"--signer-workflow github.com/{DEPOT}/.github/workflows/release.yml" in appel
        assert f"--source-ref refs/tags/{TAG}" in appel
        assert f"--source-digest {COMMIT}" in appel
        assert "--deny-self-hosted-runners" in appel


def _inchange(tfvars):
    contenu = tfvars.read_text()
    return ANCIEN_API in contenu and ANCIEN_JOB in contenu


def test_attestation_invalide_refusee(faux):
    d, tfvars, env = faux
    (d / "attestation_code").write_text("1")
    r = lancer(env, TAG)
    assert r.returncode != 0
    assert "provenance" in r.stderr
    assert _inchange(tfvars)


def test_digest_divergent_du_registre_refuse(faux):
    d, tfvars, env = faux
    autre = "sha256:" + "f" * 64
    (d / "tags_id-job.json").write_text(
        json.dumps([{"name": TAG, "digest": autre, "status": "ready"}])
    )
    r = lancer(env, TAG)
    assert r.returncode != 0
    assert "divergent" in r.stderr
    assert _inchange(tfvars)
    assert not (d / "attestations.log").exists()


@pytest.mark.parametrize(
    ("fichier", "contenu", "message"),
    [
        ("release.json", {"isDraft": True, "body": ""}, "brouillon"),
        ("run.json", {"conclusion": "failure", "headSha": COMMIT}, "non réussi"),
        ("run.json", {"conclusion": "success", "headSha": "d" * 40}, "autre commit"),
    ],
)
def test_version_ou_workflow_douteux_refuse(faux, fichier, contenu, message):
    d, tfvars, env = faux
    (d / fichier).write_text(json.dumps(contenu))
    r = lancer(env, TAG)
    assert r.returncode != 0
    assert message in r.stderr
    assert _inchange(tfvars)


def test_tag_annote_suivi_jusqu_au_commit(faux):
    d, _, env = faux
    (d / "ref.json").write_text(json.dumps({"object": {"sha": "e" * 40, "type": "tag"}}))
    (d / "tag_annote").write_text(COMMIT + "\n")
    assert lancer(env, TAG).returncode == 0


def test_sans_attestation_reserve_aux_anciennes_versions(faux):
    _, tfvars, env = faux
    r = lancer(env, TAG, "--sans-attestation")
    assert r.returncode != 0
    assert "réservé" in r.stderr
    assert _inchange(tfvars)


def test_relance_sans_modification(faux):
    _, tfvars, env = faux
    assert lancer(env, TAG).returncode == 0
    apres = tfvars.read_text()
    r = lancer(env, TAG)
    assert r.returncode == 0
    assert "déjà à jour" in r.stdout
    assert tfvars.read_text() == apres


@pytest.mark.parametrize("args", [(), ("0.1.3",), (TAG, "--autre"), (TAG, "a", "b")])
def test_arguments_invalides(faux, args):
    _, tfvars, env = faux
    assert lancer(env, *args).returncode != 0
    assert _inchange(tfvars)
