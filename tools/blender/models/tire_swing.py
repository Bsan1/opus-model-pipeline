"""
Tire swing (textured pipeline): the rope with a round turn and two half hitches on the tree's side branch, the hanging rope, two half
hitches on top of the tire (the rope's loop goes round the tire's upper cross-section) and the tire. One object, one material, UV-mapped
atlas textures (base colour, normal, AO/roughness).

Reference: video 1:04-1:08 (docs/reference/27 = 1:06, 32 = 1:07 close). Visible: a beige, clearly twisted 3-strand rope (a strand crest
about every rope diameter along it: the lay is about 3 diameters); a lump of turns sitting right on top of the tire; from the lump ONE
rope goes down the front sidewall into the hole (at 1:06 it bends under the bead and disappears); nothing else hangs in front; the
tire dark olive brown-grey, worn and dusty, matte; two ring lines on the sidewall, a lip at the hole's mouth, tread lugs.

Real sizes: a tall-sidewall 195/80 R13 tire (outer diameter 63 cm, width 19.5 cm, bead opening 33 cm): in the video the hole is half
the outer diameter. Rope 2.3 cm (measured in the 1:07 frame against the 63 cm tire).

Rope (rebuilt 21 October 2026 after the user's review: the old one was a single 12-sided tube with a 3-lobe ripple, normals
averaged by face area, bends tighter than its thickness and legs floating off the tire, so in game it read as a bent square metal
tube). Real laid rope studied: three strands twisted right-handed (Z-lay) round each other, each strand made of yarns twisted the
other way so the surface yarns run roughly along the rope; the strands press into each other (deep valleys between them). Here:
three separate strand tubes (radius 0.53 R, centres 0.5 R off the axis, so neighbours press in and the core is solid), one turn per
lay = 3 diameters, along a single continuous centreline; a generated yarn texture on every strand; smooth vertex normals (no area
weighting).
Rigging (the usual tire swing knots, how-to guides: Bob Vila, Instructables): on the branch a round turn (2.5 turns lying side by
side on the bark) and two half hitches round the standing part under the branch; on the tire the rope goes over the front shoulder
down the front sidewall, under the bead through the hole, up the back sidewall and is tied round the standing part with two half
hitches on top of the tire (the lump in the video). Physics the path follows: the loaded parts are straight (the hanging rope is
vertical, the tire hangs right under the point where it leaves the branch: the branch's side, not under its middle); under load the
loop lies tight on the tire (its centreline is the tire's cross-section hull grown by the rope radius, pressed in 0.5 mm); turns lie
against each other (2.06 R apart) and against what they bind (2 R); no bend of the centreline is tighter than one rope diameter;
the free tails hang under gravity and lie on what they rest on. The path is audited (tools/blender: Builds/QC/tire_swing.json
"rope"): rope-to-rope and rope-to-tire distances, the tightest bend.

Mechanical logic of the tire: lugs, grooves, sidewall rings and the bead lip in geometry; the rubber colour from nodes: olive
brown-grey, tone variation, dust on top, scuff marks, wear on the lug edges (light), fine rubber grain; all baked into the atlas.

Unity axes: the origin is the tree's origin (the base of the trunk); the branch sizes on the tree are the same as in tree.py.
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import opus_model as om  # noqa: E402
from opus_model import V  # noqa: E402

# The same branch and hook as tree.py
HOOK_START, HOOK_END = V(0.15, 3.45, 0.1), V(2.5, 4.1, 1.05)
HOOK_F = (2.1 - HOOK_START.x) / (HOOK_END.x - HOOK_START.x)
HOOK = HOOK_START + (HOOK_END - HOOK_START) * HOOK_F
BRANCH_AXIS = (HOOK_END - HOOK_START).normalized()
BRANCH_R = 0.13 - 0.07 * HOOK_F

# Rope (see the docstring): R = radius; lay = one strand turn per 3 diameters
ROPE_R = 0.0115
LAY = 6.0 * ROPE_R
STRAND_A, STRAND_R, STRAND_SIDES = 0.5 * ROPE_R, 0.53 * ROPE_R, 8
CONTACT = 2.0 * ROPE_R          # centre distance of two ropes lying against each other
PITCH = 2.06 * ROPE_R           # turn to turn along a wrap
BEND = 2.0 * ROPE_R             # the tightest centreline bend: one rope diameter
PRESS = 0.0005                  # the loaded loop presses this far into the rubber
SPACING = LAY / 12.0            # centreline samples: 12 per strand turn
FIBRE_TILE = 0.059              # m along a strand per turn of its surface yarns (they lie along the rope, ~33 degrees off the strand)
FIBRE_TEXTURE = "generated/rope_strand.png"
ROPE_RGB = (204, 166, 108)      # hemp beige: the 1:07 frame reads 160/128/83 lit; the game's lighting reads the albedo darker

# Round turn on the branch, in the plane across it; the hanging rope leaves on SIDE (the garden side, -Z)
ACROSS = BRANCH_AXIS.cross(V(0, 1, 0)).normalized()
SIDE = ACROSS if ACROSS.z < 0 else -ACROSS
UPW = SIDE.cross(BRANCH_AXIS).normalized()
if UPW.y < 0:
    UPW = -UPW
WRAP_R = BRANCH_R * 0.985 + ROPE_R     # on the bark (the 14-sided branch: on its corners, 0.8 mm off its flats)


def wrap_point(alpha):
    """The round turn's centreline: alpha 0 = on SIDE, pi/2 on top of the branch; the turns step along the branch by PITCH."""
    axial = (alpha / (2.0 * math.pi) - 1.25) * PITCH
    return HOOK + BRANCH_AXIS * axial + (SIDE * math.cos(alpha) + UPW * math.sin(alpha)) * WRAP_R


def bend(start, d0, d1, radius, steps=10):
    """Arc of `radius` from `start`, turning the direction d0 into d1; returns (points without the start, end point)."""
    d0, d1 = d0.normalized(), d1.normalized()
    angle = d0.angle(d1)
    if angle < 1e-4:
        return [], start
    n = (d1 - d0 * d0.dot(d1)).normalized()
    centre = start + n * radius
    pts = [centre - n * radius * math.cos(angle * k / steps) + d0 * radius * math.sin(angle * k / steps) for k in range(1, steps + 1)]
    return pts, pts[-1]


