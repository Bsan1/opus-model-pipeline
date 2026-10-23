"""
The art style as data, measured from the images that show it and enforced on every new asset (the user, 23 October 2026:
"a process to make an art style and make the next assets full of this style", then "detailed, advanced, researched";
reports/Oyun art stili tanımlama ve denetim.md, steps 1-4; skill .claude/skills/art-style).

The style is tools/blender/style/style.json (schema 2):
- rules: each with an id, a kind (invariant: changing it is a new style; tunable: adjusted within the style) and the check
  that enforces it (a gate, a test, or "review"); `validate` refuses a rule without one;
- stylisation: anchor, tie-breaker, what is modelled versus painted, detail floors, chamfer band, triangle budgets;
- measured.lit: the style's sources as seen on screen, five axes per image (colour, value, hue, light, detail), stored as
  median and IQR over the images, plus palettes; measured.albedo: base colours of the models that define the style;
- history and style_version: every change, dated.

Usage:
  py -3 tools/Style.py extract [IMAGE ...]   measure the sources (the generators' reference crops, or the images given) and
                                             the defining models; keeps rules and stylisation; leave-one-out coverage
  py -3 tools/Style.py report [MODEL ...] [--json]   models' base colours against measured.albedo (Verify runs it)
  py -3 tools/Style.py validate              schema check: every rule has an id, a kind and a check
  py -3 tools/Style.py bible                 Builds/Style/art_bible.html: the style as a visual document, generated from
                                             style.json, the measurements, the sources and the look-dev renders
Measurement discipline: one resize (Pillow BICUBIC to 256 px on the long side for detail measures), CIELAB (D65) for gamut
and value, OKLab/OKLCh for hue; numbers from different settings are never compared.
"""
import argparse
import base64
import datetime
import glob
import html
import io
import json
import math
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STYLE = os.path.join(ROOT, "tools", "blender", "style", "style.json")
OUT = os.path.join(ROOT, "Builds", "Style")
BOARD = os.path.join(OUT, "style_board.png")
PALETTE_SIZE = 16
LIGHTNESS_PERCENTILES = (0.5, 99.5)
CHROMA_PERCENTILE = 99.5
CHROMA_MARGIN = 1.10
HUE_MIN_CHROMA = 8.0      # below this a colour's hue is noise: only the overall ceiling applies to it
HUE_NEIGHBOUR = 0.8       # a hue family the style never uses gets this share of its neighbours' ceiling (at least the floor)
# 24 October 2026, the near-miss test: the shed, house and tree with their colours 2.6 x more saturated stayed under the one
# overall chroma ceiling (it comes from the mower's red deck), so a neon-green tree passed. The style's greens reach 54:
# the ceiling is per hue family now.
DETAIL_SIZE = 256
HEX = re.compile(r"^[A-Za-z]+_([0-9A-Fa-f]{6})(?:_x[0-9.]+)?_[a-z]+$")
KINDS = ("invariant", "tunable")
ENFORCE = ("error", "warn")   # a rule's gate fails the run, or only reports
# Cohen-Or et al. 2006 harmonic templates: sectors as (centre offset in degrees, width in degrees)
TEMPLATES = {"i": [(0, 18)], "V": [(0, 93.6)], "L": [(0, 18), (90, 79.2)], "I": [(0, 18), (180, 18)],
             "T": [(0, 180)], "Y": [(0, 93.6), (180, 18)], "X": [(0, 93.6), (180, 93.6)]}
HUE_NAMES = ["red", "orange", "yellow", "lime", "green", "teal", "cyan", "azure", "blue", "violet", "purple", "pink"]


# ----------------------------------------------------------------------------------------------------------------------
# Colour spaces
# ----------------------------------------------------------------------------------------------------------------------

def _linear(rgb):
    c = np.asarray(rgb, dtype=float) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def srgb_to_lab(rgb):
    """rgb (..., 3) 0..255 -> CIELAB (D65)."""
    m = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]])
    xyz = _linear(rgb) @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1)


def lab_to_srgb(lab):
    lab = np.asarray(lab, dtype=float)
    fy = (lab[..., 0] + 16) / 116
    f = np.stack([fy + lab[..., 1] / 500, fy, fy - lab[..., 2] / 200], axis=-1)
    xyz = np.where(f > 6 / 29, f ** 3, 3 * (6 / 29) ** 2 * (f - 4 / 29)) * np.array([0.95047, 1.0, 1.08883])
    m = np.array([[3.2404542, -1.5371385, -0.4985314], [-0.9692660, 1.8760108, 0.0415560], [0.0556434, -0.2040259, 1.0572252]])
    c = np.clip(xyz @ m.T, 0, 1)
    c = np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1 / 2.4) - 0.055)
    return np.round(c * 255).astype(int)


def srgb_to_oklab(rgb):
    """OKLab (Ottosson 2020): better hue uniformity than CIELAB, used for hue families."""
    lin = _linear(rgb)
    m1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566],
                   [0.0883024619, 0.2817188376, 0.6299787005]])
    m2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099],
                   [0.0259040371, 0.7827717662, -0.8086757660]])
    return np.cbrt(lin @ m1.T) @ m2.T


def chroma(lab):
    lab = np.asarray(lab, dtype=float)
    return np.hypot(lab[..., 1], lab[..., 2])


def hex_of(rgb):
    return "#%02X%02X%02X" % tuple(int(v) for v in rgb)


# ----------------------------------------------------------------------------------------------------------------------
# Measures (one image)
# ----------------------------------------------------------------------------------------------------------------------

def _hsv(rgb):
    c = np.asarray(rgb, dtype=float) / 255.0
    mx, mn = c.max(axis=-1), c.min(axis=-1)
    d = mx - mn
    s = np.where(mx > 0, d / np.maximum(mx, 1e-9), 0)
    r, g, b = c[..., 0], c[..., 1], c[..., 2]
    h = np.where(d == 0, 0, np.where(mx == r, ((g - b) / np.maximum(d, 1e-9)) % 6,
                                     np.where(mx == g, (b - r) / np.maximum(d, 1e-9) + 2, (r - g) / np.maximum(d, 1e-9) + 4)))
    return (h * 60) % 360, s


def harmony(rgb):
    """Best Cohen-Or template and its normalised fit (mean saturation-weighted hue distance to the template, degrees)."""
    h, s = _hsv(rgb.reshape(-1, 3))
    keep = s > 0.15
    h, s = h[keep], s[keep]
    if len(h) < 50:
        return {"template": "N", "fit_deg": 0.0}
    best = None
    for name, sectors in TEMPLATES.items():
        for alpha in range(0, 360, 3):
            dist = np.full(len(h), 180.0)
            for offset, width in sectors:
                centre = (alpha + offset) % 360
                d = np.abs((h - centre + 180) % 360 - 180) - width / 2
                dist = np.minimum(dist, np.maximum(d, 0))
            fit = float((dist * s).sum() / s.sum())
            if best is None or fit < best[2]:
                best = (name, alpha, fit)
    return {"template": best[0], "angle": best[1], "fit_deg": round(best[2], 2)}


def _resize(image):
    w, h = image.size
    scale = DETAIL_SIZE / max(w, h)
    return image.resize((max(8, round(w * scale)), max(8, round(h * scale))), Image.BICUBIC)


