"""
House (two storeys, side-gabled roof) and the deck on the garden side. Parts: Body (core + lap siding
boards), Foundation (concrete band, street door step, downspout stones), Trim (corner boards, frieze, fascia and
rake boards, soffits, window and door casings, sills), Windows (sliding double sash, glass), Doors (garden and
street door, glass door), Roof (sheathing, shingle rows, ridge), Gutters (gutter, downspouts), Deck (decking,
rim joists, steps), Railing (posts, handrail, balusters, lattice skirt, porch posts, beam,
ceiling, porch rake boards), Porch (the porch roof's shingles), Hardware (door handles, lamp, vent).

Reference: video 0:57 (docs/reference/29: garden facade), 0:41.6 (30: deck), 0:53.5 (31: from the side). User decision
(20 October 2026): no shutters. Visible in the video: wide light grey lap siding; on the upper floor five evenly spaced tall
sliding double-sash windows (light glass, thin casing); on the ground floor windows on the left, a glazed door and a double glass
door on the right, above them a gently sloped porch roof covering the right half of the facade (sitting in front of the deck on posts);
a low deck along the facade: a cedar-coloured rim joist, a railing with white balusters, a white diagonal lattice underneath;
grey-brown asphalt shingles; a rose-brown gutter at the eave, a downspout at the corner; a thin black vent pipe on the roof; no chimney.

Mechanical logic: the component plan (model.plan below); the downspouts' routes are measured (model.route).

Unity axes: the origin is the middle of the body's base (ground); the garden facade -Z (really the back of the house), the street facade +Z, the gable
walls ±X. The sizes match the in-game collision boxes: body 16 x 10 m, eave 6.25 m; deck x -4.2..7.8,
z -7.8..-5, top 0.5 m; two steps.
"""
import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402

import opus_model as om  # noqa: E402
from opus_model import V  # noqa: E402

W, D, H, RISE = 16.0, 10.0, 6.25, 3.4
HW, HD = W / 2, D / 2
SLOPE = math.atan2(RISE, HD)
FLOOR = 0.5                            # ground floor level = deck top
FOUND_TOP = 0.42                       # top of the concrete foundation band; the siding starts here
EXPOSURE, LAP = 0.19, 0.03             # the visible height of a board, the part going under the board above
OUT_BOTTOM, OUT_TOP = 0.026, 0.009     # how far a board sticks out of the wall: bottom edge, top edge
CORNER = 0.14                          # corner board width
TRIM_OUT = 0.036                       # how far the casings stick out of the wall plane
OVH_EAVE, OVH_RAKE = 0.38, 0.3         # eave (along the slope) and rake overhang
EAVE_Y = H - OVH_EAVE * math.sin(SLOPE)
SOFFIT_Y = EAVE_Y - 0.02
FRIEZE = 0.22                          # frieze board under the eave
CASING, HEAD = 0.1, 0.14               # casing width, head casing height
WIN_W = 0.82                           # window opening (sashes + frame)
GROUND_WIN = (1.35, 2.85)
UPPER_WIN = (4.0, 5.5)
DOOR_TOP = FLOOR + 2.05

# Deck and porch
DX0, DX1 = -4.2, 7.8
DZ0, DZ1 = -HD - 2.8, -HD
STEP0, STEP1 = -0.25, 1.46
PORCH_X0, PORCH_X1 = 1.3, HW + 0.12
PORCH_POSTS = (1.55, 4.65, 7.72)
POST_Z = DZ0 + 0.08
LEDGER_TOP = 3.62
BEAM_TOP = 2.88
PORCH_K = (LEDGER_TOP - BEAM_TOP) / (DZ1 - POST_Z)   # porch slope (rise / depth)
PORCH_EAVE_Z = DZ0 - 0.25

model = om.Model("house", __file__)
model.plan(
    "two-storey house with a side-gabled roof, a deck on the garden side and a porch roof over its right half",
    [("video", "0:57 (ref 29), 0:41.6 (ref 30), 0:53.5 (ref 31)")],
    [   # name, role, job, attached to, moves, seen/guess/real
        ("Foundation", "structural", "concrete band the walls stand on", ["ground"], "fixed", "seen"),
        ("WallCore", "structural", "the frame and sheathing everything else is fixed to", ["Foundation"], "fixed", "guess"),
        ("Siding", "structural", "lap boards, each over the one below; ends under the trim", ["WallCore"], "fixed", "seen"),
        ("CornerBoards", "structural", "cover the siding ends; tops follow the soffit slope", ["WallCore"], "fixed", "seen"),
        ("Casings", "structural", "line the openings, jamb boards inside, cover the board ends", ["WallCore"], "fixed", "seen"),
        ("Windows", "functional", "sliding double sashes in the openings", ["Casings"], "slide", "seen"),
        ("Doors", "functional", "garden, glass and street doors in their openings", ["Casings"], "hinge", "seen"),
        ("Sheathing", "structural", "the roof deck on the walls, under the overhangs", ["WallCore"], "fixed", "guess"),
        ("Shingles", "functional", "shed the rain: two layers, over the rake and fascia", ["Sheathing"], "fixed", "seen"),
        ("RidgeCaps", "functional", "close the ridge", ["Shingles"], "fixed", "seen"),
        ("Fascia", "structural", "eave board the gutter hangs on", ["WallCore", "Sheathing"], "fixed", "seen"),
        ("Soffits", "structural", "close the underside of the overhangs", ["Fascia", "WallCore"], "fixed", "seen"),
        ("RakeBoards", "structural", "trim the gable edges, cover the fascia's end, cut plumb", ["WallCore", "Sheathing"],
         "fixed", "seen"),
        ("VentPipe", "functional", "plumbing vent through the roof", ["Sheathing"], "fixed", "seen"),
        ("Gutter", "functional", "collects the rain at the eave", ["Fascia"], "fixed", "seen"),
        ("Downspouts", "functional", "from the gutter's end to the gable wall, down it, out over a splash block", ["Gutter"],
         "fixed", "seen"),
        ("SplashBlocks", "functional", "lead the water away from the wall", ["ground"], "fixed", "guess"),
        ("SkirtPosts", "structural", "corner posts of the deck skirt", ["ground"], "fixed", "guess"),
        ("DeckFrame", "structural", "ledger on the wall, rim joists, joists every 40 cm", ["WallCore", "SkirtPosts"], "fixed",
         "guess"),
        ("Decking", "structural", "cedar boards resting on the joists and rim joists", ["DeckFrame"], "fixed", "seen"),
        ("Lattice", "decorative", "white diagonal skirt behind the posts, hides the frame", ["SkirtPosts"], "fixed", "seen"),
        ("Steps", "functional", "notched stringers, treads, risers up to the deck", ["DeckFrame", "ground"], "fixed", "seen"),
        ("Railing", "functional", "posts bolted inside the rim joists, rails, balusters", ["DeckFrame"], "fixed", "seen"),
        ("PorchPosts", "structural", "carry the porch beam, standing on the decking", ["Decking"], "fixed", "seen"),
        ("PorchRoof", "functional", "covers the deck's right half: ledger on the wall, beam on the posts",
         ["WallCore", "PorchPosts"], "fixed", "seen"),
        ("Lamp", "functional", "gooseneck barn light right of the glass door", ["WallCore"], "fixed", "seen"),
        ("DoorHandles", "functional", "open the doors", ["Doors"], "fixed", "guess"),
    ],
    supports=("ground",), tier="complex", category="buildings")
