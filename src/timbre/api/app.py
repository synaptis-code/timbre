"""Fabrique de l'application FastAPI."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from timbre import __version__
from timbre.api.ws import router as ws_router
from timbre.config import Settings
from timbre.core.orchestrator import Orchestrator
from timbre.plugins.asr.whisper import FasterWhisperASR
from timbre.plugins.base import ASRBackend, LLMBackend, TTSBackend
from timbre.plugins.llm.lmstudio import LMStudioBackend
from timbre.plugins.tts.edge import EdgeTTSBackend


def create_app(
    llm: LLMBackend | None = None,
    tts: TTSBackend | None = None,
    asr: ASRBackend | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    """`llm`, `tts`, `asr` et `settings` sont injectables pour les tests.

    Par défaut : LM Studio (modèle chargé auto-détecté) + edge-tts + faster-whisper.
    """
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
    tts_backend = (
        tts if tts is not None else (EdgeTTSBackend() if app_settings.tts_enabled else None)
    )
    asr_backend = (
        asr
        if asr is not None
        else (
            FasterWhisperASR(
                model=app_settings.asr_model,
                device=app_settings.asr_device,
                language=app_settings.asr_language,
            )
            if app_settings.asr_enabled
            else None
        )
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await llm_backend.aclose()

    app = FastAPI(title="Timbre", version=__version__, lifespan=lifespan)
    app.state.settings = app_settings
    app.state.orchestrator = Orchestrator(
        llm=llm_backend, tts=tts_backend, tts_voice=app_settings.tts_voice, asr=asr_backend
    )
    app.include_router(ws_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    return app
