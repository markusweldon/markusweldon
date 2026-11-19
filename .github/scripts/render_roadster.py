#!/usr/bin/env python3
"""Render the README's roadster from a 3D model, in Blender.

The model is "Tesla roadster" by Delta Xeon on Sketchfab, licensed CC BY 4.0
(credited at the bottom of the README). It keeps its own silver paint and
black glass and is lit in the markusweldon.com palette: a hot-pink key from
one side, a cyan rim from the other, a violet glow from above, and an
emissive red light bar. Writes two transparent PNGs of the same car:

  images/roadster-rear.webp                the header view, from behind,
                                           embedded by build_images.py
  .github/scripts/assets/roadster-iso*.webp the Stats card calendar view (four wheel frames) and
  .github/scripts/assets/roadster.json     its placement, embedded by
                                           skyline_isocalendar.py

Usage:
    pip install bpy        (Blender as a Python module)
    python3 .github/scripts/render_roadster.py <model.glb>
    python3 .github/scripts/render_roadster.py --rear <model.glb>   (the header car only)
    python3 .github/scripts/render_roadster.py --finish   (outline + compress only)
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / ".github" / "scripts" / "assets"

PINK, CYAN, VIOLET = (0.976, 0.165, 0.678), (0.212, 0.976, 0.965), (0.48, 0.18, 1.0)

# The calendar maps (weeks a, days b, height) to screen (1.7(a - b), a + b - h)
# and the car is drawn 0.558 calendar units per metre along the ground.
ISO_M = 0.558
ISO_ELEV = math.atan(1 / 1.7)   # the camera elevation that gives that 1.7:1 ground


def setup(model):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(model))
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 96
    sc.cycles.use_denoising = True
    sc.render.film_transparent = True
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"

    world = bpy.data.worlds.new("night")
    sc.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.05, 0.015, 0.1, 1)       # deep violet ambient
    bg.inputs[1].default_value = 1.0

    # The light bar glows red; everything else keeps the model's own look.
    for o in bpy.data.objects:
        if o.type == "MESH" and any(s.material and s.material.name == "Material_3" for s in o.material_slots):
            mat = bpy.data.materials.new("lightbar")
            mat.use_nodes = True
            b = mat.node_tree.nodes["Principled BSDF"]
            b.inputs["Base Color"].default_value = (1, 0.05, 0.12, 1)
            b.inputs["Emission Color"].default_value = (1, 0.06, 0.18, 1)
            b.inputs["Emission Strength"].default_value = 2.5
            o.material_slots[0].material = mat

    def area(name, colour, energy, loc, size):
        light = bpy.data.lights.new(name, "AREA")
        light.color, light.energy, light.size = colour, energy, size
        obj = bpy.data.objects.new(name, light)
        sc.collection.objects.link(obj)
        obj.location = loc
        obj.rotation_euler = (Vector((0, 0, 0.6)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()

    area("pink", PINK, 520, (2.0, -5.0, 2.6), 4.0)       # hot pink from the left of the rear view
    area("cyan", CYAN, 460, (2.0, 5.0, 2.2), 4.0)        # cyan from the right
    area("violet", VIOLET, 320, (0.0, 0.0, 6.0), 6.0)    # violet sky above
    area("rear", VIOLET, 90, (8.0, 0.0, 1.2), 3.0)       # soft fill on the rear face
    return sc


# The wheel parts (tyre and rim per axle, both sides) and their axle centres.
WHEELS = {"Object_24": (-1.56, 0.395), "Object_27": (-1.56, 0.395),
          "Object_30": (1.80, 0.395), "Object_33": (1.80, 0.395)}
WHEEL_FRAMES = 4          # six spokes repeat every 60 degrees: 4 frames of 15


def turn_wheels(angle):
    """Rotate the wheels by angle (radians) about their axles. The car drives
    towards -X, so the tops of the wheels move towards -X: a negative turn
    about +Y."""
    from mathutils import Matrix
    for name, (x, z) in WHEELS.items():
        o = bpy.data.objects.get(name)
        if o is None:
            continue
        if "rest" not in o:
            o["rest"] = [list(r) for r in o.matrix_world]
        rest = Matrix(o["rest"])
        c = Vector((x, 0.0, z))
        o.matrix_world = Matrix.Translation(c) @ Matrix.Rotation(-angle, 4, "Y") @ Matrix.Translation(-c) @ rest
    bpy.context.view_layer.update()


def camera(sc, loc, target, ortho=None, lens=85):
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    bpy.context.view_layer.update()
    if ortho:
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = ortho
    else:
        cam.data.lens = lens
    return cam


def project(sc, cam, point):
    """World point -> pixel (x, y) in the rendered image."""
    from bpy_extras.object_utils import world_to_camera_view
    co = world_to_camera_view(sc, cam, Vector(point))
    return co.x * sc.render.resolution_x, (1 - co.y) * sc.render.resolution_y


def render(sc, path, w, h):
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def crop(path, scale=1.0):
    from PIL import Image
    im = Image.open(path).convert("RGBA")
    box = im.getchannel("A").point(lambda v: 255 if v > 4 else 0).getbbox()
    im = im.crop(box)
    if scale != 1.0:
        im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    im.save(path, optimize=True)
    return box, im.size


def neon_outline(im, pad=6, rim=3, glow=2.2):
    """A faint neon rim traced round the car's silhouette -- pink on the left
    fading to cyan on the right, with a soft glow, like the scenes' line art.
    rim is the grow filter size (3 = a 1 px rim). Returns the padded image."""
    import numpy as np
    from PIL import Image, ImageFilter
    canvas = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad))
    canvas.alpha_composite(im, (pad, pad))
    a = np.asarray(canvas.getchannel("A"), dtype=float) / 255
    solid = Image.fromarray(((a > 0.5) * 255).astype(np.uint8))
    grown = np.asarray(solid.filter(ImageFilter.MaxFilter(rim)), dtype=float) / 255
    edge = np.clip(grown - (a > 0.5), 0, 1)                       # a rim just outside the car
    h, w = edge.shape
    t = np.linspace(0, 1, w)[None, :, None]
    colour = (1 - t) * np.array([249, 42, 173]) + t * np.array([54, 249, 246])
    blur = np.asarray(Image.fromarray((edge * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(glow)),
                      dtype=float) / 255
    line_a = np.clip(edge * 0.85 + blur * 0.9, 0, 1)[..., None]
    base = np.asarray(canvas, dtype=float) / 255
    ba = base[..., 3:4]
    out_a = line_a + ba * (1 - line_a)
    rgb = (colour / 255 * line_a + base[..., :3] * ba * (1 - line_a)) / np.maximum(out_a, 1e-6)
    return Image.fromarray((np.dstack([np.clip(rgb, 0, 1), out_a]) * 255).astype(np.uint8), "RGBA")


def save_webp(im, out):
    """High-quality WebP keeps full colour and alpha at a fraction of the PNG's size."""
    im.save(out, "WEBP", quality=92, alpha_quality=95, method=6)


