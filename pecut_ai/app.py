"""Pecut AI desktop app: tray icon, menu and the activity watcher loop."""
import argparse
import sys
from functools import partial
from pathlib import Path

from PySide6.QtCore import QLockFile, QTimer
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import installer, phrases
from .hook import STATE_DIR
from .overlay import Overlay
from .settings import ICON_PATH, Settings, Stats, active_sessions, clear_sessions, load_manifest

POLL_MS = 400
STATS_FLUSH_MS = 5000
SNAPSHOT_MS = 350
SNAPSHOT_MAX = 40
SIZES = [0.5, 0.75, 1.0, 1.25, 1.5]
SPEEDS = [(0.75, "speed_slow"), (1.0, "speed_normal"), (1.5, "speed_fast"), (2.0, "speed_insane")]
OPACITIES = [1.0, 0.85, 0.7, 0.5]
VOLUMES = [0.25, 0.5, 0.75, 1.0]


class PecutApp:
    """Wires settings, overlay, tray menu and the session watcher together."""

    def __init__(self, qt_app, demo=False, snapshot_dir=None):
        """Create everything and start the watcher timers."""
        self.qt_app = qt_app
        self.settings = Settings()
        self.stats = Stats()
        self.manifest = load_manifest()
        self.demo = demo
        self.sessions = 0
        self.overlay = Overlay(self.settings, self.stats, self.manifest)
        self.overlay.menu_requested.connect(self.popup_menu)
        self.overlay.moved.connect(lambda x, y: self.settings.set("position", [x, y]))
        self.icon = QIcon(str(ICON_PATH))
        qt_app.setWindowIcon(self.icon)
        self.menu = QMenu()
        self.menu.aboutToShow.connect(self.build_menu)
        self.tray = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(self.icon)
            self.tray.setContextMenu(self.menu)
            self.tray.show()
        self.build_menu()
        self.poll_timer = QTimer(timeout=self.poll)
        self.poll_timer.start(POLL_MS)
        self.flush_timer = QTimer(timeout=self.stats.flush)
        self.flush_timer.start(STATS_FLUSH_MS)
        self.snapshot_dir = Path(snapshot_dir) if snapshot_dir else None
        self.snapshot_count = 0
        if self.snapshot_dir:
            self.snapshot_dir.mkdir(parents=True, exist_ok=True)
            self.snap_timer = QTimer(timeout=self.snapshot)
            self.snap_timer.start(SNAPSHOT_MS)
        self.poll()

    # ------------------------------------------------------------ loop

    def poll(self):
        """Check hook markers and start/stop the whipping accordingly."""
        self.sessions = active_sessions(int(self.settings["stale_timeout_sec"]))
        busy = self.sessions > 0 or self.demo
        if busy and not self.overlay.working:
            self.overlay.start_working()
        elif not busy and self.overlay.working:
            self.overlay.stop_working()
        if self.tray is not None:
            self.tray.setToolTip("Pecut AI - " + self.status_text())

    def status_text(self):
        """Short status line for tooltip and menu header."""
        lang = self.settings["language"]
        n = self.sessions + (1 if self.demo else 0)
        return phrases.ui_text(lang, "working", n=n) if n else phrases.ui_text(lang, "idle")

    def snapshot(self):
        """Dev/test helper: save overlay screenshots while it is visible."""
        if self.overlay.isVisible() and self.snapshot_count < SNAPSHOT_MAX:
            self.overlay.grab().save(str(self.snapshot_dir / f"snap_{self.snapshot_count:02d}.png"))
            self.snapshot_count += 1

    # ------------------------------------------------------------ menu

    def t(self, key, **kwargs):
        """Translate a UI key using the current language."""
        return phrases.ui_text(self.settings["language"], key, **kwargs)

    def popup_menu(self, pos):
        """Show the menu at a screen position (overlay right click)."""
        self.build_menu()
        self.menu.popup(pos)

    def add_choice_menu(self, title, key, options, on_change=None):
        """Submenu of exclusive checkable options bound to one setting."""
        sub = self.menu.addMenu(title)
        group = QActionGroup(sub)
        for value, label in options:
            act = QAction(label, sub, checkable=True)
            act.setChecked(self.settings[key] == value)
            act.triggered.connect(partial(self.set_choice, key, value, on_change))
            group.addAction(act)
            sub.addAction(act)
        return sub

    def add_toggle(self, key, label, on_change=None):
        """Checkable menu entry bound to a boolean setting."""
        act = QAction(label, self.menu, checkable=True)
        act.setChecked(bool(self.settings[key]))
        act.triggered.connect(partial(self.set_choice, key, not self.settings[key], on_change))
        self.menu.addAction(act)

    def add_action(self, label, handler, enabled=True):
        """Plain menu entry."""
        act = QAction(label, self.menu)
        act.setEnabled(enabled)
        if handler is not None:
            act.triggered.connect(handler)
        self.menu.addAction(act)
        return act

    def set_choice(self, key, value, on_change=None, *_):
        """Persist a setting change and run its side effect."""
        self.settings.set(key, value)
        if on_change is not None:
            on_change(value)
        self.overlay.update()

    def build_menu(self):
        """(Re)build the whole menu in the current language."""
        m = self.menu
        m.clear()
        lang = self.settings["language"]
        self.add_action(self.status_text(), None, enabled=False)
        self.add_action(self.t("today", today=self.stats.data["today"], total=self.stats.data["total"]), None, enabled=False)
        m.addSeparator()
        demo = QAction(self.t("demo"), m, checkable=True)
        demo.setChecked(self.demo)
        demo.triggered.connect(self.toggle_demo)
        m.addAction(demo)
        self.add_action(self.t("stop_now"), self.stop_now)
        m.addSeparator()
        name_key = "name_en" if lang == "en" else "name_id"
        styles = [("random", self.t("random"))] + [
            (sid, self.manifest["styles"][sid][name_key]) for sid in self.manifest.get("order", [])]
        self.add_choice_menu(self.t("style"), "style", styles, self.on_style_change)
        self.add_choice_menu(self.t("language"), "language",
                             [("id", self.t("lang_id")), ("en", self.t("lang_en")), ("mix", self.t("lang_mix"))],
                             lambda _v: self.build_menu())
        self.add_choice_menu(self.t("size"), "scale", [(s, f"{int(s * 100)}%") for s in SIZES],
                             lambda _v: self.overlay.relayout())
        self.add_choice_menu(self.t("speed"), "speed", [(v, self.t(k)) for v, k in SPEEDS], self.overlay.set_speed)
        self.add_choice_menu(self.t("opacity"), "opacity", [(o, f"{int(o * 100)}%") for o in OPACITIES],
                             self.overlay.setWindowOpacity)
        self.add_choice_menu(self.t("volume"), "volume", [(v, f"{int(v * 100)}%") for v in VOLUMES])
        m.addSeparator()
        self.add_toggle("sound", self.t("sound"))
        self.add_toggle("show_bubble", self.t("bubble"), lambda _v: self.overlay.relayout())
        self.add_toggle("show_counter", self.t("counter"))
        self.add_toggle("show_ono", self.t("ono"))
        self.add_toggle("always_on_top", self.t("on_top"), lambda _v: self.overlay.apply_window_flags())
        m.addSeparator()
        self.add_action(self.t("reset_pos"), self.reset_position)
        self.add_action(self.t("reset_count"), self.reset_counter)
        m.addSeparator()
        if installer.is_installed():
            self.add_action(self.t("hooks_remove"), self.remove_hooks)
        else:
            self.add_action(self.t("hooks_install"), self.install_hooks)
        m.addSeparator()
        self.add_action(self.t("quit"), self.quit)

    # ------------------------------------------------------------ handlers

    def on_style_change(self, value):
        """Switch GIF immediately when a concrete style is chosen."""
        if value != "random":
            self.overlay.load_style(value)

    def toggle_demo(self, checked):
        """Manual whipping without any AI running."""
        self.demo = bool(checked)
        self.poll()

    def stop_now(self):
        """Forget all sessions and demo mode right away."""
        self.demo = False
        clear_sessions()
        self.poll()

    def reset_position(self):
        """Put the overlay back in the bottom-right corner."""
        self.settings.set("position", None)
        self.overlay.place()

    def reset_counter(self):
        """Zero the lash counter."""
        self.stats.reset()
        self.overlay.update()

    def notify(self, text):
        """Tray balloon (printed when there is no tray)."""
        if self.tray is not None:
            self.tray.showMessage("Pecut AI", text, self.icon, 4000)
        else:
            print(text)

    def install_hooks(self):
        """Install hooks into ~/.claude/settings.json."""
        self.notify(self.t("hooks_ok", path=installer.install()))

    def remove_hooks(self):
        """Remove hooks from ~/.claude/settings.json."""
        self.notify(self.t("hooks_removed", path=installer.uninstall()))

    def quit(self):
        """Save and exit."""
        self.stats.flush()
        if self.tray is not None:
            self.tray.hide()
        self.qt_app.quit()


def parse_args(argv):
    """Command line options."""
    ap = argparse.ArgumentParser(prog="pecut_ai", description="Whip your AI agent while it works.")
    ap.add_argument("--demo", action="store_true", help="start whipping immediately (no AI needed)")
    ap.add_argument("--quit-after", type=float, default=0, help="auto quit after N seconds (testing)")
    ap.add_argument("--snapshot-dir", default=None, help="save overlay screenshots here (testing)")
    return ap.parse_args(argv)


def main(argv=None):
    """Entry point: single instance guard, then run the Qt event loop."""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    qt_app = QApplication(sys.argv[:1])
    qt_app.setApplicationName("Pecut AI")
    qt_app.setQuitOnLastWindowClosed(False)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(STATE_DIR / "app.lock"))
    if not lock.tryLock(100):
        print("Pecut AI is already running.")
        return 1
    app = PecutApp(qt_app, demo=args.demo, snapshot_dir=args.snapshot_dir)
    if args.quit_after > 0:
        QTimer.singleShot(int(args.quit_after * 1000), app.quit)
    code = qt_app.exec()
    lock.unlock()
    return code
