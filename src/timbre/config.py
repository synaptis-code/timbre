"""Configuration du serveur, surchargée par variables d'environnement TIMBRE_*."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TIMBRE_")

    host: str = "127.0.0.1"
    port: int = 8765
    log_level: str = "INFO"
