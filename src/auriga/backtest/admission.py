"""AURIGA - Admission statistique des Einhers (adapté d'einherjar).

Deux niveaux de filtrage :
1. SEUILS INDIVIDUELS : Sharpe >= min_sharpe, win_rate >= min_win_rate,
   profit_factor >= min_profit_factor, n_trades >= min_trades,
   max_drawdown >= -max_drawdown (moins négatif).
2. CONTRÔLE MULTI-TESTS (BH/FDR) : corrige le problème des tests multiples
   (des centaines de candidats testés → des faux positifs attendus par le
   hasard). p-values one-sided upper depuis la t-stat.

Convention de sortie : raison de rejet explicite (traçabilité).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from auriga.types import Einher, EinherMetrics

logger = logging.getLogger(__name__)


@dataclass
class AdmissionConfig:
    """Seuils d'admission (défauts = config/settings.yaml)."""

    min_sharpe: float = 2.0
    min_win_rate: float = 0.65
    min_profit_factor: float = 1.5
    min_trades: int = 30
    max_drawdown: float = 0.30  # valeur absolue max tolérée
    min_holdout_trades: int = 15
    fdr_adaptive: bool = True
    fdr_level: float = 0.05  # utilisé si fdr_adaptive=False


@dataclass
class AdmissionResult:
    """Résultat d'admission pour un Einher."""

    einher: Einher
    admitted: bool
    reason: str = ""  # "ADMITTED" ou raison de rejet
    p_value: float = 1.0


def default_admission_config() -> AdmissionConfig:
    """Charge les seuils depuis settings.yaml."""
    from auriga.utils.config import get_config

    cfg = get_config().admission
    return AdmissionConfig(
        min_sharpe=float(cfg.get("min_sharpe", 2.0)),
        min_win_rate=float(cfg.get("min_win_rate", 0.65)),
        min_profit_factor=float(cfg.get("min_profit_factor", 1.5)),
        min_trades=int(cfg.get("min_trades", 30)),
        max_drawdown=float(cfg.get("max_drawdown", 0.30)),
        min_holdout_trades=int(cfg.get("min_holdout_trades", 15)),
        fdr_adaptive=bool(cfg.get("fdr_adaptive", True)),
    )


def p_value_from_metrics(metrics: EinherMetrics) -> float:
    """p-value one-sided upper depuis la t-stat (stockée dans extra)."""
    return float(metrics.extra.get("p_value", 1.0))


def check_single_thresholds(
    metrics: EinherMetrics,
    cfg: AdmissionConfig,
) -> tuple[bool, str]:
    """Vérifie les seuils individuels. Retourne (ok, raison)."""
    if metrics.n_trades < cfg.min_trades:
        return False, f"n_trades {metrics.n_trades} < {cfg.min_trades}"
    if metrics.sharpe_ratio < cfg.min_sharpe:
        return False, f"sharpe {metrics.sharpe_ratio:.2f} < {cfg.min_sharpe}"
    if metrics.win_rate < cfg.min_win_rate:
        return False, f"win_rate {metrics.win_rate:.2f} < {cfg.min_win_rate}"
    if metrics.profit_factor < cfg.min_profit_factor:
        return False, f"profit_factor {metrics.profit_factor:.2f} < {cfg.min_profit_factor}"
    if abs(metrics.max_drawdown) > cfg.max_drawdown:
        return False, f"max_drawdown {metrics.max_drawdown:.3f} > {cfg.max_drawdown}"
    return True, ""


def adaptive_fdr_level(n_candidates: int) -> float:
    """FDR adaptatif au nombre de candidats testés.

    Moins de candidats → FDR plus permissif (peu de tests → peu de faux
    positifs attendus, un seuil trop strict tuerait tout).
    """
    if n_candidates <= 50:
        return 0.30
    if n_candidates <= 200:
        return 0.15
    if n_candidates <= 500:
        return 0.10
    return 0.05


def apply_bh_fdr(
    results: list[AdmissionResult],
    cfg: AdmissionConfig,
) -> list[AdmissionResult]:
    """Applique le contrôle Benjamini-Hochberg sur les p-values.

    Seuls les candidats ayant déjà passé les seuils individuels sont dans la
    course BH. Les autres sont marqués avec leur raison individuelle.

    Returns:
        résultats avec admitted=True seulement pour ceux qui passent BH.
    """
    # Candidats éligibles (seuils individuels OK) : ceux sans raison
    eligible = [r for r in results if r.reason == ""]
    n_eligible = len(eligible)
    n_total = len(results)

    if not eligible:
        return results

    # Niveau FDR
    if cfg.fdr_adaptive:
        fdr = adaptive_fdr_level(n_total)
    else:
        fdr = cfg.fdr_level

    # Trier par p-value croissante
    eligible_sorted = sorted(eligible, key=lambda r: r.p_value)

    # BH : trouver le plus grand k tel que p_(k) <= (k/n) * fdr
    k_max = 0
    for i, r in enumerate(eligible_sorted, start=1):
        threshold = (i / n_total) * fdr
        if r.p_value <= threshold:
            k_max = i
        else:
            break

    # Les k_max premiers passent, les autres sont rejetés BH
    for i, r in enumerate(eligible_sorted):
        if i < k_max:
            r.admitted = True
            r.reason = "ADMITTED"
        else:
            r.admitted = False
            r.reason = f"BH REJECTED (p={r.p_value:.4f} > seuil FDR={fdr})"

    logger.info(
        "BH/FDR : %d éligibles / %d total, FDR=%.2f, %d admis",
        n_eligible, n_total, fdr, k_max,
    )
    return results


def admit_einhers(
    einhers: list[Einher],
    cfg: AdmissionConfig | None = None,
    phase: str = "val",
) -> list[AdmissionResult]:
    """Admet ou rejette une liste d'Einhers (seuils + BH/FDR).

    Args:
        einhers : candidats avec metrics REMPLIES (backtest val déjà fait)
        cfg : seuils
        phase : 'val' (validation) ou 'holdout' (admission finale)

    Returns:
        AdmissionResult par Einher (admitted + raison explicite).
    """
    cfg = cfg or default_admission_config()
    results: list[AdmissionResult] = []

    for ein in einhers:
        m = ein.metrics
        ok, reason = check_single_thresholds(m, cfg)
        p = p_value_from_metrics(m)
        results.append(
            AdmissionResult(
                einher=ein,
                admitted=False,
                reason=reason if not ok else "",  # "" = éligible pour BH
                p_value=p,
            )
        )

    return apply_bh_fdr(results, cfg)
