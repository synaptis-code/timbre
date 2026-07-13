"""Backend TTS Orpheus : voix expressive (émotions), 100 % locale via LM Studio.

Chemin Windows viable (le runtime officiel vLLM n'y tourne pas) :
  1. Le modèle Orpheus tourne en GGUF dans LM Studio ; interrogé par l'API
     `/v1/completions` (streaming), il produit des jetons audio spéciaux
     `<custom_token_N>`.
  2. Un décodeur SNAC (paquet `snac` + `torch`) transforme ces jetons en audio
     24 kHz avec les émotions du modèle.

Dépendances lourdes (torch) → extra optionnel `orpheus`, installé à la demande.
Implémentation fidèle à la référence communautaire (isaiahbjork/orpheus-tts-local).

⚠️ Nécessite un modèle Orpheus chargé dans LM Studio pour fonctionner — non
vérifiable sans lui. Renseigner le nom du modèle via `Settings.orpheus_model`.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import subprocess
import sys
import wave
from collections.abc import AsyncIterator
from io import BytesIO
from typing import TYPE_CHECKING, Any

import httpx2

from timbre.plugins.base import TTSBackend, TTSError

if TYPE_CHECKING:
    from snac import SNAC  # paquet optionnel (extra `orpheus`)

logger = logging.getLogger(__name__)

# Voix du modèle Orpheus de base (anglaises). Exposées sous « orpheus-<nom> ».
ORPHEUS_VOICES: tuple[str, ...] = ("tara", "leah", "jess", "leo", "dan", "mia", "zac", "zoe")
DEFAULT_VOICE = "tara"

SAMPLE_RATE = 24000
_SNAC_REPO = "hubertsiuzdak/snac_24khz"

# Paramètres de génération (référence Orpheus).
_MAX_TOKENS = 1200
_TEMPERATURE = 0.6
_TOP_P = 0.9
_REPEAT_PENALTY = 1.1


def orpheus_ready() -> bool:
    """torch + snac sont-ils installés (décodeur audio disponible) ?"""
    return (
        importlib.util.find_spec("torch") is not None
        and importlib.util.find_spec("snac") is not None
    )


def ensure_orpheus_installed() -> None:
    """Installe l'extra `orpheus` (torch + snac) à la demande. Lève `TTSError` si échec."""
    if orpheus_ready():
        return
    logger.info("Installation des dépendances Orpheus (torch + snac) à la demande…")
    try:
        subprocess.run(
            ["uv", "pip", "install", "--python", sys.executable, "torch", "snac"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise TTSError(
            "orpheus_install_failed",
            f"Installation d'Orpheus impossible : {detail}. "
            "Vérifie « uv », ou lance « uv sync --extra orpheus ».",
        ) from exc
    importlib.invalidate_caches()
    if not orpheus_ready():
        raise TTSError(
            "orpheus_install_failed",
            "Dépendances Orpheus installées mais introuvables — redémarre le serveur.",
        )


def _token_to_id(token_string: str, index: int) -> int | None:
    """Convertit un `<custom_token_N>` en identifiant de code SNAC (0..4095)."""
    start = token_string.rfind("<custom_token_")
    if start == -1:
        return None
    token = token_string[start:]
    if not token.endswith(">"):
        return None
    number = token[len("<custom_token_") : -1]
    if not number.isdigit():
        return None
    return int(number) - 10 - ((index % 7) * 4096)


class OrpheusTTSBackend(TTSBackend):
    """Synthèse expressive : LM Studio (jetons Orpheus) → décodage SNAC → WAV 24 kHz."""

    audio_format = "wav"

    def __init__(self, base_url: str, model: str) -> None:
        self._completions_url = f"{base_url.rstrip('/')}/v1/completions"
        self._model = model
        self._snac: SNAC | None = None
        self._device = "cpu"

    def _decoder(self) -> SNAC:
        if self._snac is not None:
            return self._snac
        import torch
        from snac import SNAC

        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._snac = SNAC.from_pretrained(_SNAC_REPO).eval().to(self._device)
        logger.info("Décodeur SNAC chargé (%s).", self._device)
        return self._snac

    def _decode(self, token_ids: list[int]) -> bytes:
        """Décode les identifiants (par trames de 7) en PCM 16 bits via SNAC."""
        import torch

        frames = len(token_ids) // 7
        if frames == 0:
            return b""
        flat = token_ids[: frames * 7]
        codes_0: list[int] = []
        codes_1: list[int] = []
        codes_2: list[int] = []
        for j in range(frames):
            i = 7 * j
            codes_0.append(flat[i])
            codes_1.extend((flat[i + 1], flat[i + 4]))
            codes_2.extend((flat[i + 2], flat[i + 3], flat[i + 5], flat[i + 6]))

        snac = self._decoder()
        codes = [
            torch.tensor(codes_0, device=self._device, dtype=torch.int32).unsqueeze(0),
            torch.tensor(codes_1, device=self._device, dtype=torch.int32).unsqueeze(0),
            torch.tensor(codes_2, device=self._device, dtype=torch.int32).unsqueeze(0),
        ]
        # Codes hors plage (0..4095) → génération corrompue, on refuse proprement.
        for tensor in codes:
            if bool((tensor < 0).any()) or bool((tensor > 4095).any()):
                raise TTSError(
                    "orpheus_bad_output",
                    "Jetons audio Orpheus invalides — le modèle chargé n'est "
                    "peut-être pas un modèle Orpheus.",
                )
        with torch.inference_mode():
            audio = snac.decode(codes)
        samples = audio.squeeze().detach().cpu().numpy()
        return bytes((samples * 32767.0).clip(-32768, 32767).astype("<i2").tobytes())

    def _render(self, text: str, voice: str) -> bytes:
        prompt = f"<|audio|>{voice}: {text}<|eot_id|>"
        payload: dict[str, Any] = {
            "model": self._model,
            "prompt": prompt,
            "max_tokens": _MAX_TOKENS,
            "temperature": _TEMPERATURE,
            "top_p": _TOP_P,
            "repeat_penalty": _REPEAT_PENALTY,
            "stream": True,
        }
        token_ids: list[int] = []
        index = 0
        try:
            with (
                httpx2.Client(timeout=None) as client,
                client.stream("POST", self._completions_url, json=payload) as resp,
            ):
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[len("data:") :].strip()
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    piece = chunk.get("choices", [{}])[0].get("text", "")
                    if not piece:
                        continue
                    token_id = _token_to_id(piece, index)
                    if token_id is not None:
                        token_ids.append(token_id)
                        index += 1
        except httpx2.HTTPError as exc:
            raise TTSError(
                "orpheus_unreachable",
                f"Orpheus/LM Studio injoignable ({exc}). Le modèle « {self._model} » "
                "est-il chargé dans LM Studio ?",
            ) from exc
        return self._decode(token_ids)

    async def synthesize(
        self, text: str, voice: str, rate: float = 1.0, pitch: int = 0
    ) -> AsyncIterator[bytes]:
        name = voice.removeprefix("orpheus-") or DEFAULT_VOICE
        if name not in ORPHEUS_VOICES:
            name = DEFAULT_VOICE
        try:
            pcm = await asyncio.to_thread(self._render, text, name)
        except TTSError:
            raise
        except Exception as exc:  # pragma: no cover - garde-fou runtime
            raise TTSError("tts_failed", f"Synthèse Orpheus échouée : {exc}.") from exc
        if not pcm:
            raise TTSError("orpheus_bad_output", "Orpheus n'a produit aucun audio.")
        buffer = BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(SAMPLE_RATE)
            wav.writeframes(pcm)
        yield buffer.getvalue()
