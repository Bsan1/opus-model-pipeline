"""
The independent plausibility review of a model (.claude/skills/model-plausibility/review.md) and the approval state. A
review never runs inside a build: the numeric gates stay deterministic, an AI judgement is recorded as findings to fix or
dismiss (never as proof), and only the user approves.

Usage:
  py -3 tools/Review.py pack MODEL [--stage preview|final]
      Builds/Review/<model>/: sheet.png (labelled views, material and plan cards), brief.md (purpose, sources, plan, critical
      features, links, gate numbers, the generator's notes, the category guidance, any reference comparison) and
      manifest.json (the pack's id, the model's structure hash, the files' hashes: what exactly is being reviewed).
  py -3 tools/Review.py record MODEL FINDINGS.json --reviewer NAME
      Refuses findings that do not name this pack's id or a pack whose files changed after it was made; then writes
      tools/blender/reviews/<model>.json, tied to the structure that was reviewed.
  py -3 tools/Review.py status MODEL ID fixed|dismissed|open [--by user|auto] [--note "..."]
  py -3 tools/Review.py carry MODEL
      Moves a preview review to the final build only if its structure demonstrably did not change: the same plan, links and
      critical features, the same overall bounds (2 cm) and nearly the same pieces (5 %). Otherwise: review again.
  py -3 tools/Review.py approve MODEL [MODEL ...] [--by NAME]
      The user's approval of the asset as it is now: its asset hash (geometry, UVs, plan, surfaces) and its textures
      (compared with a small tolerance, because a bake may differ by noise).
  py -3 tools/Review.py state [MODEL ...] [--json]
      Each model's state: approved, approval outdated, reviewed, review: N open, review outdated, needs review, not
      approved; plus warnings (open high/medium findings, critical features failing or unverified) that keep an approved
      model from counting as clean.
"""
import argparse
import ast
import datetime
import glob
import hashlib
import json
import os
import shutil
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SEVERITIES = ("high", "medium", "low")
CONFIDENCES = ("high", "low")
STATUSES = ("open", "fixed", "dismissed")
VERDICTS = ("pass", "fail", "unverified")
CARRY_BOUNDS = 0.02    # m: the final's overall bounds may differ this much from the reviewed preview's
CARRY_SHELLS = 0.05    # fraction: and its piece count this much (detail like chamfers adds none; new parts do)
TEXTURE_MEAN = 1.0     # 8-bit levels on a 16 x 16 thumbnail: textures within this are the approved ones
TEXTURE_MAX = 8


def paths():
    """Every path from ROOT (the tests point ROOT at a temporary project)."""
    return {
        "skill": os.path.join(ROOT, ".claude", "skills", "model-plausibility"),
        "reviews": os.path.join(ROOT, "tools", "blender", "reviews"),
        "approvals": os.path.join(ROOT, "tools", "blender", "approvals.json"),
        "models": os.path.join(ROOT, "tools", "blender", "models"),
        "specs": os.path.join(ROOT, "Assets", "Opus", "ModelSpecs"),
        "fbx": os.path.join(ROOT, "Assets", "Opus", "Resources", "Models"),
        "renders": os.path.join(ROOT, "Builds", "Models"),
        "packs": os.path.join(ROOT, "Builds", "Review"),
    }


def sha(data):
    return hashlib.sha1(data if isinstance(data, bytes) else data.encode()).hexdigest()[:16]


def sha_file(path):
    with open(path, "rb") as f:
        return sha(f.read())


def canon(value):
    return sha(json.dumps(value, sort_keys=True))


def read_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")


def spec_path(model, stage):
    if stage == "preview":
        return os.path.join(paths()["renders"], model + "_preview", "spec.json")
    return os.path.join(paths()["specs"], model + ".json")


def load_spec(model, stage, required=True):
    spec = read_json(spec_path(model, stage))
    if spec is None and required:
        sys.exit(f"no {stage} spec for {model} (build it: tools/Models.ps1 -Only {model}"
                 + (" -Preview)" if stage == "preview" else ")"))
    return spec


def bounds(spec):
    objects = spec.get("objects", [])
    if not objects:
        return None
    def xyz(v):   # the spec writes {"x", "y", "z"}
        return [v["x"], v["y"], v["z"]] if isinstance(v, dict) else list(v)

    lo = [min(xyz(o["boundsMin"])[i] + xyz(o["position"])[i] for o in objects) for i in range(3)]
    hi = [max(xyz(o["boundsMax"])[i] + xyz(o["position"])[i] for o in objects) for i in range(3)]
    return [round(v, 4) for v in lo + hi]


