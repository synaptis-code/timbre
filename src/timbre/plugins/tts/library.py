"""Gestion à la demande des voix Piper : catalogue, installation, téléchargement.

Vit dans `app.state.voice_library`. Récupère le catalogue complet (voices.json,
mis en cache), pilote l'installation de l'extra `piper` et le téléchargement des
modèles (tâche de fond, progression interrogeable), et enregistre le moteur Piper
dans l'orchestrateur dès qu'une voix est prête.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from timbre.plugins.tts import kokoro, piper
from timbre.plugins.tts.piper import PiperVoiceSpec, derive_label

logger = logging.getLogger(__name__)

VoiceStatus = Literal["available", "downloading", "ready", "error"]


@dataclass
class _Download:
    received: int
    total: int


@dataclass(frozen=True)
class VoiceState:
    """État d'une voix Piper pour l'UI."""

    id: str
    label: str
    language_code: str
    language_english: str
    language_native: str
    quality: str
    size_bytes: int
    status: VoiceStatus
    received: int
    error: str | None


class VoiceLibrary:
    def __init__(self, voices_dir: Path, on_engine_ready: Callable[[], None]) -> None:
        self._dir = voices_dir
        self._on_ready = on_engine_ready
        self._catalog: dict[str, PiperVoiceSpec] | None = None
        self._catalog_lock = asyncio.Lock()
        self._downloads: dict[str, _Download] = {}  # clé = voice_id
        self._errors: dict[str, str] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}

    @property
    def package_installed(self) -> bool:
        return piper.piper_installed()

    async def catalog(self) -> dict[str, PiperVoiceSpec]:
        """Catalogue complet (récupéré une fois puis mis en cache)."""
        if self._catalog is None:
            async with self._catalog_lock:
                if self._catalog is None:
                    self._catalog = await asyncio.to_thread(piper.fetch_catalog)
        return self._catalog

    def _downloaded(self, voice_id: str) -> bool:
        return (self._dir / f"{voice_id}.onnx").exists() and (
            self._dir / f"{voice_id}.onnx.json"
        ).exists()

    def ready_voice_ids(self) -> list[str]:
        """IDs des voix téléchargées — lu du disque, sans dépendre du catalogue."""
        if not self._dir.exists():
            return []
        return sorted(
            path.name[: -len(".onnx")]
            for path in self._dir.glob("*.onnx")
            if (self._dir / f"{path.name}.json").exists()
        )

    def _status_of(self, voice_id: str) -> tuple[VoiceStatus, int, str | None]:
        if self._downloaded(voice_id):
            return "ready", 0, None
        if voice_id in self._downloads:
            return "downloading", self._downloads[voice_id].received, None
        if voice_id in self._errors:
            return "error", 0, self._errors[voice_id]
        return "available", 0, None

    async def voice_states(self) -> list[VoiceState]:
        catalog = await self.catalog()
        states: list[VoiceState] = []
        for spec in catalog.values():
            status, received, error = self._status_of(spec.id)
            states.append(
                VoiceState(
                    id=spec.id,
                    label=spec.label,
                    language_code=spec.language_code,
                    language_english=spec.language_english,
                    language_native=spec.language_native,
                    quality=spec.quality,
                    size_bytes=spec.size_bytes,
                    status=status,
                    received=received,
                    error=error,
                )
            )
        return states

    async def label_for(self, voice_id: str) -> str:
        """Libellé lisible d'une voix (catalogue si dispo, sinon dérivé de l'id)."""
        catalog = self._catalog  # ne force pas le fetch réseau
        if catalog is not None and voice_id in catalog:
            return catalog[voice_id].label
        return derive_label(voice_id)

    async def start_download(self, voice_id: str) -> None:
        """Installe le paquet si besoin puis télécharge la voix en tâche de fond."""
        catalog = await self.catalog()
        spec = catalog.get(voice_id)
        if spec is None:
            raise KeyError(voice_id)
        if self._downloaded(voice_id) or voice_id in self._downloads:
            return
        await asyncio.to_thread(piper.ensure_piper_installed)  # extra `piper`, court
        self._errors.pop(voice_id, None)
        self._downloads[voice_id] = _Download(received=0, total=spec.size_bytes)
        self._tasks[voice_id] = asyncio.create_task(self._run(spec))

    async def _run(self, spec: PiperVoiceSpec) -> None:
        def progress(received: int, total: int) -> None:
            state = self._downloads.get(spec.id)
            if state is not None:
                state.received = received
                state.total = total

        try:
            await asyncio.to_thread(piper.download_voice, spec, self._dir, progress)
            logger.info("Voix Piper « %s » téléchargée.", spec.id)
            self._on_ready()
        except Exception as exc:  # pragma: no cover - dépend du réseau
            logger.exception("Téléchargement de la voix Piper « %s » échoué", spec.id)
            self._errors[spec.id] = str(exc)
        finally:
            self._downloads.pop(spec.id, None)
            self._tasks.pop(spec.id, None)

    def delete_voice(self, voice_id: str) -> bool:
        """Supprime les fichiers d'une voix téléchargée. False si rien à supprimer."""
        removed = False
        for path in (self._dir / f"{voice_id}.onnx", self._dir / f"{voice_id}.onnx.json"):
            if path.exists():
                path.unlink()
                removed = True
        self._errors.pop(voice_id, None)
        return removed


