using System.Collections.Generic;
using System.Globalization;
using UnityEngine;

namespace Opus.World
{
    /// <summary>
    /// Models generated from code in the Blender pipeline (Resources/Models/*.fbx; generators in tools/blender/models,
    /// runner tools/Models.ps1). The material name in Blender has the form "<see cref="Surface.ToString"/>_<finish>"
    /// ("Plastic_2F2E31_matte", "Metal_C21F22_glossy"; the finish comes from the part's real material, not from the kind); on build each slot
    /// is turned into its own model material (Opus/Surface, hard-surface lighting, shine by finish, baked AO).
    /// Axes and scale: 1 unit = 1 m, +Z front, +Y up, +X right; parts have no rotation or scale (ModelImportTests).
    /// </summary>
    public static class ModelLibrary
    {
        public const string Folder = "Models";

        static readonly Dictionary<string, GameObject> Files = new Dictionary<string, GameObject>();

        /// <summary>The imported model file (Resources/Models/&lt;file&gt;.fbx).</summary>
        public static GameObject File(string file)
        {
            if (Files.TryGetValue(file, out GameObject asset) && asset != null)
                return asset;
            asset = Resources.Load<GameObject>($"{Folder}/{file}");
            if (asset == null)
                throw new System.IO.FileNotFoundException($"Missing model: Resources/{Folder}/{file}.fbx (generate it with tools/Models.ps1 -Only {file})");
            Files[file] = asset;
            return asset;
        }

        /// <summary>
        /// Builds a single part of the file: at the parent's origin (the part's own pivot) or, with
        /// <paramref name="keepPosition"/>, at its position in the file (moving sub-parts such as a joint or a spool).
        /// </summary>
        public static Transform Part(string file, string part, Transform parent, string name = null, bool keepPosition = false)
        {
            Transform source = File(file).transform.Find(part);
            if (source == null)
                throw new System.ArgumentException($"{file}.fbx has no part '{part}'", nameof(part));
            GameObject instance = Object.Instantiate(source.gameObject, parent, false);
            instance.name = name ?? part;
            instance.transform.localPosition = keepPosition ? source.localPosition : Vector3.zero;
            ApplySurfaces(instance, null, file);
            return instance.transform;
        }

        /// <summary>
        /// Builds the whole file; the parts sit at their positions in the file. <paramref name="recolor"/>: replaces a surface
        /// with another surface (house colour variants: siding and door colour); the finish stays the same.
        /// </summary>
        public static Transform Whole(string file, Transform parent, string name = null, System.Func<Surface, Surface> recolor = null)
        {
            GameObject instance = Object.Instantiate(File(file), parent, false);
            instance.name = name ?? file;
            ApplySurfaces(instance, recolor, file);
            return instance.transform;
        }

        static readonly Dictionary<(Surface, string, string), Material> Materials = new Dictionary<(Surface, string, string), Material>();

        /// <summary>
        /// Shared material of the models: surface + finish (glossy, metallic, satin, matte) + baked AO
        /// (<see cref="SurfaceLibrary.CreateModel"/>); <paramref name="look"/>: a building mesh with UVs in metres gets its
        /// material's tiling texture (<see cref="SurfaceLibrary.CreateTiled"/>, <see cref="SurfaceLibrary.TileLookFor"/>).
        /// </summary>
        public static Material MaterialFor(Surface surface, string finish, SurfaceLibrary.TileLook look = null)
        {
            string key = look?.name;
            if (!Materials.TryGetValue((surface, finish, key), out Material material) || material == null)
                Materials[(surface, finish, key)] = material = look != null ? SurfaceLibrary.CreateTiled(surface, finish, look)
                    : SurfaceLibrary.CreateModel(surface, finish);
            return material;
        }

        /// <summary>A model mesh with UVs uses the tiling materials (buildings); without UVs the painted triplanar ones.</summary>
        public static bool IsTiled(MeshRenderer renderer)
        {
            Mesh mesh = renderer.GetComponent<MeshFilter>()?.sharedMesh;
            return mesh != null && mesh.HasVertexAttribute(UnityEngine.Rendering.VertexAttribute.TexCoord0);
        }

        public const string AtlasPrefix = "Atlas_";

