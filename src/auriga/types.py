"""AURIGA - Types partagés (contrat de données central).

Ce module définit les dataclasses communes à tous les modules. Chaque module
importe depuis ici pour garantir des interfaces compatibles.

Convention (cohérente avec einherjar) :
- Einher = stratégie définie par (1) condition, (2) direction, (3) amplitude,
  (4) univers, (5) métriques.
- Toutes les valeurs monétaires en dollars (float).
- Toutes les dates/heures en UTC (datetime).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Conditions (règles explicables)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Condition:
    """Condition atomique : feature opérateur valeur."""

    feature_ref: str
    operator: str  # >, <, >=, <=, ==
    value: float

    def __str__(self) -> str:
        return f"{self.feature_ref} {self.operator} {self.value:.4g}"


@dataclass(frozen=True)
class ConditionNode:
    """Nœud de combinaison logique AND/OR."""

    op: str  # "AND" | "OR"
    left: "Condition | ConditionNode"
    right: "Condition | ConditionNode"

    def __str__(self) -> str:
        return f"({self.left} {self.op} {self.right})"


# ---------------------------------------------------------------------------
# Sérialisation structurelle des conditions (pour persistance/rechargement)
# ---------------------------------------------------------------------------

def condition_to_dict(cond: "Condition | ConditionNode") -> dict[str, Any]:
    """Sérialise une condition en dict JSON reconstruisible."""
    if isinstance(cond, Condition):
        return {
            "type": "atom",
            "feature_ref": cond.feature_ref,
            "operator": cond.operator,
            "value": cond.value,
        }
    return {
        "type": "node",
        "op": cond.op,
        "left": condition_to_dict(cond.left),
        "right": condition_to_dict(cond.right),
    }


def condition_from_dict(d: dict[str, Any]) -> "Condition | ConditionNode":
    """Reconstruit une condition depuis un dict produit par condition_to_dict."""
    if d.get("type") == "atom":
        return Condition(
            feature_ref=d["feature_ref"],
            operator=d["operator"],
            value=float(d["value"]),
        )
    return ConditionNode(
        op=d["op"],
        left=condition_from_dict(d["left"]),
        right=condition_from_dict(d["right"]),
    )


# ---------------------------------------------------------------------------
# Métriques
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EinherMetrics:
    """Métriques de performance d'une stratégie."""

    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    n_trades: int = 0
    max_drawdown: float = 0.0
    t_statistic: float = 0.0
    cagr: float = 0.0
    avg_net_return: float = 0.0
    total_return: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "win_rate": round(self.win_rate, 4),
            "profit_factor": round(self.profit_factor, 4),
            "n_trades": self.n_trades,
            "max_drawdown": round(self.max_drawdown, 4),
            "t_statistic": round(self.t_statistic, 4),
            "cagr": round(self.cagr, 4),
            "avg_net_return": round(self.avg_net_return, 6),
            "total_return": round(self.total_return, 4),
            "extra": self.extra,
        }


