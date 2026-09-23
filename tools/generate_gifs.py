"""Generate the 5 original whipping GIF animations (all art is drawn with code)."""
import json
import math
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "pecut_ai" / "assets" / "gifs"
ICON_PATH = ROOT / "pecut_ai" / "assets" / "icon.png"
PREVIEW_DIR = ROOT / "tools" / "previews"

BASE_W, BASE_H = 240, 180
OUT_W, OUT_H = 360, 270
SUPERSAMPLE = 3
FRAME_MS = 45
CRACK_MS = 130
AFTER_CRACK_MS = 80
GROUND_Y = 150
SHOULDER = (66, 84)
UPPER_ARM = 18
FOREARM = 17
HANDLE_LEN = 10

# Keyframes: (upper_arm_deg, forearm_deg, whip_ctrl, whip_tip, robot_flinch)
KEYFRAMES = [
    (-120, -150, (20, 40), (10, 110), 0.0),
    (-130, -170, (10, 30), (0, 80), 0.0),
    (-110, -120, (30, 10), (0, 30), 0.0),
    (-80, -60, (90, 0), (40, 0), 0.0),
    (-40, -20, (150, 20), (110, 5), 0.0),
    (-15, 0, (170, 50), (185, 40), 0.1),
    (0, 10, (140, 90), (205, 96), 1.0),
    (10, 20, (150, 115), (200, 120), 0.8),
    (20, 40, (130, 140), (185, 148), 0.5),
    (20, 50, (120, 150), (165, 150), 0.3),
    (-30, -60, (90, 140), (130, 150), 0.1),
    (-90, -120, (40, 120), (70, 150), 0.0),
]
CRACK_KEY = 6


def lerp(a, b, t):
    """Linear interpolation between two numbers."""
    return a + (b - a) * t


def lerp_pt(p, q, t):
    """Linear interpolation between two points."""
    return (lerp(p[0], q[0], t), lerp(p[1], q[1], t))


def direction(deg, length):
    """Vector of given length pointing at deg (screen coords, y down)."""
    rad = math.radians(deg)
    return (math.cos(rad) * length, math.sin(rad) * length)


def add(p, v):
    """Add a vector to a point."""
    return (p[0] + v[0], p[1] + v[1])


def bezier(p0, p1, p2, n):
    """Sample a quadratic bezier curve into n+1 points."""
    pts = []
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]
        pts.append((x, y))
    return pts


def build_frames():
    """Expand keyframes into a smooth frame list (keyframe + midpoint)."""
    frames = []
    n = len(KEYFRAMES)
    for i in range(n):
        k0 = KEYFRAMES[i]
        k1 = KEYFRAMES[(i + 1) % n]
        for t in (0.0, 0.5):
            a1 = lerp(k0[0], k1[0], t)
            a2 = lerp(k0[1], k1[1], t)
            ctrl = lerp_pt(k0[2], k1[2], t)
            tip = lerp_pt(k0[3], k1[3], t)
            flinch = k0[4] if t == 0.0 else lerp(k0[4], k1[4], t) * 0.8
            frames.append(make_pose(a1, a2, ctrl, tip, flinch, i * 2 + (1 if t else 0)))
    return frames


def make_pose(a1, a2, ctrl, tip, flinch, index):
    """Compute all joint positions for one frame."""
    elbow = add(SHOULDER, direction(a1, UPPER_ARM))
    hand = add(elbow, direction(a2, FOREARM))
    handle_end = add(hand, direction(a2, HANDLE_LEN))
    whip = bezier(handle_end, ctrl, tip, 26)
    return {
        "index": index,
        "elbow": elbow,
        "hand": hand,
        "handle_end": handle_end,
        "whip": whip,
        "tip": tip,
        "flinch": flinch,
        "crack": index == CRACK_KEY * 2,
        "after_crack": index == CRACK_KEY * 2 + 1,
    }


# ---------------------------------------------------------------- painters


