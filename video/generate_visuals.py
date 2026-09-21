"""Generate 7 PNG visuals for the AURIGA submission video.

Each visual is 1920x1080 (16:9). Same Tech & Night palette as the PDF deck.
The visuals are turned into MP4 clips by ffmpeg (Ken Burns zoom) in a
follow-up step.
"""
from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT_DIR = Path(r"D:\midas_v2\AURIGA\video\clips\frames")
OUT_DIR.mkdir(parents=True, exist_ok=True)

W, H = 1920, 1080

# Palette (Tech & Night dark mode)
BG        = (8, 8, 20)        # 000814
PANEL     = (0, 29, 61)       # 001D3D
PANEL_HI  = (0, 53, 102)      # 003566
GOLD      = (255, 195, 0)     # FFC300
GOLD_HI   = (255, 214, 10)    # FFD60A
WHITE     = (245, 245, 245)
MUTED     = (141, 153, 174)   # 8D99AE
DANGER    = (255, 107, 107)
GREEN     = (110, 231, 183)

# Fonts -- pick whatever is available on Windows
FONT_DIR_WIN = Path(r"C:\Windows\Fonts")
FONT_TITLE   = str(FONT_DIR_WIN / "georgia.ttf")
FONT_BODY    = str(FONT_DIR_WIN / "calibri.ttf")
FONT_BOLD    = str(FONT_DIR_WIN / "calibrib.ttf")
FONT_MONO    = str(FONT_DIR_WIN / "consola.ttf")

if not Path(FONT_TITLE).exists():
    FONT_TITLE = str(FONT_DIR_WIN / "arial.ttf")
if not Path(FONT_BOLD).exists():
    FONT_BOLD = FONT_TITLE


def font(size: int, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont:
    if mono:
        return ImageFont.truetype(FONT_MONO, size)
    path = FONT_BOLD if bold else FONT_BODY
    if not Path(path).exists():
        path = FONT_BODY
    return ImageFont.truetype(path, size)


def make_canvas(bg: tuple[int, int, int] = BG) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), bg)
    return img, ImageDraw.Draw(img)


def draw_constellation(draw: ImageDraw.ImageDraw, seed: int = 1, area: tuple[int, int, int, int] = (0, 0, W, H)) -> None:
    random.seed(seed)
    ax, ay, bx, by = area
    n = 40
    pts: list[tuple[int, int, int]] = []
    for _ in range(n):
        x = random.randint(ax, bx)
        y = random.randint(ay, by)
        s = random.choice([2, 2, 3, 3, 4, 5])
        pts.append((x, y, s))
    for x, y, s in pts:
        # Glow
        for r, a in [(s + 6, 30), (s + 3, 60), (s, 255)]:
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(255, 195, 0) if a == 255 else (255, 195, 0))
    # Connect a few points with faint lines
    for i in range(len(pts) - 1):
        if random.random() < 0.18:
            x1, y1, _ = pts[i]
            x2, y2, _ = pts[i + 1]
            draw.line([(x1, y1), (x2, y2)], fill=GOLD, width=1)


