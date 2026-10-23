"""
Opus model pipeline: the shared tools on the Blender side (Blender 5.x, runs in the background; called by tools/Models.ps1).

Rules so that models arrive in Unity 1:1 and facing the right way:
- 1 Blender unit = 1 m; a model is built at real size.
- The model's front is -Y in Blender, its top +Z, its right -X. In Unity these become +Z, +Y, +X: U = (-x, z, -y).
- Objects have no rotation or scale (position only); rotated parts are built by rotating their vertices.
- Material name "<Kind>_<RRGGBB>"; the kind is one of the SurfaceKind names in Unity. Unity turns this name into its own
  Opus/Surface material; the colour in Blender is only a preview.
- Every shell of a closed part must be watertight with its normals facing out (signed volume > 0).

Outputs:
- Assets/Opus/Resources/Models/<name>.fbx
- Assets/Opus/ModelSpecs/<name>.json: the sizes the Unity test compares the imported model against (in Unity axes)
- Builds/Models/<name>/*.png and views.json: contact sheet views (PowerShell labels and combines them)
"""
import hashlib
import json
import math
import os
import random
import re
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qc  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FBX_DIR = os.path.join(ROOT, "Assets", "Opus", "Resources", "Models")
SPEC_DIR = os.path.join(ROOT, "Assets", "Opus", "ModelSpecs")
RENDER_DIR = os.path.join(ROOT, "Builds", "Models")
# Textured models: the baked atlas textures go to Unity, the CC0 source textures (Unity never sees them) live next to the pipeline
TEXTURE_DIR = os.path.join(FBX_DIR, "Textures")
SOURCE_TEXTURE_DIR = os.path.join(ROOT, "tools", "blender", "source_textures")
SOURCE_PREFIX = "Source_"     # source material (in Blender, before baking): "Source_<name>_<finish>"
ATLAS_PREFIX = "Atlas_"     # the only material of a textured model: "Atlas_<model>"; Unity reads the textures from Textures/<model>/
ATLAS_UV = "atlas"
# Buildings (finish(tiled=True)): UVs in metres along each piece's grain, tiling tone + normal textures per kind (no atlas)
TILE_DIR = os.path.join(FBX_DIR, "Tiling")
TILE_UV = "tile"
# Materials of the tiled models (21 October 2026; user: "two different materials, different by their type or by the context they
# are in, must have logically different textures; set a rule so it does not happen again"). A material is one real stuff in
# one context: the house's factory-painted lap siding is not the shed's rough painted boards, though both are painted wood
# siding. Every surface of a tiled model names its material (Model.surface(material=...)); a colour variant (repainted,
# recoloured) is the same material. The rules, checked at every build (check_material_registry; Model.surface and
# finish(tiled=True)) and
# in Unity (ModelImportTests.MaterialsFollowTheTextureRules):
#   1. a surface of a tiled model names a registered material of its kind;
#   2. no two materials look alike: another texture set, or tone strength 0.1 / bump 0.15 / repeat x1.3 apart;
#   3. a material with an owner belongs to that model only (the same stuff in another context is its own material); shared
#      ones (painted trim, painted metal, glass, concrete) are the same stuff wherever they are.
# Written to Tiling/tiling.json for Unity (SurfaceLibrary.TileLookFor), so the game and the Blender preview use the same numbers.
MATERIALS = {
    "lap_siding": {"kinds": ("Siding",), "set": "wood_siding", "metres": 1.2, "strength": 0.45, "bump": 0.55, "owner": "house",
                   "note": "factory-painted lap siding: fine, tight grain under smooth paint"},
    "rough_boards": {"kinds": ("Siding",), "set": "wood_rough", "metres": 1.0, "strength": 0.7, "bump": 1.0, "owner": "shed",
                     "note": "rough-sawn boards under weathered paint: open grain, nail holes, worn edges (CC0 ambientCG PaintedWood008A)"},
    "painted_trim": {"kinds": ("Paint",), "set": "paint_thick", "metres": 0.8, "strength": 0.35, "bump": 0.3, "owner": None,
                     "note": "casings, corner boards, fascia, sashes, doors, railings: thick paint, the grain barely there, brush marks"},
    "cedar_decking": {"kinds": ("Planks",), "set": "wood_cedar", "metres": 0.9, "strength": 0.85, "bump": 0.9, "owner": "house",
                      "note": "deck boards, joists, steps: unpainted cedar, open weathered grain (CC0 ambientCG Wood049)"},
    "asphalt_blend": {"kinds": ("Shingles",), "set": "shingle_blend", "metres": 4 * 0.14, "strength": 1.0, "bump": 0.9,
                      "owner": "house", "note": "house roof: architectural shingles, a mottled blend of granules"},
    "asphalt_3tab": {"kinds": ("Shingles",), "set": "shingle_3tab", "metres": 4 * 0.14, "strength": 1.0, "bump": 1.1,
                     "owner": "shed", "note": "shed roof: plain 3-tab shingles, even fine granules, weathered streaks"},
    "concrete": {"kinds": ("Concrete", "Stone"), "set": "concrete", "metres": 1.5, "strength": 0.8, "bump": 0.6, "owner": None,
                 "note": "poured concrete: soft blotches and speckle"},
    "painted_metal": {"kinds": ("Metal",), "set": "smooth", "metres": 0.6, "strength": 0.25, "bump": 0.3, "owner": None,
                      "note": "painted metal (gutters, hinges, handles, lamp body): a faint orange peel"},
    "enamel": {"kinds": ("Metal", "Paint"), "set": "smooth", "metres": 0.4, "strength": 0.1, "bump": 0.1, "owner": None,
               "note": "vitreous enamel (the lamp shade, inside and out): glassy, almost flawless"},
    "plastic": {"kinds": ("Plastic",), "set": "smooth", "metres": 0.25, "strength": 0.4, "bump": 0.45, "owner": None,
                "note": "moulded plastic (the vent pipe): a fine stipple"},
    "glass": {"kinds": ("Glass",), "set": "smooth", "metres": 0.6, "strength": 0.0, "bump": 0.0, "owner": None,
              "note": "window and door glass: flat"},
    "frosted_glass": {"kinds": ("Glass",), "set": "smooth", "metres": 0.6, "strength": 0.0, "bump": 0.6, "owner": None,
                      "note": "frosted bulb glass: matte grain, no tone"},
}


def materials_alike(a, b):
    """Two registered looks a viewer could not tell apart (rule 2)."""
    if a["set"] != b["set"]:
        return False
    ratio = max(a["metres"], b["metres"]) / max(min(a["metres"], b["metres"]), 1e-6)
    return abs(a["strength"] - b["strength"]) < 0.1 and abs(a["bump"] - b["bump"]) < 0.15 and ratio < 1.3


def check_material_registry():
    """Rule 2 over the whole registry: raises on any two materials that would look alike."""
    names = sorted(MATERIALS)
    alike = [(x, y) for i, x in enumerate(names) for y in names[i + 1:] if materials_alike(MATERIALS[x], MATERIALS[y])]
    if alike:
        raise ValueError(f"materials that would look alike (rule 2: another set, or strength 0.1 / bump 0.15 / repeat x1.3 "
                         f"apart): {alike}")


check_material_registry()
TILE_SIZE = 1024
# Shingle rows (house, porch, shed): the generator sets their UVs itself (preset_faces): v runs up the slope from every strip's
# butt, scaled so one exposure is SHINGLE_ROW metres of texture; the "shingle" set holds four rows per repeat, each with the
# shadow under the next butt. The row lines are then in a mipmapped texture, not in sub-pixel geometry (21 October 2026: the
# 1 cm butt faces, lit as faces turned down the slope, drew dark sub-pixel lines and made moire arcs on the roof from 8 m on).
SHINGLE_ROW = 0.14
PRESET_UV = "tile_preset_uv"   # loop UV layer: UVs the generator sets itself, kept by tile_uv
PRESET_FLAG = "tile_preset"    # face int layer: 1 = the face keeps its preset UV
PLANE_N = "plane_n"            # vertex vector layer: a normal set by the generator (a shingle strip takes its roof plane's)
# Outside assets fetched with tools/Assets.ps1 (free-assets): <source>/<id>/ with asset.json (source, licence, authors)
EXTERNAL_DIR = os.path.join(ROOT, "tools", "blender", "external")
# Licences an outside asset may have (free-assets codes); anything else is refused when the model is built
EXTERNAL_LICENCES = ("CC0", "CC-BY", "OGA-BY", "BlenderKit-RF")
EXTERNAL_FORMATS = (".glb", ".gltf", ".fbx", ".obj")   # in order of preference; .blend is never opened (it can run code)

# Same names as Opus.World.SurfaceKind in Unity
SURFACE_KINDS = {
    "Paint", "Siding", "Planks", "Vinyl", "Shingles", "Brick", "Concrete", "Stone", "Bark", "Soil", "Rubber",
    "Metal", "Plastic", "Foliage", "Fabric", "Glass", "Ground", "Prop", "Plant",
}
# Preview roughness (the look in Unity comes from the shader)
# Surface finish -> Blender preview (roughness, metallic). The Unity counterpart is SurfaceLibrary.ModelFinishes (same names).
FINISHES = {"glossy": (0.22, 0.0), "satin": (0.5, 0.0), "matte": (0.85, 0.0), "metallic": (0.2, 1.0)}

# The component plan's words (Model.plan)
PLAN_TIERS = ("simple", "complex")
PLAN_SOURCE_KINDS = ("video", "image", "model", "text", "web")   # web: what the research found (SKILL.md 2b)
PLAN_ROLES = ("functional", "structural", "decorative")
PLAN_MOVES = ("fixed", "hinge", "slide", "spin", "flex", "free")
PLAN_SEEN = ("seen", "guess", "real")
PLAN_CATEGORIES = ("machines", "suspended", "buildings", "organic")   # .claude/skills/model-plausibility/categories/*.md
FEATURE_TIERS = ("critical", "important", "optional")
# Preview (tools/Models.ps1 -Preview): validation, the plan and the construction gate, then labelled renders only; no other
# gates, no baking, no FBX or spec file (Builds/Models/<name>_preview.png). For looking at the structure before detailing.
PREVIEW = os.environ.get("OPUS_PREVIEW") == "1"


def to_unity(v):
    """Blender position/direction -> Unity (right-handed -> left-handed; FBX export and Unity import together)."""
    return (-v[0], v[2], -v[1])


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def log(message):
    print("[Opus] " + message, flush=True)


# Redirected output falls back to the local code page on Windows; write the log lines as UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass


# --------------------------------------------------------------------------------------------------------------
# Geometry helpers (bmesh)
# --------------------------------------------------------------------------------------------------------------

def revolve(bm, profile, segments, material=0, materials=None, axis="X", uv=None):
    """
    Revolves a closed cross-section profile around an axis (tire, rim, cap, arrow...).

    profile: [(a, r), ...] closed loop; a is the position along the axis, r the radius. A point with r == 0 is a single pole vertex.
    materials: material index per profile edge (otherwise all `material`).
    uv: (profile point i, angle slice j) -> (u, v) source UV; for the seam i goes up to len(profile), j up to segments.
    Returns: faces[i][j] = profile edge i (point i -> i+1), angle slice j. The normals must be turned outwards afterwards
    (finish_shell).
    """
    n = len(profile)
    rings = []
    for a, r in profile:
        if r < 1e-7:
            rings.append([bm.verts.new(_axis_point(axis, a, 0.0, 0.0))] * segments)
            continue
        ring = []
        for j in range(segments):
            t = 2.0 * math.pi * j / segments
            ring.append(bm.verts.new(_axis_point(axis, a, r * math.cos(t), r * math.sin(t))))
        rings.append(ring)

    faces = []
    for i in range(n):
        ra, rb = rings[i], rings[(i + 1) % n]
        row = []
        for j in range(segments):
            k = (j + 1) % segments
            quad = [ra[j], rb[j], rb[k], ra[k]]
            quad_uv = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
            unique = []
            unique_uv = []
            for v, key in zip(quad, quad_uv):
                if v not in unique:
                    unique.append(v)
                    unique_uv.append(key)
            if len(unique) < 3:
                row.append(None)
                continue
            face = bm.faces.new(unique)
            face.material_index = materials[i] if materials else material
            if uv is not None:
                set_face_uv(bm, face, [uv(a, b) for a, b in unique_uv])
            row.append(face)
        faces.append(row)
    return faces


def revolve_at(bm, profile, segments, origin, axis, material=0, uv=None):
    """Like `revolve`, but around any axis through the given point (a along the axis, r the radius)."""
    axis = Vector(axis).normalized()
    helper = Vector((0.0, 1.0, 0.0)) if abs(axis.y) < 0.9 else Vector((1.0, 0.0, 0.0))
    u = axis.cross(helper).normalized()
    w = axis.cross(u)
    bm.verts.ensure_lookup_table()
    first = len(bm.verts)
    faces = revolve(bm, profile, segments, material=material, axis="X", uv=uv)
    bm.verts.ensure_lookup_table()
    basis = Matrix(((axis.x, u.x, w.x, origin[0]), (axis.y, u.y, w.y, origin[1]), (axis.z, u.z, w.z, origin[2]),
                    (0.0, 0.0, 0.0, 1.0)))
    bmesh.ops.transform(bm, matrix=basis, verts=bm.verts[first:])
    return faces


def _axis_point(axis, a, u, v):
    if axis == "X":
        return Vector((a, u, v))
    if axis == "Y":
        return Vector((v, a, u))
    return Vector((u, v, a))


def grid_cut(bm, spacing):
    """
    Cuts the mesh with axis planes at regular spacing (spacing: metres per axis or None; the planes are shifted by half a
    step: k*step + step/2, so they do not coincide with wall planes at whole sizes). Closed shells stay closed;
    faces lying on a plane are not split.
    """
    for axis, step in enumerate(spacing):
        if not step:
            continue
        lo = min(v.co[axis] for v in bm.verts)
        hi = max(v.co[axis] for v in bm.verts)
        k = math.floor(lo / step - 0.5) + 1
        while (k + 0.5) * step < hi:
            co, normal = Vector((0.0, 0.0, 0.0)), Vector((0.0, 0.0, 0.0))
            co[axis], normal[axis] = (k + 0.5) * step, 1.0
            bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-5, plane_co=co,
                                   plane_no=normal)
            k += 1


def canonical_order(bm):
    """
    Puts a bmesh's vertices, edges and faces in an order given by their geometry alone, so the same model always comes out
    the same. 23 October 2026: bmesh operators such as extrude_face_region and inset_region order the faces they make by
    memory address, so the wheel came out with its faces in another order at every build (with the same vertices and the
    same PYTHONHASHSEED), and the smart UV unwrap, the packing and the export's triangulation followed that order: its UVs
    and atlas differed from build to build. Sorting is stable, so coincident elements keep their (deterministic) order.
    """
    def key(co):
        return tuple(round(c, 5) for c in co)

    def sort(seq, order):
        # BMElemSeq.sort wants a number: rank the elements in Python first (a stable sort)
        rank = {element: i for i, element in enumerate(sorted(seq, key=order))}
        seq.sort(key=lambda element: rank[element])
        seq.index_update()

    sort(bm.verts, lambda v: key(v.co))
    sort(bm.edges, lambda e: tuple(sorted((key(e.verts[0].co), key(e.verts[1].co)))))
    sort(bm.faces, lambda f: (f.material_index, key(f.calc_center_median()), tuple(sorted(key(v.co) for v in f.verts))))


def canonical_mesh(mesh):
    """
    canonical_order for a mesh whose modifiers were applied (the bevel modifier orders its output its own way). The custom
    (weighted) normals do not survive a BMesh round trip in the new order (measured: 136 of 216 corners of a bevelled cube
    changed), so every corner's normal is saved by its face centre and vertex position and written back.
    """
    def key(co):
        return tuple(round(c, 5) for c in co)

    custom = mesh.has_custom_normals
    saved = {}
    if custom:
        normals = mesh.corner_normals
        for p in mesh.polygons:
            centre = key(p.center)
            for li in p.loop_indices:
                saved[(centre, key(mesh.vertices[mesh.loops[li].vertex_index].co))] = tuple(normals[li].vector)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    canonical_order(bm)
    bm.to_mesh(mesh)
    bm.free()
    # Every face starts at its smallest corner: the operators also vary where a face's loop starts, and a quad's
    # triangulation (bake, export) follows its first corner when both diagonals are equal (the wheel's flat lug quads)
    loops = mesh.loops
    count = len(loops)
    perm = list(range(count))
    for p in mesh.polygons:
        start, total = p.loop_start, p.loop_total
        first = min(range(total), key=lambda k: key(mesh.vertices[loops[start + k].vertex_index].co))
        for k in range(total):
            perm[start + k] = start + (first + k) % total
    if perm != list(range(count)):
        for prop in ("vertex_index", "edge_index"):
            values = [0] * count
            loops.foreach_get(prop, values)
            loops.foreach_set(prop, [values[perm[i]] for i in range(count)])
        for layer in mesh.uv_layers:
            values = [0.0] * (2 * count)
            layer.data.foreach_get("uv", values)
            layer.data.foreach_set("uv", [values[2 * perm[i] + j] for i in range(count) for j in (0, 1)])
    if custom:
        mesh.update()
        loop_normals = [None] * len(mesh.loops)
        for p in mesh.polygons:
            centre = key(p.center)
            for li in p.loop_indices:
                loop_normals[li] = saved.get((centre, key(mesh.vertices[mesh.loops[li].vertex_index].co)), tuple(p.normal))
        mesh.normals_split_custom_set(loop_normals)
    mesh.update()


def finish_shell(bm, faces=None):
    """Turns the normals outwards (closed shell) and updates the face normals."""
    target = faces if faces is not None else list(bm.faces)
    bmesh.ops.recalc_face_normals(bm, faces=target)
    bm.normal_update()


