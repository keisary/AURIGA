"""AURIGA - Formulaires et helpers divers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_id(*parts: Any) -> str:
    """ID déterministe à partir de composants (pour les Einhers)."""
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def read_jsonl(path: Path | str) -> list[dict[str, Any]]:
    """Lit un fichier JSONL, ignore les lignes corrompues."""
    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def append_jsonl(path: Path | str, record: dict[str, Any]) -> None:
    """Écrit une ligne JSONL de façon atomique (append + fsync)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        f.flush()


def safe_float(value: Any, default: float = 0.0) -> float:
    """Conversion float sûre."""
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default