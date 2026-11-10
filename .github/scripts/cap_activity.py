"""Cap the y axis of the activity line graph.

github-readme-activity-graph scales the chart to the busiest day, so one very
busy day squashes the rest of the month into a flat line. This redraws the
chart with CAP at the top of the axis: busier days are drawn at the top, and
the axis labels are rewritten to match, with grid lines at round steps. The curve is redrawn with the same monotone cubic smoothing the
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

    # Redraw the horizontal grid lines and axis labels at a round step (0, 5, 10 ... cap).
    step = next(st for st in (1, 2, 5, 10, 20, 25, 50, 100) if cap / st <= 8)
    count = -(-cap // step)  # intervals
    gx1, gx2 = HGRID.search(out).group(3), HGRID.search(out).group(4)
    lx = labels[0].group(3)
    gap = (bottom - top) / count
    grid_lines = "".join(
        f'<line y1="{r3(bottom - i * gap)}" y2="{r3(bottom - i * gap)}" x1="{gx1}" x2="{gx2}" class="ct-grid ct-vertical"></line>'
        for i in range(count + 1)
    )
    label_text = "".join(
        f'<text y="{r3(bottom - i * gap + 4.5)}" x="{lx}" height="{r3(gap if i < count else 30)}" width="60" '
        f'class="ct-label ct-vertical ct-start">{min(i * step, cap)}</text>'
        for i in range(count + 1)
    )
    first_grid = HGRID.search(out).start()
    out = HGRID.sub("", out)
    out = out[:first_grid] + grid_lines + out[first_grid:]
    first_label = YLABEL.search(out).start()
    out = YLABEL.sub("", out)
    out = out[:first_label] + label_text + out[first_label:]

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
