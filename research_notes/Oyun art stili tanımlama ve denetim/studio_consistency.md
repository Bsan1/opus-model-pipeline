# How studios keep a consistent art style (and how a code-first pipeline can copy it)

Scope: 3D games. Notes are for a report writer; every claim has a link. Source quality is flagged:
**[primary]** = studio, engine or platform document; **[talk desc]** = only the abstract or coverage of a talk was readable; **[vendor]** = outsourcing or AI-tool marketing; **[secondary]** = blog or press paraphrase.
Tags for small teams: **[1-2 person: yes]** = cheap and realistic for a one- or two-person team; **[1-2 person: partial]** = only a reduced form makes sense; **[1-2 person: no]** = needs a team or budget.
Access note: GDC Vault was in maintenance (redirected) during this research, the Riot Nexus VFX post now redirects, and Dot Esports returned 403. Content from those pages comes from search-result summaries and is marked as such.

## 1. The style approval pipeline (references, style frames, paint-overs, hero assets, pilots, reviews, sign-off)

### Takeaway
Across studios the order is the same: written rules and curated references first, then a few "hero" or target assets that prove the rules on real geometry and lighting, then batch production gated at block-out and detail passes. Feedback is given as located paint-overs by one owner, and each asset gets a single decision (approve, revise, escalate). The hero assets and the "near miss" examples matter more than the length of the style document.

