using System.Collections.Generic;
using System.IO;
using System.Linq;
using NUnit.Framework;
using Opus.Core;
using Opus.Editor;
using Opus.Tools;
using Opus.World;
using UnityEditor;
using UnityEngine;

namespace Opus.Tests
{
    /// <summary>
    /// Blender pipeline: every model must come in exactly matching the spec file Blender wrote (ModelSpecs/*.json, in Unity
    /// axes): scale, axes, part positions, no rotation/scale, triangle count, normal direction, closed volume,
    /// material names. The calibration model additionally proves the meaning of the axes (front +Z, right +X, up +Y).
    /// </summary>
    public class ModelImportTests
    {
        [System.Serializable]
        class Spec
        {
            public string model;
            public string generator;
            public ObjectSpec[] objects;
            public AnchorSpec[] anchors;
            public SurfaceSpec[] surfaces;
            public AtlasSpec atlas;
            public ExternalSpec[] external;
        }

        /// <summary>An outside asset a model is built from (om.external; fetched with tools/Assets.ps1).</summary>
        [System.Serializable]
        class ExternalSpec
        {
            public string @ref;
            public string part;
            public string name;
            public string licence;
            public string[] authors;
            public string page;
            public bool attributionRequired;
        }

        [System.Serializable]
        class ExternalManifest
        {
            public ExternalRecord[] assets;
        }

        [System.Serializable]
        class ExternalRecord
        {
            public string @ref;
            public string licence;
            public string page_url;
            public bool attribution_required;
        }

        // Same list as EXTERNAL_LICENCES in tools/blender/opus_model.py: usable in a commercial game, modified and shipped
        static readonly string[] AllowedLicences = { "CC0", "CC-BY", "OGA-BY", "BlenderKit-RF" };
        const string ExternalManifestPath = "tools/blender/external/assets.json";
        // Credits the licences ask for, shipped with the game
        const string CreditsPath = "Assets/Opus/Resources/ThirdPartyCredits.txt";

        [System.Serializable]
        class AtlasSpec
        {
            public int size;
            // Parts left out of the atlas (leaf clusters): <Kind>_<RRGGBB>_<finish> materials and vertex AO, like the old pipeline
            public string[] untextured;
        }

        static bool InAtlas(Spec spec, string part) =>
            spec.atlas != null && spec.atlas.size > 0 && !(spec.atlas.untextured ?? new string[0]).Contains(part);

        [System.Serializable]
        class AnchorSpec
        {
            public string name;
            public Vector3 position;
        }

        [System.Serializable]
        class SurfaceSpec
        {
            public string name;
            public string finish;
            public string note;
        }

        [System.Serializable]
        class ObjectSpec
        {
            public string name;
            public Vector3 position;
            public Vector3 boundsMin;
            public Vector3 boundsMax;
            public int triangles;
            public int vertices;
            public bool closed;
            public bool foliage;
            public float volume;
            public string[] materials;
        }

        static IEnumerable<string> Models() =>
            Directory.GetFiles(ModelImport.SpecFolder, "*.json").Select(Path.GetFileNameWithoutExtension).OrderBy(n => n);

        static Spec LoadSpec(string model) =>
            JsonUtility.FromJson<Spec>(File.ReadAllText(ModelImport.SpecFolder + model + ".json"));

        static GameObject LoadModel(string model)
        {
            var asset = AssetDatabase.LoadAssetAtPath<GameObject>(ModelImport.Folder + model + ".fbx");
            Assert.IsNotNull(asset, $"{model}.fbx is not imported");
            return asset;
        }

        static void AssertClose(Vector3 expected, Vector3 actual, float tolerance, string what)
        {
            Assert.LessOrEqual((expected - actual).magnitude, tolerance, $"{what}: expected {expected:F4}, got {actual:F4}");
        }

        [Test]
        public void EveryModelHasASpec()
        {
            var fbx = Directory.GetFiles(ModelImport.Folder, "*.fbx").Select(Path.GetFileNameWithoutExtension).OrderBy(n => n);
            CollectionAssert.AreEqual(Models().ToArray(), fbx.ToArray(), "Every FBX must have a Blender spec file (tools/Models.ps1)");
            Assert.Contains("calibration", Models().ToList());
        }

        [TestCaseSource(nameof(Models))]
        public void ImportSettingsAreFixed(string model)
        {
            var importer = (ModelImporter)AssetImporter.GetAtPath(ModelImport.Folder + model + ".fbx");
            Assert.IsTrue(ModelImport.IsConfigured(importer), $"{model}: import settings differ from ModelImport.Configure");
        }

