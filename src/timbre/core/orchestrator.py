"""Boucle de conversation.

Phase 1 : simple écho pour valider le pipeline WebSocket de bout en bout.
Deviendra la boucle ASR → LLM → TTS (streaming phrase par phrase) aux phases suivantes.
"""

from timbre.core.session import Session
from timbre.protocol.messages import AiChunk, UserMessage
from timbre.protocol.states import AppState


class Orchestrator:
    async def handle_user_message(self, session: Session, message: UserMessage) -> None:
        await session.set_state(AppState.THINKING)
        await session.send(AiChunk(text=f"Écho : {message.text}", last=True))
        await session.set_state(AppState.IDLE)
