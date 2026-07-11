"""Tests du backend LM Studio (transport HTTP simulé)."""

import json

import httpx2
import pytest

from timbre.plugins.base import LLMError
from timbre.plugins.llm.lmstudio import LMStudioBackend, fetch_lmstudio_models


def make_backend(handler, **kwargs) -> LMStudioBackend:
    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    return LMStudioBackend("http://lmstudio.test", client=client, **kwargs)


def models_v0(*entries: dict) -> httpx2.Response:
    return httpx2.Response(200, json={"data": list(entries)})


async def test_active_model_picks_loaded_llm():
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/api/v0/models"
        return models_v0(
            {"id": "nomic-embed", "type": "embeddings", "state": "loaded"},
            {"id": "gemma-3-1b", "type": "llm", "state": "not-loaded"},
            {"id": "qwen2.5-vl-7b", "type": "vlm", "state": "loaded"},
        )

    assert await make_backend(handler).active_model() == "qwen2.5-vl-7b"


async def test_active_model_errors_when_nothing_loaded():
    def handler(request: httpx2.Request) -> httpx2.Response:
        return models_v0({"id": "gemma-3-1b", "type": "llm", "state": "not-loaded"})

    with pytest.raises(LLMError) as exc_info:
        await make_backend(handler).active_model()
    assert exc_info.value.code == "no_model_loaded"


async def test_active_model_falls_back_to_v1_models():
    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/api/v0/models":
            return httpx2.Response(404)
        assert request.url.path == "/v1/models"
        return httpx2.Response(200, json={"data": [{"id": "vieux-lmstudio"}]})

    assert await make_backend(handler).active_model() == "vieux-lmstudio"


async def test_active_model_unreachable():
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("connexion refusée")

    with pytest.raises(LLMError) as exc_info:
        await make_backend(handler).active_model()
    assert exc_info.value.code == "llm_unreachable"


async def test_fetch_lmstudio_models_lists_all_downloaded_without_embeddings():
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/api/v0/models"
        return models_v0(
            {"id": "qwen2.5-vl-7b", "type": "vlm", "state": "loaded"},
            {"id": "gemma-3-1b", "type": "llm", "state": "not-loaded"},
            {"id": "nomic-embed", "type": "embeddings", "state": "not-loaded"},
        )

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    # Modèles chargés ET non chargés listés ; embeddings exclus ; triés.
    assert await fetch_lmstudio_models("http://lmstudio.test", client) == [
        "gemma-3-1b",
        "qwen2.5-vl-7b",
    ]


async def test_fetch_lmstudio_models_falls_back_to_v1():
    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/api/v0/models":
            return httpx2.Response(404)
        assert request.url.path == "/v1/models"
        return httpx2.Response(200, json={"data": [{"id": "vieux"}]})

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    assert await fetch_lmstudio_models("http://lmstudio.test", client) == ["vieux"]


async def test_supports_vision_follows_active_model_type():
    entries = [{"id": "qwen2.5-vl-7b", "type": "vlm", "state": "loaded"}]

    def handler(request: httpx2.Request) -> httpx2.Response:
        return models_v0(*entries)

    backend = make_backend(handler)
    assert await backend.supports_vision() is None  # rien résolu encore
    await backend.active_model()
    assert await backend.supports_vision() is True

    entries[0] = {"id": "gemma-3-1b", "type": "llm", "state": "loaded"}
    await backend.active_model()
    assert await backend.supports_vision() is False


async def test_model_override_skips_detection():
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError("aucune requête attendue quand le modèle est forcé")

    backend = make_backend(handler, model_override="mon-modele")
    assert await backend.active_model() == "mon-modele"


def sse(*events: dict | str) -> bytes:
    lines = []
    for event in events:
        data = event if isinstance(event, str) else json.dumps(event)
        lines.append(f"data: {data}\n\n")
    return "".join(lines).encode()


async def test_stream_chat_yields_content_and_skips_reasoning():
    body = sse(
        {"choices": [{"delta": {"reasoning_content": "hmm, réfléchissons"}}]},
        {"choices": [{"delta": {"content": "Bon"}}]},
        {"choices": [{"delta": {"content": "jour"}}]},
        {"choices": [{"delta": {}}]},
        "[DONE]",
    )

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/api/v0/models":
            return models_v0({"id": "m", "type": "llm", "state": "loaded"})
        assert request.url.path == "/v1/chat/completions"
        payload = json.loads(request.content)
        assert payload["model"] == "m"
        assert payload["stream"] is True
        return httpx2.Response(200, content=body, headers={"content-type": "text/event-stream"})

    tokens = [
        t async for t in make_backend(handler).stream_chat([{"role": "user", "content": "salut"}])
    ]
    assert tokens == ["Bon", "jour"]


async def test_stream_chat_http_error_is_explicit():
    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/api/v0/models":
            return models_v0({"id": "m", "type": "llm", "state": "loaded"})
        return httpx2.Response(400, text="modèle déchargé")

    with pytest.raises(LLMError) as exc_info:
        async for _ in make_backend(handler).stream_chat([]):
            pass
    assert exc_info.value.code == "llm_http_error"
    assert "modèle déchargé" in exc_info.value.message