        [TestCaseSource(nameof(Models))]
        public void ModelMatchesBlenderSpec(string model)
        {
            Spec spec = LoadSpec(model);
            Transform root = LoadModel(model).transform;
            Assert.Less(Quaternion.Angle(Quaternion.identity, root.localRotation), 0.01f, "root is rotated");
            AssertClose(Vector3.one, root.localScale, 1e-5f, "root scale");
            Assert.AreEqual(spec.objects.Length, root.childCount, "part count");

            foreach (ObjectSpec o in spec.objects)
            {
                Transform part = root.Find(o.name);
                Assert.IsNotNull(part, $"part {o.name} missing");
                AssertClose(o.position, part.localPosition, 1e-4f, $"{o.name} position");
                Assert.Less(Quaternion.Angle(Quaternion.identity, part.localRotation), 0.01f, $"{o.name} is rotated");
                AssertClose(Vector3.one, part.localScale, 1e-5f, $"{o.name} scale");

                Mesh mesh = part.GetComponent<MeshFilter>().sharedMesh;
                AssertClose(o.boundsMin, mesh.bounds.min, 0.001f, $"{o.name} lower bound");
                AssertClose(o.boundsMax, mesh.bounds.max, 0.001f, $"{o.name} upper bound");
                Assert.AreEqual(o.triangles, mesh.triangles.Length / 3, $"{o.name} triangle count");

                // Triangle winding (the front face in Unity) must face the same way as the vertex normals; a closed part has a positive volume
                Vector3[] v = mesh.vertices;
                Vector3[] n = mesh.normals;
                int[] t = mesh.triangles;
                Assert.AreEqual(v.Length, n.Length, $"{o.name}: no normals");
                bool textured = InAtlas(spec, o.name);
                if (textured)
                {
                    // Textured model: AO is in the texture; tangents are required for the UV and normal map
                    Assert.AreEqual(v.Length, mesh.uv.Length, $"{o.name}: no atlas UVs");
                    Assert.AreEqual(v.Length, mesh.tangents.Length, $"{o.name}: no tangents (needed for the normal map)");
                }
                else
                    Assert.AreEqual(v.Length, mesh.colors32.Length, $"{o.name}: no baked AO (vertex colour)");
                int agree = 0, compared = 0;
                double volume = 0;
                // Shingle strips carry their roof plane's normal on purpose (ShingleRowsShadeLikeTheirRoof): their winding is checked
                // by the volume below and Blender's closed-shell check, not against their normals
                Material[] slots = part.GetComponent<MeshRenderer>().sharedMaterials;
                var planeShaded = new bool[t.Length / 3];
                for (int sub = 0, first = 0; sub < mesh.subMeshCount; first += (int)mesh.GetIndexCount(sub) / 3, sub++)
                    if (slots[sub] != null && slots[sub].name.StartsWith("Shingles_"))
                        for (int k = 0; k < mesh.GetIndexCount(sub) / 3; k++)
                            planeShaded[first + k] = true;
                for (int i = 0; i < t.Length; i += 3)
                {
                    Vector3 a = v[t[i]], b = v[t[i + 1]], c = v[t[i + 2]];
                    if (!planeShaded[i / 3])
                    {
                        compared++;
                        if (Vector3.Dot(Vector3.Cross(b - a, c - a), n[t[i]] + n[t[i + 1]] + n[t[i + 2]]) > 0f)
                            agree++;
                    }
                    // Relative to the mesh's centre and in double: a small part far from its origin (the house lamp shade, 7 m out)
                    // loses its volume to float rounding otherwise
                    Vector3 centre = mesh.bounds.center;
                    double ax = a.x - centre.x, ay = a.y - centre.y, az = a.z - centre.z;
                    double bx = b.x - centre.x, by = b.y - centre.y, bz = b.z - centre.z;
                    double cx = c.x - centre.x, cy = c.y - centre.y, cz = c.z - centre.z;
                    volume += (ax * (by * cz - bz * cy) + ay * (bz * cx - bx * cz) + az * (bx * cy - by * cx)) / 6.0;
                }
                if (o.foliage)
                    // Leaves are double-sided: both faces of every leaf carry the same (outward) normal; half are reverse-wound
                    Assert.AreEqual(0.5f, agree / (float)compared, 0.02f, $"{o.name}: leaves are not double-sided");
                else
                    Assert.GreaterOrEqual(agree / (float)compared, 0.995f, $"{o.name}: some triangles are flipped ({agree}/{compared})");
                if (o.closed)
                {
                    Assert.Greater(volume, 0.0, $"{o.name}: negative volume (inside out)");
                    Assert.AreEqual(o.volume, volume, o.volume * 0.01 + 1e-8, $"{o.name} volume");
                }

                string[] materials = part.GetComponent<MeshRenderer>().sharedMaterials.Select(m => m.name).ToArray();
                CollectionAssert.AreEquivalent(o.materials, materials, $"{o.name} materials");
                if (textured)
                    CollectionAssert.AreEqual(new[] { ModelLibrary.AtlasPrefix + model }, materials, $"{o.name}: the single material of a textured model");
                else
                    foreach (string material in materials)
                        Assert.IsTrue(ModelLibrary.TryParseModelMaterial(material, out _, out _), $"{o.name}: '{material}' is not <Kind>_<RRGGBB>_<finish> (the finish is mandatory)");
            }
        }

