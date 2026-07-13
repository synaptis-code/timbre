"""Fabrique de l'application FastAPI."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from timbre import __version__
from timbre.api.rest import router as rest_router
from timbre.api.ws import router as ws_router
from timbre.config import Settings
from timbre.core.orchestrator import Orchestrator
from timbre.personas.models import Persona, VoiceConfig
from timbre.personas.repository import PersonaRepository
from timbre.plugins.asr.whisper import FasterWhisperASR
from timbre.plugins.base import ASRBackend, LLMBackend, TTSBackend
from timbre.plugins.llm.providers import ProviderManager
from timbre.plugins.tts.edge import EdgeTTSBackend
from timbre.plugins.tts.library import VoiceLibrary
from timbre.plugins.tts.piper import PiperTTSBackend, piper_installed
from timbre.storage import Storage


def create_app(
    llm: LLMBackend | None = None,
    tts: TTSBackend | None = None,
    asr: ASRBackend | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    """`llm`, `tts`, `asr` et `settings` sont injectables pour les tests.

    Par défaut : LM Studio (modèle chargé auto-détecté) + edge-tts + faster-whisper.
    `tts` injecté est enregistré sous le nom de moteur « edge-tts ».
    """
    app_settings = settings if settings is not None else Settings()
    tts_backend = (
        tts if tts is not None else (EdgeTTSBackend() if app_settings.tts_enabled else None)
    )
    tts_engines: dict[str, TTSBackend] = {"edge-tts": tts_backend} if tts_backend else {}
    # Moteur Piper local : enregistré d'emblée si le paquet est déjà présent
    # (les voix se chargent paresseusement). Sinon il sera ajouté à chaud après
    # le premier téléchargement depuis la catégorie « Voix ».
    piper_dir = Path(app_settings.piper_voices_dir)
    if piper_installed():
        tts_engines["piper"] = PiperTTSBackend(piper_dir)
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

    fallback_persona = Persona(
        id="defaut",
        name="Défaut",
        system_prompt=app_settings.system_prompt,
        voice=VoiceConfig(voice_id=app_settings.tts_voice),
    )

    storage = Storage(Path(app_settings.database_path))
    llm_manager = ProviderManager(storage, app_settings, override=llm)
    personas = PersonaRepository(storage, fallback=fallback_persona)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await storage.connect()
        await llm_manager.reload()
        yield
        await storage.aclose()
        await llm_manager.aclose()

    app = FastAPI(title="Timbre", version=__version__, lifespan=lifespan)
    # L'UI de dev (Vite) tourne sur un autre port : autoriser les appels REST locaux.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    orchestrator = Orchestrator(
        llm_manager=llm_manager,
        tts_engines=tts_engines,
        asr=asr_backend,
        personas=personas,
        default_persona_id=app_settings.persona,
        fallback_persona=fallback_persona,
    )
    app.state.settings = app_settings
    app.state.storage = storage
    app.state.llm_manager = llm_manager
    app.state.orchestrator = orchestrator
    app.state.voice_library = VoiceLibrary(
        piper_dir,
        on_engine_ready=lambda: orchestrator.register_tts_engine(
            "piper", PiperTTSBackend(piper_dir)
        ),
    )
    app.include_router(ws_router)
    app.include_router(rest_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    return app
