"""
The art style's measurements (tools/Style.py), without Blender: colour conversion against known values, a deterministic
palette, and the base-colour check (a colour outside the style fails unless the surface note gives a style exception).
Run: py -3 -m unittest discover -s tools/tests
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import Style as S  # noqa: E402

STYLE = {"measured": {"albedo": {"gamut": {"lightness": [5.0, 92.0], "chroma_max": 80.0},
                                 "palette": [{"lab": [50.0, 0.0, 0.0]}, {"lab": [45.0, 60.0, 40.0]}]}}}


class ColourTests(unittest.TestCase):
    def test_known_colours(self):
        np.testing.assert_allclose(S.srgb_to_lab([255, 255, 255]), [100.0, 0.0, 0.0], atol=0.05)
        np.testing.assert_allclose(S.srgb_to_lab([255, 0, 0]), [53.24, 80.09, 67.20], atol=0.05)
        self.assertEqual(list(S.lab_to_srgb(S.srgb_to_lab([194, 31, 34]))), [194, 31, 34])

    def test_the_palette_is_deterministic(self):
        points = S.srgb_to_lab(np.random.default_rng(0).integers(0, 256, (500, 3)))
        a, sa = S.kmeans(points, 6)
        b, sb = S.kmeans(points, 6)
        np.testing.assert_array_equal(a, b)
        self.assertAlmostEqual(float(sa.sum()), 1.0)


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        S.ROOT = self.root
        os.makedirs(os.path.join(self.root, "Assets", "Opus", "ModelSpecs"))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def spec(self, surfaces):
        with open(os.path.join(self.root, "Assets", "Opus", "ModelSpecs", "m.json"), "w", encoding="utf-8") as f:
            json.dump({"surfaces": surfaces}, f)

    def test_a_colour_inside_passes(self):
        self.spec([{"name": "Paint_C21F22_glossy", "note": "red deck"}])
        self.assertEqual(S.check("m", STYLE)[0], [])

    def test_a_neon_colour_fails(self):
        self.spec([{"name": "Plastic_00FF00_glossy", "note": "neon green"}])
        problems = S.check("m", STYLE)[0]
        self.assertEqual(len(problems), 1)
        self.assertIn("chroma", problems[0])

    def test_pure_white_fails_on_lightness(self):
        self.spec([{"name": "Paint_FFFFFF_matte", "note": "white"}])
        self.assertIn("lightness", S.check("m", STYLE)[0][0])

    def test_a_justified_exception_passes(self):
        self.spec([{"name": "Plastic_00FF00_glossy", "note": "safety light. Style exception: a warning lamp must glare"}])
        self.assertEqual(S.check("m", STYLE)[0], [])


class MeasureTests(unittest.TestCase):
    def test_two_opposite_hues_fit_a_two_sector_template(self):
        from PIL import Image
        a = np.zeros((64, 64, 3), dtype=np.uint8)
        a[:, :32] = (200, 40, 40)     # red
        a[:, 32:] = (40, 180, 190)    # cyan, opposite
        h = S.harmony(a.astype(float))
        self.assertIn(h["template"], ("I", "X", "Y", "T"))
        self.assertLess(h["fit_deg"], 2.0)

    def test_noise_has_a_flatter_spectrum_than_a_smooth_gradient(self):
        rng = np.random.default_rng(0)
        noise = rng.normal(50, 20, (128, 128))
        y, x = np.mgrid[0:128, 0:128]
        smooth = 50 + 30 * np.sin(x / 20.0) * np.cos(y / 25.0)
        self.assertLess(S.fourier_slope(noise), 0.5)
        self.assertGreater(S.fourier_slope(smooth), 1.5)

    def test_measure_gives_every_axis(self):
        from PIL import Image
        image = Image.fromarray(np.random.default_rng(1).integers(0, 256, (80, 120, 3), dtype=np.uint8))
        m = S.measure(image)
        for key in S.SCALARS + ["hue_families", "harmony", "shadow_colour", "light_colour"]:
            self.assertIn(key, m)
        self.assertAlmostEqual(m["notan_dark"] + m["notan_mid"] + m["notan_light"], 1.0, places=6)

    def test_leave_one_out_marks_the_odd_image(self):
        same = [{k: 1.0 + 0.01 * i for k in S.SCALARS} for i in range(8)]
        odd = {k: 9.0 for k in S.SCALARS}
        shares = S.leave_one_out(same + [odd])
        self.assertEqual(shares[-1], 0.0)
        self.assertGreater(min(shares[:-1]), 0.5)

    def test_a_rule_without_a_check_is_refused(self):
        style = {"style_version": "1", "summary": "x", "stylisation": {},
                 "rules": [{"id": "a", "kind": "invariant", "check": "review", "text": "t"},
                           {"id": "b", "kind": "tunable", "check": "", "text": "t"},
                           {"id": "a", "kind": "sometimes", "check": "x", "text": "t"}]}
        problems = " ".join(S.validate(style))
        self.assertIn("b: no check", problems)
        self.assertIn("kind must be", problems)
        self.assertIn("used twice", problems)


RULES = {"classes": {"machine": ["m"]},
         "finish_by_kind": {"Rubber": ["matte"], "Plastic": ["matte", "satin", "glossy"]},
         "stylisation": {"budgets_tris": {"machine": [100, 1000]}, "chamfer_applies_to": ["machine"],
                         "chamfer_mm": {"hard_parts": [1.0, 2.5]}},
         "rules": [{"id": "finish.real_material"}, {"id": "detail.budgets"}, {"id": "edges.chamfer", "enforce": "warn"}]}


class RuleTests(CheckTests):
    """Style.rules_check: finish by kind, class budgets and chamfers; a rule's "enforce" decides fail or report."""

    def model(self, surfaces=(), triangles=500, bevels=None, unchamfered=None):
        with open(os.path.join(self.root, "Assets", "Opus", "ModelSpecs", "m.json"), "w", encoding="utf-8") as f:
            json.dump({"surfaces": list(surfaces), "objects": [{"name": "Body", "triangles": triangles}],
                       "bevels_mm": bevels or {}, "unchamfered": unchamfered or {}}, f)

    def test_a_glossy_rubber_fails_a_matte_one_passes(self):
        self.model([{"name": "Rubber_303030_glossy", "note": "tyre"}])
        self.assertIn("finish.real_material", S.rules_check("m", RULES)[0][0])
        self.model([{"name": "Rubber_303030_matte", "note": "tyre"}])
        self.assertEqual(S.rules_check("m", RULES)[0], [])

    def test_over_the_budget_fails_unless_the_rule_only_reports(self):
        self.model(triangles=1500)
        self.assertIn("detail.budgets", S.rules_check("m", RULES)[0][0])
        soft = json.loads(json.dumps(RULES))
        soft["rules"][1]["enforce"] = "warn"
        problems, warnings, info = S.rules_check("m", soft)
        self.assertEqual((problems, info["triangles"]), ([], 1500))
        self.assertIn("detail.budgets", warnings[0])

    def test_a_hard_part_without_a_chamfer_or_outside_the_band_is_reported(self):
        self.model(bevels={"Body": None, "Cap": 1.5, "Lip": 4.0})
        problems, warnings, _ = S.rules_check("m", RULES)
        self.assertEqual(problems, [])
        self.assertEqual(sorted(w.split(":")[1].strip() for w in warnings), ["Body", "Lip"])
        self.model(bevels={"Body": None, "Cord": None}, unchamfered={"Cord": "a 3 mm cord"})   # on purpose, with a reason
        self.assertEqual([w.split(":")[1].strip() for w in S.rules_check("m", RULES)[1]], ["Body"])


