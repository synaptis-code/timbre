"""Instantané VRAM via nvidia-smi. Absent ou en échec → None, jamais d'erreur."""

import asyncio
import logging
import subprocess

logger = logging.getLogger(__name__)


async def vram_snapshot() -> tuple[int, int] | None:
    """(VRAM utilisée, VRAM totale) en Mo, ou None sans GPU NVIDIA."""
    return await asyncio.to_thread(_query)


def _query() -> tuple[int, int] | None:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return parse_nvidia_smi(result.stdout)


def parse_nvidia_smi(stdout: str) -> tuple[int, int] | None:
    lines = stdout.strip().splitlines()
    if not lines:
        return None
    parts = [part.strip() for part in lines[0].split(",")]
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None
