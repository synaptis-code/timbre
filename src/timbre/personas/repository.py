"""Accès aux personas stockés en base locale.

Remplace l'ancien `PersonaStore` fondé sur des fichiers JSON : les personas
sont désormais créés et édités depuis l'UI (V2.3). Validés par pydantic à
l'écriture, ils sont donc toujours valides en lecture — plus de fichier à la
main, plus de fallback silencieux.
"""

from timbre.personas.models import Persona
from timbre.storage import Storage


class PersonaError(Exception):
    """Erreur persona destinée à l'utilisateur : code stable + raison claire."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class PersonaRepository:
    def __init__(self, storage: Storage, fallback: Persona | None = None) -> None:
        self._storage = storage
        self._fallback = fallback

    async def list(self) -> list[Persona]:
        return await self._storage.list_personas()

    async def get(self, persona_id: str) -> Persona:
        if persona_id == "defaut" and self._fallback is not None:
            return self._fallback
        persona = await self._storage.get_persona(persona_id)
        if persona is None:
            raise PersonaError("persona_not_found", f"Persona « {persona_id} » introuvable.")
        return persona
