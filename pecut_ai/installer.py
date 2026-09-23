"""Install / remove the Pecut AI hooks in a Claude Code settings.json file."""
import json
import shutil
import sys
from pathlib import Path

HOOK_SCRIPT = Path(__file__).resolve().parent / "hook.py"
DEFAULT_SETTINGS = Path.home() / ".claude" / "settings.json"
MARKER = "pecut_ai/hook.py"
HOOK_TIMEOUT_SEC = 5

# Claude Code event -> hook action (and tool matcher when the event uses one)
EVENTS = {
    "UserPromptSubmit": ("start", None),
    "PostToolUse": ("beat", "*"),
    "Notification": ("stop", None),
    "Stop": ("stop", None),
    "SessionEnd": ("stop", None),
}


def python_for_hooks():
    """Console python next to the running interpreter (not pythonw)."""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        candidate = exe.with_name("python.exe")
        if candidate.exists():
            exe = candidate
    return exe


def hook_command(action):
    """Build the shell command for one hook action (forward slashes, quoted)."""
    py = python_for_hooks().as_posix()
    script = HOOK_SCRIPT.as_posix()
    return f'"{py}" "{script}" {action}'


def is_ours(entry):
    """True when a hooks entry was written by Pecut AI."""
    return any(MARKER in str(h.get("command", "")).replace("\\", "/") for h in entry.get("hooks", []))


def load_settings(path):
    """Read settings.json (empty dict when missing)."""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    return json.loads(text) if text else {}


def save_settings(path, data):
    """Back up the old file once, then write the new settings."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + ".pecut_backup"))
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def strip_ours(data):
    """Remove every Pecut AI hook entry, dropping emptied event lists."""
    hooks = data.get("hooks", {})
    for event in list(hooks.keys()):
        kept = [e for e in hooks[event] if not is_ours(e)]
        if kept:
            hooks[event] = kept
        else:
            del hooks[event]
    if not hooks and "hooks" in data:
        del data["hooks"]
    return data


def install(settings_path=DEFAULT_SETTINGS):
    """Add (or refresh) the Pecut AI hooks; returns the settings path."""
    path = Path(settings_path)
    data = strip_ours(load_settings(path))
    hooks = data.setdefault("hooks", {})
    for event, (action, matcher) in EVENTS.items():
        entry = {"hooks": [{"type": "command", "command": hook_command(action), "timeout": HOOK_TIMEOUT_SEC}]}
        if matcher is not None:
            entry = {"matcher": matcher, **entry}
        hooks.setdefault(event, []).append(entry)
    save_settings(path, data)
    return path


def uninstall(settings_path=DEFAULT_SETTINGS):
    """Remove the Pecut AI hooks; returns the settings path."""
    path = Path(settings_path)
    if path.exists():
        save_settings(path, strip_ours(load_settings(path)))
    return path


def is_installed(settings_path=DEFAULT_SETTINGS):
    """True when at least one Pecut AI hook is present."""
    try:
        data = load_settings(Path(settings_path))
    except Exception:
        return False
    return any(is_ours(e) for entries in data.get("hooks", {}).values() for e in entries)


def main():
    """CLI: python -m pecut_ai.installer [install|uninstall|status] [--settings PATH]."""
    args = sys.argv[1:]
    action = args[0] if args else "install"
    path = DEFAULT_SETTINGS
    if "--settings" in args:
        path = Path(args[args.index("--settings") + 1])
    if action == "install":
        print("Pecut AI hooks installed in", install(path))
    elif action == "uninstall":
        print("Pecut AI hooks removed from", uninstall(path))
    else:
        print("installed" if is_installed(path) else "not installed", "-", path)


if __name__ == "__main__":
    main()
