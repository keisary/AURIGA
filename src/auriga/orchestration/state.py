"""AURIGA - État persistant du système (module ORC).

Persiste l'état minimal entre les cycles :
- positions suivies (les spreads ouverts via Alpaca + l'Einher associé)
- historique des cycles (date, candidats, admis, ordres)
- état du marché (derniers prix spot par symbole)

Stockage : JSONL append-only dans outputs/state/ (léger, traçable).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from auriga.utils.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class TrackedPosition:
    """Position spread suivie par AURIGA (miroir local d'une position Alpaca)."""

    symbol: str
    einher_id: str
    direction: str
    strategy_name: str
    option_symbols: list[str]
    max_risk: float
    qty: int
    opened_at: str
    weight: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "einher_id": self.einher_id,
            "direction": self.direction,
            "strategy_name": self.strategy_name,
            "option_symbols": self.option_symbols,
            "max_risk": self.max_risk,
            "qty": self.qty,
            "opened_at": self.opened_at,
            "weight": self.weight,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "TrackedPosition":
        return TrackedPosition(
            symbol=d["symbol"], einher_id=d["einher_id"], direction=d["direction"],
            strategy_name=d.get("strategy_name", ""), option_symbols=d.get("option_symbols", []),
            max_risk=float(d.get("max_risk", 0)), qty=int(d.get("qty", 1)),
            opened_at=d.get("opened_at", ""), weight=float(d.get("weight", 0)),
        )


class StateStore:
    """Journal JSONL des événements + positions suivies."""

    def __init__(self, state_dir: Path | str | None = None):
        cfg = get_config()
        if state_dir is None:
            state_dir = Path("outputs/state")
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.positions_file = self.state_dir / "positions.jsonl"
        self.cycles_file = self.state_dir / "cycles.jsonl"
        self.spots_file = self.state_dir / "spots.jsonl"

    # ------------------------------------------------------------------
    def log_cycle(self, summary: dict[str, Any]) -> None:
        """Journalise un cycle (recherche/exécution)."""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            **summary,
        }
        with open(self.cycles_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    def read_cycles(self, limit: int = 20) -> list[dict[str, Any]]:
        if not self.cycles_file.exists():
            return []
        rows: list[dict[str, Any]] = []
        with open(self.cycles_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows[-limit:]

    # ------------------------------------------------------------------
    def add_position(self, pos: TrackedPosition) -> None:
        with open(self.positions_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(pos.to_dict(), ensure_ascii=False) + "\n")
        logger.info("Position suivie ajoutée: %s %s (%s)", pos.symbol, pos.direction, pos.einher_id)

    def read_positions(self) -> list[TrackedPosition]:
        if not self.positions_file.exists():
            return []
        out: list[TrackedPosition] = []
        with open(self.positions_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(TrackedPosition.from_dict(json.loads(line)))
                except (json.JSONDecodeError, KeyError):
                    continue
        return out

    def clear_positions(self) -> None:
        """Ferme le suivi local (positions clôturées)."""
        if self.positions_file.exists():
            self.positions_file.unlink()

    # ------------------------------------------------------------------
    def save_spots(self, spots: dict[str, float]) -> None:
        """Sauvegarde les derniers prix spot."""
        record = {"timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"), "spots": spots}
        with open(self.spots_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def read_spots(self) -> dict[str, float]:
        """Derniers spots connus."""
        if not self.spots_file.exists():
            return {}
        last: dict[str, float] = {}
        with open(self.spots_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    last = json.loads(line).get("spots", {})
                except json.JSONDecodeError:
                    continue
        return {k: float(v) for k, v in last.items()}