"""Backend ASR faster-whisper (GPU par défaut, CPU en un réglage).

Le modèle est chargé paresseusement au premier usage puis gardé chaud en
mémoire. La transcription (bibliothèque bloquante) tourne dans un thread
pour ne jamais bloquer la boucle asyncio.
"""

import asyncio
import io
import logging
from typing import TYPE_CHECKING

from timbre.plugins.asr.cuda import add_cuda_dll_directories
from timbre.plugins.base import ASRBackend, ASRError

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


class FasterWhisperASR(ASRBackend):
    def __init__(
        self,
        model: str = "large-v3-turbo",
        device: str = "cpu",
        compute_type: str | None = None,
        language: str | None = None,
    ) -> None:
        self._model_name = model
        self._device = device
        self._compute_type = compute_type or ("float16" if device == "cuda" else "int8")
        self._language = language
        self._model: WhisperModel | None = None
        self._load_lock = asyncio.Lock()

    @property
    def device(self) -> str:
        return self._device

    def set_device(self, device: str) -> None:
        """Bascule CPU/GPU en un clic : le modèle est rechargé au prochain usage."""
        if device == self._device:
            return
        logger.info(
            "device Whisper : %s → %s (rechargement au prochain tour)", self._device, device
        )
        self._device = device
        self._compute_type = "float16" if device == "cuda" else "int8"
        self._model = None

    async def transcribe(self, audio: bytes) -> str:
        model = await self._ensure_model()
        try:
            return await asyncio.to_thread(self._transcribe_sync, model, audio)
        except ASRError:
            raise
        except Exception as exc:
            raise ASRError("asr_failed", f"Transcription échouée : {exc}") from exc

    async def _ensure_model(self) -> "WhisperModel":
        if self._model is None:
            async with self._load_lock:
                if self._model is None:
                    logger.info(
                        "chargement du modèle Whisper « %s » (%s, %s)…",
                        self._model_name,
                        self._device,
                        self._compute_type,
                    )
                    self._model = await asyncio.to_thread(self._load_model)
                    logger.info("modèle Whisper prêt")
        return self._model

    def _load_model(self) -> "WhisperModel":
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise ASRError(
                "asr_unavailable",
                "faster-whisper n'est pas installé — lance `uv sync --extra asr`.",
            ) from exc
        add_cuda_dll_directories()
        try:
            return WhisperModel(
                self._model_name, device=self._device, compute_type=self._compute_type
            )
        except Exception as exc:
            raise ASRError(
                "asr_failed",
                f"Chargement de Whisper « {self._model_name} » sur {self._device} échoué : "
                f"{exc}. Essaie TIMBRE_ASR_DEVICE=cpu.",
            ) from exc

    def _transcribe_sync(self, model: "WhisperModel", audio: bytes) -> str:
        segments, _info = model.transcribe(
            io.BytesIO(audio),
            language=self._language or None,  # None = détection automatique
            beam_size=1,  # latence d'abord (§14) ; la voix est courte et proche
            condition_on_previous_text=False,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()
