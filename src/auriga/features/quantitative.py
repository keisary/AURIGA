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


# ============================================================================
# À COLLER : _numba_realized_volatility
# Source midas : quantitative_features.py, lignes 141-159
# Signature : def _numba_realized_volatility(returns, window=20):
#   -> np.ndarray float32
# ============================================================================


# ============================================================================
# À COLLER : _numba_garch_volatility
# Source midas : quantitative_features.py, lignes 162-179
# Signature : def _numba_garch_volatility(returns, alpha=0.1, beta=0.8):
#   -> np.ndarray float32
# ============================================================================


# ============================================================================
# À COLLER : _numba_volatility_clustering
# Source midas : quantitative_features.py, lignes 182-212
# Signature : def _numba_volatility_clustering(returns, threshold_factor=2.0, window=100):
#   -> np.ndarray float32 (rolling, NO data leakage)
# ============================================================================


# ============================================================================
# À COLLER : _numba_volatility_persistence
# Source midas : quantitative_features.py, lignes 215-255
# Signature : def _numba_volatility_persistence(returns, window=100):
#   -> np.ndarray float32 (rolling, NO data leakage)
# ============================================================================


# ============================================================================
# À COLLER : _numba_hurst_rs
# Source midas : quantitative_features.py, lignes 260-339
# Signature : def _numba_hurst_rs(prices, window=252):
#   -> np.ndarray float32 (rolling Hurst exponent, 0-1)
# ============================================================================


# ============================================================================
# À COLLER : _numba_autocorrelation
# Source midas : quantitative_features.py, lignes 342-384
# Signature : def _numba_autocorrelation(prices, max_lag=20, window=252):
#   -> np.ndarray float32 (rolling autocorrelation)
# ============================================================================


# ============================================================================
# À COLLER : _numba_shannon_entropy
# Source midas : quantitative_features.py, lignes 386-439
# Signature : def _numba_shannon_entropy(prices, bins=50, window=252):
#   -> np.ndarray float32 (rolling entropy)
# ============================================================================


# ============================================================================
# À COLLER : _numba_dominant_frequency
# Source midas : quantitative_features.py, lignes 575-629
# Signature : def _numba_dominant_frequency(prices, window=252):
#   -> np.ndarray float32
# ============================================================================


# ============================================================================
# À COLLER : _numba_spectral_centroid
# Source midas : quantitative_features.py, lignes 631-683
# Signature : def _numba_spectral_centroid(prices, window=252):
#   -> np.ndarray float32
# ============================================================================


# ============================================================================
# À COLLER : _numba_fractal_dimension
# Source midas : quantitative_features.py, lignes 685-766
# Signature : def _numba_fractal_dimension(prices, window=252):
#   -> np.ndarray float32
# ============================================================================


# ============================================================================
# À COLLER : _numba_dfa
# Source midas : quantitative_features.py, lignes 768-851
# Signature : def _numba_dfa(prices, window=252):
#   -> np.ndarray float32 (Detrended Fluctuation Analysis)
# ============================================================================


# ============================================================================
# À COLLER : _numba_rolling_skewness
# Source midas : quantitative_features.py, lignes 853-880
# Signature : def _numba_rolling_skewness(prices, window=50):
#   -> np.ndarray float32
# ============================================================================


# ============================================================================
# À COLLER : _numba_rolling_kurtosis
# Source midas : quantitative_features.py, lignes 882-909
# Signature : def _numba_rolling_kurtosis(prices, window=50):
#   -> np.ndarray float32 (base 3 = normale)
# ============================================================================


# ============================================================================
# À COLLER : _numba_dynamic_var
# Source midas : quantitative_features.py, lignes 911-934
# Signature : def _numba_dynamic_var(returns, confidence=0.05, window=50):
#   -> np.ndarray float32 (VaR dynamique)
# ============================================================================


# ============================================================================
# À COLLER : _numba_dynamic_cvar
# Source midas : quantitative_features.py, lignes 936-961
# Signature : def _numba_dynamic_cvar(returns, confidence=0.05, window=50):
#   -> np.ndarray float32 (CVaR dynamique)
# ============================================================================


# ============================================================================
# À COLLER : _numba_max_drawdown
# Source midas : quantitative_features.py, lignes 963-993
# Signature : def _numba_max_drawdown(prices, window=100):
#   -> np.ndarray float32
# ============================================================================


# ============================================================================
# À COLLER : _numba_regime_detection
# Source midas : quantitative_features.py, lignes 995-1041
# Signature : def _numba_regime_detection(returns, lookback=50):
#   -> np.ndarray float32 (régime marché)
# ============================================================================


# ============================================================================
# À COLLER : _numba_amihud_illiquidity
# Source midas : quantitative_features.py, lignes 1043-1079
# Signature : def _numba_amihud_illiquidity(returns, volume, window=20):
#   -> np.ndarray float32
# ============================================================================


# ============================================================================
# À COLLER : _numba_kyles_lambda
# Source midas : quantitative_features.py, lignes 1081-1123
# Signature : def _numba_kyles_lambda(prices, volume, window=20):
#   -> np.ndarray float32
# ============================================================================


# ============================================================================
# À COLLER : _numba_kaufman_efficiency
# Source midas : quantitative_features.py, lignes 1125-1153
# Signature : def _numba_kaufman_efficiency(prices, window=20):
#   -> np.ndarray float32 (Efficiency Ratio)
# ============================================================================


# ============================================================================
# À COLLER : _numba_variance_ratio
# Source midas : quantitative_features.py, lignes 1155-1196
# Signature : def _numba_variance_ratio(returns, lags=20):
#   -> np.ndarray float32
# ============================================================================


# ============================================================================
# À COLLER : calculate_price_position_numba
# Source midas : quantitative_features.py, lignes 1290-1313
# Signature : def calculate_price_position_numba(prices, window=20):
#   -> np.ndarray float32 (position du prix dans sa fenêtre 0-1)
# ============================================================================


# ============================================================================
# À COLLER : calculate_market_regime_numba
# Source midas : quantitative_features.py, lignes 1354-1387
# Signature : def calculate_market_regime_numba(returns, volatility, window=50):
#   -> np.ndarray float32 (régime par volatilité : -1/0/+1)
# ============================================================================