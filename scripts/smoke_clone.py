"""Validate the REAL Modal path: sparse blobless clone of the private vault + extract_week.

Usage: PYTHONPATH=src .venv/bin/python scripts/smoke_clone.py
Uses `gh auth token` as the clone credential and a throwaway cache dir under /tmp.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

from personal_evolver.sources.vault import ensure_clone, extract_week
from personal_evolver.timeweek import ET, week_window

CACHE = Path("/tmp/evolver-vault-cache")
REPO = "https://github.com/joydai2026-del/jjknowledgevault.git"


def main() -> None:
    token = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True).stdout.strip()
    if CACHE.exists():
        shutil.rmtree(CACHE)

    t0 = time.time()
    ensure_clone(CACHE, REPO, token)
    print(f"clone+sparse-checkout: {time.time() - t0:.1f}s")
    du = subprocess.run(["du", "-sh", str(CACHE)], capture_output=True, text=True).stdout.strip()
    print(f"cache size: {du}")
    # prove the token did not persist in the remote config
    cfg = subprocess.run(
        ["git", "-C", str(CACHE), "remote", "get-url", "origin"], capture_output=True, text=True
    ).stdout.strip()
    print(f"remote (must be tokenless): {cfg}")

    for completed in (True, False):
        w = week_window(datetime.now(ET), completed=completed)
        t1 = time.time()
        b = extract_week(CACHE, w)
        label = "completed" if completed else "in-progress"
        print(f"\n=== {label} {w.key} [{w.start.date()}..{w.next_start.date()}) ({time.time()-t1:.1f}s) ===")
        print(" journals:", [j["date"] for j in b.journals])
        print(" session-logs:", [s["date"] for s in b.session_logs])
        print(" new patterns:", [p["name"] for p in b.new_patterns])
        print(" new corrections:", len(b.new_corrections), "->", [c[:50] for c in b.new_corrections[:3]])
        print(" note:", b.note)


if __name__ == "__main__":
    main()
