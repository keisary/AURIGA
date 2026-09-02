"""AURIGA - Client de données de marché Alpaca (réel).

Utilise le SDK officiel alpaca-py quand les clés API sont disponibles,
sinon fallback sur MockMarketDataClient (mode dev/hackathon sans crédits).

Clés via variables d'environnement (ALPACA_API_KEY / ALPACA_SECRET_KEY),
chargées par src/auriga/utils/config.py. JAMAIS en dur dans le code.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import polars as pl

from auriga.utils.config import get_config

try:  # import protégé : le SDK peut ne pas être installé
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

    ALPACA_SDK_AVAILABLE = True
except ImportError:  # pragma: no cover
    ALPACA_SDK_AVAILABLE = False
    StockHistoricalDataClient = None  # type: ignore
    StockBarsRequest = None  # type: ignore
    TimeFrame = None  # type: ignore
    TimeFrameUnit = None  # type: ignore

from auriga.data.mock_data import MockMarketDataClient


class MarketDataClient:
    """Client de données : bars 1H/1D + chaînes d'options Alpaca.

    Sélection automatique :
    - réelles si clés API présentes ET mode non-mock ;
    - mock sinon.
    """

    def __init__(self, use_mock: bool | None = None):
        cfg = get_config()
        if use_mock is None:
            use_mock = cfg.orchestration.get("mock_api", True) or not cfg.has_alpaca_credentials
        self.use_mock = use_mock
        self._mock = MockMarketDataClient()
        self._client: StockHistoricalDataClient | None = None

        if not use_mock and ALPACA_SDK_AVAILABLE and cfg.has_alpaca_credentials:
            self._client = StockHistoricalDataClient(
                cfg.alpaca_api_key, cfg.alpaca_secret_key
            )

    # ------------------------------------------------------------------
    @property
    def is_mock(self) -> bool:
        return self.use_mock or self._client is None

    # ------------------------------------------------------------------
    def get_bars(
        self,
        symbol: str,
        timeframe: str = "1H",
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pl.DataFrame:
        """Retourne les bars [timestamp, open, high, low, close, volume]."""
        if self.is_mock:
            return self._mock.get_bars(symbol, timeframe, start, end)

        # --- Réel ---
        if start is None:
            start = datetime.now(timezone.utc) - timedelta(days=5 * 365)
        if end is None:
            end = datetime.now(timezone.utc)

        tf = (
            TimeFrame(1, TimeFrameUnit.Hour)
            if timeframe == "1H"
            else TimeFrame(1, TimeFrameUnit.Day)
        )
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=tf,
            start=start,
            end=end,
            adjustment="all",  # splits/dividendes ajustés
        )
        bars = self._client.get_stock_bars(req)
        df = bars.df.reset_index()
        return pl.from_pandas(df)

    # ------------------------------------------------------------------
    def get_option_chain(
        self,
        symbol: str,
        expiry_start: datetime | None = None,
        expiry_end: datetime | None = None,
    ) -> pl.DataFrame:
        """Chaîne d'options (calls/puts, strikes, expirations).

        Note : les données d'options historiques ne sont pas disponibles
        gratuitement — ceci renvoie la chaîne MOCK par défaut (le backtest
        des spreads utilise le pricing Black-Scholes, pas des prix historiques).
        """
        return self._mock.get_option_chain(symbol, expiry_start, expiry_end)

    # ------------------------------------------------------------------
    def get_spot_price(self, symbol: str) -> float:
        bars = self.get_bars(symbol, "1D")
        return float(bars["close"][-1])


def make_data_client(use_mock: bool | None = None) -> MarketDataClient:
    """Factory : retourne le bon client selon la config."""
    return MarketDataClient(use_mock=use_mock)