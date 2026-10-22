"""
The garden tree with the swing: Body (trunk, roots, branches; textured pipeline, one atlas), Leaves (leaf clusters; left out of the
atlas so they keep the soft foliage lighting in Unity, with vertex AO). The rope and tire are a separate textured model:
tire_swing.py (the branch and hook sizes are the same).

Reference: Builds/Models/tools_tree_reference.png (video 1:04-1:08; docs/reference/27). In the video the camera is low:
a thick brown trunk spreading wide at the base with 4-5 roots; a thick rope hanging from a branch, a knot at the top, a black
tire swing. The crown is not visible in the video: made with the garden's sizes and colours using the leaf cluster technique
of stylised trees found online (no downloads): double-sided leaves with real leaf shapes in clusters at the branch tips,
normals pointing out from the cluster centre (the crown takes light like a single volume), the inner leaves darkened by baked
AO, three tones of green (light on top).

Trunk (21 October 2026, after "the trunk is thin, it has no roots"): one lofted surface. The roots are buttress fins of its
cross-section: at the ground each fin reaches about 1 m from the centre and narrows towards its rounded tip, its top edge
slopes down into the soil, and above the ground it fades into a shallow fold running up the trunk (the vertical ridges at
1:06). Bark: ambientCG Bark003 (CC0, fetched with tools/Assets.ps1) gives the fine vertical grain (bump from its height map,
box-projected so the fins need no unwrap) and a little tone; the colour is the video's flat warm brown (sRGB about 90/57/38
on the lit side at 1:06). The dark patches on the trunk in the video are leaf shadows, so they are not painted.

Mechanical logic: the component plan (model.plan below).

Unity axes: the origin is the middle of the base of the trunk (ground). The sizes match the earlier garden tree (the colliding
trunk is in YardProps: r 0.35 m, 3.6 m; swing hook (2.1, 3.95, 0.9), tire centre y 0.78, r 0.36).
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import bmesh  # noqa: E402
import bpy  # noqa: E402

import opus_model as om  # noqa: E402
from opus_model import V  # noqa: E402

rng = random.Random(5)
model = om.Model("tree", __file__)
model.plan(
    "garden tree with a side branch that carries the tire swing",
    [("video", "1:04-1:08 (ref 27); the crown is never seen")],
    [   # name, role, job, attached to, moves, seen/guess/real
        ("Roots", "structural", "buttress fins going into the soil", ["ground"], "fixed", "seen"),
        ("Trunk", "structural", "carries the crown and the swing branch", ["Roots"], "fixed", "seen"),
        ("SwingBranch", "structural", "side branch the swing's rope wraps round", ["Trunk"], "fixed", "seen"),
        ("Branches", "structural", "fork from the trunk, thin ones out of thick ones", ["Trunk"], "fixed", "guess"),
        ("Leaves", "functional", "leaf clusters at the tips of the thin branches", ["Branches"], "fixed", "guess"),
    ],
    supports=("ground",), tier="simple", category="organic")
BARK_HEIGHT = model.external_texture("ambientcg:Bark003", "Bark003_1K-JPG_Displacement.jpg")
BARK_PHOTO = model.external_texture("ambientcg:Bark003", "Bark003_1K-JPG_Color.jpg")
BARK_BROWN = (78, 53, 33)        # sRGB; tuned against the 1:06 frame in game (the lavender sky light lifts and cools it)


def bark_nodes(nodes, links, bsdf, uv):
    """Flat warm brown from the video, a little tone from the bark photo, fine vertical grain as bump (box projection)."""
    coords = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (1.4, 1.4, 0.9)     # the grain runs up the trunk (texture repeats ~0.7 x 1.1 m)
    links.new(coords.outputs["Object"], mapping.inputs["Vector"])

    def image(path, data):
        node = nodes.new("ShaderNodeTexImage")
        node.image = bpy.data.images.load(path, check_existing=True)
        if data:
            node.image.colorspace_settings.name = "Non-Color"
        node.projection = "BOX"
        node.projection_blend = 0.3
        links.new(mapping.outputs["Vector"], node.inputs["Vector"])
        return node.outputs["Color"]

    photo = nodes.new("ShaderNodeRGBToBW")
    links.new(image(BARK_PHOTO, False), photo.inputs["Color"])
    tone = nodes.new("ShaderNodeMapRange")
    tone.inputs["From Min"].default_value = 0.15
    tone.inputs["From Max"].default_value = 0.6
    tone.inputs["To Min"].default_value = 0.82
    tone.inputs["To Max"].default_value = 1.12
    links.new(photo.outputs["Val"], tone.inputs["Value"])
    # Large soft patches of lighter and darker brown (paint variation, not shadow)
    patches = nodes.new("ShaderNodeTexNoise")
    patches.inputs["Scale"].default_value = 1.6
    patches.inputs["Detail"].default_value = 2.0
    links.new(coords.outputs["Object"], patches.inputs["Vector"])
    patch_tone = nodes.new("ShaderNodeMapRange")
    patch_tone.inputs["To Min"].default_value = 0.92
    patch_tone.inputs["To Max"].default_value = 1.08
    links.new(patches.outputs["Fac"], patch_tone.inputs["Value"])
    shade = nodes.new("ShaderNodeMath")
    shade.operation = "MULTIPLY"
    links.new(tone.outputs["Result"], shade.inputs[0])
    links.new(patch_tone.outputs["Result"], shade.inputs[1])
    color = nodes.new("ShaderNodeMix")
    color.data_type = "RGBA"
    color.blend_type = "MULTIPLY"
    color.inputs["Factor"].default_value = 1.0
    color.inputs["A"].default_value = (*[om.srgb_to_linear(c / 255.0) for c in BARK_BROWN], 1.0)
    links.new(shade.outputs["Value"], color.inputs["B"])
    links.new(color.outputs["Result"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.88
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.55
    bump.inputs["Distance"].default_value = 0.012
    links.new(image(BARK_HEIGHT, True), bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


BARK = model.textured_surface("bark", "matte", "Trunk, roots, branches: bark; flat warm brown in the video with a fine vertical "
                              "grain, no shine (the dark patches at 1:06 are leaf shadows, not paint)", bark_nodes)
LEAF_DARK = model.surface("Foliage", "#5E8A3A", "matte", "Crown underside and inner leaves: dark green (garden palette; the crown is not visible in the video)")
LEAF = model.surface("Foliage", "#7FA34A", "matte", "Crown middle leaves: green (garden palette)")
LEAF_LIGHT = model.surface("Foliage", "#9DBB55", "matte", "Crown top leaves: light green (garden palette; facing the sun)")

TRUNK_TOP = 3.6
HOOK_START, HOOK_END = V(0.15, 3.45, 0.1), V(2.5, 4.1, 1.05)


def spine(t):
    """The trunk's slightly curved axis (same as the old tree)."""
    return V(math.sin(t * 2.1) * 0.1, TRUNK_TOP * t, math.sin(t * 1.4 + 1.0) * 0.06)


