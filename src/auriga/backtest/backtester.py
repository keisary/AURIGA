"""AURIGA - Backtester : simulation des Einhers sur données 1H réelles.

Logique adaptée d'einherjar (les corrections y sont déjà appliquées) :
- Signal → entrée à t+1 (OPEN de la bougie suivante)
- Sortie : TP = tp_atr_mult × ATR, SL = sl_atr_mult × ATR (anti-tautologie)
  ou timeout après `horizon_bars` barres
- Si TP et SL touchés sur la même bougie → SL d'abord (conservateur)
- Métriques : Sharpe annualisé (cap 50k trades/an), t-stat one-sided upper,
  equity composée, max drawdown, profit factor, win rate
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from math import erf, sqrt

import numpy as np
import polars as pl

from auriga.research.condition_tree import evaluate_ast_on_array
from auriga.types import Condition, ConditionNode, Einher, EinherMetrics

logger = logging.getLogger(__name__)

ATR_PERIOD = 14
DEFAULT_TP_ATR = 2.5
DEFAULT_SL_ATR = 1.5


@dataclass
class TradeResult:
    """Résultat d'un trade simulé."""

    entry_idx: int
    exit_idx: int
    direction: str
    entry_price: float
    exit_price: float
    net_return: float  # après coûts
    exit_reason: str  # 'tp' | 'sl' | 'timeout'
    n_bars_held: int


@dataclass
class BacktestResult:
    """Résultat complet d'un backtest."""

    trades: list[TradeResult]
    metrics: EinherMetrics
    effective_tp_pct: float = 0.0
    effective_sl_pct: float = 0.0


# ---------------------------------------------------------------------------
# ATR
# ---------------------------------------------------------------------------

