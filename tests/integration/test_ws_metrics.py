"""Tests d'intégration des métriques de tour et de la bascule de device ASR."""

import sys
from base64 import b64encode
from pathlib import Path

from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from fakes import FakeASR, FakeLLM, FakeTTS
from timbre.api.app import create_app


class SwitchableFakeASR(FakeASR):
    """FakeASR avec device basculable, pour tester set_asr_device."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._device = "cuda"

    @property
    def device(self) -> str:
        return self._device

    def set_device(self, device: str) -> None:
        self._device = device


def test_metrics_sent_after_voice_turn():
    asr = SwitchableFakeASR(transcript="Bonjour")
    client = TestClient(create_app(llm=FakeLLM(tokens=["Salut !"]), tts=FakeTTS(), asr=asr))
    with client.websocket_connect("/ws") as ws:
        # state, model_info, persona_list, asr_info (device exposé par le fake)
        for _ in range(3):
            ws.receive_json()
        assert ws.receive_json() == {"type": "asr_info", "device": "cuda"}

        ws.send_json({"type": "user_audio", "audio_b64": b64encode(b"x").decode(), "format": "wav"})
        metrics = None
        while (msg := ws.receive_json()) != {"type": "state_change", "state": "idle"}:
            if msg["type"] == "turn_metrics":
                metrics = msg

    assert metrics is not None
    assert isinstance(metrics["asr_ms"], int)  # tour vocal : durée de transcription mesurée
    assert isinstance(metrics["first_token_ms"], int)
    assert isinstance(metrics["first_audio_ms"], int)  # une phrase a été synthétisée
    assert metrics["total_ms"] >= metrics["first_token_ms"]
    # VRAM : entiers si nvidia-smi présent, None sinon — jamais absent du message.
    assert "vram_used_mb" in metrics and "vram_total_mb" in metrics


def test_set_asr_device_switches_and_confirms():
    asr = SwitchableFakeASR()
    client = TestClient(create_app(llm=FakeLLM(), tts=FakeTTS(), asr=asr))
    with client.websocket_connect("/ws") as ws:
        for _ in range(4):
            ws.receive_json()

        ws.send_json({"type": "set_asr_device", "device": "cpu"})
        assert ws.receive_json() == {"type": "asr_info", "device": "cpu"}
        assert asr.device == "cpu"

        ws.send_json({"type": "set_asr_device", "device": "cuda"})
        assert ws.receive_json() == {"type": "asr_info", "device": "cuda"}


def test_set_asr_device_rejects_unknown_value():
    client = TestClient(create_app(llm=FakeLLM(), tts=FakeTTS(), asr=SwitchableFakeASR()))
    with client.websocket_connect("/ws") as ws:
        for _ in range(4):
            ws.receive_json()
        ws.send_json({"type": "set_asr_device", "device": "tpu"})
        assert ws.receive_json()["code"] == "invalid_message"


def test_set_asr_device_unsupported_engine_is_explicit():
    # FakeASR de base : pas de set_device → erreur claire, pas de crash.
    client = TestClient(create_app(llm=FakeLLM(), tts=FakeTTS(), asr=FakeASR()))
    with client.websocket_connect("/ws") as ws:
        for _ in range(3):
            ws.receive_json()  # pas d'asr_info : device None
        ws.send_json({"type": "set_asr_device", "device": "cpu"})
        assert ws.receive_json()["code"] == "asr_device_unsupported"