# ---------------------------------------------------------------------------
# Einher (stratégie)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Einher:
    """Stratégie de trading : condition + direction + amplitude + univers + métriques."""

    id: str
    condition: "Condition | ConditionNode"
    direction: str  # "LONG" | "SHORT"
    amplitude: float  # retour cible attendu (fraction)
    symbol: str  # actif unique pour AURIGA
    timeframe: str  # "1H" | "1D"
    horizon_bars: int  # horizon en barres
    source: str  # "xgboost" | "stgp" | ...
    metrics: EinherMetrics = field(default_factory=EinherMetrics)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def condition_str(self) -> str:
        return str(self.condition)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "condition": str(self.condition),
            "direction": self.direction,
            "amplitude": self.amplitude,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "horizon_bars": self.horizon_bars,
            "source": self.source,
            "metrics": self.metrics.to_dict(),
            "created_at": self.created_at,
            "extra": self.extra,
        }

    @staticmethod
    def new_id(prefix: str = "einher") -> str:
        return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Signal (déclenchement d'une stratégie sur les données actuelles)
# ---------------------------------------------------------------------------

@dataclass
class Signal:
    """Un Einher qui se déclenche à l'instant T sur un actif."""

    einher: Einher
    symbol: str
    price: float  # prix sous-jacent au déclenchement
    timestamp: str
    strength: float = 0.0  # force du signal (0-1), ex. marge de la condition

    def to_dict(self) -> dict[str, Any]:
        return {
            "einher_id": self.einher.id,
            "symbol": self.symbol,
            "direction": self.einher.direction,
            "price": self.price,
            "timestamp": self.timestamp,
            "strength": self.strength,
            "condition": self.einher.condition_str,
        }


# ---------------------------------------------------------------------------
# Options / spreads
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OptionLeg:
    """Une jambe d'un spread d'options."""

    symbol: str  # sous-jacent
    option_symbol: str  # OCC symbol (ex: AAPL250919C00250000)
    side: str  # "buy" | "sell"
    option_type: str  # "call" | "put"
    strike: float
    expiry: str  # YYYY-MM-DD
    qty: int = 1


@dataclass
class SpreadStrategy:
    """Spread défini-risque complet.

    signal : Signal directionnel (None pour la vente de prime systématique —
    dans ce cas `symbol` porte le sous-jacent).
    """

    name: str  # "bull_call_spread" | "bear_put_spread" | "put_credit_spread" | "call_credit_spread"
    legs: list[OptionLeg]
    max_risk: float  # perte max $
    max_profit: float  # gain max $
    debit_or_credit: float  # net premium
    dte: int  # days to expiration
    delta: float  # delta net approximatif
    signal: Signal | None = None
    symbol: str = ""  # sous-jacent (requis si signal is None)
    rationale: str = ""

    @property
    def underlying(self) -> str:
        """Symbole du sous-jacent (signal ou champ direct)."""
        if self.signal is not None:
            return self.signal.symbol
        return self.symbol

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.underlying,
            "name": self.name,
            "legs": [vars(l) for l in self.legs],
            "max_risk": round(self.max_risk, 2),
            "max_profit": round(self.max_profit, 2),
            "debit_or_credit": round(self.debit_or_credit, 2),
            "dte": self.dte,
            "delta": round(self.delta, 4),
            "rationale": self.rationale,
        }


# ---------------------------------------------------------------------------
# Ordres / exécution
# ---------------------------------------------------------------------------

@dataclass
class OrderRequest:
    """Demande d'ordre Alpaca (multi-leg supporté)."""

    strategy: SpreadStrategy
    order_type: str = "market"  # market | limit
    time_in_force: str = "day"
    take_profit: Optional[float] = None  # en $ (prix cible de sortie)
    stop_loss: Optional[float] = None  # en $ (prix stop)


@dataclass
class OrderResult:
    """Résultat d'un ordre soumis à Alpaca."""

    order_id: str
    status: str  # "accepted" | "filled" | "rejected" | "cancelled" | "error"
    submitted_at: str
    message: str = ""
    legacy: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# État du portefeuille / risque
# ---------------------------------------------------------------------------

@dataclass
class PositionState:
    """Position ouverte (options ou test)."""

    symbol: str
    strategy_name: str
    einher_id: str
    qty: int
    entry_price: float  # prix moyen (par contrat si options)
    max_risk: float
    opened_at: str
    current_value: float = 0.0  # mark-to-market


@dataclass
class PortfolioState:
    """État global du portefeuille."""

    equity: float
    cash: float
    buying_power: float
    positions: list[PositionState] = field(default_factory=list)
    day_pnl: float = 0.0
    total_pnl: float = 0.0
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    @property
    def n_positions(self) -> int:
        return len(self.positions)

    @property
    def gross_exposure(self) -> float:
        return sum(p.max_risk for p in self.positions)


@dataclass
class RiskDecision:
    """Résultat du passage du risk engine."""

    allowed: bool
    reasons: list[str] = field(default_factory=list)  # gates franchis
    blocked_by: list[str] = field(default_factory=list)  # gates bloquants
    suggested_liquidation: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reasons": self.reasons,
            "blocked_by": self.blocked_by,
            "suggested_liquidation": self.suggested_liquidation,
        }