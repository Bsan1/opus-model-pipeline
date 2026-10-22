"""
Mower wheels: RearWheel (Ø 230 x 55 mm) and FrontWheel (Ø 190 x 45 mm); sizes the same as MowerModel.

Reference (video, docs/reference/01, 21 and 22): the wheels only show at the back corners of the housing, from behind and
above; charcoal grey, a thick tire, a fine stepped tread in the silhouette. The rim and hub never show in the video (a guess):
dark grey plastic, an eight-pocket moulded rim and a dark grey hub cap.

21 October 2026 ("the wheels are toy-like"): the first version had 16 big blocks per row, 6 mm tall, spilling down the sidewall,
and a red hub cap; it read as a toy off-road tire. Now: 32 small blocks per row, 3.5 mm tall, only on the tread (like a plastic
push-mower wheel), a dark cap, and the textured pipeline: rubber grain (CC0 ambientCG Rubber001 height as bump), worn light
block edges, dust on top; moulded plastic grain on the rim.

Construction (no glued-on boxes):
- Tire: a cross-section profile (bulging sidewall, round shoulder, flat tread) revolved around the axle; the lugs are pushed
  out of the same surface (two rows, offset by half a pitch; they spill from the shoulder onto the sidewall).
- Rim: revolved from its own profile (dish, lip, hub boss, axle hole); the pockets are pushed in from the dish surface,
  leaving spokes between them. The lip grips the tire's bead.
- Hub cap: a dome profile. On sharp edges a 1.2-1.5 mm single-segment chamfer + weighted normals (the hard-surface method used in games:
  the edge catches the light softly, half the triangles of a two-segment one).
Axes: the axle is Blender X; the outer face -X (+X in Unity, the mower's right; on the left wheel MowerModel turns it 180°).
Pivot at the wheel's centre.
"""
import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import bmesh  # noqa: E402
import bpy  # noqa: E402

import opus_model as om  # noqa: E402

SEGMENTS = 96          # angle slices
LUG_PITCH = 3          # lug pitch (slices): 32 lugs / row
LUG_BLOCK = 2          # slices a lug covers
POCKETS = 8            # rim pockets (spokes between them)

model = om.Model("wheel", __file__)
model.plan(
    "push mower wheel: turns on its axle pin and rolls the mower",
    [("video", "only the back corners of the housing show the wheels")],
    [   # name, role, job, attached to, moves, seen/guess/real
        ("Hub", "structural", "turns on the axle pin", ["axle"], "spin", "guess"),
        ("Rim", "structural", "carries the tire; its pockets leave spokes", ["Hub"], "spin", "guess"),
        ("Tire", "functional", "grips the ground, small tread blocks", ["Rim"], "spin", "seen"),
        ("HubCap", "decorative", "covers the hub, dark grey", ["Hub"], "spin", "guess"),
    ],
    supports=("axle",), tier="simple", category="machines")
RUBBER_HEIGHT = os.path.join(om.SOURCE_TEXTURE_DIR, "Rubber001", "Rubber001_1K-PNG_Displacement.png")


def linear(rgb):
    return (*[om.srgb_to_linear(c / 255.0) for c in rgb], 1.0)


