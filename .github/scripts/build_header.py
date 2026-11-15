#!/usr/bin/env python3
"""Build images/header.svg: the README hero, styled after markusweldon.com.

It mirrors the site's hero: a starfield under a purple sky glow, a pine
treeline on a pink-and-cyan horizon, a scrolling cyan perspective grid, the
name in two lines of Orbitron with the site's white-pink-purple-cyan
gradient, and a terminal line typing at the site's speed.

All text is drawn as SVG paths, because GitHub shows README SVGs as images
and an image cannot load web fonts. Outlining keeps it identical for every
visitor.

Usage:
    pip install fonttools brotli
    npm pack @fontsource/orbitron@5.0.19 geist@1.3.1
    (extract both tarballs into one folder, then)
    python3 .github/scripts/build_header.py <folder-with-the-extracted-packages>
"""

import sys
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[2]

NAME = ("MARKUS", "WELDON")
TAGLINE = "Helping enterprises adopt AI-assisted development securely."
PROMPT = "~/markusweldon "
LINES = [
    "Principal Solutions Engineer",
    "Securing Agentic AI Development",
    "AppSec · Cloud · Cybersecurity",
    "Enterprise GTM · Technical Pre-Sales",
    "Ship Faster With AI, Securely",
]

# markusweldon.com design tokens (src/app/globals.css, Hero.tsx)
BG = "#0d0015"
PINK = "#f92aad"
CYAN = "#36f9f6"
TEXT_2 = "#a78bca"
PROMPT_COL = "#7b5ea7"

W, H = 1000, 500
HORIZON = 392
LEFT = 56

# Site typewriter timing (Hero.tsx): 55 ms per typed character, 1.8 s hold,
# 32 ms per deleted character, cursor toggles every 530 ms.
TYPE_MS, HOLD_MS, DELETE_MS, BLINK_MS = 55, 1800, 32, 530


def fmt(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".")


class Font:
    def __init__(self, path: Path):
        self.font = TTFont(path)
        self.glyphs = self.font.getGlyphSet()
        self.cmap = self.font.getBestCmap()
        self.upm = self.font["head"].unitsPerEm

    def advance(self, char: str, size: float) -> float:
        return self.glyphs[self.cmap[ord(char)]].width * size / self.upm

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


def find_font(font_dir: Path, filename: str) -> Font:
    hits = sorted(font_dir.rglob(filename))
    if not hits:
        sys.exit(f"Font not found: {filename} under {font_dir}")
    return Font(hits[0])


# ── Scenery ────────────────────────────────────────────────────────────────

def stars() -> str:
    """The site's deterministic starfield (Hero.tsx STARS_REG / STARS_BRIGHT)."""
    out = []
    for i in range(48):
        x, y = (i * 137.508) % 100, (i * 97.314) % 50
        size = 3 if i % 5 == 0 else 2 if i % 3 == 0 else 1.5
        op = 0.45 + ((i * 71) % 37) / 100
        dur, delay = 4 + (i % 9) * 0.4, (i * 0.47) % 5.5
        out.append(f'<g opacity="{op:.2f}"><circle class="star" cx="{fmt(x * W / 100)}" '
                   f'cy="{fmt(y * HORIZON / 100)}" r="{size / 2}" '
                   f'style="animation-duration:{dur:.1f}s;animation-delay:{delay:.1f}s"/></g>')
    for i in range(6):
        x, y = (i * 173.12 + 17) % 100, (i * 61.7 + 8) % 45
        size = 3.5 + (i % 3)
        op = 0.75 + ((i * 31) % 20) / 100
        dur, delay = 5 + (i % 4) * 0.7, (i * 1.3) % 4
        out.append(f'<g opacity="{op:.2f}"><circle class="star" cx="{fmt(x * W / 100)}" '
                   f'cy="{fmt(y * HORIZON / 100)}" r="{size / 2}" filter="url(#starGlow)" '
                   f'style="animation-duration:{dur:.1f}s;animation-delay:{delay:.1f}s"/></g>')
    return "\n".join(out)


def tree_layer(count: int, seed: int, max_h: float, min_h: float):
    """Hero.tsx treeLayer(): pines thin out toward the centre."""
    for i in range(count):
        x = (i + 0.5) * (1200 / count) + (((i * seed) % 17) - 8)
        centre = abs(x - 600) / 600
        h = (min_h + ((i * seed * 7) % (max_h - min_h))) * (0.45 + 0.55 * centre)
        yield x * W / 1200, h, h * 0.55


