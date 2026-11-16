"""Restyle the metrics isocalendar as a neon skyline.

Run after cap_isocalendar.py. GitHub colours each day by a quartile of the
year, so neighbouring towers jump between unrelated colours. This colours
each tower by its height instead (dim violet for quiet days, through purple
and pink, with cyan kept for the tallest days), puts a soft glow on those
peaks, and sets the calendar on a cyan isometric grid floor with a pink glow
underneath, like the header's horizon. Towers rise into place once when the
image loads; visitors who prefer reduced motion see them already standing.

Each tower is drawn as a lit building: its sides fade from its colour to deep
violet at the base, its top face and front edge glow, taller towers get rows
of lit cyan and pink windows, and the peak days carry a glowing beacon.

The calendar sits on a cyan isometric grid floor; the buildings are
mirrored into it like a wet street, and a pink-to-cyan horizon line with a
soft glow runs behind the far end of the city.

It also swaps the languages section's "estimation from 3.74mb of code in
1327 edited files across 204 commits" line for a generic caption.

Usage: skyline_isocalendar.py <in.svg> <out.svg>
If the calendar can't be found, the input is copied unchanged and a warning
is printed, so the card still publishes.
"""
import base64
import json
import math
import random
import re
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

SIZE = 6  # the plugin's full tower height
NUM = r"(-?\d+(?:\.\d+)?(?:e-?\d+)?)"
ANCHOR = '<g transform="scale(4) translate(12, 0)">'
GROUP = re.compile(r'<g transform="translate\(' + NUM + r", " + NUM + r'\)">')
CELL = re.compile(
    r'<g transform="translate\(' + NUM + r", " + NUM + r'\)">(\s*)'
    r'(<path fill=")(#[0-9a-fA-F]+)(" d="M1\.7,2 0,1 1\.7,0 3\.4,1 z"/>\s*'
    r'<path fill=")\5(" filter="url\(#brightness1\)" d="M0,1 1\.7,2 1\.7,' + NUM + r' 0,[^"]*"/>\s*'
    r'<path fill=")\5(" filter="url\(#brightness2\)" d="[^"]*"/>)'
)

EMPTY = "#2a0f4d"  # a day with no contributions: a dim floor tile
PEAK = "#36f9f6"   # the tallest days
PEAK_FROM = 0.8    # share of full height that counts as a peak (24 of a 30 cap)
# Most days are well under the cap, so the ramp reaches pink early.
RAMP = [(0.0, "#3d1670"), (0.15, "#7b2fff"), (0.35, "#b01fff"), (0.55, "#f92aad"), (0.8, "#ff6ec7")]


def mix(a, b, t):
    pa = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    pb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(pa, pb))


def colour(t):
    if t <= 0:
        return EMPTY
    if t >= PEAK_FROM:
        return PEAK
    for (t0, c0), (t1, c1) in zip(RAMP, RAMP[1:]):
        if t <= t1:
            return mix(c0, c1, (t - t0) / (t1 - t0))
    return RAMP[-1][1]


def fmt(x):
    return f"{x:.3f}".rstrip("0").rstrip(".")


GRADS = {}  # (colour, side) -> (gradient id, top colour)
WINDOWS = ["#36f9f6", "#ffd6f5", "#ff6ec7", "#8afcfa"]
WINDOWS_FROM = 0.37  # share of the cap (about 11 of 30 contributions) that gets lit windows

# Tower heights: a gentle power curve spreads quiet days apart while
# the busiest stay tallest, and MAX_HEIGHT makes the city half as tall again
# as the plugin's cubes (SIZE).
MAX_HEIGHT = 9.0


HEIGHT_CURVE = 0.7  # 1 is linear; lower lifts quiet days more


def height(t):
    return MAX_HEIGHT * t ** HEIGHT_CURVE


