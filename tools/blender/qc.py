"""
Quality gates of the model pipeline (21 October 2026, after the user found holes and black lines the old checks missed).

- audit_holes: looks at the model from hundreds of close cameras the way Unity draws it (back faces culled). A ray from outside
  whose first hit is a BACK face means a face is missing there: in game you would see through. Must be 0.
- texel_audit: for an atlas model, how many atlas pixels each face gets across its narrow side. A face of noticeable size under
  `min_px` cannot carry its colour: it bleeds the neighbouring pixels (the black shingle butts and downspout facets).
- fill_empty: fills the atlas pixels no face uses with the colour of the nearest used ones (push-pull), so mipmaps never mix in
  black.

Every gate reports in numbers (Builds/QC/<model>.json); a failure raises and stops the build.
"""
import json
import math
import os
import random

import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def _tree(objects):
    verts, polys = [], []
    for obj in objects:
        mw = obj.matrix_world
        base = len(verts)
        verts += [mw @ v.co for v in obj.data.vertices]
        polys += [[base + i for i in p.vertices] for p in obj.data.polygons]
    return BVHTree.FromPolygons(verts, polys, epsilon=0.0), verts, polys


def _faces(objects):
    """(area, centre, normal) of every polygon in world space."""
    out = []
    for obj in objects:
        mw = obj.matrix_world
        rot = mw.to_3x3()
        for p in obj.data.polygons:
            if p.area < 1e-8:
                continue
            out.append((p.area, mw @ p.center, (rot @ p.normal).normalized(), obj, p))
    return out


AXES = [Vector(v) for v in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))]
# 26 directions (cube faces, edges, corners) for the "can this camera see out?" test
ESCAPE = [Vector((x, y, z)).normalized() for x in (-1, 0, 1) for y in (-1, 0, 1) for z in (-1, 0, 1) if (x, y, z) != (0, 0, 0)]


def audit_holes(objects, ground=None, seed=1, per_m2=1.0, min_cameras=300, max_cameras=4000, rays=1500,
                near=0.25, far=1.6, min_dot=0.05, details=None):
    """
    Close cameras over the whole surface (area-weighted: a camera 0.25-1.6 m in front of a random point, looking at it), each
    casting `rays` random rays in a 40 degree cone. A first hit on a back face = a hole. Cameras below `ground` (world z) or
    shut in (no ray of 26 directions gets out to the sky; the ground is opaque) are skipped: a camera can only be where the
    open air is. (The first version judged "inside" by the facing of the first hit, which pressed faces such as a board's
    back on the wall core fooled.) Hits more grazing than `min_dot` (the ray within
    3 degrees of the face plane) are not counted: such a face shows 5 % of its area at most, far below a pixel for the lug and
    rope facets where curved extrusions tilt a side wall by a degree. A back hit is confirmed by four rays shifted 0.1 mm
    sideways: a ray through a shared edge can return the face behind the edge in float precision (one such hit on the
    house's siding board edge); a real gap wider than 0.2 mm (under a pixel at 0.25 m) passes the shifted rays too.
    Returns {"cameras", "rays", "backface_hits", "edge_grazes", "regions": [(unity xyz, hits), ...]}.
    """
    rng = random.Random(seed)
    tree, _, _ = _tree(objects)
    faces = _faces(objects)
    total = sum(f[0] for f in faces)
    count = int(min(max(total * per_m2, min_cameras), max_cameras))
    cumulative, acc = [], 0.0
    for f in faces:
        acc += f[0]
        cumulative.append(acc)

    def pick():
        r = rng.random() * acc
        lo, hi = 0, len(cumulative) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if cumulative[mid] < r:
                lo = mid + 1
            else:
                hi = mid
        return faces[lo]

    def inside(point):
        for d in ESCAPE:
            if ground is not None and d.z < 0.0:
                continue            # towards the ground: never out
            if tree.ray_cast(point, d, 1000.0)[0] is None:
                return False
        return True

    def confirmed(eye, d):
        s = d.orthogonal().normalized()
        u = d.cross(s)
        backs = 0
        for off in (s, -s, u, -u):
            h = tree.ray_cast(eye + off * 1e-4, d, 200.0)
            if h[0] is not None and h[1].dot(d) > 0.0:
                backs += 1
        return backs >= 3

    hits, cast, cameras, grazes = {}, 0, 0, 0
    tries = 0
    while cameras < count and tries < count * 6:
        tries += 1
        _, centre, normal, _, _ = pick()
        distance = near * (far / near) ** rng.random()
        jitter = Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1))) * 0.25 * distance
        eye = centre + normal * distance + jitter
        if ground is not None and eye.z < ground + 0.03:
            continue
        if inside(eye):
            continue
        look = (centre - eye).normalized()
        side = look.orthogonal().normalized()
        up = look.cross(side)
        cameras += 1
        for _ in range(rays):
            a = rng.random() * 2.0 * math.pi
            r = math.tan(math.radians(40.0)) * math.sqrt(rng.random())
            d = (look + side * (math.cos(a) * r) + up * (math.sin(a) * r)).normalized()
            hit = tree.ray_cast(eye, d, 200.0)
            cast += 1
            if hit[0] is not None and hit[1].dot(d) > min_dot:
                if not confirmed(eye, d):
                    grazes += 1
                    continue
                p = hit[0]
                key = (round(p.x, 2), round(p.y, 2), round(p.z, 2))
                hits[key] = hits.get(key, 0) + 1
                if details is not None:
                    details.append((p.copy(), hit[2], eye.copy(), hit[1].dot(d)))
    regions = {}
    for (x, y, z), n in hits.items():
        k = (round(x / 0.25) * 0.25, round(y / 0.25) * 0.25, round(z / 0.25) * 0.25)
        regions[k] = regions.get(k, 0) + n
    top = sorted(regions.items(), key=lambda kv: -kv[1])[:12]
    return {"cameras": cameras, "rays": cast, "backface_hits": sum(hits.values()), "hole_points": len(hits), "edge_grazes": grazes,
            "regions": [([round(-x, 2), round(z, 2), round(-y, 2)], n) for (x, y, z), n in top]}


