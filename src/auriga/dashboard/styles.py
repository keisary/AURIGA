"""AURIGA - Charte graphique du dashboard (CSS + helpers).

Thème : « Le Cocher céleste » — ciel nocturne, étoiles, or Capella,
constellation Auriga. Défini dans la charte graphique validée.
"""
from __future__ import annotations

import random

# ---------------------------------------------------------------------------
# Palette (charte AURIGA)
# ---------------------------------------------------------------------------

COLORS = {
    "bg": "#070B14",          # nuit profonde
    "surface": "#0D1424",     # bleu nuit
    "surface_hi": "#131C31",  # bleu nuit clair (hover)
    "border": "#1E2A45",      # ligne stellaire
    "text": "#E8EDF7",        # blanc étoilé
    "text_dim": "#8A94AD",    # gris stellaire
    "gold": "#F5C542",        # or Capella (accent principal)
    "blue": "#4DA3FF",        # bleu stellaire
    "green": "#2EE6A8",       # vert aurore (positif)
    "red": "#FF5C7A",         # rouge nébuleuse (négatif)
    "orange": "#FF9F43",      # orange supernova (alerte)
}

# ---------------------------------------------------------------------------
# CSS complet
# ---------------------------------------------------------------------------

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600&display=swap');

/* ===== Fond général : nuit profonde ===== */
.stApp {
    background: radial-gradient(ellipse at 20% 0%, #0B1224 0%, #070B14 55%);
    color: #E8EDF7;
    font-family: 'Inter', sans-serif;
}

/* Masquer le header/branding Streamlit par défaut */
#MainMenu, footer, header[data-testid="stHeader"] {
    visibility: hidden; height: 0;
}
.block-container { padding-top: 1.2rem; }

/* ===== Ciel étoilé (arrière-plan) ===== */
.auriga-stars {
    position: fixed; inset: 0; pointer-events: none; z-index: 0;
    background-repeat: repeat;
}
.auriga-sky { position: relative; z-index: 1; }

