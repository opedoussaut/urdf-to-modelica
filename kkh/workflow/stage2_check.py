"""Stage 2 - automated OpenModelica verification of the unmodified generated package, in increasing order:

  1 load                load and parse the package (MSL 4.1.0 loaded first)
  2 structure           checkModel of the robot class and of the test model (classes, dependencies, consistency)
  3 balance_translation equation/variable balance and translateModel of the test model
  4 simulation          controlled baseline simulation of the test model (2 s, the scorer's settings)
  5 urdf_consistency    coverage, kinematics vs URDF forward kinematics, axes/masses/CoM/inertia, joint torques vs a
                        MuJoCo reference (kkh.convert.score / dynamics, one OpenModelica session, nothing simulated twice)
  6 graphics            Placement, connection Line, Icon and Diagram annotations, read through OpenModelica's own
                        annotation API (not text matching), checked separately from the engineering verdict

Output: stage2/diagnostics.json, one machine-readable record per finding:
  {id, step, check, category, severity, blocking, entity, file, line, col, message, evidence}
plus per-step results and a verdict. A model that compiles is never called validated: "validated" requires every
engineering check (steps 1-5) to pass; graphics are reported apart.

Warnings: OMPython clears OpenModelica's message buffer and only logs warnings, so each step captures the OMPython
logger; errors arrive through OMCService.errors(). Stage 1 findings (unsupported URDF content) are carried over.

    PYTHONPATH=. python -m kkh.workflow.stage2_check runs/workflow/<run-id>
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import logging
import re
import time
from pathlib import Path

from kkh.convert import dynamics, score
from kkh.engineering.omc import MatResult, OMCService, classify, parse_messages
from kkh.engineering.urdf_model import load_urdf

SCHEMA = "kkh.workflow.diagnostics/1"
STEPS = ["load", "structure", "balance_translation", "simulation", "urdf_consistency", "records", "graphics"]
ENGINEERING_STEPS = STEPS[:6]  # everything except graphics decides "validated"
BLOCKING_STEPS = ("load", "structure", "balance_translation", "simulation")

# Mission taxonomy. Mapping from kkh.engineering.omc.classify classes is explicit and tested.
CATEGORIES = ["syntax and translation", "missing class or library", "type and unit", "connector and equation",
              "initialization and numerical", "unsupported URDF element", "mechanical or kinematic inconsistency",
              "graphical annotation", "other"]
OMC_CLASS_TO_CATEGORY = {"syntax": "syntax and translation", "compile": "syntax and translation",
                         "lookup": "missing class or library", "type": "type and unit",
                         "connect": "connector and equation", "balance": "connector and equation",
                         "initialization": "initialization and numerical", "numerical": "initialization and numerical",
                         "assertion": "initialization and numerical", "other": "other"}
_UNIT = re.compile(r"\bunit\b|inconsistent unit", re.I)
_LOG_ENTRY = re.compile(r"\[(?P<kind>\w+):(?P<level>\w+):(?P<id>\d+)\]\s*(?P<msg>.*)", re.S)


_INIT = re.compile(r"initial (conditions|values|guess)|start value", re.I)


def category_of(message: str) -> str:
    """Mission category of an OpenModelica message. omc.classify is not changed: the frozen detection experiment
    uses it; the two extra rules here only refine units and initial conditions."""
    if _UNIT.search(message):
        return "type and unit"
    if _INIT.search(message):
        return "initialization and numerical"
    return OMC_CLASS_TO_CATEGORY[classify(message)]


# Warnings that are expected for the check that produced them; kept as info with the reason, never dropped.
EXPECTED = [(re.compile(r"top-level outer element|inner declaration for outer component"),
             "expected when a component class (the robot) is checked on its own: 'world' is provided by the test model")]

_ASSERT = re.compile(r"LOG_ASSERT\s*\|\s*(?P<level>\w+)\s*\|\s*\[(?P<file>[^\]]*?):(?P<line>\d+):(?P<col>\d+)-[^\]]*\]"
                     r"(?P<body>.*?)(?=LOG_\w+\s*\||\Z)", re.S)


def parse_assertions(messages: str) -> list[dict]:
    """Runtime assertion blocks from a simulation log: location, when, the instance path and the assertion text."""
    out = []
    for m in _ASSERT.finditer(messages or ""):
        body = re.sub(r"\|\s*\|?\s*\|?\s*\|?", " ", m["body"])
        body = re.sub(r"\s+", " ", body).strip()
        cond = re.search(r"\(\(not ([\w.\[\]]+)\)\)\s*-->\s*\"([^\"]*)\"", body)
        path = cond.group(1) if cond else ""
        out.append({"level": m["level"], "file": m["file"], "line": int(m["line"]), "col": int(m["col"]),
                    "when": ("during initialization" if "during initialization" in body else
                             (re.search(r"at time ([\d.e+-]+)", body) or [None, "?"])[1]),
                    "condition": path, "text": cond.group(2) if cond else body[:200],
                    "instance": ".".join(path.split(".")[:-2]) if path else None})
    return out


class _Capture(logging.Handler):
    """Collects OMPython log records (OpenModelica warnings and notifications) during one step."""

    def __init__(self):
        super().__init__(logging.INFO)
        self.records: list[dict] = []

    def emit(self, record):
        m = _LOG_ENTRY.search(record.getMessage())
        if m:
            self.records.append({"kind": m["kind"], "level": m["level"], "omc_id": m["id"], "msg": m["msg"].strip()})


@contextlib.contextmanager
def captured():
    h, lg = _Capture(), logging.getLogger("OMPython")
    lg.addHandler(h)
    try:
        yield h.records
    finally:
        lg.removeHandler(h)


class Diagnostics:
    def __init__(self):
        self.items: list[dict] = []
        self._by_message: dict[str, dict] = {}

    def add(self, step, check, category, severity, message, *, blocking=False, entity=None, file=None, line=None,
            col=None, evidence=None):
        assert category in CATEGORIES and severity in ("error", "warning", "info") and step in STEPS + ["conversion"]
        self.items.append({"id": f"D{len(self.items) + 1:03d}", "step": step, "check": check, "category": category,
                           "severity": severity, "blocking": blocking, "entity": entity, "file": file,
                           "line": int(line) if line else None, "col": int(col) if col else None,
                           "message": message, "evidence": evidence})

    def omc(self, step, check, parsed: list[dict], logged: list[dict], pkg_root: Path | None, blocking: bool):
        """OpenModelica messages: parsed errors (with location) and captured warnings/notifications."""
        seen = set()
        for e in parsed:
            key = (e.get("msg"), e.get("line"))
            if key in seen:
                continue
            seen.add(key)
            sev = "error" if e.get("kind", "").lower() == "error" else "warning"
            self.add(step, check, category_of(e["msg"]), sev, e["msg"], blocking=blocking and sev == "error",
                     file=_pkg_rel(e.get("file"), pkg_root), line=e.get("line"), col=e.get("col"))
        for r in logged:
            if r["level"] == "error" or (r["msg"], None) in seen:
                continue  # errors are already in `parsed` with their location
            seen.add((r["msg"], None))
            if r["msg"] in self._by_message:  # the same OpenModelica warning from a later step: one finding
                self._by_message[r["msg"]].setdefault("also_in", []).append(step)
                continue
            sev = "warning" if r["level"] == "warning" else "info"
            reason = next((why for rx, why in EXPECTED if rx.search(r["msg"])), None)
            self.add(step, check, category_of(r["msg"]), "info" if reason else sev, r["msg"],
                     evidence=f"OpenModelica {r['kind']}:{r['level']}:{r['omc_id']}" + (f"; {reason}" if reason else ""))
            self._by_message[r["msg"]] = self.items[-1]


def _pkg_rel(file: str | None, root: Path | None) -> str | None:
    if not file:
        return None
    p = Path(file)
    try:
        return p.resolve().relative_to(root.resolve()).as_posix() if root else p.as_posix()
    except ValueError:
        return p.name


# ---------------------------------------------------------------- graphics (OpenModelica annotation API)

def _placement(ann) -> list[float] | None:
    """Placement → [originX, originY, x1, y1, x2, y2] from getNthComponentAnnotation's structure."""
    s = str(ann)
    if "Placement" not in s:
        return None
    m = re.search(r"'Values': \[True, ([^\]]*)\]", s)
    if not m:
        return None
    v = [x.strip() for x in m.group(1).split(",")]
    num = lambda x: float(x) if re.fullmatch(r"[-+]?\d+(\.\d*)?(e[-+]?\d+)?", x) else 0.0
    return [num(x) for x in v[:6]]


