"""
Garden shed: Body (core + lap siding boards), Trim (corner boards, rake and fascia boards,
door and window casings, sill), Roof (sheathing, shingle rows, ridge), Doors (framed double leaf), Hardware
(hinges, handles), Window (sash, muntins, glass).

Reference: Builds/Models/shed_reference.png (video 0:16 and ref 05). User decision (20 October 2026): no vent in the
gable triangle, the siding continues.
Visible: wide light blue-grey lap boards (a shadow line under every board), the gable triangle sided too;
thick white corner boards; thin white rake boards along the roof edge; dark charcoal asphalt shingles; a double door painted the same white
as the casings (a frame, a middle rail and two flat panels on each leaf), bold black wedge hinges, two
curved black handles in the middle; a side window with a thick white frame, 2x2 panes, a sill. The walls are clean (the brown stains at the base
in the video are ivy, not part of the shed).

Construction: every board laps over the one below (bottom edge 2.4 cm out, top edge 0.8 cm; the shadow line comes from this
step); each shingle row is two exposures long (two layers everywhere), its tabs offset by a third of a tab per row. What holds
what: the component plan (model.plan below).

Tiling textures (21 October 2026, like the house): one mesh; every surface gets the tiling texture of its kind in game
(painted wood grain from CC0 ambientCG PaintedWood009C, asphalt granules), UVs in metres along each board's grain, AO and a
per-board tone in the vertex colour. The atlas it had before gave thin faces under a pixel and black seams. The z-fighting gate
made these changes: only the front and back corner boards reach round the corner (they overlapped the side ones), the siding
rows' hidden ends are staggered by 3-4 mm row to row (they lay in one plane under the corner boards and casings), the casings'
side boards stop under their heads, the window's crossing muntins sit at different depths. Hinges: bolder wedge straps (9 cm at
the casing, 6 mm thick), as in the video.

Unity axes: the origin is the middle of the base (ground); the door on the -Z face (facing the garden), the window on the -X (west) face. The sizes match the
in-game collision box: a 2.6 x 2.6 m base, 2.2 m walls, a 1.3 m roof rise (45°; ridge at 3.5 m).
"""
import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402

import opus_model as om  # noqa: E402
from opus_model import V  # noqa: E402

W, D, H, RISE = 2.6, 2.6, 2.2, 1.3               # the proportions in the video: a square base, a door almost as tall as the wall, a 45° roof
HW, HD = W / 2, D / 2
EXPOSURE, LAP = 0.15, 0.025          # the visible height of a board, the part going under the board above
OUT_BOTTOM, OUT_TOP = 0.024, 0.008   # how far a board sticks out of the wall: bottom edge, top edge
CORNER = 0.11                        # corner board width
TRIM_OUT = 0.032                     # how far the casings stick out of the wall plane
DOOR_HALF, DOOR_TOP = 0.83, 1.97     # door opening
WIN_HALF, WIN_BOTTOM, WIN_TOP = 0.3, 0.95, 1.75   # narrow and tall (1.35 ratio with its casing in the video)
OVERHANG_EAVE, OVERHANG_GABLE = 0.16, 0.14
SLOPE = math.atan2(RISE, HW)