        /// <summary>
        /// Textured models (new pipeline): every part has a single atlas material; colour is sRGB, the normal map is of the normal type, orm
        /// (AO, roughness, metallic) is linear; in game drawn through the UV path of Opus/Surface (_OPUS_UVMAP).
        /// </summary>
        [TestCaseSource(nameof(Models))]
        public void TexturedModelsUseTheirAtlas(string model)
        {
            Spec spec = LoadSpec(model);
            string folder = ModelImport.TextureFolder + model + "/" + model;
            if (spec.atlas == null || spec.atlas.size <= 0)
            {
                // No atlas (painted or tiled model): no stale atlas left behind from an earlier build
                Assert.IsNull(AssetImporter.GetAtPath(folder + "_color.png"), $"{model} has no atlas but an old {folder}_color.png is left");
                return;
            }
            var color = (TextureImporter)AssetImporter.GetAtPath(folder + "_color.png");
            var normal = (TextureImporter)AssetImporter.GetAtPath(folder + "_normal.png");
            var orm = (TextureImporter)AssetImporter.GetAtPath(folder + "_orm.png");
            Assert.IsNotNull(color, "no colour texture");
            Assert.IsNotNull(normal, "no normal texture");
            Assert.IsNotNull(orm, "no orm texture");
            Assert.IsTrue(color.sRGBTexture, "colour must be sRGB");
            Assert.AreEqual(TextureImporterType.NormalMap, normal.textureType, "normal map type");
            Assert.IsFalse(orm.sRGBTexture, "orm must be linear data");

            var parent = new GameObject("AtlasTest");
            try
            {
                Transform instance = ModelLibrary.Whole(model, parent.transform);
                foreach (MeshRenderer renderer in instance.GetComponentsInChildren<MeshRenderer>())
                {
                    if (!InAtlas(spec, renderer.name))
                    {
                        // Leaf clusters: the soft foliage material of the old pipeline, not the UV path
                        foreach (Material other in renderer.sharedMaterials)
                            Assert.IsFalse(other.IsKeywordEnabled("_OPUS_UVMAP"), $"{renderer.name}: left out of the atlas but drawn through the UV path");
                        continue;
                    }
                    Material material = renderer.sharedMaterials.Single();
                    Assert.AreEqual("Opus/Surface", material.shader.name);
                    Assert.IsTrue(material.IsKeywordEnabled("_OPUS_UVMAP"), $"{renderer.name}: UV path off");
                    Assert.IsNotNull(material.GetTexture("_BumpMap"), $"{renderer.name}: normal map not bound");
                }
            }
            finally
            {
                Object.DestroyImmediate(parent);
            }
        }

        [Test]
        public void CalibrationAxesMeanTheSameInUnity()
        {
            Transform root = LoadModel("calibration").transform;
            Bounds Of(string part)
            {
                Transform t = root.Find(part);
                Bounds b = t.GetComponent<MeshFilter>().sharedMesh.bounds;
                b.center += t.localPosition;
                return b;
            }

            // 1 m cube, base on the ground, pivot at the middle of the base
            Bounds cube = Of("Cube");
            AssertClose(new Vector3(-0.5f, 0f, -0.5f), cube.min, 0.001f, "cube lower corner");
            AssertClose(new Vector3(0.5f, 1f, 0.5f), cube.max, 0.001f, "cube upper corner");

            // Arrow tips: front +Z 1.1 m, right +X 0.9 m, up +Y 1.3 m (different lengths: mirroring/rotation gets caught)
            Bounds front = Of("Arrow_Front");
            Assert.AreEqual(1.1f, front.max.z, 0.001f, "the front arrow must point to +Z");
            AssertClose(new Vector3(0f, 0.5f, front.center.z), front.center, 0.001f, "front arrow axis");
            Bounds right = Of("Arrow_Right");
            Assert.AreEqual(0.9f, right.max.x, 0.001f, "the right arrow must point to +X");
            AssertClose(new Vector3(right.center.x, 0.5f, 0f), right.center, 0.001f, "right arrow axis");
            Bounds up = Of("Arrow_Up");
            Assert.AreEqual(1.3f, up.max.y, 0.001f, "the up arrow must point to +Y");
            AssertClose(new Vector3(0f, up.center.y, 0f), up.center, 0.001f, "up arrow axis");

            // Positioned part: Blender (-0.7, -0.7, 0.2) -> Unity (0.7, 0.2, 0.7)
            AssertClose(new Vector3(0.7f, 0.2f, 0.7f), root.Find("Marker").localPosition, 1e-4f, "marker position");
            Assert.AreEqual(0.16f, Of("Marker").size.x, 0.002f, "marker diameter");
        }

