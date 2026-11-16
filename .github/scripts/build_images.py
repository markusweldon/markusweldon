#!/usr/bin/env python3
"""Build the README's images in the markusweldon.com style.

Writes, under images/:
  header.svg                  the hero: name, typing terminal, tagline,
                              location, starfield, treeline and neon grid
  card-<repo>.svg             the Featured Work project cards
  btn-<name>.svg              the pill buttons (contact links, OWASP CTA)
  synthwave-divider*.svg      the section dividers (dark and light)

Colours and fonts are the site's design tokens (personal-site:
src/app/globals.css and components). All text is drawn as SVG paths,
because GitHub shows README SVGs as images and an image cannot load web
fonts; outlining keeps every image identical for every visitor.

Usage:
    pip install fonttools brotli
    npm pack @fontsource/orbitron@5.0.19 geist@1.3.1
    (extract both tarballs into one folder, then)
    python3 .github/scripts/build_images.py <folder-with-the-extracted-packages>
"""

import math
import random
import sys
from html import escape
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[2]
IMAGES = ROOT / "images"

# ── markusweldon.com design tokens ─────────────────────────────────────────
BG = "#0d0015"
SURFACE = "#130022"
PINK = "#f92aad"
CYAN = "#36f9f6"
PURPLE = "#b01fff"
VIOLET = "#7b2fff"
LAVENDER = "#c792ea"
TEXT = "#f0e6ff"
TEXT_2 = "#a78bca"
PROMPT_COL = "#7b5ea7"

# Lucide icons (ISC licence), 24x24, stroked. The site uses the same set.
ICONS = {
    "github": '<path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4"/><path d="M9 18c-4.51 2-5-2-7-2"/>',
    "linkedin": '<path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect width="4" height="12" x="2" y="9"/><circle cx="4" cy="4" r="2"/>',
    "globe": '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>',
    "arrow-right": '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    "map-pin": '<path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"/><circle cx="12" cy="10" r="3"/>',
    "play": '<polygon points="6 3 20 12 6 21 6 3"/>',
    "shield": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
    "code": '<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>',
    "building-2": '<path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/><path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/><path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2"/><path d="M10 6h4"/><path d="M10 10h4"/><path d="M10 14h4"/><path d="M10 18h4"/>',
}

# GitHub's mark (Octicons, MIT), 16x16, filled; the site's project cards use it.
OCTOCAT = "M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"


def fmt(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".")


def icon(name: str, x: float, y: float, size: float, colour: str, width: float = 2) -> str:
    s = size / 24
    return (f'<g transform="translate({fmt(x)} {fmt(y)}) scale({s:.4f})" fill="none" stroke="{colour}" '
            f'stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</g>')


class Font:
    def __init__(self, path: Path):
        self.font = TTFont(path)
        self.glyphs = self.font.getGlyphSet()
        self.cmap = self.font.getBestCmap()
        self.upm = self.font["head"].unitsPerEm

    def advance(self, char: str, size: float) -> float:
        return self.glyphs[self.cmap[ord(char)]].width * size / self.upm

    def width(self, text: str, size: float, tracking: float = 0.0) -> float:
        return sum(self.advance(c, size) + tracking for c in text) - tracking

    def path(self, text: str, size: float, x: float, baseline: float,
             tracking: float = 0.0) -> tuple[str, float]:
        """Outline `text` starting at x; return (path data, advance width)."""
        scale = size / self.upm
        pen = SVGPathPen(self.glyphs, ntos=fmt)
        start = x
        for char in text:
            name = self.cmap[ord(char)]
            self.glyphs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, x, baseline)))
            x += self.glyphs[name].width * scale + tracking
        return pen.getCommands(), x - tracking - start

    def wrap(self, text: str, size: float, max_width: float) -> list[str]:
        lines, line = [], ""
        for word in text.split():
            trial = f"{line} {word}".strip()
            if line and self.width(trial, size) > max_width:
                lines.append(line)
                line = word
            else:
                line = trial
        return lines + [line]


class Fonts:
    def __init__(self, font_dir: Path):
        def load(filename: str) -> Font:
            hits = sorted(font_dir.rglob(filename))
            if not hits:
                sys.exit(f"Font not found: {filename} under {font_dir}")
            return Font(hits[0])
        self.display = load("orbitron-latin-900-normal.woff2")
        self.display_bold = load("orbitron-latin-700-normal.woff2")
        self.sans = load("Geist-Regular.woff2")
        self.sans_medium = load("Geist-Medium.woff2")
        self.sans_semibold = load("Geist-SemiBold.woff2")
        self.mono = load("GeistMono-Regular.woff2")
        self.mono_semibold = load("GeistMono-SemiBold.woff2")


def svg(width: float, height: float, body: str, title: str = "") -> str:
    t = f"<title>{escape(title)}</title>\n" if title else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{fmt(width)}" height="{fmt(height)}" '
            f'viewBox="0 0 {fmt(width)} {fmt(height)}">\n{t}{body}\n</svg>\n')


# ══ Header ═════════════════════════════════════════════════════════════════

NAME = ("MARKUS", "WELDON")
TAGLINE = "Helping enterprises adopt AI-assisted development securely."
LOCATION = ("Brit builder", "Lake Oswego, Oregon")
PROMPT = "~/markusweldon "
LINES = [
    "Principal Solutions Engineer",
    "Securing Agentic AI Development",
    "AppSec · Cloud · Cybersecurity",
    "Enterprise GTM · Technical Pre-Sales",
    "Ship Faster With AI, Securely",
]

HW, HH = 1000, 549
HORIZON = 443
LEFT = 56

# Site typewriter timing (Hero.tsx): 55 ms per typed character, 1.8 s hold,
# 32 ms per deleted character, cursor toggles every 530 ms.
TYPE_MS, HOLD_MS, DELETE_MS, BLINK_MS = 55, 1800, 32, 530


def inside(x: float, y: float, rects) -> bool:
    return any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in rects)


def stars(avoid=()) -> str:
    """The site's deterministic starfield (Hero.tsx STARS_REG / STARS_BRIGHT),
    leaving out any star that would land on the name or the text under it."""
    out = []
    for i in range(48):
        x, y = (i * 137.508) % 100, (i * 97.314) % 50
        size = 3 if i % 5 == 0 else 2 if i % 3 == 0 else 1.5
        op = 0.45 + ((i * 71) % 37) / 100
        dur, delay = 4 + (i % 9) * 0.4, (i * 0.47) % 5.5
        if inside(x * HW / 100, y * HORIZON / 100, avoid):
            continue
        out.append(f'<g opacity="{op:.2f}"><circle class="star" cx="{fmt(x * HW / 100)}" '
                   f'cy="{fmt(y * HORIZON / 100)}" r="{size / 2}" '
                   f'style="animation-duration:{dur:.1f}s;animation-delay:{delay:.1f}s"/></g>')
    for i in range(6):
        x, y = (i * 173.12 + 17) % 100, (i * 61.7 + 8) % 45
        size = 3.5 + (i % 3)
        op = 0.75 + ((i * 31) % 20) / 100
        dur, delay = 5 + (i % 4) * 0.7, (i * 1.3) % 4
        if inside(x * HW / 100, y * HORIZON / 100, avoid):
            continue
        out.append(f'<g opacity="{op:.2f}"><circle class="star" cx="{fmt(x * HW / 100)}" '
                   f'cy="{fmt(y * HORIZON / 100)}" r="{size / 2}" filter="url(#starGlow)" '
                   f'style="animation-duration:{dur:.1f}s;animation-delay:{delay:.1f}s"/></g>')
    return "\n".join(out)


HEADER_SKYLINE = True  # Portland and Mt Hood in neon, behind the pines
CITY = ["#36f9f6", "#ff6ec7", "#ffd6f5", "#b98cff"]  # lit window colours


