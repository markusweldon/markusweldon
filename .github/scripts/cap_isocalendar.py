"""Cap the tower height in the metrics isocalendar.

lowlighter/metrics draws each day as a tower whose height is that day's
contributions divided by the busiest day in the year. One very busy day then
flattens every other day. This rescales the towers so that CAP contributions
reach full height and busier days stop there. Colours and the "Highest in a
day" figure are left as GitHub reported them.

Usage: cap_isocalendar.py <in.svg> <out.svg> [cap]
If the calendar can't be found, the input is copied unchanged and a warning
is printed, so the card still publishes. Run it once per fresh render.
"""
import re
import sys
import xml.etree.ElementTree as ET

SIZE = 6  # the plugin's full tower height
NUM = r"(-?\d+(?:\.\d+)?(?:e-?\d+)?)"
CELL = re.compile(
    r'<g transform="translate\(' + NUM + r", " + NUM + r'\)">(\s*)'
    r'<path fill="(#[0-9a-fA-F]+)" d="M1\.7,2 0,1 1\.7,0 3\.4,1 z"/>(\s*)'
    r'<path fill="\4" filter="url\(#brightness1\)" d="M0,1 1\.7,2 1\.7,' + NUM + " 0," + NUM + r' z"/>(\s*)'
    r'<path fill="\4" filter="url\(#brightness2\)" d="M1\.7,2 3\.4,1 3\.4,' + NUM + " 1\\.7," + NUM + r' z"/>'
)
HIGHEST = re.compile(r"Highest in a day at (\d+)")


def fmt(x):
    return f"{x:.4f}".rstrip("0").rstrip(".")


def cap_svg(svg, cap):
    m = HIGHEST.search(svg)
    if not m:
        return svg, "no 'Highest in a day' figure"
    reference = int(m.group(1))
    scale_to = min(cap, reference)
    if reference <= 0 or scale_to == reference:
        return svg, f"busiest day is {reference}, at or under the cap of {cap}: nothing to do"
    changed = 0

    def fix(c):
        nonlocal changed
        x, y = float(c.group(1)), float(c.group(2))
        height = float(c.group(6)) - 2
        count = round(height / SIZE * reference)
        new_height = min(count, scale_to) / scale_to * SIZE
        y += height - new_height  # keep the base where it was
        changed += 1
        return (
            f'<g transform="translate({c.group(1)}, {fmt(y)})">{c.group(3)}'
            f'<path fill="{c.group(4)}" d="M1.7,2 0,1 1.7,0 3.4,1 z"/>{c.group(5)}'
            f'<path fill="{c.group(4)}" filter="url(#brightness1)" d="M0,1 1.7,2 1.7,{fmt(2 + new_height)} 0,{fmt(1 + new_height)} z"/>{c.group(8)}'
            f'<path fill="{c.group(4)}" filter="url(#brightness2)" d="M1.7,2 3.4,1 3.4,{fmt(1 + new_height)} 1.7,{fmt(2 + new_height)} z"/>'
        )

    out = CELL.sub(fix, svg)
    if changed < 300:  # a full year is about 365 days
        return svg, f"found only {changed} day cells, left unchanged"
    return out, f"rescaled {changed} days: {scale_to} contributions now reach full height (busiest day {reference})"


def main():
    src, dst = sys.argv[1], sys.argv[2]
    cap = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    svg = open(src, encoding="utf-8").read()
    out, note = cap_svg(svg, cap)
    ET.fromstring(out.encode("utf-8"))  # refuse to publish a broken SVG
    open(dst, "w", encoding="utf-8").write(out)
    print(("" if out is not svg else "::warning::") + "isocalendar: " + note)


if __name__ == "__main__":
    main()
