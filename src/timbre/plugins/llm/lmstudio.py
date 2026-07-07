"""Backend LLM LM Studio (API OpenAI-compatible), streaming.

Aucun nom de modèle codé en dur : à chaque tour, on interroge LM Studio pour
utiliser **le modèle réellement chargé**. Changer de modèle dans LM Studio
suffit — Timbre suit automatiquement. `TIMBRE_LLM_MODEL` permet de forcer un
modèle précis si besoin.
"""

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx2

from timbre.plugins.base import LLMBackend, LLMError

logger = logging.getLogger(__name__)

_START_HINT = (
    "Démarre le serveur local dans LM Studio (onglet Développeur → « Start server ») "
    "ou lance `lms server start`."
)
_LOAD_HINT = "Charge un modèle dans LM Studio (ou `lms load <modèle>`), puis réessaie."


class LMStudioBackend(LLMBackend):
    def __init__(
        self,
        base_url: str,
        *,
        model_override: str | None = None,
        temperature: float = 0.8,
        client: httpx2.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model_override = model_override
        self._temperature = temperature
        self._client = client or httpx2.AsyncClient(timeout=httpx2.Timeout(10.0, read=300.0))
        self._warned_reasoning_model: str | None = None
        # Type du dernier modèle résolu ("llm" | "vlm" | None si inconnu).
        self._active_model_type: str | None = None

    async def aclose(self) -> None:
        await self._client.aclose()

    async def active_model(self) -> str:
        if self._model_override is not None:
            return self._model_override

        # API native de LM Studio : expose l'état loaded/not-loaded de chaque modèle.
        response = await self._get("/api/v0/models")
        if response.status_code == 200:
            loaded = [
                entry
                for entry in response.json().get("data", [])
                if entry.get("state") == "loaded" and entry.get("type") in ("llm", "vlm")
            ]
            if not loaded:
                raise LLMError(
                    "no_model_loaded", f"Aucun modèle chargé dans LM Studio. {_LOAD_HINT}"
                )
            if len(loaded) > 1:
                ids = [str(entry["id"]) for entry in loaded]
                logger.info("plusieurs modèles chargés %s → utilisation de %s", ids, ids[0])
            self._active_model_type = str(loaded[0].get("type") or "") or None
            return str(loaded[0]["id"])

        # Repli pour les versions de LM Studio sans /api/v0 : /v1/models liste les
        # modèles servis (sans état de chargement).
        response = await self._get("/v1/models")
        if response.status_code != 200:
            raise LLMError(
                "llm_http_error",
                f"LM Studio a répondu {response.status_code} sur /v1/models. {_START_HINT}",
            )
        entries = response.json().get("data", [])
        if not entries:
            raise LLMError(
                "no_model_loaded", f"Aucun modèle disponible dans LM Studio. {_LOAD_HINT}"
            )
        self._active_model_type = None  # /v1/models ne donne pas le type
        return str(entries[0]["id"])

    async def supports_vision(self) -> bool | None:
        """Fondé sur le type ("llm"/"vlm") du dernier modèle résolu par active_model."""
        if self._model_override is not None or self._active_model_type is None:
            return None
        return self._active_model_type == "vlm"

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
                "POST", f"{self._base_url}/v1/chat/completions", json=payload
            ) as response:
                if response.status_code != 200:
                    body = (await response.aread()).decode("utf-8", errors="replace")
                    raise LLMError(
                        "llm_http_error",
                        f"LM Studio a répondu {response.status_code} : {body[:300]}",
                    )
                async for line in response.aiter_lines():
                    token = self._parse_sse_line(line, model)
                    if token is not None:
                        yield token
        except httpx2.HTTPError as exc:
            raise LLMError(
                "llm_unreachable",
                f"Connexion à LM Studio perdue pendant la génération : {exc}. {_START_HINT}",
            ) from exc

    def _parse_sse_line(self, line: str, model: str) -> str | None:
        if not line.startswith("data: "):
            return None
        data = line[len("data: ") :].strip()
        if not data or data == "[DONE]":
            return None
        try:
            choices = json.loads(data).get("choices", [])
        except json.JSONDecodeError:
            logger.warning("ligne SSE illisible ignorée : %.200s", data)
            return None
        if not choices:
            return None
        delta: dict[str, Any] = choices[0].get("delta", {})
        # Les modèles « raisonnants » émettent reasoning_content avant de répondre :
        # on ne l'affiche pas et on prévient (latence — voir §3.5 du plan).
        if delta.get("reasoning_content") and self._warned_reasoning_model != model:
            self._warned_reasoning_model = model
            logger.warning(
                "%s est un modèle 'raisonnant' : latence élevée à prévoir. "
                "Préférer un modèle Instruct pour le vocal.",
                model,
            )
        content = delta.get("content")
        return str(content) if content else None

    async def _get(self, path: str) -> httpx2.Response:
        try:
            return await self._client.get(f"{self._base_url}{path}")
        except httpx2.HTTPError as exc:
            raise LLMError(
                "llm_unreachable",
                f"LM Studio injoignable sur {self._base_url}. {_START_HINT}",
            ) from exc
