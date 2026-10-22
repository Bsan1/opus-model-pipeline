"""
Review pack for the independent plausibility review of a model (.claude/skills/model-plausibility/review.md), and the
record of what the reviewer found. The review never runs inside a build: the numeric gates stay deterministic, and an AI
judgement is recorded as findings to fix or dismiss, never as proof.

Usage:
  py -3 tools/Review.py pack MODEL [--stage preview|final]
      Builds/Review/<model>/: sheet.png (the contact or preview sheet: labelled views, material card, plan card) and brief.md
      (purpose, sources, plan, links, gate numbers, the reference notes from the generator, the guidance for its category).
      Any reviewer that reads an image and text can take it: a Claude session, another model.
  py -3 tools/Review.py record MODEL FINDINGS.json --reviewer NAME [--stage preview|final]
      Checks the reviewer's findings against the format and writes tools/blender/reviews/<model>.json with the geometry hash
      of what was reviewed (tools/Verify.ps1 shows "reviewed" / "review: N open" while the geometry is unchanged).
  py -3 tools/Review.py status MODEL ID fixed|dismissed|open [--by user|auto] [--note "what was done or why not"]
      Marks a finding.
  py -3 tools/Review.py carry MODEL
      After a preview review, when the final build only added detail: moves the review to the final geometry.
"""
import argparse
import ast
import datetime
import json
import os
import shutil
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKILL = os.path.join(ROOT, ".claude", "skills", "model-plausibility")
REVIEWS = os.path.join(ROOT, "tools", "blender", "reviews")
SEVERITIES = ("high", "medium", "low")
CONFIDENCES = ("high", "low")
STATUSES = ("open", "fixed", "dismissed")


def spec_path(model, stage):
    if stage == "preview":
        return os.path.join(ROOT, "Builds", "Models", model + "_preview", "spec.json")
    return os.path.join(ROOT, "Assets", "Opus", "ModelSpecs", model + ".json")


def sheet_path(model, stage):
    return os.path.join(ROOT, "Builds", "Models", model + ("_preview.png" if stage == "preview" else "_contact.png"))


def load_spec(model, stage):
    path = spec_path(model, stage)
    if not os.path.exists(path):
        sys.exit(f"no {stage} spec for {model}: {os.path.relpath(path, ROOT)} (build it: tools/Models.ps1 -Only {model}"
                 + (" -Preview)" if stage == "preview" else ")"))
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def generator_notes(model):
    path = os.path.join(ROOT, "tools", "blender", "models", model + ".py")
    with open(path, encoding="utf-8") as f:
        return ast.get_docstring(ast.parse(f.read())) or ""