        /// <summary>
        /// The finish of every material and its reason (what it really is, what shows in the video) must be written in Blender; on the mower
        /// the finishes read from the video: red sheet metal glossy, black plastic cover matte, painted steel handle satin, chrome metallic.
        /// </summary>
        [TestCaseSource(nameof(Models))]
        public void EverySurfaceHasAFinishAndAReason(string model)
        {
            Spec spec = LoadSpec(model);
            Assert.IsNotNull(spec.surfaces, "no material card");
            foreach (SurfaceSpec surface in spec.surfaces)
            {
                Assert.IsTrue(SurfaceLibrary.TryGetFinish(surface.finish, out _), $"{surface.name}: finish '{surface.finish}'");
                Assert.IsTrue(surface.name.EndsWith("_" + surface.finish), surface.name);
                Assert.IsFalse(string.IsNullOrWhiteSpace(surface.note), $"{surface.name}: no reason");
            }
        }

        /// <summary>
        /// Outside assets: every one a model uses has an allowed licence and, when the licence asks for credit, a line in the
        /// game's credits; everything fetched into tools/blender/external has an allowed licence too.
        /// </summary>
        [TestCaseSource(nameof(Models))]
        public void OutsideAssetsHaveAllowedLicencesAndCredits(string model)
        {
            Spec spec = LoadSpec(model);
            foreach (ExternalSpec asset in spec.external ?? new ExternalSpec[0])
            {
                Assert.Contains(asset.licence, AllowedLicences, $"{model}: {asset.@ref} has licence {asset.licence}");
                Assert.IsFalse(string.IsNullOrEmpty(asset.page), $"{model}: {asset.@ref} has no source page");
                if (!asset.attributionRequired)
                    continue;
                Assert.IsTrue(File.Exists(CreditsPath), $"{model}: {asset.@ref} ({asset.licence}) needs credit; {CreditsPath} is missing");
                StringAssert.Contains(asset.page, File.ReadAllText(CreditsPath), $"{model}: no credit line for {asset.@ref}");
            }
        }

        [Test]
        public void FetchedOutsideAssetsHaveAllowedLicences()
        {
            string path = Path.Combine(Directory.GetParent(Application.dataPath).FullName, ExternalManifestPath);
            if (!File.Exists(path))
                Assert.Ignore("nothing fetched yet");
            ExternalManifest manifest = JsonUtility.FromJson<ExternalManifest>(File.ReadAllText(path));
            Assert.IsNotEmpty(manifest.assets);
            foreach (ExternalRecord asset in manifest.assets)
            {
                Assert.Contains(asset.licence, AllowedLicences, $"{asset.@ref} has licence {asset.licence}");
                Assert.IsFalse(string.IsNullOrEmpty(asset.page_url), $"{asset.@ref} has no source page");
            }
        }

        [Test]
        public void MowerFinishesFollowTheVideo()
        {
            Spec spec = LoadSpec(MowerModel.File);
            string FinishOf(string kindAndColor) => spec.surfaces.Single(s => s.name.StartsWith(kindAndColor + "_")).finish;
            Assert.AreEqual("glossy", FinishOf("Metal_C21F22"), "red painted sheet metal housing");
            Assert.AreEqual("matte", FinishOf("Plastic_2F2E31"), "black plastic engine cover");
            Assert.AreEqual("satin", FinishOf("Metal_2A2B2F"), "painted steel handle and plates");
            Assert.AreEqual("metallic", FinishOf("Metal_A3A6AC"), "chrome starter cover");

            SurfaceLibrary.TryGetFinish("matte", out SurfaceLibrary.Finish mat);
            SurfaceLibrary.TryGetFinish("satin", out SurfaceLibrary.Finish satin);
            SurfaceLibrary.TryGetFinish("glossy", out SurfaceLibrary.Finish gloss);
            SurfaceLibrary.TryGetFinish("metallic", out SurfaceLibrary.Finish metallic);
            Assert.AreEqual(0f, mat.Gloss, "a matte surface does not shine");
            Assert.Less(satin.Gloss, gloss.Gloss);
            Assert.Less(gloss.Gloss, metallic.Gloss);
        }

        [Test]
        public void TrimmerFeaturePointsMatchTheModel()
        {
            Spec spec = LoadSpec(TrimmerModel.File);
            Vector3 Anchor(string name) => spec.anchors.Single(a => a.name == name).position;
            AssertClose(TrimmerModel.BodyFront, Anchor("BodyFront"), 1e-4f, "body front");
            AssertClose(TrimmerModel.BatteryBack, Anchor("BatteryBack"), 1e-4f, "battery back");
            AssertClose(TrimmerModel.HandleTop, Anchor("HandleTop"), 1e-4f, "D handle top");
            AssertClose(TrimmerModel.HeadCenter, Anchor("HeadCenter"), 1e-4f, "head centre");
        }