def texel_audit(objects, size, uv_name, min_px=1.5, min_area=1e-4, ground=None):
    """
    Narrow-side width of every face in atlas pixels (area / longest edge, scaled by the face's own texel density).
    Faces larger than `min_area` m2 under `min_px` fail. Faces wholly below `ground` (world z; the tree trunk's buried end
    cap) are never seen and are skipped. Returns the share of area per width band and the worst faces.
    """
    bands = {"<1": 0.0, "1-2": 0.0, "2-4": 0.0, ">=4": 0.0}
    total = 0.0
    bad = []
    for obj in objects:
        me = obj.data
        layer = me.uv_layers.get(uv_name)
        if layer is None:
            continue
        uv = layer.data
        mw = obj.matrix_world
        for p in me.polygons:
            if p.area < 1e-9:
                continue
            if ground is not None and max((mw @ me.vertices[v].co).z for v in p.vertices) < ground:
                continue
            pts = [uv[i].uv for i in p.loop_indices]
            uv_area = 0.5 * abs(sum(pts[i].x * pts[(i + 1) % len(pts)].y - pts[(i + 1) % len(pts)].x * pts[i].y
                                    for i in range(len(pts))))
            density = size * math.sqrt(uv_area / p.area)
            co = [me.vertices[v].co for v in p.vertices]
            longest = max((co[i] - co[(i + 1) % len(co)]).length for i in range(len(co)))
            px = p.area / max(longest, 1e-9) * density
            band = "<1" if px < 1 else "1-2" if px < 2 else "2-4" if px < 4 else ">=4"
            bands[band] += p.area
            total += p.area
            if px < min_px and p.area > min_area:
                c = mw @ p.center
                bad.append((round(px, 2), round(p.area * 1e4, 1), [round(-c.x, 3), round(c.z, 3), round(-c.y, 3)],
                            obj.name))
    bad.sort(key=lambda b: -b[1])
    return {"bands_percent": {k: round(100 * v / max(total, 1e-9), 1) for k, v in bands.items()},
            "thin_faces": len(bad), "worst": bad[:10]}


