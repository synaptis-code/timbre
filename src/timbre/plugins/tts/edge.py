"""Backend TTS edge-tts : voix neurales FR de qualité, faible latence.

Moteur par défaut du MVP pour valider le pipeline (§1 du plan). ⚠️ Exception
assumée au local-first : edge-tts envoie le texte au service Edge de Microsoft.
Les moteurs expressifs 100 % locaux (Orpheus, Chatterbox…) se brancheront sur
la même interface `TTSBackend` aux phases suivantes.
"""

import logging
from collections.abc import AsyncIterator

import edge_tts

from timbre.plugins.base import TTSBackend, TTSError

logger = logging.getLogger(__name__)


class EdgeTTSBackend(TTSBackend):
    async def synthesize(self, text: str, voice: str) -> AsyncIterator[bytes]:
        communicate = edge_tts.Communicate(text, voice)
        got_audio = False
        try:
            async for chunk in communicate.stream():
                data = chunk.get("data")
                if chunk.get("type") == "audio" and isinstance(data, bytes):
                    got_audio = True
                    yield data
        except Exception as exc:
            raise TTSError(
                "tts_failed",
                f"edge-tts a échoué (voix « {voice} ») : {exc}. "
                "Vérifie la connexion réseau ou change de voix.",
            ) from exc
        if not got_audio:
            raise TTSError(
                "tts_failed",
                f"edge-tts n'a produit aucun audio pour la voix « {voice} » — "
                "identifiant de voix invalide ?",
            )
