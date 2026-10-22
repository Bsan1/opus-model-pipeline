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
  - `model.route(name, centreline points, tol, free=...)`: a cable, rope or pipe reaches what it joins.
  - `model.attach(name, point)`: two pieces meet at a hinge, clip or bracket.
  - `part(..., free=True)`: only for something meant to stand apart, with a comment.
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

**Review.** Follow these steps in order:
1. `py -3 tools/Review.py pack <m> --stage preview` (or `final`) writes `Builds/Review/<m>/sheet.png` and `brief.md`.
2. Start an independent reviewer with fresh context: the Agent tool, model `sonnet` unless the model is hard to read. Prompt: *"Read exactly three files and nothing else: .claude/skills/model-plausibility/review.md, Builds/Review/<m>/brief.md, Builds/Review/<m>/sheet.png. Write Builds/Review/<m>/findings.json in the format review.md gives. Reply with one line."* Any other vision model can take the same pack, because the interface is the image, the brief and the JSON format.
   - Cost: the first trial (mower, 22 October 2026) used 91k tokens and 20 tool calls because the reviewer explored the repository; the pack alone is one image plus about 6 KB of text.
3. Record the findings: `py -3 tools/Review.py record <m> Builds/Review/<m>/findings.json --reviewer <model id> --stage ...`.
4. **Act without asking:**
   - fix high-confidence findings of high or medium severity, rebuild, and mark them `fixed`;
   - mark findings that are wrong `dismissed --by auto` and write the reason in the lessons only if it teaches something.
5. **Tell the user in one or two lines:** what was found and fixed, and only the low-confidence items for them to accept or reject. The user does not read findings files.
6. After a preview review, if the final build only added detail: `py -3 tools/Review.py carry <m>`. Review again only when a fix or a later change altered the structure.

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
