# AURIGA — Submission Kit (LabLab / Alpaca AI Trading Agents Hackathon)

> Tout ce qu'il faut pour soumettre, champ par champ. Rédigé le 04/09/2026.
> Les textes **EN** sont prêts à coller ; les annotations **FR** sont pour toi.

---

## 0. Rappels critiques

| Élément | Valeur |
|---|---|
| Deadline | **Friday Sep 4, 2026 — 17:00 CEST (15:00 UTC / 8:00 AM PDT)** |
| Plateforme | lablab.ai — Alpaca AI Trading Agents Hackathon |
| Repo public | https://github.com/keisary/AURIGA |
| One-page write-up | `SUBMISSION_WRITEUP.md` (déjà conforme : AI logic §1, risk gates §2, Alpaca infra §3, limitations honnêtes §5) |
| Règle Discord | Le write-up peut être « une slide, une section de la description, ou une page du repo » → **page du repo** : copier l'URL du fichier ou son contenu dans la description longue. |

**Exigence Discord (one-page write-up) — à couvrir dans la soumission :**
- ✅ AI logic → `SUBMISSION_WRITEUP.md` §1 (A1 XGBoost→règles, A2 signal vol, A3 vendeur gaté)
- ✅ Risk gates → §2 (8 gates, fail-closed)
- ✅ Alpaca infrastructure → §3 (market data IEX, MLEG Level 3, paper $100k)

---

## 1. Champ par champ (LabLab)

### Project title (choisir UNE option)
1. **AURIGA — Autonomous Quant Research & Investment Agent** *(recommandé, = repo)*
2. AURIGA: Rules Over Vibes — An Options Agent That Explains Itself
3. AURIGA — The Charioteer: Discover, Validate, Deploy

### Tagline / short description (~1 phrase, max 140 car.)
> AURIGA is an autonomous quant research agent that discovers XGBoost trading
> rules, gates them through 8 deterministic risk checks, and deploys defined-risk
> options spreads on Alpaca paper — the LLM narrates, it never decides.

### Tags (10)
`quantitative-trading` `options` `alpaca` `xgboost` `machine-learning`
`risk-management` `paper-trading` `streamlit` `llm-agents` `fintech`

### Long description (prêt à coller, ~180 mots)
> AURIGA (the Charioteer constellation) is an autonomous research agent that
> turns 5 years of 1H/1D Alpaca market data into explainable options strategies,
> validates them statistically, and trades them on a $100k Alpaca paper account
> — while keeping the LLM outside the execution authority.
>
> Three specialized ML engines share one pipeline: **A1** extracts human-readable
> LONG/SHORT rules from XGBoost tree paths (9 rules admitted: Sharpe≥2, WR≥0.65,
> PF≥1.5, ≥30 trades, BH/FDR-controlled); **A2** predicts volatility shocks
> (AUC≈0.75) and acts as a *risk signal*, not a strategy — we measured that
> buying vol loses (median Sharpe −2.6), consistent with the variance risk
> premium; **A3** systematically sells option premium (credit spreads) and
> learns AVOID_SELL rules to stop before the rare dangerous periods.
>
> Every order passes **8 deterministic risk gates** (daily loss, exposure per
> asset/sector/total, max positions, liquidation, A2 vol danger, A3 AVOID_SELL)
> and is **fail-closed**: a gate that cannot be verified blocks the order.
> Execution uses atomic multi-leg MLEG option orders on Alpaca paper. A
> Streamlit dashboard and a daily LLM narrative explain every decision.
>
> Limitations are stated honestly in the repo: option backtests use a synthetic
> Black-Scholes pricing proxy (Alpaca free tier has no historical option
> prices); a final 20% temporal holdout is kept untouched.

### Cover image
`assets/auriga_cover.png` (1280×720) — générée, prête à uploader.
*(Si LabLab impose un ratio différent, recadrer au centre.)*

### Video presentation (60–90 s) — script complet en §4