def _extent(diagram) -> list[float] | None:
    m = re.search(r"'Set1': \[([-\d.]+), ([-\d.]+), ([-\d.]+), ([-\d.]+)", str(diagram))
    return [float(m.group(i)) for i in range(1, 5)] if m else None


def graphics(omc: OMCService, classes: list[str]) -> list[dict]:
    """Per model class: components with/without Placement, connections with/without Line, overlapping placements,
    placements outside the diagram extent, Icon present."""
    out = []
    for cls in classes:
        if not omc.send(f"isModel({cls})"):
            continue
        comps = omc.send(f"getComponents({cls})") or ()
        placed, unplaced, centres = 0, [], {}
        ext = _extent(omc.send(f"getDiagramAnnotation({cls})")) or [-100.0, -100.0, 100.0, 100.0]
        outside = []
        for i, c in enumerate(comps, 1):
            if c[8] in ("parameter", "constant"):
                continue  # parameters are not drawn
            p = _placement(omc.send(f"getNthComponentAnnotation({cls}, {i})"))
            if p is None:
                unplaced.append(c[1])
                continue
            placed += 1
            cx, cy = p[0] + (p[2] + p[4]) / 2, p[1] + (p[3] + p[5]) / 2
            centres.setdefault((round(cx, 3), round(cy, 3)), []).append(c[1])
            lo_x, hi_x, lo_y, hi_y = min(ext[0], ext[2]), max(ext[0], ext[2]), min(ext[1], ext[3]), max(ext[1], ext[3])
            if not (lo_x <= cx <= hi_x and lo_y <= cy <= hi_y):
                outside.append(c[1])
        n_conn = omc.send(f"getConnectionCount({cls})") or 0
        no_line = []
        for i in range(1, n_conn + 1):
            if "Line" not in str(omc.send(f"getNthConnectionAnnotation({cls}, {i})")):
                a, b = (omc.send(f"getNthConnection({cls}, {i})") or ("?", "?", ""))[:2]
                no_line.append(f"{a} - {b}")
        out.append({"class": cls, "components_drawn": placed, "components_without_placement": unplaced,
                    "overlapping": [v for v in centres.values() if len(v) > 1], "outside_extent": outside,
                    "diagram_extent": ext, "connections": n_conn, "connections_without_line": no_line,
                    "has_icon": bool(omc.send(f"getIconAnnotation({cls})"))})
    return out


