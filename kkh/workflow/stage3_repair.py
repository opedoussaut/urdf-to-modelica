"""Stage 3 - two comparable AI repair arms on the SAME converted package and the SAME OpenModelica diagnostics.

  ai_only    URDF + package files + Stage 2 findings + repair rules
  ai_assets  the same, plus Modelica knowledge retrieved per finding from the governed collection (kkh.workflow.assets),
             each chunk with its id, source, version and licence; the model must cite the chunk ids it used

Identical for both arms (recorded in settings, hashed): local model, seed 42, temperature 0, context and output budgets,
attempt limit, the file-selection rule, the rules text, the output schema, and the validation (Stage 2 on the copy).
Graphics findings are not given to either arm: purely cosmetic edits must not change the scientific comparison.

Edits are search/replace blocks on named package files, applied to an isolated copy; a block that does not match
exactly once is recorded as failed, never fixed up. Every prompt, reply, edit, retrieval and validation is kept.
Nothing here touches the Stage 1 package or any approved model.

    PYTHONPATH=. python -m kkh.workflow.stage3_repair runs/workflow/<run> --case natural|F01..F10 [--arms ai_only,ai_assets]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import time
from pathlib import Path

from kkh.convert.llm import repeating
from kkh.convert.sources import prompt_text
from kkh.llm.ollama import Ollama

from . import faults as F
from . import stage2_check as s2

ARMS = ("ai_only", "ai_assets")
SETTINGS = {"seed": 42, "temperature": 0, "max_attempts": 3, "max_output_tokens": 4000, "chars_per_token": 1.6,
            "context_floor": 16384, "file_budget_chars": 26000, "retrieval_per_finding": 3,
            "retrieval_budget_chars": 9000, "max_findings": 8}

RULES = """You repair a Modelica package that a deterministic converter (DLR URDFModelica) generated from a URDF robot
description. OpenModelica and an independent comparison with the URDF produced the findings below.

Rules (a repair that breaks one is rejected, even if the model then compiles):
1. Fix the engineering problems in the findings. Do not delete components, connections, assertions or checks.
2. Do not change values copied from the URDF (masses, centres of mass, inertias, joint origins, axes, limits,
   damping, friction) unless a finding shows the value differs from the URDF; then restore the URDF value.
3. Do not change the robot's architecture (links, joints, their names and how they are connected).
4. No cosmetic or annotation-only edits (layout, colours, comments).
5. Make small edits. Each edit replaces one exact piece of text in one file: `search` must be copied character for
   character from the file shown and must occur exactly once in it.
