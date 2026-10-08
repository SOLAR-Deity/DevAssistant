from __future__ import annotations
from pathlib import Path
from logging.handlers import RotatingFileHandler
import logging


def configure_logging(base: Path) -> None:
    base.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(base / 'dev_assistant.log', maxBytes=1_000_000, backupCount=2, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s'))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