# ---------------------------------------------------------------- run

def run(run_dir: Path, log=print, ws_dir: Path | None = None, out_dir: Path | None = None) -> dict:
    """Check the Stage 1 package, or (ws_dir) a candidate: a copy of the Stage 1 workspace with edits. Every subject
    goes through exactly the same steps, so original and candidates are comparable."""
    run_dir = Path(run_dir).resolve()  # OpenModelica runs in its own working directory
    st1 = json.loads((run_dir / "stage1" / "manifest.json").read_text(encoding="utf-8"))
    if not st1.get("ok"):
        raise ValueError("stage 1 did not produce a package")
    from kkh.workflow import stage1_convert as s1
    ROOT = s1.ROOT
    package_file = ROOT / st1["generated"]["package_file"]
    pkg_dir = ROOT / st1["generated"]["package_dir"]
    if ws_dir is not None:
        ws_dir = Path(ws_dir).resolve()
        package_file = ws_dir / "URDFModelica" / "package.mo"
        pkg_dir = ws_dir / "URDFModelica" / "Examples" / pkg_dir.name
    ws_root = ws_dir if ws_dir is not None else package_file.parent.parent
    longest = max((len(str(p.resolve())) for p in ws_root.rglob("*")), default=0)
    if longest >= 255:
        raise ValueError(f"a file path in {ws_root.name} is {longest} characters long; Windows (and OpenModelica on it) "
                         "cannot open paths of 260 characters or more. Use a shorter run name or a shorter repository path.")
    test_model = st1["generated"]["test_model"]
    robot_class = test_model.rsplit(".", 1)[0] + "." + pkg_dir.name
    urdf_path = run_dir / "stage1" / "input" / Path(st1["source"]["urdf"]).name
    robot = load_urdf(urdf_path)
    out_dir = Path(out_dir).resolve() if out_dir else run_dir / "stage2"
    out_dir.mkdir(parents=True, exist_ok=True)

    d = Diagnostics()
    # Unsupported / unused URDF content is re-evaluated on the package being checked (a repair may have fixed it).
    conv_log = (run_dir / "stage1" / "convert" / "converter.log")
    mapping = s1.build_mapping(robot, pkg_dir, pkg_dir / f"{pkg_dir.name}.mo") if (pkg_dir / f"{pkg_dir.name}.mo").exists() else []
    for u in s1.unsupported(urdf_path, robot, mapping, pkg_dir, st1["converter"]["preprocessing"],
                            conv_log.read_text(encoding="utf-8") if conv_log.exists() else ""):
        d.add("conversion", "conversion record", u["category"], u["severity"], f"{u['feature']}: {u['effect']}",
              entity=u.get("entity"), evidence=u.get("evidence"))
    steps: dict[str, dict] = {}
    blocked_at = None
    t0 = time.time()
    log(f"[stage2] OpenModelica checks of {test_model}")
    omc = OMCService(out_dir / "omc")
    s: dict = {"produced": True}
    try:
        def step(name, fn):
            nonlocal blocked_at
            if blocked_at:
                steps[name] = {"state": "not reached", "blocked_by": blocked_at}
                return None
            t = time.time()
            with captured() as logged:
                ok, info, parsed = fn()
            d.omc(name, name, parsed, logged, pkg_dir, blocking=name in BLOCKING_STEPS)
            steps[name] = {"state": "pass" if ok else "fail", "seconds": round(time.time() - t, 2), **info}
            if not ok and name in BLOCKING_STEPS:
                blocked_at = name
                d.add(name, name, "other" if not parsed else category_of(parsed[0]["msg"]), "error",
                      f"step '{name}' failed; later steps not run", blocking=True)
            log(f"[stage2] {name}: {steps[name]['state']}")
            return ok

        def load():
            r = omc.load_package(package_file)
            s["loads"] = r.ok
            return r.ok, {"package_file": package_file.name}, r.errors

        def structure():
            parsed, info = [], {}
            for label, cls in (("robot_class", robot_class), ("test_model", test_model)):
                r = omc.check(cls)
                parsed += r.errors
                info[label] = {"class": cls, "ok": r.ok, **r.data}
                if not r.ok:
                    info[label]["message"] = r.messages[-1500:]
            s["checks"] = info["test_model"]["ok"]
            return info["test_model"]["ok"], info, parsed

        def balance_translation():
            eq, var = steps["structure"]["test_model"].get("equations"), steps["structure"]["test_model"].get("variables")
            s["equations"], s["variables"] = eq, var
            s["balanced"] = eq is not None and eq == var
            ok_t = bool(omc.send(f"translateModel({test_model})"))
            msg = omc.errors()
            if not s["balanced"]:
                d.add("balance_translation", "equation balance", "connector and equation", "error",
                      f"{eq} equations for {var} variables", blocking=True, entity=test_model)
            return s["balanced"] and ok_t, {"equations": eq, "variables": var, "translated": ok_t}, parse_messages(msg)

        def simulation():
            r = omc.simulate(test_model, stop_time=score.STOP_TIME, intervals=100, timeout_s=120)
            (out_dir / "simulation.log").write_text(r.messages, encoding="utf-8")
            s["simulates"], s["assertions"] = r.ok, r.data.get("assert_warnings")
            s["_result"] = r.data.get("resultFile")
            for a in parse_assertions(r.messages):
                d.add("simulation", "runtime assertions", "initialization and numerical",
                      "error" if a["level"] == "error" else "warning",
                      f"assertion '{a['text']}' violated {a['when']}", entity=a["instance"],
                      file=_pkg_rel(a["file"], pkg_dir), line=a["line"], col=a["col"],
                      evidence=f"{a['condition']} (OpenModelica simulation log)")
            return r.ok, {"stop_time_s": score.STOP_TIME, "result_file": Path(r.data["resultFile"]).name if r.ok else None,
                          "assert_warnings": r.data.get("assert_warnings"),
                          "seconds_build_and_run": r.data.get("timeTotal")}, r.errors

        def urdf_consistency():
            res = MatResult(s.pop("_result"))
            s.update(score.kinematic_match(res, robot))
            s["motion"] = "the model's own test motion"
            (out_dir / "excite").mkdir(exist_ok=True)
            info, res_ex = score._excite(omc, robot, urdf_path, test_model, package_file, out_dir / "excite")
            s["excitation"] = info
            if res_ex is not None:
                s.update(score.kinematic_match(res_ex, robot))
                s["motion"] = "standard excitation (every joint through 80 % of its range)"
                res = res_ex
            try:
                s["dynamics"] = dynamics.compare(res, robot, urdf_path, s.get("joint_vars") or {})
            except Exception as exc:
                s["dynamics"] = {"checked": False, "reason": f"{type(exc).__name__}: {exc}"[:300]}
            crit = {c["id"]: c for c in score.finish(dict(s))["criteria"]}
            _consistency_findings(d, s)
            ok = all(crit[k]["ok"] for k in ("coverage", "kinematics", "parameters", "dynamics"))
            return ok, {"motion": s["motion"], "criteria": [crit[k] for k in ("coverage", "kinematics", "parameters", "dynamics")]}, []

        for name, fn in (("load", load), ("structure", structure), ("balance_translation", balance_translation),
                         ("simulation", simulation), ("urdf_consistency", urdf_consistency)):
            step(name, fn)

        # records: static comparison of every parameter-record value with the URDF (no OpenModelica needed, so it
        # runs even when an earlier step failed): catches e.g. a limit written in degrees or a replaced mass
        t = time.time()
        try:
            table = s1.physical_table(robot, mapping, pkg_dir) if mapping else []
            missing = [m["urdf_name"] for m in mapping if not m["params_file"]]
            for r in table:
                if not r["match"]:
                    d.add("records", f"record.{r['field']}", "type and unit" if r["field"].startswith("limit") else
                          "mechanical or kinematic inconsistency", "error",
                          f"{r['field']} in the parameter record differs from the URDF", entity=r["entity"],
                          evidence=json.dumps({"urdf": r["urdf"], "record": r["generated"], "unit": r["unit"]}, default=str))
            for name in missing:
                d.add("records", "record present", "mechanical or kinematic inconsistency", "error",
                      "no parameter record found for this URDF element", entity=name)
            ok_rec = bool(table) and not missing and all(r["match"] for r in table)
            steps["records"] = {"state": "pass" if ok_rec else "fail", "seconds": round(time.time() - t, 2),
                                "values_compared": len(table), "mismatches": sum(not r["match"] for r in table),
                                "missing_records": missing}
        except Exception as exc:  # unreadable records are themselves a finding
            d.add("records", "records", "syntax and translation", "error", f"parameter records could not be read: {exc}"[:300])
            steps["records"] = {"state": "fail", "error": str(exc)[:300]}
        log(f"[stage2] records: {steps['records']['state']}")

        # graphics: independent of the engineering verdict, needs only a loaded package
        if s.get("loads"):
            t = time.time()
            classes = [c for c in (omc.send(f"getClassNames({robot_class.rsplit('.', 1)[0]}, recursive=true)") or ())]
            g = graphics(omc, list(classes))
            _graphics_findings(d, g)
            totals = {"classes": len(g), "connections": sum(x["connections"] for x in g),
                      "connections_without_line": sum(len(x["connections_without_line"]) for x in g),
                      "components_drawn": sum(x["components_drawn"] for x in g),
                      "components_without_placement": sum(len(x["components_without_placement"]) for x in g),
                      "overlapping_groups": sum(len(x["overlapping"]) for x in g),
                      "outside_extent": sum(len(x["outside_extent"]) for x in g)}
            steps["graphics"] = {"state": "pass" if not any(totals[k] for k in ("connections_without_line", "components_without_placement", "overlapping_groups", "outside_extent")) else "fail",
                                 "seconds": round(time.time() - t, 2), "totals": totals, "per_class": g}
            log(f"[stage2] graphics: {totals}")
        else:
            steps["graphics"] = {"state": "not reached", "blocked_by": "load"}
        omc_version = omc.version()
    finally:
        omc.close()

    _relate(d.items)
    eng = [steps.get(k, {}).get("state") for k in ENGINEERING_STEPS]
    verdict = ("validated" if all(x == "pass" for x in eng) else
               "simulates, engineering checks fail" if steps.get("simulation", {}).get("state") == "pass" else
               "compiles, does not simulate" if steps.get("balance_translation", {}).get("state") == "pass" else
               f"fails at {blocked_at}")
    report = {"schema": SCHEMA, "created": dt.datetime.now().isoformat(timespec="seconds"),
              "subject": {"run": run_dir.name, "package": s1._rel(pkg_dir), "test_model": test_model,
                          "robot_class": robot_class, "urdf_sha256": st1["source"]["urdf_sha256"],
                          "candidate": ws_dir is not None, "files": s1._generated_hashes(pkg_dir)},
              "tools": {"openmodelica": omc_version, "msl": "4.1.0", "seconds": round(time.time() - t0, 1)},
              "steps": steps, "verdict": verdict,
              "verdict_rule": "validated = load, structure, balance/translation, simulation, URDF consistency and "
                              "record values all pass; compiling alone is not validation; graphics are reported separately",
              "graphics_verdict": steps["graphics"]["state"],
              "counts": _counts(d.items), "findings": d.items}
    (out_dir / "diagnostics.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    log(f"[stage2] verdict: {verdict}; {report['counts']['by_severity']}")
    return report


def _consistency_findings(d: Diagnostics, s: dict):
    cat = "mechanical or kinematic inconsistency"
    for l in s.get("missing_links") or []:
        d.add("urdf_consistency", "coverage", cat, "error", "URDF link not found in the simulated model", entity=l)
    for j in s.get("missing_joints") or []:
        d.add("urdf_consistency", "coverage", cat, "error", "URDF movable joint not found in the simulated model", entity=j)
    kin = s.get("kinematics") or {}
    if kin and not kin.get("pass"):
        st = s.get("structure") or {}
        d.add("urdf_consistency", "kinematics", cat, "error",
              f"link positions differ from URDF forward kinematics by up to {kin['max_position_error_mm']} mm "
              f"(tolerance {score.KIN_TOL_MM} mm)" + (f"; orientation up to {kin['max_orientation_error_deg']} deg" if kin.get("max_orientation_error_deg") is not None else ""),
              entity=", ".join(x.split("/")[-1] for x in st.get("suspect_joints", [])) or str(kin.get("worst_link")),
              evidence=json.dumps({"worst_link": kin.get("worst_link"), "misplaced_links": st.get("misplaced_links"),
                                   "suspect_joints": st.get("suspect_joints"), "motion": s.get("motion")}, default=str))
    par = s.get("parameters") or {}
    for fam, key in (("axes", "joint"), ("masses", "link"), ("com", "link"), ("inertia", "link")):
        for r in par.get(fam) or []:
            if not r.get("match"):
                d.add("urdf_consistency", f"parameters.{fam}", cat, "error", f"{fam} differ from the URDF",
                      entity=r.get(key), evidence=json.dumps({k: r.get(k) for k in ("model", "urdf")}, default=str))
    dyn = s.get("dynamics") or {}
    if dyn.get("checked"):
        for r in dyn["joints"]:
            if not r["match"]:
                d.add("urdf_consistency", "dynamics", cat, "error",
                      f"joint torque differs from the MuJoCo reference: RMS {r['rms_nm']} N.m = {r['rms_pct_effort']}% of the effort limit",
                      entity=r["joint"], evidence=dyn["tolerance"])
            elif r["mimic"]:
                d.add("urdf_consistency", "dynamics", cat, "info", "mimic joint, torque reported but not scored",
                      entity=r["joint"], evidence=f"RMS {r['rms_nm']} N.m")
    elif dyn:
        d.add("urdf_consistency", "dynamics", "other", "warning", f"torque comparison not possible: {dyn.get('reason')}")


def _graphics_findings(d: Diagnostics, per_class: list[dict]):
    for g in per_class:
        short = g["class"].split(".")[-1]
        if g["connections_without_line"]:
            d.add("graphics", "connection lines", "graphical annotation", "warning",
                  f"{len(g['connections_without_line'])} of {g['connections']} connections have no Line annotation (not drawn in OMEdit)",
                  entity=short, evidence="; ".join(g["connections_without_line"][:12]))
        if g["components_without_placement"]:
            d.add("graphics", "placements", "graphical annotation", "warning",
                  f"{len(g['components_without_placement'])} components have no Placement", entity=short,
                  evidence=", ".join(g["components_without_placement"][:12]))
        for grp in g["overlapping"]:
            d.add("graphics", "overlaps", "graphical annotation", "info", "components drawn at the same position",
                  entity=short, evidence=", ".join(grp))
        if g["outside_extent"]:
            d.add("graphics", "diagram extent", "graphical annotation", "info",
                  f"{len(g['outside_extent'])} components outside the diagram extent {g['diagram_extent']}",
                  entity=short, evidence=", ".join(g["outside_extent"][:12]))


def _entity_names(item: dict) -> set[str]:
    e = item.get("entity") or ""
    return {x.strip().split(".")[-1].split("/")[-1] for x in re.split(r"[,;]", e) if x.strip()}


def _relate(items: list[dict]):
    """Cross-reference findings that concern the same URDF entity (e.g. a stage-1 'mimic not used' record and the
    stage-2 kinematic error it explains), so a reviewer and a repair prompt see them together."""
    for a in items:
        names = _entity_names(a)
        rel = [b["id"] for b in items if b is not a and names & _entity_names(b)]
        if rel:
            a["related"] = rel


def _counts(items: list[dict]) -> dict:
    by = lambda k: {v: sum(1 for i in items if i[k] == v) for v in sorted({i[k] for i in items})}
    return {"total": len(items), "by_severity": by("severity"), "by_category": by("category"), "by_step": by("step"),
            "blocking": sum(1 for i in items if i["blocking"])}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("run_dir", type=Path, help="run directory containing stage1/")
    a = ap.parse_args()
    r = run(a.run_dir)
    print(json.dumps({"verdict": r["verdict"], "graphics": r["graphics_verdict"], "counts": r["counts"]}, indent=1))


if __name__ == "__main__":
    main()
