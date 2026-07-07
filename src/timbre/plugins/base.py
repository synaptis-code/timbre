"""Interfaces des moteurs. Ajouter un moteur = implémenter une de ces classes,
dans un fichier de son sous-package (plugins/tts/, plugins/llm/, plugins/asr/) —
rien d'autre ne bouge dans le code.

Les signatures suivent les contrats du cahier des charges (§5). Elles seront
affinées à la phase qui branche chaque moteur (3 : TTS, 4 : ASR/VAD).
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class LLMError(Exception):
    """Erreur LLM destinée à l'utilisateur : code stable + message clair et guidant.

    Jamais avalée : la couche API la transforme en message `error` visible dans l'UI.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class LLMBackend(ABC):
    """Génération de texte en streaming (LM Studio ou tout endpoint OpenAI-compatible)."""

    @abstractmethod
    async def active_model(self) -> str:
        """Identifiant du modèle actuellement actif.

        Lève `LLMError` si le serveur est injoignable ou si aucun modèle n'est chargé.
        """

    @abstractmethod
    def stream_chat(self, messages: list[dict[str, object]]) -> AsyncIterator[str]:
        """Émet la réponse token par token. Lève `LLMError` en cas de problème."""

    async def aclose(self) -> None:  # noqa: B027 — no-op volontaire, surcharge optionnelle
        """Libère les ressources (connexions HTTP…). No-op par défaut."""


class ASRBackend(ABC):
    """Transcription parole → texte."""

    @abstractmethod
    async def transcribe(self, audio: bytes) -> str: ...


class TTSError(Exception):
    """Erreur TTS destinée à l'utilisateur : code stable + message clair."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class TTSBackend(ABC):
    """Synthèse texte → audio, streaming phrase par phrase."""

    @abstractmethod
    def synthesize(self, text: str, voice: str) -> AsyncIterator[bytes]:
        """Émet l'audio (MP3) par blocs. Lève `TTSError` en cas de problème."""
