"""AURIGA - Backtest des stratégies d'options (vol & vente de prime).

Contexte : Alpaca ne fournit pas de prix d'options historiques gratuits. On
estime le P&L en repricant via Black-Scholes avec la vol RÉALISÉE.

CORRECTION 2026-09-03 (revue Jovanny) :
- La vol réalisée midasV3 est PER-BARRE (sqrt(sum(r²))), PAS annualisée.
  black_scholes exige une vol ANNUALISÉE. On annualise : vol_ann = vol_per_bar
  × sqrt(bars_per_year).
- Anti-tautologie : le P&L d'un straddle dépend du MOUVEMENT du spot entre
  entrée et sortie (pas seulement de la vol du label). À l'échéance simulée,
  le straddle vaut |S_T − K| (intrinsèque) — le P&L mesure si le spot a bougé
  plus que la prime payée.

Méthode (straddle ATM détenu jusqu'à l'échéance simulée = horizon) :
1. Signaux = condition vraie → entrée à t+1.
2. Prime straddle = BS(call ATM) + BS(put ATM) avec vol_ann = vol_per_bar × √N.
3. Sortie à t+H : valeur intrinsèque = |S_{t+H} − K| × 100 (échéance).
4. P&L long straddle = intrinsèque − prime. P&L short = prime − intrinsèque.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import polars as pl

from auriga.options.pricing import black_scholes
from auriga.research.condition_tree import evaluate_ast_on_array
from auriga.types import Einher, EinherMetrics

logger = logging.getLogger(__name__)

ATM_STRIKE_MULT = 1.00
MULTIPLIER = 100
BARS_PER_YEAR = 252 * 24  # 1H → ~6048 barres/an
# Prime de risque de vol (IV > RV) : les acheteurs paient plus que la vol
# réalisée. On majore la vol réalisée de VOL_RISK_PREMIUM points annualisés.
VOL_RISK_PREMIUM = 0.04  # 4 points de vol annualisée


@dataclass
class OptionTrade:
    """Trade d'options simulé."""

    entry_idx: int
    exit_idx: int
    direction: str  # VOL_UP (long) | VOL_DOWN (short)
    entry_price: float  # prime totale payée/reçue ($ pour 1 contrat)
    exit_price: float  # valeur à la sortie ($)
    net_return: float  # P&L / prime engagée
    exit_reason: str = "expiry"


def _vol_per_bar(close: np.ndarray, window: int = 20) -> np.ndarray:
    """Vol réalisée PER-BARRE (identique à la feature realized_vol_20)."""
    from auriga.features.quantitative import _numba_realized_volatility

    rets = np.full(len(close), np.nan, dtype=np.float64)
    if len(close) > 1:
        rets[1:] = close[1:] / close[:-1] - 1.0
    return np.asarray(_numba_realized_volatility(rets, window), dtype=np.float64)


def _vol_annualized(vol_per_bar: float) -> float:
    """Annualise une vol per-barre."""
    if vol_per_bar is None or np.isnan(vol_per_bar) or vol_per_bar <= 0:
        return 0.0
    return float(vol_per_bar * np.sqrt(BARS_PER_YEAR))


def backtest_straddle_einher(
    einher: Einher,
    ohlcv: pl.DataFrame,
    X: np.ndarray,
    feature_names: list[str],
    costs_pct: float = 0.001,
    vol_window: int = 20,
) -> tuple[list[OptionTrade], EinherMetrics]:
    """Backtest un Einher VOL via straddle ATM détenu jusqu'à l'échéance.

    - direction VOL_UP   → LONG straddle (parie que le spot bouge beaucoup)
    - direction VOL_DOWN → SHORT straddle (parie que le spot reste range)

    L'échéance simulée = horizon de la règle. À l'échéance, le straddle vaut
    |S_T − K| (intrinsèque, valeur temps = 0). Le P&L mesure si le mouvement
    du spot a dépassé la prime payée (vol implicite = vol réalisée + prime).
    """
    n = X.shape[0]
    if n < 50:
        return [], EinherMetrics(n_trades=0)

    signal_mask = evaluate_ast_on_array(einher.condition, X, feature_names)
    signal_idx = np.where(signal_mask)[0]

    close = ohlcv["close"].to_numpy().astype(np.float64)
    vol_pb = _vol_per_bar(close, vol_window)
    horizon = einher.horizon_bars if einher.horizon_bars > 0 else 24

    trades: list[OptionTrade] = []
    next_free = 0

    for t in signal_idx:
        if t < next_free or t + horizon >= n:
            continue
        entry_idx = t + 1
        S0 = close[t]
        vol_ann_entry = _vol_annualized(vol_pb[t])
        if S0 <= 0 or vol_ann_entry <= 0:
            continue

        # Temps jusqu'à l'échéance simulée (en années)
        T = horizon / BARS_PER_YEAR
        K = S0 * ATM_STRIKE_MULT

        # Prime straddle = call ATM + put ATM (vol implicite = RV + prime risque)
        iv = min(vol_ann_entry + VOL_RISK_PREMIUM, 3.0)
        call_p = black_scholes(S0, K, T, sigma=iv, option_type="call").price
        put_p = black_scholes(S0, K, T, sigma=iv, option_type="put").price
        straddle_prime = (call_p + put_p) * MULTIPLIER  # $ pour 1 contrat

        # Sortie à l'échéance : valeur intrinsèque = |S_T − K| × 100
        S_T = close[min(entry_idx + horizon, n - 1)]
        intrinsic = abs(S_T - K) * MULTIPLIER

        if einher.direction == "VOL_UP":
            gross = intrinsic - straddle_prime
        else:
            gross = straddle_prime - intrinsic

        net_ret = gross / max(straddle_prime, 1.0) - costs_pct

        trades.append(
            OptionTrade(
                entry_idx=entry_idx,
                exit_idx=entry_idx + horizon,
                direction=einher.direction,
                entry_price=straddle_prime,
                exit_price=intrinsic,
                net_return=net_ret,
            )
        )
        next_free = entry_idx + horizon

    metrics = _metrics_from_option_trades(trades, costs_pct)
    return trades, metrics


def _metrics_from_option_trades(trades: list[OptionTrade], costs_pct: float) -> EinherMetrics:
    """Métriques depuis les trades d'options (réutilise compute_metrics)."""
    from auriga.backtest.backtester import TradeResult, compute_metrics

    converted = [
        TradeResult(
            entry_idx=tr.entry_idx, exit_idx=tr.exit_idx,
            direction="LONG" if tr.direction == "VOL_UP" else "SHORT",
            entry_price=tr.entry_price, exit_price=tr.exit_price,
            net_return=tr.net_return, exit_reason=tr.exit_reason,
            n_bars_held=tr.exit_idx - tr.entry_idx,
        )
        for tr in trades
    ]
    return compute_metrics(converted, costs_pct=costs_pct)