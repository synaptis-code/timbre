"""Tests d'intégration des personas : sélection, isolation, zéro fallback silencieux."""

import json
import sys
from pathlib import Path

from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from fakes import FakeLLM, FakeTTS
from timbre.api.app import create_app
from timbre.config import Settings


def make_persona(persona_id: str, name: str, prompt: str, **extra) -> dict:
    return {
        "id": persona_id,
        "name": name,
        "system_prompt": prompt,
        "voice": {"engine": "edge-tts", "voice_id": f"voix-{persona_id}"},
        **extra,
    }


def setup_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "personas"
    directory.mkdir()
    (directory / "lea.json").write_text(
        json.dumps(make_persona("lea", "Léa", "Tu es Léa.", temperature=0.9)), encoding="utf-8"
    )
    (directory / "marc.json").write_text(
        json.dumps(make_persona("marc", "Marc", "Tu es Marc.", greeting="Bonjour.")),
        encoding="utf-8",
    )
    (directory / "casse.json").write_text("{ pas du json", encoding="utf-8")
    return directory


def connect(tmp_path: Path, llm: FakeLLM | None = None, tts: FakeTTS | None = None, **kw):
    settings = Settings(personas_dir=str(setup_dir(tmp_path)), persona="lea", **kw)
    app = create_app(llm=llm or FakeLLM(), tts=tts or FakeTTS(), settings=settings)
    return TestClient(app).websocket_connect("/ws")


def receive_connect_sequence(ws) -> dict:
    """state_change + model_info + persona_list ; renvoie la persona_list."""
    assert ws.receive_json()["type"] == "state_change"
    assert ws.receive_json()["type"] == "model_info"
    persona_list = ws.receive_json()
    assert persona_list["type"] == "persona_list"
    return persona_list


def drain_until_idle(ws) -> list[dict]:
    received = []
    while (msg := ws.receive_json()) != {"type": "state_change", "state": "idle"}:
        received.append(msg)
    return received


def test_connect_sends_personas_with_statuses(tmp_path: Path):
    with connect(tmp_path) as ws:
        persona_list = receive_connect_sequence(ws)
    assert persona_list["active"] == "lea"
    by_id = {p["id"]: p for p in persona_list["personas"]}
    assert by_id["lea"]["valid"] is True and by_id["lea"]["error"] is None
    assert by_id["marc"]["valid"] is True
    # Le persona cassé est listé, invalide, avec sa raison — et n'a rien cassé.
    assert by_id["casse"]["valid"] is False
    assert "JSON illisible" in by_id["casse"]["error"]


def test_set_persona_applies_prompt_voice_temperature_and_greets(tmp_path: Path):
    llm = FakeLLM(tokens=["Oui."])
    tts = FakeTTS()
    with connect(tmp_path, llm=llm, tts=tts) as ws:
        receive_connect_sequence(ws)

        ws.send_json({"type": "set_persona", "persona_id": "marc"})
        updated = ws.receive_json()
        assert updated["type"] == "persona_list" and updated["active"] == "marc"
        greeting = ws.receive_json()
        assert greeting == {
            "type": "ai_chunk",
            "text": "Bonjour.",
            "last": True,
            "interrupted": False,
        }
        greeting_audio = ws.receive_json()
        assert greeting_audio["type"] == "ai_audio" and greeting_audio["text"] == "Bonjour."

        ws.send_json({"type": "user_message", "text": "Qui es-tu ?"})
        drain_until_idle(ws)

    messages = llm.received_messages[0]
    assert messages[0] == {"role": "system", "content": "Tu es Marc."}
    # Le message d'accueil fait partie de l'historique réel.
    assert {"role": "assistant", "content": "Bonjour."} in messages
    # Voix du persona (accueil + réponse) et température par défaut (marc n'en fixe pas).
    assert tts.voices[0][0] == "voix-marc"
    assert llm.received_temperatures == [0.8]


def test_persona_temperature_reaches_llm(tmp_path: Path):
    llm = FakeLLM(tokens=["Ok."])
    with connect(tmp_path, llm=llm) as ws:
        receive_connect_sequence(ws)
        ws.send_json({"type": "user_message", "text": "Salut"})
        drain_until_idle(ws)
    assert llm.received_temperatures == [0.9]  # température de Léa


def test_set_invalid_persona_keeps_current_and_explains(tmp_path: Path):
    with connect(tmp_path) as ws:
        receive_connect_sequence(ws)

        ws.send_json({"type": "set_persona", "persona_id": "casse"})
        error = ws.receive_json()
        assert error["type"] == "error" and error["code"] == "persona_invalid"
        assert "JSON illisible" in error["message"]

        ws.send_json({"type": "set_persona", "persona_id": "fantome"})
        assert ws.receive_json()["code"] == "persona_not_found"

        # Le persona courant est conservé et fonctionnel.
        ws.send_json({"type": "list_personas"})
        assert ws.receive_json()["active"] == "lea"


def test_invalid_default_persona_falls_back_explicitly(tmp_path: Path):
    directory = tmp_path / "personas"
    directory.mkdir()
    settings = Settings(personas_dir=str(directory), persona="inexistant")
    app = create_app(llm=FakeLLM(), tts=FakeTTS(), settings=settings)
    with TestClient(app).websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "state_change"
        assert ws.receive_json()["type"] == "model_info"
        # Jamais de bascule silencieuse : l'erreur arrive AVANT la liste.
        error = ws.receive_json()
        assert error["type"] == "error" and error["code"] == "persona_not_found"
        assert "secours" in error["message"]
        assert ws.receive_json()["active"] == "defaut"


def test_list_personas_rescans_directory(tmp_path: Path):
    with connect(tmp_path) as ws:
        receive_connect_sequence(ws)
        # Un nouveau persona apparaît sans redémarrage (rechargement à chaud).
        (tmp_path / "personas" / "zoe.json").write_text(
            json.dumps(make_persona("zoe", "Zoé", "Tu es Zoé.")), encoding="utf-8"
        )
        ws.send_json({"type": "list_personas"})
        ids = {p["id"] for p in ws.receive_json()["personas"]}
        assert "zoe" in ids
