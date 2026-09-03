"""AURIGA - Cache local des données de marché.

Persistance des bars et chaînes d'options en Parquet (rapide, compressé)
dans data/raw/ (brutes) et data/options/ (chaînes).

Structure des fichiers :
- data/raw/<symbol>_<TF>.parquet
- data/options/<symbol>_chain.parquet
"""
from __future__ import annotations

from pathlib import Path

import polars as pl

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
RAW_DIR = DATA_DIR / "raw"
OPTIONS_DIR = DATA_DIR / "options"


def _ensure_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OPTIONS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Bars
# ---------------------------------------------------------------------------

def bars_cache_path(symbol: str, timeframe: str) -> Path:
    return RAW_DIR / f"{symbol}_{timeframe}.parquet"


def load_cached_bars(symbol: str, timeframe: str) -> pl.DataFrame | None:
    """Charge les bars en cache, ou None si absents."""
    p = bars_cache_path(symbol, timeframe)
    if not p.exists():
        return None
    try:
        return pl.read_parquet(p)
    except Exception:
        return None


def save_cached_bars(df: pl.DataFrame, symbol: str, timeframe: str) -> Path:
    """Sauvegarde les bars en cache (overwrite). Retourne le chemin."""
    _ensure_dirs()
    p = bars_cache_path(symbol, timeframe)
    df.write_parquet(p)
    return p


def has_cached_bars(symbol: str, timeframe: str) -> bool:
    return bars_cache_path(symbol, timeframe).exists()


# ---------------------------------------------------------------------------
# Chaînes d'options
# ---------------------------------------------------------------------------

def chain_cache_path(symbol: str) -> Path:
    return OPTIONS_DIR / f"{symbol}_chain.parquet"


def load_cached_chain(symbol: str) -> pl.DataFrame | None:
    p = chain_cache_path(symbol)
    if not p.exists():
        return None
    try:
        return pl.read_parquet(p)
    except Exception:
        return None


def save_cached_chain(df: pl.DataFrame, symbol: str) -> Path:
    _ensure_dirs()
    p = chain_cache_path(symbol)
    df.write_parquet(p)
    return p


def has_cached_chain(symbol: str) -> bool:
    return chain_cache_path(symbol).exists()