def compute_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """ATR Wilder (formule identique einherjar)."""
    n = len(high)
    tr = np.zeros(n, dtype=np.float64)
    if n > 0:
        tr[0] = high[0] - low[0]
    tr[1:] = np.maximum(
        high[1:] - low[1:],
        np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1])),
    )
    atr = np.full(n, np.nan, dtype=np.float64)
    if n < period:
        return atr
    atr[period - 1] = np.mean(tr[:period])
    for i in range(period, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


# ---------------------------------------------------------------------------
# Simulation d'un trade
# ---------------------------------------------------------------------------

def simulate_trade(
    entry_idx: int,
    amplitude: int,
    direction: str,
    entry_price: float,
    tp_pct: float,
    sl_pct: float,
    highs: np.ndarray,
    lows: np.ndarray,
    opens: np.ndarray,
) -> tuple[float, str, int]:
    """Simule un trade sur [entry_idx, entry_idx+amplitude-1].

    Convention SL-first si TP et SL sur la même bougie (conservateur).
    Timeout → sortie à l'OPEN de la bougie suivante.

    Returns:
        (exit_price, exit_reason, n_bars_held)
    """
    if direction == "LONG":
        tp_price = entry_price * (1 + tp_pct)
        sl_price = entry_price * (1 - sl_pct)
    else:  # SHORT
        tp_price = entry_price * (1 - tp_pct)
        sl_price = entry_price * (1 + sl_pct)

    for offset in range(amplitude):
        idx = entry_idx + offset
        if idx >= len(highs):
            break
        h = highs[idx]
        lo = lows[idx]
        if direction == "LONG":
            tp_hit = h >= tp_price
            sl_hit = lo <= sl_price
        else:
            tp_hit = lo <= tp_price
            sl_hit = h >= sl_price
        if sl_hit and tp_hit:
            return sl_price, "sl", offset + 1
        if sl_hit:
            return sl_price, "sl", offset + 1
        if tp_hit:
            return tp_price, "tp", offset + 1

    # Timeout : sortie à l'OPEN de la bougie suivante
    next_open = entry_idx + amplitude
    if next_open < len(opens):
        return float(opens[next_open]), "timeout", amplitude
    return float(opens[min(entry_idx + amplitude - 1, len(opens) - 1)]), "timeout", amplitude


# ---------------------------------------------------------------------------
# Métriques
# ---------------------------------------------------------------------------

def compute_metrics(
    trades: list[TradeResult],
    buy_hold_return: float = 0.0,
    years_in_period: float = 1.0,
    costs_pct: float = 0.001,
) -> EinherMetrics:
    """Calcule les métriques depuis une liste de trades (formules einherjar corrigées)."""
    n = len(trades)
    if n == 0:
        return EinherMetrics(
            n_trades=0, sharpe_ratio=0.0, win_rate=0.0, profit_factor=0.0,
            max_drawdown=0.0, t_statistic=0.0, total_return=0.0,
            avg_net_return=0.0,
        )

    rets = np.array([t.net_return for t in trades], dtype=np.float64)
    reasons = np.array([t.exit_reason for t in trades])
    n_tp = int((reasons == "tp").sum())
    n_sl = int((reasons == "sl").sum())
    n_timeout = int((reasons == "timeout").sum())

    win_rate = float((rets > 0).mean())
    avg_net = float(np.mean(rets))
    # total return COMPOSÉ (pas une somme)
    total = float(np.prod(1.0 + rets) - 1.0)

    std = float(np.std(rets, ddof=1)) if n > 1 else 0.0
    degenerate = std <= 1e-12 * max(1e-12, abs(avg_net))

    # Sharpe annualisé : avg/std × sqrt(trades_per_year), cap 50k trades/an
    if std > 0 and not degenerate and years_in_period > 0:
        trades_per_year = min(n / years_in_period, 50_000.0)
        sharpe = float(avg_net / std * np.sqrt(trades_per_year))
    else:
        sharpe = 0.0

    # t-stat one-sided upper (p-value pour BH)
    if n > 1 and std > 0 and not degenerate:
        t_stat = float(avg_net / (std / np.sqrt(n)))
        if t_stat <= 1e-9:
            p_val = 1.0
        else:
            p_val = 1.0 - 0.5 * (1.0 + erf(t_stat / sqrt(2.0)))
            p_val = max(p_val, 1e-10)
    else:
        t_stat = 0.0
        p_val = 1.0

    # Max drawdown sur equity composée
    eq = np.cumprod(np.maximum(1.0 + rets, 1e-9))
    peak = np.maximum.accumulate(eq)
    dd_frac = (eq - peak) / np.maximum(peak, 1e-12)
    max_dd = float(np.min(dd_frac)) if len(dd_frac) > 0 else 0.0

    # Profit factor
    gains = rets[rets > 0].sum()
    losses = abs(rets[rets < 0].sum())
    pf = float(gains / losses) if losses > 0 else (float("inf") if gains > 0 else 0.0)

    avg_hold = float(np.mean([t.n_bars_held for t in trades]))

    return EinherMetrics(
        n_trades=n,
        sharpe_ratio=sharpe,
        win_rate=win_rate,
        profit_factor=pf,
        max_drawdown=max_dd,
        t_statistic=t_stat,
        total_return=total,
        avg_net_return=avg_net,
        cagr=0.0,
        extra={"n_tp": n_tp, "n_sl": n_sl, "n_timeout": n_timeout,
               "p_value": p_val, "avg_holding_bars": avg_hold,
               "costs_pct": costs_pct},
    )


# ---------------------------------------------------------------------------
# Backtest principal
# ---------------------------------------------------------------------------

def backtest_einher(
    einher: Einher,
    ohlcv: pl.DataFrame,
    X: np.ndarray,
    feature_names: list[str],
    costs_pct: float = 0.001,
    tp_atr_mult: float = DEFAULT_TP_ATR,
    sl_atr_mult: float = DEFAULT_SL_ATR,
    max_positions: int = 1,
) -> BacktestResult:
    """Backtest un Einher sur une fenêtre donnée (slicée par l'appelant).

    Entrée : X et ohlcv ALIGNÉS (même nombre de lignes). Les signaux sont
    évalués sur X, les trades simulés sur ohlcv.

    Args:
        einher : stratégie à tester
        ohlcv : bars [timestamp, open, high, low, close, volume] (fenêtre)
        X : features alignées (fenêtre)
        feature_names : noms des colonnes de X
        costs_pct : coût round-trip par trade (défaut 0.1%)
    """
    n = X.shape[0]
    if n < 50:
        return BacktestResult(trades=[], metrics=EinherMetrics(n_trades=0))

    # Signaux : où la condition est vraie
    signal_mask = evaluate_ast_on_array(einher.condition, X, feature_names)
    signal_idx = np.where(signal_mask)[0]

    close = ohlcv["close"].to_numpy().astype(np.float64)
    high = ohlcv["high"].to_numpy().astype(np.float64)
    low = ohlcv["low"].to_numpy().astype(np.float64)
    open_ = ohlcv["open"].to_numpy().astype(np.float64)

    # ATR pour TP/SL (dynamique par barre)
    atr = compute_atr(high, low, close, ATR_PERIOD)

    # Buy & hold sur la fenêtre
    buy_hold = float(close[-1] / close[0] - 1.0) if len(close) > 1 else 0.0
    years = max(n / (252 * 24), 1 / 252)  # 1H → 252×24 barres/an

    trades: list[TradeResult] = []
    # Parcours des signaux : on saute ceux qui tombent pendant une position
    next_free_idx = 0  # prochain index où une nouvelle entrée est possible

    for t in signal_idx:
        if t < next_free_idx:
            continue  # déjà en position à cet instant
        if t + 1 >= n:
            continue
        if np.isnan(atr[t]) or atr[t] <= 0:
            continue

        entry_idx = t + 1
        entry_price = open_[entry_idx]
        if entry_price <= 0:
            continue

        # TP/SL en multiples d'ATR de la barre du signal
        atr_entry = atr[t]
        tp_pct = tp_atr_mult * atr_entry / entry_price
        sl_pct = sl_atr_mult * atr_entry / entry_price

        horizon = einher.horizon_bars if einher.horizon_bars > 0 else 24
        exit_price, reason, held = simulate_trade(
            entry_idx, horizon, einher.direction, entry_price,
            tp_pct, sl_pct, high, low, open_,
        )

        gross_ret = (exit_price / entry_price - 1.0) if einher.direction == "LONG" \
            else (1.0 - exit_price / entry_price)
        net_ret = gross_ret - costs_pct

        trades.append(
            TradeResult(
                entry_idx=entry_idx,
                exit_idx=entry_idx + held,
                direction=einher.direction,
                entry_price=entry_price,
                exit_price=exit_price,
                net_return=net_ret,
                exit_reason=reason,
                n_bars_held=held,
            )
        )
        # Prochaine entrée possible après la fin de cette position
        next_free_idx = entry_idx + held

    metrics = compute_metrics(trades, buy_hold, years, costs_pct)
    return BacktestResult(
        trades=trades,
        metrics=metrics,
        effective_tp_pct=DEFAULT_TP_ATR,
        effective_sl_pct=DEFAULT_SL_ATR,
    )