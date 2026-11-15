#!/usr/bin/env python3
"""Build images/header.svg: the synthwave hero at the top of the README.

The name, title and tagline are drawn as SVG paths, because GitHub shows the
README's SVGs as images and an image cannot load web fonts. Outlining the text
makes it look the same for every visitor.

The terminal typing line is copied from images/typing-focus.svg, so edit the
typing text there and re-run this script.

Usage:
    pip install fonttools brotli
    npm pack @fontsource/orbitron@5.0.19 @fontsource/exo-2@5.0.19
    (extract both tarballs into one folder, then)
    python3 .github/scripts/build_header.py <folder-with-the-extracted-packages>
"""

import math
import random
import re
import sys
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[2]
NAME = "MARKUS WELDON"
TITLE = "PRINCIPAL SOLUTIONS ENGINEER"
TAGLINE = "Helping enterprises adopt AI-assisted development securely"

W, H = 1000, 480
HORIZON = 330
SUN_R = 128
CX = W / 2


def find_font(font_dir: Path, family: str, weight: int) -> Path:
    name = f"{family}-latin-{weight}-normal.woff2"
    hits = list(font_dir.rglob(name))
    if not hits:
        sys.exit(f"Font not found: {name} under {font_dir}")
    return hits[0]


def text_path(font_file: Path, text: str, size: float, baseline: float,
              tracking: float = 0.0) -> tuple[str, float]:
    """Outline `text` centred on CX with its baseline at `baseline`."""
    font = TTFont(font_file)
    glyphs = font.getGlyphSet()
    cmap = font.getBestCmap()
    scale = size / font["head"].unitsPerEm
    names = [cmap[ord(c)] for c in text]
    advances = [glyphs[n].width * scale + tracking for n in names]
    width = sum(advances) - tracking
    x = CX - width / 2
    pen = SVGPathPen(glyphs, ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip("."))
    for name, adv in zip(names, advances):
        glyphs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, x, baseline)))
        x += adv
    return pen.getCommands(), width


def floor_y(depth: float) -> float:
    """Screen y of a floor line `depth` units away (1 = the bottom edge)."""
    return HORIZON + (H - HORIZON) / depth


def grid() -> tuple[str, str]:
    """Return (svg, css) for the perspective floor grid."""
    parts = []
    for i in range(-16, 17):
        x_far = CX + i * 7
        x_near = CX + i * 120
        parts.append(f'<line x1="{x_far:.1f}" y1="{HORIZON}" x2="{x_near:.1f}" y2="{H}"/>')
    # Horizontal lines move toward the viewer. Each line runs the full depth
    # range; staggered delays make the loop seamless.
    lines, period, far = 9, 1.1, 10.0
    dur = lines * period
    frames = []
    for step in range(21):
        t = step / 20
        depth = far ** (1 - t)  # even spacing in log depth reads as steady motion
        y = floor_y(depth)
        alpha = min(1.0, (y - HORIZON) / 40)
        frames.append(f"{t * 100:.0f}%{{transform:translateY({y:.1f}px);opacity:{alpha:.2f}}}")
    for k in range(lines):
        parts.append(f'<line class="h" x1="0" y1="0" x2="{W}" y2="0" '
                     f'style="animation-delay:-{k * period:.2f}s"/>')
        # Static copy, shown only when the viewer prefers reduced motion.
        y = floor_y(far ** (1 - (k + 0.5) / lines))
        parts.append(f'<line class="hs" x1="0" y1="{y:.1f}" x2="{W}" y2="{y:.1f}"/>')
    css = (f"@keyframes run{{{''.join(frames)}}}"
           f".h{{animation:run {dur:.2f}s linear infinite;opacity:0}}")
    return "\n".join(parts), css


