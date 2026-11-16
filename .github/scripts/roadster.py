#!/usr/bin/env python3
"""A 3D model of the README's roadster, rendered to PNG for the header and
the Stats card's calendar, so both show exactly the same car.

The car is a low wedge in silver with dark bronze glass: a flat hood, a
long fastback canopy that narrows towards the tail between creased rear
haunches, a sharp shoulder crease rising towards the rear, a dark lower
band, big five-spoke wheels, and a tall rear face with a thin full-width
red light bar, a plain plate, four round pipes and a finned diffuser. No
badges or lettering. Surfaces reflect the scene: magenta sky on top, pink
city light on the flanks, cyan grid underneath.

A small z-buffer rasteriser (numpy) renders it with supersampling, and
the lights are bloomed. Writes:
  images/roadster-rear.png                 the header view, from behind,
                                           embedded by build_images.py
  .github/scripts/assets/roadster-iso.png  the calendar view (isometric) and
  .github/scripts/assets/roadster.json     its placement, embedded by
                                           skyline_isocalendar.py in CI

Usage: python3 .github/scripts/roadster.py   (needs numpy and Pillow)
"""
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[2]

# ── Shape (metres; x forward from the rear face, y left, z up) ─────────────
LENGTH = 4.3
WING = False                 # an 80s-style rear wing; off so the rear fins show
WHEELS = (0.95, 3.45)        # axle positions
TYRE_R, TYRE_W, RIM_R = 0.36, 0.30, 0.27


def smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def half_width(x):
    w = 0.97 + 0.03 * smooth(x / 0.3)                         # wide rear haunches
    w -= 0.07 * smooth((x - 1.4) / 0.9)                       # haunch to waist
    w -= 0.08 * min(1.0, max(0.0, (x - 3.2) / 1.1))           # straight-edged nose taper
    return w


def shoulder(x):
    """The crease along the side: rising from the nose towards the rear."""
    # Flat planes, like an 80s wedge: one straight line from the haunch to
    # the front axle, a steeper one down to a low, sharp nose.
    if x <= WHEELS[1]:
        return lerp(0.84, 0.74, x / WHEELS[1])
    return lerp(0.74, 0.5, (x - WHEELS[1]) / (LENGTH - WHEELS[1]))


def roof(x):
    """Canopy centreline height; None where there is no glass."""
    if 0.55 <= x <= 1.9:
        return lerp(0.98, 1.1, (x - 0.55) / 1.35)
    if 1.9 < x <= 3.25:                                      # long, raked windscreen
        return lerp(1.1, shoulder(3.25) + 0.08, (x - 1.9) / 1.35)
    return None


def fin(x):
    """The pointed sail fins either side of the rear glass: rising from the
    deck's trailing edge to a sharp peak where the glass ends, then fading
    into the glass edge further forward."""
    if x <= 0.1 or x >= 1.9:
        return 0.0
    if x <= 0.55:
        return 0.2 * (x - 0.1) / 0.45
    return 0.2 * (1.9 - x) / 1.35


def glass_half(x):
    return 0.42 + 0.32 * min(1.0, max(0.0, (x - 0.55) / 2.1))      # straight edges, narrowing rearwards


def arch_lift(x):
    """Height the lower side is cut up to around each wheel."""
    lift = 0.0
    for c in WHEELS:
        d = abs(x - c)
        if d < 0.5:                                  # squared-off 80s arch: flat top, sloped sides
            lift = max(lift, 0.74 if d < 0.27 else lerp(0.74, 0.3, (d - 0.27) / 0.23))
    return lift


