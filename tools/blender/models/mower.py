"""
Push mower: Housing (deck + rear body + wheel plates and axles), Motor (block, cover, grille, fuel
cap, primer bulb, starter), Handle (lower tubes, folding upper U tube, foam, control bar, control cable, clips).
The wheels are in a separate file (wheel.py); this file carries their axles and connection points.

Reference: Builds/Models/mower_reference.png (video 0:02, 0:46, 1:12). The mower is only seen from behind and above.
Visible: the red deck and the two-ring dome around the engine, the stepped wide rear body and the dark red rear flap;
the dark grey engine cover (a ribbed air grille in front, a ridge from the middle to the back, two hollows at the back: a knurled fuel
cap on the left, the primer bulb on the right; a lip underneath); under the lip the silver starter cover with the rope handle leaning on it; dark handle
tubes going down to the black joints above the rear wheels.
A guess (not visible, simple and sensible): the front/underside of the deck, the engine block, the wheel plates and axles, the top of the handle
(off screen): folding nuts, the grab bar, the control bar and its cable.

Mechanical logic: the component plan (model.plan below) says what every part does and what holds it; the control cable's
route is measured (model.route in build_handle).

The points are written in Unity axes (x right, y up, z front; the origin below the deck centre, on the ground). The sizes match
MowerModel/MowerTool in the game; the connection points (axles, grips) are written to the spec file and the Unity test
compares them with the in-game ones.
"""
import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import opus_model as om  # noqa: E402
from opus_model import V  # noqa: E402

FRONT_AXLE = V(0.276, 0.095, 0.22)
REAR_AXLE = V(0.316, 0.115, -0.23)
GRIP = V(0.34, 0.88, -1.03)
FRONT_HUB_IN, REAR_HUB_IN = 0.0124, 0.0151      # the wheel's inner hub face (from the centre, wheel.py: 0.55 * half width)
SIDES = (1.0, -1.0)

model = om.Model("mower", __file__)
model.plan(
    "push mower: cuts the grass while the player pushes it from behind by the handle",
    [("video", "0:02, 0:46, 1:12 (seen only from behind and above)")],
    [   # name, role, job, attached to, moves, seen/guess/real
        ("Axles", "structural", "pins the wheels turn on (the wheels are wheel.py's model)", ["WheelPlates", "wheels"],
         "fixed", "guess"),
        ("WheelPlates", "structural", "carry the axles, bolted to the deck", ["Deck"], "fixed", "guess"),
        ("Deck", "structural", "red deck: shields the blade, carries the engine", ["WheelPlates"], "fixed", "seen"),
        ("RearBody", "structural", "stepped rear body behind the deck", ["Deck"], "fixed", "seen"),
        ("RearFlap", "functional", "dark red flap over the rear discharge, hinged on a pin across the body", ["RearBody"],
         "hinge", "seen"),
        ("Engine", "functional", "drives the blade; block, fuel tank and carburettor under the cover (never seen)", ["Deck"],
         "fixed", "guess"),
        ("EngineCover", "structural", "dark grey cover: ridge, two hollows, a lip", ["Engine"], "fixed", "seen"),
        ("AirGrille", "functional", "cooling air in through the cover's front", ["EngineCover"], "fixed", "seen"),
        ("FuelCap", "functional", "closes the tank's neck coming up through the left hollow (knurled)", ["Engine"], "fixed",
         "seen"),
        ("PrimerBulb", "functional", "primes the carburettor under the right hollow", ["Engine"], "fixed", "seen"),
        ("Starter", "functional", "recoil starter; its rope handle rests on the cover, the rope stays at the engine",
         ["Engine"], "fixed", "seen"),
        ("BrakeTab", "functional", "the engine brake lever the cable pulls", ["Engine"], "hinge", "guess"),
        ("LowerTubes", "structural", "handle tubes bolted to the rear plates", ["WheelPlates"], "fixed", "seen"),
        ("UpperTube", "structural", "folding U tube, wing nuts at the fold", ["LowerTubes"], "hinge", "guess"),
        ("Foam", "functional", "the grip the hands push on", ["UpperTube", "hands"], "fixed", "guess"),
        ("ControlBar", "functional", "held against the grip to keep the engine running", ["UpperTube", "hands"], "hinge",
         "guess"),
        ("ControlCable", "functional", "from the bar's tab down the handle to the brake tab", ["ControlBar", "BrakeTab", "Clips"],
         "flex", "guess"),
        ("Clips", "structural", "hold the cable to the tubes, the rear body and the deck", ["LowerTubes", "UpperTube", "RearBody"],
         "fixed", "guess"),
    ],
    supports=("wheels", "hands"), tier="complex", category="machines")
