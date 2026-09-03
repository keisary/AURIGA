"""AURIGA - Charte graphique du dashboard (CSS + helpers).

Thème : « Le Cocher céleste » — l'identité (nom, logo, or Capella) est
conservée, mais concentrée en un seul point de netteté (le logo dans le
header). Le reste du dashboard adopte une esthétique de terminal quant
institutionnel : hairlines, tableaux, une strip de métriques unifiée —
pensé pour être lu vite et pris au sérieux par un jury technique.

Toutes les couleurs sont définies une seule fois dans COLORS, puis
injectées comme CSS custom properties (:root) — aucune couleur n'est
dupliquée en dur dans la feuille de style.
"""
from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# Palette (charte AURIGA — révisée pour un rendu institutionnel)
# ---------------------------------------------------------------------------

COLORS = {
    "bg": "#06080D",          # quasi-noir, base terminal
    "surface": "#0B0F17",     # panneaux, table de fond
    "border": "#1B212C",      # hairline structurel
    "border_soft": "#141922", # séparateurs internes (lignes de tableau)
    "text": "#E7E9EE",        # texte principal
    "text_dim": "#8B93A3",    # texte secondaire / labels
    "text_faint": "#565E6C",  # texte tertiaire / footer
    "gold": "#C9A24B",        # or Capella, desaturé — accent unique
    "blue": "#4C7EDB",        # liens de la constellation
    "green": "#3ED9A4",       # positif (P&L, LONG)
    "red": "#F0566E",         # négatif (P&L, SHORT, blocage)
    "orange": "#E7A23D",      # avertissement
}

# ---------------------------------------------------------------------------
# CSS complet
# ---------------------------------------------------------------------------

def _root_vars() -> str:
    """Génère le bloc :root à partir de COLORS — source unique de vérité."""
    mapping = {
        "--bg": "bg", "--surface": "surface", "--border": "border",
        "--border-soft": "border_soft", "--text": "text",
        "--text-dim": "text_dim", "--text-faint": "text_faint",
        "--gold": "gold", "--blue": "blue", "--green": "green",
        "--red": "red", "--orange": "orange",
    }
    decls = "".join(f"{var}:{COLORS[key]};" for var, key in mapping.items())
    return f":root{{{decls}}}"