def section(x):
    """Left half of the cross-section, sill to centreline: (y, z, material)."""
    w, zs = half_width(x), shoulder(x)
    zd = zs + 0.06
    lift = arch_lift(x)
    pts = []
    for y, z in ((0.8 * w, 0.14), (0.95 * w, 0.32), (w, 0.48)):
        if lift and z < lift:
            z = min(lift, zs - 0.05)
            y = 0.97 * w
        pts.append([y, z])
    pts.append([0.995 * w, zs])                    # shoulder crease
    pts.append([0.88 * w, zd])                      # top of the side wall
    r = roof(x)
    g = glass_half(x)
    f = fin(x)
    if r is None:                                   # hood / flat rear deck
        top = zd - 0.04 if x > 3 else zd + 0.03     # the hood sits between the fenders
        pts += [[g, top + f], [(0.88 - 1.6 * f) * g, top], [0.45 * g, top + 0.003], [0.0, top + 0.005]]
        cabin = False
    else:
        # Flat, sharp-edged glass: a short steep edge, then a flat roof. At
        # the rear the fins rise above it, so the glass sits down between them.
        ze = zd + 0.07
        pts += [[g, ze + f], [(0.93 - 1.6 * f) * g, r - 0.035], [0.5 * g, r - 0.004], [0.0, r]]
        cabin = True
    # The face from the glass edge point inward is glass, except where a fin
    # rises: there it's body, and the glass starts at the fin's inner foot.
    edge = "body" if (f > 0.02 or not cabin) else "glass"
    mats = ["trim", "body", "body", "body", "body", edge] + (["glass"] * 2 if cabin else ["body"] * 2)
    return [(-y, z) for y, z in pts], mats


# ── Mesh ───────────────────────────────────────────────────────────────────
class Mesh:
    def __init__(self):
        self.tris, self.mats = [], []

        self.norms = []
        self.lines = []          # (points, colour, width in pixels at 1x)

    def line(self, pts, colour, width=1.2):
        self.lines.append(([np.asarray(p, dtype=float) for p in pts], colour, width))

    def prism(self, bottom, top, mat):
        n = len(bottom)
        for i in range(n):
            j = (i + 1) % n
            self.quad(bottom[i], bottom[j], top[j], top[i], mat)
        self.fan(top, mat)
        self.fan(bottom, mat)

    def tri(self, a, b, c, mat, normals=None):
        self.tris.append((a, b, c))
        self.mats.append(mat)
        self.norms.append(normals)

    def quad(self, a, b, c, d, mat, normals=None):
        self.tri(a, b, c, mat, None if normals is None else (normals[0], normals[1], normals[2]))
        self.tri(a, c, d, mat, None if normals is None else (normals[0], normals[2], normals[3]))

    def fan(self, pts, mat, centre=None):
        c = centre if centre is not None else np.mean(pts, axis=0)
        for i in range(len(pts)):
            self.tri(c, pts[i], pts[(i + 1) % len(pts)], mat)


def build() -> Mesh:
    m = Mesh()
    xs = sorted(set([0.0, 0.015, 0.04] + list(np.linspace(0.08, LENGTH - 0.08, 60))
                    + [LENGTH - 0.04, LENGTH - 0.015, LENGTH]
                    + [c + d for c in WHEELS for d in (-0.5, -0.4, -0.27, -0.2, 0, 0.2, 0.27, 0.4, 0.5)]
                    + [0.1, 0.55, 0.551, 3.25, 3.251]))
    rings, ring_mats = [], []
    for x in xs:
        half, mt = section(x)
        nose = smooth((x - (LENGTH - 0.18)) / 0.18)
        full = half + [(-y, z) for y, z in reversed(half[:-1])]
        ring = [np.array([x, y * (1 - 0.05 * nose), z * (1 - 0.08 * nose) + 0.02 * nose]) for y, z in full]
        rings.append(ring)
        ring_mats.append(mt + list(reversed(mt)))
    # Normals smooth along the car but crisp across its creases.
    def edge_normal(i, j):
        a, b = rings[max(i - 1, 0)], rings[min(i + 1, len(rings) - 1)]
        along = (b[j] + b[j + 1]) / 2 - (a[j] + a[j + 1]) / 2
        n = np.cross(along, rings[i][j + 1] - rings[i][j])
        mid = (rings[i][j] + rings[i][j + 1]) / 2
        if n @ (mid - np.array([mid[0], 0.0, 0.5])) < 0:
            n = -n
        return n / (np.linalg.norm(n) or 1)
    for i in range(len(rings) - 1):
        r0, r1 = rings[i], rings[i + 1]
        for j in range(len(r0) - 1):
            n0, n1 = edge_normal(i, j), edge_normal(i + 1, j)
            ma, mb = ring_mats[i][j], ring_mats[i + 1][j]
            mat = "glass" if "glass" in (ma, mb) and ma == mb else ("body" if "glass" in (ma, mb) else ma)
            m.quad(r0[j], r1[j], r1[j + 1], r0[j + 1], mat, (n0, n1, n1, n0))
    # Underbody and end caps.
    for r0, r1 in zip(rings, rings[1:]):
        m.quad(r0[-1], r1[-1], r1[0], r0[0], "trim")
    m.fan(rings[0], "body", np.array([0.0, 0.0, 0.5]))
    m.fan(rings[-1], "trim", np.array([LENGTH, 0.0, 0.4]))

    # Neon edges along the creases: pink on the body, cyan round the glass.
    n = len(rings[0])
    for j in (3, n - 4):                                     # shoulder creases
        m.line([r[j] for r in rings], NEON_PINK, 1.3)
    cab = [i for i, x in enumerate(xs) if roof(x) is not None]
    for j in (6, n - 7):                                     # glass edges
        m.line([rings[i][j] for i in cab], NEON_CYAN, 1.1)
    m.line([rings[cab[-1]][j] for j in range(6, n - 6)], NEON_CYAN, 1.1)   # windscreen base
    m.line([rings[cab[0]][j] for j in range(6, n - 6)], NEON_CYAN, 1.1)    # rear glass edge
    finned = [i for i, x in enumerate(xs) if fin(x) > 0.0]
    for j in (5, n - 6):                                     # fin crests
        m.line([rings[i][j] for i in finned], NEON_PINK, 1.1)
    m.line(rings[0][2:n - 2], NEON_PINK, 1.3)                # rear face outline
    for c in WHEELS:                                         # arch outlines
        arch = [i for i, x in enumerate(xs) if abs(x - c) <= 0.5]
        for j in (2, n - 3):
            m.line([rings[i][j] for i in arch], NEON_PINK, 1.1)

    if WING:
        add_wing(m)
    return finish(m)


