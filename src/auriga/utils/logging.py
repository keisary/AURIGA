"""AURIGA - Utilitaires de logging et helpers divers."""
from __future__ import annotations

import logging
import sys
from datetime import UTC
from pathlib import Path


def setup_logging(level: str = "INFO", log_dir: Path | str | None = None) -> logging.Logger:
    """Configure le logging AURIGA : console + fichier optionnel."""
    fmt = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=fmt,
        stream=sys.stdout,
    )
    logger = logging.getLogger("auriga")
    if log_dir is not None:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_dir / "auriga.log", encoding="utf-8")
        fh.setFormatter(logging.Formatter(fmt))
        logger.addHandler(fh)
    return logger


def now_iso() -> str:
    """Timestamp ISO pour les logs et IDs."""
    from datetime import datetime

    return datetime.now(UTC).isoformat(timespec="seconds")