def stars() -> str:
    rng = random.Random(84)
    out = []
    for i in range(70):
        x, y = rng.uniform(12, W - 12), rng.uniform(10, HORIZON - 70)
        r = rng.choice([0.6, 0.8, 1.0, 1.3])
        cls = f' class="tw" style="animation-delay:-{rng.uniform(0, 4):.1f}s"' if i % 5 == 0 else ""
        out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r}" opacity="{rng.uniform(.35, .9):.2f}"{cls}/>')
    return "\n".join(out)


def mountains() -> str:
    def ridge(points, fill, stroke, opacity):
        pts = " ".join(f"{x},{y}" for x, y in points)
        return (f'<polygon points="0,{HORIZON} {pts} {W},{HORIZON}" fill="{fill}" '
                f'stroke="{stroke}" stroke-width="1.4" stroke-opacity="{opacity}" stroke-linejoin="round"/>')
    back = [(0, 300), (70, 262), (130, 290), (205, 238), (290, 296), (345, 276), (400, 312),
            (600, 312), (650, 270), (720, 296), (790, 236), (865, 288), (930, 258), (1000, 292)]
    front = [(0, 318), (60, 298), (120, 316), (170, 290), (240, 322), (300, 326),
             (700, 326), (760, 318), (820, 284), (880, 314), (940, 300), (1000, 316)]
    return ridge(back, "#292138", "#D33D9B", 0.7) + "\n" + ridge(front, "#1E1829", "#6DE2F1", 0.5)


def sun() -> str:
    top = HORIZON - SUN_R
    gaps = []
    # Classic striped sun: the cuts thicken as they near the horizon.
    for i, frac in enumerate([0.44, 0.56, 0.66, 0.75, 0.83, 0.90, 0.96]):
        y = top + frac * SUN_R * 1.05
        gaps.append(f'<rect x="0" y="{y:.1f}" width="{W}" height="{1.6 + i * 1.5:.1f}" fill="#000"/>')
    return f"""<mask id="stripes"><rect width="{W}" height="{H}" fill="#fff"/>{''.join(gaps)}</mask>
<circle cx="{CX}" cy="{HORIZON}" r="{SUN_R + 40}" fill="url(#sunGlow)"/>
<circle cx="{CX}" cy="{HORIZON}" r="{SUN_R}" fill="url(#sunFill)" mask="url(#stripes)" clip-path="url(#sky)"/>"""


def terminal() -> str:
    src = (ROOT / "images/typing-focus.svg").read_text()
    inner = re.search(r"<svg[^>]*>(.*)</svg>", src, re.S).group(1)
    inner = inner.replace('fill="#292138" stroke="#3a3350"',
                          'fill="#292138" fill-opacity="0.9" stroke="#6DE2F1" stroke-opacity="0.5"')
    return f'<svg x="180" y="394" width="640" height="72" viewBox="0 0 640 72">{inner}</svg>'


