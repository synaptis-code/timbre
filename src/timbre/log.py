"""Logs structurés, non bufferisés, UTF-8 (leçon n°9 du plan : diagnostiquer en direct)."""

import io
import logging
import sys


def configure_logging(level: str) -> None:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(line_buffering=True, encoding="utf-8")
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        stream=sys.stdout,
        force=True,
    )
