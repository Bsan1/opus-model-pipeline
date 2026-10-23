# Art style system: what was built, what is wrong, what is left

Handoff written 24 October 2026, for whoever continues this work (for example Codex). It is written to be honest: the
system does not yet do what the user asked.

## What the user asked

1. A process to define an art style and make every next asset in it.
2. A researched, advanced version, usable in other games too. The user will send images (possibly from several
   different games) of the look they want. The style must come out of those images in detail, and it must be documented
   in a visual document with images and explanatory text.
3. Steps 1-9 of the research report, `reports/Oyun art stili tanımlama ve denetim.md` (notes in
   `research_notes/Oyun art stili tanımlama ve denetim/`).

The scope is **3D asset modelling**. The game's lighting and post-processing are a different job.

## The mistakes

1. **The style is not derived from the images in any binding way.** This is the main failure.
   - `Style.py extract` measures 17 axes per image (table below).
   - Those numbers feed only two things: the art bible's descriptions, and the game-shot check (out of scope, see 7).
   - Not one model gate uses them. The model gates come from two other places:
     - the colour envelope (`measured.albedo`: gamut, palette, chroma ceiling per hue) is computed from **our own built
       models** (`model_colours` in `tools/Style.py`), not from the user's images;
     - triangle budgets (`stylisation.budgets_tris`), the chamfer band (`chamfer_mm`), detail floors (`detail_floor_m`)
       and finishes by kind (`finish_by_kind`) were **typed by hand**, not measured.
2. **One game, cropped around our own objects.** The sources are 17 crops from the one trailer this project clones:
   `reference_crops()` reads them from `Builds/Models/*/views.json`. So the "style" means "these objects in this trailer",
   and cloning and style are mixed together.
3. **Images from several games would be averaged.**
   - `extract` takes the median and spread of each axis over all images, and pools every pixel for one palette (k-means).
   - Mixed styles therefore give a median that describes no style, a wider band and looser checks.
   - Leave-one-out only says "this image does not look like the others". There is:
     - no per-axis agreement (which axes the images share);
     - no clustering of images into styles;
     - no way for the user to tag what an image is for (palette, shapes, materials, light).
4. **No measure is validated.** The tests (`tools/tests/test_style.py`) prove only the arithmetic:
   - known colour conversions;
   - noise has a flatter spectrum than a gradient;
   - the notan shares sum to 1;
   - an obviously odd image fails leave-one-out.
   No test shows that any axis separates two art styles, or stays stable when only the content changes.
5. **Some measures are weak or wrong proxies.**
   - `shadow_shift_a/b` compares the lightest 20 % of pixels with the darkest 20 %. Those are usually different objects
     (sky against wood), not the lit and shadowed sides of one surface. The bible's sentence "lights warmer than shadows"
     is therefore not supported.
   - `harmony`: the Cohen-Or templates T (one 180° sector) and X (two 93° sectors) fit almost anything. "T ×10, X ×7"
     says little.
   - `hue_families` and the chroma measures follow the content: a grass frame is green, a red mower crop is saturated.
   - Every measure depends on the framing and the crop.
6. **The parameters are explained nowhere.** The bible shows numbers and "7 axes off" without saying what an axis is,
   how it is computed or what it cannot tell.
7. **Scope creep.**
   - `Style.py shots`, the "Game shots" step in `tools/Verify.ps1` and the bible's section 12 compare each game shot 1:1
     with the trailer frame it recreates. That measures the game's light and post-processing; it is not a 3D art-style
     check.
   - I then suggested "darkening the game's shadows" as a next step, which is outside the task.
8. **Ad-hoc thresholds.**
   - The chroma floor per hue was changed twice (twice the median chroma, then the median) after the near-miss renders
     showed gaps. It was tuned to the examples, not derived from anything.
   - The machine budget of 30,000 triangles, which flags the wheel (38,080), was typed, not measured.
9. **The near misses are partly circular.** They are our own models with Blender approximations of mistakes (glossy
   plastic, saturation × 2.6, a baked shadow gradient, black shadows). The tests prove our gates catch our variants,
   nothing more.
10. **The look-dev "game light" is an approximation in Blender**, not the game's shader.
11. **Process.**
    - After finishing steps 5-9 I gave no written summary.
    - Several patches failed through bash heredoc quoting and had to be redone.
    - Two bugs were found late:
      - `Review.py pack` called `.items()` on the schema-2 rules list, so it would crash on any real pack;
      - the hero view was looked up under `name` instead of `file` in views.json, so `heroes.png` was never made.
      Both are fixed and tested.

## What exists and works mechanically (can be kept)

All of it is tested by `py -3 -m unittest discover -s tools/tests` (52 tests) and run by `tools/Verify.ps1`. On
24 October 2026 every step passed: style 8/8 with 2 warnings, Unity 275/275, scenarios 22/22.

