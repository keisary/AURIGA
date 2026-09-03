"""AURIGA - Signal de risque de volatilité (ex-Agent A2, transformé).

DÉCISION 2026-09-03 (Jovanny) : A2 ne produit PLUS de stratégies de trading
(l'achat de vol conditionnel simple ne bat pas la prime — mesuré sharpe
médian -2.64, conforme Ilmanen 2012). A2 devient un INDICATEUR DE RISQUE :

    VolSignal = P(choc de vol dans les H prochaines barres | features)

Ce signal est exploitable par :
1. Le Risk Engine : proba > seuil → gate 'vol_danger' bloque les nouvelles
   ventes de prime (A3) — c'est le rôle principal.
2. Le vendeur de prime : ne vendre QUE si vol_signal < seuil.
3. Le narratif LLM : le risque de vol du jour est expliqué au jury.

Label : y[t] = 1 si RV[t+H] > vol_mult × RV[t] (la vol explose), 0 sinon.
"""
from __future__ import annotations

import logging
import pickle
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import polars as pl

from auriga.features.engine import compute_features
from auriga.research.labels import split_temporal
from auriga.research.xgb_discovery import XGBConfig

logger = logging.getLogger(__name__)

VOL_MULT_DEFAULT = 1.5  # "choc" = vol × 1.5 sur l'horizon
DANGER_THRESHOLD = 0.35  # proba de choc au-delà de laquelle on bloque la vente
MODELS_DIR = Path("outputs/models")


@dataclass
class VolRiskOutput:
    """Sortie du signal de risque vol pour un actif."""

    symbol: str
    danger_proba: float  # proba courante de choc de vol (0-1)
    vol_level: str  # 'calme' | 'elevee' | 'danger'
    horizon_bars: int
    model_auc: float = 0.0


def _vol_per_bar(close: np.ndarray, window: int = 20) -> np.ndarray:
    """Vol réalisée per-barre (identique à la feature realized_vol_20)."""
    from auriga.features.quantitative import _numba_realized_volatility

    rets = np.full(len(close), np.nan, dtype=np.float64)
    if len(close) > 1:
        rets[1:] = close[1:] / close[:-1] - 1.0
    return np.asarray(_numba_realized_volatility(rets, window), dtype=np.float64)


def build_danger_labels(
    close: np.ndarray,
    horizon_bars: int,
    vol_mult: float = VOL_MULT_DEFAULT,
    vol_window: int = 20,
) -> tuple[np.ndarray, np.ndarray]:
    """Label de choc de vol : y[t] = 1 si RV[t+H] > vol_mult × RV[t].

    Returns:
        (labels int8 {-1=invalide, 0, 1}, valid_mask bool)
    """
    n = len(close)
    rv = _vol_per_bar(close, vol_window)
    labels = np.full(n, -1, dtype=np.int8)
    valid = np.zeros(n, dtype=bool)

    for t in range(vol_window, n - horizon_bars):
        rv_t = rv[t]
        rv_future = rv[t + horizon_bars]
        if np.isnan(rv_t) or np.isnan(rv_future) or rv_t <= 1e-12:
            continue
        labels[t] = 1 if rv_future > vol_mult * rv_t else 0
        valid[t] = True
    return labels, valid


