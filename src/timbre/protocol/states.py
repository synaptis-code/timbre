"""États de l'assistant, source de vérité côté backend."""

from enum import StrEnum


class AppState(StrEnum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