model.features([   # id, tier, components, what must hold, measured by, view
    ("stairs_carried", "critical", ["Steps", "DeckFrame"],
     "notched stringers carry the treads from the ground up to the deck frame", None, "steps_side"),
    ("deck_carried", "critical", ["DeckFrame", "SkirtPosts", "WallCore"],
     "the deck frame rests on a ledger on the wall and on posts at its outer edge", None, "deck_under"),
    ("porch_roof_carried", "critical", ["PorchRoof", "PorchPosts", "WallCore"],
     "the porch roof rests on the wall and on a beam carried by the posts", None, "garden"),
    ("downspouts", "important", ["Downspouts", "Gutter", "SplashBlocks"],
     "each downspout leaves the gutter, runs down the wall and ends over a splash block", "route:Downspout_*", "eave"),
])
# Tiling textures (21 October 2026): one mesh; every surface gets the tiling texture of its kind in game (painted wood grain
# from CC0 ambientCG PaintedWood009C, asphalt granules, concrete), UVs in metres along each board's grain, AO and a per-board
# tone in the vertex colour. A 4096 atlas over the whole house gave 76 px/m and thin parts under a pixel (black lines); tiling
# is sharp at any distance and the colour variants keep working by material colour.
SIDING = model.surface("Siding", "#A6B0B8", "matte",
                       "Siding: painted wooden lap boards, light grey (#A9A5AA in the video; base shifted to blue against the game's purple "
                       "sky light); matte, wood grain under the paint. Changes in game with the house colour variants", material="lap_siding")
TRIM = model.surface("Paint", "#D6DBE3", "matte", "Corner boards, frieze, eave, casings, window sashes, railing, lattice: white painted wood, a cool light grey in the video (base slightly blue so it does not turn cream in the sun); matte", material="painted_trim")
DOOR = model.surface("Paint", "#94817F", "matte",
                     "Garden and street door: rose-brown painted wood (#97807F in the video); matte. Changes with the house colour variants", material="painted_trim")
ROOF = model.surface("Shingles", "#535F61", "matte", "Asphalt shingles: neutral grey-mauve (the 0:53 and 0:57 frames read about "
                     "137/128/128 on the roof at 20-25 m; the game read 158/140/137 at 24 m with #77756F, then 153/139/138 with "
                     "#6F7373: the haze adds a lot, so the base went darker and less red); matte, granular, mottled", material="asphalt_blend")
GUTTER = model.surface("Metal", "#9A7C78", "satin", "Gutter and downspouts: painted aluminium, rose-brown (#9B8284 at the eave in the video); satin", material="painted_metal")
DECK = model.surface("Planks", "#C49A7A", "matte", "Decking, joists, rim joists, steps: cedar (#C0A27E at the edge in the video); matte, wood grain", material="cedar_decking")
FOUND = model.surface("Concrete", "#A19E99", "matte", "Foundation band, step, splash blocks: concrete; matte", material="concrete")
GLASS = model.surface("Glass", "#C8CED6", "glossy", "Window glass: light, reflecting the sky (light-coloured glass in the video); glossy", material="glass")
IRON = model.surface("Metal", "#1F1F22", "satin", "Door handles, lamp body: black painted metal; satin", material="painted_metal")
PIPE = model.surface("Plastic", "#26262A", "matte", "Vent pipe: black plastic (a thin black pipe on the roof in the video); matte", material="plastic")
LAMP = model.surface("Glass", "#EFE3C4", "glossy", "Lamp bulb: frosted, warm white; glossy", material="frosted_glass")
SHADE = model.surface("Metal", "#55585E", "satin", "Lamp shade: grey enamelled steel (a grey dish on an arm beside the glass door "
                      "at 0:57 in the video); satin", material="enamel")
SHADE_IN = model.surface("Paint", "#E6E2D8", "matte", "Inside of the lamp shade: white enamel, matte", material="enamel")



def slab(bm, corners, material=0):
    """An 8-corner box (bottom 4 + top 4 corners in order)."""
    verts = [bm.verts.new(c) for c in corners]
    faces = []
    for quad in ((0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)):
        face = bm.faces.new([verts[i] for i in quad])
        face.material_index = material
        faces.append(face)
    return faces


class Wall:
    """Wall frame: point o, u along the wall, n outwards; P = o + u*a + up*v + n*w."""

    def __init__(self, origin, u, n, half):
        self.o, self.u, self.n, self.half = Vector(origin), Vector(u), Vector(n), half

    def p(self, a, v, w):
        return self.o + self.u * a + Vector((0, 1, 0)) * v + self.n * w


FRONT = Wall((0, 0, -HD), (1, 0, 0), (0, 0, -1), HW)     # garden facade
BACK = Wall((0, 0, HD), (-1, 0, 0), (0, 0, 1), HW)       # street facade
WEST = Wall((-HW, 0, 0), (0, 0, 1), (-1, 0, 0), HD)      # gable
EAST = Wall((HW, 0, 0), (0, 0, -1), (1, 0, 0), HD)       # gable
GABLES = (WEST, EAST)


def flat_board(bm, wall, a0, a1, v0, v1, w0, w1, material=0):
    slab(bm, [wall.p(a0, v0, w0), wall.p(a1, v0, w0), wall.p(a1, v0, w1), wall.p(a0, v0, w1),
              wall.p(a0, v1, w0), wall.p(a1, v1, w0), wall.p(a1, v1, w1), wall.p(a0, v1, w1)], material)


# ---------- Openings ----------

class Opening:
    def __init__(self, wall, center, width, v0, v1, kind):
        self.wall, self.c, self.width, self.v0, self.v1, self.kind = wall, center, width, v0, v1, kind

    @property
    def a0(self):
        return self.c - self.width / 2

    @property
    def a1(self):
        return self.c + self.width / 2


OPENINGS = []
for a in (-6.2, -3.1, 0.0):
    OPENINGS.append(Opening(FRONT, a, WIN_W, *GROUND_WIN, "window"))
OPENINGS.append(Opening(FRONT, 3.2, 0.92, FLOOR, DOOR_TOP, "door"))
OPENINGS.append(Opening(FRONT, 5.9, 1.5, FLOOR, DOOR_TOP, "glass_door"))
for a in (-6.2, -3.1, 3.1, 6.2):
    OPENINGS.append(Opening(BACK, a, WIN_W, *GROUND_WIN, "window"))
OPENINGS.append(Opening(BACK, 0.0, 0.95, FLOOR, DOOR_TOP, "door"))
for wall in (FRONT, BACK):
    for a in (-6.2, -3.1, 0.0, 3.1, 6.2):
        OPENINGS.append(Opening(wall, a, WIN_W, *UPPER_WIN, "window"))
for wall in GABLES:
    for a in (-2.0, 2.0):
        OPENINGS.append(Opening(wall, a, WIN_W, *GROUND_WIN, "window"))
        OPENINGS.append(Opening(wall, a, WIN_W, *UPPER_WIN, "window"))


def holes_of(wall):
    """Gaps in the siding: down to 2 cm below the casing (the board ends hide under the casing)."""
    holes = []
    for o in OPENINGS:
        if o.wall is wall:
            bottom = 0.0 if o.kind != "window" else o.v0 - 0.12
            holes.append((o.a0 - CASING + 0.02, o.a1 + CASING - 0.02, bottom, o.v1 + HEAD - 0.02))
    return holes


# ---------- Body ----------

def board(bm, wall, a0b, a1b, a0t, a1t, v0, v1):
    slab(bm, [wall.p(a0b, v0, 0), wall.p(a1b, v0, 0), wall.p(a1b, v0, OUT_BOTTOM), wall.p(a0b, v0, OUT_BOTTOM),
              wall.p(a0t, v1, 0), wall.p(a1t, v1, 0), wall.p(a1t, v1, OUT_TOP), wall.p(a0t, v1, OUT_TOP)])


def wall_boards(bm, wall, top, holes=(), gable=False):
    """Boards from the bottom up; skips the gaps. gable: only the gable triangle (the ends cut with the roof slope)."""
    half = wall.half
    a_min, a_max = -half + CORNER * 0.5, half - CORNER * 0.5
    v = FOUND_TOP
    row = 0
    while v < top - 0.02:
        v0, v1 = v, min(v + EXPOSURE + LAP, top)
        # Hidden board ends (under corner boards and casings) staggered row to row: in one plane they z-fight
        stagger = 0.003 if row % 2 else 0.0
        row += 1
        if gable:
            if v + EXPOSURE > H + 0.01:
                def edge(y):
                    return max(0.0, half * (1.0 - (max(y, H) - H) / RISE) - 0.03 - stagger * 1.3)
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
                if s1 - s0 > 0.03:
                    board(bm, wall, s0, s1, s0, s1, v0, v1)
        v += EXPOSURE