_BASE_CSS = """
* { box-sizing: border-box; }

.stApp {
    background:
      radial-gradient(700px 420px at 12% -8%, rgba(201,162,75,0.06), transparent 60%),
      var(--bg);
    color: var(--text);
    font-family: 'Inter', -apple-system, sans-serif;
}

#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; height: 0; }
.block-container { padding-top: 1.4rem; max-width: 1180px; }

.auriga-sky { position: relative; }

/* ===== Header ===== */
.auriga-header {
    display: flex; align-items: center; gap: 14px;
    padding: 6px 0 20px 0;
    border-bottom: 1px solid var(--border);
    margin-bottom: 22px;
}
.auriga-logo { width: 34px; height: 34px; flex-shrink: 0; }
.auriga-title {
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 600; font-size: 1.28rem; letter-spacing: 0.3px;
    color: var(--text); margin: 0; line-height: 1;
}
.auriga-title .gold { color: var(--gold); }
.auriga-subtitle { font-size: 0.76rem; color: var(--text-dim); margin: 4px 0 0 0; }
.auriga-status {
    margin-left: auto; display: flex; align-items: center; gap: 7px;
    font-family: 'JetBrains Mono', monospace; font-size: 0.7rem;
    color: var(--text-dim); border: 1px solid var(--border);
    padding: 5px 11px; border-radius: 4px; letter-spacing: 0.5px;
}
.auriga-status.live { color: var(--green); }
.auriga-status.off { color: var(--red); border-color: rgba(240,86,110,0.45); }
.auriga-status .dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.auriga-status.live .dot, .auriga-status.off .dot { animation: pulse-dot 2s infinite; }
@keyframes pulse-dot { 0%,100% { opacity: 1; } 50% { opacity: 0.35; } }

/* ===== Metrics strip (remplace le kit de 4 cartes KPI identiques) ===== */
.auriga-metrics {
    display: flex; border: 1px solid var(--border); border-radius: 6px;
    overflow: hidden; margin-bottom: 26px; background: var(--surface);
}
.auriga-metric { flex: 1; padding: 14px 20px; border-right: 1px solid var(--border); }
.auriga-metric:last-child { border-right: none; }
.auriga-metric-label { font-size: 0.74rem; color: var(--text-dim); margin-bottom: 6px; }
.auriga-metric-value {
    font-family: 'JetBrains Mono', monospace; font-weight: 600;
    font-variant-numeric: tabular-nums;
    font-size: 1.5rem; color: var(--text); line-height: 1.1;
}
.auriga-metric.hero .auriga-metric-value { font-size: 1.9rem; color: var(--gold); }
.auriga-metric-value.pos { color: var(--green); }
.auriga-metric-value.neg { color: var(--red); }
.auriga-metric-sub { font-size: 0.72rem; color: var(--text-faint); margin-top: 5px; }

/* ===== Sections (plus d'icône décorative répétée) ===== */
.auriga-section {
    display: flex; align-items: baseline; justify-content: space-between;
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 600; font-size: 0.98rem; color: var(--text);
    margin: 28px 0 10px 0; padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
}
.auriga-section .meta {
    font-family: 'Inter', sans-serif; font-weight: 400;
    font-size: 0.76rem; color: var(--text-dim);
}

/* ===== Panneaux (equity, états vides) ===== */
.auriga-panel {
    border: 1px solid var(--border); border-radius: 6px; background: var(--surface);
    padding: 18px 20px;
}
.auriga-panel.dim-text { color: var(--text-dim); font-size: 0.85rem; }

/* ===== Tableaux (remplace les cartes répétées pour positions/stratégies) ===== */
.auriga-table { width: 100%; border-collapse: collapse; font-size: 0.86rem; }
.auriga-table th {
    text-align: left; font-weight: 500; font-size: 0.72rem; color: var(--text-dim);
    padding: 0 10px 8px 10px; border-bottom: 1px solid var(--border);
}
.auriga-table th.num { text-align: right; }
.auriga-table td { padding: 9px 10px; border-bottom: 1px solid var(--border-soft); }
.auriga-table tr:last-child td { border-bottom: none; }
.auriga-table td.mono { font-family: 'JetBrains Mono', monospace; font-variant-numeric: tabular-nums; }
.auriga-table td.num { text-align: right; }
.auriga-table td.strong { font-weight: 600; }
.auriga-table td.dim { color: var(--text-dim); }
.auriga-table .side { font-size: 0.74rem; font-weight: 600; }
.auriga-table .side.long { color: var(--green); }
.auriga-table .side.short { color: var(--red); }
.auriga-table tr.cond-row td {
    padding-top: 0; padding-bottom: 12px; font-size: 0.76rem; color: var(--text-faint);
}

/* ===== Risk gates (liste compacte, plus de badge par item) ===== */
.auriga-gates { display: flex; flex-direction: column; gap: 2px; }
.auriga-gate-row { display: flex; align-items: center; gap: 10px; padding: 7px 4px; font-size: 0.82rem; }
.auriga-gate-row .dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.auriga-gate-row.ok .dot { background: var(--green); }
.auriga-gate-row.warn .dot { background: var(--orange); }
.auriga-gate-row.block .dot { background: var(--red); animation: pulse-dot 1.4s infinite; }
.auriga-gate-row .label { color: var(--text); }
.auriga-gate-row .detail { margin-left: auto; font-size: 0.74rem; color: var(--text-dim); }

/* ===== Narratif ===== */
.auriga-narrative {
    border-left: 2px solid var(--gold);
    padding: 4px 0 4px 16px; line-height: 1.65; font-size: 0.88rem; color: var(--text);
    max-height: 420px; overflow-y: auto;
}
.auriga-narrative h1, .auriga-narrative h2 { color: var(--gold); font-size: 1rem; margin: 14px 0 6px 0; }
.auriga-narrative strong { color: var(--text); }

/* ===== Constellation ===== */
.auriga-constellation {
    width: 100%; border: 1px solid var(--border); border-radius: 6px; background: var(--surface);
}
.auriga-constellation svg { width: 100%; height: auto; display: block; }

/* ===== Utilitaires ===== */
.mono { font-family: 'JetBrains Mono', monospace; }
.dim { color: var(--text-dim); font-size: 0.82rem; }

/* ===== Footer ===== */
.auriga-footer {
    margin-top: 36px; padding-top: 14px; border-top: 1px solid var(--border);
    display: flex; justify-content: space-between; font-size: 0.7rem; color: var(--text-faint);
}

/* ===== Scrollbar ===== */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

/* ===== Responsive ===== */
@media (max-width: 700px) {
    .auriga-metrics { flex-wrap: wrap; }
    .auriga-metric { flex: 1 1 50%; border-bottom: 1px solid var(--border); }
}
"""