def carry_basis(spec):
    """What must stay the same for a preview review to cover the final build."""
    plan = spec.get("plan") or {}
    return {"plan": canon(plan), "links": canon(spec.get("links") or {"routes": [], "attachments": []}),
            "features": canon(spec.get("features") or []), "bounds": bounds(spec),
            "shells": (spec.get("qc", {}).get("construction") or {}).get("shells")}


# ----------------------------------------------------------------------------------------------------------------------
# Pack and record
# ----------------------------------------------------------------------------------------------------------------------

def generator_notes(model):
    path = os.path.join(paths()["models"], model + ".py")
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return ast.get_docstring(ast.parse(f.read())) or ""


def pack(model, stage):
    p = paths()
    spec = load_spec(model, stage)
    sheet = os.path.join(p["renders"], model + ("_preview.png" if stage == "preview" else "_contact.png"))
    if not os.path.exists(sheet):
        sys.exit(f"no sheet: {os.path.relpath(sheet, ROOT)}")
    out = os.path.join(p["packs"], model)
    os.makedirs(out, exist_ok=True)
    for old in glob.glob(os.path.join(out, "*")):
        os.remove(old)
    shutil.copyfile(sheet, os.path.join(out, "sheet.png"))
    files = ["sheet.png"]
    compare = read_json(os.path.join(p["renders"], model + "_compare", "compare.json"))
    if compare:
        for item in compare.get("comparisons", []):
            if "overlay" not in item:   # skipped: the frame is not available (the public repository has none)
                continue
            source = os.path.join(p["renders"], model + "_compare", item["overlay"])
            if os.path.exists(source):
                shutil.copyfile(source, os.path.join(out, item["overlay"]))
                files.append(item["overlay"])
    pack_id = sha(spec.get("structure", "") + "".join(sha_file(os.path.join(out, f)) for f in files) + stage)[:12]
    plan = spec.get("plan")
    lines = [f"# Review brief: {model} ({stage})", "",
             f"**Pack id:** `{pack_id}`: copy it into your JSON as \"pack\".", ""]
    if plan:
        lines += [f"**Purpose:** {plan['purpose']}",
                  "**Sources:** " + "; ".join(f"{s['kind']}: {s['where']}" for s in plan["sources"]),
                  f"**Held by:** {', '.join(plan['supports'])}", "",
                  "| Component | Role | Moves | Seen/guess | Job | Attached to |", "|---|---|---|---|---|---|"]
        lines += [f"| {c['name']} | {c['role']} | {c['moves']} | {c['source']} | {c['job']} | {', '.join(c['attaches'])} |"
                  for c in plan["components"]]
        located = set(spec.get("located") or [])
        unlocated = [c["name"] for c in plan["components"] if c["name"] not in located]
        if located:
            lines += ["", f"**Components without a measured location** (judge them from the renders only): "
                          f"{', '.join(unlocated) or 'none'}"]
    else:
        lines += ["No component plan: judge the object from the sheet and the notes below."]
    features = [f for f in spec.get("features") or [] if f["tier"] in ("critical", "important")]
    if features:
        lines += ["", "**Features you must give a verdict on** (pass / fail / unverified; unverified when the renders do "
                      "not show it):", "", "| Id | Tier | Expected | Measured by the build | Look at |", "|---|---|---|---|---|"]
        lines += [f"| {f['id']} | {f['tier']} | {f['expect']} | {f.get('measured') or 'nothing (visual only)'} | "
                  f"{f.get('view') or 'any view'} |" for f in features]
    links = spec.get("links")
    if links and (links["routes"] or links["attachments"]):
        lines += ["", "**Declared links** (measured: a route's piece reaches every point, an attachment's pieces meet):"]
        lines += [f"- route {r['name']}: {len(r['points'])} points" for r in links["routes"]]
        lines += [f"- attachment {a['name']}" for a in links["attachments"]]
    qc = spec.get("qc", {})
    numbers = [f"{key} {qc[key][label]}" for key, label in (("zFighting", "pairs"), ("holes", "backface_hits"),
                                                           ("joints", "bad")) if key in qc]
    if "construction" in qc:
        c = qc["construction"]
        numbers.append(f"pieces held by nothing {len(c['stray'])} of {c['shells']}, link problems {len(c['problems'])}")
    lines += ["", "**Measured gates (already enforced, do not re-check):** " + ("; ".join(numbers) or "none")]
    if compare:
        lines += ["", "**Reference comparison** (measured; advisory where marked):", ""]
        for item in compare.get("comparisons", []):
            if "overlay" not in item:
                lines += [f"- {item['name']}: {item.get('skipped', 'not compared')}"]
                continue
            lines += [f"- `{item['overlay']}` against {item['frame']}: alignment {item['alignment']} "
                      f"(reprojection {item['rms_px']} px, {item['rms_pct']} % of the object's height)"]
            lines += [f"  - {m}" for m in item.get("messages", [])]
    previous = read_json(os.path.join(p["reviews"], model + ".json"))
    decided = [f for f in (previous or {}).get("findings", []) if f.get("status") in ("dismissed", "fixed")]
    if decided:
        lines += ["", "**Already decided** (do not report these again unless the renders show the model changed there):"]
        lines += [f"- {f['component']}: {f['problem']} ({f['status']}: {f.get('note') or f.get('decided', '')})"
                  for f in decided]
    lines += ["", "**The generator's notes** (what the source shows, what is a guess):", "", "```",
              generator_notes(model).strip(), "```"]
    for category in (plan or {}).get("category", []):
        path = os.path.join(p["skill"], "categories", category + ".md")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                lines += ["", f"**Guidance for {category}:**", "", f.read().strip()]
    with open(os.path.join(out, "brief.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    files.append("brief.md")
    manifest = {"pack": pack_id, "model": model, "stage": stage, "created": datetime.datetime.now().isoformat(timespec="seconds"),
                "structure": spec.get("structure"), "geometry": spec.get("geometry"), "spec": sha_file(spec_path(model, stage)),
                "files": {f: sha_file(os.path.join(out, f)) for f in files}, "basis": carry_basis(spec),
                "features": [f["id"] for f in features]}
    write_json(os.path.join(out, "manifest.json"), manifest)
    print(f"pack {pack_id}: {os.path.relpath(out, ROOT)} ({', '.join(files)}); reviewer instructions: "
          f".claude/skills/model-plausibility/review.md")
    return manifest


def check_findings(data, manifest):
    """The reviewer's JSON against the format and against the pack it claims to review."""
    problems = []
    if not isinstance(data, dict) or data.get("pack") != manifest["pack"]:
        problems.append(f"the findings do not name this pack ({manifest['pack']}): they may be for another pack")
    findings = data.get("findings", []) if isinstance(data, dict) else []
    for i, item in enumerate(findings):
        for key in ("severity", "confidence", "component", "problem", "evidence", "fix"):
            if not str(item.get(key, "")).strip():
                problems.append(f"finding {i}: no {key}")
        if item.get("severity") not in SEVERITIES:
            problems.append(f"finding {i}: severity must be one of {SEVERITIES}")
        if item.get("confidence") not in CONFIDENCES:
            problems.append(f"finding {i}: confidence must be one of {CONFIDENCES}")
    verdicts = {v.get("id"): v for v in (data.get("features", []) if isinstance(data, dict) else [])}
    for fid in manifest.get("features", []):
        v = verdicts.get(fid)
        if v is None or v.get("verdict") not in VERDICTS:
            problems.append(f"feature {fid}: no verdict (pass / fail / unverified)")
    return problems, findings, verdicts


def record(model, findings_file, reviewer):
    p = paths()
    folder = os.path.join(p["packs"], model)
    manifest = read_json(os.path.join(folder, "manifest.json"))
    if manifest is None:
        sys.exit(f"no pack for {model}: run pack first")
    changed = [f for f, h in manifest["files"].items()
               if not os.path.exists(os.path.join(folder, f)) or sha_file(os.path.join(folder, f)) != h]
    if changed:
        sys.exit(f"the pack's files changed after it was made ({', '.join(changed)}): pack again and review again")
    data = read_json(findings_file)
    problems, findings, verdicts = check_findings(data, manifest)
    if problems:
        sys.exit("findings rejected: " + "; ".join(problems))
    for i, item in enumerate(findings):
        item.setdefault("id", f"F{i + 1}")
        item["status"] = item.get("status", "open")
        item.setdefault("decided", "")
    review = {"model": model, "pack": manifest["pack"], "stage": manifest["stage"], "structure": manifest["structure"],
              "basis": manifest["basis"], "reviewer": reviewer, "date": datetime.date.today().isoformat(),
              "findings": findings, "features": [{"id": k, "verdict": v["verdict"], "evidence": v.get("evidence", "")}
                                                 for k, v in verdicts.items()]}
    previous = read_json(os.path.join(p["reviews"], model + ".json"))
    if previous:   # earlier reviews and their decisions stay on record
        history = previous.pop("history", [])
        review["history"] = history + [previous]
    write_json(os.path.join(p["reviews"], model + ".json"), review)
    print(f"recorded pack {manifest['pack']} ({manifest['stage']}, {reviewer}): {len(findings)} findings; features "
          + (", ".join(f"{k} {v['verdict']}" for k, v in verdicts.items()) or "none"))
    return review


def carry(model):
    """A preview review covers the final build only if the structure did not change in a way that matters."""
    p = paths()
    review = read_json(os.path.join(p["reviews"], model + ".json"))
    if review is None:
        sys.exit(f"no review for {model}")
    final = load_spec(model, "final")
    if review.get("structure") == final.get("structure"):
        print(f"{model}: the review already covers this structure")
        return True
    if review.get("stage") != "preview":
        sys.exit(f"{model}: only a preview review can be carried; this one reviewed another final build: review again")
    then, now = review.get("basis") or {}, carry_basis(final)
    reasons = []
    for key in ("plan", "links", "features"):
        if then.get(key) != now[key]:
            reasons.append(f"the {key} changed")
    if then.get("bounds") and now["bounds"]:
        drift = max(abs(a - b) for a, b in zip(then["bounds"], now["bounds"]))
        if drift > CARRY_BOUNDS:
            reasons.append(f"the overall bounds moved {drift * 100:.1f} cm")
    else:
        reasons.append("no bounds to compare")
    if then.get("shells") and now["shells"]:
        change = abs(now["shells"] - then["shells"]) / then["shells"]
        if change > CARRY_SHELLS:
            reasons.append(f"the piece count changed {then['shells']} -> {now['shells']} ({change * 100:.0f} %)")
    else:
        reasons.append("no piece counts to compare")
    if reasons:
        print(f"{model}: not carried ({'; '.join(reasons)}): review the final build")
        return False
    review["carried"] = {"from": review["structure"], "bounds": now["bounds"], "shells": now["shells"]}
    review["structure"] = final.get("structure")
    write_json(os.path.join(p["reviews"], model + ".json"), review)
    print(f"{model}: review carried to the final build (same plan, links and features; bounds within "
          f"{CARRY_BOUNDS * 100:.0f} cm; pieces within {CARRY_SHELLS * 100:.0f} %)")
    return True


# ----------------------------------------------------------------------------------------------------------------------
# Approval and state
# ----------------------------------------------------------------------------------------------------------------------

def texture_files(model, spec):
    """The textures the model is drawn with: its atlas, or the tiling sets its materials use."""
    p = paths()
    if spec.get("atlas"):
        return sorted(os.path.join(ROOT, f) for f in spec["atlas"].get("textures", {}).values())
    if spec.get("tiled"):
        table = read_json(os.path.join(p["fbx"], "Tiling", "tiling.json"), {})
        sets = {table.get("materials", {}).get(m, {}).get("set") for m in table.get("models", {}).get(model, {}).values()}
        return sorted(os.path.join(p["fbx"], "Tiling", f"{s}_{kind}.png") for s in sets if s for kind in ("tone", "normal"))
    return []


def thumbnail(path):
    from PIL import Image
    with Image.open(path) as image:
        return list(image.convert("RGB").resize((16, 16), Image.BOX).tobytes())


def textures_match(approved, current):
    if set(approved) != set(current):
        return False
    for name, thumb in approved.items():
        diffs = [abs(a - b) for a, b in zip(thumb, current[name])]
        if sum(diffs) / len(diffs) > TEXTURE_MEAN or max(diffs) > TEXTURE_MAX:
            return False
    return True


def current_textures(model, spec):
    return {os.path.relpath(f, ROOT).replace("\\", "/"): thumbnail(f) for f in texture_files(model, spec) if os.path.exists(f)}


def approve(models, by):
    p = paths()
    approvals = read_json(p["approvals"], {})
    for model in models:
        spec = load_spec(model, "final")
        if not spec.get("asset"):
            sys.exit(f"{model}: the spec has no asset hash; build it first")
        approvals[model] = {"asset": spec["asset"], "structure": spec.get("structure"), "by": by,
                            "date": datetime.date.today().isoformat(), "textures": current_textures(model, spec)}
        print(f"approved: {model} ({spec['asset']}, by {by})")
    write_json(p["approvals"], dict(sorted(approvals.items())))


def state(model):
    """{"state", "warnings", "clean", "text"} for one model."""
    p = paths()
    spec = load_spec(model, "final", required=False)
    if not spec or not spec.get("structure"):
        return {"state": "not built", "warnings": [], "clean": False, "text": "not built"}
    warnings = []
    approval = (read_json(p["approvals"], {}) or {}).get(model)
    review = read_json(os.path.join(p["reviews"], model + ".json"))
    current = review is not None and review.get("structure") == spec["structure"]
    if current:
        open_findings = [f for f in review["findings"] if f.get("status") == "open"]
        serious = [f for f in open_findings if f.get("severity") in ("high", "medium")]
        if serious:
            warnings.append(f"{len(serious)} open high/medium finding(s)")
    verdicts = {v["id"]: v["verdict"] for v in (review.get("features", []) if current else [])}
    for feature in spec.get("features") or []:
        if feature["tier"] != "critical":
            continue
        if feature.get("measured") == "fail" or verdicts.get(feature["id"]) == "fail":
            warnings.append(f"critical {feature['id']} failing")
        elif verdicts.get(feature["id"]) != "pass":
            warnings.append(f"critical {feature['id']} unverified")
    approved = False
    if approval:
        if approval.get("asset") != spec.get("asset"):
            reason = "approval outdated (geometry, UVs, plan or surfaces changed)"
        elif not textures_match(approval.get("textures", {}), current_textures(model, spec)):
            reason = "approval outdated (textures changed)"
        else:
            approved, reason = True, ""
    if approved:
        name = "approved"
    elif current:
        name = f"review: {len(open_findings)} open" if open_findings else "reviewed"
    elif review is not None:
        name = "review outdated"
    elif (spec.get("plan") or {}).get("tier") == "complex":
        name = "needs review"
    else:
        name = "not approved"
    if approval and not approved:
        warnings.insert(0, reason)
    text = name + (f"; {'; '.join(warnings)}" if warnings else "")
    return {"state": name, "warnings": warnings, "clean": approved and not warnings, "text": text}


def all_models():
    return sorted(os.path.basename(f)[:-3] for f in glob.glob(os.path.join(paths()["models"], "*.py")))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=("pack", "record", "status", "carry", "approve", "state"))
    parser.add_argument("args", nargs="*")
    parser.add_argument("--stage", choices=("preview", "final"), default="final")
    parser.add_argument("--reviewer", default="")
    parser.add_argument("--by", default="")
    parser.add_argument("--note", default="")
    parser.add_argument("--json", action="store_true")
    a = parser.parse_args()
    if a.action == "pack":
        pack(a.args[0], a.stage)
    elif a.action == "record":
        if len(a.args) != 2 or not a.reviewer:
            sys.exit("record MODEL FINDINGS.json --reviewer NAME")
        record(a.args[0], a.args[1], a.reviewer)
    elif a.action == "status":
        if len(a.args) != 3 or a.args[2] not in STATUSES:
            sys.exit(f"status MODEL ID {'|'.join(STATUSES)}")
        path = os.path.join(paths()["reviews"], a.args[0] + ".json")
        review = read_json(path)
        hits = [f for f in (review or {}).get("findings", []) if f["id"] == a.args[1]]
        if not hits:
            sys.exit(f"no finding {a.args[1]} for {a.args[0]}")
        hits[0]["status"], hits[0]["decided"] = a.args[2], a.by or "auto"
        if a.note:
            hits[0]["note"] = a.note
        write_json(path, review)
        print(f"{a.args[0]} {a.args[1]}: {a.args[2]} ({a.by or 'auto'})")
    elif a.action == "carry":
        sys.exit(0 if carry(a.args[0]) else 1)
    elif a.action == "approve":
        approve(a.args, a.by or "user")
    else:
        result = {m: state(m) for m in (a.args or all_models())}
        if a.json:
            print(json.dumps(result))
        else:
            for m, s in result.items():
                print(f"{m:12} {s['text']}")


if __name__ == "__main__":
    main()