ROOT_ANGLES = [k * 2 * math.pi / 5 + rng.uniform(-0.3, 0.3) for k in range(5)]
for _ in ROOT_ANGLES:            # the old swept roots drew two numbers each: kept, so the branches and the crown stay the same
    rng.uniform(-0.15, 0.15)
    rng.uniform(0.95, 1.2)
_roots = random.Random(11)
# (angle, how far the fin reaches in trunk radii, sideways bend towards its tip)
ROOTS = [(a, _roots.uniform(1.2, 1.55), _roots.uniform(-0.18, 0.18)) for a in ROOT_ANGLES]
FIN_FALL = 0.42                  # m: how fast the fins sink into the trunk going up (their top edge slopes down to the tip)


def trunk_radius(theta, y):
    """Trunk cross-section radius at angle theta and height y: a round trunk with five buttress fins at the ground."""
    yc = max(y, 0.0)
    base = 0.36 - 0.1 * min(1.0, yc / TRUNK_TOP) + 0.015 * math.sin(y * 3.1)
    base *= 1.0 + 0.22 * math.exp(-yc / 0.5)              # the whole base widens a little
    fin_amount = math.exp(-yc / FIN_FALL)
    lobes = 0.0
    for angle, amplitude, bend in ROOTS:
        offset = theta - angle - bend * fin_amount
        c = max(0.0, math.cos(math.atan2(math.sin(offset), math.cos(offset))))
        sharp = 4.0 + 10.0 * fin_amount                    # the further out, the narrower; still thick and round (video 1:06)
        fin = amplitude * fin_amount * c ** sharp
        fold = 0.07 * math.exp(-yc / 1.4) * c ** 3          # the shallow fold continuing up the trunk
        lobes = max(lobes, fin + fold)
    return base * (1.0 + lobes)


