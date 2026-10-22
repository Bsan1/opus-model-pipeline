using System.Collections.Generic;
using Opus.Visual;
using UnityEngine;

namespace Opus.World
{
    /// <summary>
    /// Material catalogue: for every <see cref="SurfaceKind"/>, which painted pattern, repeating every how many metres, how much grime.
    /// <see cref="PrimitiveKit.MaterialFor(Surface)"/> builds the "Opus/Surface" material from this table.
    /// </summary>
    public static class SurfaceLibrary
    {
        public const string ShaderName = "Opus/Surface";

        public readonly struct Look
        {
            public readonly string Texture;
            /// <summary>How many metres one repeat of the pattern covers.</summary>
            public readonly float Tile;
            public readonly float Strength;
            public readonly bool SlopeAligned;
            public readonly float Grime;
            public readonly float GrimeHeight;
            public readonly float Tone;
            public readonly float Ao;
            public readonly float Wrap;

            public Look(string texture, float tile, float grime, float grimeHeight = 0.9f, float tone = 0.08f, float strength = 1f,
                bool slopeAligned = false, float ao = 1f, float wrap = 0.45f)
            {
                Texture = texture;
                Tile = tile;
                Strength = strength;
                SlopeAligned = slopeAligned;
                Grime = grime;
                GrimeHeight = grimeHeight;
                Tone = tone;
                Ao = ao;
                Wrap = wrap;
            }
        }

        static readonly Dictionary<SurfaceKind, Look> Looks = new Dictionary<SurfaceKind, Look>
        {
            [SurfaceKind.Paint] = new Look("paint", 1.2f, 0.45f),
            // 8 boards / repeat: 16 cm shed boards (28 cm on the house at 1.75 scale)
            [SurfaceKind.Siding] = new Look("siding", 1.28f, 0.9f, 1.2f, 0.07f),
            // 6 boards / repeat: 15 cm
            [SurfaceKind.Planks] = new Look("wood", 0.9f, 0.8f, 1.1f),
            [SurfaceKind.Vinyl] = new Look("vinyl", 2f, 0.35f, 0.75f, 0.05f),
            // 8 rows / repeat: 20 cm
            [SurfaceKind.Shingles] = new Look("shingles", 1.6f, 0f, tone: 0.1f, slopeAligned: true),
            // 12 rows / repeat: 7.5 cm
            [SurfaceKind.Brick] = new Look("brick", 0.9f, 0.3f),
            [SurfaceKind.Concrete] = new Look("concrete", 1.2f, 0.5f, 0.5f, 0.1f),
            [SurfaceKind.Stone] = new Look("stone", 0.7f, 0.4f, 0.5f, 0.1f),
            [SurfaceKind.Bark] = new Look("bark", 1.3f, 0.3f, 0.6f),
            [SurfaceKind.Soil] = new Look("soil", 0.6f, 0f, tone: 0.1f, ao: 0.5f),
            [SurfaceKind.Rubber] = new Look("rubber", 0.25f, 0f, tone: 0.03f),
            [SurfaceKind.Metal] = new Look("metal", 0.5f, 0.25f, 0.4f, 0.05f),
            [SurfaceKind.Plastic] = new Look("plastic", 0.5f, 0.2f, 0.35f, 0.04f),
            [SurfaceKind.Foliage] = new Look("leaf", 0.8f, 0f, tone: 0.1f, strength: 0.85f, wrap: 0.6f),
            [SurfaceKind.Fabric] = new Look("fabric", 0.25f, 0.1f, 0.4f, 0.03f),
            [SurfaceKind.Glass] = new Look("glass", 1f, 0f, tone: 0.04f, ao: 0f),
            [SurfaceKind.Ground] = new Look("paint", 4f, 0f, tone: 0.12f, ao: 0f),
            [SurfaceKind.Prop] = new Look("plastic", 0.3f, 0f, tone: 0.03f, ao: 0f),
            [SurfaceKind.Plant] = new Look("paint", 0.5f, 0f, tone: 0.1f, ao: 0.5f, wrap: 0.6f),
        };

