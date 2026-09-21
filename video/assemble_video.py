"""Assemble the final AURIGA submission video.

Pipeline (single pass, no intermediate files):
  1. Load 7 video clips (seg-01.mp4 .. seg-07.mp4)
  2. Concatenate them with method='compose' to honor differing durations
  3. Concatenate 7 voice-over mp3 segments in order
  4. Load ambient pad, trim to total length
  5. Composite: video + 7 subtitle PNGs at the right timecode
  6. Mix audio: voice at 1.0, ambient at 0.45
  7. Export MP4 1280x720 30fps, AAC 192k audio, libx264 CRF 20
"""
from __future__ import annotations

import sys
from pathlib import Path

from moviepy import (
    VideoFileClip, AudioFileClip, ImageClip,
    concatenate_videoclips, concatenate_audioclips,
    CompositeVideoClip, CompositeAudioClip,
)

CLIPS_DIR  = Path(r"D:\midas_v2\AURIGA\video\clips")
VOICE_DIR  = Path(r"D:\midas_v2\AURIGA\video\voice")
SUBS_DIR   = Path(r"D:\midas_v2\AURIGA\video\subs\png")
AMBIENT    = Path(r"D:\midas_v2\AURIGA\video\audio\ambient.wav")
OUT_PATH   = Path(r"D:\midas_v2\AURIGA\video\output\AURIGA_submission_video.mp4")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# (seg_id, voice_seconds, start_offset, end_offset, subtitle_lines_count)
SEGMENTS = [
    ("01", 10.56,  0.00, 10.56),
    ("02",  9.41, 10.56, 19.97),
    ("03", 17.14, 19.97, 37.11),
    ("04", 12.00, 37.11, 49.11),
    ("05",  7.75, 49.11, 56.86),
    ("06",  9.05, 56.86, 65.91),
    ("07",  9.00, 65.91, 74.91),
]

FONT_SIZE_DPI = 1920  # not used here, kept for parity with subtitle renderer


def main() -> int:
    print("Loading 7 video clips...")
    v_clips = []
    for sid, _dur, _s, _e in SEGMENTS:
        path = CLIPS_DIR / f"seg-{sid}.mp4"
        c = VideoFileClip(str(path))
        v_clips.append(c)
        print(f"  seg-{sid}  {c.duration:5.2f}s  {path.stat().st_size/1024:7.1f} KB")

    print("\nConcatenating video...")
    video = concatenate_videoclips(v_clips, method="compose")
    total = video.duration
    print(f"  total: {total:.2f}s   size: {video.size}")

    print("\nLoading 7 voice segments...")
    a_voiced = []
    for sid, _dur, _s, _e in SEGMENTS:
        a = AudioFileClip(str(VOICE_DIR / f"seg-{sid}.mp3"))
        a_voiced.append(a)
        print(f"  seg-{sid}  {a.duration:5.2f}s")
    voice = concatenate_audioclips(a_voiced)

    print("\nLoading ambient pad...")
    ambient = AudioFileClip(str(AMBIENT)).with_duration(total)
    # Drop ambient to -7 dB (factor 0.45) so the voice stays on top
    ambient_low = ambient.with_volume_scaled(0.45)
    mix = CompositeAudioClip([voice, ambient_low])
    print(f"  ambient duration: {ambient.duration:.2f}s  -> trimmed to {total:.2f}s")

    print("\nLoading 7 subtitle PNGs...")
    sub_clips = []
    for sid, _dur, start, end in SEGMENTS:
        p = SUBS_DIR / f"sub-{sid}.png"
        sub = (
            ImageClip(str(p))
            .with_start(start)
            .with_duration(end - start)
            .with_position(("center", "bottom"))
        )
        sub_clips.append(sub)
        print(f"  sub-{sid}  {start:5.2f} -> {end:5.2f}  ({end-start:5.2f}s)")

    print("\nCompositing video + subtitles...")
    final = CompositeVideoClip([video, *sub_clips]).with_audio(mix)
    final = final.with_duration(total)
    print(f"  final duration: {final.duration:.2f}s   size: {final.size}")

    print("\nWriting MP4 (libx264 CRF 20 + AAC 192k)...")
    final.write_videofile(
        str(OUT_PATH),
        fps=30,
        codec="libx264",
        audio_codec="aac",
        preset="fast",
        bitrate="5000k",
        audio_bitrate="192k",
        ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
    )
    print(f"\nOK  -> {OUT_PATH}  ({OUT_PATH.stat().st_size/1024/1024:.2f} MB)")
    final.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"FAILED: {e}", file=sys.stderr)
        raise