model = om.Model("shed", __file__)
model.plan(
    "garden shed: a small timber building with a double door and a side window",
    [("video", "0:16 (ref 05)")],
    [   # name, role, job, attached to, moves, seen/guess/real
        ("WallCore", "structural", "the frame and sheathing the boards are nailed to", ["ground"], "fixed", "guess"),
        ("Siding", "structural", "lap boards, each over the one below; ends under the trim", ["WallCore"], "fixed", "seen"),
        ("CornerBoards", "structural", "cover the siding ends at the corners", ["WallCore"], "fixed", "seen"),
        ("Casings", "structural", "line the door and window openings, cover the board ends", ["WallCore"], "fixed", "seen"),
        ("Sheathing", "structural", "the roof deck on the walls", ["WallCore"], "fixed", "guess"),
        ("Shingles", "functional", "shed the rain: two layers everywhere, over the edges", ["Sheathing"], "fixed", "seen"),
        ("RidgeCaps", "functional", "close the ridge", ["Shingles"], "fixed", "seen"),
        ("RakeBoards", "structural", "trim the gable roof edges", ["WallCore", "Sheathing"], "fixed", "seen"),
        ("Fascia", "structural", "trims the eaves", ["WallCore", "Sheathing"], "fixed", "seen"),
        ("Hinges", "functional", "black wedge straps the leaves turn on", ["Casings"], "fixed", "seen"),
        ("DoorLeaves", "functional", "framed double door: frame, middle rail, two panels", ["Hinges"], "hinge", "seen"),
        ("Handles", "functional", "pull the leaves open, bolted to them", ["DoorLeaves"], "fixed", "seen"),
        ("Sash", "structural", "window frame holding the 2x2 panes", ["Casings"], "fixed", "seen"),
        ("Glass", "functional", "the panes", ["Sash"], "fixed", "seen"),
        ("Sill", "functional", "sheds the water under the window", ["Casings"], "fixed", "seen"),
    ],
    supports=("ground",), tier="complex", category="buildings")
model.features([   # id, tier, components, what must hold, measured by, view
    ("doors_hung", "critical", ["DoorLeaves", "Hinges", "Casings"],
     "each door leaf hangs on its hinges, fixed to the casing, with a handle to pull it", None, "door"),
    ("roof_sheds_rain", "important", ["Shingles", "Sheathing", "RakeBoards", "Fascia"],
     "shingles lap in two layers over the sheathing and overhang the rake and the fascia", None, "eave"),
])
SIDING = model.surface("Siding", "#849CA4", "matte", "Siding: painted wooden lap boards, blue-green-grey (#7B8489 in the video; "
                       "base shifted to green so the game's purple sky light does not turn it purple); matte, wood grain under the paint", material="rough_boards")
TRIM = model.surface("Paint", "#DADCE0", "matte", "Corner, rake and fascia boards, casings, sill, door leaves: white painted wood, "
                     "neutral (in the video the door has the same tone as the casing, not yellow); matte", material="painted_trim")
ROOF = model.surface("Shingles", "#2F352D", "matte", "Roof: asphalt shingles, charcoal grey (the 0:16 frame reads 76/73/71 on the "
                     "roof; the game read 75/70/78 with #2E3331, a little lilac, so the base lost blue); matte, granular, mottled", material="asphalt_3tab")
IRON = model.surface("Metal", "#1D1D20", "satin", "Hinge, handle, bolt: black painted iron; dark with a little light in the video", material="painted_metal")
GLASS = model.surface("Glass", "#30363A", "glossy", "Window glass: dark, a slight reflection", material="glass")


def slab(bm, corners, material=0):
    """An 8-corner box (bottom 4 + top 4 corners in order): parts such as a board with slanted ends, a rake board."""
    verts = [bm.verts.new(c) for c in corners]
    faces = []
    for quad in ((0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)):
        face = bm.faces.new([verts[i] for i in quad])
        face.material_index = material
        faces.append(face)
    return faces


class Wall:
    """Wall frame: point o, u along the wall, n outwards; P = o + u*a + up*v + n*w."""

    def __init__(self, origin, u, n):
        self.o, self.u, self.n = Vector(origin), Vector(u), Vector(n)

    def p(self, a, v, w):
        return self.o + self.u * a + Vector((0, 1, 0)) * v + self.n * w


FRONT = Wall((0, 0, -HD), (1, 0, 0), (0, 0, -1))
BACK = Wall((0, 0, HD), (-1, 0, 0), (0, 0, 1))
WEST = Wall((-HW, 0, 0), (0, 0, 1), (-1, 0, 0))
EAST = Wall((HW, 0, 0), (0, 0, -1), (1, 0, 0))


