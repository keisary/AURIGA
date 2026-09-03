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
        backtested: list[Any] = []
        # Raccourci : si le candidat POOL, on le backteste sur CHAQUE actif du
        # pool (ses features n'ont PAS asset_id — c'est le X d'un actif seul)
        # et on agglomère les trades (l'Einher POOL est universel).
        for ein in candidates:
            if ein.symbol == "POOL":
                all_trades: list[Any] = []
                for sym_key, data in labeled.items():
                    train_mask, val_mask, _ = split_temporal(data, embargo_bars=max(hz, 24))
                    bt_idx = [i for i, (t, v) in enumerate(zip(train_mask, val_mask)) if t or v]
                    if len(bt_idx) < 100:
                        continue
                    ohlcv_sym = bars.get(sym_key)
                    if ohlcv_sym is None or len(ohlcv_sym) != data.X.shape[0]:
                        continue
                    try:
                        bt = backtest_einher(
                            ein, ohlcv_sym.slice(bt_idx[0], len(bt_idx)),
                            data.X[bt_idx], data.feature_names, costs_pct=0.001,
                        )
                        all_trades.extend(bt.trades)
                    except Exception as e:
                        logger.debug("POOL %s: skip %s (%s)", sym_key, ein.id, e)
                if all_trades:
                    # Métriques agrégées sur l'union des trades
                    from auriga.backtest.backtester import BacktestResult, compute_metrics

                    agg_metrics = compute_metrics(all_trades, costs_pct=0.001)
                    import numpy as np

                    rets = np.array([t.net_return for t in all_trades])
                    ein = ein.__class__(**{**ein.__dict__, "metrics": agg_metrics.__class__(**{
                        **agg_metrics.__dict__, "extra": {
                            **agg_metrics.extra,
                            "avg_gain": float(rets[rets > 0].mean()) if (rets > 0).any() else 0.0,
                            "avg_loss": float(abs(rets[rets < 0].mean())) if (rets < 0).any() else 0.0,
                        }
                    })})
                    backtested.append(ein)
                continue

            # Candidat spécifique à un actif
            data = labeled.get(ein.symbol)
            if data is None:
                continue
            # train_mask + val_mask = 80% ; holdout_mask = 20% (vierge)
            train_mask, val_mask, _ = split_temporal(data, embargo_bars=max(hz, 24))
            bt_idx = [i for i, (t, v) in enumerate(zip(train_mask, val_mask)) if t or v]
            if len(bt_idx) < 100:
                continue
            ohlcv_sym = bars.get(ein.symbol)
            # slice polars : les features gardent les mêmes lignes que ohlcv
            # (compute_features conserve le nombre de lignes)
            if ohlcv_sym is None or len(ohlcv_sym) != data.X.shape[0]:
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
            backtested.append(ein)

        # Admission RÉELLE : seuils individuels + BH/FDR sur le lot de
        # l'horizon (contrôle multi-tests — cause racine #3 corrigée).
        admitted_hz = []
        if backtested:
            from auriga.backtest.admission import admit_einhers, default_admission_config

            results = admit_einhers(backtested, cfg=default_admission_config())
            for r in results:
                if r.admitted:
                    admitted_hz.append(r.einher)

        logger.info("  %s: %d backtestés, %d admis (seuils + BH/FDR)",
                    hz_label, len(backtested), len(admitted_hz))
        all_admitted.extend(admitted_hz)
        summary_per_horizon[hz_label] = {
            "candidates": len(candidates),
            "admitted": len(admitted_hz),
        }

    # 3. Portfolio (diversification + sizing)
    portfolio = build_portfolio(all_admitted, config=default_portfolio_config())
    logger.info("Portefeuille: %d positions sélectionnées", len(portfolio.positions))

    # 3b. Agents A2+A3 : modèles de RISQUE (vol_signal + règles AVOID_SELL)
    # A2 est entraîné sur chaque actif → modèle de danger vol persisté.
    # A3 découvre les règles AVOID_SELL (régimes où NE PAS vendre de prime).
    from auriga.risk.vol_signal import VolRiskEngine

    vol_engine = VolRiskEngine(horizon_bars=24)
    n_vol_models = 0
    for sym, ohlcv_sym in bars.items():
        try:
            feats_sym = compute_features(ohlcv_sym, "1H")
            auc = vol_engine.train_and_save(sym, ohlcv_sym, feats_sym)
            if auc > 0:
                n_vol_models += 1
        except Exception as e:
            logger.debug("vol_signal %s: %s", sym, e)
    logger.info("VolSignal (A2): %d modèles de danger vol entraînés", n_vol_models)

    # Découverte A3 (AVOID_SELL) sur le premier horizon de la liste
    avoid_all: list[Any] = []
    try:
        from auriga.research.prime_discovery import discover_sell_prime

        hz_a3 = horizons_bars[0] if horizons_bars else 24
        for sym, ohlcv_sym in bars.items():
            try:
                feats_sym = compute_features(ohlcv_sym, "1H")
                feature_names = [c for c in feats_sym.columns if c != "timestamp"]
                X = feats_sym.select(feature_names).to_numpy().astype("float32")
                rules = discover_sell_prime(
                    ohlcv_sym, feats_sym, X, feature_names, sym,
                    hz_a3, f"{hz_a3}h",
                    config=XGBConfig(n_estimators=100), max_paths=10,
                )
                avoid_all.extend(rules)
            except Exception as e:
                logger.debug("A3 %s: %s", sym, e)
    except Exception as e:
        logger.warning("A3 discovery indisponible: %s", e)

    # Persister les règles AVOID_SELL
    import json as _json

    from auriga.types import condition_to_dict

    if avoid_all:
        avoid_path = output_dir / "avoid_sell.jsonl"
        with open(avoid_path, "w", encoding="utf-8") as f:
            for r in avoid_all:
                f.write(_json.dumps({
                    "id": r.id,
                    "symbol": r.symbol,
                    "direction": r.direction,
                    "condition": condition_to_dict(r.condition),
                    "amplitude": r.amplitude,
                    "horizon_bars": r.horizon_bars,
                    "source": r.source,
                }, ensure_ascii=False) + "\n")
        logger.info("A3: %d règles AVOID_SELL persistées -> %s", len(avoid_all), avoid_path)
    else:
        logger.info("A3: aucune règle AVOID_SELL (config actuelle)")


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

    # 2. Prix spot + features récentes (une seule passe)
    md = get_market_data_client()
    spots: dict[str, float] = {}
    recent_bars: dict[str, pl.DataFrame] = {}
    recent_feats: dict[str, pl.DataFrame] = {}
    for sym in universe["symbols"]:
        try:
            bars = md.get_recent_bars(sym, "1H", n=300)
            if bars.height >= 60:
                recent_bars[sym] = bars
                spots[sym] = float(bars["close"][-1])
                recent_feats[sym] = compute_features(bars, "1H")
        except Exception:
            pass
    state.save_spots(spots)
    logger.info("Spots + features récupérés: %d actifs", len(spots))

    # 3. Signaux actuels des stratégies A1 (portefeuille directionnel)
    signals = _check_current_signals(alloc, spots, recent_feats)
    logger.info("Signaux A1 déclenchés: %d", len(signals))

    # 4. Construire les spreads directionnels A1
    spreads_a1 = build_spreads_for_signals(signals, market_data_client=md)
    logger.info("Spreads A1 construits: %d", len(spreads_a1))

    # 5. Vente de prime A3 (credit spreads systématiques) + filtres risque
    risk_events: list[dict] = []
    spreads_prime: list[Any] = []
    prime_enabled = cfg.orchestration.get("enable_prime_selling", True)
    if prime_enabled and not cfg.raw.get("prime", {}).get("disabled", False):
        from auriga.research.prime_seller import (
            AvoidSellFilter,
            PrimeSellerConfig,
            filter_danger,
            select_prime_candidates,
        )
        from auriga.risk.vol_signal import VolRiskEngine

        prime_cfg = PrimeSellerConfig(
            max_credit_spreads_per_cycle=int(cfg.raw.get("prime", {}).get(
                "max_per_cycle", 8)),
        )
        # Charger les chaînes d'options pour la vente
        chains: dict[str, pl.DataFrame] = {}
        from auriga.data.cache import load_cached_chain

        for sym in universe["symbols"]:
            ch = load_cached_chain(sym)
            if ch is not None and ch.height > 0:
                chains[sym] = ch

        # Charger les règles AVOID_SELL (modèles entraînés en recherche)
        avoid_rules = _load_avoid_sell_rules()
        avoid_filter = AvoidSellFilter(avoid_rules)

        # VolRiskEngine : entraîne/charge les modèles de danger vol
        vol_engine = VolRiskEngine(horizon_bars=24)
        for sym in universe["symbols"]:
            if recent_bars.get(sym) is not None:
                vol_engine.load(sym)

        # Sélectionner les credit spreads candidats
        candidates = select_prime_candidates(
            list(recent_feats.keys()), spots, chains, prime_cfg
        )
        # Filtrer par danger (vol + AVOID_SELL)
        spreads_prime, risk_events = filter_danger(
            candidates, vol_engine, recent_feats, avoid_filter
        )
        logger.info("Credit spreads A3: %d candidats -> %d autorisés après filtres",
                    len(candidates), len(spreads_prime))

    spreads = spreads_a1 + spreads_prime
    logger.info("Spreads totaux à exécuter: %d (A1=%d, A3=%d)",
                len(spreads), len(spreads_a1), len(spreads_prime))

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
                results.append({"symbol": spread.underlying, "action": "BLOCKED", "reasons": decision.blocked_by})
                continue
            qty = _qty_for_weight(spread, portfolio.equity)
            order = exec_client.submit_spread(spread, qty=qty)
            results.append({"symbol": spread.underlying, "action": order.status, "order_id": order.order_id, "message": order.message})
            if order.status not in ("error", "rejected"):
                _sig = spread.signal
                state.add_position(TrackedPosition(
                    symbol=spread.underlying,
                    einher_id=_sig.einher.id if _sig is not None else f"prime_{spread.name}",
                    direction=_sig.einher.direction if _sig is not None else "SELL_PRIME",
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
            _sig = spread.signal
            results.append({
                "symbol": spread.underlying,
                "direction": _sig.einher.direction if _sig is not None else "SELL_PRIME",
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


def _check_current_signals(
    alloc: Allocation,
    spots: dict[str, float],
    recent_feats: dict[str, pl.DataFrame] | None = None,
) -> list:
    """Vérifie si les stratégies du portefeuille se déclenchent sur les
    dernières barres (évaluation de la condition sur les features récentes).

    recent_feats : features déjà calculées (optimisation — évite un 2e fetch).
    """
    from auriga.types import Signal

    signals = []
    for pos in alloc.positions:
        sym = pos.einher.symbol
        if sym not in spots or sym == "POOL":
            continue
        try:
            if recent_feats is not None and sym in recent_feats:
                feats = recent_feats[sym]
            else:
                # Fallback si les features ne sont pas fournies (mode legacy)
                from auriga.data.market_data import get_market_data_client

                md = get_market_data_client()
                recent = md.get_recent_bars(sym, "1H", n=300)
                if recent.height < 50:
                    continue
                from auriga.features.engine import compute_features

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


def _load_avoid_sell_rules() -> list:
    """Charge les règles AVOID_SELL (Agent A3) depuis les fichiers de recherche.

    Cherche dans outputs/research/ les candidats avec direction=AVOID_SELL.
    """
    import json

    from auriga.types import Einher, condition_from_dict

    rules: list = []
    search_dir = Path("outputs/research")
    if not search_dir.exists():
        return rules

    for f in sorted(search_dir.glob("avoid_sell_*.jsonl")) + sorted(search_dir.glob("candidates_*.jsonl")):
        try:
            with open(f, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if d.get("direction") != "AVOID_SELL":
                        continue
                    try:
                        rules.append(Einher(
                            id=d["id"],
                            condition=condition_from_dict(d["condition"]),
                            direction="AVOID_SELL",
                            amplitude=float(d.get("amplitude", 0)),
                            symbol=d.get("symbol", "POOL"),
                            timeframe=d.get("timeframe", "1H"),
                            horizon_bars=int(d.get("horizon_bars", 24)),
                            source=d.get("source", "xgboost:prime"),
                        ))
                    except (KeyError, TypeError):
                        continue
        except Exception:
            continue

    if rules:
        logger.info("Règles AVOID_SELL chargées: %d (fichiers de recherche)", len(rules))
    return rules


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