# Opus Model Pipeline

3D models for a Unity game, written as code in Blender's Python API (`bpy`). No modelling is done by hand: each model is a script. Running the script again gives the same mesh, textures and report.

A build only passes when **measured quality gates** come back clean: no z-fighting, no holes, no badly cut joints, no faces too thin for their texture. Each model ships with a **spec file** that a Unity test compares against the imported model.

This is the model pipeline of *Copycat Opus*, a Unity 6 (URP) yard-care game. It was taken out of that project so it can be developed on its own. The game project itself is not part of this repository.

```
component plan (model.plan) ── purpose, sources, every component's job, what holds it, how it moves
   │                            checked at once: a load path from every component to a support
generator (models/<name>.py)
   │  builds parts with the Model API (opus_model.py): revolve, loft, sweep, board, carve, settle ...
   ├─ complex models: preview (Models.ps1 -Preview, seconds) → independent review (Review.py pack/record)
   ▼
validation ── open edges, inside-out shells, zero-area faces, material names, triangle budgets
   ▼
quality gates (qc.py) ── z-fighting 0, construction (nothing held by nothing, routes reach), holes 0,
   ▼                     joints 0, texels ≥ 1.5 px, (rope audit)
   ▼                     any failure stops the build; numbers → Builds/QC/<name>.json
texturing ── atlas pipeline (small models: baked colour/normal/ORM)
          └─ tiled pipeline (buildings: UVs in metres + shared tiling textures)
   ▼
outputs ── Assets/Opus/Resources/Models/<name>.fbx
           Assets/Opus/ModelSpecs/<name>.json   (sizes, pivot, tris, volume, materials, plan, fingerprints)
           Assets/Opus/Prefabs/Models/<name>.prefab  (in the Unity project: the FBX with the game's materials)
           Builds/Models/<name>_contact.png     (labelled renders + material card)
   ▼
Unity (unity/) ── ModelImport fixes import settings, ModelImportTests compares the FBX with its spec,
                  ModelLibrary/SurfaceLibrary turn material names into game materials
```

## What is where