def shade(hexcol, k):
    r, g, b = (int(hexcol[i:i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{max(0, min(255, round(v * k))):02x}" for v in (r, g, b))


def side(col, face):
    """Id of a gradient that fades a side face from its colour to deep violet."""
    key = (col, face)
    if key not in GRADS:
        GRADS[key] = (f"mws-g{len(GRADS)}", shade(col, 0.82 if face == "l" else 0.5))
    return GRADS[key][0]


def side_defs():
    return "".join(
        f'<linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{top}"/>'
        f'<stop offset="1" stop-color="{"#1d0838" if face == "l" else "#12041f"}"/></linearGradient>'
        for (_, face), (gid, top) in GRADS.items())


# Optional effects; set either to False to switch it off.
CAR = True          # a roadster driving along a road in front of the city
REFLECTION = False  # buildings mirrored into the grid floor, like a wet street
HORIZON = False     # a pink-to-cyan line and glow behind the far end of the city
HORIZON_GAP = 1.6    # clear space between the horizon and the tallest tower under it
TEXT_COLUMN = 455    # card x where the streak figures start; the horizon stops before it
CALENDAR_DROP = 30   # px the calendar moves down into the card's empty lower edge

RGRADS = {}  # (colour, side) -> reflection gradient id


def rgrad(col, face):
    """Id of a gradient that fades a reflected side face out downwards."""
    key = (col, face)
    if key not in RGRADS:
        RGRADS[key] = f"mws-r{len(RGRADS)}"
    return RGRADS[key]


def rgrad_defs():
    return "".join(
        f'<linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{shade(col, 0.8 if face == "l" else 0.5)}" stop-opacity="0.9"/>'
        f'<stop offset="0.95" stop-color="{col}" stop-opacity="0"/></linearGradient>'
        for (col, face), gid in RGRADS.items())


def tower(col, h, peak, seed, windows):
    """One day as a lit building. Coordinates follow the plugin's cube paths."""
    if h <= 0:
        return f'<path fill="{col}" d="M1.7,2 0,1 1.7,0 3.4,1 z" stroke="#36f9f6" stroke-opacity="0.12" stroke-width="0.05"/>'
    top, edge = mix(col, "#ffffff", 0.1), mix(col, "#ffffff", 0.45)
    b2, b1 = fmt(2 + h), fmt(1 + h)
    parts = [
        f'<path fill="url(#{side(col, "l")})" d="M0,1 1.7,2 1.7,{b2} 0,{b1} z"/>',
        f'<path fill="url(#{side(col, "r")})" d="M1.7,2 3.4,1 3.4,{b1} 1.7,{b2} z"/>',
        f'<path fill="{top}" d="M1.7,2 0,1 1.7,0 3.4,1 z" stroke="{edge}" stroke-width="0.07" stroke-linejoin="round"/>',
        f'<path d="M1.7,2 1.7,{b2}" stroke="{edge}" stroke-opacity="0.55" stroke-width="0.06"/>',
    ]
    if windows:
        rng = random.Random(seed)  # the same windows for the same spot
        for face in ("l", "r"):
            for u in (0.32, 0.68):
                x = 1.7 * u if face == "l" else 1.7 + 1.7 * u
                y0 = (1 + u) if face == "l" else (2 - u)
                dy = 0.165 if face == "l" else -0.165
                y = y0 + 0.55
                while y < y0 + h - 0.35:
                    if rng.random() < 0.62:
                        parts.append(f'<path fill="{rng.choice(WINDOWS)}" fill-opacity="{0.9 if face == "l" else 0.55}" '
                                     f'd="M{x - 0.14:.2f},{y:.2f} l0.28,{dy:.3f} l0,0.24 l-0.28,{-dy:.3f} z"/>')
                    y += 0.62
    if peak:
        parts.append('<path d="M1.7,1 1.7,-0.4" stroke="#8afcfa" stroke-width="0.06"/>'
                     '<circle cx="1.7" cy="-0.6" r="0.22" fill="#36f9f6" filter="url(#mws-peak)"/>')
    return "".join(parts)


ASSETS = Path(__file__).resolve().parent / "assets"


def iso_car(corner, cols, rows) -> tuple[str, str]:
    """The header's roadster, rendered by render_roadster.py from the same 3D model in
    this calendar's isometric projection and embedded as a PNG. It drives
    along a road in front of the city towards the oldest weeks, tail to the
    viewer, with headlight beams ahead and pink streaks behind.
    Returns (svg, css); an empty svg if the render isn't there."""
    png, meta_file = ASSETS / "roadster-iso.png", ASSETS / "roadster.json"
    if not png.exists() or not meta_file.exists():
        return "", ""
    meta = json.loads(meta_file.read_text())["iso"]
    data = base64.b64encode(png.read_bytes()).decode()
    road = rows + 1.9            # day-axis centre of the road
    L = 2.4                      # car length in weeks (4.3 m at 0.558 per metre)
    ox, oy = corner(0, road)     # the car's nose on the road centreline

    def p(a, y):
        x, yy = corner(a, road + y)
        return f"{fmt(x)},{fmt(yy)}"

    floor = (
        f'<polygon points="{p(0, -0.45)} {p(-2.4, -0.85)} {p(-2.4, 0.85)} {p(0, 0.45)}" fill="url(#mws-beam)"/>'
        f'<polygon points="{p(-0.1, -0.62)} {p(L + 0.1, -0.62)} {p(L + 0.1, 0.62)} {p(-0.1, 0.62)}" fill="#000" fill-opacity="0.45"/>'
        + "".join(f'<line x1="{p(L, y).split(",")[0]}" y1="{fmt(float(p(L, y).split(",")[1]) - 0.4)}" '
                  f'x2="{p(L + 4, y).split(",")[0]}" y2="{fmt(float(p(L + 4, y).split(",")[1]) - 0.1)}" '
                  f'stroke="url(#mws-trail)" stroke-width="0.08" stroke-linecap="round"/>' for y in (-0.42, 0.42))
    )
    geom = (f'x="{fmt(ox + meta["x"])}" y="{fmt(oy + meta["y"])}" '
            f'width="{fmt(meta["w"])}" height="{fmt(meta["h"])}"')
    n = meta.get("frames", 0)
    files = [ASSETS / f"roadster-iso-{k}.png" for k in range(n)]
    if n > 1 and all(f.exists() for f in files):
        # Wheel frames shown in turn, so the wheels roll as the car drives.
        image = ""
        for k, f in enumerate(files):
            vals = ";".join("1" if j == k else "0" for j in range(n))
            b64 = base64.b64encode(f.read_bytes()).decode()
            image += (f'<image href="data:image/png;base64,{b64}" {geom} opacity="{1 if k == 0 else 0}">'
                      f'<animate attributeName="opacity" calcMode="discrete" values="{vals}" '
                      f'dur="{0.07 * n:.2f}s" repeatCount="indefinite"/></image>')
    else:
        image = f'<image href="data:image/png;base64,{data}" {geom}/>'

    def off(a):
        return corner(a, 0)[0] - corner(0, 0)[0], corner(a, 0)[1] - corner(0, 0)[1]
    (sx, sy), (ex, ey), (mx, my) = off(cols + 6), off(-8), off(cols * 0.45)
    css = (f"@keyframes mws-drive{{0%{{transform:translate({fmt(sx)}px,{fmt(sy)}px);opacity:0}}"
           f"6%{{opacity:1}}88%{{opacity:1}}"
           f"100%{{transform:translate({fmt(ex)}px,{fmt(ey)}px);opacity:0}}}}"
           f".mws-car{{animation:mws-drive 14s linear infinite}}"
           f"@media (prefers-reduced-motion: reduce){{.mws-car{{animation:none;transform:translate({fmt(mx)}px,{fmt(my)}px)}}}}")
    return f'<g class="mws-car">{floor}{image}</g>', css


def restyle(svg):
    start = svg.find(ANCHOR)
    if start < 0:
        return svg, "no isocalendar found"
    end = svg.find("</svg>", start)
    block = svg[start:end]

    cells, week, weeks, bases = [], None, 0, []
    absolute = []

    def visit(m):
        nonlocal week, weeks
        nxt = block[m.end():m.end() + 40].lstrip()
        x, y = float(m.group(1)), float(m.group(2))
        if not nxt.startswith("<path"):  # a week column
            week = (x, y)
            weeks += 1
            return
        c = CELL.match(block, m.start())
        if not c or week is None:
            return
        h = float(c.group(8)) - 2
        w, d = round(week[1]), round(-x / 1.7)
        bases.append(week[1] + y + h - w - d)
        cells.append((c, w, h))
        absolute.append((week[0] + x, week[1] + y))

    for m in GROUP.finditer(block):
        visit(m)
    if len(cells) < 300:  # a full year is about 365 days
        return svg, f"found only {len(cells)} day cells, left unchanged"

    out, pos, peaks, tops = [], 0, 0, []
    for c, w, h in cells:
        t = max(0.0, min(1.0, h / SIZE))
        col = colour(t)
        peak = t >= PEAK_FROM
        peaks += peak
        glow = ' filter="url(#mws-peak)"' if peak else ""
        out.append(block[pos:c.start()])
        d = round(-float(c.group(1)) / 1.7)
        tall = height(t)
        top = float(c.group(2)) + h - tall  # same base, new height
        tops.append((w, absolute[len(tops)][1] + h - tall))
        out.append(
            f'<g transform="translate({c.group(1)}, {fmt(top)})"{glow}>{c.group(3)}'
            f'<g class="mws-rise" style="animation-delay:{w * 14}ms">'
            f'{tower(col, tall, peak, w * 7 + d, t >= WINDOWS_FROM)}</g>'
        )
        pos = c.end()
    out.append(block[pos:])
    block = "".join(out)

    # The isometric floor: lattice corner (a, b) sits at (1.7(a - b) + 1.7, a + b + base).
    base = sum(bases) / len(bases)
    cols, rows = weeks, 7

    def corner(a, b):
        return 1.7 * (a - b) + 1.7, a + b + base

    lines = []
    for a in range(-4, cols + 5):
        (x1, y1), (x2, y2) = corner(a, -4), corner(a, rows + 4)
        lines.append(f'<line x1="{fmt(x1)}" y1="{fmt(y1)}" x2="{fmt(x2)}" y2="{fmt(y2)}"/>')
    for b in range(-4, rows + 5):
        (x1, y1), (x2, y2) = corner(-4, b), corner(cols + 4, b)
        lines.append(f'<line x1="{fmt(x1)}" y1="{fmt(y1)}" x2="{fmt(x2)}" y2="{fmt(y2)}"/>')
    cx, cy = corner(cols / 2, rows / 2)
    reflection_svg = ""
    if REFLECTION:
        refl = []
        for (c, w, h), (ax, ay) in zip(cells, absolute):
            if h <= 0.3:
                continue
            t = max(0.0, min(1.0, h / SIZE))
            col = colour(t)
            gl, gr = rgrad(col, "l"), rgrad(col, "r")
            f1, f2, d1, d2 = fmt(ay + 1 + h), fmt(ay + 2 + h), fmt(ay + 1 + 2 * h), fmt(ay + 2 + 2 * h)
            x0, x1, x2 = fmt(ax), fmt(ax + 1.7), fmt(ax + 3.4)
            refl.append(f'<path fill="url(#{gl})" d="M{x0},{f1} {x1},{f2} {x1},{d2} {x0},{d1} z"/>'
                        f'<path fill="url(#{gr})" d="M{x1},{f2} {x2},{f1} {x2},{d1} {x1},{d2} z"/>')
        reflection_svg = "".join(refl)
    # Centre the city: the plugin offsets it by a fixed 12 units, which leaves
    # it hugging the card's left edge.
    xmin = min(ax for ax, ay in absolute)
    xmax = max(ax for ax, ay in absolute) + 3.4
    tx = 60 - (xmin + xmax) / 2
    block = block.replace(ANCHOR, f'<g transform="scale(4) translate({fmt(tx)}, 0)">', 1)
    horizon_svg = ""
    if HORIZON:
        # Behind the far end of the city and above every tower it spans, so no
        # tower crosses it. The calendar is 920px wide for 480 units, scaled 4x.
        x0 = xmin - 8
        x1 = (TEXT_COLUMN - 20) / (920 / 480 * 4) - tx
        hy = min(top for (ax, ay), (w, top) in zip(absolute, tops) if ax < x1) - HORIZON_GAP
        mid, half = (x0 + x1) / 2, (x1 - x0) / 2
        horizon_svg = (
            f'<ellipse cx="{fmt(mid - 4)}" cy="{fmt(hy)}" rx="{fmt(half + 6)}" ry="9" fill="url(#mws-aura)" filter="url(#mws-blur)"/>'
            f'<rect x="{fmt(x0)}" y="{fmt(hy - 0.4)}" width="{fmt(x1 - x0)}" height="0.8" fill="url(#mws-hz)" filter="url(#mws-hzglow)"/>'
            f'<rect x="{fmt(x0)}" y="{fmt(hy - 0.13)}" width="{fmt(x1 - x0)}" height="0.26" fill="url(#mws-hz)"/>')
    floor = f"""<style>
@keyframes mws-rise{{from{{transform:scaleY(0)}}to{{transform:scaleY(1)}}}}
.mws-rise{{transform-box:fill-box;transform-origin:50% 100%;animation:mws-rise .9s cubic-bezier(.2,.8,.2,1) both}}
@media (prefers-reduced-motion: reduce){{.mws-rise{{animation:none}}}}
</style>
<defs>
{side_defs()}{rgrad_defs()}
  <radialGradient id="mws-aura" cx="0.5" cy="0.85" r="0.6"><stop offset="0" stop-color="#f92aad" stop-opacity="0.45"/>
    <stop offset="0.4" stop-color="#b01fff" stop-opacity="0.22"/><stop offset="0.75" stop-color="#36f9f6" stop-opacity="0"/></radialGradient>
  <filter id="mws-blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="4"/></filter>
  <filter id="mws-hzglow" x="-5%" y="-400%" width="110%" height="900%"><feGaussianBlur stdDeviation="0.8"/></filter>
  <linearGradient id="mws-hz" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#f92aad" stop-opacity="0"/>
    <stop offset="0.15" stop-color="#f92aad" stop-opacity="0.95"/><stop offset="0.55" stop-color="#36f9f6" stop-opacity="0.75"/>
    <stop offset="1" stop-color="#f92aad" stop-opacity="0"/></linearGradient>
  <filter id="mws-peak" x="-100%" y="-60%" width="300%" height="220%">
    <feGaussianBlur stdDeviation="0.9" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <radialGradient id="mws-fade" gradientUnits="userSpaceOnUse" cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(cols * 1.15)}"
      gradientTransform="translate({fmt(cx)} {fmt(cy)}) scale(1 0.42) translate({fmt(-cx)} {fmt(-cy)})">
    <stop offset="0.55" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>
  </radialGradient>
  <mask id="mws-mask"><rect x="-200" y="-200" width="600" height="400" fill="url(#mws-fade)"/></mask>
  <radialGradient id="mws-pool" gradientUnits="userSpaceOnUse" cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(cols * 1.05)}"
      gradientTransform="translate({fmt(cx)} {fmt(cy)}) scale(1 0.42) translate({fmt(-cx)} {fmt(-cy)})">
    <stop offset="0" stop-color="#f92aad" stop-opacity="0.32"/><stop offset="0.6" stop-color="#b01fff" stop-opacity="0.15"/>
    <stop offset="1" stop-color="#b01fff" stop-opacity="0"/>
  </radialGradient>
</defs>
<g transform="scale(4) translate({fmt(tx)}, 0)">
{horizon_svg}
  <rect x="-200" y="-200" width="600" height="400" fill="url(#mws-pool)"/>
  <g mask="url(#mws-mask)" stroke="#36f9f6" stroke-opacity="0.35" stroke-width="0.07">{''.join(lines)}</g>
  <g mask="url(#mws-mask)">{reflection_svg}</g>
</g>
"""
    if True:  # let tall towers, the horizon and its glow reach past the calendar's own box
        head = svg[:start]
        k = head.rfind('style="margin-top: -130px;"')
        if k >= 0:
            head = (head[:k] + f'style="margin-top: {-130 + CALENDAR_DROP}px; overflow: visible;"'
                    + head[k + len('style="margin-top: -130px;"'):])
        svg = head + svg[start:]
        start = len(head)
        end = svg.find("</svg>", start)
    car_svg = ""
    if CAR:
        body, car_css = iso_car(corner, cols, rows)
        car_svg = f"""<style>{car_css}</style>
<defs>
  <linearGradient id="mws-beam" gradientUnits="userSpaceOnUse" x1="{fmt(corner(0, rows + 1.9)[0])}" y1="0" x2="{fmt(corner(-2.4, rows + 1.9)[0])}" y2="0">
    <stop offset="0" stop-color="#8afcfa" stop-opacity="0.32"/><stop offset="1" stop-color="#36f9f6" stop-opacity="0"/></linearGradient>
  <linearGradient id="mws-trail" gradientUnits="userSpaceOnUse" x1="{fmt(corner(2.4, rows + 1.9)[0])}" y1="0" x2="{fmt(corner(6.4, rows + 1.9)[0])}" y2="0">
    <stop offset="0" stop-color="#ff2e6e" stop-opacity="0.95"/><stop offset="1" stop-color="#f92aad" stop-opacity="0"/></linearGradient>
  <linearGradient id="mws-carside" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#4a1d7a"/><stop offset="1" stop-color="#1a0630"/></linearGradient>
  <linearGradient id="mws-glass" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#36f9f6" stop-opacity="0.55"/><stop offset="1" stop-color="#7b2fff" stop-opacity="0.4"/></linearGradient>
</defs>
<g transform="scale(4) translate({fmt(tx)}, 0)">{body}</g>
"""
    return svg[:start] + floor + block + car_svg + svg[end:], (
        f"restyled {len(cells)} days over {weeks} weeks, {peaks} peaks in cyan")


ESTIMATE = re.compile(r"<small>estimation from [^<]*</small>")
CAPTION = "<small>Based on recently edited code</small>"


def main():
    src, dst = sys.argv[1], sys.argv[2]
    svg = open(src, encoding="utf-8").read()
    out, note = restyle(svg)
    out, swapped = ESTIMATE.subn(CAPTION, out)
    note += "; languages caption replaced" if swapped else "; no languages estimate line found"
    ET.fromstring(out.encode("utf-8"))  # refuse to publish a broken SVG
    open(dst, "w", encoding="utf-8").write(out)
    print(("" if out is not svg else "::warning::") + "skyline: " + note)


if __name__ == "__main__":
    main()