def build_body():
    # Core: a pentagon cross-section along X; window and door openings carved 12 cm deep
    core = bmesh.new()
    pent = [(-HD, 0.0), (-HD, H), (0.0, H + RISE), (HD, H), (HD, 0.0)]
    om.loft(core, [[V(x, y, z) for z, y in pent] for x in (-HW, HW)], material=0)
    cutters = []
    for o in OPENINGS:
        c = bmesh.new()
        flat_board(c, o.wall, o.a0, o.a1, o.v0, o.v1, -0.12, 0.05)
        cutters.append(c)
    bm = om.carve(core, cutters)
    for wall in (FRONT, BACK):
        wall_boards(bm, wall, SOFFIT_Y - FRIEZE + 0.02, holes_of(wall))
    for wall in GABLES:
        wall_boards(bm, wall, H, holes_of(wall))
        wall_boards(bm, wall, H + RISE, gable=True)
    return bm


def build_foundation():
    bm = bmesh.new()
    om.box(bm, (-HW - 0.03, -0.05, -HD - 0.03), (HW + 0.03, FOUND_TOP, HD + 0.03))
    # Street door step (concrete): a landing + one step
    om.box(bm, (-0.9, -0.04, HD), (0.9, FLOOR - 0.02, HD + 1.2))          # bottoms 1 cm above the band's (z-fighting)
    om.box(bm, (-0.9, -0.03, HD + 1.2), (0.9, FLOOR * 0.5, HD + 1.5))
    # Splash blocks under the downspout shoes, reaching out from the wall
    for sx, sz in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        x0, x1 = sorted((sx * (HW + 0.12), sx * (HW + 0.62)))
        z = sz * (HD - 0.15)
        om.box(bm, (x0, -0.02, z - 0.13), (x1, 0.05, z + 0.13))
    return bm


# ---------- Trim ----------

def build_trim():
    bm = bmesh.new()
    # Corner boards: an L at every corner (two boards); only the front and back boards reach round the corner (overlapping, the
    # two boards' faces z-fought)
    # On the gables the board's top is cut to the slope of the rake soffit above it, 2 mm into it (cut level at H it stood 3 cm
    # into the soffit at the corner and 7 cm short of it 14 cm in: the joint audit's find)
    reach_eave = OVH_EAVE * math.cos(SLOPE)
    t_soffit = 0.02 / math.cos(SLOPE)

    def soffit_y(a):
        return H + RISE - t_soffit - (H + RISE - EAVE_Y) * abs(a) / (HD + reach_eave) + 0.002

    for wall in (FRONT, BACK, WEST, EAST):
        reach = TRIM_OUT if wall in (FRONT, BACK) else 0.0
        for side in (-1, 1):
            a0, a1 = sorted((side * wall.half, side * (wall.half - CORNER)))
            if side > 0:
                a1 += reach
            else:
                a0 -= reach
            if wall in (FRONT, BACK):
                flat_board(bm, wall, a0, a1, FOUND_TOP - 0.02, SOFFIT_Y, 0.0, TRIM_OUT)
            else:
                v0, t0, t1 = FOUND_TOP - 0.02, soffit_y(a0), soffit_y(a1)
                slab(bm, [wall.p(a0, v0, 0.0), wall.p(a1, v0, 0.0), wall.p(a1, v0, TRIM_OUT), wall.p(a0, v0, TRIM_OUT),
                          wall.p(a0, t0, 0.0), wall.p(a1, t1, 0.0), wall.p(a1, t1, TRIM_OUT), wall.p(a0, t0, TRIM_OUT)])
    # Frieze board (under the eave, on the long walls)
    for wall in (FRONT, BACK):
        flat_board(bm, wall, -HW + CORNER, HW - CORNER, SOFFIT_Y - FRIEZE, SOFFIT_Y, 0.0, TRIM_OUT * 0.8)
    # Eave: soffit (from the wall to the fascia board) + fascia board
    reach = OVH_EAVE * math.cos(SLOPE)
    for sz in (-1, 1):
        z_wall, z_out = sz * HD, sz * (HD + reach)
        lo, hi = sorted((z_wall, z_out))
        om.box(bm, (-HW - OVH_RAKE, SOFFIT_Y, lo), (HW + OVH_RAKE, EAVE_Y, hi))
        lo, hi = sorted((z_out, z_out + sz * 0.028))
        # (its top 5 mm over the eave line, under the shingles: 2 cm over it, it showed as a white strip above the gutter)
        om.box(bm, (-HW - OVH_RAKE - 0.002, EAVE_Y - 0.2, lo), (HW + OVH_RAKE + 0.002, EAVE_Y + 0.005, hi))
    # Rake: a sloped rake board at the roof edge + a sloped soffit (from the wall to the rake board). At the eave corner (21 October
    # 2026, the joint audit's finds) the rake board runs on to 6 mm behind the fascia's face and hangs past the fascia's bottom,
    # covering its end and the eave soffit's; the sloped soffit stops at the house's corner, where the eave soffit takes over (carried
    # on to the eave line it dipped 4 mm through the eave soffit)
    drop = (H + RISE - EAVE_Y) / (HD + reach)          # the roof line's fall per metre along the gable
    t = 0.02 / math.cos(SLOPE)
    for wall in GABLES:
        for side in (-1, 1):
            # (6 mm behind the fascia's face: 2 mm back and 2 mm in, the board's and the fascia's 45 degree edge chamfers fell in
            # one plane and z-fought)
            end = HD + reach + 0.022
            ex, ey = side * end, H + RISE - drop * end
            # 23.6 cm deep (vertical): at the house's corner its bottom edge is 2 mm under the eave soffit (20.2 cm left a 5 cm sliver
            # of the soffit's end showing under it there) and over the whole fascia it is below the fascia's bottom, so it covers
            # both ends (cut to meet the fascia's bottom at its own end, a wedge of the fascia's end showed under it)
            depth = (H + RISE - drop * HD) - SOFFIT_Y + 0.002
            w0, w1 = OVH_RAKE - 0.028, OVH_RAKE + 0.004   # 4 mm proud of the roof edge (flush, they z-fought)
            slab(bm, [wall.p(0, H + RISE - depth, w0), wall.p(ex, ey - depth, w0), wall.p(ex, ey - depth, w1),
                      wall.p(0, H + RISE - depth, w1), wall.p(0, H + RISE + 0.02, w0), wall.p(ex, ey + 0.02, w0),
                      wall.p(ex, ey + 0.02, w1), wall.p(0, H + RISE + 0.02, w1)])
            hx, hy = side * HD, H + RISE - drop * HD
            slab(bm, [wall.p(0, H + RISE - t, 0.0), wall.p(hx, hy - t, 0.0), wall.p(hx, hy - t, w0),
                      wall.p(0, H + RISE - t, w0), wall.p(0, H + RISE, 0.0), wall.p(hx, hy, 0.0), wall.p(hx, hy, w0),
                      wall.p(0, H + RISE, w0)])
    # Window and door casings
    for o in OPENINGS:
        wall = o.wall
        bottom = o.v0 if o.kind == "window" else FOUND_TOP
        for side in (-1, 1):
            a0, a1 = sorted((o.c + side * o.width / 2, o.c + side * (o.width / 2 + CASING)))
            flat_board(bm, wall, a0, a1, bottom, o.v1, 0.0, TRIM_OUT)
        flat_board(bm, wall, o.a0 - CASING - 0.015, o.a1 + CASING + 0.015, o.v1, o.v1 + HEAD, 0.0, TRIM_OUT + 0.004)
        flat_board(bm, wall, o.a0 - CASING - 0.03, o.a1 + CASING + 0.03, o.v1 + HEAD, o.v1 + HEAD + 0.025, 0.0, TRIM_OUT + 0.022)
        if o.kind == "window":
            # Sill (sticking out from inside the opening) and an apron under it. Its top is 4 mm above the opening's floor: in the
            # same plane they z-fought (the flickering sill)
            flat_board(bm, wall, o.a0 - CASING - 0.04, o.a1 + CASING + 0.04, o.v0 - 0.045, o.v0 + 0.004, -0.11, TRIM_OUT + 0.04)
            flat_board(bm, wall, o.a0 - CASING + 0.02, o.a1 + CASING - 0.02, o.v0 - 0.12, o.v0 - 0.045, 0.0, TRIM_OUT)
        else:
            # Threshold: 4 mm proud of the floor and the deck (in their plane it z-fought)
            flat_board(bm, wall, o.a0 - 0.02, o.a1 + 0.02, FLOOR - 0.03, FLOOR + 0.004, -0.11, TRIM_OUT + 0.03)
        # Jamb: the inner faces of the opening (top and sides)
        flat_board(bm, wall, o.a0, o.a1, o.v1 - 0.02, o.v1, -0.12, 0.0)
        for a0, a1 in ((o.a0, o.a0 + 0.02), (o.a1 - 0.02, o.a1)):
            flat_board(bm, wall, a0, a1, o.v0 if o.kind == "window" else FLOOR, o.v1 - 0.02, -0.12, 0.0)
    return bm


