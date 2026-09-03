"""AURIGA - Position sizing mixte : vol-target plafonné par Kelly-lite.

Stratégie validée Jovanny (2026-09-02) : mélange des deux approches.

1. VOL-TARGET (base) : chaque stratégie reçoit un poids ∝ 1/volatilité de ses
   trades. Les stratégies stables (vol faible) reçoivent plus de capital.

2. KELLY-LITE (plafond) : la taille allouée ne doit pas dépasser une fraction
   du Kelly optimal (f_kelly * kelly), où kelly = win_rate - (1-win_rate)/RR
   avec RR = gain moyen / perte moyenne. On utilise f_kelly=0.25 (Kelly
   fractionnaire conservateur — le Kelly plein est trop agressif).

Résultat : poids normalisés qui respectent un budget de risque total.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

from auriga.selection.scoring import score_einher
from auriga.types import Einher

logger = logging.getLogger(__name__)

MAX_VOL_TARGET = 0.02  # vol annualisée cible par position (2%)
F_KELLY = 0.25  # fraction du Kelly utilisée (conservateur)
MAX_POSITION_PCT = 0.15  # plafond dur : 15% du capital par position


@dataclass
class Position:
    """Position allouée à une stratégie."""

    einher: Einher
    weight: float  # fraction du capital (0-1)
    score: float
    kelly: float  # Kelly optimal estimé
    vol_annual: float  # volatilité annualisée des trades
    rationale: str = ""


@dataclass
class Allocation:
    """Portefeuille alloué."""

    positions: list[Position] = field(default_factory=list)

    @property
    def total_weight(self) -> float:
        return sum(p.weight for p in self.positions)

    def to_dicts(self) -> list[dict]:
        return [
            {
                "einher_id": p.einher.id,
                "symbol": p.einher.symbol,
                "direction": p.einher.direction,
                "weight": round(p.weight, 4),
                "score": round(p.score, 4),
                "kelly": round(p.kelly, 4),
                "vol_annual": round(p.vol_annual, 4),
                "rationale": p.rationale,
            }
            for p in self.positions
        ]


def _annualized_vol(einher: Einher) -> float:
    """Volatilité annualisée des trades (depuis avg_net_return et n_trades)."""
    m = einher.metrics
    if m.n_trades < 2:
        return MAX_VOL_TARGET * 2  # vol inconnue → pénaliser légèrement
    # Approximation : vol_par_trade ≈ |avg| * sqrt(n) quand pas de std dispo.
    # Mieux : utiliser avg_net_return * sqrt(trades_par_an) comme proxy.
    # Ici on estime via le max_drawdown et le nombre de trades.
    std_proxy = abs(m.avg_net_return) * 2.0 + 0.005
    trades_per_year = max(m.n_trades / 1.0, 1.0)  # fenêtre ~1 an de données
    return min(std_proxy * np.sqrt(trades_per_year), 1.0)


def _kelly_fraction(einher: Einher) -> float:
    """Kelly optimal : f* = p - q/R où R = gain moyen / perte moyenne."""
    m = einher.metrics
    p = m.win_rate
    if p <= 0 or p >= 1:
        return 0.0
    gains = m.extra.get("avg_gain", 0.0)
    losses = m.extra.get("avg_loss", 0.0)
    if losses is None or losses <= 0:
        return p
    R = gains / losses if gains and losses else 1.0
    q = 1 - p
    return max(0.0, p - q / R) if R > 0 else 0.0


def size_portfolio(
    einhers: list[Einher],
    budget_risk_pct: float = 0.50,
) -> Allocation:
    """Alloue le capital aux stratégies (mix vol-target + Kelly plafond).

    Args:
        einhers : stratégies diversifiées, avec métriques remplies
        budget_risk_pct : fraction du capital total risqué (50% par défaut)

    Returns:
        Allocation avec poids normalisés.
    """
    if not einhers:
        return Allocation()

    raw: list[dict] = []
    for ein in einhers:
        vol = _annualized_vol(einher=ein)
        kelly = _kelly_fraction(einher=ein)
        score = score_einher(einher=ein)

        # Vol-target : poids de base inversement proportionnel à la vol
        w_vol = min(MAX_VOL_TARGET / max(vol, 1e-6), 1.0)

        # Kelly-lite : plafond = fraction du Kelly (0 si Kelly <= 0)
        w_kelly = max(F_KELLY * kelly, 0.0)

        # Mélange : base vol-target, plafonnée par Kelly-lite
        w = min(w_vol, w_kelly) if w_kelly > 0 else w_vol * 0.5

        # Ajuster par le score (qualité globale) : les meilleures reçoivent plus
        w = w * (0.5 + 0.5 * score)

        raw.append({"einher": ein, "weight": w, "score": score, "kelly": kelly, "vol": vol})

    # Normaliser pour que la somme = budget_risk_pct
    total = sum(r["weight"] for r in raw)
    positions: list[Position] = []
    if total > 0:
        for r in raw:
            w = r["weight"] / total * budget_risk_pct
            # Plafond dur par position
            w = min(w, MAX_POSITION_PCT)
            positions.append(
                Position(
                    einher=r["einher"],
                    weight=w,
                    score=r["score"],
                    kelly=r["kelly"],
                    vol_annual=r["vol"],
                    rationale=(
                        f"vol-target={r['weight']:.4f} brut, "
                        f"kelly={r['kelly']:.3f}, score={r['score']:.2f}"
                    ),
                )
            )

    # Re-normaliser après plafonnement (pour respecter le budget)
    total_w = sum(p.weight for p in positions)
    if total_w > 0:
        scale = min(1.0, budget_risk_pct / total_w) if total_w > budget_risk_pct else 1.0
        for p in positions:
            p.weight = round(p.weight * scale, 6)

    alloc = Allocation(positions=positions)
    logger.info(
        "Sizing : %d positions, poids total %.2f (budget %.0f%%)",
        len(positions), alloc.total_weight, budget_risk_pct * 100,
    )
    return alloc
