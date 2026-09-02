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


# ============================================================================
# À COLLER : _numba_ema_vectorized
# Source midas : technical_indicators.py, lignes 67-95
# Signature : def _numba_ema_vectorized(prices, periods_array):
#   -> np.ndarray shape (len(periods_array), len(prices)), float32
# ============================================================================


# ============================================================================
# À COLLER : _numba_sma_vectorized
# Source midas : technical_indicators.py, lignes 97-119
# Signature : def _numba_sma_vectorized(prices, periods_array):
#   -> np.ndarray shape (len(periods_array), len(prices)), float32
# ============================================================================


# ============================================================================
# À COLLER : _numba_rsi_vectorized
# Source midas : technical_indicators.py, lignes 121-165
# Signature : def _numba_rsi_vectorized(prices, periods_array):
#   -> np.ndarray shape (len(periods_array), len(prices)), float32
# ============================================================================


# ============================================================================
# À COLLER : _numba_macd_complete
# Source midas : technical_indicators.py, lignes 167-217
# Signature : def _numba_macd_complete(prices, fast=12, slow=26, signal=9):
#   -> (macd_line, signal_line, histogram), 3x np.ndarray float32
# ============================================================================


# ============================================================================
# À COLLER : _numba_bollinger_bands
# Source midas : technical_indicators.py, lignes 219-237
# Signature : def _numba_bollinger_bands(prices, period=20, std_dev=2.0):
#   -> (upper, middle, lower), 3x np.ndarray float32
# ============================================================================


# ============================================================================
# À COLLER : _numba_atr
# Source midas : technical_indicators.py, lignes 239-262
# Signature : def _numba_atr(high, low, close, period=14):
#   -> np.ndarray float32
# ============================================================================


# ============================================================================
# À COLLER : _numba_momentum
# Source midas : technical_indicators.py, lignes 328-338
# Signature : def _numba_momentum(prices, period=10):
#   -> np.ndarray float32
# ============================================================================


# ============================================================================
# À COLLER : _numba_roc
# Source midas : technical_indicators.py, lignes 340-353
# Signature : def _numba_roc(prices, period=12):
#   -> np.ndarray float32
# ============================================================================


# ============================================================================
# À COLLER : _numba_vwap
# Source midas : technical_indicators.py, lignes 355-373
# Signature : def _numba_vwap(prices, volumes):
#   -> np.ndarray float32
# ============================================================================


# ============================================================================
# À COLLER : _numba_adx_complete
# Source midas : technical_indicators.py, lignes 576-667
# Signature : def _numba_adx_complete(high, low, close, period=14):
#   -> np.ndarray float32 (ADX)
# ============================================================================


# ============================================================================
# À COLLER : _numba_obv
# Source midas : technical_indicators.py, lignes 669-686
# Signature : def _numba_obv(prices, volumes):
#   -> np.ndarray float32
# ============================================================================


# ============================================================================
# À COLLER : _numba_mfi
# Source midas : technical_indicators.py, lignes 765-792
# Signature : def _numba_mfi(high, low, close, volume, period=14):
#   -> np.ndarray float32
# ============================================================================


# ============================================================================
# À COLLER : _numba_aroon
# Source midas : technical_indicators.py, lignes 813-831
# Signature : def _numba_aroon(high, low, period=14):
#   -> (aroon_up, aroon_down), 2x np.ndarray float32
# ============================================================================


# ============================================================================
# À COLLER : _numba_choppiness_index
# Source midas : technical_indicators.py, lignes 911-938
# Signature : def _numba_choppiness_index(high, low, close, period=14):
#   -> np.ndarray float32
# ============================================================================


# ============================================================================
# À COLLER : _numba_vortex
# Source midas : technical_indicators.py, lignes 940-980
# Signature : def _numba_vortex(high, low, close, period=14):
#   -> (vortex_pos, vortex_neg), 2x np.ndarray float32
# ============================================================================