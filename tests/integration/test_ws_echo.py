"""Test d'intégration Phase 1 : connexion → message → écho → changements d'état."""

from starlette.testclient import TestClient

from timbre.api.app import create_app


def test_health():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_echo_flow():
    client = TestClient(create_app())
    with client.websocket_connect("/ws") as ws:
        # État initial explicite dès la connexion.
        assert ws.receive_json() == {"type": "state_change", "state": "idle"}

        ws.send_json({"type": "user_message", "text": "bonjour Timbre"})

        assert ws.receive_json() == {"type": "state_change", "state": "thinking"}
        assert ws.receive_json() == {
            "type": "ai_chunk",
            "text": "Écho : bonjour Timbre",
            "last": True,
        }
        assert ws.receive_json() == {"type": "state_change", "state": "idle"}


def test_invalid_message_yields_error_and_keeps_connection():
    client = TestClient(create_app())
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "state_change"

        ws.send_text("n'importe quoi")
        error = ws.receive_json()
        assert error["type"] == "error"
        assert error["code"] == "invalid_message"

        # La connexion survit : un message valide fonctionne toujours.
        ws.send_json({"type": "user_message", "text": "encore là ?"})
        assert ws.receive_json() == {"type": "state_change", "state": "thinking"}
        assert ws.receive_json()["text"] == "Écho : encore là ?"
        assert ws.receive_json() == {"type": "state_change", "state": "idle"}
