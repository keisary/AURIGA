# AURIGA — Autonomous Quant Research & Investment Agent

Agent autonome de recherche quantitative et de trading pour le **Hackathon Alpaca AI Trading Agents 2026** (deadline : 4 septembre 15:00 UTC).

AURIGA découvre des stratégies de trading explicables (Einhers) via **XGBoost + Programmation Génétique (STGP)**, les valide statistiquement (BH/FDR, holdout, walk-forward), les exprime en **spreads d'options définis-risque** et les exécute sur un **compte paper-trading Alpaca ($100k)** — avec un narratif quotidien généré par LLM et un dashboard Streamlit.

## Stack

- **Données** : Alpaca Market Data API (IEX, gratuit) — 25 large caps, 5 ans, bars 1H + 1D
- **Recherche** : XGBoost (arbres → règles) + STGP (search_engine einherjar adapté)
- **Validation** : backtest + admission BH/FDR adaptatif + holdout + walk-forward
- **Exécution** : alpaca-py, options multi-leg (spreads définis-risque), paper $100k
- **Risque** : daily loss limit, exposure max, positions max, stop global
- **Narratif** : LLM (OpenRouter) — le LLM propose, le moteur déterministe dispose
- **Dashboard** : Streamlit (P&L, positions, règles actives, narratif)

## Structure

```
src/auriga/
  data/          # Ingestion données Alpaca (bars + options chains) + cache
  features/      # Feature engineering (technical + quantitative, extraction midasV3)
  research/      # Découverte : XGBoost + STGP (Einhers)
  backtest/      # Backtest + admission statistique
  selection/     # Sélection portefeuille + position sizing
  options/       # Expression en spreads définis-risque
  execution/     # Exécution Alpaca paper
  risk/          # Risk engine
  narrative/     # Narratif quotidien LLM
  orchestration/ # Cycle complet + scheduler + CLI
  dashboard/     # Dashboard Streamlit
  utils/         # Config, logging, helpers, universe
```

## Installation

```bash
python -m venv .venv
# Windows :
.venv\Scripts\activate
# puis :
pip install -e ".[dev]"
cp .env.example .env  # puis remplir les clés
```

## Usage

```bash
auriga run           # cycle complet (research → exécution)
auriga research      # recherche seule
auriga dashboard     # dashboard Streamlit
auriga status        # état du portefeuille
```

## Documentation

- `CAHIER_DES_CHARGES_AURIGA.md` — SRS complet (ISO/IEC/IEEE 29148:2018), 116 exigences, décisions D1-D15.
- `AGENTS.md` — rôles des agents de développement (multi-modèles).