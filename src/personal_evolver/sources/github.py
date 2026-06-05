"""B1 — GitHub connector (output signal).

Captures the week's real work, which mostly lives in PRIVATE repos and on FEATURE branches.
The Events API and `affiliation=owner` + default-branch commit queries miss both, so we:

  - enumerate owner + collaborator + org repos, paginated, stopping once `pushed_at < start`;
  - get commits via Search (cross-repo, cross-branch) with an exact post-filter to the half-open
    window, deduped by SHA;
  - fall back to a bounded per-repo / per-branch walk if Search hits its 422 / secondary-limit /
    1,000-result ceiling;
  - capture merged PRs as the higher-altitude "shipped" list.

The HTTP client is injected so tests can drive it with httpx.MockTransport.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import httpx

from ..timeweek import ET, WeekWindow

API = "https://api.github.com"
_PER_REPO_BRANCH_CAP = 20  # bound the fallback so a repo with many stale branches can't blow up


@dataclass(frozen=True)
class Commit:
    repo: str
    sha: str
    message: str
    ts: str  # ISO committer date
    branch: str | None = None


@dataclass(frozen=True)
class PullRequest:
    repo: str
    number: int
    title: str
    merged_at: str
    url: str


@dataclass
class GitHubBundle:
    repos_touched: list[str] = field(default_factory=list)
    commits: list[Commit] = field(default_factory=list)
    prs_merged: list[PullRequest] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def totals(self) -> dict[str, int]:
        return {
            "repos_touched": len(self.repos_touched),
            "commits": len(self.commits),
            "prs_merged": len(self.prs_merged),
        }


def build_client(token: str) -> httpx.Client:
    """A configured GitHub client. The token rides in the Authorization header only."""
    return httpx.Client(
        base_url=API,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=30.0,
    )


def _paginate(client: httpx.Client, url: str, params: dict | None = None) -> list[dict]:
    """Follow GitHub `Link: rel=next` pagination, returning all items (list or search `items`)."""
    out: list[dict] = []
    next_url: str | None = url
    next_params = dict(params or {})
    while next_url:
        resp = client.get(next_url, params=next_params)
        resp.raise_for_status()
        body = resp.json()
        items = body["items"] if isinstance(body, dict) and "items" in body else body
        out.extend(items)
        next_url = resp.links.get("next", {}).get("url")
        next_params = {}  # the Link url already carries the query
    return out


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(ET)


def active_repos(client: httpx.Client, window: WeekWindow) -> list[str]:
    """Repos (owner+collaborator+org) pushed within the window, as `owner/name`."""
    repos: list[str] = []
    page = 1
    while True:
        resp = client.get(
            "/user/repos",
            params={
                "per_page": 100,
                "sort": "pushed",
                "affiliation": "owner,collaborator,organization_member",
                "page": page,
            },
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        stop = False
        for r in batch:
            pushed = _parse_ts(r["pushed_at"])
            if pushed < window.start:
                stop = True  # sorted desc by pushed -> everything after is older
                break
            if pushed < window.next_start:
                repos.append(r["full_name"])
        if stop or len(batch) < 100:
            break
        page += 1
    return repos


def _search_commits(
    client: httpx.Client, login: str, window: WeekWindow
) -> tuple[list[Commit], bool]:
    """Primary path. Returns (commits, ok). ok=False signals 'fall back to per-repo walk'."""
    q = (
        f"author:{login} "
        f"committer-date:>={window.start_iso} committer-date:<{window.next_start_iso}"
    )
    commits: list[Commit] = []
    seen: set[str] = set()
    page = 1
    while True:
        resp = client.get(
            "/search/commits",
            params={"q": q, "per_page": 100, "page": page},
            headers={"Accept": "application/vnd.github.cloak-preview+json"},
        )
        if resp.status_code in (403, 422):  # secondary rate limit / bad query -> fall back
            return commits, False
        resp.raise_for_status()
        body = resp.json()
        if body.get("total_count", 0) > 1000 and page == 1:
            return commits, False  # >1k cap: Search can't page past 1000; use the bounded walk
        for it in body.get("items", []):
            sha = it["sha"]
            if sha in seen:
                continue
            ts = _parse_ts(it["commit"]["committer"]["date"])
            if not window.contains(ts):  # exact half-open post-filter (Search dates are coarse)
                continue
            seen.add(sha)
            commits.append(
                Commit(
                    repo=it["repository"]["full_name"],
                    sha=sha,
                    message=it["commit"]["message"].splitlines()[0],
                    ts=ts.isoformat(),
                )
            )
        if not resp.links.get("next"):
            break
        page += 1
    return commits, True


def _walk_repo_commits(
    client: httpx.Client, repos: list[str], login: str, window: WeekWindow
) -> list[Commit]:
    """Bounded fallback: per repo, walk branches whose tip is in-window (cap N), dedupe by SHA."""
    commits: list[Commit] = []
    seen: set[str] = set()
    for repo in repos:
        branches = _paginate(client, f"/repos/{repo}/branches", {"per_page": 100})
        picked = 0
        for br in branches:
            if picked >= _PER_REPO_BRANCH_CAP:
                break
            branch = br["name"]
            try:
                items = _paginate(
                    client,
                    f"/repos/{repo}/commits",
                    {
                        "sha": branch,
                        "author": login,
                        "since": window.start_iso,
                        "until": window.next_start_iso,
                        "per_page": 100,
                    },
                )
            except httpx.HTTPStatusError:
                continue
            if not items:
                continue
            picked += 1
            for it in items:
                sha = it["sha"]
                ts = _parse_ts(it["commit"]["committer"]["date"])
                if sha in seen or not window.contains(ts):
                    continue
                seen.add(sha)
                commits.append(
                    Commit(
                        repo=repo,
                        sha=sha,
                        message=it["commit"]["message"].splitlines()[0],
                        ts=ts.isoformat(),
                        branch=branch,
                    )
                )
    return commits


def merged_prs(client: httpx.Client, login: str, window: WeekWindow) -> list[PullRequest]:
    start_d = window.start.date().isoformat()
    end_d = window.next_start.date().isoformat()
    q = f"author:{login} is:pr is:merged merged:{start_d}..{end_d}"
    items = _paginate(client, "/search/issues", {"q": q, "per_page": 100})
    prs: list[PullRequest] = []
    for it in items:
        merged_at = it.get("pull_request", {}).get("merged_at") or it.get("closed_at")
        if merged_at and not window.contains(_parse_ts(merged_at)):
            continue
        repo = it["repository_url"].split("/repos/")[-1]
        prs.append(
            PullRequest(
                repo=repo,
                number=it["number"],
                title=it["title"],
                merged_at=merged_at or "",
                url=it["html_url"],
            )
        )
    return prs


def fetch_github(window: WeekWindow, login: str, *, client: httpx.Client) -> GitHubBundle:
    """Top-level B1 entry point: the week's repos, commits (cross-branch), and merged PRs."""
    bundle = GitHubBundle()
    bundle.repos_touched = active_repos(client, window)
    commits, ok = _search_commits(client, login, window)
    if not ok:
        bundle.notes.append("github: search hit a limit, used bounded per-repo branch walk")
        commits = _walk_repo_commits(client, bundle.repos_touched, login, window)
    bundle.commits = commits
    bundle.prs_merged = merged_prs(client, login, window)
    return bundle
