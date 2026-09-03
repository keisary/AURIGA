"""AURIGA - Construction de credit spreads de VENTE de prime (Agent A3).

Contrairement à build_spread (qui suit un signal directionnel LONG/SHORT),
ici on construit des credit spreads de VENTE systématique :
- PUT credit spread : vendre put OTM (strike < spot), acheter put plus bas
  (protège contre la baisse). Profite du theta si le spot reste stable/hausse.
- CALL credit spread : vendre call OTM (strike > spot), acheter call plus haut
  (protège contre la hausse). Profite si le spot reste stable/baisse.

Ces spreads sont vendus quand le régime est calme (ni vol_danger, ni
AVOID_SELL) — voir prime_seller.py.
"""
from __future__ import annotations

import logging

import polars as pl

from auriga.types import OptionLeg, SpreadStrategy

logger = logging.getLogger(__name__)


def _row_to_leg(row: dict, side: str) -> OptionLeg:
    return OptionLeg(
        symbol=str(row["symbol"]),
        option_symbol=str(row["option_symbol"]),
        side=side,
        option_type=str(row["type"]),
        strike=float(row["strike"]),
        expiry=str(row["expiry"]),
        qty=1,
    )


def build_put_credit_spread(
    symbol: str,
    spot: float,
    chain: pl.DataFrame,
    spread_pct: float = 0.05,
    otm_pct: float = 0.03,  # le put vendu est ~3% SOUS le spot
) -> SpreadStrategy | None:
    """Put credit spread : vendre put OTM, acheter put plus bas (même expiry).

    - Jambe vendue : put avec strike ~ spot × (1 − otm_pct)
    - Jambe achetée : put avec strike ~ spot × (1 − otm_pct − spread_pct)
    """
    opts = chain.filter(pl.col("type") == "put").filter(pl.col("strike") > 0)

    sell_target = spot * (1 - otm_pct)
    buy_target = spot * (1 - otm_pct - spread_pct)

    sell_pool = opts.filter(pl.col("strike") <= sell_target).sort("strike", descending=True)
    buy_pool = opts.filter(pl.col("strike") <= buy_target).sort("strike", descending=True)

    if len(sell_pool) == 0 or len(buy_pool) == 0:
        return None

    sell_row = sell_pool.head(1)
    buy_row = buy_pool.head(1)

    # Même expiration (celle du put vendu)
    sell_leg = _row_to_leg(sell_row.row(0, named=True), "sell")
    buy_leg = _row_to_leg(buy_row.row(0, named=True), "buy")

    width = abs(sell_leg.strike - buy_leg.strike)
    mid_sell = (float(sell_row["bid"][0]) + float(sell_row["ask"][0])) / 2
    mid_buy = (float(buy_row["bid"][0]) + float(buy_row["ask"][0])) / 2

    credit = mid_sell - mid_buy
    if credit <= 0.01 or width <= 0:
        return None

    # max_risk = largeur − crédit reçu ; max_profit = crédit
    return SpreadStrategy(
        signal=None,  # pas de signal directionnel (vente systématique)
        name="put_credit_spread",
        legs=[sell_leg, buy_leg],
        max_risk=round(max(width - credit, 0.01), 2),
        max_profit=round(credit, 2),
        debit_or_credit=round(credit, 2),
        dte=0,
        delta=0.0,
        rationale=f"Vente prime put {spread_pct*100:.0f}% wide à {otm_pct*100:.0f}% OTM",
    )


def build_call_credit_spread(
    symbol: str,
    spot: float,
    chain: pl.DataFrame,
    spread_pct: float = 0.05,
    otm_pct: float = 0.03,
) -> SpreadStrategy | None:
    """Call credit spread : vendre call OTM, acheter call plus haut."""
    opts = chain.filter(pl.col("type") == "call").filter(pl.col("strike") > 0)

    sell_target = spot * (1 + otm_pct)
    buy_target = spot * (1 + otm_pct + spread_pct)

    sell_pool = opts.filter(pl.col("strike") >= sell_target).sort("strike")
    buy_pool = opts.filter(pl.col("strike") >= buy_target).sort("strike")

    if len(sell_pool) == 0 or len(buy_pool) == 0:
        return None

    sell_row = sell_pool.head(1)
    buy_row = buy_pool.head(1)

    sell_leg = _row_to_leg(sell_row.row(0, named=True), "sell")
    buy_leg = _row_to_leg(buy_row.row(0, named=True), "buy")

    width = abs(sell_leg.strike - buy_leg.strike)
    mid_sell = (float(sell_row["bid"][0]) + float(sell_row["ask"][0])) / 2
    mid_buy = (float(buy_row["bid"][0]) + float(buy_row["ask"][0])) / 2

    credit = mid_sell - mid_buy
    if credit <= 0.01 or width <= 0:
        return None

    return SpreadStrategy(
        signal=None,
        name="call_credit_spread",
        legs=[sell_leg, buy_leg],
        max_risk=round(max(width - credit, 0.01), 2),
        max_profit=round(credit, 2),
        debit_or_credit=round(credit, 2),
        dte=0,
        delta=0.0,
        rationale=f"Vente prime call {spread_pct*100:.0f}% wide à {otm_pct*100:.0f}% OTM",
    )