CSS = (
    "<style>\n"
    "@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700"
    "&family=JetBrains+Mono:wght@400;500;600&family=Inter:wght@400;500;600&display=swap');\n"
    f"{_root_vars()}\n{_BASE_CSS}\n"
    "</style>"
)


# ---------------------------------------------------------------------------
# Helpers HTML
# ---------------------------------------------------------------------------

def logo_svg(size: int = 34) -> str:
    """Logo : constellation Auriga, Capella en or. Seul endroit où le motif
    céleste apparaît — c'est la marque, pas un fond répété."""
    pts = [(50, 8), (86, 30), (72, 72), (28, 72), (14, 30)]
    poly = " ".join(f"{x},{y}" for x, y in pts)
    gold, blue, text = COLORS["gold"], COLORS["blue"], COLORS["text"]
    return f"""
    <svg class="auriga-logo" width="{size}" height="{size}" viewBox="0 0 100 100">
      <polygon points="{poly}" fill="none" stroke="{blue}" stroke-width="1.3"
        stroke-opacity="0.55" stroke-linejoin="round"/>
      <line x1="50" y1="8" x2="72" y2="72" stroke="{blue}" stroke-width="0.8" stroke-opacity="0.25"/>
      <line x1="50" y1="8" x2="28" y2="72" stroke="{blue}" stroke-width="0.8" stroke-opacity="0.25"/>
      <line x1="14" y1="30" x2="86" y2="30" stroke="{blue}" stroke-width="0.8" stroke-opacity="0.25"/>
      <circle cx="50" cy="8" r="4" fill="{gold}"/>
      <circle cx="86" cy="30" r="1.8" fill="{text}" opacity="0.8"/>
      <circle cx="72" cy="72" r="1.6" fill="{text}" opacity="0.8"/>
      <circle cx="28" cy="72" r="1.6" fill="{text}" opacity="0.8"/>
      <circle cx="14" cy="30" r="1.8" fill="{text}" opacity="0.8"/>
    </svg>
    """


def header_html(live: bool) -> str:
    """Header avec état de connexion explicite dans le chip (coin droit) :
    « PAPER CONNECTED » (vert, dot pulsant) ou « DISCONNECTED » (rouge)."""
    status_text = "PAPER CONNECTED" if live else "DISCONNECTED"
    status_cls = "live" if live else "off"
    return f"""
    <div class="auriga-header">
      {logo_svg()}
      <div>
        <p class="auriga-title">AURIGA<span class="gold">.</span></p>
        <p class="auriga-subtitle">Autonomous Quant Research Agent</p>
      </div>
      <div class="auriga-status {status_cls}"><span class="dot"></span>{status_text}</div>
    </div>
    """


