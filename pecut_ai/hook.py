"""Claude Code hook entry point (stdlib only, prints nothing, always exits 0).

Usage from a hook command:
    python path/to/pecut_ai/hook.py start   # prompt submitted / tool used
    python path/to/pecut_ai/hook.py stop    # Claude finished / waits for you

Each Claude Code session gets its own marker file, so several sessions can run
in parallel without write races. The desktop app watches that folder.
"""
import json
import os
import re
import sys
import time
from pathlib import Path

STATE_DIR = Path(os.environ.get("PECUT_AI_HOME", str(Path.home() / ".pecut_ai")))
SESSIONS_DIR = STATE_DIR / "sessions"
WORKING_ACTIONS = ("start", "beat")
IDLE_ACTIONS = ("stop",)


def read_hook_input():
    """Read the hook JSON payload from stdin (empty dict when absent)."""
    if sys.stdin is None or sys.stdin.isatty():
        return {}
    try:
        raw = sys.stdin.buffer.read().decode("utf-8-sig", errors="replace")
        start = raw.find("{")
        return json.loads(raw[start:]) if start >= 0 else {}
    except Exception:
        return {}


def safe_session_id(payload):
    """Return a filesystem safe session id from the hook payload."""
    sid = str(payload.get("session_id") or "default")
    return re.sub(r"[^A-Za-z0-9_-]", "_", sid)[:80] or "default"


def mark_working(sid, payload):
    """Create/refresh the marker file for a working session."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    data = {"ts": time.time(), "event": payload.get("hook_event_name", ""), "cwd": payload.get("cwd", "")}
    tmp = SESSIONS_DIR / (sid + ".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, SESSIONS_DIR / (sid + ".json"))


def mark_idle(sid):
    """Remove the marker file of a session that stopped working."""
    try:
        (SESSIONS_DIR / (sid + ".json")).unlink()
    except FileNotFoundError:
        pass


def main():
    """Dispatch start/beat/stop; never fail the calling hook."""
    try:
        action = sys.argv[1].lower() if len(sys.argv) > 1 else "start"
        payload = read_hook_input()
        sid = safe_session_id(payload)
        if action in WORKING_ACTIONS:
            mark_working(sid, payload)
        elif action in IDLE_ACTIONS:
            mark_idle(sid)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
