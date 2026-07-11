"""Parsing partagé des flux SSE « chat completions » (format OpenAI)."""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class SSEChatParser:
    """Extrait les tokens d'un flux SSE, en filtrant le raisonnement.

    `warned_models` est partagé par le backend : l'avertissement « modèle
    raisonnant » n'est émis qu'une fois par modèle (§3.5 du plan).
    """

    def __init__(self, model: str, warned_models: set[str]) -> None:
        self._model = model
        self._warned_models = warned_models

    def parse(self, line: str) -> str | None:
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
        # Les modèles « raisonnants » émettent reasoning_content avant de
        # répondre : on ne l'affiche pas et on prévient (latence).
        if delta.get("reasoning_content") and self._model not in self._warned_models:
            self._warned_models.add(self._model)
            logger.warning(
                "%s est un modèle 'raisonnant' : latence élevée à prévoir. "
                "Préférer un modèle Instruct pour le vocal.",
                self._model,
            )
        content = delta.get("content")
        return str(content) if content else None
