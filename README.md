# Opus Model Pipeline

3D models for a Unity game, written as code in Blender's Python API (`bpy`). No modelling is done by hand: each model is a script. Running the script again gives the same mesh, textures and report.

A build only passes when **measured quality gates** come back clean: no z-fighting, no holes, no badly cut joints, no faces too thin for their texture. Each model ships with a **spec file** that a Unity test compares against the imported model.

This is the model pipeline of *Copycat Opus*, a Unity 6 (URP) yard-care game. It was taken out of that project so it can be developed on its own. The game project itself is not part of this repository.

```
generator (models/<name>.py)
   │  builds parts with the Model API (opus_model.py): revolve, loft, sweep, board, carve, settle ...
   ▼
validation ── open edges, inside-out shells, zero-area faces, material names, triangle budget
   ▼
quality gates (qc.py) ── z-fighting 0, holes 0, joints 0, texels ≥ 1.5 px, (rope audit)
   ▼                     any failure stops the build; numbers → Builds/QC/<name>.json
texturing ── atlas pipeline (small models: baked colour/normal/ORM)
          └─ tiled pipeline (buildings: UVs in metres + shared tiling textures)
   ▼
outputs ── Assets/Opus/Resources/Models/<name>.fbx
           Assets/Opus/ModelSpecs/<name>.json   (sizes, pivot, tris, volume, materials in Unity axes)
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
| `tools/Assets.ps1` | **Searches and fetches licence-checked free assets** through the separate `free-assets` tool. Optional. |
| `tools/_common.ps1` | **Shared PowerShell helpers**: the project root, the log folder and Unity paths. |
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
| Joints | `qc.joint_audit` | A member's end that crosses the face it meets at 3–60°, poking through or leaving a wedge. Lapped parallel boards and chamfers are not counted. |
| Texels | `qc.texel_audit` | Atlas models only: a face over 1 cm² that gets less than 1.5 atlas px across its narrow side. Faces below the ground are ignored. |
| Rope audit | `models/tire_swing.py` | Rope-to-rope distance under 1.9 R, a bend under 0.75 D, the loop not touching the tyre |
| Spec test | `unity/Tests/EditMode/ModelImportTests.cs` | The imported FBX against its spec: ±1 mm bounds, pivot, no rotation or scale, triangles, volume, normal/winding agreement, materials, the tiling material rules |

The gates have blind spots: a thin slot that looks through onto front faces, and joints at grazing angles. Close-up screenshots in the built game (`u16_showroom` in the game project) are part of the check.

## Verify.ps1 and Board.py

These two scripts keep the edit, build and check loop cheap in time and in output to read:

- `Verify.ps1` hashes each model's inputs: its generator, `opus_model.py`, `qc.py`, the outside assets, the source textures, and the model it depends on. Only changed models are rebuilt.
  - Use `-Models a,b` or `-AllModels` to force builds.
  - `-Accept` records the current state as built.
  - A failure prints the gate's own message and exits with code 1.
- Inside a Unity project, `Verify.ps1` also runs the EditMode tests, the build and the screenshot scenarios: all of them after a code change, only the model scenarios after a model change. With no Unity project (as in this repository), it says so and stops after the checks.
- `py -3 tools/Board.py out.png shot.png@x0,y0,x1,y1=label ...` puts many shots or crops on one sheet.

## Modelling rules that came out of this work

These are the rules that grew out of reviewing every model up close against the reference video.

- **The reference video is the only design source.**
  - Measure sizes against something of known size in the frame.
  - Sample colours from the same region in the video and in the game, choosing frames without coloured light.
  - Parts the video never shows continue its design language and are marked as guesses in the generator's docstring.
- **Mechanical logic:** every part has a job and a real attachment. Nothing floats or ends in mid-air: cables run in clips to the engine, and the starter rope runs to its guide.
- **Real textures, not plastic.** Simple shapes still need painted texture: board lines, grain, grime where it belongs (only on concrete, brick and stone). Don't bake lighting into textures; dark patches in the video are often leaf shadows.
- **Buildings: build them the way they are really built.**
  - Deck boards rest on joists.
  - Stair stringers are notched, and risers reach under the tread.
  - Corner board tops follow the soffit slope, and the rake board covers the fascia's end.
  - Shingle strips are two exposures long, with rows offset by a third of a strip.
  - The sheathing runs under the overhang, with a plumb eave end.
- **Joints sit.** Sloped members are made with `om.board`, their ends cut by the planes they meet.
- **Z-fighting patterns:**
  - hidden repeated ends are staggered 2.5–4 mm per row;
  - flush faces are raised 4 mm;
  - overlapping inner shells are carved where they are covered.
- **Rope:**
  - three-strand Z-lay with every strand modelled;
  - loaded parts are straight and touch what they bind;
  - bends are at least about one diameter;
  - knots come from real rigging (round turn and half hitches);
  - tails hang under gravity.
- **Foliage** is leaf-shaped double-sided cards in clusters at the branch tips, with normals pointing out of the cluster and their own AO.
- **Held tools** (first-person view models): proportions and framing are fitted numerically to the reference frames.
- **Engine:** a mesh over 64k vertices is kept out of Unity static batching, because the joined house came out scrambled.

## Not in this repository

- **Reference frames** (`docs/reference/*.png`): these are crops of a copyrighted game trailer. The generators still name them, and the contact sheet shows an empty tile where a reference crop would go.
- **The Unity game project:** scenes, shaders, game scripts, the scenario screenshots, and `Test.ps1`, `Build.ps1` and `Shots.ps1`.
- **Build outputs:** `Assets/`, `Builds/` and `Logs/` are created by the first build.

## Assets and licences

Every texture and outside asset in `tools/blender/external/` and `tools/blender/source_textures/` is **CC0** (public domain), from [ambientCG](https://ambientcg.com) and [Poly Haven](https://polyhaven.com). They are listed in `external/CREDITS.md` and `source_textures/LICENSES.md`.

New outside assets go through `tools/Assets.ps1`. It refuses any licence outside `CC0`, `CC-BY`, `OGA-BY` and `BlenderKit-RF`, and records the source and authors. API keys for sources that need them are set by each user in their own terminal (`free-assets key set <source>`). Keys are never stored in the repository.
