"""Configuration du serveur, surchargée par variables d'environnement TIMBRE_*."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TIMBRE_")

    host: str = "127.0.0.1"
    port: int = 8765
    log_level: str = "INFO"

    # LLM (LM Studio ou tout serveur OpenAI-compatible local)
    lmstudio_base_url: str = "http://127.0.0.1:1234"
    # None = auto-détection du modèle chargé dans LM Studio (recommandé).
    llm_model: str | None = None
    llm_temperature: float = 0.8
    # Prompt système par défaut — remplacé par les personas en Phase 6.
    system_prompt: str = (
        "Tu es un assistant vocal français, chaleureux et concis. "
        "Tu réponds en phrases courtes et naturelles, comme à l'oral, sans listes ni Markdown."
    )
