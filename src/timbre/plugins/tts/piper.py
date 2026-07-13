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
from typing import TYPE_CHECKING, Literal

import httpx2

from timbre.plugins.base import TTSBackend, TTSError

if TYPE_CHECKING:
    from piper import PiperVoice  # paquet optionnel (extra `piper`)

logger = logging.getLogger(__name__)

# Catalogue officiel des voix Piper (dépôt Hugging Face rhasspy/piper-voices).
_HF_ROOT = "https://huggingface.co/rhasspy/piper-voices/resolve/main"


@dataclass(frozen=True)
class PiperVoiceSpec:
    """Une voix Piper proposée au téléchargement.

    `model` est le nom de fichier partagé (plusieurs voix peuvent venir d'un même
    fichier multi-locuteurs, distinguées par `speaker_id`).
    """

    id: str  # identifiant de voix = voice_id du persona
    label: str
    gender: Literal["F", "H"]
    model: str  # stem du fichier .onnx, ex. « fr_FR-siwis-medium »
    hf_dir: str  # dossier dans le dépôt HF, ex. « fr/fr_FR/siwis/medium »
    size_bytes: int  # taille du .onnx (affichage + progression)
    speaker_id: int | None = None
    recommended: bool = False


PIPER_VOICES: tuple[PiperVoiceSpec, ...] = (
    PiperVoiceSpec(
        "fr_FR-siwis-medium", "Siwis · Femme", "F",
        "fr_FR-siwis-medium", "fr/fr_FR/siwis/medium", 63201294, recommended=True,
    ),
    PiperVoiceSpec(
        "fr_FR-tom-medium", "Tom · Homme", "H",
        "fr_FR-tom-medium", "fr/fr_FR/tom/medium", 63511038,
    ),
    PiperVoiceSpec(
        "fr_FR-upmc-jessica", "Jessica · Femme", "F",
        "fr_FR-upmc-medium", "fr/fr_FR/upmc/medium", 76733615, speaker_id=0,
    ),
    PiperVoiceSpec(
        "fr_FR-upmc-pierre", "Pierre · Homme", "H",
        "fr_FR-upmc-medium", "fr/fr_FR/upmc/medium", 76733615, speaker_id=1,
    ),
)

SPECS_BY_ID: dict[str, PiperVoiceSpec] = {v.id: v for v in PIPER_VOICES}


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
    onnx = voices_dir / f"{spec.model}.onnx"
    config = voices_dir / f"{spec.model}.onnx.json"
    part = onnx.with_suffix(".onnx.part")
    base = f"{_HF_ROOT}/{spec.hf_dir}/{spec.model}"
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
        self._cache: dict[str, PiperVoice] = {}  # model -> voix chargée

    def _voice(self, model: str) -> PiperVoice:
        cached = self._cache.get(model)
        if cached is not None:
            return cached
        from piper import PiperVoice  # import différé : extra optionnel

        onnx = self._dir / f"{model}.onnx"
        config = self._dir / f"{model}.onnx.json"
        if not onnx.exists() or not config.exists():
            raise TTSError(
                "piper_voice_missing",
                f"La voix Piper « {model} » n'est pas téléchargée. "
                "Va dans Réglages → Voix pour la récupérer.",
            )
        voice = PiperVoice.load(str(onnx), str(config))
        self._cache[model] = voice
        return voice

    def _render(self, spec: PiperVoiceSpec, text: str, rate: float) -> bytes:
        from piper import SynthesisConfig

        voice = self._voice(spec.model)
        # length_scale est l'inverse de la vitesse (plus grand = plus lent).
        length_scale = 1.0 / rate if rate > 0 else 1.0
        syn = SynthesisConfig(length_scale=length_scale, speaker_id=spec.speaker_id)
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
        spec = SPECS_BY_ID.get(voice)
        if spec is None:
            raise TTSError("piper_voice_unknown", f"Voix Piper inconnue : « {voice} ».")
        try:
            # Synthèse CPU bloquante → thread pour ne pas figer la boucle asyncio.
            wav = await asyncio.to_thread(self._render, spec, text, rate)
        except TTSError:
            raise
        except Exception as exc:  # pragma: no cover - garde-fou runtime
            raise TTSError(
                "tts_failed", f"Synthèse Piper échouée (voix « {voice} ») : {exc}."
            ) from exc
        yield wav
