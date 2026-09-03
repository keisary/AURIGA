"""Génère les visuels AURIGA (cover 1280x720 + bannière README 1280x280).

Charte « Le Cocher céleste » : fond terminal quasi-noir, constellation Auriga
(Capella en or), texte blanc/or — cohérent avec le dashboard (styles.py).
"""
from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1]  # racine du repo (assets/ à la racine)
FONTS = {
    "seguisb": "C:/Windows/Fonts/seguisb.ttf",
    "segoeui": "C:/Windows/Fonts/segoeui.ttf",
    "arialbd": "C:/Windows/Fonts/arialbd.ttf",
    "consola": "C:/Windows/Fonts/consola.ttf",
}
BG = (6, 8, 13)
SURFACE = (11, 15, 23)
TEXT = (231, 233, 238)
DIM = (139, 147, 163)
FAINT = (86, 94, 108)
GOLD = (201, 162, 75)
BLUE = (76, 126, 219)
GREEN = (62, 217, 164)


def font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONTS[kind], size)


def vertical_gradient(w: int, h: int) -> Image.Image:
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    top, bottom = (14, 20, 32), BG
    for y in range(h):
        t = y / max(h - 1, 1)
        d.line(
            [(0, y), (w, y)],
            fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)),
        )
    return img


def starfield(d: ImageDraw.Draw, w: int, h: int, seed: int = 7, n: int = 170) -> None:
    rng = random.Random(seed)
    for _ in range(n):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        r = rng.choice([1, 1, 1, 2])
        a = rng.randint(20, 110)
        col = (231, 233, 238, a) if rng.random() < 0.75 else (139, 147, 163, a)
        d.ellipse([x - r, y - r, x + r, y + r], fill=col)


def glow(d: ImageDraw.Draw, cx: float, cy: float, radius: float, color, alpha: int) -> None:
    """Halo radial approximé par cercles concentriques alpha décroissant."""
    for k in range(14, 0, -1):
        a = int(alpha * (k / 14) ** 2)
        r = radius * (1 + (14 - k) / 6)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color + (a,))


def constellation(
    d: ImageDraw.Draw, cx: float, cy: float, scale: float, with_glow: bool = True
) -> None:
    """Pentagone Auriga (miroir du logo dashboard) centré en (cx, cy)."""
    pts = [(50, 8), (86, 30), (72, 72), (28, 72), (14, 30)]
    sc = [(cx + (x - 50) * scale, cy + (y - 40) * scale) for x, y in pts]
    for i in range(5):
        a, b = sc[i], sc[(i + 1) % 5]
        d.line([a, b], fill=BLUE + (70,), width=2)
    d.line([sc[0], sc[2]], fill=BLUE + (26,), width=1)
    d.line([sc[0], sc[3]], fill=BLUE + (26,), width=1)
    d.line([sc[1], sc[4]], fill=BLUE + (26,), width=1)
    if with_glow:
        glow(d, sc[0][0], sc[0][1], 16, GOLD, 90)
    d.ellipse([sc[0][0] - 7, sc[0][1] - 7, sc[0][0] + 7, sc[0][1] + 7], fill=GOLD)
    for x, y in sc[1:]:
        d.ellipse([x - 2.4, y - 2.4, x + 2.4, y + 2.4], fill=TEXT + (200,))


def text_letterspaced(
    d: ImageDraw.Draw,
    xy: tuple[float, float],
    s: str,
    fnt: ImageFont.FreeTypeFont,
    fill,
    tracking: int,
) -> None:
    x, y = xy
    for ch in s:
        d.text((x, y), ch, font=fnt, fill=fill)
        x += d.textlength(ch, font=fnt) + tracking


def eyebrow(d: ImageDraw.Draw, x: float, y: float, s: str, fnt, tracking: int) -> None:
    text_letterspaced(d, (x, y), s, fnt, GOLD, tracking)


def cover(w: int = 1280, h: int = 720) -> Image.Image:
    img = vertical_gradient(w, h).convert("RGBA")
    ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    starfield(d, w, h)
    # Halo or discret en haut à gauche (rappel du dashboard)
    glow(d, 150, 60, 220, GOLD, 14)
    # Constellation à droite
    constellation(d, 1010, 330, scale=7.4)
    img = Image.alpha_composite(img, ov)

    d = ImageDraw.Draw(img)
    x = 96
    eyebrow(d, x, 196, "ALPACA AI TRADING AGENTS HACKATHON 2026", font("seguisb", 21), 7)
    # AURIGA + point doré
    big = font("arialbd", 158)
    d.text((x - 6, 238), "AURIGA", font=big, fill=TEXT)
    d.text((x + d.textlength("AURIGA", font=big) - 4, 238), ".", font=big, fill=GOLD)
    d.rectangle([x, 448, x + 660, 451], fill=GOLD)
    sub = font("segoeui", 33)
    d.text((x, 478), "Autonomous Quant Research & Investment Agent", font=sub, fill=DIM)
    mono = font("consola", 19)
    d.text(
        (x, 556),
        "discover  \u00b7  validate  \u00b7  deploy   --   paper trading, options defined-risk",
        font=mono,
        fill=FAINT,
    )
    d.text((x, 640), "github.com/keisary/AURIGA", font=mono, fill=FAINT)
    return img.convert("RGB")


def banner(w: int = 1280, h: int = 280) -> Image.Image:
    img = vertical_gradient(w, h).convert("RGBA")
    ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    starfield(d, w, h, seed=3, n=80)
    constellation(d, 210, 140, scale=2.55)
    img = Image.alpha_composite(img, ov)

    d = ImageDraw.Draw(img)
    x = 420
    big = font("arialbd", 92)
    d.text((x - 4, 52), "AURIGA", font=big, fill=TEXT)
    d.text((x + d.textlength("AURIGA", font=big) - 2, 52), ".", font=big, fill=GOLD)
    d.rectangle([x, 166, x + 520, 168], fill=GOLD)
    d.text(
        (x, 192),
        "Autonomous Quant Research & Investment Agent",
        font=font("segoeui", 24),
        fill=DIM,
    )
    return img.convert("RGB")


if __name__ == "__main__":
    (OUT / "assets").mkdir(parents=True, exist_ok=True)
    cover().save(OUT / "assets" / "auriga_cover.png")
    banner().save(OUT / "assets" / "auriga_banner.png")
    print("OK: assets/auriga_cover.png (1280x720) + assets/auriga_banner.png (1280x280)")
