"""Floating always-on-top overlay that plays the whipping GIF."""
import random
import time

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QMovie, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from . import phrases
from .settings import GIF_DIR, SOUND_DIR

try:
    from PySide6.QtMultimedia import QSoundEffect
except Exception:
    QSoundEffect = None

MARGIN = 6
BUBBLE_BASE_H = 66
BUBBLE_TAIL = 12
ONO_MS = 480
SHAKE_MS = 110
ANIM_TICK_MS = 30
SCREEN_MARGIN = 24


class Overlay(QWidget):
    """Frameless, translucent, draggable whipping window."""

    menu_requested = Signal(QPoint)
    lashed = Signal()
    moved = Signal(int, int)

    def __init__(self, settings, stats, manifest):
        """Build the window from settings, stats and the GIF manifest."""
        super().__init__()
        self.settings = settings
        self.stats = stats
        self.manifest = manifest
        self.movie = None
        self.style_id = None
        self.style_meta = {}
        self.working = False
        self.bubble_text = ""
        self.ono_text = ""
        self.ono_t0 = 0.0
        self.shake_t0 = 0.0
        self.drag_offset = None
        self.drag_moved = False
        self.sounds = self.load_sounds()
        self.apply_window_flags()
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow, True)
        self.bubble_timer = QTimer(self, timeout=self.next_nag)
        self.linger_timer = QTimer(self, singleShot=True, timeout=self.finish_linger)
        self.anim_timer = QTimer(self, interval=ANIM_TICK_MS, timeout=self.update)
        self.setWindowOpacity(float(self.settings["opacity"]))
        self.relayout()

    # ------------------------------------------------------------ setup

    def apply_window_flags(self):
        """Frameless tool window, optionally always on top."""
        flags = Qt.FramelessWindowHint | Qt.Tool | Qt.NoDropShadowWindowHint
        if self.settings["always_on_top"]:
            flags |= Qt.WindowStaysOnTopHint
        visible = self.isVisible()
        self.setWindowFlags(flags)
        if visible:
            self.show()

    def load_sounds(self):
        """Load all crack WAV variants (empty list if audio is unavailable)."""
        if QSoundEffect is None:
            return []
        out = []
        for path in sorted(SOUND_DIR.glob("crack_*.wav")):
            eff = QSoundEffect(self)
            eff.setSource(QUrl.fromLocalFile(str(path)))
            out.append(eff)
        return out

    def gif_size(self):
        """Scaled GIF size in pixels."""
        meta = self.style_meta or next(iter(self.manifest["styles"].values()), {"width": 360, "height": 270})
        scale = float(self.settings["scale"])
        return int(meta["width"] * scale), int(meta["height"] * scale)

    def bubble_h(self):
        """Height reserved for the speech bubble."""
        if not self.settings["show_bubble"]:
            return 0
        return int(BUBBLE_BASE_H * max(0.75, float(self.settings["scale"])))

    def gif_rect(self):
        """Where the GIF is painted inside the window."""
        gw, gh = self.gif_size()
        return QRect(MARGIN, MARGIN + self.bubble_h(), gw, gh)

    def relayout(self):
        """Resize the window after a size/bubble change, keeping it on screen."""
        gw, gh = self.gif_size()
        self.setFixedSize(gw + 2 * MARGIN, gh + self.bubble_h() + 2 * MARGIN)
        self.place()
        self.update()

    def place(self):
        """Move to the saved position or the bottom-right corner."""
        screen = QGuiApplication.primaryScreen().availableGeometry()
        pos = self.settings["position"]
        if pos:
            x, y = pos
        else:
            x = screen.right() - self.width() - SCREEN_MARGIN
            y = screen.bottom() - self.height() - SCREEN_MARGIN
        on_any = any(s.availableGeometry().intersects(QRect(x, y, self.width(), self.height()))
                     for s in QGuiApplication.screens())
        if not on_any:
            x = screen.right() - self.width() - SCREEN_MARGIN
            y = screen.bottom() - self.height() - SCREEN_MARGIN
        self.move(x, y)

    # ------------------------------------------------------------ style

    def choose_style(self):
        """Resolve 'random' into a concrete style id."""
        order = self.manifest.get("order") or list(self.manifest["styles"].keys())
        wanted = self.settings["style"]
        if wanted in self.manifest["styles"]:
            return wanted
        choices = [s for s in order if s != self.style_id] or order
        return random.choice(choices)

    def load_style(self, style_id):
        """Swap the playing GIF to the given style."""
        if self.movie is not None:
            self.movie.stop()
            self.movie.deleteLater()
        self.style_id = style_id
        self.style_meta = self.manifest["styles"][style_id]
        self.movie = QMovie(str(GIF_DIR / self.style_meta["file"]), parent=self)
        self.movie.setCacheMode(QMovie.CacheAll)
        self.movie.setSpeed(int(100 * float(self.settings["speed"])))
        self.movie.frameChanged.connect(self.on_frame)
        self.relayout()
        if self.working:
            self.movie.start()
        else:
            self.movie.jumpToFrame(0)

    def set_speed(self, speed):
        """Apply a new playback speed."""
        if self.movie is not None:
            self.movie.setSpeed(int(100 * speed))

    # ------------------------------------------------------------ state

    def start_working(self):
        """AI started working: show up and start whipping."""
        self.linger_timer.stop()
        self.working = True
        if self.movie is None or self.settings["style"] == "random":
            self.load_style(self.choose_style())
        elif self.style_id != self.settings["style"]:
            self.load_style(self.settings["style"])
        self.bubble_text = phrases.pick(phrases.START, self.settings["language"])
        self.bubble_timer.start(int(float(self.settings["bubble_interval_sec"]) * 1000))
        self.movie.start()
        self.anim_timer.start()
        self.show()
        self.raise_()

    def stop_working(self):
        """AI finished: say something nice-ish, then disappear."""
        if not self.working:
            return
        self.working = False
        self.bubble_timer.stop()
        if self.movie is not None:
            self.movie.setPaused(True)
        self.bubble_text = phrases.pick(phrases.DONE, self.settings["language"])
        self.update()
        self.linger_timer.start(int(float(self.settings["linger_sec"]) * 1000))

    def finish_linger(self):
        """Hide after the linger period."""
        if not self.working:
            if self.movie is not None:
                self.movie.stop()
            self.anim_timer.stop()
            self.hide()

    def next_nag(self):
        """Rotate the nagging speech bubble."""
        self.bubble_text = phrases.pick(phrases.NAG, self.settings["language"], avoid=self.bubble_text)
        self.update()

    def on_frame(self, index):
        """Repaint every frame; fire the lash effects on crack frames."""
        if self.working and index in self.style_meta.get("crack_frames", []):
            self.lash()
        self.update()

    def lash(self):
        """One whip hit: counter, sound, onomatopoeia, shake."""
        self.stats.add_lash()
        self.lashed.emit()
        now = time.monotonic()
        self.ono_text = phrases.pick(phrases.ONO, self.settings["language"])
        self.ono_t0 = now
        self.shake_t0 = now
        if self.settings["sound"] and self.sounds:
            eff = random.choice(self.sounds)
            eff.setVolume(float(self.settings["volume"]))
            eff.play()

    # ------------------------------------------------------------ painting

    def paintEvent(self, event):
        """Draw bubble, GIF card, counter badge and onomatopoeia."""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        now = time.monotonic()
        gr = self.gif_rect()
        if (now - self.shake_t0) * 1000 < SHAKE_MS:
            gr.translate(random.randint(-3, 3), random.randint(-2, 2))
        self.paint_gif(p, gr)
        if self.settings["show_bubble"] and self.bubble_text:
            self.paint_bubble(p)
        if self.settings["show_counter"]:
            self.paint_counter(p, gr)
        if self.settings["show_ono"] and self.ono_text and (now - self.ono_t0) * 1000 < ONO_MS:
            self.paint_ono(p, gr, (now - self.ono_t0) * 1000 / ONO_MS)
        p.end()

    def paint_gif(self, p, gr):
        """GIF inside a rounded card with a thick border."""
        radius = 14
        path = QPainterPath()
        path.addRoundedRect(QRectF(gr), radius, radius)
        p.save()
        p.setClipPath(path)
        if self.movie is not None:
            pix = self.movie.currentPixmap()
            p.setRenderHint(QPainter.SmoothPixmapTransform, not self.style_meta.get("pixelated", False))
            p.drawPixmap(gr, pix)
        p.restore()
        p.setPen(QPen(QColor(30, 20, 15), 3))
        p.drawPath(path)

    def paint_bubble(self, p):
        """White speech bubble with a tail pointing at the foreman."""
        gw, _ = self.gif_size()
        bh = self.bubble_h() - BUBBLE_TAIL
        rect = QRectF(MARGIN + 2, MARGIN + 2, gw - 4, bh - 4)
        path = QPainterPath()
        path.addRoundedRect(rect, 14, 14)
        tail_x = MARGIN + gw * 0.2
        tail = QPolygonF([QPointF(tail_x - 9, rect.bottom() - 1), QPointF(tail_x + 9, rect.bottom() - 1),
                          QPointF(tail_x - 4, rect.bottom() + BUBBLE_TAIL + 2)])
        tail_path = QPainterPath()
        tail_path.addPolygon(tail)
        path = path.united(tail_path)
        p.setPen(QPen(QColor(30, 20, 15), 2.5))
        p.setBrush(QColor(255, 255, 255, 245))
        p.drawPath(path)
        font = QFont("Arial", 1, QFont.Black)
        font.setPixelSize(int(15 * max(0.8, float(self.settings["scale"]))))
        p.setFont(font)
        p.setPen(QColor(25, 20, 20))
        p.drawText(rect.adjusted(10, 4, -10, -4), Qt.AlignCenter | Qt.TextWordWrap, self.bubble_text)

    def paint_counter(self, p, gr):
        """Pill badge with the lash counter."""
        text = phrases.ui_text(self.settings["language"], "counter_label", n=self.stats.data["today"])
        font = QFont("Arial", 1, QFont.Bold)
        font.setPixelSize(int(12 * max(0.8, float(self.settings["scale"]))))
        p.setFont(font)
        tw = p.fontMetrics().horizontalAdvance(text) + 16
        th = p.fontMetrics().height() + 6
        badge = QRectF(gr.right() - tw - 8, gr.bottom() - th - 8, tw, th)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(20, 15, 10, 200))
        p.drawRoundedRect(badge, th / 2, th / 2)
        p.setPen(QColor(255, 220, 80))
        p.drawText(badge, Qt.AlignCenter, text)

    def paint_ono(self, p, gr, t):
        """Popping, fading CTAR! text near the robot."""
        pop = 1.35 - 0.35 * min(1.0, t * 3)
        alpha = int(255 * (1.0 - max(0.0, t - 0.55) / 0.45))
        font = QFont("Impact", 1, QFont.Black)
        font.setPixelSize(int(gr.height() * 0.17 * pop))
        path = QPainterPath()
        path.addText(0, 0, font, self.ono_text)
        box = path.boundingRect()
        cx = gr.left() + gr.width() * 0.62
        cy = gr.top() + gr.height() * 0.2
        path.translate(cx - box.width() / 2 - box.left(), cy - box.height() / 2 - box.top())
        p.save()
        p.translate(cx, cy)
        p.rotate(-8)
        p.translate(-cx, -cy)
        p.setPen(QPen(QColor(20, 10, 5, alpha), max(3, gr.height() // 45), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        p.fillPath(path, QColor(255, 225, 40, alpha))
        p.restore()

    # ------------------------------------------------------------ mouse

    def mousePressEvent(self, event):
        """Start dragging (left) or open the menu (right)."""
        if event.button() == Qt.LeftButton:
            self.drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.drag_moved = False
        elif event.button() == Qt.RightButton:
            self.menu_requested.emit(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        """Drag the window around."""
        if self.drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_offset)
            self.drag_moved = True

    def mouseReleaseEvent(self, event):
        """Remember where the window was dropped."""
        if event.button() == Qt.LeftButton and self.drag_offset is not None:
            self.drag_offset = None
            if self.drag_moved:
                self.moved.emit(self.x(), self.y())

    def mouseDoubleClickEvent(self, event):
        """Double click cycles to the next style."""
        order = self.manifest.get("order", [])
        if order and self.style_id in order:
            self.load_style(order[(order.index(self.style_id) + 1) % len(order)])
