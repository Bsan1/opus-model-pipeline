"""
Battery string trimmer (textured pipeline): Shaft (unit length, stretched to the hands in game), Motor (the body and battery in
the hands), DHandle, Head (gearbox, puck, guard, spool) and the line (Line: the spinning cross string, LineTips: short tips at
rest). Every part moves on its own in game, so each stays a separate object; they share one atlas.

Reference: video 0:07-0:10, 0:50-0:52 (docs/reference/26 at 0:07, 25 at 0:50). First person: the body bottom right, the head in
front on the ground. Read from the 0:07 frame zoomed in (21 October 2026):
- the body: a red upper shell with a plain raised ridge on top, a big light grey lower shell, a big framed black battery block
  at the back with a dark hollow and a red latch inside, a thin white label line on the red side;
- the D handle: a thick black arch standing across the shaft just in front of the body, wider (about 17 cm) than tall
  (about 12 cm above the shaft), its flat lower bar clamped on the shaft;
- the head: a flat black puck (about 21 cm wide, half as tall) with a small dark gearbox knob on top ringed in orange-red;
  no wide guard shows, so the guard is a narrow lip at the back.
The earlier model had four dark button squares on top, an O-ring handle and a wide flat guard: none of them is in the video.
A guess: the trigger, the vent and latch details, the spool and bump knob under the head (not visible).

Mechanical logic: the component plan (model.plan below).

Surfaces: moulded plastics with a faint tone variation and a fine grain in the bump, the shaft painted aluminium; all baked into
the atlas (base colour, normal, AO per part, roughness).

Unity axes (TrimmerModel root): the origin is the front end of the shaft, +Z towards the head, the shaft extends to -Z. Motor and
DHandle have their own origins relative to the shaft (shifted along the shaft length in game); the Head's frame is aligned to
world up. Anchors (spec file, checked against TrimmerModel): BodyFront, BatteryBack, HandleTop, HeadCenter, Spool.
"""
import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import bmesh  # noqa: E402

import opus_model as om  # noqa: E402
from opus_model import V  # noqa: E402

model = om.Model("trimmer", __file__)
model.plan(
    "battery string trimmer: held in both hands, the spinning line cuts grass along edges",
    [("video", "0:07-0:10, 0:50-0:52, first person")],
    [   # name, role, job, attached to, moves, seen/guess/real
        ("Motor", "functional", "body with the motor, in the rear hand", ["Shaft", "hands"], "fixed", "seen"),
        ("Battery", "functional", "powers the motor; slides into the body's back, red latch", ["Motor"], "fixed", "seen"),
        ("Trigger", "functional", "switches the motor, under the body", ["Motor", "hands"], "hinge", "guess"),
        ("Shaft", "structural", "carries the head; the drive runs inside it", ["Motor"], "fixed", "seen"),
        ("DHandle", "functional", "the front hand's grip, clamped on the shaft", ["Shaft", "hands"], "fixed", "seen"),
        ("Gearbox", "functional", "turns the drive down to the spool; knob ringed in orange", ["Shaft"], "fixed", "seen"),
        ("Head", "functional", "flat puck carrying the spool", ["Gearbox"], "spin", "seen"),
        ("Guard", "functional", "narrow lip at the back, keeps cuttings off the user", ["Gearbox"], "fixed", "seen"),
        ("Spool", "functional", "holds the line, bump knob underneath", ["Head"], "spin", "guess"),
        ("Line", "functional", "cuts the grass; out of the spool's two holes", ["Spool"], "spin", "seen"),
    ],
    supports=("hands",), tier="complex", category="machines")
model.features([   # id, tier, components, what must hold, measured by, view
    ("head_drive", "critical", ["Shaft", "Gearbox", "Head", "Spool", "Line"],
     "the shaft enters the gearbox, the head carries the spool and the line leaves its two holes", None, "head"),
    ("two_hands", "critical", ["Motor", "DHandle", "Shaft"],
     "the rear hand on the body, the front hand on the D handle clamped across the shaft", None, "handle"),
    ("battery", "important", ["Battery", "Motor"], "the battery sits in the body's back with its latch", None, "back"),
])


def plastic(name, rgb, finish, note, **look):
    """Moulded surface: the colour from the video with a faint tone variation, a fine grain in the bump (Model.moulded_surface)."""
    return model.moulded_surface(name, rgb, finish, note, **look)


