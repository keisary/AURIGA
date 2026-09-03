"""AURIGA - Runner de recherche : orchestration de la découverte XGBoost.

Pour chaque horizon (6h, 24h, 48h) :
1. Charge les bars de chaque actif (cache parquet).
2. Calcule les features (compute_features).
3. Construit les labels Y_ret + split.
4. Découverte par actif (1 modèle par actif).
5. Découverte poolée (1 modèle sur tous les actifs).
6. Persiste tous les Einhers candidats dans outputs/research/candidates_<horizon>.jsonl.

Le backtest/admission viendra ensuite (module backtest).
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import polars as pl

from auriga.data.cache import load_cached_bars
from auriga.data.market_data import download_universe
from auriga.features.engine import compute_features
from auriga.research.labels import build_labels_from_frame
from auriga.research.xgb_discovery import (
    XGBConfig,
    discover_pool,
    discover_single_asset,
)
from auriga.utils.config import get_config
from auriga.utils.universe import load_universe

logger = logging.getLogger(__name__)

# Nom de l'horizon (dans le nom de fichier)
HORIZON_LABELS = {6: "6h", 24: "24h", 48: "48h"}


def load_or_download(symbols: list[str], timeframe: str = "1H") -> dict[str, pl.DataFrame]:
    """Charge les bars depuis le cache ; télécharge les absents."""
    missing = [s for s in symbols if load_cached_bars(s, timeframe) is None]
    if missing:
        logger.info("Téléchargement des %d actifs manquants ...", len(missing))
        download_universe(missing, timeframe)
    return {s: load_cached_bars(s, timeframe) for s in symbols if load_cached_bars(s, timeframe) is not None}


def run_research(
    symbols: list[str] | None = None,
    horizons_bars: list[int] | None = None,
    output_dir: Path | str | None = None,
    config: XGBConfig | None = None,
    enable_pool: bool = True,
) -> dict[str, Any]:
    """Lance la recherche XGBoost sur l'univers.

    Returns:
        Résumé : {par_horizon: {...}, total_candidates: int, duree_s: float}
    """
    cfg = get_config()
    universe = load_universe()
    symbols = symbols or universe["symbols"]
    horizons_bars = horizons_bars or cfg.research.get("horizons_hours", [6, 24, 48])
    config = config or XGBConfig()

    if output_dir is None:
        output_dir = Path("outputs/research")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    t_start = time.time()
    summary: dict[str, Any] = {"par_horizon": {}, "total_candidates": 0}

    # Charger toutes les données une seule fois
    logger.info("Chargement des bars 1H pour %d actifs ...", len(symbols))
    bars_by_symbol = load_or_download(symbols, "1H")

    for hz in horizons_bars:
        hz_label = HORIZON_LABELS.get(hz, f"{hz}h")
        t_hz = time.time()
        logger.info("=== Recherche XGBoost H=%d (%s) ===", hz, hz_label)

        labeled_by_symbol: dict[str, Any] = {}
        einhers_all: list[Any] = []

        for sym in symbols:
            ohlcv = bars_by_symbol.get(sym)
            if ohlcv is None or ohlcv.height < 500:
                logger.warning("  %s: données insuffisantes, skip", sym)
                continue
            try:
                feats = compute_features(ohlcv, "1H")
                data = build_labels_from_frame(ohlcv, feats, horizon_bars=hz)
                if int(data.valid_mask.sum()) < 200:
                    logger.warning("  %s: trop peu de lignes valides, skip", sym)
                    continue
                labeled_by_symbol[sym] = data
            except Exception as e:
                logger.warning("  %s: échec features/labels (%s)", sym, e)
                continue

        # 1. Modèles par actif
        for sym, data in labeled_by_symbol.items():
            try:
                res = discover_single_asset(
                    data, sym, hz, hz_label, config=config, max_paths=100
                )
                einhers_all.extend(res.einhers)
                logger.info("  %s: %d einhers", sym, len(res.einhers))
            except Exception as e:
                logger.warning("  %s: échec découverte (%s)", sym, e)

        # 2. Modèle poolé
        if enable_pool and labeled_by_symbol:
            try:
                res_pool = discover_pool(
                    labeled_by_symbol, hz, hz_label, config=config, max_paths=300
                )
                einhers_all.extend(res_pool.einhers)
                logger.info("  POOL: %d einhers", len(res_pool.einhers))
            except Exception as e:
                logger.warning("  POOL: échec découverte (%s)", e)

        # 3. Persistance
        out_file = output_dir / f"candidates_{hz_label}.jsonl"
        with open(out_file, "w", encoding="utf-8") as f:
            for ein in einhers_all:
                f.write(json.dumps(ein.to_dict(), ensure_ascii=False, default=str) + "\n")

        summary["par_horizon"][hz_label] = {
            "horizon_bars": hz,
            "n_candidates": len(einhers_all),
            "fichier": str(out_file),
            "duree_s": round(time.time() - t_hz, 1),
        }
        summary["total_candidates"] += len(einhers_all)
        logger.info("H=%d : %d candidats -> %s (%.0fs)", hz, len(einhers_all), out_file, time.time() - t_hz)

    summary["duree_s"] = round(time.time() - t_start, 1)
    logger.info("Recherche terminée : %d candidats en %.0fs", summary["total_candidates"], summary["duree_s"])
    return summary
