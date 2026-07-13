"""Backend TTS Piper : voix neurales 100 % locales (.onnx), à la demande.

Contrairement à edge-tts (cloud), Piper tourne entièrement en local sur le CPU.
Le paquet `piper-tts` n'est PAS installé par défaut (extra `piper`) et les voix
sont téléchargées depuis Hugging Face à la demande, puis stockées dans
`Settings.piper_voices_dir`. Tout est piloté par la catégorie « Voix » de l'UI :
installation du paquet + téléchargement du modèle au premier clic « Télécharger ».
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import subprocess
import sys
import wave
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import httpx2

from timbre.plugins.base import TTSBackend, TTSError

if TYPE_CHECKING:
    from piper import PiperVoice  # paquet optionnel (extra `piper`)

logger = logging.getLogger(__name__)

# Catalogue officiel des voix Piper (dépôt Hugging Face rhasspy/piper-voices).
_HF_ROOT = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
_CATALOG_URL = f"{_HF_ROOT}/voices.json"


@dataclass(frozen=True)
class PiperVoiceSpec:
    """Une voix Piper du catalogue (dérivée de voices.json).

    `id` est la clé de la voix (= nom de fichier .onnx = voice_id du persona) ;
    les voix multi-locuteurs utilisent le locuteur par défaut du modèle.
    """

    id: str  # ex. « fr_FR-siwis-medium »
    name: str  # ex. « siwis »
    quality: str  # low | medium | high | x_low
    language_code: str  # ex. « fr_FR »
    language_english: str  # ex. « French »
    language_native: str  # ex. « Français »
    hf_dir: str  # dossier HF, ex. « fr/fr_FR/siwis/medium »
    size_bytes: int  # taille du .onnx (affichage + progression)

    @property
    def label(self) -> str:
        return f"{self.name.replace('_', ' ').title()} · {self.quality}"


def _spec_from_entry(entry: dict[str, Any]) -> PiperVoiceSpec | None:
    """Construit une spec depuis une entrée voices.json (None si incomplète)."""
    files = entry.get("files", {})
    onnx = next(
        (p for p in files if p.endswith(".onnx") and not p.endswith(".onnx.json")), None
    )
    if onnx is None:
        return None
    lang = entry["language"]
    return PiperVoiceSpec(
        id=entry["key"],
        name=entry.get("name", entry["key"]),
        quality=entry.get("quality", "medium"),
        language_code=lang["code"],
        language_english=lang.get("name_english", lang["code"]),
        language_native=lang.get("name_native", lang["code"]),
        hf_dir=onnx.rsplit("/", 1)[0],
        size_bytes=int(files[onnx].get("size_bytes", 0)),
    )


def parse_catalog(data: dict[str, Any]) -> dict[str, PiperVoiceSpec]:
    catalog: dict[str, PiperVoiceSpec] = {}
    for entry in data.values():
        spec = _spec_from_entry(entry)
        if spec is not None:
            catalog[spec.id] = spec
    return catalog


# Repli minimal si voices.json est injoignable (hors-ligne) : quelques voix clés.
_BUILTIN_ENTRIES: dict[str, dict[str, Any]] = {
    "fr_FR-siwis-medium": {
        "key": "fr_FR-siwis-medium", "name": "siwis", "quality": "medium",
        "language": {"code": "fr_FR", "name_english": "French", "name_native": "Français"},
        "files": {"fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx": {"size_bytes": 63201294}},
    },
    "en_US-amy-medium": {
        "key": "en_US-amy-medium", "name": "amy", "quality": "medium",
        "language": {"code": "en_US", "name_english": "English", "name_native": "English"},
        "files": {"en/en_US/amy/medium/en_US-amy-medium.onnx": {"size_bytes": 63201294}},
    },
}


def fetch_catalog() -> dict[str, PiperVoiceSpec]:
    """Récupère le catalogue complet depuis Hugging Face (repli intégré si échec).

    Fonction bloquante (réseau) : à appeler via `asyncio.to_thread`.
    """
    try:
        with httpx2.Client(follow_redirects=True, timeout=30) as client:
            resp = client.get(_CATALOG_URL)
            resp.raise_for_status()
            return parse_catalog(resp.json())
    except Exception:
        logger.warning("Catalogue Piper injoignable — repli sur la liste intégrée.")
        return parse_catalog(_BUILTIN_ENTRIES)


def derive_label(voice_id: str) -> str:
    """Libellé lisible depuis un id, sans catalogue (voix déjà téléchargée hors-ligne)."""
    lang, _, rest = voice_id.partition("-")
    return f"{rest.replace('-', ' ').title()} ({lang})" if rest else voice_id


def piper_installed() -> bool:
    """Le paquet `piper-tts` est-il importable ?"""
    return importlib.util.find_spec("piper") is not None


def ensure_piper_installed() -> None:
    """Installe l'extra `piper` à la demande (bloquant). Lève `TTSError` si échec."""
    if piper_installed():
        return
    logger.info("Installation du paquet piper-tts à la demande…")
    try:
        subprocess.run(
            ["uv", "pip", "install", "--python", sys.executable, "piper-tts>=1.4"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise TTSError(
            "piper_install_failed",
            f"Installation de Piper impossible : {detail}. "
            "Vérifie qu'« uv » est disponible, ou lance « uv sync --extra piper ».",
        ) from exc
    importlib.invalidate_caches()
    if not piper_installed():
        raise TTSError(
            "piper_install_failed",
            "Piper installé mais toujours introuvable — redémarre le serveur.",
        )


def download_voice(
    spec: PiperVoiceSpec, voices_dir: Path, on_progress: Callable[[int, int], None]
) -> None:
    """Télécharge le modèle (.onnx + .onnx.json) depuis Hugging Face.

    Fonction bloquante à exécuter dans un thread (`asyncio.to_thread`) : elle fait
    du réseau et des écritures disque. Écrit d'abord dans un fichier `.part` puis
    renomme, pour ne jamais laisser un modèle à moitié téléchargé passer pour « prêt ».
    """
    voices_dir.mkdir(parents=True, exist_ok=True)
    onnx = voices_dir / f"{spec.id}.onnx"
    config = voices_dir / f"{spec.id}.onnx.json"
    part = onnx.with_suffix(".onnx.part")
    base = f"{_HF_ROOT}/{spec.hf_dir}/{spec.id}"
    with httpx2.Client(follow_redirects=True, timeout=None) as client:
        cfg_resp = client.get(f"{base}.onnx.json")
        cfg_resp.raise_for_status()
        config.write_bytes(cfg_resp.content)

        received = 0
        with client.stream("GET", f"{base}.onnx") as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length") or spec.size_bytes)
            on_progress(0, total)
            with part.open("wb") as handle:
                for chunk in resp.iter_bytes(1 << 16):
                    handle.write(chunk)
                    received += len(chunk)
                    on_progress(received, total)
        part.replace(onnx)


class PiperTTSBackend(TTSBackend):
    """Synthèse locale via des voix Piper `.onnx` téléchargées.

    Les modèles sont chargés paresseusement et mis en cache. Chaque phrase produit
    un conteneur WAV complet (mono 16 bits), joué tel quel côté client.
    """

    audio_format: Literal["mp3", "wav"] = "wav"

    def __init__(self, voices_dir: Path) -> None:
        self._dir = voices_dir
        self._cache: dict[str, PiperVoice] = {}  # voice_id -> voix chargée

    def _voice(self, voice_id: str) -> PiperVoice:
        cached = self._cache.get(voice_id)
        if cached is not None:
            return cached
        from piper import PiperVoice  # import différé : extra optionnel

        onnx = self._dir / f"{voice_id}.onnx"
        config = self._dir / f"{voice_id}.onnx.json"
        if not onnx.exists() or not config.exists():
            raise TTSError(
                "piper_voice_missing",
                f"La voix Piper « {voice_id} » n'est pas téléchargée. "
                "Va dans Réglages → Voix pour la récupérer.",
            )
        voice = PiperVoice.load(str(onnx), str(config))
        self._cache[voice_id] = voice
        return voice

    def _render(self, voice_id: str, text: str, rate: float) -> bytes:
        from piper import SynthesisConfig

        voice = self._voice(voice_id)
        # length_scale est l'inverse de la vitesse (plus grand = plus lent).
        length_scale = 1.0 / rate if rate > 0 else 1.0
        # Voix multi-locuteurs : on prend le locuteur par défaut (0).
        speaker_id = 0 if getattr(voice.config, "num_speakers", 1) > 1 else None
        syn = SynthesisConfig(length_scale=length_scale, speaker_id=speaker_id)
        pcm = b"".join(chunk.audio_int16_bytes for chunk in voice.synthesize(text, syn))
        buffer = BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(voice.config.sample_rate)
            wav.writeframes(pcm)
        return buffer.getvalue()

    async def synthesize(
        self, text: str, voice: str, rate: float = 1.0, pitch: int = 0
    ) -> AsyncIterator[bytes]:
        try:
            # Synthèse CPU bloquante → thread pour ne pas figer la boucle asyncio.
            wav = await asyncio.to_thread(self._render, voice, text, rate)
        except TTSError:
            raise
        except Exception as exc:  # pragma: no cover - garde-fou runtime
            raise TTSError(
                "tts_failed", f"Synthèse Piper échouée (voix « {voice} ») : {exc}."
            ) from exc
        yield wav