# ---------- Windows ----------

def sash(bm, wall, a0, a1, v0, v1, w0, w1, bottom_rail, top_rail, glass_w):
    """Sash: stiles, top/bottom rails (TRIM), glass inside (GLASS, material 1)."""
    stile = 0.055
    flat_board(bm, wall, a0, a0 + stile, v0, v1, w0, w1)
    flat_board(bm, wall, a1 - stile, a1, v0, v1, w0, w1)
    flat_board(bm, wall, a0 + stile, a1 - stile, v1 - top_rail, v1, w0, w1)
    flat_board(bm, wall, a0 + stile, a1 - stile, v0, v0 + bottom_rail, w0, w1)
    flat_board(bm, wall, a0 + stile, a1 - stile, v0 + bottom_rail, v1 - top_rail, glass_w - 0.003, glass_w + 0.003, material=1)


def build_windows():
    bm = bmesh.new()
    for o in OPENINGS:
        if o.kind != "window":
            continue
        a0, a1 = o.a0 + 0.02, o.a1 - 0.02
        mid = (o.v0 + o.v1) * 0.5
        # The upper sash outside, the lower sash inside; overlapping meeting rails in the middle
        sash(bm, o.wall, a0, a1, mid - 0.018, o.v1 - 0.02, -0.055, -0.02, 0.035, 0.055, -0.04)
        sash(bm, o.wall, a0, a1, o.v0, mid + 0.018, -0.095, -0.06, 0.07, 0.035, -0.08)
    return bm


# ---------- Doors ----------

def panel_door(bm, wall, a0, a1, v0, v1, w0, w1, color, glass):
    """Framed door: the upper half with 2x2 glass, the lower half two raised panels."""
    stile, top, lock, bottom = 0.12, 0.12, 0.17, 0.22
    lock0 = v0 + 0.92
    flat_board(bm, wall, a0, a0 + stile, v0, v1, w0, w1, color)
    flat_board(bm, wall, a1 - stile, a1, v0, v1, w0, w1, color)
    flat_board(bm, wall, a0 + stile, a1 - stile, v1 - top, v1, w0, w1, color)
    flat_board(bm, wall, a0 + stile, a1 - stile, lock0, lock0 + lock, w0, w1, color)
    flat_board(bm, wall, a0 + stile, a1 - stile, v0, v0 + bottom, w0, w1, color)
    # Bottom: a middle stile + two raised panels (1 cm behind the frame, chamfered edges)
    mid = (a0 + a1) * 0.5
    flat_board(bm, wall, mid - 0.05, mid + 0.05, v0 + bottom, lock0, w0, w1, color)
    for p0, p1 in ((a0 + stile, mid - 0.05), (mid + 0.05, a1 - stile)):
        flat_board(bm, wall, p0, p1, v0 + bottom, lock0, w0, w1 - 0.014, color)
        flat_board(bm, wall, p0 + 0.035, p1 - 0.035, v0 + bottom + 0.035, lock0 - 0.035, w1 - 0.014, w1 - 0.006, color)
    # Top: 2x2 glass, muntins
    g0, g1 = lock0 + lock, v1 - top
    flat_board(bm, wall, a0 + stile, a1 - stile, g0, g1, (w0 + w1) * 0.5 - 0.003, (w0 + w1) * 0.5 + 0.003, glass)
    flat_board(bm, wall, mid - 0.016, mid + 0.016, g0, g1, w0 + 0.008, w1 - 0.006, color)
    gm = (g0 + g1) * 0.5
    flat_board(bm, wall, a0 + stile, a1 - stile, gm - 0.016, gm + 0.016, w0 + 0.0095, w1 - 0.0075, color)


def glass_door_leaf(bm, wall, a0, a1, v0, v1, w0, w1):
    """Glass door leaf (white): stiles, rails, a 2x5 glass grid."""
    stile, top, bottom = 0.1, 0.1, 0.2
    white, glass = 1, 2
    flat_board(bm, wall, a0, a0 + stile, v0, v1, w0, w1, white)
    flat_board(bm, wall, a1 - stile, a1, v0, v1, w0, w1, white)
    flat_board(bm, wall, a0 + stile, a1 - stile, v1 - top, v1, w0, w1, white)
    flat_board(bm, wall, a0 + stile, a1 - stile, v0, v0 + bottom, w0, w1, white)
    g0, g1, ga0, ga1 = v0 + bottom, v1 - top, a0 + stile, a1 - stile
    flat_board(bm, wall, ga0, ga1, g0, g1, (w0 + w1) * 0.5 - 0.003, (w0 + w1) * 0.5 + 0.003, glass)
    am = (ga0 + ga1) * 0.5
    flat_board(bm, wall, am - 0.014, am + 0.014, g0, g1, w0 + 0.008, w1 - 0.006, white)
    for k in range(1, 5):
        v = g0 + (g1 - g0) * k / 5
        # 1.5 mm inside the upright's faces: crossing in one plane they z-fought
        flat_board(bm, wall, ga0, ga1, v - 0.014, v + 0.014, w0 + 0.0095, w1 - 0.0075, white)


def build_doors():
    """Materials: 0 door colour, 1 white, 2 glass."""
    bm = bmesh.new()
    for o in OPENINGS:
        if o.kind == "door":
            panel_door(bm, o.wall, o.a0 + 0.02, o.a1 - 0.02, FLOOR, o.v1 - 0.02, -0.09, -0.045, 0, 2)
        elif o.kind == "glass_door":
            mid = o.c
            glass_door_leaf(bm, o.wall, o.a0 + 0.02, mid - 0.003, FLOOR, o.v1 - 0.02, -0.09, -0.045)
            glass_door_leaf(bm, o.wall, mid + 0.003, o.a1 - 0.02, FLOOR, o.v1 - 0.02, -0.095, -0.05)
    return bm


# ---------- Roof ----------

