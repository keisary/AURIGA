"""Generate an ambient synth pad (no licensed samples) for the AURIGA
submission video. Output: video/audio/ambient.wav, 90 s, mono, 44.1 kHz.

The pad is a slow A-minor chord (A2, C3, E3, A3) with long attack/release,
a subtle LFO on the master amplitude, and a simple convolution reverb
(white noise impulse with exponential decay) to give it depth.
"""
from __future__ import annotations

import math
import sys
import wave
from pathlib import Path

import numpy as np

OUT = Path(r"D:\midas_v2\AURIGA\video\audio\ambient.wav")
OUT.parent.mkdir(parents=True, exist_ok=True)

SR       = 44100         # sample rate (Hz)
DURATION = 90.0          # seconds (matches total voice-over length)
TWO_PI   = 2.0 * math.pi

# A-minor chord: A2, C3, E3, A3, with E4 on top for sparkle
FREQ_HZ  = [110.00, 130.81, 164.81, 220.00, 329.63]
# amplitude per voice (relative)
AMP      = [0.18, 0.14, 0.16, 0.10, 0.06]


def synth_voice(freq: float, amp: float, n: int, sr: int = SR) -> np.ndarray:
    """Sine voice with slow attack + release envelope."""
    t = np.arange(n) / sr
    # Slow attack 4 s, sustain, release 6 s
    a_sec, r_sec = 4.0, 6.0
    a_n, r_n = int(a_sec * sr), int(r_sec * sr)
    env = np.ones(n, dtype=np.float32)
    if a_n > 0:
        env[:a_n] = np.linspace(0.0, 1.0, a_n, dtype=np.float32)
    if r_n > 0:
        env[-r_n:] = np.linspace(1.0, 0.0, r_n, dtype=np.float32)
    # Add slight detune (chorus-like) by mixing two slightly different freqs
    detune = 1.005
    sig = (
        np.sin(TWO_PI * freq *        t) * 0.5
        + np.sin(TWO_PI * freq * detune * t) * 0.5
    )
    return sig.astype(np.float32) * env * amp


def lfo(n: int, freq: float = 0.10, depth: float = 0.10) -> np.ndarray:
    """Slow LFO at 0.1 Hz, +/- depth."""
    t = np.arange(n) / SR
    return 1.0 - depth + depth * (0.5 + 0.5 * np.sin(TWO_PI * freq * t))


def make_impulse(n: int, decay: float = 2.0) -> np.ndarray:
    """Exponentially decaying white noise -> cheap reverb impulse."""
    rng = np.random.default_rng(seed=42)
    noise = rng.standard_normal(n).astype(np.float32)
    t = np.arange(n) / n
    env = np.exp(-decay * t)
    return noise * env


def convolve(sig: np.ndarray, ir: np.ndarray) -> np.ndarray:
    """FFT-based convolution (much faster than np.convolve for long signals)."""
    n = sig.shape[0] + ir.shape[0] - 1
    # Round up to a power of 2 for FFT speed
    n_fft = 1 << (n - 1).bit_length()
    S = np.fft.rfft(sig, n_fft)
    H = np.fft.rfft(ir, n_fft)
    out = np.fft.irfft(S * H, n_fft).astype(np.float32)
    return out[: sig.shape[0]]


def main() -> int:
    n = int(SR * DURATION)
    pad = np.zeros(n, dtype=np.float32)
    for f, a in zip(FREQ_HZ, AMP):
        pad += synth_voice(f, a, n)
    # Master LFO (subtle tremolo)
    pad *= lfo(n, freq=0.07, depth=0.12).astype(np.float32)
    # Soft clip to keep headroom
    pad = np.tanh(pad * 1.2) * 0.65
    # Reverb
    ir = make_impulse(int(SR * 2.0), decay=2.5)
    wet = convolve(pad, ir)
    # Mix dry 70 / wet 30
    pad = (0.70 * pad + 0.30 * wet).astype(np.float32)
    # Normalize to ~ -20 dBFS so the voice-over stays on top
    peak = float(np.max(np.abs(pad)))
    if peak > 0:
        target = 0.10  # ~ -20 dB
        pad = pad * (target / peak)

    # Write 16-bit mono WAV
    pcm = (pad * 32767.0).clip(-32768, 32767).astype(np.int16)
    with wave.open(str(OUT), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    size = OUT.stat().st_size
    print(f"  ambient.wav  {DURATION:5.1f}s  mono 44.1k  {size/1024/1024:5.2f} MB  {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
