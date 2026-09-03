"""AURIGA - Agent A3 : découverte de stratégies de VENTE DE PRIME.

Objectif : détecter les régimes où VENDRE de la prime (credit spreads /
short straddles) est favorable — typiquement vol élevée mais marché
range-bound, pas de choc imminent.

Pourquoi (DESIGN_RATIONALE.md §8, Ilmanen 2012) :
- Le variance risk premium (IV > RV) rend la vente de vol gagnante EN MOYENNE.
- MAIS la vente subit des pertes catastrophiques rares (queues de risque).
- Le ML ne prédit PAS la direction : il décide QUAND vendre (régime calme)
  et QUAND NE PAS vendre (avant choc). C'est un FILTRE DE RISQUE.

Méthode :
1. Pour chaque barre t, calculer le P&L d'un short straddle sur [t, t+H]
   (via backtest_straddle_einher avec direction VOL_DOWN).
2. Label binaire : y = 1 si le short straddle est profitable (P&L > 0).
3. XGBoost classifie y à partir des features de régime/vol.
4. Règles extraites → direction "SELL_PRIME" (ne s'activent que dans les
   régimes favorables).
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

import numpy as np
import polars as pl

from auriga.research.condition_tree import path_to_ast, simplify_ast
from auriga.research.labels import LabeledData, split_temporal
from auriga.research.path_extractor import extract_paths
from auriga.research.xgb_discovery import XGBConfig

logger = logging.getLogger(__name__)

# Seuil de probabilité de danger pour déclencher AVOID_SELL.
# La classe danger est rare (~2%) : un seuil bas (0.30) signale un danger
# RELATIF (le régime ressemble aux périodes passées de perte) — conservateur.
SELL_PROBA_THRESHOLD = 0.30


def _train_classifier(X_tr, y_tr, X_va, y_va, config: XGBConfig):
    """Entraîne un XGBClassifier (fallback XGBRegressor si échec).

    Classes très déséquilibrées (danger ~2%) → scale_pos_weight = négatifs /
    positifs pour que le modèle apprenne la classe minoritaire.
    """
    import xgboost as xgb

    n_pos = max(int(y_tr.sum()), 1)
    n_neg = max(len(y_tr) - n_pos, 1)
    scale_pos_weight = n_neg / n_pos

    try:
        params = {
            "n_estimators": config.n_estimators,
            "max_depth": config.max_depth,
            "learning_rate": config.learning_rate,
            "subsample": config.subsample,
            "colsample_bytree": config.colsample_bytree,
            "min_child_weight": config.min_child_weight,
            "reg_alpha": config.reg_alpha,
            "reg_lambda": config.reg_lambda,
            "random_state": config.random_state,
            "tree_method": config.tree_method,
            "n_jobs": config.n_jobs,
            "eval_metric": "aucpr",  # mieux que logloss pour classes déséquilibrées
            "scale_pos_weight": scale_pos_weight,
            "early_stopping_rounds": config.early_stopping_rounds,
        }
        model = xgb.XGBClassifier(**params)
        model.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], verbose=False)
        return model, "classifier"
    except Exception:
        # Fallback : régresseur sur le P&L court normalisé
        from auriga.research.xgb_discovery import train_xgb

        model, backend, _ = train_xgb_adapt(X_tr, y_tr, X_va, y_va, config)
        return model, "regressor"


def train_xgb_adapt(X_tr, y_tr, X_va, y_va, config: XGBConfig):
    """Version adaptée de train_xgb (données déjà découpées)."""
    import xgboost as xgb

    params = {
        "n_estimators": config.n_estimators,
        "max_depth": config.max_depth,
        "learning_rate": config.learning_rate,
        "subsample": config.subsample,
        "colsample_bytree": config.colsample_bytree,
        "min_child_weight": config.min_child_weight,
        "reg_alpha": config.reg_alpha,
        "reg_lambda": config.reg_lambda,
        "random_state": config.random_state,
        "tree_method": config.tree_method,
        "n_jobs": config.n_jobs,
        "eval_metric": "rmse",
        "objective": "reg:squarederror",
        "early_stopping_rounds": config.early_stopping_rounds,
    }
    model = xgb.XGBRegressor(**params)
    model.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], verbose=False)
    return model, "xgboost", {}


def build_sell_prime_labels(
    ohlcv: pl.DataFrame,
    X: np.ndarray,
    feature_names: list[str],
    horizon_bars: int,
    vol_window: int = 20,
    min_short_pnl: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Calcule le label 'vente de prime profitable' sur chaque barre.

    Pour chaque t : P&L d'un SHORT straddle ATM sur [t+1, t+H].
    y[t] = 1 si P&L > min_short_pnl (la vente aurait gagné), 0 sinon.

    Returns:
        (labels, valid_mask) — labels int8 {0, 1, -1=invalide}
    """
    from auriga.backtest.options_backtest import _vol_annualized, _vol_per_bar
    from auriga.options.pricing import black_scholes as bs

    close = ohlcv["close"].to_numpy().astype(np.float64)
    vol_pb = _vol_per_bar(close, vol_window)
    n = len(close)
    labels = np.full(n, -1, dtype=np.int8)
    valid = np.zeros(n, dtype=bool)

    BARS_PER_YEAR = 252 * 24
    MULT = 100
    VRP = 0.04
    K_mult = 1.00

    for t in range(vol_window, n - horizon_bars):
        S0 = close[t]
        vol_ann = _vol_annualized(vol_pb[t])
        if S0 <= 0 or vol_ann <= 0:
            continue
        T = horizon_bars / BARS_PER_YEAR
        K = S0 * K_mult
        iv = min(vol_ann + VRP, 3.0)
        call_p = bs(S0, K, T, sigma=iv, option_type="call").price
        put_p = bs(S0, K, T, sigma=iv, option_type="put").price
        prime = (call_p + put_p) * MULT

        # Sortie à l'échéance : le short straddle garde la prime, paie |S_T-K|
        S_T = close[t + horizon_bars]
        intrinsic = abs(S_T - K) * MULT
        pnl_short = prime - intrinsic  # profit du vendeur

        if prime > 1.0:
            # Le label cible les périodes DANGEREUSES pour la vente :
            # y=1 si le short straddle PERD (queue de risque) — c'est ce que
            # le modèle doit apprendre à ÉVITER. (98% des périodes sont
            # favorables à la vente — vendre tout le temps est la base ; le
            # ML sert à filtrer les ~2% de périodes à perte.)
            labels[t] = 1 if pnl_short <= min_short_pnl else 0
            valid[t] = True

    return labels, valid


