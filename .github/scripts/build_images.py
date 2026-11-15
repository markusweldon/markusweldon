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

import sys
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
        self.sans = load("Geist-Regular.woff2")
        self.sans_medium = load("Geist-Medium.woff2")
        self.sans_semibold = load("Geist-SemiBold.woff2")
        self.mono = load("GeistMono-Regular.woff2")
        self.mono_semibold = load("GeistMono-SemiBold.woff2")


def svg(width: float, height: float, body: str, title: str = "") -> str:
    t = f"<title>{title}</title>\n" if title else ""
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


def stars() -> str:
    """The site's deterministic starfield (Hero.tsx STARS_REG / STARS_BRIGHT)."""
    out = []
    for i in range(48):
        x, y = (i * 137.508) % 100, (i * 97.314) % 50
        size = 3 if i % 5 == 0 else 2 if i % 3 == 0 else 1.5
        op = 0.45 + ((i * 71) % 37) / 100
        dur, delay = 4 + (i % 9) * 0.4, (i * 0.47) % 5.5
        out.append(f'<g opacity="{op:.2f}"><circle class="star" cx="{fmt(x * HW / 100)}" '
                   f'cy="{fmt(y * HORIZON / 100)}" r="{size / 2}" '
                   f'style="animation-duration:{dur:.1f}s;animation-delay:{delay:.1f}s"/></g>')
    for i in range(6):
        x, y = (i * 173.12 + 17) % 100, (i * 61.7 + 8) % 45
        size = 3.5 + (i % 3)
        op = 0.75 + ((i * 31) % 20) / 100
        dur, delay = 5 + (i % 4) * 0.7, (i * 1.3) % 4
        out.append(f'<g opacity="{op:.2f}"><circle class="star" cx="{fmt(x * HW / 100)}" '
                   f'cy="{fmt(y * HORIZON / 100)}" r="{size / 2}" filter="url(#starGlow)" '
                   f'style="animation-duration:{dur:.1f}s;animation-delay:{delay:.1f}s"/></g>')
    return "\n".join(out)


def tree_layer(count: int, seed: int, max_h: float, min_h: float):
    """Hero.tsx treeLayer(): pines thin out toward the centre."""
    for i in range(count):
        x = (i + 0.5) * (1200 / count) + (((i * seed) % 17) - 8)
        centre = abs(x - 600) / 600
        h = (min_h + ((i * seed * 7) % (max_h - min_h))) * (0.45 + 0.55 * centre)
        yield x * HW / 1200, h, h * 0.55


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
        parts.append(f'<line x1="{fmt(HW / 2 + i * 14)}" y1="{HORIZON}" '
                     f'x2="{fmt(HW / 2 + i * 150)}" y2="{HH}"/>')
    lines, period, far = 7, 0.9, 9.0
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


