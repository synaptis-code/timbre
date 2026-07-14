"""Backend TTS Kokoro : voix neurales locales (~82M), légères, multilingues.

100 % local et autonome (pas de LLM, pas de serveur externe — contrairement à
l'ancien Orpheus). Tourne sur CPU via onnxruntime. Un seul téléchargement (modèle
`.onnx` + banque de voix `.bin`, ~350 Mo) débloque toutes les voix. Extra optionnel
`kokoro`, installé à la demande ; la phonémisation espeak est fournie par
`espeakng-loader` (aucune install système requise, Windows OK).
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
    from kokoro_onnx import Kokoro

logger = logging.getLogger(__name__)

SAMPLE_RATE = 24000
_RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
MODEL_FILE = "kokoro-v1.0.onnx"
VOICES_FILE = "voices-v1.0.bin"
_MODEL_SIZE = 325_532_387
_VOICES_SIZE = 28_214_398
MODEL_TOTAL_SIZE = _MODEL_SIZE + _VOICES_SIZE

# Préfixe de voix Kokoro → langue espeak + libellés.
_LANGS: dict[str, tuple[str, str, str]] = {
    "af": ("en-us", "English (US)", "English"),
    "am": ("en-us", "English (US)", "English"),
    "bf": ("en-gb", "English (UK)", "English"),
    "bm": ("en-gb", "English (UK)", "English"),
    "ff": ("fr-fr", "French", "Français"),
    "ef": ("es", "Spanish", "Español"),
    "em": ("es", "Spanish", "Español"),
    "if": ("it", "Italian", "Italiano"),
    "im": ("it", "Italian", "Italiano"),
    "jf": ("ja", "Japanese", "日本語"),
    "jm": ("ja", "Japanese", "日本語"),
    "zf": ("zh", "Chinese", "中文"),
    "zm": ("zh", "Chinese", "中文"),
    "hf": ("hi", "Hindi", "हिन्दी"),
    "hm": ("hi", "Hindi", "हिन्दी"),
    "pf": ("pt-br", "Portuguese", "Português"),
    "pm": ("pt-br", "Portuguese", "Português"),
}

# Voix de la banque v1.0 (54). Le nom encode : <langue><genre>_<prénom>.
KOKORO_VOICES: tuple[str, ...] = (
    "af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica", "af_kore",
    "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky",
    "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_michael",
    "am_onyx", "am_puck", "am_santa",
    "bf_alice", "bf_emma", "bf_isabella", "bf_lily",
    "bm_daniel", "bm_fable", "bm_george", "bm_lewis",
    "ef_dora", "em_alex", "em_santa",
    "ff_siwis",
    "hf_alpha", "hf_beta", "hm_omega", "hm_psi",
    "if_sara", "im_nicola",
    "jf_alpha", "jf_gongitsune", "jf_nezumi", "jf_tebukuro", "jm_kumo",
    "pf_dora", "pm_alex", "pm_santa",
    "zf_xiaobei", "zf_xiaoni", "zf_xiaoxiao", "zf_xiaoyi",
    "zm_yunjian", "zm_yunxi", "zm_yunxia", "zm_yunyang",
)


@dataclass(frozen=True)
class KokoroVoice:
    id: str  # ex. « ff_siwis »
    label: str  # ex. « Siwis · Femme »
    gender: str  # "F" | "H"
    lang_code: str  # code espeak, ex. « fr-fr »
    language_english: str
    language_native: str


def _voice_info(voice_id: str) -> KokoroVoice:
    prefix = voice_id[:2]
    lang_code, english, native = _LANGS.get(prefix, ("en-us", "English", "English"))
    gender = "F" if len(prefix) > 1 and prefix[1] == "f" else "H"
    name = voice_id.split("_", 1)[1].title() if "_" in voice_id else voice_id
    return KokoroVoice(
        id=voice_id,
        label=f"{name} · {'Femme' if gender == 'F' else 'Homme'}",
        gender=gender,
        lang_code=lang_code,
        language_english=english,
        language_native=native,
    )


def voice_catalog() -> list[KokoroVoice]:
    return [_voice_info(v) for v in KOKORO_VOICES]


def voice_lang_family(voice_id: str) -> str:
    """Famille de langue à 2 lettres d'une voix Kokoro (« ff_siwis » → « fr »)."""
    return _voice_info(voice_id.removeprefix("kokoro-")).lang_code.split("-")[0]