def pack(model, stage):
    spec = load_spec(model, stage)
    plan = spec.get("plan")
    out = os.path.join(ROOT, "Builds", "Review", model)
    os.makedirs(out, exist_ok=True)
    sheet = sheet_path(model, stage)
    if not os.path.exists(sheet):
        sys.exit(f"no sheet: {os.path.relpath(sheet, ROOT)}")
    shutil.copyfile(sheet, os.path.join(out, "sheet.png"))
    lines = [f"# Review brief: {model} ({stage})", ""]
    if plan:
        lines += [f"**Purpose:** {plan['purpose']}",
                  f"**Sources:** " + "; ".join(f"{s['kind']}: {s['where']}" for s in plan["sources"]),
                  f"**Held by:** {', '.join(plan['supports'])}", "",
                  "| Component | Role | Moves | Seen/guess | Job | Attached to |", "|---|---|---|---|---|---|"]
        lines += [f"| {c['name']} | {c['role']} | {c['moves']} | {c['source']} | {c['job']} | {', '.join(c['attaches'])} |"
                  for c in plan["components"]]
    else:
        lines += ["No component plan: judge the object from the sheet and the notes below."]
    links = spec.get("links")
    if links:
        lines += ["", "**Declared links** (measured by the build: a route's piece reaches every point, an attachment meets):"]
        lines += [f"- route {r['name']}: {len(r['points'])} points" for r in links["routes"]]
        lines += [f"- attachment {a['name']}" for a in links["attachments"]]
    qc = spec.get("qc", {})
    numbers = []
    for key, label in (("zFighting", "pairs"), ("holes", "backface_hits"), ("joints", "bad")):
        if key in qc:
            numbers.append(f"{key} {qc[key][label]}")
    if "construction" in qc:
        c = qc["construction"]
        numbers.append(f"pieces held by nothing {len(c['stray'])} of {c['shells']}, link problems {len(c['problems'])}")
    lines += ["", "**Measured gates (already enforced, do not re-check):** " + ("; ".join(numbers) or "none in a preview")]
    lines += ["", "**The generator's notes** (what the source shows, what is a guess):", "", "```",
              generator_notes(model).strip(), "```"]
    for category in (plan or {}).get("category", []):
        path = os.path.join(SKILL, "categories", category + ".md")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                lines += ["", f"**Guidance for {category}:**", "", f.read().strip()]
    lines += ["", f"**Geometry reviewed:** {spec.get('geometry', '?')}"]
    with open(os.path.join(out, "brief.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"pack: {os.path.relpath(out, ROOT)}\\{{sheet.png, brief.md}}; instructions: "
          f"{os.path.relpath(os.path.join(SKILL, 'review.md'), ROOT)}; findings -> py -3 tools/Review.py record {model} FILE")


def record(model, findings_file, reviewer, stage):
    spec = load_spec(model, stage)
    with open(findings_file, encoding="utf-8") as f:
        data = json.load(f)
    findings = data["findings"] if isinstance(data, dict) else data
    problems = []
    for i, item in enumerate(findings):
        for key in ("severity", "confidence", "component", "problem", "evidence", "fix"):
            if not str(item.get(key, "")).strip():
                problems.append(f"finding {i}: no {key}")
        if item.get("severity") not in SEVERITIES:
            problems.append(f"finding {i}: severity must be one of {SEVERITIES}")
        if item.get("confidence") not in CONFIDENCES:
            problems.append(f"finding {i}: confidence must be one of {CONFIDENCES}")
        item.setdefault("id", f"F{i + 1}")
        item["status"] = item.get("status", "open")
        item.setdefault("decided", "")
    if problems:
        sys.exit("findings rejected: " + "; ".join(problems))
    os.makedirs(REVIEWS, exist_ok=True)
    out = {"model": model, "geometry": spec.get("geometry"), "stage": stage, "reviewer": reviewer,
           "date": datetime.date.today().isoformat(), "findings": findings}
    write_review(model, out)
    print(f"recorded {len(findings)} findings for {model} ({stage}, {reviewer}): "
          + ", ".join(f"{f['id']} {f['severity']}/{f['confidence']} {f['component']}" for f in findings))


def read_review(model):
    path = os.path.join(REVIEWS, model + ".json")
    if not os.path.exists(path):
        sys.exit(f"no review for {model}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_review(model, review):
    with open(os.path.join(REVIEWS, model + ".json"), "w", encoding="utf-8") as f:
        json.dump(review, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=("pack", "record", "status", "carry"))
    parser.add_argument("model")
    parser.add_argument("rest", nargs="*")
    parser.add_argument("--stage", choices=("preview", "final"), default="final")
    parser.add_argument("--reviewer", default="")
    parser.add_argument("--by", default="auto")
    parser.add_argument("--note", default="")
    args = parser.parse_args()
    if args.action == "pack":
        pack(args.model, args.stage)
    elif args.action == "record":
        if not args.rest or not args.reviewer:
            sys.exit("record MODEL FINDINGS.json --reviewer NAME")
        record(args.model, args.rest[0], args.reviewer, args.stage)
    elif args.action == "status":
        if len(args.rest) != 2 or args.rest[1] not in STATUSES:
            sys.exit(f"status MODEL ID {'|'.join(STATUSES)}")
        review = read_review(args.model)
        hits = [f for f in review["findings"] if f["id"] == args.rest[0]]
        if not hits:
            sys.exit(f"no finding {args.rest[0]}")
        hits[0]["status"], hits[0]["decided"] = args.rest[1], args.by
        if args.note:
            hits[0]["note"] = args.note
        write_review(args.model, review)
        print(f"{args.model} {args.rest[0]}: {args.rest[1]} ({args.by})")
    else:
        review = read_review(args.model)
        spec = load_spec(args.model, "final")
        review["carried_from"] = review["geometry"]
        review["geometry"] = spec.get("geometry")
        write_review(args.model, review)
        print(f"{args.model}: review carried to the final geometry {review['geometry']}")


if __name__ == "__main__":
    main()
