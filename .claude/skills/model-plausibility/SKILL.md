---
name: model-plausibility
description: Plan, check and review procedural Blender models (tools/blender/models/*.py) for believable function and construction - every part has a job and a real attachment, mechanisms are complete, loads have a path. Use when starting a new model, changing a model's structure, or reviewing one; loads only the category guidance that applies.
---

# Model plausibility

The numeric gates (`qc.py`) prove a model is technically sound: no z-fighting, no holes, joints cut to fit, nothing floating, declared links reaching. They cannot tell whether the object makes sense. A rope can pass every gate and still be tied wrong; a cable can reach both ends and still pull nothing. This skill covers that judgement: a plan before the geometry, then for complex models an independent review. **Keep objective checks, AI judgements and the user's decisions apart:**
- gates fail builds;
- reviews produce findings;
- only the user approves (`tools/Verify.ps1 -Approve`).

## 1. Choose the tier (cost follows complexity)

| Tier | When | Steps |
|---|---|---|
| simple | Few parts, no mechanism, nothing hanging or carrying a load beyond resting on the ground (a wheel, a pot, a stone) | Short plan → build (gates) → one look at the contact sheet |
| complex | A mechanism, a cable, rope or hinge, anything suspended, a building, a tool held in the hands | Plan → **preview** → **review** → detail → build (gates) → Unity checks → the user approves |

## 2. Read the source by its kind

The plan's `sources` names the kind.
- **video:** measure sizes against known sizes in the frame, and sample colours in clean frames. A part the video never shows is a guess in its design language.
- **image:** one view. The hidden sides are guesses; ask when the object's use is unclear.
- **model** (a 3D file the user gives): a shape and measurement reference. Rebuild it as a generator in our style. Import its mesh only if the user owns it or its licence allows (`tools/Assets.ps1`, `om.external`).
- **text:** write the plan first and show it to the user as one short table before any geometry.
- **real:** for how things are really built or rigged, look up real references (guides, photos) before modelling (rope, knots, framing).

## 3. Write the plan first

At the top of the generator, right after `om.Model(...)`:

```python
model.plan(purpose, sources=[("video", "0:46")], components=[
    # name, role, job, attached to, moves, seen/guess/real
    ("ControlBar", "functional", "held against the grip to run the engine", ["UpperTube", "hands"], "hinge", "guess"),
    ...], supports=("ground", "hands"), tier="complex", category="machines")
```

- **What the plan lists:** only components with a job or a joint. A whole board family counts as one entry ("Siding"), not one entry per board.
- **Build-time checks:** the words, every component attached to something, and a **load path** from every component to a support.
- **Where it shows:** the plan goes into the spec and onto the contact sheet (plan card).
- **Measured links:** declare the links that can be measured.
  - `model.route(name, centreline points, tol, free=..., part=..., ends=(a, b))`: a cable, rope or pipe reaches what it joins. With `part` and `ends`, it must be that piece reaching those parts, not any piece that happens to pass there.
  - `model.attach(name, point, parts=(a, b))`: those two parts meet at a hinge, clip or bracket.
  - `model.support(name, points)`: where each plan support other than the ground holds the model (the hands on the grips, the branch under the round turn, the wheels on the axle pins). The gate then demands one assembly held by its supports. A whole object floating above the ground fails; the old rule just took the biggest piece.
  - `part(..., free=True)`: only for something meant to stand apart, with a comment.
- **Critical features** (complex models): `model.features([(id, tier, components, expected, measure, view)])` lists the few relationships that make the object what it is. Examples: the mower's control chain, the swing's branch hitch, the stairs carried to the deck. Each gets a tier: critical, important or optional.
  - The build measures what it can (`route:`, `attach:`, `support:`).
  - The reviewer must give every critical and important feature a verdict: pass, fail or unverified.
  - A critical feature that is unverified or failing keeps the model from being clean, even when approved. Absence of a finding is not a pass.
- `spec.located` lists the plan components tied to geometry; the review brief names the others, which can only be judged by eye.
- The generator docstring keeps the source notes: what is visible, measurements, decisions. "Mechanical logic" prose lives in the plan, not in the docstring.

## 4. Principles (all models)

1. **Every part has a job.** It is functional or structural; or it is decorative and does not pretend a function it lacks. A button, cable, latch or vent implies a use, so it needs it.
2. **Load path.** Every piece is held by something that is itself held, down to a support. Nothing floats or ends in mid-air; free ends hang under gravity.
3. **Joints are real.** Joined things meet: a bolt, hinge, clip, knot, lap or notch. Member ends are cut to the face they meet.
4. **Mechanisms are complete.** A control reaches what it controls (lever → cable → tab). A moving part has a pivot and room to move. A flow (water, air, fuel) has a path in and out.
5. **Built as it is really built.** Real construction order and joinery; real rigging; one shell per real piece.
6. **Made for a body.** What a hand holds is where a hand reaches and sized for it. What the player sees matches how it is used.
7. **The source decides.** Proportions are measured. Details the source contradicts go (the trimmer's invented button squares). Guesses are marked `guess` and stay simple.
8. **Physics reads right.** Loaded ropes run straight. Parts interpenetrate only where they are joined. Grime and wear go only where they really occur.

## 5. Category guidance

Load only the files the plan's `category` names, from `categories/`:
- `machines.md`: machines and tools held in the hand;
- `suspended.md`: rope, swings, anything hanging;
- `buildings.md`: buildings and built structures;
- `organic.md`: plants, trees, natural arrangements.

A new kind of object gets a new file only when its first model teaches something general. Add it to `PLAN_CATEGORIES` too.

## 6. Preview, then review (complex tier)

**Preview.** `tools/Models.ps1 -Only <m> -Preview` takes seconds. It runs validation, the plan and the construction gate, then writes labelled renders and the plan card to `Builds/Models/<m>_preview.png`, with no baking, no other gates and no export. Use it once the main bodies and joints exist, before detailing.

**Reference comparison** (when a frame exists; before packing): `py -3 tools/Compare.py <m>`.
- It reads landmarks from `tools/blender/references/<m>.json`: points picked on the frame, each with its model point; `vfov_deg` fixes a known game camera.
- It solves the camera and reports the alignment: aligned ≤ 1.5 % of the object's height, rough ≤ 4 %, otherwise poor.
- It gives each landmark's leave-one-out error and each segment's length ratio, plus an overlay.
- Rough results are advisory; poor gives no numbers at all, only the overlay.
- There is no silhouette IoU on perspective frames.
- Measured on 22 October 2026:
  - the shed is rough (3 %). The fitted focal length matched the game's 60° camera within 2°, and the model's window came out 80 % of the frame's width;
  - the mower is poor: its 7 landmarks, mostly tyre silhouettes, cannot fix a camera.

**Review.** Follow these steps in order:
1. `py -3 tools/Review.py pack <m> --stage preview` (or `final`) writes `Builds/Review/<m>/sheet.png`, `brief.md`, any comparison overlays and `manifest.json` (pack id and hashes). The findings must name the pack id, and `record` refuses a pack whose files changed after it was made. Decided findings are listed so they are not reported again.
2. Start an independent reviewer with fresh context: the Agent tool, model `sonnet` unless the model is hard to read. Prompt: *"Read exactly three files and nothing else: .claude/skills/model-plausibility/review.md, Builds/Review/<m>/brief.md, Builds/Review/<m>/sheet.png. Write Builds/Review/<m>/findings.json in the format review.md gives. Reply with one line."* Any other vision model can take the same pack, because the interface is the image, the brief and the JSON format.
   - Cost, measured on the mower (22 October 2026). The first trial used 91k tokens, 20 tool calls and 225 s, because the reviewer explored the repository. With this prompt it used 65k tokens, 5 calls and 60 s; most of the rest is the agent's own fixed context, and the pack is one image plus about 7 KB. The second trial repeated none of the decided findings and found one plan gap (the rear flap's hinge pin).
3. Record the findings: `py -3 tools/Review.py record <m> Builds/Review/<m>/findings.json --reviewer <model id> --stage ...`.
4. **Act without asking:**
   - fix high-confidence findings of high or medium severity, rebuild, and mark them `fixed`;
   - mark findings that are wrong `dismissed --by auto` and write the reason in the lessons only if it teaches something.
5. **Tell the user in one or two lines:** what was found and fixed, and only the low-confidence items for them to accept or reject. The user does not read findings files.
6. After a preview review: `py -3 tools/Review.py carry <m>`. It carries the review only if the plan, links and features are the same, the bounds are within 2 cm and the piece count within 5 %; otherwise review the final build.

**State and approval** (`Review.py state`, shown on every `Verify.ps1` model line):
- reviews are tied to the model's *structure* (geometry, plan, links, features);
- the user's approval (`Verify.ps1 -Approve <m>`) is tied to the *asset* (structure, UVs, surfaces, plus the textures within bake noise);
- an approved model with an open high or medium finding, or a critical feature unverified or failing, is shown but not counted as clean.

**Cost rules:**
- one review per stage;
- none for colour, texture or material-only changes;
- never inside a build;
- the pack is one image plus a short brief.

## 7. Lessons

`lessons.md` holds past mistakes as general principles with their detection. When a defect is found by eye (by the user or by me):
1. Add a lesson, merged with an existing lesson if it shares the principle.
2. If the defect is measurable, also add a gate or a probe in `tools/blender/checks/` that catches it.
3. Keep the file small: examples go in the lessons, rules go here or in the category files, and nothing says the same thing in two places.