class Painter:
    """Anti-aliased painter; all coordinates are in 240x180 base space."""

    def __init__(self, bg, scale=None):
        self.s = scale if scale is not None else (OUT_W / BASE_W) * SUPERSAMPLE
        size = (int(round(BASE_W * self.s)), int(round(BASE_H * self.s)))
        self.img = Image.new("RGB", size, bg)
        self.d = ImageDraw.Draw(self.img, "RGBA")
        self.glow_enabled = False

    def pt(self, p):
        """Convert a base point into image pixels."""
        return (p[0] * self.s, p[1] * self.s)

    def w(self, width):
        """Convert a base line width into image pixels."""
        return max(1, int(round(width * self.s)))

    def line(self, pts, color, width, caps=True):
        """Draw a polyline with round joints and caps."""
        ps = [self.pt(p) for p in pts]
        wd = self.w(width)
        self.d.line(ps, fill=color, width=wd, joint="curve")
        if caps and wd > 2:
            r = wd / 2.0
            for q in (ps[0], ps[-1]):
                self.d.ellipse([q[0] - r, q[1] - r, q[0] + r, q[1] + r], fill=color)

    def ellipse(self, cx, cy, rx, ry, fill=None, outline=None, width=1):
        """Draw an ellipse centered at (cx, cy)."""
        box = [self.pt((cx - rx, cy - ry)), self.pt((cx + rx, cy + ry))]
        self.d.ellipse([box[0][0], box[0][1], box[1][0], box[1][1]], fill=fill,
                       outline=outline, width=self.w(width) if outline else 0)

    def polygon(self, pts, fill=None, outline=None, width=1):
        """Draw a filled polygon with an optional outline."""
        if fill is not None:
            self.d.polygon([self.pt(p) for p in pts], fill=fill)
        if outline is not None:
            self.line(list(pts) + [pts[0]], outline, width)

    def rect(self, x0, y0, x1, y1, fill=None, outline=None, width=1, radius=0):
        """Draw an axis aligned (optionally rounded) rectangle."""
        a = self.pt((x0, y0))
        b = self.pt((x1, y1))
        self.d.rounded_rectangle([a[0], a[1], b[0], b[1]], radius=radius * self.s,
                                 fill=fill, outline=outline,
                                 width=self.w(width) if outline else 0)

    def finish(self):
        """Return the final frame at output resolution."""
        return self.img.resize((OUT_W, OUT_H), Image.LANCZOS)


class PixelPainter(Painter):
    """Chunky pixel-art painter: renders tiny with no AA, then upscales."""

    def __init__(self, bg):
        super().__init__(bg, scale=0.5)

    def line(self, pts, color, width, caps=False):
        """Draw a crisp pixel line without round caps."""
        ps = [(int(round(p[0] * self.s)), int(round(p[1] * self.s))) for p in pts]
        self.d.line(ps, fill=color, width=max(1, int(round(width * self.s))))

    def finish(self):
        """Upscale with nearest neighbour to keep the pixels sharp."""
        return self.img.resize((OUT_W, OUT_H), Image.NEAREST)


class DoodlePainter(Painter):
    """Hand drawn painter: jittery, double-stroked pencil lines that boil."""

    def __init__(self, bg, seed):
        super().__init__(bg)
        self.rng = random.Random(seed)

    def jitter(self, p, amount=0.9):
        """Offset a point randomly to fake a shaky hand."""
        return (p[0] + self.rng.uniform(-amount, amount), p[1] + self.rng.uniform(-amount, amount))

    def subdivide(self, pts, step=7.0):
        """Split long segments so the wobble follows the whole stroke."""
        out = [pts[0]]
        for a, b in zip(pts, pts[1:]):
            dist = math.hypot(b[0] - a[0], b[1] - a[1])
            n = max(1, int(dist / step))
            for i in range(1, n + 1):
                out.append(lerp_pt(a, b, i / n))
        return out

    def line(self, pts, color, width, caps=True):
        """Draw two slightly different pencil passes of the same stroke."""
        dense = self.subdivide(pts)
        for _ in range(2):
            super().line([self.jitter(p) for p in dense], color, width * 0.75, caps)

    def ellipse(self, cx, cy, rx, ry, fill=None, outline=None, width=1):
        """Draw a sketchy ellipse as a wobbly loop."""
        pts = []
        for i in range(24):
            ang = 2 * math.pi * i / 24
            pts.append((cx + math.cos(ang) * rx, cy + math.sin(ang) * ry))
        self.polygon(pts, fill, outline, width)

    def polygon(self, pts, fill=None, outline=None, width=1):
        """Draw a sketchy polygon whose fill is slightly offset like marker."""
        if fill is not None:
            off = self.jitter((1.2, 1.2), 0.8)
            self.d.polygon([self.pt((p[0] + off[0], p[1] + off[1])) for p in pts], fill=fill)
        if outline is not None:
            self.line(list(pts) + [pts[0]], outline, width)

    def rect(self, x0, y0, x1, y1, fill=None, outline=None, width=1, radius=0):
        """Draw a sketchy rectangle."""
        self.polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], fill, outline, width)


