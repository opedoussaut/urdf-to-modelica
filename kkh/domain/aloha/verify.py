"""Verify frozen generated models without rewriting any generator output."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import time
import uuid
from pathlib import Path

from kkh.engineering.omc import MatResult, OMCService
from .configuration import ROOT, build_manifest
from .build import variable_filter
from .pipeline import Pipeline
from .scenarios import scenarios


def verify(experiment: str = "RightArmReach", output: Path | None = None) -> dict:
    if experiment not in scenarios():
        raise ValueError("Unknown experiment")
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S") + f"-{experiment}-{uuid.uuid4().hex[:8]}"
    output = output or ROOT / "runs" / run_id
    output.mkdir(parents=True, exist_ok=False)
    pipe = Pipeline(experiment, log=lambda *_: None, run_dir=output)
    record = {"run_id": output.name, "experiment": experiment, "mode": "frozen model verification",
              "started": dt.datetime.now(dt.timezone.utc).isoformat(), "success": False,
              "configuration": {"totals": build_manifest()["totals"]},
              "model_sha256": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in (ROOT / "generated/modelica/ALOHA2").rglob("*.mo")}}
    started = time.perf_counter()
    omc = None
    try:
        sc = scenarios()[experiment]
        omc = OMCService(output / "omc")
        record["tools"] = {"omc": omc.version(), "msl": omc.loaded_libraries()}
        record["load"] = omc.load_package(ROOT / "generated/modelica/ALOHA2/package.mo").to_dict()
        model = f"ALOHA2.Experiments.{experiment}"
        record["checks"] = {model: omc.check(model).to_dict()}
        if not record["load"]["ok"] or not record["checks"][model]["ok"]:
            return record
        record["simulation"] = omc.simulate(model, sc["stop_time"], intervals=round(sc["stop_time"] / .02),
                                             variable_filter=variable_filter(sc)).to_dict()
        if record["simulation"]["ok"]:
            mat = MatResult(record["simulation"]["data"]["resultFile"])
            mapping = json.loads((ROOT / "generated/modelica/aloha2_mapping.json").read_text())
            arms = mapping["arms"] if sc["target"] == "assembly" else [mapping["leader"]]
            record["results"] = pipe._extract(mat, arms, sc)
            record["validation"] = pipe._validate(mat, arms, sc)
            record["success"] = record["validation"]["ok"]
    except Exception as exc:
        record["error"] = str(exc)
    finally:
        if omc:
            omc.close()
        record["wall_seconds"] = round(time.perf_counter() - started, 3)
        record["finished"] = dt.datetime.now(dt.timezone.utc).isoformat()
        (output / "report.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


if __name__ == "__main__":
    import sys
    result = verify(sys.argv[1] if len(sys.argv) > 1 else "RightArmReach")
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["success"] else 1)