        [Test]
        public void MowerConnectsWhereTheGameExpects()
        {
            Spec spec = LoadSpec(MowerModel.File);
            Vector3 Anchor(string name) => spec.anchors.Single(a => a.name == name).position;
            Vector3 Left(Vector3 v) => new Vector3(-v.x, v.y, v.z);

            // The handle reaches where the player's hands are
            Vector3 grip = MowerTool.GripFromPlayer - new Vector3(0f, 0f, MowerTool.ForwardOffset);
            AssertClose(grip, Anchor("Handle_Right"), 1e-4f, "right grip");
            AssertClose(Left(grip), Anchor("Handle_Left"), 1e-4f, "left grip");
            // The axle pins on the housing are in the same place as the game's wheel axles
            AssertClose(MowerModel.FrontAxle, Anchor("Axle_Front_Right"), 1e-4f, "front axle");
            AssertClose(MowerModel.RearAxle, Anchor("Axle_Rear_Right"), 1e-4f, "rear axle");
            AssertClose(Left(MowerModel.RearAxle), Anchor("Axle_Rear_Left"), 1e-4f, "left rear axle");

            var parent = new GameObject("MowerTest");
            try
            {
                MowerModel mower = MowerModel.Build(parent.transform);
                AssertClose(Anchor("Axle_Rear_Right"), mower.RearAxles[1].localPosition, 1e-4f, "built rear wheel");
                AssertClose(Anchor("Axle_Front_Left"), mower.FrontAxles[0].localPosition, 1e-4f, "built front wheel");
                float rear = mower.RearAxles[1].GetComponentInChildren<MeshFilter>().sharedMesh.bounds.extents.y;
                Assert.AreEqual(MowerModel.RearWheelRadius, rear, 0.002f, "rear wheel radius as in the physics");
                Assert.IsTrue(parent.GetComponentsInChildren<MeshRenderer>().All(r => r.sharedMaterials.All(m => m.shader.name == "Opus/Surface")));
                Assert.LessOrEqual(mower.PartCount, 8, "renderer count");

                // Wide deck: the axle pins and handle bolts move out with the housing, the wheels stay on the pins
                mower.SetDeckScale(1.3f);
                Transform deck = parent.transform.Find("Body/Deck");
                Vector3 pin = deck.TransformPoint(MowerModel.RearAxle);
                AssertClose(pin, mower.RearAxles[1].position, 1e-4f, "rear wheel on the pin with the wide deck");
            }
            finally
            {
                Object.DestroyImmediate(parent);
            }
        }

        [Test]
        public void LibraryUsesOpusSurfaces()
        {
            var parent = new GameObject("ModelTest");
            try
            {
                Transform arrow = ModelLibrary.Part("calibration", "Arrow_Front", parent.transform);
                Assert.AreEqual(Vector3.zero, arrow.localPosition);
                Material material = arrow.GetComponent<MeshRenderer>().sharedMaterial;
                Assert.AreEqual("Opus/Surface", material.shader.name);
                Assert.AreSame(ModelLibrary.MaterialFor(new Surface(SurfaceKind.Paint, Palette.Hex("#3D6FD6")), "satin"), material);
                Assert.AreEqual(1f, material.GetFloat("_VertexAO"), "models use baked AO");
                Assert.IsTrue(material.IsKeywordEnabled("_OPUS_HARD"), "models use the hard-surface path");
                Assert.IsFalse(PrimitiveKit.MaterialFor(new Surface(SurfaceKind.Paint, Palette.Hex("#3D6FD6"))).IsKeywordEnabled("_OPUS_HARD"), "garden props on the old path");
                Assert.AreEqual(0f, material.GetFloat("_Grime"), "no grime on models");

                Transform whole = ModelLibrary.Whole("calibration", parent.transform);
                Assert.AreEqual(5, whole.childCount);
                Assert.IsTrue(whole.GetComponentsInChildren<MeshRenderer>().All(r => r.sharedMaterial.shader.name == "Opus/Surface"));
                Assert.Throws<System.ArgumentException>(() => ModelLibrary.Part("calibration", "Missing", parent.transform));
            }
            finally
            {
                Object.DestroyImmediate(parent);
            }
        }