class NeonPainter(Painter):
    """Synthwave painter: every stroke also lands on a blurred glow layer."""

    def __init__(self, bg):
        super().__init__(bg)
        self.glow = Image.new("RGB", self.img.size, (0, 0, 0))
        self.gd = ImageDraw.Draw(self.glow)

    def line(self, pts, color, width, caps=True):
        """Draw a bright core line plus a wide glow stroke."""
        if self.glow_enabled:
            ps = [self.pt(p) for p in pts]
            self.gd.line(ps, fill=color[:3], width=self.w(width * 3.2), joint="curve")
        super().line(pts, color, width, caps)
        if self.glow_enabled and width >= 1.5:
            super().line(pts, (255, 255, 255, 170), width * 0.35, caps)

    def ellipse(self, cx, cy, rx, ry, fill=None, outline=None, width=1):
        """Draw ellipse fill then glowing outline."""
        super().ellipse(cx, cy, rx, ry, fill=fill)
        if outline is not None:
            pts = [(cx + math.cos(2 * math.pi * i / 32) * rx, cy + math.sin(2 * math.pi * i / 32) * ry)
                   for i in range(33)]
            self.line(pts, outline, width, caps=False)

    def rect(self, x0, y0, x1, y1, fill=None, outline=None, width=1, radius=0):
        """Draw rect fill then glowing outline."""
        super().rect(x0, y0, x1, y1, fill=fill, radius=radius)
        if outline is not None:
            self.polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], None, outline, width)

    def finish(self):
        """Blur the glow layer and screen it on top of the frame."""
        blurred = self.glow.filter(ImageFilter.GaussianBlur(4 * self.s / SUPERSAMPLE * 1.5))
        combined = ImageChops.screen(self.img, blurred)
        combined = ImageChops.screen(combined, blurred.filter(ImageFilter.GaussianBlur(3 * self.s)))
        return combined.resize((OUT_W, OUT_H), Image.LANCZOS)


# ---------------------------------------------------------------- styles

BASE_STYLE = {
    "stick": False,
    "ow": 1.4,
    "shape_w": 1.4,
    "outline": (40, 34, 50),
    "robot_outline": None,
    "skin": (247, 196, 150),
    "shirt": (46, 134, 222),
    "pants": (52, 58, 94),
    "hat": (139, 90, 43),
    "whip": (101, 62, 30),
    "handle": (60, 36, 20),
    "robot": (190, 200, 215),
    "robot_dark": (110, 120, 140),
    "harness": (243, 112, 33),
    "buckle": (255, 205, 60),
    "laptop": (70, 72, 86),
    "screen_bg": (25, 30, 45),
    "code": (120, 230, 160),
    "eye": (80, 230, 255),
    "sweat": (120, 200, 255),
    "star": (255, 235, 90),
    "star2": (255, 120, 40),
    "desk": (170, 120, 80),
    "trail": (255, 255, 255, 110),
    "impact_scale": 1.0,
}


def style(**overrides):
    """Build a style dict from the base style plus overrides."""
    st = dict(BASE_STYLE)
    st.update(overrides)
    if st["robot_outline"] is None:
        st["robot_outline"] = st["outline"]
    return st