def finish_rear(raw, out, width=460):
    """The header car: outlined (from the car alone), on its contact shadow,
    with the tail-light bar reflected in the glossy floor below it. Saves
    WebP and records in roadster.json where the car meets the ground and how
    wide its rear is, as shares of the finished image."""
    import numpy as np
    from PIL import Image, ImageFilter
    pad = 6
    car = Image.open(raw).convert("RGBA")
    shadow_file = raw.with_name("roadster-rear-shadow-raw.png")
    shadow = Image.open(shadow_file).convert("RGBA") if shadow_file.exists() else car
    meta_file = ASSETS / "roadster.json"
    meta = json.loads(meta_file.read_text())
    rr = meta["rear_raw"]
    outlined = neon_outline(car, pad=pad)            # the outline traces the car, never its shadow
    # Room below for the reflection.
    contact = rr["contact_y"] + pad
    extra = 0
    canvas = Image.new("RGBA", (outlined.width, outlined.height + extra))
    canvas.alpha_composite(shadow, (pad, pad))
    # The tail-light bar mirrored in the floor: its bright red-pink pixels,
    # flipped about the ground line, stretched and blurred like a reflection
    # in wet asphalt.
    px = np.asarray(car, dtype=float) / 255
    rgb, a = px[..., :3], px[..., 3]
    hi, lo = rgb.max(-1), rgb.min(-1)
    r_, g_, b_ = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    lit = (a > 0.5) & (r_ > 0.55) & (b_ < 0.7 * r_) & (g_ < 0.45 * r_)   # the red light bar, not the pink-lit body
    rows = lit.sum(axis=1)
    if rows.max() > 0:                                       # keep the bar itself: a few rows round its fullest
        peak = int(rows.argmax())
        keep = np.zeros_like(lit)
        keep[max(0, peak - 4):peak + 5] = True
        lit &= keep
    # The bar's glow smeared down the wet floor from where the tyres meet
    # it: each column takes the bar's colour there and fades with distance.
    cols = lit.any(axis=0)
    if cols.any():
        colour = np.zeros((car.width, 3))
        colour[cols] = (rgb * lit[..., None]).sum(axis=0)[cols] / lit.sum(axis=0)[cols][:, None]
        length = max(8, round(car.height * 0.24))
        fall = np.exp(-np.linspace(0, 3.2, length))[:, None] * 0.62     # bright at the car, fading out
        streak = np.zeros((length, car.width, 4))
        streak[..., :3] = colour[None]
        streak[..., 3] = fall * cols[None]
        refl = Image.fromarray((streak * 255).astype(np.uint8), "RGBA").filter(ImageFilter.GaussianBlur(1.6))
        if canvas.height < int(contact) + length:
            grown = Image.new("RGBA", (canvas.width, int(contact) + length))
            grown.alpha_composite(canvas, (0, 0))
            canvas = grown
        canvas.alpha_composite(refl, (pad, int(contact) - 2))
    canvas.alpha_composite(outlined, (0, 0))
    save_webp(canvas, out)
    meta["rear"] = {"contact": contact / canvas.height, "width": rr["width"] / canvas.width}
    meta_file.write_text(json.dumps(meta, indent=1))


