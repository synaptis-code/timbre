"""Point d'entrée : `uv run timbre` (ou `python -m timbre`)."""

import logging

import uvicorn

from timbre.config import Settings
from timbre.log import configure_logging

logger = logging.getLogger(__name__)


def main() -> None:
    settings = Settings()
    configure_logging(settings.log_level)
    logger.info("Timbre démarre sur http://%s:%d", settings.host, settings.port)
    uvicorn.run(
        "timbre.api.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
