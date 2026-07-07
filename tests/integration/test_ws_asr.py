"""Tests d'intégration du tour vocal : user_audio → transcript → réponse."""

import sys
from base64 import b64encode
from pathlib import Path

from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from fakes import FakeASR, FakeLLM, FakeTTS
from timbre.api.app import create_app

FAKE_WAV = b64encode(b"fake-wav-bytes").decode()


def run_audio_turn(asr: FakeASR, llm: FakeLLM | None = None) -> list[dict]:
    client = TestClient(
        create_app(llm=llm or FakeLLM(tokens=["Salut", " !"]), tts=FakeTTS(), asr=asr)
    )
    with client.websocket_connect("/ws") as ws:
        ws.receive_json(), ws.receive_json()
        ws.send_json({"type": "user_audio", "audio_b64": FAKE_WAV, "format": "wav"})
        received = []
        while (msg := ws.receive_json()) != {"type": "state_change", "state": "idle"}:
            received.append(msg)
        return received


def test_voice_turn_full_loop():
    asr = FakeASR(transcript="Quelle heure est-il ?")
    received = run_audio_turn(asr)

    # L'audio décodé est bien parvenu à l'ASR.
    assert asr.received == [b"fake-wav-bytes"]
    # Le transcript est renvoyé au client (bulle utilisateur)…
    assert {"type": "user_transcript", "text": "Quelle heure est-il ?"} in received
    # …puis la réponse texte + voix suit comme pour un tour clavier.
    streamed = "".join(m["text"] for m in received if m["type"] == "ai_chunk")
    assert streamed == "Salut !"
    assert any(m["type"] == "ai_audio" for m in received)


def test_transcript_lands_in_history():
    llm = FakeLLM(tokens=["Ok."])
    run_audio_turn(FakeASR(transcript="Retiens ça"), llm=llm)
    roles_contents = [(t["role"], t["content"]) for t in llm.received_messages[0]]
    assert ("user", "Retiens ça") in roles_contents


def test_asr_failure_is_explicit():
    received = run_audio_turn(FakeASR(fail=True))
    assert [m["type"] for m in received] == ["state_change", "error"]
    assert received[1]["code"] == "asr_failed"


def test_empty_transcript_is_reported():
    received = run_audio_turn(FakeASR(transcript=""))
    errors = [m for m in received if m["type"] == "error"]
    assert len(errors) == 1
    assert errors[0]["code"] == "asr_empty"
    # Pas de tour LLM lancé pour du silence.
    assert not any(m["type"] == "ai_chunk" for m in received)


def test_invalid_base64_is_reported():
    client = TestClient(create_app(llm=FakeLLM(), tts=FakeTTS(), asr=FakeASR()))
    with client.websocket_connect("/ws") as ws:
        ws.receive_json(), ws.receive_json()
        ws.send_json({"type": "user_audio", "audio_b64": "pas du base64 !!!", "format": "wav"})
        messages = [ws.receive_json() for _ in range(3)]
        assert any(m.get("code") == "invalid_audio" for m in messages)


def test_asr_disabled_is_explicit():
    from timbre.config import Settings

    client = TestClient(
        create_app(llm=FakeLLM(), tts=FakeTTS(), settings=Settings(asr_enabled=False))
    )
    with client.websocket_connect("/ws") as ws:
        ws.receive_json(), ws.receive_json()
        ws.send_json({"type": "user_audio", "audio_b64": FAKE_WAV, "format": "wav"})
        assert ws.receive_json()["code"] == "asr_unavailable"
