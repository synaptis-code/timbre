"""Boucle de conversation.

Texte ou voix → LLM (streaming) → découpage en phrases → TTS phrase par
phrase, EN PARALLÈLE de la génération (latence perçue minimale, §14 du plan).
Le persona actif de la session pilote le prompt système, la voix (moteur,
voix, débit, hauteur) et la température.
"""

import asyncio
import binascii
import contextlib
import logging
import time
from base64 import b64decode, b64encode
from dataclasses import dataclass

from timbre.core.gpu import vram_snapshot
from timbre.core.segmenter import SentenceSplitter
from timbre.core.session import Session
from timbre.core.tts_text import clean_for_tts, is_speakable
from timbre.personas.models import Persona
from timbre.personas.store import PersonaError, PersonaStore
from timbre.plugins.base import ASRBackend, ASRError, LLMBackend, LLMError, TTSBackend, TTSError
from timbre.protocol.messages import (
    AiAudio,
    AiChunk,
    AsrInfo,
    ErrorMessage,
    ModelInfo,
    PersonaList,
    PersonaSummary,
    SetAsrDevice,
    SetPersona,
    TurnMetrics,
    UserAudio,
    UserMessage,
    UserTranscript,
)
from timbre.protocol.states import AppState

logger = logging.getLogger(__name__)


@dataclass
class _TurnTimer:
    """Chronomètre d'un tour, pour les métriques de latence (§14)."""

    started: float
    first_token_ms: int | None = None
    first_audio_ms: int | None = None

    def elapsed_ms(self) -> int:
        return round((time.perf_counter() - self.started) * 1000)


