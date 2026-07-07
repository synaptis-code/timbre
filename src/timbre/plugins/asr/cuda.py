"""Chargement des DLL CUDA sous Windows (leçon indispensable du plan, §8).

faster-whisper (via ctranslate2) a besoin des DLL cublas/cudnn, absentes d'une
machine Windows standard. Solution : installer les wheels `nvidia-*-cu12`
(extra `asr`) puis rendre leurs DLL trouvables AVANT le premier usage CUDA,
par trois moyens complémentaires (ctranslate2 ne passe pas toujours par le
mécanisme `add_dll_directory`) :
1. `os.add_dll_directory` sur chaque `nvidia/*/bin` ;
2. préfixe de `PATH` (recherche LoadLibrary classique) ;
3. préchargement explicite des DLL principales via ctypes.
Spécifique Windows, no-op ailleurs (§13).
"""

import ctypes
import logging
import os
import sys
import sysconfig
from pathlib import Path

logger = logging.getLogger(__name__)

_done = False

# Ordre de préchargement : Lt avant cublas (dépendance), puis cudnn et nvrtc.
_PRELOAD_PATTERNS = ("cublasLt64_*.dll", "cublas64_*.dll", "cudnn64_*.dll", "nvrtc64_*.dll")


def add_cuda_dll_directories() -> None:
    global _done
    if _done or sys.platform != "win32":
        return
    _done = True
    site_packages = Path(sysconfig.get_paths()["purelib"])
    bin_dirs = sorted((site_packages / "nvidia").glob("*/bin"))
    if not bin_dirs:
        logger.warning(
            "wheels nvidia-* introuvables dans %s — le GPU échouera probablement "
            "(installer avec `uv sync --extra asr`)",
            site_packages,
        )
        return

    for bin_dir in bin_dirs:
        os.add_dll_directory(str(bin_dir))
    os.environ["PATH"] = (
        os.pathsep.join(str(b) for b in bin_dirs) + os.pathsep + os.environ.get("PATH", "")
    )

    for bin_dir in bin_dirs:
        for pattern in _PRELOAD_PATTERNS:
            for dll in sorted(bin_dir.glob(pattern)):
                try:
                    ctypes.WinDLL(str(dll))
                    logger.debug("DLL CUDA préchargée : %s", dll.name)
                except OSError as exc:
                    logger.warning("préchargement de %s échoué : %s", dll.name, exc)