def board(bm, wall, a0b, a1b, a0t, a1t, v0, v1, material=0):
    """Lap board: bottom edge OUT_BOTTOM, top edge OUT_TOP out; the ends can be slanted (gable triangle)."""
    slab(bm, [wall.p(a0b, v0, 0), wall.p(a1b, v0, 0), wall.p(a1b, v0, OUT_BOTTOM), wall.p(a0b, v0, OUT_BOTTOM),
              wall.p(a0t, v1, 0), wall.p(a1t, v1, 0), wall.p(a1t, v1, OUT_TOP), wall.p(a0t, v1, OUT_TOP)], material)


def wall_boards(bm, wall, half_length, holes=(), gable=False):
    """The boards of one wall: from the bottom up; skips the openings (a0, a1, v0, v1); in the gable triangle the ends are cut with the slope."""
    a_min, a_max = -half_length + CORNER * 0.5, half_length - CORNER * 0.5
    v = 0.04
    top = H + (RISE if gable else 0.0)
    row = 0
    while v < top - 0.02:
        v0, v1 = v, min(v + EXPOSURE + LAP, top)
        # Hidden board ends (under corner boards and casings) staggered row to row: in one plane they would overlap (z-fighting)
        stagger = 0.003 if row % 2 else 0.0
        row += 1
        if gable:
            # Gable triangle only: starts where the lower wall's rows end (a separate call builds the lower wall)
            if v + EXPOSURE > H + 0.01:
                def edge(y):
                    return max(0.0, half_length * (1.0 - (max(y, H) - H) / RISE) - 0.06 - stagger * 1.3)
                v0 = max(v0, H - 0.005)
                eb, et = edge(v0), edge(v1)
                if et > 0.05:
                    board(bm, wall, -eb, eb, -et, et, v0, v1)
        else:
            spans = [(a_min + stagger, a_max - stagger)]
            for h0, h1, hv0, hv1 in holes:
                h0, h1 = h0 + stagger, h1 - stagger
                if v1 > hv0 and v0 < hv1:
                    nxt = []
                    for s0, s1 in spans:
                        if h0 > s0:
                            nxt.append((s0, min(s1, h0)))
                        if h1 < s1:
                            nxt.append((max(s0, h1), s1))
                    spans = nxt
            for s0, s1 in spans:
                if s1 - s0 > 0.02:
                    board(bm, wall, s0, s1, s0, s1, v0, v1)
        v += EXPOSURE


def build_body():
    # Core: behind the walls and the gable triangles (a pentagon cross-section, along Z)
    bm = bmesh.new()
    pent = [(-HW, 0.0), (HW, 0.0), (HW, H), (0.0, H + RISE), (-HW, H)]
    om.loft(bm, [[V(x, y, z) for x, y in pent] for z in (-HD, HD)], material=0)
    door_hole = (-DOOR_HALF - 0.09, DOOR_HALF + 0.09, 0.0, DOOR_TOP + 0.1)
    window_hole = (-WIN_HALF - 0.07, WIN_HALF + 0.07, WIN_BOTTOM - 0.06, WIN_TOP + 0.07)
    wall_boards(bm, FRONT, HW, holes=[door_hole])
    wall_boards(bm, FRONT, HW, gable=True)
    wall_boards(bm, BACK, HW)
    wall_boards(bm, BACK, HW, gable=True)
    wall_boards(bm, WEST, HD, holes=[window_hole])
    wall_boards(bm, EAST, HD)
    return bm


def flat_board(bm, wall, a0, a1, v0, v1, w0, w1, material=0):
    slab(bm, [wall.p(a0, v0, w0), wall.p(a1, v0, w0), wall.p(a1, v0, w1), wall.p(a0, v0, w1),
              wall.p(a0, v1, w0), wall.p(a1, v1, w0), wall.p(a1, v1, w1), wall.p(a0, v1, w1)], material)


