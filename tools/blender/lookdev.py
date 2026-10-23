"""
Look-dev scene (reports/Oyun art stili tanımlama ve denetim.md, step 3): the built models judged side by side, in the
same light every time, so an asset's faults are not confused with a scene's lighting.

Run by tools/LookDev.ps1 (blender -b --python this). Reads tools/blender/style/style.json ("lookdev": the game light's sky
and sun colours, models placed together, models left out) and the built FBX files. Writes Builds/Style/lookdev/:
- lineup_{small,large}_{neutral,game}.png: every model at true scale next to a 1.8 m person (small things and big things
  in their own rows), in neutral light and in the game's light;
- spheres.png: one sphere per surface of the models (base colour, finish, tiling grain), in neutral light;
- sil_<model>_{64,32}.png: each model as a black silhouette, 64 and 32 px (Style.py bible lays them out).
Materials are rebuilt from the surface names the pipeline exports (<Kind>_<RRGGBB>_<finish>, Atlas_<model>), with the
tiling texture and the baked AO where the model has them: an approximation of the game's shader, not the shader itself.
Deterministic: fixed sample counts, no randomness; the same input gives the same pixels.
"""
import glob
import json
import math
import os
import re
import sys

import bpy
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MODELS = os.path.join(ROOT, "Assets", "Opus", "Resources", "Models")
OUT = os.path.join(ROOT, "Builds", "Style", "lookdev")
FINISHES = {"glossy": (0.22, 0.0), "satin": (0.5, 0.0), "matte": (0.85, 0.0), "metallic": (0.2, 1.0)}
NAME = re.compile(r"^([A-Za-z]+)_([0-9A-Fa-f]{6})(?:_x[0-9.]+)?_([a-z]+)$")

with open(os.path.join(ROOT, "tools", "blender", "style", "style.json"), encoding="utf-8") as f:
    STYLE = json.load(f)
LOOK = STYLE.get("lookdev", {})
LOOKS, SLOTS = {}, {}   # tiling.json: material name -> look; model -> {slot name: material name}
tiling_path = os.path.join(MODELS, "Tiling", "tiling.json")
if os.path.exists(tiling_path):
    with open(tiling_path, encoding="utf-8") as f:
        table = json.load(f)
    LOOKS = {m["name"]: m for m in table.get("materials", [])}
    SLOTS = {m["model"]: {s["slot"]: s["material"] for s in m["slots"]} for m in table.get("models", [])}


