"""
Review and approval integrity (tools/Review.py), without Blender: each test builds a small fake project in a temporary
folder. Run: py -3 -m unittest discover -s tools/tests   (tools/Verify.ps1 runs it when tools/*.py change)

Cases (22 October 2026; the review of the plausibility pipeline found each of these possible):
- findings for another pack, or a pack whose files changed after it was made, are refused (A3);
- a preview review is carried to the final build only when plan, links, features, bounds and pieces held (A1);
- an approval goes out of date when geometry, UVs, plan or surfaces change, or textures change beyond bake noise (A2);
- an approved model with an open serious finding, or a critical feature failing or unverified, is not clean (A4, D).
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import Review as R  # noqa: E402
from PIL import Image  # noqa: E402

PLAN = {"purpose": "a test lever", "tier": "complex", "category": [], "supports": ["ground"],
        "sources": [{"kind": "text", "where": "test"}],
        "components": [{"name": "Base", "role": "structural", "job": "stands", "attaches": ["ground"], "moves": "fixed",
                        "source": "guess"}]}
FEATURES = [{"id": "lever_pivot", "tier": "critical", "components": ["Base"], "expect": "turns on its pin", "measured": None,
             "view": "front"}]


class Project(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        R.ROOT = self.root
        os.makedirs(os.path.join(self.root, "tools", "blender", "models"))
        with open(os.path.join(self.root, "tools", "blender", "models", "m.py"), "w") as f:
            f.write('"""A test model."""\n')
        self.texture("m_color.png", 120)
        self.spec(structure="s1", asset="a1")
        self.spec(structure="p1", stage="preview")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def texture(self, name, value, noise=0):
        folder = os.path.join(self.root, "Assets", "Opus", "Resources", "Models", "Textures", "m")
        os.makedirs(folder, exist_ok=True)
        image = Image.new("RGB", (64, 64), (value, value, value))
        if noise:
            image.putpixel((3, 3), (value + noise, value, value))
        image.save(os.path.join(folder, name))

    def spec(self, structure, asset=None, stage="final", plan=PLAN, features=FEATURES, shells=10, top=1.0):
        spec = {"model": "m", "structure": structure, "geometry": "g-" + structure, "plan": plan, "features": features,
                "links": {"routes": [], "attachments": []},
                "objects": [{"name": "M", "position": {"x": 0, "y": 0, "z": 0}, "boundsMin": {"x": 0, "y": 0, "z": 0},
                             "boundsMax": {"x": 1, "y": top, "z": 1}}],
                "qc": {"construction": {"shells": shells, "stray": [], "problems": []}}}
        if asset:
            spec["asset"] = asset
            spec["atlas"] = {"textures": {"color": "Assets/Opus/Resources/Models/Textures/m/m_color.png"}}
        path = R.spec_path("m", stage)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        R.write_json(path, spec)
        sheet = os.path.join(self.root, "Builds", "Models", "m_preview.png" if stage == "preview" else "m_contact.png")
        os.makedirs(os.path.dirname(sheet), exist_ok=True)
        Image.new("RGB", (32, 32), (200, 200, 200)).save(sheet)
        return spec

    def findings(self, manifest, findings=(), verdicts=None, pack=None):
        path = os.path.join(self.root, "findings.json")
        verdicts = verdicts if verdicts is not None else [{"id": f, "verdict": "pass", "evidence": "front"}
                                                          for f in manifest["features"]]
        R.write_json(path, {"pack": pack or manifest["pack"], "findings": list(findings), "features": verdicts})
        return path


class RecordTests(Project):
    def test_findings_for_another_pack_are_refused(self):
        manifest = R.pack("m", "final")
        with self.assertRaises(SystemExit):
            R.record("m", self.findings(manifest, pack="0123456789ab"), "test")

    def test_a_pack_changed_after_packing_is_refused(self):
        manifest = R.pack("m", "final")
        Image.new("RGB", (32, 32), (10, 10, 10)).save(os.path.join(self.root, "Builds", "Review", "m", "sheet.png"))
        with self.assertRaises(SystemExit):
            R.record("m", self.findings(manifest), "test")

    def test_a_critical_feature_without_a_verdict_is_refused(self):
        manifest = R.pack("m", "final")
        with self.assertRaises(SystemExit):
            R.record("m", self.findings(manifest, verdicts=[]), "test")

    def test_the_review_is_tied_to_the_structure_that_was_packed(self):
        manifest = R.pack("m", "final")
        self.spec(structure="s2", asset="a2")   # rebuilt between pack and record
        review = R.record("m", self.findings(manifest), "test")
        self.assertEqual(review["structure"], "s1")
        self.assertEqual(R.state("m")["state"], "review outdated")


    def test_a_skipped_reference_comparison_does_not_break_the_pack(self):
        folder = os.path.join(self.root, "Builds", "Models", "m_compare")
        os.makedirs(folder)
        R.write_json(os.path.join(folder, "compare.json"),
                     {"model": "m", "comparisons": [{"name": "front", "frame": "docs/reference/x.png",
                                                     "skipped": "reference frame not available"}]})
        manifest = R.pack("m", "final")
        with open(os.path.join(self.root, "Builds", "Review", "m", "brief.md"), encoding="utf-8") as f:
            self.assertIn("reference frame not available", f.read())
        self.assertEqual(sorted(manifest["files"]), ["brief.md", "sheet.png"])


class StyleFindingTests(Project):
    """A "style:" finding must say where: a pack image and the place in it (the research report, step 9)."""

    FINDING = {"severity": "low", "confidence": "high", "component": "Base", "problem": "style: the paint is mirror-glossy",
               "evidence": "sheet", "fix": "satin"}

    def test_a_style_finding_without_a_location_is_refused(self):
        manifest = R.pack("m", "final")
        with self.assertRaises(SystemExit):
            R.record("m", self.findings(manifest, [self.FINDING]), "test")
        with self.assertRaises(SystemExit):   # a location that is not in the pack
            R.record("m", self.findings(manifest, [dict(self.FINDING, location="view_top.png: the lid")]), "test")

    def test_the_pack_carries_the_heroes_and_the_near_misses(self):
        # 24 October 2026: the hero's view was looked up under the wrong key of views.json and heroes.png never appeared
        hero = os.path.join(self.root, "Builds", "Models", "h")
        os.makedirs(hero)
        R.write_json(os.path.join(hero, "views.json"), {"views": [{"type": "render", "file": "front.png"}]})
        Image.new("RGB", (40, 30), (90, 120, 80)).save(os.path.join(hero, "front.png"))
        lookdev = os.path.join(self.root, "Builds", "Style", "lookdev")
        os.makedirs(lookdev)
        for name in ("style", "glossy_plastic"):
            Image.new("RGB", (40, 30), (120, 90, 80)).save(os.path.join(lookdev, f"near_h_{name}.png"))
        R.write_json(os.path.join(self.root, "tools", "blender", "style", "style.json"),
                     {"heroes": ["h", "m"], "lookdev": {"near_miss_models": ["h"]},
                      "near_misses": [{"variant": "glossy_plastic", "rule": "surfaces.painted"}]})
        manifest = R.pack("m", "final")
        self.assertIn("heroes.png", manifest["files"])
        self.assertIn("near_misses.png", manifest["files"])

    def test_a_located_style_finding_is_recorded(self):
        manifest = R.pack("m", "final")
        review = R.record("m", self.findings(manifest, [dict(self.FINDING, location="sheet.png: the base, front view")]), "test")
        self.assertEqual(len(review["findings"]), 1)


class DecisionTests(Project):
    """One decision per round, with a located note; after MAX_ROUNDS revisions the decision goes to the user."""

    def setUp(self):
        super().setUp()
        folder = os.path.join(self.root, "Builds", "Models", "m_preview")
        os.makedirs(folder, exist_ok=True)
        Image.new("RGB", (8, 8)).save(os.path.join(folder, "front.png"))

    def test_a_note_without_a_location_is_refused(self):
        for note in ("too thin", "nowhere: the lever is too thin", "front:"):
            with self.assertRaises(SystemExit):
                R.decide("m", "revise", "blockout", note, "test")
        self.assertEqual(R.decisions("m"), [])

    def test_rounds_are_counted_and_the_last_goes_to_the_user(self):
        for _ in range(R.MAX_ROUNDS):
            R.decide("m", "revise", "blockout", "front: the lever is too thin", "test")
        with self.assertRaises(SystemExit):
            R.decide("m", "revise", "blockout", "front: still too thin", "test")
        entry = R.decide("m", "escalate", "blockout", "front: thin or thick lever, the user decides", "test")
        self.assertEqual(entry["round"], R.MAX_ROUNDS + 1)
        state = R.state("m")
        self.assertIn("blockout escalate in round 4", state["text"])
        self.assertIn("blockout escalated: waiting for the user", state["warnings"])
        R.decide("m", "approve", "blockout", "", "user")
        self.assertNotIn("blockout escalated: waiting for the user", R.state("m")["warnings"])


class TiledTextureTests(Project):
    def test_a_tiled_model_finds_its_tiling_sets(self):
        folder = os.path.join(self.root, "Assets", "Opus", "Resources", "Models", "Tiling")
        os.makedirs(folder)
        R.write_json(os.path.join(folder, "tiling.json"),   # the file's real shape: lists
                     {"materials": [{"name": "lap_siding", "set": "wood_siding"}],
                      "models": [{"model": "m", "slots": [{"slot": "Siding_A6B0B8_matte", "material": "lap_siding"}]}]})
        files = R.texture_files("m", {"tiled": True})
        self.assertEqual([os.path.basename(f) for f in files], ["wood_siding_normal.png", "wood_siding_tone.png"])


class CarryTests(Project):
    def preview_review(self):
        manifest = R.pack("m", "preview")
        return R.record("m", self.findings(manifest), "test")

    def test_an_unchanged_structure_is_carried(self):
        self.preview_review()
        self.assertTrue(R.carry("m"))
        self.assertEqual(R.state("m")["state"], "reviewed")

    def test_a_changed_plan_is_not_carried(self):
        self.preview_review()
        plan = dict(PLAN, purpose="a different object")
        self.spec(structure="s1", asset="a1", plan=plan)
        self.assertFalse(R.carry("m"))

    def test_moved_bounds_are_not_carried(self):
        self.preview_review()
        self.spec(structure="s1", asset="a1", top=1.05)
        self.assertFalse(R.carry("m"))

    def test_new_pieces_are_not_carried(self):
        self.preview_review()
        self.spec(structure="s1", asset="a1", shells=14)
        self.assertFalse(R.carry("m"))

    def test_a_final_review_is_never_carried(self):
        manifest = R.pack("m", "final")
        R.record("m", self.findings(manifest), "test")
        self.spec(structure="s2", asset="a2")
        with self.assertRaises(SystemExit):
            R.carry("m")


class ApprovalTests(Project):
    def reviewed(self, findings=(), verdict="pass"):
        manifest = R.pack("m", "final")
        R.record("m", self.findings(manifest, findings, [{"id": "lever_pivot", "verdict": verdict, "evidence": "x"}]),
                 "test")

    def test_approved_and_clean(self):
        self.reviewed()
        R.approve(["m"], "user")
        self.assertTrue(R.state("m")["clean"])

    def test_a_uv_or_plan_change_outdates_the_approval(self):
        self.reviewed()
        R.approve(["m"], "user")
        self.spec(structure="s1", asset="a2")
        s = R.state("m")
        self.assertNotEqual(s["state"], "approved")
        self.assertIn("approval outdated", s["text"])

    def test_bake_noise_keeps_the_approval_a_real_texture_change_does_not(self):
        self.reviewed()
        R.approve(["m"], "user")
        self.texture("m_color.png", 120, noise=30)   # one pixel in 4096
        self.assertTrue(R.state("m")["clean"])
        self.texture("m_color.png", 150)
        self.assertIn("textures changed", R.state("m")["text"])

    def test_an_open_serious_finding_keeps_an_approved_model_from_being_clean(self):
        finding = {"severity": "high", "confidence": "high", "component": "Base", "problem": "p", "evidence": "e",
                   "fix": "f"}
        self.reviewed([finding])
        R.approve(["m"], "user")
        s = R.state("m")
        self.assertEqual(s["state"], "approved")
        self.assertFalse(s["clean"])
        self.assertIn("open high/medium", s["text"])

    def test_an_unverified_or_failing_critical_feature_is_reported(self):
        self.reviewed(verdict="unverified")
        self.assertIn("critical lever_pivot unverified", R.state("m")["text"])
        self.reviewed(verdict="fail")
        self.assertIn("critical lever_pivot failing", R.state("m")["text"])

    def test_no_review_means_unverified_not_passed(self):
        R.approve(["m"], "user")
        s = R.state("m")
        self.assertFalse(s["clean"])
        self.assertIn("unverified", s["text"])


if __name__ == "__main__":
    unittest.main()