def skyline(avoid=(), tallest: float = 120, spread: float = 0.24) -> str:
    """A neon city on the horizon, behind the pines, like the Stats card's
    calendar city seen from the street: dark violet towers with pink rims and
    lit windows, tallest near the sun glow on the right, a few cyan towers with
    beacons. No tower rises into the text above it."""
    rng = random.Random(1984)
    back, front = [], []

    def ceiling(x0, x1):
        # Keep clear of the text, with extra room past the ends of its lines.
        tops = [y1 + 16 for rx0, ry0, rx1, y1 in avoid if x0 < rx1 + 50 and x1 > rx0 - 10]
        return max(tops) if tops else 0

    def envelope(x):
        return 0.3 + 0.7 * math.exp(-((x / HW - 0.74) / spread) ** 2)

    # Back layer: wide, dim blocks for depth.
    x = -10
    while x < HW:
        w = rng.uniform(26, 50)
        h = tallest * 0.75 * envelope(x) * rng.uniform(0.5, 1.0)
        top = max(HORIZON - h, ceiling(x, x + w))
        if HORIZON - top > 6:
            back.append(f'<rect x="{fmt(x)}" y="{fmt(top)}" width="{fmt(w)}" height="{fmt(HORIZON - top)}"/>')
        x += w + rng.uniform(-6, 2)

    # Front layer: towers with rims and windows. The two tallest become cyan
    # "peak" towers with beacons, like the peak days in the Stats calendar.
    towers, x = [], -4
    while x < HW:
        w = rng.uniform(14, 30)
        h = tallest * envelope(x + w / 2) * rng.uniform(0.35, 1.0)
        top = max(HORIZON - h, ceiling(x, x + w))
        if HORIZON - top >= 10:
            towers.append((x, w, top, rng.random()))
        x += w + rng.uniform(1, 6)
    heroes = set(sorted(range(len(towers)), key=lambda i: towers[i][2])[:2])
    for i, (x, w, top, seed) in enumerate(towers):
        wrng = random.Random(seed)
        hero = i in heroes
        rim = CYAN if hero else PINK
        front.append(f'<rect x="{fmt(x)}" y="{fmt(top)}" width="{fmt(w)}" height="{fmt(HORIZON - top)}" fill="url(#cityFill)"/>'
                     f'<rect x="{fmt(x)}" y="{fmt(top)}" width="{fmt(w)}" height="1.2" fill="{rim}" fill-opacity="{0.9 if hero else 0.55}"/>')
        if hero:
            front.append(f'<rect x="{fmt(x + w / 2 - 0.5)}" y="{fmt(top - 12)}" width="1" height="12" fill="{CYAN}" fill-opacity="0.7"/>'
                         f'<circle cx="{fmt(x + w / 2)}" cy="{fmt(top - 13)}" r="1.8" fill="{CYAN}" filter="url(#starGlow)"/>')
        wy = top + 6
        while wy < HORIZON - 8:
            wx = x + 3.5
            while wx < x + w - 4:
                if wrng.random() < (0.42 if hero else 0.3):
                    col = CYAN if hero and wrng.random() < 0.7 else wrng.choice(CITY)
                    blink = ' class="wb" style="animation-delay:-%.1fs"' % wrng.uniform(0, 7) if wrng.random() < 0.06 else ""
                    front.append(f'<rect x="{fmt(wx)}" y="{fmt(wy)}" width="2.2" height="3" fill="{col}" fill-opacity="0.8"{blink}/>')
                wx += 5.5
            wy += 7
    return (f'<g fill="#1c0a33" opacity="0.7">{"".join(back)}</g>\n'
            f'<g>{"".join(front)}</g>')


def skyline_neon(avoid=(), tallest: float = 150, centre: float = 0.82, spread: float = 0.2) -> str:
    """An outrun-style city: one dark silhouette backlit by a pink haze, its
    whole rooftop line traced in a glowing pink-to-cyan neon line, with
    spires, stepped tops and antennas, and only a few lit window strips."""
    rng = random.Random(77)
    width = int(HW) + 1
    prof = [0.0] * width  # skyline height above the horizon at each x

    def ceiling(x0, x1):
        tops = [HORIZON - (y1 + 16) for rx0, ry0, rx1, y1 in avoid if x0 < rx1 + 50 and x1 > rx0 - 10]
        return min(tops) if tops else tallest * 2

    def envelope(x):
        return 0.12 + 0.88 * math.exp(-((x / HW - centre) / spread) ** 2)

    strips, antennas = [], []
    x = 0.0
    while x < HW:
        w = rng.uniform(12, 34)
        h = min(tallest * envelope(x + w / 2) * rng.uniform(0.45, 1.0), ceiling(x, x + w))
        if h < 4:
            x += w
            continue
        if h < 22:  # no stubby buildings: the city fades out instead
            x += w + rng.uniform(2, 8)
            continue
        kind = rng.random()
        for px in range(max(0, int(x)), min(width, int(x + w))):
            t = (px - x) / w
            hh = h
            if kind < 0.3 and h > tallest * 0.45:       # crown: two setbacks
                hh = h if 0.38 < t < 0.62 else h * 0.9 if 0.2 < t < 0.8 else h * 0.78
            elif kind < 0.55:                            # one setback
                hh = h if 0.25 < t < 0.75 else h * 0.84
            prof[px] = max(prof[px], hh)
        if h > tallest * 0.55 and rng.random() < 0.45:
            antennas.append((x + w * rng.uniform(0.3, 0.7), h))
        if h > tallest * 0.4 and rng.random() < 0.5:   # a lit strip up the face
            sx = x + w * rng.uniform(0.25, 0.75)
            strips.append((sx, h * rng.uniform(0.35, 0.8), rng.choice([CYAN, PINK, "#b98cff"])))
        x += w + rng.uniform(-4, 3)

    # Trace the rooftop line across the city, keeping only the corners.
    lit = [px for px in range(width) if prof[px] > 0]
    if not lit:
        return ""
    x0, x1 = lit[0], lit[-1] + 1
    pts = [(x0, HORIZON)]
    for px in range(x0, x1):
        y = HORIZON - prof[px]
        if pts[-1][1] != y:
            pts.append((px, pts[-1][1]))
            pts.append((px, y))
    pts.append((x1, pts[-1][1]))
    pts.append((x1, HORIZON))
    outline = " ".join(f"{fmt(px)},{fmt(py)}" for px, py in pts[1:-1])
    shape = "M" + " L".join(f"{fmt(px)},{fmt(py)}" for px, py in pts) + " Z"
    peak = max(range(width), key=lambda i: prof[i])

    parts = [
        f'<linearGradient id="cityNeon" gradientUnits="userSpaceOnUse" x1="{x0}" y1="0" x2="{x1}" y2="0">'
        f'<stop offset="0" stop-color="{PINK}" stop-opacity="0"/><stop offset="0.2" stop-color="{PINK}"/>'
        f'<stop offset="0.7" stop-color="#ff6ec7"/><stop offset="1" stop-color="{CYAN}"/></linearGradient>',
        f'<ellipse cx="{fmt(peak)}" cy="{HORIZON}" rx="{fmt(HW * 0.3)}" ry="{fmt(tallest * 1.1)}" fill="url(#cityHaze)" filter="url(#blur28)"/>',
        f'<path d="{shape}" fill="url(#citySil)"/>',
    ]
    for sx, sh, col in strips:
        parts.append(f'<rect x="{fmt(sx)}" y="{fmt(HORIZON - sh)}" width="1.4" height="{fmt(sh - 4)}" fill="{col}" '
                     f'fill-opacity="0.55" filter="url(#starGlow)"/>')
    for ax, ah in antennas:
        parts.append(f'<rect x="{fmt(ax - 0.5)}" y="{fmt(HORIZON - ah - 14)}" width="1" height="14" fill="#ff9de2" fill-opacity="0.8"/>'
                     f'<circle class="beacon" cx="{fmt(ax)}" cy="{fmt(HORIZON - ah - 15)}" r="1.6" fill="{PINK}" filter="url(#starGlow)"/>')
    parts.append(f'<polyline points="{outline}" fill="none" stroke="url(#cityNeon)" stroke-width="3" stroke-opacity="0.7" filter="url(#lineGlow)"/>')
    parts.append(f'<polyline points="{outline}" fill="none" stroke="url(#cityNeon)" stroke-width="1.3" stroke-linejoin="round"/>')
    return "\n".join(parts)


