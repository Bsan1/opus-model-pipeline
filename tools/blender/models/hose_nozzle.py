"""
Pistol-type hose nozzle: Body (head, dial band, neck, yellow body, flow knob, grip, finger grooves,
coupling, hose) and Trigger (turns on the joint under the yellow body; the object position is the joint).

Reference: video 0:11-0:53 (docs/reference/04, 07, 24). Only seen in first person, from behind and above; no hand.
Settled with the user (20 October 2026): no shiny material in the video (all matte); the head is long: a big round green head
flows like a spoon into the yellow body through a long, thick neck; the grip angle is found in game by measuring against the video frame.
Visible: the back face of the head is a wide disc with a thin black knurled dial band at its edge; the neck goes down and back into
a big, round yellow body; on the back face of the yellow body a black knurled flow knob (a light ring, a white dot),
a black stripe on its upper front; the green grip comes down from under the yellow body with black finger grooves in front; behind it a yellow
rear trigger coming down from the yellow body. A guess (off screen): the front face of the head (nozzle holes), the coupling and the hose.

Mechanical logic: the component plan (model.plan below); the trigger's hinge is measured (model.attach).

Textured pipeline (21 October 2026): moulded plastic with a fine grain, the colours sampled from the 0:21 frame (green head
sRGB 33/117/68, yellow body 202/184/91; the game's sky light lifted the old flat colours to 63/136/87 and 231/200/93, so the
bases are darker). The flow knob's ring and dot are now inlays in the knob's face (they had faces in the same plane: z-fighting).

Unity axes: the origin is the centre of the nozzle (where the water comes out), +Z the direction the water comes out, +Y up, +X right.
"""
import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import bmesh  # noqa: E402
from mathutils import Matrix  # noqa: E402

import opus_model as om  # noqa: E402
from opus_model import V  # noqa: E402

model = om.Model("hose_nozzle", __file__)
model.plan(
    "pistol hose nozzle: held in one hand, the palm squeezes the rear trigger and water sprays from the head",
    [("video", "0:11-0:53, first person (refs 04, 07, 24)")],
    [   # name, role, job, attached to, moves, seen/guess/real
        ("Grip", "structural", "held in the palm, finger grooves; the water runs up inside it", ["hands"], "fixed", "seen"),
        ("Coupling", "functional", "joins the hose under the grip", ["Grip"], "fixed", "guess"),
        ("Hose", "functional", "brings the water", ["Coupling"], "flex", "guess"),
        ("YellowBody", "functional", "valve body between the grip and the neck", ["Grip"], "fixed", "seen"),
        ("FlowKnob", "functional", "sets the valve (knurled, light ring and dot)", ["YellowBody"], "spin", "seen"),
        ("Trigger", "functional", "rear trigger: the palm squeezes it towards the grip to open the flow", ["YellowBody", "hands"],
         "hinge", "seen"),
        ("Neck", "structural", "carries the water up to the head", ["YellowBody"], "fixed", "seen"),
        ("Head", "functional", "spray head, nozzle holes in its front", ["Neck"], "fixed", "seen"),
        ("DialBand", "functional", "turns to choose the spray pattern", ["Head"], "spin", "seen"),
        ("Stripe", "decorative", "black stripe on the yellow body, as in the video", ["YellowBody"], "fixed", "seen"),
    ],
    supports=("hands",), tier="complex", category="machines")
model.features([   # id, tier, components, what must hold, measured by, view
    ("trigger_hinge", "critical", ["Trigger", "YellowBody"],
     "the rear trigger turns on its joint under the yellow body and moves towards the grip when squeezed",
     "attach:TriggerHinge", "side"),
    ("palm_grip", "critical", ["Grip", "Trigger"], "the palm closes round the grip with the trigger behind it",
     "support:hands", "side"),
    ("water_path", "important", ["Coupling", "Grip", "YellowBody", "Neck", "Head"],
     "a continuous path hose -> coupling -> grip -> body -> neck -> head, no gap", None, "side"),
])
GREEN = model.moulded_surface("green", (24, 112, 60), "matte", "Head, neck, grip: green plastic; no shine in the video (user: 'no "
                              "shiny material in the video')", rough=0.72, grain=0.08)