        [Test]
        public void HouseVariantsRecolorSidingAndDoor()
        {
            // The colour variants find the door surface on the model by its colour: DOOR in house.py and the one in C# must match
            string door = $"Paint_{ColorUtility.ToHtmlStringRGB(YardProps.HouseModelDoor)}_matte";
            Assert.IsTrue(LoadSpec("house").surfaces.Any(s => s.name == door), $"no door material {door} on the house model");

            bool Uses(Transform house, Color color) => house.GetComponentsInChildren<MeshRenderer>(true)
                .SelectMany(r => r.sharedMaterials)
                .Any(m => m != null && m.HasProperty("_BaseColor") && ((Vector4)(m.GetColor("_BaseColor") - color)).magnitude < 0.01f);

            var root = new GameObject("HouseTest").transform;
            try
            {
                for (int variant = 1; variant < YardProps.HouseVariants.Length; variant++)
                {
                    Transform house = YardProps.BuildHouse(root, Vector3.zero, variant);
                    YardProps.HouseColors colors = YardProps.HouseVariants[variant].Value;
                    Assert.IsTrue(Uses(house, colors.Siding), $"variant {variant}: siding colour");
                    Assert.IsTrue(Uses(house, colors.Door), $"variant {variant}: door colour");
                    Assert.IsFalse(Uses(house, YardProps.HouseModelDoor), $"variant {variant}: the model's door colour is left");
                }
                Assert.IsTrue(Uses(YardProps.BuildHouse(root, Vector3.zero, 0), YardProps.HouseModelDoor), "variant 0 with the model's colours");
            }
            finally
            {
                Object.DestroyImmediate(root.gameObject);
            }
        }

        /// <summary>
        /// Shingle rows shade like their roof plane: the faces of the shingle strips turned away from the sky (the 1 cm butts, the
        /// strip ends) carry the roof's normal. Lit as faces turned down the slope they drew dark sub-pixel lines at a distance and
        /// made moiré arcs on the roof (21 October 2026); the row lines are in the mipmapped shingle texture instead.
        /// </summary>
        [TestCase("house")]
        [TestCase("shed")]
        public void ShingleRowsShadeLikeTheirRoof(string model)
        {
            int turned = 0, lit = 0;
            foreach (MeshRenderer renderer in LoadModel(model).GetComponentsInChildren<MeshRenderer>())
            {
                Mesh mesh = renderer.GetComponent<MeshFilter>().sharedMesh;
                Vector3[] v = mesh.vertices, n = mesh.normals;
                Material[] materials = renderer.sharedMaterials;
                for (int sub = 0; sub < mesh.subMeshCount; sub++)
                {
                    if (!materials[sub].name.StartsWith("Shingles_"))
                        continue;
                    int[] t = mesh.GetTriangles(sub);
                    for (int i = 0; i < t.Length; i += 3)
                    {
                        Vector3 face = Vector3.Cross(v[t[i + 1]] - v[t[i]], v[t[i + 2]] - v[t[i]]).normalized;
                        if (face.y >= 0.3f)
                            continue;
                        turned++;
                        if (n[t[i]].y > 0.65f && n[t[i + 1]].y > 0.65f && n[t[i + 2]].y > 0.65f)
                            lit++;
                    }
                }
            }
            Assert.Greater(turned, 100, $"{model}: no shingle faces found");
            // The rest are the ridge caps and the sheathing board, which keep their own normals
            Assert.Greater(lit / (float)turned, 0.85f, $"{model}: only {lit} of {turned} shingle faces turned from the sky shade like the roof");
        }

        /// <summary>
        /// The material rules (tools/blender/opus_model.py MATERIALS; user, 21 October 2026: two different materials, by their type or by
        /// the context they are in, must have logically different textures): no two registered materials look alike (another texture
        /// set, or tone strength 0.1 / bump 0.15 / repeat x1.3 apart); a material with an owner is used by that model only; every
        /// slot of a tiled model names a material of its kind. The house's lap siding and the shed's rough boards are the case.
        /// </summary>
        [Test]
        public void MaterialsFollowTheTextureRules()
        {
            SurfaceLibrary.TileTable table = SurfaceLibrary.TileTableAsset();
            SurfaceLibrary.TileLook[] looks = table.materials;
            for (int i = 0; i < looks.Length; i++)
                for (int j = i + 1; j < looks.Length; j++)
                {
                    SurfaceLibrary.TileLook a = looks[i], b = looks[j];
                    float ratio = Mathf.Max(a.metres, b.metres) / Mathf.Max(Mathf.Min(a.metres, b.metres), 1e-6f);
                    bool alike = a.set == b.set && Mathf.Abs(a.strength - b.strength) < 0.1f && Mathf.Abs(a.bump - b.bump) < 0.15f && ratio < 1.3f;
                    Assert.IsFalse(alike, $"materials {a.name} and {b.name} would look alike");
                }
            var byName = looks.ToDictionary(l => l.name);
            foreach (SurfaceLibrary.TileModel model in table.models)
                foreach (SurfaceLibrary.TileSlot slot in model.slots)
                {
                    Assert.IsTrue(byName.TryGetValue(slot.material, out SurfaceLibrary.TileLook look), $"{model.model}: {slot.slot} names unknown material {slot.material}");
                    string kind = slot.slot.Split('_')[0];
                    CollectionAssert.Contains(look.kinds, kind, $"{model.model}: {slot.slot} is {kind}, its material {look.name} is for {string.Join(", ", look.kinds)}");
                    Assert.IsTrue(string.IsNullOrEmpty(look.owner) || look.owner == model.model,
                        $"{model.model}: {slot.slot} uses {look.name}, which belongs to {look.owner} (the same stuff in another context is its own material)");
                }

            string Cladding(string model) => table.models.Single(m => m.model == model).slots.Single(s => s.slot.StartsWith("Siding_")).material;
            Assert.AreNotEqual(Cladding("house"), Cladding("shed"), "the house's and the shed's wall boards share a material");
            foreach (string model in new[] { "house", "shed" })
            {
                int slots = table.models.Single(m => m.model == model).slots.Length;
                int inFbx = LoadModel(model).GetComponentsInChildren<MeshRenderer>().SelectMany(r => r.sharedMaterials).Select(m => m.name).Distinct().Count();
                Assert.AreEqual(inFbx, slots, $"{model}: every material slot of the model is in tiling.json");
            }
        }