def build_trim():
    bm = bmesh.new()
    # Corner boards: two boards at every corner (L), TRIM_OUT out from the wall
    # Only the front and back boards reach round the corner (TRIM_OUT); the side boards butt against them
    for wall, half, reach in ((FRONT, HW, TRIM_OUT), (BACK, HW, TRIM_OUT), (WEST, HD, 0.0), (EAST, HD, 0.0)):
        for side in (-1, 1):
            a0, a1 = sorted((side * half, side * (half - CORNER)))
            if side > 0:
                a1 += reach
            else:
                a0 -= reach
            # 4 mm taller than the wall: their tops must not share the plane of the top siding boards (they end in the roof)
            flat_board(bm, wall, a0, a1, 0.0, H + 0.004, 0.0, TRIM_OUT)

    # Rake boards: along the top edge of the front and back gable triangles, under the roof
    for wall in (FRONT, BACK):
        for side in (-1, 1):
            run = HW + OVERHANG_EAVE * math.cos(SLOPE)
            ex, ey = side * run, H - OVERHANG_EAVE * math.sin(SLOPE)
            w0, w1 = TRIM_OUT - 0.002, TRIM_OUT + 0.025
            down = 0.18 / math.cos(SLOPE)   # in the video the rake board is wide and prominent
            slab(bm, [wall.p(0, H + RISE - down, w0), wall.p(ex, ey - down, w0), wall.p(ex, ey - down, w1),
                      wall.p(0, H + RISE - down, w1), wall.p(0, H + RISE, w0), wall.p(ex, ey, w0), wall.p(ex, ey, w1),
                      wall.p(0, H + RISE, w1)])
    # Fascia boards: on top of the side walls, under the roof edge
    for side in (-1, 1):
        x = side * (HW + OVERHANG_EAVE * math.cos(SLOPE))
        y = H - OVERHANG_EAVE * math.sin(SLOPE)
        lo, hi = sorted((x, x + side * 0.025))
        om.box(bm, (lo, y - 0.16, -HD - OVERHANG_GABLE), (hi, y, HD + OVERHANG_GABLE), material=0)
        # Soffit: from the wall to the fascia board
        lo, hi = sorted((side * HW, x))
        om.box(bm, (lo, y - 0.02, -HD - OVERHANG_GABLE), (hi, y, HD + OVERHANG_GABLE), material=0)

    # Door casing: two posts + a head; sill
    for side in (-1, 1):
        a0, a1 = sorted((side * DOOR_HALF, side * (DOOR_HALF + 0.09)))
        flat_board(bm, FRONT, a0, a1, 0.0, DOOR_TOP, 0.0, TRIM_OUT)
    flat_board(bm, FRONT, -DOOR_HALF - 0.11, DOOR_HALF + 0.11, DOOR_TOP, DOOR_TOP + 0.11, 0.0, TRIM_OUT + 0.006)
    flat_board(bm, FRONT, -DOOR_HALF - 0.12, DOOR_HALF + 0.12, DOOR_TOP + 0.11, DOOR_TOP + 0.13, 0.0, TRIM_OUT + 0.016)

    # Window casing: four sides, the bottom sill sticks out
    for side in (-1, 1):
        a0, a1 = sorted((side * WIN_HALF, side * (WIN_HALF + 0.07)))
        flat_board(bm, WEST, a0, a1, WIN_BOTTOM, WIN_TOP, 0.0, TRIM_OUT)
    flat_board(bm, WEST, -WIN_HALF - 0.07, WIN_HALF + 0.07, WIN_TOP, WIN_TOP + 0.07, 0.0, TRIM_OUT)
    flat_board(bm, WEST, -WIN_HALF - 0.1, WIN_HALF + 0.1, WIN_BOTTOM - 0.045, WIN_BOTTOM, 0.0, TRIM_OUT + 0.045)
    flat_board(bm, WEST, -WIN_HALF - 0.06, WIN_HALF + 0.06, WIN_BOTTOM - 0.11, WIN_BOTTOM - 0.045, 0.0, TRIM_OUT)
    return bm