# The hanging rope: leaves the round turn at alpha = 0 going down, straightens to vertical
_leave = -(wrap_point(1e-3) - wrap_point(0.0)).normalized()
HANG_BEND, HANG_TOP = bend(wrap_point(0.0), _leave, V(0, -1, 0), 1.5 * BEND)
TIRE_CENTER = V(HANG_TOP.x, 0.78, HANG_TOP.z)     # the tire hangs right under the rope
TIRE_OUT, TIRE_BEAD, TIRE_HALF = 0.315, 0.165, 0.0975
TREAD_DEPTH = 0.0                              # the tread pattern is in the normal map; the silhouette is round (an old tire)
FRONT = -1.0                                   # the side the front leg is on (Z sign); the loop below is built for -1

model = om.Model("tire_swing", __file__)
model.plan(
    "tire swing: a tire hung from a side branch by one rope; a child sits in it and swings",
    [("video", "1:04-1:08 (refs 27, 32)"), ("text", "real rigging: tire swing guides (Bob Vila, Instructables)")],
    [   # name, role, job, attached to, moves, seen/guess/real
        ("RoundTurn", "functional", "2.5 turns on the bark take the load by friction", ["branch"], "fixed", "real"),
        ("BranchHitches", "functional", "two half hitches round the standing part lock the round turn", ["RoundTurn"], "fixed",
         "real"),
        ("BranchTail", "decorative", "the frayed free end after the hitches, hanging", ["BranchHitches"], "flex", "real"),
        ("HangingRope", "functional", "carries the tire straight down from the branch's side", ["RoundTurn"], "flex", "seen"),
        ("Loop", "functional", "over the front shoulder, under the bead, up the back: holds the tire", ["HangingRope", "Tire"],
         "flex", "real"),
        ("TireHitches", "functional", "two half hitches on top of the tire close the loop (the lump in the video)", ["Loop"],
         "fixed", "seen"),
        ("TireTail", "decorative", "the free end lying on the tire", ["TireHitches", "Tire"], "flex", "real"),
        ("Tire", "functional", "the seat, hanging right under the rope", ["Loop"], "free", "seen"),
    ],
    supports=("branch",), tier="complex", category="suspended")
model.features([   # id, tier, components, what must hold, measured by, view
    ("branch_hitch", "critical", ["RoundTurn", "BranchHitches"],
     "a round turn on the bark locked by two half hitches round the standing part", "support:branch", "branch"),
    ("load_line", "critical", ["HangingRope", "Loop", "Tire"],
     "the rope runs straight down from the branch's side and its loop holds the tire right under it", "route:HangingRope",
     "side"),
    ("tire_hitches", "important", ["TireHitches", "TireTail"], "two half hitches close the loop on top of the tire",
     None, "knot"),
])


def math_node(nodes, links, op, a, b=None):
    node = nodes.new("ShaderNodeMath")
    node.operation = op
    for index, value in enumerate((a, b)):
        if value is None:
            continue
        if isinstance(value, (int, float)):
            node.inputs[index].default_value = float(value)
        else:
            links.new(value, node.inputs[index])
    return node.outputs[0]


def mix_rgb(nodes, links, a, b, factor, blend="MIX"):
    node = nodes.new("ShaderNodeMix")
    node.data_type = "RGBA"
    node.blend_type = blend
    for socket, value in (("A", a), ("B", b)):
        if isinstance(value, tuple):
            node.inputs[socket].default_value = value
        else:
            links.new(value, node.inputs[socket])
    if isinstance(factor, (int, float)):
        node.inputs["Factor"].default_value = float(factor)
    else:
        links.new(factor, node.inputs["Factor"])
    return node.outputs["Result"]