STYLES = {
    "pixel": style(
        ow=1.0, shape_w=1.0, outline=(20, 16, 32), skin=(255, 204, 153), shirt=(200, 40, 40),
        pants=(40, 60, 140), hat=(120, 70, 30), whip=(90, 50, 20), handle=(50, 30, 10),
        robot=(170, 180, 195), robot_dark=(90, 100, 115), harness=(230, 120, 20),
        buckle=(250, 210, 60), laptop=(60, 60, 70), screen_bg=(10, 30, 20), code=(40, 220, 120),
        eye=(40, 220, 255), desk=(150, 90, 40), trail=(255, 255, 255, 90),
    ),
    "doodle": style(
        stick=True, ow=0, shape_w=1.6, outline=(35, 35, 45), skin=(250, 247, 238),
        shirt=(35, 35, 45), pants=(35, 35, 45), hat=(250, 247, 238), whip=(35, 35, 45),
        handle=(35, 35, 45), robot=(250, 247, 238), robot_dark=(35, 35, 45),
        harness=(210, 50, 50), buckle=(250, 247, 238), laptop=(250, 247, 238),
        screen_bg=(250, 247, 238), code=(90, 110, 200), eye=(35, 35, 45), sweat=(90, 140, 230),
        star=(255, 225, 90), star2=(35, 35, 45), desk=(250, 247, 238), trail=(35, 35, 45, 50),
    ),
    "cartoon": style(),
    "neon": style(
        ow=0, shape_w=1.5, outline=(0, 240, 255), robot_outline=(255, 60, 200),
        skin=(22, 10, 42), shirt=(0, 240, 255), pants=(0, 200, 255), hat=(22, 10, 42),
        whip=(255, 230, 0), handle=(255, 180, 0), robot=(22, 10, 42), robot_dark=(255, 60, 200),
        harness=(255, 140, 0), buckle=(255, 230, 0), laptop=(22, 10, 42), screen_bg=(10, 5, 25),
        code=(60, 255, 140), eye=(255, 255, 255), sweat=(0, 240, 255), star=(255, 255, 160),
        star2=(255, 60, 200), desk=(22, 10, 42), trail=(255, 230, 0, 70),
    ),
    "comic": style(
        ow=1.8, shape_w=1.8, outline=(15, 15, 20), skin=(255, 224, 189), shirt=(250, 250, 250),
        pants=(30, 30, 35), hat=(30, 30, 35), whip=(30, 20, 10), handle=(15, 15, 20),
        robot=(235, 235, 235), robot_dark=(80, 80, 85), harness=(220, 30, 40),
        buckle=(255, 210, 0), laptop=(40, 40, 45), screen_bg=(40, 40, 45), code=(250, 250, 250),
        eye=(15, 15, 20), sweat=(120, 190, 255), star=(255, 230, 0), star2=(220, 30, 40),
        desk=(200, 200, 200), trail=(15, 15, 20, 60), impact_scale=1.5,
    ),
}

STYLE_META = {
    "pixel": {"name_id": "Pixel Art 8-bit", "name_en": "8-bit Pixel Art", "bg": (92, 148, 252)},
    "doodle": {"name_id": "Coretan Buku Tulis", "name_en": "Notebook Doodle", "bg": (250, 247, 238)},
    "cartoon": {"name_id": "Kartun Flat", "name_en": "Flat Cartoon", "bg": (143, 211, 255)},
    "neon": {"name_id": "Neon Synthwave", "name_en": "Neon Synthwave", "bg": (20, 10, 42)},
    "comic": {"name_id": "Komik Manga", "name_en": "Manga Comic", "bg": (255, 246, 216)},
}


# ---------------------------------------------------------------- backgrounds


def bg_pixel(p, pose):
    """Sky, sun, drifting clouds and a dirt road in pixel art."""
    p.rect(0, 0, BASE_W, GROUND_Y, fill=(92, 148, 252))
    p.rect(14, 12, 34, 32, fill=(255, 220, 80))
    shift = (pose["index"] * 2) % 280
    for cx, cy in ((60, 28), (170, 18)):
        x = (cx + shift) % 280 - 30
        for dx, dy, w, h in ((0, 4, 30, 8), (6, 0, 16, 6), (16, -2, 10, 6)):
            p.rect(x + dx, cy + dy, x + dx + w, cy + dy + h, fill=(255, 255, 255))
    p.rect(0, GROUND_Y, BASE_W, GROUND_Y + 6, fill=(0, 168, 68))
    p.rect(0, GROUND_Y + 6, BASE_W, BASE_H, fill=(136, 84, 40))
    for x in range(0, BASE_W, 12):
        p.rect(x, GROUND_Y + 12, x + 6, GROUND_Y + 14, fill=(100, 60, 30))