RED = plastic("red", (194, 59, 44), "glossy", "Upper shell of the body and its ridge: red glossy ABS; light streaks along the "
              "edges in the video", rough=0.28, grain=0.03)
BATTERY = plastic("battery", (28, 29, 32), "satin", "Battery: black plastic case; its edges catch the light in the video",
                  rough=0.5, grain=0.05)
WHITE = plastic("white", (217, 214, 207), "satin", "Lower shell of the body: light grey-white plastic; the lower half of the "
                "body from end to end in the video", rough=0.45, grain=0.03)
LABEL = plastic("label", (238, 234, 226), "matte", "Side lettering strip: white print; a thin white line on the red side in "
                "the video", rough=0.7, tone=0.0)
BLACK = plastic("black", (31, 32, 35), "matte", "D handle, head puck, guard, clamps: black textured plastic; flat dark in the "
                "video", rough=0.82, grain=0.12)
KEYS = plastic("rubber", (42, 42, 46), "matte", "Trigger: dark rubber (under the body, a guess)", rough=0.9, grain=0.08)
SHAFT = plastic("shaft", (43, 44, 48), "satin", "Shaft: black painted aluminium tube; a thick dark rod in the video",
                rough=0.45, tone=0.02)
ORANGE = plastic("orange", (214, 92, 52), "satin", "Ring on the gearbox knob and the bump knob: orange-red plastic; a reddish "
                 "ring on the knob on top of the head in the video", rough=0.5, grain=0.04)
LINE = plastic("line", (201, 205, 176), "matte", "Line: nylon (a guess; not distinguishable in the video)", rough=0.6, tone=0.0)
RECESS = plastic("recess", (21, 21, 23), "matte", "The hollow in the battery's back face: darker inside the frame in the video",
                 rough=0.85, tone=0.0)
LATCH = plastic("latch", (184, 51, 42), "satin", "Battery latch: red; a red part on the right inside the hollow in the video",
                rough=0.4, tone=0.0)

SHAFT_R = 0.0145
SPOOL_Y = -0.132
HEAD_CENTER = V(0.0, -0.088, 0.0)
BODY_FRONT = V(0.0, 0.0, 0.0)
BATTERY_BACK = V(0.0, 0.016, -0.432)


def ring_xy(half_w, bottom, top, radius, z, steps=5):
    return [V(x, y, z) for x, y in om.rounded_rect(half_w, bottom, top, radius, steps)]


# ----------------------------------------------------------------------------------------------------------------
# Shaft (unit length: 0 -> -1 m)
def build_shaft():
    bm = bmesh.new()
    om.revolve_at(bm, [(0.0, 0.0), (0.0, SHAFT_R), (1.0, SHAFT_R), (1.0, 0.0)], 20, V(0, 0, 0), V(0, 0, -1), material=0)
    return bm


# ----------------------------------------------------------------------------------------------------------------
# Motor (as in the video): a round capsule body; the upper half a glossy red shell, the lower half a light grey-white shell from
# end to end; a red neck going down to the shaft in front; a plain raised ridge on top; a black battery recessed into the upper
# back, flush with the body, with a framed hollow and a red latch on its back face
BODY = [(-0.004, 0.022, -0.024, 0.024, 0.021), (-0.03, 0.036, -0.04, 0.04, 0.034),
        (-0.07, 0.06, -0.066, 0.066, 0.052), (-0.12, 0.075, -0.078, 0.082, 0.064),
        (-0.40, 0.076, -0.08, 0.084, 0.066), (-0.42, 0.072, -0.075, 0.08, 0.06), (-0.426, 0.064, -0.067, 0.072, 0.052)]
SPLIT_Y = 0.004          # the line where the red and white shells meet
BATTERY_FRONT = -0.262   # front edge of the battery

# Material slots of the motor
M_RED, M_BATTERY, M_WHITE, M_LABEL, M_BLACK, M_KEYS, M_RECESS, M_LATCH = range(8)


def body_rings(grow):
    """The body's rings grown by `grow` all round, the front cap too (two shells must not share the front plane: z-fighting)."""
    rings = [ring_xy(hw + grow, bottom - grow, top + grow, r + grow, z) for z, hw, bottom, top, r in BODY]
    rings[0] = [p + V(0.0, 0.0, grow) for p in rings[0]]
    return rings


