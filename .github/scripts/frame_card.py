"""Frame a generated graph like the README's project cards.

Adds the markusweldon.com card look around an SVG that a workflow rendered:
a rounded #130022 panel with the site's faint grid (cyan rows, purple
columns), a soft pink glow in the top-right corner, and a thin pink border.
The graph's own background is switched off so the panel shows through.

Sizes are set for the image's displayed width in the README (about 830px),
so the grid, corners and border match the cards whatever the SVG's size.

With --chart (for the activity line chart), the panel skips its own grid and
the chart's grid becomes it: the dashed line for every day goes, and the
value lines turn into the site's faint cyan rows, so two grids don't clash.

Usage: frame_card.py <in.svg> <out.svg> [--chart]
If the SVG can't be framed, the input is copied unchanged and a warning is
printed, so the graph still publishes.
"""
import re
import sys
import xml.etree.ElementTree as ET

DISPLAY_WIDTH = 830  # how wide the README shows these images
SURFACE, PINK, CYAN, PURPLE = "#130022", "#f92aad", "#36f9f6", "#b01fff"

# Backgrounds the graph tools paint themselves; hidden so the panel shows.
HIDE = (
    "<style>"
    "#cardBg{fill:none!important;stroke:none!important}"  # activity graph
    "svg{background:transparent!important}"  # metrics card
    "</style>"
)


def fmt(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


def size(root):
    def num(v):
        return float(re.sub(r"[^\d.]", "", v)) if v and re.search(r"\d", v) else None
    w, h = num(root.get("width")), num(root.get("height"))
    if (w is None or h is None) and root.get("viewBox"):
        _, _, w, h = (float(v) for v in re.split(r"[\s,]+", root.get("viewBox").strip()))
    return w, h


CHART_GRID = (
    "<style>"
    ".ct-grid.ct-horizontal{display:none}"
    ".ct-grid.ct-vertical{stroke:#36f9f6!important;stroke-opacity:.14!important;stroke-dasharray:none!important}"
    "</style>"
)


def frame(svg, chart=False):
    root = ET.fromstring(svg.encode("utf-8"))
    w, h = size(root)
    if not w or not h:
        return svg, "no width or height"
    k = w / DISPLAY_WIDTH
    r, cell, line = 16 * k, 30 * k, k
    panel = f"""{HIDE}{CHART_GRID if chart else ""}
<defs>
  <pattern id="mwf-grid" width="{fmt(cell)}" height="{fmt(cell)}" patternUnits="userSpaceOnUse">
    <rect y="{fmt(cell - line)}" width="{fmt(cell)}" height="{fmt(line)}" fill="{CYAN}" fill-opacity="0.09"/>
    <rect x="{fmt(cell - line)}" width="{fmt(line)}" height="{fmt(cell)}" fill="{PURPLE}" fill-opacity="0.1"/>
  </pattern>
  <radialGradient id="mwf-glow" gradientUnits="userSpaceOnUse" cx="{fmt(w)}" cy="0" r="{fmt(min(w, 3 * h) * 0.6)}">
    <stop offset="0" stop-color="{PINK}" stop-opacity="0.12"/><stop offset="1" stop-color="{PINK}" stop-opacity="0"/>
  </radialGradient>
  <clipPath id="mwf-clip"><rect width="{fmt(w)}" height="{fmt(h)}" rx="{fmt(r)}"/></clipPath>
</defs>
<g clip-path="url(#mwf-clip)">
  <rect width="{fmt(w)}" height="{fmt(h)}" fill="{SURFACE}"/>
{"" if chart else f'  <rect width="{fmt(w)}" height="{fmt(h)}" fill="url(#mwf-grid)"/>'}
  <rect width="{fmt(w)}" height="{fmt(h)}" fill="url(#mwf-glow)"/>
</g>
"""
    border = (f'<rect x="{fmt(line / 2)}" y="{fmt(line / 2)}" width="{fmt(w - line)}" height="{fmt(h - line)}" '
              f'rx="{fmt(r - line / 2)}" fill="none" stroke="{PINK}" stroke-opacity="0.3" stroke-width="{fmt(line)}"/>\n')
    start = re.search(r"<svg\b[^>]*>", svg)
    end = svg.rfind("</svg>")
    if not start or end < start.end():
        return svg, "no root <svg> element"
    out = svg[:start.end()] + "\n" + panel + svg[start.end():end] + border + svg[end:]
    return out, f"framed a {fmt(w)}x{fmt(h)} image"


def main():
    src, dst = sys.argv[1], sys.argv[2]
    chart = "--chart" in sys.argv[3:]
    svg = open(src, encoding="utf-8").read()
    try:
        out, note = frame(svg, chart)
        ET.fromstring(out.encode("utf-8"))  # refuse to publish a broken SVG
    except ET.ParseError as err:
        out, note = svg, f"could not parse ({err})"
    open(dst, "w", encoding="utf-8").write(out)
    print(("" if out is not svg else "::warning::") + "frame: " + note)


if __name__ == "__main__":
    main()
