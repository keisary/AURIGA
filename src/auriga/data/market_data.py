"""AURIGA - Récupération de données de marché Alpaca (définitif).

Deux usages, une seule interface :
1. HISTORIQUE : bars 1H/1D depuis 2021 pour l'entraînement/backtest.
2. INFÉRENCE : les dernières barres au moment présent (pour décider de trader).

Utilise le SDK officiel alpaca-py. Clés via variables d'environnement
(ALPACA_API_KEY / ALPACA_SECRET_KEY) — jamais en dur dans le code.

API:
    data_client = get_market_data_client()
    df = data_client.get_historical_bars("AAPL", "1H", start=..., end=...)
    df = data_client.get_recent_bars("AAPL", "1H", n=300)
    chain = data_client.get_option_chain("AAPL", min_dte=14, max_dte=42)

Toutes les fonctions retournent des polars.DataFrame avec la colonne
`timestamp` en datetime UTC.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import polars as pl
from alpaca.data.enums import DataFeed
from alpaca.data.historical import OptionHistoricalDataClient, StockHistoricalDataClient
from alpaca.data.requests import (
    OptionChainRequest,
    StockBarsRequest,
)
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from auriga.data.cache import (
    has_cached_bars,
    load_cached_bars,
    save_cached_bars,
    save_cached_chain,
)
from auriga.utils.config import get_config

logger = logging.getLogger(__name__)

BAR_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


def _tf(tf: str) -> TimeFrame:
    if tf == "1H":
        return TimeFrame(1, TimeFrameUnit.Hour)
    if tf == "1D":
        return TimeFrame(1, TimeFrameUnit.Day)
    raise ValueError(f"timeframe non supporté: {tf}")


class MarketDataClient:
    """Client unique pour les données de marché Alpaca (stock + options)."""

    def __init__(self, api_key: str | None = None, secret_key: str | None = None, feed: str | None = None):
        cfg = get_config()
        self.api_key = api_key or cfg.alpaca_api_key
        self.secret_key = secret_key or cfg.alpaca_secret_key
        if not self.api_key or not self.secret_key:
            raise RuntimeError(
                "Clés API Alpaca manquantes. Renseignez ALPACA_API_KEY et "
                "ALPACA_SECRET_KEY dans .env (paper trading)."
            )
        self.feed = feed or cfg.raw.get("data", {}).get("feed", "iex")
        self._stock_client = StockHistoricalDataClient(self.api_key, self.secret_key)
        self._option_client = OptionHistoricalDataClient(self.api_key, self.secret_key)
        logger.info(
            "MarketDataClient initialisé (feed=%s, options=%s)",
            self.feed, "réel",
        )

    # ------------------------------------------------------------------
    # Bars (historique)
    # ------------------------------------------------------------------
    def get_historical_bars(
        self,
        symbol: str,
        timeframe: str = "1H",
        start: datetime | None = None,
        end: datetime | None = None,
        use_cache: bool = True,
    ) -> pl.DataFrame:
        """Bars historiques complètes (défaut : 5 ans jusqu'à aujourd'hui).

        Avec cache parquet : le 2e appel est instantané.
        """
        if start is None:
            years = get_config().research.get("history_years", 5)
            start = datetime.now(timezone.utc) - timedelta(days=365 * years)
        if end is None:
            end = datetime.now(timezone.utc)

        if use_cache and has_cached_bars(symbol, timeframe):
            cached = load_cached_bars(symbol, timeframe)
            if cached is not None and cached.height > 0:
                return cached

        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=_tf(timeframe),
            start=start,
            end=end,
            adjustment="all",
            feed=self.feed,
        )
        bars = self._stock_client.get_stock_bars(req)
        if bars.df.empty:
            logger.warning("Aucune barre pour %s %s [%s, %s]", symbol, timeframe, start, end)
            return pl.DataFrame(schema={c: pl.Float64 for c in BAR_COLUMNS[1:]})
        df = self._to_pl(bars.df.reset_index())

        if use_cache:
            save_cached_bars(df, symbol, timeframe)
        return df

    # ------------------------------------------------------------------
    # Bars (inférence temps réel)
    # ------------------------------------------------------------------
    def get_recent_bars(self, symbol: str, timeframe: str = "1H", n: int = 500) -> pl.DataFrame:
        """Les n dernières barres (pour évaluer les signaux à l'instant T)."""
        end = datetime.now(timezone.utc)
        if timeframe == "1H":
            start = end - timedelta(hours=n * 2)  # marge pour les jours sans trading
        else:
            start = end - timedelta(days=n * 2)
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=_tf(timeframe),
            start=start,
            end=end,
            adjustment="all",
            feed=self.feed,
        )
        bars = self._stock_client.get_stock_bars(req)
        if bars.df.empty:
            return pl.DataFrame(schema={c: pl.Float64 for c in BAR_COLUMNS[1:]})
        df = self._to_pl(bars.df.reset_index())
        return df.tail(n)

    # ------------------------------------------------------------------
    # Chaîne d'options
    # ------------------------------------------------------------------
    def get_option_chain(
        self,
        symbol: str,
        min_dte: int | None = None,
        max_dte: int | None = None,
        use_cache: bool = True,
    ) -> pl.DataFrame:
        """Chaîne d'options complète (calls + puts, toutes expirations).

        Retourne les colonnes : symbol, option_symbol, type, strike, expiry,
        bid, ask, last, open_interest, volume, implied_vol (si dispo).
        """
        cfg_opts = get_config().options
        min_dte = min_dte or cfg_opts.get("min_dte", 14)
        max_dte = max_dte or cfg_opts.get("max_dte", 42)

        from auriga.data.cache import has_cached_chain, load_cached_chain

        if use_cache and has_cached_chain(symbol):
            cached = load_cached_chain(symbol)
            if cached is not None and cached.height > 0:
                return cached

        # 1. Chaîne de contrats d'options pour le symbole (OptionChainRequest)
        today = datetime.now(timezone.utc).date()
        chain_req = OptionChainRequest(
            underlying_symbol=symbol,
            expiration_date_gte=(today + timedelta(days=min_dte)).isoformat(),
            expiration_date_lte=(today + timedelta(days=max_dte)).isoformat(),
        )
        contracts = self._option_client.get_option_chain(chain_req)
        if not contracts:
            logger.warning("Aucune chaîne d'options pour %s [%dd-%dd]", symbol, min_dte, max_dte)
            return pl.DataFrame()

        # contracts est un dict {option_symbol: snapshot}
        rows: list[dict[str, Any]] = []
        for occ, snap in contracts.items():
            rows.append(
                {
                    "symbol": symbol,
                    "option_symbol": occ,
                    "type": "call" if "C" in occ.split(symbol)[1][:1] and "P" not in occ.split(symbol)[1][:1] else "put",
                    "strike": float(getattr(snap, "underlying_asset", None).strike_price)
                    if getattr(snap, "underlying_asset", None) is not None
                    else 0.0,
                    "expiry": str(getattr(snap, "underlying_asset", None).expiration_date)
                    if getattr(snap, "underlying_asset", None) is not None
                    else "",
                    "multiplier": int(getattr(getattr(snap, "underlying_asset", None), "multiplier", 100)),
                    "bid": float(getattr(getattr(snap, "latest_quote", None), "bid_price", 0.0) or 0.0),
                    "ask": float(getattr(getattr(snap, "latest_quote", None), "ask_price", 0.0) or 0.0),
                    "last": float(getattr(getattr(snap, "latest_trade", None), "price", 0.0) or 0.0),
                    "open_interest": int(getattr(snap, "open_interest", 0) or 0),
                    "volume": int(getattr(snap, "volume", 0) or 0),
                    "implied_vol": float(getattr(snap, "implied_volatility", 0.0) or 0.0),
                }
            )

        df = pl.DataFrame(rows)
        if use_cache and df.height > 0:
            save_cached_chain(df, symbol)
        return df

    # ------------------------------------------------------------------
    def _to_pl(self, df: Any) -> pl.DataFrame:
        """Convertit le DataFrame alpaca-py (pandas multi-index) en polars."""
        # df a un index (timestamp, symbol) après reset_index
        df = df.rename(columns={"index": "timestamp"}) if "index" in df.columns else df
        if "timestamp" not in df.columns and "t" in df.columns:
            df = df.rename(columns={"t": "timestamp"})
        out = pl.from_pandas(df)
        if "symbol" in out.columns:
            out = out.drop("symbol")
        out = out.rename({c: c.lower() for c in out.columns if c.lower() in {"open", "high", "low", "close", "volume"}})
        if "timestamp" not in out.columns:
            raise ValueError(f"Colonne timestamp absente: {out.columns}")
        return out.select(
            [c for c in BAR_COLUMNS if c in out.columns]
        )


