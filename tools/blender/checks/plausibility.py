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

if failures:
    raise AssertionError("; ".join(failures))
om.log("Plausibility check passed: floating pieces, short cables, open hinges and broken plans are found; correct ones are not")
