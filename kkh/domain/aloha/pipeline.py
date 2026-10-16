"""End-to-end deterministic ALOHA pipeline (workflow 'D' = this project's generator):

configuration -> URDF validation -> Modelica generation -> structural completeness ->
OpenModelica load/check -> simulation -> result extraction -> independent kinematic validation -> report

Usage:  python -m kkh.domain.aloha.pipeline [Experiment]
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import time
from pathlib import Path

import numpy as np

from kkh.engineering.modelica_inspect import completeness
from kkh.engineering.omc import MatResult, OMCService
from kkh.engineering.urdf_model import load_urdf
from kkh.engineering.validation import compare_frames, compare_trajectory

from . import configuration as C
from .build import ASSEMBLY, PKG, build, variable_filter
from .scenarios import arms_for, scenarios

RUNS = C.ROOT / "runs"
REPORTS = C.ROOT / "reports"


def _quat(R: np.ndarray) -> list[float]:
    """Rotation matrix -> quaternion (x, y, z, w)."""
    t = np.trace(R)
    if t > 0:
        s = np.sqrt(t + 1.0) * 2
        w, x, y, z = 0.25 * s, (R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
        w, x, y, z = (R[2, 1] - R[1, 2]) / s, 0.25 * s, (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s
    elif R[1, 1] > R[2, 2]:
        s = np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
        w, x, y, z = (R[0, 2] - R[2, 0]) / s, (R[0, 1] + R[1, 0]) / s, 0.25 * s, (R[1, 2] + R[2, 1]) / s
    else:
        s = np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
        w, x, y, z = (R[1, 0] - R[0, 1]) / s, (R[0, 2] + R[2, 0]) / s, (R[1, 2] + R[2, 1]) / s, 0.25 * s
    return [round(float(v), 7) for v in (x, y, z, w)]


class Pipeline:
    def __init__(self, experiment: str = "RightArmReach", log=print, run_dir: Path | None = None):
        self.experiment = experiment
        self.log = log
        self.run_id = dt.datetime.now().strftime("%Y%m%d-%H%M%S") + f"-{experiment}"
        self.run_dir = run_dir or RUNS / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.steps: list[dict] = []
        self.report: dict = {"run_id": self.run_id, "experiment": experiment, "workflow": "D-deterministic-kkh",
                             "started": dt.datetime.now().isoformat(timespec="seconds")}

    def step(self, name, fn):
        t = time.time()
        self.log(f"[{name}] ...")
        try:
            out = fn()
            rec = {"step": name, "ok": True, "seconds": round(time.time() - t, 2)}
            if isinstance(out, dict) and "ok" in out:
                rec["ok"] = bool(out["ok"])
            self.steps.append(rec)
            self.log(f"[{name}] {'OK' if rec['ok'] else 'FAILED'} ({rec['seconds']} s)")
            return out
        except Exception as e:
            self.steps.append({"step": name, "ok": False, "seconds": round(time.time() - t, 2), "error": repr(e)})
            self.log(f"[{name}] ERROR {e!r}")
            raise

    def run(self) -> dict:
        try:
            self._run()
        finally:
            self.report["steps"] = self.steps
            self.report["finished"] = dt.datetime.now().isoformat(timespec="seconds")
            self.report["success"] = all(s["ok"] for s in self.steps) and len(self.steps) >= 8
            (self.run_dir / "report.json").write_text(json.dumps(self.report, indent=1))
            REPORTS.mkdir(exist_ok=True)
            (REPORTS / f"latest_{self.experiment}.json").write_text(json.dumps(self.report, indent=1))
        return self.report

    def _run(self):
        R = self.report
        manifest = self.step("configuration", lambda: {"ok": True, **C.build_manifest()})
        C.write_manifest()
        R["configuration"] = {"variant": manifest["variant"]["name"], "totals": manifest["totals"],
                              "discrepancies": len(manifest["discrepancies"])}

        def assets():
            out = {"ok": True}
            for m in C.ARM_CLASS:
                rep = C.arm_robot(m).validate_structure()
                out[m] = {k: rep[k] for k in ("ok", "n_links", "n_joints", "joint_types", "n_actuated", "errors")}
                out["ok"] &= rep["ok"]
            full = load_urdf(C.ASSEMBLY_URDF).validate_structure()
            out["assembly"] = {k: full[k] for k in ("ok", "n_links", "n_joints", "joint_types", "n_actuated")}
            out["ok"] &= full["ok"]
            return out
        R["urdf_validation"] = self.step("urdf_validation", assets)

        rec = self.step("generate_modelica", lambda: {"ok": True, **build()})
        R["generation"] = {"files": len(rec["files"]), "placeholders": rec["placeholders"],
                           "package": f"generated/modelica/{PKG}"}

        def comp():
            out = {"ok": True, "arms": {}}
            for m, cls in C.ARM_CLASS.items():
                rep = completeness(C.arm_robot(m), C.ROOT / f"generated/modelica/{PKG}/Arms/{cls}.mo")
                out["arms"][m] = rep
                out["ok"] &= rep["complete"]
            asm = (C.ROOT / f"generated/modelica/{PKG}/{ASSEMBLY}.mo").read_text()
            n_inst = sum(asm.count(f"{PKG}.Arms.{c} ") for c in C.ARM_CLASS.values())
            n_mount = asm.count("FixedRotation mount_")
            out["assembly"] = {"arm_instances": n_inst, "mounts": n_mount, "expected": len(C.ARMS)}
            out["ok"] &= n_inst == len(C.ARMS) == n_mount
            t = C.build_manifest()["totals"]
            out["totals"] = {"links_represented": 1 + sum(int(out["arms"][a["model"]]["links"].split("/")[0]) for a in C.ARMS),
                             "joints_represented": n_mount + sum(int(out["arms"][a["model"]]["joints"].split("/")[0]) for a in C.ARMS),
                             "links_urdf": t["links"], "joints_urdf": t["joints"]}
            return out
        R["completeness"] = self.step("structural_completeness", comp)

        omc = OMCService(self.run_dir / "omc")
        try:
            R["tools"] = {"omc": omc.version(), "msl": omc.loaded_libraries()}

            def load_check():
                lr = omc.load_package(C.ROOT / f"generated/modelica/{PKG}/package.mo")
                out = {"ok": lr.ok, "load": lr.ok, "checks": {}}
                for m in [f"{PKG}.Arms.{c}" for c in C.ARM_CLASS.values()] + [f"{PKG}.{ASSEMBLY}",
                                                                                f"{PKG}.Experiments.{self.experiment}"]:
                    r = omc.check(m)
                    out["checks"][m] = {"ok": r.ok, **r.data, "errors": r.errors[:5]}
                    out["ok"] &= r.ok
                return out
            R["check"] = self.step("omc_check", load_check)

            sc = scenarios()[self.experiment]

            def sim():
                r = omc.simulate(f"{PKG}.Experiments.{self.experiment}", stop_time=sc["stop_time"],
                                 intervals=int(round(sc["stop_time"] / 0.02)), variable_filter=variable_filter(sc))
                out = r.to_dict()
                out["messages"] = out["messages"][-4000:]
                return out
            R["simulation"] = self.step("simulate", sim)
            if not R["simulation"]["ok"]:
                return
            res = MatResult(R["simulation"]["data"]["resultFile"])
            mapping = json.loads((C.ROOT / "generated/modelica/aloha2_mapping.json").read_text())
            arms = mapping["arms"] if sc["target"] == "assembly" else [mapping["leader"]]
            self.report["target"] = sc["target"]
            R["results"] = self.step("extract_results", lambda: self._extract(res, arms, sc))
            R["validation"] = self.step("kinematic_validation", lambda: self._validate(res, arms, sc))
        finally:
            omc.close()

    # ----------------------------------------------------------------------------------------
    def _jvars(self, j):
        base = j["modelica"]
        local = j["urdf_local"]
        prismatic = local.endswith("finger")
        return (f"{base}.{'s' if prismatic else 'phi'}", f"{base}.{'v' if prismatic else 'w'}",
                f"{base}.{'f' if prismatic else 'tau'}", "m" if prismatic else "rad")

    def _extract(self, res: MatResult, arms: list, sc: dict) -> dict:
        step = 2  # 0.04 s for playback
        t = res.time[::step]
        out = {"time": [round(float(x), 4) for x in t], "joints": {}, "links": {}, "end_effectors": {}}
        for arm in arms:
            for j in arm["joints"]:
                if j["driven_index"] is None and not j["mimic"]:
                    continue
                pv, vv, fv, unit = self._jvars(j)
                out["joints"][j["urdf"]] = {
                    "modelica": j["modelica"], "unit": unit,
                    "q": [round(float(x), 7) for x in res.get(pv)[::step]],
                    "qd": [round(float(x), 7) for x in res.get(vv)[::step]],
                    "effort": [round(float(x), 6) for x in res.get(fv)[::step]]}
            for l in arm["links"]:
                r0 = np.stack([res.get(v) for v in l["result_vars"]["r_0"]], 1)[::step]
                RT = np.stack([res.get(v) for v in l["result_vars"]["R"]], 1)[::step]
                out["links"][l["urdf"]] = [[*map(lambda x: round(float(x), 7), r0[k]), *_quat(RT[k].reshape(3, 3).T)]
                                           for k in range(len(t))]
            ee = f"{arm['arm']}/ee_gripper_link"
            out["end_effectors"][arm["arm"]] = [p[:3] for p in out["links"][ee]]
        (self.run_dir / "results.json").write_text(json.dumps(out))
        # Summary stats
        rf = self.run_dir / "results.json"
        rf_rel = rf.relative_to(C.ROOT).as_posix() if rf.is_relative_to(C.ROOT) else rf.as_posix()
        summary = {"ok": True, "samples": len(t), "results_file": rf_rel,
                   "moving_joints": [], "peak_effort": {}, "ee_path_length_m": {}}
        for name, d in out["joints"].items():
            q = np.array(d["q"])
            if np.ptp(q) > 1e-9:
                summary["moving_joints"].append(name)
            summary["peak_effort"][name] = round(float(np.max(np.abs(d["effort"]))), 5)
        for a, p in out["end_effectors"].items():
            p = np.array(p)
            summary["ee_path_length_m"][a] = round(float(np.sum(np.linalg.norm(np.diff(p, axis=0), axis=1))), 5)
        summary["n_moving_joints"] = len(summary["moving_joints"])
        return summary

    def _validate(self, res: MatResult, arms: list, sc: dict) -> dict:
        if sc["target"] == "assembly":
            ref, key, ref_name = load_urdf(C.ASSEMBLY_URDF), "urdf", C.ASSEMBLY_URDF.name
        else:
            ref, key, ref_name = C.arm_robot(C.LEADER["model"]), "urdf_local", f"{C.LEADER['model']}.urdf"
        links, joints = [], []
        for arm in arms:
            for l in arm["links"]:
                links.append({"urdf": l[key], "r_vars": l["result_vars"]["r_0"], "R_vars": l["result_vars"]["R"]})
            for j in arm["joints"]:
                if j["driven_index"] is not None:
                    joints.append({"urdf": j[key], "var": self._jvars(j)[0]})
        fk = compare_frames(res, ref, links, joints)
        # Trajectory fidelity: simulated driven coordinates vs independent numpy evaluation of the waypoints
        Q = np.array(sc["Q"])
        traj_err = 0.0
        for arm in arms:
            for j in arm["joints"]:
                if j["driven_index"] is not None:
                    traj_err = max(traj_err, compare_trajectory(res, self._jvars(j)[0], sc["t"], Q[:, j["driven_index"] - 1]))
        # Mimic: right_finger == -left_finger
        mimic_err = 0.0
        for arm in arms:
            m = arm["modelica_instance"]
            mimic_err = max(mimic_err, float(np.max(np.abs(res.get(f"{m}.j_right_finger.s")
                                                           + res.get(f"{m}.j_left_finger.s")))))
        # Limits on simulated values
        viol = []
        for arm in arms:
            r = C.arm_robot(arm["model"])
            for j in arm["joints"]:
                jt = r.joints[j["urdf_local"]]
                if jt.type in ("revolute", "prismatic"):
                    q = res.get(self._jvars(j)[0])
                    if q.min() < jt.limit.lower - 1e-9 or q.max() > jt.limit.upper + 1e-9:
                        viol.append(j["urdf"])
        fk.pop("per_link")
        return {"ok": fk["pass"] and traj_err < 1e-9 and mimic_err < 1e-12 and not viol,
                "forward_kinematics": fk, "trajectory_max_error": traj_err, "mimic_max_error": mimic_err,
                "limit_violations": viol, "reference": f"independent numpy URDF FK on data/urdf/{ref_name}"}


def main(argv):
    exp = argv[0] if argv else "RightArmReach"
    rep = Pipeline(exp).run()
    print(json.dumps({k: rep.get(k) for k in ("run_id", "success", "steps")}, indent=1))
    return 0 if rep["success"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
