"""Cap the y axis of the activity line graph.

github-readme-activity-graph scales the chart to the busiest day, so one very
busy day squashes the rest of the month into a flat line. This redraws the
chart with CAP at the top of the axis: busier days are drawn at the top with
their real count written above them, and the axis labels are rewritten to
match. The curve is redrawn with the same monotone cubic smoothing the
chart library (Chartist) uses.

Usage: cap_activity.py <in.svg> <out.svg> [cap]
If the chart can't be read, the input is copied unchanged and a warning is
printed, so the graph still publishes. Run it once per fresh render.
"""
import re
import sys
import xml.etree.ElementTree as ET

NUM = r"(-?\d+(?:\.\d+)?)"
POINT = re.compile(
    r'<line x1="' + NUM + r'" y1="' + NUM + r'" x2="' + NUM + r'" y2="' + NUM
    + r'" class="ct-point" ct:value="(\d+)"></line>'
)
HGRID = re.compile(r'<line y1="' + NUM + r'" y2="' + NUM + r'" x1="' + NUM + r'" x2="' + NUM + r'" class="ct-grid ct-vertical"></line>')
LINE = re.compile(r'<path d="[^"]*" class="ct-line"></path>')
YLABEL = re.compile(r'(<text y="' + NUM + r'" x="' + NUM + r'"[^>]*class="ct-label ct-vertical ct-start">)([^<]*)(</text>)')


def r3(x):
    return f"{round(x, 3):.3f}".rstrip("0").rstrip(".")


def monotone_cubic(xs, ys):
    """Chartist.Interpolation.monotoneCubic, as an SVG path."""
    n = len(xs)
    if n < 2:
        return f"M{r3(xs[0])},{r3(ys[0])}"
    dxs = [xs[i + 1] - xs[i] for i in range(n - 1)]
    ms = [(ys[i + 1] - ys[i]) / dxs[i] for i in range(n - 1)]
    ds = [0.0] * n
    ds[0], ds[-1] = ms[0], ms[-1]
    for i in range(1, n - 1):
        if ms[i] == 0 or ms[i - 1] == 0 or (ms[i - 1] > 0) != (ms[i] > 0):
            ds[i] = 0.0
        else:
            ds[i] = 3 * (dxs[i - 1] + dxs[i]) / (
                (2 * dxs[i] + dxs[i - 1]) / ms[i - 1] + (dxs[i] + 2 * dxs[i - 1]) / ms[i]
            )
    d = f"M{r3(xs[0])},{r3(ys[0])}"
    for i in range(n - 1):
        d += (
            f"C{r3(xs[i] + dxs[i] / 3)},{r3(ys[i] + ds[i] * dxs[i] / 3)},"
            f"{r3(xs[i + 1] - dxs[i] / 3)},{r3(ys[i + 1] - ds[i + 1] * dxs[i] / 3)},"
            f"{r3(xs[i + 1])},{r3(ys[i + 1])}"
        )
    return d


def cap_svg(svg, cap):
    points = [(float(m.group(1)), int(m.group(5))) for m in POINT.finditer(svg)]
    grid = sorted(float(m.group(1)) for m in HGRID.finditer(svg))
    labels = list(YLABEL.finditer(svg))
    if len(points) < 2 or len(grid) < 2 or len(labels) < 2 or len(LINE.findall(svg)) != 1:
        return svg, "chart not recognised"
    top, bottom = grid[0], grid[-1]
    busiest = max(v for _, v in points)
    if busiest <= cap:
        return svg, f"busiest day is {busiest}, at or under the cap of {cap}: nothing to do"

    def y_of(v):
        return bottom - min(v, cap) / cap * (bottom - top)

    xs = [x for x, _ in points]
    ys = [y_of(v) for _, v in points]

    def fix_point(m):
        y = r3(y_of(int(m.group(5))))
        return f'<line x1="{m.group(1)}" y1="{y}" x2="{m.group(3)}" y2="{y}" class="ct-point" ct:value="{m.group(5)}"></line>'

    out = POINT.sub(fix_point, svg)
    out = LINE.sub(f'<path d="{monotone_cubic(xs, ys)}" class="ct-line"></path>', out, count=1)

    # Axis labels run bottom to top; spread 0..cap over the same grid lines.
    steps = len(labels) - 1
    ordered = sorted(YLABEL.finditer(out), key=lambda m: -float(m.group(2)))
    values = {m.start(): cap * i / steps for i, m in enumerate(ordered)}

    def fix_label(m):
        return m.group(1) + f"{values[m.start()]:g}" + m.group(5)

    out = YLABEL.sub(fix_label, out)

    # Write the real count above each day that goes past the cap.
    notes = "".join(
        f'<text x="{r3(x)}" y="{r3(top - 10)}" text-anchor="middle" class="ct-label">{v}</text>'
        for x, v in points if v > cap
    )
    anchor = '</g><text class="ct-axis-title'
    if notes and anchor not in out:
        return svg, "could not place the over-cap labels"
    out = out.replace(anchor, notes + anchor, 1)
    return out, f"axis capped at {cap} (busiest day {busiest}, {sum(v > cap for _, v in points)} day(s) over)"


def main():
    src, dst = sys.argv[1], sys.argv[2]
    cap = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    svg = open(src, encoding="utf-8").read()
    out, note = cap_svg(svg, cap)
    ET.fromstring(out.encode("utf-8"))  # refuse to publish a broken SVG
    open(dst, "w", encoding="utf-8").write(out)
    print(("" if out is not svg else "::warning::") + "activity graph: " + note)


if __name__ == "__main__":
    main()
