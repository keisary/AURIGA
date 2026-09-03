"""AURIGA - LEGACY : découverte de stratégies de VOLATILITÉ (ex-Agent A2).

⚠️ REMPLACÉ le 2026-09-03 : A2 est devenu un signal de risque (VolRiskEngine
dans risk/vol_signal.py). Ce module est conservé pour référence/historique
et pour les tests de recherche, mais il n'est PLUS appelé par le pipeline.

La mesure qui a motivé le changement : les straddles longs (achat de vol)
sont globalement perdants (sharpe médian -2.64, conforme Ilmanen 2012).
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from auriga.research.condition_tree import path_to_ast, simplify_ast
from auriga.research.labels import LabeledData, build_vol_future, split_temporal
from auriga.research.path_extractor import extract_paths
from auriga.research.xgb_discovery import XGBConfig, train_xgb
from auriga.types import Einher, EinherMetrics

logger = logging.getLogger(__name__)

# Seuil de |score| de feuille (Y_vol est un ratio, ~0.1-0.3 = choc significatif)
MIN_ABS_SCORE_VOL = 0.05


def build_vol_labeled(
    ohlcv,
    feature_frame,
    horizon_bars: int,
    feature_names: list[str] | None = None,
    vol_window: int = 20,
) -> LabeledData:
    """Construit un LabeledData dont le label est Y_vol (vol future signée)."""
    from auriga.research.labels import build_labels_from_frame

    close = ohlcv["close"].to_numpy().astype(np.float64)
    y_vol = build_vol_future(close, horizon_bars, vol_window=vol_window)

    if feature_names is None:
        feature_names = [c for c in feature_frame.columns if c != "timestamp"]
    else:
        feature_names = [f for f in feature_names if f in feature_frame.columns]

    X = feature_frame.select(feature_names).to_numpy().astype(np.float32)
    n = X.shape[0]

    valid = ~np.isnan(y_vol)
    finite_ratio = np.isfinite(X).mean(axis=1)
    valid &= finite_ratio >= 0.5

    return LabeledData(
        X=X, y=y_vol, valid_mask=valid,
        feature_names=feature_names, horizon_bars=horizon_bars,
    )


def build_vol_einhers_from_model(
    model: Any,
    backend: str,
    data: LabeledData,
    symbol: str,
    horizon_bars: int,
    horizon_label: str,
    max_paths: int = 200,
    min_abs_score: float = MIN_ABS_SCORE_VOL,
    source: str = "xgboost:vol",
) -> list[Einher]:
    """Construit les Einhers VOL depuis un modèle entraîné sur Y_vol."""
    paths = extract_paths(model, backend, data.feature_names, max_paths=max_paths)

    einhers: list[Einher] = []
    for p in paths:
        if any(feat == "asset_id" for feat, _, _ in p.conditions):
            continue
        if abs(p.score) < min_abs_score:
            continue
        direction = "VOL_UP" if p.score > 0 else "VOL_DOWN"

        try:
            ast = simplify_ast(path_to_ast(p))
        except ValueError:
            continue

        einher_id = (
            f"vol_{symbol}_{horizon_label}_{p.tree_idx:04d}_"
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
                "agent": "vol",
                "leaf_score": p.score,
                "n_conditions": len(p.conditions),
            },
        )
        einhers.append(einher)
    return einhers


def discover_vol_asset(
    data: LabeledData,
    symbol: str,
    horizon_bars: int,
    horizon_label: str,
    config: XGBConfig | None = None,
    max_paths: int = 100,
) -> list[Einher]:
    """Découverte vol complète pour un (actif, horizon)."""
    config = config or XGBConfig()
    embargo = max(horizon_bars, 24)
    train_mask, val_mask, _ = split_temporal(data, embargo_bars=embargo)

    n_train = int(train_mask.sum())
    n_val = int(val_mask.sum())
    if n_train < 100 or n_val < 20:
        return []

    model, backend, importances = train_xgb(data, train_mask, val_mask, config, symbol=symbol)
    einhers = build_vol_einhers_from_model(
        model, backend, data, symbol, horizon_bars, horizon_label,
        max_paths=max_paths, source="xgboost:vol",
    )
    logger.info(
        "VOL XGB %s H=%d: train=%d val=%d, %d einhers vol candidats",
        symbol, horizon_bars, n_train, n_val, len(einhers),
    )
    return einhers