def shingle_roof(bm, top_line, x0, x1, down, normal, length, tab=0.75, exposure=0.14, course=None, over=0.012, eave_over=0.01):
    """
    A sloped roof face: a sheathing board + shingle rows (up from the eave; every row covers the upper part of the one below,
    the strips offset by half a pitch per row). top_line(x): a point on the top edge; down: down the slope; normal: outwards.
    Every strip is two exposures + 1 cm long (as a real shingle: every point of the roof is under two layers, so the slots
    between strips show the strip below, not the sheathing). The strips take the roof plane's normal and UVs measured from
    their butt (om.preset_faces): the row lines and the shadow under each butt come from the "shingle" texture, which the
    mipmaps even out at a distance (the geometric butts alone made moire arcs, 21 October 2026).
    over: how far the rows run past x0/x1 at the rakes, so they overhang the rake boards (a rake board showing above the
    shingles drew a dotted white line along the porch roof's edge from afar). eave_over: how far the first row runs past the
    eave line (along the slope), so it overhangs the fascia.
    """
    course = course or 2.0 * exposure + 0.01

    def p(x, s, h):
        return top_line(x) + down * s + normal * h

    # The sheathing runs as far as the rows (to under their overhang at the rakes: without it the overhanging rows' undersides
    # lay in one plane and z-fought, seen from below). Its edges show at the rakes and eaves: plain granules, no row line
    # Its eave end is cut plumb, 3 mm inside the eave line, like the rake boards and the fascia it meets (cut square to the
    # slope its top edge ran out past the rake boards' plumb ends at the corners: found by the joint audit, qc.joint_audit)
    sa, sb = x0 - over, x1 + over
    e0 = length - 0.003 / abs(down.z)
    e1 = e0 - normal.z * 0.02 / down.z
    sheathing = slab(bm, [p(sa, 0, 0), p(sa, e0, 0), p(sb, e0, 0), p(sb, 0, 0),
                          p(sa, 0, 0.02), p(sa, e1, 0.02), p(sb, e1, 0.02), p(sb, 0, 0.02)])
    om.preset_faces(bm, sheathing, p(x0, 0, 0), Vector((1, 0, 0)), Vector((0, 0, 0)), v_offset=0.06)
    s = length + eave_over
    row = 0
    while s > 0.05:
        # The rows that reach the top edge are cut there, each 4 mm short of the one before (cut flush, their end faces z-fought)
        s_top = s - course if s - course > 0.012 else 0.004 * (row % 3)
        # Every row offset by a third of a strip (with strips two exposures long a row overlaps the second row above it: with
        # a half offset those two rows' slots fell in one place and their side faces z-fought)
        shift = (row % 3) * tab / 3.0
        x = x0 - shift
        while x < x1 + over:
            # The rows' cut ends at the roof edges staggered row to row (in one plane they z-fight)
            inset = 0.003 + 0.0025 * (row % 3)
            xa, xb = max(x, x0 - over) + inset, min(x + tab, x1 + over) - inset
            if xb - xa > 0.03:
                t0, t1 = 0.012, 0.004
                strip = slab(bm, [p(xa, s, 0.02), p(xa, s_top, 0.02), p(xb, s_top, 0.02), p(xb, s, 0.02),
                                  p(xa, s, 0.02 + t0), p(xa, s_top, 0.02 + t1), p(xb, s_top, 0.02 + t1), p(xb, s, 0.02 + t0)])
                om.preset_faces(bm, strip, p(xa, s, 0.02), Vector((1, 0, 0)), -down, v_scale=om.SHINGLE_ROW / exposure,
                                normal=normal)
            x += tab
        s -= exposure
        row += 1


def build_roof():
    bm = om.preset_layers(bmesh.new())
    length = math.hypot(HD, RISE) + OVH_EAVE
    x0, x1 = -HW - OVH_RAKE, HW + OVH_RAKE
    for sz in (-1, 1):
        down = Vector((0, -math.sin(SLOPE), sz * math.cos(SLOPE)))
        normal = Vector((0, math.cos(SLOPE), sz * math.sin(SLOPE)))
        # (the first row overhangs the fascia, 2.8 cm out of the eave line, by 1.2 cm)
        shingle_roof(bm, lambda x: Vector((x, H + RISE, 0.0)), x0, x1, down, normal, length, eave_over=0.04 / math.cos(SLOPE))
    # Ridge caps (along X). A cap end within 2 mm of a shingle strip's end (the strips run up under the caps) is moved 3 mm:
    # in one plane the two end faces z-fought
    strip_ends = []
    for shift in (0.0, 0.25, 0.5):
        for m in range(-1, int((x1 - x0) / 0.75) + 2):
            for inset in (0.003, 0.0055, 0.008):
                strip_ends += [x0 - shift + 0.75 * m + inset, x0 - shift + 0.75 * m - inset]

    def clear(x):
        return x + 0.003 if any(abs(x - e) < 0.002 for e in strip_ends) else x

    cap = 0.3
    x = x0 - 0.012
    count = 0
    while x < x1 + 0.012 - 0.02:
        xa, xb = clear(x), min(clear(x + cap), x1 + 0.012)
        spread = 0.14 + (0.006 if count % 2 else 0.0)   # overlapping caps' side edges off each other's plane
        count += 1
        pts = []
        for sz in (-1, 1):
            down = Vector((0, -math.sin(SLOPE), sz * math.cos(SLOPE)))
            normal = Vector((0, math.cos(SLOPE), sz * math.sin(SLOPE)))
            pts.append(Vector((0, H + RISE, 0)) + down * spread + normal * 0.034)
        prof = [pts[0], Vector((0, H + RISE + 0.07, 0)), pts[1]]
        inner = [q - Vector((0, 0.012, 0)) for q in prof]
        ring = prof + list(reversed(inner))
        faces = om.loft(bm, [[V(xa, q.y, q.z) for q in ring], [V(xb, q.y + 0.006, q.z) for q in ring]], material=0)
        # Each cap's end at xb lies on top of the next cap: that end is its butt; 28 cm of it shows
        om.preset_faces(bm, faces, V(xb, 0, 0), Vector((0, 0, 1)), Vector((-1, 0, 0)), v_scale=om.SHINGLE_ROW / (cap - 0.02))
        x += cap - 0.02
    return bm


def build_porch_roof():
    """Porch roof: from the ledger on the wall to the beam in front, a gentle slope; shingle rows."""
    bm = om.preset_layers(bmesh.new())
    angle = math.atan(PORCH_K)
    down = Vector((0, -math.sin(angle), -math.cos(angle)))
    normal = Vector((0, math.cos(angle), -math.sin(angle)))
    length = (DZ1 - PORCH_EAVE_Z) / math.cos(angle)
    # (the rake boards stand 3 cm outside X0/X1: the rows run 4.7 cm past, overhanging them by 1-1.7 cm)
    shingle_roof(bm, lambda x: Vector((x, LEDGER_TOP, DZ1)), PORCH_X0, PORCH_X1, down, normal, length, over=0.047,
                 eave_over=0.04 / math.cos(angle))
    return bm


# ---------- Gutters ----------

GUTTER_PROFILE = [(0.0, 0.0), (0.0, -0.11), (0.1, -0.11), (0.125, -0.07), (0.118, -0.04), (0.135, 0.0),
                  (0.129, 0.0), (0.112, -0.04), (0.119, -0.068), (0.096, -0.104), (0.006, -0.104), (0.006, 0.0)]


def build_gutters():
    bm = bmesh.new()
    reach = OVH_EAVE * math.cos(SLOPE)
    top = EAVE_Y + 0.0
    for sz in (-1, 1):
        z_face = sz * (HD + reach + 0.028)
        rings = []
        for x in (-HW - OVH_RAKE, HW + OVH_RAKE):
            rings.append([V(x, top + v, z_face + sz * u) for u, v in GUTTER_PROFILE])
        om.loft(bm, rings, material=0)
        # Downspouts: from the end of the gutter to the gable wall with an elbow, down along the wall, an elbow onto a stone at the bottom
        for sx in (-1, 1):
            # The top end sits in the middle of the gutter's 6 mm bottom (-0.104..-0.110): at -0.105 it was 1 mm under the inner
            # face, which the z-fighting gate counts as the same plane (found once the face order became canonical, 23 October 2026)
            out = Vector((sx * (HW + 0.12), top - 0.107, z_face + sz * 0.06))
            wall_x = sx * (HW + TRIM_OUT + 0.035)   # in front of the corner board
            z_down = sz * (HD - 0.15)
            # The shoe at the bottom points out and down and ends 8 cm above the splash block (it used to end in the block)
            path = [out, out + Vector((0, -0.12, 0)),
                    Vector((wall_x, top - 0.45, z_down)), Vector((wall_x, top - 0.6, z_down)),
                    Vector((wall_x, 0.36, z_down)), Vector((sx * (HW + 0.24), 0.18, z_down))]
            # Measured at finish: from inside the gutter down the wall to the shoe, which ends free above the splash block
            model.route(f"Downspout_{'east' if sx > 0 else 'west'}_{'garden' if sz < 0 else 'street'}",
                        [path[0], path[3], path[4], path[5]], tol=0.045, part="Gutters", ends=("Gutters", None),
                        component="Downspouts",
                        free=(3,), unity=True)
            path = om.fillet(path, 0.06, 4)
            om.sweep(bm, path, 1.0, shape=om.rounded_profile(0.03, 0.04, 0.012, 2), up=(1, 0, 0) if sx > 0 else (-1, 0, 0))
    return bm


# ---------- Deck ----------

