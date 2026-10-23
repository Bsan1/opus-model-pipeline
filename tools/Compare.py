"""
Measured comparison of a built model with a reference frame (22 October 2026; after reference-analysis-validator,
blender-kiln's reference fidelity and the low-poly guides, adapted to frames from a video in perspective).

A frame from a game video has an unknown camera, lens and lighting, so no orthographic silhouette IoU and no universal
threshold. Instead:
1. landmarks: points picked on the frame by hand, each with its model point (tools/blender/references/<model>.json);
2. the camera is solved from them (DLT, refined by least squares: focal length, rotation, position; square pixels, the
   principal point in the middle);
3. how well it fits says how far the numbers can be trusted: the reprojection error as a share of the object's height
   in the frame: aligned <= 1.5 %, rough <= 4 %, otherwise poor (advisory only);
4. per landmark, the error when the camera is solved WITHOUT it (leave-one-out): a feature in the wrong place shows up
   as its own error instead of bending the camera;
5. per segment (door width, wall height ...), the model's length in the frame over the reference's, again with the
   camera solved without the segment's two ends;
6. the model is rendered from the solved camera: an overlay (outline, reference points, model points) for the eye;
7. Builds/Models/<model>_compare/compare.json, which tools/Review.py puts into the review pack.
Messages are actionable ("window_top_back: the model's point lands 9 px to the right ..."), marked advisory when the
alignment is not good enough to judge.

Usage: py -3 tools/Compare.py MODEL   (the model must be built: Assets/Opus/Resources/Models/<model>.fbx)
"""
import json
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ALIGNED, ROUGH = 1.5, 4.0       # reprojection RMS, % of the object's height in the frame
LANDMARK_FLAG = 2.0             # % of the object's height: a landmark further off than this (and than 2 x RMS) is reported
SEGMENT_FLAG = 8.0              # %: a length off by more than this is reported (blender-kiln's band-width threshold)


def to_blender(p):
    x, y, z = p
    return np.array([-x, -z, y], dtype=float)


def rodrigues(r):
    theta = np.linalg.norm(r)
    if theta < 1e-12:
        return np.eye(3)
    k = r / theta
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(theta) * K + (1 - math.cos(theta)) * K @ K


def project(params, X, c):
    f, r, t = params[0], params[1:4], params[4:7]
    cam = X @ rodrigues(r).T + t
    return np.stack([f * cam[:, 0] / cam[:, 2] + c[0], f * cam[:, 1] / cam[:, 2] + c[1]], axis=1)


def dlt(X, x):
    rows = []
    for (X1, Y1, Z1), (u, v) in zip(X, x):
        rows.append([X1, Y1, Z1, 1, 0, 0, 0, 0, -u * X1, -u * Y1, -u * Z1, -u])
        rows.append([0, 0, 0, 0, X1, Y1, Z1, 1, -v * X1, -v * Y1, -v * Z1, -v])
    P = np.linalg.svd(np.array(rows))[2][-1].reshape(3, 4)
    M = P[:, :3]
    if np.linalg.det(M) < 0:
        P, M = -P, -M
    # RQ decomposition of M = K R
    q, r = np.linalg.qr(np.flipud(M).T)
    R = np.flipud(q.T)
    K = np.fliplr(np.flipud(r.T))
    signs = np.diag(np.sign(np.diag(K)))
    K, R = K @ signs, signs @ R
    t = np.linalg.solve(K, P[:, 3])
    if np.linalg.det(R) < 0:
        R, t = -R, -t
    return abs(K[0, 0] + K[1, 1]) / 2.0, R, t


def rotation_vector(R):
    angle = math.acos(max(-1.0, min(1.0, (np.trace(R) - 1) / 2)))
    if angle < 1e-9:
        return np.zeros(3)
    v = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]]) / (2 * math.sin(angle))
    return v * angle


def look_at(centre, target, f):
    """Camera parameters looking from centre at target (world up +Z; OpenCV axes: y down)."""
    z = (target - centre) / np.linalg.norm(target - centre)
    x = np.cross(z, [0.0, 0.0, 1.0])
    x = x / (np.linalg.norm(x) or 1.0)
    y = np.cross(z, x)
    R = np.array([x, y, z])
    return np.concatenate([[f], rotation_vector(R), -R @ centre])


def refine(params, X, x, c, fixed_focal):
    lam = 1e-3
    free = range(1, 7) if fixed_focal else range(7)
    for _ in range(200):
        res = (project(params, X, c) - x).ravel()
        J = np.zeros((res.size, 7))
        for k in free:
            step = np.zeros(7)
            step[k] = 1e-6 * max(1.0, abs(params[k]))
            J[:, k] = ((project(params + step, X, c) - x).ravel() - res) / step[k]
        A = J.T @ J
        delta = np.linalg.lstsq(A + lam * np.diag(np.diag(A) + 1e-12), -J.T @ res, rcond=None)[0]
        trial = params + delta
        if np.sum((project(trial, X, c) - x) ** 2) < np.sum(res ** 2):
            params, lam = trial, lam * 0.3
            if np.linalg.norm(delta) < 1e-10:
                break
        else:
            lam *= 10
    return params