def extrude_outward(bm, region, depth):
    """
    Pushes a face region out of its own surface (like a tire tread block): not a separate glued-on part but a bulge of the
    same surface. Every vertex moves by `depth` along the average normal of the neighbouring faces in the region.
    A negative depth pushes inwards (a pocket).
    """
    by_position = {}
    for f in region:
        for v in f.verts:
            by_position.setdefault(_key(v.co), Vector())
            by_position[_key(v.co)] += f.normal
    for key in by_position:
        by_position[key] = by_position[key].normalized()
    result = bmesh.ops.extrude_face_region(bm, geom=region)
    # The operation leaves the original faces in place; if they are not deleted the edges stay three-faced (open) ("FACES": inner
    # edges and vertices go too, the border used by the side walls stays)
    bmesh.ops.delete(bm, geom=region, context="FACES")
    moved = [g for g in result["geom"] if isinstance(g, bmesh.types.BMVert)]
    for v in moved:
        n = by_position.get(_key(v.co))
        if n is not None:
            v.co += n * depth
    return [g for g in result["geom"] if isinstance(g, bmesh.types.BMFace)]


def _key(co):
    return (round(co.x, 6), round(co.y, 6), round(co.z, 6))


def shells(bm):
    """Connected shells (face sets)."""
    seen = set()
    groups = []
    for start in bm.faces:
        if start.index in seen:
            continue
        stack = [start]
        seen.add(start.index)
        group = []
        while stack:
            f = stack.pop()
            group.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g.index not in seen:
                        seen.add(g.index)
                        stack.append(g)
        groups.append(group)
    return groups


def source_image(nodes, links, uv_socket, path, non_color=False, scale=(1.0, 1.0)):
    """
    Source texture node (the path under tools/blender/source_textures): the source UV is multiplied by `scale`.
    Returns the colour output. non_color: data maps such as normal and roughness (no sRGB conversion).
    """
    image = bpy.data.images.load(os.path.join(SOURCE_TEXTURE_DIR, path), check_existing=True)
    if non_color:
        image.colorspace_settings.name = "Non-Color"
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (scale[0], scale[1], 1.0)
    links.new(uv_socket, mapping.inputs["Vector"])
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = image
    texture.interpolation = "Cubic"
    links.new(mapping.outputs["Vector"], texture.inputs["Vector"])
    return texture.outputs["Color"]


def source_normal(nodes, links, color_socket, bsdf, strength=1.0):
    """Connects an OpenGL (+Y) normal map to the BSDF in the tangent space of the source UV."""
    normal_map = nodes.new("ShaderNodeNormalMap")
    normal_map.uv_map = SOURCE_UV
    normal_map.inputs["Strength"].default_value = strength
    links.new(color_socket, normal_map.inputs["Color"])
    links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])
    return normal_map


def coplanar_overlaps(objects, min_area=2e-6, limit=12):
    """
    Z-fighting hunter: overlapping triangles from different shells that lie in the same plane (1 mm) and face the same way.
    The graphics card cannot decide which one to draw every frame (shed corner boards, window opening vs sill).
    Only visible ones count: an overlap is hidden if it lies against a face in the same plane facing the opposite way (the underside of a
    shingle against the siding, the undersides of two shingles against the same siding).
    Returns: (total overlap area m², pair count, [(area, part/shell, part/shell, position), ...] the largest ones).
    """
    from bisect import bisect_left
    from collections import defaultdict
    buckets = defaultdict(list)
    for obj in objects:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.transform(obj.matrix_world)
        bm.faces.ensure_lookup_table()
        bm.normal_update()
        shell_of = {}
        for index, group in enumerate(shells(bm)):
            for f in group:
                shell_of[f.index] = index
        for tri in bm.calc_loop_triangles():
            face = tri[0].face
            n = face.normal
            if n.length < 0.5:
                continue
            pts = [l.vert.co.copy() for l in tri]
            if (pts[1] - pts[0]).cross(pts[2] - pts[0]).length < 2e-10:
                continue
            key = (round(n.x, 2), round(n.y, 2), round(n.z, 2))
            buckets[key].append((n.dot(pts[0]), f"{obj.name}/{shell_of[face.index]}", n.copy(), pts))
        bm.free()
    depths = {}
    for key, entries in buckets.items():
        entries.sort(key=lambda e: e[0])
        depths[key] = [e[0] for e in entries]

    def clip(poly, a, b):
        out = []
        for i in range(len(poly)):
            p, q = poly[i], poly[(i + 1) % len(poly)]
            side_p = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
            side_q = (b[0] - a[0]) * (q[1] - a[1]) - (b[1] - a[1]) * (q[0] - a[0])
            if side_p >= 0:
                out.append(p)
            if (side_p >= 0) != (side_q >= 0):
                t = side_p / (side_p - side_q)
                out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
        return out

    def area(poly):
        return 0.5 * abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                             for i in range(len(poly))))

    def ccw(tri):
        (ax, ay), (bx, by), (cx, cy) = tri
        return tri if (bx - ax) * (cy - ay) - (by - ay) * (cx - ax) > 0 else [tri[0], tri[2], tri[1]]

    def inside(point, tri):
        for k in range(3):
            a, b = tri[k], tri[(k + 1) % 3]
            if (b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0]) < -1e-7:
                return False
        return True

    def pressed(point3, normal, key, u, w):
        """Is the point lying against a face in the same plane facing the other way (normal -n)?"""
        opposite = buckets.get(tuple(round(-c, 2) for c in key))
        if not opposite:
            return False
        d = -normal.dot(point3)
        start = bisect_left(depths[tuple(round(-c, 2) for c in key)], d - 0.001)
        for d2, _, n2, pts in opposite[start:]:
            if d2 > d + 0.001:
                break
            if d2 < d - 0.001 or n2.dot(normal) > -0.999:
                continue
            tri = ccw([(p.dot(u), p.dot(w)) for p in pts])
            if inside((point3.dot(u), point3.dot(w)), tri):
                return True
        return False

    total, pairs, worst = 0.0, 0, []
    for key, entries in buckets.items():
        n0 = Vector(key).normalized()
        u = n0.orthogonal().normalized()
        w = n0.cross(u)
        flat = []
        for d, owner, n, pts in entries:
            tri = ccw([(p.dot(u), p.dot(w)) for p in pts])
            xs, ys = [p[0] for p in tri], [p[1] for p in tri]
            flat.append((d, owner, n, tri, (min(xs), min(ys), max(xs), max(ys)), pts))
        for i in range(len(flat)):
            d, owner, n, tri, box, pts = flat[i]
            for j in range(i + 1, len(flat)):
                d2, owner2, n2, tri2, box2, _ = flat[j]
                if d2 - d > 0.001:
                    break
                if owner == owner2 or n.dot(n2) < 0.999:
                    continue
                if box2[0] >= box[2] or box[0] >= box2[2] or box2[1] >= box[3] or box[1] >= box2[3]:
                    continue
                poly = tri
                for k in range(3):
                    poly = clip(poly, tri2[k], tri2[(k + 1) % 3])
                    if not poly:
                        break
                a = area(poly) if len(poly) >= 3 else 0.0
                if a <= min_area:
                    continue
                cx = sum(q[0] for q in poly) / len(poly)
                cy = sum(q[1] for q in poly) / len(poly)
                samples = [(cx, cy)] + [(cx + (q[0] - cx) * 0.7, cy + (q[1] - cy) * 0.7) for q in poly]
                def lift(x, y):
                    # The 3D point on the face's plane that projects to (x, y): u, w are perpendicular to the bucket's rounded
                    # normal n0, not to n, so u*x + w*y + n*d would miss the plane by up to centimetres far from the origin
                    base = u * x + w * y
                    return base + n0 * ((d - n.dot(base)) / n.dot(n0))
                points = [lift(x, y) for x, y in samples]
                if all(pressed(p, n, key, u, w) for p in points):
                    continue
                total += a
                pairs += 1
                worst.append((a, owner, owner2, to_unity(lift(cx, cy))))   # where the overlap is
    worst.sort(key=lambda x: -x[0])
    return total, pairs, worst[:limit]


def signed_volume(faces):
    """
    Signed volume of a closed shell, in double precision relative to a point of the shell: mathutils works in single precision,
    and a small part far from its origin (the house lamp shade, 7 m out) lost about 1 % of its volume to rounding.
    """
    faces = list(faces)
    if not faces:
        return 0.0
    ox, oy, oz = (float(c) for c in faces[0].verts[0].co)
    total = 0.0
    for f in faces:
        vs = [(v.co.x - ox, v.co.y - oy, v.co.z - oz) for v in f.verts]
        ax, ay, az = vs[0]
        for i in range(1, len(vs) - 1):
            bx, by, bz = vs[i]
            cx, cy, cz = vs[i + 1]
            total += (ax * (by * cz - bz * cy) + ay * (bz * cx - bx * cz) + az * (bx * cy - by * cx)) / 6.0
    return total


# Building in Unity space: models tied to in-game sizes, such as the mower, write their points in Unity axes (x right, y up,
# z front); the bmesh is converted to Blender axes when the part is built (Model.part(unity=True)).
UNITY_TO_BLENDER = Matrix(((-1.0, 0.0, 0.0, 0.0), (0.0, 0.0, -1.0, 0.0), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)))


def V(x, y, z):
    return Vector((x, y, z))


def _to_blender(unity_point):
    """Unity axes -> Blender axes (the inverse of to_unity)."""
    x, y, z = unity_point
    return Vector((-x, -z, y))


def rounded_rect(half_x, z_back, z_front, radius, corner_steps=6, center_x=0.0):
    """Rounded rectangle in the XZ plane [(x, z)], counter-clockwise from the back right; an equal number of points per corner."""
    radius = min(radius, half_x * 0.999, (z_front - z_back) * 0.4995)
    corners = [
        (center_x + half_x - radius, z_back + radius, -90.0),
        (center_x + half_x - radius, z_front - radius, 0.0),
        (center_x - half_x + radius, z_front - radius, 90.0),
        (center_x - half_x + radius, z_back + radius, 180.0),
    ]
    points = []
    for cx, cz, start in corners:
        for k in range(corner_steps + 1):
            t = math.radians(start + 90.0 * k / corner_steps)
            points.append((cx + radius * math.cos(t), cz + radius * math.sin(t)))
    return points


def taper_x(points, z_back, z_front, scale_back, scale_front, center_x=0.0):
    """Scales the points' x linearly along z (like a cover that is wide at the back and narrow at the front)."""
    out = []
    for x, z in points:
        t = min(1.0, max(0.0, (z - z_back) / (z_front - z_back)))
        out.append((center_x + (x - center_x) * (scale_back + (scale_front - scale_back) * t), z))
    return out


def ring_xz(points, y):
    return [V(x, y, z) for x, z in points]


SOURCE_UV = "source"


def source_uv(bm):
    """Source texture UV layer (the material nodes of textured models read it; the atlas UV is unwrapped separately for baking)."""
    return bm.loops.layers.uv.get(SOURCE_UV) or bm.loops.layers.uv.new(SOURCE_UV)


def set_face_uv(bm, face, coords):
    layer = source_uv(bm)
    for loop, uv in zip(face.loops, coords):
        loop[layer].uv = uv


def loft(bm, rings, material=0, cap_start=True, cap_end=True, closed=False, uv=None, cap_uv=None):
    """
    Joins closed rings with the same number of points in order with quads (soft shells such as the housing, a cover, a body).
    The ends are capped with a single polygon; with closed=True the last ring joins the first (torus, ring handle; no ends).
    uv: (ring i, point j) -> (u, v) source UV; for the seam it is called with i up to len(rings) and j up to the ring length.
    The normals are turned outwards afterwards with finish_shell.
    """
    verts = [[bm.verts.new(p) for p in ring] for ring in rings]
    n = len(rings[0])
    faces = []
    pairs = list(zip(verts, verts[1:]))
    if closed:
        pairs.append((verts[-1], verts[0]))
    for i, (a, b) in enumerate(pairs):
        for j in range(n):
            k = (j + 1) % n
            face = bm.faces.new((a[j], b[j], b[k], a[k]))
            face.material_index = material
            if uv is not None:
                set_face_uv(bm, face, (uv(i, j), uv(i + 1, j), uv(i + 1, j + 1), uv(i, j + 1)))
            faces.append(face)
    if not closed:
        for index, (ring, use) in enumerate(((verts[0], cap_start), (verts[-1], cap_end))):
            if use:
                face = bm.faces.new(ring)
                face.material_index = material
                if cap_uv is not None:
                    set_face_uv(bm, face, [cap_uv(index, j) for j in range(n)])
                faces.append(face)
    return faces


def fillet(points, radius, steps=6):
    """Rounds the corners of a polyline with arcs (a bent pipe)."""
    pts = [Vector(p) for p in points]
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = pts[i - 1], pts[i], pts[i + 1]
        d1, d2 = (a - b).normalized(), (c - b).normalized()
        angle = d1.angle(d2)
        if angle > math.pi - 1e-3:
            out.append(b)
            continue
        cut = min(radius / math.tan(angle / 2.0), (a - b).length * 0.49, (c - b).length * 0.49)
        p1, p2 = b + d1 * cut, b + d2 * cut
        for k in range(steps + 1):
            t = k / steps
            # Quadratic Bézier: tangent continuity at the corner
            out.append(p1 * (1 - t) ** 2 + b * 2 * t * (1 - t) + p2 * t ** 2)
    out.append(pts[-1])
    return out


def spline(points, samples=8):
    """Catmull-Rom curve: a smooth path through the control points (cable)."""
    pts = [Vector(p) for p in points]
    ext = [pts[0] * 2 - pts[1]] + pts + [pts[-1] * 2 - pts[-2]]
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for k in range(samples):
            t = k / samples
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t))
    out.append(pts[-1])
    return out


def sweep(bm, path, radius, sides=16, material=0, caps=True, radii=None, shape=None, closed=False, up=None,
          uv_scale=None, twist=None):
    """
    Sweeps the cross-section along the path (pipe, handle, rod, cable); with a rotation-minimising frame (parallel transport) it does not twist.
    radii: radius multiplier per point (a branch tapering at the tip, a cable).
    shape: a [(u, v), ...] cross-section instead of a circle (u on the frame's "normal" axis, v on its "binormal"; a flat trigger, a grip).
    closed: the path is a closed ring (D handle, rope loop): the last ring joins the first, no ends.
    up: a hint for the "normal" direction of the first frame (otherwise any direction perpendicular to the path).
    uv_scale: (u around the circumference, v per metre): the source UV (a rope texture wraps around, repeats lengthwise).
    twist: (strand count, amplitude, pitch m): the cross-section radius ripples as many times as the strand count and turns once over the pitch
    (twisted rope: 3 strands). On a closed path the pitch and the v scale are rounded so the seam is a whole turn.
    """
    path = [Vector(p) for p in path]
    cleaned = [path[0]]
    for p in path[1:]:
        if (p - cleaned[-1]).length > 1e-6:
            cleaned.append(p)
    path = cleaned
    if closed and (path[0] - path[-1]).length < 1e-6:
        path = path[:-1]
    count = len(path)
    tangents = []
    for i in range(count):
        if closed:
            a, b = path[(i - 1) % count], path[(i + 1) % count]
        else:
            a, b = path[max(i - 1, 0)], path[min(i + 1, count - 1)]
        tangents.append((b - a).normalized())
    if up is not None:
        normal = Vector(up) - tangents[0] * Vector(up).dot(tangents[0])
    else:
        helper = Vector((0.0, 1.0, 0.0)) if abs(tangents[0].y) < 0.9 else Vector((1.0, 0.0, 0.0))
        normal = tangents[0].cross(helper)
    normal = normal.normalized()
    if shape is None:
        shape = [(math.cos(2.0 * math.pi * s / sides), math.sin(2.0 * math.pi * s / sides)) for s in range(sides)]
        scale = radius
    else:
        scale = 1.0
    # Length along the path (for the twist and the source UV)
    lengths = [0.0]
    for a, b in zip(path, path[1:]):
        lengths.append(lengths[-1] + (b - a).length)
    total = lengths[-1] + ((path[0] - path[-1]).length if closed else 0.0)
    lengths.append(total)
    if twist is not None:
        lobes, amplitude, pitch = twist
        if closed:
            pitch = total / max(1, round(total / pitch))
    if uv_scale is not None:
        around, along = uv_scale
        if closed:
            along = max(1, round(total * along)) / total
    n_shape = len(shape)
    rings = []
    for i, p in enumerate(path):
        t = tangents[i]
        if i > 0:
            normal = (normal - t * normal.dot(t)).normalized()
        binormal = t.cross(normal)
        r = scale * (radii[i] if radii else 1.0)
        ring = []
        for j, (u, v) in enumerate(shape):
            k = r
            if twist is not None:
                theta = 2.0 * math.pi * j / n_shape
                k *= 1.0 + amplitude * math.cos(lobes * (theta - 2.0 * math.pi * lengths[i] / pitch))
            ring.append(p + (normal * u + binormal * v) * k)
        rings.append(ring)
    uv = cap_uv = None
    if uv_scale is not None:
        def uv(i, j):
            return (j / n_shape * around, lengths[min(i, len(lengths) - 1)] * along)

        def cap_uv(end, j):
            # End cap: a disc the size of the rope's cross-section in UV (so it has real area in the atlas)
            angle = 2.0 * math.pi * j / n_shape
            radius = around / (2.0 * math.pi)
            base = lengths[-2 if end else 0] * along
            return (around * 0.5 + math.cos(angle) * radius, base + math.sin(angle) * radius)
    return loft(bm, rings, material=material, cap_start=caps, cap_end=caps, closed=closed, uv=uv, cap_uv=cap_uv)


def rounded_profile(half_u, half_v, radius, steps=4):
    """Rounded-rectangle cross-section [(u, v)] for sweeping (flat trigger, grip, D ring cross-section)."""
    return [(u, v) for u, v in rounded_rect(half_u, -half_v, half_v, radius, steps)]


