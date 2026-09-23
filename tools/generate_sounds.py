"""Synthesize whip crack WAV variants (pure stdlib, no external samples)."""
import math
import random
import struct
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "pecut_ai" / "assets" / "sounds"
SAMPLE_RATE = 44100

# (seed, whoosh_sec, crack_decay_sec, tail_decay_sec, brightness, crack_gain)
VARIANTS = [
    (1, 0.050, 0.0060, 0.050, 0.85, 1.00),
    (2, 0.070, 0.0045, 0.070, 0.92, 0.95),
    (3, 0.035, 0.0080, 0.040, 0.75, 1.00),
    (4, 0.060, 0.0050, 0.090, 0.95, 0.90),
    (5, 0.045, 0.0070, 0.060, 0.80, 1.00),
]
TOTAL_SEC = 0.45


def synth_crack(seed, whoosh_sec, crack_decay, tail_decay, brightness, crack_gain):
    """Return float samples in [-1, 1] for one whip crack."""
    rng = random.Random(seed)
    n = int(TOTAL_SEC * SAMPLE_RATE)
    crack_at = int(whoosh_sec * SAMPLE_RATE)
    out = []
    lp = 0.0
    hp_prev_in = 0.0
    hp_prev_out = 0.0
    for i in range(n):
        noise = rng.uniform(-1.0, 1.0)
        if i < crack_at:
            t = i / crack_at
            lp += (noise - lp) * (0.05 + 0.4 * t)
            sample = lp * 0.25 * t * t
        else:
            dt = (i - crack_at) / SAMPLE_RATE
            click = crack_gain * math.exp(-dt / crack_decay)
            tail = 0.22 * math.exp(-dt / tail_decay)
            raw = noise * (click + tail)
            hp = brightness * (hp_prev_out + raw - hp_prev_in)
            hp_prev_in, hp_prev_out = raw, hp
            sample = hp * 1.4 + raw * 0.35
            if i - crack_at < 12:
                sample += (1.0 if (i - crack_at) % 2 == 0 else -0.8) * crack_gain
        out.append(sample)
    peak = max(abs(s) for s in out) or 1.0
    return [s / peak * 0.95 for s in out]


def write_wav(path, samples):
    """Write mono 16 bit PCM WAV."""
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(b"".join(struct.pack("<h", int(s * 32767)) for s in samples))


def main():
    """Generate all crack variants."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for idx, params in enumerate(VARIANTS, start=1):
        path = OUT_DIR / f"crack_{idx}.wav"
        write_wav(path, synth_crack(*params))
        print("saved", path.name)


if __name__ == "__main__":
    main()