def build(font_dir: Path) -> str:
    name_d, _ = text_path(find_font(font_dir, "orbitron", 900), NAME, 66, 104, tracking=4)
    title_d, _ = text_path(find_font(font_dir, "orbitron", 600), TITLE, 19, 146, tracking=6.5)
    tag_d, _ = text_path(find_font(font_dir, "exo-2", 600), TAGLINE, 25, 184, tracking=0.4)
    grid_svg, grid_css = grid()
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<title>Markus Weldon · Principal Solutions Engineer</title>
<style>
{grid_css}
@keyframes twinkle{{0%,100%{{opacity:.9}}50%{{opacity:.15}}}}
.tw{{animation:twinkle 4s ease-in-out infinite}}
@keyframes flicker{{0%,90%,94%,100%{{opacity:1}}91%{{opacity:.55}}92%{{opacity:1}}93%{{opacity:.75}}}}
.name{{animation:flicker 7s linear infinite}}
.hs{{display:none}}
@media (prefers-reduced-motion: reduce){{.h,.tw,.name{{animation:none}}.h{{display:none}}.hs{{display:inline}}}}
</style>
<defs>
  <clipPath id="panel"><rect width="{W}" height="{H}" rx="18"/></clipPath>
  <clipPath id="sky"><rect width="{W}" height="{HORIZON}"/></clipPath>
  <clipPath id="floor"><rect y="{HORIZON}" width="{W}" height="{H - HORIZON}"/></clipPath>
  <linearGradient id="skyFill" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#15101F"/><stop offset="0.55" stop-color="#292138"/>
    <stop offset="1" stop-color="#4A2552"/>
  </linearGradient>
  <linearGradient id="floorFill" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#3A2650"/><stop offset="1" stop-color="#15101F"/>
  </linearGradient>
  <linearGradient id="sunFill" gradientUnits="userSpaceOnUse" x1="0" y1="{HORIZON - SUN_R}" x2="0" y2="{HORIZON}">
    <stop offset="0" stop-color="#FF4FC3"/><stop offset="0.45" stop-color="#D33D9B"/>
    <stop offset="0.8" stop-color="#A06BFF"/><stop offset="1" stop-color="#8957E5"/>
  </linearGradient>
  <linearGradient id="haze" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#3A2650" stop-opacity="0.95"/><stop offset="1" stop-color="#3A2650" stop-opacity="0"/>
  </linearGradient>
  <radialGradient id="sunGlow">
    <stop offset="0.7" stop-color="#D33D9B" stop-opacity="0.4"/><stop offset="1" stop-color="#D33D9B" stop-opacity="0"/>
  </radialGradient>
  <linearGradient id="neon" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#D33D9B"/><stop offset="0.5" stop-color="#8957E5"/><stop offset="1" stop-color="#6DE2F1"/>
  </linearGradient>
  <linearGradient id="chrome" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#FFFFFF"/><stop offset="0.48" stop-color="#E9DDFF"/>
    <stop offset="0.52" stop-color="#FF4FC3"/><stop offset="1" stop-color="#FFB3E6"/>
  </linearGradient>
  <filter id="glow" x="-10%" y="-40%" width="120%" height="180%">
    <feGaussianBlur stdDeviation="5" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <filter id="softGlow" x="-5%" y="-50%" width="110%" height="200%">
    <feGaussianBlur stdDeviation="2.5" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse">
    <rect width="4" height="1" fill="#000" fill-opacity="0.18"/>
  </pattern>
</defs>
<g clip-path="url(#panel)">
<rect width="{W}" height="{HORIZON}" fill="url(#skyFill)"/>
<g fill="#FFFFFF">
{stars()}
</g>
{sun()}
{mountains()}
<rect y="{HORIZON}" width="{W}" height="{H - HORIZON}" fill="url(#floorFill)"/>
<g clip-path="url(#floor)" stroke="#D33D9B" stroke-width="1.6" stroke-opacity="0.9" filter="url(#softGlow)">
{grid_svg}
</g>
<rect y="{HORIZON}" width="{W}" height="34" fill="url(#haze)"/>
<line x1="0" y1="{HORIZON}" x2="{W}" y2="{HORIZON}" stroke="#6DE2F1" stroke-width="2" filter="url(#softGlow)"/>
<g class="name">
<path d="{name_d}" fill="url(#neon)" filter="url(#glow)" opacity="0.9"/>
<path d="{name_d}" fill="url(#chrome)" stroke="#D33D9B" stroke-width="0.8"/>
</g>
<path d="{title_d}" fill="#FF4FC3" filter="url(#softGlow)"/>
<path d="{tag_d}" fill="#6DE2F1" filter="url(#softGlow)"/>
{terminal()}
<rect width="{W}" height="{H}" fill="url(#scan)" pointer-events="none"/>
</g>
<rect x="0.75" y="0.75" width="{W - 1.5}" height="{H - 1.5}" rx="17.5" fill="none" stroke="url(#neon)" stroke-width="1.5" stroke-opacity="0.8"/>
</svg>
"""


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    out = ROOT / "images/header.svg"
    out.write_text(build(Path(sys.argv[1])))
    print(f"Wrote {out} ({out.stat().st_size / 1024:.0f} KB)")
