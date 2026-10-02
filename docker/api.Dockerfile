# Image api de bitumap (plan 002). Construire depuis la racine du dépôt :
#   docker build -f docker/api.Dockerfile .
# Images de base minimales (Chainguard, Python 3.14) épinglées par digest : quasiment aucun
# paquet système, donc presque aucune vulnérabilité sans correctif (décision du 2026-09-28).
# L'image d'exécution n'a ni shell ni gestionnaire de paquets et tourne en non-root (65532).

# --- Construction : environnement virtuel complet ---
FROM cgr.dev/chainguard/python:latest-dev@sha256:261ceae8cf0ee5055341cd5c417984a70eb0e1406f2ddf83a4c93002bb10c26c AS construction
USER root
COPY --from=ghcr.io/astral-sh/uv:0.12.19@sha256:04d046b13e60d6bcec73cbc5e1cad25d680dea90c8573340950a0ac2d1aef424 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=/usr/bin/python3.14 \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable --no-cache

# --- Exécution : Python seul + environnement virtuel ---
FROM cgr.dev/chainguard/python:latest@sha256:89281daac77a3d91ef298d70ce3b7a6ccb2ebf268c084fa9a9bda1c92e71c64d
WORKDIR /app
# Propriété root : le code est en lecture seule pour l'utilisateur d'exécution.
COPY --from=construction /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
USER 65532:65532
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/sante', timeout=2)"]
ENTRYPOINT ["uvicorn", "bitumap.api:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log", "--no-server-header"]