model.features([   # id, tier, components, what must hold, measured by, view
    ("control_chain", "critical", ["ControlBar", "ControlCable", "Clips", "BrakeTab"],
     "the bar's tab, the cable clipped down the handle and the engine's brake tab form one chain", "route:ControlCable",
     "handle_top"),
    ("on_wheels", "critical", ["Axles", "WheelPlates"], "four axle pins in plates bolted to the deck carry the wheels",
     "support:wheels", "cable"),
    ("push_grip", "critical", ["Foam", "ControlBar"], "the hands push the foam grip and hold the bar against it",
     "support:hands", "handle_top"),
    ("starter", "important", ["Starter"], "the recoil starter's handle rests at its guide on the engine, no loose rope",
     None, "motor"),
])
RED = model.surface("Metal", "#C21F22", "glossy", "Housing: red baked-paint sheet metal; thin bright lines on the dome and the edges in the video")
RED_DARK = model.surface("Metal", "#8F1A1F", "glossy", "Rear flap: the same painted sheet metal as the housing, dark red; a dark red area on top of the rear body in the video")
SHROUD = model.surface("Plastic", "#2F2E31", "matte", "Engine cover: textured black plastic; no highlights in the video, only the upward faces are light")
SHROUD_DARK = model.surface("Plastic", "#252427", "matte", "Inside the cover's rear hollows: the same plastic, in shadow; darker in the video")
BLOCK = model.surface("Metal", "#3E4046", "satin", "Engine block: painted cast aluminium (a guess; hidden under the cover in the video)")
SILVER = model.surface("Metal", "#A3A6AC", "metallic", "Starter cover, control bar, bolts: chromed/galvanised steel; a bright white reflection in the video")
BLACK = model.surface("Plastic", "#2C2D32", "matte", "Fuel cap, starter rope handle, knobs, bushings: black plastic; flat dark in the video")
STEEL = model.surface("Metal", "#2A2B2F", "satin", "Handle tubes, wheel plates, hinge: black powder-coated steel; the handles are flat dark without shine in the video")
FOAM = model.surface("Rubber", "#3A3B40", "matte", "Grip foam and primer bulb: foam/rubber (a guess; off screen)")
CABLE = model.surface("Rubber", "#232327", "matte", "Control cable sheath: black PVC")


def mirror(v, side):
    return V(v.x * side, v.y, v.z)


def plate_x(bm, x0, x1, y_mid, half_y, z_back, z_front, radius, material):
    """A flat rounded-corner plate perpendicular to X (wheel plate, tab)."""
    outline = om.rounded_rect(half_y, z_back, z_front, radius, 4, center_x=y_mid)
    om.loft(bm, [[V(x0, a, b) for a, b in outline], [V(x1, a, b) for a, b in outline]], material=material)


def offset_rect(half_x, z_back, z_front, radius, d, steps=6):
    return om.rounded_rect(half_x - d, z_back + d, z_front - d, max(radius - d, 0.006), steps)


# ==============================================================================================================
# Housing
# ==============================================================================================================

