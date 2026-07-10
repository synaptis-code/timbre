"""Tests d'intégration de l'interruption (Stop et remplacement de tour)."""

import sys
from pathlib import Path

from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from fakes import FakeLLM
from timbre.api.app import create_app
from timbre.config import Settings

SLOW_TOKENS = [f"mot{i} " for i in range(30)]


def connect(llm: FakeLLM):
    settings = Settings(tts_enabled=False)
    return TestClient(create_app(llm=llm, settings=settings)).websocket_connect("/ws")


def drain_until_idle(ws) -> list[dict]:
    received = []
    while (msg := ws.receive_json()) != {"type": "state_change", "state": "idle"}:
        received.append(msg)
    return received


def test_stop_interrupts_generation_and_archives_partial():
    llm = FakeLLM(tokens=SLOW_TOKENS, delay=0.05)
    with connect(llm) as ws:
        ws.receive_json(), ws.receive_json(), ws.receive_json(), ws.receive_json()

        ws.send_json({"type": "user_message", "text": "Compte jusqu'à trente"})
        while ws.receive_json()["type"] != "ai_chunk":
            pass
        ws.send_json({"type": "interrupt"})

        received = drain_until_idle(ws)
        closing = [m for m in received if m["type"] == "ai_chunk" and m["last"]]
        assert closing and closing[-1]["interrupted"] is True

        # Le tour suivant fonctionne, et l'historique contient le texte partiel.
        ws.send_json({"type": "user_message", "text": "Continue"})
        drain_until_idle(ws)

    partial_turn = llm.received_messages[1][2]
    assert partial_turn["role"] == "assistant"
    partial_text = str(partial_turn["content"])
    assert partial_text.startswith("mot0 ")
    assert partial_text != "".join(SLOW_TOKENS)  # bien partiel, pas inventé complet


def test_new_message_supersedes_running_turn():
    llm = FakeLLM(tokens=SLOW_TOKENS, delay=0.05)
    with connect(llm) as ws:
        ws.receive_json(), ws.receive_json(), ws.receive_json(), ws.receive_json()

        ws.send_json({"type": "user_message", "text": "Première question"})
        while ws.receive_json()["type"] != "ai_chunk":
            pass
        # L'utilisateur reparle : le tour en cours est remplacé.
        ws.send_json({"type": "user_message", "text": "Non attends, autre chose"})

        drain_until_idle(ws)  # fin (interrompue) du premier tour
        second = drain_until_idle(ws)  # deuxième tour complet
        streamed = "".join(m["text"] for m in second if m["type"] == "ai_chunk")
        assert streamed == "".join(SLOW_TOKENS)

    second_call = llm.received_messages[1]
    roles = [t["role"] for t in second_call]
    # système, q1, réponse partielle archivée, q2
    assert roles == ["system", "user", "assistant", "user"]
    assert second_call[3]["content"] == "Non attends, autre chose"


def test_interrupt_when_idle_is_a_noop():
    llm = FakeLLM(tokens=["Ok."])
    with connect(llm) as ws:
        ws.receive_json(), ws.receive_json(), ws.receive_json(), ws.receive_json()

        ws.send_json({"type": "interrupt"})
        # Aucune erreur : le message suivant démarre un tour normalement.
        ws.send_json({"type": "user_message", "text": "Toujours là ?"})
        assert ws.receive_json() == {"type": "state_change", "state": "thinking"}