YELLOW = model.moulded_surface("yellow", (198, 182, 90), "matte", "Yellow body and rear trigger: mustard-yellow plastic, matte",
                               rough=0.72, grain=0.08)
BLACK = model.moulded_surface("black", (30, 31, 34), "matte", "Dial band, flow knob, stripe, finger grooves: black rubber; flat "
                              "dark in the video", rough=0.88, grain=0.15)
RING = model.moulded_surface("ring", (95, 98, 102), "matte", "The light ring on the knob's face; a grey ring inside the knob in "
                             "the video", rough=0.6, tone=0.0)
MARK = model.moulded_surface("mark", (243, 236, 223), "matte", "Setting mark on the knob: a white dot; a small light dot on the "
                             "knob in the video", rough=0.6, tone=0.0)
HOLES = model.moulded_surface("holes", (20, 21, 24), "matte", "Nozzle holes (a guess; off screen)", rough=0.9, tone=0.0)
METAL = model.moulded_surface("coupling", (169, 173, 179), "satin", "Hose coupling: zinc casting (a guess; off screen)",
                              rough=0.45, metallic=1.0, grain=0.05)
HOSE = model.moulded_surface("hose", (52, 140, 78), "matte", "Hose: green PVC (a guess; off screen)", rough=0.6, grain=0.04)

HEAD_R = 0.05            # radius of the head
HEAD_BACK = -0.034       # back face of the head
BODY_FRONT, BODY_BACK = -0.118, -0.168     # yellow body
KNOB_BACK = -0.192       # back face of the flow knob
GRIP_TOP = V(0.0, -0.035, -0.142)
GRIP_BOTTOM = V(0.0, -0.205, -0.168)
GRIP_HALF = (0.023, 0.02)                  # grip cross-section: half width (x), half thickness
AXIS = (GRIP_BOTTOM - GRIP_TOP).normalized()
FRONT = (V(0, 0, 1) - AXIS * AXIS.z).normalized()   # the front of the grip (fingers)
HINGE = V(0.0, -0.036, BODY_BACK + 0.006)  # joint of the rear trigger: lower back of the yellow body


def grip_point(s, offset):
    """s metres along the grip axis, offset metres forwards."""
    return GRIP_TOP + AXIS * s + FRONT * offset


def knurled(radius, depth, lobes, z0, z1, rings=4, cy=0.0):
    """A thin knurled ring/knob on the Z axis (dense, shallow teeth: must not look like a saw)."""
    ringset = []
    for i in range(rings):
        z = z0 + (z1 - z0) * i / (rings - 1)
        scale = 0.95 if i in (0, rings - 1) else 1.0
        ring = []
        for k in range(lobes * 2):
            t = math.pi * 2.0 * k / (lobes * 2)
            r = (radius if k % 2 == 0 else radius - depth) * scale
            ring.append(V(r * math.cos(t), cy + r * math.sin(t), z))
        ringset.append(ring)
    return ringset


def yellow_ring(z, grow=0.0):
    """Cross-section of the yellow body: rounded corners; its top opens to the neck, its bottom to the grip."""
    return [V(x, y, z) for x, y in om.rounded_rect(0.036 + grow, -0.05 - grow, 0.036 + grow, 0.026 + grow, 6)]