def fourier_slope(gray):
    """Slope of the radially averaged Fourier amplitude spectrum (log-log, radii 4..N/4): natural scenes about 1.2;
    shallower = more fine detail (Redies; Aesthetics Toolbox)."""
    g = gray - gray.mean()
    window = np.outer(np.hanning(g.shape[0]), np.hanning(g.shape[1]))
    amp = np.abs(np.fft.fftshift(np.fft.fft2(g * window)))
    cy, cx = np.array(amp.shape) // 2
    y, x = np.indices(amp.shape)
    r = np.hypot(y - cy, x - cx).astype(int)
    radii = np.arange(4, min(amp.shape) // 4)
    means = np.array([amp[r == k].mean() for k in radii])
    ok = means > 0
    slope = -np.polyfit(np.log(radii[ok]), np.log(means[ok]), 1)[0]
    return float(slope)


def measure(image):
    """Five axes of one image (sRGB PIL image): colour, value, hue, light, detail."""
    rgb = np.asarray(image.convert("RGB"), dtype=float)
    flat = rgb.reshape(-1, 3)
    lab = srgb_to_lab(flat)
    L, C = lab[:, 0], chroma(lab)
    ok = srgb_to_oklab(flat)
    ok_c = np.hypot(ok[:, 1], ok[:, 2])
    ok_h = (np.degrees(np.arctan2(ok[:, 2], ok[:, 1])) + 360) % 360
    hues = np.bincount(((ok_h + 15) % 360 // 30).astype(int), weights=ok_c, minlength=12)
    hues = hues / max(hues.sum(), 1e-9)
    dark, light = L <= np.percentile(L, 20), L >= np.percentile(L, 80)
    shift = lab[light].mean(axis=0)[1:] - lab[dark].mean(axis=0)[1:]   # (a, b) of the lights minus the shadows
    small = _resize(image.convert("RGB"))
    gray = srgb_to_lab(np.asarray(small, dtype=float))[..., 0]
    gy, gx = np.gradient(gray)
    grad = np.hypot(gx, gy)
    k = 5
    pad = np.pad(gray, k // 2, mode="edge")
    windows = np.lib.stride_tricks.sliding_window_view(pad, (k, k))
    return {
        "lightness_median": float(np.median(L)), "lightness_p10": float(np.percentile(L, 10)),
        "lightness_p90": float(np.percentile(L, 90)), "contrast_rms": float(L.std()),
        "notan_dark": float((L < 35).mean()), "notan_mid": float(((L >= 35) & (L < 70)).mean()), "notan_light": float((L >= 70).mean()),
        "chroma_median": float(np.median(C)), "chroma_p90": float(np.percentile(C, 90)),
        "chroma_dark": float(C[L < 35].mean()) if (L < 35).any() else 0.0,
        "chroma_mid": float(C[(L >= 35) & (L < 70)].mean()) if ((L >= 35) & (L < 70)).any() else 0.0,
        "chroma_light": float(C[L >= 70].mean()) if (L >= 70).any() else 0.0,
        "shadow_shift_a": float(shift[0]), "shadow_shift_b": float(shift[1]),
        "shadow_colour": hex_of(lab_to_srgb(lab[dark].mean(axis=0))), "light_colour": hex_of(lab_to_srgb(lab[light].mean(axis=0))),
        "fourier_slope": fourier_slope(gray), "edge_density": float((grad > 6.0).mean()),
        "busyness": float(windows.std(axis=(-1, -2)).mean()),
        "hue_families": [round(float(v), 4) for v in hues], "harmony": harmony(rgb),
    }


SCALARS = ["lightness_median", "lightness_p10", "lightness_p90", "contrast_rms", "notan_dark", "notan_mid", "notan_light",
           "chroma_median", "chroma_p90", "chroma_dark", "chroma_mid", "chroma_light", "shadow_shift_a", "shadow_shift_b",
           "fourier_slope", "edge_density", "busyness"]


def profile(per_image):
    """Median and IQR (p25-p75) of every scalar over the images, plus the summed hue families and harmony templates."""
    out = {}
    for key in SCALARS:
        v = np.array([m[key] for m in per_image])
        out[key] = {"median": round(float(np.median(v)), 3), "p25": round(float(np.percentile(v, 25)), 3),
                    "p75": round(float(np.percentile(v, 75)), 3), "p10": round(float(np.percentile(v, 10)), 3),
                    "p90": round(float(np.percentile(v, 90)), 3)}
    hues = np.mean([m["hue_families"] for m in per_image], axis=0)
    out["hue_families"] = {HUE_NAMES[i]: round(float(hues[i]), 3) for i in range(12)}
    templates = [m["harmony"]["template"] for m in per_image]
    out["harmony"] = {t: templates.count(t) for t in sorted(set(templates))}
    return out


def leave_one_out(per_image, band=(10, 90), margin=0.15):
    """Each image's scalars against the band of the other images (p10-p90, widened by 15 % of its width): the share of
    an image's measures inside. A low share marks an image that does not belong to the style, or too few sources."""
    rows = []
    for i, m in enumerate(per_image):
        others = [o for j, o in enumerate(per_image) if j != i]
        inside = 0
        for key in SCALARS:
            v = np.array([o[key] for o in others])
            lo, hi = np.percentile(v, band)
            pad = (hi - lo) * margin
            inside += lo - pad <= m[key] <= hi + pad
        rows.append(round(inside / len(SCALARS), 2))
    return rows


# ----------------------------------------------------------------------------------------------------------------------
# Palettes, sources, models
# ----------------------------------------------------------------------------------------------------------------------

def kmeans(points, k, seed=7, rounds=40):
    """Deterministic k-means (farthest-point start from a seeded first centre)."""
    rng = np.random.default_rng(seed)
    centres = [points[rng.integers(len(points))]]
    for _ in range(1, k):
        d = np.min(((points[:, None, :] - np.array(centres)[None]) ** 2).sum(-1), axis=1)
        centres.append(points[int(np.argmax(d))])
    centres = np.array(centres)
    labels = np.zeros(len(points), dtype=int)
    for _ in range(rounds):
        labels = np.argmin(((points[:, None, :] - centres[None]) ** 2).sum(-1), axis=1)
        moved = np.array([points[labels == i].mean(axis=0) if np.any(labels == i) else centres[i] for i in range(k)])
        if np.allclose(moved, centres):
            break
        centres = moved
    shares = np.bincount(labels, minlength=k) / len(points)
    order = np.argsort(-shares)
    return centres[order], shares[order]


def hue_bin(lab):
    """CIELAB hue family (12 of 30 degrees, family 0 centred on 0 degrees) of one or more Lab colours."""
    lab = np.asarray(lab, dtype=float)
    return (((np.degrees(np.arctan2(lab[..., 2], lab[..., 1])) + 375) % 360) // 30).astype(int)


def hue_ceilings(groups, floor):
    """The chroma ceiling per hue family: the highest the style's own colours reach in that family (p99 of each group of
    pixels, every authored colour; x CHROMA_MARGIN). A family the style never uses gets HUE_NEIGHBOUR of its neighbours'
    ceiling; none is below `floor` (muted colours of any hue are always allowed)."""
    own = np.zeros(12)
    for lab, exact in groups:
        lab = np.asarray(lab, dtype=float).reshape(-1, 3)
        if not len(lab):
            continue
        c, b = chroma(lab), hue_bin(lab)
        for family in range(12):
            hit = c[(b == family) & (c >= HUE_MIN_CHROMA)]
            if len(hit) and (exact or len(hit) >= 50):
                own[family] = max(own[family], float(hit.max() if exact else np.percentile(hit, 99)) * CHROMA_MARGIN)
    out = [max(own[f], HUE_NEIGHBOUR * max(own[(f - 1) % 12], own[(f + 1) % 12]), floor) for f in range(12)]
    return [round(float(v), 1) for v in out]


def gamut_and_palette(lab, exact=None):
    """Lightness range, chroma ceiling (+ margin), palette and accents; `exact`: authored Lab colours that must be inside."""
    lo, hi = np.percentile(lab[:, 0], LIGHTNESS_PERCENTILES)
    ceiling = float(np.percentile(chroma(lab), CHROMA_PERCENTILE))
    if exact is not None and len(exact):
        lo, hi = min(lo, float(exact[:, 0].min())), max(hi, float(exact[:, 0].max()))
        ceiling = max(ceiling, float(chroma(exact).max()))
    centres, shares = kmeans(lab, PALETTE_SIZE)
    gamut = {"lightness": [round(float(lo) - 1, 1), round(float(hi) + 1, 1)], "chroma_max": round(ceiling * CHROMA_MARGIN, 1),
             "chroma_median": round(float(np.median(chroma(lab))), 1)}
    palette = [{"hex": hex_of(lab_to_srgb(c)), "lab": [round(float(v), 1) for v in c], "share": round(float(sh), 3)}
               for c, sh in zip(centres, shares)]
    # Accents: small-share, high-chroma colours (the 5 % most saturated pixels, clustered)
    strong = lab[chroma(lab) >= np.percentile(chroma(lab), 95)]
    accents = []
    if len(strong) >= 20:
        ac, ash = kmeans(strong, 5, seed=11)
        accents = [{"hex": hex_of(lab_to_srgb(c)), "lab": [round(float(v), 1) for v in c]} for c in ac]
    return gamut, palette, accents


def reference_crops():
    """The reference crops the generators name (Builds/Models/*/views.json), each once."""
    seen, crops = set(), []
    for path in sorted(glob.glob(os.path.join(ROOT, "Builds", "Models", "*", "views.json"))):
        with open(path, encoding="utf-8") as f:
            for view in json.load(f)["views"]:
                if view.get("type") != "reference":
                    continue
                key = (view["path"], tuple(view["crop"]))
                if key not in seen and os.path.exists(os.path.join(ROOT, view["path"])):
                    seen.add(key)
                    crops.append(key)
    return crops


def load_sources(images):
    sources = [(p, None) for p in images] if images else reference_crops()
    out = []
    for path, crop in sources:
        image = Image.open(path if os.path.isabs(path) else os.path.join(ROOT, path)).convert("RGB")
        if crop:
            x, y, w, h = crop
            image = image.crop((x, y, x + w, y + h))
        out.append((f"{path}{' crop ' + str(list(crop)) if crop else ''}", image))
    return out


def spec(model):
    with open(os.path.join(ROOT, "Assets", "Opus", "ModelSpecs", model + ".json"), encoding="utf-8") as f:
        return json.load(f)


def built_models():
    return sorted(os.path.basename(p)[:-5] for p in glob.glob(os.path.join(ROOT, "Assets", "Opus", "ModelSpecs", "*.json")))


def surface_colours(s):
    out = []
    for surface in s.get("surfaces", []):
        m = HEX.match(surface["name"])
        if m:
            out.append((surface, srgb_to_lab([int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4)])))
    return out


def atlas_pixels(s, count, rng):
    for key, rel in ((s.get("atlas") or {}).get("textures") or {}).items():
        if "color" in key and os.path.exists(os.path.join(ROOT, rel)):
            a = np.asarray(Image.open(os.path.join(ROOT, rel)).convert("RGB")).reshape(-1, 3)
            a = a[a.sum(axis=1) > 0]
            return a[rng.choice(len(a), size=min(len(a), count), replace=False)]
    return None


def model_colours(models):
    rng = np.random.default_rng(5)
    exact, pixels = [], []
    for model in models:
        s = spec(model)
        exact += [lab for surface, lab in surface_colours(s) if "style exception" not in surface.get("note", "").lower()]
        a = atlas_pixels(s, 8000, rng)
        if a is not None:
            pixels.append(srgb_to_lab(a))
    exact = np.array(exact) if exact else np.zeros((0, 3))
    return (np.concatenate([exact] + pixels) if pixels else exact), exact


def load_style():
    if not os.path.exists(STYLE):
        return {}
    with open(STYLE, encoding="utf-8") as f:
        return json.load(f)


def save_style(style):
    os.makedirs(os.path.dirname(STYLE), exist_ok=True)
    with open(STYLE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(style, f, indent=2, ensure_ascii=False)
        f.write("\n")


def validate(style):
    """Schema 2: every rule has an id, a kind and a check (a gate or "review"); ids are unique."""
    problems = []
    ids = [r.get("id") for r in style.get("rules", [])]
    for r in style.get("rules", []):
        if not r.get("id") or not r.get("text"):
            problems.append(f"a rule without id or text: {r}")
        if r.get("kind") not in KINDS:
            problems.append(f"{r.get('id')}: kind must be one of {KINDS}")
        if not str(r.get("check", "")).strip():
            problems.append(f"{r.get('id')}: no check (name the gate, test or 'review' that enforces it)")
        if r.get("enforce", "error") not in ENFORCE:
            problems.append(f"{r.get('id')}: enforce must be one of {ENFORCE}")
    for miss in style.get("near_misses", []):
        if miss.get("rule") not in ids:
            problems.append(f"near miss {miss.get('variant')}: names no rule of the style ({miss.get('rule')})")
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        problems.append(f"rule ids used twice: {duplicates}")
    for key in ("style_version", "stylisation", "summary"):
        if key not in style:
            problems.append(f"no {key}")
    return problems


# ----------------------------------------------------------------------------------------------------------------------
# extract / report
# ----------------------------------------------------------------------------------------------------------------------

def extract(images):
    style = load_style()
    problems = validate(style)
    if problems:
        sys.exit("style.json: " + "; ".join(problems))
    sources = load_sources(images)
    if len(sources) < 3:
        sys.exit("give at least 3 source images (more is better: 20-50 frames make a stable profile)")
    rng = np.random.default_rng(3)
    pixels, per_image = [], []
    for name, image in sources:
        a = np.asarray(image).reshape(-1, 3)
        pixels.append(a[rng.choice(len(a), size=min(len(a), 6000), replace=False)])
        m = measure(image)
        m["source"] = name
        per_image.append(m)
    lit_lab = srgb_to_lab(np.concatenate(pixels))
    lit_gamut, lit_palette, lit_accents = gamut_and_palette(lit_lab)
    approvals = os.path.join(ROOT, "tools", "blender", "approvals.json")
    approved = sorted(json.load(open(approvals, encoding="utf-8"))) if os.path.exists(approvals) else []
    built = built_models()
    defining = [m for m in approved if m in built] or [m for m in built if m != "calibration"]
    albedo_lab, exact = model_colours(defining)
    albedo_gamut, albedo_palette, albedo_accents = gamut_and_palette(albedo_lab, exact)
    for model in defining:   # a defining model passes its own style
        a = atlas_pixels(spec(model), 20000, np.random.default_rng(1))
        if a is None:
            continue
        lab = srgb_to_lab(a)
        p1, p99 = (float(v) for v in np.percentile(lab[:, 0], (1, 99)))
        albedo_gamut["lightness"] = [round(min(albedo_gamut["lightness"][0], p1 - 1), 1),
                                     round(max(albedo_gamut["lightness"][1], p99 + 1), 1)]
        albedo_gamut["chroma_max"] = round(max(albedo_gamut["chroma_max"], float(np.percentile(chroma(lab), 99)) * CHROMA_MARGIN), 1)
    groups = [(exact, True)] + [(srgb_to_lab(a), False) for a in
                                (atlas_pixels(spec(m), 20000, np.random.default_rng(1)) for m in defining) if a is not None]
    # The floor is the style's median chroma: with twice that (31), the shed's grey-blue siding 2.6 x more saturated (a
    # loud teal, chroma 22) still passed (24 October 2026, the near-miss page)
    albedo_gamut["chroma_floor"] = albedo_gamut["chroma_median"]
    albedo_gamut["chroma_by_hue"] = hue_ceilings(groups, floor=albedo_gamut["chroma_floor"])
    coverage = leave_one_out(per_image)
    style["measured"] = {
        "settings": {"colour": "CIELAB D65 (gamut, value), OKLab (hue)", "detail_resize": f"Pillow BICUBIC, {DETAIL_SIZE} px long side"},
        "lit": {"sources": [m["source"] for m in per_image], "pixels": int(len(lit_lab)), "gamut": lit_gamut,
                "palette": lit_palette, "accents": lit_accents, "profile": profile(per_image),
                "per_image": [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in m.items()} for m in per_image],
                "leave_one_out": {"inside_share": coverage, "median": round(float(np.median(coverage)), 2)}},
        "albedo": {"defined_by": defining, "approved_only": bool(approved), "colours": int(len(albedo_lab)),
                   "gamut": albedo_gamut, "palette": albedo_palette, "accents": albedo_accents},
    }
    save_style(style)
    board(style, [image for _, image in sources])
    p = style["measured"]["lit"]["profile"]
    print(f"lit: lightness {lit_gamut['lightness']}, chroma max {lit_gamut['chroma_max']}; value median "
          f"{p['lightness_median']['median']}, contrast {p['contrast_rms']['median']}, fourier slope {p['fourier_slope']['median']}, "
          f"harmony {p['harmony']}")
    print(f"albedo: lightness {albedo_gamut['lightness']}, chroma max {albedo_gamut['chroma_max']} from {len(defining)} models "
          f"({'approved' if approved else 'all built, none approved yet'})")
    print(f"leave-one-out: median {style['measured']['lit']['leave_one_out']['median']} of an image's measures inside the "
          f"others' band; lowest {min(coverage)} ({per_image[int(np.argmin(coverage))]['source']})")


def board(style, thumbs):
    width, sw = 1600, 98
    rows = (len(thumbs) + 7) // 8
    image = Image.new("RGB", (width, 330 + rows * 200 + 20), (243, 236, 223))
    draw = ImageDraw.Draw(image)
    font = _font(14)
    for row, (kind, label) in enumerate((("lit", "On screen (the sources, lit)"), ("albedo", "Base colours (the style's models)"))):
        m = style["measured"][kind]
        g = m["gamut"]
        y = 8 + row * 160
        draw.text((10, y), f"{label}: lightness {g['lightness'][0]}-{g['lightness'][1]}, chroma at most {g['chroma_max']} "
                           f"(median {g['chroma_median']})", fill=(40, 36, 30), font=font)
        for i, entry in enumerate(m["palette"]):
            x = 10 + i * sw
            draw.rectangle([x, y + 24, x + sw - 8, y + 100], fill=entry["hex"])
            draw.text((x, y + 104), f"{entry['hex']} {entry['share'] * 100:.0f}%", fill=(40, 36, 30), font=font)
    for i, thumb in enumerate(thumbs):
        t = thumb.copy()
        t.thumbnail((190, 190))
        image.paste(t, (10 + (i % 8) * 198, 330 + (i // 8) * 200))
    os.makedirs(OUT, exist_ok=True)
    image.save(BOARD)


def check(model, style):
    """One model's base colours against the albedo envelope: (problems, nearest palette distance, atlas stats)."""
    g = style["measured"]["albedo"]["gamut"]
    lo, hi, cmax = g["lightness"][0], g["lightness"][1], g["chroma_max"]
    palette = np.array([p["lab"] for p in style["measured"]["albedo"]["palette"]])
    by_hue = g.get("chroma_by_hue")
    s = spec(model)
    problems, nearest = [], []
    for surface, lab in surface_colours(s):
        nearest.append(float(np.min(np.linalg.norm(palette - lab, axis=1))))
        out = []
        if chroma(lab) > cmax:
            out.append(f"chroma {chroma(lab):.0f} > {cmax}")
        elif by_hue and chroma(lab) >= HUE_MIN_CHROMA and chroma(lab) > by_hue[int(hue_bin(lab))]:
            out.append(f"chroma {chroma(lab):.0f} > {by_hue[int(hue_bin(lab))]}, the style's ceiling for this hue "
                       f"({int(hue_bin(lab)) * 30} deg)")
        if not lo <= lab[0] <= hi:
            out.append(f"lightness {lab[0]:.0f} outside {lo}-{hi}")
        if out and "style exception" not in surface.get("note", "").lower():
            problems.append(f"{surface['name']}: {', '.join(out)}")
    atlas = None
    a = atlas_pixels(s, 20000, np.random.default_rng(1))
    if a is not None:
        lab = srgb_to_lab(a)
        atlas = {"chroma_p99": round(float(np.percentile(chroma(lab), 99)), 1),
                 "lightness_p1_p99": [round(float(v), 1) for v in np.percentile(lab[:, 0], (1, 99))]}
        if atlas["chroma_p99"] > cmax:
            problems.append(f"atlas: 1 % of its pixels above chroma {atlas['chroma_p99']} > {cmax}")
        if atlas["lightness_p1_p99"][0] < lo or atlas["lightness_p1_p99"][1] > hi:
            problems.append(f"atlas: lightness {atlas['lightness_p1_p99']} outside {lo}-{hi}")
        if by_hue:
            c, b = chroma(lab), hue_bin(lab)
            for family in range(12):
                hit = c[(b == family) & (c >= HUE_MIN_CHROMA)]
                if len(hit) >= 200 and float(np.percentile(hit, 99)) > by_hue[family]:
                    problems.append(f"atlas: chroma {np.percentile(hit, 99):.0f} at {family * 30} deg, above the style's "
                                    f"{by_hue[family]} for this hue")
    version = s.get("style_version")
    if version and version != style.get("style_version"):
        problems.append(f"built for style {version}, the style is now {style.get('style_version')}: rebuild and re-check")
    return problems, (round(max(nearest), 1) if nearest else None), atlas



def model_class(model, style):
    return next((c for c, models in style.get("classes", {}).items() if model in models), None)


def rules_check(model, style):
    """The style's measurable rules beyond colour: (problems, warnings, info). Each finding belongs to a rule, and the
    rule's "enforce" decides whether it fails the run ("error") or is reported ("warn"). A new gate starts as "warn" and
    becomes "error" once its near misses prove it and the user has decided what to do with the assets it flags (the
    research report, step 6).
    - finish.real_material: the finish by kind (style.finish_by_kind): a Rubber surface "glossy", a Glass one "matte" ...;
    - detail.budgets: triangles against the class budget (stylisation.budgets_tris); below the minimum only warns;
    - edges.chamfer: for the classes in chamfer_applies_to, a hard part without a chamfer or outside stylisation.chamfer_mm."""
    s = spec(model)
    found = []   # (rule id, message)
    allowed = style.get("finish_by_kind", {})
    for surface in s.get("surfaces", []):
        if not HEX.match(surface["name"]) or "style exception" in surface.get("note", "").lower():
            continue
        kind, finish = surface["name"].split("_")[0], surface["name"].split("_")[-1]
        if kind in allowed and finish not in allowed[kind]:
            found.append(("finish.real_material",
                          f"{surface['name']}: a {kind} surface is {finish}; the style allows {', '.join(allowed[kind])}"))
    cls = model_class(model, style)
    st = style.get("stylisation", {})
    budget = st.get("budgets_tris", {}).get(cls)
    tris = sum(o.get("triangles", 0) for o in s.get("objects", []))
    warnings = []
    if budget:
        if tris > budget[1]:
            found.append(("detail.budgets", f"{tris:,} triangles, above the {cls} budget {budget[1]:,}"))
        elif tris < budget[0]:
            warnings.append(f"{tris:,} triangles, below the {cls} budget {budget[0]:,} (too coarse for its class?)")
    if cls in st.get("chamfer_applies_to", []):
        band = st.get("chamfer_mm", {}).get("hard_parts")
        skip = {o["name"] for o in s.get("objects", []) if o.get("foliage")} | set(s.get("unchamfered") or {})
        for part, width in (s.get("bevels_mm") or {}).items():
            if part in skip:   # leaves, and parts the generator leaves unchamfered on purpose (part(no_chamfer=why))
                continue
            if width is None:
                found.append(("edges.chamfer", f"{part}: no chamfer (hard parts of a {cls} get {band[0]}-{band[1]} mm)"))
            elif band and not band[0] <= width <= band[1]:
                found.append(("edges.chamfer", f"{part}: chamfer {width} mm outside {band[0]}-{band[1]} mm"))
    enforce = {r["id"]: r.get("enforce", "error") for r in style.get("rules", [])}
    problems = [f"{rule}: {text}" for rule, text in found if enforce.get(rule, "error") == "error"]
    warnings += [f"{rule}: {text}" for rule, text in found if enforce.get(rule, "error") == "warn"]
    return problems, warnings, {"class": cls, "triangles": tris}

def report(models, as_json):
    style = load_style()
    problems = validate(style)
    if problems:
        print("style.json: " + "; ".join(problems))
        return 1
    if "albedo" not in style.get("measured", {}):
        sys.exit("no measured style: run py -3 tools/Style.py extract first")
    results = {}
    for model in [m for m in built_models() if not models or m in models]:
        if model in style.get("exempt", {}):
            if not as_json:
                print(f"{model:12} exempt   {style['exempt'][model]}")
            continue
        problems, distance, atlas = check(model, style)
        rule_problems, warnings, info = rules_check(model, style)
        results[model] = {"outside": problems + rule_problems, "warnings": warnings, "palette_distance_max": distance,
                          "atlas": atlas, **info}
    if as_json:
        print(json.dumps(results))
    else:
        for model, r in results.items():
            print(f"{model:12} {'ok' if not r['outside'] else 'OUTSIDE'}  farthest surface from the palette "
                  f"{r['palette_distance_max']}" + (f", atlas chroma p99 {r['atlas']['chroma_p99']}" if r["atlas"] else "")
                  + "".join(f"\n    {o}" for o in r["outside"]) + "".join(f"\n    warning: {w}" for w in r["warnings"]))
    return 1 if any(r["outside"] for r in results.values()) else 0



PAIR_SIDE = 480        # px: a pair's two frames are measured at this size, with the same filter (same settings)
PAIR_TOLERANCE = 0.5   # of the sources' p10-p90 width: how far a game shot may sit from its reference on one axis


def _pair_image(path):
    image = Image.open(path).convert("RGB")
    image.thumbnail((PAIR_SIDE, PAIR_SIDE), Image.BOX)
    return image


def pair_check(game, reference, prof):
    """One game shot against the reference frame it recreates, on every scalar axis: the difference, and whether it is
    beyond PAIR_TOLERANCE of the sources' own spread on that axis (the spread is what the style allows between images)."""
    g, r = measure(game), measure(reference)
    axes, outside = {}, []
    for key in SCALARS:
        width = prof[key]["p90"] - prof[key]["p10"]
        tolerance = max(width * PAIR_TOLERANCE, 1e-3)
        delta = g[key] - r[key]
        axes[key] = {"reference": round(r[key], 3), "game": round(g[key], 3), "delta": round(delta, 3),
                     "tolerance": round(tolerance, 3)}
        if abs(delta) > tolerance:
            outside.append(key)
    return axes, outside, g, r


def game_shots(style):
    """The game's shots of the style's pairs (style.in_game.pairs): each against its own reference frame, both measured
    at the same size (pair_check). Warn-only: the light-aware check of colour.atmosphere (the research report, step 5);
    it says where the game's light and post-processing move the picture away from the source, not which asset is wrong."""
    prof = style["measured"]["lit"]["profile"]
    rows = []
    for pair in style.get("in_game", {}).get("pairs", []):
        game, ref = os.path.join(ROOT, pair["game"]), os.path.join(ROOT, pair["reference"])
        missing = [p for p, full in ((pair["game"], game), (pair["reference"], ref)) if not os.path.exists(full)]
        if missing:
            rows.append({"label": pair["label"], "missing": missing})
            continue
        axes, outside, g, r = pair_check(_pair_image(game), _pair_image(ref), prof)
        rows.append({"label": pair["label"], "game": pair["game"], "reference": pair["reference"], "outside": outside,
                     "axes": axes, "game_shadow": g["shadow_colour"], "reference_shadow": r["shadow_colour"],
                     "game_harmony": g["harmony"]["template"], "reference_harmony": r["harmony"]["template"]})
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "game_shots.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(rows, f, indent=1)
    measured = [r for r in rows if not r.get("missing")]
    close = sum(1 for r in measured if not r["outside"])
    print(f"game shots: {close}/{len(measured)} pairs within tolerance of their reference (warning only)"
          + "".join(f"\n    {r['label']}: " + "; ".join(f"{k} {r['axes'][k]['reference']} -> {r['axes'][k]['game']}"
                                                         for k in r["outside"]) for r in measured if r["outside"])
          + "".join(f"\n    {r['label']}: missing {', '.join(r['missing'])}" for r in rows if r.get("missing")))
    return rows

def brief(name, cls):
    """The brief a new asset starts from (the research report, step 8): the style in one page, for its class."""
    style = load_style()
    st = style["stylisation"]
    albedo = style["measured"]["albedo"]
    floor = st["detail_floor_m"].get(cls, st["detail_floor_m"].get("prop"))
    lines = [f"# Brief: {name} ({cls})", "", f"**The style:** {style['summary']}", "",
             f"- Anchor: {st['anchor']}", f"- Tie-breaker: {st['tie_breaker']}",
             f"- Detail floor for a {cls}: {floor} m; smaller features are painted or left out",
             f"- Triangle budget: {st['budgets_tris'].get(cls, '(no budget for this class: add one)')}",
             f"- Chamfers on hard parts: {st['chamfer_mm']['hard_parts']} mm" + (" (checked)" if cls in st.get("chamfer_applies_to", []) else ""),
             f"- Base colours inside lightness {albedo['gamut']['lightness']} and chroma at most {albedo['gamut']['chroma_max']}; "
             f"palette: {' '.join(p['hex'] for p in albedo['palette'])}",
             "- Chroma ceiling per hue: " + ", ".join(f"{LAB_HUE_NAMES[i]} {v:g}" for i, v in enumerate(albedo["gamut"].get("chroma_by_hue", []))),
             "- Finishes by kind: " + "; ".join(f"{k} {'/'.join(v)}" for k, v in style.get("finish_by_kind", {}).items()), "",
             "**Rules** (id, kind: what; checked by):", ""]
    lines += [f"- `{r['id']}` ({r['kind']}): {r['text']}; checked by {r['check']}" for r in style["rules"]]
    lines += ["", "**Steps:** research (model-plausibility 2b), then the plan, then block-out: a preview and a decision "
              "(`Review.py decide <m> approve|revise --stage blockout --note \"<view>: ...\"`), then detail, the build (gates), "
              "the review (complex tier), the look-dev lineup and the user's approval."]
    path = os.path.join(OUT, "briefs", name + ".md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print(f"brief: {os.path.relpath(path, ROOT)}")

# ----------------------------------------------------------------------------------------------------------------------
# Art bible
# ----------------------------------------------------------------------------------------------------------------------

def _font(size):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _png(image):
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def _file_png(path, max_side=1400):
    if not os.path.exists(path):
        return None
    image = Image.open(path).convert("RGB")
    image.thumbnail((max_side, max_side))
    return _png(image)


def _swatches(entries, label=True, size=64):
    image = Image.new("RGB", (len(entries) * (size + 6) + 6, size + (22 if label else 6)), (250, 247, 240))
    draw = ImageDraw.Draw(image)
    for i, e in enumerate(entries):
        x = 6 + i * (size + 6)
        draw.rectangle([x, 4, x + size, 4 + size], fill=e["hex"])
        if label:
            draw.text((x, size + 6), e["hex"], fill=(50, 45, 40), font=_font(11))
    return _png(image)


def _notan_strip(sources, height=120):
    """Every source and its three-value notan (dark < L* 35 <= mid < 70 <= light)."""
    tiles = []
    for _, image in sources:
        t = image.copy()
        t.thumbnail((180, height))
        L = srgb_to_lab(np.asarray(t, dtype=float))[..., 0]
        notan = np.where(L < 35, 50, np.where(L < 70, 140, 235)).astype(np.uint8)
        tiles.append((t, Image.fromarray(notan, "L").convert("RGB")))
    width = sum(t.width + 6 for t, _ in tiles) + 6
    strip = Image.new("RGB", (width, height * 2 + 18), (250, 247, 240))
    x = 6
    for t, n in tiles:
        strip.paste(t, (x, 6))
        strip.paste(n, (x, height + 12))
        x += t.width + 6
    return _png(strip)


def _bars(values, labels, colours=None, width=640, height=180, fmt="{:.0%}"):
    image = Image.new("RGB", (width, height + 40), (250, 247, 240))
    draw = ImageDraw.Draw(image)
    n = len(values)
    bw = (width - 20) / n
    top = max(values) or 1
    for i, v in enumerate(values):
        x0 = 10 + i * bw
        h = height * v / top
        draw.rectangle([x0 + 3, 10 + height - h, x0 + bw - 3, 10 + height], fill=(colours[i] if colours else "#8C7F70"))
        draw.text((x0 + 3, height + 14), labels[i], fill=(50, 45, 40), font=_font(10))
        draw.text((x0 + 3, max(0, height - h - 4)), fmt.format(v), fill=(50, 45, 40), font=_font(10))
    return _png(image)


def _silhouettes(folder):
    """Every model's 64 and 32 px silhouettes, enlarged without smoothing (each pixel stays visible), with its name."""
    names = sorted({os.path.basename(p)[4:-7] for p in glob.glob(os.path.join(folder, "sil_*_64.png"))})
    if not names:
        return None
    cell = 300
    sheet = Image.new("RGB", (len(names) * cell, 180), (250, 247, 240))
    draw = ImageDraw.Draw(sheet)
    for i, name in enumerate(names):
        x = i * cell + 10
        for j, size in enumerate((64, 32)):
            path = os.path.join(folder, f"sil_{name}_{size}.png")
            if os.path.exists(path):
                sheet.paste(Image.open(path).convert("RGB").resize((128, 128), Image.NEAREST), (x + j * 140, 10))
        draw.text((x, 146), f"{name}  (64 px | 32 px)", fill=(50, 45, 40), font=_font(13))
    return _png(sheet)


def _stack(paths, width=1400):
    images = []
    for path in paths:
        if os.path.exists(path):
            image = Image.open(path).convert("RGB")
            image.thumbnail((width, 700))
            images.append(image)
    if not images:
        return None
    sheet = Image.new("RGB", (max(i.width for i in images), sum(i.height + 8 for i in images)), (250, 247, 240))
    y = 0
    for image in images:
        sheet.paste(image, (0, y))
        y += image.height + 8
    return _png(sheet)


LAB_HUE_NAMES = ["pink-red", "red", "orange", "yellow", "yellow-green", "green", "teal", "cyan", "sky blue", "blue",
                 "violet", "magenta"]   # CIELAB hue families of 30 degrees, centred on 0, 30, ... degrees (hue_bin)
AXES = {"lightness_median": "overall value", "lightness_p10": "darkest tones (L* p10)", "lightness_p90": "lightest tones (L* p90)",
        "contrast_rms": "contrast", "notan_dark": "share of dark values", "notan_mid": "share of mid values",
        "notan_light": "share of light values", "chroma_median": "overall colour", "chroma_p90": "strongest colours",
        "chroma_dark": "colour in the shadows", "chroma_mid": "colour in the mid values", "chroma_light": "colour in the lights",
        "shadow_shift_a": "light-shadow shift (red-green)", "shadow_shift_b": "light-shadow shift (yellow-blue)",
        "fourier_slope": "detail spectrum slope", "edge_density": "edges", "busyness": "fine detail"}
RED, AMBER, GREEN, ACCENT = (190, 62, 48), (204, 140, 30), (60, 130, 80), (122, 106, 154)


def _jpg(image, quality=84):
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, "JPEG", quality=quality, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()


def _open(path, max_side=None):
    if not path or not os.path.exists(path):
        return None
    image = Image.open(path).convert("RGB")
    if max_side:
        image.thumbnail((max_side, max_side))
    return image


def _callout(image, box, label, colour=RED, below=False):
    """A labelled rectangle on the image, in place; box (x0, y0, x1, y1) in the image's pixels."""
    draw = ImageDraw.Draw(image)
    x0, y0, x1, y1 = (int(v) for v in box)
    draw.rectangle([x0, y0, x1, y1], outline=colour, width=3)
    font = _font(15)
    w = int(draw.textlength(label, font=font)) + 10
    ty = y1 + 3 if below or y0 < 24 else y0 - 23
    ty = min(ty, image.height - 21)
    tx = min(max(0, x0), image.width - w)
    draw.rectangle([tx, ty, tx + w, ty + 20], fill=colour)
    draw.text((tx + 5, ty + 2), label, fill=(255, 255, 255), font=font)


def _model_view(model):
    """A model's first rendered view (Builds/Models/<model>/views.json order)."""
    folder = os.path.join(ROOT, "Builds", "Models", model)
    path = os.path.join(folder, "views.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        for view in json.load(f).get("views", []):
            png = os.path.join(folder, view.get("file", ""))
            if view.get("type") != "reference" and view.get("file") and os.path.exists(png):
                return png
    return None


def _difference_box(a, b):
    """Where two renders of the same camera differ: the box around the strongest 10 % of the difference, and its mean."""
    d = np.abs(np.asarray(a, dtype=float) - np.asarray(b, dtype=float)).mean(axis=2)
    smooth = np.asarray(Image.fromarray(np.clip(d, 0, 255).astype(np.uint8)).filter(ImageFilter.BoxBlur(4)), dtype=float)
    mask = smooth > max(6.0, float(np.percentile(smooth, 90)))
    ys, xs = np.nonzero(mask)
    if len(xs) < 50:
        return None, float(d.mean())
    return (np.percentile(xs, 1), np.percentile(ys, 1), np.percentile(xs, 99), np.percentile(ys, 99)), float(d.mean())


def _saturated_caught(model, style, factor=2.6):
    """The oversaturated near miss against the colour gate: the model's authored colours with factor x the saturation
    (as tools/blender/lookdev.py renders it), how many of them check() rejects."""
    import colorsys
    g = style["measured"]["albedo"]["gamut"]
    by_hue = g.get("chroma_by_hue")
    colours = [surface_name for surface_name in (s["name"] for s in spec(model).get("surfaces", [])) if HEX.match(surface_name)]
    caught = 0
    for name in colours:
        hexes = HEX.match(name).group(1)
        r, gg, b = (int(hexes[i:i + 2], 16) / 255 for i in (0, 2, 4))
        h, s_, v = colorsys.rgb_to_hsv(r, gg, b)
        lab = srgb_to_lab(np.array(colorsys.hsv_to_rgb(h, min(1.0, s_ * factor), v)) * 255)
        c = chroma(lab)
        caught += c > g["chroma_max"] or bool(by_hue and c >= HUE_MIN_CHROMA and c > by_hue[int(hue_bin(lab))])
    return caught, len(colours)


def _hue_ceiling_chart(ceilings, floor, width=720, height=170):
    image = Image.new("RGB", (width, height + 46), (250, 247, 240))
    draw = ImageDraw.Draw(image)
    top = max(ceilings) or 1
    bw = (width - 20) / 12
    for i, v in enumerate(ceilings):
        x0 = 10 + i * bw
        h = height * v / top
        colour = tuple(int(c) for c in lab_to_srgb([60.0, 45 * math.cos(math.radians(i * 30)), 45 * math.sin(math.radians(i * 30))]))
        draw.rectangle([x0 + 3, 10 + height - h, x0 + bw - 3, 10 + height], fill=colour if v > floor else (205, 199, 188))
        draw.text((x0 + 3, max(0, height - h - 6)), f"{v:g}", fill=(50, 45, 40), font=_font(11))
        draw.text((x0 + 3, height + 14), LAB_HUE_NAMES[i], fill=(50, 45, 40), font=_font(10))
    return _png(image)


def _tag(text, level):
    return f'<span class="tag {level}">{html.escape(text)}</span>'


def _pair_rows(rows):
    """The axes on which the game moved away from the source in at least half the pairs, with the direction."""
    measured = [r for r in rows if not r.get("missing")]
    moves = {}
    for r in measured:
        for key in r["outside"]:
            moves.setdefault(key, []).append(1 if r["axes"][key]["delta"] > 0 else -1)
    common = []
    for key, signs in sorted(moves.items(), key=lambda kv: -len(kv[1])):
        if len(signs) * 2 >= len(measured) and abs(sum(signs)) == len(signs):
            common.append(f"{AXES.get(key, key)} {'higher' if signs[0] > 0 else 'lower'} in {len(signs)} of {len(measured)}")
    return measured, common


def bible():
    style = load_style()
    problems = validate(style)
    if problems or "lit" not in style.get("measured", {}):
        sys.exit("style.json: " + "; ".join(problems or ["not measured: run extract first"]))
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import Review
    Review.ROOT = ROOT
    sources = load_sources([])
    lit, albedo = style["measured"]["lit"], style["measured"]["albedo"]
    p = lit["profile"]
    st = style["stylisation"]
    notes = style.get("notes", {})
    rules = {r["id"]: r for r in style["rules"]}
    lookdev = os.path.join(OUT, "lookdev")
    hue_colours = ["#C8504A", "#D9893F", "#D8C24A", "#A7C04A", "#5FA455", "#4FA392", "#4FA3B8", "#5A8CC8", "#5A66C0",
                   "#7E5DB8", "#A65AA8", "#C85A8C"]

    def num(key, unit=""):
        v = p[key]
        return f"{v['median']}{unit} (IQR {v['p25']}–{v['p75']})"

    def img(src, alt, caption=""):
        if not src:
            return '<p class="missing">(not rendered yet: tools/LookDev.ps1)</p>'
        cap = f"<figcaption>{caption}</figcaption>" if caption else ""
        return f'<figure><img src="{src}" alt="{html.escape(alt)}">{cap}</figure>'

    def prose(key):
        return f'<p class="prose">{html.escape(notes[key])}</p>' if notes.get(key) else ""

    def table(group):
        rows = [r for r in style["rules"] if r["id"].split(".")[0] == group]
        return ("<table><tr><th>Rule</th><th>What</th><th>Kind</th><th>Checked by</th></tr>"
                + "".join(f"<tr><td><code>{html.escape(r['id'])}</code></td><td>{html.escape(r['text'])}</td>"
                          f"<td class='{r['kind']}'>{r['kind']}</td><td>{html.escape(r['check'])}"
                          f"{' (reports only)' if r.get('enforce') == 'warn' else ''}</td></tr>" for r in rows) + "</table>")

    # Every model: class, triangles, gates, review state
    models = {}
    for m in built_models():
        if m in style.get("exempt", {}):
            continue
        colour_problems, distance, _ = check(m, style)
        rule_problems, warnings, info = rules_check(m, style)
        models[m] = {"problems": colour_problems + rule_problems, "warnings": warnings, "state": Review.state(m)["text"], **info}

    # 1-8: the look
    sh_a, sh_b = p["shadow_shift_a"]["median"], p["shadow_shift_b"]["median"]
    shift_dir = ("lights warmer (yellow/red) than shadows" if sh_b > 2 else "lights cooler (blue) than shadows" if sh_b < -2
                 else "lights and shadows the same temperature")
    families = p["hue_families"]
    top_families = sorted(families, key=lambda k: -families[k])[:4]
    harmony_counts = ", ".join(f"{k} ×{v}" for k, v in p["harmony"].items())
    by_hue = albedo["gamut"].get("chroma_by_hue")
    floor = albedo["gamut"].get("chroma_floor", albedo["gamut"]["chroma_median"])
    sections = []
    sections.append(("vision", "1. Vision", prose("vision") + f"""
<dl><dt>Anchor</dt><dd>{html.escape(st['anchor'])}</dd><dt>Tie-breaker</dt><dd>{html.escape(st['tie_breaker'])}</dd>
<dt>Modelled or painted</dt><dd>{html.escape(st['modelled_vs_painted'])}</dd>
<dt>Heroes</dt><dd>{', '.join(style.get('heroes', []))}: the assets every new one is compared with</dd></dl>
{img(_jpg(_open(os.path.join(lookdev, 'lineup_large_game.png'), 1400)) if os.path.exists(os.path.join(lookdev, 'lineup_large_game.png')) else None,
     'the style at a glance', 'The style at a glance: the large assets in the game light (look-dev scene, Blender).')}
<p class="sub">Style version <b>{html.escape(style['style_version'])}</b>, measured from {len(lit['sources'])} source crops and
{len(albedo['defined_by'])} models ({'approved' if albedo['approved_only'] else 'all built; none approved yet'}).</p>"""))
    sections.append(("value", "2. Value structure (notan)", prose("value") + f"""
<p>Every source on top, its three-value notan below (dark &lt; L* 35 ≤ mid &lt; 70 ≤ light). Dark {num('notan_dark')},
mid {num('notan_mid')}, light {num('notan_light')} of the pixels; median lightness {num('lightness_median')}, RMS contrast
{num('contrast_rms')} (L* units).</p>{img(_notan_strip(sources), 'notan')}"""))
    sections.append(("colour", "3. Colour: palettes and gamut", prose("colour") + f"""
<div class="two"><div><h3>On screen</h3><p>The lit sources: lightness {lit['gamut']['lightness'][0]}–{lit['gamut']['lightness'][1]},
chroma at most {lit['gamut']['chroma_max']} (median {lit['gamut']['chroma_median']}).</p>{img(_swatches(lit['palette'], size=48), 'lit palette')}
<p>Accents, the most saturated 5 %:</p>{img(_swatches(lit['accents'], size=48), 'accents')}</div>
<div><h3>Base colours</h3><p>What the models are painted with (the light and the haze soften them on screen): lightness
{albedo['gamut']['lightness'][0]}–{albedo['gamut']['lightness'][1]}, chroma at most {albedo['gamut']['chroma_max']}.</p>
{img(_swatches(albedo['palette'], size=48), 'albedo palette')}</div></div>
<h3>How saturated each hue may be</h3>
<p>A base colour may be as saturated as the style's own colours of that hue get (×{CHROMA_MARGIN}); a hue the style never uses
gets {HUE_NEIGHBOUR:.0%} of its neighbours', and muted colours (chroma up to {floor:.0f}, grey bars) are always allowed.
<code>Style.py report</code> fails a surface above its hue's ceiling unless its note says <i>style exception: why</i>.</p>
{img(_hue_ceiling_chart(by_hue, floor) if by_hue else None, 'chroma ceiling per hue')}"""))
    sections.append(("hue", "4. Hue families and harmony", prose("hue") + f"""
<p>Hue families of the sources (OKLCh, weighted by chroma): mostly {', '.join(top_families)}. Harmony template per source
(Cohen-Or 2006): {harmony_counts}. Saturation by value: dark {num('chroma_dark')}, mid {num('chroma_mid')}, light {num('chroma_light')}.</p>
{img(_bars(list(families.values()), list(families.keys()), hue_colours), 'hue families')}"""))
    sections.append(("light", "5. Light: shadow and light colour", prose("light") + f"""
<p>The lightest fifth of each source against its darkest fifth: {shift_dir} (Δa {sh_a}, Δb {sh_b} in CIELAB). Shadow colours
of the sources on top, their light colours below:</p>
{img(_swatches([{'hex': m['shadow_colour']} for m in lit['per_image']], label=False, size=36), 'shadow colours')}
{img(_swatches([{'hex': m['light_colour']} for m in lit['per_image']], label=False, size=36), 'light colours')}"""))
    sections.append(("detail", "6. Detail and edges", prose("detail") + f"""
<p>Fourier amplitude slope {num('fourier_slope')} (natural scenes about 1.2; steeper is calmer); edge density {num('edge_density')};
busyness {num('busyness')} (L* std in 5 px windows at {DETAIL_SIZE} px). Detail floor:
{', '.join(f'{k} {v * 1000:g} mm' for k, v in st['detail_floor_m'].items())}; chamfers on hard parts {st['chamfer_mm']['hard_parts'][0]}–{st['chamfer_mm']['hard_parts'][1]} mm.</p>"""
                     + table("detail") + table("edges")))
    sections.append(("shape", "7. Shape and silhouettes", prose("shape") + f"""
<p>Each model as a black silhouette at 64 and 32 px, enlarged without smoothing.</p>{img(_silhouettes(lookdev), 'silhouettes')}"""
                     + table("shape")))
    finish_rows = "".join(f"<tr><td>{html.escape(k)}</td><td>{', '.join(v)}</td></tr>" for k, v in style.get("finish_by_kind", {}).items())
    sections.append(("materials", "8. Materials and finish", prose("materials") + f"""
{img(_jpg(_open(os.path.join(lookdev, 'spheres.png'), 1400)) if os.path.exists(os.path.join(lookdev, 'spheres.png')) else None,
     'material spheres', 'Every surface of the models as a sphere in neutral light: base colour, finish and grain.')}
<h3>Finish by kind</h3><p>A surface's finish must be one its kind allows (<code>Style.py report</code>, rule <code>finish.real_material</code>).</p>
<table><tr><th>Kind</th><th>Finishes</th></tr>{finish_rows}</table>""" + table("surfaces") + table("finish") + table("colour")))

    # 9. The lineup, labelled
    def lineup(name):
        path = os.path.join(lookdev, name + ".png")
        image = _open(path)
        if image is None:
            return None
        labels = json.load(open(path[:-4] + ".json", encoding="utf-8")) if os.path.exists(path[:-4] + ".json") else []
        for i, item in enumerate(sorted(labels, key=lambda l: l["x0"])):
            info = models.get(item["name"])
            text = item["name"] + (f" · {info['triangles'] / 1000:.1f}k" if info else "")
            level = RED if info and info["problems"] else AMBER if info and info["warnings"] else GREEN if info else ACCENT
            _callout(image, (item["x0"], item["y0"], item["x1"], item["y1"]), text, colour=level, below=i % 2 == 1)
        image.thumbnail((1400, 1400))
        return _jpg(image)
    sections.append(("lineup", "9. The lineup", """
<p>All models at true scale beside a 1.8 m person. Label: name and triangles; green inside the style, amber with a warning,
red failing a gate. In neutral light the assets are judged by themselves; in the game light (lavender sky, warm sun) they are
seen as the game shows them, approximated in Blender.</p>"""
                     + img(lineup("lineup_large_neutral"), "lineup large neutral", "Large assets, neutral light.")
                     + img(lineup("lineup_small_neutral"), "lineup small neutral", "Small assets (below 1.5 m), neutral light.")
                     + img(lineup("lineup_large_game"), "lineup large game", "Large assets, the game's light.")
                     + img(lineup("lineup_small_game"), "lineup small game", "Small assets, the game's light.")))

    # 10. Asset classes
    cards = []
    for cls, members in style.get("classes", {}).items():
        budget = st["budgets_tris"].get(cls)
        floor_mm = st["detail_floor_m"].get(cls, st["detail_floor_m"].get("prop"))
        chamfer = cls in st.get("chamfer_applies_to", [])
        items = []
        for m in members:
            info = models.get(m)
            if info is None:
                items.append(f"<div class='card'><b>{m}</b><p class='missing'>not built</p></div>")
                continue
            view = _open(_model_view(m), 360)
            share = min(100, round(100 * info["triangles"] / budget[1])) if budget else 0
            over = budget and info["triangles"] > budget[1]
            status = (_tag("fails a gate", "bad") if info["problems"] else _tag(f"{len(info['warnings'])} warning(s)", "warn")
                      if info["warnings"] else _tag("inside the style", "good"))
            notes_list = "".join(f"<li>{html.escape(t)}</li>" for t in info["problems"] + info["warnings"][:4])
            more = len(info["warnings"]) - 4
            items.append(f"""<div class="card">{f'<img src="{_jpg(view)}" alt="{m}">' if view else ''}<b>{m}</b> {status}
<div class="bar"><span class="{'over' if over else ''}" style="width:{share}%"></span></div>
<p class="small">{info['triangles']:,} triangles{f' of {budget[1]:,}' if budget else ''} · {html.escape(info['state'])}</p>
{f'<ul class="small">{notes_list}{f"<li>… {more} more</li>" if more > 0 else ""}</ul>' if notes_list else ''}</div>""")
        cards.append(f"""<h3>{cls}</h3><p>Budget {f'{budget[0]:,}–{budget[1]:,}' if budget else '(none)'} triangles · detail floor
{floor_mm * 1000:g} mm{f" · chamfers {st['chamfer_mm']['hard_parts'][0]}–{st['chamfer_mm']['hard_parts'][1]} mm on hard parts (checked)" if chamfer else ''}</p>
<div class="grid">{''.join(items)}</div>""")
    exempt = "".join(f"<li><b>{html.escape(k)}</b>: {html.escape(v)}</li>" for k, v in style.get("exempt", {}).items())
    sections.append(("classes", "10. Asset classes", prose("classes") + "".join(cards)
                     + (f"<p>Outside the style (exempt):</p><ul>{exempt}</ul>" if exempt else "")))

    # 11. Do and don't
    blocks = []
    prof = lit["profile"]
    for near in style.get("lookdev", {}).get("near_miss_models", []):
        base_path = os.path.join(lookdev, f"near_{near}_style.png")
        base = _open(base_path)
        if base is None:
            continue
        tiles = [f'<div class="card do">{img(_jpg(base), "the style", f"<b>Do:</b> {near} in the style")}</div>']
        for miss in style.get("near_misses", []):
            path = os.path.join(lookdev, f"near_{near}_{miss['variant']}.png")
            image = _open(path)
            if image is None:
                continue
            rule = rules.get(miss["rule"], {})
            box, mean = _difference_box(base, image)
            if box:
                _callout(image, box, miss["rule"], colour=RED)
            _, outside, _, _ = pair_check(_pair_image(path), _pair_image(base_path), prof)
            seen = (f"the measured look check sees {', '.join(AXES.get(k, k) for k in outside[:4])}" if outside
                    else "the measured look check does not see it: the review must")
            gate = ""
            if miss["variant"] == "oversaturated" and spec(near).get("surfaces"):
                caught, total = _saturated_caught(near, style)
                gate = f" <code>Style.py report</code> rejects {caught} of its {total} base colours."
            tiles.append(f"""<div class="card dont">{img(_jpg(image), miss['variant'], f"<b>Don't:</b> {html.escape(miss['what'])}")}
<p class="small">Breaks <code>{html.escape(miss['rule'])}</code> ({html.escape(rule.get('text', ''))}); caught by
{html.escape(rule.get('check', ''))}.{gate} Against the style render: {mean:.1f} levels of 255 on average; {html.escape(seen)}.</p></div>""")
        blocks.append(f"<h3>{near}</h3><div class='grid'>{''.join(tiles)}</div>")
    sections.append(("dodont", "11. Do and don't", prose("do_dont") + ("".join(blocks) or '<p class="missing">(no near misses rendered yet: tools/LookDev.ps1)</p>')))

    # 12. In the game
    shots_path = os.path.join(OUT, "game_shots.json")
    rows = json.load(open(shots_path, encoding="utf-8")) if os.path.exists(shots_path) else game_shots(style)
    measured, common = _pair_rows(rows)
    pairs = []
    for r in measured:
        ref, game = _open(os.path.join(ROOT, r["reference"]), 640), _open(os.path.join(ROOT, r["game"]), 640)
        off = "".join(f"<tr><td>{AXES.get(k, k)}</td><td>{r['axes'][k]['reference']}</td><td>{r['axes'][k]['game']}</td>"
                      f"<td>±{r['axes'][k]['tolerance']}</td></tr>" for k in r["outside"])
        pairs.append(f"""<h3>{html.escape(r['label'])} {_tag('close to the source', 'good') if not r['outside'] else _tag(f"{len(r['outside'])} axes off", 'warn')}</h3>
<div class="two">{img(_jpg(ref) if ref else None, 'reference', 'The trailer')}{img(_jpg(game) if game else None, 'game', 'The game')}</div>
{f'<table><tr><th>Axis</th><th>Trailer</th><th>Game</th><th>Allowed</th></tr>{off}</table>' if off else ''}""")
    close = sum(1 for r in measured if not r["outside"])
    summary = (f"<p><b>{close} of {len(measured)}</b> game shots are within tolerance of their trailer frame on every axis "
               f"(tolerance: half the spread of the sources on that axis; <code>Style.py shots</code>, reported, never failing)."
               + (f" Across the pairs: {html.escape('; '.join(common))}." if common else "") + "</p>")
    sections.append(("game", "12. In the game", prose("in_game") + summary + "".join(pairs)))

    # 13. The process
    log_rows = []
    for m in models:
        entries = Review.decisions(m)
        if entries:
            last = "; ".join(f"{e['stage']} round {e['round']}: {e['decision']}" for e in entries[-4:])
            log_rows.append(f"<tr><td>{m}</td><td>{html.escape(last)}</td></tr>")
    sections.append(("process", "13. Making a new asset", f"""
<ol class="steps">
<li><b>Brief.</b> <code>py -3 tools/Style.py brief NAME --class CLASS</code>: this style in one page for the class (budget, detail
floor, chamfers, colours, finishes, rules).</li>
<li><b>Research and plan</b> (skill model-plausibility): how such an object is built and modelled; components, supports, features.</li>
<li><b>Block-out.</b> <code>tools/Models.ps1 -Only NAME -Preview</code>, then one decision:
<code>py -3 tools/Review.py decide NAME approve|revise|escalate --stage blockout --note "VIEW: what"</code>. A revision says
where; after {Review.MAX_ROUNDS} revisions the user decides.</li>
<li><b>Detail and build.</b> The gates run in <code>tools/Verify.ps1</code>: construction, colours and finishes, budgets, chamfers.</li>
<li><b>Review</b> (complex models): the pack carries the style board, the heroes and the near misses; a "style:" finding must name
a pack image and a place in it.</li>
<li><b>Look.</b> <code>tools/LookDev.ps1</code>: the new asset in the lineup beside the heroes, in both lights.</li>
<li><b>Approval</b> by the user (<code>tools/Verify.ps1 -Approve NAME</code>) and the final decision (<code>--stage final</code>).</li>
</ol>
<h3>Decisions so far</h3>""" + (f"<table><tr><th>Model</th><th>Last rounds</th></tr>{''.join(log_rows)}</table>" if log_rows
                               else '<p class="missing">No decisions recorded yet: the log starts with the next asset.</p>')))

    # 14. Checks and history
    all_rules = "".join(f"<tr><td><code>{html.escape(r['id'])}</code></td><td class='{r['kind']}'>{r['kind']}</td>"
                        f"<td>{'reports' if r.get('enforce') == 'warn' else 'fails'}</td><td>{html.escape(r['check'])}</td></tr>"
                        for r in style["rules"])
    lo_cov = min(lit["leave_one_out"]["inside_share"])
    sections.append(("checks", "14. Checks, budgets and history", f"""
<table><tr><th>Rule</th><th>Kind</th><th>A gate</th><th>Checked by</th></tr>{all_rules}</table>
<table><tr><th>Class</th><th>Triangles</th><th>Detail floor</th></tr>"""
                     + "".join(f"<tr><td>{k}</td><td>{v[0]:,}–{v[1]:,}</td><td>{(st['detail_floor_m'].get(k) or st['detail_floor_m'].get('prop')) * 1000:g} mm</td></tr>"
                               for k, v in st["budgets_tris"].items()) + "</table>"
                     + f"<p>Leave-one-out: a source has a median {lit['leave_one_out']['median']:.0%} of its measures inside the "
                       f"other sources' band (lowest {lo_cov:.0%}). More sources make a steadier profile: 20–50 frames.</p>"
                     + "<ul>" + "".join(f"<li><b>{html.escape(h['date'])}</b> {html.escape(h.get('version', ''))}: {html.escape(h['change'])}</li>"
                                        for h in style.get("history", [])) + "</ul>"))

    toc = "".join(f'<a href="#{key}">{html.escape(title)}</a>' for key, title, _ in sections)
    body = "".join(f'<section id="{key}"><h2>{html.escape(title)}</h2>{content}</section>' for key, title, content in sections)
    css = """
:root{--bg:#F7F3EA;--ink:#2E2A25;--muted:#6E665C;--line:#DDD3C3;--card:#FFFDF8;--accent:#7A6A9A;--good:#3C8250;--warn:#B07A12;--bad:#B43E30}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#1F1D1A;--ink:#EDE6DA;--muted:#A9A091;--line:#3A352E;--card:#26231F;--accent:#B6A5D6;--good:#7CC08D;--warn:#E0B050;--bad:#E47C6E}}
:root[data-theme="dark"]{--bg:#1F1D1A;--ink:#EDE6DA;--muted:#A9A091;--line:#3A352E;--card:#26231F;--accent:#B6A5D6;--good:#7CC08D;--warn:#E0B050;--bad:#E47C6E}
*{box-sizing:border-box} body{background:var(--bg);color:var(--ink);font:16px/1.55 Georgia,'Times New Roman',serif;margin:0}
main{max-width:1160px;margin:0 auto;padding:24px 16px 64px} h1{font-size:2.1rem;margin:.2em 0}
h2{font-size:1.4rem;border-bottom:1px solid var(--line);padding-bottom:.25em;margin-top:1.4em;color:var(--accent)}
h3{font-size:1.08rem;margin:1.2em 0 .3em}
nav{display:flex;flex-wrap:wrap;gap:6px 14px;font:14px/1.4 system-ui,sans-serif;margin:12px 0 4px} nav a{color:var(--accent);text-decoration:none}
section{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px 20px 18px;margin:18px 0}
figure{margin:10px 0} img{max-width:100%;height:auto;border-radius:6px;display:block}
figcaption{font:13px/1.4 system-ui,sans-serif;color:var(--muted);margin-top:4px}
.prose{font-size:1.06rem;border-left:3px solid var(--accent);padding-left:12px}
table{border-collapse:collapse;width:100%;margin:12px 0;font:14px/1.4 system-ui,sans-serif;display:block;overflow-x:auto}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top} th{color:var(--muted)}
td.invariant{color:var(--bad);font-weight:600} td.tunable{color:var(--good)} code{font-size:.88em;overflow-wrap:anywhere}
dl{display:grid;grid-template-columns:max-content 1fr;gap:4px 16px} dt{color:var(--muted)}
.missing{color:var(--muted);font-style:italic} .sub,.small{color:var(--muted)} .small{font:13px/1.45 system-ui,sans-serif}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px}
.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}
.card{border:1px solid var(--line);border-radius:8px;padding:10px;background:var(--bg)} .card img{margin-bottom:6px}
.card.do{border-color:var(--good)} .card.dont{border-color:var(--bad)}
.tag{font:12px/1 system-ui,sans-serif;padding:3px 7px;border-radius:10px;color:#fff;white-space:nowrap}
.tag.good{background:var(--good)} .tag.warn{background:var(--warn)} .tag.bad{background:var(--bad)}
.bar{height:6px;background:var(--line);border-radius:3px;margin:6px 0 2px;overflow:hidden}
.bar span{display:block;height:100%;background:var(--good)} .bar span.over{background:var(--bad)}
ol.steps li{margin:6px 0}
@media (max-width:600px){dl{grid-template-columns:1fr} section{padding:6px 12px 14px}}
"""
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Art bible</title><style>{css}</style></head><body><main>
<h1>Art bible: {html.escape(style['name'])}</h1>
<p class="sub">Generated by <code>tools/Style.py bible</code> from <code>tools/blender/style/style.json</code> (style
{html.escape(style['style_version'])}, {datetime.date.today().isoformat()}). Every rule names the check that enforces it; every
number is measured from the sources or the models, never typed.</p>
<p class="lead">{html.escape(style['summary'])}</p><nav>{toc}</nav>
{body}</main></body></html>"""
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "art_bible.html")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    print(f"art bible: {os.path.relpath(path, ROOT)} ({len(page) // 1024} KB, {len(sections)} sections; "
          f"{sum(1 for m in models.values() if m['problems'])} models failing a gate, "
          f"{sum(1 for m in models.values() if m['warnings'])} with warnings; game shots {close}/{len(measured)} close)")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=("extract", "report", "validate", "bible", "shots", "brief"))
    parser.add_argument("args", nargs="*")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--class", dest="cls", default="prop")
    a = parser.parse_args()
    if a.action == "shots":
        game_shots(load_style())
        return
    if a.action == "brief":
        if not a.args:
            sys.exit("brief NAME --class CLASS")
        brief(a.args[0], a.cls)
        return
    if a.action == "extract":
        extract(a.args)
    elif a.action == "report":
        sys.exit(report(a.args, a.json))
    elif a.action == "validate":
        problems = validate(load_style())
        print("style.json: " + ("ok" if not problems else "; ".join(problems)))
        sys.exit(1 if problems else 0)
    else:
        bible()


if __name__ == "__main__":
    main()
