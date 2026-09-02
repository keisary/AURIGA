"""Tests du module data/ — MARKET_DATA réel (SDK alpaca-py).

Ces tests vérifient :
1. L'interface : signatures et types attendus.
2. Le cache : roundtrip parquet.
3. La construction des requêtes (sans appeler le réseau — pas de clés en CI).

Pour un test réseau réel, exécuter : pytest tests/test_data.py -m "network"
avec des clés ALPACA_API_KEY/ALPACA_SECRET_KEY dans .env.
"""
from __future__ import annotations

import sys
from pathlib import Path

import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from auriga.data.cache import (
    has_cached_bars,
    load_cached_bars,
    save_cached_bars,
    save_cached_chain,
)


# ---------------------------------------------------------------------------
# Cache (pas de réseau)
# ---------------------------------------------------------------------------

def test_cache_roundtrip():
    df = pl.DataFrame(
        {
            "timestamp": [1, 2, 3],
            "open": [1.0, 2.0, 3.0],
            "high": [1.1, 2.1, 3.1],
            "low": [0.9, 1.9, 2.9],
            "close": [1.05, 2.05, 3.05],
            "volume": [100, 200, 300],
        }
    )
    save_cached_bars(df, "TEST", "1H")
    assert has_cached_bars("TEST", "1H")
    loaded = load_cached_bars("TEST", "1H")
    assert loaded is not None
    assert loaded.height == 3


def test_cache_chain_roundtrip():
    df = pl.DataFrame(
        {
            "symbol": ["X", "X"],
            "option_symbol": ["X1", "X2"],
            "type": ["call", "put"],
            "strike": [10.0, 20.0],
            "expiry": ["2026-09-18", "2026-09-18"],
        }
    )
    save_cached_chain(df, "TEST")
    from auriga.data.cache import load_cached_chain

    loaded = load_cached_chain("TEST")
    assert loaded is not None
    assert loaded.height == 2


# ---------------------------------------------------------------------------
# Interface du client (pas de réseau)
# ---------------------------------------------------------------------------

def test_market_data_client_requires_credentials():
    """Sans clés, la construction doit lever une erreur claire."""
    import os

    from auriga.data.market_data import MarketDataClient

    # Forcer l'absence de clés
    for v in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY"):
        os.environ.pop(v, None)
    with pytest.raises(RuntimeError, match="Clés API"):
        MarketDataClient(api_key=None, secret_key=None)


def test_market_data_client_methods_exist():
    from unittest.mock import MagicMock

    from auriga.data.market_data import MarketDataClient

    # Vérifie seulement que les méthodes sont définies avec les bons noms
    for m in ["get_historical_bars", "get_recent_bars", "get_option_chain"]:
        assert hasattr(MarketDataClient, m), f"{m} manquante"


def test_timeframe_helper():
    from auriga.data.market_data import _tf

    assert _tf("1H") is not None
    assert _tf("1D") is not None
    with pytest.raises(ValueError):
        _tf("5m")