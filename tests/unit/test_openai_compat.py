"""Tests du backend générique OpenAI-compatible."""

import json

import httpx2
import pytest

from timbre.plugins.base import LLMError
from timbre.plugins.llm.openai_compat import OpenAICompatibleBackend, fetch_openai_models


def make_backend(handler, **kwargs) -> OpenAICompatibleBackend:
    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    return OpenAICompatibleBackend(
        "http://fournisseur.test/v1", provider_name="TestIA", client=client, **kwargs
    )


def sse(*events) -> bytes:
    lines = []
    for event in events:
        data = event if isinstance(event, str) else json.dumps(event)
        lines.append(f"data: {data}\n\n")
    return "".join(lines).encode()


async def test_no_model_selected_is_explicit():
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError("aucune requête attendue")

    with pytest.raises(LLMError) as exc_info:
        await make_backend(handler).active_model()
    assert exc_info.value.code == "no_model_selected"
    assert "TestIA" in exc_info.value.message


async def test_stream_chat_sends_auth_and_parses_tokens():
    body = sse(
        {"choices": [{"delta": {"content": "Bon"}}]},
        {"choices": [{"delta": {"content": "jour"}}]},
        "[DONE]",
    )

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer sk-test"
        payload = json.loads(request.content)
        assert payload["model"] == "mon-modele"
        assert payload["temperature"] == 0.3
        return httpx2.Response(200, content=body, headers={"content-type": "text/event-stream"})

    client = httpx2.AsyncClient(
        transport=httpx2.MockTransport(handler), headers={"Authorization": "Bearer sk-test"}
    )
    backend = OpenAICompatibleBackend(
        "http://fournisseur.test/v1", provider_name="TestIA", model="mon-modele", client=client
    )
    tokens = [t async for t in backend.stream_chat([], temperature=0.3)]
    assert tokens == ["Bon", "jour"]


async def test_http_error_names_the_provider():
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(401, text="invalid api key")

    backend = make_backend(handler, model="m")
    with pytest.raises(LLMError) as exc_info:
        async for _ in backend.stream_chat([]):
            pass
    assert exc_info.value.code == "llm_http_error"
    assert "TestIA" in exc_info.value.message


async def test_fetch_models():
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/v1/models"
        return httpx2.Response(200, json={"data": [{"id": "b"}, {"id": "a"}]})

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    assert await fetch_openai_models("http://x.test/v1", None, client) == ["a", "b"]
