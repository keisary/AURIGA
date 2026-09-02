"""AURIGA - MockMarketDataClient : données de marché simulées.

Génère des séries réalistes (mouvement brownien géométrique avec régime de
volatilité) pour permettre le développement et les tests SANS clés API Alpaca.

Interface identique à MarketDataClient (même module data/market_data.py).
Reproductible : même seed -> mêmes données.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import polars as pl


class MockMarketDataClient:
    """Client mock : bars historiques et chaînes d'options simulées."""

    def __init__(self, seed: int = 42, base_prices: dict[str, float] | None = None):
        self.seed = seed
        # Prix de départ réalistes par symbole (approx 2021)
        self.base_prices = base_prices or {
            "AAPL": 130.0, "MSFT": 230.0, "NVDA": 55.0, "AMZN": 3200.0,
            "GOOGL": 1800.0, "META": 270.0, "TSLA": 700.0, "AMD": 90.0,
            "AVGO": 450.0, "JPM": 127.0, "V": 210.0, "MA": 340.0,
            "XOM": 45.0, "CVX": 85.0, "CAT": 180.0, "GE": 100.0,
            "WMT": 140.0, "COST": 370.0, "KO": 50.0, "PEP": 145.0,
            "JNJ": 160.0, "UNH": 350.0, "SPY": 370.0, "QQQ": 310.0,
            "IWM": 215.0,
        }

    # ------------------------------------------------------------------
    def _rng(self, symbol: str) -> np.random.Generator:
        """Générateur déterministe par symbole (seed fixe + hash symbol)."""
        h = abs(hash(symbol)) % (2**32)
        return np.random.default_rng(self.seed + h)

    def get_bars(
        self,
        symbol: str,
        timeframe: str = "1H",
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pl.DataFrame:
        """Bars simulés : colonnes [timestamp, open, high, low, close, volume].

        timeframes supportés : '1H', '1D'.
        """
        if start is None:
            start = datetime(2021, 1, 1, tzinfo=timezone.utc)
        if end is None:
            end = datetime.now(timezone.utc)

        step = timedelta(hours=1) if timeframe == "1H" else timedelta(days=1)
        n = max(2, int((end - start) / step))
        if n > 200_000:  # garde-fou : limiter la taille du mock
            n = 200_000

        rng = self._rng(symbol)
        base = self.base_prices.get(symbol, 100.0)

        # Régimes de volatilité: alternance low/high vol
        vol_base = 0.0004 if timeframe == "1H" else 0.015
        regime = np.where(np.arange(n) % 200 < 140, 1.0, 2.5)
        sigma = vol_base * regime

        # GBM avec dérive légère
        mu = 0.00002 if timeframe == "1H" else 0.0004
        rets = rng.normal(mu, sigma, n)
        close = base * np.exp(np.cumsum(rets))

        open_ = close * (1 + rng.normal(0, sigma / 4, n))
        high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, sigma / 2, n)))
        low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, sigma / 2, n)))
        volume = rng.integers(1_000_000, 50_000_000, n).astype(np.int64)

        timestamps = [start + i * step for i in range(n)]

        return pl.DataFrame(
            {
                "timestamp": timestamps,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        )

    # ------------------------------------------------------------------
    def get_option_chain(
        self,
        symbol: str,
        expiry_start: datetime | None = None,
        expiry_end: datetime | None = None,
        n_strikes: int = 20,
    ) -> pl.DataFrame:
        """Chaîne d'options simulée autour du prix spot.

        Colonnes: [option_symbol, type, strike, expiry, bid, ask, last,
                   open_interest, volume, implied_vol].
        """
        if expiry_start is None:
            expiry_start = datetime.now(timezone.utc) + timedelta(days=14)
        if expiry_end is None:
            expiry_end = datetime.now(timezone.utc) + timedelta(days=42)

        rng = self._rng(symbol + "_opt")
        spot = self.base_prices.get(symbol, 100.0)

        # Strikes autour du spot: +/- 15%
        lo, hi = spot * 0.85, spot * 1.15
        strikes = np.linspace(lo, hi, n_strikes).round(2)

        # Expirations hebdomadaires entre start et end
        expiries = []
        d = expiry_start
        while d <= expiry_end:
            # Vendredi ou samedi proche pour réalisme
            expiries.append(d.date().isoformat())
            d += timedelta(days=7)

        rows = []
        for exp in expiries:
            for strike in strikes:
                for otype in ("call", "put"):
                    itm = strike < spot if otype == "call" else strike > spot
                    intrinsic = max(0.0, (spot - strike) if otype == "put" else (strike - spot))
                    # Prix: intrinsèque + valeur temps (bruit)
                    prem = intrinsic + abs(rng.normal(spot * 0.02, spot * 0.01))
                    oi = int(rng.integers(50, 5000))
                    rows.append(
                        {
                            "symbol": symbol,
                            "option_symbol": f"{symbol}{exp.replace('-', '')}{otype.upper()[0]}{int(strike * 1000):08d}",
                            "type": otype,
                            "strike": strike,
                            "expiry": exp,
                            "bid": round(max(0.01, prem - spot * 0.005), 2),
                            "ask": round(prem + spot * 0.005, 2),
                            "last": round(prem, 2),
                            "open_interest": oi,
                            "volume": int(rng.integers(0, oi)),
                            "implied_vol": round(float(rng.normal(0.35, 0.08)), 4),
                        }
                    )
        return pl.DataFrame(rows)

    def get_spot_price(self, symbol: str) -> float:
        """Dernier prix simulé."""
        bars = self.get_bars(symbol, "1D")
        return float(bars["close"][-1])