"""Application FastAPI (contracts/http-api.md)."""

from bitumap.api.application import creer_application

app = creer_application()

__all__ = ["app", "creer_application"]
