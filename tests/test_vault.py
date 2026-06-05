"""Vault connector tests against a temp git fixture with backdated commits.

Covers: journals/session-logs by filename date, new patterns via base..head, corrections added
in-window (not before/after), and the empty-week note (window predating all history).
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from personal_evolver.sources.vault import extract_week
from personal_evolver.timeweek import ET, week_window

W = week_window(datetime(2026, 6, 3, 9, tzinfo=ET), completed=True)  # 2026-W22: 05-25..06-01


def _run(cwd: Path, *args: str, date: str | None = None) -> None:
    env = dict(os.environ)
    if date:
        env["GIT_COMMITTER_DATE"] = date
        env["GIT_AUTHOR_DATE"] = date
    subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, env=env, capture_output=True, text=True
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "vault"
    r.mkdir()
    _run(r, "init", "-q", "-b", "main")
    _run(r, "config", "user.email", "t@t")
    _run(r, "config", "user.name", "t")
    a = r / "agents/claude-code-m4"
    (a / "learning-journals").mkdir(parents=True)
    (a / "session-logs").mkdir(parents=True)
    (a / "patterns/active").mkdir(parents=True)

    # commit 1 — before the window
    (a / "corrections.md").write_text("# Corrections\n\n### old lesson (2026-05-20)\n")
    (a / "patterns/active/old.md").write_text("old")
    _run(r, "add", "-A")
    _run(r, "commit", "-qm", "c1", date="2026-05-20T10:00:00-04:00")

    # commit 2 — in the window
    (a / "learning-journals/2026-05-27-topic.md").write_text("journal body")
    (a / "session-logs/2026-05-27.md").write_text("session log body")
    (a / "patterns/active/new.md").write_text("new pattern")
    with (a / "corrections.md").open("a") as f:
        f.write("\n### new lesson (2026-05-27)\n")
    _run(r, "add", "-A")
    _run(r, "commit", "-qm", "c2", date="2026-05-27T10:00:00-04:00")

    # commit 3 — after the window
    (a / "learning-journals/2026-06-03-late.md").write_text("late")
    with (a / "corrections.md").open("a") as f:
        f.write("\n### later lesson (2026-06-03)\n")
    _run(r, "add", "-A")
    _run(r, "commit", "-qm", "c3", date="2026-06-03T10:00:00-04:00")
    return r


def test_journals_by_filename_date(repo: Path) -> None:
    b = extract_week(repo, W)
    assert [j["date"] for j in b.journals] == ["2026-05-27"]  # not the 06-03 one
    assert b.journals[0]["text"] == "journal body"


def test_session_logs_by_filename_date(repo: Path) -> None:
    b = extract_week(repo, W)
    assert [s["date"] for s in b.session_logs] == ["2026-05-27"]


def test_new_patterns_in_range(repo: Path) -> None:
    b = extract_week(repo, W)
    assert [p["name"] for p in b.new_patterns] == ["new"]  # 'old' was committed before the window


def test_corrections_added_in_window_only(repo: Path) -> None:
    b = extract_week(repo, W)
    joined = " | ".join(b.new_corrections)
    assert "new lesson" in joined
    assert "old lesson" not in joined  # before window
    assert "later lesson" not in joined  # after window


def test_empty_week_note(repo: Path) -> None:
    empty = week_window(datetime(2026, 3, 10, 9, tzinfo=ET), completed=True)  # 03-02..03-09
    b = extract_week(repo, empty)
    assert b.is_empty
    assert b.note
