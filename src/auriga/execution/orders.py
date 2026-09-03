"""AURIGA - Construction des ordres Alpaca multi-leg (options).

Convertit une SpreadStrategy (types.py) en ordre multi-leg Alpaca.

Format OFFICIEL (vérifié alpaca-py 0.44 + exemple officiel Alpaca) :
    MarketOrderRequest(
        qty=1,
        order_class=OrderClass.MLEG,
        time_in_force=TimeInForce.DAY,
        legs=[
            OptionLegRequest(symbol=<OCC>, side=OrderSide.SELL, ratio_qty=1),
            OptionLegRequest(symbol=<OCC>, side=OrderSide.BUY, ratio_qty=1),
        ]
    )

Règles validées par le SDK :
- Pas de symbol racine pour MLEG, pas d'asset_class
- qty (racine) REQUIS pour MLEG = nombre de spreads
- legs : 2 à 4, symboles UNIQUES, ratio_qty = quantité proportionnelle
- side : BUY/SELL (ou position_intent buy_to_open/sell_to_open)
"""
from __future__ import annotations

import logging

from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest, OptionLegRequest

from auriga.types import OrderRequest as AurigaOrderRequest
from auriga.types import SpreadStrategy

logger = logging.getLogger(__name__)


def build_multi_leg_order(
    strategy: SpreadStrategy,
    qty: int = 1,
) -> MarketOrderRequest:
    """Construit l'ordre multi-leg Alpaca pour un spread.

    Args:
        strategy : spread défini-risque (2 jambes buy/sell)
        qty : nombre de spreads (contrats par jambe)

    Returns:
        MarketOrderRequest prêt pour submit_order.
    """
    # Ordre des legs : SELL d'abord puis BUY (convention spread)
    legs = []
    for leg in strategy.legs:
        side = OrderSide.SELL if leg.side == "sell" else OrderSide.BUY
        legs.append(
            OptionLegRequest(
                symbol=leg.option_symbol,
                side=side,
                ratio_qty=qty,
            )
        )

    # Pour un bull call spread : buy lower strike, sell higher strike
    # L'ordre des legs n'a pas d'importance pour Alpaca (symboles uniques)
    req = MarketOrderRequest(
        qty=qty,
        order_class=OrderClass.MLEG,
        time_in_force=TimeInForce.DAY,
        legs=legs,
    )
    return req


def build_auriga_order_payload(
    strategy: SpreadStrategy,
    qty: int = 1,
) -> AurigaOrderRequest:
    """Enveloppe : SpreadStrategy → AurigaOrderRequest (prêt pour le client)."""
    return AurigaOrderRequest(strategy=strategy)


def validate_spread(strategy: SpreadStrategy) -> tuple[bool, str]:
    """Valide qu'un spread est exécutable (structure minimale)."""
    if len(strategy.legs) != 2:
        return False, f"Un spread vertical doit avoir 2 jambes (ici {len(strategy.legs)})"
    sides = {leg.side for leg in strategy.legs}
    if sides != {"buy", "sell"}:
        return False, f"Un spread doit avoir buy + sell (ici {sides})"
    expiries = {leg.expiry for leg in strategy.legs}
    if len(expiries) != 1:
        return False, "Les 2 jambes doivent avoir la MÊME expiration"
    symbols = {leg.option_symbol for leg in strategy.legs}
    if len(symbols) != 2:
        return False, "Les 2 jambes doivent avoir des symboles OCC DIFFÉRENTS"
    if strategy.max_risk <= 0:
        return False, f"max_risk doit être > 0 (ici {strategy.max_risk})"
    return True, ""