def train_danger_model(
    ohlcv: pl.DataFrame,
    feature_frame: pl.DataFrame,
    horizon_bars: int,
    config: XGBConfig | None = None,
    vol_mult: float = VOL_MULT_DEFAULT,
    symbol: str = "",
) -> tuple[object, float, list[str]]:
    """Entraîne le classifieur de danger vol.

    Returns:
        (model, auc_val, feature_names)
    """
    import xgboost as xgb
    from sklearn.metrics import roc_auc_score

    config = config or XGBConfig()
    close = ohlcv["close"].to_numpy().astype(np.float64)
    labels, valid = build_danger_labels(close, horizon_bars, vol_mult=vol_mult)

    feature_names = [c for c in feature_frame.columns if c != "timestamp"]
    X = feature_frame.select(feature_names).to_numpy().astype(np.float32)

    # Split temporel (réutilise la mécanique LabeledData)
    from auriga.research.labels import LabeledData

    y_reg = labels.astype(np.float64)
    y_reg[~valid] = np.nan
    data = LabeledData(X=X, y=y_reg, valid_mask=valid,
                       feature_names=feature_names, horizon_bars=horizon_bars)
    train_mask, val_mask, _ = split_temporal(data, embargo_bars=max(horizon_bars, 24))

    X_tr = X[train_mask & valid]
    y_tr = labels[train_mask & valid]
    X_va = X[val_mask & valid]
    y_va = labels[val_mask & valid]

    if len(X_tr) < 300 or len(X_va) < 50 or y_tr.sum() < 10:
        logger.warning("  %s: données insuffisantes pour vol_signal", symbol)
        raise ValueError("Pas assez de données pour entraîner le signal vol")

    n_pos = max(int(y_tr.sum()), 1)
    n_neg = max(len(y_tr) - n_pos, 1)
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
        "eval_metric": "aucpr",
        "scale_pos_weight": n_neg / n_pos,
        "early_stopping_rounds": config.early_stopping_rounds,
    }
    model = xgb.XGBClassifier(**params)
    model.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], verbose=False)

    auc = 0.0
    if len(X_va) > 10 and y_va.sum() > 0 and (y_va == 0).sum() > 0:
        try:
            proba_va = model.predict_proba(X_va)[:, 1]
            auc = float(roc_auc_score(y_va, proba_va))
        except Exception:
            auc = 0.0

    logger.info(
        "VolSignal %s H=%d: %d train (%d%% danger), %d val, AUC=%.3f",
        symbol, horizon_bars, len(X_tr), int(100 * y_tr.mean()), len(X_va), auc,
    )
    return model, auc, feature_names


