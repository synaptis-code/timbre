"""Tests d'intégration : API REST + persistance des conversations via WebSocket."""

import sys
from pathlib import Path

from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from fakes import FakeLLM, FakeTTS
from timbre.api.app import create_app
from timbre.config import Settings


def make_client(tmp_path: Path, llm: FakeLLM | None = None) -> TestClient:
    settings = Settings(database_path=str(tmp_path / "test.db"), tts_enabled=False)
    return TestClient(create_app(llm=llm or FakeLLM(), tts=FakeTTS(), settings=settings))


def drain_until_idle(ws) -> list[dict]:
    received = []
    while (msg := ws.receive_json()) != {"type": "state_change", "state": "idle"}:
        received.append(msg)
    return received


def test_rest_crud_and_settings(tmp_path: Path):
    with make_client(tmp_path) as client:
        assert client.get("/api/conversations").json() == []

        created = client.post("/api/conversations")
        assert created.status_code == 201
        cid = created.json()["id"]

        renamed = client.patch(f"/api/conversations/{cid}", json={"title": "Projet"})
        assert renamed.json()["title"] == "Projet"
        assert client.patch("/api/conversations/fantome", json={"title": "x"}).status_code == 404

        assert client.get(f"/api/conversations/{cid}/messages").json() == []
        assert client.get("/api/conversations/fantome/messages").status_code == 404

        # Réglages (langue) : lecture par défaut puis écriture persistée.
        assert client.get("/api/settings").json() == {"language": "fr"}
        assert client.put("/api/settings", json={"language": "en"}).status_code == 200
        assert client.get("/api/settings").json() == {"language": "en"}

        assert client.delete(f"/api/conversations/{cid}").status_code == 204
        assert client.delete(f"/api/conversations/{cid}").status_code == 404


def test_turn_is_persisted_and_titles_conversation(tmp_path: Path):
    llm = FakeLLM(tokens=["Bonjour", " !"])
    with make_client(tmp_path, llm=llm) as client:
        cid = client.post("/api/conversations").json()["id"]
        with client.websocket_connect(f"/ws?conversation={cid}") as ws:
            ws.receive_json(), ws.receive_json(), ws.receive_json(), ws.receive_json()
            ws.send_json({"type": "user_message", "text": "Salut Timbre"})
            drain_until_idle(ws)

        messages = client.get(f"/api/conversations/{cid}/messages").json()
        assert [(m["role"], m["content"]) for m in messages] == [
            ("user", "Salut Timbre"),
            ("assistant", "Bonjour !"),
        ]
        # Le premier message utilisateur titre la conversation.
        titles = [c["title"] for c in client.get("/api/conversations").json()]
        assert titles == ["Salut Timbre"]


def test_history_is_reloaded_on_reconnect(tmp_path: Path):
    llm = FakeLLM(tokens=["Ok."])
    with make_client(tmp_path, llm=llm) as client:
        cid = client.post("/api/conversations").json()["id"]
        with client.websocket_connect(f"/ws?conversation={cid}") as ws:
            ws.receive_json(), ws.receive_json(), ws.receive_json(), ws.receive_json()
            ws.send_json({"type": "user_message", "text": "Retiens : 42"})
            drain_until_idle(ws)

        # Nouvelle connexion (redémarrage simulé) : l'historique revient au LLM.
        with client.websocket_connect(f"/ws?conversation={cid}") as ws:
            ws.receive_json(), ws.receive_json(), ws.receive_json(), ws.receive_json()
            ws.send_json({"type": "user_message", "text": "Tu retiens quoi ?"})
            drain_until_idle(ws)

    roles_contents = [(t["role"], t["content"]) for t in llm.received_messages[1]]
    assert ("user", "Retiens : 42") in roles_contents
    assert ("assistant", "Ok.") in roles_contents


def test_unknown_conversation_is_rejected(tmp_path: Path):
    with (
        make_client(tmp_path) as client,
        client.websocket_connect("/ws?conversation=fantome") as ws,
    ):
        assert ws.receive_json()["code"] == "conversation_not_found"


def test_ephemeral_session_persists_nothing(tmp_path: Path):
    with make_client(tmp_path) as client:
        with client.websocket_connect("/ws") as ws:
            ws.receive_json(), ws.receive_json(), ws.receive_json(), ws.receive_json()
            ws.send_json({"type": "user_message", "text": "éphémère"})
            drain_until_idle(ws)
        assert client.get("/api/conversations").json() == []