def bg_doodle(p, pose):
    """Ruled notebook paper with a margin line and a pencil ground."""
    was = p.glow_enabled
    for y in range(22, BASE_H, 12):
        Painter.line(p, [(0, y), (BASE_W, y)], (170, 200, 235), 0.6, caps=False)
    Painter.line(p, [(20, 0), (20, BASE_H)], (235, 120, 120), 0.8, caps=False)
    p.glow_enabled = was
    p.line([(8, GROUND_Y + 1), (120, GROUND_Y), (232, GROUND_Y + 1)], (35, 35, 45), 1.4)
    for x in (30, 95, 150, 215):
        p.line([(x, GROUND_Y + 6), (x + 6, GROUND_Y + 6)], (35, 35, 45), 0.9)


def bg_cartoon(p, pose):
    """Gradient sky, sun, rolling hills and grass tufts."""
    for y in range(GROUND_Y):
        t = y / GROUND_Y
        col = (int(lerp(110, 225, t)), int(lerp(195, 245, t)), int(lerp(255, 255, t)))
        p.rect(0, y, BASE_W, y + 1.2, fill=col)
    p.ellipse(208, 30, 22, 22, fill=(255, 245, 180, 120))
    p.ellipse(208, 30, 15, 15, fill=(255, 225, 90))
    p.ellipse(40, 165, 90, 40, fill=(150, 210, 120))
    p.ellipse(200, 168, 100, 45, fill=(130, 200, 110))
    p.rect(0, GROUND_Y, BASE_W, BASE_H, fill=(110, 190, 90))
    p.rect(0, GROUND_Y, BASE_W, GROUND_Y + 3, fill=(90, 165, 75))
    for x in (20, 105, 128, 225):
        p.polygon([(x, GROUND_Y + 12), (x + 3, GROUND_Y + 5), (x + 6, GROUND_Y + 12)], fill=(80, 150, 65))


def bg_neon(p, pose):
    """Synthwave night: gradient sky, striped sun, scrolling glowing grid."""
    for y in range(GROUND_Y):
        t = y / GROUND_Y
        col = (int(lerp(14, 60, t)), int(lerp(6, 10, t)), int(lerp(36, 70, t)))
        p.rect(0, y, BASE_W, y + 1.2, fill=col)
    for i in range(18):
        t = i / 17
        col = (255, int(lerp(220, 40, t)), int(lerp(80, 160, t)))
        y0 = 88 + i * 3.4
        half = math.sqrt(max(0.0, 44 ** 2 - (y0 + 1.7 - 128) ** 2))
        if i > 7 and i % 2 == 0:
            continue
        p.rect(120 - half, y0, 120 + half, y0 + 3.4, fill=col)
    p.rect(0, GROUND_Y, BASE_W, BASE_H, fill=(18, 4, 30))
    p.glow_enabled = True
    grid = (255, 40, 200)
    offset = (pose["index"] % 6) / 6.0
    for k in range(7):
        y = GROUND_Y + ((k + offset) ** 1.8) * 1.4
        if y < BASE_H:
            p.line([(0, y), (BASE_W, y)], grid, 0.8, caps=False)
    for k in range(-8, 9):
        p.line([(120 + k * 6, GROUND_Y), (120 + k * 40, BASE_H)], grid, 0.8, caps=False)
    p.glow_enabled = False