def add_wing(m):
    """A big rear wing on two struts, as on the 80s wedge and the track roadster."""
    wy, xl, xt = 0.98, 0.42, -0.04                           # half span, leading and trailing edge
    zl, zt, th = 1.12, 1.18, 0.035
    bottom = [np.array(p) for p in ((xt, -wy, zt), (xl, -wy, zl), (xl, wy, zl), (xt, wy, zt))]
    top = [p + np.array([0, 0, th]) for p in bottom]
    m.prism(bottom, top, "body")
    for s in (-1, 1):
        ep = [np.array(p) for p in ((xt - 0.02, s * wy, zt - 0.1), (xl + 0.04, s * wy, zl - 0.08),
                                    (xl + 0.04, s * wy, zl + 0.08), (xt - 0.02, s * wy, zt + 0.1))]
        m.prism(ep, [p + np.array([0, s * 0.02, 0]) for p in ep], "body")
        m.line(ep + [ep[0]], NEON_PINK, 1.1)
        deck = section(0.2)[0][7][1] + 0.01
        sb = [np.array(p) for p in ((0.12, s * 0.42 - 0.02, deck), (0.3, s * 0.42 - 0.02, deck),
                                    (0.3, s * 0.42 + 0.02, deck), (0.12, s * 0.42 + 0.02, deck))]
        st = [np.array(p) for p in ((0.1, s * 0.42 - 0.02, zt - 0.01), (0.26, s * 0.42 - 0.02, zl + 0.02),
                                    (0.26, s * 0.42 + 0.02, zl + 0.02), (0.1, s * 0.42 + 0.02, zt - 0.01))]
        m.prism(sb, st, "trim")
    m.line([top[0], top[3]], NEON_PINK, 1.3)                 # trailing edge
    m.line([top[1], top[2]], NEON_PINK, 1.1)                 # leading edge
    m.quad(np.array([xt - 0.004, -wy * 0.96, zt + 0.004]), np.array([xt - 0.004, wy * 0.96, zt + 0.004]),
           np.array([xt - 0.004, wy * 0.96, zt + th - 0.004]), np.array([xt - 0.004, -wy * 0.96, zt + th - 0.004]), "light")