@dataclass(frozen=True)
class KokoroVoiceInfo:
    id: str  # préfixé « kokoro-… »
    label: str
    gender: str
    language_english: str
    language_native: str


class KokoroLibrary:
    """Kokoro = un seul téléchargement (modèle + banque de voix) qui débloque
    toutes les voix. Pas de gestion par voix (contrairement à Piper)."""

    def __init__(self, models_dir: Path, on_engine_ready: Callable[[], None]) -> None:
        self._dir = models_dir
        self._on_ready = on_engine_ready
        self._download: _Download | None = None
        self._error: str | None = None
        self._task: asyncio.Task[None] | None = None

    @property
    def installed(self) -> bool:
        return kokoro.kokoro_installed() and kokoro.model_present(self._dir)

    def voices(self) -> list[KokoroVoiceInfo]:
        return [
            KokoroVoiceInfo(
                id=f"kokoro-{v.id}",
                label=v.label,
                gender=v.gender,
                language_english=v.language_english,
                language_native=v.language_native,
            )
            for v in kokoro.voice_catalog()
        ]

    def status(self) -> tuple[VoiceStatus, int, int, str | None]:
        total = kokoro.MODEL_TOTAL_SIZE
        if self.installed:
            return "ready", total, total, None
        if self._download is not None:
            return "downloading", self._download.received, self._download.total, None
        if self._error is not None:
            return "error", 0, total, self._error
        return "available", 0, total, None

    async def install(self) -> None:
        """Installe le paquet (si besoin) puis télécharge le modèle en tâche de fond."""
        if self.installed or self._download is not None:
            return
        await asyncio.to_thread(kokoro.ensure_kokoro_installed)
        self._error = None
        self._download = _Download(received=0, total=kokoro.MODEL_TOTAL_SIZE)
        self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        def progress(received: int, total: int) -> None:
            if self._download is not None:
                self._download.received = received
                self._download.total = total

        try:
            await asyncio.to_thread(kokoro.download_model, self._dir, progress)
            logger.info("Modèle Kokoro téléchargé.")
            self._on_ready()
        except Exception as exc:  # pragma: no cover - dépend du réseau
            logger.exception("Téléchargement de Kokoro échoué")
            self._error = str(exc)
        finally:
            self._download = None
            self._task = None

    def uninstall(self) -> bool:
        removed = False
        for name in (kokoro.MODEL_FILE, kokoro.VOICES_FILE):
            path = self._dir / name
            if path.exists():
                path.unlink()
                removed = True
        self._error = None
        return removed