def finish_iso():
    """The calendar car: each raw wheel frame outlined and saved as WebP, with
    the placement in roadster.json grown to cover the padding. The rim is
    thicker than the header's because this car is drawn far smaller."""
    from PIL import Image
    meta_file = ASSETS / "roadster.json"
    meta = json.loads(meta_file.read_text())
    raw = meta["iso_raw"]
    pad = 5
    frames = []
    for k in range(raw["frames"]):
        im = Image.open(ASSETS / f"roadster-iso-raw-{k}.png").convert("RGBA")
        out = neon_outline(im, pad=pad, rim=5, glow=1.6)
        save_webp(out, ASSETS / f"roadster-iso-{k}.webp")
        frames.append(out)
    save_webp(frames[0], ASSETS / "roadster-iso.webp")
    upp = raw["w"] / im.width
    meta["iso"] = {"x": raw["x"] - pad * upp, "y": raw["y"] - pad * upp,
                   "w": raw["w"] + 2 * pad * upp, "h": raw["h"] + 2 * pad * upp, "frames": raw["frames"]}
    meta_file.write_text(json.dumps(meta, indent=1))


# The header's grid puts the eye at this height, as a share of the car's width:
# where the car touches the ground, the horizon is EYE car-widths above it.
# Rendering from the same height is what makes the car sit on the grid.
EYE = 0.7
CAR_W = 2.248             # the model's width in metres (its bounding box)


def ground_catcher(sc):
    """An invisible floor that only catches shadows, so the render carries
    the car's own contact shadow."""
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
    plane = bpy.context.active_object
    plane.is_shadow_catcher = True
    return plane


def render_rear(sc):
    """The header car from behind, at the grid's eye height, twice: the car
    alone (for the outline) and over a shadow-catching floor (for its
    shadow). Both share one crop. Records where the car meets the ground and
    how wide its rear is, as shares of the image, in roadster.json."""
    from PIL import Image
    cam = camera(sc, (11.5, 0.0, EYE * CAR_W), (0.0, 0.0, 0.55), lens=70)
    W, H = 1400, 900
    car = ASSETS / "roadster-rear-raw.png"           # kept, so the finish can be redone without Blender
    shadow = ASSETS / "roadster-rear-shadow-raw.png"
    render(sc, car, W, H)
    plane = ground_catcher(sc)
    render(sc, shadow, W, H)
    bpy.data.objects.remove(plane, do_unlink=True)
    ims = [Image.open(f).convert("RGBA") for f in (car, shadow)]
    box = ims[1].getchannel("A").point(lambda v: 255 if v > 40 else 0).getbbox()   # the shadow's body, not its faint tails
    contact = project(sc, cam, (1.80, 0.0, 0.0))     # the ground under the rear axle, where the tyres touch
    left, right = (project(sc, cam, (2.68, y, 0.0)) for y in (-CAR_W / 2, CAR_W / 2))
    scale = 460 / (box[2] - box[0])
    for f, im in zip((car, shadow), ims):
        im = im.crop(box)
        im.resize((460, round(im.height * scale)), Image.LANCZOS).save(f, optimize=True)
    meta_file = ASSETS / "roadster.json"
    meta = json.loads(meta_file.read_text()) if meta_file.exists() else {}
    meta["rear_raw"] = {"contact_y": (contact[1] - box[1]) * scale,
                        "width": abs(right[0] - left[0]) * scale}
    meta_file.write_text(json.dumps(meta, indent=1))
    rear = ROOT / "images" / "roadster-rear.webp"
    finish_rear(car, rear)
    return rear


