"""GitHub connector tests (mocked). Exercises the failure modes the reviewers flagged:
collaborator/org repo enumeration + pushed_at stop, cross-branch SHA dedupe, the Search
fallback trigger (422 and the 1,000-result cap), and merged-PR post-filtering.
"""

from __future__ import annotations

import json
from datetime import datetime

import httpx

from personal_evolver.sources.github import (
    fetch_github,
    merged_prs,
)
from personal_evolver.timeweek import ET, week_window

W = week_window(datetime(2026, 6, 3, 9, tzinfo=ET), completed=True)  # 2026-W22: 05-25..06-01
IN = "2026-05-27T10:00:00-04:00"
OUT_AFTER = "2026-06-02T10:00:00-04:00"


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.github.com")


def _json(payload, links: str | None = None) -> httpx.Response:
    headers = {"Link": links} if links else {}
    return httpx.Response(200, content=json.dumps(payload), headers=headers)


def test_active_repos_includes_collaborator_and_stops_on_old() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert "organization_member" in req.url.params["affiliation"]
        return _json(
            [
                {"full_name": "joydai2026-del/owned", "pushed_at": IN},
                {"full_name": "ownly/collab", "pushed_at": "2026-05-28T01:00:00-04:00"},
                {"full_name": "old/stale", "pushed_at": "2026-04-01T00:00:00-04:00"},
            ]
        )

    bundle = fetch_github_repos_only(handler)
    assert bundle == ["joydai2026-del/owned", "ownly/collab"]  # stale dropped


def fetch_github_repos_only(handler):
    from personal_evolver.sources.github import active_repos

    with _client(handler) as c:
        return active_repos(c, W)


def test_search_commits_dedupe_and_postfilter() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        p = req.url.path
        if p == "/user/repos":
            return _json([{"full_name": "joydai2026-del/a", "pushed_at": IN}])
        if p == "/search/commits":
            return _json(
                {
                    "total_count": 3,
                    "items": [
                        _commit("sha1", IN, "first"),
                        _commit("sha1", IN, "first dup"),  # duplicate SHA
                        _commit("sha2", OUT_AFTER, "out of window"),  # filtered
                    ],
                }
            )
        if p == "/search/issues":
            return _json({"items": []})
        raise AssertionError(p)

    with _client(handler) as c:
        bundle = fetch_github(W, "joydai2026-del", client=c)
    assert [x.sha for x in bundle.commits] == ["sha1"]
    assert bundle.totals["commits"] == 1


def test_search_fallback_on_422_uses_branch_walk() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        p = req.url.path
        if p == "/user/repos":
            return _json([{"full_name": "joydai2026-del/a", "pushed_at": IN}])
        if p == "/search/commits":
            return httpx.Response(422, content=json.dumps({"message": "bad query"}))
        if p == "/repos/joydai2026-del/a/branches":
            return _json([{"name": "main"}, {"name": "feat/x"}])
        if p == "/repos/joydai2026-del/a/commits":
            branch = req.url.params["sha"]
            if branch == "feat/x":
                return _json([_repo_commit("shaF", IN, "feature work")])
            return _json([_repo_commit("shaM", IN, "main work")])
        if p == "/search/issues":
            return _json({"items": []})
        raise AssertionError(p)

    with _client(handler) as c:
        bundle = fetch_github(W, "joydai2026-del", client=c)
    assert any("branch walk" in n for n in bundle.notes)
    shas = {x.sha for x in bundle.commits}
    assert shas == {"shaM", "shaF"}
    feat = next(x for x in bundle.commits if x.sha == "shaF")
    assert feat.branch == "feat/x"  # the fallback records the real branch name


def test_search_fallback_on_1k_cap() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        p = req.url.path
        if p == "/user/repos":
            return _json([{"full_name": "joydai2026-del/a", "pushed_at": IN}])
        if p == "/search/commits":
            return _json({"total_count": 5000, "items": [_commit("x", IN, "noise")]})
        if p == "/repos/joydai2026-del/a/branches":
            return _json([{"name": "main"}])
        if p == "/repos/joydai2026-del/a/commits":
            return _json([_repo_commit("real", IN, "real")])
        if p == "/search/issues":
            return _json({"items": []})
        raise AssertionError(p)

    with _client(handler) as c:
        bundle = fetch_github(W, "joydai2026-del", client=c)
    assert {x.sha for x in bundle.commits} == {"real"}


def test_merged_prs_postfilter() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return _json(
            {
                "items": [
                    _pr(1, "shipped in window", IN),
                    _pr(2, "merged later", OUT_AFTER),  # filtered
                ]
            }
        )

    with _client(handler) as c:
        prs = merged_prs(c, "joydai2026-del", W)
    assert [p.number for p in prs] == [1]


# --- payload builders ---
def _commit(sha: str, date: str, msg: str) -> dict:
    return {
        "sha": sha,
        "commit": {"committer": {"date": date}, "message": msg},
        "repository": {"full_name": "joydai2026-del/a"},
    }


def _repo_commit(sha: str, date: str, msg: str) -> dict:
    return {"sha": sha, "commit": {"committer": {"date": date}, "message": msg}}


def _pr(number: int, title: str, merged: str) -> dict:
    return {
        "number": number,
        "title": title,
        "repository_url": "https://api.github.com/repos/joydai2026-del/a",
        "html_url": f"https://github.com/joydai2026-del/a/pull/{number}",
        "pull_request": {"merged_at": merged},
    }