6. Explain each edit in one sentence and list the finding ids it addresses.
Return JSON only, following the schema."""

ASSETS_RULE = """7. Reference material from the Modelica Standard Library, ModelicaReference and project patterns is given
below, each item with an id. For every edit, list in `cites` the ids of the items you actually used (empty if none).
Do not invent ids. Never take physical values from the reference material: robot values come from the URDF only."""

SCHEMA = {"type": "object", "required": ["edits"], "properties": {"edits": {"type": "array", "items": {
    "type": "object", "required": ["file", "search", "replace", "explanation", "addresses", "cites"],
    "properties": {"file": {"type": "string"}, "search": {"type": "string"}, "replace": {"type": "string"},
                   "explanation": {"type": "string"}, "addresses": {"type": "array", "items": {"type": "string"}},
                   "cites": {"type": "array", "items": {"type": "string"}}}}}}}


def settings_digest(model: str) -> str:
    blob = json.dumps({"settings": SETTINGS, "rules": RULES, "assets_rule": ASSETS_RULE, "schema": SCHEMA, "model": model},
                      sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


# ---------------------------------------------------------------- case inputs

def case_paths(run_dir: Path, case: str) -> tuple[Path, Path]:
    """(workspace to repair, its Stage 2 diagnostics) for the natural conversion or a frozen fault."""
    run_dir = Path(run_dir)
    if case == "natural":
        return F.stage1_ws(run_dir), run_dir / "stage2" / "diagnostics.json"
    if case not in {f["id"] for f in F.FAULTS}:
        raise ValueError(f"unknown case {case}")
    return run_dir / "faults" / case / "ws", run_dir / "faults" / case / "stage2" / "diagnostics.json"


def in_scope(findings: list[dict]) -> list[dict]:
    """Findings given to both arms: errors and warnings, at most max_findings (errors first). Excluded, for both arms
    alike: graphics and rewritten visual mesh paths (drawing only; cosmetic edits must not drive the comparison)."""
    keep = [f for f in findings if f["severity"] in ("error", "warning") and f["step"] != "graphics"
            and not f["message"].startswith("visual mesh URI")]
    keep.sort(key=lambda f: (f["severity"] != "error", f["id"]))
    return keep[:SETTINGS["max_findings"]]


def select_files(pkg_dir: Path, findings: list[dict], mapping: list[dict]) -> list[str]:
    """Same rule for both arms: the main robot model, the test model, every file a finding names, and the model and
    parameter record of every entity a finding names (in that order, within the file budget)."""
    name = pkg_dir.name
    want = [f"{name}.mo", f"{name}Test.mo"]
    for f in findings:
        if f.get("file") and (pkg_dir / f["file"]).exists():
            want.append(f["file"])
    by_entity = {}
    for m in mapping:
        by_entity.setdefault(m["urdf_name"].split("/")[-1], []).extend(x for x in (m["model_file"], m["params_file"]) if x)
    for f in findings:
        for e in re.split(r"[,;]\s*", f.get("entity") or ""):
            want += by_entity.get(e.split(".")[-1].split("/")[-1], [])
    out, used = [], 0
    for w in dict.fromkeys(want):
        size = len((pkg_dir / w).read_text(encoding="utf-8")) if (pkg_dir / w).exists() else 0
        if size and used + size <= SETTINGS["file_budget_chars"]:
            out.append(w)
            used += size
    return out


def _findings_text(findings: list[dict]) -> str:
    keys = ("id", "step", "check", "category", "severity", "entity", "file", "line", "message", "evidence")
    return json.dumps([{k: f.get(k) for k in keys if f.get(k) is not None} for f in findings], indent=1)


def build_messages(arm: str, urdf: Path, pkg_dir: Path, files: list[str], findings: list[dict], retrieved: list[dict],
                   history: list[dict]) -> list[dict]:
    parts = [RULES + ("\n" + ASSETS_RULE if arm == "ai_assets" else ""),
             "## URDF (visual/collision geometry removed)\n" + prompt_text(urdf),
             "## OpenModelica and URDF-consistency findings\n" + _findings_text(findings)]
    if arm == "ai_assets":
        parts.append("## Modelica reference material\n" + "\n\n".join(
            f"[{c['id']}] {c['asset_id']} {c['version']} ({c['licence']}), {c['source_path']}:{c['line_start']}\n{c['text']}"
            for c in retrieved))
    parts.append("## Package files (paths relative to the package)\n" + "\n\n".join(
        f"### {f}\n```modelica\n{(pkg_dir / f).read_text(encoding='utf-8')}\n```" for f in files))
    for h in history:
        parts.append(h)
    return [{"role": "user", "content": "\n\n".join(parts)}]


# ---------------------------------------------------------------- edits

def apply_edits(pkg_dir: Path, edits: list[dict]) -> list[dict]:
    """Apply search/replace edits in order. Paths must stay inside the package; search must match exactly once."""
    out = []
    root = pkg_dir.resolve()
    for i, e in enumerate(edits, 1):
        rec = {"n": i, **{k: e.get(k) for k in ("file", "explanation", "addresses", "cites")}, "applied": False}
        target = (pkg_dir / str(e.get("file", ""))).resolve()
        if root not in target.parents or target.suffix != ".mo" or not target.exists():
            rec["error"] = "file is not a .mo file of this package"
        else:
            text = target.read_text(encoding="utf-8")
            n = text.count(e.get("search") or "\0") if e.get("search") else 0
            if n != 1:
                rec["error"] = f"search text found {n} times"
            elif e["search"] == e.get("replace"):
                rec["error"] = "no change"
            else:
                target.write_text(text.replace(e["search"], e["replace"], 1), encoding="utf-8")
                rec.update(applied=True, search=e["search"], replace=e["replace"])
        out.append(rec)
    return out


def check_citations(edits: list[dict], supplied: set[str]) -> list[dict]:
    """Citations of ids that were not supplied are flagged (the AI-only arm was supplied none)."""
    return [{"edit": e["n"], "invented": [c for c in (e.get("cites") or []) if c not in supplied]}
            for e in edits if [c for c in (e.get("cites") or []) if c not in supplied]]


# ---------------------------------------------------------------- one arm

def repair(run_dir: Path, case: str, arm: str, model: str, log=print, client: Ollama | None = None) -> dict:
    assert arm in ARMS
    run_dir = Path(run_dir).resolve()
    src_ws, diag_path = case_paths(run_dir, case)
    diag = json.loads(diag_path.read_text(encoding="utf-8"))
    st1 = json.loads((run_dir / "stage1" / "manifest.json").read_text(encoding="utf-8"))
    urdf = run_dir / "stage1" / "input" / Path(st1["source"]["urdf"]).name
    out = run_dir / "repair" / case / arm
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    from kkh.workflow import stage1_convert as s1
    from kkh.engineering.urdf_model import load_urdf
    robot = load_urdf(urdf)
    client = client or Ollama(timeout=3600)
    record = {"case": case, "arm": arm, "model": model, "settings": SETTINGS, "settings_digest": settings_digest(model),
              "fault_set": {"version": F.VERSION, "digest": F.set_digest()} if case != "natural" else None,
              "started": dt.datetime.now().isoformat(timespec="seconds"), "initial_verdict": diag["verdict"],
              "attempts": []}
    ws = F.copy_ws(run_dir, out / "ws") if case == "natural" else _copy(src_ws, out / "ws")
    pkg_dir = ws / "URDFModelica" / "Examples" / F.TARGET["package"]
    findings, verdict, history = in_scope(diag["findings"]), diag["verdict"], []
    t0 = time.time()
    try:
        from kkh.workflow import assets as A
        index = A.build() if arm == "ai_assets" else None
    except Exception as exc:  # the assets arm cannot run without its knowledge; say so, never fall back silently
        if arm == "ai_assets":
            raise RuntimeError(f"Modelica asset index unavailable: {exc}") from exc
        index = None
    for attempt in range(1, SETTINGS["max_attempts"] + 1):
        mapping = s1.build_mapping(robot, pkg_dir, pkg_dir / f"{pkg_dir.name}.mo") if (pkg_dir / f"{pkg_dir.name}.mo").exists() else []
        files = select_files(pkg_dir, findings, mapping)
        retrieved, queries = [], []
        if arm == "ai_assets":
            seen, used = set(), 0
            for f in findings:
                r = A.retrieve(f, k=SETTINGS["retrieval_per_finding"], index=index)
                queries.append({"finding": f["id"], "query": r["query"], "chunks": [c["id"] for c in r["chunks"]]})
                for c in r["chunks"]:
                    if c["id"] not in seen and used + len(c["text"]) <= SETTINGS["retrieval_budget_chars"]:
                        seen.add(c["id"])
                        retrieved.append(c)
                        used += len(c["text"])
        messages = build_messages(arm, urdf, pkg_dir, files, findings, retrieved, history)
        prompt_chars = len(messages[0]["content"])
        num_ctx = max(SETTINGS["context_floor"], int(prompt_chars / SETTINGS["chars_per_token"]) + SETTINGS["max_output_tokens"] + 1024)
        num_ctx = (num_ctx + 1023) // 1024 * 1024
        a = {"attempt": attempt, "files_shown": files, "findings_given": [f["id"] for f in findings],
             "retrieval": queries, "retrieved": [{k: c[k] for k in ("id", "asset_id", "version", "licence", "source_path", "line_start", "line_end")} for c in retrieved],
             "prompt_chars": prompt_chars, "num_ctx": num_ctx}
        d = out / f"attempt{attempt}"
        d.mkdir()
        (d / "prompt.md").write_text(messages[0]["content"], encoding="utf-8")
        log(f"[repair] {case}/{arm} attempt {attempt}: {len(findings)} findings, {len(files)} files, {len(retrieved)} chunks, ctx {num_ctx}")
        t = time.time()
        stopped = {"repeat": False}

        def watch(text, n):
            if text and repeating(text):
                stopped["repeat"] = True
                raise RuntimeError("repetition loop")

        try:
            reply = client.chat(messages, model=model, schema=SCHEMA, seed=SETTINGS["seed"],
                                max_tokens=SETTINGS["max_output_tokens"], num_ctx=num_ctx, allow_truncated=True, on_token=watch)
            a.update(seconds_llm=round(time.time() - t, 1), truncated=reply["truncated"], tokens=reply["metrics"])
            (d / "reply.json").write_text(reply["content"], encoding="utf-8")
            try:
                edits = json.loads(reply["content"]).get("edits") or []
            except json.JSONDecodeError as exc:
                edits, a["parse_error"] = [], str(exc)[:200]
        except Exception as exc:
            edits = []
            a.update(seconds_llm=round(time.time() - t, 1), error=("the model was repeating itself" if stopped["repeat"] else str(exc)[:300]))
        a["edits"] = apply_edits(pkg_dir, edits)
        a["citation_flags"] = check_citations(a["edits"], {c["id"] for c in retrieved})
        applied = sum(e["applied"] for e in a["edits"])
        log(f"[repair]   {len(edits)} edits proposed, {applied} applied; validating")
        if applied:
            v = s2.run(run_dir, log=lambda *_: None, ws_dir=ws, out_dir=d / "stage2")
            verdict = v["verdict"]
            findings = in_scope(v["findings"])
            a["validation"] = {"verdict": verdict, "counts": v["counts"], "steps": {k: x.get("state") for k, x in v["steps"].items()}}
        else:
            a["validation"] = {"verdict": verdict, "note": "no edit applied; package unchanged"}
        record["attempts"].append(a)
        (out / "record.json").write_text(json.dumps(record, indent=1, default=str), encoding="utf-8")
        log(f"[repair]   verdict: {verdict}")
        if verdict == "validated":
            break
        failed = [e for e in a["edits"] if not e["applied"]]
        history = ["## Your previous attempt\n" + json.dumps({"applied": [e["n"] for e in a["edits"] if e["applied"]],
                                                                "not_applied": [{"n": e["n"], "file": e["file"], "why": e.get("error")} for e in failed],
                                                                "verdict_after": verdict}, indent=1)
                   + "\nThe files above already include your applied edits. The findings above are the current ones. "
                     "Propose the next edits."]
    record.update(final_verdict=verdict, seconds=round(time.time() - t0, 1), finished=dt.datetime.now().isoformat(timespec="seconds"),
                  candidate_ws=ws.as_posix(), final_diagnostics=(out / f"attempt{len(record['attempts'])}" / "stage2" / "diagnostics.json").as_posix())
    (out / "record.json").write_text(json.dumps(record, indent=1, default=str), encoding="utf-8")
    return record


def _copy(src: Path, dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    return dest


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--case", default="natural")
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--model", default="nemotron-3-nano:4b")
    a = ap.parse_args()
    for arm in a.arms.split(","):
        r = repair(a.run_dir, a.case, arm, a.model)
        print(json.dumps({"case": r["case"], "arm": arm, "final_verdict": r["final_verdict"], "attempts": len(r["attempts"]), "seconds": r["seconds"]}))


if __name__ == "__main__":
    main()