def build_body():
    # Head: nozzles in the flat front face (carved), the back face rounded at the edge
    head = bmesh.new()
    om.revolve_at(head, [(HEAD_BACK, 0.0), (HEAD_BACK, 0.034), (HEAD_BACK + 0.002, HEAD_R - 0.004),
                         (HEAD_BACK + 0.008, HEAD_R), (-0.005, HEAD_R), (-0.001, HEAD_R - 0.004), (0.0, HEAD_R - 0.009),
                         (0.0, 0.0)], 48, V(0, 0, 0), V(0, 0, 1), material=0)
    holes = []
    for ring_r, count in ((0.016, 6), (0.031, 12)):
        for k in range(count):
            a = math.pi * 2.0 * (k + 0.5) / count
            c = bmesh.new()
            om.revolve_at(c, [(-0.004, 0.0), (-0.004, 0.0028), (0.01, 0.0028), (0.01, 0.0)], 10,
                          V(ring_r * math.cos(a), ring_r * math.sin(a), 0.0), V(0, 0, 1), material=5)
            holes.append(c)
    c = bmesh.new()
    om.revolve_at(c, [(-0.004, 0.0), (-0.004, 0.005), (0.01, 0.005), (0.01, 0.0)], 14, V(0, 0, 0), V(0, 0, 1), material=5)
    bmesh.ops.rotate(c, verts=c.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(7.0), 3, "Z"))
    holes.append(c)
    bm = om.carve(head, holes)

    # Dial band: a thin, densely knurled black band at the edge of the head
    om.loft(bm, knurled(HEAD_R + 0.0025, 0.0012, 60, HEAD_BACK + 0.009, -0.006), material=2)

    # Neck: from the lower half of the head's back face to the yellow body; thin and long (the back of the head shows as a flat disc)
    om.revolve_at(bm, [(BODY_FRONT - 0.012, 0.0), (BODY_FRONT - 0.012, 0.027), (BODY_FRONT + 0.012, 0.027),
                       (-0.085, 0.026), (-0.062, 0.025), (-0.046, 0.026), (HEAD_BACK - 0.003, 0.03),
                       (HEAD_BACK + 0.004, 0.031), (HEAD_BACK + 0.004, 0.0)], 40, V(0, -0.012, 0), V(0, 0, 1), material=0)

    # Yellow body: wraps the back end of the neck, opens to the grip below; a black stripe in front
    om.loft(bm, [yellow_ring(BODY_FRONT, -0.004), yellow_ring(BODY_FRONT - 0.006), yellow_ring(BODY_BACK + 0.006),
                 yellow_ring(BODY_BACK, -0.004)], material=1)
    om.loft(bm, [[V(x, y, z) for x, y in om.rounded_rect(0.0375, -0.022, 0.0375, 0.026, 6)]
                 for z in (BODY_FRONT - 0.002, BODY_FRONT - 0.009)], material=2)   # black stripe (its back cap clear of the neck's end cap)

    # Flow knob: on the back face of the yellow body, facing the camera; a grey ring and a white dot on its face
    om.loft(bm, knurled(0.03, 0.0012, 36, KNOB_BACK + 0.004, BODY_BACK + 0.002), material=2)
    om.revolve_at(bm, [(KNOB_BACK, 0.0), (KNOB_BACK, 0.019), (KNOB_BACK + 0.002, 0.025), (KNOB_BACK + 0.006, 0.0)], 36,
                  V(0, 0, 0), V(0, 0, 1), material=2)
    # The grey ring: an annulus inlaid in the knob's face (stands 0.8 mm proud, sinks 0.7 mm in: no face in the knob's plane)
    om.revolve_at(bm, [(KNOB_BACK - 0.0008, 0.0165), (KNOB_BACK - 0.0008, 0.0205), (KNOB_BACK + 0.0007, 0.0205),
                       (KNOB_BACK + 0.0007, 0.0165)], 30, V(0, 0, 0), V(0, 0, 1), material=3)
    # The white dot: a short peg in the face
    om.revolve_at(bm, [(KNOB_BACK - 0.0012, 0.0), (KNOB_BACK - 0.0012, 0.0025), (KNOB_BACK + 0.0007, 0.0025),
                       (KNOB_BACK + 0.0007, 0.0)], 12, V(-0.012, -0.009, 0), V(0, 0, 1), material=4)

    # Grip: down from under the yellow body, curving slightly forwards
    grip_path = om.spline([GRIP_TOP + AXIS * -0.012, grip_point(0.07, 0.003), grip_point(0.13, 0.002), GRIP_BOTTOM], 6)
    om.sweep(bm, grip_path, 1.0, material=0, shape=om.rounded_profile(GRIP_HALF[0], GRIP_HALF[1], 0.013, 4), up=(1, 0, 0))
    # Finger grooves: black rubber strips on the front of the grip
    for k in range(4):
        center = grip_point(0.05 + k * 0.03, GRIP_HALF[1] - 0.003)
        arc = [center + V(0.019 * math.cos(math.radians(a)), 0, 0) + FRONT * (0.005 * math.sin(math.radians(a)))
               for a in range(0, 181, 20)]
        om.sweep(bm, arc, 0.0045, 10, material=2)

    # Coupling and hose
    om.revolve_at(bm, [(0.0, 0.0), (0.0, 0.021), (0.006, 0.023), (0.03, 0.023), (0.036, 0.019), (0.036, 0.0)], 24,
                  GRIP_BOTTOM - AXIS * 0.004, AXIS, material=6)
    start = GRIP_BOTTOM + AXIS * 0.032
    hose = om.spline([start, start + AXIS * 0.06, start + V(0.02, -0.17, -0.07), start + V(0.05, -0.36, -0.24)], 8)
    om.sweep(bm, hose, 0.017, 16, material=7)
    return bm


