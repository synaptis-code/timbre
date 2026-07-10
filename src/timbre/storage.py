"""Persistance locale SQLite : conversations, messages, réglages.

Architecture inspirée d'AnythingLLM (workspaces/threads) réécrite en Python :
un simple fichier `timbre.db` local — rien ne quitte jamais la machine.
"""

import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import aiosqlite
from pydantic import BaseModel

logger = logging.getLogger(__name__)

DEFAULT_TITLE = "Nouvelle conversation"
_TITLE_MAX = 48

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    interrupted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, id);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

Role = Literal["user", "assistant"]


class ConversationMeta(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class StoredMessage(BaseModel):
    role: Role
    content: str
    interrupted: bool
    created_at: str


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


class Storage:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._db = await aiosqlite.connect(self._path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA foreign_keys = ON")
        await self._db.executescript(_SCHEMA)
        await self._db.commit()
        logger.info("base locale prête : %s", self._path)

    async def aclose(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    @property
    def _conn(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("Storage non connecté — appeler connect() d'abord")
        return self._db

    # ── Conversations ───────────────────────────────────────────────────────

    async def create_conversation(self) -> ConversationMeta:
        now = _now()
        meta = ConversationMeta(
            id=uuid.uuid4().hex, title=DEFAULT_TITLE, created_at=now, updated_at=now
        )
        await self._conn.execute(
            "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (meta.id, meta.title, meta.created_at, meta.updated_at),
        )
        await self._conn.commit()
        return meta

    async def list_conversations(self) -> list[ConversationMeta]:
        cursor = await self._conn.execute(
            "SELECT id, title, created_at, updated_at FROM conversations ORDER BY updated_at DESC"
        )
        return [ConversationMeta(**dict(row)) async for row in cursor]

    async def get_conversation(self, conversation_id: str) -> ConversationMeta | None:
        cursor = await self._conn.execute(
            "SELECT id, title, created_at, updated_at FROM conversations WHERE id = ?",
            (conversation_id,),
        )
        row = await cursor.fetchone()
        return ConversationMeta(**dict(row)) if row is not None else None

    async def rename_conversation(self, conversation_id: str, title: str) -> bool:
        cursor = await self._conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (title.strip()[:120], _now(), conversation_id),
        )
        await self._conn.commit()
        return cursor.rowcount > 0

    async def delete_conversation(self, conversation_id: str) -> bool:
        cursor = await self._conn.execute(
            "DELETE FROM conversations WHERE id = ?", (conversation_id,)
        )
        await self._conn.commit()
        return cursor.rowcount > 0

    # ── Messages ────────────────────────────────────────────────────────────

    async def add_message(
        self,
        conversation_id: str,
        role: Role,
        content: str,
        interrupted: bool = False,
    ) -> None:
        now = _now()
        await self._conn.execute(
            "INSERT INTO messages (conversation_id, role, content, interrupted, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (conversation_id, role, content, int(interrupted), now),
        )
        # Premier message utilisateur → il devient le titre de la conversation.
        if role == "user":
            title = content.strip()[:_TITLE_MAX] or DEFAULT_TITLE
            await self._conn.execute(
                "UPDATE conversations SET title = ? WHERE id = ? AND title = ?",
                (title, conversation_id, DEFAULT_TITLE),
            )
        await self._conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id)
        )
        await self._conn.commit()

    async def list_messages(self, conversation_id: str) -> list[StoredMessage]:
        cursor = await self._conn.execute(
            "SELECT role, content, interrupted, created_at FROM messages "
            "WHERE conversation_id = ? ORDER BY id",
            (conversation_id,),
        )
        return [
            StoredMessage(
                role=row["role"],
                content=row["content"],
                interrupted=bool(row["interrupted"]),
                created_at=row["created_at"],
            )
            async for row in cursor
        ]

    # ── Réglages ────────────────────────────────────────────────────────────

    async def get_setting(self, key: str, default: str) -> str:
        cursor = await self._conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return str(row["value"]) if row is not None else default

    async def set_setting(self, key: str, value: str) -> None:
        await self._conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        await self._conn.commit()