def foliage_normals(bm, layer_name="dir"):
    """Custom normal layer for leaf vertices (float vector); part(foliage=True) turns it into the vertex normals."""
    return bm.verts.layers.float_vector.get(layer_name) or bm.verts.layers.float_vector.new(layer_name)


def _slot_material(index):
    name = f"_yuva{index}"
    return bpy.data.materials.get(name) or bpy.data.materials.new(name)


def _temp_object(bm, name):
    finish_shell(bm)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    # Boolean only carries the cutter's face index if there is a real material in that slot (empty slot -> first material):
    # placeholder materials in the same order on both objects
    for index in range(12):
        mesh.materials.append(_slot_material(index))
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def carve(bm, cutters):
    """
    Subtracts the cutters from a single closed shell (boolean difference, exact solver) and returns the result as a new bmesh.
    Carving only applies to that shell; other shells nested in it (screw, cap) are added afterwards with `merge`.
    The cutter's face material index goes to the cut surface.
    """
    target = _temp_object(bm, "carved")
    removed = []
    for index, cutter_bm in enumerate(cutters):
        cutter = _temp_object(cutter_bm, f"cutter{index}")
        removed.append(cutter)
        mod = target.modifiers.new(f"Carve{index}", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.solver = "EXACT"
        mod.object = cutter
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = target.evaluated_get(depsgraph)
    result = bmesh.new()
    result.from_mesh(evaluated.to_mesh())
    evaluated.to_mesh_clear()
    for obj in removed + [target]:
        mesh = obj.data
        bpy.data.objects.remove(obj)
        bpy.data.meshes.remove(mesh)
    return result


def merge(target, source):
    """Adds the content of the source bmesh to target (source is freed)."""
    mesh = bpy.data.meshes.new("merged")
    source.to_mesh(mesh)
    source.free()
    target.from_mesh(mesh)
    bpy.data.meshes.remove(mesh)
    return target


def board(bm, origin, axis, side, up, width, depth, start, end, material=0):
    """
    A straight member (board, rafter, rail, rake board) whose ends are cut to the faces they meet, whatever its slope: its
    cross-section runs `width` along `side` and `depth` along `up` from `origin`, its length along `axis`, and each end is cut by a
    plane (point, normal): the face it sits on or butts against (a wall's plane, a fascia's face, a level floor, a plumb line).
    A sloped member left with its ends square to its length crosses the face it meets: part pokes through, part leaves a wedge
    (the porch's rake boards, 21 October 2026). qc.joint_audit fails a build on that; this helper is the way not to make it.
    Returns the six faces.
    """
    origin, axis, side, up = Vector(origin), Vector(axis).normalized(), Vector(side), Vector(up)

    def cut(corner, plane):
        point, normal = Vector(plane[0]), Vector(plane[1])
        along = axis.dot(normal)
        if abs(along) < 1e-6:
            raise ValueError("board: an end plane runs along the board")
        return corner + axis * ((point - corner).dot(normal) / along)

    section = [origin, origin + side * width, origin + side * width + up * depth, origin + up * depth]
    a = [bm.verts.new(cut(c, start)) for c in section]
    b = [bm.verts.new(cut(c, end)) for c in section]
    faces = [bm.faces.new(list(reversed(a))), bm.faces.new(b)]
    for k in range(4):
        faces.append(bm.faces.new((a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k])))
    for face in faces:
        face.material_index = material
    finish_shell(bm, faces)
    return faces


def box(bm, lo, hi, material=0):
    """Axis-aligned box (a cutter or a simple part)."""
    lo, hi = Vector(lo), Vector(hi)
    corners = [Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    v = [bm.verts.new(c) for c in corners]
    faces = []
    for quad in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
        face = bm.faces.new([v[i] for i in quad])
        face.material_index = material
        faces.append(face)
    return faces


def settle(bodies, colliders=(), frames=200, limit=600, shape="CONVEX_HULL", friction=0.7, bounce=0.05,
           damping=(0.25, 0.6), density=None, margin=0.001, substeps=20, iterations=30, rest=5e-4, sleep=(0.02, 0.1)):
    """
    Rigid body placement: instead of laying parts out by hand it drops them and leaves them where they come to rest
    (apples in a crate, stones at a flowerbed edge, stacked logs). The Bullet simulation gives the same result for the same input;
    the model comes out the same in every build.

    bodies: the parts to drop (objects returned by Model.part), in the air at the start without touching each other or the
    colliders (otherwise an error: bodies starting interpenetrated fling each other, one falls through the floor).
    colliders: static collision objects (crate, ground); their shapes as they are (MESH, can be concave).
    shape: collision shape of the bodies (CONVEX_HULL: stone, apple; SPHERE; BOX).
    density: kg/m³ (None = all 1 kg); so that with parts of different sizes the heavy one settles lower.
    sleep: (m/s, rad/s) a body below these speeds goes to sleep (Bullet deactivation): a resting stone stays without jitter.
    damping: (linear, angular) damping; Bullet has no rolling friction, the angular damping stops round parts that would roll
    forever on a flat floor.
    frames: at least this many frames (24 frames/s); after that it checks every 10 frames and ends when all have stopped or at `limit`.
    At the end the simulation is removed; every body's rotation is baked into its vertices, only the position stays on the object (the pipeline's rule).
    Returns: every body's movement over the last 10 frames (m). If any moves more than `rest`, a warning is written.
    """
    touching = _overlapping_pairs(list(bodies), list(colliders))
    if touching:
        raise ValueError("settle: parts interpenetrating at the start: " + ", ".join(f"{a}-{b}" for a, b in touching[:8]))
    scene = bpy.context.scene
    if scene.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()
    world = scene.rigidbody_world
    if world.collection is None:
        world.collection = bpy.data.collections.new("RigidBodyWorld")
    world.substeps_per_frame = substeps
    world.solver_iterations = iterations
    scene.frame_start, scene.frame_end = 1, limit
    world.point_cache.frame_start, world.point_cache.frame_end = 1, limit

    def add(obj, kind):
        with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj],
                                       selected_editable_objects=[obj]):
            bpy.ops.rigidbody.object_add(type=kind)
        body = obj.rigid_body
        body.friction = friction
        body.restitution = bounce
        body.use_margin = True
        body.collision_margin = margin
        return body

    for obj in bodies:
        if obj.data.users > 1:
            obj.data = obj.data.copy()
        # Centre of mass ≈ middle of the bounding box: move the origin there (the body rotates around its origin)
        corners = [v.co for v in obj.data.vertices]
        center = Vector([(min(c[i] for c in corners) + max(c[i] for c in corners)) * 0.5 for i in range(3)])
        obj.data.transform(Matrix.Translation(-center))
        obj.location = Vector(obj.location) + center
        body = add(obj, "ACTIVE")
        body.collision_shape = shape
        body.linear_damping, body.angular_damping = damping
        body.use_deactivation = True
        body.deactivate_linear_velocity, body.deactivate_angular_velocity = sleep
        if density:
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            body.mass = max(abs(bm.calc_volume(signed=False)) * density, 1e-3)
            bm.free()
    for obj in colliders:
        body = add(obj, "PASSIVE")
        body.collision_shape = "MESH"

    depsgraph = bpy.context.evaluated_depsgraph_get()
    sizes = [max(obj.dimensions) * 0.5 for obj in bodies]

    def poses():
        return [obj.evaluated_get(depsgraph).matrix_world.copy() for obj in bodies]

    before = after = None
    motion = []
    frame = 0
    while frame < limit:
        frame += 1
        scene.frame_set(frame)
        if frame >= frames and frame % 10 == 0:
            before, after = after, poses()
            if before is not None:
                motion = [(b.translation - a.translation).length +
                          a.to_quaternion().rotation_difference(b.to_quaternion()).angle * size
                          for a, b, size in zip(before, after, sizes)]
                if max(motion) <= rest:
                    break
    if after is None:
        raise ValueError("settle: frames must be smaller than limit and a multiple of 10")

    for obj in list(bodies) + list(colliders):
        with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj],
                                       selected_editable_objects=[obj]):
            bpy.ops.rigidbody.object_remove()
    bpy.ops.rigidbody.world_remove()
    scene.frame_set(1)
    for obj, final in zip(bodies, after):
        location, rotation, _ = final.decompose()
        obj.data.transform(rotation.to_matrix().to_4x4())
        obj.data.update()
        obj.rotation_euler = (0.0, 0.0, 0.0)
        obj.scale = (1.0, 1.0, 1.0)
        obj.location = location
    moving = [f"{obj.name} {m * 1000:.1f} mm" for obj, m in zip(bodies, motion) if m > rest]
    log(f"Settle: {len(bodies)} bodies, {frame} frames" +
        (f"; NOT SETTLED: {', '.join(moving)}" if moving else f"; all stopped (at most {max(motion) * 1000:.2f} mm)"))
    return motion


def _overlapping_pairs(bodies, colliders):
    """Pairs of objects that intersect or where one is inside the other (body-body and body-collider)."""
    from mathutils.bvhtree import BVHTree
    bpy.context.view_layer.update()      # so the new positions reach matrix_world
    shapes = []
    for obj in bodies + colliders:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.transform(obj.matrix_world)
        shapes.append((obj.name, BVHTree.FromBMesh(bm), next(iter(bm.verts)).co.copy() if bm.verts else None))
        bm.free()
    pairs = []
    for i in range(len(bodies)):
        for j in range(i + 1, len(shapes)):
            (a, tree_a, point_a), (b, tree_b, point_b) = shapes[i], shapes[j]
            inside = False
            for point, tree in ((point_a, tree_b), (point_b, tree_a)):
                hit, normal, _, _ = tree.find_nearest(point) if point is not None else (None, None, None, None)
                inside = inside or (hit is not None and (point - hit).dot(normal) < 0.0)
            if tree_a.overlap(tree_b) or inside:
                pairs.append((a, b))
    return pairs


# --------------------------------------------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------------------------------------------

def _periodic_noise(size, seed, falloff, lo_cut=1.0):
    """Tileable noise (filtered white noise in frequency space): `falloff` sets how rough (higher = smoother); zero mean, unit std."""
    import numpy as np
    rng = np.random.default_rng(seed)
    white = rng.standard_normal((size, size))
    fy = np.fft.fftfreq(size)[:, None] * size
    fx = np.fft.fftfreq(size)[None, :] * size
    radius = np.sqrt(fx * fx + fy * fy)
    gain = 1.0 / np.maximum(radius, lo_cut) ** falloff
    gain[0, 0] = 0.0
    field = np.real(np.fft.ifft2(np.fft.fft2(white) * gain))
    return (field - field.mean()) / max(field.std(), 1e-9)


def _normal_from_height(height, strength):
    """Tangent-space normal map (OpenGL +Y, as Unity) from a tileable height field (wrapping differences)."""
    import numpy as np
    dx = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) * 0.5 * strength
    dy = (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)) * 0.5 * strength
    n = np.stack([-dx, -dy, np.ones_like(height)], axis=-1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * 0.5 + 0.5


def _save_png(path, rgb):
    import numpy as np
    size = rgb.shape[0]
    image = bpy.data.images.new(os.path.basename(path), size, size, alpha=False, float_buffer=False)
    image.colorspace_settings.name = "Non-Color"
    rgba = np.ones((size, size, 4), dtype=np.float32)
    rgba[..., :3] = np.clip(rgb, 0.0, 1.0)
    image.pixels.foreach_set(rgba.ravel())
    image.filepath_raw = path
    image.file_format = "PNG"
    image.save()
    bpy.data.images.remove(image)


def write_tile_sets(model):
    """
    The tiled models' textures (Assets/Opus/Resources/Models/Tiling/<set>_{tone,normal}.png, 1024, seamless) and tiling.json
    (the materials' looks and every tiled model's slot -> material map, merged with the other models'). tone: grey, 0.5 = the
    material colour as is. The wood sets come from CC0 photos (outside assets, licence-checked): their luminance (the tone;
    the colour stays the material's) and their normal maps, each processed to its stuff; shingles, concrete and the smooth set
    are generated from tileable noise. Deterministic: the same files every build.
    """
    import numpy as np
    os.makedirs(TILE_DIR, exist_ok=True)

    def photo(ref, name):
        image = bpy.data.images.load(model.external_texture(ref, name), check_existing=True)
        image.colorspace_settings.name = "Non-Color"
        w, h = image.size
        px = np.empty(w * h * 4, dtype=np.float32)
        image.pixels.foreach_get(px)
        return px.reshape(h, w, 4)[..., :3]

    def luminance(rgb):
        lum = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
        return (lum - lum.mean()) / max(float(lum.std()), 1e-6)

    def blur(field, radius, axis=None):
        """Box blur, wrapping (seamless); axis: along one image axis only (0 = v, 1 = u)."""
        out = field.copy()
        axes = (0, 1) if axis is None else (axis,)
        for ax in axes:
            acc = np.zeros_like(field)
            for k in range(-radius, radius + 1):
                acc += np.roll(out, k, axis=ax)
            out = acc / (2 * radius + 1)
        return out

    def save(name, tone_field, contrast, normal=None, height=None, bump=1.0):
        tone = 0.5 + tone_field / max(float(tone_field.std()), 1e-6) * contrast
        _save_png(os.path.join(TILE_DIR, f"{name}_tone.png"), np.repeat(tone[..., None], 3, axis=-1))
        if normal is None:
            normal = _normal_from_height(height / max(float(height.std()), 1e-9), bump * 0.05)
        _save_png(os.path.join(TILE_DIR, f"{name}_normal.png"), normal)

    # House lap siding: the painted-wood photo with its grain softened (paint over a smoothed board)
    lum009 = luminance(photo("ambientcg:PaintedWood009C", "PaintedWood009C_1K-JPG_Color.jpg"))
    normal009 = photo("ambientcg:PaintedWood009C", "PaintedWood009C_1K-JPG_NormalGL.jpg")
    save("wood_siding", blur(lum009, 1), 0.07, normal=normal009)
    # Shed: rough-sawn weathered boards, a photo of its own
    save("wood_rough", luminance(photo("ambientcg:PaintedWood008A", "PaintedWood008A_1K-JPG_Color.jpg")), 0.11,
         normal=photo("ambientcg:PaintedWood008A", "PaintedWood008A_1K-JPG_NormalGL.jpg"))
    # Trim: thick paint, the grain barely there under it, brush marks along the board
    streaks = blur(_periodic_noise(TILE_SIZE, 51, 0.8), 24, axis=1)
    paint = 0.35 * blur(lum009, 6) + 0.8 * streaks / max(float(streaks.std()), 1e-6)
    save("paint_thick", paint, 0.035, height=paint, bump=0.6)
    # Deck: unpainted cedar boards, a wood-grain photo
    save("wood_cedar", luminance(photo("ambientcg:Wood049", "Wood049_1K-JPG_Color.jpg")), 0.12,
         normal=photo("ambientcg:Wood049", "Wood049_1K-JPG_NormalGL.jpg"))
    _write_shingle_set("shingle_blend", granules=0.07, blotches=0.07, streaks=0.0, seed=41)
    _write_shingle_set("shingle_3tab", granules=0.09, blotches=0.025, streaks=0.05, seed=61)
    sets = {
        # concrete: soft blotches + speckle
        "concrete": (0.9 * _periodic_noise(TILE_SIZE, 21, 2.2, 2.0) + 0.35 * _periodic_noise(TILE_SIZE, 22, 0.4), 0.08, 1.6),
        # metal, plastic, glass: almost flat, a faint orange peel (the materials scale it)
        "smooth": (_periodic_noise(TILE_SIZE, 31, 1.4, 3.0), 0.02, 0.6),
    }
    for name, (field, contrast, bump) in sets.items():
        save(name, field, contrast, height=field, bump=bump)
    for stale in ("wood_paint", "asphalt", "shingle"):
        for suffix in ("tone.png", "normal.png", "tone.png.meta", "normal.png.meta"):
            path = os.path.join(TILE_DIR, f"{stale}_{suffix}")
            if os.path.exists(path):
                os.remove(path)
    # tiling.json: the registry's looks + this model's slot -> material map (the other models' maps kept)
    path = os.path.join(TILE_DIR, "tiling.json")
    models = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            models = {m["model"]: m for m in json.load(f).get("models", [])}
    used = sorted({slot.name for obj, _ in model.parts for slot in obj.data.materials if slot})
    models[model.name] = {"model": model.name, "slots": [{"slot": name, "material": model.surface_materials[name]} for name in used]}
    table = {
        "materials": [{"name": name, "set": m["set"], "metres": m["metres"], "strength": m["strength"], "bump": m["bump"],
                       "owner": m["owner"] or "", "kinds": list(m["kinds"])} for name, m in sorted(MATERIALS.items())],
        "models": [models[name] for name in sorted(models)],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(table, f, indent=1)
        f.write("\n")


def _write_shingle_set(name, granules, blotches, streaks, seed):
    """
    Asphalt shingle rows (SHINGLE_ROW per row, four rows per repeat, v up the slope from the butt): fine granules, soft
    blotches of darker and lighter granules (the blend of an architectural shingle; the video's roofs read as mottled, not as
    lines), weathering streaks running down the slope (plain 3-tab), a lit edge at the butt, a light fall-off up the row and
    the shadow the next row's butt casts. Averaged by the mipmaps at a distance: the roof turns an even tone instead of
    drawing its rows.
    """
    import numpy as np
    size = TILE_SIZE
    rows = 4
    v = ((np.arange(size) + 0.5) / size * rows % 1.0) * SHINGLE_ROW          # metres from the row's butt, per texel row
    v = np.repeat(v[:, None], size, axis=1)

    def smoothstep(a, b, x):
        t = np.clip((x - a) / (b - a), 0.0, 1.0)
        return t * t * (3.0 - 2.0 * t)

    grain = _periodic_noise(size, seed, 0.35)
    blotch = _periodic_noise(size, seed + 1, 1.9, 3.0)
    mid = _periodic_noise(size, seed + 2, 1.2, 2.0)
    # Streaks down the slope: noise stretched along v (wrapping box blur over rows)
    streak = _periodic_noise(size, seed + 3, 0.6)
    acc = np.zeros_like(streak)
    for k in range(-40, 41):
        acc += np.roll(streak, k, axis=0)
    streak = acc / max(float(acc.std()), 1e-9)
    lit_edge = (1.0 - smoothstep(0.0, 0.006, v)) * 0.06
    fall = (v / SHINGLE_ROW) * 0.06
    shadow = smoothstep(SHINGLE_ROW - 0.03, SHINGLE_ROW, v) ** 1.6 * 0.32
    factor = 1.0 + granules * grain + blotches * blotch + 0.03 * mid + streaks * streak + lit_edge - fall - shadow
    _save_png(os.path.join(TILE_DIR, f"{name}_tone.png"), np.repeat((0.5 * factor)[..., None], 3, axis=-1))
    height = 0.6 * grain + 0.25 * blotch - 6.0 * shadow
    _save_png(os.path.join(TILE_DIR, f"{name}_normal.png"), _normal_from_height(height, 0.05))


def _plane_normals(mesh):
    """The vertices given a normal by preset_faces(normal=...) take it on every face; the others keep the normals they have."""
    attribute = mesh.attributes[PLANE_N]
    planes = [Vector(attribute.data[i].vector) for i in range(len(mesh.vertices))]
    mesh.attributes.remove(attribute)
    corner = [Vector(c.vector) for c in mesh.corner_normals]
    normals = []
    for loop in mesh.loops:
        p = planes[loop.vertex_index]
        normals.append(tuple(p.normalized()) if p.length > 0.5 else tuple(corner[loop.index]))
    for poly in mesh.polygons:
        poly.use_smooth = True
    mesh.normals_split_custom_set(normals)


def preset_layers(bm):
    """The layers preset_faces writes; made before any face is built (adding a layer to a bmesh invalidates its faces)."""
    if bm.loops.layers.uv.get(PRESET_UV) is None:
        bm.loops.layers.uv.new(PRESET_UV)
    if bm.faces.layers.int.get(PRESET_FLAG) is None:
        bm.faces.layers.int.new(PRESET_FLAG)
    if bm.verts.layers.float_vector.get(PLANE_N) is None:
        bm.verts.layers.float_vector.new(PLANE_N)
    return bm


def preset_faces(bm, faces, origin, u_axis, v_axis, v_scale=1.0, v_offset=0.0, normal=None):
    """
    Tiling UVs set by the generator instead of tile_uv's projection: u = (p - origin) . u_axis, v = (p - origin) . v_axis * v_scale
    + v_offset (metres of texture). Shingle rows: v up the slope from each strip's butt, scaled so one exposure is SHINGLE_ROW, so
    the row's shadow in the "shingle" texture sits right under the next butt (tile_uv only adds a random u offset per piece).
    normal: the faces' vertices take this normal (a shingle strip shades like its roof plane).
    """
    uv = bm.loops.layers.uv.get(PRESET_UV)
    flag = bm.faces.layers.int.get(PRESET_FLAG)
    plane = bm.verts.layers.float_vector.get(PLANE_N)
    if uv is None or flag is None or plane is None:
        raise RuntimeError("preset_faces: call preset_layers(bm) before building the faces (a new layer invalidates them)")
    origin, u_axis, v_axis = Vector(origin), Vector(u_axis), Vector(v_axis)
    n = Vector(normal).normalized() if normal is not None else None
    for face in faces:
        face[flag] = 1
        for loop in face.loops:
            d = loop.vert.co - origin
            loop[uv].uv = (d.dot(u_axis), d.dot(v_axis) * v_scale + v_offset)
        if n is not None:
            for vert in face.verts:
                vert[plane] = n


def tile_uv(obj, seed=3):
    """
    UVs in metres for the tiling textures: every face is projected on its own plane with u along the piece's grain (the
    shell's longest bounding box axis, or the next one when that axis is the face's normal), v across it; every piece
    (shell) gets its own random offset so neighbouring boards do not repeat the same part of the texture.
    """
    rng = random.Random(seed)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    layer = bm.loops.layers.uv.new(TILE_UV)
    preset = bm.loops.layers.uv.get(PRESET_UV)
    flag = bm.faces.layers.int.get(PRESET_FLAG)
    axes = [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))]
    for group in shells(bm):
        verts = {v for f in group for v in f.verts}
        lo = [min(v.co[i] for v in verts) for i in range(3)]
        hi = [max(v.co[i] for v in verts) for i in range(3)]
        order = sorted(range(3), key=lambda i: -(hi[i] - lo[i]))
        offset = (rng.uniform(0.0, 20.0), rng.uniform(0.0, 20.0))
        for face in group:
            if flag is not None and face[flag]:
                for loop in face.loops:
                    pu, pv = loop[preset].uv
                    loop[layer].uv = (pu + offset[0], pv)
                continue
            n = face.normal
            u = None
            for i in order:
                candidate = axes[i] - n * axes[i].dot(n)
                if candidate.length > 0.35:
                    u = candidate.normalized()
                    break
            if u is None:
                u = n.orthogonal().normalized()
            v = n.cross(u)
            for loop in face.loops:
                co = loop.vert.co
                loop[layer].uv = (co.dot(u) + offset[0], co.dot(v) + offset[1])
    if preset is not None:
        bm.loops.layers.uv.remove(preset)
    bm.to_mesh(obj.data)
    bm.free()


