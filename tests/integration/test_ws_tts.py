"""Tests d'intégration du pipeline voix (TTS factice injecté)."""

import sys
from base64 import b64decode
from pathlib import Path

from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from fakes import FakeLLM, FakeTTS
from timbre.api.app import create_app


def run_turn(llm: FakeLLM, tts: FakeTTS, text: str = "Parle-moi") -> list[dict]:
    """Envoie un message et collecte tous les messages jusqu'au retour à idle."""
    client = TestClient(create_app(llm=llm, tts=tts))
    with client.websocket_connect("/ws") as ws:
        ws.receive_json(), ws.receive_json(), ws.receive_json(), ws.receive_json()
        ws.send_json({"type": "user_message", "text": text})
        received = []
        while (msg := ws.receive_json()) != {"type": "state_change", "state": "idle"}:
            received.append(msg)
        return received


def test_sentences_are_synthesized_in_order():
    tts = FakeTTS()
    received = run_turn(FakeLLM(tokens=["Bonjour", " ! ", "Ça", " va", " ?"]), tts)

    audio = [m for m in received if m["type"] == "ai_audio"]
    assert [m["text"] for m in audio] == ["Bonjour !", "Ça va ?"]
    assert all(m["format"] == "mp3" for m in audio)
    assert b64decode(audio[0]["audio_b64"]) == b"AUDIO(Bonjour !)"
    # L'état est passé à « parle » au moins une fois.
    assert {"type": "state_change", "state": "speaking"} in received
    # Et le texte complet est bien arrivé aussi (voix EN PLUS du texte, jamais à la place).
    streamed = "".join(m["text"] for m in received if m["type"] == "ai_chunk")
    assert streamed == "Bonjour ! Ça va ?"


def test_text_is_cleaned_before_synthesis():
    tts = FakeTTS()
    run_turn(FakeLLM(tokens=["[joy] Salut **toi** 😊 !"]), tts)
    assert tts.spoken == ["Salut toi !"]


def test_emoji_only_sentence_is_not_synthesized():
    tts = FakeTTS()
    run_turn(FakeLLM(tokens=["😊🎉."]), tts)
    assert tts.spoken == []


def test_tts_failure_reported_once_and_text_flow_survives():
    tts = FakeTTS(fail=True)
    llm = FakeLLM(tokens=["Un. ", "Deux. ", "Trois."])
    received = run_turn(llm, tts)

    errors = [m for m in received if m["type"] == "error"]
    assert len(errors) == 1  # signalée une fois, pas trois
    assert errors[0]["code"] == "tts_failed"
    assert [m for m in received if m["type"] == "ai_audio"] == []
    # Le texte du tour est complet malgré la panne voix.
    streamed = "".join(m["text"] for m in received if m["type"] == "ai_chunk")
    assert streamed == "Un. Deux. Trois."
