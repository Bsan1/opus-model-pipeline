"""
Renders the model's mask from each solved camera for tools/Compare.py (run by it: blender -b --python this -- jobs.json).
The camera comes in OpenCV form (world -> camera R, t; x right, y down, looking along +z; focal in pixels, the principal
point in the middle) in Blender's world axes; Blender cameras look along -Z with +Y up.
"""
import json
import os
import sys

import bpy
from mathutils import Matrix, Vector

job_path = sys.argv[sys.argv.index("--") + 1]
with open(job_path, encoding="utf-8") as f:
    data = json.load(f)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=data["fbx"])   # the defaults undo the export's axis conversion (opus_model.export)
scene = bpy.context.scene
engines = {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
scene.render.engine = "BLENDER_WORKBENCH" if "BLENDER_WORKBENCH" in engines else scene.render.engine
scene.display.shading.light = "FLAT"
scene.display.shading.color_type = "SINGLE"
scene.display.shading.single_color = (1.0, 1.0, 1.0)
scene.render.film_transparent = True
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
camera = bpy.data.objects.new("CompareCamera", bpy.data.cameras.new("CompareCamera"))
scene.collection.objects.link(camera)
scene.camera = camera

for job in data["jobs"]:
    R = Matrix(job["R"])
    t = Vector(job["t"])
    centre = -(R.transposed() @ t)
    rows = [R[0], -R[1], -R[2]]          # the Blender camera's X, Y, Z axes in world space
    rotation = Matrix(rows).transposed()
    camera.matrix_world = Matrix.Translation(centre) @ rotation.to_4x4()
    camera.data.sensor_fit = "HORIZONTAL"
    camera.data.sensor_width = 36.0
    camera.data.lens = job["focal_px"] * 36.0 / job["width"]
    camera.data.clip_start = 0.01
    camera.data.clip_end = 1000.0
    scene.render.resolution_x = job["width"]
    scene.render.resolution_y = job["height"]
    scene.render.resolution_percentage = 100
    scene.render.filepath = job["mask"]
    bpy.ops.render.render(write_still=True)
    # The alpha is the mask: write it as white on black
    image = bpy.data.images.load(job["mask"], check_existing=False)
    pixels = list(image.pixels)
    for i in range(0, len(pixels), 4):
        a = 1.0 if pixels[i + 3] > 0.5 else 0.0
        pixels[i:i + 4] = [a, a, a, 1.0]
    image.pixels[:] = pixels
    image.filepath_raw = job["mask"]
    image.file_format = "PNG"
    image.save()
    print(f"[Opus] compare mask: {os.path.basename(job['mask'])}")
