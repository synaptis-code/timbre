"""Backend générique pour tout service exposant l'API OpenAI (/chat/completions).

Couvre la grande majorité des fournisseurs : Ollama, LocalAI, OpenAI, Gemini
(endpoint de compatibilité), NVIDIA NIM, Together, DeepSeek, Groq, Mistral,
OpenRouter, xAI, Perplexity, Fireworks, SambaNova, Lemonade…
"""

import logging
from collections.abc import AsyncIterator

import httpx2

from timbre.plugins.base import LLMBackend, LLMError
from timbre.plugins.llm.sse import SSEChatParser

logger = logging.getLogger(__name__)


class OpenAICompatibleBackend(LLMBackend):
    def __init__(
        self,
        base_url: str,
        *,
        provider_name: str,
        api_key: str | None = None,
        model: str | None = None,
        temperature: float = 0.8,
        client: httpx2.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._provider_name = provider_name
        self._model = model
        self._temperature = temperature
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = client or httpx2.AsyncClient(
            timeout=httpx2.Timeout(15.0, read=300.0), headers=headers
        )
        self._warned_models: set[str] = set()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def active_model(self) -> str:
        if not self._model:
            raise LLMError(
                "no_model_selected",
                f"Aucun modèle choisi pour {self._provider_name} — Réglages → Fournisseur d'IA.",
            )
        return self._model

    async def stream_chat(
        self, messages: list[dict[str, object]], temperature: float | None = None
    ) -> AsyncIterator[str]:
        model = await self.active_model()
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self._temperature,
            "stream": True,
        }
        try:
            async with self._client.stream(
                "POST", f"{self._base_url}/chat/completions", json=payload
            ) as response:
                if response.status_code != 200:
                    body = (await response.aread()).decode("utf-8", errors="replace")
                    raise LLMError(
                        "llm_http_error",
                        f"{self._provider_name} a répondu {response.status_code} : {body[:300]}",
                    )
                parser = SSEChatParser(model, self._warned_models)
                async for line in response.aiter_lines():
                    token = parser.parse(line)
                    if token is not None:
                        yield token
        except httpx2.HTTPError as exc:
            raise LLMError(
                "llm_unreachable",
                f"{self._provider_name} injoignable ({self._base_url}) : {exc}",
            ) from exc


async def fetch_openai_models(
    base_url: str, api_key: str | None, client: httpx2.AsyncClient | None = None
) -> list[str]:
    """Liste les modèles via GET /models (format OpenAI)."""
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    owns_client = client is None
    http = client or httpx2.AsyncClient(timeout=15.0)
    try:
        response = await http.get(f"{base_url.rstrip('/')}/models", headers=headers)
        if response.status_code != 200:
            raise LLMError(
                "llm_http_error",
                f"Liste des modèles refusée ({response.status_code}) : {response.text[:200]}",
            )
        entries = response.json().get("data", [])
        return sorted(str(entry["id"]) for entry in entries if "id" in entry)
    except httpx2.HTTPError as exc:
        raise LLMError("llm_unreachable", f"Fournisseur injoignable : {exc}") from exc
    finally:
        if owns_client:
            await http.aclose()
