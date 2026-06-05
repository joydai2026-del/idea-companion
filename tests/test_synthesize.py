"""Synthesis tests with a fake LLM. Locks the phase-gate rules: 2..6 themes, citations resolved
from the code-built index only (no hallucinated cites), automated-commit de-noising, empty-week
floor (no LLM call)."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from personal_evolver.sources.github import Commit, GitHubBundle, PullRequest
from personal_evolver.sources.notion_read import NotionBundle, NotionInput
from personal_evolver.sources.vault import VaultBundle
from personal_evolver.synthesize import (
    SourceBundle,
    build_index,
    compute_stats,
    render_digest,
    synthesize,
)
from personal_evolver.timeweek import ET, week_window

W = week_window(datetime(2026, 6, 3, 9, tzinfo=ET), completed=True)


def _bundle() -> SourceBundle:
    gh = GitHubBundle(
        repos_touched=["joydai2026-del/a"],
        commits=[
            Commit("joydai2026-del/a", "s1", "ship the synthesis brain", "2026-05-27T10:00:00-04:00"),
            Commit("joydai2026-del/a", "s2", "fix the week boundary", "2026-05-28T10:00:00-04:00"),
            Commit("joydai2026-del/a", "a1", "chore: daily outreach health check", "2026-05-29T10:00:00-04:00"),
        ],
        prs_merged=[PullRequest("joydai2026-del/a", 5, "land Phase 1", "2026-05-30T10:00:00-04:00", "http://pr/5")],
    )
    vault = VaultBundle(
        journals=[{"date": "2026-05-27", "path": "x", "text": "learned to verify the live source first"}],
        new_corrections=["verify the live source before asserting (2026-05-27)"],
    )
    notion = NotionBundle(
        journal_text="This week I shipped the synthesis and kept relearning to check live state.",
        inputs=[NotionInput("A talk on agents", "http://yt/1", "youtube", "2026-05-28T00:00:00Z")],
    )
    return SourceBundle(window=W, github=gh, vault=vault, notion=notion)


def test_automated_commits_denoised_in_stats_and_index() -> None:
    b = _bundle()
    stats = compute_stats(b)
    assert stats["commits_substantive"] == 2
    assert stats["commits_automated"] == 1
    labels = [c.label for c in build_index(b)]
    assert not any("health check" in label for label in labels)  # automated excluded from citations
    assert any("synthesis brain" in label for label in labels)


def test_theme_cap_and_citation_resolution() -> None:
    b = _bundle()

    def fake_llm(_prompt: str) -> str:
        # 8 themes (over the cap) and a hallucinated cite [99] that must be dropped
        return json.dumps(
            {
                "headline": "You shipped Phase 1 and re-learned to verify live state.",
                "themes": [
                    {"title": f"Theme {i}", "summary": "did things", "cites": [1, 99] if i == 0 else [2]}
                    for i in range(8)
                ],
                "recurring_lesson": "verify live source (3x)",
                "mistake_to_lesson": None,
                "keep_relearning": "check the deploy target",
            }
        )

    s = synthesize(b, fake_llm)
    assert len(s.themes) == 6  # capped
    # citation 99 was never in the index -> dropped; only real indices survive
    assert 99 not in s.citations
    assert all(idx in {c.idx for c in build_index(b)} for idx in s.citations)
    assert s.keep_relearning == "check the deploy target"


def test_empty_week_takes_floor_without_calling_llm() -> None:
    empty = SourceBundle(window=W, github=GitHubBundle(), vault=VaultBundle(), notion=NotionBundle())

    def exploding_llm(_prompt: str) -> str:
        raise AssertionError("LLM must not be called on an empty week")

    s = synthesize(empty, exploding_llm)
    assert s.is_floor
    assert s.themes == []
    digest = render_digest(s)
    assert "Nothing much" in digest


def test_digest_is_short_and_idless() -> None:
    b = _bundle()
    s = synthesize(b, lambda _p: json.dumps(
        {"headline": "Shipped Phase 1.", "themes": [{"title": "Build", "summary": "x", "cites": [1]}],
         "recurring_lesson": None, "mistake_to_lesson": None, "keep_relearning": "verify live state"}
    ))
    d = render_digest(s)
    assert d.count("\n") <= 6
    assert "joydai2026-del" not in d  # no raw repo IDs in the phone digest


@pytest.mark.parametrize("lang", ["en", "zh", "bilingual"])
def test_prompt_language_note(lang: str) -> None:
    from personal_evolver.synthesize import build_prompt

    b = _bundle()
    p = build_prompt(b, build_index(b), language=lang)
    assert b.window.key in p
