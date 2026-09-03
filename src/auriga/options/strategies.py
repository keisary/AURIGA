"""AURIGA - Construction des spreads d'options définis-risque.

Convertit un signal (direction + amplitude + confiance) en spread vertical
défini-risque (requis par les règles du hackathon : options obligatoires) :

- Signal LONG  → bull call spread (débit) OU put credit spread (crédit)
- Signal SHORT → bear put spread (débit) OU call credit spread (crédit)

Chaque spread a un risque MAXIMUM borné (largeur du spread − prime reçue
pour les crédits, coût net pour les débits) → conforme risk management.

Stratégie par défaut (alignée sur des options 2-6 semaines) :
- Débit spread (plus directionnel, plus simple) : bull call / bear put
"""
from __future__ import annotations

import logging

import polars as pl

from auriga.types import OptionLeg, Signal, SpreadStrategy

logger = logging.getLogger(__name__)


def _row_to_leg(row: dict, side: str) -> OptionLeg:
    """Convertit une ligne polars en OptionLeg."""
    return OptionLeg(
        symbol=str(row["symbol"]),
        option_symbol=str(row["option_symbol"]),
        side=side,
        option_type=str(row["type"]),
        strike=float(row["strike"]),
        expiry=str(row["expiry"]),
        qty=1,
    )


def build_spread(
    signal: Signal,
    chain: pl.DataFrame,
    spot: float,
    option_type: str = "call",
    spread_pct: float = 0.05,
) -> SpreadStrategy | None:
    """Construit un spread défini-risque pour un signal.

    Args:
        signal : Signal (einher + direction + prix)
        chain : chaîne d'options du symbole
        spot : prix actuel du sous-jacent
        option_type : 'call' (LONG→bull call, SHORT→call credit) ou 'put'
        spread_pct : largeur du spread en % du spot

    Returns:
        SpreadStrategy ou None si la chaîne est insuffisante.
    """
    direction = signal.einher.direction  # 'LONG' | 'SHORT'
    opts = chain.filter(pl.col("type") == option_type).filter(pl.col("strike") > 0)

    if direction == "LONG" and option_type == "call":
        # Bull call spread : achat call ATM (strike ~spot), vente call +spread_pct
        buy_pool = opts.filter(pl.col("strike") <= spot).sort("strike", descending=True)
        sell_pool = opts.filter(pl.col("strike") >= spot * (1 + spread_pct)).sort("strike")
    elif direction == "SHORT" and option_type == "put":
        # Bear put spread : achat put ATM, vente put -spread_pct (crédit inversé)
        # En fait bear put spread = achat put avec strike > spot (ITM léger) et
        # vente put avec strike encore plus haut ? Non.
        # Bear put spread débit : ACHETER put strike proche (>= spot), VENDRE put
        # strike plus bas. On achète le put le plus proche >= spot.
        buy_pool = opts.filter(pl.col("strike") >= spot).sort("strike")
        sell_pool = opts.filter(pl.col("strike") <= spot * (1 - spread_pct)).sort("strike", descending=True)
    elif direction == "SHORT" and option_type == "call":
        # Call credit spread : VENDRE call OTM (strike > spot), ACHETER call plus haut
        sell_pool = opts.filter(pl.col("strike") >= spot * (1 + spread_pct * 0.5)).sort("strike")
        buy_pool = opts.filter(pl.col("strike") >= spot * (1 + spread_pct * 1.5)).sort("strike")
    elif direction == "LONG" and option_type == "put":
        # Put credit spread : VENDRE put OTM (strike < spot), ACHETER put plus bas
        sell_pool = opts.filter(pl.col("strike") <= spot * (1 - spread_pct * 0.5)).sort("strike", descending=True)
        buy_pool = opts.filter(pl.col("strike") <= spot * (1 - spread_pct * 1.5)).sort("strike", descending=True)
    else:
        return None

    if len(buy_pool) == 0 or len(sell_pool) == 0:
        return None

    # Même expiration pour les deux jambes : la plus proche dispo sur les deux
    buy_row = buy_pool.head(1)
    sell_row = sell_pool.head(1)

    buy_leg = _row_to_leg(buy_row.row(0, named=True), "buy")
    sell_leg = _row_to_leg(sell_row.row(0, named=True), "sell")

    # Calcul max_risk/max_profit selon le type de spread
    buy_strike = buy_leg.strike
    sell_strike = sell_leg.strike
    width = abs(sell_strike - buy_strike)

    # Estimation des prix (mid)
    mid_buy = (float(buy_row["bid"][0]) + float(buy_row["ask"][0])) / 2
    mid_sell = (float(sell_row["bid"][0]) + float(sell_row["ask"][0])) / 2

    if mid_buy <= 0 and mid_sell <= 0:
        # Chaîne sans prix (mode snapshot incomplet) : on estime la largeur
        return None

    # Nom + nature du spread (débit = on paie, crédit = on reçoit)
    is_debit_spread = (direction == "LONG" and option_type == "call") or \
                      (direction == "SHORT" and option_type == "put")
    if direction == "LONG" and option_type == "call":
        name = "bull_call_spread"
    elif direction == "SHORT" and option_type == "put":
        name = "bear_put_spread"
    elif direction == "SHORT" and option_type == "call":
        name = "call_credit_spread"
    else:
        name = "put_credit_spread"

    # Débit net = prix payé pour la jambe achetée − prix reçu pour la jambe vendue.
    # Crédit net = l'inverse (on vend la jambe chère, on achète la jambe moins chère).
    net = mid_buy - mid_sell if is_debit_spread else mid_sell - mid_buy

    if net <= 0.01:
        return None  # spread sans valeur (bid/ask invalides)

    if is_debit_spread:
        # Spread débit : risque = débit payé, gain max = largeur − débit
        max_risk = net
        max_profit = max(width - net, 0.01)
    else:
        # Spread crédit : risque = largeur − crédit reçu, gain max = crédit
        max_risk = max(width - net, 0.01)
        max_profit = net

    return SpreadStrategy(
        signal=signal,
        name=name,
        legs=[buy_leg, sell_leg],
        max_risk=round(max_risk, 2),
        max_profit=round(max_profit, 2),
        debit_or_credit=round(net, 2),
        dte=0,  # calculé par l'appelant
        delta=0.0,
        rationale=f"{direction} {option_type} spread {spread_pct*100:.0f}% wide",
    )


def select_expiry(chain: pl.DataFrame, min_dte: int = 14, max_dte: int = 42) -> str | None:
    """Sélectionne l'expiration cible dans la chaîne (DTE 14-42 par défaut)."""
    from auriga.options.occ import days_to_expiry

    # Filtrer les expiries invalides/vides (robustesse)
    expiries = sorted(
        e for e in chain["expiry"].unique().to_list()
        if isinstance(e, str) and len(e) == 10 and e[4] == "-"
    )
    for exp in expiries:
        try:
            dte = days_to_expiry(exp)
        except Exception:
            continue
        if min_dte <= dte <= max_dte:
            return exp
    # Fallback : la plus proche au-delà de min_dte
    for exp in expiries:
        try:
            dte = days_to_expiry(exp)
        except Exception:
            continue
        if dte >= min_dte:
            return exp
    return expiries[0] if expiries else None
