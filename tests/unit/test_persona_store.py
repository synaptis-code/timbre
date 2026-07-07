"""Tests du chargement des personas : validation stricte, isolation, erreurs claires."""

import json
from pathlib import Path

import pytest

from timbre.personas.store import PersonaError, PersonaStore

VALID = {
    "id": "lea",
    "name": "Léa",
    "system_prompt": "Tu es Léa.",
    "voice": {"engine": "edge-tts", "voice_id": "fr-FR-VivienneMultilingualNeural"},
}


def write(directory: Path, name: str, content: object) -> None:
    text = content if isinstance(content, str) else json.dumps(content)
    (directory / name).write_text(text, encoding="utf-8")


def test_valid_persona_loads(tmp_path: Path):
    write(tmp_path, "lea.json", VALID)
    store = PersonaStore(tmp_path, known_engines={"edge-tts"})
    assert store.get("lea").name == "Léa"


def test_broken_persona_never_breaks_the_others(tmp_path: Path):
    write(tmp_path, "casse.json", "{ pas du json")
    write(tmp_path, "lea.json", VALID)
    store = PersonaStore(tmp_path, known_engines={"edge-tts"})

    statuses = {s.id: s for s in store.scan()}
    assert statuses["lea"].persona is not None
    assert statuses["casse"].persona is None
    assert "JSON illisible" in str(statuses["casse"].error)
    # Et le valide reste utilisable.
    assert store.get("lea").id == "lea"


def test_schema_violation_gives_field_level_reason(tmp_path: Path):
    write(tmp_path, "sans-prompt.json", {"id": "x", "name": "X", "voice": {"voice_id": "v"}})
    store = PersonaStore(tmp_path, known_engines={"edge-tts"})
    status = store.scan()[0]
    assert status.persona is None
    assert "system_prompt" in str(status.error)


def test_extra_field_is_rejected(tmp_path: Path):
    write(tmp_path, "typo.json", {**VALID, "greting": "coucou"})  # faute de frappe
    store = PersonaStore(tmp_path, known_engines={"edge-tts"})
    status = store.scan()[0]
    assert status.persona is None
    assert "greting" in str(status.error)


def test_duplicate_id_is_flagged(tmp_path: Path):
    write(tmp_path, "a.json", VALID)
    write(tmp_path, "b.json", {**VALID, "name": "Copie"})
    store = PersonaStore(tmp_path, known_engines={"edge-tts"})
    statuses = store.scan()
    assert statuses[0].persona is not None
    assert statuses[1].persona is None
    assert "déjà utilisé" in str(statuses[1].error)


def test_unknown_engine_invalid_when_tts_enabled(tmp_path: Path):
    write(tmp_path, "lea.json", {**VALID, "voice": {"engine": "orpheus", "voice_id": "x"}})
    store = PersonaStore(tmp_path, known_engines={"edge-tts"})
    assert "moteur TTS inconnu" in str(store.scan()[0].error)
    # TTS désactivé (known_engines=None) : le moteur n'est pas vérifié.
    assert PersonaStore(tmp_path, known_engines=None).scan()[0].persona is not None


def test_get_unknown_id_raises_not_found(tmp_path: Path):
    store = PersonaStore(tmp_path, known_engines={"edge-tts"})
    with pytest.raises(PersonaError) as exc_info:
        store.get("fantome")
    assert exc_info.value.code == "persona_not_found"


def test_utf8_bom_is_tolerated(tmp_path: Path):
    # Notepad/PowerShell sous Windows ajoutent un BOM : un persona valide doit charger.
    (tmp_path / "lea.json").write_text(json.dumps(VALID), encoding="utf-8-sig")
    store = PersonaStore(tmp_path, known_engines={"edge-tts"})
    assert store.get("lea").name == "Léa"


def test_hot_reload_scan_picks_up_edits(tmp_path: Path):
    write(tmp_path, "lea.json", VALID)
    store = PersonaStore(tmp_path, known_engines={"edge-tts"})
    assert store.get("lea").greeting == ""
    write(tmp_path, "lea.json", {**VALID, "greeting": "Recoucou !"})
    assert store.get("lea").greeting == "Recoucou !"
