"""Deterministic visual-quality pass: draw the connections OMEdit cannot draw (connect without a Line annotation).

Separate from the repair comparison by design: it runs only on an APPROVED copy (Stage 6), never on the input of the
AI arms, and it changes annotations only (verified: the package text with annotations removed is identical before and
after). Component positions are read through OpenModelica's own annotation API; each missing route becomes an
orthogonal three-segment line between the two components' centres. Quality is measured before/after with the same
Stage 2 graphics check.

    PYTHONPATH=. python -m kkh.workflow.layout <workspace dir> <package name>
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from kkh.engineering.omc import OMCService

from .stage2_check import _placement, graphics
from .stage4_validate import _strip_annotations


def _centre(p: list[float]) -> tuple[float, float]:
    return p[0] + (p[2] + p[4]) / 2, p[1] + (p[3] + p[5]) / 2


def _component(ref: str) -> str:
    """'elbow.flange_a' -> 'elbow'; 'rotational_flange_a[3]' -> 'rotational_flange_a'."""
    return re.sub(r"\[.*?\]", "", ref.split(".")[0]).strip()


def _connect_rx(a: str, b: str) -> re.Pattern:
    tok = lambda s: r"\s*".join(re.escape(x) for x in re.findall(r"\w+|[^\w\s]", s))
    return re.compile(r"connect\s*\(\s*" + tok(a) + r"\s*,\s*" + tok(b) + r"\s*\)\s*;")


def route(p1: tuple[float, float], p2: tuple[float, float]) -> list[list[float]]:
    xm = round((p1[0] + p2[0]) / 2, 1)
    pts = [[round(p1[0], 1), round(p1[1], 1)], [xm, round(p1[1], 1)], [xm, round(p2[1], 1)], [round(p2[0], 1), round(p2[1], 1)]]
    return [pt for i, pt in enumerate(pts) if i == 0 or pt != pts[i - 1]]


def run(ws: Path, package: str, work: Path | None = None) -> dict:
    ws = Path(ws).resolve()
    pkg_dir = ws / "URDFModelica" / "Examples" / package
    omc = OMCService((work or ws.parent / "layout_omc").resolve())
    added, skipped, per_file = [], [], {}
    try:
        omc.load_package(ws / "URDFModelica" / "package.mo")
        prefix = f"URDFModelica.Examples.{package}"
        classes = list(omc.send(f"getClassNames({prefix}, recursive=true)") or ())
        before = graphics(omc, classes)
        for g in before:
            if not g["connections_without_line"]:
                continue
            cls = g["class"]
            comps = omc.send(f"getComponents({cls})") or ()
            centre = {}
            for i, c in enumerate(comps, 1):
                p = _placement(omc.send(f"getNthComponentAnnotation({cls}, {i})"))
                if p:
                    centre[c[1]] = _centre(p)
            rel = cls[len(prefix) + 1:].replace(".", "/") + ".mo"
            f = pkg_dir / rel
            if not f.exists():
                skipped += [{"class": cls, "connection": x, "why": "class file not found"} for x in g["connections_without_line"]]
                continue
            text = per_file.get(f, f.read_text(encoding="utf-8"))
            for conn in g["connections_without_line"]:
                a, b = [s.strip() for s in conn.split(" - ")]
                ca, cb = centre.get(_component(a)), centre.get(_component(b))
                rx = _connect_rx(a, b)
                if not ca or not cb or len(rx.findall(text)) != 1:
                    skipped.append({"class": cls, "connection": conn,
                                    "why": "component without placement" if not ca or not cb else "connect statement not found once"})
                    continue
                pts = ", ".join("{%s, %s}" % (x, y) for x, y in route(ca, cb))
                text = rx.sub(lambda m: m.group(0)[:-1].rstrip() + f"\n    annotation (Line(points = {{{pts}}}, color = {{0, 0, 127}}));", text, count=1)
                added.append({"class": cls, "connection": conn})
            per_file[f] = text
        originals = {f: f.read_text(encoding="utf-8") for f in per_file}
        for f, text in per_file.items():
            if _strip_annotations(text) != _strip_annotations(originals[f]):
                raise RuntimeError(f"layout pass would change more than annotations in {f.name}")
            f.write_text(text, encoding="utf-8")
        omc.close()
        omc = OMCService((work or ws.parent / "layout_omc").resolve())
        omc.load_package(ws / "URDFModelica" / "package.mo")
        after = graphics(omc, classes)
    finally:
        omc.close()
    tot = lambda gs: {"connections": sum(g["connections"] for g in gs),
                      "connections_without_line": sum(len(g["connections_without_line"]) for g in gs)}
    return {"before": tot(before), "after": tot(after), "added": added, "skipped": skipped,
            "files_changed": sorted(f.relative_to(pkg_dir).as_posix() for f in per_file),
            "annotations_only": True}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("ws", type=Path)
    ap.add_argument("package")
    a = ap.parse_args()
    r = run(a.ws, a.package)
    print(json.dumps({k: r[k] for k in ("before", "after", "files_changed")} | {"skipped": len(r["skipped"])}, indent=1))


if __name__ == "__main__":
    main()
