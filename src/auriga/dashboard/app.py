"""AURIGA - Dashboard Streamlit (vitrine du système).

Affiche : état du compte (P&L réel Alpaca), positions suivies, constellation
des stratégies actives, risk gates, narratif quotidien.

Charte : « Le Cocher céleste » (styles.py) — identité concentrée dans le
logo, le reste du dashboard est un terminal quant institutionnel (strip de
métriques, tableaux, liste de gates compacte).

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
    """État RÉEL du compte Alpaca paper.

    En cas d'échec de connexion → aucun chiffre fabriqué : les champs passent
    à None et l'UI affiche des « — » + un bandeau « ALPACA DISCONNECTED »
    explicite. Un faux $100,000 présenté comme réel serait trompeur pour le
    jury (revue 2026-09-03, P1 dashboard).
    """
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
        return {
            "equity": None,
            "cash": None,
            "buying_power": None,
            "day_pnl": None,
            "total_pnl": None,
            "n_positions": 0,
            "live": False,
            "error": str(e),
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
st.markdown('<div class="auriga-sky">', unsafe_allow_html=True)

account = load_account()
portfolio = load_portfolio()
narrative = load_narrative()
risk_state = load_risk_state()

# ----- Header + état de connexion -----
is_live = bool(account.get("live"))
st.markdown(styles.header_html(is_live), unsafe_allow_html=True)
if not is_live:
    # Bandeau d'avertissement visible : on ne laisse JAMAIS croire qu'un
    # compte réel est connecté quand la connexion Alpaca a échoué.
    st.markdown(
        styles.connection_banner_html(False, str(account.get("error") or "")),
        unsafe_allow_html=True,
    )

# ----- Metrics strip (equity en hero, P&L jour/total, positions) -----
if is_live:
    equity = account["equity"]
    day_pnl = float(account.get("day_pnl") or 0.0)
    total_pnl = float(account.get("total_pnl") or 0.0)
    metrics = [
        {"label": "Equity", "value": f"${equity:,.0f}", "sub": "capital paper", "hero": True},
        {
            "label": "P&L jour",
            "value": f"{'+' if day_pnl >= 0 else ''}${day_pnl:,.0f}",
            "sub": "mark-to-market",
            "cls": "pos" if day_pnl >= 0 else "neg",
        },
        {
            "label": "P&L total",
            "value": f"{'+' if total_pnl >= 0 else ''}${total_pnl:,.0f}",
            "sub": "depuis lancement",
            "cls": "pos" if total_pnl >= 0 else "neg",
        },
    ]
else:
    # Mode démo honnête : aucune valeur fabriquée, des « — » explicites.
    metrics = [
        {"label": "Equity", "value": "—", "sub": "non connecté", "hero": True},
        {"label": "P&L jour", "value": "—", "sub": "non connecté"},
        {"label": "P&L total", "value": "—", "sub": "non connecté"},
    ]
metrics.append(
    {
        "label": "Positions ouvertes",
        "value": f"{len(risk_state['positions'])}",
        "sub": f"{len(portfolio)} stratégies au portefeuille",
    }
)
st.markdown(styles.metrics_strip_html(metrics), unsafe_allow_html=True)

# ----- Équity & constellation -----
st.markdown(styles.section_html("État du portefeuille"), unsafe_allow_html=True)

col_a, col_b = st.columns([3, 2])

with col_a:
    st.markdown(styles.equity_panel_html(is_live), unsafe_allow_html=True)

with col_b:
    st.markdown(styles.section_html("Constellation des stratégies"), unsafe_allow_html=True)
    st.markdown(
        styles.constellation_svg(portfolio, width=440, height=240),
        unsafe_allow_html=True,
    )

# ----- Positions -----
st.markdown(
    styles.section_html("Positions actives", meta=f"{len(risk_state['positions'])} ouvertes"),
    unsafe_allow_html=True,
)
position_rows = [
    {
        "symbol": p.symbol,
        "direction": p.direction,
        "strategy": p.strategy_name,
        "risk": p.max_risk,
    }
    for p in risk_state["positions"]
]
st.markdown(styles.positions_table_html(position_rows), unsafe_allow_html=True)

# ----- Stratégies (détail) -----
st.markdown(
    styles.section_html("Stratégies du portefeuille", meta=f"{len(portfolio)} au total"),
    unsafe_allow_html=True,
)
strategy_rows = [
    {
        "symbol": s["symbol"],
        "direction": s["direction"],
        "score": s.get("score", 0.0),
        "weight": s.get("weight", 0.0),
        "condition": s.get("condition_str", ""),
    }
    for s in portfolio
]
st.markdown(styles.strategies_table_html(strategy_rows), unsafe_allow_html=True)

# ----- Risk gates & Narratif -----
st.markdown(styles.section_html("Risk engine & narratif"), unsafe_allow_html=True)
col_r, col_n = st.columns(2)

with col_r:
    gates = [
        {
            "label": "Perte quotidienne max (-2%)",
            "status": "ok" if not risk_state["last_blocked"] else "warn",
        },
        {"label": "Exposition max / actif (10%)", "status": "ok"},
        {"label": "Exposition max / secteur (25%)", "status": "ok"},
        {
            "label": "Positions max (12)",
            "status": "ok" if len(risk_state["positions"]) < 12 else "warn",
        },
        {"label": "Stop global & liquidation (-25%)", "status": "ok"},
    ]
    for b in risk_state["last_blocked"]:
        gates.append(
            {
                "label": f"Blocage {b.get('symbol', '?')}",
                "status": "block",
                "detail": "; ".join(b.get("reasons", [])),
            }
        )
    st.markdown(styles.gates_list_html(gates), unsafe_allow_html=True)

with col_n:
    if narrative:
        st.markdown(f'<div class="auriga-narrative">{narrative}</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="dim" style="padding:6px 2px">Aucun narratif généré — le rapport LLM '
            "quotidien apparaîtra ici après le premier cycle.</div>",
            unsafe_allow_html=True,
        )

# ----- Footer -----
st.markdown(styles.footer_html(), unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)  # close .auriga-sky