def deck_outline():
    """Outline of the deck from above: front a half circle, straight sides, rounded rear corners (dense polygon)."""
    pts = []
    for k in range(61):
        a = math.radians(180.0 * k / 60)
        pts.append((0.285 * math.cos(a), 0.06 + 0.285 * math.sin(a)))
    pts.append((-0.285, -0.15))
    for k in range(1, 16):
        a = math.radians(180.0 + 90.0 * k / 15)
        pts.append((-0.215 + 0.07 * math.cos(a), -0.15 + 0.07 * math.sin(a)))
    for k in range(0, 16):
        a = math.radians(270.0 + 90.0 * k / 15)
        pts.append((0.215 + 0.07 * math.cos(a), -0.15 + 0.07 * math.sin(a)))
    return pts


def polar_radii(outline, center, samples):
    """Radii where rays at equal angles from the centre cross the outline (the deck is star-shaped)."""
    cx, cz = center
    radii = []
    n = len(outline)
    for j in range(samples):
        t = 2.0 * math.pi * j / samples
        dx, dz = math.cos(t), math.sin(t)
        best = None
        for i in range(n):
            (x1, z1), (x2, z2) = outline[i], outline[(i + 1) % n]
            ex, ez = x2 - x1, z2 - z1
            det = dx * (-ez) - dz * (-ex)
            if abs(det) < 1e-12:
                continue
            ox, oz = x1 - cx, z1 - cz
            r = (ox * (-ez) - oz * (-ex)) / det
            u = (dx * oz - dz * ox) / det
            if r > 0 and -1e-9 <= u <= 1 + 1e-9:
                best = r if best is None else min(best, r)
        radii.append(best)
    return radii


HOUSING_FRONT, HOUSING_TILT = -0.185, 0.16


def housing_lift(z):
    """The top of the rear body rises towards the back (+2 cm at the back): more of the rear face shows, less of the roof."""
    return max(0.0, HOUSING_FRONT - z) * HOUSING_TILT


