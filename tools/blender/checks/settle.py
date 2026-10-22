"""
Pipeline check: rigid body placement (opus_model.settle).

40 irregular stones are dropped into a shallow open-top crate (they do not fit on the floor, they pile up). Checks:
- all stopped (movement < 0.5 mm over the last 10 frames);
- all inside the crate (nothing spills over the walls or the floor);
- the stones do not sink into each other or the crate (deepest interpenetration under 2 mm; the gauge is tested with a deliberate sink);
- no rotation or scale on the objects, the shells are closed (Model.validate);
- the same input gives the same result (two runs exactly the same).
Images: Builds/Models/settle_check/. The model is not exported.
Run: powershell -ExecutionPolicy Bypass -File tools/Models.ps1 -Checks
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import bmesh  # noqa: E402
from mathutils import Vector, noise  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import opus_model as om  # noqa: E402

INNER = Vector((0.40, 0.28, 0.12))   # inner size of the crate (m): shallow, so the stones pile two high
WALL = 0.02
COUNT = 40


def stone_mesh(rng):
    """Irregular stone: an icosphere, its radius distorted by noise, squashed on one axis."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
    radius = rng.uniform(0.032, 0.05)
    squash = Vector((rng.uniform(0.8, 1.15), rng.uniform(0.75, 1.0), rng.uniform(0.55, 0.8)))
    offset = Vector((rng.uniform(-50, 50), rng.uniform(-50, 50), rng.uniform(-50, 50)))
    for v in bm.verts:
        d = v.co.normalized()
        bump = 1.0 + 0.18 * noise.noise(d * 1.6 + offset)
        v.co = Vector((d.x * squash.x, d.y * squash.y, d.z * squash.z)) * radius * bump
    return bm


def crate_mesh():
    """Open-top crate: the inner cavity is carved out of the outer box (a single closed shell)."""
    outer = bmesh.new()
    om.box(outer, (-INNER.x / 2 - WALL, -INNER.y / 2 - WALL, -WALL), (INNER.x / 2 + WALL, INNER.y / 2 + WALL, INNER.z))
    hole = bmesh.new()
    om.box(hole, (-INNER.x / 2, -INNER.y / 2, 0.0), (INNER.x / 2, INNER.y / 2, INNER.z + 0.1))
    return om.carve(outer, [hole])


