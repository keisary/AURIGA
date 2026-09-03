"""AURIGA - Client d'exécution Alpaca (paper trading).

Utilise le SDK officiel alpaca-py (TradingClient). Clés depuis .env
(ALPACA_API_KEY / ALPACA_SECRET_KEY). Paper par défaut.

Responsabilités :
- get_account() → état du compte (equity, cash, buying power)
- get_positions() → positions ouvertes
- submit_spread(strategy, qty) → ordre multi-leg
- submit_auriga_order(order) → ordre depuis OrderRequest
- close_position(symbol) / cancel_order / get_orders
- retry/backoff sur les erreurs transitoires (429, 5xx)
"""
from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

from auriga.types import (
    OrderResult,
    PortfolioState,
    PositionState,
    SpreadStrategy,
)
from auriga.utils.config import get_config

logger = logging.getLogger(__name__)


class ExecutionClient:
    """Client d'exécution Alpaca paper (stocks + options multi-leg)."""

    def __init__(self, api_key: str | None = None, secret_key: str | None = None):
        cfg = get_config()
        self.api_key = api_key or cfg.alpaca_api_key
        self.secret_key = secret_key or cfg.alpaca_secret_key
        if not self.api_key or not self.secret_key:
            raise RuntimeError(
                "Clés API Alpaca manquantes. Renseignez ALPACA_API_KEY et "
                "ALPACA_SECRET_KEY dans .env."
            )
        self.paper = cfg.alpaca_paper
        try:
            from alpaca.trading.client import TradingClient

            self._client = TradingClient(
                self.api_key, self.secret_key, paper=self.paper
            )
            logger.info("ExecutionClient initialisé (paper=%s)", self.paper)
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(f"alpaca-py non installé: {e}")

    # ------------------------------------------------------------------
    def _with_retry(self, fn, *args, retries: int = 3, **kwargs):
        """Exécute fn avec retry/backoff sur erreurs transitoires."""
        for attempt in range(retries):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                is_transient = (
                    "429" in str(e) or "500" in str(e) or "502" in str(e)
                    or "503" in str(e) or "504" in str(e)
                    or "timeout" in str(e).lower() or "rate" in str(e).lower()
                )
                if not is_transient or attempt == retries - 1:
                    raise
                wait = 2 ** attempt  # 1s, 2s, 4s
                logger.warning("Erreur transitoire (%s), retry %d dans %ds",
                               str(e)[:80], attempt + 1, wait)
                time.sleep(wait)
        raise RuntimeError("Unreachable")  # pragma: no cover

    # ------------------------------------------------------------------
    def get_account(self) -> PortfolioState:
        """État du compte paper."""
        acc = self._with_retry(self._client.get_account)
        positions = self.get_positions()
        return PortfolioState(
            equity=float(acc.equity or 0),
            cash=float(acc.cash or 0),
            buying_power=float(acc.buying_power or 0),
            positions=positions,
            day_pnl=float(getattr(acc, "equity", 0) or 0) - float(getattr(acc, "last_equity", 0) or 0),
            total_pnl=float(getattr(acc, "equity", 0) or 0) - 100_000.0,  # capital initial hackathon
        )

    def get_positions(self) -> list[PositionState]:
        """Positions ouvertes."""
        try:
            positions = self._with_retry(self._client.get_all_positions)
        except Exception:
            return []
        out: list[PositionState] = []
        for p in positions:
            out.append(
                PositionState(
                    symbol=str(getattr(p, "symbol", "")),
                    strategy_name=str(getattr(p, "asset_class", "")),
                    einher_id="",
                    qty=int(getattr(p, "qty", 0) or 0),
                    entry_price=float(getattr(p, "avg_entry_price", 0) or 0),
                    max_risk=0.0,
                    opened_at="",
                    current_value=float(getattr(p, "market_value", 0) or 0),
                )
            )
        return out

    def get_buying_power(self) -> float:
        acc = self._with_retry(self._client.get_account)
        return float(getattr(acc, "buying_power", 0) or 0)

    # ------------------------------------------------------------------
    def submit_spread(
        self,
        strategy: SpreadStrategy,
        qty: int = 1,
        order_type: str = "market",
    ) -> OrderResult:
        """Soumet un spread multi-leg en ordre unique (atomic).

        Format officiel Alpaca (vérifié alpaca-py 0.44) : MarketOrderRequest
        avec order_class=MLEG + legs=[OptionLegRequest(...)].
        """
        from auriga.execution.orders import build_multi_leg_order, validate_spread

        ok, reason = validate_spread(strategy)
        if not ok:
            return OrderResult(
                order_id="", status="rejected", submitted_at=_now(),
                message=reason,
            )

        try:
            req = build_multi_leg_order(strategy, qty=qty)
            order = self._with_retry(self._client.submit_order, req)
            return OrderResult(
                order_id=str(getattr(order, "id", "")),
                status=str(getattr(order, "status", "submitted")).lower(),
                submitted_at=_now(),
                message=f"Ordre {getattr(order, 'id', '')} soumis (class=MLEG)",
            )
        except Exception as e:
            logger.error("Échec soumission spread %s: %s", strategy.name, e)
            return OrderResult(
                order_id="", status="error", submitted_at=_now(),
                message=str(e),
            )

    # ------------------------------------------------------------------
    def close_position(self, symbol: str) -> OrderResult:
        """Ferme une position (par symbole)."""
        try:
            self._with_retry(self._client.close_position, symbol)
            return OrderResult(
                order_id="", status="accepted", submitted_at=_now(),
                message=f"Position {symbol} fermée",
            )
        except Exception as e:
            return OrderResult(
                order_id="", status="error", submitted_at=_now(), message=str(e),
            )

    def cancel_order(self, order_id: str) -> OrderResult:
        try:
            self._with_retry(self._client.cancel_order_by_id, order_id)
            return OrderResult(order_id=order_id, status="cancelled", submitted_at=_now())
        except Exception as e:
            return OrderResult(order_id=order_id, status="error", submitted_at=_now(), message=str(e))


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


_client: ExecutionClient | None = None


def get_execution_client() -> ExecutionClient:
    """Singleton du client d'exécution."""
    global _client
    if _client is None:
        _client = ExecutionClient()
    return _client
