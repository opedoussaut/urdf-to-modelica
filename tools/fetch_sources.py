"""Fetch pinned public engineering sources into third_party/ (read-only reference assets).

Usage: python tools/fetch_sources.py
Each source is checked out at the exact commit in config/public_sources.json.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TP = ROOT / "third_party"


def git(*args, cwd=None):
    subprocess.run(["git", "-c", "core.longpaths=true", *args], cwd=cwd, check=True)


def main():
    cfg = json.loads((ROOT / "config" / "public_sources.json").read_text())
    TP.mkdir(exist_ok=True)
    for s in cfg["sources"]:
        d = TP / s["dir"]
        if not (d / ".git").exists():
            args = ["clone", "--filter=blob:none", "--no-checkout", s["url"], str(d)]
            git(*args)
            if s.get("sparse"):
                git("sparse-checkout", "set", *s["sparse"], cwd=d)
        git("fetch", "--depth", "1", "origin", s["commit"], cwd=d)
        git("checkout", "-q", "--detach", s["commit"], cwd=d)
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=d, text=True).strip()
        ok = head == s["commit"]
        print(f"{s['id']:32s} {head[:12]} {'OK' if ok else 'MISMATCH'}")
        if not ok:
            sys.exit(1)


if __name__ == "__main__":
    main()
