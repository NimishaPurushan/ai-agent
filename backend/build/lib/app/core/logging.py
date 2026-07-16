"""Centralized logging configuration."""
import logging
import sys

_CONFIGURED = False


def configure_logging(level: str = "INFO") -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    # Silence noisy libs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("opensearch").setLevel(logging.WARNING)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

