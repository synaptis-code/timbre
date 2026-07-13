"""Interfaces des moteurs. Ajouter un moteur = implémenter une de ces classes,
dans un fichier de son sous-package (plugins/tts/, plugins/llm/, plugins/asr/) —
rien d'autre ne bouge dans le code.

Les signatures suivent les contrats du cahier des charges (§5). Elles seront
affinées à la phase qui branche chaque moteur (3 : TTS, 4 : ASR/VAD).
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Literal


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
    def stream_chat(
        self, messages: list[dict[str, object]], temperature: float | None = None
    ) -> AsyncIterator[str]:
        """Émet la réponse token par token. Lève `LLMError` en cas de problème.

        `temperature=None` : valeur par défaut du backend (les personas la surchargent).
        """

    async def supports_vision(self) -> bool | None:
        """Le modèle actif accepte-t-il les images ? None = indéterminé (on tente)."""
        return None

    async def aclose(self) -> None:  # noqa: B027 — no-op volontaire, surcharge optionnelle
        """Libère les ressources (connexions HTTP…). No-op par défaut."""


class ASRError(Exception):
    """Erreur ASR destinée à l'utilisateur : code stable + message clair."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ASRBackend(ABC):
    """Transcription parole → texte."""

    @abstractmethod
    async def transcribe(self, audio: bytes) -> str:
        """Transcrit un enregistrement (WAV/MP3…). Lève `ASRError` en cas de problème."""

    @property
    def device(self) -> str | None:
        """Périphérique d'inférence ("cuda"/"cpu"), None si sans objet."""
        return None

    def set_device(self, device: str) -> None:
        """Bascule CPU/GPU. Lève `ASRError` si le moteur ne le permet pas."""
        raise ASRError(
            "asr_device_unsupported",
            "Ce moteur ASR ne permet pas de changer de périphérique.",
        )


class TTSError(Exception):
    """Erreur TTS destinée à l'utilisateur : code stable + message clair."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class TTSBackend(ABC):
    """Synthèse texte → audio, streaming phrase par phrase."""

    #: Conteneur produit par `synthesize` — "mp3" (edge-tts) ou "wav" (Piper local).
    audio_format: Literal["mp3", "wav"] = "mp3"

    @abstractmethod
    def synthesize(
        self, text: str, voice: str, rate: float = 1.0, pitch: int = 0
    ) -> AsyncIterator[bytes]:
        """Émet l'audio (voir `audio_format`) par blocs. Lève `TTSError` en cas de problème.

        `rate` : vitesse (1.0 = normale) ; `pitch` : décalage en Hz relatifs.
        """
