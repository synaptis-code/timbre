"""Tests d'intégration de la boucle de conversation (LLM factice injecté)."""

import sys
from pathlib import Path

from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from fakes import FakeLLM
from timbre.api.app import create_app
from timbre.config import Settings
from timbre.plugins.base import LLMError


def connect(llm: FakeLLM):
    # TTS coupé ici : ces tests couvrent le flux texte (l'audio a les siens).
    settings = Settings(tts_enabled=False)
    return TestClient(create_app(llm=llm, settings=settings)).websocket_connect("/ws")


def test_health():
    client = TestClient(create_app(llm=FakeLLM()))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_conversation_flow():
    with connect(FakeLLM(tokens=["Bon", "jour", " !"])) as ws:
        # À la connexion : état initial + modèle + personas + device ASR.
        assert ws.receive_json() == {"type": "state_change", "state": "idle"}
        assert ws.receive_json() == {"type": "model_info", "model": "fake-model"}
        assert ws.receive_json()["type"] == "persona_list"
        assert ws.receive_json()["type"] == "asr_info"

        ws.send_json({"type": "user_message", "text": "Salut !"})

        assert ws.receive_json() == {"type": "state_change", "state": "thinking"}
        assert ws.receive_json() == {"type": "model_info", "model": "fake-model"}
        chunk = {"type": "ai_chunk", "last": False, "interrupted": False}
        assert ws.receive_json() == {**chunk, "text": "Bon"}
        assert ws.receive_json() == {**chunk, "text": "jour"}
        assert ws.receive_json() == {**chunk, "text": " !"}
        assert ws.receive_json() == {**chunk, "text": "", "last": True}
        metrics = ws.receive_json()
        assert metrics["type"] == "turn_metrics"
        assert isinstance(metrics["total_ms"], int)
        assert isinstance(metrics["first_token_ms"], int)
        assert metrics["asr_ms"] is None  # tour clavier
        assert ws.receive_json() == {"type": "state_change", "state": "idle"}


def test_history_sent_to_llm_includes_system_prompt_and_turns():
    llm = FakeLLM(tokens=["Ça", " va"])
    with connect(llm) as ws:
        ws.receive_json(), ws.receive_json(), ws.receive_json(), ws.receive_json()

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
        assert ws.receive_json()["type"] == "persona_list"
        assert ws.receive_json()["type"] == "asr_info"

        ws.send_json({"type": "user_message", "text": "Allô ?"})
        assert ws.receive_json() == {"type": "state_change", "state": "thinking"}
        assert ws.receive_json()["code"] == "llm_unreachable"
        assert ws.receive_json() == {"type": "state_change", "state": "idle"}


def test_stream_failure_archives_partial_text():
    llm = FakeLLM(tokens=["Il", " était", " une fois"], fail_after=2)
    with connect(llm) as ws:
        ws.receive_json(), ws.receive_json(), ws.receive_json(), ws.receive_json()

        ws.send_json({"type": "user_message", "text": "Raconte une histoire"})
        received = []
        while (msg := ws.receive_json()) != {"type": "state_change", "state": "idle"}:
            received.append(msg)
        types = [m["type"] for m in received]
        assert "error" in types  # la coupure est signalée…
        closing = {"type": "ai_chunk", "text": "", "last": True, "interrupted": False}
        assert closing in received  # …la bulle est close

        # …et le tour suivant voit exactement le texte partiel réellement émis.
        ws.send_json({"type": "user_message", "text": "Continue"})
        while ws.receive_json() != {"type": "state_change", "state": "idle"}:
            pass

    partial_turn = llm.received_messages[1][2]
    assert partial_turn == {"role": "assistant", "content": "Il était"}


def test_invalid_message_yields_error_and_keeps_connection():
    with connect(FakeLLM()) as ws:
        ws.receive_json(), ws.receive_json(), ws.receive_json(), ws.receive_json()

        ws.send_text("n'importe quoi")
        error = ws.receive_json()
        assert error["type"] == "error"
        assert error["code"] == "invalid_message"

        ws.send_json({"type": "user_message", "text": "encore là ?"})
        assert ws.receive_json() == {"type": "state_change", "state": "thinking"}