def build_roof():
    """
    Two sloped faces: a sheathing board + shingle rows + ridge caps. Like the house (21 October 2026): every strip two exposures +
    1 cm long (two layers everywhere, the slots show the strip below), rows offset by a third of a tab (with a half offset the
    overlapping rows' slots met and z-fought), the strips shade with the roof plane's normal and take UVs from their butt, so
    the row lines come from the mipmapped "shingle" texture (the geometric butts alone made moire at a distance).
    """
    bm = om.preset_layers(bmesh.new())
    length = math.hypot(HW, RISE) + OVERHANG_EAVE
    z0, z1 = -HD - OVERHANG_GABLE, HD + OVERHANG_GABLE
    tab = 0.333
    for side in (-1, 1):
        d = Vector((side * math.cos(SLOPE), -math.sin(SLOPE), 0))     # from the ridge to the eave
        nrm = Vector((side * math.sin(SLOPE), math.cos(SLOPE), 0))    # out of the roof
        ridge = Vector((0, H + RISE, 0))
        # Sheathing board (2.2 cm thick)
        p0, p1 = ridge, ridge + d * length
        sheathing = slab(bm, [p0 + V(0, 0, z0), p1 + V(0, 0, z0), p1 + V(0, 0, z1), p0 + V(0, 0, z1),
                              p0 + nrm * 0.022 + V(0, 0, z0), p1 + nrm * 0.022 + V(0, 0, z0), p1 + nrm * 0.022 + V(0, 0, z1),
                              p0 + nrm * 0.022 + V(0, 0, z1)])
        om.preset_faces(bm, sheathing, p0, Vector((0, 0, 1)), Vector((0, 0, 0)), v_offset=0.06)
        # Shingle rows: from the eave to the ridge; every row covers the upper part of the previous one
        exposure = 0.13
        course = 2.0 * exposure + 0.01
        s = length + 0.01
        row = 0
        while s > 0.06:
            # The rows reaching the ridge are cut there, each 4 mm short of the one before (flush, their end faces z-fought)
            s_top = s - course if s - course > 0.012 else 0.004 * (row % 3)
            shift = (row % 3) * tab / 3.0
            z = z0 - shift
            while z < z1:
                # At the gable ends the rows' cut ends are staggered (in one plane the overlapping rows would z-fight)
                inset = 0.004 + 0.0025 * (row % 3)
                za, zb = max(z, z0) + inset, min(z + tab, z1) - inset
                if zb - za > 0.03:
                    base0, base1 = ridge + d * s + nrm * 0.022, ridge + d * s_top + nrm * 0.022
                    t0, t1 = 0.011, 0.003   # the lower (visible) edge thick, the upper thin
                    strip = slab(bm, [base0 + V(0, 0, za), base1 + V(0, 0, za), base1 + V(0, 0, zb), base0 + V(0, 0, zb),
                                      base0 + nrm * t0 + V(0, 0, za), base1 + nrm * t1 + V(0, 0, za), base1 + nrm * t1 + V(0, 0, zb),
                                      base0 + nrm * t0 + V(0, 0, zb)])
                    om.preset_faces(bm, strip, base0 + V(0, 0, za), Vector((0, 0, 1)), -d, v_scale=om.SHINGLE_ROW / exposure,
                                    normal=nrm)
                z += tab
            s -= exposure
            row += 1
    # Ridge: cap shingles covering the join of the two faces (each a bent strip)
    cap = 0.25
    z = z0
    count = 0
    while z < z1 - 0.02:
        za, zb = z, min(z + cap, z1)
        # Every other cap 4 mm wider: the overlapping caps' side edges must not share a plane (z-fighting)
        spread = 0.12 + (0.004 if count % 2 else 0.0)
        count += 1
        pts = []
        for side in (-1, 1):
            d = Vector((side * math.cos(SLOPE), -math.sin(SLOPE), 0))
            nrm = Vector((side * math.sin(SLOPE), math.cos(SLOPE), 0))
            pts.append(Vector((0, H + RISE, 0)) + d * spread + nrm * 0.03)
        top = Vector((0, H + RISE + 0.055, 0))
        prof = [pts[0], top, pts[1]]
        # Cross-section: three points on the outer face, the inner face 1 cm inside
        inner = [p - Vector((0, 0.012, 0)) for p in prof]
        ring = prof + list(reversed(inner))
        faces = om.loft(bm, [[V(p.x, p.y, za) for p in ring], [V(p.x, p.y + 0.006, zb) for p in ring]], material=0)
        # Each cap's end at zb lies on top of the next cap: that end is its butt
        om.preset_faces(bm, faces, V(0, 0, zb), Vector((1, 0, 0)), Vector((0, 0, -1)), v_scale=om.SHINGLE_ROW / (cap - 0.02))
        z += cap - 0.02
    return bm


