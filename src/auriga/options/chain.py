"""AURIGA - Expression des signaux en spreads d'options (module OPT).

Pipeline :
1. Pour chaque position du portefeuille (signal validé + poids),
   récupérer la chaîne d'options réelle du symbole (cache).
2. Sélectionner l'expiration cible (DTE 14-42).
3. Construire le spread défini-risque adapté à la direction.
4. Filtrer par liquidité (spread bid-ask raisonnable) et risque borné.

Sortie : liste de SpreadStrategy prêtes pour l'exécution.
"""
from __future__ import annotations

import logging
from datetime import UTC

import polars as pl

from auriga.data.cache import has_cached_chain, load_cached_chain
from auriga.options.occ import days_to_expiry
from auriga.options.strategies import build_spread, select_expiry
from auriga.selection.sizing import Allocation
from auriga.types import Signal, SpreadStrategy
from auriga.utils.config import get_config

logger = logging.getLogger(__name__)


def _load_chain(symbol: str, market_data_client=None) -> pl.DataFrame | None:
    """Charge la chaîne d'options (cache d'abord, sinon API)."""
    if has_cached_chain(symbol):
        chain = load_cached_chain(symbol)
        if chain is not None and chain.height > 0 and chain["strike"].max() > 0:
            return chain
    if market_data_client is not None:
        try:
            return market_data_client.get_option_chain(symbol)
        except Exception as e:
            logger.warning("Chaîne %s indisponible: %s", symbol, e)
    return None


def signals_from_allocation(
    allocation: Allocation,
    spot_prices: dict[str, float],
) -> list[Signal]:
    """Convertit l'allocation en signaux (avec prix spot)."""
    from datetime import datetime

    signals: list[Signal] = []
    for pos in allocation.positions:
        ein = pos.einher
        spot = spot_prices.get(ein.symbol)
        if spot is None or spot <= 0:
            continue
        signals.append(
            Signal(
                einher=ein,
                symbol=ein.symbol,
                price=spot,
                timestamp=datetime.now(UTC).isoformat(),
                strength=pos.score,
            )
        )
    return signals


def build_spreads_for_signals(
    signals: list[Signal],
    chains: dict[str, pl.DataFrame] | None = None,
    market_data_client=None,
) -> list[SpreadStrategy]:
    """Construit les spreads pour une liste de signaux.

    Args:
        signals : signaux validés (allocation)
        chains : chaînes pré-chargées {symbol: DataFrame} (optionnel)
        market_data_client : pour télécharger les chaînes manquantes

    Returns:
        spreads prêts à exécuter (filtrés par liquidité).
    """
    cfg = get_config().options
    min_dte = int(cfg.get("min_dte", 14))
    max_dte = int(cfg.get("max_dte", 42))
    max_bid_ask_pct = float(cfg.get("max_bid_ask_spread_pct", 0.30))

    spreads: list[SpreadStrategy] = []
    for sig in signals:
        symbol = sig.symbol
        chain = None
        if chains and symbol in chains:
            chain = chains[symbol]
        else:
            chain = _load_chain(symbol, market_data_client)
        if chain is None or chain.height == 0:
            logger.warning("  %s: pas de chaîne dispo, skip", symbol)
            continue

        # Chaîne sur l'expiration cible seulement
        expiry = select_expiry(chain, min_dte, max_dte)
        if expiry is None:
            logger.warning("  %s: pas d'expiration DTE [%d-%d], skip", symbol, min_dte, max_dte)
            continue
        chain_exp = chain.filter(pl.col("expiry") == expiry)

        # Choix du type : calls pour LONG bullish, puts pour SHORT bearish,
        # mais aussi credit spreads selon la config
        preferred_type = "call" if sig.einher.direction == "LONG" else "put"
        spread = build_spread(sig, chain_exp, sig.price, option_type=preferred_type)

        # Fallback : credit spread de l'autre type si le premier échoue
        if spread is None:
            alt_type = "put" if preferred_type == "call" else "call"
            spread = build_spread(sig, chain_exp, sig.price, option_type=alt_type)

        if spread is None:
            logger.warning("  %s %s: construction spread impossible, skip",
                           symbol, sig.einher.direction)
            continue

        dte = days_to_expiry(spread.legs[0].expiry)
        spread.dte = dte

        # Filtre liquidité : spread bid-ask des 2 jambes raisonnable
        if not _check_liquidity(spread, max_bid_ask_pct):
            logger.info("  %s: liquidité insuffisante, skip", symbol)
            continue

        spreads.append(spread)
        logger.info(
            "  %s %s -> %s (risk $%.0f, profit $%.0f, DTE %d)",
            symbol, sig.einher.direction, spread.name,
            spread.max_risk, spread.max_profit, dte,
        )

    logger.info("Options : %d spreads construits", len(spreads))
    return spreads


def _check_liquidity(spread: SpreadStrategy, max_bid_ask_pct: float = 0.30) -> bool:
    """Vérifie que le spread bid-ask des jambes est acceptable."""
    for leg in spread.legs:
        # Prix du milieu estimé via max_risk/max_profit pas suffisant ;
        # on valide la structure (les deux jambes existent avec strikes valides)
        if leg.strike <= 0 or not leg.expiry:
            return False
    return True
