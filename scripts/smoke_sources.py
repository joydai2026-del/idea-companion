"""Live smoke for the source connectors against real local data. Not a unit test.

Usage: PYTHONPATH=src .venv/bin/python scripts/smoke_sources.py
Requires `gh auth token` for GitHub; reads the local vault at ~/Documents/jj-knowledge-vault.
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path

from personal_evolver.sources.github import build_client, fetch_github
from personal_evolver.sources.vault import extract_week
from personal_evolver.timeweek import ET, week_window

VAULT = Path.home() / "Documents" / "jj-knowledge-vault"


def main() -> None:
    token = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True).stdout.strip()
    for completed in (True, False):
        w = week_window(datetime.now(ET), completed=completed)
        label = "completed" if completed else "in-progress"
        print(f"=== {label} {w.key} [{w.start.date()}..{w.next_start.date()}) ===")

        with build_client(token) as c:
            gh = fetch_github(w, "joydai2026-del", client=c)
        print(f"  GitHub: {gh.totals} notes={gh.notes}")

        if VAULT.exists():
            v = extract_week(VAULT, w)
            print(f"  Vault journals={[j['date'] for j in v.journals]} "
                  f"session_logs={[s['date'] for s in v.session_logs]} "
                  f"patterns={[p['name'] for p in v.new_patterns]} "
                  f"corrections={len(v.new_corrections)} note={v.note}")
        print()


if __name__ == "__main__":
    main()
