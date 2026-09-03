# AURIGA — Autonomous Quant Research & Investment Agent

Agent autonome de recherche quantitative et de trading pour le **Hackathon Alpaca AI Trading Agents 2026**.

AURIGA combine **deux moteurs de stratégies** (direction + vente de prime) et **un signal de risque** (volatilité) en un système cohérent qui découvre, valide et exécute des **spreads d'options définis-risque** sur un **compte paper Alpaca ($100k)** — avec narratif quotidien LLM et dashboard Streamlit.

## Architecture multi-agents

```
        ┌─────────────────────────────────────────────┐
        │  SIGNAL DE RISQUE VOL (A2)                  │
        │  P(choc de vol) → gate vol_danger           │
        └──────────────────┬──────────────────────────┘
        ┌──────────────────┴──────────────────────────┐
        │              RISK ENGINE (8 gates)          │
        └──────┬───────────────────────────┬───────────┘
               ▼                           ▼
        ┌──────────────┐            ┌──────────────────┐
        │ A1 Direction │            │ A3 Vendeur prime │
        │ XGBoost →    │            │ credit spreads   │
        │ règles LONG/ │            │ filtrés AVOID_SELL│
        │ SHORT        │            └──────────────────┘
        └──────────────┘
```

| Agent | Rôle | Méthode | Expression options |
|---|---|---|---|
| **A1 Direction** | Prédire LONG/SHORT (6h/24h/48h) | XGBoost → règles explicables | Bull/bear spreads (débit) |
| **A2 Vol (risque)** | P(choc de vol) par actif | XGBoost classifieur (AUC ~0.75) | Aucune — gate vol_danger |
| **A3 Vente prime** | Vendre du theta en régime calme | Règles AVOID_SELL sur ~2% périodes dangereuses | Put/call credit spreads |

## Stack

- **Données** : Alpaca Market Data API (IEX) — 25 large caps, 5 ans, 1H + 1D + chaînes options
- **Features** : 36 fonctions Numba (technical + quantitative, extraites de midasV3)
- **Validation** : backtest ATR-based + admission (Sharpe≥2, WR≥0.65, PF≥1.5, ≥30 trades) + BH/FDR + holdout vierge
- **Exécution** : alpaca-py, ordres multi-leg MLEG, paper $100k
- **Risque** : 8 gates déterministes (daily loss, exposures, positions, vol danger, AVOID_SELL)
- **Narratif** : LLM OpenRouter (le LLM propose, le moteur dispose)
- **Dashboard** : Streamlit charte « Le Cocher céleste »

## Structure

```
src/auriga/
  data/          # Ingestion Alpaca (bars + options chains) + cache parquet
  features/      # Feature engineering (36 features Numba)
  research/      # Découverte : xgb_discovery (A1), prime_discovery (A3)
  backtest/      # Backtest directionnel + straddles options + admission
  selection/     # Scoring, diversification, sizing (vol-target × Kelly)
  options/       # Spreads (occ, pricing Black-Scholes, strategies, credit_spreads)
  execution/     # Client Alpaca paper, ordres multi-leg MLEG
  risk/          # Risk engine + vol_signal (A2)
  narrative/     # Narratif quotidien LLM
  orchestration/ # Pipeline 2 modes + state + CLI
  dashboard/     # Dashboard Streamlit
  utils/         # Config, logging, helpers, universe
```

## Documentation

- `CAHIER_DES_CHARGES_AURIGA.md` — SRS complet (ISO/IEC/IEEE 29148), décisions D1-D15
- `DESIGN_RATIONALE.md` — chaque choix de conception, sourcé (Ilmanen 2012, AQR, arXiv...)
- `SUBMISSION_WRITEUP.md` — one-page write-up pour le jury
- `AGENTS.md` — plan des agents de développement

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install numpy polars pandas numba xgboost scipy scikit-learn alpaca-py streamlit python-dotenv requests pyyaml pyarrow pytest ruff
cp .env.example .env   # remplir ALPACA_API_KEY, ALPACA_SECRET_KEY, OPENROUTER_API_KEY
```

## Usage

```bash
PYTHONPATH=src python -m auriga.orchestration.cli research   # mode recherche (A1+A2+A3)
PYTHONPATH=src python -m auriga.orchestration.cli run        # dry-run complet par défaut
PYTHONPATH=src python -m auriga.orchestration.cli run --no-dry-run  # ordres paper réels
PYTHONPATH=src python -m auriga.orchestration.cli status     # état portefeuille
PYTHONPATH=src python -m auriga.orchestration.cli dashboard  # Streamlit
PYTHONPATH=src python -m auriga.orchestration.cli collect    # collecte données univers
```

## Tests

```bash
PYTHONPATH=src python -m pytest tests/ -q
```

*Projet de recherche en paper trading — pas un conseil financier.*