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
5. [Pourquoi la multi-agent architecture (3 moteurs + routeur)](#5-pourquoi-larchitecture-multi-agents)
6. [Agent A1 — Direction (momentum/régression)](#6-agent-a1--direction)
7. [Agent A2 — Volatilité directionnelle (achat conditionnel)](#7-agent-a2--volatilité-directionnelle)
8. [Agent A3 — Vendeur de prime (vente gatée)](#8-agent-a3--vendeur-de-prime)
9. [Routeur de régime (méta-agent)](#9-routeur-de-régime)
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
(signal faible, bruit dominant), AURIGA combine **plusieurs moteurs de recherche
spécialisés** — direction, volatilité, vente de prime — chacun exploitant une
source de rendement différente et robuste. La diversification des *sources
d'alpha* est la vraie protection contre l'overfitting et la non-stationnarité
des marchés.

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
**trois moteurs de recherche spécialisés** + un routeur de régime :

```
                    ┌─────────────────────┐
                    │  Routeur de régime   │
                    │  (méta-agent)        │
                    └──────────┬──────────┘
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌──────────┐   ┌──────────┐   ┌──────────┐
        │ A1       │   │ A2       │   │ A3       │
        │ Direction│   │ Volatilité│  │ Vendeur  │
        │ XGBoost  │   │ (achat)  │   │ prime    │
        └──────────┘   └──────────┘   └──────────┘
```

**Justification** :
- **Diversification des sources d'alpha** : la direction (momentum), la
  volatilité (achat conditionnel), et la vente de prime (theta) sont des
  sources de rendement *orthogonales*. Leur corrélation est faible.
- **Robustesse** : si une source échoue cette semaine (ex: marché en range →
  la direction perd), une autre compense (le vendeur de prime gagne en range).
- **Crédibilité** : montrer 3 thèses distinctes = profondeur de recherche.
- **Alignement avec les tracks du hackathon** : « Options Alpha Agents »
  (A1+A2) et « Income & Portfolio Overlay Agents » (A3).

**Sources** :
- Ilmanen (2012) : la vente de prime et l'achat de vol sont les deux faces
  d'une même prime de risque ; les combiner diversifie.
- Taleb (réponse à Ilmanen) : l'achat d'options conditionnel (quand le risque
  de queue est mal payé) est défendable — le ML permet ce timing.

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

## 7. Agent A2 — Volatilité directionnelle (achat conditionnel)

**Objectif** : prédire si la **volatilité va AUGMENTER ou DIMINUER** sur
l'horizon. Quand la hausse de vol est prédite avec confiance → **ACHETER** de
la volatilité (long straddle/strangle) ; quand la baisse est prédite → ne rien
faire (ou laisser A3 vendre).

**Label** : `Y_vol[t] = vol_réalisée[t+H] / vol_réalisée[t] − 1` (signé).

**Features** : vol réalisée, GARCH, vol clustering, vol persistence, Hurst,
entropie, skewness (les 36 features actuelles contiennent déjà ces signaux).

**Pourquoi l'achat conditionnel est défendable** :
- L'achat PASSIF d'options perd en moyenne (Ilmanen 2012 : le long VIX a perdu
  ~28%/an). Mais l'achat **conditionnel**, quand le modèle détecte un régime de
  choc de vol imminent, transforme un actif à espérance négative en assurance
  rentable.
- Taleb : le vrai bénéfice du long-options est la **convexité** — il paie
  quand tout le reste échoue. Un système qui anticipe ces régimes capte cette
  convexité sans saigner en continu.

**Expression options** : long straddle ou strangle (achat call + put même
strike/expiration), ou strangle asymétrique selon le skew prédit.

**Sources** :
- Ilmanen (2012) + réponse de Taleb : le débat achat vs vente de vol.
- « Volatility Forecasting and Return Prediction under Market Regimes »
  (arXiv 2606.09478) : la vol est persistante et prédictible ; les signaux
  conditionnés au régime deviennent robustes.

---

## 8. Agent A3 — Vendeur de prime (vente gatée)

**Objectif** : détecter les régimes où **vendre de la prime** (credit spreads)
est favorable — typiquement vol élevée mais marché range-bound, pas de choc
imminent.

**Pourquoi la vente de prime gagne en moyenne** :
- Le « variance risk premium » : la vol implicite est structurellement
  SUPÉRIEURE à la vol réalisée (les acheteurs d'assurance paient plus que la
  juste valeur). Vendre = encaisser cette prime.
- Ilmanen (2012) : « La preuve empirique est sans ambiguïté : vendre de
  l'assurance et des tickets de loterie a généré des récompenses positives à
  long terme. »

**Le rôle du ML (gating)** : la vente de prime subit des **pertes
catastrophiques rares** (queues de risque). Le ML ne prédit PAS la direction ;
il décide QUAND vendre (régime calme) et QUAND NE PAS vendre (avant earnings,
crise, choc de vol). C'est un filtre de risque, pas un prédicteur de direction.

**Label** : 1 si un credit spread court sur [t, t+H] aurait été profitable
(backtest Black-Scholes), 0 sinon.

**Expression options** : put credit spread / call credit spread (défini-risque).

**Sources** :
- Ilmanen (2012) — la prime de vente de vol.
- « Options Selling Using Machine Learning » (SSRN 4766370, 2024) — le ML
  améliore le vanilla selling (Sharpe et rendements mensuels supérieurs).

---

## 9. Routeur de régime

**Objectif** : classifier le régime de marché courant et router l'allocation
vers l'agent adapté :
- **Tendance haussière/baissière** → Agent A1 (direction).
- **Range / vol basse** → Agent A3 (vendre de la prime).
- **Pré-choc / vol élevée** → Agent A2 (acheter de la vol).

**Méthode** : classification sur features de régime (regime_50,
vol_regime_50, Hurst, choppiness, kaufman efficiency). Simple et robuste
(seuils ou petit modèle).

**Source** : « Tabular Deep Learning for Algorithmic Trading: Cross-Regime
Bayesian Optimisation » (arXiv 2608.27076) — la robustesse aux régimes est la
clé de la généralisation out-of-sample.

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
| **Risque** | 6 gates (daily loss, exposure actif/secteur/total, positions) | REQ-F-RSK du cahier des charges |

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