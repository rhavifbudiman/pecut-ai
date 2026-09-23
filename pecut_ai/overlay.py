"""Floating always-on-top overlay that plays the whipping animation.

Performance notes (why this file looks the way it does):
- Every GIF frame is decoded, scaled and framed (rounded card + border) ONCE when
  a style is loaded. Playing a frame is then a single pixmap copy.
- The speech bubble, counter badge and CTAR! text are also rendered once into
  pixmaps and only re-rendered when their text or the size changes.
- One timer drives the animation at the GIF's own frame rate and only the GIF
  area is repainted per frame. Nothing ticks while the window is hidden.
"""
import random
import time

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QGuiApplication, QImage, QImageReader, QPainter, QPainterPath,
                           QPen, QPixmap, QPolygonF)
from PySide6.QtWidgets import QWidget

from . import phrases
from .settings import GIF_DIR
from .sound import SoundPlayer

MARGIN = 6
BUBBLE_BASE_H = 66
BUBBLE_TAIL = 12
ONO_MS = 480
ONO_POP = 1.35
SHAKE_MS = 110
SHAKE_PAD = 6
CARD_RADIUS = 14
CARD_BORDER = 3
CARD_PAD = 2
DEFAULT_FRAME_MS = 40
MIN_FRAME_MS = 10
ECO_FRAME_STEP = 2
SCREEN_MARGIN = 24
INK = QColor(30, 20, 15)


