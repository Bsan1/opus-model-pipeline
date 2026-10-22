using UnityEditor;

namespace Opus.Editor
{
    /// <summary>
    /// Fixed import settings for the Blender pipeline's models (Assets/Opus/Resources/Models): 1 unit = 1 m
    /// (the file's unit scale is read, no extra scale), the axis conversion is baked into the data, not the root (no -90° left on the root),
    /// normals from the file (the weighted normals from Blender), tangents with MikkTSpace (the same tangent space Blender bakes
    /// the normal map in), no cameras/lights/animation/colliders. The materials are placeholders; in game
    /// ModelLibrary turns their names into Opus surfaces. Atlases of textured models (Models/Textures/&lt;model&gt;/):
    /// _color sRGB, _normal a normal map, _orm linear data (AO, roughness, metallic). Verified by ModelImportTests.
    /// </summary>
    public sealed class ModelImport : AssetPostprocessor
    {
        public const string Folder = "Assets/Opus/Resources/Models/";
        public const string SpecFolder = "Assets/Opus/ModelSpecs/";
        public const string TextureFolder = Folder + "Textures/";
        public const string TilingFolder = Folder + "Tiling/";

        // Raised when the settings change so the models get reimported
        public override uint GetVersion() => 5;

        void OnPreprocessModel()
        {
            if (assetPath.StartsWith(Folder))
                Configure((ModelImporter)assetImporter);
        }

        void OnPreprocessTexture()
        {
            if (assetPath.StartsWith(TextureFolder) || assetPath.StartsWith(TilingFolder))
                ConfigureTexture((TextureImporter)assetImporter, assetPath);
        }

        public static void ConfigureTexture(TextureImporter importer, string path)
        {
            importer.textureType = path.EndsWith("_normal.png") ? TextureImporterType.NormalMap : TextureImporterType.Default;
            importer.sRGBTexture = path.EndsWith("_color.png");
            importer.alphaSource = TextureImporterAlphaSource.None;
            importer.mipmapEnabled = true;
            // Atlases clamp; the buildings' tiling textures (Models/Tiling) repeat
            importer.wrapMode = path.StartsWith(TilingFolder) ? UnityEngine.TextureWrapMode.Repeat : UnityEngine.TextureWrapMode.Clamp;
            importer.filterMode = UnityEngine.FilterMode.Trilinear;
            importer.anisoLevel = 8;
            importer.maxTextureSize = 4096;   // the shed and house atlases are 4096
            importer.textureCompression = TextureImporterCompression.CompressedHQ;
        }

        public static void Configure(ModelImporter importer)
        {
            importer.globalScale = 1f;
            importer.useFileScale = true;
            importer.bakeAxisConversion = false;
            importer.preserveHierarchy = true;
            importer.sortHierarchyByName = false;
            importer.importNormals = ModelImporterNormals.Import;
            importer.importTangents = ModelImporterTangents.CalculateMikk;
            importer.importBlendShapes = false;
            importer.importVisibility = false;
            importer.importCameras = false;
            importer.importLights = false;
            importer.importAnimation = false;
            importer.animationType = ModelImporterAnimationType.None;
            importer.addCollider = false;
            importer.generateSecondaryUV = false;
            importer.meshCompression = ModelImporterMeshCompression.Off;
            // Static batching and MeshBaker read the vertex data at runtime
            importer.isReadable = true;
            importer.materialImportMode = ModelImporterMaterialImportMode.ImportViaMaterialDescription;
            importer.materialLocation = ModelImporterMaterialLocation.InPrefab;
        }

        /// <summary>Are the settings the same as <see cref="Configure"/> (test)?</summary>
        public static bool IsConfigured(ModelImporter importer) =>
            importer.globalScale == 1f && importer.useFileScale && !importer.bakeAxisConversion && importer.preserveHierarchy
            && importer.importNormals == ModelImporterNormals.Import && importer.importTangents == ModelImporterTangents.CalculateMikk
            && !importer.importCameras && !importer.importLights
            && !importer.importAnimation && !importer.addCollider && importer.isReadable
            && importer.meshCompression == ModelImporterMeshCompression.Off;
    }
}
