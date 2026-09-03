"""AURIGA - Pipeline principal (module ORC).

Deux modes d'exécution (décision Jovanny 2026-09-02) :

1. MODE RECHERCHE (`run_research_mode`) : cycle complet de découverte
   data → features → XGBoost → backtest val → admission → sélection.
   N'exécute AUCUN ordre. Produit un portefeuille candidat + rapport.

2. MODE TRADING (`run_trading_mode`) : reprend le portefeuille de la
   recherche, vérifie les signaux ACTUELS (dernières barres), construit
   les spreads, passe les risk gates et exécute en paper. Produit le
   narratif quotidien.

`run_full()` enchaîne les deux.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import polars as pl

from auriga.features.engine import compute_features
from auriga.orchestration.state import StateStore, TrackedPosition
from auriga.research.labels import build_labels_from_frame, split_temporal
from auriga.research.runner import load_or_download
from auriga.research.xgb_discovery import XGBConfig, discover_pool, discover_single_asset
from auriga.utils.config import get_config
from auriga.utils.universe import load_universe

logger = logging.getLogger(__name__)


def run_research_mode(
    symbols: list[str] | None = None,
    horizons_bars: list[int] | None = None,
    max_paths_per_model: int = 60,
    output_dir: Path | str | None = None,
) -> dict[str, Any]:
    """MODE RECHERCHE : découvre, backteste, admet, sélectionne. Aucun ordre.

    Returns:
        Résumé {candidates, admitted, portfolio, fichiers...}
    """
    from auriga.backtest.backtester import backtest_einher
    from auriga.selection.portfolio import build_portfolio, default_portfolio_config

    cfg = get_config()
    universe = load_universe()
    symbols = symbols or universe["symbols"]
    horizons_bars = horizons_bars or cfg.research.get("horizons_hours", [6, 24, 48])
    output_dir = Path(output_dir or Path("outputs/research"))
    output_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    logger.info("=== MODE RECHERCHE : %d actifs, horizons %s ===", len(symbols), horizons_bars)

    # 1. Données
    bars = load_or_download(symbols, "1H")
    logger.info("Bars chargées: %d actifs", len(bars))

    # 2. Pour chaque horizon : découvrir + backtester + admettre
    all_admitted: list[Any] = []
    summary_per_horizon: dict[str, Any] = {}

    for hz in horizons_bars:
        hz_label = f"{hz}h"
        logger.info("--- Horizon %s ---", hz_label)
        labeled = {}
        for sym, ohlcv in bars.items():
            try:
                feats = compute_features(ohlcv, "1H")
                data = build_labels_from_frame(ohlcv, feats, horizon_bars=hz)
                if int(data.valid_mask.sum()) >= 200:
                    labeled[sym] = data
            except Exception as e:
                logger.warning("  %s: features/labels échoué (%s)", sym, e)

        # Découverte par actif + pool
        candidates: list[Any] = []
        for sym, data in labeled.items():
            try:
                res = discover_single_asset(
                    data, sym, hz, hz_label,
                    config=XGBConfig(), max_paths=max_paths_per_model,
                )
                candidates.extend(res.einhers)
            except Exception as e:
                logger.warning("  %s: découverte échouée (%s)", sym, e)
        try:
            res_pool = discover_pool(labeled, hz, hz_label, max_paths=max_paths_per_model * 2)
            candidates.extend(res_pool.einhers)
        except Exception as e:
            logger.warning("  POOL: découverte échouée (%s)", e)

        logger.info("  %s: %d candidats", hz_label, len(candidates))

        # Backtest sur fenêtre TRAIN+VAL (80%) pour maximiser les trades
        # observés. Le holdout (20% final) reste VIERGE pour la validation
        # définitive (pas de fuite). NB: backtester sur train inclut une part
        # d'optimisme (le modèle a vu ces barres) — le holdout est la vérité.
        admitted_hz: list[Any] = []
        for ein in candidates:
            sym_key = ein.symbol if ein.symbol in labeled else next(iter(labeled.keys()))
            data = labeled.get(sym_key)
            if data is None:
                continue
            # train_mask + val_mask = 80% ; holdout_mask = 20% (vierge)
            train_mask, val_mask, _ = split_temporal(data, embargo_bars=max(hz, 24))
            bt_idx = [i for i, (t, v) in enumerate(zip(train_mask, val_mask)) if t or v]
            if len(bt_idx) < 100:
                continue
            ohlcv_sym = bars[sym_key] if sym_key in bars else next(iter(bars.values()))
            # slice polars : les features gardent les mêmes lignes que ohlcv
            # (compute_features conserve le nombre de lignes)
            if len(ohlcv_sym) != data.X.shape[0]:
                # Désalignement (features n'a pas toutes les lignes) → skip
                continue
            X = data.X
            ohlcv_bt = ohlcv_sym.slice(bt_idx[0], len(bt_idx))
            bt = backtest_einher(ein, ohlcv_bt, X[bt_idx], data.feature_names, costs_pct=0.001)
            m = bt.metrics
            # enrichir metrics pour le scoring
            if m.n_trades > 0:
                import numpy as np

                rets = np.array([t.net_return for t in bt.trades])
                ein = ein.__class__(**{**ein.__dict__, "metrics": m.__class__(**{
                    **m.__dict__, "extra": {
                        **m.extra,
                        "avg_gain": float(rets[rets > 0].mean()) if (rets > 0).any() else 0.0,
                        "avg_loss": float(abs(rets[rets < 0].mean())) if (rets < 0).any() else 0.0,
                    }
                })})
            if m.n_trades >= 30 and m.sharpe_ratio >= 1.0 and m.win_rate >= 0.55:
                admitted_hz.append(ein)

        logger.info("  %s: %d admis (seuils recherche)", hz_label, len(admitted_hz))
        all_admitted.extend(admitted_hz)
        summary_per_horizon[hz_label] = {
            "candidates": len(candidates),
            "admitted": len(admitted_hz),
        }

    # 3. Portfolio (diversification + sizing)
    portfolio = build_portfolio(all_admitted, config=default_portfolio_config())
    logger.info("Portefeuille: %d positions sélectionnées", len(portfolio.positions))

    # 4. Persistance
    portfolio_path = output_dir / "portfolio.jsonl"
    with open(portfolio_path, "w", encoding="utf-8") as f:
        import json

        from auriga.types import condition_to_dict

        for p in portfolio.positions:
            f.write(json.dumps({
                "einher_id": p.einher.id,
                "symbol": p.einher.symbol,
                "direction": p.einher.direction,
                "weight": p.weight,
                "score": p.score,
                "condition": condition_to_dict(p.einher.condition),
                "condition_str": str(p.einher.condition),
                "source": p.einher.source,
                "horizon_bars": p.einher.horizon_bars,
                "amplitude": p.einher.amplitude,
            }, ensure_ascii=False) + "\n")

    summary = {
        "mode": "research",
        "actifs": len(symbols),
        "horizons": [f"{h}h" for h in horizons_bars],
        "candidats_total": sum(v["candidates"] for v in summary_per_horizon.values()),
        "admis_total": len(all_admitted),
        "positions_portefeuille": len(portfolio.positions),
        "par_horizon": summary_per_horizon,
        "portfolio_file": str(portfolio_path),
        "duree_s": round(time.time() - t0, 1),
    }
    logger.info("=== RECHERCHE TERMINÉE : %d admis, %d positions, %.0fs ===",
                len(all_admitted), len(portfolio.positions), summary["duree_s"])
    return summary


def run_trading_mode(
    portfolio_file: Path | str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """MODE TRADING : signaux actuels → spreads → risk gates → ordres paper.

    Args:
        portfolio_file : portefeuille produit par run_research_mode
        dry_run : True = construire et vérifier sans soumettre d'ordre

    Returns:
        Résumé {signaux, spreads, ordres, narratif...}
    """
    from auriga.data.market_data import get_market_data_client
    from auriga.execution.client import get_execution_client
    from auriga.narrative.generator import NarrativeFacts, NarrativeGenerator
    from auriga.options.chain import build_spreads_for_signals
    from auriga.risk.engine import RiskEngine, default_risk_config
    from auriga.selection.sizing import Allocation, Position

    cfg = get_config()
    state = StateStore()
    universe = load_universe()

    if portfolio_file is None:
        portfolio_file = Path("outputs/research/portfolio.jsonl")
    portfolio_file = Path(portfolio_file)

    import json

    if not portfolio_file.exists():
        return {"mode": "trading", "erreur": "portfolio.jsonl introuvable — lancer le mode recherche d'abord"}

    # 1. Charger le portefeuille
    positions_alloc: list[Position] = []
    with open(portfolio_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            from auriga.types import Einher, condition_from_dict

            ein = Einher(
                id=d["einher_id"],
                condition=condition_from_dict(d["condition"]),
                direction=d["direction"],
                amplitude=float(d.get("amplitude", 0.0)),
                symbol=d["symbol"], timeframe="1H",
                horizon_bars=int(d.get("horizon_bars", 24)),
                source=d.get("source", "xgb"),
            )
            positions_alloc.append(Position(einher=ein, weight=d["weight"], score=d.get("score", 0), kelly=0, vol_annual=0))
    alloc = Allocation(positions=positions_alloc)
    logger.info("Portefeuille chargé: %d positions", len(alloc.positions))

    if dry_run:
        logger.info("DRY RUN: pas d'ordres soumis")

    # 2. Prix spot actuels
    md = get_market_data_client()
    spots: dict[str, float] = {}
    for sym in universe["symbols"]:
        try:
            recent = md.get_recent_bars(sym, "1H", n=5)
            if recent.height > 0:
                spots[sym] = float(recent["close"][-1])
        except Exception:
            pass
    state.save_spots(spots)
    logger.info("Spots récupérés: %d actifs", len(spots))

    # 3. Vérifier les signaux actuels des stratégies du portefeuille
    signals = _check_current_signals(alloc, spots, md)
    logger.info("Signaux actuels déclenchés: %d", len(signals))

    # 4. Construire les spreads
    spreads = build_spreads_for_signals(signals, market_data_client=md)
    logger.info("Spreads construits: %d", len(spreads))

    # 5. Risk gates + exécution
    exec_client = None
    risk = RiskEngine(config=default_risk_config())
    portfolio = None
    results = []
    if not dry_run and spreads:
        exec_client = get_execution_client()
        portfolio = exec_client.get_account()
        for spread in spreads:
            decision = risk.evaluate_spread(spread, portfolio)
            if not decision.allowed:
                results.append({"symbol": spread.signal.symbol, "action": "BLOCKED", "reasons": decision.blocked_by})
                continue
            qty = _qty_for_weight(spread, portfolio.equity)
            order = exec_client.submit_spread(spread, qty=qty)
            results.append({"symbol": spread.signal.symbol, "action": order.status, "order_id": order.order_id, "message": order.message})
            if order.status not in ("error", "rejected"):
                state.add_position(TrackedPosition(
                    symbol=spread.signal.symbol,
                    einher_id=spread.signal.einher.id,
                    direction=spread.signal.einher.direction,
                    strategy_name=spread.name,
                    option_symbols=[l.option_symbol for l in spread.legs],
                    max_risk=spread.max_risk,
                    qty=qty,
                    opened_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                ))
    elif dry_run and spreads:
        # Dry run: simuler le risk check avec un portefeuille vide
        from auriga.types import PortfolioState

        portfolio = PortfolioState(equity=100000, cash=100000, buying_power=400000)
        for spread in spreads:
            decision = risk.evaluate_spread(spread, portfolio)
            results.append({
                "symbol": spread.signal.symbol,
                "direction": spread.signal.einher.direction,
                "spread": spread.name,
                "max_risk": spread.max_risk,
                "action": "OK" if decision.allowed else "BLOCKED",
                "reasons": decision.blocked_by,
            })

    # 6. Narratif
    facts = NarrativeFacts(
        date=_today(),
        portfolio={
            "equity": portfolio.equity if portfolio else 100000,
            "positions": len(state.read_positions()),
        },
        positions=[p.to_dict() for p in state.read_positions()],
        risk_events=[r for r in results if r.get("action") == "BLOCKED"],
    )
    gen = NarrativeGenerator()
    text, ok_llm = gen.generate(facts)
    report_path = gen.save(text)
    state.log_cycle({"mode": "trading", "dry_run": dry_run, "signaux": len(signals), "spreads": len(spreads), "resultats": results})

    summary = {
        "mode": "trading",
        "dry_run": dry_run,
        "spots": len(spots),
        "signaux_declenches": len(signals),
        "spreads_construits": len(spreads),
        "resultats": results,
        "narratif": str(report_path),
        "llm_ok": ok_llm,
    }
    return summary


def _check_current_signals(alloc: Allocation, spots: dict[str, float], md) -> list:
    """Vérifie si les stratégies du portefeuille se déclenchent sur les
    dernières barres (évaluation de la condition sur les features récentes)."""
    from auriga.types import Signal

    signals = []
    for pos in alloc.positions:
        sym = pos.einher.symbol
        if sym not in spots or sym == "POOL":
            continue
        try:
            recent = md.get_recent_bars(sym, "1H", n=300)
            if recent.height < 50:
                continue
            feats = compute_features(recent, "1H")
            from auriga.research.condition_tree import evaluate_ast_on_array

            feature_names = [c for c in feats.columns if c != "timestamp"]
            X = feats.select(feature_names).to_numpy().astype("float32")
            mask = evaluate_ast_on_array(pos.einher.condition, X, feature_names)
            if mask.any():
                signals.append(Signal(
                    einher=pos.einher, symbol=sym, price=spots[sym],
                    timestamp=_today(), strength=pos.score,
                ))
        except Exception as e:
            logger.debug("Signal %s %s échec: %s", sym, pos.einher.id, e)
    return signals


def _qty_for_weight(spread, equity: float, max_risk_usd: float = 2500) -> int:
    """Calcule le nombre de contrats selon le risque max par position."""
    qty = max(1, int(max_risk_usd / max(spread.max_risk, 1)))
    return min(qty, 10)  # cap 10 contrats


def _today() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def run_full(
    symbols: list[str] | None = None,
    horizons_bars: list[int] | None = None,
    dry_run: bool = True,
    output_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Cycle complet : recherche PUIS trading (dry_run par défaut)."""
    research = run_research_mode(symbols, horizons_bars, output_dir=output_dir)
    portfolio_file = Path(output_dir or "outputs/research") / "portfolio.jsonl"
    trading = run_trading_mode(portfolio_file=portfolio_file, dry_run=dry_run)
    return {"research": research, "trading": trading}