        /// <summary>
        /// Textured model material ("Atlas_tire_swing"): the model's only material; colour, normal and AO/roughness are baked in
        /// Blender into atlas textures (Resources/Models/Textures/&lt;model&gt;/&lt;model&gt;_{color,normal,orm}).
        /// </summary>
        public static bool TryParseAtlasMaterial(string materialName, out string model)
        {
            model = null;
            if (string.IsNullOrEmpty(materialName) || !materialName.StartsWith(AtlasPrefix) || materialName.Length <= AtlasPrefix.Length)
                return false;
            model = materialName.Substring(AtlasPrefix.Length);
            return true;
        }

        static readonly Dictionary<string, Material> Atlases = new Dictionary<string, Material>();

        /// <summary>Shared material of a textured model (Opus/Surface, _OPUS_UVMAP).</summary>
        public static Material AtlasMaterialFor(string model)
        {
            if (Atlases.TryGetValue(model, out Material material) && material != null)
                return material;
            Texture2D Map(string map)
            {
                var texture = Resources.Load<Texture2D>($"{Folder}/Textures/{model}/{model}_{map}");
                if (texture == null)
                    throw new System.IO.FileNotFoundException($"Missing texture: Resources/{Folder}/Textures/{model}/{model}_{map}.png (tools/Models.ps1 -Only {model})");
                return texture;
            }
            return Atlases[model] = SurfaceLibrary.CreateAtlas(model, Map("color"), Map("normal"), Map("orm"));
        }

        /// <summary>"Plastic_2F2E31_matte" -> surface + finish. The finish is mandatory: it is not derived from the kind.</summary>
        public static bool TryParseModelMaterial(string materialName, out Surface surface, out string finish)
        {
            surface = default;
            finish = null;
            if (string.IsNullOrEmpty(materialName))
                return false;
            int cut = materialName.LastIndexOf('_');
            if (cut <= 0 || !SurfaceLibrary.TryGetFinish(materialName.Substring(cut + 1), out _))
                return false;
            finish = materialName.Substring(cut + 1);
            return TryParseSurface(materialName.Substring(0, cut), out surface);
        }

        /// <summary>
        /// Replaces the imported placeholder materials with the surface in their names; on a tiled mesh each slot takes the look of the
        /// material <paramref name="file"/>'s build registered for it (a recoloured variant keeps it).
        /// </summary>
        public static void ApplySurfaces(GameObject root, System.Func<Surface, Surface> recolor = null, string file = null)
        {
            foreach (MeshRenderer renderer in root.GetComponentsInChildren<MeshRenderer>(true))
            {
                Material[] materials = renderer.sharedMaterials;
                for (int i = 0; i < materials.Length; i++)
                {
                    string materialName = materials[i] != null ? materials[i].name : null;
                    if (TryParseAtlasMaterial(materialName, out string atlasModel))
                    {
                        materials[i] = AtlasMaterialFor(atlasModel);
                        continue;
                    }
                    if (!TryParseModelMaterial(materialName, out Surface surface, out string finish))
                        throw new System.FormatException($"{renderer.name}: material name '{materialName}' is not <Kind>_<RRGGBB>_<finish>");
                    SurfaceLibrary.TileLook look = IsTiled(renderer)
                        ? SurfaceLibrary.TileLookFor(file ?? throw new System.ArgumentException($"{renderer.name}: a tiled mesh needs its model file"), materialName)
                        : null;
                    materials[i] = MaterialFor(recolor != null ? recolor(surface) : surface, finish, look);
                }
                renderer.sharedMaterials = materials;
            }
        }

        /// <summary>"Rubber_232327" or "Planks_8A6A4A_x0.5" -> <see cref="Surface"/>.</summary>
        public static bool TryParseSurface(string materialName, out Surface surface)
        {
            surface = default;
            if (string.IsNullOrEmpty(materialName))
                return false;
            string[] parts = materialName.Split('_');
            if (parts.Length < 2 || parts.Length > 3 || parts[1].Length != 6)
                return false;
            if (parts[0].Length == 0 || !char.IsLetter(parts[0][0]) || !System.Enum.TryParse(parts[0], false, out SurfaceKind kind)
                || !System.Enum.IsDefined(typeof(SurfaceKind), kind))
                return false;
            if (!ColorUtility.TryParseHtmlString("#" + parts[1], out Color color))
                return false;
            float scale = 1f;
            if (parts.Length == 3 && (!parts[2].StartsWith("x")
                    || !float.TryParse(parts[2].Substring(1), NumberStyles.Float, CultureInfo.InvariantCulture, out scale) || scale <= 0f))
                return false;
            surface = new Surface(kind, color, scale);
            return true;
        }
    }
}