class VolRiskEngine:
    """Moteur de signal de risque vol : score temps réel par actif.

    Modèles entraînés par actif + horizon, persistés dans outputs/models/.
    """

    def __init__(self, horizon_bars: int = 24, threshold: float = DANGER_THRESHOLD):
        self.horizon_bars = horizon_bars
        self.threshold = threshold
        self._models: dict[str, tuple[object, float]] = {}  # symbol -> (model, auc)

    # ------------------------------------------------------------------
    def _model_path(self, symbol: str) -> Path:
        return MODELS_DIR / f"volsignal_{symbol}_H{self.horizon_bars}.pkl"

    def train_and_save(self, symbol: str, ohlcv: pl.DataFrame, feature_frame: pl.DataFrame) -> float:
        """Entraîne le modèle vol_signal d'un actif et le persiste. Retourne AUC."""
        try:
            model, auc, _ = train_danger_model(
                ohlcv, feature_frame, self.horizon_bars, symbol=symbol
            )
            MODELS_DIR.mkdir(parents=True, exist_ok=True)
            with open(self._model_path(symbol), "wb") as f:
                pickle.dump({"model": model, "auc": auc, "horizon": self.horizon_bars}, f)
            self._models[symbol] = (model, auc)
            return auc
        except Exception as e:
            logger.warning("  vol_signal %s: échec (%s)", symbol, e)
            return 0.0

    def load(self, symbol: str) -> bool:
        """Charge un modèle persisté. Retourne True si OK."""
        path = self._model_path(symbol)
        if not path.exists():
            return False
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            self._models[symbol] = (data["model"], data.get("auc", 0.0))
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    def score_recent(self, symbol: str, recent_bars: pl.DataFrame) -> VolRiskOutput | None:
        """Score le danger vol courant à partir des dernières barres.

        Retourne None si le modèle n'est pas dispo ou données insuffisantes.
        """
        entry = self._models.get(symbol)
        if entry is None:
            if not self.load(symbol):
                return None
            entry = self._models.get(symbol)
        if entry is None:
            return None
        model, auc = entry

        try:
            feats = compute_features(recent_bars, "1H")
            feature_names = [c for c in feats.columns if c != "timestamp"]
            X = feats.select(feature_names).to_numpy().astype(np.float32)
            if X.shape[0] < 50:
                return None
            proba = float(model.predict_proba(X[-1:, :])[0, 1])
        except Exception as e:
            logger.debug("score_recent %s: %s", symbol, e)
            return None

        if proba >= self.threshold:
            level = "danger"
        elif proba >= self.threshold * 0.6:
            level = "elevee"
        else:
            level = "calme"

        return VolRiskOutput(
            symbol=symbol,
            danger_proba=round(proba, 4),
            vol_level=level,
            horizon_bars=self.horizon_bars,
            model_auc=round(auc, 3),
        )

    # ------------------------------------------------------------------
    def is_danger(self, symbol: str, recent_bars: pl.DataFrame) -> tuple[bool, VolRiskOutput | None]:
        """True si le risque vol bloque les ventes de prime sur cet actif.

        FAIL-CLOSED : modèle absent / données insuffisantes → bloquer
        (vol_level='unknown' traité comme danger par l'appelant).
        """
        out = self.score_recent(symbol, recent_bars)
        if out is None:
            return True, VolRiskOutput(
                symbol=symbol, danger_proba=1.0, vol_level="unknown",
                horizon_bars=self.horizon_bars,
            )
        return out.vol_level in ("danger", "unknown"), out

    def is_danger_from_features(
        self, symbol: str, feats_recent: pl.DataFrame
    ) -> tuple[bool, VolRiskOutput | None]:
        """Score le danger vol depuis des features DÉJÀ calculées (optimisation).

        FAIL-CLOSED (revue 2026-09-03) : si le modèle est absent ou les
        données insuffisantes, on retourne un niveau 'unknown' qui DOIT
        bloquer la vente de prime (on ne vend pas sans pouvoir évaluer le
        risque vol). L'appelant traite 'unknown' comme un blocage.
        """
        entry = self._models.get(symbol)
        if entry is None:
            if not self.load(symbol):
                return True, VolRiskOutput(
                    symbol=symbol, danger_proba=1.0, vol_level="unknown",
                    horizon_bars=self.horizon_bars,
                )
            entry = self._models.get(symbol)
        if entry is None:
            return True, VolRiskOutput(
                symbol=symbol, danger_proba=1.0, vol_level="unknown",
                horizon_bars=self.horizon_bars,
            )
        model, auc = entry

        try:
            feature_names = [c for c in feats_recent.columns if c != "timestamp"]
            X = feats_recent.select(feature_names).to_numpy().astype(np.float32)
            if X.shape[0] < 50:
                return True, VolRiskOutput(
                    symbol=symbol, danger_proba=1.0, vol_level="unknown",
                    horizon_bars=self.horizon_bars,
                )
            proba = float(model.predict_proba(X[-1:, :])[0, 1])
        except Exception as e:
            logger.warning("Signal vol %s INOPÉRANT → blocage: %s", symbol, e)
            return True, VolRiskOutput(
                symbol=symbol, danger_proba=1.0, vol_level="unknown",
                horizon_bars=self.horizon_bars,
            )

        if proba >= self.threshold:
            level = "danger"
        elif proba >= self.threshold * 0.6:
            level = "elevee"
        else:
            level = "calme"

        out = VolRiskOutput(
            symbol=symbol,
            danger_proba=round(proba, 4),
            vol_level=level,
            horizon_bars=self.horizon_bars,
            model_auc=round(auc, 3),
        )
        # 'unknown' n'apparaît que via les retours anticipés (déjà True) ;
        # ici le modèle a répondu : danger uniquement si niveau danger.
        return level == "danger", out