def new_canvas(w, h, dpr):
    """Transparent HiDPI-aware image to paint into."""
    img = QImage(max(1, round(w * dpr)), max(1, round(h * dpr)), QImage.Format_ARGB32_Premultiplied)
    img.setDevicePixelRatio(dpr)
    img.fill(Qt.transparent)
    return img


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
        self.style_id = None
        self.style_meta = {}
        self.frames = []
        self.frames_size = None
        self.delays = []
        self.frame_index = 0
        self.working = False
        self.bubble_text = ""
        self.bubble_pix = None
        self.counter_key = None
        self.counter_pix = None
        self.ono_text = ""
        self.ono_pix = None
        self.ono_t0 = 0.0
        self.shake_t0 = 0.0
        self.drag_offset = None
        self.drag_moved = False
        self.sound = SoundPlayer()
        self.apply_window_flags()
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow, True)
        self.bubble_timer = QTimer(self, timeout=self.next_nag)
        self.linger_timer = QTimer(self, singleShot=True, timeout=self.finish_linger)
        self.frame_timer = QTimer(self, singleShot=True, timeout=self.next_frame)
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

    def dpr(self):
        """Device pixel ratio of the screen the window is on."""
        screen = self.screen() or QGuiApplication.primaryScreen()
        return screen.devicePixelRatio() if screen else 1.0

    def scale(self):
        """User size factor."""
        return float(self.settings["scale"])

    def gif_size(self):
        """Scaled GIF size in pixels."""
        meta = self.style_meta or next(iter(self.manifest["styles"].values()), {"width": 360, "height": 270})
        return int(meta["width"] * self.scale()), int(meta["height"] * self.scale())

    def bubble_h(self):
        """Height reserved for the speech bubble."""
        if not self.settings["show_bubble"]:
            return 0
        return int(BUBBLE_BASE_H * max(0.75, self.scale()))

    def gif_rect(self):
        """Where the GIF is painted inside the window."""
        gw, gh = self.gif_size()
        return QRect(MARGIN, MARGIN + self.bubble_h(), gw, gh)

    def relayout(self):
        """Resize after a size/bubble change, re-render caches, keep on screen."""
        gw, gh = self.gif_size()
        self.setFixedSize(gw + 2 * MARGIN, gh + self.bubble_h() + 2 * MARGIN)
        if self.style_id is not None and self.frames and self.frames_size != (gw, gh, self.dpr()):
            self.bake_frames()
        self.bubble_pix = None
        self.counter_key = None
        self.ono_pix = None
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
        """Swap the playing animation to the given style."""
        self.style_id = style_id
        self.style_meta = self.manifest["styles"][style_id]
        self.frames = []
        self.frames_size = None
        self.frame_index = 0
        self.relayout()
        self.bake_frames()
        self.update()

    def bake_frames(self):
        """Decode the GIF once and pre-render every frame as a finished card."""
        gw, gh = self.gif_size()
        dpr = self.dpr()
        reader = QImageReader(str(GIF_DIR / self.style_meta["file"]))
        mode = Qt.FastTransformation if self.style_meta.get("pixelated") else Qt.SmoothTransformation
        target = QSize(round(gw * dpr), round(gh * dpr))
        card = QPainterPath()
        card.addRoundedRect(QRectF(CARD_PAD, CARD_PAD, gw, gh), CARD_RADIUS, CARD_RADIUS)
        frames, delays = [], []
        while True:
            img = reader.read()
            if img.isNull():
                break
            delays.append(reader.nextImageDelay() or DEFAULT_FRAME_MS)
            src = img.scaled(target, Qt.IgnoreAspectRatio, mode)
            src.setDevicePixelRatio(dpr)
            out = new_canvas(gw + 2 * CARD_PAD, gh + 2 * CARD_PAD, dpr)
            p = QPainter(out)
            p.setRenderHint(QPainter.Antialiasing, True)
            p.setClipPath(card)
            p.drawImage(QPointF(CARD_PAD, CARD_PAD), src)
            p.setClipping(False)
            p.setPen(QPen(INK, CARD_BORDER))
            p.drawPath(card)
            p.end()
            frames.append(QPixmap.fromImage(out))
        self.frames = frames
        self.delays = delays or [DEFAULT_FRAME_MS]
        self.frames_size = (gw, gh, dpr)
        self.frame_index = min(self.frame_index, max(0, len(frames) - 1))

    def set_speed(self, _speed):
        """Speed is read on every frame tick, nothing to do here."""

    # ------------------------------------------------------------ state

    def start_working(self):
        """AI started working: show up and start whipping."""
        self.linger_timer.stop()
        self.working = True
        if not self.frames or self.settings["style"] == "random":
            self.load_style(self.choose_style())
        elif self.style_id != self.settings["style"]:
            self.load_style(self.settings["style"])
        self.set_bubble(phrases.pick(phrases.START, self.settings["language"]))
        self.bubble_timer.start(int(float(self.settings["bubble_interval_sec"]) * 1000))
        self.frame_index = 0
        self.show()
        self.raise_()
        self.schedule_frame()

    def stop_working(self):
        """AI finished: say something nice-ish, then disappear."""
        if not self.working:
            return
        self.working = False
        self.bubble_timer.stop()
        self.frame_timer.stop()
        self.ono_text = ""
        self.set_bubble(phrases.pick(phrases.DONE, self.settings["language"]))
        self.linger_timer.start(int(float(self.settings["linger_sec"]) * 1000))

    def finish_linger(self):
        """Hide after the linger period."""
        if not self.working:
            self.frame_timer.stop()
            self.hide()

    def set_bubble(self, text):
        """Change the speech bubble text (re-rendered lazily)."""
        self.bubble_text = text
        self.bubble_pix = None
        self.update()

    def next_nag(self):
        """Rotate the nagging speech bubble."""
        self.set_bubble(phrases.pick(phrases.NAG, self.settings["language"], avoid=self.bubble_text))

    def frame_step(self):
        """How many GIF frames to advance per tick (eco mode skips every other one)."""
        return ECO_FRAME_STEP if self.settings["eco_mode"] else 1

    def schedule_frame(self):
        """Arm the timer for the current frame's duration at the chosen speed."""
        if not self.working or not self.frames:
            return
        step = self.frame_step()
        ms = sum(self.delays[(self.frame_index + k) % len(self.delays)] for k in range(step))
        self.frame_timer.start(max(MIN_FRAME_MS, int(ms / max(0.1, float(self.settings["speed"])))))

    def next_frame(self):
        """Advance the animation, fire lash effects on crack frames, repaint the GIF area."""
        if not self.working or not self.frames:
            return
        n = len(self.frames)
        cracks = self.style_meta.get("crack_frames", [])
        for _ in range(self.frame_step()):
            self.frame_index = (self.frame_index + 1) % n
            if self.frame_index in cracks:
                self.lash()
        self.update(self.gif_rect().adjusted(-SHAKE_PAD, -SHAKE_PAD, SHAKE_PAD, SHAKE_PAD))
        self.schedule_frame()

    def lash(self):
        """One whip hit: counter, sound, onomatopoeia, shake."""
        self.stats.add_lash()
        self.lashed.emit()
        now = time.monotonic()
        text = phrases.pick(phrases.ONO, self.settings["language"])
        if text != self.ono_text:
            self.ono_text = text
            self.ono_pix = None
        self.ono_t0 = now
        self.shake_t0 = now
        if self.settings["sound"]:
            self.sound.play(self.settings["volume"])

    # ------------------------------------------------------------ cached layers

    def render_bubble(self):
        """Speech bubble with a tail pointing at the foreman, as a pixmap."""
        gw, _ = self.gif_size()
        bh = self.bubble_h() - BUBBLE_TAIL
        img = new_canvas(gw + 2 * MARGIN, self.bubble_h() + MARGIN, self.dpr())
        rect = QRectF(MARGIN + 2, MARGIN + 2, gw - 4, bh - 4)
        path = QPainterPath()
        path.addRoundedRect(rect, 14, 14)
        tail_x = MARGIN + gw * 0.2
        tail = QPolygonF([QPointF(tail_x - 9, rect.bottom() - 1), QPointF(tail_x + 9, rect.bottom() - 1),
                          QPointF(tail_x - 4, rect.bottom() + BUBBLE_TAIL + 2)])
        tail_path = QPainterPath()
        tail_path.addPolygon(tail)
        path = path.united(tail_path)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(QPen(INK, 2.5))
        p.setBrush(QColor(255, 255, 255, 245))
        p.drawPath(path)
        font = QFont("Arial", 1, QFont.Black)
        font.setPixelSize(int(15 * max(0.8, self.scale())))
        p.setFont(font)
        p.setPen(QColor(25, 20, 20))
        p.drawText(rect.adjusted(10, 4, -10, -4), Qt.AlignCenter | Qt.TextWordWrap, self.bubble_text)
        p.end()
        return QPixmap.fromImage(img)

    def render_counter(self, text):
        """Pill badge with the lash counter, as a pixmap."""
        font = QFont("Arial", 1, QFont.Bold)
        font.setPixelSize(int(12 * max(0.8, self.scale())))
        metrics = QFontMetrics(font)
        tw = metrics.horizontalAdvance(text) + 16
        th = metrics.height() + 6
        img = new_canvas(tw, th, self.dpr())
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setFont(font)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(20, 15, 10, 200))
        p.drawRoundedRect(QRectF(0, 0, tw, th), th / 2, th / 2)
        p.setPen(QColor(255, 220, 80))
        p.drawText(QRectF(0, 0, tw, th), Qt.AlignCenter, text)
        p.end()
        return QPixmap.fromImage(img)

    def render_ono(self, gr):
        """CTAR! text at its biggest pop size, tilted, as a pixmap."""
        font = QFont("Impact", 1, QFont.Black)
        font.setPixelSize(int(gr.height() * 0.17 * ONO_POP))
        path = QPainterPath()
        path.addText(0, 0, font, self.ono_text)
        stroke = max(3, gr.height() // 45)
        box = path.boundingRect().adjusted(-stroke, -stroke, stroke, stroke)
        side = int((box.width() ** 2 + box.height() ** 2) ** 0.5) + 2
        img = new_canvas(side, side, self.dpr())
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.translate(side / 2, side / 2)
        p.rotate(-8)
        p.translate(-box.center())
        p.setPen(QPen(QColor(20, 10, 5), stroke, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        p.fillPath(path, QColor(255, 225, 40))
        p.end()
        return QPixmap.fromImage(img)

    # ------------------------------------------------------------ painting

    def paintEvent(self, event):
        """Blit the cached layers: bubble, GIF card, counter, CTAR!."""
        p = QPainter(self)
        now = time.monotonic()
        gr = self.gif_rect()
        if self.working and (now - self.shake_t0) * 1000 < SHAKE_MS:
            gr.translate(random.randint(-3, 3), random.randint(-2, 2))
        if self.frames:
            p.drawPixmap(gr.left() - CARD_PAD, gr.top() - CARD_PAD, self.frames[self.frame_index])
        if self.settings["show_bubble"] and self.bubble_text:
            if self.bubble_pix is None:
                self.bubble_pix = self.render_bubble()
            p.drawPixmap(0, 0, self.bubble_pix)
        if self.settings["show_counter"]:
            self.paint_counter(p, gr)
        age_ms = (now - self.ono_t0) * 1000
        if self.working and self.settings["show_ono"] and self.ono_text and age_ms < ONO_MS:
            self.paint_ono(p, gr, age_ms / ONO_MS)
        p.end()

    def paint_counter(self, p, gr):
        """Counter badge in the bottom-right of the GIF card."""
        text = phrases.ui_text(self.settings["language"], "counter_label", n=self.stats.data["today"])
        if text != self.counter_key:
            self.counter_key = text
            self.counter_pix = self.render_counter(text)
        size = self.counter_pix.deviceIndependentSize()
        p.drawPixmap(QPointF(gr.right() - size.width() - 8, gr.bottom() - size.height() - 8), self.counter_pix)

    def paint_ono(self, p, gr, t):
        """Popping, fading CTAR! near the robot (scaled + faded cached pixmap)."""
        if self.ono_pix is None:
            self.ono_pix = self.render_ono(gr)
        pop = (ONO_POP - 0.35 * min(1.0, t * 3)) / ONO_POP
        size = self.ono_pix.deviceIndependentSize()
        w, h = size.width() * pop, size.height() * pop
        cx = gr.left() + gr.width() * 0.62
        cy = gr.top() + gr.height() * 0.2
        p.save()
        p.setOpacity(1.0 - max(0.0, t - 0.55) / 0.45)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        p.drawPixmap(QRectF(cx - w / 2, cy - h / 2, w, h), self.ono_pix, QRectF(self.ono_pix.rect()))
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
            self.schedule_frame()