class NearMissTests(CheckTests):
    """The near misses (style.json near_misses, rendered by tools/blender/lookdev.py) against the gates that should catch
    them. 24 October 2026: a tree 2.6 x more saturated stayed under the one overall chroma ceiling; it fails per hue now."""

    STYLE = {"measured": {"albedo": {"gamut": {"lightness": [5.0, 92.0], "chroma_max": 80.0},
                                     "palette": [{"lab": [50.0, 0.0, 0.0]}]}}}

    @staticmethod
    def saturated(hex_colour, factor):
        import colorsys
        r, g, b = (int(hex_colour[i:i + 2], 16) / 255 for i in (0, 2, 4))
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        return S.hex_of(np.array(colorsys.hsv_to_rgb(h, min(1.0, s * factor), v)) * 255).lstrip("#")

    def test_the_ceilings_come_from_the_styles_own_colours(self):
        leaf = S.srgb_to_lab(np.array([[76, 128, 52], [96, 140, 60]], dtype=float))
        ceilings = S.hue_ceilings([(leaf, True)], floor=20.0)
        family = int(S.hue_bin(leaf[0]))
        self.assertAlmostEqual(ceilings[family], round(float(S.chroma(leaf).max()) * S.CHROMA_MARGIN, 1), places=1)
        self.assertEqual(ceilings[(family + 6) % 12], 20.0)   # a hue the style never uses: the floor

    def test_an_oversaturated_leaf_fails_per_hue_under_the_overall_ceiling(self):
        leaf = "4C8034"
        style = json.loads(json.dumps(self.STYLE))
        style["measured"]["albedo"]["gamut"]["chroma_by_hue"] = S.hue_ceilings(
            [(S.srgb_to_lab(np.array([[int(leaf[i:i + 2], 16) for i in (0, 2, 4)]], dtype=float)), True)], floor=20.0)
        self.spec([{"name": f"Leaf_{leaf}_matte", "note": "the style"}])
        self.assertEqual(S.check("m", style)[0], [])
        loud = self.saturated(leaf, 2.6)
        lab = S.srgb_to_lab(np.array([[int(loud[i:i + 2], 16) for i in (0, 2, 4)]], dtype=float))[0]
        self.assertLess(S.chroma(lab), 80.0)   # the overall ceiling alone lets it through
        self.spec([{"name": f"Leaf_{loud}_matte", "note": "near miss: oversaturated"}])
        self.assertIn("for this hue", S.check("m", style)[0][0])

    def test_a_near_miss_must_name_a_rule(self):
        style = {"style_version": "1", "summary": "x", "stylisation": {},
                 "rules": [{"id": "a", "kind": "invariant", "check": "review", "text": "t"}],
                 "near_misses": [{"variant": "glossy_plastic", "rule": "a"}, {"variant": "x", "rule": "nope"}]}
        self.assertEqual([p for p in S.validate(style) if "near miss" in p], ["near miss x: names no rule of the style (nope)"])


class PairTests(unittest.TestCase):
    """A game shot against the reference frame it recreates (Style.pair_check, Style.py shots)."""

    PROFILE = {k: {"p10": 0.0, "p90": 10.0} for k in S.SCALARS}

    def frame(self, lift=0):
        from PIL import Image
        rng = np.random.default_rng(4)
        base = rng.integers(20, 200, (60, 90, 3)).astype(int)
        base[:, :45] //= 3   # a dark half
        return Image.fromarray(np.clip(base + lift, 0, 255).astype(np.uint8))

    def test_the_same_frame_is_within_tolerance(self):
        axes, outside, _, _ = S.pair_check(self.frame(), self.frame(), self.PROFILE)
        self.assertEqual(outside, [])
        self.assertEqual(axes["lightness_p10"]["delta"], 0.0)

    def test_lifted_shadows_are_reported(self):
        _, outside, _, _ = S.pair_check(self.frame(lift=60), self.frame(), self.PROFILE)
        self.assertIn("lightness_p10", outside)


if __name__ == "__main__":
    unittest.main()
