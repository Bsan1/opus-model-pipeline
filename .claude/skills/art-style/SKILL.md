---
name: art-style
description: Define an art style from the images the user sends (frames, screenshots, concept art, a moodboard) or a description, document it as a generated art bible, get it approved, and keep every new 3D asset inside it - measured on five axes (tools/Style.py), rules with ids and checks (tools/blender/style/style.json), a deterministic look-dev scene (tools/LookDev.ps1), gates in Verify and in the review. Use when starting a project's look, before making any new asset, or when the style should change.
---

# Art style

Research behind this: `reports/Oyun art stili tanımlama ve denetim.md` (art bibles, image style analysis, checkable rules, studio consistency). The principle is to hold the style with measured gates, not with adjectives. Every rule names the check that enforces it; every number is measured from the user's images; the art bible is generated from the data, never maintained by hand.

## The pieces

| Piece | What it is |
|---|---|
| `tools/blender/style/style.json` | **The style.** `stylisation` holds the anchor, the tie-breaker, what is modelled versus painted, detail floors, the chamfer band and triangle budgets. `classes` puts each model in a class; `finish_by_kind` says which finishes each kind of surface may have; `heroes` are the assets every new one is compared with; `exempt` lists technical assets outside the look, each with its reason. `rules` gives each rule an `id`, a `kind` (`invariant`: changing it makes a new style; `tunable`: adjusted within the style), a `check` (the gate, test or `review` that enforces it) and optionally `enforce: warn` (the gate reports but does not fail). `near_misses` names the mistakes to show and the rule each breaks. `lookdev` sets the game light, placement and the near-miss models; `in_game.pairs` pairs reference frames with the game shots that recreate them; `notes` is the prose of the art bible. `measured` is written by `Style.py`. `history` and `style_version` record changes. |
| `py -3 tools/Style.py extract [images]` | **Measures the sources** on five axes per image: colour, value/notan, hue (OKLCh families, Cohen-Or harmony), light (the shadow-to-light colour shift) and detail (Fourier slope, edge density, busyness). It stores the median and IQR across images, plus palettes and accents. It also measures the base-colour envelope of the defining models, and runs a leave-one-out test (how much of each image falls inside the others' band). |
| `powershell -ExecutionPolicy Bypass -File tools/LookDev.ps1` | **The look-dev scene**, deterministic (the same pixels every run): lineups at true scale beside a 1.8 m person, in neutral and game light, with label boxes; one material sphere per surface; 64 and 32 px silhouettes; the near-miss models as they are and as each near miss. |
| `py -3 tools/Style.py bible` | **The art bible** in `Builds/Style/art_bible.html`, 14 sections, each with prose (`notes`), numbers, images and the checks: vision, notan, colour (with the ceiling per hue), hue and harmony, light, detail, shape, materials, the labelled lineup, one page per asset class (every model with its view, triangles against the budget, gate results and review state), do/don't (each near miss with the rule, the check and what is measured), the game beside the trailer, the process with the decision log, and the checks and history. |
| `py -3 tools/Style.py report` / `validate` | **The gates** (Verify runs `report`): base colours (surfaces and atlas) inside the envelope and under the chroma ceiling of their hue; finishes allowed for their kind; triangles within the class budget; chamfers on the hard parts of the classes in `chamfer_applies_to`; built for the current `style_version`. `validate` refuses a rule without a check or a near miss without a rule. |
| `py -3 tools/Style.py shots` | **The look in the game** (Verify, warning only): each game shot against the reference frame it recreates, both measured at the same size; an axis is off when it moves more than half the sources' own spread. A difference here is the game's light or post-processing, not one asset. |
| `py -3 tools/Style.py brief <name> --class <class>` | **The brief** a new asset starts from: the style in one page for its class. |
| `py -3 tools/Review.py decide <m> approve\|revise\|escalate --stage blockout\|final --note "<view>: <what>"` | **One decision per round**, logged with its round number; a note must say where; after 3 revisions the user decides. |

## 1. Define a style (a new game, or when the user changes it)

1. **Sources:** ask the user for the images that show the look they want.
   - 20-50 is best: frames of a video, screenshots, concept art. They should show the kinds of objects to be made, in the light they will be seen in.
   - Crop out UI and anything unrelated: measures from a screen full of HUD are about the HUD.
   - From a description alone, find images first (model-plausibility step 2b) and get the user's yes on them.
2. **Measure:** `py -3 tools/Style.py extract <images...>`.
   - Read the leave-one-out line. An image well below the others is either off-style, so drop it, or a second style, so ask the user.
3. **Write `stylisation` and `rules`:**
   - The **anchor** names an existing look and the distance from it ("like X, but with fewer details and softer edges"). The **tie-breaker** names what wins in a conflict.
   - The **detail floor** sets which features are modelled and which are painted.
   - Every rule needs a `check`. If none exists yet, write `review` and add the gate when a defect shows up.
   - Mark the few `invariant`s (what makes the style recognisable); the rest are `tunable`.
4. **Pilot:** build one or two typical assets, a hard-surface prop and an organic one. Then run `tools/LookDev.ps1` and `py -3 tools/Style.py bible`.
5. **Approve:** send the user the art bible with **one** question: is this the style?
6. **Lock it:**
   - on a yes, approve the pilots (`tools/Verify.ps1 -Approve <models>`);
   - run `Style.py extract` again, so the base-colour envelope now comes from the approved models only;
   - raise `style_version` and add a `history` entry.

## 2. Apply it to every new asset

- **Before the plan:** `py -3 tools/Style.py brief <name> --class <class>`, and read it. For a new kind of object, also read the art bible's lineup and do/don't pages.
- **Block-out first:** the preview build, then one decision (`Review.py decide ... --stage blockout`). Detail comes after an approve.
- **Colours:** take them from the base-colour palette, or sample them from the source and keep them inside the envelope. An exception gets `style exception: <why>` in its surface note.
- **Scale and detail:** stay within the class's detail floor and triangle budget, and the chamfer band for hard parts. Check the silhouette at 64 and 32 px in the look-dev output.
- **Gates:** `tools/Verify.ps1` runs `Style.py report` after the models. A colour, an atlas or a style version outside the style fails the run, with the surface's name.
- **Review:** every review pack carries `style_board.png`, `heroes.png` (compare pairwise, one axis at a time) and `near_misses.png`, with the rules. The reviewer reports mismatches as findings starting with "style:", each with a location (a pack image and where in it); `record` refuses one without. AI judgement is a second opinion, never a gate: confirm each "style:" finding by eye or with a number.
- **Look:** before approval, see the asset in the lineup beside the approved ones, in both lights. This is where a foreign asset shows.

## Near misses: prove every gate

A near miss is the same model with one typical mistake: glossy flat plastic, oversaturated colours, a shadow painted into the texture, black shadows without sky light. `style.json` `near_misses` names each with the rule it breaks; `LookDev.ps1` renders them on `lookdev.near_miss_models` (one hard-surface, one organic model: a mistake shows on what it affects); the bible puts each beside the style with what the measured checks see. A gate counts only when a test shows it catching its near miss (`tools/tests/test_style.py`, NearMissTests). When none can, the rule's check says `review` and the bible says the review must see it.

Measured on 24 October 2026: one chroma ceiling let a tree 2.6 × more saturated through, because the ceiling came from the mower's red deck. The ceiling is per hue now, and the test proves it. The do/don't page then showed the shed's siding turning teal under a floor of twice the median chroma; the floor is the median now. Look at the do/don't page after every style change: it is where a gate's gap shows.

## 3. Evolve it

- **Only the user changes the style.**
  - Edit `stylisation` or `rules`, raise `style_version`, add a `history` entry, and run `extract` again.
  - Then `Style.py report` lists every model built for an older version or now outside the style. Show the user that list; don't rebuild unasked.
- **Changing an invariant makes a new style:** re-approve the pilot assets first.
- **Approving an asset that widens the look is also a style change,** because the next `extract` takes it in. Say so when asking.

## Don't

- Don't make a learned similarity or aesthetic score (CLIP, an aesthetic predictor) a pass/fail gate: they lean towards content, not style.
- Don't use literature thresholds as absolute limits in a stylised project. Every threshold comes from the user's own images.
- Don't compare a lit frame with a base colour. Don't compare a prop on a plain background with a full scene. Don't compare numbers measured with different settings.
- Don't put a game's numbers (its sky colour, its chamfer millimetres) into the tools. They belong in that game's `style.json`.
- Don't make a new gate fail the run before its near miss is proven and the user has decided on the existing assets it flags: start it with `enforce: warn`.
- Don't add a dependency with a non-commercial or unchecked licence to the public pipeline.

## Cost

`Style.py` and `LookDev.ps1` run locally and print a few lines each. Look at the art bible once per style change, not once per asset. The reviewer gets the board inside the pack.