RAIL = 0.16                              # the top and bottom rails of the leaf (the hinges are screwed to them)
MID_RAIL = (0.84, 0.94)                  # middle rail; the handles just above it, on the inner stile


def build_doors():
    """
    Framed double leaf: stiles and top/middle/bottom rails at full thickness, two flat panels set back 1.4 cm between them
    (the panel stays inside the frame; with a one-piece backing its corners would sit under the frame and spread the AO over the whole
    panel). 8 mm between the leaves.
    """
    bm = bmesh.new()
    back, panel, face = -0.02, 0.012, 0.026   # relative to the wall plane: leaf back, panel face, frame face
    stile = 0.1
    for side in (-1, 1):
        a0, a1 = sorted((side * 0.004, side * DOOR_HALF))
        v0, v1 = 0.04, DOOR_TOP - 0.006
        flat_board(bm, FRONT, a0, a0 + stile, v0, v1, back, face)
        flat_board(bm, FRONT, a1 - stile, a1, v0, v1, back, face)
        for r0, r1 in ((v0, v0 + RAIL), MID_RAIL, (v1 - RAIL, v1)):
            flat_board(bm, FRONT, a0 + stile, a1 - stile, r0, r1, back, face)
        for p0, p1 in ((v0 + RAIL, MID_RAIL[0]), (MID_RAIL[1], v1 - RAIL)):
            flat_board(bm, FRONT, a0 + stile, a1 - stile, p0, p1, back, panel)
    return bm


def build_iron():
    """Wedge strap hinges (screwed to the top and bottom rails, hinged to the casing; at the very top and bottom of the leaf as in
    the video: bold black wedges, about a quarter of the leaf long) and curved handles bolted to the inner stile."""
    bm = bmesh.new()
    face = 0.026 + 0.002
    for side in (-1, 1):
        edge = side * (DOOR_HALF - 0.01)
        for v in (DOOR_TOP - 0.006 - RAIL * 0.5, 0.04 + RAIL * 0.5):
            tip = side * (DOOR_HALF - 0.25)
            pts = [FRONT.p(edge, v - 0.045, face), FRONT.p(edge, v + 0.045, face), FRONT.p(tip, v + 0.011, face),
                   FRONT.p(tip, v - 0.011, face)]
            off = FRONT.n * 0.006
            slab(bm, pts + [p + off for p in pts])
            # Hinge knuckle (pin): a vertical cylinder where the casing and the leaf meet
            om.sweep(bm, [FRONT.p(side * (DOOR_HALF + 0.01), v - 0.04, face + 0.004),
                          FRONT.p(side * (DOOR_HALF + 0.01), v + 0.04, face + 0.004)], 0.011, 12)
            # Bolt heads
            for t in (0.35, 0.7):
                a = edge + (tip - edge) * t
                om.revolve_at(bm, [(0.0, 0.0), (0.0, 0.007), (0.003, 0.006), (0.005, 0.0)], 10,
                              FRONT.p(a, v, face + 0.005), FRONT.n)
        # Curved handle (D): vertical, near the inner edge of the leaf
        a = side * 0.07
        arc = [FRONT.p(a, 0.98, face), FRONT.p(a, 0.99, face + 0.035), FRONT.p(a, 1.09, face + 0.05),
               FRONT.p(a, 1.19, face + 0.035), FRONT.p(a, 1.2, face)]
        om.sweep(bm, om.spline(arc, 6), 0.009, 10)
        for vv in (0.98, 1.2):
            om.revolve_at(bm, [(0.0, 0.0), (0.0, 0.016), (0.006, 0.014), (0.008, 0.0)], 12, FRONT.p(a, vv, face), FRONT.n)
    return bm