def build():
    model = om.Model("settle_check", __file__)
    wood = model.surface("Planks", "#9C7B55", "matte", "Check crate")
    stone = model.surface("Stone", "#8E8A82", "matte", "Check stones")
    crate = model.part("Crate", crate_mesh(), [wood], smooth=False)
    floor = bmesh.new()
    om.box(floor, (-1.0, -1.0, -WALL - 0.05), (1.0, 1.0, -WALL))
    ground = model.part("Ground", floor, [wood], smooth=False)   # so anything spilling out of the crate does not fall forever
    rng = random.Random(7)
    meshes = [stone_mesh(rng) for _ in range(COUNT)]
    # Dropped in waves: every wave, on a grid fitting the crate floor (spacing by the largest stone) two layers high,
    # falls just above the pile so far; the settled stones become colliders for the next wave.
    # Dropping all of them at once from 7 layers up toppled the pile and a stone bounced out of the crate.
    step = max(max(v.co.length for v in bm.verts) for bm in meshes) * 2.0 + 0.004
    columns, rows = max(int(INNER.x // step), 1), max(int(INNER.y // step), 1)
    wave = columns * rows * 2
    stones, motion = [], []
    for first in range(0, COUNT, wave):
        top = max([INNER.z] + [max(o.location.z + v.co.z for v in o.data.vertices) for o in stones])
        batch = []
        for index in range(first, min(first + wave, COUNT)):
            layer, cell = divmod(index - first, columns * rows)
            ix, iy = divmod(cell, rows)
            location = ((ix - (columns - 1) / 2) * step + rng.uniform(-0.005, 0.005),
                        (iy - (rows - 1) / 2) * step + rng.uniform(-0.005, 0.005), top + step * (0.5 + layer))
            batch.append(model.part(f"Stone{index:02d}", meshes[index], [stone], location=location, sharp=180.0))
        motion += om.settle(batch, [crate, ground] + stones)
        stones += batch
    return model, crate, stones, motion


def deepest_overlap(objects):
    """Deepest interpenetration between pairs of objects (m): how deep a vertex of one object lies inside the other."""
    trees = []
    for obj in objects:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.translate(bm, vec=Vector(obj.location), verts=bm.verts)
        trees.append((obj, BVHTree.FromBMesh(bm), [v.co.copy() for v in bm.verts]))
        bm.free()
    worst, where = 0.0, None
    for i, (a, tree_a, verts_a) in enumerate(trees):
        for j, (b, tree_b, verts_b) in enumerate(trees):
            if i == j or not tree_a.overlap(tree_b):
                continue
            for co in verts_a:
                hit, normal, _, distance = tree_b.find_nearest(co)
                if hit is not None and (co - hit).dot(normal) < 0.0 and distance > worst:
                    worst, where = distance, f"{a.name} -> {b.name}"
    return worst, where


def check():
    model, crate, stones, motion = build()
    errors = []
    if max(motion) > 5e-4:
        errors.append(f"a stone did not settle: at most {max(motion) * 1000:.2f} mm")
    tolerance = 0.002
    for obj in stones:
        co = [Vector(obj.location) + v.co for v in obj.data.vertices]
        lo = Vector([min(c[i] for c in co) for i in range(3)])
        hi = Vector([max(c[i] for c in co) for i in range(3)])
        if lo.x < -INNER.x / 2 - tolerance or hi.x > INNER.x / 2 + tolerance or \
                lo.y < -INNER.y / 2 - tolerance or hi.y > INNER.y / 2 + tolerance or lo.z < -tolerance:
            errors.append(f"{obj.name} is outside the crate: {tuple(round(c, 3) for c in lo)} .. "
                          f"{tuple(round(c, 3) for c in hi)}")
    depth, where = deepest_overlap(stones + [crate])
    if depth > 0.002:
        errors.append(f"sinking {depth * 1000:.1f} mm ({where})")
    # The gauge itself: sinking the lowest stone on the crate floor 1 cm into it must be caught
    lowest = min(stones, key=lambda o: min(v.co.z for v in o.data.vertices) + o.location.z)
    lowest.location.z -= 0.01
    probe, _ = deepest_overlap([lowest, crate])
    lowest.location.z += 0.01
    if probe < 0.005:
        errors.append(f"the sink gauge does not work: found {probe * 1000:.1f} mm on a stone sunk 1 cm")
    model.validate(None)
    first = [tuple(round(c, 6) for c in obj.location) for obj in stones]
    heights = sorted(round(obj.location.z, 3) for obj in stones)
    om.log(f"Settle: stone centre heights {heights[0]}..{heights[-1]} m; deepest sinking "
           f"{depth * 1000:.2f} mm ({where})")

    model_again, _, stones_again, _ = build()
    second = [tuple(round(c, 6) for c in obj.location) for obj in stones_again]
    if first != second:
        moved = sum(1 for a, b in zip(first, second) if a != b)
        errors.append(f"not reproducible: {moved} stones elsewhere on the second run")

    if errors:
        raise RuntimeError("Settle check failed:\n  " + "\n  ".join(errors))
    om.log("Settle check passed")
    return model_again


def render(model):
    names = [obj.name for obj, _ in model.parts if obj.name != "Ground"]
    model.render([
        {"file": "overview", "label": f"{COUNT} stones dropped into a crate (rigid body)", "objects": names,
         "direction": (0.55, -1.0, 0.85)},
        {"file": "top", "label": "From above", "objects": names, "direction": (0.0, -0.05, 1.0)},
        {"file": "close", "label": "Close: the stones lean on each other", "objects": names,
         "direction": (-0.4, -1.0, 0.5), "zoom": 1.8},
    ], [])


render(check())