def terminal(f: Fonts, top: float) -> str:
    mono, size, box_h = f.mono, 20, 38
    baseline = top + 26
    prompt_d, prompt_w = mono.path(PROMPT, size, LEFT + 12, baseline)
    chevron_x = LEFT + 12 + prompt_w + 2
    text_x = chevron_x + mono.advance(" ", size) * 2
    adv = mono.advance("M", size)
    events, total = typing_timeline()

    times = [0] + [t for t, _, _ in events]
    counts = [0] + [n for _, _, n in events]
    widths = [fmt(text_x - LEFT + n * adv + 18) for n in counts]
    cursor_xs = [fmt(text_x + n * adv + 2) for n in counts]

    out = [
        f'<rect x="{LEFT}" y="{top}" height="{box_h}" width="{widths[0]}" rx="4" '
        f'fill="{CYAN}" fill-opacity="0.04">{discrete("width", widths, times, total)}</rect>',
        f'<rect x="{LEFT}" y="{top}" width="2" height="{box_h}" fill="{CYAN}" fill-opacity="0.4"/>',
        f'<path d="{prompt_d}" fill="{PROMPT_COL}"/>',
        f'<path d="M{fmt(chevron_x)} {fmt(baseline - 13)} l6 6 l-6 6" fill="none" stroke="{PROMPT_COL}" '
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
        out.append(f'<clipPath id="type{i}"><rect x="{fmt(text_x)}" y="{top}" height="{box_h}" '
                   f'width="0">{discrete("width", line_widths, line_times, total)}</rect></clipPath>')
        out.append(f'<path d="{d}" fill="{CYAN}" clip-path="url(#type{i})"/>')
    out.append(f'<rect x="{cursor_xs[0]}" y="{fmt(baseline - 15)}" width="2" height="16" fill="{CYAN}">'
               f'{discrete("x", cursor_xs, times, total)}'
               f'<animate attributeName="opacity" calcMode="discrete" values="1;0" keyTimes="0;0.5" '
               f'dur="{2 * BLINK_MS / 1000:.2f}s" repeatCount="indefinite"/></rect>')
    return "\n".join(out)


def location(f: Fonts, baseline: float) -> str:
    """'Brit builder · (pin) Lake Oswego, Oregon' in the site's dim mono."""
    size, colour, x = 15, PROMPT_COL, LEFT
    out = []
    d, w = f.mono.path(f"{LOCATION[0]} · ", size, x, baseline)
    out.append(f'<path d="{d}" fill="{colour}"/>')
    x += w + 2
    out.append(icon("map-pin", x, baseline - 13, 15, colour, 2.2))
    x += 21
    d, w = f.mono.path(LOCATION[1], size, x, baseline)
    out.append(f'<path d="{d}" fill="{colour}"/>')
    return "\n".join(out)


def header(f: Fonts) -> str:
    name_size = 94
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
    tagline, _ = f.sans.path(TAGLINE, 20, LEFT, 347)
    grid_svg, grid_css = grid()

    # The site's .gradient-text is 135deg across the full-width heading box.
    box_w, box_h = HW - 2 * LEFT, 2 * name_size
    half = (box_w + box_h) * 0.7071 / 2
    cx, cy = LEFT + box_w / 2, top + box_h / 2
    g = (cx - half * .7071, cy - half * .7071, cx + half * .7071, cy + half * .7071)

    body = f"""<style>
@keyframes twinkle{{0%,100%{{opacity:1;transform:scale(1)}}50%{{opacity:.08;transform:scale(.4)}}}}
.star{{fill:#fff;transform-box:fill-box;transform-origin:center;animation:twinkle 4s ease-in-out infinite}}
@keyframes pulse{{0%,100%{{opacity:.55}}50%{{opacity:1}}}}
.horizon{{animation:pulse 5s ease-in-out infinite}}
{grid_css}
.hs{{display:none}}
@media (prefers-reduced-motion: reduce){{.star,.horizon,.h{{animation:none}}.h{{display:none}}.hs{{display:inline}}}}
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
  <filter id="lineGlow" x="-5%" y="-800%" width="110%" height="1700%"><feGaussianBlur stdDeviation="8"/></filter>
  <filter id="starGlow" x="-200%" y="-200%" width="500%" height="500%">
    <feGaussianBlur stdDeviation="2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
</defs>
<g clip-path="url(#panel)">
<rect width="{HW}" height="{HH}" fill="{BG}"/>
<rect width="{HW}" height="{HH}" fill="url(#skyGlow)"/>
{stars()}
<ellipse cx="680" cy="{HORIZON - 30}" rx="330" ry="170" fill="url(#aura)" filter="url(#blur28)"/>
<g clip-path="url(#floor)" stroke="{CYAN}" stroke-opacity="0.35" stroke-width="1">
{grid_svg}
</g>
<rect y="{HORIZON}" width="{HW}" height="{HH - HORIZON}" fill="url(#floorFade)"/>
{treeline()}
<g class="horizon">
<rect y="{HORIZON - 1}" width="{HW}" height="3" fill="url(#horizonLine)" filter="url(#lineGlow)"/>
<rect y="{HORIZON - 1}" width="{HW}" height="3" fill="url(#horizonLine)"/>
</g>
<path d="{line1} {line2}" fill="url(#nameFill)"/>
{terminal(f, 255)}
<path d="{tagline}" fill="{TEXT_2}"/>
{location(f, 381)}
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


def pill(f: Fonts, x: float, y: float, text: str, dot: str | None = None) -> tuple[str, float]:
    """The site's tag pill: text-xs, purple tint, rounded-full."""
    size, h = 12, 22
    tx = x + 9 + (12 if dot else 0)
    d, w = f.sans.path(text, size, tx, y + 15)
    width = (tx - x) + w + 9
    out = (f'<rect x="{fmt(x + .5)}" y="{fmt(y + .5)}" width="{fmt(width - 1)}" height="{h - 1}" rx="{h / 2 - .5}" '
           f'fill="{PURPLE}" fill-opacity="0.08" stroke="{PURPLE}" stroke-opacity="0.2"/>')
    if dot:
        out += f'<circle cx="{fmt(x + 13)}" cy="{fmt(y + h / 2)}" r="3.5" fill="{dot}"/>'
    out += f'<path d="{d}" fill="{LAVENDER}"/>'
    return out, width


def card(f: Fonts, title: str, desc: str, lang: str, lang_colour: str, topic: str) -> str:
    # globals.css .section-grid: faint cyan rows and purple columns.
    out = [f'<defs><pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse" x="{PAD}" y="0">'
           f'<rect y="29" width="30" height="1" fill="{CYAN}" fill-opacity="0.09"/>'
           f'<rect x="29" width="1" height="30" fill="{PURPLE}" fill-opacity="0.1"/></pattern>'
           f'<radialGradient id="glow" cx="1" cy="0" r="0.9"><stop offset="0" stop-color="{PINK}" stop-opacity="0.12"/>'
           f'<stop offset="1" stop-color="{PINK}" stop-opacity="0"/></radialGradient>'
           f'<clipPath id="c"><rect width="{CW}" height="{CH}" rx="16"/></clipPath></defs>',
           f'<rect width="{CW}" height="{CH}" rx="16" fill="{SURFACE}"/>',
           f'<g clip-path="url(#c)"><rect width="{CW}" height="{CH}" fill="url(#grid)"/>'
           f'<rect width="{CW}" height="{CH}" fill="url(#glow)"/></g>',
           f'<rect x="0.5" y="0.5" width="{CW - 1}" height="{CH - 1}" rx="15.5" fill="none" '
           f'stroke="{PINK}" stroke-opacity="0.3"/>',
           f'<path transform="translate({PAD} {PAD})" d="{OCTOCAT}" fill="{PINK}"/>']
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
    outputs = {"header.svg": header(f)}
    for repo, *details in CARDS:
        outputs[f"card-{repo}.svg"] = card(f, *details)
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