def build_motor():
    # Lower shell (white): along the whole body, below the split line (cut above it; otherwise it would show through the battery's hollow)
    white = bmesh.new()
    om.loft(white, body_rings(0.0), material=M_WHITE)
    above = bmesh.new()
    om.box(above, (-0.2, SPLIT_Y + 0.002, 0.05), (0.2, 0.2, -0.5), material=M_WHITE)
    behind = bmesh.new()   # the space the battery takes at the back (the battery comes down there)
    om.box(behind, (-0.2, -0.058, -0.355), (0.2, 0.2, -0.5), material=M_WHITE)
    bm = om.carve(white, [above, behind])

    # Upper shell (red): a slightly wider shell, the part below the split line and the battery bay carved out
    red = bmesh.new()
    om.loft(red, body_rings(0.0015), material=M_RED)
    below = bmesh.new()
    om.box(below, (-0.2, -0.2, 0.05), (0.2, SPLIT_Y, -0.5), material=M_RED)
    slot = bmesh.new()
    om.box(slot, (-0.2, SPLIT_Y - 0.001, BATTERY_FRONT), (0.2, 0.2, -0.5), material=M_RED)
    om.merge(bm, om.carve(red, [below, slot]))

    # Battery: a black case sitting in the bay, its front edge round; it comes down at the back (in the video almost the whole back face is
    # black), a big frame and a hollow on its back face, a red latch on the right inside it
    battery = bmesh.new()
    rings = []
    for z, grow, top, bottom in ((BATTERY_FRONT, -0.006, 0.08, SPLIT_Y), (BATTERY_FRONT - 0.008, 0.0, 0.088, SPLIT_Y),
                                 (-0.33, 0.0, 0.088, SPLIT_Y), (-0.365, 0.0, 0.088, -0.05), (-0.415, 0.0, 0.088, -0.056),
                                 (-0.428, -0.004, 0.083, -0.052), (-0.432, -0.012, 0.075, -0.044)):
        rings.append(ring_xy(0.077 + grow, bottom, top, 0.036 + grow * 0.5, z))
    om.loft(battery, rings, material=M_BATTERY)
    recess = bmesh.new()
    om.loft(recess, [ring_xy(0.056, -0.034, 0.07, 0.02, z) for z in (-0.418, -0.45)], material=M_RECESS)
    om.merge(bm, om.carve(battery, [recess]))
    om.box(bm, (0.03, 0.0, -0.424), (0.046, 0.04, -0.416), material=M_LATCH)        # latch (inside the hollow, on the right)

    # Top ridge: a plain raised strip of the red shell (the video shows no buttons on top)
    om.loft(bm, [ring_xy(0.04, 0.078, 0.091, 0.012, z) for z in (-0.12, -0.245)], material=M_RED)

    # The white lettering strip on the front side (on both sides)
    for side in (-1.0, 1.0):
        lo, hi = sorted((side * 0.0745, side * 0.0775))
        om.box(bm, (lo, 0.03, -0.17), (hi, 0.035, -0.09), material=M_LABEL)

    # Trigger: under the white shell, at the front (the fingers of the holding hand)
    trigger = om.spline([V(0, -0.07, -0.108), V(0, -0.083, -0.118), V(0, -0.086, -0.135), V(0, -0.074, -0.148)], 5)
    om.sweep(bm, trigger, 1.0, material=M_KEYS, shape=om.rounded_profile(0.011, 0.007, 0.005, 3), up=(1, 0, 0))
    # Shaft clamp: in front of the red neck, the shaft enters here
    om.revolve_at(bm, [(0.0, 0.0), (0.0, 0.02), (0.005, 0.023), (0.026, 0.023), (0.03, 0.02), (0.03, 0.0)], 20,
                  V(0, 0, 0.022), V(0, 0, -1), material=M_BLACK)
    return bm


# ----------------------------------------------------------------------------------------------------------------
# D handle: a thick arch standing across the shaft, its flat lower bar on the clamp
HANDLE_HALF_W, HANDLE_BASE, HANDLE_RISE, HANDLE_TUBE = 0.085, 0.05, 0.105, 0.016
HANDLE_TOP = V(0.0, HANDLE_BASE + HANDLE_RISE, 0.0)