def fill_empty(pixels, mask):
    """
    Push-pull fill: pixels (H x W x C float32) where mask (H x W bool) is False take the colour of the nearest used pixels,
    averaged over a mip pyramid. Used pixels stay unchanged.
    """
    levels = []
    c = pixels * mask[..., None]
    w = mask.astype(np.float32)
    while min(c.shape[0], c.shape[1]) > 1:
        levels.append((c, w))
        h, wd = c.shape[0] // 2, c.shape[1] // 2
        c = c[:h * 2, :wd * 2].reshape(h, 2, wd, 2, -1).sum(axis=(1, 3))
        w = w[:h * 2, :wd * 2].reshape(h, 2, wd, 2).sum(axis=(1, 3))
    colour = c / np.maximum(w, 1e-8)[..., None]
    for c_l, w_l in reversed(levels):
        up = np.repeat(np.repeat(colour, 2, axis=0), 2, axis=1)
        if up.shape[0] < c_l.shape[0] or up.shape[1] < c_l.shape[1]:
            up = np.pad(up, ((0, c_l.shape[0] - up.shape[0]), (0, c_l.shape[1] - up.shape[1]), (0, 0)), mode="edge")
        up = up[:c_l.shape[0], :c_l.shape[1]]
        own = c_l / np.maximum(w_l, 1e-8)[..., None]
        colour = np.where((w_l > 0)[..., None], own, up)
    return np.where(mask[..., None], pixels, colour).astype(np.float32)


def write_report(root, model, report):
    folder = os.path.join(root, "Builds", "QC")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, model + ".json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
        f.write("\n")


def _shell_groups(bm):
    """Connected face sets of a bmesh."""
    seen, groups = set(), []
    for start in bm.faces:
        if start.index in seen:
            continue
        stack, group = [start], []
        seen.add(start.index)
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


