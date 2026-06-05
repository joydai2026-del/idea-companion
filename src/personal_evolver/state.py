"""Per-week run ledger on the Modal Volume (the cron's private state).

This is a cache/observability ledger, NOT the only idempotency source: Notion (queried by
`week_key`) is the source of truth for "did this week's page already get made" (see orchestrate.py).
The ledger lets a resumed run see status + retry count and avoids redundant work.

Writer ownership (locked §10): the cron owns `weeks/<key>/{run.json, synthesis.json}`. The audio
side-car owns `weeks/<key>/audio/*` and never touches these files. No shared mutable file.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

# status lifecycle: pending -> writing -> complete | failed
STATUSES = ("pending", "writing", "complete", "failed")


@dataclass
class RunLedger:
    week_key: str
    status: str = "pending"
    notion_page_id: str | None = None
    audio_status: str | None = None  # set by the side-car's audio.json, mirrored on read
    source_hashes: dict = field(default_factory=dict)
    retry_count: int = 0
    updated_at: str = ""  # ISO; passed in by the caller (no wall-clock in library code)


class LedgerStore:
    """Reads/writes per-week ledgers under a Volume root. Single-writer: the weekly cron only."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _dir(self, week_key: str) -> Path:
        return self.root / "weeks" / week_key

    def _path(self, week_key: str) -> Path:
        return self._dir(week_key) / "run.json"

    def load(self, week_key: str) -> RunLedger | None:
        p = self._path(week_key)
        if not p.exists():
            return None
        return RunLedger(**json.loads(p.read_text(encoding="utf-8")))

    def save(self, ledger: RunLedger) -> None:
        d = self._dir(ledger.week_key)
        d.mkdir(parents=True, exist_ok=True)
        # atomic write: temp + replace, so a crash never leaves a half-written ledger
        tmp = d / "run.json.tmp"
        tmp.write_text(json.dumps(asdict(ledger), indent=2), encoding="utf-8")
        tmp.replace(d / "run.json")

    def save_synthesis(self, week_key: str, synthesis_json: str) -> None:
        d = self._dir(week_key)
        d.mkdir(parents=True, exist_ok=True)
        (d / "synthesis.json").write_text(synthesis_json, encoding="utf-8")

    def weeks_missing_audio(self, limit: int = 2) -> list[str]:
        """Most-recent weeks with a synthesis but no episode (for the audio side-car's catch-up)."""
        weeks_dir = self.root / "weeks"
        if not weeks_dir.exists():
            return []
        out: list[str] = []
        for d in sorted((p for p in weeks_dir.iterdir() if p.is_dir()), reverse=True):
            if (d / "synthesis.json").exists() and not (d / "audio" / "episode.mp3").exists():
                out.append(d.name)
            if len(out) >= limit:
                break
        return out
