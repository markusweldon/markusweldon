"""Restyle the metrics isocalendar as a neon skyline.

Run after cap_isocalendar.py. GitHub colours each day by a quartile of the
year, so neighbouring towers jump between unrelated colours. This colours
each tower by its height instead (dim violet for quiet days, through purple
and pink, with cyan kept for the tallest days), puts a soft glow on those
peaks, and sets the calendar on a cyan isometric grid floor with a pink glow
underneath, like the header's horizon. Towers rise into place once when the
image loads; visitors who prefer reduced motion see them already standing.

It also swaps the languages section's "estimation from 3.74mb of code in
1327 edited files across 204 commits" line for a generic caption.

Usage: skyline_isocalendar.py <in.svg> <out.svg>
If the calendar can't be found, the input is copied unchanged and a warning
is printed, so the card still publishes.
"""
import re
import sys
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


def restyle(svg):
    start = svg.find(ANCHOR)
    if start < 0:
        return svg, "no isocalendar found"
    end = svg.find("</svg>", start)
    block = svg[start:end]

    cells, week, weeks, bases = [], None, 0, []

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

    for m in GROUP.finditer(block):
        visit(m)
    if len(cells) < 300:  # a full year is about 365 days
        return svg, f"found only {len(cells)} day cells, left unchanged"

    out, pos, peaks = [], 0, 0
    for c, w, h in cells:
        t = max(0.0, min(1.0, h / SIZE))
        col = colour(t)
        peak = t >= PEAK_FROM
        peaks += peak
        glow = ' filter="url(#mws-peak)"' if peak else ""
        out.append(block[pos:c.start()])
        out.append(
            f'<g transform="translate({c.group(1)}, {c.group(2)})"{glow}>{c.group(3)}'
            f'<g class="mws-rise" style="animation-delay:{w * 14}ms">'
            f'{c.group(4)}{col}{c.group(6)}{col}{c.group(7)}{col}{c.group(9)}</g>'
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
    floor = f"""<style>
@keyframes mws-rise{{from{{transform:scaleY(0)}}to{{transform:scaleY(1)}}}}
.mws-rise{{transform-box:fill-box;transform-origin:50% 100%;animation:mws-rise .9s cubic-bezier(.2,.8,.2,1) both}}
@media (prefers-reduced-motion: reduce){{.mws-rise{{animation:none}}}}
</style>
<defs>
  <filter id="mws-peak" x="-100%" y="-60%" width="300%" height="220%">
    <feGaussianBlur stdDeviation="0.9" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <radialGradient id="mws-fade" gradientUnits="userSpaceOnUse" cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(cols * 1.15)}"
      gradientTransform="translate({fmt(cx)} {fmt(cy)}) scale(1 0.42) translate({fmt(-cx)} {fmt(-cy)})">
    <stop offset="0.55" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>
  </radialGradient>
  <mask id="mws-mask"><rect x="-200" y="-200" width="600" height="400" fill="url(#mws-fade)"/></mask>
  <radialGradient id="mws-pool" gradientUnits="userSpaceOnUse" cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(cols * 0.9)}"
      gradientTransform="translate({fmt(cx)} {fmt(cy)}) scale(1 0.42) translate({fmt(-cx)} {fmt(-cy)})">
    <stop offset="0" stop-color="#f92aad" stop-opacity="0.22"/><stop offset="0.6" stop-color="#b01fff" stop-opacity="0.1"/>
    <stop offset="1" stop-color="#b01fff" stop-opacity="0"/>
  </radialGradient>
</defs>
<g transform="scale(4) translate(12, 0)">
  <rect x="-200" y="-200" width="600" height="400" fill="url(#mws-pool)"/>
  <g mask="url(#mws-mask)" stroke="#36f9f6" stroke-opacity="0.35" stroke-width="0.07">{''.join(lines)}</g>
</g>
"""
    return svg[:start] + floor + block + svg[end:], (
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