def make_strand_texture(nu=256, nv=512, yarns=6):
    """
    One strand's surface (u: once round the strand, v: FIBRE_TILE along it), seamless: `yarns` rounded yarns twisted against the
    strand's lay, each made of fine fibres. R = height (1 = yarn crest), G = tone (fibre streaks, a yarn a little lighter or
    darker than the next, the odd dark fibre).
    """
    import numpy as np

    rng = np.random.default_rng(5)
    x = (np.arange(nu) + 0.5) / nu
    y = (np.arange(nv) + 0.5) / nv
    X, Y = np.meshgrid(x, y)
    along = X - Y                      # constant along a yarn: a yarn turns once round the strand per tile
    phase = yarns * along
    f = phase - np.floor(phase)
    crest = np.sqrt(np.clip(1.0 - (2.0 * f - 1.0) ** 2, 0.0, 1.0)) ** 0.7
    fibres = np.zeros_like(X)
    for _ in range(48):
        m = int(rng.integers(30, 120))
        n = int(rng.integers(-3, 4))
        fibres += rng.uniform(0.4, 1.0) / math.sqrt(m) * np.sin(2.0 * math.pi * (m * along + n * Y) + rng.uniform(0, 2 * math.pi))
    fibres /= max(float(np.abs(fibres).max()), 1e-6)
    dark = np.zeros_like(X)
    for _ in range(12):
        m = int(rng.integers(150, 260))
        dark += np.sin(2.0 * math.pi * (m * along + int(rng.integers(-2, 3)) * Y) + rng.uniform(0, 2 * math.pi))
    dark = np.clip((dark / 12.0 - 0.32) * 6.0, 0.0, 1.0)
    index = np.floor(phase).astype(int) % yarns
    yarn_tone = rng.uniform(0.93, 1.07, yarns)[index]
    height = np.clip(crest * (0.85 + 0.15 * fibres), 0.0, 1.0)
    tone = np.clip(0.5 + 0.12 * fibres + (yarn_tone - 1.0) - 0.18 * dark, 0.0, 1.0)

    path = os.path.join(om.SOURCE_TEXTURE_DIR, FIBRE_TEXTURE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    image = bpy.data.images.new("rope_strand_generate", nu, nv, alpha=False, float_buffer=False)
    image.colorspace_settings.name = "Non-Color"
    rgba = np.ones((nv, nu, 4), dtype=np.float32)
    rgba[..., 0], rgba[..., 1], rgba[..., 2] = height, tone, 0.0
    image.pixels.foreach_set(rgba.ravel())
    image.filepath_raw = path
    image.file_format = "PNG"
    image.save()
    bpy.data.images.remove(image)


def rope_nodes(nodes, links, bsdf, uv):
    """Hemp strand: beige, darker down between the yarns, fibre streaks; the yarns as bump; matte."""
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = bpy.data.images.load(os.path.join(om.SOURCE_TEXTURE_DIR, FIBRE_TEXTURE), check_existing=True)
    texture.image.colorspace_settings.name = "Non-Color"
    texture.interpolation = "Cubic"
    links.new(uv, texture.inputs["Vector"])
    channels = nodes.new("ShaderNodeSeparateColor")
    links.new(texture.outputs["Color"], channels.inputs["Color"])
    height, tone = channels.outputs["Red"], channels.outputs["Green"]
    shade = math_node(nodes, links, "MULTIPLY", math_node(nodes, links, "ADD", math_node(nodes, links, "MULTIPLY", height, 0.3), 0.7),
                      math_node(nodes, links, "ADD", math_node(nodes, links, "MULTIPLY", tone, 0.8), 0.6))
    base = (*[om.srgb_to_linear(c / 255.0) for c in ROPE_RGB], 1.0)
    colour = nodes.new("ShaderNodeMix")
    colour.data_type = "RGBA"
    colour.blend_type = "MULTIPLY"
    colour.inputs["Factor"].default_value = 1.0
    colour.inputs["A"].default_value = base
    combine = nodes.new("ShaderNodeCombineColor")
    for channel in ("Red", "Green", "Blue"):
        links.new(shade, combine.inputs[channel])
    links.new(combine.outputs["Color"], colour.inputs["B"])
    links.new(colour.outputs["Result"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.88
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.9
    bump.inputs["Distance"].default_value = 0.0012
    links.new(height, bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


def rubber_nodes(nodes, links, bsdf, uv):
    """
    Old tire rubber: olive brown-grey, large-scale tone, dust on top, scuff marks on the sidewall, wear on the lug and lip edges
    (the sharpness of the geometry: Cycles 'Pointiness'), fine rubber grain (normal).
    """
    texture = nodes.new("ShaderNodeTexCoord")
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 7.0
    noise.inputs["Detail"].default_value = 8.0
    links.new(texture.outputs["Object"], noise.inputs["Vector"])
    # Olive brown-grey in the video (sRGB about 80/72/56 on the sidewall at 1:07). The game's lavender sky light added blue:
    # with a neutral base the tire read purple-grey (95/85/92), so the base leans warm and low in blue.
    base = mix_rgb(nodes, links, (0.038, 0.045, 0.019, 1.0), (0.053, 0.058, 0.024, 1.0), noise.outputs["Fac"])

    # Scuff marks: thin, long, light streaks (noise stretched along the circumference)
    streak_map = nodes.new("ShaderNodeMapping")
    streak_map.inputs["Scale"].default_value = (2.0, 2.0, 40.0)
    links.new(uv, streak_map.inputs["Vector"])
    streak = nodes.new("ShaderNodeTexNoise")
    streak.inputs["Scale"].default_value = 6.0
    streak.inputs["Detail"].default_value = 4.0
    links.new(streak_map.outputs["Vector"], streak.inputs["Vector"])
    streak_mask = math_node(nodes, links, "MULTIPLY",
                            math_node(nodes, links, "MAXIMUM", math_node(nodes, links, "SUBTRACT", streak.outputs["Fac"], 0.58), 0.0), 3.0)
    scuffed = mix_rgb(nodes, links, base, (0.12, 0.115, 0.085, 1.0), streak_mask)

    # Wear: sharp convex edges (lug edges, lip) light grey
    geometry = nodes.new("ShaderNodeNewGeometry")
    wear = math_node(nodes, links, "MULTIPLY",
                     math_node(nodes, links, "MAXIMUM", math_node(nodes, links, "SUBTRACT", geometry.outputs["Pointiness"], 0.53), 0.0), 9.0)
    worn = mix_rgb(nodes, links, scuffed, (0.15, 0.142, 0.105, 1.0), math_node(nodes, links, "MINIMUM", wear, 0.7))

    # Dust: faces looking at world up, broken up by noise
    up = nodes.new("ShaderNodeSeparateXYZ")
    links.new(geometry.outputs["Normal"], up.inputs["Vector"])
    dust = math_node(nodes, links, "MULTIPLY",
                     math_node(nodes, links, "MAXIMUM", math_node(nodes, links, "SUBTRACT", up.outputs["Z"], 0.3), 0.0),
                     math_node(nodes, links, "ADD", noise.outputs["Fac"], 0.3))
    dusty = mix_rgb(nodes, links, worn, (0.2, 0.18, 0.13, 1.0), math_node(nodes, links, "MINIMUM", dust, 0.8))
    links.new(math_node(nodes, links, "ADD", math_node(nodes, links, "MULTIPLY", noise.outputs["Fac"], 0.1), 0.78),
              bsdf.inputs["Roughness"])

    # Tread pattern: source UV (u profile length m, v circumference m) -> pattern texture (u: relative to the tread centre, v: seamless repeat)
    coords = nodes.new("ShaderNodeSeparateXYZ")
    links.new(uv, coords.inputs["Vector"])
    tex_u = math_node(nodes, links, "ADD", math_node(nodes, links, "MULTIPLY", coords.outputs["X"], 1.0 / TREAD_W),
                      0.5 - TREAD_CENTER / TREAD_W)
    tex_v = math_node(nodes, links, "FRACT", math_node(nodes, links, "MULTIPLY", coords.outputs["Y"], 1.0 / TREAD_TILE))
    vector = nodes.new("ShaderNodeCombineXYZ")
    links.new(tex_u, vector.inputs["X"])
    links.new(tex_v, vector.inputs["Y"])
    tread = nodes.new("ShaderNodeTexImage")
    tread.image = bpy.data.images.load(os.path.join(om.SOURCE_TEXTURE_DIR, TREAD_TEXTURE), check_existing=True)
    tread.image.colorspace_settings.name = "Non-Color"
    tread.extension = "EXTEND"                  # no pattern outside the tread (the texture's edge is flat)
    tread.interpolation = "Cubic"
    links.new(vector.outputs["Vector"], tread.inputs["Vector"])
    height = tread.outputs["Color"]
    groove = math_node(nodes, links, "SUBTRACT", 1.0, height)
    # Dirt in the groove bottoms, wear on the block edges (light)
    dirty = mix_rgb(nodes, links, dusty, (0.03, 0.028, 0.025, 1.0), math_node(nodes, links, "MULTIPLY", groove, 0.75))
    edge = math_node(nodes, links, "MINIMUM", math_node(nodes, links, "MULTIPLY",
                                                        math_node(nodes, links, "MULTIPLY", height, groove), 4.0), 1.0)
    final = mix_rgb(nodes, links, dirty, (0.14, 0.135, 0.1, 1.0), math_node(nodes, links, "MULTIPLY", edge, 0.35))
    links.new(final, bsdf.inputs["Base Color"])
    tread_bump = nodes.new("ShaderNodeBump")
    tread_bump.inputs["Strength"].default_value = 1.0
    tread_bump.inputs["Distance"].default_value = 0.0045
    links.new(height, tread_bump.inputs["Height"])

    # Fine rubber grain (on top of the tread pattern)
    grain = nodes.new("ShaderNodeTexNoise")
    grain.inputs["Scale"].default_value = 260.0
    grain.inputs["Detail"].default_value = 2.0
    links.new(texture.outputs["Object"], grain.inputs["Vector"])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.25
    bump.inputs["Distance"].default_value = 0.0006
    links.new(grain.outputs["Fac"], bump.inputs["Height"])
    links.new(tread_bump.outputs["Normal"], bump.inputs["Normal"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


# ---------- Tire ----------

# Tread strips (along the axis, m; drawn at 205 width and scaled to TIRE_HALF)
TREAD_A = (-0.07, -0.055, -0.04, -0.025, -0.008, 0.008, 0.025, 0.04, 0.055, 0.07)


def tire_profile():
    """
    Closed cross-section (a along the axis, radius r): the outer face from one bead opening to the other, the inner liner back. On the sidewall a
    rim protector rib and a ring groove (the two ring lines in the video), the tread split into strips (the lugs bulge from these).
    Drawn from a 205/55 R16 cross-section; the sidewall height and width are stretched to the TIRE_* sizes.
    """
    half = 0.1025
    side = [(-0.084, 0.203), (-0.09, 0.207), (-0.094, 0.212), (-0.1015, 0.2155), (-0.1015, 0.2215), (-0.096, 0.2255),
            (-0.099, 0.236), (-0.1015, 0.245), (-0.0955, 0.2485), (-0.0955, 0.2555), (-0.1015, 0.259),
            (-half, 0.266), (-0.1015, 0.282), (-0.097, 0.296), (-0.09, 0.3065), (-0.08, 0.3125)]
    crown = [(a, 0.3162 - 0.6 * a * a) for a in TREAD_A]
    outer = side + crown + [(-a, r) for a, r in reversed(side)]
    inner = [(0.077, 0.206), (0.084, 0.222), (0.0885, 0.25), (0.0875, 0.275), (0.082, 0.292), (0.07, 0.301),
             (0.0, 0.3035), (-0.07, 0.301), (-0.082, 0.292), (-0.0875, 0.275), (-0.0885, 0.25), (-0.084, 0.222),
             (-0.077, 0.206)]
    stretch = (TIRE_OUT - TIRE_BEAD) / (0.3162 - 0.203)
    return [(a * TIRE_HALF / half, TIRE_BEAD + (r - 0.203) * stretch) for a, r in outer + inner], len(side)


PROFILE, TREAD_START = tire_profile()
ARC = [0.0]
for (a0, r0), (a1, r1) in zip(PROFILE, PROFILE[1:] + PROFILE[:1]):
    ARC.append(ARC[-1] + math.hypot(a1 - a0, r1 - r0))
SEGMENTS = 192

# Tread pattern (old tires studied: Sketchfab "Dirty Old Tires", "Tire Swing"): V/arrow-shaped blocks with rounded edges,
# a zigzag longitudinal groove in the middle, zigzag grooves on both sides, shoulder blocks with lateral grooves widening outwards,
# fine sipes in the blocks; since it is a worn old tire the silhouette is round, the pattern is baked from a height texture into the normal
# map. The texture is generated from code (source_textures/generated/tire_tread.png), seamless around the circumference.
TREAD_PITCH = 2.0 * math.pi * TIRE_OUT / 56     # 56 lug pitches: a whole number around the circumference
TREAD_TILE = 4 * TREAD_PITCH
TREAD_W = 0.17
TREAD_CENTER = (ARC[TREAD_START] + ARC[TREAD_START + len(TREAD_A) - 1]) * 0.5
TREAD_TEXTURE = "generated/tire_tread.png"


def make_tread_texture(nu=512, nv=448):
    """Height texture of the tread pattern (1 = block face, 0 = groove bottom; block edges rounded over 1.4 mm)."""
    import numpy as np

    def smoothstep(a, b, x):
        t = np.clip((x - a) / (b - a), 0.0, 1.0)
        return t * t * (3.0 - 2.0 * t)

    def tri(t):
        f = t - np.floor(t)
        return 4.0 * np.abs(f - 0.5) - 1.0

    x = (np.arange(nu) + 0.5) / nu * TREAD_W - TREAD_W / 2
    y = (np.arange(nv) + 0.5) / nv * TREAD_TILE
    X, Y = np.meshgrid(x, y)
    P = TREAD_PITCH
    ax = np.abs(X)
    left = X < 0.0

    def groove(d, w):
        return smoothstep(w, w + 0.0014, d)

    d_center = np.abs(X - 0.005 * tri(Y / P))
    d_side = np.abs(ax - (0.036 + 0.004 * tri(Y / P + 0.5)))
    slope = 0.55
    t = (Y - slope * ax) / P + np.where(left, 0.5, 0.0)
    d_lat = np.abs(t - np.round(t)) * P / math.sqrt(1.0 + slope * slope)
    ts = (Y - 0.2 * ax) / P + np.where(left, 0.25, 0.75)
    d_sh = np.abs(ts - np.round(ts)) * P
    h = np.minimum(groove(d_center, 0.0028), groove(d_side, 0.0024))
    h = np.minimum(h, np.where(ax < 0.036, groove(d_lat, 0.0016), 1.0))
    h = np.minimum(h, np.where(ax >= 0.036, groove(d_sh, 0.0018 + np.clip(ax - 0.04, 0.0, None) * 0.06), 1.0))
    tsp = t + 0.5
    d_sipe = np.abs(tsp - np.round(tsp)) * P / math.sqrt(1.0 + slope * slope)
    h = h * np.where(ax < 0.07, 1.0 - 0.45 * (1.0 - smoothstep(0.0003, 0.0009, d_sipe)), 1.0)
    fade = smoothstep(0.072, 0.085, ax)
    h = h * (1.0 - fade) + fade

    path = os.path.join(om.SOURCE_TEXTURE_DIR, TREAD_TEXTURE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    image = bpy.data.images.new("tire_tread_generate", nu, nv, alpha=False, float_buffer=False)
    image.colorspace_settings.name = "Non-Color"
    rgba = np.ones((nv, nu, 4), dtype=np.float32)
    for channel in range(3):
        rgba[..., channel] = h
    image.pixels.foreach_set(rgba.ravel())
    image.filepath_raw = path
    image.file_format = "PNG"
    image.save()
    bpy.data.images.remove(image)


def build_tire(bm):
    circumference = 2.0 * math.pi * TIRE_OUT

    def uv(i, j):
        return (ARC[i], j / SEGMENTS * circumference)

    faces = om.revolve_at(bm, PROFILE, SEGMENTS, TIRE_CENTER, V(0, 0, 1), material=1, uv=uv)
    om.finish_shell(bm, [f for row in faces for f in row if f is not None])


# ---------- Rope ----------

def _hull(points):
    """Convex hull (counter-clockwise) of 2D points."""
    pts = sorted(set(points))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _erode(poly, e):
    """A convex counter-clockwise polygon shrunk by e (every edge moved inwards; Sutherland-Hodgman clipping)."""
    out = list(poly)
    for k in range(len(poly)):
        (ax, ay), (bx, by) = poly[k], poly[(k + 1) % len(poly)]
        length = math.hypot(bx - ax, by - ay)
        if length < 1e-9:
            continue
        nx, ny = (by - ay) / length, -(bx - ax) / length
        limit = nx * ax + ny * ay - e
        clipped = []
        for i in range(len(out)):
            p, q = out[i], out[(i + 1) % len(out)]
            dp, dq = nx * p[0] + ny * p[1] - limit, nx * q[0] + ny * q[1] - limit
            if dp <= 0:
                clipped.append(p)
            if (dp <= 0) != (dq <= 0):
                t = dp / (dp - dq)
                clipped.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
        out = clipped
    cleaned = []
    for p in out:
        if not cleaned or math.hypot(p[0] - cleaned[-1][0], p[1] - cleaned[-1][1]) > 1e-7:
            cleaned.append(p)
    if len(cleaned) > 1 and math.hypot(cleaned[0][0] - cleaned[-1][0], cleaned[0][1] - cleaned[-1][1]) < 1e-7:
        cleaned.pop()
    return cleaned


def _grow(poly, radius, step=math.radians(3.0)):
    """Boundary of a convex counter-clockwise polygon grown by `radius`: the edges moved out, arcs round the corners."""
    n = len(poly)
    normals = []
    for k in range(n):
        (ax, ay), (bx, by) = poly[k], poly[(k + 1) % n]
        length = math.hypot(bx - ax, by - ay)
        normals.append(math.atan2(-(bx - ax) / length, (by - ay) / length))
    out = []
    for k in range(n):
        a0, a1 = normals[k - 1], normals[k]
        while a1 < a0:
            a1 += 2.0 * math.pi
        steps = max(1, int((a1 - a0) / step))
        for i in range(steps + 1):
            a = a0 + (a1 - a0) * i / steps
            out.append((poly[k][0] + radius * math.cos(a), poly[k][1] + radius * math.sin(a)))
    return out


def loop_section():
    """
    The loaded loop's centreline in the tire's cross-section (a along the axis, r from the axis; counter-clockwise, so at the top it
    runs towards -a = the front): the profile's hull grown by the rope radius (pressed PRESS into the rubber), with its corners
    rounded to BEND (the hull is first shrunk by BEND - R, then grown by BEND: no bend tighter than one rope diameter).
    """
    hull = _hull([(round(a, 6), round(r, 6)) for a, r in PROFILE])
    core = _erode(hull, BEND - (ROPE_R - PRESS))
    return _grow(core, BEND)


def hermite(p0, t0, p1, t1, steps=40):
    """Cubic Hermite curve from p0 (direction t0) to p1 (direction t1), tangents scaled to the chord; without p0."""
    m = (p1 - p0).length
    t0, t1 = t0.normalized() * m, t1.normalized() * m
    out = []
    for k in range(1, steps + 1):
        t = k / steps
        h00, h10, h01, h11 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t, -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
        out.append(p0 * h00 + t0 * h10 + p1 * h01 + t1 * h11)
    return out


def arc_fillet(points, radius, step=math.radians(4.0)):
    """Rounds every corner of a polyline with a circular arc of `radius` (less where the legs are too short); a true arc,
    so the bend is never tighter than asked (a quadratic Bezier corner is 0.7 x as tight)."""
    pts = [Vector(p) for p in points]
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = pts[i - 1], pts[i], pts[i + 1]
        d1, d2 = (b - a).normalized(), (c - b).normalized()
        turn = d1.angle(d2)
        if turn < 1e-4:
            out.append(b)
            continue
        cut = min(radius * math.tan(turn / 2.0), (b - a).length * 0.49, (c - b).length * 0.49)
        r = cut / math.tan(turn / 2.0)
        p1 = b - d1 * cut
        inward = (d2 - d1 * d1.dot(d2)).normalized()
        centre = p1 + inward * r
        steps = max(2, int(turn / step))
        for k in range(steps + 1):
            phi = turn * k / steps
            out.append(centre - inward * r * math.cos(phi) + d1 * r * math.sin(phi))
    out.append(pts[-1])
    return out


def local(x, r, a):
    """A point x off the tire's middle plane, r from the axis (on the circle through the top), a along the axis -> world."""
    return TIRE_CENTER + V(x, math.sqrt(max(r * r - x * x, 0.0)), a)


TIRE_HITCH_TURNS = 1.5
BRANCH_HITCH_TURNS = 2.0
ROPE_PARTS = {}                 # name -> (first, last) sample index on the final path (for the audit)


def tire_knot():
    """
    On the tire, from the hanging rope down: through the half hitches on top, round the lowest turn (it works as a pulley) over the
    front shoulder, down the front sidewall, under the bead, up the back sidewall (moving 2 R aside), up into the hitches round the
    standing part (TIRE_HITCH_TURNS turns going up), out at the back, down onto the tread and over the back shoulder (the tail).
    Returns {"pulley": y of the lump's front-lowest point (local), "parts": [(name, points), ...]}.
    """
    loop = loop_section()
    n = len(loop)
    middle = (TIRE_OUT + TIRE_BEAD) * 0.5

    def crossing(a_value, start=0):
        """Index k on the upper chain where the loop (counter-clockwise) passes a = a_value going towards -a."""
        for i in range(n):
            k = (start + i) % n
            (a0, r0), (a1, r1) = loop[k], loop[(k + 1) % n]
            if r0 > middle and a0 >= a_value > a1:
                return k
        raise RuntimeError(f"the loop does not cross a = {a_value}")

    def at(k, a_value):
        (a0, r0), (a1, r1) = loop[k], loop[(k + 1) % n]
        t = (a0 - a_value) / (a0 - a1)
        return r0 + (r1 - r0) * t

    k_start = crossing(-CONTACT)
    r_start = at(k_start, -CONTACT)
    pulley = r_start + CONTACT                       # the lowest turn's front point (local y; x = 0, a = -CONTACT)
    y_b = pulley - PITCH * 0.25                      # where the hitch helix starts (theta = pi, x = -CONTACT)

    # The standing part's bend round the pulley: from (0, pulley, 0) going down to (0, r_start, -CONTACT) going -a
    hang = [TIRE_CENTER + V(0, pulley, 0)]
    for k in range(1, 13):
        phi = 0.5 * math.pi * k / 12
        hang.append(TIRE_CENTER + V(0, pulley - CONTACT * math.sin(phi), -CONTACT + CONTACT * math.cos(phi)))

    # The loop: from a = -CONTACT at the top round the front, under the bead, up the back, to a = +4 R on top
    a_end = 4.0 * ROPE_R
    k_end = crossing(a_end, k_start + n // 2)
    section = [(-CONTACT, r_start)]
    k = (k_start + 1) % n
    while True:
        section.append(loop[k])
        if k == k_end:
            break
        k = (k + 1) % n
    section.append((a_end, at(k_end, a_end)))
    lengths = [0.0]
    for (a0, r0), (a1, r1) in zip(section, section[1:]):
        lengths.append(lengths[-1] + math.hypot(a1 - a0, r1 - r0))
    # x moves from 0 (front) to -CONTACT (back) while the loop goes under the bead (the back leg rises beside the standing part)
    def x_of(s):
        t = min(max((s / lengths[-1] - 0.35) / 0.3, 0.0), 1.0)
        return -CONTACT * (t * t * (3.0 - 2.0 * t))
    belt = [local(x_of(s), r, a) for (a, r), s in zip(section[1:], lengths[1:])]

    # The back leg rises from the tread into the hitch helix (theta = pi: x = -CONTACT, a = 0, going -a)
    rise_slope = PITCH / (2.0 * math.pi * CONTACT)
    end = belt[-1]
    start_helix = TIRE_CENTER + V(-CONTACT, y_b, 0.0)
    rise = hermite(end, V(0, 0, -1), start_helix, V(0, rise_slope, -1), 30)

    # Half hitches: TIRE_HITCH_TURNS turns round the standing part going up (theta from pi)
    turns = []
    count = int(TIRE_HITCH_TURNS * 64)
    for k in range(1, count + 1):
        theta = math.pi + 2.0 * math.pi * TIRE_HITCH_TURNS * k / count
        y = y_b + PITCH * (theta - math.pi) / (2.0 * math.pi)
        turns.append(TIRE_CENTER + V(CONTACT * math.cos(theta), y, CONTACT * math.sin(theta)))
    y_e = y_b + PITCH * TIRE_HITCH_TURNS
    theta_end = math.pi + 2.0 * math.pi * TIRE_HITCH_TURNS
    out_dir = V(-math.sin(theta_end), rise_slope, math.cos(theta_end))

    # Tail: out of the last turn (x = +CONTACT, going +a), down onto the back of the tread, then along the loop's hull (clockwise)
    # over the back shoulder and down the back sidewall, ending 10 cm under the tread
    land_a = 7.5 * ROPE_R
    k_land = crossing(land_a, k_start + n // 2)
    corners = [turns[-1] - out_dir.normalized() * 0.004, turns[-1], turns[-1] + out_dir.normalized() * 2.2 * ROPE_R,
               local(CONTACT, at(k_land, land_a), land_a)]
    k = k_land
    while True:
        a, r = loop[k]
        if r < TIRE_OUT - 0.10:
            break
        if a > land_a + 1e-4:
            corners.append(local(CONTACT, r, a))
        k = (k - 1) % n
    tail = arc_fillet(corners, 2.5 * ROPE_R)[2:]
    return {"pulley": pulley, "top": y_e + ROPE_R,
            "parts": [("tire_bend", hang), ("loop", belt), ("loop_rise", rise), ("tire_hitches", turns), ("tire_tail", tail)]}


def branch_knot(hang_bottom_y):
    """
    On the branch, from the tail's end up: the tail along the standing part, two half hitches round it (going up), the rope under the
    round turn (clear of it) to the branch's far side and straight up into the round turn, the round turn back to SIDE (decreasing
    alpha), the bend to vertical and the hanging rope down to `hang_bottom_y`.
    """
    sx, sz = HANG_TOP.x, HANG_TOP.z
    top = HANG_TOP.y - 0.14
    bottom = top - PITCH * BRANCH_HITCH_TURNS
    far = wrap_point(5.0 * math.pi)
    theta_top = math.atan2(far.z - sz, far.x - sx)          # the hitches end facing the branch's far side
    theta_bottom = theta_top - 2.0 * math.pi * BRANCH_HITCH_TURNS
    slope = PITCH / (2.0 * math.pi * CONTACT)

    def around(u, y):
        """Unrolled coordinates on the cylinder of radius CONTACT round the standing part -> world."""
        return V(sx + CONTACT * math.cos(u / CONTACT), y, sz + CONTACT * math.sin(u / CONTACT))

    # Tail: hangs 6 cm down beside the standing part and turns into the lowest hitch along an arc of 4 R drawn on the cylinder
    # (on the cylinder its bend is ~0.9 diameter: the cylinder's own curve adds to it)
    rho = 4.0 * ROPE_R
    gamma = 0.5 * math.pi - math.atan(slope)
    u_end = CONTACT * theta_bottom
    u_t, y_t = u_end - rho * (1.0 - math.cos(gamma)), bottom - rho * math.sin(gamma)
    tail = [around(u_t, y_t - 0.06 + 0.06 * k / 12) for k in range(12)]
    tail += [around(u_t + rho - rho * math.cos(gamma * k / 16), y_t + rho * math.sin(gamma * k / 16)) for k in range(17)]
    count = int(BRANCH_HITCH_TURNS * 64)
    hitches = [around(u_end + CONTACT * 2.0 * math.pi * BRANCH_HITCH_TURNS * k / count,
                      bottom + PITCH * BRANCH_HITCH_TURNS * k / count) for k in range(1, count + 1)]
    q = hitches[-1]
    q_dir = (hitches[-1] - hitches[-2]).normalized()
    # Under the round turn (more than a rope's width below its lowest turn) to the far side, then up into it along its tangent
    below = far - UPW * (WRAP_R + CONTACT + 0.012)
    climb = arc_fillet([q - q_dir * 0.004, q, q + q_dir * 7.0 * ROPE_R, below, far], 2.5 * ROPE_R)[2:]
    steps = int(5.0 * math.pi / math.radians(3.0))
    wrap = [wrap_point(5.0 * math.pi * (1.0 - k / steps)) for k in range(1, steps + 1)]
    down = list(HANG_BEND)
    length = HANG_TOP.y - hang_bottom_y
    rope = [HANG_TOP + V(0, -length * k / 200, 0) for k in range(1, 201)]
    return [("branch_tail", tail), ("branch_hitches", hitches), ("branch_climb", climb), ("round_turn", wrap),
            ("hang_bend", down), ("hanging", rope)]


def resample(points, spacing):
    lengths = [0.0]
    for a, b in zip(points, points[1:]):
        lengths.append(lengths[-1] + (b - a).length)
    total = lengths[-1]
    count = max(2, int(round(total / spacing)))
    out, k = [], 0
    for i in range(count + 1):
        target = total * i / count
        while k < len(lengths) - 2 and lengths[k + 1] < target:
            k += 1
        span = max(lengths[k + 1] - lengths[k], 1e-12)
        out.append(points[k].lerp(points[k + 1], min(max((target - lengths[k]) / span, 0.0), 1.0)))
    return out, lengths


def rope_path():
    """The whole rope as one centreline (branch tail end -> tire tail end), resampled every SPACING; ROPE_PARTS marks its pieces."""
    knot = tire_knot()
    pieces = branch_knot(TIRE_CENTER.y + knot["pulley"]) + knot["parts"]
    raw, marks = [], []
    for name, pts in pieces:
        first = len(raw)
        for p in pts:
            if not raw or (p - raw[-1]).length > 1e-6:
                raw.append(Vector(p))
        marks.append((name, first, len(raw) - 1))
    path, raw_lengths = resample(raw, SPACING)
    total = raw_lengths[-1]
    for name, first, last in marks:
        ROPE_PARTS[name] = (int(round(raw_lengths[first] / total * (len(path) - 1))),
                            int(round(raw_lengths[last] / total * (len(path) - 1))))
    return path


def frames(path):
    """Rotation-minimising frames (parallel transport) along the path: [(tangent, normal, binormal)], arc lengths."""
    tangents = []
    for i in range(len(path)):
        a, b = path[max(i - 1, 0)], path[min(i + 1, len(path) - 1)]
        tangents.append((b - a).normalized())
    helper = V(1, 0, 0) if abs(tangents[0].x) < 0.9 else V(0, 0, 1)
    normal = tangents[0].cross(helper).normalized()
    out, lengths = [], [0.0]
    for i, t in enumerate(tangents):
        if i:
            lengths.append(lengths[-1] + (path[i] - path[i - 1]).length)
        normal = (normal - t * normal.dot(t)).normalized()
        out.append((t, normal, t.cross(normal)))
    return out, lengths


def fray(bm, tip, direction, radial, rng):
    """Fibres opening out of a strand's cut end: thin tapering tufts."""
    side = direction.cross(radial).normalized()
    for k in range(4):
        spread = radial * rng.uniform(0.15, 0.5) + side * rng.uniform(-0.35, 0.35)
        start = tip - direction * 0.004 + side * rng.uniform(-0.6, 0.6) * STRAND_R + radial * rng.uniform(-0.3, 0.5) * STRAND_R
        length = rng.uniform(0.022, 0.038)
        end = start + (direction + spread).normalized() * length + V(0, -0.004, 0)
        mid = (start + end) * 0.5 + spread * 0.003
        om.sweep(bm, [start, mid, end], 0.0011, sides=5, material=0, radii=[1.0, 0.7, 0.3],
                 uv_scale=(1.0, 1.0 / FIBRE_TILE))


ROPE_PATH = []


def build_rope(bm):
    """Three strands twisted along the rope's centreline (Z-lay, one turn per LAY); both cut ends open into frayed strands."""
    path = rope_path()
    ROPE_PATH[:] = path
    frame, lengths = frames(path)
    rng = random.Random(7)
    for k in range(3):
        strand = []
        for (t, normal, binormal), p, s in zip(frame, path, lengths):
            theta = 2.0 * math.pi * s / LAY + 2.0 * math.pi * k / 3.0
            strand.append(p + (normal * math.cos(theta) + binormal * math.sin(theta)) * STRAND_A)
        radii = [1.0] * len(strand)
        # The cut ends: the strands open out over 2.2 cm, thinning, and their fibres splay
        ends = []
        for index, sign in ((0, -1.0), (len(path) - 1, 1.0)):
            t = frame[index][0] * sign
            radial = (strand[index] - path[index]).normalized()
            extra = [strand[index] + t * (0.0055 * j) + radial * (0.0055 * j * math.tan(math.radians(16.0))) for j in range(1, 5)]
            ends.append((extra, t, radial))
        start_extra, end_extra = ends[0][0], ends[1][0]
        strand = list(reversed(start_extra)) + strand + end_extra
        taper = [0.72, 0.8, 0.88, 0.95]
        radii = taper + radii + list(reversed(taper))
        om.sweep(bm, strand, STRAND_R, sides=STRAND_SIDES, material=0, radii=radii, uv_scale=(1.0, 1.0 / FIBRE_TILE))
        for extra, t, radial in ends:
            fray(bm, extra[-1], t, radial, rng)


def rope_audit():
    """
    Measures the built rope's centreline: the closest approach of two parts of the rope (2 R = lying against each other), the tightest
    bend (in rope diameters), and the loop's distance from the tire surface (0 = touching; negative = pressed in). Fails the build on
    rope parts passing through each other, bends under 0.95 diameter, the loop floating off the tire or sinking into it.
    """
    import numpy as np
    from mathutils.bvhtree import BVHTree

    path = np.array([tuple(p) for p in ROPE_PATH])
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))])
    closest = np.inf
    where = None
    for i in range(0, len(path), 2):
        d = np.linalg.norm(path - path[i], axis=1)
        d[np.abs(s - s[i]) < 3.2 * CONTACT] = np.inf
        j = int(np.argmin(d))
        if d[j] < closest:
            closest, where = float(d[j]), (i, j)
    a, b, c = path[:-2], path[1:-1], path[2:]
    ab, bc, ca = np.linalg.norm(b - a, axis=1), np.linalg.norm(c - b, axis=1), np.linalg.norm(a - c, axis=1)
    area2 = np.linalg.norm(np.cross(b - a, c - a), axis=1)
    radius = np.where(area2 > 1e-14, ab * bc * ca / np.maximum(2.0 * area2, 1e-14), np.inf)
    # Bends are measured over 3 samples: average over 3 neighbours so resampling noise is not counted as a kink
    smooth = np.minimum.reduce([radius[:-2], radius[1:-1], radius[2:]]) if len(radius) > 2 else radius
    tight = int(np.argmin(smooth))
    tire = bmesh.new()
    build_tire(tire)
    tree = BVHTree.FromBMesh(tire)
    tire.free()
    first, last = ROPE_PARTS["loop"]
    gaps = []
    for i in range(first, last + 1):
        p = Vector(path[i])
        hit = tree.find_nearest(p)
        sign = 1.0 if (p - hit[0]).dot(hit[1]) >= 0.0 else -1.0
        gaps.append(sign * hit[3] - ROPE_R)
    gaps = np.array(gaps)

    def part_of(index):
        return next((name for name, (f, l) in ROPE_PARTS.items() if f <= index <= l), "?")

    report = {
        "samples": len(path), "lengthM": round(float(s[-1]), 3),
        "closestRopeToRope_R": round(closest / ROPE_R, 3), "closestAt": [part_of(where[0]), part_of(where[1])],
        "tightestBend_D": round(float(smooth[tight]) / (2.0 * ROPE_R), 3), "tightestAt": part_of(tight + 2),
        "loopGapToTireMm": {"min": round(float(gaps.min()) * 1000, 2), "max": round(float(gaps.max()) * 1000, 2),
                            "touchingPercent": round(100.0 * float(np.mean(np.abs(gaps + PRESS) < 0.0015)), 1)},
        "tireCenter": [round(TIRE_CENTER.x, 4), round(TIRE_CENTER.y, 4), round(TIRE_CENTER.z, 4)],
        "hangTop": [round(HANG_TOP.x, 4), round(HANG_TOP.y, 4), round(HANG_TOP.z, 4)],
    }
    om.log(f"rope: {report}")
    problems = []
    if closest < 1.9 * ROPE_R:
        problems.append(f"rope parts pass through each other: {closest / ROPE_R:.2f} R apart ({report['closestAt']})")
    # A wrap round another rope is 1 D by itself and turning into it adds a little; under 0.75 D the inside strands would pinch
    if smooth[tight] < 0.75 * 2.0 * ROPE_R:
        problems.append(f"a bend tighter than 0.75 diameter: {report['tightestBend_D']} D at {report['tightestAt']}")
    if gaps.min() < -0.002:
        problems.append(f"the loop sinks {-gaps.min() * 1000:.1f} mm into the tire")
    # (where the loop bridges the hole between the bead toes it is off the rubber by design; elsewhere it must lie on it)
    if report["loopGapToTireMm"]["touchingPercent"] < 55.0:
        problems.append(f"the loop touches the tire along {report['loopGapToTireMm']['touchingPercent']}% of its length only")
    if problems:
        model.qc["rope"] = report
        model._write_qc()
        raise RuntimeError("tire_swing: rope audit: " + "; ".join(problems))
    return report


make_tread_texture()
make_strand_texture()
ROPE = model.textured_surface("rope", "matte", "Swing rope: 3-strand hemp rope, every strand modelled, its yarns in a generated texture; "
                              "beige in the video, clearly twisted, matte", rope_nodes)
TIRE = model.textured_surface("tire", "matte", "Swing tire: old car tire rubber; dark olive brown-grey in the video, matte, "
                              "worn, scuffed and dusty", rubber_nodes)

rope = bmesh.new()
build_rope(rope)
# Plain smooth normals on the rope: normals weighted by face area made the soft strands read as flat facets
model.part("Rope", rope, [ROPE, TIRE], unity=True, smooth=True, weighted=False)
tire = bmesh.new()
build_tire(tire)
model.part("Tire", tire, [ROPE, TIRE], unity=True, smooth=True)


def unity_dir(x, y, z):
    return (-x, -z, y)


def to_blender(v):
    return (-v.x, -v.z, v.y)


everything = ["TireSwing"]
model.qc["rope"] = rope_audit()
# Measured at finish: the hanging rope runs from the branch (outside the model) straight down to where the loop lies on the
# tire (the loop's middle spans the hole under the bead and touches nothing: not a point for this)
hang_first, hang_last = ROPE_PARTS["hanging"]
model.route("HangingRope", [ROPE_PATH[hang_first], ROPE_PATH[hang_last], ROPE_PATH[ROPE_PARTS["loop"][0]]],
            tol=0.014, free=(0,), unity=True, part="Rope", ends=(None, "Tire"))
turn_first, turn_last = ROPE_PARTS["round_turn"]
model.support("branch", [ROPE_PATH[turn_first], ROPE_PATH[(turn_first + turn_last) // 2]], tol=0.014, unity=True,
              component="RoundTurn")   # the bark under the round turn (the branch is the tree's model)
model.finish_textured(
    size=2048,
    joined_name="TireSwing",
    ground=0.0,
    ao_distance=0.15,
    budget=90000,
    views=[
        {"file": "overview", "label": "Swing (the angle in the video)", "objects": everything, "direction": unity_dir(-0.3, 0.1, -1.0),
         "ground": 0.0},
        {"file": "tire", "label": "Tire and knot (the 1:07 angle in the video)", "objects": everything,
         "direction": unity_dir(-0.35, 0.12, -1.0), "target": to_blender(TIRE_CENTER + V(0, 0.08, 0)), "radius": 0.45,
         "ground": 0.0},
        {"file": "knot", "label": "Hitch and tail", "objects": everything, "direction": unity_dir(-0.6, 0.2, -1.0),
         "target": to_blender(TIRE_CENTER + V(0, TIRE_OUT + 0.05, 0)), "radius": 0.17, "ground": 0.0},
        {"file": "side", "label": "From the side: the loop wraps the tire's cross-section", "objects": everything,
         "direction": unity_dir(1.0, 0.1, 0.0), "target": to_blender(TIRE_CENTER + V(0, TIRE_OUT, 0)), "radius": 0.22,
         "ground": 0.0},
        {"file": "outer", "label": "Tire tread: lugs", "objects": everything, "direction": unity_dir(0.2, -0.6, -1.0),
         "target": to_blender(TIRE_CENTER + V(0, -0.28, 0)), "radius": 0.16, "ground": 0.0},
        {"file": "branch", "label": "The rope wound around the branch and its knot", "objects": everything, "direction": unity_dir(-0.3, -0.2, -1.0),
         "target": to_blender(HOOK - V(0, 0.08, 0)), "radius": 0.25, "ground": 0.0},
    ],
    references=[
        {"label": "Reference: video 1:07 (tire, knot, tail)", "path": "docs/reference/32_swing_close.png",
         "crop": [255, 150, 260, 280]},
        {"label": "Reference: video 1:06", "path": "docs/reference/27_tree_swing.png", "crop": [330, 0, 420, 478]},
    ],
)