def text_centered(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont,
                  y: int, color: tuple[int, int, int], w: int = W) -> None:
    bbox = draw.textbbox((0, 0), text, font=fnt)
    tw = bbox[2] - bbox[0]
    draw.text(((w - tw) // 2, y), text, font=fnt, fill=color)


def draw_panel(d, x, y, w, h, fill=PANEL, border=None, radius=12):
    d.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=fill, outline=border)


# ---- Visual 1: Cover ----
def visual_01() -> Path:
    img, d = make_canvas()
    draw_constellation(d, seed=7, area=(0, 0, W, H))
    # Glow under the title
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for r, a in [(180, 18), (110, 35), (60, 60)]:
        gd.ellipse([W // 2 - r, 380 - r // 2, W // 2 + r, 380 + r // 2], fill=(255, 195, 0, a))
    glow = glow.filter(ImageFilter.GaussianBlur(40))
    img.paste(glow, (0, 0), glow)
    d = ImageDraw.Draw(img)

    f_eyebrow = font(28, bold=True)
    f_title   = font(220, bold=True)
    f_sub     = font(40, bold=True)
    f_tag     = font(30)
    f_meta    = font(22)

    text_centered(d, "ALPACA AI TRADING AGENTS HACKATHON 2026", f_eyebrow, 220, GOLD)
    text_centered(d, "AURIGA", f_title, 330, WHITE)
    text_centered(d, "Autonomous Quant Research & Investment Agent", f_sub, 620, WHITE)
    text_centered(d, "Discover, validate, deploy -- the LLM narrates, it never decides.", f_tag, 690, MUTED)

    # Accent rule
    d.rectangle([W // 2 - 80, 800, W // 2 + 80, 802], fill=GOLD)
    text_centered(d, "Submission video  |  Alpaca paper $100,000  |  5-year backtest", f_meta, 820, MUTED)
    text_centered(d, "github.com/keisary/AURIGA", f_meta, 980, GOLD)

    out = OUT_DIR / "seg-01.png"
    img.save(out, "PNG")
    return out


# ---- Visual 2: Data flow diagram ----
def visual_02() -> Path:
    img, d = make_canvas()
    draw_constellation(d, seed=2, area=(0, 0, W, H))

    f_eyebrow = font(26, bold=True)
    f_title   = font(58, bold=True)
    f_box_h   = font(28, bold=True)
    f_box_s   = font(22)
    f_caption = font(20)

    text_centered(d, "01  /  DATA -> DISCOVERY", f_eyebrow, 90, GOLD)
    text_centered(d, "From raw bars to human-readable rules", f_title, 140, WHITE)

    boxes = [
        ("MARKET DATA", "5y * 1H / 1D\nAlpaca IEX feed"),
        ("FEATURES",    "36 technical +\nquantitative signals"),
        ("XGBOOST",     "Tree-path\nextraction engine"),
        ("RULES",       "Human-readable\nLONG / SHORT rules"),
    ]
    box_w, box_h = 320, 220
    gap = 60
    total_w = box_w * 4 + gap * 3
    x0 = (W - total_w) // 2
    y0 = 360
    for i, (h_, s_) in enumerate(boxes):
        x = x0 + i * (box_w + gap)
        draw_panel(d, x, y0, box_w, box_h, fill=PANEL, border=GOLD, radius=14)
        d.rectangle([x, y0, x + box_w, y0 + 8], fill=GOLD)
        text_centered(d, h_, f_box_h, y0 + 30, GOLD, w=box_w)
        # Subtitle
        for j, line in enumerate(s_.split("\n")):
            text_centered(d, line, f_box_s, y0 + 90 + j * 30, WHITE, w=box_w)
        # Arrow
        if i < 3:
            ax = x + box_w + 8
            ay = y0 + box_h // 2
            d.polygon([(ax, ay - 12), (ax + gap - 16, ay), (ax, ay + 12)], fill=GOLD)

    # Bottom caption
    text_centered(d, "9 rules admitted  |  Sharpe >= 2  |  WR >= 0.65  |  PF >= 1.5  |  >= 30 trades", f_caption, 720, MUTED)
    text_centered(d, "Validation: BH/FDR-controlled, 20% temporal holdout kept virgin.", f_caption, 760, MUTED)

    out = OUT_DIR / "seg-02.png"
    img.save(out, "PNG")
    return out


# ---- Visual 3: Three agents A1 / A2 / A3 ----
def visual_03() -> Path:
    img, d = make_canvas()
    draw_constellation(d, seed=3, area=(0, 0, W, H))

    f_eyebrow = font(26, bold=True)
    f_title   = font(58, bold=True)
    f_tag     = font(24, bold=True)
    f_h       = font(34, bold=True)
    f_b       = font(22)
    f_kpi     = font(74, bold=True)
    f_kl      = font(20)
    f_n       = font(18)

    text_centered(d, "02  /  THREE AGENTS, THREE THESES", f_eyebrow, 80, GOLD)
    text_centered(d, "AI Logic -- a portfolio, not a black box", f_title, 130, WHITE)

    cards = [
        {
            "tag": "A1  DIRECTION",
            "h":   "Directional alpha",
            "b":   "XGBoost -> explainable rules\nDebit vertical spreads (bull / bear)",
            "kpi": "9",
            "kl":  "rules admitted",
            "n":   "Sharpe >= 2, WR >= 0.65,\nPF >= 1.5, >= 30 trades,\nBH/FDR-controlled",
        },
        {
            "tag": "A2  VOL RISK",
            "h":   "Volatility risk signal",
            "b":   "XGBoost on vol shock\nA guard, not a strategy",
            "kpi": "~0.75",
            "kl":  "AUC on vol shock",
            "n":   "Long-vol straddles lose\n(median Sharpe -2.6).\nFlags danger for A3.",
        },
        {
            "tag": "A3  PREMIUM SELLER",
            "h":   "Gated income engine",
            "b":   "AVOID_SELL on the ~2% tail\nPut / call credit spreads",
            "kpi": "~98%",
            "kl":  "of periods profitable",
            "n":   "Stops selling when overbought\n+ drawdown + regime shift\ncoincide -- the rare tail.",
        },
    ]
    cw, ch = 460, 720
    gap = 60
    total_w = cw * 3 + gap * 2
    x0 = (W - total_w) // 2
    y0 = 240
    for i, c in enumerate(cards):
        x = x0 + i * (cw + gap)
        draw_panel(d, x, y0, cw, ch, fill=PANEL, border=GOLD, radius=16)
        d.rectangle([x, y0, x + cw, y0 + 10], fill=GOLD)
        # Tag
        bb = d.textbbox((0, 0), c["tag"], font=f_tag)
        tw = bb[2] - bb[0]
        d.text((x + (cw - tw) // 2, y0 + 36), c["tag"], font=f_tag, fill=GOLD)
        # H
        bb = d.textbbox((0, 0), c["h"], font=f_h)
        tw = bb[2] - bb[0]
        d.text((x + (cw - tw) // 2, y0 + 80), c["h"], font=f_h, fill=WHITE)
        # Body
        for j, line in enumerate(c["b"].split("\n")):
            bb = d.textbbox((0, 0), line, font=f_b)
            tw = bb[2] - bb[0]
            d.text((x + (cw - tw) // 2, y0 + 150 + j * 30), line, font=f_b, fill=WHITE)
        # KPI
        bb = d.textbbox((0, 0), c["kpi"], font=f_kpi)
        tw = bb[2] - bb[0]
        d.text((x + (cw - tw) // 2, y0 + 280), c["kpi"], font=f_kpi, fill=GOLD)
        # KPI label
        bb = d.textbbox((0, 0), c["kl"], font=f_kl)
        tw = bb[2] - bb[0]
        d.text((x + (cw - tw) // 2, y0 + 380), c["kl"], font=f_kl, fill=MUTED)
        # Note
        for j, line in enumerate(c["n"].split("\n")):
            bb = d.textbbox((0, 0), line, font=f_n)
            tw = bb[2] - bb[0]
            d.text((x + (cw - tw) // 2, y0 + 440 + j * 26), line, font=f_n, fill=WHITE)

    out = OUT_DIR / "seg-03.png"
    img.save(out, "PNG")
    return out


# ---- Visual 4: Risk engine 8 gates ----
def visual_04() -> Path:
    img, d = make_canvas()
    draw_constellation(d, seed=4, area=(0, 0, W, H))

    f_eyebrow = font(26, bold=True)
    f_title   = font(50, bold=True)
    f_code    = font(26, bold=True)
    f_lbl     = font(22, bold=True)
    f_rule    = font(17)
    f_status  = font(28, bold=True)
    f_sub     = font(20)

    text_centered(d, "03  /  RISK ENGINE", f_eyebrow, 70, GOLD)
    text_centered(d, "8 deterministic gates -- fail-closed", f_title, 115, WHITE)

    gates = [
        ("G1", "Daily loss limit",      "-2% equity  ->  halt"),
        ("G2", "Max exposure / asset",  "10% capital"),
        ("G3", "Max exposure / sector", "25% capital"),
        ("G4", "Max total exposure",    "80% capital"),
        ("G5", "Max positions",         "12 concurrent"),
        ("G6", "Vol danger (A2)",       "P(vol shock) > 0.35  ->  block sells"),
        ("G7", "AVOID_SELL (A3)",       "any triggered rule  ->  block sells"),
        ("G8", "Liquidation",           "total P&L < -25%  ->  close positions"),
    ]
    cols, rows = 4, 2
    cw, ch = 380, 200
    gap_x, gap_y = 30, 30
    total_w = cw * cols + gap_x * (cols - 1)
    x0 = (W - total_w) // 2
    y0 = 220
    for i, (code, lbl, rule) in enumerate(gates):
        c = i % cols
        r = i // cols
        x = x0 + c * (cw + gap_x)
        y = y0 + r * (ch + gap_y)
        draw_panel(d, x, y, cw, ch, fill=PANEL, border=GOLD, radius=10)
        # Code badge
        d.rectangle([x + 10, y + 10, x + 70, y + 50], fill=GOLD)
        text_centered(d, code, f_code, y + 14, BG, w=60)
        # Label
        d.text((x + 80, y + 14), lbl, font=f_lbl, fill=WHITE)
        # Rule
        for j, line in enumerate(rule.split("\n")):
            d.text((x + 20, y + 90 + j * 24), line, font=f_rule, fill=MUTED)

    # Status block: TRADE APPROVED -> TRADE BLOCKED
    sy = 760
    draw_panel(d, 140, sy, 760, 90, fill=PANEL, border=GREEN, radius=10)
    text_centered(d, "TRADE APPROVED  ->  multi-leg submitted to Alpaca paper", f_status, sy + 28, GREEN, w=760)
    text_centered(d, "8/8 gates passed  |  spread selected  |  risk engine signed", f_sub, sy + 60, WHITE, w=760)

    draw_panel(d, 1020, sy, 760, 90, fill=PANEL, border=DANGER, radius=10)
    text_centered(d, "TRADE BLOCKED  ->  Reason: volatility danger (G6)", f_status, sy + 28, DANGER, w=760)
    text_centered(d, "A2 AUC 0.75 flag  |  A3 AVOID_SELL triggered  |  fail-closed", f_sub, sy + 60, WHITE, w=760)

    out = OUT_DIR / "seg-04.png"
    img.save(out, "PNG")
    return out


# ---- Visual 5: Alpaca paper order ----
def visual_05() -> Path:
    img, d = make_canvas()
    draw_constellation(d, seed=5, area=(0, 0, W, H))

    f_eyebrow = font(26, bold=True)
    f_title   = font(50, bold=True)
    f_field   = font(22)
    f_val     = font(28, bold=True)
    f_pill    = font(22, bold=True)
    f_mono    = font(20, mono=True)

    text_centered(d, "04  /  ALPACA PAPER", f_eyebrow, 80, GOLD)
    text_centered(d, "Atomic multi-leg option spreads", f_title, 130, WHITE)

    # Order card
    cx, cy, cw, ch = 220, 250, 1480, 540
    draw_panel(d, cx, cy, cw, ch, fill=PANEL, border=GOLD, radius=14)
    d.rectangle([cx, cy, cx + cw, cy + 10], fill=GOLD)
    # Title bar
    d.text((cx + 30, cy + 30), "ORDER  /  MLEG  /  OPRA option chain", font=f_pill, fill=GOLD)
    # PAPER badge
    draw_panel(d, cx + cw - 170, cy + 24, 130, 40, fill=GOLD, radius=8)
    text_centered(d, "PAPER", font(20, bold=True), cy + 30, BG, w=130)

    # Two legs
    leg_w = (cw - 90) // 2
    leg_y = cy + 110
    leg_h = 360
    # Leg 1
    draw_panel(d, cx + 30, leg_y, leg_w, leg_h, fill=(0, 18, 40), border=GOLD, radius=10)
    d.text((cx + 50, leg_y + 20), "LEG 1  /  BUY", font=f_pill, fill=GOLD)
    rows1 = [
        ("Symbol",    "AAPL  241220C00230000"),
        ("Side",      "buy_to_open"),
        ("Qty",       "1 contract"),
        ("Type",      "limit  /  GTC"),
        ("Limit px",  "$ 2.40"),
        ("Status",    "WORKING"),
    ]
    for i, (k, v) in enumerate(rows1):
        d.text((cx + 60, leg_y + 70 + i * 42), k, font=f_field, fill=MUTED)
        d.text((cx + 60, leg_y + 90 + i * 42), v, font=f_val, fill=WHITE)
    # Leg 2
    draw_panel(d, cx + 60 + leg_w, leg_y, leg_w, leg_h, fill=(0, 18, 40), border=GOLD, radius=10)
    d.text((cx + 80 + leg_w, leg_y + 20), "LEG 2  /  SELL", font=f_pill, fill=GOLD)
    rows2 = [
        ("Symbol",    "AAPL  241220C00235000"),
        ("Side",      "sell_to_open"),
        ("Qty",       "1 contract"),
        ("Type",      "limit  /  GTC"),
        ("Limit px",  "$ 1.65"),
        ("Status",    "WORKING"),
    ]
    for i, (k, v) in enumerate(rows2):
        d.text((cx + 80 + leg_w, leg_y + 70 + i * 42), k, font=f_field, fill=MUTED)
        d.text((cx + 80 + leg_w, leg_y + 90 + i * 42), v, font=f_val, fill=WHITE)

    # Bottom
    text_centered(d, "Atomic order, level 3, zero commissions, defined risk.", f_mono, 850, GOLD)
    text_centered(d, "alpaca-py  |  multi-leg MLEG  |  paper account $100,000", f_mono, 900, MUTED)

    out = OUT_DIR / "seg-05.png"
    img.save(out, "PNG")
    return out


# ---- Visual 6: Streamlit dashboard ----
def visual_06() -> Path:
    img, d = make_canvas()
    draw_constellation(d, seed=6, area=(0, 0, W, H))

    f_eyebrow = font(26, bold=True)
    f_title   = font(50, bold=True)
    f_h       = font(24, bold=True)
    f_v       = font(40, bold=True)
    f_l       = font(18)
    f_pill    = font(20, bold=True)

    text_centered(d, "05  /  STREAMLIT DASHBOARD", f_eyebrow, 80, GOLD)
    text_centered(d, "Every decision is explainable", f_title, 130, WHITE)

    # Sidebar
    sx, sy, sw, sh = 80, 240, 280, 720
    draw_panel(d, sx, sy, sw, sh, fill=PANEL, border=GOLD, radius=12)
    d.text((sx + 24, sy + 30), "AURIGA", font=f_h, fill=GOLD)
    d.text((sx + 24, sy + 70), "Paper mode", font=f_l, fill=MUTED)
    draw_panel(d, sx + 24, sy + 110, 160, 40, fill=GREEN, radius=8)
    text_centered(d, "PAPER CONNECTED", f_pill, sy + 118, (8, 50, 30), w=160)
    items = ["Status", "Positions", "Equity curve", "Constellation", "Narrative", "Risk gates"]
    for i, it in enumerate(items):
        d.text((sx + 24, sy + 200 + i * 50), it, font=f_l, fill=WHITE)

    # Main area: equity curve + cards
    mx, my, mw, mh = 400, 240, 1440, 720
    draw_panel(d, mx, my, mw, mh, fill=PANEL, border=GOLD, radius=12)
    # KPI cards (3 columns)
    kx, ky, kw, kh = mx + 30, my + 30, 440, 140
    kpis = [
        ("EQUITY",      "$ 102,640",  GREEN),
        ("DAILY P&L",   "+ $ 412",    GREEN),
        ("OPEN POS.",   "4 / 12",     GOLD),
    ]
    for i, (l, v, col) in enumerate(kpis):
        x = kx + i * (kw + 20)
        draw_panel(d, x, ky, kw, kh, fill=(0, 18, 40), border=GOLD, radius=10)
        d.text((x + 20, ky + 20), l, font=f_l, fill=MUTED)
        d.text((x + 20, ky + 50), v, font=f_v, fill=col)

    # Equity curve
    cx, cy_, cw_, ch_ = mx + 30, my + 200, 880, 280
    draw_panel(d, cx, cy_, cw_, ch_, fill=(0, 18, 40), border=GOLD, radius=10)
    d.text((cx + 20, cy_ + 16), "EQUITY CURVE  /  last 30 days", font=f_l, fill=MUTED)
    # Draw a fake equity curve
    n = 80
    pts = []
    base = 100000
    for i in range(n):
        base += math.sin(i / 4.0) * 80 + (i * 30) + random.uniform(-40, 40)
        x = cx + 40 + i * (cw_ - 80) / (n - 1)
        y = cy_ + ch_ - 40 - (base - 100000) * 1.2
        pts.append((x, y))
    # Filled area
    poly = [(cx + 40, cy_ + ch_ - 40)] + pts + [(cx + cw_ - 40, cy_ + ch_ - 40)]
    d.polygon(poly, fill=(0, 53, 102))
    for i in range(len(pts) - 1):
        d.line([pts[i], pts[i + 1]], fill=GOLD, width=2)

    # Right: rule constellation (mini)
    rx, ry, rw, rh = mx + 940, my + 200, 470, 280
    draw_panel(d, rx, ry, rw, rh, fill=(0, 18, 40), border=GOLD, radius=10)
    d.text((rx + 20, ry + 16), "ACTIVE RULES  /  constellation", font=f_l, fill=MUTED)
    random.seed(99)
    nodes = []
    for _ in range(8):
        nx = rx + 80 + random.randint(0, rw - 160)
        ny = ry + 80 + random.randint(0, rh - 120)
        nodes.append((nx, ny))
    for i, (x1, y1) in enumerate(nodes):
        for j, (x2, y2) in enumerate(nodes):
            if i < j and (x1 - x2) ** 2 + (y1 - y2) ** 2 < 120 ** 2:
                d.line([(x1, y1), (x2, y2)], fill=(0, 53, 102), width=1)
    for x, y in nodes:
        d.ellipse([x - 8, y - 8, x + 8, y + 8], fill=GOLD)

    # Bottom: LLM narrative
    nx, ny_, nw, nh = mx + 30, my + 510, 1380, 180
    draw_panel(d, nx, ny_, nw, nh, fill=(0, 18, 40), border=GOLD, radius=10)
    d.text((nx + 20, ny_ + 16), "DAILY LLM NARRATIVE  /  2026-09-04", font=f_l, fill=MUTED)
    txt = ("9 rules in the live portfolio, 4 active. A1 long AAPL spread +320 today, A2 flagged no vol danger, "
           "A3 sold SPY put credit spread. Risk gates: 8/8 passed. No liquidation triggers.")
    d.text((nx + 20, ny_ + 50), txt, font=font(18), fill=WHITE)

    out = OUT_DIR / "seg-06.png"
    img.save(out, "PNG")
    return out


# ---- Visual 7: Closing ----
def visual_07() -> Path:
    img, d = make_canvas()
    draw_constellation(d, seed=8, area=(0, 0, W, H))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for r, a in [(220, 14), (140, 28), (80, 50)]:
        gd.ellipse([W // 2 - r, 480 - r // 2, W // 2 + r, 480 + r // 2], fill=(255, 195, 0, a))
    glow = glow.filter(ImageFilter.GaussianBlur(50))
    img.paste(glow, (0, 0), glow)
    d = ImageDraw.Draw(img)

    f_quote = font(56, bold=True)
    f_attr  = font(32)
    f_repo  = font(28, bold=True)
    f_thx   = font(24)

    text_centered(d, "\"AURIGA doesn't ask an LLM whether to trade.\"", f_quote, 440, WHITE)
    text_centered(d, "The quantitative system decides. The LLM explains.", f_attr, 560, GOLD)
    d.rectangle([W // 2 - 100, 660, W // 2 + 100, 662], fill=GOLD)
    text_centered(d, "github.com/keisary/AURIGA", f_repo, 700, GOLD)
    text_centered(d, "Thanks -- looking forward to the jury's questions.", f_thx, 780, MUTED)

    out = OUT_DIR / "seg-07.png"
    img.save(out, "PNG")
    return out


def main() -> int:
    out = []
    out.append(visual_01())
    out.append(visual_02())
    out.append(visual_03())
    out.append(visual_04())
    out.append(visual_05())
    out.append(visual_06())
    out.append(visual_07())
    for p in out:
        sz = p.stat().st_size
        print(f"  {p.name}  {sz:>8} bytes  ({sz/1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