/* ===== Header branding ===== */
.auriga-header {
    display: flex; align-items: center; gap: 16px;
    padding: 10px 4px 18px 4px;
    border-bottom: 1px solid #1E2A45;
    margin-bottom: 20px;
}
.auriga-logo { width: 46px; height: 46px; flex-shrink: 0; }
.auriga-title {
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700; font-size: 1.7rem; letter-spacing: 2px;
    color: #E8EDF7; margin: 0;
}
.auriga-title .gold { color: #F5C542; }
.auriga-subtitle {
    font-size: 0.78rem; color: #8A94AD; letter-spacing: 3px;
    text-transform: uppercase; margin: 0;
}
.auriga-status {
    margin-left: auto; display: flex; align-items: center; gap: 8px;
    font-family: 'JetBrains Mono', monospace; font-size: 0.75rem;
    color: #2EE6A8; background: rgba(46,230,168,0.08);
    border: 1px solid rgba(46,230,168,0.25);
    padding: 5px 12px; border-radius: 20px;
}
.auriga-status .dot {
    width: 7px; height: 7px; border-radius: 50%; background: #2EE6A8;
    animation: pulse-dot 2s infinite;
}
@keyframes pulse-dot {
    0%,100% { opacity: 1; box-shadow: 0 0 0 0 rgba(46,230,168,0.5); }
    50%     { opacity: 0.6; box-shadow: 0 0 0 5px rgba(46,230,168,0); }
}

/* ===== KPI cards ===== */
.auriga-kpi {
    background: linear-gradient(160deg, #0D1424 0%, #0A101F 100%);
    border: 1px solid #1E2A45; border-radius: 12px;
    padding: 16px 18px; position: relative; overflow: hidden;
}
.auriga-kpi::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, transparent, #F5C54255, transparent);
}
.auriga-kpi-label {
    font-size: 0.7rem; color: #8A94AD; letter-spacing: 1.5px;
    text-transform: uppercase; margin-bottom: 6px;
}
.auriga-kpi-value {
    font-family: 'JetBrains Mono', monospace; font-weight: 600;
    font-size: 1.55rem; color: #E8EDF7; line-height: 1.1;
}
.auriga-kpi-value.pos { color: #2EE6A8; }
.auriga-kpi-value.neg { color: #FF5C7A; }
.auriga-kpi-value.gold { color: #F5C542; }
.auriga-kpi-sub { font-size: 0.72rem; color: #8A94AD; margin-top: 5px; }

/* ===== Section headers ===== */
.auriga-section {
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 600; font-size: 1.05rem; color: #E8EDF7;
    letter-spacing: 0.5px; margin: 22px 0 10px 0;
    display: flex; align-items: center; gap: 10px;
}
.auriga-section .star { color: #F5C542; font-size: 0.9rem; }

/* ===== Cards génériques ===== */
.auriga-card {
    background: #0D1424; border: 1px solid #1E2A45;
    border-radius: 12px; padding: 16px 18px;
    transition: border-color 0.2s, box-shadow 0.2s, transform 0.2s;
}
.auriga-card:hover {
    border-color: #F5C54266;
    box-shadow: 0 0 18px rgba(245,197,66,0.06);
    transform: translateY(-1px);
}

/* ===== Positions ===== */
.auriga-position {
    display: flex; justify-content: space-between; align-items: center;
    padding: 10px 14px; border-radius: 8px;
    background: #0A101F; border: 1px solid #1E2A45;
    margin-bottom: 6px;
}
.auriga-position .sym {
    font-family: 'JetBrains Mono', monospace; font-weight: 600; font-size: 0.95rem;
}
.auriga-position .dir-long { color: #2EE6A8; }
.auriga-position .dir-short { color: #FF5C7A; }
.auriga-position .strat { font-size: 0.75rem; color: #8A94AD; }
.auriga-position .risk {
    font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #E8EDF7;
}
.badge {
    font-family: 'JetBrains Mono', monospace; font-size: 0.65rem;
    padding: 2px 8px; border-radius: 10px; letter-spacing: 0.5px;
}
.badge-long { background: rgba(46,230,168,0.12); color: #2EE6A8; border: 1px solid rgba(46,230,168,0.3); }
.badge-short { background: rgba(255,92,122,0.12); color: #FF5C7A; border: 1px solid rgba(255,92,122,0.3); }

/* ===== Risk gates ===== */
.auriga-gate {
    display: flex; align-items: center; gap: 10px;
    padding: 7px 12px; border-radius: 8px; margin-bottom: 5px;
    font-size: 0.82rem;
}
.auriga-gate.ok { background: rgba(46,230,168,0.05); color: #2EE6A8; }
.auriga-gate.warn { background: rgba(255,159,67,0.08); color: #FF9F43; }
.auriga-gate.block { background: rgba(255,92,122,0.08); color: #FF5C7A; animation: gate-pulse 1.5s infinite; }
@keyframes gate-pulse {
    0%,100% { opacity: 1; } 50% { opacity: 0.65; }
}
.auriga-gate .glyph { font-weight: 700; }

/* ===== Narratif ===== */
.auriga-narrative {
    background: linear-gradient(165deg, #0D1424, #0A101F);
    border: 1px solid #1E2A45; border-left: 3px solid #F5C542;
    border-radius: 12px; padding: 18px 22px;
    line-height: 1.6; font-size: 0.92rem; color: #C9D2E3;
    max-height: 420px; overflow-y: auto;
}
.auriga-narrative h1, .auriga-narrative h2 { color: #F5C542; font-size: 1.1rem; margin-top: 12px; }
.auriga-narrative strong { color: #E8EDF7; }
.auriga-narrative li { margin-bottom: 4px; }

/* ===== Scintillement des étoiles ===== */
@keyframes twinkle {
    0%,100% { opacity: 0.25; }
    50% { opacity: 0.9; }
}

/* ===== Count-up / twinkle card ===== */
@keyframes card-in {
    from { opacity: 0; transform: scale(0.96); }
    to { opacity: 1; transform: scale(1); }
}
.auriga-card { animation: card-in 0.4s ease-out; }

/* ===== Constellation SVG container ===== */
.auriga-constellation {
    width: 100%; border-radius: 12px;
    background: radial-gradient(ellipse at center, #0B1224 0%, #070B14 80%);
    border: 1px solid #1E2A45;
}
.auriga-constellation svg { width: 100%; height: auto; display: block; }

/* ===== Métriques texte générique ===== */
.mono { font-family: 'JetBrains Mono', monospace; }
.dim { color: #8A94AD; font-size: 0.8rem; }

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #1E2A45; border-radius: 3px; }
</style>
"""


# ---------------------------------------------------------------------------
# Helpers HTML
# ---------------------------------------------------------------------------

def stars_background(n_stars: int = 70, seed: int = 42) -> str:
    """Génère un ciel étoilé en CSS (box-shadows positionnés)."""
    rng = random.Random(seed)
    stars = []
    for _ in range(n_stars):
        x = rng.randint(0, 100)
        y = rng.randint(0, 100)
        size = rng.choice([1, 1, 1, 2, 2, 3])
        opacity = rng.uniform(0.15, 0.7)
        tw = "animation: twinkle %ds ease-in-out infinite; animation-delay: %.1fs;" % (
            rng.randint(3, 8), rng.uniform(0, 4)
        )
        stars.append(
            f"<div style='position:absolute;left:{x}%;top:{y}%;width:{size}px;"
            f"height:{size}px;border-radius:50%;background:#E8EDF7;opacity:{opacity:.2f};"
            f"{tw}'></div>"
        )
    return f'<div class="auriga-stars">{"".join(stars)}</div>'


def logo_svg(size: int = 46) -> str:
    """Logo : pentagone de la constellation Auriga, Capella en or."""
    # Points du pentagone (étoile à 5 branches simplifiée - forme Auriga)
    pts = [
        (50, 6),    # Capella (sommet, or)
        (88, 28),
        (74, 70),
        (26, 70),
        (12, 28),
    ]
    poly = " ".join(f"{x},{y}" for x, y in pts)
    return f"""
    <svg class="auriga-logo" width="{size}" height="{size}" viewBox="0 0 100 100">
      <defs>
        <radialGradient id="capella-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="#F5C542" stop-opacity="0.9"/>
          <stop offset="100%" stop-color="#F5C542" stop-opacity="0"/>
        </radialGradient>
      </defs>
      <circle cx="50" cy="6" r="22" fill="url(#capella-glow)"/>
      <!-- lignes de la constellation -->
      <polygon points="{poly}" fill="none" stroke="#4DA3FF" stroke-width="1.4" stroke-opacity="0.7"
        stroke-linejoin="round"/>
      <!-- diagonales internes (étoile) -->
      <line x1="50" y1="6" x2="74" y2="70" stroke="#4DA3FF" stroke-width="1" stroke-opacity="0.35"/>
      <line x1="50" y1="6" x2="26" y2="70" stroke="#4DA3FF" stroke-width="1" stroke-opacity="0.35"/>
      <line x1="12" y1="28" x2="88" y2="28" stroke="#4DA3FF" stroke-width="1" stroke-opacity="0.35"/>
      <!-- étoiles -->
      <circle cx="50" cy="6" r="4.5" fill="#F5C542"/>
      <circle cx="88" cy="28" r="2.2" fill="#E8EDF7"/>
      <circle cx="74" cy="70" r="2" fill="#E8EDF7"/>
      <circle cx="26" cy="70" r="2" fill="#E8EDF7"/>
      <circle cx="12" cy="28" r="2.2" fill="#E8EDF7"/>
    </svg>
    """


def header_html(status_text: str = "SYSTÈME ACTIF") -> str:
    return f"""
    <div class="auriga-header">
      {logo_svg()}
      <div>
        <p class="auriga-title">AURIGA<span class="gold">.</span></p>
        <p class="auriga-subtitle">Autonomous Quant Research Agent</p>
      </div>
      <div class="auriga-status"><span class="dot"></span>{status_text}</div>
    </div>
    """


def kpi_html(label: str, value: str, sub: str = "", cls: str = "") -> str:
    return f"""
    <div class="auriga-kpi">
      <div class="auriga-kpi-label">{label}</div>
      <div class="auriga-kpi-value {cls}">{value}</div>
      <div class="auriga-kpi-sub">{sub}</div>
    </div>
    """


def section_html(title: str) -> str:
    return f'<div class="auriga-section"><span class="star">✦</span>{title}</div>'


def position_html(symbol: str, direction: str, strategy: str, risk: float) -> str:
    dir_cls = "dir-long" if direction == "LONG" else "dir-short"
    badge_cls = "badge-long" if direction == "LONG" else "badge-short"
    return f"""
    <div class="auriga-position">
      <div>
        <span class="sym">{symbol}</span>
        <span class="badge {badge_cls}">{direction}</span>
        <div class="strat">{strategy}</div>
      </div>
      <div class="risk">risk ${risk:,.0f}</div>
    </div>
    """


def gate_html(label: str, status: str, detail: str = "") -> str:
    """status: 'ok' | 'warn' | 'block'"""
    glyph = {"ok": "✓", "warn": "⚠", "block": "✕"}.get(status, "•")
    return f"""
    <div class="auriga-gate {status}">
      <span class="glyph">{glyph}</span>
      <span>{label}</span>
      <span style="margin-left:auto;font-size:0.75rem">{detail}</span>
    </div>
    """


def constellation_svg(
    strategies: list[dict],
    width: int = 640,
    height: int = 320,
) -> str:
    """Génère la « constellation » des stratégies actives.

    Chaque stratégie = une étoile ; les liens = corrélation/partage de
    l'univers. La taille de l'étoile = score de la stratégie.
    """
    if not strategies:
        return "<div class='dim' style='padding:30px;text-align:center'>Aucune stratégie active — lancer la recherche</div>"

    n = len(strategies)
    import math

    cx, cy = width / 2, height / 2
    r = min(width, height) / 2 - 40
    positions = []
    for i, s in enumerate(strategies):
        angle = -math.pi / 2 + 2 * math.pi * i / n
        x = cx + r * 0.85 * math.cos(angle)
        y = cy + r * 0.85 * math.sin(angle)
        positions.append((x, y, s))

    parts = []
    # Liens entre étoiles voisines (constellation)
    for i in range(n):
        x1, y1, _ = positions[i]
        x2, y2, _ = positions[(i + 1) % n]
        parts.append(
            f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" '
            f'stroke="#4DA3FF" stroke-width="0.8" stroke-opacity="0.35"/>'
        )
    # Quelques liens croisés
    for i in range(0, n, 2):
        if i + 2 < n:
            x1, y1, _ = positions[i]
            x2, y2, _ = positions[i + 2]
            parts.append(
                f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" '
                f'stroke="#F5C542" stroke-width="0.5" stroke-opacity="0.15"/>'
            )
    # Étoiles
    for x, y, s in positions:
        score = s.get("score", 0.5)
        rad = 3 + score * 6
        sym = s.get("symbol", "?")
        direction = s.get("direction", "LONG")
        color = "#2EE6A8" if direction == "LONG" else "#FF5C7A"
        parts.append(
            f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rad:.1f}" fill="{color}" opacity="0.9"/>'
        )
        parts.append(
            f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rad*2.6:.1f}" fill="none" '
            f'stroke="{color}" stroke-width="0.5" opacity="0.25"/>'
        )
        parts.append(
            f'<text x="{x:.0f}" y="{y - rad - 8:.0f}" text-anchor="middle" '
            f'fill="#8A94AD" font-size="9" font-family="JetBrains Mono">{sym}</text>'
        )

    return f"""
    <div class="auriga-constellation">
      <svg viewBox="0 0 {width} {height}">
        <rect width="{width}" height="{height}" fill="transparent"/>
        {''.join(parts)}
      </svg>
    </div>
    """