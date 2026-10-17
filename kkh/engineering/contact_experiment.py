"""Run the isolated Modelica-first cube/table contact experiment.

This does NOT modify the frozen ALOHA2 package or activate MuJoCo.
OpenModelica must be installed and `omc` available on PATH.
"""
from __future__ import annotations

import argparse
import csv
import math
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "engineering" / "modelica" / "GEN7Contact"


def mos_script(package_file: Path) -> str:
    """Create OMC commands without shell interpolation (paths are escaped)."""
    escaped = package_file.resolve().as_posix().replace('"', '\\"')
    return (
        'loadModel(Modelica, {"4.1.0"});\n'
        f'loadFile("{escaped}");\n'
        'checkModel(GEN7Contact.CubeTableDrop);\n'
        'simulate(GEN7Contact.CubeTableDrop, stopTime=1.5, '
        'numberOfIntervals=1500, outputFormat="csv");\n'
        'getErrorString();\n'
    )


def validate_result(csv_path: Path) -> dict:
    """Numerical evidence gates; do not infer grasping or full robot physics."""
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) < 100:
        raise ValueError("Contact run contains insufficient samples")
    def col(suffix):
        matches = [k for k in rows[0] if k == suffix or k.endswith("." + suffix)]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one column {suffix}, found {matches}")
        return [float(row[matches[0]]) for row in rows]
    z, f, penetration = col("z"), col("normalForce"), col("penetration")
    times = col("time")
    if not all(math.isfinite(x) for x in z + f + penetration + times):
        raise ValueError("Contact simulation produced non-finite results")
    if any(n < -1e-8 for n in f):
        raise ValueError("Unilateral contact produced a tensile normal force")
    if max(penetration) > 0.02:
        raise ValueError("Penetration exceeded half the assumed cube side")
    if not any(n > 0 for n in f):
        raise ValueError("No cube/table contact occurred")
    if not all(n <= 1e-7 for n, t in zip(f, times) if t < 0.05):
        raise ValueError("Nonzero contact force before expected freefall impact")
    metrics = {"samples": len(rows), "max_penetration_m": max(penetration),
               "max_contact_force_N": max(f), "final_cube_centre_height_m": z[-1]}
    return metrics


def run(output_dir: Path) -> dict:
    if not shutil.which("omc"):
        raise RuntimeError("OpenModelica omc executable is not available on PATH")
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    script = output_dir / "cube_table_drop.mos"
    script.write_text(mos_script(MODEL_DIR / "package.mo"), encoding="utf-8")
    completed = subprocess.run(["omc", str(script)], cwd=output_dir,
                               text=True, capture_output=True, timeout=120)
    csv = output_dir / "GEN7Contact.CubeTableDrop_res.csv"
    record = {"model": "GEN7Contact.CubeTableDrop", "returncode": completed.returncode,
              "omc_stdout": completed.stdout, "omc_stderr": completed.stderr,
              "csv": str(csv) if csv.exists() else None,
              "modelica_source": str(MODEL_DIR / "CubeTableDrop.mo")}
    if completed.returncode == 0 and csv.exists():
        try:
            record["contact_validation"] = validate_result(csv)
        except (ValueError, OSError) as exc:
            record["contact_validation_error"] = str(exc)
    (output_dir / "run.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    if completed.returncode or not csv.exists() or "contact_validation" not in record:
        raise RuntimeError("Contact experiment failed validation; see run.json for diagnostics")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "contact-experiment")
    args = parser.parse_args()
    print(json.dumps(run(args.out), indent=2))