def joint_audit(objects, tol=0.003, near=0.03, min_angle=3.0, max_angle=60.0, elongation=3.0, min_area=1e-4, min_width=0.01,
                reach=0.06, details=None):
    """
    Member ends that do not sit on what they meet (21 October 2026: the porch's rake boards were cut square to their 15 degree
    slope, so their ends crossed the vertical fascia, 9 mm proud of it at the top and 4 cm behind it at the bottom). For every
    long shell (a board, a rail, a pipe: its longest extent at least `elongation` x the next), its end faces (normal along the
    long axis, over `min_area`) are checked against the faces of other shells within `near` of the end's centre (not of
    parallel members: lapped boards run behind each other by design): an end that
    crosses such a face at an angle (its corners more than `tol` on both sides of it but none further than `reach`, the two
    faces `min_angle`..`max_angle` apart) is cut at the wrong angle: part of it pokes through, part leaves a wedge. Faces
    narrower than `min_width` (edge chamfers) are not counted as something an end meets.
    Returns {"members", "ends", "bad", "worst": [(part, Unity xyz, angle, mm in front, mm behind), ...]}.
    """
    import bmesh
    import numpy as np
    verts, polys, shell_of, normals, widths = [], [], [], [], []
    axes = []                                    # per shell: its long axis, or None for a shell that is not a member
    ends = []                                    # (shell, centre, normal, corners, part)
    members = 0
    shell = 0
    for obj in objects:
        mw = obj.matrix_world
        rot = mw.to_3x3()
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.normal_update()
        for group in _shell_groups(bm):
            pts = np.array([tuple(mw @ v.co) for v in {v for f in group for v in f.verts}])
            for f in group:
                corners = [mw @ v.co for v in f.verts]
                base = len(verts)
                verts += corners
                polys.append(list(range(base, base + len(corners))))
                shell_of.append(shell)
                normals.append((rot @ f.normal).normalized())
                longest = max((corners[i] - corners[i - 1]).length for i in range(len(corners)))
                widths.append(f.calc_area() / max(longest, 1e-9))
            axes.append(None)
            if len(pts) >= 8:
                centred = pts - pts.mean(axis=0)
                _, vecs = np.linalg.eigh(centred.T @ centred)
                spans = [float(np.ptp(centred @ vecs[:, k])) for k in range(3)]
                if spans[2] >= elongation * max(spans[1], 1e-6):
                    members += 1
                    axis = Vector(tuple(vecs[:, 2]))
                    axes[-1] = axis
                    for f in group:
                        n = (rot @ f.normal).normalized()
                        if abs(n.dot(axis)) > 0.7 and f.calc_area() > min_area:
                            corners = [mw @ v.co for v in f.verts]
                            longest = max((corners[i] - corners[i - 1]).length for i in range(len(corners)))
                            if f.calc_area() / max(longest, 1e-9) < min_width * 0.5:
                                continue        # an edge chamfer at the end, not the end itself
                            centre = sum(corners, Vector()) / len(corners)
                            ends.append((shell, centre, n, corners, obj.name, spans[2], axis))
            shell += 1
        bm.free()
    tree = BVHTree.FromPolygons(verts, polys, epsilon=0.0)
    bad = []
    for own, centre, n_end, corners, part, length, axis in ends:
        seen = set()
        for _, _, index, _ in tree.find_nearest_range(centre, near):
            if index is None or index in seen or shell_of[index] == own or widths[index] < min_width:
                continue
            other_axis = axes[shell_of[index]]
            if other_axis is not None and abs(axis.dot(other_axis)) > math.cos(math.radians(30.0)):
                continue        # a parallel member (lapped boards): an end running behind the next board is how laps are built
            seen.add(index)
            n_other = normals[index]
            angle = math.degrees(math.acos(min(1.0, abs(n_end.dot(n_other)))))
            if not (min_angle < angle < max_angle):
                continue
            origin = verts[polys[index][0]]
            d = [(c - origin).dot(n_other) for c in corners]
            if max(d) > tol and min(d) < -tol and max(d) < reach and -min(d) < reach:
                bad.append((part, [round(-centre.x, 3), round(centre.z, 3), round(-centre.y, 3)], round(angle, 1),
                            round(max(d) * 1000, 1), round(-min(d) * 1000, 1)))
                if details is not None:
                    other = sum((verts[i] for i in polys[index]), Vector()) / len(polys[index])
                    details.append({"end_normal": [round(-n_end.x, 3), round(n_end.z, 3), round(-n_end.y, 3)],
                                    "member_length": round(length, 3), "met_normal": [round(-n_other.x, 3), round(n_other.z, 3),
                                                                                      round(-n_other.y, 3)],
                                    "met_centre": [round(-other.x, 3), round(other.z, 3), round(-other.y, 3)],
                                    "met_width": round(widths[index], 3)})
                break
    bad.sort(key=lambda b: -min(b[3], b[4]))
    return {"members": members, "ends": len(ends), "bad": len(bad), "worst": bad[:40]}


# ----------------------------------------------------------------------------------------------------------------------
# Construction plausibility (22 October 2026): what the numeric gates above never asked. Is every piece held by something,
# does a cable or rope reach both things it joins, do two parts really meet at a hinge or a clip? These only catch the
# measurable half of "does it make sense" (a part floating in mid-air, a cable ending short); whether a design is right is
# the plan's and the reviewer's job (.claude/skills/model-plausibility).
# ----------------------------------------------------------------------------------------------------------------------

def _unity(v):
    return [round(-v.x, 3), round(v.z, 3), round(-v.y, 3)]