def build_handle():
    bm = bmesh.new()
    loop = []
    for k in range(48):
        t = 2.0 * math.pi * k / 48
        c, s = math.cos(t), math.sin(t)
        if s >= 0.0:      # the arch: half an ellipse
            loop.append(V(HANDLE_HALF_W * c, HANDLE_BASE + HANDLE_RISE * s, 0.0))
        else:             # the lower bar: flat with rounded corners (a superellipse)
            loop.append(V(HANDLE_HALF_W * math.copysign(abs(c) ** (1 / 3), c),
                          HANDLE_BASE - 0.012 * abs(s) ** (1 / 3), 0.0))
    om.sweep(bm, loop, HANDLE_TUBE, sides=16, material=0, closed=True, up=(0, 0, 1))
    # Clamp: a collar around the shaft, a block joining the lower bar, a tightening knob on the side
    om.revolve_at(bm, [(-0.026, 0.0), (-0.026, 0.023), (-0.02, 0.026), (0.02, 0.026), (0.026, 0.023), (0.026, 0.0)], 20,
                  V(0, 0, 0), V(0, 0, 1), material=0)
    om.loft(bm, [ring_xy(0.02, 0.012, HANDLE_BASE - 0.004, 0.006, z) for z in (-0.02, 0.02)], material=0)
    om.revolve_at(bm, [(0.0, 0.0), (0.0, 0.014), (0.004, 0.016), (0.014, 0.012), (0.016, 0.0)], 16, V(0.024, 0.0, 0.0),
                  V(1, 0, 0), material=0)
    return bm


# ----------------------------------------------------------------------------------------------------------------
# Head (frame aligned to world up; origin at the shaft's end): a flat puck under a small gearbox knob
def build_head():
    bm = bmesh.new()
    # Gearbox knob: down from the end of the shaft (material 0 black)
    om.revolve_at(bm, [(0.025, 0.0), (0.025, 0.02), (0.0, 0.026), (-0.034, 0.03), (-0.05, 0.034), (-0.05, 0.0)], 24,
                  V(0, 0, 0), V(0, 1, 0), material=0)
    # Orange-red ring around the knob
    om.revolve_at(bm, [(-0.012, 0.0), (-0.012, 0.031), (-0.016, 0.034), (-0.026, 0.034), (-0.03, 0.031), (-0.03, 0.0)], 32,
                  V(0, 0, 0), V(0, 1, 0), material=1)
    # Puck: a flat top with a round shoulder, nearly straight sides, a rolled lower lip
    om.revolve_at(bm, [(-0.046, 0.0), (-0.046, 0.05), (-0.049, 0.085), (-0.055, 0.1), (-0.064, 0.106), (-0.105, 0.108),
                       (-0.114, 0.104), (-0.118, 0.096), (-0.118, 0.0)], 48, V(0, 0, 0), V(0, 1, 0), material=0)
    # Spool and the orange bump knob
    om.revolve_at(bm, [(-0.117, 0.0), (-0.117, 0.058), (-0.122, 0.06), (-0.144, 0.06), (-0.148, 0.056), (-0.148, 0.0)], 32,
                  V(0, 0, 0), V(0, 1, 0), material=0)
    om.revolve_at(bm, [(-0.147, 0.0), (-0.147, 0.032), (-0.156, 0.03), (-0.164, 0.02), (-0.168, 0.0)], 24,
                  V(0, 0, 0), V(0, 1, 0), material=1)
    # Line holes (rings on both sides of the spool)
    for side in (-1.0, 1.0):
        om.revolve_at(bm, [(-0.004, 0.0), (-0.004, 0.006), (0.004, 0.006), (0.004, 0.0)], 12, V(side * 0.059, SPOOL_Y, 0.0),
                      V(1, 0, 0), material=0)
    # Guard: a narrow lip around the back of the puck (towards the player, -Z), just outside its rim; held by an arm
    inner, outer, y = 0.112, 0.134, -0.1
    arc = [math.pi + math.pi * k / 24 for k in range(25)]
    rings = []
    for t in arc:
        cx, sz = math.cos(t), math.sin(t)
        rings.append([V(cx * inner, y + 0.005, sz * inner), V(cx * outer, y + 0.005, sz * outer),
                      V(cx * (outer + 0.004), y - 0.018, sz * (outer + 0.004)), V(cx * (outer - 0.005), y - 0.018, sz * (outer - 0.005)),
                      V(cx * (outer - 0.005), y - 0.003, sz * (outer - 0.005)), V(cx * inner, y - 0.003, sz * inner)])
    om.loft(bm, rings, material=0)
    om.loft(bm, [ring_xy(0.014, y - 0.007, y + 0.008, 0.004, z) for z in (-0.1, -0.125)], material=0)   # arm into the puck (its faces off the guard's planes)
    return bm


