# AURIGA — Plan des agents de développement

> Orchestrateur : Hermes Agent (décisions finales).
> Chaque agent travaille de façon autonome sur son module, mais DOIT revenir à l'orchestrateur si :
> - une exigence du cahier des charges est ambiguë ou contradictoire avec le code réel ;
> - un choix de design important doit être tranché ;
> - un module dépend d'un autre non encore livré.
>
> Convention : code Python lisible, typé, ruff-clean, docstrings en français.
> Tous les modules sont dans `src/auriga/`, tests dans `tests/`.

## Modèles des agents (OpenRouter, modèles free variés)

| Agent | Rôle | Modèle recommandé (free) |
|---|---|---|
| A1 | Ingestion données Alpaca | z-ai/glm-5.2:free |
| A2 | Feature engineering (extraction midasV3) | minimax/minimax-m3:free |
| A3 | Découverte XGBoost (arbres → règles) | google/gemma-4-31b-it:free |
| A4 | Découverte STGP (search_engine adapté) | z-ai/glm-5.2:free |
| A5 | Backtest + admission statistique | minimax/minimax-m3:free |
| A6 | Sélection portefeuille + sizing | nvidia/nemotron-3-super-120b-a12b:free |
| A7 | Options définis-risque (spreads) | minimax/minimax-m3:free |
| A8 | Exécution Alpaca (alpaca-py) | cohere/north-mini-code:free |
| A9 | Risk engine | z-ai/glm-5.2:free |
| A10 | Narratif LLM (OpenRouter) | nvidia/nemotron-3-super-120b-a12b:free |
| A11 | Orchestration + CLI + dashboard | minimax/minimax-m3:free |

## Rôles détaillés

### A1 — Ingestion données Alpaca (module `data/`)
- Interface Alpaca Market Data (bars 1H/1D, options chains) via alpaca-py
- Cache local parquet/JSONL dans `data/raw/`, `data/processed/`
- Mock API si pas de clés (mode `mock_api: true` dans settings.yaml)
- Livrables : `data/market_data.py`, `data/cache.py`, `data/mock_data.py`

### A2 — Feature engineering (module `features/`)
- Extraction ciblée des fonctions de calcul midasV3 :
  - technical_indicators.py → EMA/SMA/RSI/MACD/Bollinger/ATR (Numba)
  - quantitative_features.py → volatilité réalisée, Hurst, entropies, DFA, skewness, VaR, maxDrawdown, régime
- API unique : `compute_features(ohlcv_df) -> DataFrame` (polars)
- Pas de fuite future (fenêtres glissantes, lookback configurable)
- Livrables : `features/technical.py`, `features/quantitative.py`, `features/engine.py`

### A3 — Découverte XGBoost (module `research/`)
- Adaptation du pipeline xgb_einhers : entraîner GBDT, extraire chemins d'arbres → règles
- Config adaptée 1H (25k-70k barres, depth≤4, subsample)
- Sortie : Einhers (condition_tree, direction, amplitude, métriques)
- Livrables : `research/xgboost_discovery.py`

### A4 — Découverte STGP (module `research/`)
- Adaptation du search_engine (STGP + MAP-Elites + bootstrap)
- Admission commune avec A3 (BH/FDR + holdout + walk-forward)
- Livrables : `research/stgp_discovery.py`

### A5 — Backtest + admission (module `backtest/`)
- Backtest des Einhers sur données 1H (coûts réalistes)
- Admission : seuils (Sharpe≥2, WR≥0.65, PF≥1.5, n_trades≥30, maxDD≤0.30)
- BH/FDR adaptatif + holdout + walk-forward (stabilité ≥60%)
- Livrables : `backtest/backtester.py`, `backtest/admission.py`

### A6 — Sélection portefeuille (module `selection/`)
- Sélection des Einhers admis avec MMR (diversité, anti-corrélation)
- Position sizing (Kelly-lite / vol-target, plafonné)
- Contraintes : max positions, max par actif, max par secteur
- Livrables : `selection/portfolio.py`, `selection/sizing.py`

### A7 — Options définis-risque (module `options/`)
- Mapping signal → spread : long → bull call spread / put credit spread ; short → bear put spread / call credit spread
- Sélection strikes/expirations : DTE 14-42, delta 0.20-0.45, open interest min
- Pricing théorique Black-Scholes pour backtest (pas de données options historiques)
- Livrables : `options/strategies.py`, `options/pricing.py`, `options/chain_selector.py`

### A8 — Exécution Alpaca (module `execution/`)
- alpaca-py : compte, ordres (multi-leg), positions, watchlists
- Ordres bracket (TP/SL), vérification buying power
- Retry/backoff sur rate limits
- Livrables : `execution/client.py`, `execution/orders.py`

### A9 — Risk engine (module `risk/`)
- Daily loss limit (-2% → stop), max exposure/actif (10%), max exposure/secteur (25%)
- Max positions, max total exposure (80%), stop global (15%)
- Vérification AVANT ordre, journalisation des blocs, liquidation si seuil critique
- Livrables : `risk/engine.py`

### A10 — Narratif LLM (module `narrative/`)
- Rapport quotidien en langage naturel (OpenRouter)
- Ancré sur des faits (P&L, décisions, trades), le LLM NE DÉCIDE PAS
- Versionné et horodaté → `outputs/narratives/`
- Livrables : `narrative/generator.py`

### A11 — Orchestration + CLI + dashboard (modules `orchestration/`, `dashboard/`)
- Cycle complet : ING → FEAT → DISC → VAL → SEL → OPT → EXEC → RSK → NAR
- CLI : `auriga run|research|dashboard|status`
- Dashboard Streamlit : P&L, positions, règles actives, narratif, risk gates
- Livrables : `orchestration/pipeline.py`, `orchestration/cli.py`, `dashboard/app.py`

## Dépendances entre agents (ordre de lancement)

```
A1 → A2 → (A3, A4) → A5 → A6 → A7 → A8, A9 → A10 → A11
```

A1 et A2 peuvent partir en parallèle. A3 et A4 en parallèle après A2. Les agents amont doivent livrer des interfaces stables (signatures) pour que les aval puissent travailler sur des mocks.