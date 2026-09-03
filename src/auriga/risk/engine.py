"""AURIGA - Risk Engine : garde-fous avant exécution.

Applique les risk gates (REQ-F-RSK) avant CHAQUE ordre :
- daily_loss_limit : perte journalière max (défaut -2%) → stop nouveaux ordres
- max_asset_exposure : exposition max par actif (10%)
- max_sector_exposure : exposition max par secteur (25%)
- max_positions : nombre max de positions simultanées (12)
- max_total_exposure : capital max risqué total (80%)
- liquidation_threshold : perte totale > 25% → liquidation suggérée

Chaque gate bloquante est journalisée (traçabilité pour le dashboard).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from auriga.types import (
    PortfolioState,
    RiskDecision,
    SpreadStrategy,
)
from auriga.utils.config import get_config
from auriga.utils.universe import load_universe, sector_of

logger = logging.getLogger(__name__)


@dataclass
class RiskConfig:
    """Seuils du risk engine (défauts depuis settings.yaml)."""

    daily_loss_limit: float = 0.02  # -2% → stop
    max_asset_exposure: float = 0.10  # 10% par actif
    max_sector_exposure: float = 0.25  # 25% par secteur
    max_total_exposure: float = 0.80  # 80% du capital
    max_positions: int = 12
    stop_loss_pct: float = 0.15
    liquidation_threshold: float = 0.25  # -25% → liquidation


def default_risk_config() -> RiskConfig:
    """Charge les seuils depuis settings.yaml."""
    cfg = get_config().risk
    return RiskConfig(
        daily_loss_limit=float(cfg.get("daily_loss_limit", 0.02)),
        max_asset_exposure=float(cfg.get("max_asset_exposure", 0.10)),
        max_sector_exposure=float(cfg.get("max_sector_exposure", 0.25)),
        max_total_exposure=float(cfg.get("max_total_exposure", 0.80)),
        max_positions=int(cfg.get("max_positions", 12)),
        stop_loss_pct=float(cfg.get("stop_loss_pct", 0.15)),
        liquidation_threshold=float(cfg.get("liquidation_threshold", 0.25)),
    )


class RiskEngine:
    """Évalue les ordres/spreads contre les risk gates.

    Gates de base (config) + extra_checks : fonctions de gate additionnelles
    fournies par les agents (vol_signal, AVOID_SELL). Chaque fonction a la
    signature (spread) -> (ok: bool, raison: str).
    """

    def __init__(self, config: RiskConfig | None = None):
        self.config = config or default_risk_config()
        self._universe = load_universe()
        self.extra_checks: list = []  # [(fn, label), ...]

    def add_check(self, fn, label: str) -> None:
        """Ajoute une gate externe (ex: vol_danger, avoid_sell)."""
        self.extra_checks.append((fn, label))

    # ------------------------------------------------------------------
    def _run_extra_checks(self, spread: SpreadStrategy) -> tuple[list[str], list[str]]:
        """Exécute les gates externes. Retourne (raisons, bloquants).

        FAIL-CLOSED (revue 2026-09-03) : une gate qui ne peut pas être
        vérifiée (exception, donnée manquante) BLOQUE l'ordre. Pour un
        système de trading, "je ne peux pas vérifier le risque" doit être
        traité comme un risque, pas comme un feu vert.
        """
        reasons: list[str] = []
        blocked: list[str] = []
        for fn, label in self.extra_checks:
            try:
                ok, detail = fn(spread)
                if ok:
                    reasons.append(f"{label}_ok")
                else:
                    blocked.append(f"{label}: {detail}")
            except Exception as e:
                # FAIL-CLOSED : gate indisponible → on bloque (pas de log only)
                blocked.append(f"{label}: unavailable ({str(e)[:80]})")
                logger.warning("Gate %s INOPÉRANTE → ordre bloqué: %s", label, e)
        return reasons, blocked

    # ------------------------------------------------------------------
    def evaluate_spread(
        self,
        spread: SpreadStrategy,
        portfolio: PortfolioState,
        capital: float | None = None,
    ) -> RiskDecision:
        """Évalue un spread proposé contre les gates.

        Args:
            spread : position proposée (max_risk en $)
            portfolio : état courant du portefeuille
            capital : equity totale (défaut = portfolio.equity)

        Returns:
            RiskDecision (allowed + raisons/bloquants).
        """
        capital = capital or portfolio.equity or 100_000.0
        reasons: list[str] = []
        blocked: list[str] = []

        # Gate 1 : daily loss limit
        if portfolio.day_pnl <= -self.config.daily_loss_limit * capital:
            blocked.append(
                f"daily_loss: {portfolio.day_pnl/capital*100:.1f}% "
                f"<= -{self.config.daily_loss_limit*100:.0f}%"
            )
        else:
            reasons.append("daily_loss_ok")

        # Gate 2 : nombre max de positions
        n_new = 1
        if len(portfolio.positions) + n_new > self.config.max_positions:
            blocked.append(
                f"max_positions: {len(portfolio.positions)}+1 > {self.config.max_positions}"
            )
        else:
            reasons.append("positions_ok")

        # Gate 3 : exposition par actif
        symbol = spread.underlying
        existing_asset = sum(
            p.max_risk for p in portfolio.positions if p.symbol == symbol
        )
        asset_expo = (existing_asset + spread.max_risk) / capital
        if asset_expo > self.config.max_asset_exposure:
            blocked.append(
                f"asset_exposure: {symbol} {asset_expo*100:.1f}% "
                f"> {self.config.max_asset_exposure*100:.0f}%"
            )
        else:
            reasons.append("asset_exposure_ok")

        # Gate 4 : exposition par secteur
        sector = sector_of(symbol, self._universe)
        if sector:
            existing_sector = sum(
                p.max_risk for p in portfolio.positions
                if sector_of(p.symbol, self._universe) == sector
            )
            sector_expo = (existing_sector + spread.max_risk) / capital
            if sector_expo > self.config.max_sector_exposure:
                blocked.append(
                    f"sector_exposure: {sector} {sector_expo*100:.1f}% "
                    f"> {self.config.max_sector_exposure*100:.0f}%"
                )
            else:
                reasons.append("sector_exposure_ok")
        else:
            reasons.append("sector_unknown_ok")

        # Gate 5 : exposition totale (max_risk cumulé)
        total_expo = (portfolio.gross_exposure + spread.max_risk) / capital
        if total_expo > self.config.max_total_exposure:
            blocked.append(
                f"total_exposure: {total_expo*100:.1f}% > {self.config.max_total_exposure*100:.0f}%"
            )
        else:
            reasons.append("total_exposure_ok")

        # Gate 6 : taille de position raisonnable vs capital
        if spread.max_risk > self.config.max_asset_exposure * capital:
            blocked.append(f"position_size: ${spread.max_risk:.0f} trop grande")
        else:
            reasons.append("position_size_ok")

        # Gates externes (vol_danger, avoid_sell — fournies par les agents)
        extra_reasons, extra_blocked = self._run_extra_checks(spread)
        reasons.extend(extra_reasons)
        blocked.extend(extra_blocked)

        # Liquidation suggérée si perte totale trop profonde
        liquidation: list[str] = []
        total_pnl_pct = portfolio.total_pnl / capital if capital > 0 else 0
        if total_pnl_pct <= -self.config.liquidation_threshold:
            liquidation = [p.symbol for p in portfolio.positions]

        decision = RiskDecision(
            allowed=len(blocked) == 0,
            reasons=reasons,
            blocked_by=blocked,
            suggested_liquidation=liquidation,
        )
        if not decision.allowed:
            logger.warning(
                "RISK BLOQUÉ %s %s: %s",
                symbol, spread.name, "; ".join(blocked),
            )
        return decision

    # ------------------------------------------------------------------
    def evaluate_portfolio(self, portfolio: PortfolioState, capital: float | None = None) -> RiskDecision:
        """Évalue l'état global du portefeuille (sans nouvel ordre)."""
        capital = capital or portfolio.equity or 100_000.0
        reasons: list[str] = []
        blocked: list[str] = []
        liquidation: list[str] = []

        if portfolio.day_pnl <= -self.config.daily_loss_limit * capital:
            blocked.append("daily_loss_limit_atteint")
            # En cas de daily loss limit : suggérer de tout liquider
            liquidation = [p.symbol for p in portfolio.positions]

        total_expo = portfolio.gross_exposure / capital if capital > 0 else 0
        if total_expo > self.config.max_total_exposure:
            blocked.append(f"total_exposure {total_expo*100:.0f}%")

        total_pnl_pct = portfolio.total_pnl / capital if capital > 0 else 0
        if total_pnl_pct <= -self.config.liquidation_threshold:
            liquidation = [p.symbol for p in portfolio.positions]

        if not blocked:
            reasons.append("portfolio_ok")
        return RiskDecision(
            allowed=len(blocked) == 0,
            reasons=reasons,
            blocked_by=blocked,
            suggested_liquidation=liquidation,
        )

    # ------------------------------------------------------------------
    def check_position_size(self, risk_usd: float, capital: float) -> tuple[bool, str]:
        """Vérifie qu'un risque en $ est dans les bornes."""
        if risk_usd <= 0:
            return False, "risk_usd <= 0"
        if risk_usd > self.config.max_asset_exposure * capital:
            return False, (
                f"risk ${risk_usd:.0f} > "
                f"{self.config.max_asset_exposure*100:.0f}% du capital (${capital:,.0f})"
            )
        return True, ""