def _tiled_preview(material, look):
    """Blender preview of a tiling material (contact sheet): tone x colour, the normal map, roughness by the finish."""
    set_name, metres, strength, bump = look["set"], look["metres"], look["strength"], look["bump"]
    nodes, links = material.node_tree.nodes, material.node_tree.links
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    colour = tuple(bsdf.inputs["Base Color"].default_value)
    uv = nodes.new("ShaderNodeUVMap")
    uv.uv_map = TILE_UV
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (1.0 / metres, 1.0 / metres, 1.0)
    links.new(uv.outputs["UV"], mapping.inputs["Vector"])

    def image(map_name):
        node = nodes.new("ShaderNodeTexImage")
        node.image = bpy.data.images.load(os.path.join(TILE_DIR, f"{set_name}_{map_name}.png"), check_existing=True)
        node.image.colorspace_settings.name = "Non-Color"
        links.new(mapping.outputs["Vector"], node.inputs["Vector"])
        return node.outputs["Color"]

    tone = nodes.new("ShaderNodeMath")
    tone.operation = "MULTIPLY"
    tone.inputs[1].default_value = 2.0
    separate = nodes.new("ShaderNodeSeparateColor")
    links.new(image("tone"), separate.inputs["Color"])
    links.new(separate.outputs["Red"], tone.inputs[0])
    mix = nodes.new("ShaderNodeMix")
    mix.data_type = "FLOAT"
    mix.inputs["Factor"].default_value = strength
    mix.inputs["A"].default_value = 1.0
    links.new(tone.outputs["Value"], mix.inputs["B"])
    shade = nodes.new("ShaderNodeMix")
    shade.data_type = "RGBA"
    shade.blend_type = "MULTIPLY"
    shade.inputs["Factor"].default_value = 1.0
    shade.inputs["A"].default_value = colour
    links.new(mix.outputs["Result"], shade.inputs["B"])
    links.new(shade.outputs["Result"], bsdf.inputs["Base Color"])
    normal_map = nodes.new("ShaderNodeNormalMap")
    normal_map.uv_map = TILE_UV
    normal_map.inputs["Strength"].default_value = bump
    links.new(image("normal"), normal_map.inputs["Color"])
    links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])