# Downtown Portland, left to right, in design units (Wells Fargo Center = 120
# tall): (x, width, height, shape, name).
PORTLAND = [
    (0, 16, 26, "rect", ""), (17, 14, 38, "rect", ""), (32, 12, 52, "spire", "Union Station"),
    (46, 18, 44, "rect", ""), (66, 22, 104, "chamfer", "Big Pink"), (90, 16, 62, "rect", ""),
    (107, 20, 86, "pill", "1000 Broadway"), (129, 24, 96, "pyramid", "KOIN Center"),
    (155, 18, 72, "rect", "Fox Tower"), (175, 24, 120, "crown", "Wells Fargo Center"),
    (201, 20, 88, "chamfer", "PacWest Center"), (223, 18, 66, "rect", "Standard Insurance"),
    (243, 16, 54, "setback", ""), (261, 20, 42, "rect", ""), (283, 16, 30, "rect", ""),
    (301, 22, 20, "rect", ""),
]
# Mt Hood, unit half-width: broad shoulders, slightly concave flanks and a
# softened summit.
HOOD = [(-1, 0), (-0.7, 0.16), (-0.5, 0.31), (-0.32, 0.5), (-0.18, 0.7), (-0.09, 0.86),
        (-0.03, 0.96), (0.03, 1), (0.1, 0.95), (0.2, 0.82), (0.34, 0.63), (0.52, 0.42),
        (0.74, 0.2), (1, 0)]


# Mt Hood's place in the scene, in the same design units as PORTLAND: centred
# behind the right of downtown, its peak just under the tallest tower.
HOOD_AT, HOOD_HALF, HOOD_HIGH = 320, 122, 106
SCENE_W = HOOD_AT + HOOD_HALF  # the scene's full width, city plus mountain


def portland(x0: float, scale: float) -> str:
    """Portland's skyline with Mt Hood behind it, in the outrun neon style:
    dark silhouettes backlit by a pink haze, the rooftops traced in a glowing
    pink-to-cyan line, and Hood's snowcap and outline in lavender. One scene,
    placed at x0 and scaled as a whole, so it looks the same everywhere."""
    hood_x, hood_w, hood_h = x0 + HOOD_AT * scale, HOOD_HALF * scale, HOOD_HIGH * scale
    span = max(bx + bw for bx, bw, *_ in PORTLAND) * scale
    width = int(HW) + 2
    prof = [0.0] * width
    beacons, strips = [], []
    for bx, bw, bh, shape, name in PORTLAND:
        X, W, H = x0 + bx * scale, bw * scale, bh * scale
        for px in range(max(0, int(X)), min(width, int(X + W) + 1)):
            t = min(1.0, max(0.0, (px - X) / W))
            d = min(t, 1 - t) * W
            hh = H
            if shape == "chamfer":
                hh = H - max(0.0, 0.28 * W - d)
            elif shape == "pill":
                r = W / 2
                hh = H - r + math.sqrt(max(0.0, r * r - (px - X - r) ** 2))
            elif shape == "pyramid":
                base = H * 0.74
                hh = base + (H - base) * max(0.0, 1 - abs(t - 0.5) / 0.42)
            elif shape == "crown":
                hh = H + (6 * scale if 0.4 < t < 0.6 else 0) - (5 * scale if d < 0.12 * W else 0)
            elif shape == "setback":
                hh = H if 0.3 < t < 0.7 else H * 0.8
            elif shape == "spire":
                hh = H * 0.68 + H * 0.32 * max(0.0, 1 - abs(t - 0.5) / 0.22) if abs(t - 0.5) < 0.22 else H * 0.68
            prof[px] = max(prof[px], hh)
        if shape == "pyramid":
            beacons.append((X + W / 2, H + 12 * scale, PINK))
        if shape == "crown":
            beacons.append((X + W / 2, H + 6 * scale + 10 * scale, CYAN))
        if name == "Big Pink":
            strips.append((X + W * 0.5, H * 0.85, PINK))
        if name in ("Wells Fargo Center", "PacWest Center"):
            strips.append((X + W * 0.3, H * 0.7, CYAN))

    lit = [px for px in range(width) if prof[px] > 0]
    c0, c1 = lit[0], lit[-1]
    raw = [(c0, HORIZON)] + [(px, HORIZON - prof[px]) for px in range(c0, c1 + 1)] + [(c1, HORIZON)]
    pts = [raw[0]]
    for px, py in raw[1:]:
        if abs(py - pts[-1][1]) > 2.5 and px != pts[-1][0]:  # a wall: go straight up or down
            pts.append((px, pts[-1][1]))
        pts.append((px, py))
    simple = [pts[0]]
    for i in range(1, len(pts) - 1):  # drop points on a straight run
        (ax, ay), (bx, by), (cx, cy) = simple[-1], pts[i], pts[i + 1]
        if abs((bx - ax) * (cy - ay) - (by - ay) * (cx - ax)) > 0.6:
            simple.append(pts[i])
    simple.append(pts[-1])
    roof = " ".join(f"{fmt(px)},{fmt(py)}" for px, py in simple[1:-1])
    city = "M" + " L".join(f"{fmt(px)},{fmt(py)}" for px, py in simple) + " Z"

    hood = [(hood_x + u * hood_w, HORIZON - v * hood_h) for u, v in HOOD]
    hood_d = "M" + " L".join(f"{fmt(x)},{fmt(y)}" for x, y in hood) + " Z"
    hood_line = " ".join(f"{fmt(x)},{fmt(y)}" for x, y in hood)
    # Snowcap: the top of the cone down to a ragged snowline.
    snow_v = 0.6
    def edge(v, side):
        seq = HOOD if side < 0 else HOOD[::-1]
        for (u1, v1), (u2, v2) in zip(seq, seq[1:]):
            if min(v1, v2) <= v <= max(v1, v2) and v1 != v2:
                return u1 + (u2 - u1) * (v - v1) / (v2 - v1)
        return 0
    left_u, right_u = edge(snow_v, -1), edge(snow_v, 1)
    top = [(u, v) for u, v in HOOD if v > snow_v]
    jag, n = [], 9
    for i in range(n + 1):
        u = right_u - (right_u - left_u) * i / n
        v = snow_v + (0.07 if i % 2 else -0.02) + (0.05 if i in (3, 6) else 0)
        jag.append((u, v))
    snow = [(left_u, snow_v)] + top + [(right_u, snow_v)] + jag[1:-1]
    snow_d = "M" + " L".join(f"{fmt(hood_x + u * hood_w)},{fmt(HORIZON - v * hood_h)}" for u, v in snow) + " Z"

    parts = [
        f'<linearGradient id="pdxNeon" gradientUnits="userSpaceOnUse" x1="{c0}" y1="0" x2="{c1}" y2="0">'
        f'<stop offset="0" stop-color="{PINK}" stop-opacity="0.2"/><stop offset="0.25" stop-color="{PINK}"/>'
        f'<stop offset="0.7" stop-color="#ff6ec7"/><stop offset="1" stop-color="{CYAN}"/></linearGradient>',
        f'<ellipse cx="{fmt(hood_x)}" cy="{HORIZON}" rx="{fmt(hood_w * 1.5)}" ry="{fmt(hood_h * 1.05)}" fill="url(#cityHaze)" filter="url(#blur28)"/>',
        f'<path d="{hood_d}" fill="url(#hoodFill)"/>',
        f'<path d="{snow_d}" fill="url(#hoodSnow)"/>',
        f'<polyline points="{hood_line}" fill="none" stroke="#b98cff" stroke-width="2.4" stroke-opacity="0.5" filter="url(#lineGlow)"/>',
        f'<polyline points="{hood_line}" fill="none" stroke="#d9c6ff" stroke-width="1" stroke-opacity="0.85" stroke-linejoin="round"/>',
        f'<path d="{city}" fill="url(#citySil)"/>',
    ]
    for sx, sh, col in strips:
        parts.append(f'<rect x="{fmt(sx)}" y="{fmt(HORIZON - sh)}" width="1.4" height="{fmt(sh - 4)}" fill="{col}" '
                     f'fill-opacity="0.55" filter="url(#starGlow)"/>')
    for bx, bh, col in beacons:
        parts.append(f'<rect x="{fmt(bx - 0.5)}" y="{fmt(HORIZON - bh)}" width="1" height="{fmt(bh - (bh - 12 * scale) if col == PINK else 10 * scale)}" '
                     f'fill="{col}" fill-opacity="0.8"/>'
                     f'<circle class="beacon" cx="{fmt(bx)}" cy="{fmt(HORIZON - bh - 1)}" r="1.7" fill="{col}" filter="url(#starGlow)"/>')
    parts.append(f'<polyline points="{roof}" fill="none" stroke="url(#pdxNeon)" stroke-width="3" stroke-opacity="0.7" filter="url(#lineGlow)"/>')
    parts.append(f'<polyline points="{roof}" fill="none" stroke="url(#pdxNeon)" stroke-width="1.3" stroke-linejoin="round"/>')
    return "\n".join(parts)


