"""Cut the isometric contribution city out of the metrics card.

markusweldon.com shows the calendar on its own, so this takes the calendar's
SVG (restyled by skyline_isocalendar.py, roadster included) out of the
finished github-metrics.svg and saves it as a standalone, transparent image.
The crop leaves room for the tallest towers, which reach above the plugin's
own box.

Usage: extract_isocalendar.py <github-metrics.svg> <isocalendar.svg>
Exits with an error if the calendar can't be found, so a stale image stays.
"""
import re
import sys
import xml.etree.ElementTree as ET

# Crop, in the calendar's own units (the plugin draws it in a 480 x 270 box).
VIEW = (24, 0, 432, 272)
WIDTH = 960  # pixels across


def extract(svg: str) -> str:
    anchor = svg.find('<g transform="scale(4)')
    if anchor < 0:
        raise ValueError("no isocalendar in the card")
    start = svg.rfind("<svg", 0, anchor)
    depth = 0
    for m in re.finditer(r"<svg\b|</svg>", svg[start:]):
        depth += 1 if m.group() != "</svg>" else -1
        if depth == 0:
            end = start + m.end()
            break
    else:
        raise ValueError("calendar <svg> is not closed")
    inner = svg[start:end]
    body = inner[inner.index(">") + 1:-len("</svg>")]
    x, y, w, h = VIEW
    height = round(WIDTH * h / w)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
            f'viewBox="{x} {y} {w} {h}">\n<title>Markus Weldon\'s GitHub contributions over the past year</title>\n'
            f"{body}\n</svg>\n")


def main():
    src, dst = sys.argv[1], sys.argv[2]
    out = extract(open(src, encoding="utf-8").read())
    ET.fromstring(out.encode("utf-8"))  # refuse to publish a broken SVG
    open(dst, "w", encoding="utf-8").write(out)
    print(f"isocalendar: wrote {dst} ({len(out) // 1024} KB)")


if __name__ == "__main__":
    main()
