"""Mode 3 - DLR URDFModelica (deterministic, no LLM), for any URDF.

Same documented pre-processing as kkh/benchmark/workflow_a.py (converter defects found during evaluation):
  T1  '/'-namespaced URDF names -> '_' (Modelica class names cannot contain '/')
  T2  <texture> material -> <color rgba> (converter crashes on textures)
  T3  '-' in robot/link/joint names -> '_' (the converter documents that names must not contain '-')
and running the converter with a relative root path (it rewrites '-' to '_' in absolute paths).
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UMO = ROOT / "third_party" / "urdfmodelica" / "URDFModelica"
CONVERTER_COMMIT = "92541b6f6aa76fd510983a25afd3082377b4028f"


def title(name: str) -> str:
    """Converter naming rule: title form (first letter upper case, the rest lower case)."""
    return name.replace("/", "_").replace("-", "_").capitalize()


def preprocess(text: str) -> tuple[str, list[str]]:
    applied = []
    new = re.sub(r'(name|link|joint)="([^"/]*)/([^"]*)"', r'\1="\2_\3"', text)
    if new != text:
        applied.append("T1")
    text, new = new, re.sub(r'<texture filename="[^"]*"\s*/>', '<color rgba="0.1 0.1 0.1 1" />', new)
    if new != text:
        applied.append("T2")
    text, new = new, re.sub(r'((?:name|link|joint)=")([^"]*)"', lambda m: m.group(1) + m.group(2).replace("-", "_") + '"', new)
    if new != text:
        applied.append("T3")
    return new, applied


def convert(urdf: Path, out_dir: Path) -> dict:
    """Run the converter in an isolated copy of the library. Returns paths and the model to check/simulate."""
    t0 = time.time()
    ws = out_dir / "ws"
    if ws.exists():
        shutil.rmtree(ws)
    shutil.copytree(UMO, ws / "URDFModelica", ignore=shutil.ignore_patterns("Reference", "*.PNG", "*.png", "*.stl", "*.STL", "*.dae"))
    text, applied = preprocess(urdf.read_text(encoding="utf-8"))
    (ws / "robot.urdf").write_text(text, encoding="utf-8")
    args = ["URDFModelica/Resources/urdf_to_package.py", "-i", "robot.urdf", "-o", "robot_record.mo", "-r", ".",
            "-p", "URDFModelica/Examples", "-s"]
    p = subprocess.run([sys.executable, *args], cwd=ws, capture_output=True, text=True, timeout=300)
    out = {"mode": "urdfmodelica", "converter_commit": CONVERTER_COMMIT, "preprocessing": applied + ["relative-root"],
           "converter_ok": p.returncode == 0, "llm_calls": 0, "repair_attempts": 0, "human_interventions": 0,
           "converter_log": (p.stdout + p.stderr)[-3000:], "converter_args": args, "returncode": p.returncode}
    (out_dir / "converter.log").write_text(p.stdout + p.stderr, encoding="utf-8")  # full log; the dict keeps the tail
    name = re.search(r'<robot[^>]*\bname="([^"]+)"', text)
    pkg = title(name.group(1)) if name else None
    gen = ws / "URDFModelica" / "Examples" / pkg if pkg else None
    if p.returncode != 0 or not gen or not gen.exists():
        out["error"] = "converter failed" if p.returncode else "converter produced no package"
    else:
        out.update(package_file=ws / "URDFModelica" / "package.mo", model=f"URDFModelica.Examples.{pkg}.{pkg}Test",
                   main_file=gen / f"{pkg}.mo", files=sorted(f.relative_to(gen).as_posix() for f in gen.rglob("*.mo")))
    out["seconds"] = round(time.time() - t0, 2)
    return out
