"""B2 — Vault connector (the richest reflection signal).

Reads JJ's private knowledge vault from a PRIVATE git repo. Two halves:

  - `ensure_clone()` does a sparse, blobless clone into a Modal-Volume cache (the 108 MB repo is
    never fully transferred; only the 4 reflection dirs are checked out). Auth rides through a
    `GIT_ASKPASS` helper so the PAT never lands in the remote URL, `.git/config`, or argv.
  - `extract_week()` pulls the week's committed reflection: journals + session-logs (by filename
    date), newly added/changed patterns, and corrections added in the window. Works on any local
    clone, so it is unit-testable against a temp git fixture and runs against the live vault.

The git range is `base..head` where base = last commit before the window starts and head = last
commit before it ends; results are then date-filtered to the half-open window.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from ..timeweek import ET, WeekWindow

# The 4 dirs JJ scoped (locked decision §1 #6). Paths are relative to the repo root.
JOURNALS = "agents/claude-code-m4/learning-journals"
SESSION_LOGS = "agents/claude-code-m4/session-logs"
PATTERNS = "agents/claude-code-m4/patterns"
CORRECTIONS = "agents/claude-code-m4/corrections.md"
SCOPE = [JOURNALS, SESSION_LOGS, PATTERNS, CORRECTIONS]

_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
_HASH_RE = re.compile(r"[0-9a-f]{40}")


@dataclass
class VaultBundle:
    journals: list[dict] = field(default_factory=list)  # {date, path, text}
    session_logs: list[dict] = field(default_factory=list)  # {date, path, text}
    new_patterns: list[dict] = field(default_factory=list)  # {name, path}
    new_corrections: list[str] = field(default_factory=list)  # added dated correction headings
    note: str | None = None

    @property
    def is_empty(self) -> bool:
        return not (
            self.journals or self.session_logs or self.new_patterns or self.new_corrections
        )


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def ensure_clone(cache_dir: Path, repo_url: str, token: str) -> Path:
    """Sparse, blobless clone (or refresh) of the scoped dirs into `cache_dir`. Returns the path.

    The PAT is supplied via GIT_ASKPASS so it never appears in the remote URL or argv.
    """
    cache_dir = Path(cache_dir)
    askpass = _write_askpass(token)
    env = {
        **os.environ,
        "GIT_ASKPASS": str(askpass),
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_LFS_SKIP_SMUDGE": "1",  # the 4 text dirs aren't LFS; skip LFS so checkout can't stall
    }
    # url carries a username placeholder only; the password comes from GIT_ASKPASS.
    auth_url = repo_url.replace("https://", "https://x-access-token@")
    try:
        if not (cache_dir / ".git").exists():
            cache_dir.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "clone", "--filter=blob:none", "--no-checkout", auth_url, str(cache_dir)],
                check=True,
                env=env,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "-C", str(cache_dir), "sparse-checkout", "set", *SCOPE],
                check=True,
                env=env,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "-C", str(cache_dir), "checkout"],
                check=True,
                env=env,
                capture_output=True,
                text=True,
            )
            _detokenize_remote(cache_dir, repo_url)
        else:
            subprocess.run(
                ["git", "-C", str(cache_dir), "pull", "--ff-only"],
                check=True,
                env=env,
                capture_output=True,
                text=True,
            )
        return cache_dir
    finally:
        askpass.unlink(missing_ok=True)


def _write_askpass(token: str) -> Path:
    fd, path = tempfile.mkstemp(prefix="evolver-askpass-", suffix=".sh")
    with os.fdopen(fd, "w") as f:
        # GIT_ASKPASS is called with the prompt as argv[1]; echo the token for the password prompt.
        f.write(f'#!/bin/sh\necho "{token}"\n')
    os.chmod(path, 0o700)
    return Path(path)


def _detokenize_remote(repo: Path, clean_url: str) -> None:
    """Ensure the persisted remote has no embedded credential."""
    _git(repo, "remote", "set-url", "origin", clean_url)


def _in_window_date(text: str, window: WeekWindow) -> str | None:
    """Return the YYYY-MM-DD if `text` contains a date inside the window, else None."""
    m = _DATE_RE.search(text)
    if not m:
        return None
    try:
        d = datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=ET)
    except ValueError:
        return None
    return m.group(1) if window.start <= d < window.next_start else None


def _show(repo: Path, ref: str, path: str) -> str:
    try:
        return _git(repo, "show", f"{ref}:{path}")
    except subprocess.CalledProcessError:
        return ""


def _all_paths_under(repo: Path, *dirs: str) -> list[str]:
    """Every path ever touched under `dirs` across ALL branches (deduped)."""
    out = _git(repo, "log", "--all", "--name-only", "--pretty=format:", "--", *dirs)
    return sorted({line.strip() for line in out.splitlines() if line.strip()})


def _newest_commit_for(repo: Path, path: str) -> str:
    return _git(repo, "log", "--all", "-1", "--format=%H", "--", path).strip()


def _windowed_commits_touching(
    repo: Path, window: WeekWindow, *paths: str, grace_days: int = 7
) -> dict[str, str]:
    """{path: newest commit that touched it within [start, next_start+grace)} across ALL branches.

    The grace window catches reflection committed a little after its dated day (late wrap-ups);
    item-level date filtering (filename / heading) stays authoritative for what counts as in-week.
    """
    until = window.next_start + timedelta(days=grace_days)
    out = _git(
        repo, "log", "--all", "--no-merges",
        f"--since={window.start_iso}", f"--until={until.isoformat()}",
        "--name-only", "--pretty=format:%H", "--", *paths,
    )
    result: dict[str, str] = {}
    current = ""
    for line in out.splitlines():
        s = line.strip()
        if not s:
            continue
        if _HASH_RE.fullmatch(s):
            current = s
        else:
            result.setdefault(s, current)
    return result


def extract_week(repo: Path, window: WeekWindow) -> VaultBundle:
    """Extract the window's reflection from a local clone, UNIONED across all branches.

    JJ's wrap-ups scatter across feature branches (main is often stale), so we read every branch:
    journals/session-logs by filename date (robust to late commits), new patterns + corrections
    by a windowed commit scan, all deduped.
    """
    repo = Path(repo)
    bundle = VaultBundle()

    # journals + session-logs: every dated file across all branches, filtered by filename date
    for rel_dir, sink in ((JOURNALS, bundle.journals), (SESSION_LOGS, bundle.session_logs)):
        for path in _all_paths_under(repo, rel_dir):
            if not path.endswith(".md"):
                continue
            day = _in_window_date(Path(path).name, window)
            if day:
                commit = _newest_commit_for(repo, path)
                sink.append({"date": day, "path": path, "text": _show(repo, commit, path)})

    # patterns: added/modified within the window on any branch
    for path in sorted(_windowed_commits_touching(repo, window, PATTERNS)):
        if path.endswith(".md") and "/active/" in path:
            bundle.new_patterns.append({"name": Path(path).stem, "path": path})

    # corrections: in-window dated headings, from any branch's corrections.md touched in-window
    seen: set[str] = set()
    for _path, commit in _windowed_commits_touching(repo, window, CORRECTIONS).items():
        for line in _show(repo, commit, CORRECTIONS).splitlines():
            if line.startswith("###") and _in_window_date(line, window):
                heading = line.lstrip("# ").strip()
                if heading not in seen:
                    seen.add(heading)
                    bundle.new_corrections.append(heading)

    if bundle.is_empty:
        bundle.note = "no vault reflection committed in this window"
    return bundle