def build_deck():
    """
    The deck as it is built (21 October 2026: the boards used to stop 1 cm short of the rim joists with nothing under them, so
    you saw through the gap): joists every 40 cm between the rim joists and a ledger on the wall carry the boards; the boards
    rest on them and on the rim joists and overhang the rim joists by 2 cm.
    """
    bm = bmesh.new()
    top = FLOOR
    over = 0.02
    x0, x1 = DX0 - 0.045 - over, DX1 + 0.045 + over
    # Decking boards (along X, 14 cm, 8 mm gap)
    z = DZ0 - 0.045 - over
    while z < DZ1 - 0.05:
        z1 = min(z + 0.14, DZ1 - 0.005)
        om.box(bm, (x0, top - 0.028, z), (x1, top, z1))
        z += 0.148
    # Rim joists (in front and on the sides, under the decking)
    om.box(bm, (DX0, top - 0.24, DZ0 - 0.045), (DX1, top - 0.028, DZ0))
    for x in (DX0, DX1):
        lo, hi = sorted((x, x + (0.045 if x == DX1 else -0.045)))
        om.box(bm, (lo, top - 0.24, DZ0 - 0.045), (hi, top - 0.028, DZ1))
    # Ledger on the wall and joists every 40 cm (along Z), under the boards
    om.box(bm, (DX0, top - 0.24, DZ1 - 0.045), (DX1, top - 0.028, DZ1))
    x = DX0 + 0.4
    while x < DX1 - 0.2:
        om.box(bm, (x - 0.0225, top - 0.235, DZ0), (x + 0.0225, top - 0.028, DZ1 - 0.045))
        x += 0.4
    # Steps: two steps, each two boards; three stringers under them (cut at a slant). The back board of each tread runs 5 mm into
    # the riser (or the rim joist) behind it and every riser reaches 1 cm below the tread in front of it: there used to be a 5-6 mm
    # slot at both (a light line across the step in the game, 21 October 2026)
    riser = top / 3
    for i in (1, 2):
        step_top = top - riser * i
        z_hi = DZ0 - 0.045 - 0.29 * (i - 1)
        for k in range(2):
            za, zb = z_hi - 0.145 * (k + 1), z_hi - 0.145 * k - 0.006 + (0.011 if k == 0 else 0.0)
            # (the treads overhang the risers by 12 mm at the ends; flush, their end faces z-fought where they meet)
            om.box(bm, (STEP0 - 0.012, step_top - 0.03, za), (STEP1 + 0.012, step_top, zb))
        # Front face (riser): under the front edge of the step, down past the tread below (the bottom one stops 5 mm above the ground)
        bottom = 0.005 if i == 2 else step_top - riser - 0.04
        om.box(bm, (STEP0, bottom, z_hi - 0.29), (STEP1, step_top - 0.03, z_hi - 0.27))
    # Stringers: notched in steps, the treads rest on the notches and the risers stand in front of them (21 October 2026: they were
    # cut as one straight slope, so they stuck up through both treads like a ramp: diagonal boards at the ends, a strip in the middle)
    under2, under1 = top - 2 * riser - 0.03, top - riser - 0.03       # the treads' undersides
    back2, back1 = DZ0 - 0.045 - 0.29 - 0.27, DZ0 - 0.045 - 0.27      # behind each riser
    profile = [(back2, 0.0), (back2, under2), (back1, under2), (back1, under1), (DZ0 - 0.045, under1), (DZ0 - 0.045, 0.18)]
    for x in (STEP0 + 0.04, (STEP0 + STEP1) * 0.5, STEP1 - 0.04):
        om.loft(bm, [[V(x + side * 0.022, y, z) for z, y in profile] for side in (-1, 1)], material=0)
    return bm


def lattice(bm, wall, a0, a1, v0, v1, w, spacing=0.13, width=0.034, thick=0.007):
    """Diagonal lattice: two layers of 45° slats, clipped to the rectangle (the slat edges clipped one by one)."""
    def clip(p, d):
        t0, t1 = -1e9, 1e9
        for pc, dc, lo, hi in ((p[0], d[0], a0, a1), (p[1], d[1], v0, v1)):
            if abs(dc) < 1e-9:
                if pc < lo or pc > hi:
                    return None
                continue
            ta, tb = (lo - pc) / dc, (hi - pc) / dc
            t0, t1 = max(t0, min(ta, tb)), min(t1, max(ta, tb))
        return (t0, t1) if t1 - t0 > 0.02 else None

    for layer, sign in enumerate((1, -1)):
        d = (1 / math.sqrt(2), sign / math.sqrt(2))
        perp = (-d[1], d[0])
        c = -(v1 - v0) - (a1 - a0)
        while c < (a1 - a0) + (v1 - v0):
            base = (a0 + c, v0) if sign > 0 else (a0 + c, v1)
            edges = []
            for off in (-width / 2, width / 2):
                p = (base[0] + perp[0] * off, base[1] + perp[1] * off)
                r = clip(p, d)
                if r is None:
                    break
                edges.append(((p[0] + d[0] * r[0], p[1] + d[1] * r[0]), (p[0] + d[0] * r[1], p[1] + d[1] * r[1])))
            if len(edges) == 2:
                (s0, e0), (s1, e1) = edges
                wa, wb = w + layer * thick, w + (layer + 1) * thick
                slab(bm, [wall.p(s0[0], s0[1], wa), wall.p(e0[0], e0[1], wa), wall.p(e1[0], e1[1], wa), wall.p(s1[0], s1[1], wa),
                          wall.p(s0[0], s0[1], wb), wall.p(e0[0], e0[1], wb), wall.p(e1[0], e1[1], wb), wall.p(s1[0], s1[1], wb)])
            c += spacing


DECK_FRONT = Wall((0, 0, DZ0 - 0.045), (1, 0, 0), (0, 0, -1), 0)
DECK_WEST = Wall((DX0 - 0.045, 0, 0), (0, 0, 1), (-1, 0, 0), 0)
DECK_EAST = Wall((DX1 + 0.045, 0, 0), (0, 0, -1), (1, 0, 0), 0)


def rail_section(bm, a_wall, a0, a1, base):
    """Railing section (between two posts): bottom rail, top rail + handrail, square balusters (11 cm apart)."""
    bottom0, bottom1 = base + 0.07, base + 0.12
    top0, top1 = base + 0.83, base + 0.92
    flat_board(bm, a_wall, a0, a1, bottom0, bottom1, -0.03, 0.03)
    flat_board(bm, a_wall, a0, a1, top0, top1, -0.022, 0.022)
    # The handrail ends 6 mm short of the posts, under their caps: wider than the posts, two handrails met at a corner and z-fought
    flat_board(bm, a_wall, a0 + 0.006, a1 - 0.006, top1, top1 + 0.035, -0.05, 0.05)
    n = max(1, round((a1 - a0) / 0.11))
    step = (a1 - a0) / n
    for k in range(n):
        a = a0 + step * (k + 0.5)
        flat_board(bm, a_wall, a - 0.017, a + 0.017, bottom1, top0, -0.017, 0.017)


def post(bm, x, z, top, size=0.09, cap=True):
    h = size / 2
    # The post stands 2 mm above the handrail and the cap sits on it: with the cap's underside at the handrail's underside
    # they z-fought where the handrail runs into the post
    top += 0.002 if cap else 0.0
    # Railing posts (with a cap) are bolted inside the rim joist and start at its bottom; porch posts stand on the decking
    bottom = FLOOR - 0.24 if cap else FLOOR + 0.02   # inside its base trim, which sits on the boards
    om.box(bm, (x - h, bottom, z - h), (x + h, top, z + h))
    if cap:
        om.box(bm, (x - h - 0.02, top, z - h - 0.02), (x + h + 0.02, top + 0.03, z + h + 0.02))
        om.box(bm, (x - h + 0.01, top + 0.03, z - h + 0.01), (x + h - 0.01, top + 0.06, z + h - 0.01))