def build_lines(spinning):
    bm = bmesh.new()
    if spinning:
        for axis in (V(1, 0, 0), V(0, 0, 1)):
            om.sweep(bm, [axis * -0.18, axis * 0.18], 0.0015, 6, material=0)
    else:
        for side in (-1.0, 1.0):
            om.sweep(bm, [V(side * 0.058, 0, 0), V(side * 0.12, -0.004, 0.012)], 0.0015, 6, material=0)
    return bm


model.part("Shaft", build_shaft(), [SHAFT], unity=True,
           no_chamfer="a round tube: no hard edge along it, and its two ends sit inside the motor's neck and the gearbox")
model.part("Motor", build_motor(), [RED, BATTERY, WHITE, LABEL, BLACK, KEYS, RECESS, LATCH], unity=True,
           bevel={"width": 0.0018, "segments": 1, "angle": 35.0})
model.part("DHandle", build_handle(), [BLACK], unity=True, bevel={"width": 0.0012, "segments": 1, "angle": 35.0})
model.part("Head", build_head(), [BLACK, ORANGE], unity=True, bevel={"width": 0.0012, "segments": 1, "angle": 35.0})
model.part("Line", build_lines(True), [LINE], unity=True, location=(0.0, SPOOL_Y, 0.0), smooth=False,
           no_chamfer="a 3 mm nylon cord: thinner than the chamfer band allows")
# free: the two tips are apart from each other; each comes out of a spool hole in the Head, another object
model.part("LineTips", build_lines(False), [LINE], unity=True, location=(0.0, SPOOL_Y, 0.0), smooth=False, free=True,
           no_chamfer="a 3 mm nylon cord: thinner than the chamfer band allows")
model.anchor("Spool", V(0.0, SPOOL_Y, 0.0))
model.anchor("BodyFront", BODY_FRONT)
model.anchor("BatteryBack", BATTERY_BACK)
model.anchor("HandleTop", HANDLE_TOP)
model.anchor("HeadCenter", HEAD_CENTER)


def unity_dir(x, y, z):
    return (-x, -z, y)


model.finish_textured(
    size=2048,
    budget=20000,
    total_budget=20000,   # all six parts together
    moving=("Shaft", "Motor", "DHandle", "Head", "Line", "LineTips"),
    islands="smart",
    ao_distance=0.05,
    ao_together=False,
    views=[
        {"file": "motor", "label": "Body: from the player's side (back-right-top)", "objects": ["Motor"], "direction": unity_dir(0.7, 0.55, -0.6)},
        {"file": "engine_side", "label": "Body from the right: label, grey underside, trigger", "objects": ["Motor"], "direction": unity_dir(1.0, 0.1, 0.05),
         "ortho": True},
        {"file": "back", "label": "Battery from behind: frame, latch", "objects": ["Motor"], "direction": unity_dir(0.25, 0.3, -1.0)},
        {"file": "handle", "label": "D handle and clamp", "objects": ["DHandle", "Shaft"], "direction": unity_dir(0.6, 0.35, -0.7),
         "target": unity_dir(0.0, 0.09, 0.0), "radius": 0.16},
        {"file": "head", "label": "Head from the player's side: puck, knob ring, guard lip", "objects": ["Head", "LineTips"],
         "direction": unity_dir(0.35, 0.65, -0.7)},
        {"file": "head_under", "label": "Head from the side, low (a guess): spool, knob, line", "objects": ["Head", "Line"],
         "direction": unity_dir(0.35, 0.12, -0.93)},
    ],
    references=[
        {"label": "Reference: body, video 0:07", "path": "docs/reference/26_trimmer_body.png", "crop": [420, 110, 330, 240]},
        {"label": "Reference: head and D handle, video 0:50", "path": "docs/reference/25_trimmer_head.png", "crop": [200, 80, 420, 260]},
    ],
)
