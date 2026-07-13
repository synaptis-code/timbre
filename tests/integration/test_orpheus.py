"""Moteur Orpheus : parsing des jetons, routage, activation/désactivation.

La synthèse réelle (LM Studio + SNAC) n'est pas testée ici — elle exige un
modèle Orpheus chargé. On vérifie le câblage : endpoints, routage de moteur,
et l'exposition des voix quand le moteur est activé. L'installation lourde
(torch+snac) est neutralisée par monkeypatch.
"""

import sys
from pathlib import Path

import pytest
from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from fakes import FakeLLM, FakeTTS
from timbre.api.app import create_app
from timbre.config import Settings


def make_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        database_path=str(tmp_path / "test.db"),
        piper_voices_dir=str(tmp_path / "voices"),
    )
    return TestClient(create_app(llm=FakeLLM(), tts=FakeTTS(), settings=settings))


def test_token_to_id_parsing() -> None:
    from timbre.plugins.tts.orpheus import _token_to_id

    assert _token_to_id("<custom_token_10>", 0) == 0
    assert _token_to_id("<custom_token_4106>", 1) == 0  # 4106 - 10 - (1 * 4096)
    assert _token_to_id("pas un token", 0) is None
    assert _token_to_id("<custom_token_abc>", 0) is None


def test_voice_engine_routes_orpheus() -> None:
    from timbre.api.rest import voice_engine

    assert voice_engine("orpheus-tara") == "orpheus"
    assert voice_engine("fr-FR-VivienneMultilingualNeural") == "edge-tts"
    assert voice_engine("de_DE-thorsten-medium") == "piper"


def test_orpheus_status_defaults_disabled(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        body = client.get("/api/voices/orpheus").json()
    assert body["enabled"] is False
    assert body["model"] == ""
    assert len(body["voices"]) == 8


def test_enable_then_disable_orpheus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import timbre.api.rest as rest

    monkeypatch.setattr(rest, "ensure_orpheus_installed", lambda: None)
    with make_client(tmp_path) as client:
        enabled = client.post("/api/voices/orpheus", json={"model": "orpheus-3b"}).json()
        assert enabled["enabled"] is True
        assert enabled["model"] == "orpheus-3b"

        voices = client.get("/api/voices").json()
        assert any(v["engine"] == "orpheus" and v["id"] == "orpheus-tara" for v in voices)

        after = client.delete("/api/voices/orpheus").json()
        assert after["enabled"] is False
        voices = client.get("/api/voices").json()
        assert all(v["engine"] != "orpheus" for v in voices)
