# AURIGA — Autonomous Quant Research & Investment Agent

**Hackathon Alpaca AI Trading Agents 2026** — Submission write-up (1 page)
Paper account : $100,000 · Universe : 25 US large caps + ETFs avec options

---

## 1. AI Logic — what AURIGA does

AURIGA is a **multi-agent options trading system** built on Alpaca's Trading API.
It combines three specialized ML engines, each with a distinct, testable thesis:

### Agent 1 — Directional alpha (XGBoost → explainable rules)
- **Goal** : predict short-term direction (6h/24h/48h) on 25 liquid large caps.
- **Method** : XGBoost regresses future returns on 36 technical/quantitative
  features (momentum, volatility, statistical, volume — ported from a
  production feature pipeline). Each tree path is converted into a human-
  readable rule : *"if RSI < 30 AND volume ratio > 1.5 AND ADX > 25 → LONG"*.
- **Expression** : debit vertical spreads (bull call / bear put).
- **Validation** : backtest (ATR-based TP/SL, 0.1% costs) → strict admission
  (Sharpe ≥ 2, win rate ≥ 0.65, profit factor ≥ 1.5, ≥30 trades) →
  Benjamini-Hochberg FDR control → out-of-sample holdout kept virgin.
- **Result** : 9 rules admitted on the full 25-asset run, 7 in the live portfolio.

### Agent 2 — Volatility RISK signal (not a strategy — a guard)
- **Goal** : estimate `P(volatility shock in next 24h)` per asset.
- **Why** : we empirically measured that long-volatility straddles lose
  (median Sharpe −2.6) — consistent with the variance risk premium literature
  (Ilmanen 2012). Buying vol is expensive; so A2 does NOT trade. It feeds the
  risk engine.
- **Method** : XGBoost classifier on the label `RV[t+24] > 1.5 × RV[t]`,
  AUC ≈ 0.75 (volatility is predictable — returns are not).
- **Use** : when A2 flags *danger*, the risk engine blocks new premium sales.

### Agent 3 — Systematic premium seller (gated income engine)
- **Goal** : systematically sell option premium (put/call credit spreads,
  ~3% OTM, 5% wide) when the regime is calm.
- **Why** : the vol risk premium (IV > realized vol) makes selling structurally
  profitable (~98% of periods measured). The tail risk is the ~2% of dangerous
  periods — which is exactly what ML can flag.
- **Method** : A3 learns `AVOID_SELL` rules (XGBoost on the rare losing
  periods : recent drawdown + overbought + regime shifts) and STOPS selling
  when triggered.
- **Expression** : put credit spreads (income bias) / call credit spreads.

### Portfolio construction
Admitted rules are scored (Sharpe/WR/PF/drawdown weighted), de-duplicated
(Jaccard ≥ 0.7 on shared features), sized with a **vol-target × fractional
Kelly** blend, and constrained per asset (10%), sector (25%), total (80%).

## 2. Risk gates (all deterministic, auditable)

| Gate | Rule |
|---|---|
| Daily loss limit | −2% of equity → no new orders |
| Max exposure / asset | 10% of capital |
| Max exposure / sector | 25% of capital |
| Max total exposure | 80% of capital |
| Max positions | 12 |
| **Vol danger (A2)** | P(vol shock) > 0.35 → block premium sales |
| **AVOID_SELL (A3)** | any triggered rule → block premium sales |
| Liquidation | total P&L < −25% → close positions |

Every order passes ALL gates before submission. LLM never decides — it only
narrates facts after the deterministic engine has acted.

## 3. Alpaca infrastructure

- **Market Data** : IEX feed, 5 years of 1H/1D bars + live option chains
  (OCC symbols parsed) for the 25-asset universe.
- **Execution** : `alpaca-py` — multi-leg MLEG orders (Level 3), vertical
  spreads as single atomic orders, zero commissions, paper account.
- **Cadence** : research cycle (all agents) → current-signal check → spreads →
  risk gates → paper orders ; daily narrative report + Streamlit dashboard
  (P&L, positions, constellation of strategies, risk state).

## 4. Why AURIGA is defensible

1. **Explainable alpha** : every position traces to a human-readable rule
   with backtested metrics — not a black box.
2. **Honest research** : we measured what does NOT work (long volatility) and
   re-purposed it as a risk signal. The system adapts to evidence.
3. **Two orthogonal income streams** : directional debit spreads (trend) +
   gated premium selling (range/theta) — one hedge of the other.
4. **Institutional-grade risk** : 8 deterministic gates + ML risk flags before
   any order. Fail-closed by design : any gate that cannot be verified
   blocks the order.

## 5. Limitations (stated honestly)

- **Options backtest is a synthetic proxy.** Alpaca's free tier does not
  provide historical options prices, so option P&L in backtests is estimated
  via Black-Scholes repricing using realized volatility (IV = RV + risk
  premium). Statements like "X% of periods were profitable" refer to this
  *synthetic pricing proxy*, NOT to actual historical option fills. Live
  paper fills (which use real option quotes) are the ground truth.
- **A final 20% temporal holdout is kept untouched** during strategy
  discovery and admission, for out-of-sample evaluation. Metrics shown are
  from the train+validation window; holdout results are not claimed yet.
- **5 days of P&L is a small sample.** Results during the competition period
  are indicative, not statistically conclusive.

*Disclaimer : paper trading research only — not investment advice.*