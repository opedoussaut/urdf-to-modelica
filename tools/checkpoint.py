"""Non-destructive recovery checkpoint of the project (nothing in the repository is modified).

Writes to E:/users/opt2.ai/NOVA/ai-kkh-preserved/<label>-<timestamp>/:
  repository.bundle         git bundle --all (every branch, tag and commit)
  working-tree.patch        uncommitted tracked changes (git diff HEAD), if any
  untracked/                untracked, non-ignored files, if any
  user-data/studio.sqlite3  consistent copy via the SQLite backup API (chats, trajectories, model revisions)
  user-data/...             copilot audits, studio model working copies, validation and run reports (JSON only)
  manifest.json             SHA-256 of every file

Excluded: .venv, node_modules, web/dist, build, third_party (re-fetchable, pinned), license files,
simulation result binaries (*.mat), large benchmark candidate copies, the live data directory.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST_ROOT = ROOT.parent / "ai-kkh-preserved"
EXCLUDE_SUFFIX = {".mat", ".license", ".lic", ".key", ".exe", ".dll", ".o", ".c", ".h", ".libs", ".log"}
COPY_TREES = ["runs/copilot", "runs/studio/models", "runs/studio/validation"]
REPORT_NAMES = {"report.json", "results.json", "trial.json", "metrics.json"}


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*args, **kw):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, **kw)


def main(label: str = "checkpoint") -> Path:
    dest = DEST_ROOT / f"{label}-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}"
    dest.mkdir(parents=True, exist_ok=False)
    git("bundle", "create", str(dest / "repository.bundle"), "--all")
    diff = git("diff", "HEAD", "--binary").stdout
    if diff:
        (dest / "working-tree.patch").write_bytes(diff)
    untracked = git("ls-files", "--others", "--exclude-standard", text=True).stdout.split()
    for rel in untracked:
        src = ROOT / rel
        if src.suffix.lower() in EXCLUDE_SUFFIX or not src.is_file():
            continue
        (dest / "untracked" / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest / "untracked" / rel)
    ud = dest / "user-data"
    db = ROOT / "runs/studio/studio.sqlite3"
    if db.exists():
        (ud / "runs/studio").mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True) as src, \
                sqlite3.connect(ud / "runs/studio/studio.sqlite3") as out:
            src.backup(out)
    for tree in COPY_TREES:
        base = ROOT / tree
        for f in base.rglob("*") if base.exists() else []:
            if f.is_file() and f.suffix.lower() not in EXCLUDE_SUFFIX and f.stat().st_size < 20_000_000:
                target = ud / f.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, target)
    for f in (ROOT / "runs").rglob("*.json"):
        rel = f.relative_to(ROOT)
        if f.name in REPORT_NAMES and "ALOHA2" not in rel.parts and "omc" not in rel.parts \
               :
            target = ud / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, target)
    files = {p.relative_to(dest).as_posix(): {"sha256": sha(p), "bytes": p.stat().st_size}
             for p in dest.rglob("*") if p.is_file()}
    manifest = {"created": dt.datetime.now(dt.timezone.utc).isoformat(), "source": str(ROOT),
                "head": git("rev-parse", "HEAD", text=True).stdout.strip(),
                "branch": git("rev-parse", "--abbrev-ref", "HEAD", text=True).stdout.strip(),
                "uncommitted_patch": bool(diff), "untracked_files": len(untracked),
                "excluded": "venv, node_modules, web/dist, build, third_party, licenses/keys, *.mat, benchmark model copies",
                "files": files}
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=1))
    git("bundle", "verify", str(dest / "repository.bundle"))
    print(dest, len(files), "files", round(sum(f["bytes"] for f in files.values()) / 1e6, 1), "MB")
    return dest


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "checkpoint")
