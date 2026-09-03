"""AURIGA - Backtest des stratégies d'options (vol & vente de prime).

Contexte : Alpaca ne fournit pas de prix d'options historiques. On estime le
P&L des stratégies d'options en repricant via Black-Scholes à l'entrée ET à
la sortie, avec la vol RÉALISÉE de la fenêtre comme proxy de la vol future.

Stratégies simulées :
- LONG STRADDLE (Agent A2 VOL_UP) : achat call + put ATM, profit si |mouvement|
  > prime payée (la vol réalisée dépasse la vol implicite payée).
- SHORT STRADDLE / CREDIT SPREAD (Agent A3) : vente, profit du theta si le
  sous-jacent ne bouge pas trop.

Simplification honnête : à l'entrée, on paie la vol implicite (IV ~ RV
historique + prime) ; à la sortie (H barres plus tard), on repricie avec la
vol réalisée de la fenêtre écoulée. Le P&L = différence de prix × 100.
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

ATM_STRIKE_MULT = 1.00  # strike ATM = spot
IV_BUMP = 0.05  # vol implicite = vol réalisée + 5pts (variance risk premium)
MULTIPLIER = 100  # contrat = 100 actions


@dataclass
class OptionTrade:
    """Trade d'options simulé."""

    entry_idx: int
    exit_idx: int
    direction: str  # VOL_UP | VOL_DOWN
    entry_price: float  # coût total straddle (ou crédit reçu)
    exit_price: float
    net_return: float  # P&L / capital engagé (approx)
    exit_reason: str  # 'expiry' | 'timeout'


def _estimate_vol(close: np.ndarray, window: int = 20) -> np.ndarray:
    """Vol réalisée annualisée approximée sur fenêtre glissante."""
    from auriga.features.quantitative import _numba_realized_volatility

    rets = np.full(len(close), np.nan, dtype=np.float64)
    if len(close) > 1:
        rets[1:] = close[1:] / close[:-1] - 1.0
    rv = np.asarray(_numba_realized_volatility(rets, window), dtype=np.float64)
    # RV par barre ~ sqrt(252*24) pour annualiser (1H) — ici on garde per-bar
    return rv


def backtest_vol_einher(
    einher: Einher,
    ohlcv: pl.DataFrame,
    X: np.ndarray,
    feature_names: list[str],
    costs_pct: float = 0.001,
    vol_window: int = 20,
) -> tuple[list[OptionTrade], EinherMetrics]:
    """Backtest un Einher VOL (straddle long si VOL_UP, short si VOL_DOWN).

    Méthode :
    1. Signaux = où la condition est vraie.
    2. À l'entrée (t+1) : prix straddle ATM avec vol_impl = RV_t + bump.
    3. À la sortie (t+1+H) : reprice avec vol réalisée de [t, t+H].
    4. P&L straddle long ≈ (prix_sortie − prix_entrée) × 2 legs × 100.
    """
    n = X.shape[0]
    if n < 50:
        return [], EinherMetrics(n_trades=0)

    signal_mask = evaluate_ast_on_array(einher.condition, X, feature_names)
    signal_idx = np.where(signal_mask)[0]

    close = ohlcv["close"].to_numpy().astype(np.float64)
    rv = _estimate_vol(close, vol_window)
    horizon = einher.horizon_bars if einher.horizon_bars > 0 else 24

    trades: list[OptionTrade] = []
    next_free = 0

    for t in signal_idx:
        if t < next_free or t + horizon >= n:
            continue
        entry_idx = t + 1
        S0 = close[t]
        if S0 <= 0 or np.isnan(rv[t]) or rv[t] <= 0:
            continue

        # Vol implicite à l'entrée = vol réalisée + prime de risque
        iv_entry = min(rv[t] + IV_BUMP, 1.5)
        # Vol réalisée sur la fenêtre de détention (sortie)
        window_rets = close[t : t + horizon + 1]
        if len(window_rets) < 2:
            continue
        rv_exit = np.std(np.diff(window_rets) / window_rets[:-1]) * np.sqrt(1)  # per-bar

        # Temps restant (en années, approximation 1H → 1/(252*24))
        T_entry = max(horizon / (252 * 24), 1e-4)

        # Prix straddle ATM à l'entrée (2 legs)
        call_entry = black_scholes(S0, S0 * ATM_STRIKE_MULT, T_entry, sigma=iv_entry, option_type="call").price
        put_entry = black_scholes(S0, S0 * ATM_STRIKE_MULT, T_entry, sigma=iv_entry, option_type="put").price
        straddle_entry = (call_entry + put_entry) * MULTIPLIER

        # Prix à la sortie : sous-jacent à S_exit, vol réalisée, temps ≈ 0
        S_exit = close[min(t + horizon, n - 1)]
        iv_exit = max(rv_exit, 0.01)
        T_exit = max((horizon - (t + horizon - entry_idx)) / (252 * 24), 1e-6)
        # Pour un straddle, à l'échéance le prix ≈ |S-K| (intrinsèque)
        # On reprice avec vol résiduelle petite (on est proche de l'échéance)
        call_exit = black_scholes(S_exit, S0 * ATM_STRIKE_MULT, T_exit, sigma=iv_exit, option_type="call").price
        put_exit = black_scholes(S_exit, S0 * ATM_STRIKE_MULT, T_exit, sigma=iv_exit, option_type="put").price
        straddle_exit = (call_exit + put_exit) * MULTIPLIER

        if einher.direction == "VOL_UP":
            # Long straddle : profit si le straddle a pris de la valeur
            gross = straddle_exit - straddle_entry
            capital = straddle_entry
        else:
            # Short straddle : profit si le straddle a perdu de la valeur
            gross = straddle_entry - straddle_exit
            capital = straddle_entry

        net_ret = gross / max(capital, 1.0) - costs_pct
        trades.append(
            OptionTrade(
                entry_idx=entry_idx,
                exit_idx=entry_idx + horizon,
                direction=einher.direction,
                entry_price=straddle_entry,
                exit_price=straddle_exit,
                net_return=net_ret,
                exit_reason="timeout",
            )
        )
        next_free = entry_idx + horizon

    metrics = _metrics_from_option_trades(trades, costs_pct)
    return trades, metrics


def _metrics_from_option_trades(trades: list[OptionTrade], costs_pct: float) -> EinherMetrics:
    """Métriques depuis les trades d'options (mêmes formules que le backtester)."""
    from auriga.backtest.backtester import compute_metrics
    from auriga.backtest.backtester import TradeResult

    # Convertir en TradeResult pour réutiliser compute_metrics
    converted = [
        TradeResult(
            entry_idx=tr.entry_idx, exit_idx=tr.exit_idx,
            direction="LONG" if tr.net_return >= 0 else "SHORT",
            entry_price=tr.entry_price, exit_price=tr.exit_price,
            net_return=tr.net_return, exit_reason=tr.exit_reason,
            n_bars_held=tr.exit_idx - tr.entry_idx,
        )
        for tr in trades
    ]
    return compute_metrics(converted, costs_pct=costs_pct)