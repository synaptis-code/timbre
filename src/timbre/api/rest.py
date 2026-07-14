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
from timbre.plugins.tts.library import KokoroLibrary, VoiceLibrary
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
EDGE_VOICE_IDS: frozenset[str] = frozenset(v.id for v in EDGE_VOICES)


def voice_engine(voice_id: str) -> str:
    """Moteur d'une voix, déduit de son identifiant.

    Les clés Piper portent un code langue « xx_YY » (underscore), ex.
    « fr_FR-siwis-medium » ; les identifiants edge-tts n'utilisent que des tirets
    (« fr-FR-VivienneMultilingualNeural »). Tout le reste retombe sur edge-tts.
    """
    if voice_id in EDGE_VOICE_IDS:
        return "edge-tts"
    if voice_id.startswith("kokoro-"):
        return "kokoro"
    return "piper" if "_" in voice_id else "edge-tts"


def _library(request: Request) -> VoiceLibrary:
    library: VoiceLibrary = request.app.state.voice_library
    return library


def _kokoro_library(request: Request) -> KokoroLibrary:
    library: KokoroLibrary = request.app.state.kokoro_library
    return library


@router.get("/voices")
async def list_voices(request: Request) -> list[VoiceOption]:
    """Voix = Vivienne + voix Piper téléchargées + voix Kokoro si installé."""
    library = _library(request)
    piper = [
        VoiceOption(id=vid, label=f"{await library.label_for(vid)} · Piper", engine="piper")
        for vid in library.ready_voice_ids()
    ]
    kokoro: list[VoiceOption] = []
    if request.app.state.orchestrator.tts_engine("kokoro") is not None:
        kokoro = [
            VoiceOption(id=v.id, label=f"{v.label} · Kokoro", engine="kokoro")
            for v in _kokoro_library(request).voices()
        ]
    return [*EDGE_VOICES, *piper, *kokoro]


class PiperVoiceInfo(BaseModel):
    id: str
    label: str
    language_code: str
    language_english: str
    language_native: str
    quality: str
    size_bytes: int
    status: str  # available | downloading | ready | error
    received: int
    error: str | None


class PiperLibrary(BaseModel):
    package_installed: bool
    voices: list[PiperVoiceInfo]


async def _piper_library(request: Request) -> PiperLibrary:
    library = _library(request)
    return PiperLibrary(
        package_installed=library.package_installed,
        voices=[PiperVoiceInfo(**vars(state)) for state in await library.voice_states()],
    )


@router.get("/voices/piper")
async def get_piper_library(request: Request) -> PiperLibrary:
    return await _piper_library(request)


