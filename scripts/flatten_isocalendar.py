#!/usr/bin/env python3
"""Rescale the cubes of the lowlighter/metrics isometric calendar.

The plugin draws every day's height as count / (busiest day of the year), so a
single outlier day (e.g. one day with ~190 contributions when a busy day is
~40) shoots up as a tower and squashes every other day flat.

This script reads the rendered SVG, recovers each cube's ratio from its path
data, picks a robust cap that ignores isolated spikes, and redraws heights as
min(ratio / cap, 1). Colors, positions and every other part of the card are
left untouched.

Usage: flatten_isocalendar.py <svg-file>   (rewrites the file in place)
"""
import re
import sys

SIZE = 6  # cube height scale used by the plugin

# One day cube: <g transform="translate(X, Y)"> + top, left and right faces.
CUBE = re.compile(
    r'(<g transform="translate\((?P<x>-?[0-9.]+), (?P<y>-?[0-9.e-]+)\)">\s*'
    r'<path fill="(?P<c1>[^"]+)" d="M1\.7,2 0,1 1\.7,0 3\.4,1 z"/>\s*)'
    r'<path fill="(?P<c2>[^"]+)" filter="url\(#brightness1\)" d="M0,1 1\.7,2 1\.7,(?P<l>[0-9.e-]+) 0,[0-9.e-]+ z"/>'
    r'(?P<ws>\s*)'
    r'<path fill="(?P<c3>[^"]+)" filter="url\(#brightness2\)" d="M1\.7,2 3\.4,1 3\.4,[0-9.e-]+ 1\.7,[0-9.e-]+ z"/>'
)

# A day counts as an isolated spike when it is more than this many times the
# next busiest day; spikes are clamped to the height of the day below them.
SPIKE_FACTOR = 2.0


def robust_cap(ratios):
    values = sorted({r for r in ratios if r > 0}, reverse=True)
    for i, v in enumerate(values[:-1]):
        if v <= SPIKE_FACTOR * values[i + 1]:
            return v
    return values[-1] if values else 1.0


def main(path):
    svg = open(path, encoding="utf-8").read()
    cubes = list(CUBE.finditer(svg))
    if not cubes:
        print("isocalendar: no cubes found, leaving the SVG unchanged")
        return
    ratios = [(float(m["l"]) - 2) / SIZE for m in cubes]
    cap = robust_cap(ratios)
    if cap >= max(ratios):
        print("isocalendar: no outlier day, leaving the SVG unchanged")
        return

    def redraw(m):
        old = (float(m["l"]) - 2) / SIZE
        new = min(old / cap, 1.0)
        j = float(m["y"]) - (1 - old) * SIZE  # day-of-week row offset
        y = j + (1 - new) * SIZE
        h = new * SIZE
        return (
            f'<g transform="translate({m["x"]}, {y:g})">'
            + m.group(1)[m.group(1).index(">") + 1:]
            + f'<path fill="{m["c2"]}" filter="url(#brightness1)" d="M0,1 1.7,2 1.7,{2 + h:g} 0,{1 + h:g} z"/>'
            + m["ws"]
            + f'<path fill="{m["c3"]}" filter="url(#brightness2)" d="M1.7,2 3.4,1 3.4,{1 + h:g} 1.7,{2 + h:g} z"/>'
        )

    svg = CUBE.sub(redraw, svg)
    open(path, "w", encoding="utf-8").write(svg)
    print(f"isocalendar: {len(cubes)} cubes rescaled, cap {cap:.3f} of the busiest day")


if __name__ == "__main__":
    main(sys.argv[1])
