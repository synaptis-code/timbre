"""Boucle de conversation.

Phase 2 : texte → LLM (streaming token par token) → texte.
Le TTS (Phase 3) puis l'ASR/VAD (Phase 4) se brancheront autour de cette boucle.
"""

import logging

from timbre.core.session import Session
from timbre.plugins.base import LLMBackend, LLMError
from timbre.protocol.messages import AiChunk, ErrorMessage, ModelInfo, UserMessage
from timbre.protocol.states import AppState

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, llm: LLMBackend) -> None:
        self._llm = llm

    async def announce_model(self, session: Session) -> None:
        """Détecte le modèle actif et l'annonce au client ; erreur explicite sinon."""
        try:
            await session.send(ModelInfo(model=await self._llm.active_model()))
        except LLMError as exc:
            await session.send(ErrorMessage(code=exc.code, message=exc.message))

    async def handle_user_message(self, session: Session, message: UserMessage) -> None:
        conversation = session.conversation
        conversation.add_user(message.text)
        await session.set_state(AppState.THINKING)

        try:
            model = await self._llm.active_model()
        except LLMError as exc:
            await session.send(ErrorMessage(code=exc.code, message=exc.message))
            await session.set_state(AppState.IDLE)
            return
        # Ré-annoncé à chaque tour : si l'utilisateur change de modèle dans
        # LM Studio, l'UI le reflète immédiatement.
        await session.send(ModelInfo(model=model))

        emitted: list[str] = []
        try:
            async for token in self._llm.stream_chat(conversation.to_messages()):
                emitted.append(token)
                await session.send(AiChunk(text=token))
            await session.send(AiChunk(text="", last=True))
        except LLMError as exc:
            logger.warning("génération interrompue (%s) : %s", exc.code, exc.message)
            if emitted:
                await session.send(AiChunk(text="", last=True))
            await session.send(ErrorMessage(code=exc.code, message=exc.message))
        finally:
            # Seul le texte réellement émis entre dans l'historique (bug n°3).
            conversation.add_assistant("".join(emitted))
            await session.set_state(AppState.IDLE)