def finish(m):
    """Rear face details, haunch vents and wheels."""
    # Rear face details, just behind the cap.
    w0 = half_width(0.0)
    X = -0.006
    m.quad(np.array([X, -0.82 * w0, 0.14]), np.array([X, 0.82 * w0, 0.14]),
           np.array([X, 0.965 * w0, 0.42]), np.array([X, -0.965 * w0, 0.42]), "trim")
    zb = shoulder(0.0) - 0.05
    m.quad(np.array([X, -0.985 * w0, zb - 0.019]), np.array([X, 0.985 * w0, zb - 0.019]),
           np.array([X, 0.985 * w0, zb + 0.019]), np.array([X, -0.985 * w0, zb + 0.019]), "light")
    m.quad(np.array([X - 0.001, -0.95 * w0, zb - 0.004]), np.array([X - 0.001, 0.95 * w0, zb - 0.004]),
           np.array([X - 0.001, 0.95 * w0, zb + 0.004]), np.array([X - 0.001, -0.95 * w0, zb + 0.004]), "core")
    for s in (-1, 1):                               # the bar wraps the corners
        m.quad(np.array([X, s * 0.985 * w0, zb - 0.013]), np.array([0.12, s * 0.996 * half_width(0.12), zb - 0.013]),
               np.array([0.12, s * 0.996 * half_width(0.12), zb + 0.013]), np.array([X, s * 0.985 * w0, zb + 0.013]), "light")
        m.quad(np.array([0.2, s * 1.0 * half_width(0.2), 0.52]), np.array([0.3, s * 1.0 * half_width(0.3), 0.52]),
               np.array([0.3, s * 1.0 * half_width(0.3), 0.55]), np.array([0.2, s * 1.0 * half_width(0.2), 0.55]), "light")
    m.quad(np.array([X - 0.002, -0.17, 0.47]), np.array([X - 0.002, 0.17, 0.47]),
           np.array([X - 0.002, 0.17, 0.58]), np.array([X - 0.002, -0.17, 0.58]), "plate")
    for py in (-0.39, -0.13, 0.13, 0.39):           # four round pipes
        ring_o, ring_i = [], []
        for k in range(20):
            a = 2 * math.pi * k / 20
            ring_o.append(np.array([X - 0.003, py + 0.055 * math.cos(a), 0.27 + 0.055 * math.sin(a)]))
            ring_i.append(np.array([X - 0.004, py + 0.036 * math.cos(a), 0.27 + 0.036 * math.sin(a)]))
        for k in range(20):
            m.quad(ring_o[k], ring_o[(k + 1) % 20], ring_i[(k + 1) % 20], ring_i[k], "pipe")
        m.fan(ring_i, "hole")
    pl = [np.array([X - 0.004, y, z]) for y, z in ((-0.17, 0.47), (0.17, 0.47), (0.17, 0.58), (-0.17, 0.58))]
    m.line(pl + [pl[0]], NEON_CYAN, 0.9)
    for fy in (-0.72, -0.6, 0.6, 0.72):             # diffuser fins
        m.quad(np.array([X - 0.004, fy - 0.012, 0.14]), np.array([X - 0.004, fy + 0.012, 0.14]),
               np.array([X - 0.004, fy + 0.012, 0.36]), np.array([X - 0.004, fy - 0.012, 0.36]), "fin")

    # Vent slots on the haunches either side of the rear glass.
    def haunch(x, t):
        half, _ = section(x)
        (y4, z4), (y5, z5) = half[4], half[5]
        return lerp(y4, y5, t), lerp(z4, z5, t)
    for s in (-1, 1):
        xs_v = np.linspace(0.75, 1.7, 9)
        for x0, x1 in zip(xs_v, xs_v[1:]):
            ta, tb = lerp(0.62, 0.7, (x0 - 0.75) / 0.95), lerp(0.62, 0.7, (x1 - 0.75) / 0.95)
            q = []
            for x, t in ((x0, ta), (x1, tb), (x1, tb + 0.16), (x0, ta + 0.16)):
                y, z = haunch(x, t)
                q.append(np.array([x, -s * y, z + 0.015]))
            m.quad(*q, "hole")

    # Wheels: tyre, sidewall, dark rim with five twisted silver spokes.
    seg = 40
    for xc in WHEELS:
        for s in (-1, 1):
            yo = s * (half_width(xc) - 0.03)          # outer face
            yi = yo - s * TYRE_W
            outer, inner = [], []
            for k in range(seg):
                a = 2 * math.pi * k / seg
                outer.append(np.array([xc + TYRE_R * math.cos(a), yo, TYRE_R + TYRE_R * math.sin(a)]))
                inner.append(np.array([xc + TYRE_R * math.cos(a), yi, TYRE_R + TYRE_R * math.sin(a)]))
            rim = [np.array([xc + RIM_R * math.cos(2 * math.pi * k / seg), yo + s * 0.004,
                             TYRE_R + RIM_R * math.sin(2 * math.pi * k / seg)]) for k in range(seg)]
            for k in range(seg):
                n = (k + 1) % seg
                m.quad(outer[k], outer[n], inner[n], inner[k], "tyre")
                m.quad(outer[k], outer[n], rim[n], rim[k], "tyre")
            m.fan(rim, "rim", np.array([xc, yo + s * 0.004, TYRE_R]))
            for k in range(5):
                a0 = 2 * math.pi * k / 5 + 0.15
                hub, tip = 0.05, RIM_R - 0.01
                pts = [(hub, a0 - 0.32), (tip, a0 - 0.02), (tip, a0 + 0.12), (hub, a0 + 0.36)]
                quad = [np.array([xc + r * math.cos(a), yo + s * 0.012, TYRE_R + r * math.sin(a)]) for r, a in pts]
                m.quad(*quad, "spoke")
            m.fan([np.array([xc + 0.05 * math.cos(2 * math.pi * k / 12), yo + s * 0.014,
                             TYRE_R + 0.05 * math.sin(2 * math.pi * k / 12)]) for k in range(12)], "spoke")
    return m


