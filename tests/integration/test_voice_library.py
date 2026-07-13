"""Bibliothèque de voix Piper : état, listing, inférence du moteur, suppression.

Aucun téléchargement réseau : on simule une voix « prête » en créant les fichiers
modèle dans le dossier temporaire, et on vérifie le comportement des endpoints.
"""

import sys
from pathlib import Path

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


def _fake_model(voices_dir: Path, model: str) -> None:
    voices_dir.mkdir(parents=True, exist_ok=True)
    (voices_dir / f"{model}.onnx").write_bytes(b"fake-onnx")
    (voices_dir / f"{model}.onnx.json").write_text("{}", encoding="utf-8")


def test_piper_library_lists_catalog(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        body = client.get("/api/voices/piper").json()
    assert isinstance(body["package_installed"], bool)
    voices = body["voices"]
    assert len(voices) == 4
    assert all(v["status"] == "available" for v in voices)
    assert any(v["recommended"] for v in voices)


def test_download_unknown_voice_is_404(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        assert client.post("/api/voices/piper/inconnue/download").status_code == 404


def test_ready_voice_appears_in_voices_and_is_deletable(tmp_path: Path) -> None:
    _fake_model(tmp_path / "voices", "fr_FR-siwis-medium")
    with make_client(tmp_path) as client:
        # Listée comme voix sélectionnable, moteur « piper ».
        voices = client.get("/api/voices").json()
        siwis = next((v for v in voices if v["id"] == "fr_FR-siwis-medium"), None)
        assert siwis is not None
        assert siwis["engine"] == "piper"

        # Statut « ready » dans la bibliothèque.
        lib = client.get("/api/voices/piper").json()
        state = next(v for v in lib["voices"] if v["id"] == "fr_FR-siwis-medium")
        assert state["status"] == "ready"

        # Suppression → redevient « available » et disparaît des voix sélectionnables.
        after = client.delete("/api/voices/piper/fr_FR-siwis-medium").json()
        state = next(v for v in after["voices"] if v["id"] == "fr_FR-siwis-medium")
        assert state["status"] == "available"
        voices = client.get("/api/voices").json()
        assert all(v["id"] != "fr_FR-siwis-medium" for v in voices)


def test_shared_model_makes_both_speakers_ready(tmp_path: Path) -> None:
    # Jessica et Pierre partagent le fichier upmc : télécharger l'un fournit l'autre.
    _fake_model(tmp_path / "voices", "fr_FR-upmc-medium")
    with make_client(tmp_path) as client:
        lib = client.get("/api/voices/piper").json()
        by_id = {v["id"]: v for v in lib["voices"]}
    assert by_id["fr_FR-upmc-jessica"]["status"] == "ready"
    assert by_id["fr_FR-upmc-pierre"]["status"] == "ready"


def test_persona_with_piper_voice_gets_piper_engine(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        piper_persona = client.post(
            "/api/personas",
            json={"name": "Locale", "system_prompt": "Tu es locale.",
                  "voice_id": "fr_FR-tom-medium"},
        ).json()
        edge_persona = client.post(
            "/api/personas",
            json={"name": "Cloud", "system_prompt": "Tu es cloud.",
                  "voice_id": "fr-FR-VivienneMultilingualNeural"},
        ).json()
    assert piper_persona["voice"]["engine"] == "piper"
    assert edge_persona["voice"]["engine"] == "edge-tts"
