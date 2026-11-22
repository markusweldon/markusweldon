"""Cut the isometric contribution city out of the metrics card.

markusweldon.com shows the calendar on its own, so this takes the calendar's
SVG (restyled by skyline_isocalendar.py, roadster included) out of the
finished github-metrics.svg and saves it as a standalone, transparent image.
The crop leaves room for the tallest towers, which reach above the plugin's
own box.

It also writes the same calendar as four stacked layers next to it
(isocalendar-floor.svg, -back.svg, -city.svg, -front.svg): the floor and the
towers hold still, and only the two small car layers move. A browser redraws
a whole SVG image on every frame of any animation in it, so with one image
the whole city is redrawn as the car moves; stacked, only the car is.

Usage: extract_isocalendar.py <github-metrics.svg> <isocalendar.svg>
Exits with an error if the calendar can't be found, so a stale image stays.
"""
import re
import sys
import xml.etree.ElementTree as ET

# Crop, in the calendar's own units (the plugin draws it in a 480 x 270 box).
VIEW = (24, 0, 432, 272)
WIDTH = 1920  # pixels across: twice the shown size, so phones draw it sharp


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


MARKS = ("<!--mws:back-->", "<!--mws:city-->", "<!--mws:front-->", "<!--mws:end-->")
SHARED = re.compile(r"<style\b.*?</style>|<defs\b.*?</defs>|<filter\b.*?</filter>", re.S)


def layers(full: str) -> dict:
    """The calendar as four stacked layers, all with the same size and view.
    Each carries every style, gradient and filter (they draw nothing), plus
    only its own drawing. Empty if the calendar has no layer markers."""
    head = full[:full.index(">") + 1]
    body = full[len(head):full.rindex("</svg>")]
    if not all(m in body for m in MARKS):
        return {}
    i_back, i_city, i_front, i_end = (body.index(m) for m in MARKS)
    shared = "".join(SHARED.findall(body))
    parts = {
        "floor": body[:i_back],                               # the plugin's filters and the grid floor
        "back": SHARED.sub("", body[i_back:i_city]),          # the car behind the towers
        "city": SHARED.sub("", body[i_city:i_front]),         # the towers
        "front": SHARED.sub("", body[i_front:i_end]),         # the car in front, smoke in the air
    }
    out = {}
    for name, drawing in parts.items():
        styles = "" if name == "floor" else shared
        out[name] = f"{head}\n{styles}\n{drawing}\n</svg>\n"
    return out


def main():
    src, dst = sys.argv[1], sys.argv[2]
    out = extract(open(src, encoding="utf-8").read())
    ET.fromstring(out.encode("utf-8"))  # refuse to publish a broken SVG
    open(dst, "w", encoding="utf-8").write(out)
    print(f"isocalendar: wrote {dst} ({len(out) // 1024} KB)")
    for name, layer in layers(out).items():
        ET.fromstring(layer.encode("utf-8"))
        path = dst.replace(".svg", f"-{name}.svg")
        open(path, "w", encoding="utf-8").write(layer)
        print(f"isocalendar: wrote {path} ({len(layer) // 1024} KB)")


if __name__ == "__main__":
    main()
