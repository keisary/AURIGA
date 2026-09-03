"""AURIGA - Scoring des Einhers pour la sélection de portefeuille.

Un score pondéré caractérise la qualité d'un Einher avec UN seul chiffre,
en combinant les métriques (Sharpe, win rate, profit factor, drawdown,
nombre de trades). Utilisé par la sélection pour classer et prioriser.

Formule (poids équilibrés, chaque terme borné) :
    score = 0.25 * S(sharpe) + 0.20 * S(win_rate) + 0.20 * S(profit_factor)
          + 0.20 * S(drawdown) + 0.15 * S(trades)
où chaque S() est une transformation sigmoïde/log bornée en [0, 1].
"""
from __future__ import annotations

import math

from auriga.types import Einher, EinherMetrics

# Poids des métriques (somme = 1.0)
WEIGHTS = {
    "sharpe": 0.25,
    "win_rate": 0.20,
    "profit_factor": 0.20,
    "drawdown": 0.20,
    "trades": 0.15,
}


def _s_sharpe(sharpe: float) -> float:
    """Sigmoid centré sur 2.0 (le seuil d'admission)."""
    if sharpe <= 0:
        return 0.0
    return 1.0 / (1.0 + math.exp(-(sharpe - 2.0) / 1.2))


def _s_win_rate(wr: float) -> float:
    """Linéaire borné en [0.5, 0.9] → [0, 1]."""
    if wr <= 0.5:
        return 0.0
    if wr >= 0.9:
        return 1.0
    return (wr - 0.5) / 0.4


def _s_profit_factor(pf: float) -> float:
    """Log compressé : PF 1.0 → 0, PF 3.0 → ~0.8."""
    if pf <= 1.0:
        return 0.0
    return min(1.0, math.log(pf) / math.log(4.0))


def _s_drawdown(dd: float) -> float:
    """Drawdown (négatif) : 0 → 1.0, -0.30 → 0.0."""
    dd_abs = abs(dd)
    if dd_abs <= 0.05:
        return 1.0
    if dd_abs >= 0.30:
        return 0.0
    return 1.0 - (dd_abs - 0.05) / 0.25


def _s_trades(n: int, min_trades: int = 30) -> float:
    """Nombre de trades : min 30 → 0.2, 100+ → 1.0."""
    if n < min_trades:
        return max(0.0, n / min_trades * 0.2)
    if n >= 100:
        return 1.0
    return 0.2 + 0.8 * (n - min_trades) / 70.0


def score_einher(einher: Einher) -> float:
    """Score pondéré [0, 1] d'un Einher (métriques remplies)."""
    m: EinherMetrics = einher.metrics
    return (
        WEIGHTS["sharpe"] * _s_sharpe(m.sharpe_ratio)
        + WEIGHTS["win_rate"] * _s_win_rate(m.win_rate)
        + WEIGHTS["profit_factor"] * _s_profit_factor(m.profit_factor)
        + WEIGHTS["drawdown"] * _s_drawdown(m.max_drawdown)
        + WEIGHTS["trades"] * _s_trades(m.n_trades)
    )


def score_breakdown(einher: Einher) -> dict[str, float]:
    """Détail du score (pour le dashboard/audit)."""
    m: EinherMetrics = einher.metrics
    return {
        "sharpe": WEIGHTS["sharpe"] * _s_sharpe(m.sharpe_ratio),
        "win_rate": WEIGHTS["win_rate"] * _s_win_rate(m.win_rate),
        "profit_factor": WEIGHTS["profit_factor"] * _s_profit_factor(m.profit_factor),
        "drawdown": WEIGHTS["drawdown"] * _s_drawdown(m.max_drawdown),
        "trades": WEIGHTS["trades"] * _s_trades(m.n_trades),
        "total": score_einher(einher),
    }


def rank_einhers(einhers: list[Einher]) -> list[Einher]:
    """Classe les Einhers par score décroissant."""
    return sorted(einhers, key=score_einher, reverse=True)
