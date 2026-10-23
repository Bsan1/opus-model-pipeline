"""
Pipeline check: the same part built twice comes out the same: the same vertex order, the same face order and every face
starting at the same corner (23 October 2026). bmesh operators (extrude_face_region, inset_region) and the bevel modifier
order what they make by memory address, so the wheel came out in another order at every build, and its smart UV unwrap,
its bake and the export's triangulation (which follows a quad's first corner when both diagonals are equal) followed:
its UVs and atlas differed from build to build. om.canonical_order / om.canonical_mesh put every part in an order given
by its geometry alone.
Here: a revolved part with pushed-out lugs, an inset and a bevel (the operators that reorder), built twice in this process
(new allocations, other addresses). Run: powershell -ExecutionPolicy Bypass -File tools/Models.ps1 -Checks
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import bmesh  # noqa: E402

import opus_model as om  # noqa: E402


def build(label):
    model = om.Model(label, __file__)
    paint = model.surface("Rubber", "#303030", "matte", "check part")
    bm = bmesh.new()
    rows = om.revolve(bm, [(0.0, 0.05), (0.0, 0.1), (0.02, 0.12), (0.06, 0.12), (0.08, 0.1), (0.08, 0.05)], 48)
    om.finish_shell(bm)
    for start in range(0, 48, 6):
        om.extrude_outward(bm, [rows[2][(start + k) % 48] for k in range(3)], 0.004)
    region = [rows[4][(start + 1) % 48] for start in range(0, 48, 12)]
    bmesh.ops.inset_region(bm, faces=region, thickness=0.002, depth=0.0, use_even_offset=True)
    obj = model.part("Wheel", bm, [paint], bevel={"width": 0.001, "segments": 1, "angle": 30.0})
    mesh = obj.data
    return ([tuple(round(c, 6) for c in v.co) for v in mesh.vertices], [tuple(p.vertices) for p in mesh.polygons])


first, second = build("determinism_a"), build("determinism_b")
same_verts, same_faces = first[0] == second[0], first[1] == second[1]
om.log(f"determinism: {len(first[0])} vertices same order {same_verts}, {len(first[1])} faces same order and start {same_faces}")
if not (same_verts and same_faces):
    differing = sum(1 for a, b in zip(first[1], second[1]) if a != b)
    raise AssertionError(f"the same part built twice came out in another order ({differing} faces differ): "
                         f"canonical_order / canonical_mesh no longer cover every operator")
om.log("Determinism check passed: the same part, the same order")