def build_window():
    """Recessed window: sash frame, 2x2 muntins (as in the video), glass (4 cm behind the casing)."""
    bm = bmesh.new()
    glass_w = 0.004
    flat_board(bm, WEST, -WIN_HALF, WIN_HALF, WIN_BOTTOM, WIN_TOP, -0.01, glass_w, material=1)
    sash0, sash1 = glass_w - 0.002, glass_w + 0.016
    flat_board(bm, WEST, -WIN_HALF, -WIN_HALF + 0.045, WIN_BOTTOM, WIN_TOP, sash0, sash1)
    flat_board(bm, WEST, WIN_HALF - 0.045, WIN_HALF, WIN_BOTTOM, WIN_TOP, sash0, sash1)
    flat_board(bm, WEST, -WIN_HALF + 0.045, WIN_HALF - 0.045, WIN_TOP - 0.045, WIN_TOP, sash0, sash1)
    flat_board(bm, WEST, -WIN_HALF + 0.045, WIN_HALF - 0.045, WIN_BOTTOM, WIN_BOTTOM + 0.05, sash0, sash1)
    flat_board(bm, WEST, -0.012, 0.012, WIN_BOTTOM + 0.05, WIN_TOP - 0.045, sash0, sash1 - 0.004)
    v = WIN_BOTTOM + 0.05 + (WIN_TOP - 0.045 - WIN_BOTTOM - 0.05) * 0.5
    flat_board(bm, WEST, -WIN_HALF + 0.045, WIN_HALF - 0.045, v - 0.012, v + 0.012, sash0 + 0.0012,
               sash1 - 0.0055)   # behind the upright's face, in front of its back
    return bm


model.part("Body", build_body(), [SIDING], unity=True, bevel={"width": 0.002, "segments": 1, "angle": 35.0},
           tone_jitter=0.05, ao_grid=(0.25, None, 0.25))
model.part("Trim", build_trim(), [TRIM], unity=True, bevel={"width": 0.004, "segments": 1, "angle": 35.0},
           ao_grid=(0.3, 0.3, 0.3))
model.part("Roof", build_roof(), [ROOF], unity=True, tone_jitter=0.08)
model.part("Doors", build_doors(), [TRIM], unity=True, bevel={"width": 0.003, "segments": 1, "angle": 35.0},
           ao_grid=(None, 0.3, None))
model.part("Hardware", build_iron(), [IRON], unity=True)
model.part("Window", build_window(), [TRIM, GLASS], unity=True, bevel={"width": 0.002, "segments": 1, "angle": 35.0})


def unity_dir(x, y, z):
    return (-x, -z, y)


everything = ["Shed"]
model.finish(
    budget=45000,
    join="Shed",
    tiled=True,
    ground=0.0,
    ao_distance=0.3,
    views=[
        {"file": "front_left", "label": "Front-left (the angle in the video)", "objects": everything, "direction": unity_dir(-0.55, 0.15, -1.0),
         "ground": 0.0},
        {"file": "front", "label": "From the front: door, gable siding", "objects": everything, "direction": unity_dir(0.0, 0.1, -1.0), "ground": 0.0},
        {"file": "side", "label": "From the west: window", "objects": everything, "direction": unity_dir(-1.0, 0.15, -0.25), "ground": 0.0},
        {"file": "back", "label": "Back-right", "objects": everything, "direction": unity_dir(0.8, 0.45, 1.0), "ground": 0.0},
        {"file": "door", "label": "Door up close: frame, hinge, handle", "objects": everything, "direction": unity_dir(0.25, 0.1, -1.0),
         "target": unity_dir(0.0, 1.1, -1.3), "radius": 1.0, "ground": 0.0},
        {"file": "eave", "label": "Eave and shingles up close", "objects": everything, "direction": unity_dir(-0.7, 0.2, -0.9),
         "target": unity_dir(-HW, H, -HD), "radius": 0.7, "ground": 0.0},
    ],
    references=[
        {"label": "Reference: video 0:16", "path": "docs/reference/28_shed_front.png", "crop": [330, 20, 330, 240]},
        {"label": "Reference: ref 05 (window)", "path": "docs/reference/05_ivy_covered_shed.png", "crop": [180, 30, 280, 250]},
    ],
)
