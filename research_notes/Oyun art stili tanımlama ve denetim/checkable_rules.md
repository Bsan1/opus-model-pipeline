# Turning an art style into machine-checkable rules for 3D game assets (and what still needs human/AI visual review)

Scope note: research notes for a Blender (Python) + Unity pipeline. Numbers come with their source. When a number comes from a forum, a vendor blog or a single practitioner, the note says so. "Inferences" are my own derivations (unit conversions, measurement recipes) and are not sourced claims.

---

## 1. Material rules: PBR albedo ranges, metalness/roughness, stylised vs PBR, colour limits, material libraries

### Takeaway
The most-cited numeric anchors come from Adobe/Allegorithmic's PBR guide. Dielectric albedo should stay between 30-50 sRGB (floor) and 240 sRGB (ceiling). Metal albedo should be 180-255 sRGB (70-100% reflectance). Metallic should be binary 0/1, F0 is 4%, and roughness has no numeric target. Unreal's measured Base Color table agrees with this once its values are read as linear. Stylised projects use the same ranges as a starting point and break them on purpose. No published source gives numeric saturation limits for stylised albedo.

### Cited Findings
**Dielectric albedo (base colour), metal/roughness workflow**
- Dark limit: "you should not go under 30-50 sRGB". The guide calls 30 the tolerant limit and 50 the strict one. No dielectric albedo value should go above 240 sRGB. — [Adobe, The PBR Guide Part 2](https://www.adobe.com/learn/substance-3d-designer/web/the-pbr-guide-part-2)
- Metal reflectance (base colour on metal) is 70-100% specular, which maps to 180-255 sRGB. The guide says these values should come from real-world measured data. — [Adobe PBR Guide Part 2](https://www.adobe.com/learn/substance-3d-designer/web/the-pbr-guide-part-2)
- Metallic map: 0 (0 sRGB) is non-metal and 1 (255 sRGB) is raw metal, and the map is usually binary. Raw metal greyscale is 235-255 sRGB. Grey below 235 sRGB means the metal reflectance in the base colour should be lowered. Transitional greys are allowed for thin dielectric layers such as dirt, with no fixed mapping. — [Adobe PBR Guide Part 2](https://www.adobe.com/learn/substance-3d-designer/web/the-pbr-guide-part-2)
- Dielectric F0 is hardcoded at 4% (0.04) in metal/roughness. specularLevel spans 0.0-0.08 linear and is remapped to 0-1, so 0.5 = 4%. Common dielectrics are 2-5% (0.02-0.05 linear, 40-75 sRGB in the spec/gloss workflow). Gemstones are 0.05-0.17 linear and liquids 0.02-0.04. When IOR is unknown, use 0.04 (plastic). — [Adobe PBR Guide Part 2](https://www.adobe.com/learn/substance-3d-designer/web/the-pbr-guide-part-2)
- Roughness: 0 = smooth, 1 = rough. The guide gives no numeric target and treats roughness as an artistic choice. — [Adobe PBR Guide Part 2](https://www.adobe.com/learn/substance-3d-designer/web/the-pbr-guide-part-2)
- White fringes (metal/rough) or black fringes (spec/gloss) at metal-dielectric transitions depend on texture resolution and texel density. The fix is adequate texel density; no numeric threshold is given. — [Adobe PBR Guide Part 2](https://www.adobe.com/learn/substance-3d-designer/web/the-pbr-guide-part-2)
- Stylised: the guide has no numeric rules for stylised work. It says stylised art is possible in a physically based setup and advises using the guidelines "without being slaves to them". — [Adobe PBR Guide Part 2](https://www.adobe.com/learn/substance-3d-designer/web/the-pbr-guide-part-2)

**Unreal Engine physically based materials**
- Metallic: non-metals 0, metals 1. Pure surfaces use 0 or 1. Hybrids (corroded, dusty or rusty metal) may need values in between. Masks for paint on metal should be black and white, with no intermediate greys. — [Unreal docs, Physically Based Materials](https://dev.epicgames.com/documentation/en-us/unreal-engine/physically-based-materials-in-unreal-engine)
- Specular default is 0.5 (about 4% reflectance). Don't set very diffuse materials to Specular 0; raise Roughness instead. Measured Specular values: glass 0.5, plastic 0.5, quartz 0.570, ice 0.224, water 0.255, milk 0.277, skin 0.35. Use Roughness, not Specular, for surface-variation maps. — [Unreal docs](https://dev.epicgames.com/documentation/en-us/unreal-engine/physically-based-materials-in-unreal-engine)
- Measured Base Color for non-metals: charcoal 0.02, fresh asphalt 0.02, worn asphalt 0.08, bare soil 0.13, green grass 0.21, desert sand 0.36, fresh concrete 0.51, ocean ice 0.56, fresh snow 0.81. — [Unreal docs](https://dev.epicgames.com/documentation/en-us/unreal-engine/physically-based-materials-in-unreal-engine)
- Measured Base Color for metals (RGB): iron 0.560/0.570/0.580, silver 0.972/0.960/0.915, aluminium 0.913/0.921/0.925, gold 1.000/0.766/0.336, copper 0.955/0.637/0.538, chromium 0.550/0.556/0.554, nickel 0.660/0.609/0.526, titanium 0.542/0.497/0.449, cobalt 0.662/0.655/0.634, platinum 0.672/0.637/0.585. The page does not state the colour space. — [Unreal docs](https://dev.epicgames.com/documentation/en-us/unreal-engine/physically-based-materials-in-unreal-engine)
- Cavity maps (AO with a very short trace distance) are multiplied into Base Color and into the 0.5 Specular default. Controlling IOR through Specular is unnecessary for "99% of Materials". — [Unreal docs](https://dev.epicgames.com/documentation/en-us/unreal-engine/physically-based-materials-in-unreal-engine)

**Other published floors and ceilings (they disagree)**
- War Thunder's PBR compliance wiki anchors coal at about RGB 59 and fresh snow at about RGB 236. For any painted surface it says you would not want to go below about 12% brightness (RGB 31). — [War Thunder wiki, PBR texture compliance](https://old-wiki.warthunder.com/PBR_texture_compliance)
- Other practitioner sources in the same search give stricter ranges. One gives 60-240 sRGB for non-metal albedo. Another gives about 80-240, with the darkest albedo "no less than 50-60" and 55-60 preferred as "black". Practitioner advice also says to avoid fully bright, fully dark or fully saturated patches and to keep baked shadows, highlights and AO out of albedo. I could not verify which page in the result set says which; they were among [Polycount comment 2078652](https://polycount.com/discussion/comment/2078652/), [Polycount comment 2078760](https://polycount.com/discussion/comment/2078760), [Shinsoj PBR albedo chart](https://shinsoj.artstation.com/blog/Q9j6/pbr-color-space-conversion-and-albedo-chart), [BlenderKit "material PBR incorrect"](https://www.blenderkit.com/docs/tutorials/most-common-upload-problems/material-pbr-incorrect) and [IRPR glossary](https://3d.irpr.agency/glossary/albedo/). These conflict with Adobe's more tolerant 30 sRGB floor.
- Stylised practice (weak source, an unvetted "skills" page): paint values directly into albedo and keep roughness variation low except for wet or metal accents. — [skills.sh hand-painted style](https://skills.sh/arjun988/blender-skills/hand-painted-style)
- A practitioner view: "Doesn't matter if your game is stylized or not, following PBR workflow will improve your lighting quality". The search summary attributed this to one of the Polycount pages above (not individually verified).

### Inferences
- Unreal's measured table matches Adobe's ranges if it is linear. Converting with the sRGB transfer function: charcoal 0.02 → about 39 sRGB, fresh snow 0.81 → about 232 sRGB, iron 0.56 → about 197 sRGB, titanium's blue channel 0.449 → about 179 sRGB. That puts dielectrics in roughly 39-232 sRGB and metals at about 179-255 sRGB, consistent with Adobe's 30-240 and 180-255. A validator should therefore treat Unreal's table as linear.
- Checkable material rules for the pipeline (measure in Blender by reading the image pixels or the Principled BSDF inputs; in Unity, read the texture in an AssetPostprocessor):
  1. Dielectric albedo: the 1st and 99th percentile of pixel luminance (sRGB) should fall inside [30 or 50, 240]. Use percentiles, not min/max, so a few dark seam pixels don't fail the asset.
  2. Metal albedo: where metallic ≥ 0.5, the luminance percentile should be ≥ 180 sRGB.
  3. Metallic map: the share of pixels outside {0, 1} (for example 0.1 < m < 0.9) should be below a small threshold, such as 2-5% for transition zones. This threshold is my suggestion, not a sourced number.
  4. Unity Standard/URP Lit has no Specular 0.5 parameter, so the F0 = 4% default holds automatically. Only check that the "specular" override is unused or at its default.
  5. Roughness gets no physical range check. For a style, check the histogram against the style's own allowed band, for example "stylised: one roughness band per material class".
- Stylised games need a style-specific palette rule rather than the PBR ranges: an allowed HSV/OKLCH range per material class plus a saturation cap. These numbers must come from the project's reference measurements (the project already has tools/Style.py for that); no external source supplies them.
- A "material library" constraint can be checked as "every material slot name or shader parameter set must match an entry in a registry" (the project's MATERIALS registry). This is a set-membership check, not a numeric one.

### Gaps
- I found no published numeric saturation or chroma limits for stylised or hand-painted albedo. Studios presumably set these per project.
- I did not fetch or verify Substance Painter's "PBR Validate" filter thresholds.
- I did not fetch Sébastien Lagarde's (DONTNOD) PBR chart or other measured-albedo charts, which are usually treated as primary.
- I found no source for Unity-specific albedo guidance (Unity's own "PBR material validator" scene-view mode exists, but I did not verify its thresholds in this session).

---

## 2. Geometry rules: bevels, edge sharpness, triangle budgets, density vs silhouette, minimum feature size, silhouette tests, proportions

### Takeaway
Hard platform limits exist (Roblox rigid accessory: 1 mesh, ≤ 4,000 triangles), but general triangle budgets per asset class are only rules of thumb, and published figures disagree widely. Bevel size has no published numeric rule. Practitioner consensus: bevel edges that show in the silhouette, use a few standard sizes, and exaggerate them because small bevels shrink to a few pixels when mipped. Minimum feature size and triangle density are best derived from the projected size on screen at the game camera. The documented GPU concern is triangles smaller than a 2x2 pixel quad; a forum claim puts the slow zone below about 8x8 pixels.

### Cited Findings
**Platform hard limits**
- Roblox rigid accessories: 1 mesh, ≤ 4,000 triangles, quads preferred, no faces with 5+ sides, textures ≤ 2048×2048 (larger ones are auto-downscaled), ≥ 1 attachment. Maximum bounding boxes are defined per asset type and body scale, e.g. a Normal-scale Hat is 1.87 × 2.5 × 1.87 studs and a Back accessory 9.86 × 8.59 × 4.87 studs. — [Roblox Creator Docs, Accessory specifications](https://create.roblox.com/docs/art/accessories/specifications)
- Meta Horizon Worlds custom models: export as a single FBX, UV-unwrap first, name textures `MaterialName_BR.png` (the `_BR` suffix matters). — [Meta Horizon import video page](https://developers.meta.com/horizon-worlds/learn/videos/importing-custom-models/); naming rule via [Meta community forum](https://communityforums.atmeta.com/discussions/Creator_Discussion/help-with-blender-and-horizon-needed/1338497). I did not find triangle limits.

**Triangle budgets per asset class (rules of thumb that disagree)**
- Third-party guides: mobile background props 100-800 tris. Other guides give PC/console small props 2K-10K and mobile small props 300-2K. Mobile hero characters range from under 5K to 15K-30K depending on the guide, and console hero characters from 20K-40K (body) to 50K-100K+. — [Neural4D polygon count guide](https://blog.neural4d.com/user-guide/polygon-count-for-3d-game-assets/), [Tripo3D poly count guide](https://www.tripo3d.ai/blog/poly-count-for-game-assets-how-to-prepare-ai-3d-models). Both are vendor blogs and weak sources.
- A shipped-game reference: HUNT: Showdown main characters at LOD0 use 35,000-70,000 triangles, according to CryEngine's character-budget documentation as summarised by search; I did not fetch the page. — [CryEngine docs, Character Budgets](https://cryengine.com/docs/static/engines/cryengine-5/categories/23756816/pages/23307976)
- Method advice: set the triangle budget at scene level, then split it by asset importance and viewing distance. Shaders, textures and draw calls can matter more than geometry. — [Neural4D](https://blog.neural4d.com/user-guide/polygon-count-for-3d-game-assets/) (weak source)

**Small and thin triangles (density vs screen size)**
- GPUs shade in 2x2 pixel quads. If even one sample hits a triangle, the whole quad is shaded, so small triangles cause "overshading". — [Self Shadow, Overdraw in Overdrive](https://blog.selfshadow.com/publications/overdraw-in-overdrive/)
- A forum claim says rasterising tiny triangles (below about 8x8 pixels) is "catastrophically slow" on modern hardware. No benchmark is given. — [gamedev.net, LOD in modern games](https://gamedev.net/topic/660929-lod-in-modern-games)
- Long thin triangles hurt both quad usage and rasterisation patterns, but subdividing to fix them can add edges and vertex cost. — [Polycount comment](https://polycount.com/discussion/comment/2528967); [Unity forum, thin triangles](https://discussions.unity.com/t/thin-triangles-gpu-performance-issue/682664)
- I found no vendor (NVIDIA, AMD, Epic) document with exact quad-efficiency thresholds; profiling is the reliable route. — same search; see Gaps.

**Bevels and edge sharpness**
- Practitioners bevel edges that are noticeable in the silhouette and leave hidden edges hard. Small bevels "might not show up at all unless exaggerated", and sharper bevels "only take up a few pixels when mipped". The advice is to standardise on a few bevel sizes (small, medium, large, or exact reusable values) and to exaggerate details on flat surfaces. Some artists find chamfer + weighted normals faster than baking and nearly identical in look. — Polycount threads (search cluster; individual comment attribution not verified): [comment 2577213](https://polycount.com/discussion/comment/2577213), [comment 2577181](https://polycount.com/discussion/comment/2577181), [comment 2425413](https://polycount.com/discussion/comment/2425413), [comment 2629643](https://polycount.com/discussion/comment/2629643)
- A hard-surface guide (not game-specific) says 2-3 bevel segments are usually enough. Tiny bevels still shape the edge's response to light, and the bevel should be tested under a strong key light. — [Novedge, Cinema 4D beveling tip](https://novedge.com/blogs/design-news/cinema-4d-tip-beveling-best-practices-for-realistic-hard-surface-modeling)

**Silhouette readability tests**
- Black-fill test: fill the character fully black with no interior lines or textures, view it at the smallest size it will appear in game, and ask someone unfamiliar with it what it reads as. Mark where limbs merge into the torso or props vanish. — [itechguides](https://www.itechguides.com/what-makes-a-fictional-character-design-visually-appealing/) (weak, general-audience source)
- "Three-read rule": silhouette at about 32 px (icon scale), colour blocking at about 64 px (squint distance), then detail only if it strengthens the first two reads. This comes from one weak source and should be treated as a rule of thumb. — [skillselion character-design skill](https://skillselion.com/skills/omer-metin/skills-for-antigravity/character-design)
- Disney's silhouette activity sheet: each part (body, hair, clothes) should be separately identifiable, because overlapping shapes merge into a blob. — [Walt Disney Family Museum, Silhouette PDF](https://www.waltdisney.org/sites/default/files/2020-05/T%26T_Silhouette-final2.pdf)
- Different characters should have distinct silhouettes, while the same character in different poses should keep a similar one. — [Lemma Soft forum resource](https://lemmasoft.renai.us/forums/viewtopic.php?p=536569)
- I found no academic validation of the black-fill test. It is a practitioner heuristic. — same search

### Inferences
- **Minimum feature size from the game camera.** On-screen size in pixels ≈ feature_size × screen_height_px / (2 × distance × tan(vFOV/2)). Example: 1080p, 60° vFOV, 10 m away gives about 93.5 px per metre, so a 2 cm bevel is about 1.9 px, below the 2x2 quad and effectively invisible. To read, a bevel probably needs about 3-4 px at the typical camera distance, which in this example is about 3-4 cm. The 3-4 px target is my inference from the "few pixels when mipped" remark and the 2x2 quad mechanism, not a sourced number.
- **A relative bevel rule is checkable.** Bevel width / object bounding-box diagonal (or smallest bbox dimension) inside a style band. The band has to be measured from the style reference. In Blender: detect bevel faces as narrow face strips between faces at a dihedral angle of about 90° (or read the Bevel modifier width before applying). Report edges with dihedral angle > ~60-80° and no bevel strip as "razor edges", but only for edges that lie on the silhouette from the game camera. Thresholds are mine.
- **Silhouette test can be automated as rendering plus a numeric proxy.** Render a flat black mask at the target pixel height (for example 32, 64 px and the real game-camera size) from 8 yaw angles. Then compute: (a) coverage and convexity (mask area / convex-hull area), (b) count of disconnected parts and "holes" that vanish at small size, (c) IoU against the previous asset version or the reference object's mask, (d) distance between masks of different asset classes (distinctness). These are proxies; the judgement of whether a shape "reads" stays with human or AI review.
- **Triangle density vs silhouette.** A checkable proxy is "triangles per projected screen pixel at the expected screen size". Average projected triangle area should stay above about 4 px² (one 2x2 quad), and more conservatively around the forum's 8x8 = 64 px² for LOD0 at the typical distance. Beyond that, add LODs. Also check the triangle aspect ratio (long/short edge) to flag sliver triangles. All thresholds are inferences.
- **Proportion and exaggeration rules** are checkable only as ratios measured against the reference (for example head:body height ratio, wall thickness / opening width, handle diameter / hand size). An external source cannot supply them; they come from the style's own reference measurements.

### Gaps
- No published numeric bevel-size-to-object-size rule was found, in either stylised or realistic guidance.
- I did not find Polycount wiki budget pages, or Unity/Unreal official LOD screen-size defaults (Unity LODGroup transition heights, Unreal "Auto LOD screen size") within the tool budget.
- No authoritative GPU vendor threshold for "minimum triangle size" was found; the 8x8 px figure comes only from a forum.
- Meta Horizon Worlds triangle limits, Fortnite UEFN and Sketchfab numeric limits were not found or not fetched.
- I found no GDC talk describing numeric silhouette or shape-language metrics.

---

## 3. Texture rules: texel density per asset class, mip/resolution rules, texture frequency/detail checks

### Takeaway
The de facto texel density reference values are 10.24 px/cm (1024 px/m) for first-person or hero assets, 5.12 px/cm (512 px/m) for third-person or background props, and 2.56 px/cm (256 px/m) or lower for top-down. Each project sets its own target early. Power-of-two textures are a common validator warning (glTF Validator). Platform maximums exist (Roblox 2048²). I found no published numeric standard for texture "frequency" or detail level.

### Cited Findings
- Maxon's texel density docs give example densities by camera type: first person 10.24, third person 5.12, top-down 2.56 or lower, labelled px/cm. The closer the camera, the higher the density should be. — [Maxon Cinema 4D help, Texel Density](https://help.maxon.net/c4d/2027/en-us/Content/html/Texel_Density.html.md)
- Polycount users (informal): 512 px/m is "fairly typical" for third-person games, especially on console; first person is probably closer to 1024 px/m. — [Polycount comment 2707204](https://polycount.com/discussion/comment/2707204), [Polycount comment 2709190](https://polycount.com/discussion/comment/2709190) (forum, informal; exact comment attribution not verified)
- Studios set a texel density guideline early in production for consistency. Example: 5.12 px/cm for background props, 10.24 px/cm for hero assets. — [RebusFarm blog, Texel Density Basics](https://rebusfarm.net/blog/texel-density-basics-every-artist-should-know)
- Insufficient texel density causes visible white or black fringes at metal/dielectric transitions in PBR maps. — [Adobe PBR Guide Part 2](https://www.adobe.com/learn/substance-3d-designer/web/the-pbr-guide-part-2)
- glTF Validator warns on non-power-of-two image dimensions and on unsupported image features (animations, custom colour spaces). — [KhronosGroup/glTF-Validator](https://github.com/KhronosGroup/glTF-Validator)
- Roblox marketplace accessories: texture ≤ 2048×2048; larger textures are auto-downscaled. — [Roblox accessory specifications](https://create.roblox.com/docs/art/accessories/specifications)
- Blender add-ons that check texel density range or consistency include uGame (open source), Export Checker, Model Inspector, AI Mesh Inspector and InspectOps. These are product listings I did not verify. — [uGame on GitHub](https://github.com/abcg-code/uGame), [Export Checker](https://superhivemarket.com/products/export-checker), [Model Inspector](https://superhivemarket.com/products/model-inspector)
- Small bevel detail "only takes up a few pixels when mipped". In other words, mip levels erase small detail at distance. — [Polycount thread](https://polycount.com/discussion/comment/2577213) (attribution not verified)

### Inferences
- **Measuring texel density per face in Blender.** TD(face) = sqrt(UV_area × tex_w × tex_h) / sqrt(world_area), in px/m. Report the area-weighted mean, the 5th and 95th percentile, and the share of faces outside ±(15-25)% of the target. Allowed spread: stylised hand-painted projects usually want stricter uniformity, because painted brush strokes reveal density changes. That is my inference; no numeric source was found.
- **Resolution rule derived from texel density.** Required texture size ≈ TD_target × sqrt(total world surface area / UV packing efficiency), rounded up to a power of two and capped by the platform maximum. Example: 512 px/m on a 2 m² prop at 70% packing gives sqrt(2 / 0.7) × 512 ≈ 865 px, so 1024².
- **Texture frequency and detail check (proxy).** Render or sample the albedo at the mip level the game camera actually uses: mip ≈ log2(texels per screen pixel) from the distance formula in section 2. Then compare the high-frequency energy (Laplacian variance or FFT high-band ratio) against the style reference at the same mip. Hand-painted styles typically have low high-frequency energy and large value shapes; photoreal styles have high-frequency noise. Both thresholds would be measured from the reference, not taken from literature.
- A glTF export run through the Khronos validator gives free checks for power-of-two size, accessor validity and similar structural issues. The pipeline could run it after Blender export.

### Gaps
- I did not fetch the 80.lv or Leonardo Iezzi texel-density articles, or any Unreal art guideline document with texel targets.
- I found no published numeric standard for texture "frequency" or detail level per style.
- Unity's mip-streaming and texture-size guidance was not researched within the tool budget.

---

## 4. Validation tooling: Unity, Unreal, Blender, glTF, Substance, studio asset checkers

### Takeaway
Each engine has a hook for automated checks. Unity uses AssetPostprocessor callbacks at import, versioned with GetVersion. Unreal uses the Data Validation plugin with UEditorValidatorBase, which runs on save, from menus, or in CI via `-run=DataValidation`. glTF has the Khronos validator, which writes a JSON report and exits non-zero on errors. Blender has several third-party add-ons, with uGame as the open-source option. I did not find GDC-documented studio "asset checkers" with concrete thresholds in this session.

### Cited Findings
**Unreal Data Validation**
- The built-in Data Validation plugin is enabled by default. Validators derive from `UEditorValidatorBase`. `CanValidateAsset` decides whether a validator applies to a `UObject`. `ValidateLoadedAsset` does the check and must call `AssetPasses` or `AssetFails` on every path. A custom UObject can instead override `IsDataValid`. — [Unreal docs, Data Validation](https://dev.epicgames.com/documentation/en-us/unreal-engine/data-validation-in-unreal-engine)
- It runs on asset save (on by default); from the Asset Actions menu (Validate Assets, Validate Assets and Dependencies, Validate Assets in Folder); from Tools > Validate Data...; and in CI with the commandlet `-run=DataValidation`. Failures go to the Message Log, or to the console in CI. — [Unreal docs](https://dev.epicgames.com/documentation/en-us/unreal-engine/data-validation-in-unreal-engine)
- C++ rules run by default. Blueprint validators are auto-discovered at editor start, though auto-registration is disabled in Fortnite for performance. Python validators register through `UEditorValidatorSubsystem.AddValidator`. Documented example checks: naming conventions, space and performance budgets, non-cyclic dependencies. — [Unreal docs](https://dev.epicgames.com/documentation/en-us/unreal-engine/data-validation-in-unreal-engine)

**Unity AssetPostprocessor**
- Model callbacks in import order: `OnPreprocessModel` (override ModelImporter settings), `OnPreprocessMaterialDescription`, `OnPostprocessMeshHierarchy`, `OnAssignMaterialModel`, `OnPostprocessGameObjectWithUserProperties`, `OnPostprocessMaterial`, `OnPostprocessModel` (root GameObject after the Avatar is generated). — [Unity Scripting API, AssetPostprocessor](https://docs.unity3d.com/ScriptReference/AssetPostprocessor.html)
- Texture callbacks: `OnPreprocessTexture` (before the importer runs) and `OnPostprocessTexture` (on the Texture2D just before compression), plus variants for Texture2DArray, Texture3D, cubemaps and sprites. `OnPreprocessAsset` runs before any import, `OnPostprocessPrefab` after prefab import, and `OnPostprocessAllAssets` after a batch. — [Unity Scripting API](https://docs.unity3d.com/ScriptReference/AssetPostprocessor.html)
- `GetPostprocessOrder` sets execution priority. `GetVersion` must be incremented whenever the postprocessor's output or dependencies change, which triggers reimport. — [Unity Scripting API](https://docs.unity3d.com/ScriptReference/AssetPostprocessor.html)

**Khronos glTF Validator**
- It checks JSON/GLB container validity; schema property names, types and limits; internal references; Data URI encoding; binary buffers (NaN, invalid quaternions, indecomposable matrices, accessor min/max, sparse encoding, animation I/O); images (non-power-of-two warning, unsupported features); and about 20 extensions (KHR_materials_*, KHR_texture_transform, KHR_mesh_quantization, and others). — [KhronosGroup/glTF-Validator](https://github.com/KhronosGroup/glTF-Validator)
- Its output is a JSON report listing all issues plus asset statistics, written to `<asset>.report.json` by default. The CLI is `gltf_validator [options] <input>` (a directory input is validated recursively). The exit code is non-zero if any error is found, and a YAML config (`-c`) sets validation options. It is also on npm as `gltf-validator`. The full issue list is in ISSUES.md. — [KhronosGroup/glTF-Validator](https://github.com/KhronosGroup/glTF-Validator)

**Blender asset checkers (not verified beyond listings)**
- uGame (open source): non-manifold edges, flipped normals, stray vertices, n-gons, texel density, unwrap quality, texture and rig checks, a game-readiness summary. — [github.com/abcg-code/uGame](https://github.com/abcg-code/uGame)
- Export Checker (paid): profiles for Generic Game Asset, Unreal and Unity. It flags non-planar n-gons, loose and degenerate faces, flipped normals and texel-density range, and sorts fixes into safe, confirm and manual. — [Superhive, Export Checker](https://superhivemarket.com/products/export-checker)
- Model Inspector, AI Mesh Inspector, Skava Game Asset Validator Pro and InspectOps (paid) offer similar mesh and UV checks. — [Model Inspector](https://superhivemarket.com/products/model-inspector), [AI Mesh Inspector](https://superhivemarket.com/products/mesh-inspector), [Skava](https://superhivemarket.com/products/skava-game-asset-validator-pro), [InspectOps](https://superhivemarket.com/products/inspectops)

### Inferences
- The Unreal Data Validation model maps cleanly onto the project's own pipeline: a rule registry where each rule has an "applies to" predicate (CanValidateAsset) and a pass/fail result with a message (ValidateLoadedAsset). Run it on save or export and in batch for CI. A Unity equivalent: an AssetPostprocessor reads meshes and textures at import and writes failures to a report. Bump GetVersion whenever rules change so every asset re-validates.
- Split the work. Blender (Python) checks things that are cheapest on the source: topology, bevels, texel density, material registry, albedo percentiles. Unity checks things that only exist after import: final texture compression and size, material/shader assignment, rendering at the real game camera for silhouette and close shots. glTF Validator is an optional structural gate if glTF is used as an interchange format.
- Rules should have three severities (error, warning, info) and a per-asset "waiver" with a written reason, mirroring the safe/confirm/manual split seen in Export Checker.

### Gaps
- I found no GDC or tech-art talk transcript in this session describing a specific studio asset checker with numeric thresholds.
- Substance Painter's "PBR Validate" filter and Substance's PBR-safe/strict thresholds were not verified.
- Unity's own Project Auditor package and the URP "Material Validator" debug view were not researched.

---

## 5. Style aspects that numbers cannot check, and how teams handle them (art review, turntables, AI/VLM review, reliability)

### Takeaway
Appeal, shape language, readability and "does this belong in our world" are judged visually. The common practitioner tools are the black-fill silhouette test at the real display size, colour-block or "squint" reads, and reference comparison. VLM judges can help but are unreliable without task-specific training. Zero-shot GPT-4V pairwise comparison was reported as human-aligned for text-to-3D (CVPR 2024). A CVPR 2025 study measured GPT-4o's pairwise agreement with humans at only about 0.48-0.69 across criteria (0.5 = chance), against 0.67-0.99 for a fine-tuned model. Treat a general VLM as an advisory second opinion on rendered views, not as a gate.

### Cited Findings
- **GPT-4V as evaluator (Wu et al., CVPR 2024).** GPT-4V generates evaluation prompts and compares two text-to-3D outputs pairwise under user-defined criteria. The results are aggregated into Elo ratings, and the authors report alignment with human preference across criteria. The motivation is that user studies are expensive to scale. — [CVPR 2024 paper page](https://openaccess.thecvf.com/content/CVPR2024/html/Wu_GPT-4Vision_is_a_Human-Aligned_Evaluator_for_Text-to-3D_Generation_CVPR_2024_paper.html), [arXiv/HF 2401.04092](https://huggingface.co/papers/2401.04092)
- **Gen3DEval (Maiti et al., CVPR 2025).** General VLMs "do not perform well on evaluating generated 3D objects", and GPT-4V is "not specifically trained for 3D quality assessment". GPT-4o's pairwise accuracy against human judgments was 0.59, 0.48, 0.69, 0.54, 0.54, 0.61 and 0.55 across the paper's criteria, versus 0.9, 0.85, 0.89, 0.99, 0.67, 0.98 and 0.86 for the fine-tuned Gen3DEval. The extracted table's column labels were garbled, so the mapping of values to criteria is unverified. Open VLMs (Phi-3.5-Vision about 0.47-0.65, LLaVA-Llama3-8B near 0.5) were near chance, and some (Llama3.2-Vision-11B, PaliGemma) as low as 0.02-0.06. — [arXiv 2504.08125](https://arxiv.org/html/2504.08125v1), [CVPR 2025 PDF](https://openaccess.thecvf.com/content/CVPR2025/papers/Maiti_Gen3DEval_Using_vLLMs_for_Automatic_Evaluation_of_Generated_3D_Objects_CVPR_2025_paper.pdf)
- Gen3DEval's inputs: up to 8 images, 4 per object, using RGB and surface-normal renders sampled from a 360° turntable video. GPT-4o received 8 images in sequence; models without multi-image support got a 4x2 grid. — [arXiv 2504.08125](https://arxiv.org/html/2504.08125v1)
- Known limits: GPT-4V-style judges are costly at scale. Human labels are themselves noisy: appearance sways text-fidelity judgments, and background or scale sways appearance judgments. Gen3DEval's own Janus (multi-face) assessments are "slightly erratic", and its out-of-domain surface evaluation is weaker. — [arXiv 2504.08125](https://arxiv.org/html/2504.08125v1)
- These contradict each other in degree. Wu et al. (2024) report zero-shot GPT-4V pairwise judging as human-aligned, while Maiti et al. (2025) report its successor GPT-4o performing "significantly worse" than a fine-tuned judge, near chance on some criteria. — [Wu et al.](https://openaccess.thecvf.com/content/CVPR2024/html/Wu_GPT-4Vision_is_a_Human-Aligned_Evaluator_for_Text-to-3D_Generation_CVPR_2024_paper.html); contradicted by [Maiti et al.](https://arxiv.org/html/2504.08125v1)
- Human review practices: the black-fill silhouette test at the smallest in-game size, shown to someone unfamiliar with the design — [itechguides](https://www.itechguides.com/what-makes-a-fictional-character-design-visually-appealing/). Reads at about 32 px (silhouette) and about 64 px (colour blocking) — [skillselion](https://skillselion.com/skills/omer-metin/skills-for-antigravity/character-design) (weak). Each part separately identifiable, no blob merging — [Disney silhouette PDF](https://www.waltdisney.org/sites/default/files/2020-05/T%26T_Silhouette-final2.pdf). Test bevels and edges under a strong key light — [Novedge](https://novedge.com/blogs/design-news/cinema-4d-tip-beveling-best-practices-for-realistic-hard-surface-modeling).
- Roughness itself is described as an "artistic choice" with no numeric target. That makes even part of material correctness a matter of visual judgement. — [Adobe PBR Guide Part 2](https://www.adobe.com/learn/substance-3d-designer/web/the-pbr-guide-part-2)

### Inferences
- **What numbers can check:** albedo, metal and roughness ranges; palette membership; texel density; triangle count and density; bevel presence and relative size; bbox scale against real-world size; silhouette mask metrics; detail frequency at the game mip.
- **What needs eyes:** appeal; shape language (round = friendly, angular = threat, and so on); whether exaggeration feels consistent with the rest of the set; whether the asset reads as its function; whether wear and painting match the style's brushwork; whether it "belongs" next to approved assets.
- **A practical review protocol that follows from the evidence:**
  1. Always render a fixed "review board": an 8-view turntable with RGB plus a normal or clay pass (the Gen3DEval input design), a black silhouette at the real game-camera pixel size, and a side-by-side with 2-3 approved style-reference assets under the same lighting.
  2. Use a VLM pairwise, not as an absolute score: "which of A/B fits the reference set better on criterion X". That is the setup Wu et al. found human-aligned. Because Maiti et al. measured general-VLM agreement near chance on some criteria, treat VLM output as advisory, require concrete, verifiable reasons (for example "edge at X is razor-sharp"), and have every claim it makes re-checked by a numeric gate or a human.
  3. Randomise A/B order and ask twice to detect position bias or inconsistency. This is my suggestion; the fetched sources did not quantify VLM position bias.
  4. Keep humans as the final gate for appeal and shape language, and turn every defect found by eye into a new numeric gate where possible (consistent with the project's existing quality-control rule).

### Gaps
- No source quantified VLM judges specifically on *style consistency* (as opposed to text-to-3D quality), or on stylised game assets.
- VLM failure modes such as position bias, verbosity bias and sensitivity to lighting or background were not quantified in the fetched sources.
- I found no GDC talk on studio art-review practice (turntable reviews, paint-overs, style bibles) within the tool budget. Overwatch, Fortnite and Sea of Thieves style talks were not fetched.