def build_trigger():
    """Rear trigger: from the joint down along the back of the grip (a palm gap between them). Points relative to the joint."""
    bm = bmesh.new()
    gap = GRIP_HALF[1] + 0.012
    path = [p - HINGE for p in om.spline([HINGE, grip_point(0.045, -gap), grip_point(0.1, -gap - 0.002),
                                           grip_point(0.155, -gap + 0.004)], 6)]
    om.sweep(bm, path, 1.0, material=0, shape=om.rounded_profile(0.03, 0.01, 0.008, 4), up=(1, 0, 0))
    om.revolve_at(bm, [(-0.022, 0.0), (-0.022, 0.006), (0.022, 0.006), (0.022, 0.0)], 14, V(0, 0, 0), V(1, 0, 0), material=1)
    return bm


model.part("Body", build_body(), [GREEN, YELLOW, BLACK, RING, MARK, HOLES, METAL, HOSE], unity=True,
           bevel={"width": 0.0008, "segments": 1, "angle": 35.0})
model.part("Trigger", build_trigger(), [YELLOW, BLACK], unity=True, location=(HINGE.x, HINGE.y, HINGE.z),
           bevel={"width": 0.001, "segments": 1, "angle": 35.0})
model.anchor("Joint", HINGE)
# Measured at finish: the trigger and the body meet at the joint; the palm holds the grip
model.attach("TriggerHinge", HINGE, tol=0.004, unity=True, parts=("Body", "Trigger"), component="Trigger")
model.support("hands", [GRIP_TOP, GRIP_BOTTOM], tol=0.03, unity=True, component="Grip")
model.anchor("Nozzle", V(0, 0, 0))
model.anchor("HeadBack", V(0, 0, HEAD_BACK))
model.anchor("Knob", V(0, 0, KNOB_BACK))
model.anchor("GripUpper", GRIP_TOP)
model.anchor("GripLower", GRIP_BOTTOM)


def unity_dir(x, y, z):
    return (-x, -z, y)


both = ["Body", "Trigger"]
model.finish_textured(
    size=2048,
    budget=24000,
    total_budget=24000,   # the whole model (Body + Trigger) fits the same budget
    moving=tuple(both),
    islands="smart",
    ao_distance=0.03,
    views=[
        {"file": "player", "label": "From the player's side (from behind and above)", "objects": both, "direction": unity_dir(0.25, 0.55, -0.8)},
        {"file": "side", "label": "From the right: head, neck, yellow body, grip, trigger", "objects": both, "direction": unity_dir(1.0, 0.05, 0.0),
         "ortho": True},
        {"file": "front", "label": "From the front: head, nozzles (off screen)", "objects": both, "direction": unity_dir(0.25, 0.15, 1.0)},
        {"file": "back", "label": "From behind: flow knob, yellow body, trigger", "objects": both, "direction": unity_dir(-0.2, 0.25, -1.0)},
    ],
    references=[
        {"label": "Reference: video 0:21", "path": "docs/reference/24_hose_nozzle.png", "crop": [490, 220, 200, 260]},
        {"label": "Reference: video 0:31 (ref 07)", "path": "docs/reference/07_hose_dry_spot_dog.png", "crop": [470, 228, 260, 250]},
    ],
)
