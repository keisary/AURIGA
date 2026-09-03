# AURIGA — Autonomous Quant Research & Investment Agent

![AURIGA](assets/auriga_banner.png)

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

- `CAHIER_DES_CHARGES_AURIGA.md` — SRS complet (ISO/IEC/IEEE 29148), décisions D1-D17
- `DESIGN_RATIONALE.md` — chaque choix de conception, sourcé (Ilmanen 2012, AQR, arXiv...)
- `SUBMISSION_WRITEUP.md` — one-page write-up pour le jury
- `SUBMISSION_KIT.md` — kit de soumission (champs LabLab, script vidéo, checklist)
- `AGENTS.md` — plan des agents de développement

## Installation (Windows / PowerShell)

```powershell
# 1. Cloner et entrer dans le repo
git clone https://github.com/keisary/AURIGA.git
cd AURIGA

# 2. Environnement virtuel
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Dépendances
python -m pip install --upgrade pip
python -m pip install numpy polars pandas numba xgboost scipy scikit-learn alpaca-py streamlit python-dotenv requests pyyaml pyarrow pytest ruff

# 4. Configuration
copy .env.example .env
# → remplir ALPACA_API_KEY, ALPACA_SECRET_KEY (paper), OPENROUTER_API_KEY
```

> ⚠️ Si `Activate.ps1` est bloqué par la politique d'exécution :
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` puis réessayer.

## Usage (PowerShell)

```powershell
# Depuis la racine du repo, avec le venv activé :
$env:PYTHONPATH = "src"

python -m auriga.orchestration.cli research            # mode recherche (A1+A2+A3)
python -m auriga.orchestration.cli run                 # dry-run complet (défaut)
python -m auriga.orchestration.cli run --no-dry-run    # ordres paper réels
python -m auriga.orchestration.cli status              # état portefeuille
python -m auriga.orchestration.cli dashboard           # Streamlit
python -m auriga.orchestration.cli collect             # collecte données univers
```

Ou sans variable d'environnement (PowerShell) :
```powershell
python -m streamlit run src/auriga/dashboard/app.py    # dashboard
```

## Tests

```powershell
python -m pytest tests/ -q
# (pythonpath=src déjà configuré dans pyproject.toml — pas de PYTHONPATH à poser)
```

*Projet de recherche en paper trading — pas un conseil financier.*