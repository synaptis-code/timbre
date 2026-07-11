"""Persistance locale SQLite : conversations, messages, réglages.

Architecture inspirée d'AnythingLLM (workspaces/threads) réécrite en Python :
un simple fichier `timbre.db` local — rien ne quitte jamais la machine.
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import aiosqlite
from pydantic import BaseModel

from timbre.personas.models import Persona, VoiceConfig, VoiceParams

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
CREATE TABLE IF NOT EXISTS personas (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'fr',
    system_prompt TEXT NOT NULL,
    voice_engine TEXT NOT NULL DEFAULT 'edge-tts',
    voice_id TEXT NOT NULL,
    voice_rate REAL NOT NULL DEFAULT 1.0,
    voice_pitch INTEGER NOT NULL DEFAULT 0,
    greeting TEXT NOT NULL DEFAULT '',
    temperature REAL NOT NULL DEFAULT 0.8,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
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
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Ouvre la base (idempotent). Appelé au démarrage, mais la connexion
        est aussi établie paresseusement au premier accès (robustesse)."""
        await self._ensure()

    async def _ensure(self) -> aiosqlite.Connection:
        if self._db is not None:
            return self._db
        async with self._lock:
            if self._db is None:
                db = await aiosqlite.connect(self._path)
                db.row_factory = aiosqlite.Row
                await db.execute("PRAGMA foreign_keys = ON")
                await db.executescript(_SCHEMA)
                await db.commit()
                self._db = db
                await self._seed_default_persona()
                logger.info("base locale prête : %s", self._path)
        return self._db

    async def aclose(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    # ── Conversations ───────────────────────────────────────────────────────

    async def create_conversation(self) -> ConversationMeta:
        now = _now()
        meta = ConversationMeta(
            id=uuid.uuid4().hex, title=DEFAULT_TITLE, created_at=now, updated_at=now
        )
        await (await self._ensure()).execute(
            "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (meta.id, meta.title, meta.created_at, meta.updated_at),
        )
        await (await self._ensure()).commit()
        return meta

    async def list_conversations(self) -> list[ConversationMeta]:
        cursor = await (await self._ensure()).execute(
            "SELECT id, title, created_at, updated_at FROM conversations ORDER BY updated_at DESC"
        )
        return [ConversationMeta(**dict(row)) async for row in cursor]

    async def get_conversation(self, conversation_id: str) -> ConversationMeta | None:
        cursor = await (await self._ensure()).execute(
            "SELECT id, title, created_at, updated_at FROM conversations WHERE id = ?",
            (conversation_id,),
        )
        row = await cursor.fetchone()
        return ConversationMeta(**dict(row)) if row is not None else None

    async def rename_conversation(self, conversation_id: str, title: str) -> bool:
        cursor = await (await self._ensure()).execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (title.strip()[:120], _now(), conversation_id),
        )
        await (await self._ensure()).commit()
        return cursor.rowcount > 0

    async def delete_conversation(self, conversation_id: str) -> bool:
        cursor = await (await self._ensure()).execute(
            "DELETE FROM conversations WHERE id = ?", (conversation_id,)
        )
        await (await self._ensure()).commit()
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
        await (await self._ensure()).execute(
            "INSERT INTO messages (conversation_id, role, content, interrupted, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (conversation_id, role, content, int(interrupted), now),
        )
        # Premier message utilisateur → il devient le titre de la conversation.
        if role == "user":
            title = content.strip()[:_TITLE_MAX] or DEFAULT_TITLE
            await (await self._ensure()).execute(
                "UPDATE conversations SET title = ? WHERE id = ? AND title = ?",
                (title, conversation_id, DEFAULT_TITLE),
            )
        await (await self._ensure()).execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id)
        )
        await (await self._ensure()).commit()

    async def list_messages(self, conversation_id: str) -> list[StoredMessage]:
        cursor = await (await self._ensure()).execute(
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
        cursor = await (await self._ensure()).execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        return str(row["value"]) if row is not None else default

    async def set_setting(self, key: str, value: str) -> None:
        await (await self._ensure()).execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        await (await self._ensure()).commit()

    # ── Personas ────────────────────────────────────────────────────────────

    async def list_personas(self) -> list[Persona]:
        cursor = await (await self._ensure()).execute(
            "SELECT * FROM personas ORDER BY name COLLATE NOCASE"
        )
        return [_persona_from_row(row) async for row in cursor]

    async def get_persona(self, persona_id: str) -> Persona | None:
        cursor = await (await self._ensure()).execute(
            "SELECT * FROM personas WHERE id = ?", (persona_id,)
        )
        row = await cursor.fetchone()
        return _persona_from_row(row) if row is not None else None

    async def persona_exists(self, persona_id: str) -> bool:
        cursor = await (await self._ensure()).execute(
            "SELECT 1 FROM personas WHERE id = ?", (persona_id,)
        )
        return await cursor.fetchone() is not None

    async def count_personas(self) -> int:
        cursor = await (await self._ensure()).execute("SELECT COUNT(*) AS n FROM personas")
        row = await cursor.fetchone()
        return int(row["n"]) if row is not None else 0

    async def upsert_persona(self, persona: Persona, *, is_new: bool) -> None:
        now = _now()
        created = now if is_new else None
        await (await self._ensure()).execute(
            "INSERT INTO personas "
            "(id, name, language, system_prompt, voice_engine, voice_id, voice_rate, "
            " voice_pitch, greeting, temperature, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET "
            "name=excluded.name, language=excluded.language, "
            "system_prompt=excluded.system_prompt, voice_engine=excluded.voice_engine, "
            "voice_id=excluded.voice_id, voice_rate=excluded.voice_rate, "
            "voice_pitch=excluded.voice_pitch, greeting=excluded.greeting, "
            "temperature=excluded.temperature, updated_at=excluded.updated_at",
            (
                persona.id,
                persona.name,
                persona.language,
                persona.system_prompt,
                persona.voice.engine,
                persona.voice.voice_id,
                persona.voice.params.rate,
                persona.voice.params.pitch,
                persona.greeting,
                persona.temperature,
                created or now,
                now,
            ),
        )
        await (await self._ensure()).commit()

    async def delete_persona(self, persona_id: str) -> bool:
        cursor = await (await self._ensure()).execute(
            "DELETE FROM personas WHERE id = ?", (persona_id,)
        )
        await (await self._ensure()).commit()
        return cursor.rowcount > 0

    async def _seed_default_persona(self) -> None:
        if await self.count_personas() > 0:
            return
        logger.info("aucun persona — création du persona par défaut « Timbre »")
        await self.upsert_persona(_DEFAULT_PERSONA, is_new=True)


def _persona_from_row(row: aiosqlite.Row) -> Persona:
    return Persona(
        id=row["id"],
        name=row["name"],
        language=row["language"],
        system_prompt=row["system_prompt"],
        voice=VoiceConfig(
            engine=row["voice_engine"],
            voice_id=row["voice_id"],
            params=VoiceParams(rate=row["voice_rate"], pitch=row["voice_pitch"]),
        ),
        greeting=row["greeting"],
        temperature=row["temperature"],
    )


_DEFAULT_PERSONA = Persona(
    id="timbre",
    name="Timbre",
    language="fr",
    system_prompt=(
        "Tu es Timbre, un super assistant vocal français : brillant, chaleureux, direct et "
        "débrouillard. Tu réponds à l'oral, en phrases courtes et naturelles, sans listes ni "
        "Markdown. Tu vas droit au but, tu admets quand tu ne sais pas, et tu proposes toujours "
        "la prochaine étape utile."
    ),
    voice=VoiceConfig(engine="edge-tts", voice_id="fr-FR-VivienneMultilingualNeural"),
    greeting="Salut ! Je t'écoute.",
    temperature=0.8,
)
