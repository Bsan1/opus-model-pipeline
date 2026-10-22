"""
Pipeline check: an outside asset through om.external (free-assets -> tools/blender/external -> atlas bake).

Uses Poly Haven's "Planter Pot Clay" (CC0), fetched with tools/Assets.ps1 -Get polyhaven:planter_pot_clay. Checks:
- the licence gate: a folder whose asset.json says CC-BY-NC is refused, a folder without asset.json is refused;
- one part, no rotation or scale, scaled to the asked height, centred with its bottom on the ground;
- decimated to the triangle budget;
- the asset's own materials become source materials and the bake carries their texture into the atlas
  (the baked colour is not flat and matches the source texture's average colour);
- the spec's "external" record names the asset, its licence and its authors.
Images: Builds/Models/external_check/ (views) and Builds/Models/external_check_atlas/. Nothing goes to Unity.
Run: powershell -ExecutionPolicy Bypass -File tools/Models.ps1 -Checks
"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import bpy  # noqa: E402
import numpy as np  # noqa: E402

import opus_model as om  # noqa: E402

REF = "polyhaven:planter_pot_clay"
HEIGHT = 0.24     # m, the asked size of the Z axis
BUDGET = 1500     # triangles (the source has 3,080)


def expect_refusal(folder, what):
    try:
        om.Model("external_refused", __file__).external(REF, "matte", "refusal test", folder=folder)
    except RuntimeError as e:
        om.log(f"refused as expected ({what}): {str(e).splitlines()[0]}")
        return
    raise AssertionError(f"om.external accepted {what}")


def licence_gate():
    source = os.path.join(om.EXTERNAL_DIR, "polyhaven", "planter_pot_clay")
    with tempfile.TemporaryDirectory() as tmp:
        folder = os.path.join(tmp, "asset")
        shutil.copytree(source, folder)
        record_path = os.path.join(folder, "asset.json")
        with open(record_path, encoding="utf-8") as f:
            record = json.load(f)
        record["licence"], record["licence_note"] = "CC-BY-NC", "CC Attribution-NonCommercial (test)"
        with open(record_path, "w", encoding="utf-8") as f:
            json.dump(record, f)
        expect_refusal(folder, "a non-commercial licence")
        os.remove(record_path)
        expect_refusal(folder, "a folder without asset.json")


def check():
    licence_gate()
    model = om.Model("external_check", __file__)
    pot = model.external(REF, "matte", "Check: a clay planter pot from Poly Haven", size=HEIGHT, axis="z",
                         budget=BUDGET, name="Pot")
    bpy.context.view_layer.update()
    verts = [pot.matrix_world @ v.co for v in pot.data.vertices]
    lo = [min(v[i] for v in verts) for i in range(3)]
    hi = [max(v[i] for v in verts) for i in range(3)]
    triangles = sum(len(p.vertices) - 2 for p in pot.data.polygons)
    assert len(model.parts) == 1, model.parts
    assert abs((hi[2] - lo[2]) - HEIGHT) < 1e-4, f"height {hi[2] - lo[2]:.4f} m, asked {HEIGHT}"
    assert abs(lo[2]) < 1e-5, f"bottom at z {lo[2]:.5f}"
    assert abs(lo[0] + hi[0]) < 1e-4 and abs(lo[1] + hi[1]) < 1e-4, f"not centred: {lo} {hi}"
    assert triangles <= BUDGET, f"{triangles} tris, budget {BUDGET}"
    assert all(m.name.startswith(om.SOURCE_PREFIX) for m in pot.data.materials), [m.name for m in pot.data.materials]
    record = model.external_assets[0]
    assert record["ref"] == REF and record["licence"] == "CC0" and record["authors"], record
    om.log(f"external: {triangles} tris, {hi[0] - lo[0]:.3f} x {hi[1] - lo[1]:.3f} x {hi[2] - lo[2]:.3f} m, "
           f"{len(pot.data.materials)} materials, licence {record['licence']} ({', '.join(record['authors'])})")

    source = bpy.data.images.load(os.path.join(om.EXTERNAL_DIR, "polyhaven", "planter_pot_clay", "textures",
                                               "planter_pot_clay_diff_1k.jpg"))
    model.finish_textured(size=512, ao_distance=0.05, islands="smart", export=False, budget=BUDGET, views=[
        {"file": "front", "label": "External asset after the atlas bake (front)", "objects": ["Pot"],
         "direction": (0.0, -1.0, 0.35), "ground": 0.0},
        {"file": "top", "label": "From above", "objects": ["Pot"], "direction": (0.3, -0.4, 1.0), "ground": 0.0},
    ])
    baked = bpy.data.images.load(os.path.join(om.RENDER_DIR, "external_check_atlas", "external_check_color.png"))
    colour = mean_colour(baked)
    reference = mean_colour(source)
    spread = colour_spread(baked)
    om.log(f"baked colour mean {np.round(colour, 3)}, source texture mean {np.round(reference, 3)}, spread {spread:.3f}")
    assert spread > 0.03, "the baked atlas is flat: the source texture did not reach the bake"
    assert np.abs(colour - reference).max() < 0.12, "the baked colour does not match the source texture"


def pixels(image):
    values = np.empty(image.size[0] * image.size[1] * 4, dtype=np.float32)
    image.pixels.foreach_get(values)
    return values.reshape(-1, 4)


def mean_colour(image):
    """Average colour of the covered pixels (the atlas background is black)."""
    p = pixels(image)[:, :3]
    covered = p[p.sum(axis=1) > 0.02]
    return covered.mean(axis=0)


def colour_spread(image):
    p = pixels(image)[:, :3]
    covered = p[p.sum(axis=1) > 0.02]
    return float(covered.std(axis=0).mean())


check()
