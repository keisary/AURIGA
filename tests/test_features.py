"""Tests du module features/ — vérifie que les fonctions collées depuis midas
sont cohérentes avec le registre et que l'engine produit le DataFrame attendu.

NOTE : ces tests sont valides UNE FOIS que les fonctions _numba_* ont été
collées depuis midasV3. Avant cela, ils vérifient que le système dégrade
proprement.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from auriga.features.engine import FEATURE_NAMES, compute_features


def _ohlcv(n: int = 3000, seed: int = 0) -> pl.DataFrame:
    """Données OHLCV synthétiques déterministes (sans mock)."""
    rng = np.random.default_rng(seed)
    close = np.cumsum(rng.normal(0.0002, 0.01, n)) + 100.0
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.003, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.003, n)))
    volume = rng.integers(1_000_000, 30_000_000, n)
    return pl.DataFrame(
        {
            "timestamp": list(range(n)),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def test_engine_produces_all_columns():
    """Le DataFrame de sortie doit contenir toutes les colonnes du registre."""

    ohlcv = _ohlcv(3000)
    df = compute_features(ohlcv, "1H")
    assert df.height == ohlcv.height
    assert "timestamp" in df.columns
    for name in FEATURE_NAMES:
        assert name in df.columns, f"colonne {name} manquante"


def test_engine_no_inf():
    """Aucune valeur infinie dans les features."""

    ohlcv = _ohlcv(2000)
    df = compute_features(ohlcv, "1H")
    for name in FEATURE_NAMES:
        arr = df[name].to_numpy()
        assert not np.isinf(arr).any(), f"inf dans {name}"


def test_engine_same_rows_as_input():

    ohlcv = _ohlcv(500)
    df = compute_features(ohlcv, "1H")
    assert df.height == ohlcv.height


def test_engine_timeframe_1d():

    ohlcv = _ohlcv(800)
    df = compute_features(ohlcv, "1D")
    assert df.height == ohlcv.height
    assert len(df.columns) == len(FEATURE_NAMES) + 1  # + timestamp