def pine(x: float, h: float, w: float, base: float) -> str:
    t1, t2, t3 = base - h, base - h * 0.62, base - h * 0.3
    pts = [(x, t1), (x + w * .22, t2), (x + w * .12, t2), (x + w * .36, t3), (x + w * .2, t3),
           (x + w * .5, base), (x - w * .5, base), (x - w * .2, t3), (x - w * .36, t3),
           (x - w * .12, t2), (x - w * .22, t2)]
    return " ".join(f"{fmt(px)},{fmt(py)}" for px, py in pts)


def treeline() -> str:
    back = "".join(f'<polygon points="{pine(x, h, w, HORIZON)}"/>' for x, h, w in tree_layer(48, 13, 52, 26))
    front = "".join(f'<polygon points="{pine(x, h, w, HORIZON)}"/>' for x, h, w in tree_layer(34, 29, 68, 34))
    return f'<g fill="#16002a" opacity="0.85">{back}</g>\n<g fill="#08000f">{front}</g>'


def grid() -> tuple[str, str]:
    """Cyan perspective floor; horizontal lines roll toward the viewer."""
    parts = []
    for i in range(-14, 15):
        parts.append(f'<line x1="{fmt(W / 2 + i * 14)}" y1="{HORIZON}" '
                     f'x2="{fmt(W / 2 + i * 150)}" y2="{H}"/>')
    lines, period, far = 7, 0.9, 9.0
    frames = []
    for step in range(21):
        t = step / 20
        depth = far ** (1 - t)
        y = HORIZON + (H - HORIZON) / depth
        frames.append(f"{t * 100:.0f}%{{transform:translateY({y:.1f}px)}}")
    for k in range(lines):
        parts.append(f'<line class="h" x1="0" y1="0" x2="{W}" y2="0" '
                     f'style="animation-delay:-{k * period:.2f}s"/>')
        y = HORIZON + (H - HORIZON) / far ** (1 - (k + 0.5) / lines)
        parts.append(f'<line class="hs" x1="0" y1="{y:.1f}" x2="{W}" y2="{y:.1f}"/>')
    css = (f"@keyframes run{{{''.join(frames)}}}"
           f".h{{animation:run {lines * period:.2f}s linear infinite}}")
    return "\n".join(parts), css


# ── Terminal typewriter ────────────────────────────────────────────────────

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


def terminal(mono: Font, top: float) -> str:
    size, box_h = 20, 38
    baseline = top + 26
    prompt_d, prompt_w = mono.path(PROMPT, size, LEFT + 12, baseline)
    chevron_x = LEFT + 12 + prompt_w + 2
    text_x = chevron_x + mono.advance(" ", size) * 2
    adv = mono.advance("M", size)
    events, total = typing_timeline()

    out = []
    times = [0] + [t for t, _, _ in events]
    counts = [0] + [n for _, _, n in events]
    widths = [fmt(12 + (text_x - LEFT - 12) + n * adv + 4 + 14) for n in counts]
    cursor_xs = [fmt(text_x + n * adv + 2) for n in counts]

    out.append(f'<rect x="{LEFT}" y="{top}" height="{box_h}" width="{widths[0]}" rx="4" '
               f'fill="{CYAN}" fill-opacity="0.04">{discrete("width", widths, times, total)}</rect>')
    out.append(f'<rect x="{LEFT}" y="{top}" width="2" height="{box_h}" fill="{CYAN}" fill-opacity="0.4"/>')
    out.append(f'<path d="{prompt_d}" fill="{PROMPT_COL}"/>')
    cy = baseline - 7
    out.append(f'<path d="M{fmt(chevron_x)} {fmt(cy - 6)} l6 6 l-6 6" fill="none" stroke="{PROMPT_COL}" '
               f'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>')

    for i, line in enumerate(LINES):
        d, _ = mono.path(line, size, text_x, baseline)
        line_times, line_widths, last = [0], ["0"], "0"
        for t, li, n in events:
            w = fmt(n * adv) if li == i else "0"
            if w != last:
                line_times.append(t)
                line_widths.append(w)
                last = w
        out.append(f'<clipPath id="type{i}"><rect x="{fmt(text_x)}" y="{top}" height="{box_h}" '
                   f'width="0">{discrete("width", line_widths, line_times, total)}</rect></clipPath>')
        out.append(f'<path d="{d}" fill="{CYAN}" clip-path="url(#type{i})"/>')

    out.append(f'<rect x="{cursor_xs[0]}" y="{fmt(baseline - 15)}" width="2" height="16" fill="{CYAN}">'
               f'{discrete("x", cursor_xs, times, total)}'
               f'<animate attributeName="opacity" calcMode="discrete" values="1;0" keyTimes="0;0.5" '
               f'dur="{2 * BLINK_MS / 1000:.2f}s" repeatCount="indefinite"/></rect>')
    return "\n".join(out)


# ── Assemble ───────────────────────────────────────────────────────────────

