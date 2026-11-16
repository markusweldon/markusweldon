#!/usr/bin/env python3
"""Render the README's roadster from a 3D model, in Blender.

The model is "Tesla roadster" by Delta Xeon on Sketchfab, licensed CC BY 4.0
(credited at the bottom of the README). It keeps its own silver paint and
black glass and is lit in the markusweldon.com palette: a hot-pink key from
one side, a cyan rim from the other, a violet glow from above, and an
emissive red light bar. Writes two transparent PNGs of the same car:

  images/roadster-rear.png                 the header view, from behind,
                                           embedded by build_images.py
  .github/scripts/assets/roadster-iso.png  the Stats card calendar view and
  .github/scripts/assets/roadster.json     its placement, embedded by
                                           skyline_isocalendar.py

Usage:
    pip install bpy        (Blender as a Python module)
    python3 .github/scripts/render_roadster.py <model.glb>
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


def main(model):
    sc = setup(model)
    (ROOT / "images").mkdir(exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)

    # Header: from behind (+X is the rear), a little above, matching the grid.
    camera(sc, (11.5, 0.0, 2.7), (0.0, 0.0, 0.55), lens=70)
    rear = ROOT / "images" / "roadster-rear.png"
    render(sc, rear, 1400, 900)
    crop(rear)
    from PIL import Image
    im = Image.open(rear)
    if im.width != 460:
        im.resize((460, round(im.height * 460 / im.width)), Image.LANCZOS).save(rear, optimize=True)

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
    iso = ASSETS / "roadster-iso.png"
    render(sc, iso, W, H)
    nose = project(sc, cam, (-2.44, 0.0, 0.0))     # the car's front, on the ground, centreline
    box, size = crop(iso)
    # Calendar units per pixel: a metre along the ground covers ISO_M * |(1.7, 1)|
    # calendar units, and this camera draws it |proj(a)| pixels long.
    pa, p0 = project(sc, cam, (1, 0, 0)), project(sc, cam, (0, 0, 0))
    px_per_m = math.hypot(pa[0] - p0[0], pa[1] - p0[1])
    upp = ISO_M * math.hypot(1.7, 1.0) / px_per_m
    # Shrink the PNG: it's drawn about 30 calendar units wide at 4 px each.
    scale = min(1.0, 140 / size[0])
    from PIL import Image
    im = Image.open(iso)
    im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    im.save(iso, optimize=True)
    meta = {"iso": {"x": (box[0] - nose[0]) * upp, "y": (box[1] - nose[1]) * upp,
                    "w": size[0] * upp, "h": size[1] * upp}}
    (ASSETS / "roadster.json").write_text(json.dumps(meta, indent=1))
    print("rear", Image.open(rear).size, "iso", im.size, meta)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(Path(sys.argv[1]).resolve())
