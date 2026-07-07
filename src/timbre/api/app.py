"""Fabrique de l'application FastAPI."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from timbre import __version__
from timbre.api.ws import router as ws_router
from timbre.config import Settings
from timbre.core.orchestrator import Orchestrator
from timbre.plugins.base import LLMBackend
from timbre.plugins.llm.lmstudio import LMStudioBackend


def create_app(llm: LLMBackend | None = None, settings: Settings | None = None) -> FastAPI:
    """`llm` et `settings` sont injectables pour les tests ; par défaut : LM Studio."""
    app_settings = settings if settings is not None else Settings()
    llm_backend = (
        llm
        if llm is not None
        else LMStudioBackend(
            app_settings.lmstudio_base_url,
            model_override=app_settings.llm_model,
            temperature=app_settings.llm_temperature,
        )
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await llm_backend.aclose()

    app = FastAPI(title="Timbre", version=__version__, lifespan=lifespan)
    app.state.settings = app_settings
    app.state.orchestrator = Orchestrator(llm=llm_backend)
    app.include_router(ws_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    return app
