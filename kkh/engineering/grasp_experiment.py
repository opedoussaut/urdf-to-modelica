"""Run the isolated Modelica pinch/lift/release surrogate, never the live Studio.

Requires the earlier GEN7Contact package and OpenModelica `omc` on PATH.
Outputs are evidence about an assumed 2D surrogate, NOT validated ALOHA grasping.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "engineering" / "modelica" / "GEN7Contact"
MODEL = "GEN7Contact.TwoFingerGrasp"


def mos_script(package_file: Path) -> str:
    path = package_file.resolve().as_posix().replace('"', '\\"')
    return (
        'loadModel(Modelica, {"4.1.0"});\n'
        f'loadFile("{path}");\n'
        f'checkModel({MODEL});\n'
        f'simulate({MODEL}, stopTime=2.4, numberOfIntervals=2400, '
        'tolerance=1e-7, outputFormat="csv");\n'
        'getErrorString();\n'
    )


def validate_result(path: Path) -> dict:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) < 500:
        raise ValueError("Insufficient simulation samples")
    def col(name: str) -> list[float]:
        keys = [k for k in rows[0] if k == name or k.endswith("." + name)]
        if len(keys) != 1:
            raise ValueError(f"Expected exactly one {name} column, found {keys}")
        result = [float(row[keys[0]]) for row in rows]
        if not all(math.isfinite(value) for value in result):
            raise ValueError(f"Non-finite {name}")
        return result

    t = col("time")
    z = col("z")
    x = col("x")
    nf_left = col("leftNormal")
    nf_right = col("rightNormal")
    table = col("tableNormal")
    fp_left = col("leftPenetration")
    fp_right = col("rightPenetration")
    tp = col("tablePenetration")
    friction_left = col("leftFriction")
    friction_right = col("rightFriction")
    # Modelica parameters may be elided from CSV output; use exported force limits.
    # These diagnostic variables preserve the actual simulated parameter value.
    capacity_left = col("leftFrictionLimit")
    capacity_right = col("rightFrictionLimit")
    if any(t[i] < t[i-1] for i in range(1, len(t))):
        raise ValueError("Simulation time is not monotonic")
    if any(min(a, b, c) < -1e-7 for a, b, c in zip(nf_left, nf_right, table)):
        raise ValueError("Contact normal became tensile")
    if any(limit < -1e-7 for limit in capacity_left + capacity_right):
        raise ValueError("Negative friction capacity")
    if any(abs(f) > limit + 1e-6 for f, limit in
           list(zip(friction_left, capacity_left)) +
           list(zip(friction_right, capacity_right))):
        raise ValueError("Friction exceeds computed mu*N")
    if max(fp_left + fp_right) > 0.005 or max(tp) > 0.005:
        raise ValueError("Excessive penetration in assumed contact model")
    if not any(a > 0 and b > 0 for a, b, tt in zip(nf_left, nf_right, t) if 0.5 < tt < 1.4):
        raise ValueError("No two-sided pinch contact during lift interval")
    if not any(v > 0.045 for v, tt in zip(z, t) if 1.15 <= tt <= 1.44):
        raise ValueError("Cube did not lift from table after pinch")
    if abs(x[-1]) > 0.01:
        raise ValueError("Cube drifted horizontally from symmetric grip")
    if not (0.015 <= z[-1] <= 0.035):
        raise ValueError("Cube did not return near the table after release")
    return {
        "samples": len(rows),
        "max_cube_height_m": max(z),
        "final_cube_height_m": z[-1],
        "max_horizontal_drift_m": max(abs(v) for v in x),
        "max_finger_penetration_m": max(fp_left + fp_right),
        "max_table_penetration_m": max(tp),
        "peak_finger_normal_N": max(nf_left + nf_right),
        "peak_table_normal_N": max(table),
        "grasp_claim": "NONE: assumed reduced-order 2D surrogate, not validated physical grasp",
    }


def run(out: Path) -> dict:
    omc = shutil.which("omc")
    if not omc:
        raise RuntimeError("omc not available on PATH; add OpenModelica bin for this session")
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    script = out / "grasp.mos"
    script.write_text(mos_script(MODEL_DIR / "package.mo"), encoding="utf-8")
    result = out / f"{MODEL}_res.csv"
    result.unlink(missing_ok=True)  # Never accept a stale simulation result.
    finished = subprocess.run([omc, str(script)], cwd=out, capture_output=True,
                              text=True, timeout=120)
    report = {"model": MODEL, "returncode": finished.returncode,
              "omc_stdout": finished.stdout, "omc_stderr": finished.stderr,
              "result_csv": str(result) if result.exists() else None}
    if finished.returncode == 0 and result.exists():
        try:
            report["validation"] = validate_result(result)
        except (ValueError, OSError) as exc:
            report["validation_error"] = str(exc)
    (out / "run.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if finished.returncode != 0 or "validation" not in report:
        raise RuntimeError(f"Grasp experiment failed; inspect {out / 'run.json'}")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "grasp-experiment")
    print(json.dumps(run(parser.parse_args().out), indent=2))
