"""Tests de la persistance SQLite locale."""

from pathlib import Path

import pytest

from timbre.storage import DEFAULT_TITLE, Storage


@pytest.fixture
async def storage(tmp_path: Path):
    store = Storage(tmp_path / "test.db")
    await store.connect()
    yield store
    await store.aclose()


async def test_create_and_list_ordered_by_activity(storage: Storage):
    first = await storage.create_conversation()
    second = await storage.create_conversation()
    # Un message dans la première la fait remonter en tête.
    await storage.add_message(first.id, "user", "coucou")
    titles = [c.id for c in await storage.list_conversations()]
    assert titles == [first.id, second.id]


async def test_first_user_message_becomes_title(storage: Storage):
    convo = await storage.create_conversation()
    assert convo.title == DEFAULT_TITLE
    await storage.add_message(convo.id, "user", "Explique-moi la photosynthèse en deux phrases")
    meta = await storage.get_conversation(convo.id)
    assert meta is not None and meta.title.startswith("Explique-moi la photosynthèse")
    # Les messages suivants ne changent plus le titre.
    await storage.add_message(convo.id, "user", "Autre question")
    meta = await storage.get_conversation(convo.id)
    assert meta is not None and meta.title.startswith("Explique-moi")


async def test_messages_roundtrip_with_interrupted_flag(storage: Storage):
    convo = await storage.create_conversation()
    await storage.add_message(convo.id, "user", "Raconte")
    await storage.add_message(convo.id, "assistant", "Il était", interrupted=True)
    messages = await storage.list_messages(convo.id)
    assert [(m.role, m.content, m.interrupted) for m in messages] == [
        ("user", "Raconte", False),
        ("assistant", "Il était", True),
    ]


async def test_delete_cascades_messages(storage: Storage):
    convo = await storage.create_conversation()
    await storage.add_message(convo.id, "user", "x")
    assert await storage.delete_conversation(convo.id)
    assert await storage.get_conversation(convo.id) is None
    assert await storage.list_messages(convo.id) == []
    assert not await storage.delete_conversation(convo.id)  # déjà supprimée


async def test_rename(storage: Storage):
    convo = await storage.create_conversation()
    assert await storage.rename_conversation(convo.id, "Mon titre")
    meta = await storage.get_conversation(convo.id)
    assert meta is not None and meta.title == "Mon titre"
    assert not await storage.rename_conversation("fantome", "x")


async def test_settings_roundtrip(storage: Storage):
    assert await storage.get_setting("language", "fr") == "fr"
    await storage.set_setting("language", "en")
    await storage.set_setting("language", "es")
    assert await storage.get_setting("language", "fr") == "es"
