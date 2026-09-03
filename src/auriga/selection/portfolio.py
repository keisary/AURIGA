"""AURIGA - Sélection de portefeuille : orchestrateur final.

Pipeline :
1. Classer les Einhers admis par score pondéré.
2. Diversifier (éliminer les redondants, Jaccard >= 0.7 sur mêmes features).
3. Appliquer les contraintes dures :
   - max_positions (10-15)
   - max 1 stratégie par actif (évite le double comptage)
   - exposure max par secteur (via universe.sector_of)
4. Sizer (mix vol-target + Kelly-lite).

Sortie : Allocation prête pour le module options.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from auriga.selection.diversify import diversify
from auriga.selection.scoring import rank_einhers, score_einher
from auriga.selection.sizing import Allocation, Position, size_portfolio
from auriga.types import Einher
from auriga.utils.universe import sector_of

logger = logging.getLogger(__name__)


@dataclass
class PortfolioConfig:
    """Contraintes de portefeuille (défauts depuis settings.yaml)."""

    max_positions: int = 12
    max_per_asset: int = 1
    max_per_sector: float = 0.25  # 25% du capital par secteur
    budget_risk_pct: float = 0.50
    jaccard_threshold: float = 0.70
    diversify_enabled: bool = True


def default_portfolio_config() -> PortfolioConfig:
    from auriga.utils.config import get_config

    sel = get_config().selection
    return PortfolioConfig(
        max_positions=int(sel.get("max_positions", 12)),
        max_per_asset=int(sel.get("max_per_asset", 1)),
        max_per_sector=float(sel.get("max_per_sector", 0.25)),
        budget_risk_pct=float(sel.get("budget_risk_pct", 0.50)),
        diversify_enabled=bool(sel.get("diversify", True)),
    )


def build_portfolio(
    einhers: list[Einher],
    config: PortfolioConfig | None = None,
    universe: dict | None = None,
) -> Allocation:
    """Construit le portefeuille final depuis les Einhers admis.

    Args:
        einhers : stratégies ADMISES (déjà validées par le backtest)
        config : contraintes
        universe : {symbols, sectors} (pour l'exposition sectorielle)

    Returns:
        Allocation (positions pondérées).
    """
    config = config or default_portfolio_config()
    if not einhers:
        return Allocation()

    # 1. Classer par score
    ranked = rank_einhers(einhers)

    # 2. Diversifier (éliminer les quasi-jumeaux)
    if config.diversify_enabled:
        ranked = diversify(ranked, threshold=config.jaccard_threshold)

    # 3. Contraintes : max par actif
    per_asset: dict[str, int] = {}
    filtered: list[Einher] = []
    for ein in ranked:
        if per_asset.get(ein.symbol, 0) >= config.max_per_asset:
            continue
        per_asset[ein.symbol] = per_asset.get(ein.symbol, 0) + 1
        filtered.append(ein)

    # 4. Cap sur le nombre de positions (avant sizing)
    filtered = filtered[: config.max_positions * 2]

    # 5. Sizing
    allocation = size_portfolio(filtered, budget_risk_pct=config.budget_risk_pct)

    # 6. Contrainte sectorielle : retirer les positions qui dépassent
    # l'exposition max par secteur (après sizing).
    sector_expo: dict[str, float] = {}
    kept: list[Position] = []
    for pos in allocation.positions:
        sector = sector_of(pos.einher.symbol, universe)
        if sector and sector_expo.get(sector, 0.0) + pos.weight > config.max_per_sector:
            logger.info("  Secteur %s saturé: skip %s (%.1f%%)",
                        sector, pos.einher.id, pos.weight * 100)
            continue
        if sector:
            sector_expo[sector] = sector_expo.get(sector, 0.0) + pos.weight
        kept.append(pos)

    # Re-normaliser
    total = sum(p.weight for p in kept)
    if total > 0:
        scale = min(1.0, config.budget_risk_pct / total) if total > config.budget_risk_pct else 1.0
        for p in kept:
            p.weight = round(p.weight * scale, 6)

    final = Allocation(positions=kept[: config.max_positions])
    logger.info(
        "Portefeuille : %d positions sur %d candidats (score top %.3f)",
        len(final.positions), len(einhers),
        score_einher(final.positions[0].einher) if final.positions else 0,
    )
    return final
