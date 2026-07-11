"""API REST : conversations, historique, réglages, fournisseurs d'IA.

Tout est persisté en SQLite local — les clés API ne quittent jamais la
machine et ne sont jamais renvoyées par l'API (seulement un indicateur).
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from timbre.plugins.base import LLMError
from timbre.plugins.llm.providers import (
    ACTIVE_KEY,
    PROVIDERS,
    SPECS_BY_ID,
    ProviderManager,
    config_key,
)
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


class ModelsResponse(BaseModel):
    models: list[str]


@router.get("/providers/{provider_id}/models")
async def list_provider_models(request: Request, provider_id: str) -> ModelsResponse:
    if provider_id not in SPECS_BY_ID:
        raise HTTPException(status_code=404, detail=f"Fournisseur inconnu : {provider_id}")
    try:
        return ModelsResponse(models=await _manager(request).list_models(provider_id))
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc


class SettingsPayload(BaseModel):
    language: str = Field(min_length=2, max_length=8)


@router.get("/settings")
async def get_settings(request: Request) -> SettingsPayload:
    return SettingsPayload(language=await _storage(request).get_setting("language", "fr"))


@router.put("/settings")
async def put_settings(request: Request, payload: SettingsPayload) -> SettingsPayload:
    await _storage(request).set_setting("language", payload.language)
    return payload
