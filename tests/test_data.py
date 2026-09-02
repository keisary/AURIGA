"""Tests du module data/ : mock, cache, MarketDataClient."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
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
from auriga.data.market_data import MarketDataClient
from auriga.data.mock_data import MockMarketDataClient


# ---------------------------------------------------------------------------
# Mock
# ---------------------------------------------------------------------------

def test_mock_bars_shape_and_columns():
    mock = MockMarketDataClient()
    df = mock.get_bars("AAPL", "1H")
    assert isinstance(df, pl.DataFrame)
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert df.height > 1000
    # Pas de NaN
    assert not df.null_count().sum_horizontal().to_list()[0] > 0


def test_mock_bars_no_nan():
    mock = MockMarketDataClient()
    df = mock.get_bars("AAPL", "1D")
    assert df["close"].is_null().sum() == 0
    assert df["volume"].is_null().sum() == 0
    # high >= low
    assert (df["high"] >= df["low"]).all()


def test_mock_reproducible():
    m1 = MockMarketDataClient(seed=42)
    m2 = MockMarketDataClient(seed=42)
    df1 = m1.get_bars("NVDA", "1D")
    df2 = m2.get_bars("NVDA", "1D")
    assert df1["close"].to_list() == df2["close"].to_list()


def test_mock_option_chain():
    mock = MockMarketDataClient()
    chain = mock.get_option_chain("AAPL")
    assert "option_symbol" in chain.columns
    assert "strike" in chain.columns
    assert "expiry" in chain.columns
    assert "call" in chain["type"].unique().to_list()
    assert "put" in chain["type"].unique().to_list()
    assert chain.height > 100


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def test_cache_roundtrip(tmp_path):
    mock = MockMarketDataClient()
    df = mock.get_bars("AAPL", "1H").head(100)
    save_cached_bars(df, "AAPL", "1H")
    assert has_cached_bars("AAPL", "1H")
    loaded = load_cached_bars("AAPL", "1H")
    assert loaded is not None
    assert loaded.height == 100


def test_cache_chain_roundtrip(tmp_path):
    mock = MockMarketDataClient()
    chain = mock.get_option_chain("MSFT")
    save_cached_chain(chain, "MSFT")
    from auriga.data.cache import load_cached_chain

    loaded = load_cached_chain("MSFT")
    assert loaded is not None
    assert loaded.height == chain.height


# ---------------------------------------------------------------------------
# MarketDataClient (sélection auto mock / réel)
# ---------------------------------------------------------------------------

def test_client_selects_mock_without_creds():
    # Sans clés, le client doit être en mock même si mock_api=False (fallback)
    client = MarketDataClient(use_mock=True)
    assert client.is_mock
    df = client.get_bars("AAPL", "1H")
    assert df.height > 100
    spot = client.get_spot_price("AAPL")
    assert spot > 0