"""Tests d'intégration de la vision : capture par tour vers le LLM multimodal."""

import sys
from pathlib import Path

from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from fakes import FakeLLM
from timbre.api.app import create_app
from timbre.config import Settings

IMAGE = "data:image/jpeg;base64,AAAA"


def connect(llm: FakeLLM):
    settings = Settings(tts_enabled=False)
    return TestClient(create_app(llm=llm, settings=settings)).websocket_connect("/ws")


def drain_until_idle(ws) -> list[dict]:
    received = []
    while (msg := ws.receive_json()) != {"type": "state_change", "state": "idle"}:
        received.append(msg)
    return received


def test_image_reaches_llm_in_openai_multimodal_format():
    llm = FakeLLM(tokens=["Je", " vois."])
    with connect(llm) as ws:
        ws.receive_json(), ws.receive_json(), ws.receive_json(), ws.receive_json()
        ws.send_json({"type": "user_message", "text": "Que vois-tu ?", "image": IMAGE})
        drain_until_idle(ws)

    content = llm.received_messages[0][-1]["content"]
    assert content == [
        {"type": "text", "text": "Que vois-tu ?"},
        {"type": "image_url", "image_url": {"url": IMAGE}},
    ]


def test_only_latest_image_kept_in_history():
    llm = FakeLLM(tokens=["Vu."])
    with connect(llm) as ws:
        ws.receive_json(), ws.receive_json(), ws.receive_json(), ws.receive_json()
        ws.send_json({"type": "user_message", "text": "Écran un", "image": IMAGE})
        drain_until_idle(ws)
        ws.send_json({"type": "user_message", "text": "Écran deux", "image": IMAGE})
        drain_until_idle(ws)

    second_call = llm.received_messages[1]
    user_turns = [t for t in second_call if t["role"] == "user"]
    # L'ancienne image est remplacée par un marqueur texte, la nouvelle est là.
    assert user_turns[0]["content"] == "Écran un [capture d'écran précédente retirée]"
    assert isinstance(user_turns[1]["content"], list)


def test_model_without_vision_says_so_and_answers_text_only():
    llm = FakeLLM(tokens=["Réponse", " texte."], vision=False)
    with connect(llm) as ws:
        ws.receive_json(), ws.receive_json(), ws.receive_json(), ws.receive_json()
        ws.send_json({"type": "user_message", "text": "Regarde ça", "image": IMAGE})
        received = drain_until_idle(ws)

    errors = [m for m in received if m["type"] == "error"]
    assert len(errors) == 1 and errors[0]["code"] == "no_vision"
    assert "qwen2.5-vl" in errors[0]["message"]
    # Le tour continue en texte seul : réponse complète, image absente de l'historique.
    streamed = "".join(m["text"] for m in received if m["type"] == "ai_chunk")
    assert streamed == "Réponse texte."
    assert llm.received_messages[0][-1]["content"] == "Regarde ça"


def test_invalid_image_payload_is_rejected():
    with connect(FakeLLM()) as ws:
        ws.receive_json(), ws.receive_json(), ws.receive_json(), ws.receive_json()
        ws.send_json({"type": "user_message", "text": "hop", "image": "http://exemple.com/a.png"})
        error = ws.receive_json()
        assert error["type"] == "error"
        assert error["code"] == "invalid_message"
