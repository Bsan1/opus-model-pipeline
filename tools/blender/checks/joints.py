"""
Pipeline check: the joint gate (qc.joint_audit) still catches a member end cut at the wrong angle for what it meets.

The case the user found on 21 October 2026: the porch's rake board runs down a 15 degree slope into a vertical fascia board; cut
square to its slope its end crossed the fascia's face (9 mm proud at the top, 4 cm behind at the bottom). Checks:
- a sloped board cut square to its slope against a vertical fascia: found;
- the same board cut plumb, 2 mm behind the fascia's face: not found;
- two lapped boards (the upper one's bottom edge over the lower one, parallel members): not found.
Nothing is exported. Run: powershell -ExecutionPolicy Bypass -File tools/Models.ps1 -Checks
"""
import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402

import opus_model as om  # noqa: E402
import qc  # noqa: E402

ANGLE = math.radians(15.0)
DOWN = Vector((0.0, -math.sin(ANGLE), -math.cos(ANGLE)))        # down the slope (Unity axes: -Z out of the wall)
NORMAL = Vector((0.0, math.cos(ANGLE), -math.sin(ANGLE)))
LENGTH = 2.0
TOP = Vector((0.0, 3.0, 0.0))


def box(lo, hi):
    bm = bmesh.new()
    om.box(bm, lo, hi)
    return bm


def slab(corners):
    bm = bmesh.new()
    verts = [bm.verts.new(c) for c in corners]
    for quad in ((0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)):
        bm.faces.new([verts[i] for i in quad])
    return bm


def board(plumb):
    """The rake board, 3 cm thick, 17 cm deep, from the wall down to the fascia; plumb: its eave end cut vertical."""
    eave_z = (TOP + DOWN * LENGTH).z

    def p(x, s, h):
        return TOP + Vector((x, 0.0, 0.0)) + DOWN * s + NORMAL * h

    def end(x, h):
        if not plumb:
            return p(x, LENGTH, h)
        z = eave_z - 0.026
        return p(x, (z - TOP.z - NORMAL.z * h) / DOWN.z, h)

    return slab([p(0.0, 0.0, -0.17), end(0.0, -0.17), end(0.03, -0.17), p(0.03, 0.0, -0.17),
                 p(0.0, 0.0, 0.018), end(0.0, 0.018), end(0.03, 0.018), p(0.03, 0.0, 0.018)])


def audit(name, parts):
    model = om.Model(name, __file__)
    for index, bm in enumerate(parts):
        model.part(f"P{index}", bm, [model.surface("Paint", "#FFFFFF", "matte", "check part")], unity=True, smooth=False)
    result = qc.joint_audit([obj for obj, _ in model.parts])
    om.log(f"{name}: {result['bad']} bad of {result['ends']} ends ({result['worst'][:2]})")
    return result["bad"]


eave = TOP + DOWN * LENGTH
fascia = box((-0.03, eave.y - 0.17, eave.z - 0.028), (0.06, eave.y + 0.012, eave.z))
square = audit("joints_square", [board(False), fascia])
fascia = box((-0.03, eave.y - 0.17, eave.z - 0.028), (0.06, eave.y + 0.012, eave.z))
plumb = audit("joints_plumb", [board(True), fascia])
lap_lower = box((0.0, 1.0, 0.0), (2.0, 1.22, 0.026))
lap_upper = box((0.0, 1.19, 0.0), (2.0, 1.41, 0.026))
lapped = audit("joints_lapped", [lap_lower, lap_upper])
if square < 1:
    raise AssertionError("the joint gate missed a square-cut sloped board crossing a vertical fascia")
if plumb or lapped:
    raise AssertionError(f"the joint gate flagged a correct joint (plumb cut {plumb}, lapped boards {lapped})")
om.log("Joint check passed: the square cut is found, the plumb cut and the lap are not")
