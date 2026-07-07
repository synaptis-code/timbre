"""Boucle de conversation.

Phase 3 : texte → LLM (streaming) → découpage en phrases → TTS phrase par
phrase, EN PARALLÈLE de la génération (latence perçue minimale, §14 du plan).
L'ASR/VAD (Phase 4) se branchera en amont.
"""

import asyncio
import binascii
import contextlib
import logging
from base64 import b64decode, b64encode

from timbre.core.segmenter import SentenceSplitter
from timbre.core.session import Session
from timbre.core.tts_text import clean_for_tts, is_speakable
from timbre.plugins.base import ASRBackend, ASRError, LLMBackend, LLMError, TTSBackend, TTSError
from timbre.protocol.messages import (
    AiAudio,
    AiChunk,
    ErrorMessage,
    ModelInfo,
    UserAudio,
    UserMessage,
    UserTranscript,
)
from timbre.protocol.states import AppState

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(
        self,
        llm: LLMBackend,
        tts: TTSBackend | None = None,
        tts_voice: str = "",
        asr: ASRBackend | None = None,
    ) -> None:
        self._llm = llm
        self._tts = tts
        self._tts_voice = tts_voice
        self._asr = asr

    async def announce_model(self, session: Session) -> None:
        """Détecte le modèle actif et l'annonce au client ; erreur explicite sinon."""
        try:
            await session.send(ModelInfo(model=await self._llm.active_model()))
        except LLMError as exc:
            await session.send(ErrorMessage(code=exc.code, message=exc.message))

    async def handle_user_message(self, session: Session, message: UserMessage) -> None:
        await self._generate_reply(session, message.text)

    async def handle_user_audio(self, session: Session, message: UserAudio) -> None:
        """Une prise de parole : transcription puis tour de conversation normal."""
        if self._asr is None:
            await session.send(
                ErrorMessage(
                    code="asr_unavailable",
                    message="La transcription vocale est désactivée (TIMBRE_ASR_ENABLED=0).",
                )
            )
            return
        await session.set_state(AppState.THINKING)
        try:
            audio = b64decode(message.audio_b64, validate=True)
        except binascii.Error:
            await session.send(
                ErrorMessage(code="invalid_audio", message="Audio illisible (base64 invalide).")
            )
            await session.set_state(AppState.IDLE)
            return
        try:
            transcript = await self._asr.transcribe(audio)
        except ASRError as exc:
            await session.send(ErrorMessage(code=exc.code, message=exc.message))
            await session.set_state(AppState.IDLE)
            return
        if not transcript:
            await session.send(
                ErrorMessage(
                    code="asr_empty",
                    message="Je n'ai rien entendu de clair — parle un peu plus fort ?",
                )
            )
            await session.set_state(AppState.IDLE)
            return
        await session.send(UserTranscript(text=transcript))
        await self._generate_reply(session, transcript)

    async def _generate_reply(self, session: Session, user_text: str) -> None:
        conversation = session.conversation
        conversation.add_user(user_text)
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
        interrupted = False
        try:
            try:
                async for token in self._llm.stream_chat(conversation.to_messages()):
                    emitted.append(token)
                    await session.send(AiChunk(text=token))
                    for sentence in splitter.feed(token):
                        sentences.put_nowait(sentence)
                await session.send(AiChunk(text="", last=True))
            except asyncio.CancelledError:
                # Interruption (bouton Stop ou nouvelle prise de parole) : on coupe
                # court, sans corrompre l'historique (bug n°3).
                interrupted = True
            except LLMError as exc:
                logger.warning("génération interrompue (%s) : %s", exc.code, exc.message)
                if emitted:
                    await session.send(AiChunk(text="", last=True))
                await session.send(ErrorMessage(code=exc.code, message=exc.message))
            # Voix : drain complet en fin normale, coupure sèche si interrompu.
            if speaker is not None:
                if interrupted:
                    speaker.cancel()
                else:
                    for sentence in splitter.flush():
                        sentences.put_nowait(sentence)
                    sentences.put_nowait(None)
                with contextlib.suppress(asyncio.CancelledError):
                    await speaker
        except asyncio.CancelledError:
            # Annulation reçue pendant le drain de la voix.
            interrupted = True
            if speaker is not None:
                speaker.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await speaker
        finally:
            if interrupted and emitted:
                await session.send(AiChunk(text="", last=True, interrupted=True))
            # Seul le texte réellement émis entre dans l'historique (bug n°3) —
            # un tour interrompu est archivé tel quel, jamais inventé.
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