# ── Shading ────────────────────────────────────────────────────────────────
def hexrgb(h):
    return np.array([int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)])


NEON_PINK, NEON_CYAN = "#ff4fc8", "#36f9f6"
BASE = {"body": hexrgb("#1d0a33"), "trim": hexrgb("#0a0712"), "glass": hexrgb("#07040f"),
        "tyre": hexrgb("#0b0a0f"), "rim": hexrgb("#14101e"), "spoke": hexrgb("#8c7fb2"),
        "plate": hexrgb("#2c2142"), "pipe": hexrgb("#ffb35c"), "hole": hexrgb("#08060c"),
        "fin": hexrgb("#221d2c"), "light": hexrgb("#ff2a4a"), "core": hexrgb("#ffd6de")}
EMISSIVE = {"light", "pipe", "core"}
REFLECT = {"body": 0.4, "trim": 0.1, "glass": 0.32, "tyre": 0.04, "rim": 0.1, "spoke": 0.35,
           "plate": 0.1, "fin": 0.1, "hole": 0.0}
SKY_TOP, SKY_MID, CITY, GRID = hexrgb("#5a24c8"), hexrgb("#f92aad"), hexrgb("#b01fff"), hexrgb("#36f9f6")
KEY = np.array([-0.45, 0.45, 0.77]) / np.linalg.norm([-0.45, 0.45, 0.77])


def env(n):
    z = n[2]
    if z >= 0.25:
        return lerp(SKY_MID, SKY_TOP, smooth((z - 0.25) / 0.75))
    if z >= -0.15:
        return lerp(CITY * 0.5, SKY_MID * 0.85, smooth((z + 0.15) / 0.4))
    return lerp(GRID * 0.7, CITY * 0.5, smooth((z + 1) / 0.85))


def shade(mat, n, view):
    base = BASE[mat]
    if mat in EMISSIVE:
        return base, 1.0
    if mat in ("light",):
        return base, 1.0
    diff = max(0.0, float(n @ KEY))
    col = base * (0.1 + 0.62 * diff) + env(n) * REFLECT.get(mat, 0.2)
    h = KEY + view
    h = h / np.linalg.norm(h)
    sp = max(0.0, float(n @ h))
    shine = {"body": (0.5, 45), "glass": (0.6, 80), "spoke": (0.4, 40)}.get(mat)
    if shine:
        col = col + shine[0] * sp ** shine[1]
    return np.clip(col, 0, 1), 0.0


