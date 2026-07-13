"""API REST : conversations, historique, réglages, fournisseurs d'IA.

Tout est persisté en SQLite local — les clés API ne quittent jamais la
machine et ne sont jamais renvoyées par l'API (seulement un indicateur).
"""

import re

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, ValidationError

from timbre.personas.models import Persona, VoiceConfig, VoiceParams
from timbre.plugins.base import LLMError, TTSError
from timbre.plugins.llm.providers import (
    ACTIVE_KEY,
    PROVIDERS,
    SPECS_BY_ID,
    ProviderManager,
    config_key,
)
from timbre.plugins.tts.library import VoiceLibrary
from timbre.plugins.tts.piper import SPECS_BY_ID as PIPER_SPECS_BY_ID
from timbre.storage import ConversationMeta, Storage, StoredMessage

router = APIRouter(prefix="/api")


def _storage(request: Request) -> Storage:
    storage: Storage = request.app.state.storage
    return storage


def _manager(request: Request) -> ProviderManager:
    manager: ProviderManager = request.app.state.llm_manager
    return manager


@router.get("/conversations")
async def list_conversations(request: Request) -> list[ConversationMeta]:
    return await _storage(request).list_conversations()


@router.post("/conversations", status_code=201)
async def create_conversation(request: Request) -> ConversationMeta:
    return await _storage(request).create_conversation()


class RenamePayload(BaseModel):
    title: str = Field(min_length=1, max_length=120)


@router.patch("/conversations/{conversation_id}")
async def rename_conversation(
    request: Request, conversation_id: str, payload: RenamePayload
) -> ConversationMeta:
    storage = _storage(request)
    if not await storage.rename_conversation(conversation_id, payload.title):
        raise HTTPException(status_code=404, detail="Conversation introuvable.")
    meta = await storage.get_conversation(conversation_id)
    assert meta is not None
    return meta


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(request: Request, conversation_id: str) -> None:
    if not await _storage(request).delete_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation introuvable.")


@router.get("/conversations/{conversation_id}/messages")
async def list_messages(request: Request, conversation_id: str) -> list[StoredMessage]:
    storage = _storage(request)
    if await storage.get_conversation(conversation_id) is None:
        raise HTTPException(status_code=404, detail="Conversation introuvable.")
    return await storage.list_messages(conversation_id)


class ProviderInfo(BaseModel):
    id: str
    name: str
    description: str
    local: bool
    needs_key: bool
    base_url: str
    model: str | None
    has_key: bool


class ProvidersState(BaseModel):
    active: str
    providers: list[ProviderInfo]


async def _providers_state(request: Request) -> ProvidersState:
    manager = _manager(request)
    storage = _storage(request)
    infos = []
    for spec in PROVIDERS:
        base_url, api_key, model = await manager.config(spec)
        infos.append(
            ProviderInfo(
                id=spec.id,
                name=spec.name,
                description=spec.description,
                local=spec.local,
                needs_key=spec.needs_key,
                base_url=base_url,
                model=model,
                has_key=api_key is not None,
            )
        )
    active = await storage.get_setting(ACTIVE_KEY, "lmstudio")
    return ProvidersState(active=active, providers=infos)


@router.get("/providers")
async def get_providers(request: Request) -> ProvidersState:
    return await _providers_state(request)


class ActiveProviderPayload(BaseModel):
    provider: str


# Déclaré AVANT /providers/{provider_id} : sinon « active » serait pris pour un id.
@router.put("/providers/active")
async def set_active_provider(request: Request, payload: ActiveProviderPayload) -> ProvidersState:
    spec = SPECS_BY_ID.get(payload.provider)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Fournisseur inconnu : {payload.provider}")
    manager = _manager(request)
    _base_url, api_key, model = await manager.config(spec)
    if spec.needs_key and api_key is None:
        raise HTTPException(status_code=400, detail=f"Renseigne d'abord la clé API de {spec.name}.")
    if spec.kind != "lmstudio" and model is None:
        raise HTTPException(status_code=400, detail=f"Choisis d'abord un modèle pour {spec.name}.")
    await _storage(request).set_setting(ACTIVE_KEY, spec.id)
    await manager.reload()
    return await _providers_state(request)


