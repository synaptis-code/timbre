"""Boucle de conversation.

Phase 3 : texte → LLM (streaming) → découpage en phrases → TTS phrase par
phrase, EN PARALLÈLE de la génération (latence perçue minimale, §14 du plan).
L'ASR/VAD (Phase 4) se branchera en amont.
"""

import asyncio
import logging
from base64 import b64encode

from timbre.core.segmenter import SentenceSplitter
from timbre.core.session import Session
from timbre.core.tts_text import clean_for_tts, is_speakable
from timbre.plugins.base import LLMBackend, LLMError, TTSBackend, TTSError
from timbre.protocol.messages import AiAudio, AiChunk, ErrorMessage, ModelInfo, UserMessage
from timbre.protocol.states import AppState

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(
        self,
        llm: LLMBackend,
        tts: TTSBackend | None = None,
        tts_voice: str = "",
    ) -> None:
        self._llm = llm
        self._tts = tts
        self._tts_voice = tts_voice

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

        splitter = SentenceSplitter()
        sentences: asyncio.Queue[str | None] = asyncio.Queue()
        speaker: asyncio.Task[None] | None = None
        if self._tts is not None:
            speaker = asyncio.create_task(self._speak_sentences(session, sentences))

        emitted: list[str] = []
        try:
            try:
                async for token in self._llm.stream_chat(conversation.to_messages()):
                    emitted.append(token)
                    await session.send(AiChunk(text=token))
                    for sentence in splitter.feed(token):
                        sentences.put_nowait(sentence)
                await session.send(AiChunk(text="", last=True))
            except LLMError as exc:
                logger.warning("génération interrompue (%s) : %s", exc.code, exc.message)
                if emitted:
                    await session.send(AiChunk(text="", last=True))
                await session.send(ErrorMessage(code=exc.code, message=exc.message))
        finally:
            if speaker is not None:
                for sentence in splitter.flush():
                    sentences.put_nowait(sentence)
                sentences.put_nowait(None)
                await speaker
            # Seul le texte réellement émis entre dans l'historique (bug n°3).
            conversation.add_assistant("".join(emitted))
            await session.set_state(AppState.IDLE)

    async def _speak_sentences(
        self, session: Session, sentences: asyncio.Queue[str | None]
    ) -> None:
        """Synthétise chaque phrase dès qu'elle est close, pendant que le LLM continue.

        Une panne TTS est signalée UNE fois puis la voix est coupée pour le tour ;
        le texte, lui, continue d'arriver — jamais de tour perdu pour un souci audio.
        """
        assert self._tts is not None
        failed = False
        while (sentence := await sentences.get()) is not None:
            text = clean_for_tts(sentence)
            if failed or not is_speakable(text):
                continue
            try:
                audio = b"".join(
                    [chunk async for chunk in self._tts.synthesize(text, self._tts_voice)]
                )
            except TTSError as exc:
                failed = True
                logger.warning("TTS en panne pour ce tour (%s) : %s", exc.code, exc.message)
                await session.send(ErrorMessage(code=exc.code, message=exc.message))
                continue
            except Exception:
                failed = True
                logger.exception("erreur TTS inattendue")
                await session.send(
                    ErrorMessage(
                        code="tts_failed",
                        message="Erreur TTS inattendue — voir les logs serveur.",
                    )
                )
                continue
            if not audio:
                continue
            await session.set_state(AppState.SPEAKING)
            await session.send(AiAudio(audio_b64=b64encode(audio).decode("ascii"), text=text))