def linear(hex_colour):
    c = [int(hex_colour.lstrip("#")[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c] + [1.0]


def engine(scene):
    names = {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    for name in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        if name in names:
            scene.render.engine = name
            scene.eevee.taa_render_samples = 32
            return
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 32
    scene.cycles.seed = 0


def material(slot_name, model):
    """A preview material from the exported surface name (cached by model and name)."""
    base = re.sub(r"\.\d{3}$", "", slot_name)
    key = f"look:{model}:{base}"
    if key in bpy.data.materials:
        return bpy.data.materials[key]
    mat = bpy.data.materials.new(key)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    colour_socket = bsdf.inputs["Base Color"]
    ao = nodes.new("ShaderNodeVertexColor")   # the baked AO (vertex colour); white where there is none
    multiply = nodes.new("ShaderNodeMix")
    multiply.data_type = "RGBA"
    multiply.blend_type = "MULTIPLY"
    multiply.inputs["Factor"].default_value = 1.0
    links.new(ao.outputs["Color"], multiply.inputs[7])
    links.new(multiply.outputs[2], colour_socket)
    if base.startswith("Atlas_"):
        texture = os.path.join(MODELS, "Textures", model, f"{model}_color.png")
        if os.path.exists(texture):
            image = nodes.new("ShaderNodeTexImage")
            image.image = bpy.data.images.load(texture, check_existing=True)
            uv = nodes.new("ShaderNodeUVMap")
            links.new(uv.outputs["UV"], image.inputs["Vector"])
            links.new(image.outputs["Color"], multiply.inputs[6])
        bsdf.inputs["Roughness"].default_value = 0.7
        return mat
    m = NAME.match(base)
    if not m:
        multiply.inputs[6].default_value = (0.6, 0.6, 0.6, 1.0)
        return mat
    kind, hex_colour, finish = m.groups()
    rough, metal = FINISHES.get(finish, (0.7, 0.0))
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    look = LOOKS.get(SLOTS.get(model, {}).get(base, ""))
    tone = os.path.join(MODELS, "Tiling", f"{look['set']}_tone.png") if look else None
    if tone and os.path.exists(tone):
        image = nodes.new("ShaderNodeTexImage")
        image.image = bpy.data.images.load(tone, check_existing=True)
        mapping = nodes.new("ShaderNodeMapping")
        mapping.inputs["Scale"].default_value = (1.0 / look["metres"], 1.0 / look["metres"], 1.0)
        uv = nodes.new("ShaderNodeUVMap")
        links.new(uv.outputs["UV"], mapping.inputs["Vector"])
        links.new(mapping.outputs["Vector"], image.inputs["Vector"])
        tint = nodes.new("ShaderNodeMix")
        tint.data_type = "RGBA"
        tint.blend_type = "MULTIPLY"
        tint.inputs["Factor"].default_value = min(1.0, look.get("strength", 0.5))
        tint.inputs[6].default_value = linear(hex_colour)
        links.new(image.outputs["Color"], tint.inputs[7])
        links.new(tint.outputs[2], multiply.inputs[6])
    else:
        multiply.inputs[6].default_value = linear(hex_colour)
    return mat


def ensure_ao(mesh):
    """The AO node reads the mesh's render colour attribute; a mesh without one would come out black, so it gets white."""
    if not mesh.color_attributes:
        attribute = mesh.color_attributes.new("look_ao", "FLOAT_COLOR", "POINT")
        attribute.data.foreach_set("color", [1.0] * (4 * len(attribute.data)))
    mesh.color_attributes.render_color_index = 0
    mesh.color_attributes.active_color_index = 0


def import_model(model):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=os.path.join(MODELS, model + ".fbx"))
    objects = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    for obj in objects:
        ensure_ao(obj.data)
        for slot in obj.material_slots:
            if slot.material:
                slot.material = material(slot.material.name, model)
    return objects


def bounds(objects):
    bpy.context.view_layer.update()   # matrix_world is stale right after a move
    points = [o.matrix_world @ Vector(c) for o in objects for c in o.bound_box]
    lo = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    hi = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    return lo, hi


def move(objects, offset):
    for o in objects:
        if o.parent is None:
            o.location += offset


def person(x):
    """A 1.8 m neutral grey figure (the scale reference)."""
    grey = bpy.data.materials.new("look:person")
    grey.use_nodes = True
    next(n for n in grey.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = (0.35, 0.35, 0.37, 1)
    parts = []
    bpy.ops.mesh.primitive_cylinder_add(radius=0.17, depth=1.5, location=(x, 0, 0.75))
    parts.append(bpy.context.active_object)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.13, location=(x, 0, 1.67))
    parts.append(bpy.context.active_object)
    for p in parts:
        ensure_ao(p.data)
        p.data.materials.append(grey)
    return parts


def lights(kind):
    scene = bpy.context.scene
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    background = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    for o in [o for o in bpy.data.objects if o.type == "LIGHT"]:
        bpy.data.objects.remove(o)
    if kind == "neutral":
        background.inputs["Color"].default_value = (0.55, 0.55, 0.55, 1)
        sky_strength, sun_colour, sun_strength = 1.0, (1, 1, 1), 2.5
    else:
        background.inputs["Color"].default_value = linear(LOOK.get("game_sky", "#A79FBF"))
        sky_strength, sun_colour, sun_strength = 1.0, linear(LOOK.get("game_sun", "#FFE8C8"))[:3], LOOK.get("sun_strength", 3.5)
    background.inputs["Strength"].default_value = sky_strength
    sun = bpy.data.objects.new("look:sun", bpy.data.lights.new("look:sun", "SUN"))
    sun.data.energy = sun_strength
    sun.data.color = sun_colour
    sun.rotation_euler = (math.radians(50), 0, math.radians(-35))
    scene.collection.objects.link(sun)


def ground():
    bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, -0.001))
    plane = bpy.context.active_object
    mat = bpy.data.materials.new("look:ground")
    mat.use_nodes = True
    next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = (0.3, 0.3, 0.3, 1)
    plane.data.materials.append(mat)
    return plane


