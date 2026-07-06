"""Interfaces des moteurs. Ajouter un moteur = implémenter une de ces classes,
dans un fichier de son sous-package (plugins/tts/, plugins/llm/, plugins/asr/) —
rien d'autre ne bouge dans le code.

Les signatures suivent les contrats du cahier des charges (§5). Elles seront
affinées à la phase qui branche chaque moteur (2 : LLM, 3 : TTS, 4 : ASR/VAD).
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class LLMBackend(ABC):
    """Génération de texte en streaming (LM Studio ou tout endpoint OpenAI-compatible)."""

    @abstractmethod
    def stream_chat(
        self, messages: list[dict[str, object]], images: list[str] | None = None
    ) -> AsyncIterator[str]:
        """Émet la réponse token par token. `images` : data-URLs pour le multimodal."""


class ASRBackend(ABC):
    """Transcription parole → texte."""

    @abstractmethod
    async def transcribe(self, audio: bytes) -> str: ...


class TTSBackend(ABC):
    """Synthèse texte → audio, streaming phrase par phrase."""

    @abstractmethod
    def synthesize(self, text: str, voice: str) -> AsyncIterator[bytes]:
        """Émet l'audio par blocs prêts à jouer."""