class ShellMap:
    """Every polygon of the objects in one BVH (world space), with the shell (connected face set) it belongs to."""

    def __init__(self, objects):
        import bmesh
        verts, polys, self.owner, self.shell_object = [], [], [], []
        for obj in objects:
            mw = obj.matrix_world
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            bm.verts.ensure_lookup_table()
            bm.faces.ensure_lookup_table()
            base = len(verts)
            verts += [mw @ v.co for v in bm.verts]
            shell_of = [0] * len(bm.faces)
            for group in _shell_groups(bm):
                for f in group:
                    shell_of[f.index] = len(self.shell_object)
                self.shell_object.append(obj.name)
            for f in bm.faces:
                polys.append([base + v.index for v in f.verts])
                self.owner.append(shell_of[f.index])
            bm.free()
        self.verts, self.polys = verts, polys
        self.count = len(self.shell_object)
        self.tree = BVHTree.FromPolygons(verts, polys, epsilon=0.0) if polys else None

    def near(self, point, tol):
        """The shells with a face within `tol` of the point."""
        if self.tree is None:
            return set()
        return {self.owner[i] for _, _, i, _ in self.tree.find_nearest_range(Vector(point), tol)}

    def distance(self, point):
        hit = self.tree.find_nearest(Vector(point)) if self.tree else None
        return hit[3] if hit and hit[0] is not None else float("inf")


def connectivity(objects, tol=0.003, spacing=0.05, ground=None, seed=7, supports=None):
    """
    Contact graph of the shells: two shells are joined when their triangles intersect (one runs into the other) or a sample
    point of one (its vertices, every triangle's centre and points every `spacing` metres over larger triangles) lies within
    `tol` of the other (one rests on the other); with `ground` (world z) a shell
    reaching z <= ground + tol stands on the ground; `supports` [(point, tol)] are where something outside holds it (hands,
    a branch, the wheels). A model should be ONE assembly held by its supports: the main component is everything joined to
    the ground or a support; all else is stray. With no ground and no supports the biggest component is taken (nothing to
    test the hold against). If there are supports but nothing touches them, the whole model floats: every component is
    stray and `floating` says how high it is (22 October 2026: before, the biggest component counted as held, so a whole
    object floating above the ground passed).
    Returns {shells, components, stray: [{object, shells, triangles, unity, size_mm}], floating}.
    """
    m = ShellMap(objects)
    parent = list(range(m.count + 1))   # the last node is the ground
    ground_node = m.count

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    # Pieces that run into each other (a pin in a plate, a cable entering its tab): their triangles intersect
    if m.tree is not None:
        for a, b in m.tree.overlap(m.tree):
            if m.owner[a] != m.owner[b]:
                union(m.owner[a], m.owner[b])
    rng = random.Random(seed)
    tris = [0] * m.count
    lo = [None] * m.count
    hi = [None] * m.count
    step = spacing * spacing
    for poly, shell in zip(m.polys, m.owner):
        corners = [m.verts[i] for i in poly]
        points = list(corners)
        for k in range(1, len(corners) - 1):
            a, b, c = corners[0], corners[k], corners[k + 1]
            tris[shell] += 1
            area = (b - a).cross(c - a).length * 0.5
            points.append((a + b + c) / 3.0)
            for _ in range(min(int(area / step), 400)):
                u, v = rng.random(), rng.random()
                if u + v > 1.0:
                    u, v = 1.0 - u, 1.0 - v
                points.append(a + (b - a) * u + (c - a) * v)
        for p in corners:
            lo[shell] = Vector(p) if lo[shell] is None else Vector(map(min, lo[shell], p))
            hi[shell] = Vector(p) if hi[shell] is None else Vector(map(max, hi[shell], p))
        for p in points:
            if ground is not None and p.z <= ground + tol:
                union(ground_node, shell)
            for other in m.near(p, tol):
                if other != shell:
                    union(shell, other)

    for point, reach in supports or ():
        for shell in m.near(point, reach):
            union(ground_node, shell)

    groups = {}
    for s in range(m.count):
        groups.setdefault(find(s), []).append(s)
    root_ground = find(ground_node)
    floating = None
    if root_ground in groups:
        main = root_ground
    elif ground is not None or supports:
        main = None
        low = min((v.z for v in m.verts), default=0.0)
        floating = (f"nothing touches the ground or a declared support: the whole model is held by nothing (lowest point "
                    f"{(low - (ground or 0.0)) * 1000:.0f} mm above the ground)" if ground is not None else
                    "nothing touches a declared support: the whole model is held by nothing")
    else:
        main = max(groups, key=lambda r: sum(tris[s] for s in groups[r])) if groups else None
    stray = []
    for root, members in groups.items():
        if root == main:
            continue
        a = Vector(map(min, *[lo[s] for s in members])) if len(members) > 1 else lo[members[0]]
        b = Vector(map(max, *[hi[s] for s in members])) if len(members) > 1 else hi[members[0]]
        stray.append({"object": m.shell_object[members[0]], "shells": len(members),
                      "triangles": sum(tris[s] for s in members), "unity": _unity((a + b) * 0.5),
                      "size_mm": [round(abs(c) * 1000) for c in (b - a)]})
    stray.sort(key=lambda s: -s["triangles"])
    return {"shells": m.count, "components": len(groups), "stray": stray, "floating": floating}