def discover_sell_prime(
    ohlcv: pl.DataFrame,
    feats: pl.DataFrame,
    X: np.ndarray,
    feature_names: list[str],
    symbol: str,
    horizon_bars: int,
    horizon_label: str,
    config: XGBConfig | None = None,
    max_paths: int = 100,
    min_proba: float = SELL_PROBA_THRESHOLD,
) -> list[Any]:
    """Découverte complète A3 pour un (actif, horizon).

    Returns:
        liste d'Einhers direction='SELL_PRIME' (règles de régime favorable).
    """
    config = config or XGBConfig()

    # 1. Labels de vente profitable
    labels, valid = build_sell_prime_labels(
        ohlcv, X, feature_names, horizon_bars=horizon_bars
    )
    n_valid = int(valid.sum())
    if n_valid < 300:
        logger.warning("  %s: pas assez de barres valides pour A3 (%d)", symbol, n_valid)
        return []

    # 2. Masques temporels
    y_reg = labels.astype(np.float64)
    y_reg[~valid] = np.nan
    # Data bidon pour split : on passe par LabeledData avec y = labels
    data = LabeledData(
        X=X, y=y_reg, valid_mask=valid,
        feature_names=feature_names, horizon_bars=horizon_bars,
    )
    train_mask, val_mask, _ = split_temporal(data, embargo_bars=max(horizon_bars, 24))

    X_tr = X[train_mask & valid]
    y_tr = labels[train_mask & valid].astype(np.int8)
    X_va = X[val_mask & valid]
    y_va = labels[val_mask & valid].astype(np.int8)

    if len(X_tr) < 200 or len(X_va) < 50:
        logger.warning("  %s: trop peu d'échantillons A3 (%d train)", symbol, len(X_tr))
        return []

    # 3. Entraîner le classifieur
    model, kind = _train_classifier(X_tr, y_tr, X_va, y_va, config)
    logger.info(
        "A3 %s H=%d: %d train, %d val, %d%% labels positifs (%s)",
        symbol, horizon_bars, len(X_tr), len(X_va),
        int(100 * y_tr.mean()) if y_tr.size else 0, kind,
    )

    # 4. Extraire les règles des arbres (probabilité de "danger" > seuil)
    paths = extract_paths(model, "xgboost", feature_names, max_paths=max_paths)
    from auriga.types import Einher, EinherMetrics

    einhers: list[Any] = []
    for p in paths:
        if any(feat == "asset_id" for feat, _, _ in p.conditions):
            continue
        # En classification, le score de feuille est un log-odds.
        # proba = P(période DANGEREUSE). On garde les feuilles qui détectent
        # le danger → l'Einher AVOID_SELL sert de filtre : on ne vend pas
        # quand sa condition est vraie.
        proba = 1.0 / (1.0 + np.exp(-p.score)) if kind == "classifier" else p.score
        if proba < min_proba:
            continue
        try:
            ast = simplify_ast(path_to_ast(p))
        except ValueError:
            continue

        einher_id = (
            f"prime_{symbol}_{horizon_label}_{p.tree_idx:04d}_"
            f"{p.path_idx:04d}_{uuid.uuid4().hex[:6]}"
        )
        einhers.append(
            Einher(
                id=einher_id,
                condition=ast,
                direction="AVOID_SELL",
                amplitude=float(proba),
                symbol=symbol,
                timeframe="1H",
                horizon_bars=horizon_bars,
                source="xgboost:prime",
                metrics=EinherMetrics(n_trades=0),
                extra={"agent": "prime", "danger_proba": float(proba), "leaf_score": p.score},
            )
        )

    logger.info("A3 %s H=%d: %d règles AVOID_SELL", symbol, horizon_bars, len(einhers))
    return einhers