# ── Rasteriser ─────────────────────────────────────────────────────────────
def render(mesh, project, view, px_per_unit, pad=10, ss=3, bloom=True, depth_tol=0.06):
    """project(p) -> (sx, sy, depth) with smaller depth nearer. Returns an
    RGBA image and (x0, y0, scale): the image's top-left in projected units
    and units per pixel."""
    P = np.array([[project(v) for v in t] for t in mesh.tris])          # (n, 3, 3)
    xmin, ymin = P[:, :, 0].min(), P[:, :, 1].min()
    xmax, ymax = P[:, :, 0].max(), P[:, :, 1].max()
    s = px_per_unit * ss
    W = int(math.ceil((xmax - xmin) * s)) + 2 * pad * ss
    H = int(math.ceil((ymax - ymin) * s)) + 2 * pad * ss
    ox, oy = xmin - pad * ss / s, ymin - pad * ss / s
    zbuf = np.full((H, W), np.inf)
    rgb = np.zeros((H, W, 3))
    alpha = np.zeros((H, W))
    glow = np.zeros((H, W, 3))
    for (a, b, c), mat, tri, vn in zip(P, mesh.mats, mesh.tris, mesh.norms):
        A = np.array(tri)
        n = np.cross(A[1] - A[0], A[2] - A[0])
        ln = np.linalg.norm(n)
        if ln < 1e-12:
            continue
        n = n / ln
        cen = A.mean(axis=0)
        if mat in ("tyre", "rim", "spoke"):
            if n @ view < 0:
                n = -n
            back = False
        else:
            if n @ (cen - np.array([cen[0], 0.0, 0.5])) < 0:   # point it outwards
                n = -n
            back = n @ view < 0
            if mat in ("light", "core", "plate", "pipe", "hole", "fin") and back:
                n, back = -n, False
        col, emit = shade(mat, n, view)
        cols = None
        if vn is not None and not back:
            cols = [shade(mat, v, view)[0] for v in vn]
        if back and mat in ("body", "trim", "glass"):
            col, cols = hexrgb("#0a0810"), None        # inside of a wheel well
        x = (np.array([a[0], b[0], c[0]]) - ox) * s
        y = (np.array([a[1], b[1], c[1]]) - oy) * s
        z = np.array([a[2], b[2], c[2]])
        x0, x1 = max(int(x.min()), 0), min(int(x.max()) + 1, W)
        y0, y1 = max(int(y.min()), 0), min(int(y.max()) + 1, H)
        if x0 >= x1 or y0 >= y1:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
        d = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
        if abs(d) < 1e-12:
            continue
        w0 = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / d
        w1 = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / d
        w2 = 1 - w0 - w1
        inside = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if not inside.any():
            continue
        depth = w0 * z[0] + w1 * z[1] + w2 * z[2]
        if mat in ("light", "core", "plate", "pipe", "hole", "fin", "spoke"):
            depth = depth - 1e-3                      # decals win against their panel
        zb = zbuf[y0:y1, x0:x1]
        win = inside & (depth < zb)
        zb[win] = depth[win]
        if cols is None:
            rgb[y0:y1, x0:x1][win] = col
        else:
            rgb[y0:y1, x0:x1][win] = (w0[win, None] * cols[0] + w1[win, None] * cols[1] + w2[win, None] * cols[2])
        alpha[y0:y1, x0:x1][win] = 1.0
        g = glow[y0:y1, x0:x1]
        g[win] = col * emit
    # Neon edges: drawn where they're not hidden behind the body, and bloomed.
    for pts, colour, width in mesh.lines:
        col = hexrgb(colour)
        rad = max(1.0, width * W * 0.0022)          # widths are relative to the car's size
        r = int(math.ceil(rad))
        oyy, oxx = np.mgrid[-r:r + 1, -r:r + 1]
        disc = (oxx ** 2 + oyy ** 2) <= rad * rad
        for p0, p1 in zip(pts, pts[1:]):
            a, b = np.array(project(p0)), np.array(project(p1))
            steps = int(max(abs(b[0] - a[0]), abs(b[1] - a[1])) * s / max(rad * 0.6, 0.5)) + 1
            for t in np.linspace(0, 1, steps + 1):
                q = a + (b - a) * t
                cx, cy = int((q[0] - ox) * s), int((q[1] - oy) * s)
                if not (r <= cx < W - r and r <= cy < H - r):
                    continue
                zl = zbuf[cy - r:cy + r + 1, cx - r:cx + r + 1]
                vis = disc & (q[2] <= zl + depth_tol)
                if not vis.any():
                    continue
                rgb[cy - r:cy + r + 1, cx - r:cx + r + 1][vis] = col
                alpha[cy - r:cy + r + 1, cx - r:cx + r + 1][vis] = 1.0
                glow[cy - r:cy + r + 1, cx - r:cx + r + 1][vis] = col
    img = np.dstack([rgb, alpha])
    im = Image.fromarray((img * 255).astype(np.uint8), "RGBA")
    im = im.resize((W // ss, H // ss), Image.LANCZOS)
    if bloom and glow.any():
        gim = Image.fromarray((np.clip(glow, 0, 1) * 255).astype(np.uint8), "RGB").resize((W // ss, H // ss), Image.LANCZOS)
        wf = W // ss                                  # glow sized to the image, so it fades inside the padding
        g1 = np.asarray(gim.filter(ImageFilter.GaussianBlur(max(0.6, wf * 0.004))), dtype=float) / 255
        g2 = np.asarray(gim.filter(ImageFilter.GaussianBlur(max(1.0, wf * 0.012))), dtype=float) / 255
        bloom_rgb = np.clip(g1 * 0.9 + g2 * 1.1, 0, 1)
        base = np.asarray(im, dtype=float) / 255
        a = base[:, :, 3:4]
        lum = bloom_rgb.max(axis=2, keepdims=True)
        out_a = np.clip(a + lum * (1 - a), 0, 1)
        out_rgb = (base[:, :, :3] * a + bloom_rgb) / np.maximum(out_a, 1e-6)
        im = Image.fromarray((np.dstack([np.clip(out_rgb, 0, 1), out_a]) * 255).astype(np.uint8), "RGBA")
    return im, (ox, oy, 1 / px_per_unit)


# ── Cameras ────────────────────────────────────────────────────────────────
REAR_CAM = np.array([-7.6, 0.0, 2.35])
REAR_LOOK = np.array([2.2, 0.0, 0.55])


def rear_projector(focal=1.0):
    f = REAR_LOOK - REAR_CAM
    f = f / np.linalg.norm(f)
    r = np.cross(f, [0, 0, 1.0])
    r = r / np.linalg.norm(r)
    u = np.cross(r, f)

    def project(p):
        d = np.asarray(p) - REAR_CAM
        zc = d @ f
        return (focal * (d @ r) / zc, -focal * (d @ u) / zc, zc)
    view = -f
    return project, view


# The calendar: weeks run along a, days along b; the plugin projects (a, b,
# height) to (1.7(a - b), a + b - height). The car drives towards the older
# weeks (-a), tail towards the viewer, so x (forward) maps to -a.
ISO_M = 0.558      # calendar units per metre along the ground
ISO_Z = 1.1        # height units per metre


def iso_project(p):
    x, y, z = p
    a = (LENGTH - x) * ISO_M
    b = y * ISO_M
    zz = z * ISO_Z
    return (1.7 * (a - b), a + b - zz, -(a + b + 2 * zz))


ISO_VIEW = np.array([-1 / ISO_M, 1 / ISO_M, 2 / ISO_Z])
ISO_VIEW = ISO_VIEW / np.linalg.norm(ISO_VIEW)


def crop(im, ox, oy, upp):
    """Trim transparent margins; return the image and its new top-left."""
    box = im.getchannel("A").point(lambda v: 255 if v > 6 else 0).getbbox()
    return im.crop(box), (ox + box[0] * upp, oy + box[1] * upp)


def main():
    import json
    mesh = build()
    proj, view = rear_projector()
    rear, (ox, oy, upp) = render(mesh, proj, view, px_per_unit=1500)
    rear, _ = crop(rear, ox, oy, upp)
    rear = rear.resize((460, round(rear.height * 460 / rear.width)), Image.LANCZOS)
    rear.save(ROOT / "images" / "roadster-rear.png", optimize=True)
    iso, (ix, iy, iupp) = render(mesh, iso_project, ISO_VIEW, px_per_unit=18, pad=4)
    iso, (ix, iy) = crop(iso, ix, iy, iupp)
    assets = ROOT / ".github" / "scripts" / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    iso.save(assets / "roadster-iso.png", optimize=True)
    # The iso image's top-left and size in calendar units, relative to the
    # car's nose on the road centreline.
    meta = {"iso": {"x": ix, "y": iy, "w": iso.width * iupp, "h": iso.height * iupp}}
    (assets / "roadster.json").write_text(json.dumps(meta, indent=1))
    print("rear", rear.size, "iso", iso.size, meta)


if __name__ == "__main__":
    main()
