"""Fabrique de l'application FastAPI."""

from fastapi import FastAPI

from timbre import __version__
from timbre.api.ws import router as ws_router


def create_app() -> FastAPI:
    app = FastAPI(title="Timbre", version=__version__)
    app.include_router(ws_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    return app