def error(params, X, x, c):
    return float(np.sum((project(params, X, c) - x) ** 2))


def solve(X, x, c, start=None, focal=None):
    """
    Least-squares camera (Levenberg-Marquardt). From `start` (the full solve: a leave-one-out solve started afresh can
    fall into another minimum), else the best of a DLT start and views from 24 directions round the landmarks (a few
    landmarks nearly in one plane make the DLT degenerate). focal: fixed focal length in pixels (a known game camera).
    """
    if start is not None:
        return refine(np.array(start, dtype=float), X, x, c, focal is not None)
    starts = []
    try:
        f, R, t = dlt(X, x)
        starts.append(np.concatenate([[focal or f], rotation_vector(R), t]))
    except np.linalg.LinAlgError:
        pass
    target = X.mean(axis=0)
    size = float(np.linalg.norm(X.max(axis=0) - X.min(axis=0))) or 1.0
    f0 = focal or c[1] * 2.0
    spread = float(np.linalg.norm(x.max(axis=0) - x.min(axis=0))) or 1.0
    distance = f0 * size / spread
    for azimuth in range(0, 360, 30):
        for elevation in (15, 45):
            a, e = math.radians(azimuth), math.radians(elevation)
            offset = np.array([math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)]) * distance
            starts.append(look_at(target + offset, target, f0))
    best = None
    for start in starts:
        if (X @ rodrigues(start[1:4]).T + start[4:7])[:, 2].min() <= 0:
            continue
        params = refine(start, X, x, c, focal is not None)
        if (X @ rodrigues(params[1:4]).T + params[4:7])[:, 2].min() <= 0:
            continue
        if best is None or error(params, X, x, c) < error(best, X, x, c):
            best = params
    return best if best is not None else refine(starts[0], X, x, c, focal is not None)


def find_blender():
    for candidate in (os.environ.get("BLENDER"), r"D:\Steam\steamapps\common\Blender\blender.exe",
                      r"C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe"):
        if candidate and os.path.exists(candidate):
            return candidate
    base = r"C:\Program Files\Blender Foundation"
    for folder in sorted(os.listdir(base), reverse=True) if os.path.isdir(base) else []:
        path = os.path.join(base, folder, "blender.exe")
        if os.path.exists(path):
            return path
    sys.exit("Blender not found; set BLENDER")


