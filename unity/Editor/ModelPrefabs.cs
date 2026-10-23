using System.Collections.Generic;
using System.IO;
using System.Linq;
using Opus.World;
using UnityEditor;
using UnityEngine;

namespace Opus.Editor
{
    /// <summary>
    /// One prefab per Blender model (the user, 23 October 2026: every 3D model as an FBX and a prefab, in a clear folder
    /// structure). Layout:
    /// - Assets/Opus/Resources/Models/&lt;model&gt;.fbx: the model as Blender exports it; the game loads it from here
    ///   (<see cref="ModelLibrary.File"/>), so it stays.
    /// - Assets/Opus/Prefabs/Models/&lt;model&gt;.prefab: a Prefab Variant of that FBX with the game's materials, ready to drag into
    ///   a scene; geometry changes reach it through the FBX.
    /// - Assets/Opus/Prefabs/Models/Materials/&lt;model&gt;/*.mat: those materials saved as assets (the game builds them in code,
    ///   which a prefab cannot keep), made by the same code (<see cref="ModelLibrary.ApplySurfaces"/>).
    /// Rebuilt by tools/Prefabs.ps1 (tools/Verify.ps1 runs it before the tests) and by every build; prefabs and material
    /// folders of models that no longer exist are removed. Checked by ModelImportTests.EveryModelHasAPrefab.
    /// </summary>
    public static class ModelPrefabs
    {
        public const string Folder = "Assets/Opus/Prefabs/Models/";
        public const string MaterialFolder = Folder + "Materials/";

        public static string PrefabPath(string model) => Folder + model + ".prefab";

        public static IEnumerable<string> Models() =>
            Directory.GetFiles(ModelImport.SpecFolder, "*.json").Select(Path.GetFileNameWithoutExtension).OrderBy(n => n);

        /// <summary>Batch entry: Unity -batchmode -executeMethod Opus.Editor.ModelPrefabs.Generate</summary>
        public static void Generate() => BatchUtil.Run("Model prefabs", BuildAll);

        internal static void BuildAll()
        {
            EnsureFolder(Folder);
            EnsureFolder(MaterialFolder);
            var models = Models().ToList();
            foreach (string model in models)
                Build(model);
            // Stale ones: a prefab or material folder whose model is gone
            foreach (string path in Directory.GetFiles(Folder, "*.prefab"))
                if (!models.Contains(Path.GetFileNameWithoutExtension(path)))
                    AssetDatabase.DeleteAsset(path.Replace('\\', '/'));
            foreach (string path in Directory.GetDirectories(MaterialFolder))
                if (!models.Contains(Path.GetFileName(path)))
                    AssetDatabase.DeleteAsset(path.Replace('\\', '/'));
            AssetDatabase.SaveAssets();
            Debug.Log($"[Opus] Model prefabs: {models.Count} in {Folder}");
        }

        static void Build(string model)
        {
            var source = AssetDatabase.LoadAssetAtPath<GameObject>(ModelImport.Folder + model + ".fbx");
            if (source == null)
                throw new FileNotFoundException($"{model}.fbx is not imported ({ModelImport.Folder})");
            var instance = (GameObject)PrefabUtility.InstantiatePrefab(source);
            try
            {
                instance.name = model;
                ModelLibrary.ApplySurfaces(instance, null, model);
                string folder = MaterialFolder + model + "/";
                EnsureFolder(folder);
                var saved = new Dictionary<Material, Material>();
                var used = new HashSet<string>();
                foreach (MeshRenderer renderer in instance.GetComponentsInChildren<MeshRenderer>(true))
                {
                    Material[] materials = renderer.sharedMaterials;
                    for (int i = 0; i < materials.Length; i++)
                    {
                        Material material = materials[i];
                        if (material == null || AssetDatabase.Contains(material))
                            continue;
                        if (!saved.TryGetValue(material, out Material asset))
                        {
                            // Two different materials may share a name: the second gets a number
                            string path = folder + FileName(material.name) + ".mat";
                            for (int n = 2; used.Contains(path); n++)
                                path = folder + FileName(material.name) + "_" + n + ".mat";
                            asset = AssetDatabase.LoadAssetAtPath<Material>(path);
                            if (asset == null)
                            {
                                asset = new Material(material) { name = material.name };
                                AssetDatabase.CreateAsset(asset, path);
                            }
                            else
                            {
                                EditorUtility.CopySerialized(material, asset);
                                asset.name = Path.GetFileNameWithoutExtension(path);
                                EditorUtility.SetDirty(asset);
                            }
                            saved[material] = asset;
                            used.Add(path);
                        }
                        materials[i] = asset;
                    }
                    renderer.sharedMaterials = materials;
                }
                foreach (string path in Directory.GetFiles(folder, "*.mat"))
                    if (!used.Contains(path.Replace('\\', '/')))
                        AssetDatabase.DeleteAsset(path.Replace('\\', '/'));
                PrefabUtility.SaveAsPrefabAsset(instance, PrefabPath(model));
            }
            finally
            {
                Object.DestroyImmediate(instance);
            }
        }

        static string FileName(string name)
        {
            foreach (char c in Path.GetInvalidFileNameChars())
                name = name.Replace(c, '_');
            return name.Replace(' ', '_');
        }

        static void EnsureFolder(string folder)
        {
            string path = folder.TrimEnd('/');
            if (AssetDatabase.IsValidFolder(path))
                return;
            string parent = Path.GetDirectoryName(path).Replace('\\', '/');
            EnsureFolder(parent + "/");
            AssetDatabase.CreateFolder(parent, Path.GetFileName(path));
        }
    }
}
