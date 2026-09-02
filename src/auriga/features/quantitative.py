"""AURIGA - Features quantitatives (extraction midasV3).

Les fonctions ci-dessous sont copiées depuis
D:/midas_v2/midasV3/src/agents/technical/data_enrichment/quantitative_features.py
(bloc Numba réel, lignes ~131-1388).

Chaque fonction est décorée @njit(nopython=True, cache=True). Leur signature
est conservée à l'identique. L'engine (features/engine.py) les appelle avec
des arrays numpy.

IMPORTANT : ne pas utiliser les fonctions du bloc `else:` (fallback constantes,
lignes 1389+) ni les classes d'optimisation (Dask, cache, memory mapping,
lignes 1500+).
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

@njit(nopython=True, cache=True)
def _numba_hurst_rs(prices, window=252):
    """
    Hurst Exponent avec R/S analysis ROLLING (NO DATA LEAKAGE).
    
    CORRECTION: Version précédente calculait UN SEUL Hurst pour tout le dataset.
    Cette version calcule Hurst sur rolling window de `window` jours.
    
    Args:
        prices: Array de prix
        window: Taille fenêtre rolling (défaut 252 = 1 an trading)
    
    Returns:
        Array de Hurst exponents (même taille que prices)
    """
    n = len(prices)
    hurst_array = np.full(n, 0.5, dtype=OPTIMAL_FLOAT)  # Default: random walk
    
    # Scales pour R/S analysis (ajustées pour window)
    scales = np.array([10, 20, 50, min(100, window // 4)], dtype=np.int32)
    
    for i in range(window, n):
        # Lookback window
        window_prices = prices[i - window : i]
        
        # Calculer rendements sur window
        window_returns = np.diff(window_prices) / window_prices[:-1]
        N = len(window_returns)
        
        if N < 10:
            continue
        
        rs_values = np.zeros(len(scales), dtype=OPTIMAL_FLOAT)
        
        # Pour chaque échelle
        for scale_idx, scale in enumerate(scales):
            if scale >= N:
                continue
            
            n_segments = N // scale
            rs_segment = np.zeros(n_segments, dtype=OPTIMAL_FLOAT)
            
            for j in range(n_segments):
                start_idx = j * scale
                end_idx = start_idx + scale
                segment = window_returns[start_idx:end_idx]
                
                mean_return = np.mean(segment)
                cumulative_devs = np.cumsum(segment - mean_return)
                
                R = np.max(cumulative_devs) - np.min(cumulative_devs)
                S = np.std(segment)
                
                if S > 0:
                    rs_segment[j] = R / S
                else:
                    rs_segment[j] = 1.0
            
            rs_values[scale_idx] = np.mean(rs_segment)
        
        # Log-log regression
        valid_scales = scales[scales < N]
        valid_rs = rs_values[:len(valid_scales)]
        
        if len(valid_scales) >= 2:
            log_scales = np.log(valid_scales.astype(OPTIMAL_FLOAT))
            log_rs = np.log(valid_rs)
            
            # Linear regression slope = Hurst exponent
            n_points = len(log_scales)
            sum_x = np.sum(log_scales)
            sum_y = np.sum(log_rs)
            sum_xy = np.sum(log_scales * log_rs)
            sum_x2 = np.sum(log_scales * log_scales)
            
            denominator = n_points * sum_x2 - sum_x * sum_x
            if abs(denominator) > 1e-10:
                h = (n_points * sum_xy - sum_x * sum_y) / denominator
                hurst_array[i] = max(0.0, min(1.0, h))
    
    return hurst_array

@njit(nopython=True, cache=True)
def _numba_realized_volatility(returns, window=20):
    """Realized Volatility ultra-rapide"""
    N = len(returns)
    if N < window:
        return np.full(N, np.std(returns), dtype=OPTIMAL_FLOAT)

    rv = np.zeros(N, dtype=OPTIMAL_FLOAT)

    # Calcul glissant
    for i in range(window - 1, N):
        window_returns = returns[i - window + 1 : i + 1]
        rv[i] = np.sqrt(np.sum(window_returns**2))

    # Remplir les premières valeurs
    initial_rv = rv[window - 1]
    for i in range(window - 1):
        rv[i] = initial_rv

    return rv

@njit(nopython=True, cache=True)
def _numba_rolling_skewness(prices, window=50):
    """Skewness roulante ultra-rapide"""
    n = len(prices)
    if n < window:
        return np.full(n, 0.0, dtype=OPTIMAL_FLOAT)

    skewness = np.zeros(n, dtype=OPTIMAL_FLOAT)

    for i in range(window - 1, n):
        window_data = prices[i - window + 1 : i + 1]
        mean_val = np.mean(window_data)
        std_val = np.std(window_data)

        if std_val > 1e-10:
            # Calcul du skewness
            skew_sum = 0.0
            for val in window_data:
                skew_sum += ((val - mean_val) / std_val) ** 3
            skewness[i] = skew_sum / window
        else:
            skewness[i] = 0.0

    # Remplir les premières valeurs
    for i in range(window - 1):
        skewness[i] = skewness[window - 1]

    return skewness

@njit(nopython=True, cache=True)
def _numba_rolling_kurtosis(prices, window=50):
    """Kurtosis roulante ultra-rapide"""
    n = len(prices)
    if n < window:
        return np.full(n, 3.0, dtype=OPTIMAL_FLOAT)  # Kurtosis normale = 3

    kurtosis = np.zeros(n, dtype=OPTIMAL_FLOAT)

    for i in range(window - 1, n):
        window_data = prices[i - window + 1 : i + 1]
        mean_val = np.mean(window_data)
        std_val = np.std(window_data)

        if std_val > 1e-10:
            # Calcul du kurtosis
            kurt_sum = 0.0
            for val in window_data:
                kurt_sum += ((val - mean_val) / std_val) ** 4
            kurtosis[i] = kurt_sum / window
        else:
            kurtosis[i] = 3.0

    # Remplir les premières valeurs
    for i in range(window - 1):
        kurtosis[i] = kurtosis[window - 1]

    return kurtosis

@njit(nopython=True, cache=True)
def _numba_dynamic_var(returns, confidence=0.05, window=50):
    """VaR dynamique ultra-rapide"""
    n = len(returns)
    if n < window:
        return np.full(n, 0.0, dtype=OPTIMAL_FLOAT)

    var_values = np.zeros(n, dtype=OPTIMAL_FLOAT)
    percentile_rank = int(confidence * window)

    for i in range(window - 1, n):
        window_returns = returns[i - window + 1 : i + 1].copy()
        # Tri pour trouver le percentile
        window_returns.sort()
        if percentile_rank < len(window_returns):
            var_values[i] = -window_returns[percentile_rank]  # VaR négatif
        else:
            var_values[i] = -window_returns[0]

    # Remplir les premières valeurs
    for i in range(window - 1):
        var_values[i] = var_values[window - 1]

    return var_values

@njit(nopython=True, cache=True)
def _numba_dynamic_cvar(returns, confidence=0.05, window=50):
    """CVaR (Expected Shortfall) dynamique ultra-rapide"""
    n = len(returns)
    if n < window:
        return np.full(n, 0.0, dtype=OPTIMAL_FLOAT)

    cvar_values = np.zeros(n, dtype=OPTIMAL_FLOAT)
    percentile_rank = int(confidence * window)

    for i in range(window - 1, n):
        window_returns = returns[i - window + 1 : i + 1].copy()
        window_returns.sort()

        # CVaR = moyenne des returns pires que VaR
        if percentile_rank > 0:
            tail_returns = window_returns[:percentile_rank]
            cvar_values[i] = -np.mean(tail_returns)  # CVaR négatif
        else:
            cvar_values[i] = -window_returns[0]

    # Remplir les premières valeurs
    for i in range(window - 1):
        cvar_values[i] = cvar_values[window - 1]

    return cvar_values

@njit(nopython=True, cache=True)
def _numba_max_drawdown(prices, window=100):
    """Maximum Drawdown roulant ultra-rapide"""
    n = len(prices)
    if n < window:
        return np.full(n, 0.0, dtype=OPTIMAL_FLOAT)

    drawdowns = np.zeros(n, dtype=OPTIMAL_FLOAT)

    for i in range(window - 1, n):
        window_prices = prices[i - window + 1 : i + 1]

        # Trouver le maximum drawdown dans la fenêtre
        max_dd = 0.0
        peak = window_prices[0]

        for price in window_prices:
            if price > peak:
                peak = price

            drawdown = (peak - price) / peak if peak > 0 else 0.0
            if drawdown > max_dd:
                max_dd = drawdown

        drawdowns[i] = max_dd

    # Remplir les premières valeurs
    for i in range(window - 1):
        drawdowns[i] = drawdowns[window - 1]

    return drawdowns

@njit(nopython=True, cache=True)
def _numba_regime_detection(returns, lookback=50):
    """Détection de régime adaptative ultra-rapide (z-score, asset-agnostique)"""
    n = len(returns)
    if n < lookback:
        return np.full(n, 0.0, dtype=OPTIMAL_FLOAT)  # Régime neutre

    regimes = np.zeros(n, dtype=OPTIMAL_FLOAT)

    for i in range(lookback - 1, n):
        window_returns = returns[i - lookback + 1 : i + 1]

        # Calculs adaptatifs pour classification de régime
        mean_return = np.mean(window_returns)
        volatility = np.std(window_returns)

        # Z-score du rendement moyen (adaptatif à l'échelle de l'asset)
        # Évite les seuils absolus qui ne fonctionnent pas cross-asset
        if volatility > 1e-10:
            z_score = mean_return / volatility
        else:
            z_score = 0.0

        # Volatilité relative au rendement moyen absolu
        # Ratio élevé = marché chaotique, ratio bas = marché directionnel
        mean_abs = np.mean(np.abs(window_returns))
        vol_ratio = volatility / mean_abs if mean_abs > 1e-10 else 2.0

        # Classification adaptative:
        # 1.0 = Bull (z-score positif significatif, volatilité contrôlée)
        # -1.0 = Bear (z-score négatif significatif, volatilité élevée)
        # 0.0 = Sideways (z-score faible ou volatilité non directionnelle)

        if z_score > 0.5 and vol_ratio < 1.5:
            regimes[i] = 1.0  # Bull
        elif z_score < -0.5 and vol_ratio > 1.0:
            regimes[i] = -1.0  # Bear
        else:
            regimes[i] = 0.0  # Sideways

    # Remplir les premières valeurs
    for i in range(lookback - 1):
        regimes[i] = regimes[lookback - 1]

    return regimes

@njit(nopython=True, cache=True)
def _numba_kaufman_efficiency(prices, window=20):
    """Ratio d'efficience de Kaufman ultra-rapide"""
    n = len(prices)
    if n < window:
        return np.full(n, 0.5, dtype=OPTIMAL_FLOAT)
        
    er = np.zeros(n, dtype=OPTIMAL_FLOAT)
    
    abs_diff = np.abs(np.diff(prices))
    abs_diff = np.concatenate((np.array([0.0], dtype=OPTIMAL_FLOAT), abs_diff))
    
    for i in range(window, n):
        # Directional movement: |Price_t - Price_t-n|
        direction = np.abs(prices[i] - prices[i - window])
        
        # Volatility: Sum(|Price_i - Price_i-1|)
        volatility = np.sum(abs_diff[i - window + 1 : i + 1])
        
        if volatility > 1e-10:
            er[i] = direction / volatility
        else:
            er[i] = 1.0 if direction == 0 else 0.0
            
    # Remplir
    for i in range(window):
        er[i] = er[window] if window < n else 0.5
        
    return er
    
@njit(nopython=True, cache=True)
def calculate_market_regime_numba(returns, volatility, window=50):
    """Régime de marché combiné ultra-rapide"""
    n = len(returns)
    if n < window:
        return np.zeros(n, dtype=OPTIMAL_FLOAT)

    regime = np.zeros(n, dtype=OPTIMAL_FLOAT)

    for i in range(window - 1, n):
        window_returns = returns[i - window + 1 : i + 1]
        window_vol = (
            volatility[i - window + 1 : i + 1]
            if i < len(volatility)
            else np.full(window, 0.1)
        )

        mean_return = np.mean(window_returns)
        mean_vol = np.mean(window_vol)

        # Classification des régimes
        if mean_return > 0.002 and mean_vol < 0.02:
            regime[i] = 2.0  # Bull market
        elif mean_return < -0.002 and mean_vol > 0.03:
            regime[i] = -2.0  # Bear market
        elif mean_vol > 0.04:
            regime[i] = -1.0  # High volatility
        else:
            regime[i] = 0.0  # Neutral/Sideways

    # Remplir les premières valeurs
    for i in range(window - 1):
        regime[i] = regime[window - 1]

    return regime