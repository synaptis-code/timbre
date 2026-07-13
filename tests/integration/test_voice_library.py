"""Bibliothèque de voix Piper : catalogue, état, inférence du moteur, aperçu.

Le catalogue réseau (voices.json) est remplacé par un faux catalogue via
monkeypatch : les tests restent hors-ligne et déterministes.
"""

import sys
from pathlib import Path

import pytest
from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from fakes import FakeLLM, FakeTTS
from timbre.api.app import create_app
from timbre.config import Settings
from timbre.plugins.tts import piper


def _fake_catalog() -> dict[str, piper.PiperVoiceSpec]:
    return {
        "fr_FR-siwis-medium": piper.PiperVoiceSpec(
            id="fr_FR-siwis-medium", name="siwis", quality="medium",
            language_code="fr_FR", language_english="French", language_native="Français",
            hf_dir="fr/fr_FR/siwis/medium", size_bytes=63201294,
        ),
        "en_US-amy-medium": piper.PiperVoiceSpec(
            id="en_US-amy-medium", name="amy", quality="medium",
            language_code="en_US", language_english="English", language_native="English",
            hf_dir="en/en_US/amy/medium", size_bytes=63201294,
        ),
    }


@pytest.fixture(autouse=True)
def _stub_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(piper, "fetch_catalog", _fake_catalog)


def make_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        database_path=str(tmp_path / "test.db"),
        piper_voices_dir=str(tmp_path / "voices"),
    )
    return TestClient(create_app(llm=FakeLLM(), tts=FakeTTS(), settings=settings))


def _fake_model(voices_dir: Path, voice_id: str) -> None:
    voices_dir.mkdir(parents=True, exist_ok=True)
    (voices_dir / f"{voice_id}.onnx").write_bytes(b"fake-onnx")
    (voices_dir / f"{voice_id}.onnx.json").write_text("{}", encoding="utf-8")


def test_piper_library_lists_catalog(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        body = client.get("/api/voices/piper").json()
    assert isinstance(body["package_installed"], bool)
    langs = {v["language_english"] for v in body["voices"]}
    assert {"French", "English"} <= langs
    assert all(v["status"] == "available" for v in body["voices"])


def test_download_unknown_voice_is_404(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        assert client.post("/api/voices/piper/inconnue/download").status_code == 404


def test_ready_voice_appears_in_voices_and_is_deletable(tmp_path: Path) -> None:
    _fake_model(tmp_path / "voices", "fr_FR-siwis-medium")
    with make_client(tmp_path) as client:
        voices = client.get("/api/voices").json()
        siwis = next((v for v in voices if v["id"] == "fr_FR-siwis-medium"), None)
        assert siwis is not None
        assert siwis["engine"] == "piper"

        lib = client.get("/api/voices/piper").json()
        state = next(v for v in lib["voices"] if v["id"] == "fr_FR-siwis-medium")
        assert state["status"] == "ready"

        after = client.delete("/api/voices/piper/fr_FR-siwis-medium").json()
        state = next(v for v in after["voices"] if v["id"] == "fr_FR-siwis-medium")
        assert state["status"] == "available"
        voices = client.get("/api/voices").json()
        assert all(v["id"] != "fr_FR-siwis-medium" for v in voices)


def test_preview_vivienne_returns_audio(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        resp = client.get("/api/voices/fr-FR-VivienneMultilingualNeural/preview")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("audio/mpeg")
    assert resp.content.startswith(b"AUDIO(")  # FakeTTS


def test_preview_undownloaded_piper_voice_is_400(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        resp = client.get("/api/voices/fr_FR-siwis-medium/preview")
    assert resp.status_code == 400


def test_persona_with_piper_voice_gets_piper_engine(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        piper_persona = client.post(
            "/api/personas",
            json={"name": "Locale", "system_prompt": "Tu es locale.",
                  "voice_id": "en_US-amy-medium"},
        ).json()
        edge_persona = client.post(
            "/api/personas",
            json={"name": "Cloud", "system_prompt": "Tu es cloud.",
                  "voice_id": "fr-FR-VivienneMultilingualNeural"},
        ).json()
    assert piper_persona["voice"]["engine"] == "piper"
    assert edge_persona["voice"]["engine"] == "edge-tts"
