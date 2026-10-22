"""
Calibration model: proves the scale and axes of the Blender -> FBX -> Unity pipeline.

- Cube: 1 m cube, base on the ground, pivot at the middle of the base (in Unity -0.5..0.5, 0..1, -0.5..0.5).
- Arrow_Front: the model's front (Blender -Y) -> Unity +Z, tip at 1.1 m. Blue.
- Arrow_Right: the model's right (Blender -X) -> Unity +X, tip at 0.9 m. Red.
- Arrow_Up: up (Blender +Z) -> Unity +Y, tip at 1.3 m. Green.
- Marker: a ball with a non-zero object position; Blender (-0.7, -0.7, 0.2) -> Unity (0.7, 0.2, 0.7). Yellow.
Since the arrows have different lengths, mirroring or rotation shows immediately in the Unity test and in the game.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import bmesh  # noqa: E402
from mathutils import Matrix  # noqa: E402

import opus_model as om  # noqa: E402

model = om.Model("calibration", __file__)
concrete = model.surface("Concrete", "#C9C3B8", "matte", "Calibration cube (scale and axis check)")
blue = model.surface("Paint", "#3D6FD6", "satin", "Front arrow (+Z)")
red = model.surface("Paint", "#D6453D", "satin", "Right arrow (+X)")
green = model.surface("Paint", "#4CA64A", "satin", "Up arrow (+Y)")
yellow = model.surface("Paint", "#E8C23A", "satin", "Position marker")

# Cube
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
bmesh.ops.translate(bm, verts=bm.verts, vec=(0.0, 0.0, 0.5))
om.finish_shell(bm)
model.part("Cube", bm, [concrete], bevel={"width": 0.012, "segments": 2, "angle": 30.0})


def arrow(name, axis, start, shaft_end, tip, material, offset):
    """Arrow along an axis: shaft (r 3.5 cm) + head (r 7 cm). start/shaft_end/tip are positions on the axis."""
    bm = bmesh.new()
    profile = [(start, 0.0), (start, 0.035), (shaft_end, 0.035), (shaft_end, 0.072), (tip, 0.0)]
    om.revolve(bm, profile, 32, axis=axis)
    bmesh.ops.translate(bm, verts=bm.verts, vec=offset)
    om.finish_shell(bm)
    model.part(name, bm, [material])


arrow("Arrow_Front", "Y", -0.45, -0.96, -1.1, blue, (0.0, 0.0, 0.5))
arrow("Arrow_Right", "X", -0.45, -0.78, -0.9, red, (0.0, 0.0, 0.5))
arrow("Arrow_Up", "Z", 0.95, 1.18, 1.3, green, (0.0, 0.0, 0.0))

# An object with a non-zero position (pivot at the ball's centre)
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=0.08, matrix=Matrix.Identity(4))
om.finish_shell(bm)
model.part("Marker", bm, [yellow], location=(-0.7, -0.7, 0.2), free=True)   # a position probe, not part of anything

everything = ["Cube", "Arrow_Front", "Arrow_Right", "Arrow_Up", "Marker"]
model.finish(
    views=[
        {"file": "three_quarter", "label": "3/4 (front-right-top)", "objects": everything, "direction": (-0.85, -1.0, 0.75)},
        {"file": "front", "label": "From the front (Blender -Y)", "objects": everything, "direction": (0.0, -1.0, 0.0), "ortho": True},
        {"file": "right", "label": "From the right (Blender -X)", "objects": everything, "direction": (-1.0, 0.0, 0.0), "ortho": True},
        {"file": "top", "label": "From above (front at the bottom)", "objects": everything, "direction": (0.0, -0.001, 1.0), "ortho": True},
    ],
)
