"""Pre-render subtitle overlays as transparent PNGs (Pillow).

Each subtitle PNG is sized 1600x230 with a soft drop-shadow so it reads
cleanly on the dark Tech & Night background. They get composited onto the
final video by assemble_video.py with a precise start/end per segment.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUT_DIR = Path(r"D:\midas_v2\AURIGA\video\subs\png")
OUT_DIR.mkdir(parents=True, exist_ok=True)

FONT_PATH = Path(r"C:\Windows\Fonts\georgia.ttf")
FONT_SIZE = 52
LINE_GAP  = 8
MAX_W     = 1600          # max subtitle strip width (px)
PADDING   = 28
CANVAS_W  = 1920
CANVAS_H  = 240

# (id, start_seconds, end_seconds, text_lines)
SEGMENTS = [
    ("01", 0.00, 10.56, [
        "AURIGA, an autonomous quant research and investment agent.",
        "It discovers strategies, validates them statistically,",
        "and deploys them on an Alpaca paper account.",
    ]),
    ("02", 10.56, 19.97, [
        "Five years of one-hour and one-day Alpaca market data",
        "flow through thirty-six features into an XGBoost",
        "discovery engine that converts tree paths into rules.",
    ]),
    ("03", 19.97, 37.11, [
        "Three agents, three testable theses.",
        "A1 trades direction with debit spreads.",
        "A2 is a risk signal -- buying volatility loses.",
        "A3 systematically sells premium in calm regimes.",
    ]),
    ("04", 37.11, 49.11, [
        "Every order passes eight deterministic risk gates:",
        "daily loss, exposures, positions, volatility danger.",
        "Fail-closed: a gate that cannot be verified blocks the order.",
    ]),
    ("05", 49.11, 56.86, [
        "Approved spreads are submitted as atomic multi-leg",
        "option orders to Alpaca paper trading --",
        "defined risk, zero commissions.",
    ]),
    ("06", 56.86, 65.91, [
        "A Streamlit dashboard and a daily LLM narrative",
        "explain every decision. Positions trace back",
        "to their rules and their backtested metrics.",
    ]),
    ("07", 65.91, 74.91, [
        "\"AURIGA doesn't ask an LLM whether to trade.\"",
        "The quantitative system decides. The LLM explains.",
    ]),
]


def make_subtitle(lines: list[str]) -> Path:
    fnt = ImageFont.truetype(str(FONT_PATH), FONT_SIZE)
    # Measure text block
    line_h = FONT_SIZE + LINE_GAP
    block_h = line_h * len(lines)
    # Render text into a temp image to measure width
    tmp = Image.new("RGBA", (MAX_W, block_h + LINE_GAP), (0, 0, 0, 0))
    td = ImageDraw.Draw(tmp)
    widths = []
    for i, line in enumerate(lines):
        bbox = td.textbbox((0, 0), line, font=fnt)
        w = bbox[2] - bbox[0]
        widths.append(w)
        td.text((0, i * line_h), line, font=fnt, fill=(255, 255, 255, 255))
    block_w = min(MAX_W, max(widths) + 2 * PADDING)
    # Crop the temp image to actual width
    text_img = tmp.crop((0, 0, max(widths), block_h))
    # Build canvas with shadow + plate
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    cd = ImageDraw.Draw(canvas)
    # Plate position (centered, 16px from bottom of canvas)
    plate_x = (CANVAS_W - block_w) // 2
    plate_y = (CANVAS_H - block_h) // 2
    plate_box = [plate_x - PADDING, plate_y - PADDING,
                 plate_x + block_w + PADDING, plate_y + block_h + PADDING]
    # Soft shadow
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(plate_box, radius=16, fill=(0, 0, 0, 200))
    shadow = shadow.filter(ImageFilter.GaussianBlur(8))
    canvas = Image.alpha_composite(canvas, shadow)
    cd = ImageDraw.Draw(canvas)
    cd.rounded_rectangle(plate_box, radius=16, fill=(8, 8, 20, 220), outline=(255, 195, 0, 220), width=2)
    # Paste text
    canvas.paste(text_img, (plate_x, plate_y), text_img)
    return canvas


def main() -> int:
    for sid, _start, _end, lines in SEGMENTS:
        img = make_subtitle(lines)
        out = OUT_DIR / f"sub-{sid}.png"
        img.save(out, "PNG")
        print(f"  sub-{sid}  {out.stat().st_size/1024:5.1f} KB  {len(lines)} lines  {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
