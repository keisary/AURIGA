"""AURIGA - Découverte de stratégies par XGBoost (adapté d'einherjar).

Pipeline :
1. Pour chaque (actif, horizon) : entraîne un XGBRegressor sur les features,
   cible = rendement futur (Y_ret).
2. Extrait les chemins des arbres → règles candidates (Einhers).
3. Pool : un modèle unique sur tous les actifs concaténés (avec asset_id).

La direction vien du signe du score de la feuille :
- score > +min_abs_score → LONG
- score < -min_abs_score → SHORT
- sinon → skip (signal trop faible)

TP/SL en multiple d'ATR (anti-tautologie : jamais basé sur Y_ret prédit).
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from auriga.research.condition_tree import path_to_ast, simplify_ast
from auriga.research.labels import LabeledData, split_temporal
from auriga.research.path_extractor import extract_paths
from auriga.types import Condition, ConditionNode, Einher, EinherMetrics

logger = logging.getLogger(__name__)

# Seuil minimum de |score| de feuille pour assigner LONG/SHORT
MIN_ABS_SCORE_FOR_DIRECTION = 0.0005


@dataclass
class XGBConfig:
    """Hyperparamètres XGBoost pour AURIGA (1H, large caps)."""

    n_estimators: int = 200
    max_depth: int = 3  # calibré 2026-09-02 (test AAPL): depth=4 -> regles trop
    # restrictives (25 trades moy), depth=2 -> trop simples (0 admis).
    # depth=3 = sweet spot (40 trades moy, admis possibles).
    learning_rate: float = 0.05
    subsample: float = 0.8
    colsample_bytree: float = 0.6
    min_child_weight: int = 10
    reg_alpha: float = 0.1
    reg_lambda: float = 1.0
    random_state: int = 42
    tree_method: str = "hist"
    n_jobs: int = 1  # anti oversubscription (leçon einherjar)
    early_stopping_rounds: int = 20


@dataclass
class DiscoveryResult:
    """Résultat de la découverte pour un (modèle, horizon)."""

    horizon_bars: int
    einhers: list[Einher] = field(default_factory=list)
    n_paths_extracted: int = 0
    model_info: dict[str, Any] = field(default_factory=dict)


def _get_model_backend() -> tuple[Any, str]:
    """Retourne (module xgboost, 'xgboost') ou (None, 'sklearn')."""
    try:
        import xgboost

        return xgboost, "xgboost"
    except ImportError:
        return None, "sklearn"


def train_xgb(
    data: LabeledData,
    train_mask: np.ndarray,
    val_mask: np.ndarray,
    config: XGBConfig | None = None,
    symbol: str | None = None,
) -> tuple[Any, str, dict[str, float]]:
    """Entraîne un XGBRegressor sur les données labellisées.

    Returns:
        (model, backend, importances) — importances par feature (gain).
    """
    config = config or XGBConfig()
    xgb_mod, backend = _get_model_backend()

    X_tr = data.X[train_mask]
    y_tr = data.y[train_mask]
    X_va = data.X[val_mask]
    y_va = data.y[val_mask]

    if len(X_tr) < 100 or len(X_va) < 20:
        raise ValueError(
            f"Données insuffisantes train={len(X_tr)} val={len(X_va)} "
            f"pour {symbol or 'pool'}"
        )

    if backend == "xgboost":
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
        model = xgb_mod.XGBRegressor(**params)
        model.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], verbose=False)

        booster = model.get_booster()
        raw_imp = booster.get_score(importance_type="gain")
        importances = {data.feature_names[i]: float(raw_imp.get(f"f{i}", 0.0)) for i in range(len(data.feature_names))}
    else:
        from sklearn.ensemble import GradientBoostingRegressor

        model = GradientBoostingRegressor(
            n_estimators=config.n_estimators,
            max_depth=config.max_depth,
            learning_rate=config.learning_rate,
            subsample=config.subsample,
            random_state=config.random_state,
        )
        model.fit(X_tr, y_tr)
        importances = {
            data.feature_names[i]: float(model.feature_importances_[i])
            for i in range(len(data.feature_names))
        }

    importances = dict(sorted(importances.items(), key=lambda x: x[1], reverse=True))
    return model, backend, importances


def build_einhers_from_model(
    model: Any,
    backend: str,
    data: LabeledData,
    symbol: str,
    horizon_bars: int,
    horizon_label: str,
    max_paths: int = 200,
    min_abs_score: float = MIN_ABS_SCORE_FOR_DIRECTION,
    source: str = "xgboost",
) -> list[Einher]:
    """Construit les Einhers candidats depuis un modèle entraîné.

    Chaque chemin d'arbre devient une règle candidate (Einher).
    Le backtest/validation se fera ensuite (module backtest).
    """
    paths = extract_paths(model, backend, data.feature_names, max_paths=max_paths)

    einhers: list[Einher] = []
    for p in paths:
        if abs(p.score) < min_abs_score:
            continue
        direction = "LONG" if p.score > 0 else "SHORT"

        try:
            ast = simplify_ast(path_to_ast(p))
        except ValueError:
            continue

        einher_id = (
            f"xgb_{symbol}_{horizon_label}_{p.tree_idx:04d}_"
            f"{p.path_idx:04d}_{uuid.uuid4().hex[:6]}"
        )
        einher = Einher(
            id=einher_id,
            condition=ast,
            direction=direction,
            amplitude=abs(p.score),
            symbol=symbol,
            timeframe="1H",
            horizon_bars=horizon_bars,
            source=source,
            metrics=EinherMetrics(n_trades=0),
            extra={
                "tree_idx": p.tree_idx,
                "path_idx": p.path_idx,
                "leaf_score": p.score,
                "n_conditions": len(p.conditions),
            },
        )
        einhers.append(einher)

    return einhers


def discover_single_asset(
    data: LabeledData,
    symbol: str,
    horizon_bars: int,
    horizon_label: str,
    config: XGBConfig | None = None,
    max_paths: int = 200,
    train_ratio: float = 0.6,
    val_ratio: float = 0.2,
) -> DiscoveryResult:
    """Découverte complète pour un (actif, horizon) : train + extraction."""
    config = config or XGBConfig()
    embargo = max(horizon_bars, 24)  # anti-fuite : embargo >= horizon

    train_mask, val_mask, _ = split_temporal(
        data, train_ratio=train_ratio, val_ratio=val_ratio, embargo_bars=embargo
    )
    n_train = int(train_mask.sum())
    n_val = int(val_mask.sum())
    if n_train < 100 or n_val < 20:
        return DiscoveryResult(horizon_bars=horizon_bars)

    model, backend, importances = train_xgb(
        data, train_mask, val_mask, config, symbol=symbol
    )
    einhers = build_einhers_from_model(
        model, backend, data, symbol, horizon_bars, horizon_label,
        max_paths=max_paths, source=f"xgboost:{symbol}",
    )
    logger.info(
        "XGB %s H=%d: train=%d val=%d, %d chemins, %d einhers candidats",
        symbol, horizon_bars, n_train, n_val, len(einhers), len(einhers),
    )
    return DiscoveryResult(
        horizon_bars=horizon_bars,
        einhers=einhers,
        n_paths_extracted=len(einhers),
        model_info={"backend": backend, "importances": importances},
    )


def discover_pool(
    labeled_by_symbol: dict[str, LabeledData],
    horizon_bars: int,
    horizon_label: str,
    config: XGBConfig | None = None,
    max_paths: int = 300,
) -> DiscoveryResult:
    """Découverte sur le pool de tous les actifs (un modèle unique).

    Le pool ajoute une colonne asset_id (fabriquée par pool_assets dans labels.py).
    Les Einhers poolés sont taggés avec leur actif statistiquement dominant ?
    NON : un Einher poolé est UNIVERSEL (s'applique à tous les actifs du pool).
    """
    from auriga.research.labels import pool_assets

    feature_names = list(labeled_by_symbol.values())[0].feature_names
    data = pool_assets(labeled_by_symbol, feature_names)
    if data is None:
        return DiscoveryResult(horizon_bars=horizon_bars)

    config = config or XGBConfig()
    embargo = max(horizon_bars, 24)
    train_mask, val_mask, _ = split_temporal(data, embargo_bars=embargo)

    n_train = int(train_mask.sum())
    n_val = int(val_mask.sum())
    if n_train < 100 or n_val < 20:
        return DiscoveryResult(horizon_bars=horizon_bars)

    model, backend, importances = train_xgb(data, train_mask, val_mask, config, symbol="POOL")
    einhers = build_einhers_from_model(
        model, backend, data, symbol="POOL", horizon_bars=horizon_bars,
        horizon_label=horizon_label, max_paths=max_paths,
        source=f"xgboost:pool",
    )
    logger.info(
        "XGB POOL H=%d: train=%d val=%d, %d einhers candidats",
        horizon_bars, n_train, n_val, len(einhers),
    )
    return DiscoveryResult(
        horizon_bars=horizon_bars,
        einhers=einhers,
        n_paths_extracted=len(einhers),
        model_info={"backend": backend, "importances": importances},
    )