### Cited Findings
- Guerrilla Games (Horizon) outsources a very large share of its assets, keeps a small internal asset art team and a relatively large concept art team, and guards quality through highly detailed briefs. This is the GDC "Art Direction Bootcamp" talk by Maarten van der Gaag; only the abstract was reachable. **[talk desc]** — [GDC Vault: Guerrilla Games' Approach to Asset Production](https://gdcvault.com/play/1023158/Art-Direction-Bootcamp-Guerrilla-Games)
- A Guerrilla-related article says outsourcing studios won't do visual design or art direction, so outsourcing needs careful preparation, and it estimates a style-guide phase of about 2 months. This comes from a search summary; the page was not opened. **[secondary]** — [DualShockers: Guerrilla talks outsourcing](https://www.dualshockers.com/ps4-exclusive-horizon-zero-dawns-new-images-show-a-roof-guerrilla-talks-outsourcing/)
- Overwatch: per assistant art director Arnold Tsang, the team set its core tenets first, then worked with engineers and animators to build "visual targets" that realized the style guide. **[secondary interview]** — [Vice: What it's like to art direct Overwatch](https://creators.vice.com/en_us/article/heres-what-its-like-to-art-direct-overwatch); talk: [GDC 2017 The Art of Overwatch](https://gdcvault.com/play/1024268/The-Art-of-Overwatch-Evolving) **[talk desc]**
- Rare's Sea of Thieves talk (Ryan Stevenson, GDC 2018) frames the look as a few simple rules that carry through every visual part of the game. The concrete rules were not in the coverage. **[talk desc]** — [80.lv GDC18 Visual Adventures on Sea of Thieves](https://80.lv/articles/gdc18-visual-adventures-on-sea-of-thieves/); recording: [Game Developer video](https://gamedeveloper.com/art/video-how-rare-crafted-the-look-and-feel-of-i-sea-of-thieves-i-)
- A secondhand paraphrase of the Sea of Thieves rules: simplify structures and build complex scenes from simple objects, hand-paint textures instead of using photos, make props worn and slightly imperfect, and use the light source to set the mood. **[secondary]** — [Habrador blog: stylized graphics in Fortnite and Sea of Thieves](https://blog.habrador.com/2018/08/stylized-graphics-fortnite-sea-of-thieves.html)
- Sea of Thieves water started photorealistic, and artists then added stylisation on top so it still behaves like water. Stylisation is layered on correct behaviour, not a replacement for it. **[secondary]** — [MCV: Sea of Thieves started with photorealistic water](https://www.mcvuk.com/development-news/rares-sea-of-thieves-started-with-photorealistic-water/)
- Riot's League VFX team found there was "no single point of reference for successful VFX", which led to inconsistency across teams. They wrote a style guide with four goals (visual clarity, minimal clutter, support the champion theme, delight players) built on five areas: gameplay, value, color, shape and timing. Read via search summary; the page now redirects. **[primary, indirect]** — [Riot Nexus: VFX Style Guide (2017)](https://nexus.leagueoflegends.com/en-us/2017/10/dev-leagues-vfx-style-guide/)
- Blender Studio's documented hero-asset process: drawn concept, then 3D tests (modelling and sculpting), then paint-overs on the 3D model to annotate and push it, which starts the feedback loop. Preliminary colour, lighting and shading are tested against the target look, and the outputs are a design model, look-dev paintings and style guides for later departments. This is a WIP docs pull request. **[primary, WIP]** — [Blender Studio tools PR #143 (pipeline overview)](https://projects.blender.org/studio/blender-studio-tools/pulls/143.patch); related: [Blender: Asset Creation Pipeline Design (2021)](https://code.blender.org/2021/06/asset-creation-pipeline-design)
- Recommended practice: lock a few hero assets early (one character, one environment piece, one prop) to test the direction on real geometry and lighting before other assets are built. Put "near misses" next to good examples; the source claims this prevents more rework than the rest of the bible combined. **[vendor]** — [Juego Studio: Art Direction in Games, lock a visual style before production](https://www.juegostudio.com/blog/art-direction-in-games)
- Paint-over feedback is a standard art-lead duty. A Blizzard environment-artist job listing asks for clear paint-over and verbal feedback to both internal and outsourced artists. **[primary, job ad]** — [Hitmarker: Blizzard Environment Artist listing](https://hitmarker.net/jobs/blizzard-entertainment-environment-artist-dungeons-architecture-and-props-774549)
- A practitioner describes giving paint-overs to an outsource team and building a smart material to unify the look and shorten turnaround. Feedback plus a shared material fixes drift faster than feedback alone. **[secondary, portfolio]** — [Gorilla Gills ArtStation: Mutant Arm Environment](https://gorillagills.artstation.com/projects/eJGGLb)
- An outsourcing pipeline with explicit gates, in order **[vendor, fetched]** — [Lemonsky: Game art outsourcing pipeline](https://www.lemonskystudios.com/insights/game-art-outsourcing-pipeline):
  1. Four documents before the first brief: style guide, technical specification, workflow map, definition of done.
  2. A paid test asset and a small ramp-up batch. The test asset "proves the style guide works".
  3. A brief with reference, specs, scope and deadline. If it needs a follow-up call to be understood, it goes back.
  4. Block-out gate, which locks silhouette, proportion and read. The source calls it "the most valuable gate in the pipeline".
  5. Detail pass reviewed against the style guide.
  6. Delivery: naming, folder and import tests pass. An asset counts as delivered "when it performs in the build".
  7. Integration on target hardware.
  8. Reviews through one owner, one tool and a fixed cadence. Every note has a location (drawn callout, named material or region, or the reference it should match), and each asset has a revision budget.
  9. One decision per asset: approved, revise with notes, or escalate. "The partner never hears two opinions about the same asset."
  10. Health metrics: first-pass approval rate and revision rounds per asset.

### Inferences
- **Ordered workflow for a code-first pipeline** (synthesised from the sources above):
  1. Gather references and measure them (palette, value range, proportions).
  2. Write the style rules as data (style.json or similar).
  3. Build 2-3 hero assets plus deliberately wrong "near miss" variants.
  4. Look-dev scene and lineup check (section 2).
  5. Freeze the hero assets as the bar.
  6. Per new asset: block-out gate (silhouette, proportion and scale against the lineup), detail gate (materials, palette and value checks), then an in-game camera shot.
  7. One reviewer decision: approve, revise with located notes, or escalate.
  8. Record the decision and the round count.

  Steps 1-3 and 6-8 are **[1-2 person: yes]**. A formal 2-month style-guide phase is **[1-2 person: no]**, but a 1-2 day "hero + near-miss" pass is realistic.
- For an AI or procedural author, the "paint-over" maps to a located correction note on a screenshot: an annotated image or a named part or material plus the target value. A vague "make it nicer" does not count. The Lemonsky rule that "every note has a location" can be enforced mechanically, for example by requiring a part or material id in every review note.
- The Riot VFX guide structure (gameplay, value, color, shape, timing) is a compact checklist template that fits a small team better than a long art bible.
- The project already has an `art-style` skill (measured colours in tools/Style.py, rules in style.json, a style board, a Verify check). The studio practices that skill lacks are explicit hero or near-miss assets, a block-out gate before detail, and a per-asset decision log with round counts.

### Gaps
- The full Guerrilla brief template and the Sea of Thieves rule list could not be read (GDC Vault in maintenance; coverage only paraphrases).
- No primary source found for formal sign-off stage names at a named AAA studio (e.g. "concept approved, block-out approved, final approved" with titles of approvers). Outsourcing vendors describe them, but only as marketing.

## 2. Look-dev and test scenes (lighting tests, material balls, lineups, turntables, grey-box to final, gameplay camera)

### Takeaway
Studios check assets in neutral, known lighting and compare them with a reference asset side by side, so that asset defects are not confused with scene lighting. They also check albedo and roughness against measured ranges with debug views, give everyone the same scale reference, and judge layout and read at the gameplay camera during block-out. All of these can be automated cheaply.

### Cited Findings
- Unity's (now legacy) Look Dev tool is an image-based lighting viewer. It can load two assets in two views so that "an Art Director can check that a new Asset matches the art direction guidelines of a reference Asset". Accurate test lighting tells you whether the asset itself or the game's lighting causes poor quality. **[primary]** — [Unity Manual 2018.2: Look Dev](https://docs.unity3d.com/2018.2/Documentation/Manual/LookDev.html); [Unity 2019.2 Look Dev (experimental)](https://docs.unity3d.com/2019.2/Documentation/Manual/LookDev.html)
- Look-dev artists "own the visual truth of assets". They author and validate materials and shaders so assets stay consistent under different lighting, validate under HDRI sweeps, multiple key/fill/rim setups and exposure brackets, and produce turntables and "look bibles". **[secondary, school]** — [VFS: Look Dev Artist](https://vfs.edu/node/8534)
- Ninja Theory presented a formal look-dev workflow for UE4, from photo shoot to final look-dev scene (Unreal Fest Europe 2019; only the description was seen). **[talk desc]** — [Unreal Fest Europe 2019: Enabling a Look Development Workflow for UE4](https://www.unrealengine.com/events/unreal-fest-europe-2019/enabling-a-look-development-workflow-for-ue4-from-shoot-to-final-lookdev-scene)
- Sumo Digital built a PBR Value Checker for Unreal. It reads unlit viewport colours on a linear 0-1 RGB scale, compares them with a hard minimum and maximum, and recolours the view: in Albedo mode green means acceptable, red too dark, blue too bright, and Roughness mode works the same way. It adjusts expectations for dielectric versus metal and for roughness. "Green" only means within a realistic range, not perfect. Exact thresholds are in a linked PDF that was not read. **[primary]** — [Sumo Digital: PBR Value Checker article](https://www.sumo-digital.com/?p=3443)
- Unity's Material Validator debug mode uses sRGB luminance ranges of 50-243 for non-metals and 186-255 for metals, and flags pixels below the minimum in red and above the maximum in blue. **[primary]** — [Unity 6 Manual: Material Validator](https://docs.unity.com/en-us/engine/6000.0/manual/materials-and-shaders/materials/troubleshooting/material-validator)
- OpenMoonRay gives physically reasonable albedo (max of RGB) as 0.032-0.87, and about 0.04 for very dark materials. **[primary]** — [OpenMoonRay: PBR Validity](https://docs.openmoonray.org/user-reference/how-to-guides/pbr-validity/)
- BeamNG's modding docs warn that materials checked only under the authoring tool's default studio light can look too bright, too dark, too saturated or too reflective in game. **[primary]** — [BeamNG: Blender and Substance Painter workflow](https://documentation.beamng.com/modding/lighting/art_workflow/)
- A CGI lead handed every look-dev artist a scale-reference file of a man, so that all models are built to the same scale. This is an anecdote from one student project. **[secondary]** — [UAL student blog](https://jhoward.myblog.arts.ac.uk/?p=722)
- Epic's Fortnite-ready asset guide: check scale and units first (cm, Z-up), use a 512 cm grid, and note that player characters are 192 cm tall so that architecture and furniture fit. Import a mesh at block-out to catch coordinate problems early, and put the pivot at ground level, or at the centre for randomly rotated meshes. **[primary]** — [Epic: Fortnite-ready assets best practices](https://dev.epicgames.com/documentation/fortnite/fortniteready-assets-best-practices-in-fortnite); [Epic: Modeling tips in UEFN](https://dev.epicgames.com/documentation/fortnite/modeling-tips-in-unreal-editor-for-fortnite)
- Block-out guidance: consider human vantage points, narrow down camera-height requirements, and test paths, sightlines and landmarks before detail is added. **[secondary, school]** — [RMCAD: Environment Artist Playbook, blockout to final](https://www.rmcad.edu/blog/environment-artist-playbook-from-blockout-to-final-pass/)
- A typical critique from a community art test: flat white lighting made the materials hard to judge, and the materials "all look the same, a bit like a rather glossy plastic". Lighting and material problems mask each other. **[secondary, forum]** — [Polycount: environment art test](https://polycount.com/discussion/189476/enrvironment-art-test)

### Inferences
- **Minimum look-dev kit for Blender to Unity** (all **[1-2 person: yes]**):
  - A fixed neutral HDRI plus 2-3 named lighting rigs (key/fill/rim, overcast, game lighting) saved as a scene that renders the same way every time.
  - A material-ball row: one sphere per registered material, rendered under each rig.
  - A lineup scene: new asset next to the frozen hero assets and a human-height reference, all at a fixed camera.
  - An automated albedo and roughness range check in the style of Sumo, Unity and OpenMoonRay, with per-material-type ranges.
  - A render from the real gameplay camera at play distance.
  - A turntable only for hero or complex assets.
- Use the side-by-side "new vs reference" idea from Unity Look Dev as a board image (new asset beside the hero asset, same rig), so one image goes to review. This fits the project's token-economy rule of one board image.
- Material-ball and lineup renders are deterministic, so they can be pixel- or metric-diffed between versions to catch regressions when the style changes (see section 6).

### Gaps
- Exact Sumo Digital thresholds are not known (the PDF was not opened).
- No primary studio source was found that describes a formal "asset lineup" standard. The practice is widely described informally, but I found no citable AAA document for it.

## 3. Material libraries, master materials, trim sheets and palettes as style enforcement

### Takeaway
The strongest consistency tool in studios is technical: a small set of master materials (shared shaders) exposes only a few parameters, so every asset is forced into the same shading model. Shared trim sheets and texture sets make materials reusable across assets. Enforcement comes from what is exposed, not from any engine feature.

### Cited Findings
- A UW tech-art course assignment has students build 2-3 master materials and create instances from them, with the requirement that all materials look like they belong in the same game. **[primary, course]** — [UW CSE 490J Tech Art assignment 4](https://courses.cs.washington.edu/courses/cse490j/17su/assignments/assignment_4)
- A Fab stylized-surface pack ships 1 advanced master material and 29 material instances, presented as a way to keep a cohesive visual identity across environments while each surface varies by parameters. **[vendor]** — [Fab: Stylized Surface Material Pack](https://www.fab.com/listings/db924329-af84-4612-b96e-e2dcadd0ac9f)
- A hobbyist recreating an Overwatch-like look in UE4 uses one instanced master material with high roughness and low specular as the default for most surfaces, swapping only textures. **[secondary, forum]** — [Polycount thread](https://polycount.com/discussion/comment/2471072/)
- Insomniac's "Ultimate Trim" (Sunset Overdrive, GDC 2015, Morten Olsen): a standardised trim layout of horizontal strips with increasing vertical resolution, plus normal maps with 45-degree bevels on every edge. It gives hard-surface props a high-poly look, and materials move between assets without redoing UVs. Free Blender and 3ds Max add-ons and Substance generators exist (non-commercial). **[secondary]** — [CG Channel: Ultimate Trim tools](https://www.cgchannel.com/?p=105538); art-direction side of the same game: [GDC: Insomniac put the style in Sunset Overdrive](https://gdconf.com/article/see-how-insomniac-put-the-style-in-sunset-overdrive-at-gdc-2015/)
- Riot's League texture update aimed for "everything looks consistent" and for art that supports gameplay rather than hindering it. **[secondary press]** — [PC Gamer: LoL mass texture update](https://www.pcgamer.com/uk/league-of-legends-mass-texture-update-brings-new-hotness-to-old-champions)
- Overwatch's team hand-crafted textures for a painterly, "artisan" result and wanted the world to feel made by people rather than simulated. Coverage of Tsang's comments; exact article not verified. **[secondary]** — [Cook & Becker: Designing Overwatch](https://cookandbecker.com/en/article/378/designing-overwatch.html)
- A vendor style-guide checklist includes exact colour-palette values and line-weight rules per asset category (2D-oriented marketing). **[vendor]** — [Nerdbot: 5 things great 2D art services have in common](https://nerdbot.com/2026/08/06/5-things-great-2d-art-services-have-in-common/)

### Inferences
- For a procedural Blender pipeline the equivalent of "master material + instances" is a material registry: each material type (wood, painted metal, grass, fabric) has one builder function with a few exposed parameters (tint from palette, wear, roughness band). Models request a registry entry and never build ad-hoc node trees. **[1-2 person: yes]** The project's existing MATERIALS registry and its rule that different materials get different textures already implement this.
- Palettes become enforceable when stored as named swatches in data and referenced by name (e.g. `palette.wood_dark`), not as free RGB in model code. A lint step can then reject literal colours. **[1-2 person: yes]**
- Trim sheets suit modular hard-surface sets (buildings, machines). For a mostly organic or outdoor scene they are optional. **[1-2 person: partial]**
- In Unity the same rule means one shared shader (or Shader Graph) per material family plus material variants, with a check that every imported material uses a whitelisted shader. **[1-2 person: yes]**

### Gaps
- No primary AAA source (Epic or a studio) was found that explicitly documents "master materials as style enforcement" policy, e.g. locking parameters or limiting who may create new master materials. Evidence is courses, forums and marketplace descriptions.
- No source was found on Unity-specific studio shader libraries used for style (as opposed to performance).

## 4. Outsourcing style guides, acceptance criteria, and UGC-platform enforcement

### Takeaway
Outsourcing relies on a style guide plus a technical spec plus a "definition of done", a paid pilot asset, gated milestones and a single reviewer. UGC platforms (Roblox, Fortnite/Fab) enforce only technical and safety rules automatically: scale, triangle budgets, texture size, UVs, rigging, naming. They do not judge aesthetic style. Style consistency is a human or curated layer on top of automated technical gates.

### Cited Findings
- Roblox's UGC validation system runs automatically on every Studio upload of an avatar asset and on in-experience creation via AvatarCreationService. **[primary, fetched]** — [Roblox: Validation system](https://create.roblox.com/docs/marketplace/validation-system)
  - Check categories: schema (hierarchy, child types, tags, banned scripts); mesh (triangle budgets, bounding boxes, surface area, centering, watertightness, degenerate triangles); textures and materials (max resolution, UV validity, PBR textures on SurfaceAppearance, vertex colours); rigging and skinning; inner and outer cages (fit and UV conformance to templates); attachments (naming, position, orientation); dynamic heads (at least 17 FACS poses; head size flagged below 95% or above 120% of default); and security and moderation.
  - Failures return error messages plus "visualization tools … that provide asset-specific visual guides".
  - The page describes no aesthetic or style review. Moderation is a separate step before sale.
- Roblox also ships an offline Blender add-on (Avatar Validation Tool) that catches common issues before export. It is not comprehensive, so test in Studio too. **[primary]** — [Roblox: Blender Validation Tool](https://create.roblox.com/docs/art/avatar/validation-tool)
- Fab requires technical file-format and structure criteria plus content criteria from its Terms and Epic Content Guidelines, and says it publishes only products with real value to customers. **[primary]** — [Fab: asset file format and structure requirements](https://dev.epicgames.com/documentation/fab/asset-file-format-and-structure-requirements-in-fab); [Fab documentation](https://dev.epicgames.com/documentation/fab/fab-documentation)
- Fortnite (UEFN) asset guidance is mainly technical: units, scale (192 cm player), grid, pivots and per-platform budgets. **[primary]** — [Epic: Fortnite-ready assets best practices](https://dev.epicgames.com/documentation/fortnite/fortniteready-assets-best-practices-in-fortnite)
- Unreal studios use or buy validators: e.g. a third-party "Asset Pipeline Validator" checks naming (per-class prefixes and regex), triangle budget, texture source size and collision. Thresholds live in a data asset; it auto-fixes naming and collision and flags the rest for a human. **[vendor]** — [Unreal forums: Overthink Studio Pipeline Validator](https://forums.unrealengine.com/t/overthink-studio-pipeline-validator-auto-prep-tool/2745564)
- Outsourcing acceptance: a definition of done names engine, platform and quality tier and how each is verified. A block-out gate locks silhouette, proportion and read. Delivery is accepted only when naming, folder and import tests pass and the asset performs in the build. Health is tracked by first-pass approval rate and revision rounds per asset. **[vendor, fetched]** — [Lemonsky: Game art outsourcing pipeline](https://www.lemonskystudios.com/insights/game-art-outsourcing-pipeline)
- A 3D vendor-brief template advises treating unresolved technical limits as blocking before work starts. **[vendor template]** — [Seeles: 3D asset vendor brief](https://www.seeles.ai/features/tools/3d-asset-vendor-brief-for-outsourced-art-producer)
- A vendor recommends that an art director review each production batch against the style guide to catch drift before it compounds. **[vendor]** — [Nerdbot: 5 things great 2D art services have in common](https://nerdbot.com/2026/08/06/5-things-great-2d-art-services-have-in-common/)

### Inferences
- Treat the AI or procedural author like an outsourcing partner. Give it a brief (references, specs, scope), a definition of done (the measured gates), a block-out gate and a single reviewer decision. Track first-pass approval rate and revision rounds per model as the pipeline's health metric. **[1-2 person: yes]**
- Copy Roblox's split. Hard technical gates are automatic and blocking (scale, bounds, triangle budget, texture size, UVs, naming, pivots, palette membership, albedo range). Style plausibility is a separate review layer, human or AI-reviewer, that cannot be passed by automation alone. Copy also Roblox's "error plus visual guide" pattern: each failed gate should produce an image showing where it failed. **[1-2 person: yes]**
- An offline validator mirroring the engine checks (Roblox's Blender add-on) maps directly to running the Unity-side checks already in Blender before export. **[1-2 person: yes]**

### Gaps
- No public source was found on how Roblox or Epic measure aesthetic consistency of UGC (e.g. style classifiers or curated "featured" standards). The public docs cover only technical and safety rules.
- Fortnite's LEGO/Fab style guides for creators (if any) were not found.

## 5. How AI and procedural pipelines keep generated content on-style (2024-2026)

### Takeaway
In shipped production, "on-style" generation comes from structure, not prompts. Procedural studios (Embark) encode the style in tools that turn grey boxes into final assets with fixed rules and sockets. AI-image studios train custom style models on their own art and anchor generations to references. Every credible source keeps a human or measured review gate. Measured research (2026) shows current text- or image-to-3D output is fast but carries heavy technical debt (dense geometry, broken UVs, hard-to-edit materials) and inconsistent prompt adherence.

### Cited Findings
- Embark (ARC Raiders, THE FINALS) builds its character pipeline on Houdini and USD (PDG and Solaris) to "maximize artistic freedom while minimizing repetitive work". This is the GDC 2026 talk "Freedom Through Structure"; only the description was seen. **[talk desc]** — [SideFX: GDC 2026 Freedom Through Structure, Character Pipelines at Embark](https://www.sidefx.com/learn/talks/gdc-2026-freedom-through-structure-character-pipelines-at-embark/); [GDC Vault entry](https://gdcvault.com/play/1035652/Freedom-Through-Structure-Character-Pipelines)
- Per an NDC 2026 session report, Embark's tools turn simple grey boxes into in-game models. A developer marks areas for damage, cables or vegetation and the tool adds detail through "data sockets" at a button press. About 20 people made ARC Raiders' 3D content. Read via search summary; the page returned 403. **[secondary]** — [Dot Esports: ARC Raiders art creation (NDC 2026)](https://dotesports.com/arc-raiders/news/arc-raiders-art-creation)
- Embark's procedural destructible buildings for THE FINALS aimed at scalable, artist-friendly tools that accelerate environment art. **[primary]** — [SideFX: Making the procedural buildings of THE FINALS](https://www.sidefx.com/community/making-the-procedural-buildings-of-the-finals-using-houdini/)
- Ubisoft La Forge's Generative Base Material prototype was built with material and technical artists. It synthesises a tileable texture from a prompt, then CHORD estimates base colour, normal, roughness and metalness. It is open-weights under a research-only licence, delivered as ComfyUI nodes, and intended for prototyping and placeholder assets; no shipped-title use was found. Community guidance: keep source textures free of baked lighting (AO, highlights, shadows). **[primary]** — [Ubisoft La Forge: Generative Base Material / CHORD](https://www.ubisoft.com/en-us/studio/laforge/news/1i3YOvQX2iArLlScBPqBZs/generative-base-material-an-opensource-prototype-for-pbr-material-estimation-debuting-at-siggraph-asia-2025); [arXiv paper](https://arxiv.org/html/2509.09952v1); [Comfy blog](https://blog.comfy.org/p/ubisoft-open-sources-the-chord-model); [RunComfy workflow notes](https://www.runcomfy.com/comfyui-workflows/chord-model-workflow-in-comfyui-pbr-material-generation) **[secondary]**
- Practice-led study (Begemann & Hutson, Lindenwood, June 2026) **[academic, fetched]** — [Prompted Props, Human Pipelines](https://digitalcommons.lindenwood.edu/faculty-research-papers/813):
  - Setup: the same stylised tavern was built by hand in Blender and with Meshy 6 and Hunyuan 3D.
  - Time: 238 min with AI versus 716 min by hand.
  - Geometry: about 32.8 M triangles with AI versus about 294 K by hand.
  - AI output problems: fragmented UVs, material-editing constraints, clipping, texture loss on decimation, and "inconsistent prompt adherence".
  - Authors' conclusion: AI contributes most to "ideation, rough prop exploration, and early prototyping". Humans remain needed for retopology, UVs, materials, engine validation and art direction.
- Studios train custom style models on their own existing art. Ace Games (Fiona's Farm) trained FLUX-based styles in Layer and claims it set a game's style "in just a week" instead of months. Cosmic Lounge says earlier gen-AI tools lacked the style control they needed. **[vendor case studies]** — [Layer: Ace Games](https://layer.ai/success-stories/ace-games); [Layer: Cosmic Lounge](https://www.layer.ai/case-study/cosmic-lounge)
- Scenario-style custom training typically uses 15-50 reference images per style, and its 3D generation is less mature than dedicated 3D tools. Third-party blog. **[secondary]** — [DataStudios: Scenario custom-trained generation](https://www.datastudios.org/post/scenario-custom-trained-ai-game-asset-generation-style-consistency-and-pricing-explained)
- Every AI image generation "is a fresh interpretation of a text prompt", which is why reference anchoring (concept art as the style anchor) and fixed rules matter. **[vendor]** — [Makko: AI game art generator, consistency is the hard part](https://blog.makko.ai/ai-game-art-generator/)
- Style drift in AI pipelines comes from vague prompts, inconsistent references, switching models, missing negative examples and weak review criteria. The fix: define the style, turn it into repeatable rules, and review against clear criteria. **[vendor]** — [Virtuall: AI game assets that match your art style](https://virtuall.pro/blog/how-to-create-ai-game-assets-that-match-your-art-style)
- A studio trained a style model on hand-painted references to produce matching textures, objects and environments. **[vendor]** — [Morphic: AI asset creation](https://morphic.com/blog/how-ai-is-transforming-game-development-a-closer-look-at-asset-creation)

### Inferences
- The Embark pattern matches the project's approach closely: style lives in code (procedural builders plus sockets and rules), and artists or agents supply only block-out intent. This is the most transferable AAA practice for a code-first Blender pipeline. **[1-2 person: yes]**
- Conditioning methods ranked for this project:
  1. Procedural builders that read style.json and the palette and material registry. Deterministic and cheapest. **[1-2 person: yes]**
  2. Reference anchoring: the reference images and hero-asset renders are included in every generation or review prompt. **[1-2 person: yes]**
  3. Negative examples: the near-miss gallery is passed to the reviewer. **[1-2 person: yes]**
  4. Custom style models such as LoRA. Mostly 2D and texture-oriented, they need 15-50 curated images and add licence and versioning overhead. **[1-2 person: partial]**
  5. Text- or image-to-3D generators (Meshy, Hunyuan, Blender MCP generate_3d). Use for ideation and silhouette exploration only, then rebuild procedurally, per the Lindenwood debt figures. **[1-2 person: partial]**
- Neutral, unlit source textures (CHORD guidance) and albedo-range gates (section 2) protect generated materials from baked-lighting drift.

### Gaps
- No primary source from a large studio quantifies style-consistency rates of AI-generated 3D assets in a shipped game. Vendor productivity claims (Layer "one week", "300+ studios") are self-reported.
- A frequently repeated claim that about 50% of studios have integrated AI into production pipelines appeared only in an unattributed search summary; no primary survey was verified.
- No public source was found describing automated style classifiers (e.g. CLIP-similarity or palette-distance gates) used by a named studio in production. This is a gap in public evidence, not proof that nobody uses them.

## 6. Evolving a style during production without breaking consistency (versioning, re-validating old assets)

### Takeaway
Studios evolve a style by naming a small set of identity invariants that must not change (palette, silhouette, motion and readability), changing everything else, and then running explicit update passes over legacy content: League's texture and visual updates, Overwatch 2's hero reworks. Public sources say little about formal versioning of style guides. "Living style guide under version control plus automated checks" appears only in vendor writing.

### Cited Findings
- Overwatch 2: the team kept Tracer's "color palette, silhouette, and sense of motion" while updating her outfit, shaders and lighting. All art decisions had to serve gameplay ("an unwavering emphasis on gameplay") and storytelling. **[primary, fetched]** — [Blizzard: Overwatch 2 "Evolving the Art" panel recap](https://news.blizzard.com/en-us/article/23189038/2)
- Riot's Senior Art Director posting for VALORANT describes the job as stewarding the game's distinct visual style, "continuing to evolve it to stay fresh whilst remaining rooted in its foundations". **[primary, job ad]** — [Builtin: Senior Art Director, VALORANT](https://builtin.com/job/senior-art-direction-valorant/7631854)
- VALORANT's style ("illustrative visual design", between realism and cel-shading) was chosen so that lighting, characters, weapons and skills stay readable on a wide range of hardware and over a long-running game. **[secondary interview]** — [Inverse: Moby Francke interview](https://inverse.com/gaming/valorant-art-style-interview-moby-francke); [CogConnected on Eurogamer interview](https://cogconnected.com/2020/06/riot-games-talks-developing-valorant-black-licorice-culture/)
- League's Summoner's Rift update targeted a style independent of a particular time or place, aimed at clarifying gameplay. **[secondary repost of Riot blog, 2014]** — [Surrender at 20: Defining Rifts red posts](https://surrenderat20.net/2014/11/red-post-collection-defining-rifts.html)
- League's mass texture update re-touched old champions so that "everything looks consistent". This is an explicit re-validation pass over legacy assets. **[secondary press]** — [PC Gamer: LoL mass texture update](https://www.pcgamer.com/uk/league-of-legends-mass-texture-update-brings-new-hotness-to-old-champions)
- Riot created the VFX style guide after inconsistency had built up across teams, i.e. the guide was introduced mid-life of the game and then applied to new work. **[primary, indirect]** — [Riot Nexus: VFX Style Guide](https://nexus.leagueoflegends.com/en-us/2017/10/dev-leagues-vfx-style-guide/)
- A vendor recommends a living style guide with version control plus automated checks before builds. **[vendor]** — [IXIE Gaming: AI in game art pipelines](https://www.ixiegaming.com/?p=34885)

### Inferences
- A workable versioning scheme for the project (synthesised; no single source describes it) **[1-2 person: yes]**:
  1. Split style.json into **invariants** (palette families, value range, silhouette and proportion rules, readability at game distance) and **tunables** (exact shades, wear amount, outline width).
  2. Give the file a version number, and stamp every asset's build record with the style version it passed.
  3. On a version bump, re-run all measured gates over all assets automatically (cheap, because models are procedural and regenerable). Re-render the lineup and material-ball scenes and diff them against the previous version.
  4. Only assets that fail or visibly change go to human review.
  5. Changing an invariant requires re-approving the hero assets first, as in the Overwatch 2 approach.
- Procedural assets have an advantage that hand-made studio assets lack: a legacy "update pass" (League texture update, OW2 hero reworks) is a re-run, not a re-model. The main cost is review, so batch it into one board image per version change.

### Gaps
- No primary source was found on how a named studio versions its art bible (document version numbers, change logs, approval of style changes) or on formal re-validation criteria for legacy assets.
- Whether Riot retro-fitted old VFX to the 2017 guide, and how, was not confirmed (source page now redirects).
