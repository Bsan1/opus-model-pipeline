# Lessons: past mistakes as general rules

Each entry gives the mistake once, the principle it breaks (P1–P8 in SKILL.md) and how the same class of mistake is caught now:
- **auto:** a gate or check fails the build;
- **review:** the independent review should see it;
- **look:** only a close look in the game catches it.

Merge an entry into an existing one when it shares the principle and the detection. Keep this file under about 30 entries.

| # | Object, what was wrong | Why it was wrong → principle | Caught by |
|---|---|---|---|
| L1 | tire_swing: the rope read as "a bent square metal tube": one 12-sided tube, area-weighted normals, bends tighter than its thickness, legs floating off the tire | Load-bearing rope follows its load path and real rigging (P2, P5, P8) | auto: rope audit, `route`; review: knot types and strands |
| L2 | mower (the user's rule for the first mower): "cables should not go to meaningless places"; the video shows the starter rope staying at the engine, not running to the handle | Every cable or rope has a reason and ends where it works (P1, P4) | review: the plan's job for each line |
| L3 | mower: the control cable needed clips and a real end in the brake tab | A control chain is complete and held along its run (P3, P4) | auto: `route` (a short cable fails); review |
| L4 | trimmer: four button squares, an O-ring handle and a wide guard that the video does not have | Invented details that the source contradicts go (P7) | review: source notes against the sheet |
| L5 | hose nozzle: the head's shape, angle and length differed from the video. I had shortened the barrel as "not elegant" when the real problem was a thin pipe seen from the side; rebuilt from scratch with the rear trigger the video shows | Read shape and mechanism from the source; fix the cause the user points at, and ask when it is unclear (P4, P7) | review: source notes against the sheet |
| L6 | wheel: 16 big blocks spilling down the sidewall and a red cap: a toy off-road tire | Detail scale and colour come from the source, not from a generic idea (P7) | review; look |
| L7 | shed: 3 × 2.6 m with a 34° roof instead of 2.6 × 2.6 m with 45° | Proportions are measured against something of known size in the frame (P7) | look: compare with the frame; review if references are in the pack |
| L8 | house: stair stringers cut as one straight slope stuck up through both treads | Members are shaped the way they are really built: notched stringers (P5) | auto: overlap and construction gates catch some; review |
| L9 | house: the porch's rake boards cut square to their slope crossed the fascia | A member's end is cut to the face it meets (P3) | auto: joint gate, `checks/joints.py` |
| L10 | house: deck boards stopped 1 cm short of the rim joists with nothing under them | Every board rests on what carries it (P2, P5) | auto: holes gate (see-through), construction gate |
| L11 | house: a riser 5 mm above its tread left a light slot | Thin slots onto front faces are a gate blind spot (P5) | look: close-ups in the built game |
| L12 | house and shed: holes and black lines in models called "clean" | Never claim clean without measured gates (process) | auto: holes and texel gates |
| L13 | house: one wood photo on every wooden surface (siding, shed boards, deck, trim) | Different stuff, or the same stuff in another context, looks different (P7, P8) | auto: the `MATERIALS` registry rules |
| L14 | house: shingle row lines drew moiré arcs from 8 m | Sub-pixel repeated geometry belongs in a mipmapped texture (technical) | look: far shots, luminance profile |
| L15 | house: the joined mesh was scrambled in game by static batching | Engine limits are part of construction (technical) | auto: Unity test `BigModelMeshesStayOutOfStaticBatches` |
| L16 | tree: dark patches painted on the bark were leaf shadows in the video | Do not bake lighting into a texture (P8) | review: source notes |
| L17 | yard props: grime on painted wood read as stains | Wear and grime only where they really occur (P8) | review; look |
| L18 | tire_swing: the tire hung under the branch's middle, not under where the rope leaves it (moved 9 cm) | Loaded rope runs straight: gravity sets the hang point (P2, P8) | review; rope audit for the rope itself |
| L19 | mower: every part glossy, the shine given by kind; the user: "black plastic is matte, red metal is glossy; do you model without understanding what the materials are?" | The finish comes from each part's real material and the source, not from its kind (P7, P8) | review: material card notes; look |
| L20 | house and shed: every board's tone changed at every build. The seed was Python's `hash(name)`, which is salted per process | Reproducible builds: seeds from stable hashes (crc32), never `hash()` or set order (technical) | auto: hashing two builds of a model; reviews and approvals go out of date when it fails |
| L21 | the fingerprints for reviews and approvals were hashed in mesh order, so calibration got a new hash at every build. The wheel's UVs and atlas differed from build to build too: `extrude_face_region`, `inset_region` and the bevel modifier order their faces, and where each face starts, by memory address, and smart UV, the bake and the export's triangulation follow that order | The same input must give the same output: elements in an order given by geometry (`om.canonical_order`, `om.canonical_mesh`), fingerprints independent of order (technical) | auto: `checks/determinism.py` (fails without the fix: 23 faces differ) |
| L22 | the construction gate took the biggest connected piece as held, so a whole object floating 50 cm above the ground passed; `attach` was met by any two nearby pieces; `route` by any piece passing the points | A check must test the claim (held by a support, these two parts meet), not something merely correlated with it (P2, P3) | auto: `checks/plausibility.py` (a broken and a correct case for each) |
