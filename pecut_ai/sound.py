"""Lightweight, portable whip sound player (no QtMultimedia).

Windows uses the built-in winsound module, macOS uses afplay and Linux uses the
first available of pw-play / paplay / aplay. Volume is baked into cached copies
of the WAV files, so every backend plays at the right loudness without needing
a volume API. Nothing runs between lashes: no audio threads, no open device.
"""
import array
import random
import shutil
import subprocess
import sys
import wave

from .hook import STATE_DIR
from .settings import SOUND_DIR

CACHE_DIR = STATE_DIR / "cache" / "sounds"
LINUX_PLAYERS = ("pw-play", "paplay", "aplay")

try:
    import winsound
except ImportError:
    winsound = None


def find_player():
    """Command prefix of the external player (None on Windows or when missing)."""
    if sys.platform == "darwin":
        return ["afplay"]
    for name in LINUX_PLAYERS:
        path = shutil.which(name)
        if path:
            return [path, "-q"] if name == "aplay" else [path]
    return None


def scale_wav(src, dst, volume):
    """Write a copy of a 16-bit WAV with every sample multiplied by volume."""
    with wave.open(str(src), "rb") as rf:
        params = rf.getparams()
        frames = rf.readframes(rf.getnframes())
    samples = array.array("h", frames)
    if sys.byteorder == "big":
        samples.byteswap()
    for i, s in enumerate(samples):
        samples[i] = int(s * volume)
    if sys.byteorder == "big":
        samples.byteswap()
    tmp = dst.with_suffix(".tmp")
    with wave.open(str(tmp), "wb") as wf:
        wf.setparams(params)
        wf.writeframes(samples.tobytes())
    tmp.replace(dst)


class SoundPlayer:
    """Plays a random crack variant at the requested volume."""

    def __init__(self):
        """Find the source WAVs and the platform backend."""
        self.sources = sorted(SOUND_DIR.glob("crack_*.wav"))
        self.player = None if winsound else find_player()
        self.volume = None
        self.files = []

    @property
    def available(self):
        """True when there is something to play and a way to play it."""
        return bool(self.sources) and (winsound is not None or self.player is not None)

    def prepare(self, volume):
        """Make sure volume-scaled copies exist for this volume."""
        volume = round(max(0.0, min(1.0, float(volume))), 2)
        if volume == self.volume:
            return
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        files = []
        for src in self.sources:
            dst = CACHE_DIR / f"{src.stem}_v{int(volume * 100)}.wav"
            if not dst.exists():
                scale_wav(src, dst, volume)
            files.append(dst)
        self.files = files
        self.volume = volume

    def play(self, volume):
        """Fire and forget one crack (never raises)."""
        if not self.available:
            return
        try:
            self.prepare(volume)
            path = str(random.choice(self.files))
            if winsound is not None:
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            else:
                subprocess.Popen(self.player + [path], stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