def compare(model):
    manifest_path = os.path.join(ROOT, "tools", "blender", "references", model + ".json")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    out_dir = os.path.join(ROOT, "Builds", "Models", model + "_compare")
    os.makedirs(out_dir, exist_ok=True)
    fbx = os.path.join(ROOT, "Assets", "Opus", "Resources", "Models", model + ".fbx")
    results, jobs = [], []
    for comp in manifest["comparisons"]:
        frame_path = os.path.join(ROOT, comp["frame"])
        if not os.path.exists(frame_path):
            results.append({"name": comp["name"], "frame": comp["frame"], "skipped": "reference frame not available"})
            continue
        size = Image.open(frame_path).size
        c = np.array([size[0] / 2.0, size[1] / 2.0])
        ids = [lm["id"] for lm in comp["landmarks"]]
        X = np.array([to_blender(lm["model"]) for lm in comp["landmarks"]])
        x = np.array([lm["image"] for lm in comp["landmarks"]], dtype=float)
        focal = (size[1] / 2.0) / math.tan(math.radians(comp["vfov_deg"]) / 2) if comp.get("vfov_deg") else None
        minimum = 4 if focal else 6
        params = solve(X, x, c, focal=focal)
        proj = project(params, X, c)
        rms = float(np.sqrt(np.mean(np.sum((proj - x) ** 2, axis=1))))
        height = float(x[:, 1].max() - x[:, 1].min()) or 1.0
        rms_pct = rms / height * 100
        alignment = "aligned" if rms_pct <= ALIGNED else "rough" if rms_pct <= ROUGH else "poor"
        advisory = alignment != "aligned" or len(ids) < 8
        poor = alignment == "poor"
        landmarks, messages = [], []
        for i, lid in enumerate(ids):
            keep = [k for k in range(len(ids)) if k != i]
            loo = project(solve(X[keep], x[keep], c, params, focal), X[i:i + 1], c)[0] if len(keep) >= minimum else proj[i]
            d = loo - x[i]
            err = float(np.linalg.norm(d))
            entry = {"id": lid, "error_px": round(err, 1), "error_pct": round(err / height * 100, 1),
                     "dx": round(float(d[0]), 1), "dy": round(float(d[1]), 1),
                     "uncertain": bool(comp["landmarks"][i].get("uncertain"))}
            landmarks.append(entry)
            if not poor and entry["error_pct"] > LANDMARK_FLAG and err > 2 * rms:
                horizontal = "to the right of" if d[0] > 0 else "to the left of"
                vertical = "below" if d[1] > 0 else "above"
                direction = horizontal if abs(d[0]) >= abs(d[1]) else vertical
                messages.append(f"{'advisory: ' if advisory or entry['uncertain'] else ''}{lid}: the model's point lands "
                                f"{err:.0f} px ({entry['error_pct']} % of the height) {direction} the reference point"
                                f"{' (uncertain landmark)' if entry['uncertain'] else ''}")
        segments = []
        for a, b, label in comp.get("segments", []):
            ia, ib = ids.index(a), ids.index(b)
            keep = [k for k in range(len(ids)) if k not in (ia, ib)]
            p = solve(X[keep], x[keep], c, params, focal) if len(keep) >= minimum else params
            pa, pb = project(p, X[[ia, ib]], c)
            ratio = float(np.linalg.norm(pb - pa) / max(np.linalg.norm(x[ib] - x[ia]), 1e-6))
            segments.append({"segment": label, "ratio": round(ratio, 3)})
            if not poor and abs(ratio - 1) * 100 > SEGMENT_FLAG:
                messages.append(f"{'advisory: ' if advisory else ''}{label}: the model's is {ratio * 100:.0f} % of the "
                                f"reference's ({'too long' if ratio > 1 else 'too short'})")
        f, r, t = params[0], params[1:4], params[4:7]
        R = rodrigues(r)
        jobs.append({"name": comp["name"], "width": size[0], "height": size[1], "focal_px": float(f),
                     "R": R.tolist(), "t": t.tolist(), "mask": os.path.join(out_dir, comp["name"] + "_mask.png")})
        results.append({"name": comp["name"], "frame": comp["frame"], "overlay": comp["name"] + "_overlay.png",
                        "alignment": alignment, "advisory": advisory, "rms_px": round(rms, 1), "rms_pct": round(rms_pct, 2),
                        "focal_px": round(float(f), 1), "landmarks": landmarks, "segments": segments,
                        "messages": ([f"the camera could not be solved well from these {len(ids)} landmarks (RMS {rms_pct:.0f} % of the height): no measurement, use the overlay only"] if poor else
                                     messages or ["no landmark or segment off by more than the thresholds"]),
                        "fixed_vfov_deg": comp.get("vfov_deg"),
                        "_proj": proj.tolist(), "_x": x.tolist(), "_ids": ids})
    if jobs:
        job_path = os.path.join(out_dir, "jobs.json")
        with open(job_path, "w", encoding="utf-8") as f:
            json.dump({"fbx": fbx, "jobs": jobs}, f)
        script = os.path.join(ROOT, "tools", "blender", "compare_render.py")
        run = subprocess.run([find_blender(), "-b", "--factory-startup", "--python-exit-code", "1", "--python", script,
                              "--", job_path], capture_output=True, text=True)
        if run.returncode != 0:
            sys.exit("the mask render failed:\n" + run.stderr[-2000:])
    for res in results:
        if "skipped" in res:
            continue
        overlay(res, os.path.join(ROOT, res["frame"]), os.path.join(out_dir, res["name"] + "_mask.png"),
                os.path.join(out_dir, res["overlay"]))
        for key in ("_proj", "_x", "_ids"):
            res.pop(key)
    with open(os.path.join(out_dir, "compare.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"model": model, "comparisons": results}, f, indent=2)
        f.write("\n")
    for res in results:
        if "skipped" in res:
            print(f"{model} {res['name']}: skipped ({res['skipped']})")
            continue
        print(f"{model} {res['name']}: {res['alignment']} (RMS {res['rms_px']} px = {res['rms_pct']} % of the height, "
              f"{len(res['landmarks'])} landmarks); " + "; ".join(res["messages"]))
    return results


def overlay(res, frame_path, mask_path, out_path):
    """The frame, the model's outline from the solved camera, reference points (green) and model points (red)."""
    frame = Image.open(frame_path).convert("RGB")
    mask = np.asarray(Image.open(mask_path).convert("L")) > 127
    edge = mask & ~(np.roll(mask, 1, 0) & np.roll(mask, -1, 0) & np.roll(mask, 1, 1) & np.roll(mask, -1, 1))
    pixels = np.asarray(frame).copy()
    pixels[edge] = (255, 40, 200)
    image = Image.fromarray(pixels)
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 11)
    except OSError:
        font = ImageFont.load_default()
    for lid, (u, v), (pu, pv) in zip(res["_ids"], res["_x"], res["_proj"]):
        draw.ellipse([u - 3, v - 3, u + 3, v + 3], outline=(40, 230, 60), width=2)
        draw.line([pu - 3, pv - 3, pu + 3, pv + 3], fill=(255, 30, 30), width=2)
        draw.line([pu - 3, pv + 3, pu + 3, pv - 3], fill=(255, 30, 30), width=2)
        draw.text((u + 5, v - 6), lid, fill=(255, 255, 255), font=font)
    draw.rectangle([0, 0, frame.width, 16], fill=(0, 0, 0))
    draw.text((4, 2), f"{res['name']}: {res['alignment']}, RMS {res['rms_px']} px ({res['rms_pct']} %); green = reference, "
                      f"red = model, magenta = model outline", fill=(255, 255, 255), font=font)
    image.save(out_path)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("py -3 tools/Compare.py MODEL")
    compare(sys.argv[1])
