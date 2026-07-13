"""Configuration du serveur, surchargée par variables d'environnement TIMBRE_*."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TIMBRE_")

    host: str = "127.0.0.1"
    port: int = 8765
    log_level: str = "INFO"

    # Persistance locale (conversations, messages, réglages)
    database_path: str = "timbre.db"

    # LLM (LM Studio ou tout serveur OpenAI-compatible local)
    lmstudio_base_url: str = "http://127.0.0.1:1234"
    # None = auto-détection du modèle chargé dans LM Studio (recommandé).
    llm_model: str | None = None
    llm_temperature: float = 0.8
    # ASR (faster-whisper — nécessite `uv sync --extra asr`)
    asr_enabled: bool = True
    asr_model: str = "large-v3-turbo"
    asr_device: str = "cuda"  # "cpu" si pas de GPU NVIDIA ou VRAM saturée
    asr_language: str = "fr"

    # TTS (edge-tts par défaut ; deviendra un choix de plugin avec les personas)
    tts_enabled: bool = True
    tts_voice: str = "fr-FR-VivienneMultilingualNeural"
    # Voix Piper locales téléchargées à la demande (fichiers .onnx). Hors du repo.
    piper_voices_dir: str = "voices/piper"

    # Personas (stockés en base locale ; créés/édités depuis l'UI)
    persona: str = "timbre"  # persona actif par défaut à la connexion

    # Prompt système de secours, utilisé si le persona par défaut est invalide
    # (avec une erreur explicite — jamais de bascule silencieuse).
    system_prompt: str = (
        "Tu es un assistant vocal français, chaleureux et concis. "
        "Tu réponds en phrases courtes et naturelles, comme à l'oral, sans listes ni Markdown."
    )