| Path | What it is for |
| --- | --- |
| `tools/blender/opus_model.py` | **The Model API.** It holds the conventions: units, axes and material names. It has the geometry helpers, the material registry, both texture pipelines and the AO bake, plus the FBX, spec and render output. Every generator imports it as `om`. |
| `tools/blender/qc.py` | **Quality gates**: the hole audit, texel audit, joint audit, atlas fill and QC report. |
| `tools/blender/models/*.py` | **Generators**, one model each. They range from the calibration cube to the two-storey house. They double as worked examples. |
| `tools/blender/checks/*.py` | **Pipeline checks**: small scenes that prove a gate or helper still works. For example, `joints.py` checks that a square-cut board is caught and a plumb-cut one is not. |
| `tools/blender/external/` | **Outside assets** (CC0, from ambientCG and Poly Haven) with their licence records (`assets.json`, `CREDITS.md`). |
| `tools/blender/source_textures/` | **CC0 texture sources** used by the generators (`LICENSES.md`). `generated/` is written by the builds. |
| `tools/Models.ps1` | **Runs Blender in the background**. Use it for one model (`-Only house`), every model, or the checks (`-Checks`). It also draws the contact sheets. |
| `tools/Verify.ps1` | **The one command to verify everything.** It rebuilds only models whose inputs changed, runs up to 3 builds in parallel, and prints one line per model and per step. |
| `tools/Board.py` | **Puts many screenshots or crops on one labelled image**, so they can be reviewed in one look. |
| `tools/Review.py` | **The independent plausibility review and the approval state.** `pack` writes one image, a brief and a manifest (pack id, hashes); `record` accepts only findings that name this pack and only if its files did not change; `carry` moves a preview review to the final build only when its structure demonstrably did not change; `approve` and `state` keep the user's approval apart from reviews. |
| `tools/Compare.py`, `tools/blender/compare_render.py`, `tools/blender/references/` | **Measured comparison with a reference frame.** It solves the frame's camera from landmarks picked by hand and reports the alignment, each landmark's leave-one-out error and each segment's length ratio. It renders an overlay. Advisory unless aligned. |
| `tools/Prefabs.ps1`, `unity/Editor/ModelPrefabs.cs` | **One prefab per model** inside the Unity project: `Assets/Opus/Prefabs/Models/<model>.prefab` (a Prefab Variant of the FBX with the game's materials), its materials saved in `Prefabs/Models/Materials/<model>/`. In the game project, every build and `Verify.ps1` run it, and `ModelImportTests.EveryModelHasAPrefab` checks it. |
| `.claude/skills/model-plausibility/research/` | **What was learned about each kind of object before modelling it**: sources, the tricks adopted and rejected (skill step 2b). Read before searching again. |
| `tools/tests/` | **Tests of the review, approval, comparison and art-style logic**, plain Python, no Blender: `py -3 -m unittest discover -s tools/tests`. |
| `.claude/skills/model-plausibility/` | **How to plan and review a model** (a Claude Code skill; readable by anyone): principles, a guidance file per category (`machines`, `suspended`, `buildings`, `organic`), `lessons.md` (past mistakes as general rules) and `review.md` (the reviewer's instructions and output format). |
| `tools/blender/reviews/`, `tools/blender/approvals.json` | **Decision records:** what a reviewer found, and which geometry the user approved. Keyed by the model's geometry hash. |
| `tools/Assets.ps1` | **Searches and fetches licence-checked free assets** through the separate `free-assets` tool. Optional. |
| `tools/Style.py`, `tools/blender/style/style.json`, `tools/LookDev.ps1`, `tools/blender/lookdev.py`, `.claude/skills/art-style/` | **The art style (work in progress: read `docs/art-style-handoff.md` first).** Rules with checks, model gates (colours per hue, finish by kind, triangle budgets, chamfers) in `Verify.ps1`, a deterministic look-dev scene, a one-page brief per asset and a generated art bible. The image measurements do not yet drive the gates; the handoff lists what is wrong and what is left. |
| `docs/art-style-handoff.md`, `reports/`, `research_notes/` | **The art-style handoff and its research**: the research report on defining and enforcing a game art style (Turkish), its notes (English), and an honest account of the current state. |
| `tools/_common.ps1` | **Shared PowerShell helpers**: the project root, the log folder, Unity and Blender paths. |
| `unity/` | **The Unity side**, kept for reference (it compiles only inside the game project). `ModelImport.cs` holds the import settings, `ModelLibrary.cs` and `SurfaceLibrary.cs` build the game materials, and `ModelImportTests.cs` checks each model against its spec. |

## Requirements

- Windows with PowerShell 5.1. The scripts are `.ps1`; the Blender side is plain Python.
- **Blender 5.x.** `Models.ps1` looks for it here, in order:
  - the `-BlenderPath` argument;
  - the `BLENDER` environment variable;
  - Steam installs;
  - `C:\Program Files\Blender Foundation\`.
- **Python 3 with Pillow**, only for `tools/Board.py`.
- **Unity 6000.3** for the `unity/` files, used inside a Unity project.

## Quick start

Build one model:

```bash
powershell -ExecutionPolicy Bypass -File tools/Models.ps1 -Only wheel
```

Preview a model's structure in seconds: no baking, no export; it writes `Builds/Models/<name>_preview.png` with the plan card:

```bash
powershell -ExecutionPolicy Bypass -File tools/Models.ps1 -Only mower -Preview
```

Run the pipeline checks:

```bash
powershell -ExecutionPolicy Bypass -File tools/Models.ps1 -Checks
```

Build whatever changed and print a short report:

```bash
powershell -ExecutionPolicy Bypass -File tools/Verify.ps1
```

Rebuild every model:

```bash
powershell -ExecutionPolicy Bypass -File tools/Verify.ps1 -AllModels
```

This is the real `Verify.ps1 -AllModels` output on this repository, on a fresh clone (`zf` = z-fighting pairs, `thin` = faces under the texel limit):

```
Models: 9 to build (calibration, hose_nozzle, house, mower, shed, tire_swing, tree, trimmer, wheel)
  calibration  ok    zf 0, holes 0, joints 0  26 s
  hose_nozzle  ok    zf 0, holes 0, joints 0, thin 0  140 s
  house        ok    zf 0, holes 0, joints 0  178 s
  tire_swing   ok    zf 0, holes 0, joints 0, thin 0  183 s
  shed         ok    zf 0, holes 0, joints 0  62 s
  tree         ok    zf 0, holes 0, joints 0, thin 0  114 s
  wheel        ok    zf 0, holes 0, joints 0, thin 0  91 s
  trimmer      ok    zf 0, holes 0, joints 0, thin 0  133 s
  mower        ok    zf 0, holes 0, joints 0  14 s
Checks: 3/3
Unity: no Unity project here (tests, build and scenarios run in the game project)
All passed
```

A failing gate looks like this. The example is a sloped board cut square into a fascia:

```
  qc_probe     FAIL  RuntimeError: qc_probe: QC joints: 1 ends cut at the wrong angle for what they meet (part, Unity xyz,
                     angle, mm in front, mm behind): [('Rake', [0.015, 2.409, -1.912], 15.0, 44.0, 4.7)]
FAILED: model qc_probe
```

Every run leaves these behind:
- full logs in `Logs/`;
- gate numbers in `Builds/QC/<model>.json`;
- the contact sheet in `Builds/Models/<model>_contact.png`.

`wheel` must be built before `mower`, because the mower imports `wheel.fbx`. `house` must be built before `shed`, because both write `Tiling/tiling.json`. Both scripts handle this order themselves.

## Writing a generator

A minimal generator. The real ones live in `tools/blender/models/`, and `calibration.py` is the smallest:

```python
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import bmesh
import opus_model as om

model = om.Model("crate", __file__)
model.plan("a wooden crate that holds apples", [("text", "the user's description")],
           [("Box", "functional", "holds the apples", ["ground"], "fixed", "guess")], tier="simple")
wood = model.surface("Planks", "#8A6A48", "matte", "rough pine boards (why this finish: what it really is)")

bm = bmesh.new()
om.box(bm, (-0.3, -0.2, 0.0), (0.3, 0.2, 0.35))
model.part("Crate", bm, [wood], bevel={"width": 0.004, "segments": 1, "angle": 30.0})

model.finish(views=[{"file": "three_quarter", "label": "3/4", "objects": ["Crate"], "direction": (-0.85, -1.0, 0.75)}])
```

**Conventions.** The build fails or the Unity test catches it when one is broken.

- **Units and axes:**
  - 1 Blender unit = 1 m, and models are built at real size.
  - The model's front is Blender −Y, its top +Z and its right −X. In Unity these become +Z, +Y and +X, so `U = (−x, z, −y)`. `part(unity=True)` takes points in Unity axes.
  - Parts carry position only: no rotation, no scale. Rotated parts are built by rotating their vertices.
- **Material names** are `<Kind>_<RRGGBB>_<finish>`.
  - The kind is one of `SURFACE_KINDS`, the same names as the game's `SurfaceKind`.
  - The finish is glossy, satin, matte or metallic. Pick it from the part's real material, not from the kind.
  - `surface(...)` asks for a reason (`note`). It is printed on the contact sheet's material card.
- **Closed shells:** every shell of a closed part is watertight, with normals facing out.
- **One mesh per model**, apart from parts that move.
- **No stacked primitives.** A wheel is one revolved profile with its lugs pushed out of the same surface, not boxes glued onto a cylinder.

**Main helpers.** Each is documented in its docstring.

| Helper | What it does |
| --- | --- |
| `revolve`, `revolve_at` | Profile around an axis: wheels, nozzles, pots |
| `loft` | Ring-by-ring shells: housings, handles |
| `fillet`, `spline`, `sweep` | Bent pipes, cables and rope strands |
| `board` | A member whose ends are cut by the planes of the faces they meet: rake boards, stringers, rafters |
| `box`, `extrude_outward`, `carve`, `merge` | Blocks, lugs and pockets pushed out of a surface, boolean carving of one shell |
| `part(..., bevel=, ao_grid=, foliage=, tone_jitter=)` | Edge chamfer + weighted normals; AO vertices along long faces; double-sided leaves; a tone per shell |
| `settle(bodies, colliders)` | Places things by Bullet physics instead of by hand: apples in a crate, stones. Same input, same result. |
| `external("polyhaven:<id>", ...)` | Imports a licence-checked outside asset as one part (glTF, FBX or OBJ; never `.blend`) |
| `anchor(name, unity_point)` | A connection point the Unity test compares with its in-game counterpart |

## The two texture pipelines

**Atlas pipeline (small models)**

```python
model.finish_textured(size=2048, moving=[...])
```

- Source materials come from `textured_surface`, `moulded_surface`, `painted_wood_surface` or `asphalt_surface`. These use CC0 photos or Blender nodes, through a source UV that the generator lays out.
- The build joins the static parts and unwraps one atlas UV, sizing the islands by their 3D area.
- Cycles bakes colour, a tangent-space normal (OpenGL +Y), and ORM (AO, roughness, metallic) into `Textures/<model>/`.
- Pixels that no face uses are filled from their neighbours, so mipmaps never pull in black.
- Options:
  - `ground=0.0` keeps the gate cameras above the ground;
  - `untextured=("Leaves",)` keeps foliage out of the atlas;
  - `ao_together=False` bakes AO per part, for parts that move apart in game.

**Tiled pipeline (buildings)**

```python
model.finish(join="House", tiled=True)
```

A 4096 atlas over a whole house gave only 76 px/m: sub-pixel faces and black lines. Buildings use this pipeline instead.

- UVs are in metres along each board's grain (`tile_uv`).
- AO and a per-board tone go into the vertex colour.
- The textures are seamless 1024 tiling sets that `write_tile_sets` writes, along with `Tiling/tiling.json`.
- Shingle rows get their UVs and roof-plane normals from the generator (`preset_layers`, `preset_faces`). The row lines are then in a mipmapped texture rather than sub-pixel geometry, which had caused moiré from 8 m away.

**Material registry (`MATERIALS` in `opus_model.py`).** Every tiled surface names a material, and three rules hold:

1. The material is registered for that surface's kind.
2. No two materials look alike. Each has another texture set, or differs by at least 0.1 tone strength, 0.15 bump or ×1.3 repeat.
3. A material with an owner belongs only to that model.

The house's factory-painted siding and the shed's rough boards are both "painted wood siding", but they are different materials. A different paint colour alone is not a different material.

These rules are checked on import, in `Model.surface`, in `finish(tiled=True)` and in a Unity test.

## Quality gates

Every gate is a hard failure that prints numbers. Every defect that someone spotted by eye was turned into a gate, a check or a construction rule, so it cannot come back.

| Gate | Where | Fails on |
| --- | --- | --- |
| Validation | `Model.validate` | Open edges, inside-out shells, zero-area faces, loose vertices, wrong material names, over the triangle budget |
| Z-fighting | `om.coplanar_overlaps` | Overlapping faces in one plane facing the same way. The model must have 0. |
| Holes | `qc.audit_holes` | A back face seen first from outside, as Unity draws it (back faces culled). Hundreds of close cameras (0.25–1.6 m) cast rays. A camera counts only where it can see the sky. An edge graze is confirmed with rays shifted 0.1 mm. The model must have 0. |
| Construction | `qc.connectivity`, `qc.check_links` | A piece not joined (intersecting or within 3 mm) to an assembly held by the ground or by a declared `support` (hands, a branch, the wheels). A whole object floating above the ground fails. A plan support never located. Leaves and `part(free=True)` are exempt. A declared `route` whose piece (of `part`) does not reach every point or whose ends do not touch the named parts. A declared `attach` point where the two named parts do not meet. |
| Joints | `qc.joint_audit` | A member's end that crosses the face it meets at 3–60°, poking through or leaving a wedge. Lapped parallel boards and chamfers are not counted. |
| Texels | `qc.texel_audit` | Atlas models only: a face over 1 cm² that gets less than 1.5 atlas px across its narrow side. Faces below the ground are ignored. |
| Rope audit | `models/tire_swing.py` | Rope-to-rope distance under 1.9 R, a bend under 0.75 D, the loop not touching the tyre |
| Spec test | `unity/Tests/EditMode/ModelImportTests.cs` | The imported FBX against its spec: ±1 mm bounds, pivot, no rotation or scale, triangles, volume, normal/winding agreement, materials, the tiling material rules |

The gates have blind spots: a thin slot that looks through onto front faces, and joints at grazing angles. Close-up screenshots in the built game (`u16_showroom` in the game project) are part of the check.

## Verify.ps1 and Board.py

These two scripts keep the edit, build and check loop cheap in time and in output to read:

- `Verify.ps1` hashes the content of each model's inputs: its generator, `opus_model.py`, `qc.py`, the outside assets, the source textures, and the model it depends on. Only changed models are rebuilt; touching a file without changing it rebuilds nothing.
  - Use `-Models a,b` or `-AllModels` to force builds.
  - `-Accept` records the current state as built.
  - A failure prints the gate's own message and exits with code 1.
  - Every model line ends with its approval state. **A passing build is not an approval**: `approved` means the user approved exactly this geometry (`-Approve a,b`). A complex model shows `needs review` until a review of its current geometry exists, then `reviewed` or `review: N open`.
  - `-Stats` prints builds, failures and review findings per model; every build is appended to `Builds/QC/history.jsonl`.
- Inside a Unity project, `Verify.ps1` also runs the EditMode tests, the build and the screenshot scenarios: all of them after a code change, only the model scenarios after a model change. With no Unity project (as in this repository), it says so and stops after the checks.
- `py -3 tools/Board.py out.png shot.png@x0,y0,x1,y1=label ...` puts many shots or crops on one sheet.

## Planning and reviewing a model (functional plausibility)

A model can pass every gate and still make no sense: a rope tied wrong, a cable that pulls nothing, a detail that suggests a function the object cannot have. Three things cover this, and they are kept apart:

| | What | Who decides |
|---|---|---|
| **Measured** | Plan check (every component attached to something, a load path to a support), construction gate, supports, routes and attachments, rope audit, measured critical features, the reference comparison (advisory unless aligned) | The build: pass or fail |
| **Judged** | The independent review of complex models: findings with severity, confidence, evidence and a fix, and a verdict (pass, fail, unverified) on every critical and important feature | Recorded against the reviewed structure; confident findings are fixed, doubtful ones are put to the user |
| **Approved** | The user's approval of the asset (geometry, UVs, plan, surfaces, textures within bake noise) | The user (`Verify.ps1 -Approve`). An approved model with an open serious finding or a critical feature unverified or failing is shown but not counted as clean |

The workflow depends on the tier.
- A **simple** model (few parts, nothing moving or hanging) gets a short plan, the gates and one look at the sheet.
- A **complex** model (a mechanism, a cable or rope, anything suspended, a building, a hand-held tool) goes through these steps:
  1. plan;
  2. preview (`Models.ps1 -Only <m> -Preview`, seconds);
  3. review (`Review.py pack`, then a separate reviewer with fresh context, then `Review.py record`);
  4. detail;
  5. full build;
  6. Unity checks;
  7. the user's approval.

The review never runs inside a build. Any vision-capable model can be the reviewer: the pack is one image plus `brief.md`, and the output format is in `.claude/skills/model-plausibility/review.md`. Measured on the mower: 65k tokens, 5 tool calls and 60 s per review with the bounded prompt; the first, unbounded trial cost 91k, 20 and 225 s.

**Critical features** (`model.features`) name the few relationships that make an object what it is, such as the mower's control chain or the swing's branch hitch. A convincing whole does not count as acceptance: an unobserved critical feature is unverified, not passed.

The modelling rules that came out of this work live in that skill, so they exist in one place:
- the general principles in `SKILL.md`;
- the rules per kind of object in `categories/*.md`;
- every past mistake with the principle it broke and what catches it now in `lessons.md`.

Sources can be a video, an image, a 3D model, a text description or web research. The plan names which, and the skill says how each is read.

**Research first.** Before the first model of a new kind of object, look up how others model it for games and how it is really built: breakdowns, tutorials, construction guides. Keep it to a small budget of at most 3 searches and 4 pages. The tricks adopted and rejected are kept in `research/<kind>.md`, so the next model of that kind reads them instead of searching again.

**Reproducible builds.** The same generator gives the same mesh, UVs, atlas and FBX mesh at every build. Some bmesh operators (`extrude_face_region`, `inset_region`) and the bevel modifier order their output by memory address, so `om.canonical_order` and `om.canonical_mesh` reorder every part by its geometry, keeping its custom normals. `checks/determinism.py` fails without that.

## Not in this repository

- **Reference frames** (`docs/reference/*.png`): these are crops of a copyrighted game trailer. The generators still name them, and the contact sheet shows an empty tile where a reference crop would go.
- **The Unity game project:** scenes, shaders, game scripts, the scenario screenshots, and `Test.ps1`, `Build.ps1` and `Shots.ps1`.
- **Build outputs:** `Assets/`, `Builds/` and `Logs/` are created by the first build.
- **The art bible and the style board** (`Builds/Style/art_bible.html`, `style_board.png`): they embed the reference frames. `Style.py bible` and `Style.py extract` write them again from your own images.

## Assets and licences

The code is under the [MIT licence](LICENSE). The textures and outside assets keep their own licence (CC0, below).

Every texture and outside asset in `tools/blender/external/` and `tools/blender/source_textures/` is **CC0** (public domain), from [ambientCG](https://ambientcg.com) and [Poly Haven](https://polyhaven.com). They are listed in `external/CREDITS.md` and `source_textures/LICENSES.md`.

New outside assets go through `tools/Assets.ps1`. It refuses any licence outside `CC0`, `CC-BY`, `OGA-BY` and `BlenderKit-RF`, and records the source and authors. API keys for sources that need them are set by each user in their own terminal (`free-assets key set <source>`). Keys are never stored in the repository.