def camera_for(lo, hi, path, width=1600, elevation=8.0, aspect=None, labels=None, front=False):
    scene = bpy.context.scene
    cam = scene.camera
    centre = (lo + hi) * 0.5
    size_x, size_z = hi.x - lo.x, hi.z - lo.z
    aspect = aspect or max(0.25, min(1.0, (size_z + 0.5) / max(size_x, 1e-3) * 1.3))
    scene.render.resolution_x, scene.render.resolution_y = width, max(32, int(width * aspect))
    cam.data.type = "ORTHO"
    e = math.radians(elevation)
    # The visible height includes the depth seen from above; Blender's ortho_scale spans the image's longer side
    size_v = size_z * math.cos(e) + (hi.y - lo.y) * math.sin(e)
    if aspect <= 1.0:
        cam.data.ortho_scale = max(size_x * 1.06, size_v * 1.12 / aspect)
    else:
        cam.data.ortho_scale = max(size_v * 1.12, size_x * 1.06 * aspect)
    distance = 60 + size_x
    # The lineups look from -Y; front=True looks from +Y (the side the shed's door is on)
    side = hi.y + distance * math.cos(e) if front else lo.y - distance * math.cos(e)
    cam.location = Vector((centre.x, side, centre.z + distance * math.sin(e)))
    cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.clip_end = distance * 4
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    if labels:   # where each group landed in the image (pixels from the top left), for the art bible's callouts
        from bpy_extras.object_utils import world_to_camera_view
        bpy.context.view_layer.update()
        out = []
        for name, objects in labels:
            points = [world_to_camera_view(scene, cam, o.matrix_world @ Vector(c)) for o in objects for c in o.bound_box]
            xs = [p.x * scene.render.resolution_x for p in points]
            ys = [(1 - p.y) * scene.render.resolution_y for p in points]
            out.append({"name": name, "x0": round(min(xs)), "x1": round(max(xs)), "y0": round(min(ys)), "y1": round(max(ys))})
        with open(path[:-4] + ".json", "w", encoding="utf-8") as f:
            json.dump(out, f)


