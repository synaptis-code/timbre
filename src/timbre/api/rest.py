"""API REST : conversations, historique, réglages (persistés en SQLite local)."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from timbre.storage import ConversationMeta, Storage, StoredMessage

router = APIRouter(prefix="/api")


def _storage(request: Request) -> Storage:
    storage: Storage = request.app.state.storage
    return storage


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


class SettingsPayload(BaseModel):
    language: str = Field(min_length=2, max_length=8)


@router.get("/settings")
async def get_settings(request: Request) -> SettingsPayload:
    return SettingsPayload(language=await _storage(request).get_setting("language", "fr"))


@router.put("/settings")
async def put_settings(request: Request, payload: SettingsPayload) -> SettingsPayload:
    await _storage(request).set_setting("language", payload.language)
    return payload
