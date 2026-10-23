"""
Pipeline check: the construction gate and the plan check (22 October 2026) catch the classes of mistake they are for, and
leave correct construction alone.

Caught:
- a piece held by nothing (a block 5 cm above another: "nothing floats or ends in mid-air");
- a cable that stops 2 cm short of the tab it should enter (the mower's control cable must reach the engine's brake tab);
- a hinge whose two halves do not meet;
- a plan with a component attached to nothing, one with no load path to a support, an unknown role.
Not caught:
- a block standing on another; two blocks standing apart on the ground (the downspout's splash block);
- a cable that reaches both tabs; a hinge whose halves meet.
Nothing is exported. Run: powershell -ExecutionPolicy Bypass -File tools/Models.ps1 -Checks
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import bmesh  # noqa: E402

import opus_model as om  # noqa: E402


def box(lo, hi):
    bm = bmesh.new()
    om.box(bm, lo, hi)
    return bm


def construction(name, boxes, ground=None, routes=(), attachments=()):
    model = om.Model(name, __file__)
    paint = model.surface("Paint", "#FFFFFF", "matte", "check part")
    for index, (lo, hi) in enumerate(boxes):
        model.part(f"P{index}", box(lo, hi), [paint], smooth=False)
    for route_name, points, tol in routes:
        model.route(route_name, points, tol=tol)
    for attach_name, point in attachments:
        model.attach(attach_name, point)
    result = model._gate_construction(ground, raise_errors=False)
    om.log(f"{name}: {len(result['stray'])} held by nothing, problems {result['problems']}")
    return len(result["stray"]), result["problems"]


failures = []

# Pieces held by nothing
floating, _ = construction("floating", [((0, 0, 0), (1, 1, 0.1)), ((0, 0, 0.15), (1, 1, 0.25))])
stacked, _ = construction("stacked", [((0, 0, 0), (1, 1, 0.1)), ((0.2, 0.2, 0.1), (0.8, 0.8, 0.3))], ground=0.0)
apart, _ = construction("apart_on_ground", [((0, 0, 0), (1, 1, 0.1)), ((2, 0, 0), (2.3, 0.4, 0.05))], ground=0.0)
if floating != 1:
    failures.append(f"a block 5 cm above another: {floating} held by nothing, expected 1")
if stacked or apart:
    failures.append(f"correct stacking flagged: stacked {stacked}, apart on the ground {apart}")

# A cable (2 cm square rod, centreline at z = 0.11) from a tab on one block to a tab on another
tabs = [((0, 0, 0), (0.1, 0.1, 0.2)), ((1.0, 0, 0), (1.1, 0.1, 0.2))]
cable_points = [(0.1, 0.05, 0.11), (1.0, 0.05, 0.11)]
reaching = tabs + [((0.095, 0.04, 0.1), (1.005, 0.06, 0.12))]
short = tabs + [((0.095, 0.04, 0.1), (0.98, 0.06, 0.12)), ((0.4, 0.06, 0.1), (0.5, 0.1, 0.12))]   # + a clip, so it is held
ok_floating, ok_problems = construction("cable_reaches", reaching, routes=[("cable", cable_points, 0.012)])
_, short_problems = construction("cable_short", short, routes=[("cable", cable_points, 0.012)])
if ok_problems or ok_floating:
    failures.append(f"a cable reaching into both tabs flagged: {ok_floating} held by nothing, {ok_problems}")
if not short_problems:
    failures.append("a cable ending 2 cm short of its tab was not caught")

# A hinge: two leaves meeting at the pin, then 1 cm apart
meeting = [((0, 0, 0), (0.1, 0.01, 0.1)), ((0.1, 0, 0), (0.2, 0.01, 0.1))]
gap = [((0, 0, 0), (0.1, 0.01, 0.1)), ((0.11, 0, 0), (0.21, 0.01, 0.1))]
_, hinge_ok = construction("hinge_meets", meeting, ground=0.0, attachments=[("hinge", (0.1, 0.005, 0.05))])
_, hinge_gap = construction("hinge_gap", gap, ground=0.0, attachments=[("hinge", (0.1, 0.005, 0.05))])
if hinge_ok:
    failures.append(f"a hinge whose leaves meet flagged: {hinge_ok}")
if not hinge_gap:
    failures.append("a hinge whose leaves are 1 cm apart was not caught")

# The plan
good = [("Deck", "structural", "carries the engine", ["Wheels"], "fixed", "seen"),
        ("Wheels", "functional", "roll on the ground", ["ground"], "spin", "seen"),
        ("Badge", "decorative", "the maker's badge on the deck", ["Deck"], "fixed", "guess")]
bad_plans = {
    "attached to nothing": good + [("Knob", "functional", "sets the height", [], "spin", "guess")],
    "no load path": good + [("Cable", "functional", "brakes the blade", ["Lever"], "flex", "guess"),
                            ("Lever", "functional", "pulled by the hand", ["Cable"], "hinge", "guess")],
    "unknown role": good + [("Grille", "pretty", "air in", ["Deck"], "fixed", "seen")],
}
om.Model("plan_good", __file__).plan("a check", [("text", "this check")], good)
for label, components in bad_plans.items():
    try:
        om.Model("plan_bad", __file__).plan("a check", [("text", "this check")], components)
        failures.append(f"a plan with a component {label} was accepted")
    except ValueError as error:
        om.log(f"plan ({label}) refused: {error}")

# ---- Held and identified (22 October 2026: the second review found these passing) -----------------------------------

def assembly(name, parts, ground=None, plan_supports=None, supports=(), routes=(), attachments=()):
    """Named box parts; returns (pieces held by nothing, problems)."""
    model = om.Model(name, __file__)
    paint = model.surface("Paint", "#FFFFFF", "matte", "check part")
    if plan_supports is not None:
        model.plan("a check", [("text", "this check")],
                   [(p, "structural", "check part", [plan_supports[0]], "fixed", "guess") for p in parts],
                   supports=plan_supports)
    for part_name, (lo, hi) in parts.items():
        model.part(part_name, box(lo, hi), [paint], smooth=False)
    for support_name, points in supports:
        model.support(support_name, points, tol=0.01)
    for route_name, points, kwargs in routes:
        model.route(route_name, points, **kwargs)
    for attach_name, point, kwargs in attachments:
        model.attach(attach_name, point, **kwargs)
    result = model._gate_construction(ground, raise_errors=False)
    om.log(f"{name}: {len(result['stray'])} held by nothing, problems {result['problems']}")
    return len(result["stray"]), result["problems"]


def expect(label, outcome, caught):
    stray, problems = outcome
    if caught and not (stray or problems):
        failures.append(f"{label}: not caught")
    if not caught and (stray or problems):
        failures.append(f"{label}: flagged although correct ({stray} held by nothing, {problems})")


# 1-2. A whole object, internally connected, floating 0.5 m above the ground; the same standing on it
table = {"Top": ((0, 0, 0.7), (1, 1, 0.75)), "Leg": ((0.45, 0.45, 0.5), (0.55, 0.55, 0.7))}
expect("a whole object floating above the ground", assembly("floating_whole", table, ground=0.0), caught=True)
standing = {"Top": ((0, 0, 0.7), (1, 1, 0.75)), "Leg": ((0.45, 0.45, 0.0), (0.55, 0.55, 0.7))}
expect("an object standing on the ground", assembly("standing", standing, ground=0.0), caught=False)
# 3. A hanging object held at a declared support point; the same with the support point 3 cm off the model
hanging = {"Hook": ((0, 0, 1.9), (0.02, 0.02, 2.0)), "Seat": ((-0.2, -0.2, 1.5), (0.22, 0.22, 1.9))}
expect("a hanging object held by its support",
       assembly("hanging", hanging, ground=0.0, plan_supports=("branch",), supports=[("branch", [(0.01, 0.01, 2.0)])]),
       caught=False)
expect("a support point that touches nothing",
       assembly("support_off", hanging, ground=0.0, plan_supports=("branch",), supports=[("branch", [(0.01, 0.01, 2.04)])]),
       caught=True)
# 4. A plan support never located in the geometry
expect("a plan support not located", assembly("support_missing", hanging, ground=0.0, plan_supports=("branch",)),
       caught=True)
# 5. An attachment met by the wrong two parts: Lever meets Frame at the point, the Pin is 2 cm away
hinge = {"Frame": ((0, 0, 0), (0.1, 0.1, 0.1)), "Lever": ((0.1, 0.04, 0.04), (0.3, 0.06, 0.06)),
         "Pin": ((0.12, 0.04, 0.0), (0.14, 0.06, 0.03))}
expect("an attachment met by the wrong parts",
       assembly("attach_wrong", hinge, ground=0.0, attachments=[("pivot", (0.1, 0.05, 0.05), {"parts": ("Lever", "Pin")})]),
       caught=True)
expect("an attachment met by the right parts",
       assembly("attach_right", hinge, ground=0.0, attachments=[("pivot", (0.1, 0.05, 0.05), {"parts": ("Lever", "Frame")})]),
       caught=False)
# 6. A route satisfied by the wrong piece: the Frame rail passes every point, the Cable stops 2 cm short of the Tab
rail = {"Lever": ((0, 0, 0), (0.1, 0.1, 0.2)), "Tab": ((1.0, 0, 0), (1.1, 0.1, 0.2)),
        "Rail": ((0.05, 0.04, 0.1), (1.05, 0.06, 0.102)), "Cable": ((0.095, 0.04, 0.104), (0.98, 0.06, 0.124))}
points = [(0.1, 0.05, 0.11), (1.0, 0.05, 0.11)]
expect("a route checked without naming its part (the rail stands in for the cable)",
       assembly("route_anyone", rail, ground=0.0, routes=[("cable", points, {"tol": 0.012})]), caught=False)
expect("a route whose named part stops short",
       assembly("route_part", rail, ground=0.0, routes=[("cable", points, {"tol": 0.012, "part": "Cable"})]), caught=True)
# 7. A route whose end touches the wrong part: the Cable reaches the Tab's place, but the Tab is not there (a Plate is)
ends = {"Lever": ((0, 0, 0), (0.1, 0.1, 0.2)), "Plate": ((1.0, 0, 0), (1.1, 0.1, 0.2)),
        "Cable": ((0.095, 0.04, 0.1), (1.005, 0.06, 0.12))}
expect("a route ending on the wrong part",
       assembly("route_ends", ends, ground=0.0,
                routes=[("cable", points, {"tol": 0.012, "part": "Cable", "ends": ("Lever", "Tab")})]), caught=True)
expect("a route ending on the right parts",
       assembly("route_ends_ok", ends, ground=0.0,
                routes=[("cable", points, {"tol": 0.012, "part": "Cable", "ends": ("Lever", "Plate")})]), caught=False)

# 8. Features: a critical feature measured by a route that fails is "fail"; a measure naming nothing is a problem
model = om.Model("features", __file__)
model.plan("a check", [("text", "this check")],
           [("Lever", "functional", "pulled", ["ground"], "hinge", "guess"),
            ("Cable", "functional", "pulls the tab", ["Lever", "Tab"], "flex", "guess"),
            ("Tab", "functional", "is pulled", ["ground"], "hinge", "guess")])
model.features([("chain", "critical", ["Lever", "Cable", "Tab"], "the cable joins lever and tab", "route:cable", None),
                ("ghost", "important", ["Tab"], "measured by nothing that exists", "attach:nowhere", None)])
paint = model.surface("Paint", "#FFFFFF", "matte", "check part")
for part_name, (lo, hi) in rail.items():
    model.part(part_name, box(lo, hi), [paint], smooth=False)
model.route("cable", points, tol=0.012, part="Cable", component="Cable")
result = model._gate_construction(0.0, raise_errors=False)
measured = {f["id"]: f["measured"] for f in model.feature_data}
om.log(f"features: measured {measured}, problems {result['problems']}")
if measured.get("chain") != "fail":
    failures.append(f"a critical feature whose route fails was measured {measured.get('chain')}, not fail")
if not any("nowhere" in p for p in result["problems"]):
    failures.append("a feature measured by an undeclared attachment was not reported")
try:
    om.Model("features_bad", __file__).features([("x", "critical", ["Nothing"], "no plan", None, None)])
    failures.append("features without a plan were accepted")
except ValueError:
    pass

if failures:
    raise AssertionError("; ".join(failures))
om.log("Plausibility check passed: floating pieces, short cables, open hinges and broken plans are found; correct ones are not")