**`tools/blender/style/style.json` (schema 2)**
- rules, each with `id`, `kind` (invariant or tunable), `check` and `enforce` (error or warn);
- `classes`, `finish_by_kind`, `heroes`, `exempt`, `near_misses`, `lookdev`, `notes` (the bible's prose), `measured`,
  `history`;
- `Style.py validate` refuses a rule without a check, and a near miss that names no rule.

**Model gates (`Style.py report`, `rules_check` and `check`)**
- base colours inside the envelope and under the chroma ceiling of their hue;
- finish by kind;
- triangles against the class budget;
- chamfers on hard parts. A part can opt out with a reason: `part(no_chamfer="why")` in `tools/blender/opus_model.py`,
  recorded as `spec.unchamfered`;
- every model is built for the current `style_version`.

**Look-dev (`tools/LookDev.ps1`, `tools/blender/lookdev.py`)**
- deterministic: the same pixels every run;
- lineups with label boxes;
- material spheres and 64/32 px silhouettes;
- near-miss renders: `Builds/Style/lookdev/near_<model>_<variant>.png`.

**Process tools**
- `Style.py brief <name> --class <class>`: a one-page brief per asset class.
- `Review.py decide <m> approve|revise|escalate --stage blockout|final --note "<view>: <what>"`:
  - the log is `tools/blender/decisions/<m>.jsonl`, with round numbers;
  - a note without a location is refused;
  - after 3 revisions only approve or escalate is accepted.
- Review packs carry `heroes.png` and `near_misses.png`. A "style:" finding needs a location in the pack.

**The art bible (`Style.py bible` → `Builds/Style/art_bible.html`)**
- one self-contained HTML file, generated from the data, with light and dark themes;
- the mechanics are reusable, the content is not good enough (see the mistakes).

## The 17 image axes (what `measure()` in `tools/Style.py` computes)

Colour is in CIELAB D65 (L* 0-100 for lightness, chroma for saturation). The detail axes are computed on the image
shrunk to 256 px on its long side (Pillow, bicubic).

| Axis | Meaning | Computation |
|---|---|---|
| lightness_median, lightness_p10, lightness_p90 | how light the image is; how dark its darks and how light its lights | median and 10th / 90th percentile of L* |
| contrast_rms | soft or hard | standard deviation of L* |
| notan_dark, notan_mid, notan_light | three-value structure | share of pixels with L* < 35, 35-70, ≥ 70 |
| chroma_median, chroma_p90 | overall and strongest saturation | median and 90th percentile of chroma |
| chroma_dark, chroma_mid, chroma_light | where the saturation is spent | mean chroma in the three value bands |
| shadow_shift_a, shadow_shift_b | intended: light warmer or cooler than shadow | (a, b) mean of the lightest 20 % minus the darkest 20 %. A wrong proxy (mistake 5) |
| fourier_slope | calm large forms or fine detail | slope of the radially averaged amplitude spectrum, log-log, radii 4 to N/4, Hann window |
| edge_density | amount of edges and lines | share of pixels whose L* gradient is above 6 |
| busyness | how busy the surfaces are | mean L* standard deviation in 5 × 5 windows |

The non-scalar outputs are `hue_families` (12 OKLCh bins weighted by chroma), `harmony` (the best Cohen-Or template),
and `shadow_colour` / `light_colour`.

## What a correct version needs

1. **Input:** N images, possibly from different games, each optionally tagged by the user with what it is for (palette,
   shapes, materials, light, overall).
2. **Measure the style, not the content:**
   - measure objects (crops or masks) with normalised framing;
   - treat hue only as evidence when the images agree on it;
   - replace the shadow-shift proxy with a measure taken on the lit and shadowed sides of the same surface, or drop it.
3. **Agreement across sources:**
   - for each axis, how much the images agree;
   - axes where they agree become rules, with a strength;
   - axes where they disagree are not part of the style, or the user chooses;
   - cluster the images and ask the user which cluster is the target.
4. **Validate every axis before it becomes a gate:**
   - use labelled image sets of 2-3 clearly different styles;
   - compare the spread within a style with the difference between styles (for example a Fisher ratio, or the
     leave-one-out classification accuracy);
   - keep only the axes that separate the styles, and show the scores in the document.
5. **Turn the image findings into 3D asset rules:**
   - palettes and chroma ceilings from the images, with the light roughly removed, instead of from our own models;
   - value, contrast and detail-frequency targets measured on renders of the asset in neutral light, against object
     crops of the sources;
   - budgets and detail floors derived from something stated, or clearly marked as the user's choice.
6. **Explain every parameter where it is shown,** with its own picture (notan, edge map, spectrum) and what it cannot
   tell.
7. **Remove the 1:1 trailer comparison from the style system:**
   - remove `Style.py shots`, the "Game shots" Verify step and bible section 12;
   - keep `tools/Compare.py` (geometric accuracy against a reference) as a separate model-accuracy tool.

## Files

- **Style tools:**
  - `tools/Style.py`: measurement, extract, the gates, shots, brief, bible;
  - `tools/blender/style/style.json`;
  - `tools/blender/lookdev.py`, `tools/LookDev.ps1`.
- **Review:** `tools/Review.py` (pack, record, decide, state); `.claude/skills/model-plausibility/review.md`.
- **Skills:** `.claude/skills/art-style/SKILL.md`, `.claude/skills/model-plausibility/SKILL.md`.
- **Tests:** `tools/tests/test_style.py`, `tools/tests/test_review.py`.
- **Outputs:** `Builds/Style/` (`art_bible.html`, `style_board.png`, `game_shots.json`, `briefs/`, `lookdev/`).
- **Constraints:**
  - `docs/reference/` holds copyrighted trailer frames: never publish them;
  - the public pipeline repository (github.com/Bsan1/opus-model-pipeline) does not contain this art-style work yet.
