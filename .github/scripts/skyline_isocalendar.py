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
    parts = []
    if peak:  # the glow: a blurred silhouette behind the tower, never the tower itself
        parts.append(f'<path fill="#36f9f6" opacity="0.55" filter="url(#mws-glow)" '
                     f'd="M0,1 1.7,0 3.4,1 3.4,{b1} 1.7,{b2} 0,{b1} z"/>')
    parts += [
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


def iso_car(corner, cols, rows) -> tuple[str, str, str]:
    """The header's roadster, rendered by render_roadster.py from the same 3D model in
    this calendar's isometric projection and embedded as a PNG. It drives
    along a road in front of the city towards the oldest weeks, tail to the
    viewer, with headlight beams ahead and pink streaks behind.
    Returns (svg, css, back svg); the back svg goes before the city, for a
    car that drives behind it. Empty svgs if the render isn't there."""
    png, meta_file = ASSETS / "roadster-iso.webp", ASSETS / "roadster.json"
    if not png.exists() or not meta_file.exists():
        return "", "", ""
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
    files = [ASSETS / f"roadster-iso-{k}.webp" for k in range(n)]
    if n > 1 and all(f.exists() for f in files):
        # Wheel frames shown in turn, so the wheels roll as the car drives.
        # A CSS animation, not SMIL: Safari drops SMIL-animated images when
        # the SVG is opened on its own.
        dur = 0.04 * n                             # quick wheel frames for the faster car
        image = (f"<style>@keyframes mws-wheel{{0%{{opacity:1}}{100 / n:.3f}%{{opacity:0}}100%{{opacity:0}}}}"
                 f".mws-w{{opacity:0;animation:mws-wheel {dur:.2f}s steps(1,end) infinite}}"
                 f"@media (prefers-reduced-motion: reduce){{.mws-w{{animation:none}}.mws-w0{{opacity:1}}}}</style>")
        for k, f in enumerate(files):
            b64 = base64.b64encode(f.read_bytes()).decode()
            image += (f'<image class="mws-w mws-w{k}" href="data:image/webp;base64,{b64}" {geom} '
                      f'style="animation-delay:-{dur - 0.04 * k:.2f}s"/>')
    else:
        image = f'<image href="data:image/webp;base64,{data}" {geom}/>'

    flight = rocket_hop(corner, cols, rows, road, L, (ox, oy), geom, image)
    if flight:
        return flight

    def off(a):
        return corner(a, 0)[0] - corner(0, 0)[0], corner(a, 0)[1] - corner(0, 0)[1]
    (sx, sy), (ex, ey), (mx, my) = off(cols + 6), off(-8), off(cols * 0.45)
    # A fast pass, about 4.5 s across the city, then a short gap before the next.
    css = (f"@keyframes mws-drive{{0%{{transform:translate({fmt(sx)}px,{fmt(sy)}px);opacity:0}}"
           f"4%{{opacity:1}}70%{{opacity:1}}"
           f"75%{{transform:translate({fmt(ex)}px,{fmt(ey)}px);opacity:0}}"
           f"100%{{transform:translate({fmt(ex)}px,{fmt(ey)}px);opacity:0}}}}"
           f".mws-car{{animation:mws-drive 6s linear infinite}}"
           f"@media (prefers-reduced-motion: reduce){{.mws-car{{animation:none;transform:translate({fmt(mx)}px,{fmt(my)}px)}}}}")
    return f'<g class="mws-car">{floor}{image}</g>', css, ""


# The rocket hop: the 2026 Roadster's party trick. Distances are in
# calendar units (weeks along the road, days across, a cell's height up).
HOP_SPEED = 15.0         # weeks a second on the road: the same pace as before the hop
HOP_AIR = 2.6            # seconds in the air: the road pace slows to hang-time over the city
HOP_GAP = 1.2            # seconds off screen between passes
HOP_LIFT, HOP_LAND = 0.30, 0.62   # where along the road (0 start .. 1 end) it lifts off and lands
HOP_HIGH = MAX_HEIGHT + 5         # apex above the ground, clear of the tallest towers
HOP_ROLL = (0.30, 0.70)           # the barrel roll, as shares of the flight
BACK_ROAD = 1.9                   # the far road, this many days behind the oldest row
A_EXIT = -2.0                      # week where the hop pass leaves the far road, short of the card's heading
FADE_IN, FADE_OUT = 0.5, 0.7      # seconds the car takes to fade in as it enters and out as it leaves


def rocket_hop(corner, cols, rows, road, L, nose, geom, level):
    """The car drives in on the near road, lights its rocket thrusters (smoke
    billowing off the road), lifts off and arcs right over the city,
    barrel-rolling above the towers and trailing smoke, then drops onto the
    far road behind the city on its jets and drives on there, glimpsed
    between the towers. It keeps moving forwards throughout. The roll is 16
    real renders of the car turning about its long axis
    (render_roadster.py --roll).
    Returns (front svg, css, back svg): the back svg is drawn before the
    city, so the towers hide the car once it is behind them. None if the
    roll frames aren't there."""
    meta = json.loads((ASSETS / "roadster.json").read_text())
    roll = meta.get("roll")
    if not roll:
        return None
    files = [ASSETS / f"roadster-roll-{k}.webp" for k in range(roll["frames"])]
    if not all(f.exists() for f in files):
        return None
    n = roll["frames"]
    ox, oy = nose
    cross = road + BACK_ROAD                       # days from the near road to the far road
    a0, a1 = cols + 6, -8.0                        # the run: in from the newest weeks, out past the oldest
    span = a0 - a1
    # Two passes per cycle: a plain drive along the near road, then the hop.
    # The hop's drive on the far road ends at A_EXIT, well short of the end
    # of the city, so it never runs into the card's heading above it.
    plain = span / HOP_SPEED                                        # seconds
    lift_s = HOP_LIFT * span / HOP_SPEED
    r_exit = (a0 - A_EXIT) / span
    hop = lift_s + HOP_AIR + (r_exit - HOP_LAND) * span / HOP_SPEED
    hop_at = plain + HOP_GAP                                        # when the hop pass starts
    cycle = round(hop_at + hop + HOP_GAP, 2)

    def smooth(u):                                 # 0..1, gentle at both ends
        u = min(1.0, max(0.0, u))
        return u * u * (3 - 2 * u)

    def state(t):
        """At cycle time t (0..1): along-road a, days off the near road db
        (negative = towards the far road), height z, roll angle, thrust on,
        flight share f, whether the car is behind the city, and its opacity
        (fading in as it enters and out as it leaves)."""
        T = t * cycle
        if T < hop_at:                             # the plain pass
            u = T / plain
            if u >= 1:
                return a1, 0.0, 0.0, 0.0, False, -1.0, False, 0.0
            op = min(1.0, T / FADE_IN, (plain - T) / FADE_OUT)
            return a0 - span * u, 0.0, 0.0, 0.0, False, -1.0, False, op
        T -= hop_at
        if T >= hop:
            return A_EXIT, -cross, 0.0, 0.0, False, 2.0, True, 0.0
        if T < lift_s:                             # road pace, then hang-time, then road pace
            r = HOP_LIFT * T / lift_s
        elif T < lift_s + HOP_AIR:
            r = HOP_LIFT + (HOP_LAND - HOP_LIFT) * (T - lift_s) / HOP_AIR
        else:
            r = HOP_LAND + (T - lift_s - HOP_AIR) * HOP_SPEED / span
        a = a0 - span * r
        f = (r - HOP_LIFT) / (HOP_LAND - HOP_LIFT)
        if f <= 0:
            db, z = 0.0, 0.0
        elif f >= 1:
            db, z = -cross, 0.0
        else:
            db, z = -cross * smooth(f), HOP_HIGH * math.sin(math.pi * f)
        q = (f - HOP_ROLL[0]) / (HOP_ROLL[1] - HOP_ROLL[0])
        angle = 360 * smooth(q) if 0 < q < 1 else 0.0
        thrust = (-0.05 < f < HOP_ROLL[0]) or (HOP_ROLL[1] < f < 1.05)
        behind = road + db < -0.6                  # past the oldest row: every tower is in front of it
        op = min(1.0, T / FADE_IN, (hop - T) / FADE_OUT)
        return a, db, z, angle, thrust, f, behind, max(0.0, op)

    def screen(a, db, z):                          # offset from the car's start position
        return 1.7 * (a - db), a + db - z

    def pct(t):
        # Three decimals: two would round a window's edges together, and the
        # browser merges keyframes at the same offset into a slow cross-fade.
        return f"{t * 100:.3f}%"

    def fade(t):
        return state(t)[7]

    car_kf, ground_kf = [], []
    for i in range(801):
        t = i / 800
        a, db, z, angle, thrust, f, behind, op = state(t)
        x, y = screen(a, db, z)
        car_kf.append(f"{pct(t)}{{transform:translate({fmt(x)}px,{fmt(y)}px);opacity:{op:.2f}}}")
        gx, gy = screen(a, db, 0)
        ground_kf.append(f"{pct(t)}{{transform:translate({fmt(gx)}px,{fmt(gy)}px);"
                         f"opacity:{op * max(0.0, 1 - z / 3):.2f}}}")

    def windows(pred):
        """Spans of cycle time where pred(t) holds."""
        spans, was = [], False
        for i in range(4001):
            t = i / 4000
            now = pred(t)
            if now and not was:
                spans.append([t, 1.0])
            if was and not now:
                spans[-1][1] = t
            was = now
        return spans

    def window_kf(name, spans, show, hide):
        # Instant switches at each edge. Every offset must be distinct: the
        # browser merges keyframes at the same offset, which turns a switch
        # into a slow fade across the whole gap to the next one.
        stops, last = [], None
        def stop(t, value):
            nonlocal last
            key = pct(min(1.0, max(0.0, t)))
            if key != last:
                stops.append(f"{key}{{opacity:{value}}}")
                last = key
        stop(0, show if spans and spans[0][0] <= 0 else hide)
        for s0, s1 in spans:
            if s0 > 0:
                stop(s0, hide)
                stop(s0 + 0.0001, show)
            if s1 < 1:
                stop(s1, show)
                stop(s1 + 0.0001, hide)
        stop(1, show if spans and spans[-1][1] >= 1 else hide)
        return f"@keyframes {name}{{{''.join(stops)}}}.{name}{{animation:{name} {cycle}s linear infinite}}"

    def frame_at(t):
        # The renders turn the car the other way, so play them backwards: it
        # rolls towards the far side, the way it's flying.
        angle = state(t)[3]
        return None if angle == 0 else -round(angle / (360 / n)) % n

    css = [f"@keyframes mws-hop{{{''.join(car_kf)}}}@keyframes mws-gnd{{{''.join(ground_kf)}}}",
           f".mws-hopcar{{animation:mws-hop {cycle}s linear infinite}}.mws-gnd{{animation:mws-gnd {cycle}s linear infinite}}",
           # The front copy shows until the car is behind the city, the back copy after.
           window_kf("mws-fr", windows(lambda t: fade(t) > 0 and not state(t)[6]), 1, 0),
           window_kf("mws-bk", windows(lambda t: fade(t) > 0 and state(t)[6]), 1, 0),
           window_kf("mws-lv", windows(lambda t: frame_at(t) is None), 1, 0),
           window_kf("mws-jet", windows(lambda t: state(t)[4]), 1, 0)]
    css += [window_kf(f"mws-r{k}", windows(lambda t, k=k: frame_at(t) == k), 1, 0) for k in range(n)]
    css.append("@keyframes mws-flame{0%{transform:scaleY(1)}50%{transform:scaleY(0.72)}100%{transform:scaleY(1)}}"
               ".mws-flame{transform-box:fill-box;transform-origin:50% 0;animation:mws-flame .09s linear infinite}")

    # Four downward thrusters under the car, front and rear, each side.
    def under(da, dbo, dz):                        # a point on the car, from its nose on the road
        return ox + 1.7 * (da - dbo), oy + da + dbo - dz
    jets = []
    for da in (0.5, 1.9):
        for dbo in (-0.28, 0.28):
            jx, jy = under(da, dbo, 0.22)
            w, h = 0.55, 4.2
            jets.append(f'<polygon class="mws-flame" points="{fmt(jx - w * 1.6)},{fmt(jy)} {fmt(jx + w * 1.6)},{fmt(jy)} {fmt(jx)},{fmt(jy + h * 1.1)}" '
                        f'fill="url(#mws-jetglow)" filter="url(#mws-jetblur)"/>'
                        f'<polygon class="mws-flame" points="{fmt(jx - w)},{fmt(jy)} {fmt(jx + w)},{fmt(jy)} {fmt(jx)},{fmt(jy + h)}" fill="url(#mws-jetglow)"/>'
                        f'<polygon class="mws-flame" points="{fmt(jx - w * 0.4)},{fmt(jy)} {fmt(jx + w * 0.4)},{fmt(jy)} {fmt(jx)},{fmt(jy + h * 0.65)}" fill="#ffffff"/>')
    jets_svg = f'<g class="mws-jet">{"".join(jets)}</g>'

    roll_imgs = "".join(
        f'<image class="mws-r{k}" href="data:image/webp;base64,{base64.b64encode(f.read_bytes()).decode()}" '
        f'x="{fmt(ox + roll["x"])}" y="{fmt(oy + roll["y"])}" width="{fmt(roll["w"])}" height="{fmt(roll["h"])}"/>'
        for k, f in enumerate(files))
    car = f'{jets_svg}<g class="mws-lv">{level}</g>{roll_imgs}'

    # Smoke: puffs left behind in the world, each in front of or behind the
    # city by where it is. A burst off the road at lift-off and at landing,
    # and a plume from the tail through the flight.
    front_puffs, back_puffs = [], []
    def puff(t, a, db, z, size, grow):
        x, y = screen(a, db, z)
        (back_puffs if road + db < -0.6 else front_puffs).append(
            f'<circle class="mws-puff" cx="{fmt(ox + x)}" cy="{fmt(oy + y)}" r="{fmt(size)}" '
            f'fill="url(#mws-smoke)" style="--g:{grow};animation-delay:{t * cycle:.2f}s"/>')
    t_lift, t_land = (hop_at + lift_s) / cycle, (hop_at + lift_s + HOP_AIR) / cycle
    for t0 in (t_lift, t_land):
        for j in range(12):
            t = t0 + (j - 4) * 0.035 / cycle
            a, db, *_ = state(t)
            for side in (-0.7, 0, 0.7):
                puff(t, a + 1.2 + side * 1.1, db + side, 0, 1.15, 4.0)
    t = t_lift
    while t < t_land:
        a, db, z, *_ = state(t)
        puff(t, a + L, db, z + 0.5, 0.75, 3.0)
        t += 0.04 / cycle                          # a puff every 40 ms, so the trail reads as one plume
    css.append("@keyframes mws-puff{0%{opacity:0;scale:.7}2%{opacity:.95}16%{opacity:0;scale:var(--g)}100%{opacity:0;scale:var(--g)}}"
               f".mws-puff{{opacity:0;transform-box:fill-box;transform-origin:center;animation:mws-puff {cycle}s linear infinite}}")

    # The car's shadow on whichever road it's over, fading as it climbs.
    def p(da, dbo):
        x, y = corner(da, road + dbo)
        return f"{fmt(x)},{fmt(y)}"
    shadow = f'<polygon points="{p(-0.1, -0.62)} {p(L + 0.1, -0.62)} {p(L + 0.1, 0.62)} {p(-0.1, 0.62)}" fill="#000" fill-opacity="0.45"/>'

    mx, my = screen(a0 + (a1 - a0) * 0.2, 0, 0)
    css.append(f"@media (prefers-reduced-motion: reduce){{.mws-hopcar,.mws-gnd{{animation:none;transform:translate({fmt(mx)}px,{fmt(my)}px)}}"
               ".mws-fr,.mws-lv{animation:none;opacity:1}.mws-bk,.mws-jet,.mws-puff,"
               + ",".join(f".mws-r{k}" for k in range(n)) + "{animation:none;opacity:0}}")
    defs = ('<defs><linearGradient id="mws-jetglow" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#e9fdff"/><stop offset="0.35" stop-color="#36f9f6" stop-opacity="0.85"/>'
            '<stop offset="1" stop-color="#f92aad" stop-opacity="0"/></linearGradient>'
            '<filter id="mws-jetblur" x="-100%" y="-30%" width="300%" height="160%"><feGaussianBlur stdDeviation="0.45"/></filter>'
            '<radialGradient id="mws-smoke"><stop offset="0" stop-color="#ffffff" stop-opacity="1"/>'
            '<stop offset="0.45" stop-color="#f1e8ff" stop-opacity="0.8"/><stop offset="1" stop-color="#d9c8f0" stop-opacity="0"/></radialGradient></defs>')
    front = (f'{defs}<g>{"".join(front_puffs)}</g>'
             f'<g class="mws-fr"><g class="mws-hopcar">{car}</g></g>')
    back = (f'<g class="mws-gnd">{shadow}</g><g>{"".join(back_puffs)}</g>'
            f'<g class="mws-bk"><g class="mws-hopcar">{car}</g></g>')
    return front, "".join(css), back


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
        glow = ""  # peaks glow from a blurred copy under them, so the tower stays sharp
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
  <filter id="mws-glow" x="-100%" y="-60%" width="300%" height="220%"><feGaussianBlur stdDeviation="0.9"/></filter>
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
    car_svg = back_svg = ""
    if CAR:
        body, car_css, back = iso_car(corner, cols, rows)
        if back:
            back_svg = f'<g transform="scale(4) translate({fmt(tx)}, 0)">{back}</g>'

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
    return svg[:start] + floor + back_svg + block + car_svg + svg[end:], (
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
