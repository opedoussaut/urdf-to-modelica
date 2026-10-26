"""Stage 4 - independent validation of the repair candidates, and the comparison report.

For each case (natural conversion or frozen fault) and each arm, the FINAL candidate package is checked again with
exactly the same Stage 2 pipeline as the original (fresh OpenModelica session, nothing reused from the repair loop),
then compared with the original:
  resolved / remaining / new findings (matched by step, check, category, entity and the message with numbers removed)
  compile and simulation success, verdict before and after
  integrity guard: components or connections removed, URDF-copied record values changed, assertions removed,
                   annotation-only edits, files added or deleted - each flag with evidence
  attempts, seconds, tokens (local inference: no monetary cost)
A candidate that compiles only thanks to a flagged change is REJECTED, never counted as a success.
Graphics are measured and reported apart; they never decide the repair verdict.

    PYTHONPATH=. python -m kkh.workflow.stage4_validate runs/workflow/<run> [--cases natural,F01,...]
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import json
import re
from pathlib import Path

from . import faults as F
from . import stage2_check as s2
from .stage3_repair import ARMS, case_paths, in_scope

_NUM = re.compile(r"[-+]?\d+(\.\d+)?(e[-+]?\d+)?")
_PATH = re.compile(r"(?:[A-Za-z]:)?[\\/][^\s\]\)'\"]*[\\/]([^\s\]\)'\"\\/]+)")  # keep only the file name


def key(f: dict) -> tuple:
    """Identity of a finding across copies: no absolute paths (each copy lives elsewhere) and no numbers."""
    ent = (f.get("entity") or "").split(".")[-1].split("/")[-1]
    msg = _PATH.sub(r"\1", f["message"])
    return (f["step"], f["check"], f["category"], ent, _NUM.sub("#", msg))


_GATES = ["fails at load", "fails at structure", "fails at balance_translation", "compiles, does not simulate",
          "simulates, engineering checks fail", "validated"]


def verdict_rank(verdict: str) -> int:
    """How far a package gets: failing at an earlier gate is worse, whatever the finding counts say."""
    return _GATES.index(verdict) if verdict in _GATES else (3 if verdict.startswith("fails at simulation") else -1)


def compare_findings(before: list[dict], after: list[dict]) -> dict:
    """Engineering findings (errors and warnings, graphics excluded) before vs after."""
    b = {key(f): f for f in in_scope_all(before)}
    a = {key(f): f for f in in_scope_all(after)}
    return {"initial": len(b), "remaining": [b[k]["message"] for k in b if k in a],
            "resolved": [b[k] | {"_k": None} for k in b if k not in a], "new": [a[k] for k in a if k not in b]}


def in_scope_all(findings: list[dict]) -> list[dict]:
    return [f for f in findings if f["severity"] in ("error", "warning") and f["step"] != "graphics"]


def _strip_annotations(text: str) -> str:
    out, i = [], 0
    for m in re.finditer(r"annotation\s*\(", text):
        if m.start() < i:
            continue
        out.append(text[i:m.start()])
        depth, j = 0, m.end() - 1
        while j < len(text):
            depth += {"(": 1, ")": -1}.get(text[j], 0)
            if depth == 0:
                break
            j += 1
        i = j + 1
    out.append(text[i:])
    return re.sub(r"\s+", "", "".join(out))  # whitespace-insensitive: layout of the text is not content


def integrity(orig_pkg: Path, cand_pkg: Path, orig_diag: dict, cand_diag: dict) -> list[dict]:
    """Changes that would make a model 'pass' by altering the engineering problem. Each flag carries evidence."""
    flags = []
    of = {p.relative_to(orig_pkg).as_posix(): p for p in orig_pkg.rglob("*.mo")}
    cf = {p.relative_to(cand_pkg).as_posix(): p for p in cand_pkg.rglob("*.mo")}
    for gone in sorted(set(of) - set(cf)):
        flags.append({"flag": "file deleted", "file": gone})
    for new in sorted(set(cf) - set(of)):
        flags.append({"flag": "file added", "file": new})
    for rel in sorted(set(of) & set(cf)):
        a, b = of[rel].read_text(encoding="utf-8"), cf[rel].read_text(encoding="utf-8")
        if a == b:
            continue
        if _strip_annotations(a) == _strip_annotations(b):
            flags.append({"flag": "annotation-only edit", "file": rel})
        for what, rx in (("assertion removed", r"\bassert\s*\("), ("connection removed", r"\bconnect\s*\(")):
            na, nb = len(re.findall(rx, a)), len(re.findall(rx, b))
            if nb < na:
                flags.append({"flag": what, "file": rel, "evidence": f"{na} -> {nb}"})
        decl = lambda t: set(re.findall(r"^\s*(?:Links|Joints)\.\w+\s+(\w+)\s*\(", t, re.M))
        for comp in sorted(decl(a) - decl(b)):
            flags.append({"flag": "component removed", "file": rel, "evidence": comp})
        if re.search(r"AssertionLevel\.\w+", a) and re.findall(r"AssertionLevel\.\w+", a) != re.findall(r"AssertionLevel\.\w+", b):
            flags.append({"flag": "assertion level changed", "file": rel})
    # URDF-copied values that matched before and differ now (the records step compares every value with the URDF)
    before = {key(f) for f in orig_diag["findings"] if f["step"] == "records"}
    for f in cand_diag["findings"]:
        if f["step"] == "records" and key(f) not in before:
            flags.append({"flag": "URDF value changed", "entity": f.get("entity"), "evidence": f"{f['check']}: {f.get('evidence')}"})
    return flags


def diff(orig_pkg: Path, cand_pkg: Path) -> list[dict]:
    out = []
    for p in sorted(cand_pkg.rglob("*.mo")):
        rel = p.relative_to(cand_pkg).as_posix()
        o = orig_pkg / rel
        a = o.read_text(encoding="utf-8").splitlines(keepends=True) if o.exists() else []
        b = p.read_text(encoding="utf-8").splitlines(keepends=True)
        if a != b:
            out.append({"file": rel, "diff": "".join(difflib.unified_diff(a, b, "original/" + rel, "candidate/" + rel, n=2))})
    return out


def validate_case(run_dir: Path, case: str, log=print) -> dict:
    run_dir = Path(run_dir).resolve()
    src_ws, diag_path = case_paths(run_dir, case)
    orig_diag = json.loads(diag_path.read_text(encoding="utf-8"))
    orig_pkg = F.pkg_of(src_ws)
    res = {"case": case, "original": {"verdict": orig_diag["verdict"], "engineering_findings": len(in_scope_all(orig_diag["findings"])),
                                      "graphics": orig_diag["steps"].get("graphics", {}).get("totals")}, "arms": {}}
    if case != "natural":
        res["fault"] = next({k: f[k] for k in ("id", "title", "category", "entity", "held_out")} for f in F.FAULTS if f["id"] == case)
    for arm in ARMS:
        rec_path = run_dir / "repair" / case / arm / "record.json"
        if not rec_path.exists():
            res["arms"][arm] = {"state": "not run"}
            continue
        rec = json.loads(rec_path.read_text(encoding="utf-8"))
        cand_ws = Path(rec["candidate_ws"])
        cand_pkg = F.pkg_of(cand_ws)
        vdir = run_dir / "validate" / case / arm
        stored = vdir / "diagnostics.json"
        from .stage1_convert import _generated_hashes
        if stored.exists() and json.loads(stored.read_text(encoding="utf-8"))["subject"]["files"] == _generated_hashes(cand_pkg):
            log(f"[validate] {case}/{arm}: candidate unchanged since its independent check; reusing it")
            v = json.loads(stored.read_text(encoding="utf-8"))
        else:
            log(f"[validate] {case}/{arm}: independent Stage 2")
            v = s2.run(run_dir, log=lambda *_: None, ws_dir=cand_ws, out_dir=vdir)
        cmp = compare_findings(orig_diag["findings"], v["findings"])
        flags = integrity(orig_pkg, cand_pkg, orig_diag, v)
        changed = diff(orig_pkg, cand_pkg)
        tokens = [a.get("tokens") or {} for a in rec["attempts"]]
        fault_fixed = F.restored(next(f for f in F.FAULTS if f["id"] == case), cand_ws) if case != "natural" else None
        before_rank, after_rank = verdict_rank(orig_diag["verdict"]), verdict_rank(v["verdict"])
        state = ("unchanged" if not changed else
                 "rejected (integrity)" if flags else
                 "validated" if v["verdict"] == "validated" else
                 "regressed" if after_rank < before_rank else
                 "improved" if after_rank > before_rank or len(cmp["resolved"]) > len(cmp["new"]) else "not improved")
        res["arms"][arm] = {
            "state": state, "verdict_before": orig_diag["verdict"], "verdict_after": v["verdict"],
            "compiles": v["steps"].get("balance_translation", {}).get("state") == "pass",
            "simulates": v["steps"].get("simulation", {}).get("state") == "pass",
            "findings": {"initial": cmp["initial"], "resolved": len(cmp["resolved"]), "remaining": len(cmp["remaining"]),
                         "new": len(cmp["new"]), "resolved_list": [f["message"][:160] for f in cmp["resolved"]],
                         "new_list": [{k: f.get(k) for k in ("step", "check", "category", "entity", "message")} for f in cmp["new"]]},
            "fault_text_reverted": fault_fixed,
            "integrity_flags": flags, "files_changed": [c["file"] for c in changed],
            "attempts": len(rec["attempts"]), "seconds": rec.get("seconds"),
            "edits_proposed": sum(len(a["edits"]) for a in rec["attempts"]),
            "edits_applied": sum(e["applied"] for a in rec["attempts"] for e in a["edits"]),
            "citation_flags": sum(len(a.get("citation_flags") or []) for a in rec["attempts"]),
            "chunks_supplied": sum(len(a.get("retrieved") or []) for a in rec["attempts"]),
            "tokens_in": sum((t.get("prompt_eval_count") or 0) for t in tokens), "tokens_out": sum((t.get("eval_count") or 0) for t in tokens),
            "cost": "local inference (no API cost)", "model": rec["model"], "settings_digest": rec["settings_digest"],
            "graphics": v["steps"].get("graphics", {}).get("totals")}
        (run_dir / "validate" / case / arm / "diff.json").write_text(json.dumps(changed, indent=1), encoding="utf-8")
        log(f"[validate]   {state}; resolved {len(cmp['resolved'])}, new {len(cmp['new'])}, flags {len(flags)}")
    out = run_dir / "validate" / case / "comparison.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    return res


def report(run_dir: Path, cases: list[str]) -> dict:
    """Aggregate comparison over the validated cases (written to <run>/validate/report.json)."""
    run_dir = Path(run_dir).resolve()
    rows = []
    for c in cases:
        p = run_dir / "validate" / c / "comparison.json"
        if p.exists():
            rows.append(json.loads(p.read_text(encoding="utf-8")))
    summary = {}
    for arm in ARMS:
        rs = [r["arms"].get(arm, {}) for r in rows if r["arms"].get(arm, {}).get("state") not in (None, "not run")]
        summary[arm] = {"cases": len(rs), "validated": sum(r["state"] == "validated" for r in rs),
                        "rejected_integrity": sum(r["state"].startswith("rejected") for r in rs),
                        "improved": sum(r["state"] == "improved" for r in rs),
                        "regressed": sum(r["state"] == "regressed" for r in rs),
                        "unchanged_or_not_improved": sum(r["state"] in ("unchanged", "not improved") for r in rs),
                        "findings_resolved": sum(r["findings"]["resolved"] for r in rs),
                        "findings_new": sum(r["findings"]["new"] for r in rs),
                        "faults_reverted": sum(1 for r in rs if r.get("fault_text_reverted")),
                        "tokens_out": sum(r["tokens_out"] for r in rs), "seconds": round(sum(r["seconds"] or 0 for r in rs), 1)}
    rep = {"created": dt.datetime.now().isoformat(timespec="seconds"), "fault_set": {"version": F.VERSION, "digest": F.set_digest()},
           "summary": summary, "cases": rows,
           "rule": "validated = the independent Stage 2 passes every engineering step AND no integrity flag; a flagged "
                   "candidate is rejected even if it compiles; graphics never decide the verdict"}
    (run_dir / "validate" / "report.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    return rep


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--cases", default="natural")
    a = ap.parse_args()
    cases = a.cases.split(",")
    for c in cases:
        validate_case(a.run_dir, c)
    print(json.dumps(report(a.run_dir, cases)["summary"], indent=1))


if __name__ == "__main__":
    main()