def bg_comic(p, pose):
    """Cream paper with halftone dots; speed lines and red burst on impact."""
    for gy in range(0, BASE_H + 8, 8):
        for gx in range(0, BASE_W + 8, 8):
            ox = 4 if (gy // 8) % 2 else 0
            r = 0.4 + 1.8 * (gy / BASE_H)
            p.ellipse(gx + ox, gy, r, r, fill=(225, 205, 160))
    if pose["crack"] or pose["after_crack"]:
        tip = pose["tip"]
        rng = random.Random(7 + pose["index"])
        burst = []
        for i in range(28):
            ang = 2 * math.pi * i / 28
            rad = 60 if i % 2 == 0 else 34
            burst.append((tip[0] + math.cos(ang) * rad, tip[1] + math.sin(ang) * rad))
        p.polygon(burst, fill=(235, 60, 50, 150 if pose["crack"] else 80))
        for i in range(40):
            ang = rng.uniform(0, 2 * math.pi)
            r0 = rng.uniform(40, 70)
            r1 = r0 + rng.uniform(60, 160)
            a = (tip[0] + math.cos(ang) * r0, tip[1] + math.sin(ang) * r0)
            b = (tip[0] + math.cos(ang) * r1, tip[1] + math.sin(ang) * r1)
            p.line([a, b], (15, 15, 20, 200), rng.uniform(0.4, 1.4), caps=False)
    p.line([(0, GROUND_Y), (BASE_W, GROUND_Y)], (15, 15, 20), 2.0)


BACKGROUNDS = {
    "pixel": bg_pixel,
    "doodle": bg_doodle,
    "cartoon": bg_cartoon,
    "neon": bg_neon,
    "comic": bg_comic,
}


# ---------------------------------------------------------------- scene parts


def limb(p, st, pts, color, width):
    """Draw a limb: outline pass then colour pass (or a stick line)."""
    if st["stick"]:
        p.line(pts, st["outline"], 2.4)
        return
    if st["ow"]:
        p.line(pts, st["outline"], width + 2 * st["ow"])
    p.line(pts, color, width)


def draw_desk_and_laptop(p, st, pose):
    """Desk with a laptop showing code that scrolls every frame."""
    ro = st["robot_outline"]
    p.rect(136, 124, 180, 128, fill=st["desk"], outline=ro, width=st["shape_w"])
    p.line([(140, 128), (140, GROUND_Y)], ro, 2)
    p.line([(176, 128), (176, GROUND_Y)], ro, 2)
    p.rect(146, 100, 172, 123, fill=st["laptop"], outline=ro, width=st["shape_w"], radius=1.5)
    p.rect(148.5, 102.5, 169.5, 120, fill=st["screen_bg"])
    rng = random.Random(pose["index"] // 2)
    for row in range(4):
        y = 105 + row * 4
        length = rng.uniform(5, 17)
        p.line([(150.5, y), (150.5 + length, y)], st["code"], 1.2, caps=False)
    p.rect(140, 122, 178, 125, fill=st["laptop"], outline=ro, width=st["shape_w"], radius=1)


def draw_robot(p, st, pose):
    """The AI agent: a robot in a harness, typing and flinching."""
    ro = st["robot_outline"]
    fl = pose["flinch"]
    rx = 194 + 6 * fl
    sw = st["shape_w"]
    for lx in (-11, 5):
        p.rect(rx + lx, 138, rx + lx + 6, GROUND_Y, fill=st["robot_dark"], outline=ro, width=sw)
    typing = 3 if pose["index"] % 2 else 0
    back_arm = [(rx - 6, 104), (rx - 18, 114), (164 + typing, 120)]
    limb(p, dict(st, outline=ro), back_arm, st["robot_dark"], 4)
    p.rect(rx - 16, 96, rx + 16, 138, fill=st["robot"], outline=ro, width=sw, radius=4)
    p.line([(rx - 14, 98), (rx + 14, 134)], st["harness"], 3.2)
    p.line([(rx + 14, 98), (rx - 14, 134)], st["harness"], 3.2)
    p.rect(rx - 16, 127, rx + 16, 132, fill=st["harness"])
    p.ellipse(rx, 116, 4, 4, fill=None, outline=st["buckle"], width=1.6)
    front_arm = [(rx - 12, 103), (rx - 24, 112), (157 - typing, 121)]
    limb(p, dict(st, outline=ro), front_arm, st["robot_dark"], 4)
    p.rect(rx - 4, 92, rx + 4, 97, fill=st["robot_dark"])
    tilt = 3 * fl
    p.rect(rx - 13 + tilt, 70, rx + 13 + tilt, 93, fill=st["robot"], outline=ro, width=sw, radius=5)
    ant_tip = (rx + tilt + 5 * fl, 61 - 2 * fl)
    p.line([(rx + tilt, 70), ant_tip], ro, 1.6)
    blink = st["star2"] if pose["index"] % 4 < 2 else st["buckle"]
    p.ellipse(ant_tip[0], ant_tip[1], 2.6, 2.6, fill=blink, outline=ro, width=1)
    ex = rx - 8 + tilt
    if fl > 0.45:
        for cx, sgn in ((ex, 1), (ex + 10, -1)):
            p.line([(cx - 2.5 * sgn, 77), (cx + 2.5 * sgn, 80), (cx - 2.5 * sgn, 83)], st["eye"] if st["stick"] else ro, 1.4)
        mouth = [(ex - 2, 88), (ex + 1, 86), (ex + 4, 88), (ex + 7, 86), (ex + 10, 88)]
        p.line(mouth, ro, 1.2)
    else:
        for cx in (ex, ex + 10):
            p.rect(cx - 2, 77.5, cx + 2, 82.5, fill=st["eye"])
        p.line([(ex - 1, 88), (ex + 8, 88)], ro, 1.2)
    if fl > 0.05:
        for dx, dy, sz in ((17, -6, 1.0), (22, 2, 0.75)):
            cx, cy = rx + tilt + dx, 76 + dy - 4 * fl
            drop = [(cx, cy - 4 * sz), (cx + 2.4 * sz, cy + 1 * sz), (cx, cy + 3 * sz), (cx - 2.4 * sz, cy + 1 * sz)]
            p.polygon(drop, fill=st["sweat"], outline=ro, width=0.8)


def draw_person(p, st, pose, back=True):
    """The foreman: hat, mustache, angry eyebrows, whip arm."""
    o = st["outline"]
    sw = st["shape_w"]
    if back:
        limb(p, st, [SHOULDER, (52, 98), (58, 110)], st["shirt"], 6)
        for leg in ([(60, 114), (54, 132), (48, GROUND_Y - 2)], [(60, 114), (68, 132), (74, GROUND_Y - 2)]):
            limb(p, st, leg, st["pants"], 7)
        for fx in (46, 76):
            p.ellipse(fx, GROUND_Y - 2, 5, 2.5, fill=o)
        limb(p, st, [(60, 114), (64, 80)], st["shirt"], 13)
        p.ellipse(64, 67, 11, 11, fill=st["skin"], outline=o, width=sw)
        p.line([(66, 60), (74, 63)], o, 1.8)
        p.ellipse(70, 65.5, 1.6, 1.6, fill=o)
        p.line([(64, 71), (75, 70.5)], o, 2.4)
        if pose["crack"]:
            p.ellipse(71, 74.5, 2.6, 2.0, fill=o)
        p.line([(49, 57), (80, 57)], o, 3.4)
        p.line([(50, 57), (79, 57)], st["hat"], 1.6)
        p.polygon([(55, 57), (57, 44), (72, 44), (75, 57)], fill=st["hat"], outline=o, width=sw)
        return
    limb(p, st, [SHOULDER, pose["elbow"], pose["hand"]], st["shirt"], 6)
    p.ellipse(pose["hand"][0], pose["hand"][1], 3.4, 3.4, fill=st["skin"], outline=o, width=sw * 0.8)


def draw_whip(p, st, pose, prev_pose):
    """Handle, tapered lash, motion trail and the cracker at the tip."""
    if prev_pose is not None and 8 <= pose["index"] <= 13:
        p.line(prev_pose["whip"], st["trail"], 1.4, caps=False)
    p.line([pose["hand"], pose["handle_end"]], st["handle"], 3.6)
    pts = pose["whip"]
    n = len(pts) - 1
    for i in range(n):
        width = 2.8 - 1.9 * (i / n)
        p.line([pts[i], pts[i + 1]], st["whip"], width, caps=True)


def draw_impact(p, st, pose):
    """Star burst at the whip tip on the crack frame."""
    if not (pose["crack"] or pose["after_crack"]):
        return
    k = st["impact_scale"] * (1.0 if pose["crack"] else 0.6)
    tx, ty = pose["tip"]
    star = []
    for i in range(16):
        ang = 2 * math.pi * i / 16 + 0.2
        rad = (15 if i % 2 == 0 else 6) * k
        star.append((tx + math.cos(ang) * rad, ty + math.sin(ang) * rad))
    p.glow_enabled = True
    p.polygon(star, fill=st["star"], outline=st["star2"], width=1.4)
    for ang in (-60, -20, 20, 60):
        a = add(pose["tip"], direction(ang - 180, 19 * k))
        b = add(pose["tip"], direction(ang - 180, 27 * k))
        p.line([a, b], st["star2"], 1.6)
    p.glow_enabled = False


def render_frame(style_id, pose, prev_pose):
    """Render one frame of one style into an RGB image."""
    st = STYLES[style_id]
    bg = STYLE_META[style_id]["bg"]
    if style_id == "pixel":
        p = PixelPainter(bg)
    elif style_id == "doodle":
        p = DoodlePainter(bg, seed=pose["index"] // 2)
    elif style_id == "neon":
        p = NeonPainter(bg)
    else:
        p = Painter(bg)
    BACKGROUNDS[style_id](p, pose)
    p.glow_enabled = style_id == "neon"
    draw_desk_and_laptop(p, st, pose)
    draw_robot(p, st, pose)
    draw_person(p, st, pose, back=True)
    draw_whip(p, st, pose, prev_pose)
    draw_person(p, st, pose, back=False)
    draw_impact(p, st, pose)
    if style_id == "comic":
        p.glow_enabled = False
        p.rect(1.5, 1.5, BASE_W - 1.5, BASE_H - 1.5, outline=(15, 15, 20), width=3)
    return p.finish()


def frame_durations(frames):
    """Per frame durations: normal, long hold on crack, short after."""
    out = []
    for f in frames:
        if f["crack"]:
            out.append(CRACK_MS)
        elif f["after_crack"]:
            out.append(AFTER_CRACK_MS)
        else:
            out.append(FRAME_MS)
    return out


def save_gif(style_id, frames):
    """Render and save one style as a looping GIF plus a preview strip."""
    images = []
    prev = None
    for f in frames:
        images.append(render_frame(style_id, f, prev))
        prev = f
    pal_frames = [im.convert("P", palette=Image.ADAPTIVE, colors=255) for im in images]
    path = OUT_DIR / f"{style_id}.gif"
    pal_frames[0].save(path, save_all=True, append_images=pal_frames[1:],
                       duration=frame_durations(frames), loop=0, disposal=1, optimize=False)
    pick = [0, 4, 8, 11, 12, 16]
    strip = Image.new("RGB", (OUT_W * 3, OUT_H * 2), (0, 0, 0))
    for n, idx in enumerate(pick):
        strip.paste(images[idx], ((n % 3) * OUT_W, (n // 3) * OUT_H))
    strip.save(PREVIEW_DIR / f"{style_id}_preview.png")
    return path


def save_icon(frames):
    """Tray/app icon: a whip crack on an orange disc."""
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([8, 8, size - 8, size - 8], fill=(255, 140, 30, 255), outline=(60, 30, 10, 255), width=10)
    pts = bezier((60, 200), (90, 60), (200, 80), 30)
    for i in range(len(pts) - 1):
        wd = int(22 - 16 * i / len(pts))
        d.line([pts[i], pts[i + 1]], fill=(60, 30, 10, 255), width=wd)
    d.line([(40, 225), (68, 190)], fill=(30, 15, 5, 255), width=26)
    star = []
    for i in range(12):
        ang = 2 * math.pi * i / 12
        rad = 40 if i % 2 == 0 else 16
        star.append((200 + math.cos(ang) * rad, 80 + math.sin(ang) * rad))
    d.polygon(star, fill=(255, 240, 90, 255), outline=(60, 30, 10, 255))
    img.save(ICON_PATH)


def main():
    """Generate all GIFs, the manifest and the icon."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    frames = build_frames()
    crack_idx = [f["index"] for f in frames if f["crack"]]
    manifest = {"order": list(STYLES.keys()), "styles": {}}
    for style_id in STYLES:
        path = save_gif(style_id, frames)
        meta = STYLE_META[style_id]
        manifest["styles"][style_id] = {
            "file": path.name,
            "name_id": meta["name_id"],
            "name_en": meta["name_en"],
            "crack_frames": crack_idx,
            "frame_count": len(frames),
            "width": OUT_W,
            "height": OUT_H,
            "pixelated": style_id == "pixel",
        }
        print("saved", path.name, path.stat().st_size // 1024, "KB")
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    save_icon(frames)
    print("saved manifest + icon")


if __name__ == "__main__":
    main()
