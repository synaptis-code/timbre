"""Tests d'intégration des personas (stockés en base) : sélection et @invocation."""

import sys
from pathlib import Path

from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from fakes import FakeLLM, FakeTTS
from timbre.api.app import create_app
from timbre.config import Settings


def make_client(tmp_path: Path, llm: FakeLLM | None = None, tts: FakeTTS | None = None):
    settings = Settings(database_path=str(tmp_path / "test.db"))
    return TestClient(create_app(llm=llm or FakeLLM(), tts=tts or FakeTTS(), settings=settings))


def make_payload(name: str, **extra) -> dict:
    return {
        "name": name,
        "system_prompt": f"Tu es {name}.",
        "voice_id": f"voix-{name.lower()}",
        **extra,
    }


def receive_connect(ws) -> dict:
    assert ws.receive_json()["type"] == "state_change"
    assert ws.receive_json()["type"] == "model_info"
    persona_list = ws.receive_json()
    assert persona_list["type"] == "persona_list"
    assert ws.receive_json()["type"] == "asr_info"
    return persona_list


def drain_until_idle(ws) -> list[dict]:
    received = []
    while (msg := ws.receive_json()) != {"type": "state_change", "state": "idle"}:
        received.append(msg)
    return received


def test_default_persona_seeded_and_active(tmp_path: Path):
    with make_client(tmp_path) as client:
        with client.websocket_connect("/ws") as ws:
            persona_list = receive_connect(ws)
        assert persona_list["active"] == "timbre"
        assert [p["name"] for p in persona_list["personas"]] == ["Timbre"]
        # REST : le persona par défaut existe.
        personas = client.get("/api/personas").json()
        assert personas[0]["id"] == "timbre"


def test_create_persona_appears_in_list_and_is_selectable(tmp_path: Path):
    llm = FakeLLM(tokens=["Ok."])
    tts = FakeTTS()
    with make_client(tmp_path, llm=llm, tts=tts) as client:
        created = client.post(
            "/api/personas",
            json=make_payload("Coach", greeting="On y va !", temperature=1.1, pitch=3),
        )
        assert created.status_code == 201
        coach_id = created.json()["id"]
        assert coach_id == "coach"

        with client.websocket_connect("/ws") as ws:
            persona_list = receive_connect(ws)
            assert {p["id"] for p in persona_list["personas"]} == {"timbre", "coach"}

            # Sélection explicite → accueil parlé + voix/température du persona.
            ws.send_json({"type": "set_persona", "persona_id": coach_id})
            assert ws.receive_json()["type"] == "persona_list"
            greeting = ws.receive_json()
            assert greeting["type"] == "ai_chunk" and greeting["text"] == "On y va !"
            assert ws.receive_json()["type"] == "ai_audio"

            ws.send_json({"type": "user_message", "text": "Salut"})
            drain_until_idle(ws)

    assert tts.voices[0][0] == "voix-coach"
    assert llm.received_temperatures == [1.1]


def test_at_invocation_switches_silently(tmp_path: Path):
    with make_client(tmp_path) as client:
        client.post("/api/personas", json=make_payload("Marie", greeting="Coucou !"))
        with client.websocket_connect("/ws") as ws:
            receive_connect(ws)
            # greet=False : aucun message d'accueil, juste la mise à jour de la liste.
            ws.send_json({"type": "set_persona", "persona_id": "marie", "greet": False})
            updated = ws.receive_json()
            assert updated["type"] == "persona_list" and updated["active"] == "marie"
            # Le tour suivant démarre directement, sans accueil intercalé.
            ws.send_json({"type": "user_message", "text": "Salut Marie"})
            assert ws.receive_json() == {"type": "state_change", "state": "thinking"}


def test_edit_persona_takes_effect_on_reconnect(tmp_path: Path):
    llm = FakeLLM(tokens=["Ok."])
    with make_client(tmp_path, llm=llm) as client:
        client.put(
            "/api/personas/timbre",
            json=make_payload("Timbre", system_prompt="Tu es un pirate."),
        )
        with client.websocket_connect("/ws") as ws:
            receive_connect(ws)
            ws.send_json({"type": "user_message", "text": "Qui es-tu ?"})
            drain_until_idle(ws)
    assert llm.received_messages[0][0] == {"role": "system", "content": "Tu es un pirate."}


def test_set_unknown_persona_keeps_current(tmp_path: Path):
    with make_client(tmp_path) as client, client.websocket_connect("/ws") as ws:
        receive_connect(ws)
        ws.send_json({"type": "set_persona", "persona_id": "fantome"})
        error = ws.receive_json()
        assert error["type"] == "error" and error["code"] == "persona_not_found"


def test_cannot_delete_last_persona(tmp_path: Path):
    with make_client(tmp_path) as client:
        assert client.delete("/api/personas/timbre").status_code == 400
        client.post("/api/personas", json=make_payload("Autre"))
        assert client.delete("/api/personas/timbre").status_code == 204


def test_voices_endpoint(tmp_path: Path):
    with make_client(tmp_path) as client:
        voices = client.get("/api/voices").json()
        assert any(v["id"] == "fr-FR-VivienneMultilingualNeural" for v in voices)
