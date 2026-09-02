"""AURIGA - Indicateurs techniques (extraction midasV3).

Les fonctions ci-dessous sont copiées depuis
D:/midas_v2/midasV3/src/agents/technical/data_enrichment/technical_indicators.py
(bloc Numba réel, lignes ~67-978).

Chaque fonction est décorée @njit(nopython=True, cache=True). Leur signature
est conservée à l'identique. L'engine (features/engine.py) les appelle avec
des arrays numpy float64/float32.

IMPORTANT : ne pas utiliser les fonctions du bloc `else:` (fallback constantes)
ni les classes d'optimisation (Dask, cache, memory mapping) du même fichier.
"""
from __future__ import annotations

import numpy as np

try:
    from numba import njit, prange

    NUMBA_AVAILABLE = True
except ImportError:  # pragma: no cover
    NUMBA_AVAILABLE = False

    def njit(*args, **kwargs):
        def decorator(func):
            return func

        return decorator if args and callable(args[0]) else decorator

    prange = range
    
OPTIMAL_FLOAT = np.float32

@njit(nopython=True, cache=True, parallel=True)
def _numba_ema_vectorized(prices, periods_array):
    """Calcul vectorisé multi-périodes de l'EMA ultra-rapide"""
    n = len(prices)
    num_periods = len(periods_array)
    results = np.full((num_periods, n), np.nan, dtype=OPTIMAL_FLOAT)
    
    if n < 2:
        return results
    
    # Calcul pour chaque période
    for p_idx in prange(num_periods):
        period = periods_array[p_idx]
        
        if period >= n:
            continue
        
        # Premier EMA = SMA
        results[p_idx, period - 1] = np.mean(prices[:period])
        
        # Coefficient de lissage
        alpha = 2.0 / (period + 1.0)
        
        # Calculs EMA suivants
        for i in range(period, n):
            results[p_idx, i] = alpha * prices[i] + (1.0 - alpha) * results[p_idx, i - 1]
    
    return results


@njit(nopython=True, cache=True, parallel=True)
def _numba_sma_vectorized(prices, periods_array):
    """Calcul vectorisé multi-périodes du SMA ultra-rapide"""
    n = len(prices)
    num_periods = len(periods_array)
    results = np.full((num_periods, n), np.nan, dtype=OPTIMAL_FLOAT)
    
    if n < 1:
        return results
    
    # Calcul pour chaque période
    for p_idx in prange(num_periods):
        period = periods_array[p_idx]
        
        if period >= n:
            continue
        
        # Calcul SMA pour chaque position
        for i in range(period - 1, n):
            results[p_idx, i] = np.mean(prices[i - period + 1 : i + 1])
    
    return results


@njit(nopython=True, cache=True, parallel=True)
def _numba_rsi_vectorized(prices, periods_array):
    """Calcul vectorisé multi-périodes du RSI ultra-rapide"""
    n = len(prices)
    num_periods = len(periods_array)
    results = np.full((num_periods, n), np.nan, dtype=OPTIMAL_FLOAT)
    
    if n < 2:
        return results
    
    # Calcul des variations
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    
    # Calcul pour chaque période
    for p_idx in prange(num_periods):
        period = periods_array[p_idx]
        
        if period >= n:
            continue
            
        # Premier RSI (SMA)
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])
        
        if avg_loss == 0:
            results[p_idx, period] = 100.0
        else:
            rs = avg_gain / avg_loss
            results[p_idx, period] = 100.0 - (100.0 / (1.0 + rs))
        
        # Calculs suivants avec EMA
        for i in range(period + 1, n):
            avg_gain = (avg_gain * (period - 1) + gains[i - 1]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i - 1]) / period
            
            if avg_loss == 0:
                results[p_idx, i] = 100.0
            else:
                rs = avg_gain / avg_loss
                results[p_idx, i] = 100.0 - (100.0 / (1.0 + rs))
    
    return results


@njit(nopython=True, cache=True)
def _numba_macd_complete(prices, fast=12, slow=26, signal=9):
    """MACD complet ultra-rapide avec ligne de signal et histogramme"""
    n = len(prices)

    # EMA rapide et lente
    alpha_fast = 2.0 / (fast + 1.0)
    alpha_slow = 2.0 / (slow + 1.0)
    alpha_signal = 2.0 / (signal + 1.0)

    ema_fast = np.full(n, np.nan, dtype=OPTIMAL_FLOAT)
    ema_slow = np.full(n, np.nan, dtype=OPTIMAL_FLOAT)
    macd_line = np.full(n, np.nan, dtype=OPTIMAL_FLOAT)
    signal_line = np.full(n, np.nan, dtype=OPTIMAL_FLOAT)
    histogram = np.full(n, np.nan, dtype=OPTIMAL_FLOAT)

    # Initialisation EMA
    ema_fast[fast - 1] = np.mean(prices[:fast])
    ema_slow[slow - 1] = np.mean(prices[:slow])

    # Calcul EMA
    for i in range(fast, n):
        ema_fast[i] = alpha_fast * prices[i] + (1 - alpha_fast) * ema_fast[i - 1]

    for i in range(slow, n):
        ema_slow[i] = alpha_slow * prices[i] + (1 - alpha_slow) * ema_slow[i - 1]

    # MACD line
    for i in range(slow - 1, n):
        if not np.isnan(ema_fast[i]) and not np.isnan(ema_slow[i]):
            macd_line[i] = ema_fast[i] - ema_slow[i]

    # Signal line
    signal_start = slow + signal - 2
    if signal_start < n:
        signal_line[signal_start] = macd_line[signal_start]

        for i in range(signal_start + 1, n):
            if not np.isnan(macd_line[i]):
                signal_line[i] = (
                    alpha_signal * macd_line[i]
                    + (1 - alpha_signal) * signal_line[i - 1]
                )

    # Histogramme
    for i in range(n):
        if not np.isnan(macd_line[i]) and not np.isnan(signal_line[i]):
            histogram[i] = macd_line[i] - signal_line[i]

    return macd_line, signal_line, histogram