def build_trunk():
    bm = bmesh.new()
    sides, rows = 112, 46
    rings = []
    for i in range(rows + 1):
        t = i / rows
        y = -0.15 + (TRUNK_TOP + 0.5) * t ** 1.8               # rows bunched at the ground where the fins change fast
        c = spine(max(0.0, y) / TRUNK_TOP)
        ring = []
        for s in range(sides):
            a = 2 * math.pi * s / sides
            r = trunk_radius(a, y)
            ring.append(V(c.x + math.cos(a) * r, y, c.z + math.sin(a) * r))
        rings.append(ring)
    om.loft(bm, rings, material=0)

    # Branches: thick branches forking from the top of the trunk, thin ones from those; the tips are the centres of the leaf clusters
    tips = []
    top = spine(1.0)
    leader = om.spline([top + V(0, -0.4, 0), top + V(0.05, 0.6, 0.02), top + V(0.12, 1.5, 0.08)], 6)
    om.sweep(bm, leader, 1.0, 14, material=0, radii=[0.24 - 0.17 * k / (len(leader) - 1) for k in range(len(leader))])
    tips.append((leader[-1], 0.95))
    for k in range(5):
        a = k * 2 * math.pi / 5 + rng.uniform(-0.35, 0.35) + 0.4
        out = V(math.cos(a), 0, math.sin(a))
        start = spine(rng.uniform(0.8, 0.95))
        end = start + out * rng.uniform(1.6, 2.1) + V(0, rng.uniform(1.2, 1.8), 0)
        mid = start + (end - start) * 0.45 + V(0, 0.25, 0)
        limb = om.spline([start, mid, end], 6)
        om.sweep(bm, limb, 1.0, 14, material=0, radii=[0.16 - 0.11 * j / (len(limb) - 1) for j in range(len(limb))])
        tips.append((end, rng.uniform(0.8, 0.95)))
        for j in range(2):
            fork = limb[len(limb) * (j + 2) // 5]
            side = out.cross(V(0, 1, 0)) * (1 if j == 0 else -1)
            twig_end = fork + side * rng.uniform(0.7, 1.0) + out * rng.uniform(0.3, 0.6) + V(0, rng.uniform(0.6, 1.0), 0)
            twig = om.spline([fork, fork + (twig_end - fork) * 0.5 + V(0, 0.1, 0), twig_end], 5)
            om.sweep(bm, twig, 1.0, 10, material=0, radii=[0.075 - 0.05 * q / (len(twig) - 1) for q in range(len(twig))])
            tips.append((twig_end, rng.uniform(0.62, 0.8)))

    # Swing branch: sideways from the trunk, passes over the hook; a small cluster at its tip
    swing = [HOOK_START + (HOOK_END - HOOK_START) * f for f in (0.0, 0.35, 0.7, 1.0)]
    swing = om.spline(swing, 6)
    om.sweep(bm, swing, 1.0, 14, material=0, radii=[0.13 - 0.07 * k / (len(swing) - 1) for k in range(len(swing))])
    tips.append((HOOK_END + V(0.25, 0.25, 0.1), 0.6))
    return bm, tips


def leaf_shape(length, width):
    half = [(0.0, 0.5), (0.42, 0.24), (0.5, -0.04), (0.33, -0.3), (0.0, -0.5)]
    pts = [(u * width, v * length) for u, v in half]
    pts += [(-u * width, v * length) for u, v in reversed(half[1:-1])]
    return pts


def build_leaves(tips):
    """
    Leaf clusters: real-shaped leaves (double-sided) spread over a sphere shell at every branch tip. The vertex normals point
    out from the cluster centre and the crown centre (the spherical normal method used on stylised trees).
    """
    bm = bmesh.new()
    directions = om.foliage_normals(bm)
    crown = V(0.2, 5.0, 0.3)
    clusters = list(tips)
    # Filler clusters inside the crown (the gaps between the branches)
    for _ in range(6):
        a = rng.uniform(0, 2 * math.pi)
        clusters.append((crown + V(math.cos(a) * rng.uniform(0.6, 1.3), rng.uniform(-0.5, 0.6), math.sin(a) * rng.uniform(0.6, 1.3)),
                         rng.uniform(0.75, 0.95)))
    count = 0
    for center, radius in clusters:
        n = int(radius * radius * 300)
        for _ in range(n):
            d = V(rng.gauss(0, 1), rng.gauss(0, 1) * 0.85 + 0.1, rng.gauss(0, 1)).normalized()
            p = center + d * radius * rng.uniform(0.55, 1.0)
            outward = (p - center).normalized()
            out_crown = (p - crown).normalized()
            facing = (outward + V(rng.uniform(-0.6, 0.6), rng.uniform(-0.2, 0.7), rng.uniform(-0.6, 0.6))).normalized()
            u_axis = facing.cross(V(0, 1, 0))
            if u_axis.length < 0.2:
                u_axis = facing.cross(V(1, 0, 0))
            u_axis = u_axis.normalized()
            v_axis = facing.cross(u_axis).normalized()
            spin = rng.uniform(0, 2 * math.pi)
            u_rot = u_axis * math.cos(spin) + v_axis * math.sin(spin)
            v_rot = facing.cross(u_rot).normalized()
            shape = leaf_shape(rng.uniform(0.26, 0.34), rng.uniform(0.15, 0.19))
            bend = rng.uniform(0.01, 0.03)
            points = [p + u_rot * su + v_rot * sv + facing * (bend * (1 - (2 * su / 0.19) ** 2)) for su, sv in shape]
            normal = (outward * 0.6 + out_crown * 0.4).normalized()
            height = (p.y - 3.8) / 2.6 + rng.uniform(-0.25, 0.25)
            inner = (p - center).length / radius < 0.75
            material = 0 if inner or height < 0.3 else (2 if height > 0.75 else 1)
            for order in (points, list(reversed(points))):
                verts = [bm.verts.new(q) for q in order]
                for v in verts:
                    v[directions] = normal
                face = bm.faces.new(verts)
                face.material_index = material
            count += 1
    om.log(f"leaves: {count} leaves, {len(clusters)} clusters")
    return bm


trunk, tips = build_trunk()
model.part("Body", trunk, [BARK], unity=True, weighted=False, sharp=85.0)
model.part("Leaves", build_leaves(tips), [LEAF_DARK, LEAF, LEAF_LIGHT], unity=True, foliage=True)


def unity_dir(x, y, z):
    return (-x, -z, y)


everything = ["Body", "Leaves"]
model.finish_textured(
    size=2048,
    budget=60000,
    total_budget=80000,   # body + leaves
    ao_distance=0.6,
    islands="smart",
    ground=0.0,
    untextured=("Leaves",),
    views=[
        {"file": "overview", "label": "Overview (from the garden)", "objects": everything, "direction": unity_dir(0.8, 0.35, -0.9), "ground": 0.0},
        {"file": "close_crown", "label": "Crown up close: leaf clusters", "objects": everything, "direction": unity_dir(0.7, 0.2, -0.75),
         "target": unity_dir(1.3, 5.2, 0.8), "radius": 1.6, "ground": 0.0},
        {"file": "trunk", "label": "Trunk and roots (the angle in the video)", "objects": everything, "direction": unity_dir(-0.2, 0.25, -1.0),
         "target": unity_dir(0.0, 0.9, 0.0), "radius": 1.6, "ground": 0.0},
        {"file": "roots", "label": "Root fins from above", "objects": everything, "direction": unity_dir(0.35, 1.0, -0.55),
         "target": unity_dir(0.0, 0.2, 0.0), "radius": 1.3, "ground": 0.0},
        {"file": "from_above", "label": "Crown from above and the side", "objects": everything, "direction": unity_dir(0.5, 1.0, -0.6), "ground": 0.0},
    ],
    references=[
        {"label": "Reference: trunk and roots, video 1:06", "path": "docs/reference/27_tree_swing.png", "crop": [0, 0, 300, 478]},
    ],
)