def tree_layer(count: int, seed: int, max_h: float, min_h: float):
    """Hero.tsx treeLayer(): pines thin out toward the centre."""
    for i in range(count):
        x = (i + 0.5) * (1200 / count) + (((i * seed) % 17) - 8)
        centre = abs(x - 600) / 600
        h = (min_h + ((i * seed * 7) % (max_h - min_h))) * (0.45 + 0.55 * centre)
        yield x * HW / 1200, h, h * 0.55


def pine(x: float, h: float, w: float, base: float) -> str:
    """A Douglas fir: a narrow spire over 6-9 jagged branch tiers whose tips
    droop, widening towards the base, on a short trunk. Seeded by position,
    so each tree is different but the same every build."""
    rng = random.Random(round(x * 7.3 + h))
    trunk = h * 0.1
    crown = h - trunk
    tiers = 6 + int(h // 18) if h > 20 else 5
    left, right = [], []
    for i in range(tiers):
        t = (i + 1) / tiers
        y_tip = base - trunk - crown * (1 - t) + crown * 0.02
        y_in = y_tip - crown / tiers * 0.55
        half = w / 2 * (0.12 + 0.88 * t ** 0.9)
        for side, pts in ((-1, left), (1, right)):
            j = rng.uniform(0.85, 1.12)
            pts.append((x + side * half * 0.42, y_in))
            pts.append((x + side * half * j, y_tip + rng.uniform(0, 1.2)))
            pts.append((x + side * half * j * 0.7, y_tip - 0.6))
    top = (x, base - h)
    tw = max(1.2, w * 0.07)
    pts = [top] + right + [(x + tw, base - trunk + 1), (x + tw, base), (x - tw, base), (x - tw, base - trunk + 1)] + left[::-1]
    return " ".join(f"{fmt(px)},{fmt(py)}" for px, py in pts)


def treeline(avoid=()) -> str:
    def capped(layer):
        for x, h, w in layer:
            # Keep tree tops clear of any text above them.
            under = [y1 for x0, y0, x1, y1 in avoid if x0 - 10 < x < x1 + 10]
            if under:
                room = HORIZON - max(under) - 6
                if room < h:  # shrink to fit, keeping some variety in height
                    h = max(8.0, room * (0.68 + 0.32 * ((x * 0.618) % 1)))
                    w = h * 0.55
            yield x, h, w
    back = "".join(f'<polygon points="{pine(x, h, w, HORIZON)}"/>' for x, h, w in capped(tree_layer(48, 13, 52, 26)))
    front = "".join(f'<polygon points="{pine(x, h, w, HORIZON)}"/>' for x, h, w in capped(tree_layer(34, 29, 68, 34)))
    # Lit from the city: violet back row, plum front row with a faint lavender
    # rim, so the treeline reads against the dark sky.
    return (f'<g fill="url(#treeBack)" opacity="0.85">{back}</g>\n'
            f'<g fill="url(#treeFront)" stroke="#b98cff" stroke-opacity="0.3" stroke-width="0.6" '
            f'stroke-linejoin="round">{front}</g>')


HEADER_CAR = True  # a modern electric roadster driving into the grid, seen from behind


def car(cx: float, ground: float, width: float) -> str:
    """The roadster from behind, rendered by render_roadster.py (the same 3D model
    the Stats card's calendar uses), embedded as a PNG so it shows inside
    GitHub's image proxy. A pink glow sits on the grid under it."""
    import base64
    png = IMAGES / "roadster-rear.png"
    data = base64.b64encode(png.read_bytes()).decode()
    from PIL import Image as _Image
    with _Image.open(png) as im:
        h = width * im.height / im.width
    return f"""<g transform="translate({fmt(cx)} {fmt(ground)})">
<ellipse cx="0" cy="-2" rx="{fmt(width * 0.62)}" ry="{fmt(width * 0.07)}" fill="{PINK}" fill-opacity="0.4" filter="url(#carGlow)"/>
<g class="car"><image href="data:image/png;base64,{data}" x="{fmt(-width / 2)}" y="{fmt(-h)}" width="{fmt(width)}" height="{fmt(h)}"/></g>
</g>"""


# The car holds its lane, perfectly still; the grid rushing past gives the speed.
CAR_CSS = ""


def grid() -> tuple[str, str]:
    """Cyan perspective floor; horizontal lines roll toward the viewer."""
    parts = []
    for i in range(-14, 15):
        parts.append(f'<line x1="{fmt(HW / 2 + i * 14)}" y1="{HORIZON}" '
                     f'x2="{fmt(HW / 2 + i * 150)}" y2="{HH}"/>')
    lines, period, far = 7, 0.22, 9.0  # a line every 0.22 s: the floor races towards the viewer
    frames = []
    for step in range(21):
        t = step / 20
        y = HORIZON + (HH - HORIZON) / far ** (1 - t)
        frames.append(f"{t * 100:.0f}%{{transform:translateY({y:.1f}px)}}")
    for k in range(lines):
        parts.append(f'<line class="h" x1="0" y1="0" x2="{HW}" y2="0" '
                     f'style="animation-delay:-{k * period:.2f}s"/>')
        y = HORIZON + (HH - HORIZON) / far ** (1 - (k + 0.5) / lines)
        parts.append(f'<line class="hs" x1="0" y1="{y:.1f}" x2="{HW}" y2="{y:.1f}"/>')
    css = (f"@keyframes run{{{''.join(frames)}}}"
           f".h{{animation:run {lines * period:.2f}s linear infinite}}")
    return "\n".join(parts), css


def typing_timeline() -> tuple[list[tuple[int, int, int]], int]:
    """Return [(time_ms, line_index, visible_chars)] and the cycle length."""
    events, t = [], 0
    for i, line in enumerate(LINES):
        for n in range(1, len(line) + 1):
            t += TYPE_MS
            events.append((t, i, n))
        t += HOLD_MS
        for n in range(len(line) - 1, -1, -1):
            t += DELETE_MS
            events.append((t, i, n))
    return events, t + TYPE_MS


def discrete(attr: str, values: list[str], times: list[int], total: int) -> str:
    keys = ";".join(f"{v / total:.5f}" for v in times)
    return (f'<animate attributeName="{attr}" calcMode="discrete" values="{";".join(values)}" '
            f'keyTimes="{keys}" dur="{total / 1000:.3f}s" repeatCount="indefinite"/>')


def terminal(f: Fonts, top: float, size: float = 20, prompt: bool = True) -> str:
    mono, box_h = f.mono, size * 1.9
    baseline = top + size * 1.3
    if prompt:
        prompt_d, prompt_w = mono.path(PROMPT, size, LEFT + 12, baseline)
        chevron_x = LEFT + 12 + prompt_w + 2
    else:  # phones: just the chevron, so the longest line still fits
        prompt_d, chevron_x = "", LEFT + 12
    text_x = chevron_x + mono.advance(" ", size) * 2
    adv = mono.advance("M", size)
    events, total = typing_timeline()

    times = [0] + [t for t, _, _ in events]
    counts = [0] + [n for _, _, n in events]
    widths = [fmt(text_x - LEFT + n * adv + 18) for n in counts]
    cursor_xs = [fmt(text_x + n * adv + 2) for n in counts]

    out = [
        f'<rect x="{LEFT}" y="{top}" height="{fmt(box_h)}" width="{widths[0]}" rx="4" '
        f'fill="{CYAN}" fill-opacity="0.04">{discrete("width", widths, times, total)}</rect>',
        f'<rect x="{LEFT}" y="{top}" width="2" height="{fmt(box_h)}" fill="{CYAN}" fill-opacity="0.4"/>',
        f'<path d="{prompt_d}" fill="{PROMPT_COL}"/>',
        f'<path d="M{fmt(chevron_x)} {fmt(baseline - size * 0.65)} l{fmt(size * 0.3)} {fmt(size * 0.3)} '
        f'l{fmt(-size * 0.3)} {fmt(size * 0.3)}" fill="none" stroke="{PROMPT_COL}" '
        f'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>',
    ]
    for i, line in enumerate(LINES):
        d, _ = mono.path(line, size, text_x, baseline)
        line_times, line_widths, last = [0], ["0"], "0"
        for t, li, n in events:
            w = fmt(n * adv) if li == i else "0"
            if w != last:
                line_times.append(t)
                line_widths.append(w)
                last = w
        out.append(f'<clipPath id="type{i}"><rect x="{fmt(text_x)}" y="{top}" height="{fmt(box_h)}" '
                   f'width="0">{discrete("width", line_widths, line_times, total)}</rect></clipPath>')
        out.append(f'<path d="{d}" fill="{CYAN}" clip-path="url(#type{i})"/>')
    out.append(f'<rect x="{cursor_xs[0]}" y="{fmt(baseline - size * 0.75)}" width="2" height="{fmt(size * 0.8)}" fill="{CYAN}">'
               f'{discrete("x", cursor_xs, times, total)}'
               f'<animate attributeName="opacity" calcMode="discrete" values="1;0" keyTimes="0;0.5" '
               f'dur="{2 * BLINK_MS / 1000:.2f}s" repeatCount="indefinite"/></rect>')
    return "\n".join(out)


def location(f: Fonts, baseline: float, size: float = 15) -> str:
    """'Brit builder · (pin) Lake Oswego, Oregon' in the site's dim mono."""
    colour, x, k = PROMPT_COL, LEFT, size / 15
    out = []
    d, w = f.mono.path(f"{LOCATION[0]} · ", size, x, baseline)
    out.append(f'<path d="{d}" fill="{colour}"/>')
    x += w + 2 * k
    out.append(icon("map-pin", x, baseline - 13 * k, size, colour, 2.2))
    x += 21 * k
    d, w = f.mono.path(LOCATION[1], size, x, baseline)
    out.append(f'<path d="{d}" fill="{colour}"/>')
    return "\n".join(out)


def header_phone(f: Fonts) -> str:
    """The hero laid out for phones: 480 wide, so once a phone scales it to its
    screen the text is a readable size. Served by a <picture> media query."""
    global HW, HH, HORIZON, LEFT
    saved = HW, HH, HORIZON, LEFT
    try:
        HW, LEFT = 480, 28
        return header(f, phone=True)
    finally:
        HW, HH, HORIZON, LEFT = saved


def header(f: Fonts, text: bool = True, phone: bool = False) -> str:
    """The README hero. With text=False, just the scene (used as a backdrop)."""
    global HH, HORIZON
    name_size = 76 if phone else 94
    tracking = -0.025 * name_size  # Tailwind tracking-tight
    # Put the top of the capitals as far from the panel's top edge as the
    # first letter's ink is from its left edge.
    first = f.display.glyphs[f.display.cmap[ord(NAME[0][0])]]
    bounds = BoundsPen(f.display.glyphs)
    first.draw(bounds)
    scale = name_size / f.display.upm
    ink_left, cap_top = LEFT + bounds.bounds[0] * scale, bounds.bounds[3] * scale
    baseline = ink_left + cap_top
    top = baseline - 0.72 * name_size
    line1, _ = f.display.path(NAME[0], name_size, LEFT, baseline, tracking)
    line2, _ = f.display.path(NAME[1], name_size, LEFT, baseline + name_size, tracking)
    if phone:
        # Stack everything under the name, then put the horizon below it.
        term_top = baseline + name_size + 30
        term_size = 16
        tag_size, tag_lead = 18, 26
        tag_lines = f.sans.wrap(TAGLINE, tag_size, HW - 2 * LEFT)
        tag_y = term_top + term_size * 1.9 + 40
        loc_y = tag_y + (len(tag_lines) - 1) * tag_lead + 32
        HORIZON = round(loc_y + 120)  # room for the skyline under the text
        HH = HORIZON + 96
        tagline = " ".join(f.sans.path(line, tag_size, LEFT, tag_y + i * tag_lead)[0]
                           for i, line in enumerate(tag_lines))
        term = terminal(f, term_top, term_size, prompt=False)
        loc = location(f, loc_y, 13)
    else:
        tagline, _ = f.sans.path(TAGLINE, 20, LEFT, 347)
        term, loc = terminal(f, 255), location(f, 381)
    grid_svg, grid_css = grid()

    # Where the text sits, so stars stay off it and towers stay below it.
    pad = 14
    if text:
        name_w = max(f.display.width(n, name_size, tracking) for n in NAME)
        if phone:
            t_top, t_size, tags, t_lead, t_y, l_y, l_size = term_top, term_size, tag_lines, tag_lead, tag_y, loc_y, 13
            t_w = f.mono.width("  " + max(LINES, key=len), t_size) + 30
        else:
            t_top, t_size, tags, t_lead, t_y, l_y, l_size = 255, 20, [TAGLINE], 0, 347, 381, 15
            t_w = f.mono.width(PROMPT + "  " + max(LINES, key=len), t_size) + 30
        l_w = f.mono.width(f"{LOCATION[0]} · " + LOCATION[1], l_size) + 24
        rects = [(LEFT, top, LEFT + name_w, baseline + name_size),
                 (LEFT, t_top, LEFT + t_w, t_top + t_size * 1.9)]
        rects += [(LEFT, t_y + i * t_lead - 18, LEFT + f.sans.width(line, 18 if phone else 20), t_y + i * t_lead + 5)
                  for i, line in enumerate(tags)]
        rects.append((LEFT, l_y - l_size, LEFT + l_w, l_y + 4))
        avoid = [(x0 - pad, y0 - pad, x1 + pad, y1 + pad) for x0, y0, x1, y1 in rects]
    else:
        avoid = []

    # The site's .gradient-text is 135deg across the full-width heading box.
    box_w, box_h = HW - 2 * LEFT, 2 * name_size
    half = (box_w + box_h) * 0.7071 / 2
    cx, cy = LEFT + box_w / 2, top + box_h / 2
    g = (cx - half * .7071, cy - half * .7071, cx + half * .7071, cy + half * .7071)

    words = (f'<path d="{line1} {line2}" fill="url(#nameFill)"/>\n{term}\n'
             f'<path d="{tagline}" fill="{TEXT_2}"/>\n{loc}') if text else ""
    body = f"""<style>
@keyframes twinkle{{0%,100%{{opacity:1;transform:scale(1)}}50%{{opacity:.08;transform:scale(.4)}}}}
.star{{fill:#fff;transform-box:fill-box;transform-origin:center;animation:twinkle 4s ease-in-out infinite}}
@keyframes pulse{{0%,100%{{opacity:.55}}50%{{opacity:1}}}}
.horizon{{animation:pulse 5s ease-in-out infinite}}
{grid_css}
{CAR_CSS if HEADER_CAR else ""}
.hs{{display:none}}
@keyframes winblink{{0%,100%{{opacity:.8}}50%{{opacity:.1}}}}
.wb{{animation:winblink 7s ease-in-out infinite}}
@keyframes beacon{{0%,100%{{opacity:1}}50%{{opacity:.25}}}}
.beacon{{animation:beacon 2.4s ease-in-out infinite}}
@media (prefers-reduced-motion: reduce){{.star,.horizon,.h,.wb,.beacon,.carwrap,.car{{animation:none}}.h{{display:none}}.hs{{display:inline}}}}
</style>
<defs>
  <clipPath id="panel"><rect width="{HW}" height="{HH}" rx="16"/></clipPath>
  <clipPath id="floor"><rect y="{HORIZON}" width="{HW}" height="{HH - HORIZON}"/></clipPath>
  <radialGradient id="skyGlow" cx="0.5" cy="0" r="0.5" gradientTransform="translate(0.5 0) scale(0.8 0.45) translate(-0.5 0)">
    <stop offset="0" stop-color="{VIOLET}" stop-opacity="0.16"/><stop offset="1" stop-color="{VIOLET}" stop-opacity="0"/>
  </radialGradient>
  <radialGradient id="aura" cx="0.5" cy="0.9" r="0.6">
    <stop offset="0" stop-color="{PINK}" stop-opacity="0.3"/><stop offset="0.35" stop-color="{PURPLE}" stop-opacity="0.18"/>
    <stop offset="0.6" stop-color="{CYAN}" stop-opacity="0.06"/><stop offset="0.75" stop-color="{CYAN}" stop-opacity="0"/>
  </radialGradient>
  <linearGradient id="horizonLine" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="{PINK}" stop-opacity="0"/><stop offset="0.2" stop-color="{PINK}" stop-opacity="0.9"/>
    <stop offset="0.5" stop-color="{CYAN}" stop-opacity="0.75"/><stop offset="0.8" stop-color="{PINK}" stop-opacity="0.9"/>
    <stop offset="1" stop-color="{PINK}" stop-opacity="0"/>
  </linearGradient>
  <linearGradient id="floorFade" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0.5" stop-color="{BG}" stop-opacity="0"/><stop offset="0.8" stop-color="{BG}" stop-opacity="0.8"/>
    <stop offset="1" stop-color="{BG}"/>
  </linearGradient>
  <linearGradient id="nameFill" gradientUnits="userSpaceOnUse" x1="{fmt(g[0])}" y1="{fmt(g[1])}" x2="{fmt(g[2])}" y2="{fmt(g[3])}">
    <stop offset="0" stop-color="#ffffff"/><stop offset="0.2" stop-color="#ff9de2"/><stop offset="0.45" stop-color="{PINK}"/>
    <stop offset="0.7" stop-color="{PURPLE}"/><stop offset="1" stop-color="{CYAN}"/>
  </linearGradient>
  <linearGradient id="border" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="{PINK}"/><stop offset="0.5" stop-color="{PURPLE}"/><stop offset="1" stop-color="{CYAN}"/>
  </linearGradient>
  <filter id="blur28" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="28"/></filter>
  <linearGradient id="treeBack" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#3f1868"/><stop offset="1" stop-color="#220b40"/></linearGradient>
  <linearGradient id="treeFront" x1="0" y1="0" x2="1" y2="0.35">
    <stop offset="0" stop-color="#160628"/><stop offset="0.55" stop-color="#2d0f52"/><stop offset="1" stop-color="#55208a"/></linearGradient>
  <linearGradient id="carHaunchL" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#4a1d7a"/><stop offset="1" stop-color="#22093f"/></linearGradient>
  <linearGradient id="carHaunchR" x1="1" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#2c0d50"/><stop offset="1" stop-color="#140528"/></linearGradient>
  <linearGradient id="carBody" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#2b0b4a"/><stop offset="1" stop-color="#0d0015"/></linearGradient>
  <linearGradient id="carGlass" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="{CYAN}" stop-opacity="0.45"/><stop offset="0.5" stop-color="{VIOLET}" stop-opacity="0.25"/>
    <stop offset="1" stop-color="{PINK}" stop-opacity="0.35"/></linearGradient>
  <linearGradient id="tailLight" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#ff2e6e"/><stop offset="0.5" stop-color="#ff7ab0"/><stop offset="1" stop-color="#ff2e6e"/></linearGradient>
  <filter id="tailGlow" x="-20%" y="-300%" width="140%" height="700%"><feGaussianBlur stdDeviation="3.5"/></filter>
  <filter id="carGlow" x="-30%" y="-200%" width="160%" height="500%"><feGaussianBlur stdDeviation="7"/></filter>
  <linearGradient id="citySil" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#2b0b4a"/><stop offset="1" stop-color="#0a0012"/></linearGradient>
  <linearGradient id="hoodFill" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#2a1150"/><stop offset="1" stop-color="#140628"/></linearGradient>
  <linearGradient id="hoodSnow" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#f3e9ff" stop-opacity="0.85"/><stop offset="1" stop-color="#b98cff" stop-opacity="0.35"/></linearGradient>
  <radialGradient id="cityHaze" cx="0.5" cy="1" r="0.75">
    <stop offset="0" stop-color="{PINK}" stop-opacity="0.55"/><stop offset="0.45" stop-color="{PURPLE}" stop-opacity="0.25"/>
    <stop offset="1" stop-color="{VIOLET}" stop-opacity="0"/></radialGradient>
  <linearGradient id="cityFill" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#2a0f4d"/><stop offset="1" stop-color="#12041f"/></linearGradient>
  <filter id="lineGlow" x="-5%" y="-800%" width="110%" height="1700%"><feGaussianBlur stdDeviation="8"/></filter>
  <filter id="starGlow" x="-200%" y="-200%" width="500%" height="500%">
    <feGaussianBlur stdDeviation="2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
</defs>
<g clip-path="url(#panel)">
<rect width="{HW}" height="{HH}" fill="{BG}"/>
<rect width="{HW}" height="{HH}" fill="url(#skyGlow)"/>
{stars(avoid)}
<ellipse cx="{fmt(HW * 0.68)}" cy="{HORIZON - 30}" rx="{fmt(HW * 0.33)}" ry="170" fill="url(#aura)" filter="url(#blur28)"/>
<g clip-path="url(#floor)" stroke="{CYAN}" stroke-opacity="0.35" stroke-width="1">
{grid_svg}
</g>
<rect y="{HORIZON}" width="{HW}" height="{HH - HORIZON}" fill="url(#floorFade)"/>
{(portland((HW - SCENE_W * 0.72) / 2, 0.72) if phone else portland(598, 0.92)) if HEADER_SKYLINE else ""}
{treeline(avoid)}
<g class="horizon">
<rect y="{HORIZON - 1}" width="{HW}" height="3" fill="url(#horizonLine)" filter="url(#lineGlow)"/>
<rect y="{HORIZON - 1}" width="{HW}" height="3" fill="url(#horizonLine)"/>
</g>
{f'<g class="carwrap">{car(HW / 2, HH - 4, 104 if phone else 128)}</g>' if HEADER_CAR else ""}
{words}
</g>
<rect x="0.5" y="0.5" width="{HW - 1}" height="{HH - 1}" rx="15.5" fill="none" stroke="url(#border)" stroke-opacity="0.45"/>"""
    return svg(HW, HH, body, "Markus Weldon · Principal Solutions Engineer")


# ══ Project cards ══════════════════════════════════════════════════════════

# (repo, title, description, language, language colour, topic)
CARDS = [
    ("cverdict", "CVErdict",
     "CVE Verdict: cuts through the noise of the CVE program surge to show which new "
     "vulnerabilities need attention and why.", "TypeScript", "#3178c6", "CVE Triage"),
    ("openfix", "OpenFix",
     "Turns scanner findings into verified fixes with any model. Each patch is proven by a "
     "rescan, your tests and a regression test, then lands as a draft PR.",
     "Python", "#3572A5", "Verified Fixes"),
    ("agentinel", "agentinel",
     "Red-teams and statically audits MCP servers and AI agents against the OWASP Agentic "
     "Top 10 (2026).", "Python", "#3572A5", "MCP & Agent Security"),
    ("claude-owasp-security-skills", "claude-owasp-security-skills",
     "OWASP Top 10:2025, API, Mobile, LLM/Agentic and CI/CD standards, shipped as Claude "
     "Code skills.", "Shell", "#89e051", "Claude Code Skills"),
    ("snyk-ai-secure-pipeline", "snyk-ai-secure-pipeline",
     "End-to-end DevSecOps demo: Snyk Code, OSS, Container and IaC, plus an MCP server for "
     "Claude Code.", "JavaScript", "#f1e05a", "DevSecOps"),
    ("claude-snyk-security-expert", "claude-snyk-security-expert",
     "Snyk-powered security subagent for Claude Code: enterprise vulnerability assessment "
     "and remediation.", "Claude Code", CYAN, "Security Subagent"),
]

CW, CH, PAD = 400, 182, 24


def pill(f: Fonts, x: float, y: float, text: str, dot: str | None = None,
         size: float = 12, h: float = 22) -> tuple[str, float]:
    """The site's tag pill: text-xs, purple tint, rounded-full."""
    tx = x + 9 + (12 if dot else 0)
    d, w = f.sans.path(text, size, tx, y + h / 2 + size * 0.36)
    width = (tx - x) + w + 9
    out = (f'<rect x="{fmt(x + .5)}" y="{fmt(y + .5)}" width="{fmt(width - 1)}" height="{h - 1}" rx="{h / 2 - .5}" '
           f'fill="{PURPLE}" fill-opacity="0.08" stroke="{PURPLE}" stroke-opacity="0.2"/>')
    if dot:
        out += f'<circle cx="{fmt(x + 13)}" cy="{fmt(y + h / 2)}" r="3.5" fill="{dot}"/>'
    out += f'<path d="{d}" fill="{LAVENDER}"/>'
    return out, width


def panel(w: float, h: float, wash: bool = False, top_line: bool = False) -> list[str]:
    """The card background: #130022 panel, the site's section grid (faint cyan
    rows, purple columns), a pink corner glow and a thin pink border. `wash`
    adds the Focus Areas cards' pink-violet-cyan tint; `top_line` their glowing
    top edge."""
    out = [f'<defs><pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse" x="{PAD}" y="0">'
           f'<rect y="29" width="30" height="1" fill="{CYAN}" fill-opacity="0.09"/>'
           f'<rect x="29" width="1" height="30" fill="{PURPLE}" fill-opacity="0.1"/></pattern>'
           f'<radialGradient id="glow" cx="1" cy="0" r="0.9"><stop offset="0" stop-color="{PINK}" stop-opacity="0.12"/>'
           f'<stop offset="1" stop-color="{PINK}" stop-opacity="0"/></radialGradient>'
           f'<linearGradient id="wash" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{PINK}" stop-opacity="0.07"/>'
           f'<stop offset="0.5" stop-color="{VIOLET}" stop-opacity="0.05"/><stop offset="1" stop-color="{CYAN}" stop-opacity="0.04"/></linearGradient>'
           f'<linearGradient id="edge" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{PINK}" stop-opacity="0"/>'
           f'<stop offset="0.4" stop-color="{PINK}" stop-opacity="0.8"/><stop offset="0.75" stop-color="{CYAN}" stop-opacity="0.4"/>'
           f'<stop offset="1" stop-color="{CYAN}" stop-opacity="0"/></linearGradient>'
           f'<clipPath id="c"><rect width="{w}" height="{h}" rx="16"/></clipPath></defs>',
           f'<rect width="{w}" height="{h}" rx="16" fill="{SURFACE}"/>',
           f'<g clip-path="url(#c)"><rect width="{w}" height="{h}" fill="url(#grid)"/>'
           + (f'<rect width="{w}" height="{h}" fill="url(#wash)"/>' if wash else "")
           + f'<rect width="{w}" height="{h}" fill="url(#glow)"/>'
           + (f'<rect x="16" width="{w - 32}" height="1" fill="url(#edge)"/>' if top_line else "")
           + '</g>',
           f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="15.5" fill="none" '
           f'stroke="{PINK}" stroke-opacity="0.3"/>']
    return out


def card(f: Fonts, title: str, desc: str, lang: str, lang_colour: str, topic: str) -> str:
    out = panel(CW, CH) + [f'<path transform="translate({PAD} {PAD})" d="{OCTOCAT}" fill="{PINK}"/>']
    d, _ = f.mono_semibold.path(title, 16, PAD + 26, PAD + 13)
    # The header name's pink-to-cyan gradient, fitted to each title's own
    # width so short and long names both run the full range.
    out.insert(0, f'<defs><linearGradient id="title" x1="0" y1="0" x2="1" y2="0">'
                  f'<stop offset="0" stop-color="#ff9de2"/><stop offset="0.45" stop-color="{PINK}"/>'
                  f'<stop offset="1" stop-color="{CYAN}"/></linearGradient></defs>')
    out.append(f'<path d="{d}" fill="url(#title)"/>')
    lines = f.sans.wrap(desc, 14, CW - 2 * PAD)
    if len(lines) > 3:
        sys.exit(f"Card description for {title} needs more than three lines")
    for i, line in enumerate(lines):
        d, _ = f.sans.path(line, 14, PAD, PAD + 44 + i * 22.75)
        out.append(f'<path d="{d}" fill="{TEXT_2}"/>')
    x, y = PAD, CH - PAD - 22
    p, w = pill(f, x, y, lang, lang_colour)
    out.append(p)
    p, _ = pill(f, x + w + 6, y, topic)
    out.append(p)
    return svg(CW, CH, "\n".join(out), title)


# ══ Focus Areas cards ══════════════════════════════════════════════════════

# The site's FOCUS_AREAS (personal-site src/lib/content.ts), shortened to fit.
FOCUS = [
    ("agentic-ai-security", "shield", "Agentic AI Security",
     "Security for AI agents, MCP servers and AI-native apps, from runtime "
     "orchestration to evaluation loops."),
    ("secure-ai-development", "code", "Securing AI-Driven Development",
     "Secure-at-inception guardrails in AI coding assistants, IDEs and CI/CD, "
     "so AI-written code ships secure."),
    ("enterprise-ai-strategy", "building-2", "Enterprise AI Security Strategy",
     "Partnering with CISOs and platform leaders on AI security programs, from "
     "asset visibility to agentic defense."),
]
FW, FPAD = 270, 22


def focus_cards(f: Fonts, wide: bool = False) -> dict[str, str]:
    """Cards like the site's Focus Areas. The 270px set sits three across on
    desktop; the wide set (400px, icon beside the title) is what phones get,
    so the cards match the width of every other card on the page."""
    w = CW if wide else FW
    pad = PAD if wide else FPAD
    text_x = pad + 44 + 16 if wide else pad
    wrapped = [f.sans.wrap(desc, 13.5, w - 2 * pad) for *_, desc in FOCUS]
    titles = [f.sans_semibold.wrap(title, 16, w - text_x - pad) for _, _, title, _ in FOCUS]
    title_lines = max(len(t) for t in titles)  # every card leaves room for the longest title
    if wide:
        title_y = pad + 22 + 6 - (title_lines - 1) * 10.5  # centred on the icon tile
        desc_y = pad + 44 + 30
    else:
        title_y = pad + 44 + 30
        desc_y = title_y + (title_lines - 1) * 21 + 26
    h = desc_y + (max(len(w) for w in wrapped) - 1) * 21 + pad + 2
    cards = {}
    for (slug, icon_name, title, _), lines, tlines in zip(FOCUS, wrapped, titles):
        out = panel(w, h, wash=True, top_line=True)
        out.insert(0, f'<defs><linearGradient id="tile" x1="0" y1="0" x2="1" y2="1">'
                      f'<stop offset="0" stop-color="{PINK}" stop-opacity="0.15"/>'
                      f'<stop offset="1" stop-color="{VIOLET}" stop-opacity="0.15"/></linearGradient>'
                      f'<filter id="tileGlow" x="-50%" y="-50%" width="200%" height="200%">'
                      f'<feGaussianBlur stdDeviation="8"/></filter></defs>')
        out.append(f'<rect x="{pad}" y="{pad}" width="44" height="44" rx="12" fill="{PINK}" fill-opacity="0.12" '
                   f'filter="url(#tileGlow)"/>')
        out.append(f'<rect x="{pad + .5}" y="{pad + .5}" width="43" height="43" rx="11.5" fill="url(#tile)" '
                   f'stroke="{PINK}" stroke-opacity="0.35"/>')
        out.append(icon(icon_name, pad + 12, pad + 12, 20, PINK))
        for i, tline in enumerate(tlines):
            d, _ = f.sans_semibold.path(tline, 16, text_x, title_y + i * 21)
            out.append(f'<path d="{d}" fill="{TEXT}"/>')
        for i, line in enumerate(lines):
            d, _ = f.sans.path(line, 13.5, pad, desc_y + i * 21)
            out.append(f'<path d="{d}" fill="{TEXT_2}"/>')
        name = f"focus-{slug}-wide.svg" if wide else f"focus-{slug}.svg"
        cards[name] = svg(w, h, "\n".join(out), title)
    return cards


# ══ Stack cards ════════════════════════════════════════════════════════════

STACK = [
    ("ai-security", "AI & Security", ["Claude Code", "MCP", "Snyk", "OWASP"]),
    ("languages", "Languages", ["Python", "TypeScript", "JavaScript"]),
    ("web-runtime", "Web & Runtime", ["React", "Next.js", "Svelte", "Astro", "Node.js", "GraphQL"]),
    ("cloud-infra", "Cloud & Infra", ["AWS", "GCP", "Vercel", "Cloudflare", "Docker", "Kubernetes"]),
]


def stack_cards(f: Fonts) -> dict[str, str]:
    """A 2x2 grid of cards: the site's pink section label over its tag pills."""
    size, ph, gap = 13, 26, 8
    label_y = PAD + 10
    first_row = label_y + 18

    def layout(tags):
        rows, x, row = [[]], PAD, 0
        for tag in tags:
            w = f.sans.width(tag, size) + 18
            if x + w > CW - PAD and rows[-1]:
                rows.append([])
                x, row = PAD, row + 1
            rows[-1].append((x, tag))
            x += w + gap
        return rows

    layouts = [layout(tags) for *_, tags in STACK]
    cards = {}
    for i, ((slug, label, _), rows) in enumerate(zip(STACK, layouts)):
        # Cards sit two to a row in the README; each pair shares a height.
        pair = layouts[i - i % 2:i - i % 2 + 2]
        h = first_row + max(len(r) for r in pair) * (ph + gap) - gap + PAD
        out = panel(CW, h, top_line=True)
        d, _ = f.display_bold.path(label.upper(), 11, PAD, label_y, tracking=2.4)
        out.append(f'<path d="{d}" fill="{PINK}"/>')
        for r, row in enumerate(rows):
            for x, tag in row:
                p, _ = pill(f, x, first_row + r * (ph + gap), tag, size=size, h=ph)
                out.append(p)
        cards[f"stack-{slug}.svg"] = svg(CW, h, "\n".join(out), label)
    return cards


# ══ Pill buttons ═══════════════════════════════════════════════════════════

# (file, label, icon, icon side, style, fixed width)
# The four contact buttons share one width so they line up in a row on
# desktop and wrap into an even 2x2 on a phone.
ROW_W = 150
BUTTONS = [
    ("btn-website", "Website", "globe", "left", "purple", ROW_W),
    ("btn-github", "GitHub", "github", "left", "cyan", ROW_W),
    ("btn-linkedin", "LinkedIn", "linkedin", "left", "pink", ROW_W),
    ("btn-contact", "Get in Touch", "arrow-right", "right", "primary", ROW_W),
    ("btn-owasp-skills", "Try the OWASP Skills for Claude Code", "play", "left", "primary", None),
]

BTN_STYLES = {  # globals.css .btn-ghost-* / .btn-primary
    "cyan": dict(border=CYAN, text=CYAN),
    "pink": dict(border=PINK, text=PINK),
    "purple": dict(border=PURPLE, text=LAVENDER),
}


def button(f: Fonts, label: str, icon_name: str, side: str, style: str,
           fixed: float | None) -> str:
    m, h, size, gap, isz = 8, 40, 14, 8, 15  # m: margin for the glow
    primary = style == "primary"
    font = f.sans_semibold if primary else f.sans_medium
    text_w = font.width(label, size)
    content = isz + gap + text_w
    width = fixed or content + 48
    if content + 32 > width:
        sys.exit(f"Button label too long for {width}px: {label}")
    W, H = width + 2 * m, h + 2 * m
    colour = "#ffffff" if primary else BTN_STYLES[style]["text"]
    start = m + (width - content) / 2
    tx = start + (isz + gap if side == "left" else 0)
    ix = start if side == "left" else tx + text_w + gap
    d, _ = font.path(label, size, tx, m + h / 2 + 5)
    out = []
    if primary:
        out.append(f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
                   f'<stop offset="0" stop-color="{PINK}"/><stop offset="1" stop-color="{VIOLET}"/></linearGradient>'
                   f'<filter id="glow" x="-20%" y="-60%" width="140%" height="220%"><feGaussianBlur stdDeviation="5"/></filter></defs>')
        out.append(f'<rect x="{m}" y="{m}" width="{fmt(width)}" height="{h}" rx="{h / 2}" fill="url(#g)" '
                   f'opacity="0.55" filter="url(#glow)"/>')
        out.append(f'<rect x="{m}" y="{m}" width="{fmt(width)}" height="{h}" rx="{h / 2}" fill="url(#g)"/>')
    else:
        border = BTN_STYLES[style]["border"]
        out.append(f'<rect x="{m + .5}" y="{m + .5}" width="{fmt(width - 1)}" height="{h - 1}" rx="{h / 2 - .5}" '
                   f'fill="{SURFACE}" stroke="{border}" stroke-opacity="0.55"/>')
    out.append(icon(icon_name, ix, m + (h - isz) / 2, isz, colour))
    out.append(f'<path d="{d}" fill="{colour}"/>')
    return svg(W, H, "\n".join(out), label)


# ══ Section dividers ═══════════════════════════════════════════════════════

def divider(pink: str, cyan: str, glow: float) -> str:
    """globals.css .divider: a thin line fading in and out, pink to cyan."""
    body = f"""<defs>
  <linearGradient id="line" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="{pink}" stop-opacity="0"/><stop offset="0.3" stop-color="{pink}"/>
    <stop offset="0.7" stop-color="{cyan}"/><stop offset="1" stop-color="{cyan}" stop-opacity="0"/>
  </linearGradient>
  <filter id="glow" x="-5%" y="-400%" width="110%" height="900%"><feGaussianBlur stdDeviation="3"/></filter>
</defs>
<rect x="0" y="3" width="1200" height="4" fill="url(#line)" filter="url(#glow)" opacity="{glow}"/>
<rect x="0" y="4" width="1200" height="2" fill="url(#line)"/>"""
    return svg(1200, 10, body).replace("<svg ", '<svg preserveAspectRatio="none" ', 1)


def main(font_dir: Path) -> None:
    f = Fonts(font_dir)
    outputs = {"header.svg": header(f), "header-phone.svg": header_phone(f)}
    for repo, *details in CARDS:
        outputs[f"card-{repo}.svg"] = card(f, *details)
    outputs.update(focus_cards(f))
    outputs.update(focus_cards(f, wide=True))
    outputs.update(stack_cards(f))
    for name, *details in BUTTONS:
        outputs[f"{name}.svg"] = button(f, *details)
    outputs["synthwave-divider.svg"] = divider(PINK, CYAN, 0.7)
    outputs["synthwave-divider-light.svg"] = divider(PINK, "#0aa6a3", 0.35)
    for name, content in outputs.items():
        (IMAGES / name).write_text(content)
        print(f"Wrote images/{name} ({len(content) / 1024:.0f} KB)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(Path(sys.argv[1]))