class ProviderConfigPayload(BaseModel):
    """Champs à mettre à jour ; chaîne vide = effacer la valeur."""

    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None


@router.put("/providers/{provider_id}")
async def update_provider(
    request: Request, provider_id: str, payload: ProviderConfigPayload
) -> ProvidersState:
    spec = SPECS_BY_ID.get(provider_id)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Fournisseur inconnu : {provider_id}")
    storage = _storage(request)
    for field in ("api_key", "base_url", "model"):
        value = getattr(payload, field)
        if value is not None:
            await storage.set_setting(config_key(provider_id, field), value.strip())
    if await storage.get_setting(ACTIVE_KEY, "lmstudio") == provider_id:
        await _manager(request).reload()
    return await _providers_state(request)


class ModelsQuery(BaseModel):
    """Config ad-hoc pour lister les modèles sans la persister (clé jamais en URL)."""

    api_key: str | None = None
    base_url: str | None = None


class ModelsResponse(BaseModel):
    models: list[str]


@router.post("/providers/{provider_id}/models")
async def list_provider_models(
    request: Request, provider_id: str, query: ModelsQuery | None = None
) -> ModelsResponse:
    if provider_id not in SPECS_BY_ID:
        raise HTTPException(status_code=404, detail=f"Fournisseur inconnu : {provider_id}")
    payload = query or ModelsQuery()
    try:
        models = await _manager(request).list_models(
            provider_id,
            api_key=payload.api_key or None,
            base_url=payload.base_url or None,
        )
        return ModelsResponse(models=models)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc


# ── Personas ─────────────────────────────────────────────────────────────

class VoiceOption(BaseModel):
    """Une voix sélectionnable dans l'éditeur de personas (moteur + identifiant)."""

    id: str
    label: str
    engine: str


# Voix cloud edge-tts toujours disponibles (le moteur ne pèse rien en local).
EDGE_VOICES: list[VoiceOption] = [
    VoiceOption(
        id="fr-FR-VivienneMultilingualNeural", label="Vivienne · Multilingue", engine="edge-tts"
    ),
]


def _library(request: Request) -> VoiceLibrary:
    library: VoiceLibrary = request.app.state.voice_library
    return library


@router.get("/voices")
def list_voices(request: Request) -> list[VoiceOption]:
    """Voix sélectionnables = Vivienne + voix Piper effectivement téléchargées."""
    ready = _library(request).ready_voice_ids()
    piper = [
        VoiceOption(id=vid, label=f"{PIPER_SPECS_BY_ID[vid].label} · Piper", engine="piper")
        for vid in ready
    ]
    return [*EDGE_VOICES, *piper]


class PiperVoiceInfo(BaseModel):
    id: str
    label: str
    gender: str
    size_bytes: int
    recommended: bool
    status: str  # available | downloading | ready | error
    received: int
    error: str | None


class PiperLibrary(BaseModel):
    package_installed: bool
    voices: list[PiperVoiceInfo]


def _piper_library(request: Request) -> PiperLibrary:
    library = _library(request)
    return PiperLibrary(
        package_installed=library.package_installed,
        voices=[PiperVoiceInfo(**vars(state)) for state in library.voice_states()],
    )


@router.get("/voices/piper")
def get_piper_library(request: Request) -> PiperLibrary:
    return _piper_library(request)


