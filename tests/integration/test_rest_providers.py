"""Tests d'intégration de l'API fournisseurs d'IA."""

import sys
from pathlib import Path

from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from timbre.api.app import create_app
from timbre.config import Settings


def make_client(tmp_path: Path) -> TestClient:
    # Pas d'override llm : le ProviderManager construit les vrais backends
    # (aucun appel réseau tant qu'aucun tour n'est joué).
    settings = Settings(database_path=str(tmp_path / "test.db"), tts_enabled=False)
    return TestClient(create_app(settings=settings))


def test_defaults_to_lmstudio_with_full_catalog(tmp_path: Path):
    with make_client(tmp_path) as client:
        state = client.get("/api/providers").json()
        assert state["active"] == "lmstudio"
        ids = {p["id"] for p in state["providers"]}
        assert {"lmstudio", "ollama", "openai", "anthropic", "gemini", "deepseek"} <= ids
        lmstudio = next(p for p in state["providers"] if p["id"] == "lmstudio")
        assert lmstudio["local"] is True and lmstudio["needs_key"] is False
        assert lmstudio["description"]  # chaque fournisseur porte une description


def test_configure_and_activate_provider(tmp_path: Path):
    with make_client(tmp_path) as client:
        # Sans clé ni modèle : refus explicites.
        refused = client.put("/api/providers/active", json={"provider": "deepseek"})
        assert refused.status_code == 400 and "clé API" in refused.json()["detail"]

        state = client.put(
            "/api/providers/deepseek", json={"api_key": "sk-secret", "model": "deepseek-chat"}
        ).json()
        deepseek = next(p for p in state["providers"] if p["id"] == "deepseek")
        # La clé n'est JAMAIS renvoyée — seulement l'indicateur.
        assert deepseek["has_key"] is True
        assert "sk-secret" not in state.__str__()

        activated = client.put("/api/providers/active", json={"provider": "deepseek"})
        assert activated.status_code == 200
        assert activated.json()["active"] == "deepseek"

        # Retour à LM Studio : toujours possible sans configuration.
        back = client.put("/api/providers/active", json={"provider": "lmstudio"})
        assert back.json()["active"] == "lmstudio"


def test_model_required_before_activation(tmp_path: Path):
    with make_client(tmp_path) as client:
        client.put("/api/providers/groq", json={"api_key": "sk"})
        refused = client.put("/api/providers/active", json={"provider": "groq"})
        assert refused.status_code == 400 and "modèle" in refused.json()["detail"]


def test_unknown_provider_is_404(tmp_path: Path):
    with make_client(tmp_path) as client:
        assert client.put("/api/providers/active", json={"provider": "skynet"}).status_code == 404
        assert client.put("/api/providers/skynet", json={}).status_code == 404
        assert client.post("/api/providers/skynet/models", json={}).status_code == 404


def test_local_provider_without_key_can_activate_with_model(tmp_path: Path):
    with make_client(tmp_path) as client:
        client.put("/api/providers/ollama", json={"model": "llama3.2"})
        activated = client.put("/api/providers/active", json={"provider": "ollama"})
        assert activated.status_code == 200 and activated.json()["active"] == "ollama"
