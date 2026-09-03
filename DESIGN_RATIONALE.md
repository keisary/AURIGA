# AURIGA — Décisions de conception sourcées

> Ce document explique et défend **chaque choix de conception** du système AURIGA,
> avec les sources académiques et techniques qui les motivent. Il sert de base
> pour la présentation au jury (one-page write-up) et pour toute discussion
> sur l'architecture.
>
> **Version** : 1.0 — 03/09/2026
> **Projet** : AURIGA — Autonomous Quant Research & Investment Agent
> **Contexte** : Hackathon Alpaca AI Trading Agents 2026 (deadline 04/09 15:00 UTC)

---

## Table des matières

1. [Positionnement et thèse](#1-positionnement-et-thèse)
2. [Pourquoi la recherche de règles explicables (Einhers)](#2-pourquoi-la-recherche-de-règles-explicables)
3. [Pourquoi XGBoost + arbres → règles](#3-pourquoi-xgboost--arbres--règles)
4. [Pourquoi les options définis-risque (spreads)](#4-pourquoi-les-options-définis-risque)
5. [Pourquoi l'architecture multi-agents (2 moteurs + signal de risque)](#5-pourquoi-larchitecture-multi-agents)
6. [Agent A1 — Direction (momentum/régression)](#6-agent-a1--direction)
7. [Agent A2 — Signal de risque de volatilité (plus aucun trading)](#7-agent-a2--signal-de-risque-de-volatilité-transformé-2026-09-03)
8. [Agent A3 — Vendeur de prime (vente gatée)](#8-agent-a3--vendeur-de-prime)
9. [Routeur de régime — arbitrage simplifié au code freeze](#9-routeur-de-régime)
10. [Pourquoi le LLM hybride (propose, ne décide pas)](#10-pourquoi-le-llm-hybride)
11. [Choix techniques](#11-choix-techniques)
12. [Références complètes](#12-références-complètes)

---

## 1. Positionnement et thèse

**AURIGA** (le Cocher, constellation) est un agent autonome de recherche
quantitative qui **découvre, valide et exécute** des stratégies d'options
définis-risque sur des actions/ETF US liquides, avec un narratif quotidien
explicable.

**Thèse centrale** : plutôt qu'un seul modèle qui prédit la direction des prix
(signal faible, bruit dominant), AURIGA combine **deux moteurs de stratégies**
(direction A1, vente de prime A3) **sécurisés par un signal de risque** de
volatilité (A2) — chacun exploitant une source de rendement différente et
robuste. La diversification des *sources d'alpha* est la vraie protection
contre l'overfitting et la non-stationnarité des marchés.

**Sources** :
- Ilmanen, A. (2012). *Do Financial Markets Reward Buying or Selling Insurance
  and Lottery Tickets?* Financial Analysts Journal, 68(5). — La référence sur
  les primes de risque asymétriques.
- « Combating Overfitting in Quant Trading » — les données financières ont un
  ratio signal/bruit exceptionnellement bas ; les modèles doivent être
  régularisés et diversifiés.

---

## 2. Pourquoi la recherche de règles explicables (Einhers)

**Décision** : AURIGA découvre des **règles explicables** (Einhers) de la forme
« si RSI < 30 ET volume > 1.5×moyenne ET ADX > 25 → LONG », plutôt que des
boîtes noires qui émettent des signaux opaques.

**Justification** :
1. **Testabilité** : une règle lisible peut être backtestée, falsifiée,
   améliorée. Une boîte noire ne peut pas être auditée.
2. **Crédibilité face au jury** : le cahier des charges du hackathon exige une
   explication claire de la logique IA (« AI logic and risk controls »).
3. **Traçabilité** : chaque Einher porte sa condition, sa source, ses métriques.
4. **Robustesse** : les règles simples et parcimonieuses sur-fittent moins que
   les modèles complexes (voir §3).

**Source** : « Quant Convergence » (2026) — les règles simples et robustes
(Graham) battent les modèles IA complexes sur les actions, en rendement ET en
gestion du risque.

---

## 3. Pourquoi XGBoost + arbres → règles

**Décision** : le moteur de découverte entraîne un **XGBoost** (régression sur
le rendement futur), puis **extrait les chemins des arbres** pour transformer
chaque feuille en règle candidate.

**Pourquoi XGBoost** :
- État de l'art sur données tabulaires financières (benchmarks MDPI 2025 :
  XGBoost meilleur en moyenne sur 6 modèles testés).
- Gère les NaN, les interactions non-linéaires, et produit des **arbres
  interprétables** par nature (contrairement aux réseaux de neurones).

**Pourquoi l'extraction de chemins** :
- Un chemin racine→feuille EST une règle : la conjonction des conditions
  menant à une feuille de prédiction extrême.
- Chaque feuille a un score (valeur prédite) → direction LONG si > 0,
  SHORT si < 0.
- Limite : les règles profondes (4+ conditions) se déclenchent trop rarement
  → calibration `max_depth=3` (testée sur données réelles, 2026-09-02).

**Leçons apprises d'einherjar (projet précurseur)** :
- `n_jobs=1` par worker (anti oversubscription CPU).
- Early stopping RÉEL (transmis au constructeur, pas au fit).
- Pas de `del locals()` (no-op en CPython).
- Correction du Sharpe multi-actif (échelle d'indépendance).

**Source** : « Label-Driven Optimization of Trading Models » (MDPI, 2025) —
XGBoost meilleur en moyenne ; l'horizon optimal varie par actif (3-10 jours).

---

## 4. Pourquoi les options définis-risque (spreads)

**Décision** : AURIGA exprime tous ses signaux en **spreads verticaux
définis-risque** (bull call, bear put, put/call credit spreads), jamais en
positions nues.

**Justification** :
1. **Exigence du hackathon** : « All strategies must incorporate options
   trading » — les options sont obligatoires.
2. **Risque borné** : un spread vertical a une perte maximale connue à
   l'avance (la largeur du spread). C'est un risk gate *structurel*, pas
   seulement procédural.
3. **Capital efficient** : le risque max par position est défini par la
   structure (margin requirement = risque max).
4. **Crédible** : les spreads définis-risque sont la pratique standard des
   institutionnels.

**Source** : documentation Alpaca (multi-leg Level 3 options, zero commission,
paper trading $100k).

---

## 5. Pourquoi l'architecture multi-agents

**Décision** : AURIGA ne se limite pas à un moteur directionnel. Il combine
**deux moteurs de stratégies** (direction + vente de prime) + **un signal de
risque** (volatilité) + des règles d'arrêt (AVOID_SELL) :

```
        ┌─────────────────────────────────────────────┐
        │  SIGNAL DE RISQUE VOL (A2, ex-agent vol)     │
        │  P(choc de vol) → gate vol_danger            │
        └──────────────────┬──────────────────────────┘
                           │ bloque si danger
        ┌──────────────────┴──────────────────────────┐
        │              RISK ENGINE (gates)             │
        │  daily loss · expositions · positions · vol  │
        └──────┬───────────────────────────┬───────────┘
               ▼                           ▼
        ┌──────────────┐            ┌──────────────────┐
        │ A1 Direction │            │ A3 Vendeur prime │
        │ (spreads     │            │ (credit spreads  │
        │  débit)      │            │  filtrés AVOID   │
        └──────────────┘            └──────────────────┘
```

**Rôle d'A2 après transformation (2026-09-03)** : A2 ne génère plus de
positions. Il produit un score de danger vol [0,1] par actif, consommé par le
Risk Engine (gate vol_danger) et par le narratif LLM.

**Justification** :
- **Diversification des sources d'alpha** : la direction (momentum) et la
  vente de prime (theta) sont des sources de rendement *orthogonales*. La
  vente de prime gagne en range, la direction gagne en tendance.
- **Gestion active du risque** : le signal de vol (A2) + les règles AVOID_SELL
  (A3) protègent le portefeuille des queues de risque — le problème central
  de la vente de prime.
- **Robustesse** : si une source échoue cette semaine, l'autre compense.
- **Crédibilité** : montrer des thèses distinctes + une mesure honnête de ce
  qui ne marche pas (l'achat de vol) = profondeur de recherche rare au jury.
- **Alignement avec les tracks du hackathon** : « Options Alpha Agents »
  (A1) et « Income & Portfolio Overlay Agents » (A3).

---

## 6. Agent A1 — Direction

**Objectif** : prédire la direction du prix (LONG/SHORT) sur un horizon
(6h/24h/48h en barres 1H).

**Méthode** :
- Label : rendement futur signé `Y_ret[t] = close[t+H]/close[t] − 1`.
- XGBoost régresseur sur 36 features techniques/quantitatives.
- Extraction des chemins d'arbres → règles LONG/SHORT.
- Backtest TP/SL ATR-based (anti-tautologie), admission BH/FDR + holdout.

**Résultat mesuré** (run 25 actifs, 03/09/2026) : 9 Einhers admis aux seuils
stricts (Sharpe≥2, WR≥0.65, PF≥1.5, trades≥30), 7 positions au portefeuille.
Les règles sont diversifiées (volatility, momentum, statistical, risk).

**Limite connue** : la prédiction de direction pure est le signal le plus
faible des marchés (bruit dominant). D'où les agents A2 et A3.

**Sources** :
- « Combating Overfitting in Quant Trading » — le boosting sur-fitte le bruit ;
  d'où depth=3, early stopping, admission stricte.
- « Volatility Forecasting and Return Prediction under Market Regimes »
  (arXiv 2606.09478) — la prédictibilité des retours est faible ; celle de la
  volatilité est forte.

---

## 7. Agent A2 — Signal de risque de volatilité (transformé, 2026-09-03)

**DÉCISION DE CONCEPTION MAJEURE** : après mesure sur données réelles,
A2 ne produit PLUS de stratégies de trading autonomes. Il est transformé
en **indicateur de risque** (VolSignal).

**Mesure qui a motivé la décision** (AAPL 1H, backtest Black-Scholes
corrigé avec annualisation + anti-tautologie — *proxy synthétique, la vol
réalisée servant d'entrée : Alpaca ne fournit pas d'historique de prix
d'options gratuit, voir SUBMISSION_WRITEUP §5*) :
- Les straddles longs (achat de vol) sont **globalement PERDANTS** :
  sharpe médian −2.64 sur les règles avec >5 trades.
- Ce résultat est conforme à la littérature : la prime de risque de vol
  (IV > RV) rend l'achat de vol structurellement coûteux.

**Nouveau rôle** : A2 prédit `P(choc de vol dans les H prochaines barres)`
via un XGBClassifier sur le label `RV[t+H] > 1.5×RV[t]`. Ce signal est
exploité par :
1. Le **Risk Engine** : proba > seuil → gate `vol_danger` bloque les
   nouvelles ventes de prime (A3). C'est le rôle principal.
2. Le **vendeur de prime** : ne vendre QUE si vol_signal < seuil.
3. Le **narratif LLM** : le risque de vol du jour est expliqué au jury.

**Mesure** : AUC = 0.746 sur AAPL (la vol est prédictible — conforme
arXiv 2606.09478 : la vol est persistante, les retours non).

**Source** : Ilmanen (2012) + réponse de Taleb + mesure directe sur nos
données (DESIGN_RATIONALE, ce document).

---

## 8. Agent A3 — Vendeur de prime (vente gatée)

**Objectif** : vendre des credit spreads de façon SYSTÉMATIQUE quand le
régime est calme, et S'ARRÊTER quand les signaux de risque (A2 vol_danger
+ règles AVOID_SELL) détectent une période dangereuse.

**Pourquoi la vente de prime gagne en moyenne** :
- Le « variance risk premium » : la vol implicite est structurellement
  SUPÉRIEURE à la vol réalisée (les acheteurs d'assurance paient plus que la
  juste valeur). Vendre = encaisser cette prime.
- Ilmanen (2012) : « La preuve empirique est sans ambiguïté : vendre de
  l'assurance et des tickets de loterie a généré des récompenses positives à
  long terme. »
- **Mesure locale** : sur AAPL 1H, ~98.3% des périodes sont profitables à la
  vente d'un short straddle — la base est de vendre. (P&L reconstruit par
  **proxy Black-Scholes** sur vol réalisée, pas par des prix d'options
  historiques — la formulation exacte est : « ~98% des périodes sont
  profitables *selon notre proxy synthétique de pricing* ».)

**Le rôle du ML (gating)** : la vente de prime subit des **pertes
catastrophiques rares** (~1.7% des périodes mesurées). Le ML n'apprend PAS
à prédire la direction : il apprend à reconnaître les ~2% de périodes
DANGEREUSES (règles AVOID_SELL) et à s'arrêter. C'est un filtre de risque.

**Mesure** : 20 règles AVOID_SELL cohérentes sur AAPL (ex : max_dd récent
+ mfi surachat + kurtosis bas = zone dangereuse pour vendre).

**Expression options** : put credit spread / call credit spread (défini-risque),
strike vendu ~3% OTM, protection ~5% plus loin.

**Sources** :
- Ilmanen (2012) — la prime de vente de vol.
- « Options Selling Using Machine Learning » (SSRN 4766370, 2024) — le ML
  améliore le vanilla selling (Sharpe et rendements mensuels supérieurs).

---

## 9. Routeur de régime

**ÉTAT AU CODE FREEZE (04/09/2026)** : il n'existe PAS de méta-routeur
implémenté comme module autonome dans le MVP. L'arbitrage entre agents est
assuré par l'orchestration (chaque agent n'agit que lorsque sa propre
condition se déclenche, et le Risk Engine tranche) :
- **Tendance haussière/baissière** → Agent A1 (direction, spreads débit).
- **Range / vol basse** → Agent A3 (vendre de la prime, credit spreads).
- **Pré-choc / vol élevée** → le signal A2 **bloque** A3 (gate vol_danger) —
  A2 ne produit plus JAMAIS d'achat de vol (mesure : straddles longs perdants,
  voir §7).

**Note sur la conception initiale** : un classifieur de régime (features
regime_50, vol_regime_50, Hurst, choppiness, kaufman efficiency) était prévu
pour router l'allocation. Ces features restent calculées par le pipeline de
features, mais le routeur lui-même n'a pas été nécessaire : la logique
« chaque agent agit quand SA condition se déclenche, le Risk Engine tranche »
a suffi au MVP et évite une couche de paramètres supplémentaire à 24h de la
deadline. Un routeur explicite reste une piste V2.

**Source** : « Tabular Deep Learning for Algorithmic Trading: Cross-Regime
Bayesian Optimisation » (arXiv 2608.27076) — la robustesse aux régimes est la
clé de la généralisation out-of-sample (direction de recherche pour V2).

---

## 10. Pourquoi le LLM hybride (propose, ne décide pas)

**Décision** : le LLM génère le narratif quotidien et PEUT proposer des
hypothèses de règles, mais **ne décide JAMAIS** d'un trade. Toute décision
d'exécution passe par le moteur déterministe (backtest + admission + risk
gates).

**Justification** :
1. **Sécurité** : un LLM qui décide = risque d'hallucination, de dérive, de
   comportement non reproductible.
2. **Crédibilité** : les risk gates doivent être déterministes et auditables.
3. **Conformité** : le cahier des charges du hackathon exige des risk gates
   explicites.

**Source** : bonnes pratiques agentiques 2025-2026 (le LLM propose, le code
dispose) + cahier des charges AURIGA D2.

---

## 11. Choix techniques

| Choix | Décision | Justification |
|---|---|---|
| **Données** | Alpaca Market Data, feed IEX, 5 ans, 1H | IEX gratuit, 1H = TF avec assez de barres (~10k/actif), 1D trop peu (t-stat~0.13 mesuré) |
| **Univers** | 25 large caps US + ETF avec options liquides | Options obligatoires, liquidité, diversité sectorielle |
| **Features** | 36 fonctions Numba extraites de midasV3 | Réutilise un pipeline éprouvé, pas de fuite future (rolling) |
| **Horizons** | 6h / 24h / 48h (1H) | Courts pour le hackathon (P&L en 5 jours), alignés détention options |
| **Backtest** | TP/SL ATR, SL-first si simultané, coûts 0.1% | Anti-tautologie, conservateur |
| **Admission** | Seuils stricts (Sharpe≥2, WR≥0.65, PF≥1.5, trades≥30) + BH/FDR adaptatif + holdout vierge | Contrôle multi-tests, anti-overfitting |
| **Sélection** | Score pondéré + diversify Jaccard + sizing mixte vol-target/Kelly | Portefeuille diversifié, risque maîtrisé |
| **Exécution** | alpaca-py, ordres multi-leg MLEG, paper $100k | Format officiel Alpaca |
| **Risque** | 8 gates déterministes + ML (voir write-up §2) : daily loss, exposition actif/secteur/total, positions max, liquidation −25%, gate vol_danger (A2), règles AVOID_SELL (A3) — **fail-closed** | REQ-F-RSK du cahier des charges ; une gate invérifiable bloque l'ordre |

---

## 12. Références complètes

1. **Ilmanen, A. (2012)** — *Do Financial Markets Reward Buying or Selling
   Insurance and Lottery Tickets?* Financial Analysts Journal 68(5) + réponse
   de N. Taleb. AQR.
   → Primes de risque asymétriques : vente de vol vs achat de vol.

2. **Joshi, Venkateswaran, Bhattacharyya (2024)** — *Options Selling Using
   Machine Learning.* SSRN 4766370 (WorldQuant University).
   → Le ML améliore la vente systématique de strangles (Sharpe supérieur).

3. **MDPI Mathematics (2025)** — *Label-Driven Optimization of Trading Models
   Across Indices and Stocks.*
   → XGBoost meilleur en moyenne ; horizon optimal par actif (3-10 jours).

4. **arXiv 2606.09478** — *Volatility Forecasting and Return Prediction under
   Market Regimes.*
   → La vol est prédictible ; les retours non. Signaux conditionnés au régime.

5. **arXiv 2608.27076** — *Tabular Deep Learning for Algorithmic Trading:
   Cross-Regime Bayesian Optimisation.*
   → Robustesse aux régimes = clé de la généralisation OOS.

6. **arXiv 2606.24575** — *Quant Convergence: Value Investing vs Modern
   Factor Models.*
   → Les règles simples robustes battent les modèles complexes.

7. **« Combating Overfitting in Quant Trading »** (guide pratique)
   → Le boosting (XGBoost) sur-fitte le bruit ; régularisation + bagging +
   admission stricte nécessaires.

8. **Documentation Alpaca** — Trading API, MCP Server, multi-leg options
   (Level 3), paper trading.

9. **Cahier des charges AURIGA v0.2** — SRS complet (ISO/IEC/IEEE 29148),
   décisions D1-D15, 116+ exigences.

---

*Document généré pour AURIGA — Hackathon Alpaca AI Trading Agents 2026.*
*Aucun contenu de ce document n'est un conseil financier.*