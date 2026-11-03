"""Full measurement campaign, resumable: conversion comparison with several local models, then AI reviews.

    PYTHONPATH=. python -m kkh.convert.batch --robot aloha_wx250s \
        --models nemotron-3-nano:4b,qwen2.5-coder:7b,qwen3-coder:30b [--run <existing run id>] [--skip-convert]

1. Conversion: all three methods, each AI method once per model (one new run, unless --run reuses one).
2. AI reviews (every model) of: every file that run produced, and every seeded test file
   (kkh/benchmark/detection.MUTATIONS). A review that already exists for the same target, mode and model is skipped,
   so the command can be stopped and started again.
Progress goes to runs/convert/batch_<run>.log; every result is stored where the studio pages read it.
"""
from __future__ import annotations

import argparse
import datetime as dt
import time

from . import review, runner, sources


def _log(f, msg):
    line = f"{dt.datetime.now().strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    f.write(line + "\n")
    f.flush()


def done_reviews(target: dict) -> set[tuple[str, str, str]]:
    return {(r["mode"], r.get("llm_model") or "", r.get("protocol", "v1")) for r in review.list_reviews(target)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--robot", default="aloha_wx250s")
    ap.add_argument("--models", default="nemotron-3-nano:4b,qwen2.5-coder:7b,qwen3-coder:30b")
    ap.add_argument("--run", default="", help="reuse an existing conversion run instead of starting a new one")
    ap.add_argument("--skip-convert", action="store_true")
    ap.add_argument("--seeded-only", action="store_true")
    ap.add_argument("--protocol", default="v1", choices=["v1", "v2"], help="review protocol (see kkh.convert.review.PROTOCOLS)")
    a = ap.parse_args()
    models = [m for m in a.models.split(",") if m]
    run_id = a.run
    sources.RUNS.mkdir(parents=True, exist_ok=True)
    import os
    (sources.RUNS / "batch.pid").write_text(str(os.getpid()))  # Reset refuses while this process lives
    log = open(sources.RUNS / f"batch_{run_id or dt.datetime.now().strftime('%Y%m%d-%H%M')}.log", "a", encoding="utf-8")
    t0 = time.time()
    if not run_id and not a.skip_convert and not a.seeded_only:
        _log(log, f"conversion: {a.robot}, models {models}")
        rep = runner.run_comparison(a.robot, ["llm", "llm_rag", "urdfmodelica"], models=models, log=lambda m: _log(log, m))
        run_id = rep["id"]
        _log(log, f"conversion done: run {run_id}, ranking {rep['ranking']}")
    targets = []
    if run_id and not a.seeded_only:
        rep = runner.load(run_id)
        targets += [{"kind": "conversion", "run": run_id, "mode": k} for k, m in rep["modes"].items() if m.get("main_file")]
    targets += [{"kind": "seeded", "mutation": s["id"]} for s in review.seeded_list()]
    # small models first: early results arrive quickly; the 30B model runs last
    order = sorted(models, key=lambda m: ("30b" in m, m))
    jobs = [(t, mode, m) for m in order for t in targets for mode in ("ai",)]
    _log(log, f"reviews (protocol {a.protocol}): {len(targets)} files x 2 modes x {len(order)} models = {len(jobs)} (existing ones skipped)")
    for n, (t, mode, m) in enumerate(jobs, 1):
        if (mode, m, a.protocol) in done_reviews(t):
            continue
        name = t.get("mutation") or f"{t['run']}:{t['mode']}"
        try:
            r = review.run_review(t, mode, m, protocol=a.protocol)
            s = r["score"]
            _log(log, f"[{n}/{len(jobs)}] {name} {mode} {m}: recall {s['recall']} precision {s['precision']} "
                      f"false alarms {s['false_alarms']} fixed {s['corrections_fixed']}/{s['corrections_proposed']} ({r['seconds']} s)")
        except Exception as exc:  # recorded, never invented; the next run retries it
            _log(log, f"[{n}/{len(jobs)}] {name} {mode} {m}: FAILED {type(exc).__name__}: {str(exc)[:200]}")
    _log(log, f"campaign finished in {round((time.time() - t0) / 60, 1)} min")


if __name__ == "__main__":
    main()