        /// <summary>
        /// Static batching leaves the big meshes alone: the house joined into one mesh (over 64k vertices) came out of the batch with its
        /// triangles scrambled in game, while its small parts (collision boxes, grill) still batch.
        /// </summary>
        [Test]
        public void BigModelMeshesStayOutOfStaticBatches()
        {
            var root = new GameObject("BatchTest").transform;
            try
            {
                Transform house = YardProps.BuildHouse(root, Vector3.zero);
                MeshFilter model = house.Find("HouseModel").GetComponentsInChildren<MeshFilter>().OrderByDescending(f => f.sharedMesh.vertexCount).First();
                Assert.Greater(model.sharedMesh.vertexCount, YardBuilder.MaxBatchVertices, "the house mesh is expected to be big (else this test checks nothing)");
                GameObject[] batched = YardBuilder.Batchable(house);
                CollectionAssert.DoesNotContain(batched, model.gameObject, "the big house mesh is batched");
                Assert.IsTrue(batched.Any(g => g.name == "Grill"), "the small parts are no longer batched");
                Assert.IsTrue(batched.All(g => g.GetComponent<MeshFilter>().sharedMesh.vertexCount <= YardBuilder.MaxBatchVertices));
            }
            finally
            {
                Object.DestroyImmediate(root.gameObject);
            }
        }

        /// <summary>
        /// Buildings (meshes with UVs in metres): every material is the tiling one of its kind, its textures are bound and repeat,
        /// the mesh carries AO in the vertex colour and tangents for the normal map.
        /// </summary>
        [TestCase("house")]
        [TestCase("shed")]
        public void BuildingsUseTilingTextures(string model)
        {
            var parent = new GameObject("TiledTest");
            try
            {
                Transform instance = ModelLibrary.Whole(model, parent.transform);
                MeshRenderer[] renderers = instance.GetComponentsInChildren<MeshRenderer>();
                Assert.IsNotEmpty(renderers);
                foreach (MeshRenderer renderer in renderers)
                {
                    Mesh mesh = renderer.GetComponent<MeshFilter>().sharedMesh;
                    Assert.IsTrue(ModelLibrary.IsTiled(renderer), $"{renderer.name}: no UVs");
                    Assert.AreEqual(mesh.vertexCount, mesh.tangents.Length, $"{renderer.name}: no tangents");
                    Assert.AreEqual(mesh.vertexCount, mesh.colors32.Length, $"{renderer.name}: no vertex AO");
                    foreach (Material material in renderer.sharedMaterials)
                    {
                        Assert.IsTrue(material.IsKeywordEnabled("_OPUS_TILED"), $"{renderer.name}: {material.name} is not tiled");
                        var tone = (Texture2D)material.GetTexture("_BaseMap");
                        Assert.IsNotNull(tone, $"{material.name}: no tone texture");
                        Assert.AreEqual(TextureWrapMode.Repeat, tone.wrapMode, $"{material.name}: the tile does not repeat");
                        Assert.IsNotNull(material.GetTexture("_BumpMap"), $"{material.name}: no normal map");
                        Assert.Greater(material.GetFloat("_Tile"), 0.05f, $"{material.name}: tile size");
                    }
                }
            }
            finally
            {
                Object.DestroyImmediate(parent);
            }
        }

