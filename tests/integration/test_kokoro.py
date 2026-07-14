"""Moteur Kokoro : routage, langue d'aperçu, listing, installé/désinstallé.

Aucun téléchargement ni synthèse réelle (exige le modèle ~350 Mo). On simule le
modèle présent via des fichiers factices et on neutralise la présence du paquet.
"""

import sys
from pathlib import Path

import pytest
from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from fakes import FakeLLM, FakeTTS
from timbre.api.app import create_app
from timbre.config import Settings
from timbre.plugins.tts import kokoro


@pytest.fixture(autouse=True)
def _pretend_package_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    # Le paquet kokoro-onnx n'est pas requis pour ces tests de câblage.
    monkeypatch.setattr(kokoro, "kokoro_installed", lambda: True)


def make_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        database_path=str(tmp_path / "test.db"),
        piper_voices_dir=str(tmp_path / "piper"),
        kokoro_models_dir=str(tmp_path / "kokoro"),
    )
    return TestClient(create_app(llm=FakeLLM(), tts=FakeTTS(), settings=settings))


def _fake_model(models_dir: Path) -> None:
    models_dir.mkdir(parents=True, exist_ok=True)
    (models_dir / kokoro.MODEL_FILE).write_bytes(b"fake-onnx")
    (models_dir / kokoro.VOICES_FILE).write_bytes(b"fake-voices")


def test_voice_engine_and_language() -> None:
    from timbre.api.rest import preview_text, voice_engine

    assert voice_engine("kokoro-ff_siwis") == "kokoro"
    assert voice_engine("kokoro-af_heart") == "kokoro"
    assert kokoro.voice_lang_family("kokoro-ff_siwis") == "fr"
    assert kokoro.voice_lang_family("kokoro-af_heart") == "en"
    assert preview_text("kokoro-ff_siwis").startswith("Bonjour")
    assert preview_text("kokoro-af_heart").startswith("Hello")


def test_kokoro_status_lists_all_voices(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        body = client.get("/api/voices/kokoro").json()
    assert body["status"] == "available"
    assert len(body["voices"]) == len(kokoro.KOKORO_VOICES)
    langs = {v["language_english"] for v in body["voices"]}
    assert "French" in langs and "English (US)" in langs
    assert all(v["id"].startswith("kokoro-") for v in body["voices"])


def test_installed_kokoro_voices_are_selectable_and_removable(tmp_path: Path) -> None:
    _fake_model(tmp_path / "kokoro")  # présent avant create_app → moteur enregistré
    with make_client(tmp_path) as client:
        status = client.get("/api/voices/kokoro").json()
        assert status["status"] == "ready"

        voices = client.get("/api/voices").json()
        assert any(v["engine"] == "kokoro" and v["id"] == "kokoro-ff_siwis" for v in voices)

        after = client.delete("/api/voices/kokoro").json()
        assert after["status"] == "available"
        voices = client.get("/api/voices").json()
        assert all(v["engine"] != "kokoro" for v in voices)


def test_persona_with_kokoro_voice_gets_kokoro_engine(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        persona = client.post(
            "/api/personas",
            json={"name": "Voix locale", "system_prompt": "Test.",
                  "voice_id": "kokoro-ff_siwis"},
        ).json()
    assert persona["voice"]["engine"] == "kokoro"
