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


async def test_default_persona_seeded(storage: Storage):
    personas = await storage.list_personas()
    assert [p.id for p in personas] == ["timbre"]
    assert personas[0].voice.voice_id == "fr-FR-VivienneMultilingualNeural"


async def test_persona_upsert_and_roundtrip(storage: Storage):
    from timbre.personas.models import Persona, VoiceConfig, VoiceParams

    persona = Persona(
        id="coach",
        name="Coach",
        system_prompt="Tu es Coach.",
        voice=VoiceConfig(voice_id="fr-FR-HenriNeural", params=VoiceParams(rate=1.1, pitch=3)),
        greeting="On y va !",
        temperature=1.2,
    )
    await storage.upsert_persona(persona, is_new=True)
    loaded = await storage.get_persona("coach")
    assert loaded is not None
    assert loaded.voice.params.rate == 1.1 and loaded.voice.params.pitch == 3
    assert loaded.temperature == 1.2

    # Mise à jour : mêmes id, nouveaux champs.
    persona2 = persona.model_copy(update={"name": "Coach Pro"})
    await storage.upsert_persona(persona2, is_new=False)
    reloaded = await storage.get_persona("coach")
    assert reloaded is not None and reloaded.name == "Coach Pro"
    assert await storage.count_personas() == 2  # timbre + coach


async def test_persona_delete(storage: Storage):
    from timbre.personas.models import Persona, VoiceConfig

    await storage.upsert_persona(
        Persona(
            id="x", name="X", system_prompt="x", voice=VoiceConfig(voice_id="fr-FR-HenriNeural")
        ),
        is_new=True,
    )
    assert await storage.delete_persona("x") is True
    assert await storage.get_persona("x") is None
    assert await storage.delete_persona("x") is False
