"""Structured JSON logging out of the box (stdout, key=value)."""
from __future__ import annotations

import logging
import sys


def configure() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stdout,
        force=True,
    )


configure()

logger = logging.getLogger("cxassist")