@njit(nopython=True, cache=True)
def _numba_bollinger_bands(prices, period=20, std_dev=2.0):
    """Bollinger Bands ultra-rapides"""
    n = len(prices)
    middle = np.full(n, np.nan, dtype=OPTIMAL_FLOAT)
    upper = np.full(n, np.nan, dtype=OPTIMAL_FLOAT)
    lower = np.full(n, np.nan, dtype=OPTIMAL_FLOAT)

    for i in range(period - 1, n):
        window = prices[i - period + 1 : i + 1]
        sma = np.mean(window)
        std = np.std(window)

        middle[i] = sma
        upper[i] = sma + (std_dev * std)
        lower[i] = sma - (std_dev * std)

    return upper, middle, lower


@njit(nopython=True, cache=True)
def _numba_atr(high, low, close, period=14):
    """Average True Range ultra-rapide"""
    n = len(high)
    tr = np.full(n, np.nan, dtype=OPTIMAL_FLOAT)
    atr = np.full(n, np.nan, dtype=OPTIMAL_FLOAT)

    # True Range
    for i in range(1, n):
        tr1 = high[i] - low[i]
        tr2 = abs(high[i] - close[i - 1])
        tr3 = abs(low[i] - close[i - 1])
        tr[i] = max(tr1, tr2, tr3)

    tr[0] = high[0] - low[0]  # Premier TR

    # ATR (moyenne mobile du TR)
    atr[period - 1] = np.mean(tr[:period])

    for i in range(period, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period

    return atr

@njit(nopython=True, cache=True)
def _numba_adx_complete(high, low, close, period=14):
    """ADX complet avec DI+ et DI- ultra-rapide"""
    n = len(high)

    # Initialiser les arrays
    tr = np.full(n, np.nan, dtype=OPTIMAL_FLOAT)
    dm_plus = np.full(n, np.nan, dtype=OPTIMAL_FLOAT)
    dm_minus = np.full(n, np.nan, dtype=OPTIMAL_FLOAT)

    di_plus = np.full(n, np.nan, dtype=OPTIMAL_FLOAT)
    di_minus = np.full(n, np.nan, dtype=OPTIMAL_FLOAT)
    adx = np.full(n, np.nan, dtype=OPTIMAL_FLOAT)

    # Calcul TR, DM+ et DM-
    for i in range(1, n):
        # True Range
        tr1 = high[i] - low[i]
        tr2 = abs(high[i] - close[i - 1])
        tr3 = abs(low[i] - close[i - 1])
        tr[i] = max(tr1, tr2, tr3)

        # Directional Movement
        up_move = high[i] - high[i - 1]
        down_move = low[i - 1] - low[i]

        if up_move > down_move and up_move > 0:
            dm_plus[i] = up_move
        else:
            dm_plus[i] = 0.0

        if down_move > up_move and down_move > 0:
            dm_minus[i] = down_move
        else:
            dm_minus[i] = 0.0

    # Premier TR
    tr[0] = high[0] - low[0]
    dm_plus[0] = 0.0
    dm_minus[0] = 0.0

    # Calcul des moyennes mobiles
    if n > period:
        # ATR
        atr_sum = np.sum(tr[1 : period + 1])
        atr = atr_sum

        # DM+ et DM- moyennes
        dm_plus_sum = np.sum(dm_plus[1 : period + 1])
        dm_minus_sum = np.sum(dm_minus[1 : period + 1])

        dm_plus_avg = dm_plus_sum
        dm_minus_avg = dm_minus_sum

        # Calcul DI+ et DI-
        if atr != 0:
            di_plus[period] = 100.0 * dm_plus_avg / atr
            di_minus[period] = 100.0 * dm_minus_avg / atr

        # Calculs suivants avec lissage
        for i in range(period + 1, n):
            # ATR lissé
            atr = atr - (atr / period) + tr[i]

            # DM lissés
            dm_plus_avg = dm_plus_avg - (dm_plus_avg / period) + dm_plus[i]
            dm_minus_avg = dm_minus_avg - (dm_minus_avg / period) + dm_minus[i]

            # DI+ et DI-
            if atr != 0:
                di_plus[i] = 100.0 * dm_plus_avg / atr
                di_minus[i] = 100.0 * dm_minus_avg / atr

        # Calcul ADX
        dx_values = np.full(n, np.nan, dtype=OPTIMAL_FLOAT)
        for i in range(period, n):
            if not np.isnan(di_plus[i]) and not np.isnan(di_minus[i]):
                di_sum = di_plus[i] + di_minus[i]
                if di_sum != 0:
                    dx_values[i] = 100.0 * abs(di_plus[i] - di_minus[i]) / di_sum

        # ADX comme moyenne mobile de DX
        if period * 2 < n:
            adx_start = period * 2 - 1
            adx[adx_start] = np.mean(dx_values[period : adx_start + 1])

            for i in range(adx_start + 1, n):
                if not np.isnan(dx_values[i]):
                    adx[i] = (adx[i - 1] * (period - 1) + dx_values[i]) / period

    return adx, di_plus, di_minus