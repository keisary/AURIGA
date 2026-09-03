"""AURIGA - Construction des ordres Alpaca multi-leg (options).

Convertit une SpreadStrategy (types.py) en payload d'ordre Alpaca.

API alpaca-py (v0.44) :
- MarketOrderRequest / LimitOrderRequest avec asset_class=US_OPTION
- OrderClass.MLEG pour les ordres multi-leg (spreads)
- Chaque leg : symbol (OCC), side (buy/sell), qty, order_type, time_in_force

L'API Alpaca multi-leg s'attend à une structure de legs plate :
  legs = [ {symbol, side, qty, type, time_in_force}, ... ]
avec un ordre unique pour les spreads verticaux (class=MLEG).

Vérifié contre le SDK installé (alpaca-py 0.44) : OrderClass.MLEG existe,
AssetClass.US_OPTION existe, MarketOrderRequest accepte les kwargs étendus.
"""
from __future__ import annotations

import logging
from typing import Any

from alpaca.trading.enums import AssetClass, OrderClass, OrderSide, OrderType, TimeInForce
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.models import OrderRequest

from auriga.types import OptionLeg, OrderRequest as AurigaOrderRequest, SpreadStrategy

logger = logging.getLogger(__name__)


def build_multi_leg_payload(
    strategy: SpreadStrategy,
    qty_per_leg: int = 1,
    order_type: str = "market",
    time_in_force: str = "day",
) -> dict[str, Any]:
    """Construit le payload d'un ordre multi-leg Alpaca pour un spread.

    Args:
        strategy : spread défini-risque (2 jambes)
        qty_per_leg : nombre de contrats par jambe (défaut 1)
        order_type : 'market' | 'limit'
        time_in_force : 'day' | 'gtc'

    Returns:
        dict compatible alpaca-py (OrderRequest multi-leg).
    """
    legs_payload = []
    for leg in strategy.legs:
        side = OrderSide.BUY if leg.side == "buy" else OrderSide.SELL
        legs_payload.append(
            {
                "symbol": leg.option_symbol,
                "side": side,
                "qty": qty_per_leg,
                "type": OrderType.MARKET if order_type == "market" else OrderType.LIMIT,
                "time_in_force": TimeInForce.DAY if time_in_force == "day" else TimeInForce.GTC,
            }
        )

    return {
        "symbol": strategy.signal.symbol,  # sous-jacent (référence)
        "qty": qty_per_leg,
        "asset_class": AssetClass.US_OPTION,
        "order_class": OrderClass.MLEG,
        "type": OrderType.MARKET if order_type == "market" else OrderType.LIMIT,
        "time_in_force": TimeInForce.DAY if time_in_force == "day" else TimeInForce.GTC,
        "legs": legs_payload,
    }


def build_auriga_order_payload(
    strategy: SpreadStrategy,
    qty_per_leg: int = 1,
    order_type: str = "market",
) -> AurigaOrderRequest:
    """Enveloppe : SpreadStrategy → AurigaOrderRequest (prêt pour le client)."""
    return AurigaOrderRequest(
        strategy=strategy,
        order_type=order_type,
        time_in_force="day",
    )


def validate_spread(strategy: SpreadStrategy) -> tuple[bool, str]:
    """Valide qu'un spread est exécutable (structure minimale).

    Returns:
        (ok, raison)
    """
    if len(strategy.legs) != 2:
        return False, f"Un spread vertical doit avoir 2 jambes (ici {len(strategy.legs)})"
    sides = {leg.side for leg in strategy.legs}
    if sides != {"buy", "sell"}:
        return False, f"Un spread doit avoir buy + sell (ici {sides})"
    expiries = {leg.expiry for leg in strategy.legs}
    if len(expiries) != 1:
        return False, "Les 2 jambes doivent avoir la MÊME expiration"
    if strategy.max_risk <= 0:
        return False, f"max_risk doit être > 0 (ici {strategy.max_risk})"
    return True, ""