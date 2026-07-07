"""Doubles de test partagés."""

from collections.abc import AsyncIterator

from timbre.plugins.base import LLMBackend, LLMError


class FakeLLM(LLMBackend):
    """LLM factice : émet des tokens prédéfinis et enregistre ce qu'il reçoit."""

    def __init__(
        self,
        tokens: list[str] | None = None,
        *,
        model: str = "fake-model",
        error: LLMError | None = None,
        fail_after: int | None = None,
    ) -> None:
        self.tokens = tokens if tokens is not None else ["Bon", "jour", " !"]
        self.model = model
        self.error = error
        self.fail_after = fail_after
        self.received_messages: list[list[dict[str, object]]] = []

    async def active_model(self) -> str:
        if self.error is not None:
            raise self.error
        return self.model

    async def stream_chat(self, messages: list[dict[str, object]]) -> AsyncIterator[str]:
        if self.error is not None:
            raise self.error
        self.received_messages.append(messages)
        for index, token in enumerate(self.tokens):
            if self.fail_after is not None and index >= self.fail_after:
                raise LLMError("llm_unreachable", "connexion perdue (simulée)")
            yield token