        [Test]
        public void SurfaceNamesParse()
        {
            Assert.IsTrue(ModelLibrary.TryParseSurface("Rubber_232327", out Surface rubber));
            Assert.AreEqual(SurfaceKind.Rubber, rubber.Kind);
            Assert.AreEqual("232327", ColorUtility.ToHtmlStringRGB(rubber.Color));
            Assert.IsTrue(ModelLibrary.TryParseSurface("Planks_8A6A4A_x0.5", out Surface planks));
            Assert.AreEqual(0.5f, planks.Scale, 1e-6f);
            // Same format as Surface.ToString
            Assert.IsTrue(ModelLibrary.TryParseSurface(rubber.ToString(), out Surface again));
            Assert.AreEqual(rubber, again);

            foreach (string bad in new[] { null, "", "Tire", "Rubber_23232", "Rubber_GG2327", "3_232327", "Tire_232327", "Rubber_232327_2" })
                Assert.IsFalse(ModelLibrary.TryParseSurface(bad, out _), bad ?? "null");

            // Model material: the finish is mandatory and one of the known names
            Assert.IsTrue(ModelLibrary.TryParseModelMaterial("Plastic_2F2E31_matte", out Surface shroud, out string finish));
            Assert.AreEqual(SurfaceKind.Plastic, shroud.Kind);
            Assert.AreEqual("matte", finish);
            Assert.IsTrue(ModelLibrary.TryParseModelMaterial("Planks_8A6A4A_x0.5_satin", out Surface scaled, out _));
            Assert.AreEqual(0.5f, scaled.Scale, 1e-6f);
            foreach (string bad in new[] { "Plastic_2F2E31", "Plastic_2F2E31_polished", "Plastic_matte" })
                Assert.IsFalse(ModelLibrary.TryParseModelMaterial(bad, out _, out _), bad);
        }

        /// <summary>
        /// Every model is an FBX and a prefab (the user, 23 October 2026): Assets/Opus/Prefabs/Models/&lt;model&gt;.prefab, a variant
        /// of the FBX with every part, carrying the game's materials as saved assets (not the FBX's placeholders, nothing that
        /// exists only in memory), whose textures are assets too; no prefab without a model.
        /// </summary>
        [Test]
        public void EveryModelHasAPrefab()
        {
            var prefabs = Directory.GetFiles(ModelPrefabs.Folder, "*.prefab").Select(Path.GetFileNameWithoutExtension).OrderBy(n => n);
            CollectionAssert.AreEqual(Models().ToArray(), prefabs.ToArray(), "one prefab per model (tools/Prefabs.ps1)");
            foreach (string model in Models())
            {
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(ModelPrefabs.PrefabPath(model));
                Assert.IsNotNull(prefab, $"{model}: no prefab");
                Assert.AreEqual(LoadModel(model), PrefabUtility.GetCorrespondingObjectFromSource(prefab), $"{model}: the prefab is not a variant of its FBX");
                foreach (ObjectSpec o in LoadSpec(model).objects)
                {
                    Transform part = prefab.transform.Find(o.name);
                    Assert.IsNotNull(part, $"{model}: the prefab has no part {o.name}");
                    foreach (Material material in part.GetComponent<MeshRenderer>().sharedMaterials)
                    {
                        Assert.IsNotNull(material, $"{model}/{o.name}: a missing material");
                        string path = AssetDatabase.GetAssetPath(material);
                        StringAssert.StartsWith(ModelPrefabs.MaterialFolder + model + "/", path, $"{model}/{o.name}: '{material.name}' is not a saved game material");
                        foreach (int id in material.GetTexturePropertyNameIDs())
                        {
                            Texture texture = material.GetTexture(id);
                            Assert.IsTrue(texture == null || AssetDatabase.Contains(texture), $"{model}/{material.name}: a texture that exists only in memory");
                        }
                    }
                }
            }
        }

        /// <summary>
        /// What each model costs once imported, measured, not judged (22 October 2026, after the delivery checks of
        /// blender-game-skills: UV and normal seams split vertices, so Unity's vertex count is not Blender's). Writes
        /// Builds/QC/delivery.json (tools/Verify.ps1 prints one line from it); asserts only that every part was measured.
        /// No thresholds and no LODs until a measured frame time asks for them.
        /// </summary>
        [Test]
        public void DeliveryCostsAreMeasured()
        {
            var rows = new List<string>();
            foreach (string model in Models())
            {
                Spec spec = LoadSpec(model);
                Transform root = LoadModel(model).transform;
                foreach (ObjectSpec o in spec.objects)
                {
                    Mesh mesh = root.Find(o.name).GetComponent<MeshFilter>().sharedMesh;
                    Assert.IsNotNull(mesh, $"{model}/{o.name}: no mesh");
                    rows.Add($"{{\"model\": \"{model}\", \"part\": \"{o.name}\", \"triangles\": {mesh.triangles.Length / 3}, " +
                             $"\"blenderVertices\": {o.vertices}, \"unityVertices\": {mesh.vertexCount}, " +
                             $"\"drawCalls\": {mesh.subMeshCount}, \"index32\": {(mesh.indexFormat == UnityEngine.Rendering.IndexFormat.UInt32 ? "true" : "false")}}}");
                }
            }
            string folder = Path.Combine(Application.dataPath, "..", "Builds", "QC");
            Directory.CreateDirectory(folder);
            File.WriteAllText(Path.Combine(folder, "delivery.json"), "[\n  " + string.Join(",\n  ", rows) + "\n]\n");
            Assert.Greater(rows.Count, 0);
        }
    }
}