def build_deck():
    bm = bmesh.new()
    center = (0.0, 0.02)
    samples = 96
    radii = polar_radii(deck_outline(), center, samples)
    dirs = [(math.cos(2 * math.pi * j / samples), math.sin(2 * math.pi * j / samples)) for j in range(samples)]

    def ring(radius_of, y):
        return [V(center[0] + d[0] * radius_of(j), y, center[1] + d[1] * radius_of(j)) for j, d in enumerate(dirs)]

    # Skirt -> shoulder -> flat top -> dome skirt -> dome ridge -> inner groove -> engine collar
    top = [r - 0.030 for r in radii]
    dome_foot = [min(0.222, t - 0.012) for t in top]
    dome_rim = [min(0.208, f - 0.010) for f in dome_foot]
    dome_in = [min(0.192, f - 0.010) for f in dome_rim]
    rings = [
        ring(lambda j: radii[j] + 0.004, 0.040),
        ring(lambda j: radii[j], 0.060),
        ring(lambda j: radii[j] - 0.002, 0.125),
        ring(lambda j: radii[j] - 0.012, 0.150),
        ring(lambda j: top[j], 0.162),
        ring(lambda j: dome_foot[j], 0.166),
        ring(lambda j: dome_rim[j], 0.186),
        ring(lambda j: dome_in[j], 0.192),
        ring(lambda j: 0.152, 0.196),
        ring(lambda j: 0.147, 0.200),
        ring(lambda j: 0.143, 0.214),
        ring(lambda j: 0.132, 0.220),
    ]
    om.loft(bm, rings, material=0)

    # Rear body: a wide, stepped box behind the deck (lower lip, middle step, round top)
    hx, zb, zf, rr = 0.235, -0.31, -0.185, 0.04
    profile = [(-0.006, 0.045), (-0.006, 0.075), (0.0, 0.079), (0.0, 0.100), (-0.005, 0.104), (-0.005, 0.112),
               (0.001, 0.117), (0.004, 0.178), (0.012, 0.194), (0.026, 0.200)]
    rings = []
    for d, y in profile:
        lift = 1.0 if y >= 0.178 else 0.0   # the top wall and roof rise towards the back
        rings.append([V(x, y + lift * housing_lift(z), z) for x, z in offset_rect(hx, zb, zf, rr, d)])
    om.loft(bm, rings, material=0)

    # Rear flap (above the rear discharge opening, hinged at the front; follows the roof's slope) and the hinge pin
    door = om.rounded_rect(0.12, -0.285, -0.205, 0.018, 4)
    door_top = offset_rect(0.12, -0.285, -0.205, 0.018, 0.005, 4)
    om.loft(bm, [[V(x, y + housing_lift(z), z) for x, z in pts]
                 for pts, y in ((door, 0.196), (door, 0.204), (door_top, 0.208))], material=1)
    hinge_y = 0.206 + housing_lift(-0.198)
    om.sweep(bm, [V(-0.132, hinge_y, -0.198), V(0.132, hinge_y, -0.198)], 0.0045, 12, material=2)
    for side in SIDES:
        om.box(bm, (side * 0.10 - 0.012, hinge_y - 0.009, -0.205), (side * 0.10 + 0.012, hinge_y + 0.005, -0.19), material=2)

    for side in SIDES:
        # Front wheel: a plate bolted to the deck skirt, an axle pin, a bushing
        fa = mirror(FRONT_AXLE, side)
        skirt = math.sqrt(0.285 ** 2 - (FRONT_AXLE.z - 0.06) ** 2)
        x_in, x_out = side * (skirt - 0.004), side * (skirt + 0.006)
        plate_x(bm, x_in, x_out, FRONT_AXLE.y + 0.004, 0.032, FRONT_AXLE.z - 0.032, FRONT_AXLE.z + 0.032, 0.012, 2)
        hub_in = side * (FRONT_AXLE.x - FRONT_HUB_IN)
        om.sweep(bm, [V(x_out, fa.y, fa.z), V(hub_in, fa.y, fa.z)], 0.011, 16, material=3)
        # (the pins start 3 mm inside the plate: their end cap lay in the plate's inner face and z-fought)
        om.sweep(bm, [V(x_in + side * 0.003, fa.y, fa.z), V(side * (FRONT_AXLE.x + FRONT_HUB_IN - 0.001), fa.y, fa.z)], 0.006, 12,
                 material=2)

        # Rear wheel: a long plate bolted to the side of the rear body (axle + handle mount + height lever)
        ra = mirror(REAR_AXLE, side)
        x_in, x_out = side * 0.249, side * 0.258
        plate_x(bm, x_in, x_out, 0.165, 0.106, -0.312, -0.168, 0.022, 2)
        hub_in = side * (REAR_AXLE.x - REAR_HUB_IN)
        om.sweep(bm, [V(x_out, ra.y, ra.z), V(hub_in, ra.y, ra.z)], 0.013, 16, material=3)
        om.sweep(bm, [V(x_in + side * 0.003, ra.y, ra.z), V(side * (REAR_AXLE.x + REAR_HUB_IN - 0.001), ra.y, ra.z)], 0.0072, 12,
                 material=2)
        # Height adjustment lever: up and forward from the pivot on the plate, a knob at its end
        pivot = V(side * 0.262, 0.150, -0.262)
        tip = V(side * 0.264, 0.212, -0.205)
        om.sweep(bm, [pivot, tip], 0.0055, 10, material=2)
        om.revolve_at(bm, [(-0.012, 0.0), (-0.012, 0.010), (-0.006, 0.015), (0.008, 0.015), (0.014, 0.008), (0.016, 0.0)],
                      16, tip, (tip - pivot).normalized(), material=3)
    return bm


# ==============================================================================================================
# Motor
# ==============================================================================================================

SHROUD_BACK, SHROUD_FRONT, SHROUD_HALF = -0.135, 0.172, 0.126


def shroud_ring(d, y, steps=6):
    pts = offset_rect(SHROUD_HALF, SHROUD_BACK, SHROUD_FRONT, 0.06, d, steps)
    return om.ring_xz(om.taper_x(pts, SHROUD_BACK, SHROUD_FRONT, 1.0, 0.84), y)


