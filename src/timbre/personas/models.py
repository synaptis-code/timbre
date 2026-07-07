"""Schéma d'un persona (§11 du plan) : JSON strict, impossible à casser sans le savoir.

Tout champ inconnu ou invalide est rejeté à la lecture avec une raison claire —
l'inverse du YAML fragile du projet de référence (bug n°1).
"""

from pydantic import BaseModel, ConfigDict, Field


class VoiceParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rate: float = Field(default=1.0, ge=0.5, le=2.0, description="Vitesse (1.0 = normale)")
    pitch: int = Field(default=0, ge=-50, le=50, description="Hauteur en Hz relatifs")


class VoiceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engine: str = "edge-tts"
    voice_id: str = Field(min_length=1)
    params: VoiceParams = VoiceParams()


class Persona(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,31}$")
    name: str = Field(min_length=1)
    language: str = "fr"
    system_prompt: str = Field(min_length=1)
    voice: VoiceConfig
    greeting: str = ""
    temperature: float = Field(default=0.8, ge=0.0, le=2.0)
