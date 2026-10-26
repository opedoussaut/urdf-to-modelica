"""Repair campaign: both arms on a list of cases with one local model, then independent validation and the report.

The base run (Stage 1, Stage 2, frozen faults with their characterisation) is copied once per model into its own run
directory, so a dry run (nemotron) and a measured run (qwen3-coder) never overwrite each other. Resumable: a case whose
two arm records exist is not repeated.

    PYTHONPATH=. python -m kkh.workflow.campaign runs/workflow/<base run> --model qwen3-coder:30b --cases natural,F04,F05
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

from . import faults as F
from . import stage3_repair as s3
from . import stage4_validate as s4


def model_tag(model: str) -> str:
    """Short, readable tag for run folders (Windows path limit): 'qwen3-coder:30b' -> 'qwen3-30b'."""
    name, _, size = model.lower().partition(':')
    head = re.sub(r'[^a-z0-9.]+', '-', name).split('-')[0].replace('.', '')
    return f"{head}-{re.sub(r'[^a-z0-9]+', '', size)}" if size else head


def model_run(base: Path, model: str) -> Path:
    legacy = base.parent / f"{base.name}--{re.sub(r'[^a-z0-9]+', '-', model.lower()).strip('-')}"
    dest = legacy if legacy.exists() else base.parent / f"{base.name}--{model_tag(model)}"
    if not dest.exists():
        shutil.copytree(base, dest, ignore=shutil.ignore_patterns("repair", "validate", "review", "approved", "omc", "excite",
                                                                  "decisions.jsonl"))
        (dest / "campaign.json").write_text(json.dumps({"base": base.name, "model": model}, indent=1), encoding="utf-8")
    return dest


def run(base: Path, model: str, cases: list[str], log=print) -> dict:
    d = model_run(Path(base), model)
    for c in cases:
        for arm in s3.ARMS:
            if (d / "repair" / c / arm / "record.json").exists() and json.loads((d / "repair" / c / arm / "record.json").read_text(encoding="utf-8")).get("final_verdict"):
                log(f"[campaign] {c}/{arm}: already done")
                continue
            try:
                s3.repair(d, c, arm, model, log=log)
            except Exception as exc:  # recorded, the campaign goes on
                (d / "repair" / c / arm).mkdir(parents=True, exist_ok=True)
                (d / "repair" / c / arm / "error.txt").write_text(str(exc), encoding="utf-8")
                log(f"[campaign] {c}/{arm} failed: {exc}")
        s4.validate_case(d, c, log=log)
        s4.report(d, cases)
    rep = s4.report(d, cases)
    write_md(d)
    log(f"[campaign] {model}: {json.dumps(rep['summary'])}")
    return rep


ARM = {"ai_only": "AI only", "ai_assets": "AI + Modelica assets"}


def write_md(run_dir: Path) -> Path:
    """reports/workflow/REPAIR_CAMPAIGN_<model>.md, generated from <run>/validate/report.json (numbers copied, not typed)."""
    run_dir = Path(run_dir)
    rep = json.loads((run_dir / "validate" / "report.json").read_text(encoding="utf-8"))
    model = json.loads((run_dir / "campaign.json").read_text(encoding="utf-8"))["model"]
    root = Path(__file__).resolve().parents[2]
    out = root / "reports" / "workflow" / f"REPAIR_CAMPAIGN_{re.sub(r'[^A-Za-z0-9]+', '_', model)}.md"
    L = [f"# Repair campaign: {model} on the converted ALOHA 2 follower arm",
         "",
         f"Generated {rep['created']} from `runs/workflow/{run_dir.name}/validate/report.json`. "
         f"Fault set {rep['fault_set']['version']} (digest `{rep['fault_set']['digest'][:16]}`), frozen before these runs.",
         "Each arm: same local model, seed 42, temperature 0, same inputs, at most 3 attempts; validated independently.",
         f"Rule: {rep['rule']}.", "", "## Summary", "",
         "| Arm | Cases | Validated | Improved | Regressed | Rejected (integrity) | Faults undone | Findings resolved / new | Seconds |",
         "|---|---|---|---|---|---|---|---|---|"]
    for arm, s in rep["summary"].items():
        L.append(f"| {ARM[arm]} | {s['cases']} | {s['validated']} | {s['improved']} | {s.get('regressed', 0)} | {s['rejected_integrity']} | "
                 f"{s['faults_reverted']} | {s['findings_resolved']} / {s['findings_new']} | {s['seconds']} |")
    L += ["", "## Per case", "", "| Case | Arm | State | Verdict after | Resolved / new | Edits applied / proposed | Integrity flags |",
          "|---|---|---|---|---|---|---|"]
    for c in rep["cases"]:
        name = c["case"] if c["case"] == "natural" else f"{c['case']} {c['fault']['title']}" + (" (held out)" if c["fault"]["held_out"] else "")
        for arm, a in c["arms"].items():
            if a.get("state") == "not run":
                L.append(f"| {name} | {ARM[arm]} | not run | | | | |")
                continue
            L.append(f"| {name} | {ARM[arm]} | {a['state']} | {a['verdict_after']} | {a['findings']['resolved']} / {a['findings']['new']} | "
                     f"{a['edits_applied']} / {a['edits_proposed']} | {len(a['integrity_flags'])} |")
    L += ["", "These numbers describe this model, these cases and these settings only; they are not a general ranking of the two approaches."]
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("base", type=Path)
    ap.add_argument("--model", required=True)
    ap.add_argument("--cases", default="natural," + ",".join(f["id"] for f in F.FAULTS))
    a = ap.parse_args()
    run(a.base, a.model, a.cases.split(","))


if __name__ == "__main__":
    main()
