"""End-to-end demo on JJ's REAL week (GitHub live + vault from the remote clone).

Two modes:
  dump   : build the real SourceBundle, print stats + the numbered citation index + the prompt.
  render : read a synthesis JSON from /tmp/evolver-synth.json and print the digest + Notion page.

Usage:
  PYTHONPATH=src .venv/bin/python scripts/demo_synthesis.py dump
  PYTHONPATH=src .venv/bin/python scripts/demo_synthesis.py render
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from personal_evolver.sources.github import build_client, fetch_github
from personal_evolver.sources.vault import extract_week
from personal_evolver.synthesize import (
    SourceBundle,
    build_index,
    build_prompt,
    compute_stats,
    parse_synthesis,
    render_digest,
    render_notion_markdown,
)
from personal_evolver.timeweek import ET, week_window

CACHE = Path("/tmp/evolver-vault-cache")
SYNTH = Path("/tmp/evolver-synth.json")


def real_bundle() -> SourceBundle:
    w = week_window(datetime.now(ET), completed=False)  # in-progress week = most data for the demo
    token = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True).stdout.strip()
    with build_client(token) as c:
        gh = fetch_github(w, "joydai2026-del", client=c)
    vault = extract_week(CACHE, w) if CACHE.exists() else None
    return SourceBundle(window=w, github=gh, vault=vault, notion=None)


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "dump"
    b = real_bundle()
    if mode == "dump":
        print("WINDOW:", b.window.key, b.window.start.date(), "->", b.window.next_start.date())
        print("STATS:", json.dumps(compute_stats(b), indent=0))
        print("\nCITATION INDEX (what the LLM may cite, built in code):")
        for c in build_index(b):
            print(f"  [{c.idx}] ({c.kind}) {c.label}")
        print("\n----- PROMPT -----\n")
        print(build_prompt(b, build_index(b)))
    elif mode == "render":
        synth = parse_synthesis(SYNTH.read_text(), build_index(b), b.window, compute_stats(b))
        print("===== PHONE DIGEST =====\n")
        print(render_digest(synth))
        print("\n\n===== NOTION WEEKLY REVIEW PAGE =====\n")
        print(render_notion_markdown(synth))


if __name__ == "__main__":
    main()
