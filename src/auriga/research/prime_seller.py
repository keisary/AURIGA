"""AURIGA - Vente de prime systématique (Agent A3, exécution).

DÉCISION 2026-09-03 (Jovanny) : le portefeuille exécutable = stratégies
directionnelles A1 + VENTE SYSTÉMATIQUE de credit spreads, filtrée par les
signaux de risque (VolSignal A2 + règles AVOID_SELL A3).

Logique :
1. Pour chaque actif de l'univers, construire un put credit spread OTM
   (et/ou call credit spread) à l'expiration cible.
2. NE PAS vendre si :
   - VolRiskEngine signale 'danger' (choc de vol imminent) ;
   - une règle AVOID_SELL se déclenche sur les features actuelles.
3. Passer les risk gates (RiskEngine) puis soumettre l'ordre multi-leg.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import polars as pl

from auriga.options.credit_spreads import build_call_credit_spread, build_put_credit_spread
from auriga.options.occ import days_to_expiry
from auriga.options.strategies import select_expiry
from auriga.risk.vol_signal import VolRiskEngine
from auriga.types import SpreadStrategy
from auriga.utils.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class PrimeSellerConfig:
    """Paramètres de la vente de prime."""

    spread_pct: float = 0.05  # largeur du spread (5% du spot)
    otm_pct: float = 0.03  # le strike vendu est à 3% OTM
    max_credit_spreads_per_cycle: int = 8
    min_credit_usd: float = 0.15  # crédit minimum par contrat ($)
    enable_call_spreads: bool = False  # put spreads par défaut (biais haussier)
    vol_danger_threshold: float = 0.35


def default_prime_seller_config() -> PrimeSellerConfig:
    return PrimeSellerConfig()


class AvoidSellFilter:
    """Filtre AVOID_SELL : évalue les règles A3 sur les features actuelles.

    Les règles AVOID_SELL sont chargées depuis le portfolio ou un fichier ;
    si l'une se déclenche sur les features courantes → on ne vend PAS.
    """

    def __init__(self, avoid_rules: list | None = None):
        self.avoid_rules = avoid_rules or []

    def is_blocked(self, symbol: str, feats_recent: pl.DataFrame) -> tuple[bool, str]:
        """True si une règle AVOID_SELL se déclenche sur les features actuelles.

        feats_recent : DataFrame de features (sortie compute_features) incluant
        la dernière barre courante.
        """
        if not self.avoid_rules:
            return False, ""
        from auriga.research.condition_tree import evaluate_ast_on_array

        feature_names = [c for c in feats_recent.columns if c != "timestamp"]
        X = feats_recent.select(feature_names).to_numpy().astype("float32")
        for rule in self.avoid_rules:
            if rule.symbol not in ("POOL", symbol):
                continue
            try:
                mask = evaluate_ast_on_array(rule.condition, X, feature_names)
                if bool(mask[-1]):  # la condition est vraie sur la dernière barre
                    return True, f"AVOID_SELL {rule.id[:24]}"
            except Exception:
                continue
        return False, ""


def build_prime_spreads_for_symbol(
    symbol: str,
    spot: float,
    chain: pl.DataFrame,
    cfg: PrimeSellerConfig | None = None,
    side: str = "put",
) -> SpreadStrategy | None:
    """Construit un credit spread de vente pour un actif."""
    cfg = cfg or default_prime_seller_config()
    if side == "put":
        spread = build_put_credit_spread(
            symbol, spot, chain,
            spread_pct=cfg.spread_pct, otm_pct=cfg.otm_pct,
        )
    else:
        spread = build_call_credit_spread(
            symbol, spot, chain,
            spread_pct=cfg.spread_pct, otm_pct=cfg.otm_pct,
        )
    if spread is None:
        return None
    if spread.debit_or_credit < cfg.min_credit_usd:
        return None
    return spread


def select_prime_candidates(
    symbols: list[str],
    spots: dict[str, float],
    chains: dict[str, pl.DataFrame],
    cfg: PrimeSellerConfig | None = None,
) -> list[SpreadStrategy]:
    """Sélectionne les credit spreads candidats (avant filtres risque).

    Retourne les spreads les plus crédités, limités à max_credit_spreads.
    """
    cfg = cfg or default_prime_seller_config()
    candidates: list[SpreadStrategy] = []

    for sym in symbols:
        spot = spots.get(sym)
        chain = chains.get(sym)
        if spot is None or spot <= 0 or chain is None:
            continue
        # Expiration cible
        exp = select_expiry(chain)
        if exp is None:
            continue
        chain_exp = chain.filter(pl.col("expiry") == exp)
        if chain_exp.height == 0:
            continue

        spread = build_prime_spreads_for_symbol(sym, spot, chain_exp, cfg, side="put")
        if spread is not None:
            spread.dte = days_to_expiry(exp)
            candidates.append(spread)

        if cfg.enable_call_spreads:
            spread_c = build_prime_spreads_for_symbol(sym, spot, chain_exp, cfg, side="call")
            if spread_c is not None:
                spread_c.dte = days_to_expiry(exp)
                candidates.append(spread_c)

    # Garder les meilleurs crédits
    candidates.sort(key=lambda s: s.debit_or_credit, reverse=True)
    return candidates[: cfg.max_credit_spreads_per_cycle]


def filter_danger(
    candidates: list[SpreadStrategy],
    vol_engine: VolRiskEngine,
    recent_feats: dict[str, pl.DataFrame],
    avoid_filter: AvoidSellFilter | None = None,
) -> tuple[list[SpreadStrategy], list[dict]]:
    """Filtre les candidats par les signaux de risque (vol + AVOID_SELL).

    Args:
        candidates : credit spreads proposés
        vol_engine : moteur de signal vol (A2)
        recent_feats : {symbol: features récentes (compute_features)}
        avoid_filter : filtre AVOID_SELL (A3)

    Returns:
        (spreads autorisés, événements de blocage pour le narratif)
    """
    allowed: list[SpreadStrategy] = []
    events: list[dict] = []

    for spread in candidates:
        sym = spread.underlying
        feats = recent_feats.get(sym)
        if feats is None or feats.height < 60:
            continue

        # 1. Signal vol (A2) — nécessite les bars pour scorer ; on passe par
        #    le VolRiskEngine qui calcule ses propres features si besoin.
        danger, vol_out = vol_engine.is_danger_from_features(sym, feats)
        if danger:
            events.append({
                "symbol": sym, "type": "vol_danger",
                "detail": f"proba={vol_out.danger_proba:.2f}",
            })
            continue

        # 2. AVOID_SELL (A3)
        if avoid_filter is not None:
            blocked, reason = avoid_filter.is_blocked(sym, feats)
            if blocked:
                events.append({"symbol": sym, "type": "avoid_sell", "detail": reason})
                continue

        allowed.append(spread)

    logger.info(
        "Filtre danger : %d/%d credit spreads autorisés (%d bloqués)",
        len(allowed), len(candidates), len(events),
    )
    return allowed, events