def connection_banner_html(live: bool, error: str = "") -> str:
    """Bandeau d'état — rendu UNIQUEMENT quand la connexion Alpaca a échoué.

    Le mode connecté reste épuré (le chip vert du header suffit). En mode
    démo/déconnecté, aucune ambiguïté : message d'avertissement explicite,
    aucune donnée réelle n'est affichée par ailleurs.
    """
    if live:
        return ""
    err = f" · {error[:100]}" if error else ""
    return (
        "<div style='background:rgba(240,86,110,0.08);border:1px solid "
        "rgba(240,86,110,0.35);border-radius:6px;padding:9px 14px;"
        "margin-bottom:14px;font-family:JetBrains Mono,monospace;"
        "font-size:0.78rem;color:var(--red)'>"
        "⚠ ALPACA DISCONNECTED — AFFICHAGE DÉMO (aucune donnée réelle)"
        f"{err}</div>"
    )


def metrics_strip_html(metrics: list[dict]) -> str:
    """Strip de métriques unifiée (remplace 4 cartes KPI identiques).

    Chaque item : {"label": str, "value": str, "sub": str,
                    "cls": "pos"|"neg"|"" (optionnel), "hero": bool (optionnel)}.
    Le premier métrique porté en "hero" prend la place du gros chiffre —
    ici l'equity, la donnée la plus importante du dashboard.
    """
    parts = []
    for m in metrics:
        cls = m.get("cls", "")
        hero_cls = "hero" if m.get("hero") else ""
        parts.append(
            f'<div class="auriga-metric {hero_cls}">'
            f'<div class="auriga-metric-label">{m["label"]}</div>'
            f'<div class="auriga-metric-value {cls}">{m["value"]}</div>'
            f'<div class="auriga-metric-sub">{m.get("sub", "")}</div>'
            f'</div>'
        )
    return f'<div class="auriga-metrics">{"".join(parts)}</div>'


def section_html(title: str, meta: str = "") -> str:
    meta_html = f'<span class="meta">{meta}</span>' if meta else ""
    return f'<div class="auriga-section"><span>{title}</span>{meta_html}</div>'


def equity_panel_html(live: bool, starting_capital: float = 100_000.0) -> str:
    """État vide honnête pour la courbe d'equity — pas de faux graphique."""
    note = (
        "Historique en cours de constitution — la courbe apparaîtra après "
        "les premiers cycles enregistrés."
        if live else
        "Compte de démonstration — aucun historique réel à afficher."
    )
    return (
        '<div class="auriga-panel dim-text" style="min-height:220px;display:flex;'
        'flex-direction:column;justify-content:center;align-items:center;'
        'text-align:center;gap:6px">'
        f'<div class="mono" style="color:var(--text-dim);font-size:0.82rem">'
        f'Capital de départ : ${starting_capital:,.0f}</div>'
        f'<div>{note}</div>'
        '</div>'
    )


def positions_table_html(rows: list[dict]) -> str:
    """rows: [{"symbol", "direction", "strategy", "risk"}]"""
    if not rows:
        return (
            '<div class="dim" style="padding:6px 2px">Aucune position ouverte — '
            'le système attend des signaux validés par le risk engine.</div>'
        )
    body = []
    for r in rows:
        side_cls = "long" if r["direction"] == "LONG" else "short"
        body.append(
            f'<tr><td class="mono strong">{r["symbol"]}</td>'
            f'<td><span class="side {side_cls}">{r["direction"]}</span></td>'
            f'<td class="dim">{r["strategy"]}</td>'
            f'<td class="mono num">${r["risk"]:,.0f}</td></tr>'
        )
    return (
        '<table class="auriga-table"><thead><tr>'
        '<th>Symbole</th><th>Sens</th><th>Stratégie</th><th class="num">Risque max</th>'
        '</tr></thead><tbody>' + "".join(body) + '</tbody></table>'
    )