def build_engine():
    # Cover: a rounded box, narrow at the front. At the back hollows on both sides of the ridge (fuel cap, primer bulb) and an opening
    # underneath (the starter shows); carving applies only to the cover's own shell
    shroud = bmesh.new()
    om.loft(shroud, [shroud_ring(-0.002, 0.180), shroud_ring(0.0, 0.232), shroud_ring(0.008, 0.330), shroud_ring(0.020, 0.365),
                     shroud_ring(0.036, 0.385), shroud_ring(0.056, 0.395)], material=0)
    cutters = []
    for side in SIDES:
        c = bmesh.new()
        lo, hi = sorted((side * 0.022, side * 0.104))
        om.box(c, (lo, 0.335, -0.25), (hi, 0.45, -0.035), material=6)   # the inside of the hollow one tone darker
        cutters.append(c)
    c = bmesh.new()
    om.box(c, (-0.095, 0.17, -0.25), (0.095, 0.296, -0.062), material=0)
    cutters.append(c)
    bm = om.carve(shroud, cutters)

    # Air grille (wide, ribbed, in the front half)
    grille_bm = bmesh.new()
    grille = om.rounded_rect(0.062, 0.0, 0.125, 0.02, 5)
    om.loft(grille_bm, [om.ring_xz(grille, 0.384), om.ring_xz(grille, 0.410),
                        om.ring_xz(om.rounded_rect(0.058, 0.004, 0.121, 0.017, 5), 0.413)], material=0)
    grooves = []
    for z in (0.022, 0.048, 0.074, 0.100):
        c = bmesh.new()
        om.box(c, (-0.054, 0.401, z - 0.006), (0.054, 0.43, z + 0.006), material=3)   # dark slot
        grooves.append(c)
    om.merge(bm, om.carve(grille_bm, grooves))

    # A ridge from the middle to the back and a vertical ridge on the rear face down to the lip. Both are 1.5 mm wider than the gap
    # between the hollows (their sides used to lie in the hollow walls' plane), the ridge's foot sits deeper than the grille's and
    # the rear bar's top 2 mm under the ridge's (z-fighting gate, 21 October 2026)
    om.loft(bm, [om.ring_xz(om.rounded_rect(0.0235, -0.118, 0.04, 0.008, 3), y) for y in (0.380, 0.404)], material=0)
    rear_bar = om.rounded_rect(0.0235, -0.140, -0.110, 0.006, 3)
    om.loft(bm, [om.ring_xz(rear_bar, 0.300), om.ring_xz(rear_bar, 0.402)], material=0)

    # A flange sitting on the block and the deck collar (under the cover; visible through the opening at the back)
    flange = om.rounded_rect(0.105, -0.120, 0.145, 0.035, 5)
    om.loft(bm, [om.ring_xz(flange, 0.214), om.ring_xz(flange, 0.226)], material=1)
    block = om.rounded_rect(0.090, -0.195, 0.130, 0.030, 5)   # carries the starter at the back
    om.loft(bm, [om.ring_xz(block, 0.226), om.ring_xz(block, 0.238)], material=1)

    # Starter: a horizontal silver cover on top of the block, its back half sticking out from under the cover; the rope handle leans on its edge
    starter_z = -0.125
    om.revolve_at(bm, [(0.0, 0.0), (0.0, 0.063), (0.026, 0.067), (0.036, 0.061), (0.042, 0.040), (0.044, 0.0)],
                  48, V(0.0, 0.238, starter_z), V(0.0, 1.0, 0.0), material=2)
    grip_path = [V(0.046 * math.cos(math.radians(a)), 0.286, starter_z + 0.046 * math.sin(math.radians(a)))
                 for a in range(222, 319, 8)]
    om.sweep(bm, grip_path, 0.0078, 12, material=3)
    # The dark hub in the middle of the starter cover (the dark circle inside the silver in the video)
    om.revolve_at(bm, [(0.0, 0.0), (0.0, 0.021), (0.004, 0.021), (0.007, 0.013), (0.008, 0.0)], 24,
                  V(0.0, 0.279, starter_z), V(0.0, 1.0, 0.0), material=3)
    # The brake tab the control cable attaches to (right rear of the block)
    om.box(bm, (0.078, 0.226, -0.100), (0.095, 0.250, -0.074), material=5)   # 5 mm proud of the block's side (in its plane it z-fought)

    # Fuel cap (left hollow, knurled) and primer bulb (right hollow)
    fuel = V(-0.063, 0.335, -0.085)
    lobes = []
    for k in range(48):
        t = 2.0 * math.pi * k / 48
        r = 0.034 if (k // 2) % 2 == 0 else 0.031
        lobes.append((fuel.x + r * math.cos(t), fuel.z + r * math.sin(t)))
    om.loft(bm, [om.ring_xz(lobes, 0.334), om.ring_xz(lobes, 0.352),
                 om.ring_xz([(fuel.x + (x - fuel.x) * 0.82, fuel.z + (z - fuel.z) * 0.82) for x, z in lobes], 0.357)], material=3)
    om.revolve_at(bm, [(0.0, 0.0), (0.0, 0.019), (0.005, 0.019), (0.006, 0.013), (0.014, 0.012), (0.020, 0.006), (0.022, 0.0)],
                  24, V(0.063, 0.334, -0.08), V(0.0, 1.0, 0.0), material=4)
    return bm


# ==============================================================================================================
# Handle
# ==============================================================================================================

TUBE_R = 0.0125
MOUNT = V(0.2705, 0.255, -0.285)   # above and behind the wheel: the bolt and knob do not touch the wheel


def handle_frame():
    corner = V(0.375, 0.885, -1.035)
    u = (GRIP - MOUNT).normalized()
    length = (GRIP - MOUNT).length
    fold = MOUNT + u * (length * 0.45)
    up_start = fold - u * 0.075 + V(0.025, 0.0, 0.0)
    return u, fold, up_start, corner


def under(u):
    """Direction of the tube's underside (the cable runs here)."""
    down = V(0.0, -1.0, 0.0)
    return (down - u * down.dot(u)).normalized()


def build_handle():
    bm = bmesh.new()
    u, fold, up_start, corner = handle_frame()
    for side in SIDES:
        # Lower tube: from 2 cm below the bolt on the plate to the fold
        om.sweep(bm, [mirror(MOUNT - u * 0.02, side), mirror(fold + u * 0.03, side)], TUBE_R, 16, material=0)
        # Handle bolt and its outer knob (the black joint in the video)
        om.revolve_at(bm, [(0.0, 0.0), (0.0, 0.019), (0.004, 0.021), (0.012, 0.020), (0.016, 0.012), (0.017, 0.0)],
                      20, mirror(V(MOUNT.x + TUBE_R, MOUNT.y, MOUNT.z), side), V(side, 0.0, 0.0), material=2)
        # Fold: a bolt and a wing nut joining the two tubes side by side
        bolt = fold - u * 0.035
        om.sweep(bm, [mirror(bolt - V(0.014, 0, 0), side), mirror(bolt + V(0.055, 0, 0), side)], 0.004, 8, material=3)
        om.revolve_at(bm, [(0.0, 0.0), (0.0, 0.016), (0.006, 0.018), (0.014, 0.012), (0.016, 0.0)], 20,
                      mirror(bolt + V(0.025 + TUBE_R, 0, 0), side), V(side, 0.0, 0.0), material=2)
        wing = []
        for k in range(32):
            t = 2.0 * math.pi * k / 32
            r = 0.030 if math.cos(2 * t) > 0.55 else 0.014
            wing.append(V(0.0, r * math.sin(t), r * math.cos(t)))
        base = mirror(bolt + V(0.025 + TUBE_R + 0.004, 0, 0), side)
        om.loft(bm, [[base + p for p in wing], [base + V(side * 0.008, 0, 0) + p for p in wing]], material=2)

    # Upper U tube (a single bent tube): left fold -> left corner -> grab bar -> right corner -> right fold
    left = [mirror(up_start, -1), mirror(corner, -1)]
    right = [corner, up_start]
    path = om.fillet(left + right, 0.04, 8)
    om.sweep(bm, path, TUBE_R, 16, material=0)
    # Foam grip
    om.sweep(bm, om.fillet([V(-0.33, corner.y, corner.z), V(0.33, corner.y, corner.z)], 0.0, 1), 0.0185, 18, material=1)

    # Control bar: a U bar hinged to the upper tubes, resting against the bar when held
    leg_dir = (corner - up_start).normalized()
    pivot = up_start + leg_dir * ((0.80 - up_start.y) / leg_dir.y) + V(0.0, 0.0, 0.016)
    bail = [mirror(pivot, -1), V(-0.35, 0.862, -0.992), V(0.35, 0.862, -0.992), pivot]
    om.sweep(bm, om.fillet(bail, 0.03, 6), 0.0045, 10, material=3)
    for side in SIDES:
        om.revolve_at(bm, [(-0.006, 0.0), (-0.006, 0.008), (0.006, 0.008), (0.006, 0.0)], 12,
                      mirror(pivot, side), V(1.0, 0.0, 0.0), material=2)
    # The tab at the bar's right end: the cable comes out here
    arm_end = pivot + V(-0.012, -0.034, 0.022)
    om.sweep(bm, [pivot, arm_end], 0.004, 8, material=3)

    # Control cable: from the tab down under the right tube with clips, over the rear body to the brake tab
    lower_u = u
    lower_under = under(lower_u)
    upper_under = under(leg_dir)
    off = TUBE_R + 0.0034
    points = [arm_end, arm_end + V(-0.006, -0.03, 0.02)]
    for t in (0.72, 0.5, 0.28, 0.08):
        points.append(up_start + leg_dir * ((corner - up_start).length * t) + upper_under * off)
    for t in (0.9, 0.62, 0.36, 0.2):
        points.append(MOUNT + lower_u * ((fold - MOUNT).length * t) + lower_under * off)
    # It leaves the tube above the plate and goes over the rear body and the rear flap to the brake tab right of the starter
    # It leaves the tube above the plate; runs clipped along the right top edge of the rear body, comes down onto the deck at the front edge
    # (second clip), enters the opening at the back of the engine cover from the dome skirt and connects to the brake tab.
    # Every point is 0-3 mm above the surface; it passes through no part.
    points += [V(0.236, 0.25, -0.318), V(0.216, 0.222, -0.292), V(0.206, 0.2136, -0.25), V(0.196, 0.2075, -0.212),
               V(0.175, 0.19, -0.176), V(0.15, 0.1725, -0.172), V(0.12, 0.19, -0.152), V(0.093, 0.206, -0.138),
               V(0.087, 0.222, -0.114), V(0.083, 0.234, -0.09)]
    om.sweep(bm, om.spline(points, 8), 0.0032, 8, material=4)
    # Measured at finish: the cable leaves the bar's tab, passes both body clips and ends in the brake tab
    model.route("ControlCable", [points[0], V(0.206, 0.2136, -0.25), V(0.15, 0.1725, -0.172), points[-1]], tol=0.007,
                unity=True, part="Handle", ends=("Handle", "Motor"))
    # The clips holding the cable to the rear body and the deck
    om.box(bm, (0.199, 0.2104, -0.256), (0.213, 0.219, -0.244), material=2)
    om.box(bm, (0.143, 0.1665, -0.178), (0.157, 0.1775, -0.166), material=2)
    # Clips (tube + cable)
    for t in (0.5, 0.18):
        center = up_start + leg_dir * ((corner - up_start).length * t) + upper_under * 0.004
        om.sweep(bm, [center - leg_dir * 0.006, center + leg_dir * 0.006], 0.0215, 16, material=2)
    center = MOUNT + lower_u * ((fold - MOUNT).length * 0.5) + lower_under * 0.004
    om.sweep(bm, [center - lower_u * 0.006, center + lower_u * 0.006], 0.0215, 16, material=2)
    return bm


# ==============================================================================================================

model.part("Housing", build_deck(), [RED, RED_DARK, STEEL, BLACK], unity=True,
           bevel={"width": 0.0025, "segments": 1, "angle": 30.0}, weighted=False)   # soft shell: plain smoothing

model.part("Motor", build_engine(), [SHROUD, BLOCK, SILVER, BLACK, FOAM, STEEL, SHROUD_DARK], unity=True,
           bevel={"width": 0.002, "segments": 1, "angle": 30.0})
model.part("Handle", build_handle(), [STEEL, FOAM, BLACK, SILVER, CABLE], unity=True,
           bevel={"width": 0.0015, "segments": 1, "angle": 40.0})

for side, label in ((1.0, "Right"), (-1.0, "Left")):
    model.anchor(f"Handle_{label}", mirror(GRIP, side))
    model.anchor(f"Axle_Front_{label}", mirror(FRONT_AXLE, side))
    model.anchor(f"Axle_Rear_{label}", mirror(REAR_AXLE, side))
# What holds the mower from outside: the wheels (wheel.py) on the four axle pins, the hands on the grips
model.support("wheels", [mirror(a, s) for a in (FRONT_AXLE, REAR_AXLE) for s in SIDES], tol=0.02, unity=True,
              component="Axles")
model.support("hands", [mirror(GRIP, s) for s in SIDES], tol=0.03, unity=True, component="Foam")

# Show the wheels in the views too (render only; not exported)
bpy.ops.import_scene.fbx(filepath=os.path.join(om.FBX_DIR, "wheel.fbx"))
imported = {o.name: o for o in bpy.context.selected_objects}
for part, axle in (("RearWheel", REAR_AXLE), ("FrontWheel", FRONT_AXLE)):
    source = imported[part]
    for side in SIDES:
        wheel = source.copy()
        bpy.context.scene.collection.objects.link(wheel)
        p = mirror(axle, side)
        wheel.location = (-p.x, -p.z, p.y)
        wheel.rotation_euler = (0.0, 0.0, 0.0 if side > 0 else math.pi)
    bpy.data.objects.remove(source)


def unity_dir(x, y, z):
    return (-x, -z, y)


everything = ["Housing", "Motor", "Handle"]
model.finish(
    budget=30000,
    total_budget=30000,   # Housing + Motor + Handle together
    views=[
        {"file": "player", "label": "From the player's side (from behind and above)", "objects": ["Housing", "Motor"],
         "direction": unity_dir(0.0, 0.815, -0.578), "zoom": 1.05, "ground": 0.0},
        {"file": "motor", "label": "Engine cover up close", "objects": ["Motor"], "direction": unity_dir(0.12, 0.75, -0.65),
         "target": unity_dir(0.0, 0.31, -0.04), "radius": 0.2, "ground": 0.0},
        {"file": "three_quarter", "label": "Rear-right 3/4 (handle and cable)", "objects": everything,
         "direction": unity_dir(0.85, 0.55, -0.75), "ground": 0.0},
        {"file": "cable", "label": "Right handle base: plate, axle, cable", "objects": everything,
         "direction": unity_dir(0.9, 0.55, -0.55), "target": unity_dir(0.22, 0.24, -0.28), "radius": 0.2, "ground": 0.0},
        {"file": "side", "label": "From the right (handle, grip at 0.88 m)", "objects": everything, "direction": unity_dir(1.0, 0.0, 0.0), "ground": 0.0,
         "ortho": True},
        {"file": "handle_top", "label": "Top of the handle: foam, control bar, cable exit", "objects": everything,
         "direction": unity_dir(0.45, 0.55, 0.7), "target": unity_dir(0.05, 0.84, -0.99), "radius": 0.42, "ground": 0.0},
        {"file": "front", "label": "Front 3/4 (not visible in game, a guess)", "objects": ["Housing", "Motor"],
         "direction": unity_dir(-0.8, 0.55, 0.9), "ground": 0.0},
    ],
    references=[
        {"label": "Reference: video 0:46", "path": "docs/reference/22_mower_close.png", "crop": [300, 248, 260, 230]},
        {"label": "Reference: engine top, video 1:12", "path": "docs/reference/23_mower_engine_top.png", "crop": [325, 290, 200, 150]},
    ],
)