### Slide presentation
1 slide max si demandée : utiliser `assets/auriga_cover.png` comme fond + la phrase d'ouverture du §4. Alternative : pointer vers `SUBMISSION_WRITEUP.md`.

### Demo platform / Application URL
- Le dashboard tourne en local (Streamlit, clés paper privées) → **pas d'URL publique**.
- Soumettre : URL du repo GitHub + lien vidéo.
- Si un champ URL est **obligatoire** : mettre le repo GitHub (https://github.com/keisary/AURIGA) — c'est accepté comme démo pour un agent qui exige des clés privées.

---

## 2. Le pitch (à retenir pour la vidéo et le jury)

> **Ne pas vendre** : « un agent IA qui trade avec Alpaca » (des dizaines de projets).
>
> **Vendre** : *An autonomous quantitative research agent that discovers,
> statistically validates and deploys trading strategies — while keeping the
> LLM outside the execution authority.*

```
LLM → narration / interprétation   (❌ aucun pouvoir d'exécution)
Quant system → validation statistique → risk engine → exécution
```

Phrase de clôture vidéo :
> **"AURIGA doesn't ask an LLM whether to trade. The quantitative system
> decides. The LLM explains."**

---

## 3. Ordre de travail demain matin (avant 15:00 UTC)

```text
1.  Lire ce kit + vérifier le repo (déjà poussé : d474593 → 6420d25)
2.  Vérifier le dashboard : http://localhost:8501 (déjà lancé)
    → chip « PAPER CONNECTED » vert si clés OK ; bandeau rouge si déconnecté
3.  Enregistrer la vidéo 60-90 s (script §4) — OBS ou Xbox Game Bar
4.  Uploader cover + vidéo sur LabLab
5.  Remplir les champs (§1) + coller le write-up ou son URL
6.  Relire SUBMISSION_WRITEUP.md une dernière fois
7.  SOUMETTRE avant 17:00 CEST — ne pas attendre la dernière minute
```

---

## 4. Script vidéo — 90 secondes

VO = voiceover anglais. Les temps sont indicatifs (±5 s).

| t | Visuel | Voiceover / texte |
|---|---|---|
| 0–10 s | Cover + logo constellation, titre | *"AURIGA — an autonomous quant research and investment agent. It discovers strategies, validates them statistically, and deploys them on an Alpaca paper account."* |
| 10–25 s | Schéma : Market Data → Features → Strategy Discovery (surimpression flèches) | *"Five years of 1-hour and 1-day Alpaca market data flow through 36 features into an XGBoost discovery engine that converts tree paths into human-readable rules."* |
| 25–40 s | Trois cartes A1 / A2 / A3 | *"Three agents, three testable theses. A1 trades direction with debit spreads. A2 predicts volatility shocks — and we turned it into a risk signal, because buying volatility loses. A3 systematically sells premium in calm regimes."* |
| 40–55 s | Risk engine, 8 gates, puis « TRADE APPROVED » → « TRADE BLOCKED — Reason: volatility danger » | *"Every order passes eight deterministic risk gates — daily loss, exposures, positions, volatility danger. Fail-closed: if a gate cannot be verified, the order is blocked."* |
| 55–70 s | Écran Alpaca paper (ordres multi-leg) | *"Approved spreads are submitted as atomic multi-leg option orders to Alpaca paper trading — defined risk, zero commissions."* |
| 70–85 s | Dashboard : equity, positions, constellation, narratif | *"A Streamlit dashboard and a daily LLM narrative explain every decision — positions trace back to their rules and their backtested metrics."* |
| 85–90 s | Cover, tagline finale | *"AURIGA doesn't ask an LLM whether to trade. The quantitative system decides. The LLM explains."* |

### Conseils de tournage
- 60–90 s max ; couper A3 si besoin (jamais le risk engine).
- Montrer un vrai re-run du dashboard + un dry-run console (`python -m auriga.orchestration.cli run`).
- Sous-titres activés (les juges regardent souvent sans le son).
- Fichier : MP4, 16:9, ≥720p.

---

*Checklist générée pour la soumission — dernière mise à jour 04/09/2026.*