# ---------------------------------------------------------------------------
# Factory / helpers
# ---------------------------------------------------------------------------

_client: MarketDataClient | None = None


def get_market_data_client() -> MarketDataClient:
    """Singleton du client de données."""
    global _client
    if _client is None:
        _client = MarketDataClient()
    return _client


def download_universe(
    symbols: list[str], timeframe: str = "1H", use_cache: bool = True
) -> dict[str, pl.DataFrame]:
    """Télécharge les bars pour tout l'univers. Retourne {symbol: DataFrame}."""
    client = get_market_data_client()
    out: dict[str, pl.DataFrame] = {}
    for sym in symbols:
        try:
            out[sym] = client.get_historical_bars(sym, timeframe, use_cache=use_cache)
            logger.info("  %s: %d barres", sym, out[sym].height)
        except Exception as e:
            logger.error("  %s: échec (%s)", sym, e)
    return out


def download_option_chains(symbols: list[str]) -> dict[str, pl.DataFrame]:
    """Télécharge les chaînes d'options pour tout l'univers."""
    client = get_market_data_client()
    out: dict[str, pl.DataFrame] = {}
    for sym in symbols:
        try:
            out[sym] = client.get_option_chain(sym)
            logger.info("  %s: %d contrats", sym, out[sym].height)
        except Exception as e:
            logger.error("  %s: échec (%s)", sym, e)
    return out