class Orchestrator:
    def __init__(
        self,
        llm: LLMBackend,
        tts_engines: dict[str, TTSBackend],
        asr: ASRBackend | None,
        persona_store: PersonaStore,
        default_persona_id: str,
        fallback_persona: Persona,
    ) -> None:
        self._llm = llm
        self._tts_engines = tts_engines
        self._asr = asr
        self._store = persona_store
        self._default_persona_id = default_persona_id
        self.fallback_persona = fallback_persona

    # ── Personas ────────────────────────────────────────────────────────────

    async def init_persona(self, session: Session) -> None:
        """Applique le persona par défaut à la connexion.

        S'il est invalide : erreur EXPLICITE + persona de secours annoncé —
        jamais de bascule silencieuse (bug n°2).
        """
        try:
            persona = self._store.get(self._default_persona_id)
        except PersonaError as exc:
            await session.send(
                ErrorMessage(
                    code=exc.code,
                    message=f"{exc.message} Persona de secours « Défaut » utilisé.",
                )
            )
            persona = self.fallback_persona
        self._apply_persona(session, persona)
        await self.send_persona_list(session)

    async def handle_set_persona(self, session: Session, message: SetPersona) -> None:
        try:
            persona = self._store.get(message.persona_id)
        except PersonaError as exc:
            # Persona courant conservé, raison affichée — pas de bascule silencieuse.
            await session.send(ErrorMessage(code=exc.code, message=exc.message))
            return
        self._apply_persona(session, persona)
        await self.send_persona_list(session)
        if persona.greeting:
            session.conversation.add_assistant(persona.greeting)
            await session.persist_message("assistant", persona.greeting)
            await session.send(AiChunk(text=persona.greeting, last=True))
            await self._speak_one(session, persona.greeting)

    async def send_persona_list(self, session: Session) -> None:
        """Re-scan du dossier à chaque appel : rechargement à chaud."""
        summaries = [
            PersonaSummary(
                id=status.id,
                name=status.persona.name if status.persona else status.id,
                valid=status.persona is not None,
                error=status.error,
            )
            for status in self._store.scan()
        ]
        await session.send(PersonaList(personas=summaries, active=session.persona.id))

    def _apply_persona(self, session: Session, persona: Persona) -> None:
        session.persona = persona
        session.conversation.set_system_prompt(persona.system_prompt)
        logger.info("persona actif : %s (%s)", persona.id, persona.voice.voice_id)

    def _engine_for(self, session: Session) -> TTSBackend | None:
        return self._tts_engines.get(session.persona.voice.engine)

    # ── ASR (device) ────────────────────────────────────────────────────────

    async def announce_asr(self, session: Session) -> None:
        if self._asr is not None and self._asr.device is not None:
            await session.send(AsrInfo(device=self._asr.device))

    async def handle_set_asr_device(self, session: Session, message: SetAsrDevice) -> None:
        if self._asr is None:
            await session.send(
                ErrorMessage(
                    code="asr_unavailable",
                    message="La transcription vocale est désactivée (TIMBRE_ASR_ENABLED=0).",
                )
            )
            return
        try:
            self._asr.set_device(message.device)
        except ASRError as exc:
            await session.send(ErrorMessage(code=exc.code, message=exc.message))
            return
        await session.send(AsrInfo(device=message.device))

    # ── Modèle ──────────────────────────────────────────────────────────────

    async def announce_model(self, session: Session) -> None:
        """Détecte le modèle actif et l'annonce au client ; erreur explicite sinon."""
        try:
            await session.send(ModelInfo(model=await self._llm.active_model()))
        except LLMError as exc:
            await session.send(ErrorMessage(code=exc.code, message=exc.message))

    # ── Tours de conversation ───────────────────────────────────────────────

    async def handle_user_message(self, session: Session, message: UserMessage) -> None:
        await self._generate_reply(session, message.text, image=message.image)

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
        asr_started = time.perf_counter()
        try:
            transcript = await self._asr.transcribe(audio)
        except ASRError as exc:
            await session.send(ErrorMessage(code=exc.code, message=exc.message))
            await session.set_state(AppState.IDLE)
            return
        asr_ms = round((time.perf_counter() - asr_started) * 1000)
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
        await self._generate_reply(session, transcript, image=message.image, asr_ms=asr_ms)

    async def _generate_reply(
        self,
        session: Session,
        user_text: str,
        image: str | None = None,
        asr_ms: int | None = None,
    ) -> None:
        conversation = session.conversation
        await session.set_state(AppState.THINKING)

        try:
            model = await self._llm.active_model()
        except LLMError as exc:
            conversation.add_user(user_text)  # la question reste dans l'historique
            await session.send(ErrorMessage(code=exc.code, message=exc.message))
            await session.set_state(AppState.IDLE)
            return
        # Ré-annoncé à chaque tour : si l'utilisateur change de modèle dans
        # LM Studio, l'UI le reflète immédiatement.
        await session.send(ModelInfo(model=model))

        # Garde vision : si le modèle chargé ne voit pas les images, on le dit
        # et on continue en texte seul — jamais d'échec silencieux ni de crash.
        if image is not None and await self._llm.supports_vision() is False:
            await session.send(
                ErrorMessage(
                    code="no_vision",
                    message=(
                        f"Le modèle « {model} » ne voit pas les images — capture ignorée. "
                        "Charge un modèle vision (ex. qwen2.5-vl) dans LM Studio."
                    ),
                )
            )
            image = None
        conversation.add_user(user_text, image=image)
        await session.persist_message("user", user_text)

        timer = _TurnTimer(started=time.perf_counter())
        splitter = SentenceSplitter()
        sentences: asyncio.Queue[str | None] = asyncio.Queue()
        speaker: asyncio.Task[None] | None = None
        if self._engine_for(session) is not None:
            speaker = asyncio.create_task(self._speak_sentences(session, sentences, timer))

        emitted: list[str] = []
        interrupted = False
        try:
            try:
                stream = self._llm.stream_chat(
                    conversation.to_messages(), temperature=session.persona.temperature
                )
                async for token in stream:
                    if timer.first_token_ms is None:
                        timer.first_token_ms = timer.elapsed_ms()
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
            assistant_text = "".join(emitted)
            conversation.add_assistant(assistant_text)
            await session.persist_message("assistant", assistant_text, interrupted)
            vram = await vram_snapshot()
            await session.send(
                TurnMetrics(
                    asr_ms=asr_ms,
                    first_token_ms=timer.first_token_ms,
                    first_audio_ms=timer.first_audio_ms,
                    total_ms=timer.elapsed_ms(),
                    vram_used_mb=vram[0] if vram is not None else None,
                    vram_total_mb=vram[1] if vram is not None else None,
                )
            )
            await session.set_state(AppState.IDLE)

    # ── Voix ────────────────────────────────────────────────────────────────

    async def _speak_sentences(
        self, session: Session, sentences: asyncio.Queue[str | None], timer: _TurnTimer
    ) -> None:
        """Synthétise chaque phrase dès qu'elle est close, pendant que le LLM continue.

        Une panne TTS est signalée UNE fois puis la voix est coupée pour le tour ;
        le texte, lui, continue d'arriver — jamais de tour perdu pour un souci audio.
        """
        failed = False
        while (sentence := await sentences.get()) is not None:
            if failed:
                continue
            audio = await self._synthesize(session, sentence)
            if audio is None:
                failed = True
            elif audio:
                if timer.first_audio_ms is None:
                    timer.first_audio_ms = timer.elapsed_ms()
                await session.set_state(AppState.SPEAKING)
                await session.send(
                    AiAudio(
                        audio_b64=b64encode(audio).decode("ascii"),
                        text=clean_for_tts(sentence),
                    )
                )

    async def _speak_one(self, session: Session, text: str) -> None:
        """Synthèse ponctuelle (message d'accueil d'un persona)."""
        audio = await self._synthesize(session, text)
        if audio:
            await session.send(
                AiAudio(audio_b64=b64encode(audio).decode("ascii"), text=clean_for_tts(text))
            )

    async def _synthesize(self, session: Session, sentence: str) -> bytes | None:
        """Renvoie l'audio d'une phrase, b"" si rien à dire, None si panne (signalée)."""
        engine = self._engine_for(session)
        text = clean_for_tts(sentence)
        if engine is None or not is_speakable(text):
            return b""
        voice = session.persona.voice
        try:
            return b"".join(
                [
                    chunk
                    async for chunk in engine.synthesize(
                        text, voice.voice_id, rate=voice.params.rate, pitch=voice.params.pitch
                    )
                ]
            )
        except TTSError as exc:
            logger.warning("TTS en panne pour ce tour (%s) : %s", exc.code, exc.message)
            await session.send(ErrorMessage(code=exc.code, message=exc.message))
            return None
        except Exception:
            logger.exception("erreur TTS inattendue")
            await session.send(
                ErrorMessage(
                    code="tts_failed",
                    message="Erreur TTS inattendue — voir les logs serveur.",
                )
            )
            return None