def main():
    os.makedirs(OUT, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    engine(scene)
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"
    cam = bpy.data.objects.new("look:camera", bpy.data.cameras.new("look:camera"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    skip = set(LOOK.get("exclude", [])) | set(STYLE.get("exempt", {}))   # exempt: technical assets outside the look
    together = {m: group[0] for group in LOOK.get("together", []) for m in group[1:]}
    models = [os.path.basename(p)[:-4] for p in sorted(glob.glob(os.path.join(MODELS, "*.fbx")))]
    models = [m for m in models if m not in skip]
    loaded = {m: import_model(m) for m in models}
    slots = {}   # host model -> all objects placed with it
    for m in models:
        host = together.get(m, m)
        slots.setdefault(host, []).extend(loaded[m])
    small_limit = LOOK.get("small_row_below_m", 1.5)
    rows = {"small": [], "large": []}
    for host, objects in slots.items():
        lo, hi = bounds(objects)
        rows["small" if max(hi - lo) < small_limit else "large"].append((host, objects, lo, hi))
    ground_plane = ground()
    everything = [o for objects in slots.values() for o in objects]
    for row, entries in rows.items():
        if not entries:
            continue
        gap = 0.25 if row == "small" else 2.0
        x = 0.0
        figure = person(x - 0.6 if row == "small" else x - 1.5)
        placed = list(figure)
        groups = [("person 1.8 m", list(figure))]
        for host, objects, lo, hi in sorted(entries, key=lambda e: max(e[3] - e[2])):
            move(objects, Vector((x - lo.x, -(lo.y + hi.y) * 0.5, -lo.z)))
            x += (hi.x - lo.x) + gap
            placed += objects
            groups.append((host, objects))
        # Only this row (and its person) is visible
        for o in everything:
            o.hide_render = o not in placed
        for kind in ("neutral", "game"):
            lights(kind)
            lo, hi = bounds(placed)
            camera_for(lo, hi, os.path.join(OUT, f"lineup_{row}_{kind}.png"), labels=groups)
        for o in figure:
            bpy.data.objects.remove(o)
        for host, objects, _, _ in entries:   # off to the side for the next row
            move(objects, Vector((0, 500, 0)))
    # Silhouettes: black on white, each model alone, 64 and 32 px
    lights("neutral")
    ground_plane.hide_render = True
    black = bpy.data.materials.new("look:black")
    black.use_nodes = True
    nodes = black.node_tree.nodes
    for n in list(nodes):
        nodes.remove(n)
    emit = nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = (0, 0, 0, 1)
    out = nodes.new("ShaderNodeOutputMaterial")
    black.node_tree.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    scene.view_layers[0].material_override = black
    world = scene.world.node_tree.nodes
    next(n for n in world if n.type == "BACKGROUND").inputs["Color"].default_value = (1, 1, 1, 1)
    for host, objects in slots.items():
        for o in everything:
            o.hide_render = o not in objects
        lo, hi = bounds(objects)
        for size in (64, 32):
            camera_for(lo, hi, os.path.join(OUT, f"sil_{host}_{size}.png"), width=size, elevation=12.0, aspect=1.0)
    scene.view_layers[0].material_override = None
    ground_plane.hide_render = False
    # Material spheres: one per surface, in neutral light
    for o in everything:
        o.hide_render = True
    lights("neutral")
    seen, spheres = [], []
    for m in models:
        for obj in loaded[m]:
            for slot in obj.material_slots:
                if slot.material and slot.material.name not in seen:
                    seen.append(slot.material.name)
    per_row = 10
    for i, name in enumerate(seen):
        x, y = (i % per_row) * 0.75, 0
        z = -(i // per_row) * 0.95
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.3, segments=48, ring_count=24, location=(x, y, z + 0.6))
        sphere = bpy.context.active_object
        bpy.ops.object.shade_smooth()
        ensure_ao(sphere.data)
        sphere.data.materials.append(bpy.data.materials[name])
        bpy.ops.object.text_add(location=(x - 0.33, y - 0.31, z + 0.18))
        label = bpy.context.active_object
        label.data.body = name.split(":")[-1].replace("_", " ")[:22]
        label.data.size = 0.07
        label.rotation_euler = (math.radians(90), 0, 0)
        label.data.materials.append(bpy.data.materials["look:person"] if "look:person" in bpy.data.materials else black)
        spheres += [sphere, label]
    ground_plane.hide_render = True
    lo, hi = bounds(spheres)
    camera_for(lo, hi, os.path.join(OUT, "spheres.png"), width=1600, elevation=4.0,
               aspect=max(0.2, (hi.z - lo.z + 0.3) / (hi.x - lo.x + 0.3)))
    near_misses(loaded, everything, spheres, ground_plane)
    print(f"[Opus] look-dev: {len(models)} models, {len(seen)} surfaces -> {os.path.relpath(OUT, ROOT)}")


def _variant(mat, kind):
    """A copy of a preview material turned into one of the style's near misses."""
    copy = mat.copy()
    copy.name = f"{mat.name}:{kind}"
    nodes, links = copy.node_tree.nodes, copy.node_tree.links
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    base = bsdf.inputs["Base Color"]
    source = base.links[0].from_socket if base.is_linked else None
    if kind == "glossy_plastic":
        m = NAME.match(mat.name.split(":")[-1])
        colour = linear(m.group(2)) if m else (0.5, 0.5, 0.5, 1.0)
        for link in list(base.links):
            links.remove(link)
        base.default_value = colour
        bsdf.inputs["Roughness"].default_value = 0.08
    elif kind == "oversaturated" and source is not None:
        hs = nodes.new("ShaderNodeHueSaturation")
        hs.inputs["Saturation"].default_value = 2.6
        links.new(source, hs.inputs["Color"])
        links.new(hs.outputs["Color"], base)
    elif kind == "baked_shadow" and source is not None:
        coords = nodes.new("ShaderNodeTexCoord")
        split = nodes.new("ShaderNodeSeparateXYZ")
        ramp = nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.0
        ramp.color_ramp.elements[0].color = (0.12, 0.1, 0.1, 1)
        ramp.color_ramp.elements[1].position = 0.55
        mix = nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        links.new(coords.outputs["Generated"], split.inputs["Vector"])
        links.new(split.outputs["Z"], ramp.inputs["Fac"])
        links.new(source, mix.inputs[6])
        links.new(ramp.outputs["Color"], mix.inputs[7])
        links.new(mix.outputs[2], base)
    return copy


def near_misses(loaded, everything, spheres, ground_plane):
    """The near-miss models in the game light: each as it is, and as the mistakes a generator makes easily (the art
    bible's do/don't, style.json near_misses). A hard-surface and an organic model, because a mistake shows on what it
    affects (24 October 2026: on the near-grey shed, 2.6 x the saturation changed the picture by 3.6 levels in 255)."""
    for model in LOOK.get("near_miss_models", []):
        if model in loaded:
            _near_miss(model, loaded[model], everything, spheres, ground_plane)


def _near_miss(model, objects, everything, spheres, ground_plane):
    for o in everything + spheres:
        o.hide_render = o not in objects
    ground_plane.hide_render = False
    originals = {(o.name, i): slot.material for o in objects for i, slot in enumerate(o.material_slots)}
    lo, hi = bounds(objects)
    back = Vector((0, -(lo.y + hi.y) * 0.5, 0))   # onto the ground plane, where its shadow can fall
    move(objects, back)
    lo, hi = bounds(objects)
    print(f"[Opus] near-miss {model}: {len(objects)} objects, bounds {tuple(round(v, 2) for v in lo)} .. {tuple(round(v, 2) for v in hi)}; "
          f"parents {sorted({o.parent.name if o.parent else '-' for o in objects})}")
    variants = [("style", None, "game"), ("glossy_plastic", "glossy_plastic", "game"), ("oversaturated", "oversaturated", "game"),
                ("baked_shadow", "baked_shadow", "game"), ("black_shadows", None, "black")]
    for name, kind, light in variants:
        for o in objects:
            for i, slot in enumerate(o.material_slots):
                original = originals[(o.name, i)]
                slot.material = _variant(original, kind) if kind and original else original
        lights("game")
        bpy.data.objects["look:sun"].rotation_euler.z += math.pi   # light the door side the camera looks at
        if light == "black":
            next(n for n in bpy.context.scene.world.node_tree.nodes if n.type == "BACKGROUND").inputs["Strength"].default_value = 0.0
        camera_for(lo, hi, os.path.join(OUT, f"near_{model}_{name}.png"), width=640, elevation=10.0, aspect=1.15, front=True)
    for o in objects:
        for i, slot in enumerate(o.material_slots):
            slot.material = originals[(o.name, i)]


main()
