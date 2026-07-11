"""Tests du backend Anthropic (conversion de format + streaming)."""

import json

import httpx2
import pytest

from timbre.plugins.base import LLMError
from timbre.plugins.llm.anthropic import AnthropicBackend, convert_messages

IMAGE_URL = "data:image/jpeg;base64,QUJD"


def test_convert_extracts_system_and_images():
    system, converted = convert_messages(
        [
            {"role": "system", "content": "Tu es Timbre."},
            {"role": "user", "content": "Salut"},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Regarde"},
                    {"type": "image_url", "image_url": {"url": IMAGE_URL}},
                ],
            },
        ]
    )
    assert system == "Tu es Timbre."
    assert converted[0] == {"role": "user", "content": "Salut"}
    assert converted[1]["content"][1] == {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/jpeg", "data": "QUJD"},
    }


async def test_stream_parses_text_deltas():
    events = [
        {"type": "message_start"},
        {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Bon"}},
        {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "jour"}},
        {"type": "message_stop"},
    ]
    body = "".join(f"data: {json.dumps(e)}\n\n" for e in events).encode()

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/v1/messages"
        assert request.headers["x-api-key"] == "sk-ant"
        payload = json.loads(request.content)
        assert payload["system"] == "Tu es Timbre."
        assert payload["max_tokens"] > 0
        return httpx2.Response(200, content=body, headers={"content-type": "text/event-stream"})

    client = httpx2.AsyncClient(
        transport=httpx2.MockTransport(handler),
        headers={"x-api-key": "sk-ant", "anthropic-version": "2023-06-01"},
    )
    backend = AnthropicBackend(
        "http://anthropic.test", api_key="sk-ant", model="claude-x", client=client
    )
    messages = [
        {"role": "system", "content": "Tu es Timbre."},
        {"role": "user", "content": "Salut"},
    ]
    tokens = [t async for t in backend.stream_chat(messages)]
    assert tokens == ["Bon", "jour"]
    assert await backend.supports_vision() is True


async def test_no_model_is_explicit():
    backend = AnthropicBackend(api_key="sk")
    with pytest.raises(LLMError) as exc_info:
        await backend.active_model()
    assert exc_info.value.code == "no_model_selected"
    await backend.aclose()
