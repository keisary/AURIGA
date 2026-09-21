"""Generate 7 voice-over segments for the AURIGA submission video.

Script source: D:\\midas_v2\\AURIGA\\SUBMISSION_KIT.md, section 4.
Voice: en-US-GuyNeural (Edge TTS, free, no key required).
Output: video/voice/seg-XX.mp3 (one per segment)
"""
import asyncio
import sys
from pathlib import Path

import edge_tts

OUT_DIR = Path(r"D:\midas_v2\AURIGA\video\voice")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# (segment_id, text). No en-dash or em-dash: ASCII only.
SEGMENTS = [
    (
        "01",
        "AURIGA, an autonomous quant research and investment agent. "
        "It discovers strategies, validates them statistically, "
        "and deploys them on an Alpaca paper account.",
    ),
    (
        "02",
        "Five years of one-hour and one-day Alpaca market data flow through "
        "thirty-six features into an XGBoost discovery engine "
        "that converts tree paths into human-readable rules.",
    ),
    (
        "03",
        "Three agents, three testable theses. "
        "A one trades direction with debit spreads. "
        "A two predicts volatility shocks, and we turned it into a risk signal, "
        "because buying volatility loses. "
        "A three systematically sells premium in calm regimes.",
    ),
    (
        "04",
        "Every order passes eight deterministic risk gates: "
        "daily loss, exposures, positions, volatility danger. "
        "Fail-closed: if a gate cannot be verified, the order is blocked.",
    ),
    (
        "05",
        "Approved spreads are submitted as atomic multi-leg option orders "
        "to Alpaca paper trading, defined risk, zero commissions.",
    ),
    (
        "06",
        "A Streamlit dashboard and a daily LLM narrative explain every decision. "
        "Positions trace back to their rules and their backtested metrics.",
    ),
    (
        "07",
        "AURIGA doesn't ask an LLM whether to trade. "
        "The quantitative system decides. The LLM explains.",
    ),
]

VOICE = "en-US-GuyNeural"
RATE = "+0%"  # tweak to -10% .. +20% if pacing off


async def gen_one(sid: str, text: str) -> Path:
    out = OUT_DIR / f"seg-{sid}.mp3"
    comm = edge_tts.Communicate(text, voice=VOICE, rate=RATE)
    await comm.save(str(out))
    return out


async def main() -> int:
    print(f"Voice: {VOICE}  rate={RATE}")
    for sid, txt in SEGMENTS:
        p = await gen_one(sid, txt)
        size = p.stat().st_size
        print(f"  seg-{sid}  {size:>7} bytes  {p.name}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