        /// <summary>
        /// Hard-surface finish of the Blender models (separate from the soft painted light of the garden props): the shadow side drops to a
        /// dark neutral, painted metal and plastic shine and reflect the sky at the edges, the pattern is light, no grime (the mower
        /// is clean); recesses are darkened by the AO baked in Blender. Reference: the mower in the video.
        /// </summary>
        public readonly struct Finish
        {
            public readonly float Gloss;
            public readonly float SpecPower;
            public readonly float Reflect;
            public readonly float ShadeDepth;
            public readonly float Strength;

            public Finish(float gloss, float specPower, float reflect, float shadeDepth, float strength)
            {
                Gloss = gloss;
                SpecPower = specPower;
                Reflect = reflect;
                ShadeDepth = shadeDepth;
                Strength = strength;
            }
        }

        /// <summary>
        /// Surface finishes. Not derived from the kind: every material slot carries in its name the finish chosen in Blender from the part's
        /// real material and its look in the video ("Plastic_2F2E31_matte"; the names match FINISHES in tools/blender/opus_model.py).
        /// The same kind can have different finishes: a black plastic cap is matte, red painted sheet metal glossy, a painted steel handle satin.
        /// </summary>
        static readonly Dictionary<string, Finish> ModelFinishes = new Dictionary<string, Finish>
        {
            ["glossy"] = new Finish(0.55f, 40f, 0.2f, 0.85f, 0.3f),    // baked paint, polished sheet metal
            ["metallic"] = new Finish(0.8f, 70f, 0.45f, 0.85f, 0.15f),  // chrome, galvanised
            ["satin"] = new Finish(0.14f, 14f, 0.06f, 0.85f, 0.35f),   // electrostatic paint, painted casting
            ["matte"] = new Finish(0f, 8f, 0f, 0.85f, 0.45f),            // textured plastic, rubber, foam
        };

        public static IEnumerable<string> FinishNames => ModelFinishes.Keys;

        public static bool TryGetFinish(string name, out Finish finish) =>
            ModelFinishes.TryGetValue(name ?? "", out finish);

        /// <summary>A new material for a Blender model (cached in ModelLibrary).</summary>
        public static Material CreateModel(Surface surface, string finishName)
        {
            if (!TryGetFinish(finishName, out Finish finish))
                throw new System.ArgumentException($"Unknown surface finish '{finishName}'", nameof(finishName));
            Material material = Create(surface);
            material.name = $"OpusModel_{surface}_{finishName}";
            Look look = LookOf(surface.Kind);
            bool natural = IsNaturalTexture(surface.Kind);
            bool foliage = surface.Kind == SurfaceKind.Foliage;
            // Only concrete, brick and stone get grime at the base; painted wood (the shed and house in the video), the mower, tools and plants stay clean
            material.SetFloat("_Grime", IsWeathering(surface.Kind) ? look.Grime : 0f);
            material.SetFloat("_AO", 0.3f);
            material.SetFloat("_Tone", natural || foliage ? look.Tone : 0.02f);
            // Leaves take light softly (light passes through them); their shadows are not as dark as hard surfaces
            material.SetFloat("_Wrap", foliage ? look.Wrap : 0.25f);
            // On natural surfaces such as bark, wood and fabric the painted pattern is the surface itself: full strength
            material.SetFloat("_Strength", natural ? look.Strength : finish.Strength);
            material.SetFloat("_ShadeDepth", foliage ? 0.45f : finish.ShadeDepth);
            material.SetFloat("_Gloss", finish.Gloss);
            material.SetFloat("_SpecPower", finish.SpecPower);
            material.SetFloat("_Reflect", finish.Reflect);
            // On the model the boards and shingle rows are real geometry: they must not be drawn a second time in the texture. Siding gets paint
            // brush marks, shingles granular asphalt (the concrete pattern).
            if (ModelTextures.TryGetValue(surface.Kind, out (string texture, float tile, float strength) model))
            {
                material.SetTexture("_BaseMap", SurfaceTextures.Get(model.texture));
                material.SetFloat("_Tile", model.tile * surface.Scale);
                material.SetFloat("_Strength", model.strength);
            }
            material.SetFloat("_VertexAO", 1f);
            material.EnableKeyword("_OPUS_HARD");
            return material;
        }