def main(model):
    sc = setup(model)
    (ROOT / "images").mkdir(exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)

    rear = render_rear(sc)

    # Calendar: orthographic, at the calendar's angle. The car drives towards
    # the older weeks (-a), so its rear (+X) points along +a, towards the
    # viewer's lower right; days (+b) run to the lower left.
    # Seen from (+X, -Y): +X (the rear) runs to the lower right, -Y to the lower left.
    horiz = Vector((1, -1, 0)).normalized()
    d = 30.0
    loc = horiz * (d * math.cos(ISO_ELEV)) + Vector((0, 0, d * math.sin(ISO_ELEV)))
    ortho = 7.5
    cam = camera(sc, tuple(loc), (0.0, 0.0, 0.0), ortho=ortho)
    W, H = 900, 900
    sc.render.resolution_x, sc.render.resolution_y = W, H
    pa, p0 = project(sc, cam, (1, 0, 0)), project(sc, cam, (0, 0, 0))
    assert pa[0] > p0[0] and pa[1] > p0[1], "the rear must point to the lower right"
    frames = []
    for k in range(WHEEL_FRAMES):                  # the same view with the wheels a little further round
        turn_wheels(math.radians(60 / WHEEL_FRAMES * k))
        f = ASSETS / f"roadster-iso-raw-{k}.png"
        render(sc, f, W, H)
        frames.append(f)
    turn_wheels(0.0)
    nose = project(sc, cam, (-2.44, 0.0, 0.0))     # the car's front, on the ground, centreline
    from PIL import Image
    ims = [Image.open(f).convert("RGBA") for f in frames]
    box = None
    for im in ims:                                 # one crop for every frame, so they line up
        b = im.getchannel("A").point(lambda v: 255 if v > 4 else 0).getbbox()
        box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
    size = (box[2] - box[0], box[3] - box[1])
    # Calendar units per pixel: a metre along the ground covers ISO_M * |(1.7, 1)|
    # calendar units, and this camera draws it |proj(a)| pixels long.
    pa, p0 = project(sc, cam, (1, 0, 0)), project(sc, cam, (0, 0, 0))
    px_per_m = math.hypot(pa[0] - p0[0], pa[1] - p0[1])
    upp = ISO_M * math.hypot(1.7, 1.0) / px_per_m
    # Shrink the PNG: it's drawn about 30 calendar units wide at 4 px each.
    scale = min(1.0, 140 / size[0])
    for k, (f, im) in enumerate(zip(frames, ims)):
        im = im.crop(box)
        im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
        im.save(f, optimize=True)
    meta = {"iso_raw": {"x": (box[0] - nose[0]) * upp, "y": (box[1] - nose[1]) * upp,
                        "w": size[0] * upp, "h": size[1] * upp, "frames": WHEEL_FRAMES}}
    (ASSETS / "roadster.json").write_text(json.dumps(meta, indent=1))
    finish_iso()
    print("rear", Image.open(rear).size, "iso", im.size, json.loads((ASSETS / "roadster.json").read_text()))


if __name__ == "__main__":
    if sys.argv[1:] == ["--finish"]:                  # redo both cars' outline and compression only
        finish_rear(ASSETS / "roadster-rear-raw.png", ROOT / "images" / "roadster-rear.webp")
        finish_iso()
    elif len(sys.argv) == 3 and sys.argv[1] == "--rear":   # re-render the header car only
        render_rear(setup(Path(sys.argv[2]).resolve()))
    elif len(sys.argv) == 2:
        main(Path(sys.argv[1]).resolve())
    else:
        sys.exit(__doc__)
