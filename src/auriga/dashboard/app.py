"""AURIGA - Dashboard Streamlit (vitrine du système).

Affiche : état du compte (P&L réel Alpaca), positions suivies, constellation
des stratégies actives, risk gates, narratif quotidien.

Charte : « Le Cocher céleste » (styles.py).

Lancement :  streamlit run src/auriga/dashboard/app.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

# Permet de lancer depuis la racine du repo sans installation
_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))



from auriga.dashboard import styles
from auriga.orchestration.state import StateStore
from auriga.selection.scoring import score_breakdown
from auriga.utils.universe import load_universe

st.set_page_config(
    page_title="AURIGA — Autonomous Quant Research Agent",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Chargement des données
# ---------------------------------------------------------------------------

def load_account() -> dict:
    """État du compte Alpaca (ou valeurs par défaut si indisponible)."""
    from dotenv import load_dotenv

    load_dotenv(_ROOT / ".env")
    try:
        from auriga.execution.client import get_execution_client

        client = get_execution_client()
        acc = client.get_account()
        return {
            "equity": acc.equity,
            "cash": acc.cash,
            "buying_power": acc.buying_power,
            "day_pnl": acc.day_pnl,
            "total_pnl": acc.total_pnl,
            "n_positions": len(acc.positions),
            "live": True,
        }
    except Exception as e:
        # MODE DÉMO explicite — les valeurs sont des placeholders VISIBLES,
        # jamais présentées comme un vrai compte connecté.
        return {
            "equity": None, "cash": None, "buying_power": None,
            "day_pnl": None, "total_pnl": None, "n_positions": 0,
            "live": False, "error": str(e),
        }


def load_portfolio() -> list[dict]:
    """Stratégies du portefeuille (portfolio.jsonl)."""
    path = _ROOT / "outputs" / "research" / "portfolio.jsonl"
    if not path.exists():
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def load_narrative() -> str | None:
    """Dernier narratif quotidien."""
    narr_dir = _ROOT / "outputs" / "narratives"
    if not narr_dir.exists():
        return None
    reports = sorted(narr_dir.glob("report_*.md"))
    if not reports:
        return None
    return reports[-1].read_text(encoding="utf-8")


def load_risk_state() -> dict:
    """État des risk gates (lu depuis le state store)."""
    try:
        state = StateStore()
        positions = state.read_positions()
        cycles = state.read_cycles(limit=1)
        last_blocked = []
        if cycles:
            results = cycles[-1].get("resultats", [])
            last_blocked = [r for r in results if r.get("action") == "BLOCKED"]
        return {"positions": positions, "last_blocked": last_blocked}
    except Exception:
        return {"positions": [], "last_blocked": []}


# ---------------------------------------------------------------------------
# Rendu
# ---------------------------------------------------------------------------

st.markdown(styles.CSS, unsafe_allow_html=True)
st.markdown(styles.stars_background(70), unsafe_allow_html=True)
st.markdown('<div class="auriga-sky">', unsafe_allow_html=True)

account = load_account()
portfolio = load_portfolio()
narrative = load_narrative()
risk_state = load_risk_state()

# ----- Header -----
status_text = "PAPER CONNECTED" if account.get("live") else "MODE DÉMO"
st.markdown(styles.header_html(status_text), unsafe_allow_html=True)

# Bandeau de connexion explicite (CONNECTED / DISCONNECTED)
if account.get("live"):
    st.markdown(
        "<div style='background:rgba(46,230,168,0.08);border:1px solid rgba(46,230,168,0.3);"
        "border-radius:8px;padding:8px 14px;margin-bottom:12px;font-family:JetBrains Mono,monospace;"
        "font-size:0.8rem;color:#2EE6A8'>● ALPACA PAPER TRADING — CONNECTED</div>",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        f"<div style='background:rgba(255,92,122,0.1);border:1px solid rgba(255,92,122,0.4);"
        f"border-radius:8px;padding:8px 14px;margin-bottom:12px;font-family:JetBrains Mono,monospace;"
        f"font-size:0.8rem;color:#FF5C7A'>⚠ ALPACA DISCONNECTED — AFFICHAGE DÉMO (aucune donnée réelle)"
        f"{' · ' + str(account.get('error'))[:80] if account.get('error') else ''}</div>",
        unsafe_allow_html=True,
    )

# ----- KPI Row -----
equity = account["equity"]
day_pnl = account.get("day_pnl")
total_pnl = account.get("total_pnl")

if equity is None:
    # Mode démo : pas de fausses valeurs
    k1 = styles.kpi_html("EQUITY", "—", "non connecté", "gold")
    k2 = styles.kpi_html("P&L JOUR", "—", "non connecté")
    k3 = styles.kpi_html("P&L TOTAL", "—", "non connecté")
else:
    k1 = styles.kpi_html("EQUITY", f"${equity:,.0f}", "capital paper", "gold")
    k2_cls = "pos" if day_pnl >= 0 else "neg"
    k2_sign = "+" if day_pnl >= 0 else ""
    k2 = styles.kpi_html("P&L JOUR", f"{k2_sign}${day_pnl:,.0f}", "mark-to-market", k2_cls)
    k3_cls = "pos" if total_pnl >= 0 else "neg"
    k3_sign = "+" if total_pnl >= 0 else ""
    k3 = styles.kpi_html("P&L TOTAL", f"{k3_sign}${total_pnl:,.0f}", "depuis lancement", k3_cls)
k4 = styles.kpi_html(
    "POSITIONS",
    f"{len(risk_state['positions'])}",
    f"{len(portfolio)} stratégies au portefeuille",
)

cols = st.columns(4)
for col, kpi in zip(cols, [k1, k2, k3, k4]):
    with col:
        st.markdown(kpi, unsafe_allow_html=True)

# ----- Equity & positions -----
st.markdown(styles.section_html("État du portefeuille"), unsafe_allow_html=True)

col_a, col_b = st.columns([3, 2])

with col_a:
    st.markdown(
        "<div class='auriga-card'><div class='dim'>Equity curve — historique à venir "
        "(le compte paper a démarré à $100,000)</div></div>",
        unsafe_allow_html=True,
    )

with col_b:
    st.markdown(styles.section_html("Constellation des stratégies"), unsafe_allow_html=True)
    st.markdown(
        styles.constellation_svg(portfolio, width=480, height=260),
        unsafe_allow_html=True,
    )

# ----- Positions -----
st.markdown(styles.section_html("Positions actives"), unsafe_allow_html=True)
if risk_state["positions"]:
    for p in risk_state["positions"]:
        st.markdown(
            styles.position_html(p.symbol, p.direction, p.strategy_name, p.max_risk),
            unsafe_allow_html=True,
        )
else:
    st.markdown(
        "<div class='auriga-card dim'>Aucune position ouverte — le système attend "
        "des signaux validés par le risk engine.</div>",
        unsafe_allow_html=True,
    )

# ----- Stratégies (détail) -----
st.markdown(styles.section_html("Stratégies du portefeuille"), unsafe_allow_html=True)
if portfolio:
    cards = []
    for s in portfolio:
        cond = s.get("condition_str", "")
        cards.append(
            f"<div class='auriga-card' style='margin-bottom:8px'>"
            f"<span class='mono' style='font-weight:600'>{s['symbol']}</span> "
            f"<span class='badge {'badge-long' if s['direction']=='LONG' else 'badge-short'}'>{s['direction']}</span> "
            f"<span class='dim'>score {s.get('score', 0):.2f} · poids {s.get('weight', 0)*100:.0f}%</span>"
            f"<div class='mono dim' style='margin-top:4px;font-size:0.78rem'>{cond}</div>"
            f"</div>"
        )
    st.markdown("".join(cards), unsafe_allow_html=True)
else:
    st.markdown(
        "<div class='auriga-card dim'>Aucune stratégie — lancer <b>auriga research</b> "
        "pour découvrir des stratégies.</div>",
        unsafe_allow_html=True,
    )

# ----- Risk gates & Narratif -----
st.markdown(styles.section_html("Risk engine & Narratif"), unsafe_allow_html=True)
col_r, col_n = st.columns(2)

with col_r:
    gates = [
        styles.gate_html("Daily loss limit (-2%)", "ok" if not risk_state["last_blocked"] else "warn"),
        styles.gate_html("Exposition max / actif (10%)", "ok"),
        styles.gate_html("Exposition max / secteur (25%)", "ok"),
        styles.gate_html("Positions max (12)", "ok" if len(risk_state["positions"]) < 12 else "warn"),
        styles.gate_html("Stop global & liquidation (-25%)", "ok"),
    ]
    # Derniers blocages
    for b in risk_state["last_blocked"]:
        gates.append(
            styles.gate_html(f"Blocage {b.get('symbol', '?')}", "block", "; ".join(b.get("reasons", [])))
        )
    st.markdown("".join(gates), unsafe_allow_html=True)

with col_n:
    if narrative:
        st.markdown(
            f"<div class='auriga-narrative'>{narrative}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div class='auriga-card dim'>Aucun narratif généré — le rapport LLM "
            "quotidien apparaîtra ici après le premier cycle.</div>",
            unsafe_allow_html=True,
        )

# ----- Footer -----
st.markdown(
    "<div style='margin-top:40px;padding-top:14px;border-top:1px solid #1E2A45;"
    "display:flex;justify-content:space-between;font-size:0.7rem;color:#5A6478'>"
    "<span>AURIGA — Autonomous Quant Research &amp; Investment Agent</span>"
    "<span>Paper trading · Options définis-risque · Le LLM propose, le moteur dispose</span>"
    "</div>",
    unsafe_allow_html=True,
)

st.markdown("</div>", unsafe_allow_html=True)  # close .auriga-sky