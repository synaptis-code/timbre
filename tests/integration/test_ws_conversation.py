"""Tests d'intégration de la boucle de conversation (LLM factice injecté)."""

import sys
from pathlib import Path

from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from fakes import FakeLLM
from timbre.api.app import create_app
from timbre.plugins.base import LLMError


def connect(llm: FakeLLM):
    return TestClient(create_app(llm=llm)).websocket_connect("/ws")


def test_health():
    client = TestClient(create_app(llm=FakeLLM()))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_conversation_flow():
    with connect(FakeLLM(tokens=["Bon", "jour", " !"])) as ws:
        # À la connexion : état initial + modèle détecté automatiquement.
        assert ws.receive_json() == {"type": "state_change", "state": "idle"}
        assert ws.receive_json() == {"type": "model_info", "model": "fake-model"}

        ws.send_json({"type": "user_message", "text": "Salut !"})

        assert ws.receive_json() == {"type": "state_change", "state": "thinking"}
        assert ws.receive_json() == {"type": "model_info", "model": "fake-model"}
        assert ws.receive_json() == {"type": "ai_chunk", "text": "Bon", "last": False}
        assert ws.receive_json() == {"type": "ai_chunk", "text": "jour", "last": False}
        assert ws.receive_json() == {"type": "ai_chunk", "text": " !", "last": False}
        assert ws.receive_json() == {"type": "ai_chunk", "text": "", "last": True}
        assert ws.receive_json() == {"type": "state_change", "state": "idle"}


def test_history_sent_to_llm_includes_system_prompt_and_turns():
    llm = FakeLLM(tokens=["Ça", " va"])
    with connect(llm) as ws:
        ws.receive_json(), ws.receive_json()

        ws.send_json({"type": "user_message", "text": "Comment ça va ?"})
        while ws.receive_json() != {"type": "state_change", "state": "idle"}:
            pass
        ws.send_json({"type": "user_message", "text": "Tant mieux."})
        while ws.receive_json() != {"type": "state_change", "state": "idle"}:
            pass

    second_call = llm.received_messages[1]
    roles = [turn["role"] for turn in second_call]
    assert roles == ["system", "user", "assistant", "user"]
    # Bug n°3 du plan : l'historique contient exactement le texte émis.
    assert second_call[2]["content"] == "Ça va"


def test_llm_unreachable_yields_explicit_error():
    error = LLMError("llm_unreachable", "LM Studio injoignable (simulé)")
    with connect(FakeLLM(error=error)) as ws:
        assert ws.receive_json()["type"] == "state_change"
        # Dès la connexion : erreur guidante, pas de fallback silencieux.
        first = ws.receive_json()
        assert first["type"] == "error"
        assert first["code"] == "llm_unreachable"

        ws.send_json({"type": "user_message", "text": "Allô ?"})
        assert ws.receive_json() == {"type": "state_change", "state": "thinking"}
        assert ws.receive_json()["code"] == "llm_unreachable"
        assert ws.receive_json() == {"type": "state_change", "state": "idle"}


def test_stream_failure_archives_partial_text():
    llm = FakeLLM(tokens=["Il", " était", " une fois"], fail_after=2)
    with connect(llm) as ws:
        ws.receive_json(), ws.receive_json()

        ws.send_json({"type": "user_message", "text": "Raconte une histoire"})
        received = []
        while (msg := ws.receive_json()) != {"type": "state_change", "state": "idle"}:
            received.append(msg)
        types = [m["type"] for m in received]
        assert "error" in types  # la coupure est signalée…
        assert {"type": "ai_chunk", "text": "", "last": True} in received  # …la bulle est close

        # …et le tour suivant voit exactement le texte partiel réellement émis.
        ws.send_json({"type": "user_message", "text": "Continue"})
        while ws.receive_json() != {"type": "state_change", "state": "idle"}:
            pass

    partial_turn = llm.received_messages[1][2]
    assert partial_turn == {"role": "assistant", "content": "Il était"}


def test_invalid_message_yields_error_and_keeps_connection():
    with connect(FakeLLM()) as ws:
        ws.receive_json(), ws.receive_json()

        ws.send_text("n'importe quoi")
        error = ws.receive_json()
        assert error["type"] == "error"
        assert error["code"] == "invalid_message"

        ws.send_json({"type": "user_message", "text": "encore là ?"})
        assert ws.receive_json() == {"type": "state_change", "state": "thinking"}
