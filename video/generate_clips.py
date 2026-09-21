"""Turn 7 PNG visuals into 1280x720 30fps MP4 clips with a Ken Burns motion
(zoom in / out / pan) at the per-segment durations measured by ffprobe.

Uses moviepy (cleaner than wrestling with ffmpeg 8 expression parsing).
"""
from __future__ import annotations

import sys
from pathlib import Path

from moviepy import ImageClip

FRAMES_DIR = Path(r"D:\midas_v2\AURIGA\video\clips\frames")
CLIPS_DIR  = Path(r"D:\midas_v2\AURIGA\video\clips")
CLIPS_DIR.mkdir(parents=True, exist_ok=True)

# (id, duration_seconds, mode)
SEGMENTS = [
    ("01", 10.56, "in"),
    ("02",  9.41, "pan"),
    ("03", 17.14, "out"),
    ("04", 12.00, "in"),
    ("05",  7.75, "pan"),
    ("06",  9.05, "in"),
    ("07",  9.00, "out"),
]


def make_clip(seg_id: str, dur: float, mode: str) -> Path:
    src = FRAMES_DIR / f"seg-{seg_id}.png"
    dst = CLIPS_DIR / f"seg-{seg_id}.mp4"
    base = ImageClip(str(src)).with_duration(dur).with_fps(30)

    if mode == "in":
        # 1.00 -> 1.10 zoom
        clip = base.resized(lambda t: 1.0 + 0.10 * t / dur)
    elif mode == "out":
        # 1.10 -> 1.00
        clip = base.resized(lambda t: 1.10 - 0.10 * t / dur)
    else:  # pan: slight horizontal pan + zoom
        clip = base.resized(lambda t: 1.02 + 0.04 * t / dur)

    # Force final 1280x720
    if clip.size != (1280, 720):
        clip = clip.resized((1280, 720))

    clip.write_videofile(
        str(dst),
        fps=30,
        codec="libx264",
        preset="fast",
        bitrate="4000k",
        audio=False,
        ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
    )
    return dst


def main() -> int:
    for sid, dur, mode in SEGMENTS:
        try:
            p = make_clip(sid, dur, mode)
            sz = p.stat().st_size
            print(f"  seg-{sid}  {dur:5.2f}s  {mode:<4}  {sz/1024:6.1f} KB  {p.name}")
        except Exception as e:
            print(f"  seg-{sid}  FAILED: {e}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
