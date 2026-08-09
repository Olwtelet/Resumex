"""Logging setup.

Logs are for diagnostics and go to stderr; anything the user is meant to *read*
goes through :mod:`resumex.console` instead.
"""

from __future__ import annotations

import logging
import sys

LOGGER_NAME = "resumex"


def configure(verbose: bool = False) -> logging.Logger:
    """Attach a single stderr handler to the ``resumex`` logger."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG if verbose else logging.WARNING)
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)-7s %(name)s: %(message)s", datefmt="%H:%M:%S"
        )
        if verbose
        else logging.Formatter("%(levelname)s: %(message)s")
    )
    logger.addHandler(handler)
    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a child of the ``resumex`` logger."""
    suffix = name.removeprefix("resumex.")
    return logging.getLogger(LOGGER_NAME if suffix == name else f"{LOGGER_NAME}.{suffix}")