def check_links(objects, routes, attachments, supports=()):
    """
    routes: [{"name", "points": [Blender xyz], "tol", "free": [indices of points on things outside the model], "part",
    "ends"}]: one shell (the cable, rope or pipe; of `part` when given) must pass within tol of every point, and at every
    end that is not free touch another shell (of the part named in `ends` when given).
    attachments: [{"name", "point", "tol", "parts"}]: two shells meet within tol of the point (a hinge, a clip, a bracket);
    with `parts`, one of each of those two parts (22 October 2026: before, any two nearby pieces satisfied it).
    supports: [{"name", "points", "tol"}]: every point touches the model.
    Returns the failures as readable strings (empty: all hold).
    """
    m = ShellMap(objects)
    problems = []

    def owners(shells):
        return {m.shell_object[s] for s in shells}

    for route in routes:
        tol = route["tol"]
        sets = [m.near(p, tol) for p in route["points"]]
        common = set.intersection(*sets) if sets else set()
        if route.get("part"):
            common = {s for s in common if m.shell_object[s] == route["part"]}
        if not common:
            far = [f"point {i} {_unity(Vector(p))}: nearest surface {m.distance(p) * 1000:.1f} mm, near {sorted(owners(s))}"
                   for i, (p, s) in enumerate(zip(route["points"], sets))]
            problems.append(f"route '{route['name']}': no single piece{' of ' + route['part'] if route.get('part') else ''} "
                            f"passes within {tol * 1000:.0f} mm of all its points ({'; '.join(far)})")
            continue
        for k, i in enumerate((0, len(route["points"]) - 1)):
            if i in route.get("free", ()):
                continue
            touched = sets[i] - common
            want = route["ends"][k] if route.get("ends") else None
            if want and want not in owners(touched):
                problems.append(f"route '{route['name']}': its end {i} at {_unity(Vector(route['points'][i]))} does not "
                                f"touch {want} (touches {sorted(owners(touched)) or 'nothing'})")
            elif not touched:
                problems.append(f"route '{route['name']}': its end {i} at {_unity(Vector(route['points'][i]))} touches "
                                f"nothing within {tol * 1000:.0f} mm (it ends in mid-air)")
    for attachment in attachments:
        found = m.near(attachment["point"], attachment["tol"])
        where = f"attachment '{attachment['name']}' at {_unity(Vector(attachment['point']))}"
        if attachment.get("parts"):
            missing = [p for p in attachment["parts"] if p not in owners(found)]
            if missing:
                problems.append(f"{where}: {', '.join(missing)} not within {attachment['tol'] * 1000:.0f} mm "
                                f"(there: {sorted(owners(found)) or 'nothing'})")
        elif len(found) < 2:
            problems.append(f"{where}: {len(found)} piece(s) within {attachment['tol'] * 1000:.0f} mm, needs two that meet")
    for support in supports:
        for i, point in enumerate(support["points"]):
            if not m.near(point, support["tol"]):
                problems.append(f"support '{support['name']}' point {i} at {_unity(Vector(point))} touches nothing "
                                f"within {support['tol'] * 1000:.0f} mm (nearest {m.distance(point) * 1000:.0f} mm)")
    return problems
