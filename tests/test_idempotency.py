"""Orchestrator idempotency tests (no Modal/network). Locks the crash-safe §10 design:
Notion (queried by week_key) is the source of truth, so reruns and a crash between page-create
and ledger-write never duplicate the weekly page."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from personal_evolver.orchestrate import run_week
from personal_evolver.sources.github import Commit, GitHubBundle, PullRequest
from personal_evolver.state import LedgerStore
from personal_evolver.synthesize import SourceBundle, Synthesis
from personal_evolver.timeweek import ET, week_window

W = week_window(datetime(2026, 6, 8, 9, tzinfo=ET), completed=True)
NOW = "2026-06-08T00:30:00-04:00"


def _sources(_window) -> SourceBundle:
    gh = GitHubBundle(
        repos_touched=["joydai2026-del/a"],
        commits=[Commit("joydai2026-del/a", "s1", "ship a thing", "2026-06-02T10:00:00-04:00")],
        prs_merged=[PullRequest("joydai2026-del/a", 9, "land it", "2026-06-03T10:00:00-04:00", "http://pr/9")],
    )
    return SourceBundle(window=W, github=gh)


def _llm(_prompt: str) -> str:
    return json.dumps(
        {
            "headline": "Shipped a thing.",
            "themes": [{"title": "Build", "summary": "you shipped", "cites": [1]}],
            "recurring_lesson": None,
            "mistake_to_lesson": None,
            "keep_relearning": None,
        }
    )


class FakeNotion:
    def __init__(self) -> None:
        self.pages: dict[str, str] = {}
        self.creates = 0
        self.updates = 0
        self._n = 0

    def find_page_by_week_key(self, week_key: str) -> str | None:
        return self.pages.get(week_key)

    def create_review(self, week_key: str, synthesis: Synthesis) -> str:
        self.creates += 1
        self._n += 1
        pid = f"page-{self._n}"
        self.pages[week_key] = pid
        return pid

    def update_review(self, page_id: str, synthesis: Synthesis) -> None:
        self.updates += 1

    def send_digest(self, text: str) -> None:
        pass


def _run(tmp: Path, notion: FakeNotion):
    return run_week(
        W, sources=_sources, llm=_llm, notion=notion, ledger=LedgerStore(tmp), now_iso=NOW
    )


def test_first_run_creates_and_records(tmp_path: Path) -> None:
    notion = FakeNotion()
    res = _run(tmp_path, notion)
    assert res.created is True
    assert notion.creates == 1
    led = LedgerStore(tmp_path).load(W.key)
    assert led.status == "complete"
    assert led.notion_page_id == res.notion_page_id
    # synthesis.json persisted (also the Phase-2 grounding doc)
    synth_json = (tmp_path / "weeks" / W.key / "synthesis.json").read_text()
    assert json.loads(synth_json)["window_key"] == W.key


def test_rerun_updates_no_duplicate(tmp_path: Path) -> None:
    notion = FakeNotion()
    _run(tmp_path, notion)
    res2 = _run(tmp_path, notion)
    assert res2.created is False
    assert notion.creates == 1  # not duplicated
    assert notion.updates == 1
    assert LedgerStore(tmp_path).load(W.key).retry_count == 1


def test_crash_between_create_and_ledger_does_not_duplicate(tmp_path: Path) -> None:
    notion = FakeNotion()
    _run(tmp_path, notion)  # page created, ledger recorded
    # Simulate a crash AFTER Notion create but BEFORE the ledger captured the page id:
    store = LedgerStore(tmp_path)
    led = store.load(W.key)
    led.notion_page_id = None
    led.status = "writing"
    store.save(led)
    # Re-run: Notion still has the page (source of truth), so we update, not create again.
    res = _run(tmp_path, notion)
    assert res.created is False
    assert notion.creates == 1  # still one page despite the lost ledger pointer


def test_weeks_missing_audio_caps_at_two(tmp_path: Path) -> None:
    store = LedgerStore(tmp_path)
    for key in ("2026-W20", "2026-W21", "2026-W22"):
        store.save_synthesis(key, "{}")
    # newest two missing audio
    missing = store.weeks_missing_audio(limit=2)
    assert missing == ["2026-W22", "2026-W21"]