        /// <summary>
        /// Textured Blender model: hard-surface lighting + UV-mapped atlas textures (colour, normal, AO/roughness/metallic).
        /// No pattern, grime, tone or vertex AO; all of it is baked into the textures in Blender. Shine comes from the roughness map.
        /// </summary>
        public static Material CreateAtlas(string model, Texture2D color, Texture2D normal, Texture2D orm)
        {
            Material material = Create(new Surface(SurfaceKind.Prop, Color.white));
            material.name = "OpusAtlas_" + model;
            material.SetTexture("_BaseMap", color);
            material.SetTexture("_BumpMap", normal);
            material.SetTexture("_OrmMap", orm);
            material.SetColor("_BaseColor", Color.white);
            material.SetFloat("_Grime", 0f);
            material.SetFloat("_Tone", 0f);
            material.SetFloat("_AO", 0.3f);
            material.SetFloat("_Wrap", 0.25f);
            material.SetFloat("_ShadeDepth", 0.85f);
            material.SetFloat("_VertexAO", 0f);
            material.EnableKeyword("_OPUS_HARD");
            material.EnableKeyword("_OPUS_UVMAP");
            return material;
        }

        /// <summary>
        /// A building model's material (the mesh has UVs in metres along each piece's grain): the model material of
        /// <see cref="CreateModel"/> + a tiling tone texture and its normal map for the kind (Models/Tiling, written by Blender:
        /// tools/blender/opus_model.py tile_sets; which set, how many metres per repeat and how strong, from tiling.json).
        /// AO and the per-piece tone stay in the vertex colour. A colour variant only changes the colour, as before.
        /// </summary>
        /// <summary>
        /// Tiled model material (buildings: UVs in metres): the model finish (<see cref="CreateModel"/>) with its material's tiling
        /// texture (<see cref="TileLookFor"/>): tone and normal map, repeat size, tone and normal strength.
        /// </summary>
        public static Material CreateTiled(Surface surface, string finishName, TileLook look)
        {
            Material material = CreateModel(surface, finishName);
            material.name = $"OpusTiled_{surface}_{finishName}_{look.name}";
            material.SetTexture("_BaseMap", TileTexture(look.set, "tone"));
            material.SetTexture("_BumpMap", TileTexture(look.set, "normal"));
            material.SetFloat("_Tile", look.metres);
            material.SetFloat("_Strength", look.strength);
            material.SetFloat("_BumpScale", look.bump);
            material.SetFloat("_Grime", 0f);
            material.EnableKeyword("_OPUS_TILED");
            return material;
        }

        /// <summary>A registered material's look (tools/blender/opus_model.py MATERIALS, written to Models/Tiling/tiling.json).</summary>
        [System.Serializable]
        public class TileLook
        {
            public string name;
            public string set;
            public float metres;
            public float strength;
            public float bump;
            /// <summary>The model the material belongs to; empty for a shared one (painted trim, glass, concrete...).</summary>
            public string owner;
            public string[] kinds;
        }

        [System.Serializable]
        public class TileSlot
        {
            public string slot;
            public string material;
        }

        [System.Serializable]
        public class TileModel
        {
            public string model;
            public TileSlot[] slots;
        }

        [System.Serializable]
        public class TileTable
        {
            public TileLook[] materials;
            public TileModel[] models;
        }

        static TileTable tileTable;
        static Dictionary<string, TileLook> tileMaterials;
        static Dictionary<(string model, string slot), TileLook> tileSlots;

        /// <summary>Models/Tiling/tiling.json: the materials' looks and every tiled model's slot -> material map.</summary>
        public static TileTable TileTableAsset()
        {
            if (tileTable != null)
                return tileTable;
            var json = Resources.Load<TextAsset>("Models/Tiling/tiling");
            if (json == null)
                throw new System.IO.FileNotFoundException("Missing Resources/Models/Tiling/tiling.json (tools/Models.ps1 builds it)");
            tileTable = JsonUtility.FromJson<TileTable>(json.text);
            tileMaterials = new Dictionary<string, TileLook>();
            foreach (TileLook look in tileTable.materials)
                tileMaterials[look.name] = look;
            tileSlots = new Dictionary<(string, string), TileLook>();
            foreach (TileModel model in tileTable.models)
                foreach (TileSlot slot in model.slots)
                    tileSlots[(model.model, slot.slot)] = tileMaterials[slot.material];
            return tileTable;
        }