class Model:
    def __init__(self, name, generator):
        self.name = name
        self.generator = os.path.relpath(generator, ROOT).replace("\\", "/")
        self.parts = []
        self.anchors = []
        self.foliage = set()
        self.tone_jitter = {}
        self.materials = {}
        self.surface_notes = {}
        self.atlas = None          # textured model: info about the baked atlas (written to the spec file)
        self.external_assets = []  # outside assets used (ref, licence, authors, page): written to the spec file
        self.qc = {}               # quality gates (qc.py): holes, z-fighting, thin faces; Builds/QC/<model>.json
        self.surface_materials = {}  # slot name -> registered material (MATERIALS) of the tiled models
        self.tiled = False         # building with tiling textures (finish(tiled=True))
        self.plan_data = None      # the component plan (plan()): written to the spec file and the contact sheet
        self.routes = []           # cables, ropes, pipes that must reach what they join (route())
        self.attachments = []      # points where two parts must meet (attach())
        self.free_parts = set()    # parts allowed to stand apart (part(free=True))
        self.supports = []         # where something outside the model holds it (support())
        self.located = []          # plan components tied to geometry (a part, route, attachment, support or anchor)
        self.feature_data = []     # identity-defining features with their acceptance (features())
        self.bevels = {}           # part -> chamfer width in metres (None: none): Style.py checks the style's chamfer band
        self.unchamfered = {}      # part -> why it has no chamfer on purpose (part(no_chamfer=...))
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene = bpy.context.scene
        scene.unit_settings.system = "METRIC"
        scene.unit_settings.scale_length = 1.0
        scene.unit_settings.length_unit = "METERS"

    def surface(self, kind, hex_color, finish, note, material=None):
        """
        Material slot: name "<Kind>_<RRGGBB>_<finish>" (in Unity it maps to SurfaceLibrary's model finish).

        finish is mandatory and is not derived from the kind: it is chosen by what the part really is and how it looks in the video
        (black plastic cover matte, red baked-paint sheet metal glossy, electrostatically painted steel satin, chrome metallic).
        note: the reason "what it really is; what shows in the video"; written on the contact sheet's material card and in the spec file.
        material: the registered material (MATERIALS) whose texture the surface takes on a tiled model (the rules there).
        """
        if material is not None:
            entry = MATERIALS.get(material)
            if entry is None:
                raise ValueError(f"{kind} {hex_color}: unknown material '{material}' (register it in MATERIALS)")
            if kind not in entry["kinds"]:
                raise ValueError(f"{kind} {hex_color}: material '{material}' is for {entry['kinds']}, not {kind} (rule 1)")
            if entry["owner"] not in (None, self.name):
                raise ValueError(f"{kind} {hex_color}: material '{material}' belongs to the {entry['owner']} model; the same stuff "
                                 f"in another context is its own material (rule 3)")
        if kind not in SURFACE_KINDS:
            raise ValueError(f"Unknown surface kind: {kind}")
        if finish not in FINISHES:
            raise ValueError(f"Finish '{finish}' is invalid; it must be one of: {', '.join(FINISHES)}")
        if not note:
            raise ValueError(f"{kind} {hex_color}: the material's reason (what it really is, what shows in the video) must be written")
        hex_color = hex_color.lstrip("#").upper()
        name = f"{kind}_{hex_color}_{finish}"
        if material is not None:
            if self.surface_materials.get(name, material) != material:
                raise ValueError(f"{name} names two materials: {self.surface_materials[name]} and {material}")
            self.surface_materials[name] = material
        if name in self.materials:
            return self.materials[name]
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        rgb = [srgb_to_linear(int(hex_color[i:i + 2], 16) / 255.0) for i in (0, 2, 4)]
        roughness, metallic = FINISHES[finish]
        bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
        mat.diffuse_color = (*rgb, 1.0)
        self.materials[name] = mat
        self.surface_notes[name] = {"name": name, "finish": finish, "note": note}
        return mat

    def textured_surface(self, name, finish, note, build):
        """
        Source material of a textured model: build(nodes, links, bsdf, uv) builds the Blender nodes; `uv` is the source UV
        output (the source_image, source_normal helpers). Name "Source_<name>_<finish>". finish_textured bakes all source
        materials into the model's single atlas (base colour, normal, AO, roughness).
        """
        if finish not in FINISHES:
            raise ValueError(f"Finish '{finish}' is invalid; it must be one of: {', '.join(FINISHES)}")
        if not note:
            raise ValueError(f"{name}: the material's reason (what it really is, what shows in the video) must be written")
        mname = f"{SOURCE_PREFIX}{name}_{finish}"
        if mname in self.materials:
            return self.materials[mname]
        mat = bpy.data.materials.new(mname)
        if bpy.app.version < (5, 0, 0):
            mat.use_nodes = True
        nodes, links = mat.node_tree.nodes, mat.node_tree.links
        bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
        roughness, metallic = FINISHES[finish]
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
        uv = nodes.new("ShaderNodeUVMap")
        uv.uv_map = SOURCE_UV
        build(nodes, links, bsdf, uv.outputs["UV"])
        self.materials[mname] = mat
        self.surface_notes[mname] = {"name": mname, "finish": finish, "note": note}
        return mat

    def moulded_surface(self, name, rgb, finish, note, rough=None, grain=0.0, tone=0.04, metallic=0.0, grain_scale=900.0):
        """
        Source material for moulded or painted surfaces (plastic, painted metal, rubber parts): the colour sampled from the video
        (sRGB 0-255) with a faint large tone variation (`tone`), a fine surface grain in the bump (`grain` strength), roughness and
        metallic. Baked into the atlas like any textured_surface.
        """
        def build(nodes, links, bsdf, uv):
            coords = nodes.new("ShaderNodeTexCoord")
            noise = nodes.new("ShaderNodeTexNoise")
            noise.inputs["Scale"].default_value = 9.0
            noise.inputs["Detail"].default_value = 3.0
            links.new(coords.outputs["Object"], noise.inputs["Vector"])
            vary = nodes.new("ShaderNodeMapRange")
            vary.inputs["To Min"].default_value = 1.0 - tone
            vary.inputs["To Max"].default_value = 1.0 + tone
            links.new(noise.outputs["Fac"], vary.inputs["Value"])
            color = nodes.new("ShaderNodeMix")
            color.data_type = "RGBA"
            color.blend_type = "MULTIPLY"
            color.inputs["Factor"].default_value = 1.0
            color.inputs["A"].default_value = (*[srgb_to_linear(c / 255.0) for c in rgb], 1.0)
            links.new(vary.outputs["Result"], color.inputs["B"])
            links.new(color.outputs["Result"], bsdf.inputs["Base Color"])
            if rough is not None:
                bsdf.inputs["Roughness"].default_value = rough
            bsdf.inputs["Metallic"].default_value = metallic
            if grain > 0.0:
                fine = nodes.new("ShaderNodeTexNoise")
                fine.inputs["Scale"].default_value = grain_scale
                fine.inputs["Detail"].default_value = 2.0
                links.new(coords.outputs["Object"], fine.inputs["Vector"])
                bump = nodes.new("ShaderNodeBump")
                bump.inputs["Strength"].default_value = grain
                bump.inputs["Distance"].default_value = 0.0004
                links.new(fine.outputs["Fac"], bump.inputs["Height"])
                links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
        return self.textured_surface(name, finish, note, build)

    def painted_wood_surface(self, name, rgb, finish, note, rough=0.8, island_tone=0.03, grain=0.4, photo_tone=(0.9, 1.06),
                             scale=1.2, wood="ambientcg:PaintedWood009C"):
        """
        Painted (or oiled) wood: the colour from the video x a faint tone from a painted-wood photo x a per-piece tone (every
        board, shingle or trim piece is its own mesh island: Random Per Island), grain from the photo's height as bump. Box
        projection in object space, so the grain runs along horizontal boards. The photo is an outside asset (licence-checked).
        """
        height_path = self.external_texture(wood, f"{wood.split(':')[1]}_1K-JPG_Displacement.jpg")
        photo_path = self.external_texture(wood, f"{wood.split(':')[1]}_1K-JPG_Color.jpg")

        def build(nodes, links, bsdf, uv):
            coords = nodes.new("ShaderNodeTexCoord")
            mapping = nodes.new("ShaderNodeMapping")
            mapping.inputs["Scale"].default_value = (scale, scale, scale)
            links.new(coords.outputs["Object"], mapping.inputs["Vector"])

            def image(path, data):
                node = nodes.new("ShaderNodeTexImage")
                node.image = bpy.data.images.load(path, check_existing=True)
                if data:
                    node.image.colorspace_settings.name = "Non-Color"
                node.projection = "BOX"
                node.projection_blend = 0.2
                links.new(mapping.outputs["Vector"], node.inputs["Vector"])
                return node.outputs["Color"]

            photo = nodes.new("ShaderNodeRGBToBW")
            links.new(image(photo_path, False), photo.inputs["Color"])
            tone = nodes.new("ShaderNodeMapRange")
            tone.inputs["From Min"].default_value = 0.35
            tone.inputs["From Max"].default_value = 0.75
            tone.inputs["To Min"].default_value, tone.inputs["To Max"].default_value = photo_tone
            links.new(photo.outputs["Val"], tone.inputs["Value"])
            geometry = nodes.new("ShaderNodeNewGeometry")
            piece = nodes.new("ShaderNodeMapRange")
            piece.inputs["To Min"].default_value = 1.0 - island_tone
            piece.inputs["To Max"].default_value = 1.0 + island_tone
            links.new(geometry.outputs["Random Per Island"], piece.inputs["Value"])
            both = nodes.new("ShaderNodeMath")
            both.operation = "MULTIPLY"
            links.new(tone.outputs["Result"], both.inputs[0])
            links.new(piece.outputs["Result"], both.inputs[1])
            color = nodes.new("ShaderNodeMix")
            color.data_type = "RGBA"
            color.blend_type = "MULTIPLY"
            color.inputs["Factor"].default_value = 1.0
            color.inputs["A"].default_value = (*[srgb_to_linear(c / 255.0) for c in rgb], 1.0)
            links.new(both.outputs["Value"], color.inputs["B"])
            links.new(color.outputs["Result"], bsdf.inputs["Base Color"])
            bsdf.inputs["Roughness"].default_value = rough
            if grain > 0.0:
                bump = nodes.new("ShaderNodeBump")
                bump.inputs["Strength"].default_value = grain
                bump.inputs["Distance"].default_value = 0.003
                links.new(image(height_path, True), bump.inputs["Height"])
                links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
        return self.textured_surface(name, finish, note, build)

    def asphalt_surface(self, name, rgb, finish, note, island_tone=0.1):
        """Asphalt shingles: the colour from the video with fine granules (noise speckle and bump), every shingle a little different."""
        def build(nodes, links, bsdf, uv):
            coords = nodes.new("ShaderNodeTexCoord")
            granules = nodes.new("ShaderNodeTexNoise")
            granules.inputs["Scale"].default_value = 260.0
            granules.inputs["Detail"].default_value = 4.0
            links.new(coords.outputs["Object"], granules.inputs["Vector"])
            speck = nodes.new("ShaderNodeMapRange")
            speck.inputs["To Min"].default_value = 0.85
            speck.inputs["To Max"].default_value = 1.18
            links.new(granules.outputs["Fac"], speck.inputs["Value"])
            geometry = nodes.new("ShaderNodeNewGeometry")
            piece = nodes.new("ShaderNodeMapRange")
            piece.inputs["To Min"].default_value = 1.0 - island_tone
            piece.inputs["To Max"].default_value = 1.0 + island_tone
            links.new(geometry.outputs["Random Per Island"], piece.inputs["Value"])
            both = nodes.new("ShaderNodeMath")
            both.operation = "MULTIPLY"
            links.new(speck.outputs["Result"], both.inputs[0])
            links.new(piece.outputs["Result"], both.inputs[1])
            color = nodes.new("ShaderNodeMix")
            color.data_type = "RGBA"
            color.blend_type = "MULTIPLY"
            color.inputs["Factor"].default_value = 1.0
            color.inputs["A"].default_value = (*[srgb_to_linear(c / 255.0) for c in rgb], 1.0)
            links.new(both.outputs["Value"], color.inputs["B"])
            links.new(color.outputs["Result"], bsdf.inputs["Base Color"])
            bsdf.inputs["Roughness"].default_value = 0.9
            bump = nodes.new("ShaderNodeBump")
            bump.inputs["Strength"].default_value = 0.35
            bump.inputs["Distance"].default_value = 0.0015
            links.new(granules.outputs["Fac"], bump.inputs["Height"])
            links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
        return self.textured_surface(name, finish, note, build)

    def anchor(self, name, unity_point):
        """Connection point (in Unity axes): written to the spec file, the Unity test compares it with its in-game counterpart."""
        self.anchors.append({"name": name, "position": _vec(unity_point)})

    def plan(self, purpose, sources, components, supports=("ground",), tier="complex", category=()):
        """
        The component plan, written at the top of the generator before any geometry (.claude/skills/model-plausibility):
        what the object is for, where its design comes from, and for every important component what it does, what holds it,
        whether it moves and whether its form was seen or guessed. Decorative details are fine; a detail that suggests a
        function (a button, a cable, a latch) has to have it.
        purpose: what the object is and how it is used, one sentence.
        sources: [(kind, where)]: kind video | image | model | text | web; where: frame times, a file, the user's words, a page.
        components: [(name, role, job, attaches_to, moves, source)]:
          role functional | structural | decorative; job: what it does (or, if decorative, why it is there);
          attaches_to: [names of other components or of `supports`];
          moves fixed | hinge | slide | spin | flex | free; source seen | guess | real (from real-world references).
        supports: what holds the whole object from outside ("ground", "hands", "branch", "wall" ...).
        tier: "simple" (the gates and one look at the contact sheet) or "complex" (also a preview and an independent review).
        category: which guidance applies (PLAN_CATEGORIES; the skill's categories/<name>.md, given to the reviewer).
        Raises at once on unknown words, a component attached to nothing, or one with no load path to a support.
        """
        problems = []
        if tier not in PLAN_TIERS:
            problems.append(f"tier '{tier}' is not one of {PLAN_TIERS}")
        category = (category,) if isinstance(category, str) else tuple(category)
        for c in category:
            if c not in PLAN_CATEGORIES:
                problems.append(f"category '{c}' is not one of {PLAN_CATEGORIES}")
        for kind, _ in sources:
            if kind not in PLAN_SOURCE_KINDS:
                problems.append(f"source kind '{kind}' is not one of {PLAN_SOURCE_KINDS}")
        names = [c[0] for c in components]
        duplicates = sorted({n for n in names if names.count(n) > 1})
        if duplicates:
            problems.append(f"components named twice: {duplicates}")
        known = set(names) | set(supports)
        edges = {n: set() for n in known}
        for name, role, job, attaches, moves, source in components:
            if role not in PLAN_ROLES:
                problems.append(f"{name}: role '{role}' is not one of {PLAN_ROLES}")
            if moves not in PLAN_MOVES:
                problems.append(f"{name}: moves '{moves}' is not one of {PLAN_MOVES}")
            if source not in PLAN_SEEN:
                problems.append(f"{name}: source '{source}' is not one of {PLAN_SEEN}")
            if not job.strip():
                problems.append(f"{name}: no job (what it does, or why a decorative detail is there)")
            if not attaches:
                problems.append(f"{name}: attached to nothing")
            for other in attaches:
                if other not in known:
                    problems.append(f"{name}: attached to '{other}', which is neither a component nor a support")
                else:
                    edges[name].add(other)
                    edges[other].add(name)
        held, stack = set(supports), list(supports)
        while stack:
            for other in edges.get(stack.pop(), ()):
                if other not in held:
                    held.add(other)
                    stack.append(other)
        loose = [n for n in names if n not in held]
        if loose:
            problems.append(f"no load path to {list(supports)} from: {loose}")
        if problems:
            raise ValueError(f"{self.name}: plan: " + "; ".join(problems))
        self.plan_data = {
            "purpose": purpose, "tier": tier, "category": list(category), "supports": list(supports),
            "sources": [{"kind": k, "where": w} for k, w in sources],
            "components": [{"name": n, "role": r, "job": j, "attaches": list(a), "moves": m, "source": s}
                           for n, r, j, a, m, s in components],
        }

    def features(self, items):
        """
        The features that make the object what it is, each with its own acceptance (after the per-feature review of
        img2threejs: a convincing whole must not hide a missing control or a wrong attachment). The plan says what every
        component does; a feature says which relationship must be seen to hold.
        items: [(id, tier, components, expect, measure, view)]:
          tier critical | important | optional;
          components: plan component names; expect: the relationship or behaviour that must hold;
          measure: "route:<name>" | "attach:<name>" | "support:<name>" (a glob, e.g. "route:Downspout_*") or None (visual
          only); view: the contact-sheet view that shows it, or None.
        The build sets `measured` (pass/fail) from the construction gate; the reviewer must give every critical and
        important feature a verdict (pass, fail, unverified). A critical feature counts only when measured (if measurable)
        and seen to pass: unverified is never passed (Review.py state).
        """
        problems = []
        names = {c["name"] for c in (self.plan_data or {}).get("components", [])}
        if not names:
            problems.append("features need a plan (model.plan first)")
        out = []
        for fid, tier, components, expect, measure, view in items:
            if tier not in FEATURE_TIERS:
                problems.append(f"{fid}: tier '{tier}' is not one of {FEATURE_TIERS}")
            unknown = [c for c in components if c not in names]
            if unknown:
                problems.append(f"{fid}: components not in the plan: {unknown}")
            if measure and measure.split(":")[0] not in ("route", "attach", "support"):
                problems.append(f"{fid}: measure '{measure}' is not route:/attach:/support:<name>")
            if not expect.strip():
                problems.append(f"{fid}: no expectation")
            out.append({"id": fid, "tier": tier, "components": list(components), "expect": expect, "measure": measure,
                        "view": view, "measured": None})
        if problems:
            raise ValueError(f"{self.name}: features: " + "; ".join(problems))
        self.feature_data = out

    def _measure_features(self, problems, views=None):
        """Each feature's measured result from the construction gate's problems; unknown names or views are problems."""
        import fnmatch
        declared = {"route": [r["name"] for r in self.routes], "attach": [a["name"] for a in self.attachments],
                    "support": [s["name"] for s in self.supports]}
        labels = {"route": "route", "attach": "attachment", "support": "support"}
        extra = []
        for feature in self.feature_data:
            if feature["measure"]:
                kind, pattern = feature["measure"].split(":", 1)
                hits = fnmatch.filter(declared[kind], pattern)
                if not hits:
                    extra.append(f"feature {feature['id']}: no {kind} matches '{pattern}'")
                    feature["measured"] = "fail"
                    continue
                failing = [h for h in hits if any(f"{labels[kind]} '{h}'" in p for p in problems)]
                feature["measured"] = "fail" if failing else "pass"
            if views is not None and feature["view"] and feature["view"] not in {v["file"] for v in views}:
                extra.append(f"feature {feature['id']}: no view '{feature['view']}' on the contact sheet")
        return extra

    def route(self, name, points, tol=0.005, free=(), unity=False, part=None, ends=None, component=None):
        """
        A cable, rope, pipe or rod that runs from one thing to another: `points` lie on its centreline (its two ends and any
        clip or guide on the way). Checked at finish: one piece passes within `tol` of every point (tol > its radius) and
        each end not listed in `free` (indices of points on things outside the model) touches another piece.
        part: the piece must belong to this part (a cable of the Handle, not some other piece that happens to pass there);
        ends: (part at the first point, part at the last point) its ends must touch; component: its name in the plan.
        """
        pts = [_to_blender(p) if unity else Vector(p) for p in points]
        self.routes.append({"name": name, "points": pts, "tol": tol, "free": tuple(free), "part": part,
                            "ends": tuple(ends) if ends else None, "component": component or name})

    def attach(self, name, point, tol=0.004, unity=False, parts=None, component=None):
        """
        A point where two pieces must meet (a hinge pin, a clip, a bracket, a bolt): checked at finish. parts: the two
        parts that must meet there (otherwise any two nearby pieces count); component: its name in the plan.
        """
        self.attachments.append({"name": name, "point": _to_blender(point) if unity else Vector(point), "tol": tol,
                                 "parts": tuple(parts) if parts else None, "component": component or name})

    def support(self, name, points, tol=0.02, unity=False, component=None):
        """
        Where something outside the model holds it: the plan's support `name` ("hands", "branch", "wheels") acts at these
        points. The construction gate counts the pieces there as held (like the ground), so a model is one assembly held by
        its supports, not merely one connected lump; every point must touch the model. Each plan support other than
        "ground" needs one (or, for models whose parts are assembled in game, finish(ao_together=False), it is not checked).
        """
        pts = [_to_blender(p) if unity else Vector(p) for p in points]
        self.supports.append({"name": name, "points": pts, "tol": tol, "component": component})

    def _gate_construction(self, ground, separate=False, contact=0.003, raise_errors=True, views=None):
        """
        Construction gate (qc.connectivity, qc.check_links): every piece is held by the others or the ground (no part
        floating in mid-air), every declared route reaches what it joins, every declared attachment meets. Leaves and
        parts made with free=True are left out.
        """
        solid = [obj for obj, _ in self.parts if obj.name not in self.foliage and obj.name not in self.free_parts]
        groups = [[obj] for obj in solid] if separate else [solid]
        result = {"shells": 0, "components": 0, "stray": [], "routes": len(self.routes),
                  "attachments": len(self.attachments), "supports": len(self.supports), "problems": []}
        problems = []
        # The plan's supports must be where the geometry is held (combined models; parts assembled in game are not)
        declared = {s["name"] for s in self.supports}
        if self.plan_data and not separate:
            for name in self.plan_data["supports"]:
                if name == "ground" and ground is None:
                    problems.append("the plan stands it on the ground but finish(ground=...) is not set")
                elif name != "ground" and name not in declared:
                    problems.append(f"the plan's support '{name}' is not located (model.support)")
        held = [(p, s["tol"]) for s in self.supports for p in s["points"]] if not separate else None
        for group in groups:
            if not group:
                continue
            r = qc.connectivity(group, tol=contact, ground=ground, supports=held)
            result["shells"] += r["shells"]
            result["components"] += r["components"]
            result["stray"] += r["stray"]
            if r.get("floating"):
                problems.append(r["floating"])
        problems += qc.check_links(solid, self.routes, self.attachments, self.supports) if solid else []
        # Plan components tied to geometry; links must name components that exist
        if self.plan_data:
            names = {c["name"] for c in self.plan_data["components"]}
            tied = ({obj.name for obj, _ in self.parts} | {r["component"] for r in self.routes}
                    | {a["component"] for a in self.attachments} | {a["name"] for a in self.anchors}
                    | {s["component"] for s in self.supports if s["component"]})
            self.located = sorted(names & tied)
            for item in self.routes + self.attachments:
                if item["component"] not in names:
                    problems.append(f"'{item['name']}' names the component '{item['component']}', which the plan "
                                    f"does not have (component=...)")
        problems += self._measure_features(problems, views)
        result["problems"] = problems
        result["stray"] = result["stray"][:20]
        floating = len(result["stray"])
        self.qc["construction"] = result
        log(f"{self.name}: QC construction: {floating} pieces held by nothing ({result['shells']} shells); links: "
            f"{result['routes']} routes, {result['attachments']} attachments, {len(result['problems'])} failing")
        if (floating or result["problems"]) and raise_errors:
            self._write_qc()
            raise RuntimeError(f"{self.name}: QC construction: {floating} pieces held by nothing (object, shells, tris, "
                               f"Unity centre, size mm): {result['stray'][:8]}; {'; '.join(result['problems'])}")
        return result

    def part(self, name, bm, materials, location=(0.0, 0.0, 0.0), closed=True, bevel=None, smooth=True, sharp=60.0,
             unity=False, cutters=None, weighted=True, foliage=False, tone_jitter=0.0, ao_grid=None, free=False,
             no_chamfer=""):
        """
        Builds a part (object) from a bmesh.
        free: the part may stand apart from the rest (the calibration markers); every other part must be held by the others
        no_chamfer: why this part has no chamfer on purpose (a cord, a round tube with hidden ends); the style's chamfer check
            (Style.py, rule edges.chamfer) then skips it instead of reporting it
        or the ground (the construction gate).
        tone_jitter: the tone of every separate shell (board, shingle tab) varies randomly by this fraction (baked into the vertex colour).
        ao_grid: (x, y, z) metres (None = no cut on that axis; Unity axes if unity=True): long faces are split at these
        intervals. AO is baked into the vertices; if a 3 m board only has its end vertices, the darkness of an end under the trim
        spreads over the whole board (the shed siding and door panels went dark like that).
        foliage: leaves: double-sided open surfaces (no closedness and winding check, no bevel); the vertex
        normals become the directions in the generator's "dir" layer (outwards from the cluster centre: the crown takes light like a single volume).
        unity: the bmesh (and cutters) were written in Unity axes; converted to Blender axes, location is in Unity too.
        cutters: [bmesh, ...] cutters; subtracted from the part (boolean difference, exact solver). The cutter's face material index
        goes to the cut surface.
        bevel: {"width": m, "segments": n, "angle": degrees} edge rounding (edges sharper than the threshold angle are rounded).
        smooth: smooth shading + normals weighted by face area (flat faces stay flat, rounded edges
        catch the light softly). Edges still sharper than `sharp` degrees after rounding are marked sharp;
        otherwise the normals of the two faces blend and the face shades as if it faced the wrong way.
        """
        if foliage:
            closed, bevel, smooth = False, None, False
        directions = bm.verts.layers.float_vector.get("dir") if foliage else None
        if foliage and directions is None:
            raise ValueError(f"{name}: the leaf part has no 'dir' normal layer (foliage_normals)")
        if ao_grid:
            grid_cut(bm, ao_grid)
        if unity:
            bmesh.ops.transform(bm, matrix=UNITY_TO_BLENDER, verts=bm.verts)
            location = (-location[0], -location[2], location[1])
            if directions is not None:
                rotation = UNITY_TO_BLENDER.to_3x3()
                for v in bm.verts:
                    v[directions] = rotation @ Vector(v[directions])
            planes = bm.verts.layers.float_vector.get(PLANE_N)
            if planes is not None:
                rotation = UNITY_TO_BLENDER.to_3x3()
                for v in bm.verts:
                    v[planes] = rotation @ Vector(v[planes])
        if not foliage:
            finish_shell(bm)   # on leaves the two faces already face opposite ways; not a shell
        canonical_order(bm)
        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)
        bm.free()
        for mat in materials:
            mesh.materials.append(mat)
        obj = bpy.data.objects.new(name, mesh)
        obj.location = location
        bpy.context.scene.collection.objects.link(obj)
        if foliage:
            attribute = mesh.attributes["dir"]
            normals = [tuple(Vector(attribute.data[i].vector).normalized()) for i in range(len(mesh.vertices))]
            mesh.attributes.remove(attribute)
            for poly in mesh.polygons:
                poly.use_smooth = True
            mesh.normals_split_custom_set_from_vertices(normals)
            self.foliage.add(name)
        if free:
            self.free_parts.add(name)
        if tone_jitter > 0.0:
            self.tone_jitter[name] = tone_jitter
        for index, cutter_bm in enumerate(cutters or []):
            if unity:
                bmesh.ops.transform(cutter_bm, matrix=UNITY_TO_BLENDER, verts=cutter_bm.verts)
            bmesh.ops.translate(cutter_bm, vec=-Vector(location), verts=cutter_bm.verts)
            finish_shell(cutter_bm)
            cutter_mesh = bpy.data.meshes.new(f"{name}_cutter{index}")
            cutter_bm.to_mesh(cutter_mesh)
            cutter_bm.free()
            cutter = bpy.data.objects.new(cutter_mesh.name, cutter_mesh)
            cutter.location = location
            bpy.context.scene.collection.objects.link(cutter)
            mod = obj.modifiers.new("Carve", "BOOLEAN")
            mod.operation = "DIFFERENCE"
            mod.solver = "EXACT"
            mod.object = cutter
            self._apply_modifiers(obj)
            bpy.data.objects.remove(cutter)
            bpy.data.meshes.remove(cutter_mesh)
        if bevel and no_chamfer:
            raise ValueError(f"{name}: a bevel and no_chamfer together")
        self.bevels[name] = bevel["width"] if bevel else None
        if no_chamfer:
            self.unchamfered[name] = no_chamfer
        if bevel:
            mod = obj.modifiers.new("Bevel", "BEVEL")
            mod.width = bevel["width"]
            mod.segments = bevel.get("segments", 2)
            mod.limit_method = "ANGLE"
            mod.angle_limit = math.radians(bevel.get("angle", 30.0))
            mod.use_clamp_overlap = True
            mod.miter_outer = "MITER_ARC"
            self._apply_modifiers(obj)
            # Inner corners where three rounded edges meet can leave crushed (zero-area) faces: dissolve them
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges[:])
            bm.to_mesh(obj.data)
            bm.free()
        if smooth:
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            bm.normal_update()
            limit = math.radians(sharp)
            for face in bm.faces:
                face.smooth = True
            for edge in bm.edges:
                if len(edge.link_faces) == 2 and edge.calc_face_angle(0.0) > limit:
                    edge.smooth = False
            bm.to_mesh(obj.data)
            bm.free()
            if weighted:
                # Hard parts: flat faces stay flat, chamfers catch the light. Off on soft shells (housing):
                # with wide and narrow rings side by side the area weighting spoils the normals and the shine shows a sawtooth
                mod = obj.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL")
                mod.mode = "FACE_AREA"
                mod.weight = 50
                mod.keep_sharp = True
                self._apply_modifiers(obj)
        canonical_mesh(obj.data)   # (also for parts that had no modifier to apply)
        if PLANE_N in obj.data.attributes:
            _plane_normals(obj.data)
        self.parts.append((obj, closed))
        return obj

    @staticmethod
    def _external_record(ref, folder=None):
        """Folder and asset.json of an outside asset; refuses a missing record or a licence outside EXTERNAL_LICENCES."""
        source, _, asset_id = ref.partition(":")
        safe_id = re.sub(r"[^A-Za-z0-9._-]+", "_", asset_id)
        folder = folder or os.path.join(EXTERNAL_DIR, source, safe_id)
        record_path = os.path.join(folder, "asset.json")
        if not os.path.exists(record_path):
            raise RuntimeError(f"{ref}: {os.path.relpath(record_path, ROOT)} is missing; fetch the asset with "
                               f"tools/Assets.ps1 -Get {ref}")
        with open(record_path, encoding="utf-8") as f:
            record = json.load(f)
        if record.get("licence") not in EXTERNAL_LICENCES:
            raise RuntimeError(f"{ref}: licence {record.get('licence')} ({record.get('licence_note', '')}) is not allowed "
                               f"for the game; allowed: {', '.join(EXTERNAL_LICENCES)}")
        return folder, safe_id, record

    def external_texture(self, ref, file):
        """
        Path of an outside texture (an image in an asset fetched with tools/Assets.ps1) for a source material: the licence is
        checked like external(), and the asset is written to the spec's "external" list (part "(texture)").
        """
        folder, _, record = self._external_record(ref)
        path = os.path.join(folder, file)
        if not os.path.exists(path):
            raise RuntimeError(f"{ref}: no {file} in {os.path.relpath(folder, ROOT)}")
        if not any(e["ref"] == ref for e in self.external_assets):
            self.external_assets.append({
                "ref": ref, "part": "(texture)", "name": record.get("name", ref), "licence": record["licence"],
                "authors": [a for a in record.get("authors") or [] if a], "page": record.get("page_url", ""),
                "attributionRequired": bool(record.get("attribution_required")), "file": file,
            })
        return path

    def external(self, ref, finish, note, size=None, axis="max", budget=None, file=None, name=None,
                 location=(0.0, 0.0, 0.0), turn=0.0, sharp=50.0, folder=None):
        """
        Imports an outside asset fetched with tools/Assets.ps1 (free-assets) as one part of a textured model.
        ref: "<source>:<id>"; the files are in tools/blender/external/<source>/<id>/ (or `folder`), next to asset.json.
        - Licence: asset.json's licence must be one of EXTERNAL_LICENCES; it goes into the spec file ("external") so the
          Unity test can check credits.
        - Shape: every mesh of the file is joined into one part with its transforms applied, turned `turn` degrees about
          Z (the model's front is -Y; glTF assets facing +Z arrive facing -Y already), scaled so `axis` ("x", "y", "z"
          in Blender axes, or "max") measures `size` m (measured from the video; None keeps the asset's own size),
          centred on X/Y with its bottom at z = 0 and moved to `location` (Blender axes).
        - budget: triangles; the part is decimated (collapse) down to it.
        - Shading: the asset's own normals are dropped; smooth shading with edges sharper than `sharp` degrees split,
          like the generated parts.
        - Materials: the asset's materials become source materials "Source_<id>_<n>_<finish>" sampling SOURCE_UV, so
          finish_textured bakes them into the model's single atlas like any generated source. `note` says what the
          part really is and why this asset (the reason every surface needs).
        """
        folder, safe_id, record = self._external_record(ref, folder)
        asset_id = ref.partition(":")[2]
        if not note:
            raise ValueError(f"{ref}: the reason (what the part really is, why this asset) must be written")
        if file is None:
            found = [os.path.relpath(os.path.join(r, n), folder) for r, _, names in os.walk(folder) for n in names
                     if os.path.splitext(n)[1].lower() in EXTERNAL_FORMATS]
            if not found:
                raise RuntimeError(f"{ref}: no {'/'.join(EXTERNAL_FORMATS)} file in {folder}")
            found.sort(key=lambda p: (EXTERNAL_FORMATS.index(os.path.splitext(p)[1].lower()), len(p), p))
            file = found[0]
        path = os.path.join(folder, file)

        before = set(bpy.data.objects)
        extension = os.path.splitext(path)[1].lower()
        if extension in (".glb", ".gltf"):
            bpy.ops.import_scene.gltf(filepath=path)
        elif extension == ".fbx":
            bpy.ops.import_scene.fbx(filepath=path)
        else:
            bpy.ops.wm.obj_import(filepath=path, forward_axis="NEGATIVE_Z", up_axis="Y")
        new = [o for o in bpy.data.objects if o not in before]
        meshes = [o for o in new if o.type == "MESH" and len(o.data.polygons)]
        if not meshes:
            raise RuntimeError(f"{ref}: {file} has no mesh")
        bpy.context.view_layer.update()
        for o in meshes:
            if o.data.users > 1:
                o.data = o.data.copy()
            world = o.matrix_world.copy()
            o.parent = None
            o.data.transform(world)
            o.matrix_world = Matrix.Identity(4)
        for o in new:
            if o not in meshes:
                bpy.data.objects.remove(o)
        bpy.ops.object.select_all(action="DESELECT")
        for o in meshes:
            o.select_set(True)
        bpy.context.view_layer.objects.active = meshes[0]
        if len(meshes) > 1:
            bpy.ops.object.join()
        obj = bpy.context.view_layer.objects.active
        obj.name = obj.data.name = name or f"Ext_{safe_id}"
        mesh = obj.data

        # One UV map: the asset's first, renamed to the source UV the bake reads
        names = [layer.name for layer in mesh.uv_layers]
        if not names:
            raise RuntimeError(f"{ref}: the mesh has no UVs, its textures cannot be baked")
        for extra in names[1:]:
            mesh.uv_layers.remove(mesh.uv_layers[extra])
        mesh.uv_layers[0].name = SOURCE_UV

        bm = bmesh.new()
        bm.from_mesh(mesh)
        if turn:
            bmesh.ops.rotate(bm, verts=bm.verts, cent=(0.0, 0.0, 0.0), matrix=Matrix.Rotation(math.radians(turn), 3, "Z"))
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
        bmesh.ops.dissolve_degenerate(bm, dist=1e-7, edges=bm.edges[:])
        bmesh.ops.delete(bm, geom=[e for e in bm.edges if not e.link_faces], context="EDGES")
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
        bm.to_mesh(mesh)
        bm.free()

        triangles = sum(len(p.vertices) - 2 for p in mesh.polygons)
        if budget and triangles > budget:
            mod = obj.modifiers.new("Decimate", "DECIMATE")
            mod.ratio = 0.98 * budget / triangles
            mod.use_collapse_triangulate = True
            self._apply_modifiers(obj)
            mesh = obj.data

        if mesh.has_custom_normals:
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.mesh.customdata_custom_splitnormals_clear()
        # Size and place after decimating (collapsing moves the extreme vertices a little)
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.dissolve_degenerate(bm, dist=1e-7, edges=bm.edges[:])
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
        lo = Vector([min(v.co[i] for v in bm.verts) for i in range(3)])
        hi = Vector([max(v.co[i] for v in bm.verts) for i in range(3)])
        if size:
            dims = hi - lo
            measured = max(dims) if axis == "max" else dims["xyz".index(axis)]
            factor = size / measured
            bmesh.ops.scale(bm, vec=(factor, factor, factor), verts=bm.verts)
            lo, hi = lo * factor, hi * factor
        bmesh.ops.translate(bm, vec=(-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z), verts=bm.verts)
        bm.normal_update()
        limit = math.radians(sharp)
        for face in bm.faces:
            face.smooth = True
        for edge in bm.edges:
            edge.smooth = not (len(edge.link_faces) == 2 and edge.calc_face_angle(0.0) > limit)
        bm.to_mesh(mesh)
        bm.free()

        credit = f"{record['name']} by {', '.join(a for a in record.get('authors') or [] if a) or 'unknown'}"
        for index, mat in enumerate(mesh.materials):
            if mat is None:
                raise RuntimeError(f"{ref}: material slot {index} is empty")
            mat.name = f"{SOURCE_PREFIX}{safe_id}_{index}_{finish}"
            if finish not in FINISHES:
                raise ValueError(f"Finish '{finish}' is invalid; it must be one of: {', '.join(FINISHES)}")
            nodes, links = mat.node_tree.nodes, mat.node_tree.links
            uv = None
            for node in list(nodes):
                if node.type == "UVMAP":
                    node.uv_map = SOURCE_UV
                elif node.type == "NORMAL_MAP":
                    node.uv_map = SOURCE_UV
                elif node.type == "TEX_IMAGE" and not node.inputs["Vector"].is_linked:
                    if uv is None:
                        uv = nodes.new("ShaderNodeUVMap")
                        uv.uv_map = SOURCE_UV
                    links.new(uv.outputs["UV"], node.inputs["Vector"])
            self.materials[mat.name] = mat
            self.surface_notes[mat.name] = {"name": mat.name, "finish": finish,
                                            "note": f"{note} (outside asset {ref}: {credit}, {record['licence']})"}
        obj.location = location
        self.external_assets.append({
            "ref": ref, "part": obj.name, "name": record.get("name", asset_id), "licence": record["licence"],
            "authors": [a for a in record.get("authors") or [] if a], "page": record.get("page_url", ""),
            "attributionRequired": bool(record.get("attribution_required")), "file": file.replace("\\", "/"),
        })
        log(f"{ref}: {file} -> {obj.name}, {sum(len(p.vertices) - 2 for p in mesh.polygons)} tris, {record['licence']}")
        self.parts.append((obj, False))
        return obj

    @staticmethod
    def _apply_modifiers(obj):
        if not obj.modifiers:
            return
        depsgraph = bpy.context.evaluated_depsgraph_get()
        evaluated = obj.evaluated_get(depsgraph)
        mesh = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=depsgraph)
        old = obj.data
        # Boolean can add the cutter's (materialless) slots as empty ones: the part's own list is written back.
        # Clearing the slots resets the face indices, so the indices are saved first and written back afterwards.
        materials = list(old.materials)
        indices = [min(poly.material_index, len(materials) - 1) for poly in mesh.polygons]
        mesh.materials.clear()
        for material in materials:
            mesh.materials.append(material)
        mesh.polygons.foreach_set("material_index", indices)
        mesh.update()
        obj.modifiers.clear()
        obj.data = mesh
        mesh.name = obj.name
        bpy.data.meshes.remove(old)
        canonical_mesh(mesh)   # modifiers (bevel, booleans) order their output their own way: the same model, the same order

    # ----------------------------------------------------------------------------------------------------------

    def _gate_overlaps(self, separate=False):
        """z-fighting gate: overlapping coplanar faces stop the build (separate: each part checked on its own)."""
        groups = [[obj] for obj, _ in self.parts] if separate else [[obj for obj, _ in self.parts]]
        total, pairs, worst = 0.0, 0, []
        for group in groups:
            t, n, w = coplanar_overlaps(group, limit=100000)
            total, pairs, worst = total + t, pairs + n, worst + w
        worst.sort(key=lambda x: -x[0])
        self.qc["zFighting"] = {"pairs": pairs, "cm2": round(total * 1e4, 2)}
        if pairs:
            lines = [f"{a * 1e4:.2f} cm² {first} <-> {second} Unity {tuple(round(c, 3) for c in where)}"
                     for a, first, second, where in worst[:20]]
            self._write_qc()
            raise RuntimeError(f"{self.name}: QC z-fighting: {pairs} pairs, {total * 1e4:.1f} cm² of overlapping faces\n  "
                               + "\n  ".join(lines))

    def _gate_holes(self, ground, separate=False):
        """Hole gate (qc.audit_holes): close cameras all over the model; any back face seen first stops the build."""
        solid = [obj for obj, _ in self.parts if obj.name not in self.foliage]
        groups = [[obj] for obj in solid] if separate else [solid]
        result = {"cameras": 0, "rays": 0, "backface_hits": 0, "hole_points": 0, "edge_grazes": 0, "regions": []}
        examples = []
        for group in groups:
            details = []
            r = qc.audit_holes(group, ground=ground, details=details)
            for key in ("cameras", "rays", "backface_hits", "hole_points", "edge_grazes"):
                result[key] += r[key]
            result["regions"] += [[group[0].name] + list(region) for region in r["regions"]]
            for point, _, eye, dot in details[:6]:
                examples.append({"part": group[0].name, "unity": [round(c, 4) for c in to_unity(point)],
                                 "eye": [round(c, 3) for c in to_unity(eye)], "dot": round(dot, 3)})
        result["examples"] = examples
        self.qc["holes"] = result
        log(f"{self.name}: QC holes: {result['backface_hits']} back-face hits at {result['hole_points']} points "
            f"({result['cameras']} cameras, {result['rays']} rays, {result['edge_grazes']} edge grazes dropped)")
        if result["backface_hits"]:
            self._write_qc()
            raise RuntimeError(f"{self.name}: QC holes: back faces visible at {result['hole_points']} points; the largest "
                               f"regions (part, Unity xyz, hits): {result['regions'][:12]}; examples {examples[:6]}")

    def _gate_joints(self, separate=False):
        """
        Joint gate (qc.joint_audit): a member's end that crosses the face it meets at an angle (part poking through, part leaving a
        wedge: the porch's square-cut rake boards, 21 October 2026) stops the build.
        """
        solid = [obj for obj, _ in self.parts if obj.name not in self.foliage]
        groups = [[obj] for obj in solid] if separate else [solid]
        result = {"members": 0, "ends": 0, "bad": 0, "worst": []}
        for group in groups:
            r = qc.joint_audit(group)
            for key in ("members", "ends", "bad"):
                result[key] += r[key]
            result["worst"] += r["worst"]
        result["worst"] = result["worst"][:12]
        self.qc["joints"] = result
        log(f"{self.name}: QC joints: {result['bad']} member ends not sitting on what they meet "
            f"({result['members']} members, {result['ends']} ends checked)")
        if result["bad"]:
            self._write_qc()
            raise RuntimeError(f"{self.name}: QC joints: {result['bad']} ends cut at the wrong angle for what they meet "
                               f"(part, Unity xyz, angle, mm in front, mm behind): {result['worst']}")

    def _write_qc(self):
        qc.write_report(ROOT, self.name, self.qc)

    def _join(self, parts, name):
        """Joins the parts into one object of that name; returns (object, closed)."""
        closed_all = all(c for _, c in parts)
        bpy.ops.object.select_all(action="DESELECT")
        for obj, _ in parts:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = parts[0][0]
        bpy.ops.object.join()
        joined = bpy.context.view_layer.objects.active
        joined.name = joined.data.name = name
        return joined, closed_all

    def _preview(self, views, references, budget, total_budget, ground, separate, contact, join_name, apart=()):
        """Models.ps1 -Preview: the cheap checks, then labelled renders into Builds/Models/<name>_preview (no FBX, no spec)."""
        self.drop_unused_slots()
        stats = self.validate(budget, total_budget)
        construction = self._gate_construction(ground, separate=separate, contact=contact, raise_errors=False, views=views)
        static = [(o, c) for o, c in self.parts if o.name not in apart]
        kept = [(o, c) for o, c in self.parts if o.name in apart]   # taken before the join removes the other objects
        if join_name and len(static) > 1:
            self.parts = [self._join(static, join_name)] + kept
        if views:
            self.render(views, references or [], folder=self.name + "_preview")
        preview = {"model": self.name, "preview": True, "objects": stats, "anchors": self.anchors,
                   "surfaces": [self.surface_notes[n] for n in self.materials], "plan": self.plan_data,
                   "qc": {"construction": construction}, "links": self._links_spec(), "located": self.located,
                   "features": self.feature_data}
        preview.update(self._fingerprints())
        del preview["asset"]   # no UVs or textures yet: a preview has a structure, not an asset
        with open(os.path.join(RENDER_DIR, self.name + "_preview", "spec.json"), "w", encoding="utf-8") as f:
            json.dump(preview, f, ensure_ascii=False, indent=2)
        log(f"{self.name}: preview, {len(self.parts)} parts, " + ", ".join(f"{s['name']} {s['triangles']} tris" for s in stats))

    def finish(self, views=None, references=None, budget=None, ao_distance=0.08, ao_together=True, ground=None, join=None,
               tiled=False, total_budget=None, contact=0.003):
        """
        Validates, bakes the ambient occlusion (AO) into the vertex colour, writes the FBX and the spec file, renders the
        contact sheet views. Quality gates (a failure stops the build): z-fighting 0, holes 0, joints 0 (`ground`: world z below which no
        inspection camera goes), construction (nothing held by nothing within `contact` metres; routes and attachments).
        budget: triangles per object; total_budget: triangles of the whole model.
        With OPUS_PREVIEW=1 (Models.ps1 -Preview) only the cheap checks and the renders run (_preview).
        join: joins all parts into one object of that name (one mesh, a material per surface).
        tiled: buildings; UVs in metres along each piece's grain (tile_uv) and the tiling textures of Models/Tiling
        (write_tile_sets) instead of an atlas: sharp at any distance, no seams to bleed; AO and the per-piece tone stay in the
        vertex colour, a colour variant only changes the material colour.
        """
        if PREVIEW:
            return self._preview(views, references, budget, total_budget, ground, not ao_together, contact, join)
        self.drop_unused_slots()
        self.validate(budget, total_budget)
        self._gate_overlaps(separate=not ao_together)
        self._gate_construction(ground, separate=not ao_together, contact=contact, views=views)
        if join and len(self.parts) > 1:
            self.parts = [self._join(self.parts, join)]
        self._gate_holes(ground, separate=not ao_together)
        self._gate_joints(separate=not ao_together)
        if tiled:
            used = sorted({slot.name for obj, _ in self.parts for slot in obj.data.materials if slot})
            missing = [name for name in used if name not in self.surface_materials]
            if missing:
                raise RuntimeError(f"{self.name}: surfaces without a material (rule 1; Model.surface(material=...)): {missing}")
            write_tile_sets(self)
            for obj, _ in self.parts:
                tile_uv(obj)
            for name, material in self.materials.items():
                _tiled_preview(material, MATERIALS[self.surface_materials[name]])
            self.tiled = True
        stats = self.validate(budget, total_budget)
        self._write_qc()
        self.bake_ao(ao_distance, together=ao_together)
        self.export()
        self.write_spec(stats)
        if views:
            self.render(views, references or [])
        log(f"{self.name}: {len(self.parts)} parts, " +
            ", ".join(f"{s['name']} {s['triangles']} tris" for s in stats))

    def finish_textured(self, size=2048, moving=(), joined_name=None, views=None, references=None, budget=None,
                        ao_distance=0.3, ao_floor=0.35, margin=8, islands="source", chunk=1.0, export=True, untextured=(),
                        ao_together=True, cut=None, pack_shape="CONCAVE", ground=None, min_px=1.5, total_budget=None,
                        contact=0.003):
        """
        Textured model (new pipeline):
        1. Validates; stops if there are overlapping faces in the same plane (z-fighting).
        2. Joins the static parts into a single object (parts named in `moving` stay separate: wheel, line, leaf).
        3. Unwraps a shared atlas UV for all of them, measures the texel density. islands="source": the generator's source UV
           (a perfect cylinder unwrap for the rope and the tire) is cut into `chunk` UV-unit pieces, the islands are equalised by their 3D area
           and packed (so a long rope does not become a single thin strip wasting the atlas). "smart": Blender's angle-based
           unwrap.
        4. Bakes the source materials into the atlas with Cycles: base colour (unlit), tangent-space normal (OpenGL +Y),
           roughness, metallic, AO (neighbouring parts cast shadows too; the darkest is `ao_floor`).
        5. Builds a single "Atlas_<model>" material; writes the textures to Textures/<model>/<model>_{color,normal,orm}.png
           (orm: R = AO, G = roughness, B = metallic); only the atlas UV goes into the FBX.
        export=False (pipeline checks): the textures go to Builds/Models/<model>_atlas/; no FBX, no spec file.
        untextured: parts left out of the atlas (leaf clusters): they keep their <Kind>_<RRGGBB>_<finish> materials and get vertex AO
        like the old pipeline, because in Unity leaves need the soft foliage lighting (light passes through them), not the hard
        surface lighting of the atlas material. The spec's atlas lists them.
        cut: metres; long faces are split by axis planes at this spacing before a "smart" unwrap (16 m siding boards made
        islands so long the packer left most of the atlas empty). pack_shape: "AABB" packs many box-like islands (boards)
        quickly and tightly, "CONCAVE" (default) follows the island outlines.
        Quality gates (qc.py; a failure stops the build): z-fighting 0; holes 0 (close cameras all over, back faces must never be
        seen first; `ground`: world z below which no camera goes); joints 0 (no member end crossing the face it meets at an
        angle, qc.joint_audit); every face over 1 cm² at least `min_px` atlas pixels across
        its narrow side. Atlas pixels no face uses are filled with the nearest used colour (no black to bleed into mipmaps).
        ao_together=False: every part's AO is baked with the other parts hidden (parts that sit on top of each other in the
        file but apart in game, e.g. the trimmer's motor, handle and head all at the shaft's origin).
        """
        import numpy as np

        if PREVIEW:
            apart = set(moving) | set(untextured)
            first = next((o.name for o, _ in self.parts if o.name not in apart), None)
            return self._preview(views, references, budget, total_budget, ground, not ao_together, contact,
                                 joined_name or first, apart)
        self.drop_unused_slots()
        self.validate(budget, total_budget)
        # Parts that only overlap in the file (they are apart in game) are checked one by one
        self._gate_overlaps(separate=not ao_together)
        self._gate_construction(ground, separate=not ao_together, contact=contact, views=views)
        self._gate_holes(ground, separate=not ao_together)
        self._gate_joints(separate=not ao_together)

        # 2. Joining
        static = [(obj, closed) for obj, closed in self.parts if obj.name not in moving and obj.name not in untextured]
        if len(static) > 1:
            # The parts kept apart, taken before the join (joining removes the other objects)
            apart = [(o, c) for o, c in self.parts if o.name in moving or o.name in untextured]
            self.parts = [self._join(static, joined_name or static[0][0].name)] + apart
        objects = [obj for obj, _ in self.parts if obj.name not in untextured]
        if cut:
            for obj in objects:
                bm = bmesh.new()
                bm.from_mesh(obj.data)
                grid_cut(bm, (cut, cut, cut))
                bm.to_mesh(obj.data)
                bm.free()

        # 3. Atlas UV
        for obj in objects:
            layers = obj.data.uv_layers
            if layers.get(SOURCE_UV) is None:
                layers.new(name=SOURCE_UV)
            atlas = layers.get(ATLAS_UV) or layers.new(name=ATLAS_UV)
            layers.active = atlas
        bpy.ops.object.select_all(action="DESELECT")
        for obj in objects:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = objects[0]
        if islands == "source":
            for obj in objects:
                mesh = obj.data
                source = mesh.uv_layers[SOURCE_UV].data
                target = mesh.uv_layers[ATLAS_UV].data
                for poly in mesh.polygons:
                    pts = [source[i].uv for i in poly.loop_indices]
                    centre = sum(p.y for p in pts) / len(pts)
                    piece = math.floor(centre / chunk)
                    for i in poly.loop_indices:
                        target[i].uv = (source[i].uv.x, source[i].uv.y + piece * 0.37)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        if islands == "smart":
            bpy.ops.uv.smart_project(angle_limit=math.radians(60.0), island_margin=0.0, area_weight=0.0,
                                     correct_aspect=True, scale_to_bounds=False)
        bpy.ops.uv.select_all(action="SELECT")
        bpy.ops.uv.average_islands_scale()
        if pack_shape == "AABB":
            # A fixed gap of 2 x margin pixels: the default margin scales per island and with tens of thousands of small islands
            # (every board face) the gaps alone filled the atlas (the house used 0.85 % of it)
            bpy.ops.uv.pack_islands(rotate=True, rotate_method="AXIS_ALIGNED", shape_method="AABB",
                                    margin_method="FRACTION", margin=2.0 * margin / size)
        else:
            bpy.ops.uv.pack_islands(rotate=True, margin=2.5 * margin / size)
        bpy.ops.object.mode_set(mode="OBJECT")

        def density(obj):
            mesh = obj.data
            data = mesh.uv_layers[ATLAS_UV].data
            uv_area = area = 0.0
            for poly in mesh.polygons:
                area += poly.area
                pts = [data[i].uv for i in poly.loop_indices]
                uv_area += 0.5 * abs(sum(pts[i].x * pts[(i + 1) % len(pts)].y - pts[(i + 1) % len(pts)].x * pts[i].y
                                         for i in range(len(pts))))
            return size * math.sqrt(uv_area / max(area, 1e-9))

        densities = {obj.name: round(density(obj)) for obj in objects}
        texels = qc.texel_audit(objects, size, ATLAS_UV, min_px=min_px, ground=ground)
        self.qc["texels"] = {"atlas": size, "density_px_per_m": densities, **texels}
        log(f"{self.name}: QC texels: area by narrow-side width (px) {texels['bands_percent']}, "
            f"{texels['thin_faces']} faces over 1 cm² under {min_px} px")
        if texels["thin_faces"]:
            self._write_qc()
            raise RuntimeError(f"{self.name}: QC texels: {texels['thin_faces']} faces too thin for the atlas "
                               f"(px, cm², Unity xyz, part): {texels['worst']}")

        # 4. Baking
        scene = bpy.context.scene
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.render.bake.target = "IMAGE_TEXTURES"
        if scene.world is None:
            scene.world = bpy.data.worlds.new("AO")
        scene.world.light_settings.distance = ao_distance
        images = {}
        for key, data in (("color", False), ("normal", True), ("rough", True), ("metal", True), ("ao", True)):
            image = bpy.data.images.new(f"{self.name}_{key}", size, size, alpha=False, float_buffer=False)
            image.colorspace_settings.name = "Non-Color" if data else "sRGB"
            images[key] = image
        metallic = any(m.node_tree and any(n.type == "BSDF_PRINCIPLED" and n.inputs["Metallic"].default_value > 0.0
                                           for n in m.node_tree.nodes)
                       for obj in objects for m in obj.data.materials if m)
        passes = [("color", "DIFFUSE", 8), ("normal", "NORMAL", 8), ("rough", "ROUGHNESS", 8), ("ao", "AO", 96)]
        if metallic:
            passes.append(("metal", "EMIT", 4))
        for key, kind, samples in passes:
            scene.cycles.samples = samples
            for index, obj in enumerate(objects):
                alone = kind == "AO" and not ao_together
                if alone:
                    for other, _ in self.parts:
                        other.hide_render = other is not obj
                self._bake_into(obj, images[key], kind, index == 0, margin)
                if alone:
                    for other, _ in self.parts:
                        other.hide_render = False

        def pixels(image):
            values = np.empty(size * size * 4, dtype=np.float32)
            image.pixels.foreach_get(values)
            return values.reshape(-1, 4)

        # Coverage: the pixels the faces really use (white emission, no margin). Every other pixel is filled with the nearest
        # used colour, so neither the bake margin's edge nor mipmaps ever mix black into a face
        coverage = bpy.data.images.new(f"{self.name}_coverage", size, size, alpha=False, float_buffer=False)
        coverage.colorspace_settings.name = "Non-Color"
        scene.cycles.samples = 1
        for index, obj in enumerate(objects):
            self._bake_into(obj, coverage, "EMIT", index == 0, 0, emit_color=lambda mat: (1.0, 1.0, 1.0))
        used = (pixels(coverage)[:, 0] > 0.5).reshape(size, size)
        self.qc["atlasUsedPercent"] = round(100.0 * float(used.mean()), 1)
        for key in [k for k, _, _ in passes]:
            filled = qc.fill_empty(pixels(images[key]).reshape(size, size, 4), used)
            images[key].pixels.foreach_set(filled.ravel())

        orm = np.ones((size * size, 4), dtype=np.float32)
        orm[:, 0] = ao_floor + (1.0 - ao_floor) * pixels(images["ao"])[:, 0]
        orm[:, 1] = pixels(images["rough"])[:, 0]
        orm[:, 2] = pixels(images["metal"])[:, 0] if metallic else 0.0
        images["orm"] = bpy.data.images.new(f"{self.name}_orm", size, size, alpha=False, float_buffer=False)
        images["orm"].colorspace_settings.name = "Non-Color"
        images["orm"].pixels.foreach_set(orm.ravel())

        folder = os.path.join(TEXTURE_DIR, self.name) if export else os.path.join(RENDER_DIR, self.name + "_atlas")
        os.makedirs(folder, exist_ok=True)
        files = {}
        for key in ("color", "normal", "orm"):
            path = os.path.join(folder, f"{self.name}_{key}.png")
            images[key].filepath_raw = path
            images[key].file_format = "PNG"
            images[key].save()
            files[key] = os.path.relpath(path, ROOT).replace("\\", "/")

        # 5. A single material: the atlas textures (the Blender preview uses them too)
        mat = bpy.data.materials.new(ATLAS_PREFIX + self.name)
        if bpy.app.version < (5, 0, 0):
            mat.use_nodes = True
        nodes, links = mat.node_tree.nodes, mat.node_tree.links
        bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
        uv = nodes.new("ShaderNodeUVMap")
        uv.uv_map = ATLAS_UV

        def texture(image):
            node = nodes.new("ShaderNodeTexImage")
            node.image = image
            links.new(uv.outputs["UV"], node.inputs["Vector"])
            return node

        color, packed, normal = texture(images["color"]), texture(images["orm"]), texture(images["normal"])
        split = nodes.new("ShaderNodeSeparateColor")
        links.new(packed.outputs["Color"], split.inputs["Color"])
        shade = nodes.new("ShaderNodeMix")
        shade.data_type = "RGBA"
        shade.blend_type = "MULTIPLY"
        shade.inputs["Factor"].default_value = 1.0
        links.new(color.outputs["Color"], shade.inputs["A"])
        links.new(split.outputs["Red"], shade.inputs["B"])
        links.new(shade.outputs["Result"], bsdf.inputs["Base Color"])
        links.new(split.outputs["Green"], bsdf.inputs["Roughness"])
        links.new(split.outputs["Blue"], bsdf.inputs["Metallic"])
        normal_map = nodes.new("ShaderNodeNormalMap")
        normal_map.uv_map = ATLAS_UV
        links.new(normal.outputs["Color"], normal_map.inputs["Color"])
        links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])
        for obj in objects:
            obj.data.materials.clear()
            obj.data.materials.append(mat)
            obj.data.uv_layers.remove(obj.data.uv_layers[SOURCE_UV])

        self.atlas = {"size": size, "textures": files, "texelDensity": densities, "ao": ao_distance}
        if untextured:
            self.atlas["untextured"] = sorted(untextured)
            self.bake_ao(ao_distance, only=untextured)
        stats = self.validate(budget, total_budget)
        self._write_qc()
        if export:
            self.export()
            self.write_spec(stats)
        if views:
            self.render(views, references or [])
        log(f"{self.name}: {len(self.parts)} parts, atlas {size} px, texel density " +
            ", ".join(f"{n} {d} px/m" for n, d in densities.items()) + "; " +
            ", ".join(f"{s['name']} {s['triangles']} tris" for s in stats))

    @staticmethod
    def _bake_into(obj, image, kind, clear, margin, emit_color=None):
        """Puts the selected target image node into all of the object's materials and bakes in a single pass (the bake_maps.py method)."""
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        added = []
        emit = []
        for mat in obj.data.materials:
            if mat is None:
                continue
            tree = mat.node_tree
            for node in tree.nodes:
                node.select = False
            target = tree.nodes.new("ShaderNodeTexImage")
            target.image = image
            target.select = True
            tree.nodes.active = target
            added.append((tree, target))
            if kind == "EMIT":
                # Metallic cannot be baked in Cycles: temporarily wired to the emission colour
                out = next(n for n in tree.nodes if n.type == "OUTPUT_MATERIAL")
                bsdf = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
                previous = out.inputs["Surface"].links[0].from_socket if out.inputs["Surface"].links else None
                emission = tree.nodes.new("ShaderNodeEmission")
                if emit_color is not None:
                    emission.inputs["Color"].default_value = (*emit_color(mat), 1.0)
                else:
                    value = bsdf.inputs["Metallic"].default_value
                    emission.inputs["Color"].default_value = (value, value, value, 1.0)
                tree.links.new(emission.outputs[0], out.inputs["Surface"])
                emit.append((tree, out, previous, emission))
        kwargs = {"type": kind, "margin": margin, "use_clear": clear}
        if kind == "DIFFUSE":
            kwargs["pass_filter"] = {"COLOR"}
        if kind == "NORMAL":
            kwargs["normal_space"] = "TANGENT"
        bpy.ops.object.bake(**kwargs)
        for tree, out, previous, emission in emit:
            tree.nodes.remove(emission)
            if previous is not None:
                tree.links.new(previous, out.inputs["Surface"])
        for tree, target in added:
            tree.nodes.remove(target)

    @staticmethod
    def _jitter_islands(obj, values, amount):
        """Varies the vertex colour (AO) values by a random multiplier per shell: every board a touch different in tone."""
        import random
        import zlib
        # crc32, not hash(): Python salts str hashes per process, so every build gave the boards new tones (22 October 2026)
        rng = random.Random(zlib.crc32(obj.name.encode()) & 0xFFFF)
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        polygons = obj.data.polygons
        for group in shells(bm):
            factor = 1.0 + rng.uniform(-amount, amount * 0.5)
            for face in group:
                for loop_index in polygons[face.index].loop_indices:
                    base = loop_index * 4
                    for c in range(3):
                        values[base + c] = min(1.0, values[base + c] * factor)
        bm.free()

    def drop_unused_slots(self):
        """
        Drops the material slots no face uses (the FBX export drops them too; the spec file should write the same list as the
        FBX). The face indices are remapped to the new order.
        """
        for obj, _ in self.parts:
            mesh = obj.data
            indices = [0] * len(mesh.polygons)
            mesh.polygons.foreach_get("material_index", indices)
            used = sorted(set(indices))
            if len(used) == len(mesh.materials):
                continue
            keep = [mesh.materials[i] for i in used]
            remap = {old: new for new, old in enumerate(used)}
            mesh.materials.clear()
            for material in keep:
                mesh.materials.append(material)
            mesh.polygons.foreach_set("material_index", [remap[i] for i in indices])
            mesh.update()

    @staticmethod
    def _even_preset_ao(mesh, values):
        """
        Pieces with preset UVs (shingle strips, ridge caps): one AO value per piece (its 90th percentile). Baked per vertex the AO
        ran from light at a strip's butt to dark under the next row and drew every row line again in the vertex colour; the rows'
        shading is in the texture. The value still darkens a strip under a ridge cap or next to the vent pipe.
        """
        flags = mesh.attributes[PRESET_FLAG].data
        bm = bmesh.new()
        bm.from_mesh(mesh)
        for group in shells(bm):
            if not any(flags[f.index].value for f in group):
                continue
            corners = [i for f in group for i in mesh.polygons[f.index].loop_indices]
            ao = sorted(values[4 * i] for i in corners)
            level = ao[int(0.9 * (len(ao) - 1))]
            for i in corners:
                values[4 * i] = values[4 * i + 1] = values[4 * i + 2] = level
        bm.free()

    def bake_ao(self, distance, samples=64, floor=0.3, together=True, only=None):
        """
        Bakes the ambient occlusion into every part's vertex colour (R, "AO"): recesses, joints, under lids.
        The other parts in the scene (and wheels added only for rendering) cast shadows. In Unity Opus/Surface
        multiplies the albedo by it on models. `floor`: the darkest value (so deep recesses do not go pitch black).
        together=False: every part is baked on its own (a part library stacked in the same place, e.g. the wheels).
        only: bake just these parts (the untextured parts of a textured model); the others still cast shadows.
        """
        scene = bpy.context.scene
        engine = scene.render.engine
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = samples
        if scene.world is None:
            scene.world = bpy.data.worlds.new("AO")
        scene.world.light_settings.distance = distance
        for obj, _ in self.parts:
            if only is not None and obj.name not in only:
                continue
            mesh = obj.data
            attribute = mesh.color_attributes.new("AO", "BYTE_COLOR", "CORNER")
            mesh.color_attributes.active_color = attribute
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            # Leaves are dense: a short distance and a high floor (otherwise the crown goes pitch black); the other parts normal
            leafy = obj.name in self.foliage
            scene.world.light_settings.distance = min(distance, 0.3) if leafy else distance
            part_floor = 0.58 if leafy else floor
            for other, _ in self.parts:
                other.hide_render = not together and other is not obj
            bpy.ops.object.bake(type="AO", target="VERTEX_COLORS")
            values = [0.0] * (len(attribute.data) * 4)
            attribute.data.foreach_get("color", values)
            for i in range(0, len(values), 4):
                ao = part_floor + (1.0 - part_floor) * values[i]
                values[i] = values[i + 1] = values[i + 2] = ao
                values[i + 3] = 1.0
            if PRESET_FLAG in mesh.attributes:
                self._even_preset_ao(mesh, values)
            if self.tone_jitter.get(obj.name, 0.0) > 0.0:
                self._jitter_islands(obj, values, self.tone_jitter[obj.name])
            attribute.data.foreach_set("color", values)
            if PRESET_FLAG in mesh.attributes:
                mesh.attributes.remove(mesh.attributes[PRESET_FLAG])
        for obj, _ in self.parts:
            obj.hide_render = False
        scene.render.engine = engine
        bpy.ops.object.select_all(action="DESELECT")

    def validate(self, budget, total_budget=None):
        errors = []
        stats = []
        for obj, closed in self.parts:
            if any(abs(c) > 1e-6 for c in obj.rotation_euler) or any(abs(s - 1.0) > 1e-6 for s in obj.scale):
                errors.append(f"{obj.name}: rotation/scale not applied")
            for slot in obj.data.materials:
                kind = slot.name.split("_")[0] if slot else ""
                textured = slot is not None and slot.name.startswith((SOURCE_PREFIX, ATLAS_PREFIX))
                if kind not in SURFACE_KINDS and not textured:
                    errors.append(f"{obj.name}: material name '{slot.name if slot else None}' is not <Kind>_<RRGGBB>")
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            bm.faces.ensure_lookup_table()
            bm.normal_update()
            degenerate = sum(1 for f in bm.faces if f.calc_area() < 1e-10)
            if degenerate:
                errors.append(f"{obj.name}: {degenerate} zero-area faces")
            loose = sum(1 for v in bm.verts if not v.link_faces)
            if loose:
                errors.append(f"{obj.name}: {loose} loose vertices")
            volume = 0.0
            if closed:
                open_edges = sum(1 for e in bm.edges if not e.is_manifold)
                if open_edges:
                    errors.append(f"{obj.name}: {open_edges} open/non-manifold edges")
                for index, group in enumerate(shells(bm)):
                    v = signed_volume(group)
                    if v <= 0.0:
                        errors.append(f"{obj.name}: shell {index} inside out (volume {v:.3e})")
                    volume += v
            triangles = sum(len(p.vertices) - 2 for p in obj.data.polygons)
            if budget and triangles > budget:
                errors.append(f"{obj.name}: {triangles} tris, budget {budget}")
            verts = [to_unity(v.co) for v in obj.data.vertices]
            stats.append({
                "name": obj.name,
                "position": _vec(to_unity(obj.location)),
                "boundsMin": _vec([min(v[i] for v in verts) for i in range(3)]),
                "boundsMax": _vec([max(v[i] for v in verts) for i in range(3)]),
                "triangles": triangles,
                "vertices": len(obj.data.vertices),
                "closed": closed,
                "foliage": obj.name in self.foliage,
                "volume": round(volume, 9),
                "materials": [m.name for m in obj.data.materials],
            })
            bm.free()
        total = sum(s["triangles"] for s in stats)
        if total_budget and total > total_budget:
            errors.append(f"the whole model: {total} tris, total budget {total_budget}")
        if errors:
            raise RuntimeError("Model validation failed:\n  " + "\n  ".join(errors))
        return stats

    def export(self):
        os.makedirs(FBX_DIR, exist_ok=True)
        path = os.path.join(FBX_DIR, self.name + ".fbx")
        bpy.ops.object.select_all(action="DESELECT")
        for obj, _ in self.parts:
            obj.select_set(True)
        bpy.ops.export_scene.fbx(
            filepath=path,
            use_selection=True,
            object_types={"MESH"},
            use_mesh_modifiers=True,
            apply_unit_scale=True,
            apply_scale_options="FBX_SCALE_UNITS",
            axis_forward="-Z",
            axis_up="Y",
            bake_space_transform=True,
            mesh_smooth_type="OFF",
            use_triangles=True,
            use_tspace=False,
            use_custom_props=False,
            add_leaf_bones=False,
            bake_anim=False,
            path_mode="STRIP",
            embed_textures=False,
        )
        log(f"FBX: {os.path.relpath(path, ROOT)}")

    def write_spec(self, stats):
        os.makedirs(SPEC_DIR, exist_ok=True)
        spec = {
            "model": self.name,
            "generator": self.generator,
            "blender": bpy.app.version_string,
            "objects": stats,
            "anchors": self.anchors,
            "surfaces": [self.surface_notes[name] for name in self.materials
                         if self.atlas is not None
                         or any(name in [m.name for m in obj.data.materials] for obj, _ in self.parts)],
        }
        if self.atlas is not None:
            spec["atlas"] = self.atlas
        if self.external_assets:
            spec["external"] = self.external_assets
        if self.qc:
            spec["qc"] = self.qc
        if self.tiled:
            spec["tiled"] = True
        if self.plan_data:
            spec["plan"] = self.plan_data
            spec["located"] = self.located
        if self.feature_data:
            spec["features"] = self.feature_data
        if self.bevels:
            spec["bevels_mm"] = {k: (round(v * 1000, 2) if v else None) for k, v in sorted(self.bevels.items())}
        if self.unchamfered:
            spec["unchamfered"] = dict(sorted(self.unchamfered.items()))
        if self.routes or self.attachments:
            spec["links"] = self._links_spec()
        spec.update(self._fingerprints())
        style_path = os.path.join(ROOT, "tools", "blender", "style", "style.json")
        if os.path.exists(style_path):   # the art style this model was built for (Style.py report flags an older one)
            with open(style_path, encoding="utf-8") as f:
                spec["style_version"] = json.load(f).get("style_version")
        path = os.path.join(SPEC_DIR, self.name + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(spec, f, ensure_ascii=False, indent=2)
            f.write("\n")

    # ----------------------------------------------------------------------------------------------------------
    # Contact sheet views
    # ----------------------------------------------------------------------------------------------------------

    def _links_spec(self):
        return {"routes": [{"name": r["name"], "points": [_vec(to_unity(p)) for p in r["points"]], "free": list(r["free"])}
                           for r in self.routes],
                "attachments": [{"name": a["name"], "point": _vec(to_unity(a["point"]))} for a in self.attachments]}

    def _fingerprints(self):
        """
        Three hashes (tools/Review.py, tools/Verify.ps1):
        - geometry: positions to 0.1 mm, faces, material slots;
        - structure: geometry + the plan + the declared links + anchors. A review is valid while it is unchanged;
        - asset: structure + every UV layer + the surfaces. With the textures (compared with a tolerance by Review.py,
          because a bake may differ by noise) it is what the user approves.
        """
        geometry, uvs = self._geometry_hashes()
        canon = json.dumps({"plan": self.plan_data, "links": self._links_spec(), "anchors": self.anchors,
                            "features": [{k: v for k, v in f.items() if k != "measured"} for f in self.feature_data]},
                           sort_keys=True)
        structure = hashlib.sha1((geometry + canon).encode()).hexdigest()[:16]
        digest = hashlib.sha1((structure + uvs).encode())
        digest.update(json.dumps([self.surface_notes.get(n) for n in sorted(self.materials)], sort_keys=True).encode())
        return {"geometry": geometry, "structure": structure, "asset": digest.hexdigest()[:16]}

    def _geometry_hashes(self):
        """
        (geometry, uvs): short hashes of what the model is, independent of the order of vertices and faces and of how a
        flat face is cut into triangles:
        - geometry: per part, the set of vertex positions (0.1 mm) and, per material, the face count and area (mm²);
        - uvs: per part and UV layer, the set of (corner position, UV) pairs.
        23 October 2026: hashing vertices and faces in mesh order gave the calibration model a new hash at every build of
        the same geometry, and the wheel's faces came in another order at every build (bmesh operators order by memory
        address: fixed by canonical_order / canonical_mesh); either would have outdated every review and approval.
        """
        geometry, uvs = hashlib.sha1(), hashlib.sha1()
        for obj, _ in sorted(self.parts, key=lambda p: p[0].name):
            mw = obj.matrix_world
            corners = [tuple(int(round(c * 10000)) for c in (mw @ v.co)) for v in obj.data.vertices]
            names = [m.name if m else "" for m in obj.data.materials]
            per_material = {}
            for p in obj.data.polygons:
                name = names[p.material_index] if p.material_index < len(names) else ""
                count, area = per_material.get(name, (0, 0.0))
                per_material[name] = (count + 1, area + p.area)
            geometry.update(obj.name.encode())
            geometry.update(repr(sorted(set(corners))).encode())
            geometry.update(repr(sorted((n, c, round(a * 1e6)) for n, (c, a) in per_material.items())).encode())
            for layer in sorted(obj.data.uv_layers, key=lambda layer: layer.name):
                pairs = {(corners[obj.data.loops[i].vertex_index], tuple(int(round(c * 10000)) for c in layer.data[i].uv))
                         for i in range(len(obj.data.loops))}
                uvs.update((obj.name + layer.name).encode())
                uvs.update(repr(sorted(pairs)).encode())
        return geometry.hexdigest()[:16], uvs.hexdigest()[:16]

    def render(self, views, references, folder=None):
        """
        views: [{"file", "label", "objects": [name...], "direction": (x,y,z), "zoom": 1, "target": (x,y,z)|None,
                 "offsets": {name: (x,y,z)}, "ortho": False, "clip_through": (x,y,z)|None}]
                 clip_through: a section view; the camera's near plane passes through this point, cutting away what is in
                 front of it (a joined building cannot hide its parts, so this is how the inside of a deck is shown)
        references: [{"label", "path" (relative to the project root), "crop": [x, y, w, h]}] (PowerShell crops)
        folder: Builds/Models/<folder> (default the model's name; the preview uses <name>_preview)
        """
        out_dir = os.path.join(RENDER_DIR, folder or self.name)
        os.makedirs(out_dir, exist_ok=True)
        for old in os.listdir(out_dir):
            os.remove(os.path.join(out_dir, old))
        scene = bpy.context.scene
        _setup_render(scene)
        ground = _ground(scene)
        camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
        scene.collection.objects.link(camera)
        scene.camera = camera

        entries = []
        for view in views:
            names = set(view["objects"])
            offsets = view.get("offsets", {})
            for obj, _ in self.parts:
                obj.hide_render = obj.name not in names
                obj.location = Vector(obj.location) + Vector(offsets.get(obj.name, (0.0, 0.0, 0.0)))
            bpy.context.view_layer.update()
            visible = [obj for obj, _ in self.parts if obj.name in names]
            lo, hi = _bounds(visible)
            ground.location = (0.0, 0.0, view.get("ground", lo.z) - 0.0005)
            center = Vector(view["target"]) if view.get("target") else (lo + hi) * 0.5
            radius = view.get("radius") or max((hi - lo).length * 0.5, 0.01)
            direction = Vector(view["direction"]).normalized()
            camera.data.lens = view.get("lens", 50.0)
            camera.data.sensor_width = 36.0
            if view.get("ortho"):
                camera.data.type = "ORTHO"
                camera.data.ortho_scale = radius * 2.3 / view.get("zoom", 1.0)
                distance = radius * 4.0
            else:
                camera.data.type = "PERSP"
                half_fov = math.atan(18.0 / camera.data.lens)
                distance = radius / math.sin(half_fov) * 1.08 / view.get("zoom", 1.0)
            camera.data.clip_start = distance * 0.01
            camera.data.clip_end = distance * 10.0 + 10.0
            camera.location = center + direction * distance
            if view.get("clip_through"):
                # A section: everything nearer than this point is cut away (the lattice in front of a deck's supports)
                depth = (Vector(view["clip_through"]) - camera.location).dot(-direction)
                camera.data.clip_start = max(0.001, depth)
            camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
            scene.render.filepath = os.path.join(out_dir, view["file"] + ".png")
            bpy.ops.render.render(write_still=True)
            entries.append({"type": "render", "file": view["file"] + ".png", "label": view["label"]})
            for obj, _ in self.parts:
                obj.location = Vector(obj.location) - Vector(offsets.get(obj.name, (0.0, 0.0, 0.0)))
                obj.hide_render = False

        for ref in references:
            entries.append({"type": "reference", "path": ref["path"], "crop": ref["crop"], "label": ref["label"]})
        with open(os.path.join(out_dir, "views.json"), "w", encoding="utf-8") as f:
            json.dump({"model": self.name, "views": entries}, f, ensure_ascii=False, indent=2)
        log(f"Views: {os.path.relpath(out_dir, ROOT)} ({len(views)} renders)")


def _vec(v):
    return {"x": round(v[0], 6), "y": round(v[1], 6), "z": round(v[2], 6)}


def _bounds(objects):
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for obj in objects:
        for corner in obj.bound_box:
            p = obj.matrix_world @ Vector(corner)
            lo = Vector((min(lo.x, p.x), min(lo.y, p.y), min(lo.z, p.z)))
            hi = Vector((max(hi.x, p.x), max(hi.y, p.y), max(hi.z, p.z)))
    return lo, hi


def _setup_render(scene):
    engines = {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    for engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "CYCLES"):
        if engine in engines:
            scene.render.engine = engine
            break
    if scene.render.engine == "CYCLES":
        scene.cycles.samples = 48
        scene.cycles.use_denoising = True
    else:
        scene.eevee.taa_render_samples = 48
    scene.render.resolution_x = 640
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"

    # As in the game: a warm sun, a lavender sky fill
    world = bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.47, 0.45, 0.56, 1.0)
    background.inputs["Strength"].default_value = 0.9
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 3.2
    sun.data.color = (1.0, 0.92, 0.8)
    sun.data.angle = math.radians(6.0)
    sun.rotation_euler = Vector((-0.4, 0.7, -0.8)).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(sun)


def _ground(scene):
    """A 10 cm checkered ground (for scale)."""
    bpy.ops.mesh.primitive_plane_add(size=20.0)
    ground = bpy.context.active_object
    ground.name = "Ground"
    mat = bpy.data.materials.new("Ground")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.9
    checker = nodes.new("ShaderNodeTexChecker")
    checker.inputs["Scale"].default_value = 10.0
    checker.inputs["Color1"].default_value = (0.62, 0.6, 0.55, 1.0)
    checker.inputs["Color2"].default_value = (0.52, 0.5, 0.46, 1.0)
    coords = nodes.new("ShaderNodeTexCoord")
    links.new(coords.outputs["Object"], checker.inputs["Vector"])
    links.new(checker.outputs["Color"], bsdf.inputs["Base Color"])
    ground.data.materials.append(mat)
    return ground