def rubber_nodes(nodes, links, bsdf, uv):
    """Charcoal rubber: fine grain (box-projected height as bump), light worn block edges, a little dust on top."""
    coords = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (12.0, 12.0, 12.0)
    links.new(coords.outputs["Object"], mapping.inputs["Vector"])
    height = nodes.new("ShaderNodeTexImage")
    height.image = bpy.data.images.load(RUBBER_HEIGHT, check_existing=True)
    height.image.colorspace_settings.name = "Non-Color"
    height.projection = "BOX"
    height.projection_blend = 0.3
    links.new(mapping.outputs["Vector"], height.inputs["Vector"])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.35
    bump.inputs["Distance"].default_value = 0.0008
    links.new(height.outputs["Color"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    geometry = nodes.new("ShaderNodeNewGeometry")
    edge = nodes.new("ShaderNodeMapRange")       # sharp convex edges (block corners) wear lighter
    edge.inputs["From Min"].default_value = 0.52
    edge.inputs["From Max"].default_value = 0.62
    links.new(geometry.outputs["Pointiness"], edge.inputs["Value"])
    worn = nodes.new("ShaderNodeMix")
    worn.data_type = "RGBA"
    worn.inputs["A"].default_value = linear((44, 44, 48))
    worn.inputs["B"].default_value = linear((78, 76, 74))
    links.new(edge.outputs["Result"], worn.inputs["Factor"])
    up = nodes.new("ShaderNodeSeparateXYZ")
    links.new(geometry.outputs["Normal"], up.inputs["Vector"])
    dust_amount = nodes.new("ShaderNodeMapRange")
    dust_amount.inputs["From Min"].default_value = 0.4
    dust_amount.inputs["From Max"].default_value = 1.0
    dust_amount.inputs["To Max"].default_value = 0.35
    links.new(up.outputs["Z"], dust_amount.inputs["Value"])
    dusty = nodes.new("ShaderNodeMix")
    dusty.data_type = "RGBA"
    dusty.inputs["B"].default_value = linear((112, 104, 92))
    links.new(worn.outputs["Result"], dusty.inputs["A"])
    links.new(dust_amount.outputs["Result"], dusty.inputs["Factor"])
    links.new(dusty.outputs["Result"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.88


def plastic_nodes(rgb, rough):
    def build(nodes, links, bsdf, uv):
        coords = nodes.new("ShaderNodeTexCoord")
        grain = nodes.new("ShaderNodeTexNoise")
        grain.inputs["Scale"].default_value = 700.0
        links.new(coords.outputs["Object"], grain.inputs["Vector"])
        bump = nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.08
        bump.inputs["Distance"].default_value = 0.0003
        links.new(grain.outputs["Fac"], bump.inputs["Height"])
        links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
        bsdf.inputs["Base Color"].default_value = linear(rgb)
        bsdf.inputs["Roughness"].default_value = rough
    return build


TIRE = model.textured_surface("tire", "matte", "Tire: rubber; charcoal grey in the video, no shine", rubber_nodes)
RIM = model.textured_surface("rim", "matte", "Rim: moulded plastic (a guess; not visible in the video)",
                             plastic_nodes((69, 71, 77), 0.7))
CAP = model.textured_surface("cap", "satin", "Hub cap: dark grey plastic (a guess; not visible in the video; the red cap read "
                             "as a toy)", plastic_nodes((47, 48, 52), 0.5))


def quarter(cx, cr, ax, ar, start_deg, end_deg, steps):
    """Points (a, r) of an ellipse arc, ends excluded."""
    points = []
    for k in range(1, steps):
        t = math.radians(start_deg + (end_deg - start_deg) * k / steps)
        points.append((cx + ax * math.cos(t), cr + ar * math.sin(t)))
    return points


def wheel(name, radius, width):
    h = width * 0.5
    depth = radius * 0.03                  # lug height (3.5 mm on the rear wheel)
    crown = radius - depth                 # tread radius without lugs
    bead = radius * 0.60                   # tire bead = rim edge
    wall = crown - bead
    shoulder_a, shoulder_r = 0.30 * h, 0.32 * wall

    bm = bmesh.new()

    # --- Tire profile (outer side -a) ---
    outer = [
        (-0.78 * h, bead - 0.002),
        (-0.90 * h, bead + 0.10 * wall),
        (-0.98 * h, bead + 0.30 * wall),
        (-1.00 * h, bead + 0.52 * wall),
        (-1.00 * h, crown - shoulder_r),
    ]
    outer += quarter(-0.70 * h, crown - shoulder_r, shoulder_a, shoulder_r, 180.0, 90.0, 3)
    outer += [(-0.70 * h, crown), (-0.38 * h, crown), (-0.07 * h, crown)]
    inner = [(-a, r) for a, r in reversed(outer)]
    profile = outer + inner
    tire = om.revolve(bm, profile, SEGMENTS, material=0)
    om.finish_shell(bm, [f for row in tire for f in row if f])

    # Lug regions: from the shoulder (profile edge 5) to the middle of the tread, not down the sidewall; the right row is mirrored
    left_rows = list(range(5, len(outer) - 1))
    right_rows = [len(profile) - 2 - i for i in left_rows]
    for rows, shift in ((left_rows, 0), (right_rows, LUG_PITCH // 2)):
        for start in range(0, SEGMENTS, LUG_PITCH):
            region = [tire[i][(start + shift + k) % SEGMENTS] for i in rows for k in range(LUG_BLOCK)]
            om.extrude_outward(bm, region, depth)

    # --- Rim profile ---
    hub, hole, lip = radius * 0.19, radius * 0.07, bead + radius * 0.05
    rim_profile = [
        (-0.55 * h, hole),
        (-0.55 * h, hub),
        (-0.40 * h, hub + radius * 0.04),
        (-0.22 * h, hub + radius * 0.075),         # start of the dish floor (the pockets start here)
        (-0.22 * h, bead - radius * 0.10),         # end of the dish floor
        # The flange: the slope stays under the tyre seat until it reaches the flange's outer face. (Until 21 October 2026 the
        # slope rose above the seat before a = -0.72h and crossed it: a self-intersecting profile, inside-out slivers the hole
        # gate found.)
        (-0.70 * h, bead - radius * 0.06),
        (-0.92 * h, bead - radius * 0.03),
        (-0.92 * h, lip),
        (-0.72 * h, lip),
        (-0.72 * h, bead - 0.003),
        (0.72 * h, bead - 0.003),
        (0.80 * h, bead + radius * 0.01),
        (0.80 * h, bead - radius * 0.07),
        (0.45 * h, bead - radius * 0.11),
        (0.45 * h, hub + radius * 0.05),
        (0.55 * h, hub),
        (0.55 * h, hole),
    ]
    rim = om.revolve(bm, rim_profile, SEGMENTS, material=1)
    om.finish_shell(bm, [f for row in rim for f in row if f])
    pitch = SEGMENTS // POCKETS
    for p in range(POCKETS):
        # Pocket: pushed in from the dish floor, leaving an edge margin (spoke and ring)
        region = [rim[3][(p * pitch + k) % SEGMENTS] for k in range(pitch - 3)]
        bmesh.ops.inset_region(bm, faces=region, thickness=radius * 0.018, depth=0.0, use_even_offset=True)
        om.extrude_outward(bm, region, -radius * 0.10)

    # --- Hub cap (dome): its back face inside the hub, bulging outwards ---
    face = -0.55 * h + 0.0005
    cap_r = hub * 0.86
    dome = radius * 0.075
    cap_profile = [(face, 0.0), (face, cap_r)]
    cap_profile += [(face - dome * math.cos(math.radians(t)), cap_r * math.sin(math.radians(t)))
                    for t in (80.0, 65.0, 50.0, 35.0, 20.0)]
    cap_profile.append((face - dome, 0.0))
    om.revolve(bm, cap_profile, 48, material=2)

    om.finish_shell(bm)
    return model.part(name, bm, [TIRE, RIM, CAP], bevel={"width": radius * 0.013, "segments": 1, "angle": 30.0})


wheel("RearWheel", 0.115, 0.055)
wheel("FrontWheel", 0.095, 0.045)

both = ["RearWheel", "FrontWheel"]
model.finish_textured(
    size=2048,
    budget=24000,
    total_budget=40000,   # both wheels (each drawn twice in game)
    moving=tuple(both),
    islands="smart",
    ao_distance=0.03,
    ao_together=False,
    views=[
        {"file": "three_quarter", "label": "Rear wheel 3/4 (outer face)", "objects": ["RearWheel"], "direction": (-1.0, -0.75, 0.45)},
        {"file": "front", "label": "From the rolling direction (lug profile)", "objects": ["RearWheel"], "direction": (-0.05, -1.0, 0.12)},
        {"file": "tread", "label": "Tread: two offset rows of small blocks", "objects": ["RearWheel"], "direction": (-0.3, -0.55, 1.0),
         "zoom": 1.1},
        {"file": "outer", "label": "Outer face: pocketed rim, hub", "objects": ["RearWheel"], "direction": (-1.0, -0.1, 0.1)},
        {"file": "inner", "label": "Inner face (facing the housing)", "objects": ["RearWheel"], "direction": (1.0, -0.35, 0.3)},
        {"file": "pair", "label": "Rear and front wheel (ground 10 cm squares)", "objects": both, "direction": (-1.0, -0.55, 0.4),
         "offsets": {"FrontWheel": (0.0, -0.3, -0.02)}},
    ],
    references=[
        {"label": "Reference: video, rear wheel (right)", "path": "docs/reference/21_mower_rear_wheel.png", "crop": [425, 330, 170, 148]},
        {"label": "Reference: video, the mower from behind", "path": "docs/reference/21_mower_rear_wheel.png", "crop": [290, 255, 300, 223]},
    ],
)