        /// <summary>
        /// The look of a tiled model's material slot ("Siding_A6B0B8_matte" on the house: lap_siding). Every slot of a tiled model
        /// names its material in the Blender build (the material rules); a colour variant keeps the slot's look.
        /// </summary>
        public static TileLook TileLookFor(string model, string slot)
        {
            TileTableAsset();
            if (!tileSlots.TryGetValue((model, slot), out TileLook look))
                throw new KeyNotFoundException($"{model}: material slot '{slot}' has no registered material in tiling.json (tools/Models.ps1 -Only {model})");
            return look;
        }

        static readonly Dictionary<string, Texture2D> TileTextures = new Dictionary<string, Texture2D>();

        static Texture2D TileTexture(string set, string map)
        {
            string key = $"{set}_{map}";
            if (TileTextures.TryGetValue(key, out Texture2D texture) && texture != null)
                return texture;
            texture = Resources.Load<Texture2D>($"Models/Tiling/{key}");
            if (texture == null)
                throw new System.IO.FileNotFoundException($"Missing Resources/Models/Tiling/{key}.png (tools/Models.ps1 builds it)");
            return TileTextures[key] = texture;
        }

        /// <summary>
        /// Natural/textured kinds whose pattern is the surface itself (bark, wood, fabric, stone...): on models the pattern is drawn
        /// at full strength. On painted or moulded surfaces (metal, plastic, rubber, paint) the pattern fades with the finish.
        /// </summary>
        public static bool IsNaturalTexture(SurfaceKind kind) =>
            kind == SurfaceKind.Bark || kind == SurfaceKind.Planks || kind == SurfaceKind.Siding || kind == SurfaceKind.Fabric
            || kind == SurfaceKind.Stone || kind == SurfaceKind.Concrete || kind == SurfaceKind.Brick || kind == SurfaceKind.Soil
            || kind == SurfaceKind.Shingles;

        static readonly Dictionary<SurfaceKind, (string texture, float tile, float strength)> ModelTextures =
            new Dictionary<SurfaceKind, (string, float, float)>
            {
                [SurfaceKind.Siding] = ("paint", 1.2f, 0.7f),
                [SurfaceKind.Shingles] = ("concrete", 0.6f, 0.8f),
                // The deck boards are separate and spaced on the model: the joints in the texture must not be drawn again, only the paint marks
                [SurfaceKind.Planks] = ("paint", 1.0f, 0.6f),
            };

        /// <summary>
        /// Structural surfaces that get grime at the base (on models, grime only on these). No painted wood siding or boards: the round
        /// blotches of the grime texture looked like stains on the clean shed in the video.
        /// </summary>
        public static bool IsWeathering(SurfaceKind kind) =>
            kind == SurfaceKind.Concrete || kind == SurfaceKind.Brick || kind == SurfaceKind.Stone;

        public static IEnumerable<SurfaceKind> Kinds => Looks.Keys;

        public static Look LookOf(SurfaceKind kind) => Looks.TryGetValue(kind, out Look look) ? look : Looks[SurfaceKind.Paint];

        static Shader shader;

        /// <summary>A new surface material (cached in <see cref="PrimitiveKit"/>).</summary>
        public static Material Create(Surface surface)
        {
            if (shader == null)
            {
                shader = Shader.Find(ShaderName);
                if (shader == null)
                {
                    Debug.LogError($"[Opus] {ShaderName} shader not found.");
                    shader = Shader.Find(PrimitiveKit.ShaderName);
                }
            }

            Look look = LookOf(surface.Kind);
            var material = new Material(shader) { name = "Opus_" + surface };
            material.SetColor("_BaseColor", surface.Color);
            material.SetTexture("_BaseMap", SurfaceTextures.Get(look.Texture));
            material.SetTexture("_GrimeMap", SurfaceTextures.Get(SurfaceTextures.Grime));
            material.SetFloat("_Tile", look.Tile * surface.Scale);
            material.SetFloat("_Strength", look.Strength);
            material.SetFloat("_SlopeAlign", look.SlopeAligned ? 1f : 0f);
            material.SetFloat("_Grime", look.Grime);
            material.SetFloat("_GrimeHeight", look.GrimeHeight);
            material.SetFloat("_Tone", look.Tone);
            material.SetFloat("_AO", look.Ao);
            material.SetFloat("_Wrap", look.Wrap);
            return material;
        }
    }
}