@router.post("/voices/piper/{voice_id}/download", status_code=202)
async def download_piper_voice(request: Request, voice_id: str) -> PiperLibrary:
    try:
        await _library(request).start_download(voice_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Voix Piper inconnue.") from exc
    except TTSError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return _piper_library(request)


@router.delete("/voices/piper/{voice_id}")
def delete_piper_voice(request: Request, voice_id: str) -> PiperLibrary:
    try:
        _library(request).delete_voice(voice_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Voix Piper inconnue.") from exc
    return _piper_library(request)


_PREVIEW_TEXT = "Bonjour ! Voici un aperçu de ma voix."


@router.get("/voices/{voice_id}/preview")
async def preview_voice(request: Request, voice_id: str) -> Response:
    """Synthétise une courte phrase avec la voix demandée (aperçu à l'écoute)."""
    orchestrator = request.app.state.orchestrator
    engine_name = "piper" if voice_id in PIPER_SPECS_BY_ID else "edge-tts"
    engine = orchestrator.tts_engine(engine_name)
    if engine is None:
        raise HTTPException(
            status_code=400,
            detail="Moteur de voix indisponible (voix non téléchargée ?).",
        )
    try:
        audio = b"".join([chunk async for chunk in engine.synthesize(_PREVIEW_TEXT, voice_id)])
    except TTSError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    media_type = "audio/wav" if engine.audio_format == "wav" else "audio/mpeg"
    return Response(content=audio, media_type=media_type)


class PersonaPayload(BaseModel):
    """Champs éditables d'un persona (l'id est dérivé du nom à la création)."""

    name: str = Field(min_length=1, max_length=48)
    system_prompt: str = Field(min_length=1)
    voice_id: str = Field(min_length=1)
    rate: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch: int = Field(default=0, ge=-50, le=50)
    greeting: str = ""
    temperature: float = Field(default=0.8, ge=0.0, le=2.0)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:32]
    return slug or "persona"


def _build_persona(persona_id: str, payload: PersonaPayload) -> Persona:
    # Le moteur découle de la voix choisie : une voix Piper → moteur « piper »,
    # sinon edge-tts (Vivienne). L'UI n'a pas à gérer le moteur explicitement.
    engine = "piper" if payload.voice_id in PIPER_SPECS_BY_ID else "edge-tts"
    return Persona(
        id=persona_id,
        name=payload.name,
        system_prompt=payload.system_prompt,
        voice=VoiceConfig(
            engine=engine,
            voice_id=payload.voice_id,
            params=VoiceParams(rate=payload.rate, pitch=payload.pitch),
        ),
        greeting=payload.greeting,
        temperature=payload.temperature,
    )


@router.get("/personas")
async def list_personas(request: Request) -> list[Persona]:
    return await _storage(request).list_personas()


@router.post("/personas", status_code=201)
async def create_persona(request: Request, payload: PersonaPayload) -> Persona:
    storage = _storage(request)
    base = _slugify(payload.name)
    persona_id = base
    suffix = 2
    while await storage.persona_exists(persona_id):
        persona_id = f"{base}-{suffix}"
        suffix += 1
    try:
        persona = _build_persona(persona_id, payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await storage.upsert_persona(persona, is_new=True)
    return persona


@router.put("/personas/{persona_id}")
async def update_persona(request: Request, persona_id: str, payload: PersonaPayload) -> Persona:
    storage = _storage(request)
    if not await storage.persona_exists(persona_id):
        raise HTTPException(status_code=404, detail="Persona introuvable.")
    try:
        persona = _build_persona(persona_id, payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await storage.upsert_persona(persona, is_new=False)
    return persona


@router.delete("/personas/{persona_id}", status_code=204)
async def delete_persona(request: Request, persona_id: str) -> None:
    storage = _storage(request)
    if await storage.count_personas() <= 1:
        raise HTTPException(status_code=400, detail="Impossible de supprimer le dernier persona.")
    if not await storage.delete_persona(persona_id):
        raise HTTPException(status_code=404, detail="Persona introuvable.")


class SettingsPayload(BaseModel):
    language: str = Field(min_length=2, max_length=8)


@router.get("/settings")
async def get_settings(request: Request) -> SettingsPayload:
    return SettingsPayload(language=await _storage(request).get_setting("language", "fr"))


@router.put("/settings")
async def put_settings(request: Request, payload: SettingsPayload) -> SettingsPayload:
    await _storage(request).set_setting("language", payload.language)
    return payload
