"""AURIGA - Construction des labels supervisés (Y_ret) et splits temporels.

IMPORTANT : contrairement à einherjar qui chargeait Y_ret depuis les .npy
de midasV3, ici on CALCULE le label depuis les prix Alpaca :

    Y_ret[t] = close[t + H] / close[t] - 1     (rendement futur sur horizon H)

Règles anti-fuite :
- Y_ret est le LABEL, jamais une feature.
- Les features n'utilisent que le passé (fenêtres roulantes closes à t).
- L'embargo entre train/val/holdout est >= horizon (les labels du train
  regardent le futur proche, ils ne doivent pas déborder dans la val).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import polars as pl


@dataclass
class LabeledData:
    """Données avec labels et splits prêts pour XGBoost."""

    X: np.ndarray          # (N, F) features (float32)
    y: np.ndarray          # (N,) rendement futur (label)
    valid_mask: np.ndarray  # (N,) bool — lignes avec label valide
    feature_names: list[str]
    horizon_bars: int


def build_y_future(close: np.ndarray, horizon_bars: int) -> np.ndarray:
    """Calcule Y_ret[t] = close[t+H]/close[t] - 1.

    Les H dernières lignes n'ont pas de futur → NaN (seront masquées).
    """
    close = np.asarray(close, dtype=np.float64)
    n = len(close)
    y = np.full(n, np.nan, dtype=np.float64)
    if n > horizon_bars:
        y[: n - horizon_bars] = close[horizon_bars:] / close[: n - horizon_bars] - 1.0
    return y


def build_vol_future(close: np.ndarray, horizon_bars: int, vol_window: int = 20) -> np.ndarray:
    """Calcule le label de VOLATILITÉ future signé.

    Y_vol[t] = RV[t+H] / RV[t] - 1  où RV = vol réalisée (rolling window).

    Positif → la volatilité va AUGMENTER (achat de vol / long straddle).
    Négatif → la volatilité va DIMINUER (vente de vol / credit spread).
    """
    from auriga.features.quantitative import _numba_realized_volatility as _rv_fn

    close = np.asarray(close, dtype=np.float64)
    n = len(close)
    rets = np.full(n, np.nan, dtype=np.float64)
    if n > 1:
        rets[1:] = close[1:] / close[:-1] - 1.0
    rv = np.asarray(_rv_fn(rets, vol_window), dtype=np.float64)

    y = np.full(n, np.nan, dtype=np.float64)
    for t in range(n - horizon_bars):
        rv_t = rv[t]
        rv_future = rv[t + horizon_bars]
        if rv_t is not None and not np.isnan(rv_t) and rv_t > 1e-12 and not np.isnan(rv_future):
            y[t] = rv_future / rv_t - 1.0
    return y


def build_labels_from_frame(
    ohlcv: pl.DataFrame,
    feature_frame: pl.DataFrame,
    feature_names: list[str] | None = None,
    horizon_bars: int = 24,
) -> LabeledData:
    """Assemble X (features) + y (rendement futur) pour un actif.

    Args:
        ohlcv : bars [timestamp, open, high, low, close, volume]
        feature_frame : sortie de compute_features (timestamp + features)
        feature_names : colonnes features à utiliser (défaut = tout sauf timestamp)
        horizon_bars : horizon de prédiction en barres

    Returns:
        LabeledData (les lignes sans label valide sont masquées par valid_mask).
    """
    close = ohlcv["close"].to_numpy().astype(np.float64)
    y = build_y_future(close, horizon_bars)

    if feature_names is None:
        feature_names = [c for c in feature_frame.columns if c != "timestamp"]
    else:
        feature_names = [f for f in feature_names if f in feature_frame.columns]

    X = feature_frame.select(feature_names).to_numpy().astype(np.float32)

    valid = ~np.isnan(y)
    # Lignes où une feature est NaN (warmup des fenêtres roulantes) → invalides
    # MAIS pas toutes : une seule feature longue-fenêtre (hurst_252) rendrait
    # les 252 premières lignes invalides. On garde les lignes où >= 50% des
    # features sont finies (les NaN restants seront gérés par XGBoost).
    finite_ratio = np.isfinite(X).mean(axis=1)
    valid &= finite_ratio >= 0.5

    return LabeledData(
        X=X,
        y=y,
        valid_mask=valid,
        feature_names=feature_names,
        horizon_bars=horizon_bars,
    )


def split_temporal(
    data: LabeledData,
    train_ratio: float = 0.6,
    val_ratio: float = 0.2,
    embargo_bars: int = 0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Split temporel 60/20/20 avec embargo entre les fenêtres.

    Returns:
        (train_mask, val_mask, holdout_mask) — bool sur les lignes.
    """
    n = data.X.shape[0]
    # Seuls les indices valides sont splitables
    valid_idx = np.where(data.valid_mask)[0]
    n_valid = len(valid_idx)

    if n_valid < 50:
        # Trop peu de données : tout en train, val/holdout vides
        train_mask = data.valid_mask.copy()
        return train_mask, np.zeros(n, dtype=bool), np.zeros(n, dtype=bool)

    n_train = int(round(n_valid * train_ratio))
    n_val = int(round(n_valid * val_ratio))

    idx_train = valid_idx[:n_train]
    idx_val = valid_idx[n_train : n_train + n_val]
    idx_holdout = valid_idx[n_train + n_val :]

    # Embargo : retire les `embargo_bars` premières lignes de val/holdout
    # (les labels du train voient le futur proche qui chevauche le début val).
    if embargo_bars > 0:
        idx_val = idx_val[embargo_bars:] if len(idx_val) > embargo_bars else idx_val[:0]
        idx_holdout = idx_holdout[embargo_bars:] if len(idx_holdout) > embargo_bars else idx_holdout[:0]

    train_mask = np.zeros(n, dtype=bool)
    val_mask = np.zeros(n, dtype=bool)
    holdout_mask = np.zeros(n, dtype=bool)
    train_mask[idx_train] = True
    val_mask[idx_val] = True
    holdout_mask[idx_holdout] = True
    return train_mask, val_mask, holdout_mask


def pool_assets(
    labeled_by_symbol: dict[str, LabeledData],
    feature_names: list[str],
) -> LabeledData | None:
    """Concatène plusieurs actifs en un dataset poolé.

    Ajoute une colonne 'asset_id' au début de X pour que le modèle
    puisse distinguer l'origine de chaque ligne.

    Returns:
        LabeledData poolé, ou None si aucun actif valide.
    """
    xs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    masks: list[np.ndarray] = []

    for i, (sym, ld) in enumerate(labeled_by_symbol.items()):
        n = ld.X.shape[0]
        asset_id = np.full((n, 1), i, dtype=np.float32)
        xs.append(np.hstack([asset_id, ld.X]))
        ys.append(ld.y)
        masks.append(ld.valid_mask)

    if not xs:
        return None

    X_pool = np.vstack(xs).astype(np.float32)
    y_pool = np.concatenate(ys)
    mask_pool = np.concatenate(masks)

    return LabeledData(
        X=X_pool,
        y=y_pool,
        valid_mask=mask_pool,
        feature_names=["asset_id"] + feature_names,
        horizon_bars=list(labeled_by_symbol.values())[0].horizon_bars,
    )