def kokoro_installed() -> bool:
    """Le paquet `kokoro-onnx` est-il importable ?"""
    return importlib.util.find_spec("kokoro_onnx") is not None


def model_present(models_dir: Path) -> bool:
    return (models_dir / MODEL_FILE).exists() and (models_dir / VOICES_FILE).exists()


def ensure_kokoro_installed() -> None:
    """Installe l'extra `kokoro` à la demande. Lève `TTSError` si échec."""
    if kokoro_installed():
        return
    logger.info("Installation des dépendances Kokoro à la demande…")
    try:
        subprocess.run(
            ["uv", "pip", "install", "--python", sys.executable,
             "kokoro-onnx", "soundfile", "espeakng-loader"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise TTSError(
            "kokoro_install_failed",
            f"Installation de Kokoro impossible : {detail}. "
            "Vérifie « uv », ou lance « uv sync --extra kokoro ».",
        ) from exc
    importlib.invalidate_caches()
    if not kokoro_installed():
        raise TTSError(
            "kokoro_install_failed",
            "Kokoro installé mais introuvable — redémarre le serveur.",
        )


def download_model(models_dir: Path, on_progress: Callable[[int, int], None]) -> None:
    """Télécharge le modèle Kokoro (.onnx + .bin). Bloquant → `asyncio.to_thread`."""
    models_dir.mkdir(parents=True, exist_ok=True)
    total = _MODEL_SIZE + _VOICES_SIZE
    received = 0
    with httpx2.Client(follow_redirects=True, timeout=None) as client:
        for name in (MODEL_FILE, VOICES_FILE):
            part = models_dir / f"{name}.part"
            with client.stream("GET", f"{_RELEASE}/{name}") as resp:
                resp.raise_for_status()
                with part.open("wb") as handle:
                    for chunk in resp.iter_bytes(1 << 16):
                        handle.write(chunk)
                        received += len(chunk)
                        on_progress(received, total)
            part.replace(models_dir / name)


class KokoroTTSBackend(TTSBackend):
    """Synthèse locale via Kokoro (onnx). Une phrase → un conteneur WAV 24 kHz."""

    audio_format: Literal["mp3", "wav"] = "wav"

    def __init__(self, models_dir: Path) -> None:
        self._dir = models_dir
        self._kokoro: Kokoro | None = None

    def _engine(self) -> Kokoro:
        if self._kokoro is not None:
            return self._kokoro
        # espeak embarqué : pointer phonemizer vers la lib fournie par le loader.
        try:
            import espeakng_loader
            from phonemizer.backend.espeak.wrapper import EspeakWrapper

            EspeakWrapper.set_library(espeakng_loader.get_library_path())
            EspeakWrapper.set_data_path(espeakng_loader.get_data_path())
        except Exception:  # pragma: no cover - espeak système présent = OK aussi
            logger.debug("espeakng-loader indisponible, on tente l'espeak système.")
        from kokoro_onnx import Kokoro

        model = self._dir / MODEL_FILE
        voices = self._dir / VOICES_FILE
        if not model.exists() or not voices.exists():
            raise TTSError(
                "kokoro_missing",
                "Kokoro n'est pas téléchargé. Va dans Réglages → Voix pour l'installer.",
            )
        self._kokoro = Kokoro(str(model), str(voices))
        return self._kokoro

    def _render(self, text: str, voice_id: str, rate: float) -> bytes:
        import numpy as np

        info = _voice_info(voice_id)
        samples, sample_rate = self._engine().create(
            text, voice=voice_id, speed=rate if rate > 0 else 1.0, lang=info.lang_code
        )
        pcm: Any = (np.asarray(samples) * 32767.0).clip(-32768, 32767).astype("<i2")
        buffer = BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(int(sample_rate))
            wav.writeframes(pcm.tobytes())
        return buffer.getvalue()

    async def synthesize(
        self, text: str, voice: str, rate: float = 1.0, pitch: int = 0
    ) -> AsyncIterator[bytes]:
        name = voice.removeprefix("kokoro-")  # id persona = « kokoro-ff_siwis »
        if name not in set(KOKORO_VOICES):
            raise TTSError("kokoro_voice_unknown", f"Voix Kokoro inconnue : « {voice} ».")
        try:
            wav = await asyncio.to_thread(self._render, text, name, rate)
        except TTSError:
            raise
        except Exception as exc:  # pragma: no cover - garde-fou runtime
            raise TTSError("tts_failed", f"Synthèse Kokoro échouée : {exc}.") from exc
        yield wav