def strategies_table_html(rows: list[dict]) -> str:
    """rows: [{"symbol", "direction", "score", "weight", "condition"}]"""
    if not rows:
        return (
            '<div class="dim" style="padding:6px 2px">Aucune stratégie — lancer '
            '<span class="mono">auriga research</span> pour découvrir des stratégies.</div>'
        )
    body = []
    for r in rows:
        side_cls = "long" if r["direction"] == "LONG" else "short"
        body.append(
            f'<tr><td class="mono strong">{r["symbol"]}</td>'
            f'<td><span class="side {side_cls}">{r["direction"]}</span></td>'
            f'<td class="mono num">{r["score"]:.2f}</td>'
            f'<td class="mono num">{r["weight"] * 100:.0f}%</td></tr>'
        )
        if r.get("condition"):
            body.append(
                f'<tr class="cond-row"><td colspan="4" class="mono">{r["condition"]}</td></tr>'
            )
    return (
        '<table class="auriga-table"><thead><tr>'
        '<th>Symbole</th><th>Sens</th><th class="num">Score</th><th class="num">Poids</th>'
        '</tr></thead><tbody>' + "".join(body) + '</tbody></table>'
    )


def gates_list_html(gates: list[dict]) -> str:
    """gates: [{"label", "status": "ok"|"warn"|"block", "detail"}]"""
    rows = []
    for g in gates:
        rows.append(
            f'<div class="auriga-gate-row {g["status"]}"><span class="dot"></span>'
            f'<span class="label">{g["label"]}</span>'
            f'<span class="detail">{g.get("detail", "")}</span></div>'
        )
    return f'<div class="auriga-gates">{"".join(rows)}</div>'


def constellation_svg(strategies: list[dict], width: int = 640, height: int = 320) -> str:
    """Constellation des stratégies actives — étoile = stratégie, taille = score."""
    if not strategies:
        return (
            "<div class='dim' style='padding:30px;text-align:center'>"
            "Aucune stratégie active — lancer la recherche</div>"
        )

    n = len(strategies)
    cx, cy = width / 2, height / 2
    r = min(width, height) / 2 - 36
    positions = []
    for i, s in enumerate(strategies):
        angle = -math.pi / 2 + 2 * math.pi * i / n
        x = cx + r * 0.85 * math.cos(angle)
        y = cy + r * 0.85 * math.sin(angle)
        positions.append((x, y, s))

    blue, gold, dim = COLORS["blue"], COLORS["gold"], COLORS["text_dim"]
    parts = []
    for i in range(n):
        x1, y1, _ = positions[i]
        x2, y2, _ = positions[(i + 1) % n]
        parts.append(
            f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" '
            f'stroke="{blue}" stroke-width="0.8" stroke-opacity="0.3"/>'
        )
    for i in range(0, n, 2):
        if i + 2 < n:
            x1, y1, _ = positions[i]
            x2, y2, _ = positions[i + 2]
            parts.append(
                f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" '
                f'stroke="{gold}" stroke-width="0.5" stroke-opacity="0.12"/>'
            )
    for x, y, s in positions:
        score = s.get("score", 0.5)
        rad = 3 + score * 6
        sym = s.get("symbol", "?")
        direction = s.get("direction", "LONG")
        color = COLORS["green"] if direction == "LONG" else COLORS["red"]
        parts.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rad:.1f}" fill="{color}" opacity="0.9"/>')
        parts.append(
            f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rad * 2.2:.1f}" fill="none" '
            f'stroke="{color}" stroke-width="0.5" opacity="0.2"/>'
        )
        parts.append(
            f'<text x="{x:.0f}" y="{y - rad - 8:.0f}" text-anchor="middle" '
            f'fill="{dim}" font-size="9" font-family="JetBrains Mono">{sym}</text>'
        )

    return f"""
    <div class="auriga-constellation">
      <svg viewBox="0 0 {width} {height}">{''.join(parts)}</svg>
    </div>
    """


def footer_html() -> str:
    return (
        '<div class="auriga-footer">'
        '<span>AURIGA — Autonomous Quant Research &amp; Investment Agent</span>'
        '<span>Paper trading · Options définis-risque · Le LLM propose, le moteur dispose</span>'
        '</div>'
    )
