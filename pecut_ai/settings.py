"""User settings, lash statistics and the session activity scanner."""
import datetime as dt
import json
import time
from pathlib import Path

from .hook import SESSIONS_DIR, STATE_DIR

SETTINGS_PATH = STATE_DIR / "settings.json"
STATS_PATH = STATE_DIR / "stats.json"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
GIF_DIR = ASSETS_DIR / "gifs"
SOUND_DIR = ASSETS_DIR / "sounds"
ICON_PATH = ASSETS_DIR / "icon.png"
MANIFEST_PATH = GIF_DIR / "manifest.json"

DEFAULTS = {
    "style": "random",
    "language": "id",
    "sound": True,
    "volume": 0.7,
    "show_bubble": True,
    "show_counter": True,
    "show_ono": True,
    "always_on_top": True,
    "scale": 0.75,
    "speed": 1.0,
    "opacity": 1.0,
    "position": None,
    "stale_timeout_sec": 600,
    "linger_sec": 2.5,
    "bubble_interval_sec": 3.5,
}


def read_json(path, fallback):
    """Read a JSON file, returning fallback on any problem."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return fallback


def write_json(path, data):
    """Atomically write a JSON file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


class Settings:
    """Dict-like persistent settings with defaults."""

    def __init__(self):
        self.data = dict(DEFAULTS)
        self.data.update(read_json(SETTINGS_PATH, {}))

    def __getitem__(self, key):
        return self.data[key]

    def set(self, key, value):
        """Change one setting and persist immediately."""
        self.data[key] = value
        write_json(SETTINGS_PATH, self.data)


class Stats:
    """Lash counter: today and all-time totals."""

    def __init__(self):
        self.data = {"total": 0, "today": 0, "date": self.today_str()}
        self.data.update(read_json(STATS_PATH, {}))
        self.roll_day()
        self.dirty = False

    @staticmethod
    def today_str():
        """Local date as YYYY-MM-DD."""
        return dt.date.today().isoformat()

    def roll_day(self):
        """Reset the daily counter when the date changed."""
        if self.data.get("date") != self.today_str():
            self.data["date"] = self.today_str()
            self.data["today"] = 0

    def add_lash(self):
        """Count one lash."""
        self.roll_day()
        self.data["today"] += 1
        self.data["total"] += 1
        self.dirty = True

    def reset(self):
        """Zero both counters."""
        self.data.update({"total": 0, "today": 0, "date": self.today_str()})
        self.dirty = True
        self.flush()

    def flush(self):
        """Persist when something changed."""
        if self.dirty:
            write_json(STATS_PATH, self.data)
            self.dirty = False


def load_manifest():
    """Load the GIF style manifest shipped with the app."""
    return read_json(MANIFEST_PATH, {"order": [], "styles": {}})


def active_sessions(stale_timeout_sec):
    """Count sessions marked as working; delete markers older than the timeout."""
    if not SESSIONS_DIR.exists():
        return 0
    now = time.time()
    count = 0
    for marker in SESSIONS_DIR.glob("*.json"):
        try:
            age = now - marker.stat().st_mtime
        except FileNotFoundError:
            continue
        if age > stale_timeout_sec:
            try:
                marker.unlink()
            except OSError:
                pass
            continue
        count += 1
    return count


def clear_sessions():
    """Forget every working session (manual stop)."""
    if SESSIONS_DIR.exists():
        for marker in SESSIONS_DIR.glob("*.json"):
            try:
                marker.unlink()
            except OSError:
                pass
