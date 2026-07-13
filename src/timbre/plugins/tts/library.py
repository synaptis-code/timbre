"""Gestion à la demande des voix Piper : installation, téléchargement, état.

Vit dans `app.state.voice_library`. Pilote l'installation de l'extra `piper`, le
téléchargement des modèles (en tâche de fond, avec progression interrogeable), et
enregistre le moteur Piper dans l'orchestrateur dès qu'une voix est prête.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from timbre.plugins.tts.piper import (
    PIPER_VOICES,
    SPECS_BY_ID,
    PiperVoiceSpec,
    download_voice,
    ensure_piper_installed,
    piper_installed,
)

logger = logging.getLogger(__name__)

VoiceStatus = Literal["available", "downloading", "ready", "error"]


@dataclass
class _Download:
    received: int
    total: int
    error: str | None = None


@dataclass(frozen=True)
class VoiceState:
    """État d'une voix Piper pour l'UI."""

    id: str
    label: str
    gender: str
    size_bytes: int
    recommended: bool
    status: VoiceStatus
    received: int
    error: str | None


class VoiceLibrary:
    def __init__(self, voices_dir: Path, on_engine_ready: Callable[[], None]) -> None:
        self._dir = voices_dir
        self._on_ready = on_engine_ready
        self._downloads: dict[str, _Download] = {}  # clé = model (fichier)
        self._errors: dict[str, str] = {}  # clé = model
        self._tasks: dict[str, asyncio.Task[None]] = {}

    @property
    def package_installed(self) -> bool:
        return piper_installed()

    def _model_ready(self, model: str) -> bool:
        return (self._dir / f"{model}.onnx").exists() and (
            self._dir / f"{model}.onnx.json"
        ).exists()

    def _status(self, spec: PiperVoiceSpec) -> VoiceState:
        model = spec.model
        if self._model_ready(model):
            status: VoiceStatus = "ready"
            received = spec.size_bytes
            error: str | None = None
        elif model in self._downloads:
            status = "downloading"
            received = self._downloads[model].received
            error = None
        elif model in self._errors:
            status = "error"
            received = 0
            error = self._errors[model]
        else:
            status = "available"
            received = 0
            error = None
        return VoiceState(
            id=spec.id,
            label=spec.label,
            gender=spec.gender,
            size_bytes=spec.size_bytes,
            recommended=spec.recommended,
            status=status,
            received=received,
            error=error,
        )

    def voice_states(self) -> list[VoiceState]:
        return [self._status(spec) for spec in PIPER_VOICES]

    def ready_voice_ids(self) -> list[str]:
        return [spec.id for spec in PIPER_VOICES if self._model_ready(spec.model)]

    async def start_download(self, voice_id: str) -> None:
        """Installe le paquet si besoin puis lance le téléchargement en tâche de fond."""
        spec = SPECS_BY_ID[voice_id]  # KeyError → 404 côté REST
        model = spec.model
        if self._model_ready(model) or model in self._downloads:
            return
        # Peut installer l'extra `piper` (bloquant, court) — hors de la boucle.
        await asyncio.to_thread(ensure_piper_installed)
        self._errors.pop(model, None)
        self._downloads[model] = _Download(received=0, total=spec.size_bytes)
        self._tasks[model] = asyncio.create_task(self._run(spec))

    async def _run(self, spec: PiperVoiceSpec) -> None:
        model = spec.model

        def progress(received: int, total: int) -> None:
            state = self._downloads.get(model)
            if state is not None:
                state.received = received
                state.total = total

        try:
            await asyncio.to_thread(download_voice, spec, self._dir, progress)
            logger.info("Voix Piper « %s » téléchargée.", spec.id)
            self._on_ready()
        except Exception as exc:  # pragma: no cover - dépend du réseau
            logger.exception("Téléchargement de la voix Piper « %s » échoué", spec.id)
            self._errors[model] = str(exc)
        finally:
            self._downloads.pop(model, None)
            self._tasks.pop(model, None)

    def delete_voice(self, voice_id: str) -> bool:
        """Supprime le modèle de la voix. Renvoie False si rien n'était présent.

        Les voix partageant un même fichier (locuteurs multiples) disparaissent
        ensemble : c'est le fichier qui est supprimé.
        """
        spec = SPECS_BY_ID[voice_id]  # KeyError → 404 côté REST
        removed = False
        for path in (self._dir / f"{spec.model}.onnx", self._dir / f"{spec.model}.onnx.json"):
            if path.exists():
                path.unlink()
                removed = True
        self._errors.pop(spec.model, None)
        return removed