@router.post("/voices/piper/{voice_id}/download", status_code=202)
async def download_piper_voice(request: Request, voice_id: str) -> PiperLibrary:
    try:
        await _library(request).start_download(voice_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Voix Piper inconnue.") from exc
    except TTSError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return await _piper_library(request)


@router.delete("/voices/piper/{voice_id}")
async def delete_piper_voice(request: Request, voice_id: str) -> PiperLibrary:
    try:
        _library(request).delete_voice(voice_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Voix Piper inconnue.") from exc
    return await _piper_library(request)


# ── Kokoro (un seul téléchargement débloque toutes les voix) ──────────────────

class KokoroVoiceInfo(BaseModel):
    id: str
    label: str
    gender: str
    language_english: str
    language_native: str


class KokoroLibraryInfo(BaseModel):
    status: str  # available | downloading | ready | error
    received: int
    total: int
    error: str | None
    voices: list[KokoroVoiceInfo]


def _kokoro_info(request: Request) -> KokoroLibraryInfo:
    library = _kokoro_library(request)
    status, received, total, error = library.status()
    return KokoroLibraryInfo(
        status=status,
        received=received,
        total=total,
        error=error,
        voices=[KokoroVoiceInfo(**vars(v)) for v in library.voices()],
    )


@router.get("/voices/kokoro")
def get_kokoro(request: Request) -> KokoroLibraryInfo:
    return _kokoro_info(request)


@router.post("/voices/kokoro/install", status_code=202)
async def install_kokoro(request: Request) -> KokoroLibraryInfo:
    try:
        await _kokoro_library(request).install()
    except TTSError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return _kokoro_info(request)


@router.delete("/voices/kokoro")
def uninstall_kokoro(request: Request) -> KokoroLibraryInfo:
    _kokoro_library(request).uninstall()
    request.app.state.orchestrator.remove_tts_engine("kokoro")
    return _kokoro_info(request)


# Phrase d'aperçu par famille de langue (« Bonjour, voici un aperçu de ma voix »).
# Repli anglais pour les langues non listées. La famille est déduite de l'id de la
# voix : « de_DE-thorsten-medium » → « de », « fr-FR-VivienneMultilingual » → « fr ».
_PREVIEW_TEXTS: dict[str, str] = {
    "en": "Hello! This is a preview of my voice.",
    "fr": "Bonjour ! Voici un aperçu de ma voix.",
    "de": "Hallo! Das ist eine Hörprobe meiner Stimme.",
    "es": "¡Hola! Esta es una muestra de mi voz.",
    "it": "Ciao! Questa è un'anteprima della mia voce.",
    "pt": "Olá! Esta é uma amostra da minha voz.",
    "nl": "Hallo! Dit is een voorbeeld van mijn stem.",
    "ru": "Привет! Это пример моего голоса.",
    "pl": "Cześć! To jest próbka mojego głosu.",
    "uk": "Привіт! Це зразок мого голосу.",
    "zh": "你好！这是我的声音示例。",  # noqa: RUF001 — ponctuation chinoise volontaire
    "ar": "مرحبًا! هذه عيّنة من صوتي.",
    "hi": "नमस्ते! यह मेरी आवाज़ का एक नमूना है।",
    "tr": "Merhaba! Bu, sesimin bir örneği.",
    "sv": "Hej! Det här är ett smakprov på min röst.",
    "el": "Γεια σας! Αυτό είναι ένα δείγμα της φωνής μου.",
    "cs": "Ahoj! Toto je ukázka mého hlasu.",
    "fi": "Hei! Tämä on näyte äänestäni.",
    "da": "Hej! Dette er en prøve på min stemme.",
    "no": "Hei! Dette er en prøve på stemmen min.",
    "ro": "Bună! Aceasta este o mostră a vocii mele.",
    "hu": "Szia! Ez egy minta a hangomból.",
    "ca": "Hola! Aquesta és una mostra de la meva veu.",
    "fa": "سلام! این نمونه‌ای از صدای من است.",
    "vi": "Xin chào! Đây là một mẫu giọng nói của tôi.",
    "is": "Halló! Þetta er sýnishorn af röddinni minni.",
    "sk": "Ahoj! Toto je ukážka môjho hlasu.",
    "sr": "Здраво! Ово је узорак мог гласа.",  # noqa: RUF001 — cyrillique volontaire
    "bg": "Здравейте! Това е мостра на моя глас.",  # noqa: RUF001 — cyrillique volontaire
    "id": "Halo! Ini adalah contoh suara saya.",
    "sw": "Habari! Hii ni sampuli ya sauti yangu.",
}
_PREVIEW_DEFAULT = _PREVIEW_TEXTS["en"]


def preview_text(voice_id: str) -> str:
    """Phrase d'aperçu dans la langue de la voix (repli anglais)."""
    if voice_id.startswith("kokoro-"):
        from timbre.plugins.tts.kokoro import voice_lang_family

        family = voice_lang_family(voice_id)
    else:
        family = voice_id.split("-", 1)[0].split("_", 1)[0].lower()
    return _PREVIEW_TEXTS.get(family, _PREVIEW_DEFAULT)


@router.get("/voices/{voice_id}/preview")
async def preview_voice(request: Request, voice_id: str) -> Response:
    """Synthétise une courte phrase (dans la langue de la voix) pour l'aperçu."""
    orchestrator = request.app.state.orchestrator
    engine = orchestrator.tts_engine(voice_engine(voice_id))
    if engine is None:
        raise HTTPException(
            status_code=400,
            detail="Moteur de voix indisponible (voix non téléchargée ?).",
        )
    try:
        text = preview_text(voice_id)
        audio = b"".join([chunk async for chunk in engine.synthesize(text, voice_id)])
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
    engine = voice_engine(payload.voice_id)
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
