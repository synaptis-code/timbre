"""Backend Anthropic (API Messages, streaming SSE).

Format propre à Anthropic : prompt système séparé, images en blocs base64.
La conversion depuis notre format interne (style OpenAI) est faite ici.
"""

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx2

from timbre.plugins.base import LLMBackend, LLMError

logger = logging.getLogger(__name__)

_API_VERSION = "2023-06-01"
_MAX_TOKENS = 2048  # réponses vocales : courtes par design


def _convert_image_part(part: dict[str, Any]) -> dict[str, Any]:
    """`image_url` data-URL (OpenAI) → bloc image base64 (Anthropic)."""
    url = str(part.get("image_url", {}).get("url", ""))
    header, _, data = url.partition(";base64,")
    media_type = header.removeprefix("data:") or "image/jpeg"
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": data},
    }


def convert_messages(
    messages: list[dict[str, object]],
) -> tuple[str, list[dict[str, object]]]:
    """(prompt système, messages au format Anthropic)."""
    system = ""
    converted: list[dict[str, object]] = []
    for message in messages:
        role = str(message.get("role"))
        content = message.get("content")
        if role == "system":
            system = str(content)
            continue
        if isinstance(content, list):
            parts = [
                _convert_image_part(part) if part.get("type") == "image_url" else part
                for part in content
            ]
            converted.append({"role": role, "content": parts})
        else:
            converted.append({"role": role, "content": content})
    return system, converted


class AnthropicBackend(LLMBackend):
    def __init__(
        self,
        base_url: str = "https://api.anthropic.com",
        *,
        api_key: str,
        model: str | None = None,
        temperature: float = 0.8,
        client: httpx2.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._temperature = temperature
        self._client = client or httpx2.AsyncClient(
            timeout=httpx2.Timeout(15.0, read=300.0),
            headers={"x-api-key": api_key, "anthropic-version": _API_VERSION},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def active_model(self) -> str:
        if not self._model:
            raise LLMError(
                "no_model_selected",
                "Aucun modèle choisi pour Anthropic — Réglages → Fournisseur d'IA.",
            )
        return self._model

    async def supports_vision(self) -> bool | None:
        return True  # les modèles Claude actuels acceptent les images

    async def stream_chat(
        self, messages: list[dict[str, object]], temperature: float | None = None
    ) -> AsyncIterator[str]:
        model = await self.active_model()
        system, converted = convert_messages(messages)
        payload: dict[str, object] = {
            "model": model,
            "messages": converted,
            "max_tokens": _MAX_TOKENS,
            "temperature": temperature if temperature is not None else self._temperature,
            "stream": True,
        }
        if system:
            payload["system"] = system
        try:
            async with self._client.stream(
                "POST", f"{self._base_url}/v1/messages", json=payload
            ) as response:
                if response.status_code != 200:
                    body = (await response.aread()).decode("utf-8", errors="replace")
                    raise LLMError(
                        "llm_http_error",
                        f"Anthropic a répondu {response.status_code} : {body[:300]}",
                    )
                async for line in response.aiter_lines():
                    token = _parse_event_line(line)
                    if token is not None:
                        yield token
        except httpx2.HTTPError as exc:
            raise LLMError("llm_unreachable", f"Anthropic injoignable : {exc}") from exc


def _parse_event_line(line: str) -> str | None:
    if not line.startswith("data: "):
        return None
    try:
        event = json.loads(line[len("data: ") :])
    except json.JSONDecodeError:
        return None
    if event.get("type") != "content_block_delta":
        return None
    delta = event.get("delta", {})
    if delta.get("type") != "text_delta":
        return None
    text = delta.get("text")
    return str(text) if text else None


async def fetch_anthropic_models(base_url: str, api_key: str) -> list[str]:
    async with httpx2.AsyncClient(
        timeout=15.0, headers={"x-api-key": api_key, "anthropic-version": _API_VERSION}
    ) as client:
        try:
            response = await client.get(f"{base_url.rstrip('/')}/v1/models")
        except httpx2.HTTPError as exc:
            raise LLMError("llm_unreachable", f"Anthropic injoignable : {exc}") from exc
        if response.status_code != 200:
            raise LLMError(
                "llm_http_error",
                f"Liste des modèles refusée ({response.status_code}) : {response.text[:200]}",
            )
        return [str(entry["id"]) for entry in response.json().get("data", [])]
