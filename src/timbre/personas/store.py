"""Chargement des personas : validation stricte, isolation par fichier.

Règles by-design (bugs n°1 et 2 du plan) :
- chaque fichier est validé indépendamment : un persona cassé n'empêche JAMAIS
  les autres de charger ;
- toute erreur est portée par un statut explicite (fichier, raison) destiné à
  l'UI — jamais de fallback silencieux ;
- re-scan du dossier à chaque appel : éditer un fichier = effet immédiat
  (rechargement à chaud, §11).
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from timbre.personas.models import Persona

logger = logging.getLogger(__name__)


class PersonaError(Exception):
    """Erreur persona destinée à l'utilisateur : code stable + raison claire."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class PersonaStatus:
    """Résultat de lecture d'un fichier persona : valide OU erreur, jamais ni-ni."""

    id: str  # id du persona, ou nom du fichier si illisible
    file: str
    persona: Persona | None
    error: str | None


class PersonaStore:
    def __init__(self, directory: Path, known_engines: set[str] | None = None) -> None:
        """`known_engines=None` : TTS désactivé, le moteur n'est pas vérifié."""
        self._directory = directory
        self._known_engines = known_engines

    def scan(self) -> list[PersonaStatus]:
        if not self._directory.is_dir():
            logger.warning("dossier de personas introuvable : %s", self._directory)
            return []
        statuses: list[PersonaStatus] = []
        seen_ids: set[str] = set()
        for file in sorted(self._directory.glob("*.json")):
            status = self._read_file(file)
            if status.persona is not None and status.persona.id in seen_ids:
                status = PersonaStatus(
                    id=status.id,
                    file=status.file,
                    persona=None,
                    error=f"id « {status.id} » déjà utilisé par un autre fichier",
                )
            if status.persona is not None:
                seen_ids.add(status.persona.id)
            statuses.append(status)
        return statuses

    def get(self, persona_id: str) -> Persona:
        """Renvoie le persona valide, ou lève une `PersonaError` explicite."""
        for status in self.scan():
            if status.id != persona_id:
                continue
            if status.persona is None:
                raise PersonaError(
                    "persona_invalid",
                    f"Persona « {persona_id} » invalide ({status.file}) : {status.error}",
                )
            return status.persona
        raise PersonaError(
            "persona_not_found",
            f"Persona « {persona_id} » introuvable dans {self._directory}.",
        )

    def _read_file(self, file: Path) -> PersonaStatus:
        try:
            # utf-8-sig : tolère le BOM que Notepad/PowerShell ajoutent sous Windows.
            data = json.loads(file.read_text(encoding="utf-8-sig"))
            persona = Persona.model_validate(data)
        except json.JSONDecodeError as exc:
            return PersonaStatus(
                id=file.stem, file=file.name, persona=None, error=f"JSON illisible : {exc}"
            )
        except ValidationError as exc:
            details = " ; ".join(
                f"{'.'.join(str(loc) for loc in err['loc']) or '<racine>'} : {err['msg']}"
                for err in exc.errors()
            )
            return PersonaStatus(id=file.stem, file=file.name, persona=None, error=details)
        except OSError as exc:
            return PersonaStatus(
                id=file.stem, file=file.name, persona=None, error=f"lecture impossible : {exc}"
            )
        if self._known_engines is not None and persona.voice.engine not in self._known_engines:
            return PersonaStatus(
                id=persona.id,
                file=file.name,
                persona=None,
                error=(
                    f"moteur TTS inconnu : « {persona.voice.engine} » "
                    f"(disponibles : {', '.join(sorted(self._known_engines))})"
                ),
            )
        return PersonaStatus(id=persona.id, file=file.name, persona=persona, error=None)