def build(font_dir: Path) -> str:
    orbitron = find_font(font_dir, "orbitron-latin-900-normal.woff2")
    mono = find_font(font_dir, "GeistMono-Regular.woff2")
    sans = find_font(font_dir, "Geist-Regular.woff2")

    name_size = 94
    tracking = -0.025 * name_size  # Tailwind tracking-tight
    line1, _ = orbitron.path(NAME[0], name_size, LEFT, 40 + 0.72 * name_size, tracking)
    line2, _ = orbitron.path(NAME[1], name_size, LEFT, 40 + 1.72 * name_size, tracking)
    tagline, _ = sans.path(TAGLINE, 20, LEFT, 326)
    grid_svg, grid_css = grid()

    # The site's .gradient-text is 135deg across the full-width heading box.
    box_x, box_y, box_w, box_h = LEFT, 40, W - 2 * LEFT, 2 * name_size
    half = (box_w + box_h) * 0.7071 / 2
    cx, cy = box_x + box_w / 2, box_y + box_h / 2
    g = (cx - half * .7071, cy - half * .7071, cx + half * .7071, cy + half * .7071)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<title>Markus Weldon · Principal Solutions Engineer</title>
<style>
@keyframes twinkle{{0%,100%{{opacity:1;transform:scale(1)}}50%{{opacity:.08;transform:scale(.4)}}}}
.star{{fill:#fff;transform-box:fill-box;transform-origin:center;animation:twinkle 4s ease-in-out infinite}}
@keyframes pulse{{0%,100%{{opacity:.55}}50%{{opacity:1}}}}
.horizon{{animation:pulse 5s ease-in-out infinite}}
{grid_css}
.hs{{display:none}}
@media (prefers-reduced-motion: reduce){{.star,.horizon,.h{{animation:none}}.h{{display:none}}.hs{{display:inline}}}}
</style>
<defs>
  <clipPath id="panel"><rect width="{W}" height="{H}" rx="16"/></clipPath>
  <clipPath id="floor"><rect y="{HORIZON}" width="{W}" height="{H - HORIZON}"/></clipPath>
  <radialGradient id="skyGlow" cx="0.5" cy="0" r="0.5" gradientTransform="translate(0.5 0) scale(0.8 0.45) translate(-0.5 0)">
    <stop offset="0" stop-color="#7b2fff" stop-opacity="0.16"/><stop offset="1" stop-color="#7b2fff" stop-opacity="0"/>
  </radialGradient>
  <radialGradient id="aura" cx="0.5" cy="0.9" r="0.6">
    <stop offset="0" stop-color="{PINK}" stop-opacity="0.3"/><stop offset="0.35" stop-color="#b01fff" stop-opacity="0.18"/>
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
    <stop offset="0.7" stop-color="#b01fff"/><stop offset="1" stop-color="{CYAN}"/>
  </linearGradient>
  <linearGradient id="border" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="{PINK}"/><stop offset="0.5" stop-color="#b01fff"/><stop offset="1" stop-color="{CYAN}"/>
  </linearGradient>
  <filter id="blur28" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="28"/></filter>
  <filter id="lineGlow" x="-5%" y="-800%" width="110%" height="1700%"><feGaussianBlur stdDeviation="8"/></filter>
  <filter id="starGlow" x="-200%" y="-200%" width="500%" height="500%">
    <feGaussianBlur stdDeviation="2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
</defs>
<g clip-path="url(#panel)">
<rect width="{W}" height="{H}" fill="{BG}"/>
<rect width="{W}" height="{H}" fill="url(#skyGlow)"/>
{stars()}
<ellipse cx="680" cy="{HORIZON - 30}" rx="330" ry="170" fill="url(#aura)" filter="url(#blur28)"/>
<g clip-path="url(#floor)" stroke="{CYAN}" stroke-opacity="0.35" stroke-width="1">
{grid_svg}
</g>
<rect y="{HORIZON}" width="{W}" height="{H - HORIZON}" fill="url(#floorFade)"/>
{treeline()}
<g class="horizon">
<rect y="{HORIZON - 1}" width="{W}" height="3" fill="url(#horizonLine)" filter="url(#lineGlow)"/>
<rect y="{HORIZON - 1}" width="{W}" height="3" fill="url(#horizonLine)"/>
</g>
<path d="{line1} {line2}" fill="url(#nameFill)"/>
{terminal(mono, 236)}
<path d="{tagline}" fill="{TEXT_2}"/>
</g>
<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="15.5" fill="none" stroke="url(#border)" stroke-opacity="0.45"/>
</svg>
"""


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    out = ROOT / "images/header.svg"
    out.write_text(build(Path(sys.argv[1])))
    print(f"Wrote {out} ({out.stat().st_size / 1024:.0f} KB)")