def build_railing():
    """White: railing posts and sections, lattice skirt, porch posts, beams, ceiling, rake boards."""
    bm = bmesh.new()
    rail_top = FLOOR + 0.92
    # Railing line (through the post centres): front and both sides; the step gap stays open
    rz = DZ0 + 0.045
    rail_front = Wall((0, 0, rz), (1, 0, 0), (0, 0, -1), 0)
    front_posts = [DX0 + 0.045, (DX0 + STEP0) * 0.5, STEP0 - 0.045]
    for x in front_posts:
        post(bm, x, rz, rail_top)
    for a, b in zip(front_posts, front_posts[1:]):
        rail_section(bm, rail_front, a + 0.045, b - 0.045, FLOOR)
    # Right of the step gap: between the porch posts
    porch = list(PORCH_POSTS)
    for a, b in zip(porch, porch[1:]):
        rail_section(bm, rail_front, a + 0.065, b - 0.065, FLOOR)
    # Sides
    west = Wall((DX0 + 0.045, 0, 0), (0, 0, 1), (-1, 0, 0), 0)
    east = Wall((DX1 - 0.08, 0, 0), (0, 0, -1), (1, 0, 0), 0)
    side_z = [rz, (rz + DZ1) * 0.5, DZ1 - 0.092]   # the last post in front of the wall's siding, clear of the ledger
    for z in side_z[1:]:
        post(bm, DX0 + 0.045, z, rail_top)
        post(bm, DX1 - 0.08, z, rail_top)
    for z0, z1 in zip(side_z, side_z[1:]):
        rail_section(bm, west, z0 + 0.045, z1 - 0.045, FLOOR)
        rail_section(bm, east, -z1 + 0.045, -z0 - (0.065 if z0 == rz else 0.045), FLOOR)
    # Skirting under the rim joists, as it is built: a 9 cm corner post at each front corner and a bottom rail at the ground
    # (both flush with the rim joist's face), the lattice panels set 3 cm behind them, their cut slat ends tucked behind the
    # posts, the rail and the rim joist (21 October 2026: the panels used to run past each other at the corners, unframed)
    rim_bottom = FLOOR - 0.24
    post_w = 0.09
    for x in (DX0 - 0.045, DX1 + 0.045 - post_w):
        om.box(bm, (x, 0.0, DZ0 - 0.045), (x + post_w, rim_bottom, DZ0 - 0.045 + post_w))
    rail = 0.09
    om.box(bm, (DX0 - 0.045 + post_w, 0.0, DZ0 - 0.045), (DX1 + 0.045 - post_w, rail, DZ0 - 0.02))
    for x0, x1 in ((DX0 - 0.045, DX0 - 0.02), (DX1 + 0.02, DX1 + 0.045)):
        om.box(bm, (x0, 0.0, DZ0 - 0.045 + post_w), (x1, rail, DZ1))
    # Panels: behind the frame (w -0.040..-0.026 from the rim joist face: clear of the rail's back and the rim joist's inner face),
    # from behind the rail to behind the rim joist
    lattice(bm, DECK_FRONT, DX0 - 0.045 + post_w - 0.03, DX1 + 0.045 - post_w + 0.03, rail - 0.04, rim_bottom + 0.03, -0.040)
    lattice(bm, DECK_WEST, DZ0 - 0.045 + post_w - 0.03, DZ1 - 0.002, rail - 0.04, rim_bottom + 0.03, -0.040)
    lattice(bm, DECK_EAST, -DZ1 + 0.002, -(DZ0 - 0.045 + post_w - 0.03), rail - 0.04, rim_bottom + 0.03, -0.040)
    # Porch posts (with base and cap trim), beam, the ledger on the wall
    for x in PORCH_POSTS:
        post(bm, x, POST_Z, BEAM_TOP - 0.28, size=0.13, cap=False)
        om.box(bm, (x - 0.09, FLOOR, POST_Z - 0.09), (x + 0.09, FLOOR + 0.16, POST_Z + 0.09))
        om.box(bm, (x - 0.085, BEAM_TOP - 0.36, POST_Z - 0.085), (x + 0.085, BEAM_TOP - 0.28, POST_Z + 0.085))
    om.box(bm, (PORCH_X0 + 0.12, BEAM_TOP - 0.28, POST_Z - 0.08), (PORCH_X1 - 0.3, BEAM_TOP, POST_Z + 0.08))
    om.box(bm, (PORCH_X0, LEDGER_TOP - 0.2, DZ1 - 0.06), (HW, LEDGER_TOP, DZ1 - 0.02))
    # Ceiling: a white board just under the porch sheathing
    angle = math.atan(PORCH_K)
    down = Vector((0, -math.sin(angle), -math.cos(angle)))
    normal = Vector((0, math.cos(angle), -math.sin(angle)))
    length = (DZ1 - PORCH_EAVE_Z) / math.cos(angle)

    def pr(x, s, h):
        return Vector((x, LEDGER_TOP, DZ1)) + down * s + normal * h

    slab(bm, [pr(PORCH_X0, 0, -0.012), pr(PORCH_X0, length, -0.012), pr(PORCH_X1, length, -0.012), pr(PORCH_X1, 0, -0.012),
              pr(PORCH_X0, 0, 0), pr(PORCH_X0, length, 0), pr(PORCH_X1, length, 0), pr(PORCH_X1, 0, 0)])
    # Porch fascia board (in front) and a sloped rake board on both sides
    eave = pr(0, length, 0)
    # The fascia's ends 2 mm inside the rake boards' outer faces (flush, they z-fought). Both stay under the shingles (their
    # tops 3.5 cm over the roof plane stood above the shingles and drew a dotted white line along the edge from afar)
    om.box(bm, (PORCH_X0 - 0.028, eave.y - 0.17, eave.z - 0.028), (PORCH_X1 + 0.028, eave.y + 0.012, eave.z))
    # Both ends cut to what they meet (om.board): at the wall in the facade's plane, in front 2 mm behind the fascia's face (cut
    # square to the 15 degree slope the front end stood 4 cm out of the fascia at the bottom and the top end hung tilted at the
    # wall: the user's find)
    wall_plane = (Vector((0, 0, DZ1)), Vector((0, 0, 1)))
    front_plane = (Vector((0, 0, eave.z - 0.026)), Vector((0, 0, -1)))
    for x0 in (PORCH_X0 - 0.03, PORCH_X1):
        om.board(bm, pr(x0, 0, -0.17), down, Vector((1, 0, 0)), normal, 0.03, 0.188, wall_plane, front_plane)
    return bm


# ---------- Hardware ----------

def build_hardware():
    """Door handles (a round knob + rosette), the lamp's wall plate and arm (its shade and bulb are separate parts)."""
    bm = bmesh.new()
    for o in OPENINGS:
        if o.kind != "door":
            continue
        a = o.a1 - 0.02 - 0.07
        center = o.wall.p(a, FLOOR + 0.95, -0.045)
        # Profiles (a along the axis, radius r): rosette, then neck and knob
        om.revolve_at(bm, [(0.0, 0.0), (0.0, 0.03), (0.01, 0.028), (0.012, 0.0)], 14, center, o.wall.n)
        om.revolve_at(bm, [(0.0, 0.0), (0.0, 0.008), (0.035, 0.008), (0.04, 0.022), (0.055, 0.028), (0.07, 0.022),
                           (0.077, 0.0)], 14, center, o.wall.n)
    # Lamp: a gooseneck barn light right of the glass door (as at 0:57 in the video): a round wall plate on the siding, an arm
    # out from the wall bending down, a grey enamelled dish shade over a frosted bulb (21 October 2026: the old box lantern
    # "does not look like a lamp")
    plate = FRONT.p(LAMP_A, LAMP_V, OUT_BOTTOM)
    om.revolve_at(bm, [(0.0, 0.0), (0.0, 0.065), (0.006, 0.062), (0.016, 0.05), (0.018, 0.0)], 24, plate, FRONT.n)
    arm = om.spline([FRONT.p(LAMP_A, LAMP_V, OUT_BOTTOM + 0.01), FRONT.p(LAMP_A, LAMP_V, 0.17),
                     FRONT.p(LAMP_A, LAMP_V - 0.02, 0.25), FRONT.p(LAMP_A, LAMP_V - 0.075, LAMP_W)], 8)
    om.sweep(bm, arm, 0.011, 12)
    return bm


LAMP_A, LAMP_V, LAMP_W = 7.2, FLOOR + 1.95, 0.29     # on the garden facade: right of the glass door, under the porch roof


def build_lamp_shade():
    """The lamp's dish shade (grey outside, white inside) hanging from the arm's end, its axis vertical."""
    bm = bmesh.new()
    top = FRONT.p(LAMP_A, LAMP_V - 0.07, LAMP_W)
    # Profile (a along the vertical axis, down is negative; r): the outer face from the hub to the rolled rim, then the inner face back
    outer = [(0.0, 0.0), (0.0, 0.022), (-0.012, 0.03), (-0.035, 0.07), (-0.06, 0.115), (-0.072, 0.14), (-0.076, 0.142)]
    # The inner face 4-8 mm under the outer one everywhere (an earlier profile crossed it: a self-intersecting shell)
    inner = [(-0.078, 0.136), (-0.065, 0.113), (-0.04, 0.068), (-0.017, 0.028), (-0.008, 0.0)]
    rows = om.revolve_at(bm, outer + inner, 40, top, Vector((0, 1, 0)), material=0)
    # The inside faces white (the profile edges from the rim back to the hub)
    for k, row in enumerate(rows):
        if k >= len(outer) - 1:
            for f in row:
                if f is not None:
                    f.material_index = 1
    # Triangulated here: the thin shell's quads are not flat, and the FBX importer split them the other way (an 11 % volume change)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    return bm


def build_lamp_glass():
    """Frosted bulb under the shade."""
    bm = bmesh.new()
    center = FRONT.p(LAMP_A, LAMP_V - 0.07, LAMP_W)
    om.revolve_at(bm, [(-0.006, 0.0), (-0.006, 0.012), (-0.02, 0.016), (-0.04, 0.03), (-0.06, 0.03), (-0.075, 0.02),
                       (-0.082, 0.0)], 20, center, Vector((0, 1, 0)))
    return bm


def build_vent():
    """Vent pipe on the roof."""
    bm = bmesh.new()
    # Vent pipe: on the garden-side slope, vertical, a rubber collar at its base
    s = 2.4
    down = Vector((0, -math.sin(SLOPE), -math.cos(SLOPE)))
    normal = Vector((0, math.cos(SLOPE), -math.sin(SLOPE)))
    base = Vector((-4.5, H + RISE, 0)) + down * s + normal * 0.03
    om.revolve_at(bm, [(-0.2, 0.0), (-0.2, 0.045), (0.62, 0.045), (0.62, 0.0)], 14, base, Vector((0, 1, 0)), material=1)
    om.revolve_at(bm, [(-0.06, 0.0), (-0.06, 0.13), (0.1, 0.06), (0.1, 0.0)], 14, base, Vector((0, 1, 0)), material=1)
    return bm


# ---------- Parts ----------

model.part("Body", build_body(), [SIDING], unity=True, tone_jitter=0.04, ao_grid=(0.8, None, 0.8))
model.part("Foundation", build_foundation(), [FOUND], unity=True, ao_grid=(0.8, None, 0.8))
model.part("Trim", build_trim(), [TRIM], unity=True, bevel={"width": 0.004, "segments": 1, "angle": 35.0},
           ao_grid=(0.8, 0.8, 0.8))
model.part("Windows", build_windows(), [TRIM, GLASS], unity=True)
model.part("Doors", build_doors(), [DOOR, TRIM, GLASS], unity=True, bevel={"width": 0.002, "segments": 1, "angle": 35.0})
model.part("Roof", build_roof(), [ROOF], unity=True, tone_jitter=0.06)
model.part("Gutters", build_gutters(), [GUTTER], unity=True)
model.part("Deck", build_deck(), [DECK], unity=True, bevel={"width": 0.003, "segments": 1, "angle": 35.0},
           tone_jitter=0.06, ao_grid=(0.8, None, 0.8))
model.part("Railing", build_railing(), [TRIM], unity=True, ao_grid=(0.8, None, 0.8))
model.part("Porch", build_porch_roof(), [ROOF], unity=True, tone_jitter=0.06)
hardware = build_hardware()
om.merge(hardware, build_vent())
model.part("Hardware", hardware, [IRON, PIPE], unity=True)
model.part("LampShade", build_lamp_shade(), [SHADE, SHADE_IN], unity=True)
model.part("Lamp", build_lamp_glass(), [LAMP], unity=True)


def unity_dir(x, y, z):
    return (-x, -z, y)


everything = ["House"]
model.finish(
    budget=160000,
    join="House",
    tiled=True,
    ground=0.0,
    ao_distance=0.4,
    views=[
        {"file": "garden_left", "label": "From the garden, from the left (the angle in the video)", "objects": everything,
         "direction": unity_dir(-0.45, 0.12, -1.0), "ground": 0.0},
        {"file": "garden", "label": "Garden facade", "objects": everything, "direction": unity_dir(0.0, 0.1, -1.0), "ground": 0.0},
        {"file": "side", "label": "West gable", "objects": everything, "direction": unity_dir(-1.0, 0.2, -0.35), "ground": 0.0},
        {"file": "street", "label": "Street facade", "objects": everything, "direction": unity_dir(0.6, 0.3, 1.0), "ground": 0.0},
        {"file": "deck", "label": "Deck: railing, lattice, step", "objects": everything,
         "direction": unity_dir(-0.5, 0.25, -1.0), "target": unity_dir(0.5, 0.7, -7.6), "radius": 2.2, "ground": 0.0},
        # The two critical features no other view shows (23 October 2026: the review left them unverified)
        {"file": "steps_side", "label": "Section through the middle stringer: notched under the treads, from the ground to the rim joist",
         "objects": everything, "direction": unity_dir(-1.0, 0.04, 0.0), "target": unity_dir((STEP0 + STEP1) * 0.5, 0.25, DZ0 - 0.3),
         "radius": 0.55, "ground": 0.0, "clip_through": unity_dir((STEP0 + STEP1) * 0.5 - 0.03, 0.25, DZ0 - 0.3)},
        # A section through the front rim joist (the lattice and the rim's front cut away): what carries the deck's outer
        # edge along its whole length (a camera inside the skirt only saw the nearest joist; one from below read as noise)
        {"file": "deck_under", "label": "Section just inside the front rim joist, west half: what carries the deck's outer edge",
         "objects": everything, "direction": unity_dir(0.0, 0.12, -1.0), "target": unity_dir(-2.0, 0.22, DZ0 + 0.6),
         "radius": 2.3, "lens": 35, "ground": 0.0, "clip_through": unity_dir(-2.0, 0.22, DZ0 + 0.01)},
        {"file": "door", "label": "Doors and porch", "objects": everything, "direction": unity_dir(-0.2, 0.15, -1.0),
         "target": unity_dir(4.6, 1.8, -5.2), "radius": 2.3, "ground": 0.0},
        {"file": "window", "label": "Upper floor window", "objects": everything, "direction": unity_dir(-0.3, 0.05, -1.0),
         "target": unity_dir(-3.1, 4.8, -5.0), "radius": 1.1, "ground": 0.0},
        {"file": "sill", "label": "Ground floor window sill (no z-fighting)", "objects": everything,
         "direction": unity_dir(-0.4, 0.5, -1.0), "target": unity_dir(-3.1, 1.35, -5.05), "radius": 0.55, "ground": 0.0},
        {"file": "lamp", "label": "Lamp right of the glass door: plate, gooseneck arm, dish shade, bulb", "objects": everything,
         "direction": unity_dir(-0.6, 0.1, -1.0), "target": unity_dir(LAMP_A, LAMP_V - 0.05, -HD - 0.2), "radius": 0.4,
         "ground": 0.0},
        {"file": "eave", "label": "Eave corner: gutter, downspout", "objects": everything,
         "direction": unity_dir(-0.8, 0.1, -0.7), "target": unity_dir(-HW, 5.6, -HD), "radius": 1.1, "ground": 0.0},
    ],
    references=[
        {"label": "Reference: garden facade, video 0:57", "path": "docs/reference/29_house_garden_facade.png", "crop": [360, 0, 488, 250]},
        {"label": "Reference: deck, video 0:41.6", "path": "docs/reference/30_house_deck.png", "crop": [150, 0, 560, 160]},
        {"label": "Reference: from the side, video 0:53.5", "path": "docs/reference/31_house_side.png", "crop": [200, 0, 420, 260]},
        {"label": "Reference: the lamp beside the glass door, video 0:57", "path": "docs/reference/29_house_garden_facade.png",
         "crop": [660, 110, 140, 100]},
    ],
)
