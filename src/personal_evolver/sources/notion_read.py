"""B3 + B4 — Notion readers (runtime uses a personal-workspace integration token).

B4 reads the week's entry from the "2026 Journal Tracker" data source (the journal is rows in an
inline DB, verified live). B3 reads dropped links from the Evolution "Inputs" DB. Both fail soft:
a missing entry or unconfigured DB returns empty, never raises, so the synthesis still runs.

The Notion API is hit directly with httpx so this works inside Modal with just the token.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from ..timeweek import WeekWindow

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# locked decision §1 #2 — the journal lives here (data source id, dashes stripped for the API)
JOURNAL_DATA_SOURCE = "d52442f52cf78224a0f78776e6146c0d"


@dataclass
class NotionInput:
    title: str
    url: str
    kind: str  # youtube | article | other
    added_at: str


@dataclass
class NotionBundle:
    journal_text: str | None = None
    inputs: list[NotionInput] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def build_client(token: str) -> httpx.Client:
    return httpx.Client(
        base_url=NOTION_API,
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _plain_text(rich: list[dict]) -> str:
    return "".join(part.get("plain_text", "") for part in rich)


def _date_in_window(value: str | None, window: WeekWindow) -> bool:
    if not value:
        return False
    from datetime import datetime

    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return window.contains(dt)


def read_journal(
    client: httpx.Client, window: WeekWindow, *, data_source: str = JOURNAL_DATA_SOURCE
) -> str | None:
    """Return the window's journal entry text, or None if there isn't one (fails soft)."""
    try:
        resp = client.post(f"/data_sources/{data_source}/query", json={"page_size": 50})
        resp.raise_for_status()
    except httpx.HTTPError:
        return None
    for row in resp.json().get("results", []):
        props = row.get("properties", {})
        date_prop = next(
            (p.get("date", {}).get("start") for p in props.values() if p.get("type") == "date"),
            None,
        )
        if _date_in_window(date_prop, window) or _date_in_window(row.get("created_time"), window):
            # join all rich-text/title properties as the entry body
            chunks: list[str] = []
            for p in props.values():
                if p.get("type") == "title":
                    chunks.append(_plain_text(p.get("title", [])))
                elif p.get("type") == "rich_text":
                    chunks.append(_plain_text(p.get("rich_text", [])))
            body = "\n".join(c for c in chunks if c.strip())
            if body.strip():
                return body
    return None


def read_inputs(
    client: httpx.Client, window: WeekWindow, inputs_db: str | None
) -> list[NotionInput]:
    """Return dropped links added in the window from the Inputs DB. Empty if unconfigured."""
    if not inputs_db:
        return []
    try:
        resp = client.post(f"/data_sources/{inputs_db}/query", json={"page_size": 100})
        resp.raise_for_status()
    except httpx.HTTPError:
        return []
    out: list[NotionInput] = []
    for row in resp.json().get("results", []):
        if not _date_in_window(row.get("created_time"), window):
            continue
        props = row.get("properties", {})
        title = next(
            (_plain_text(p.get("title", [])) for p in props.values() if p.get("type") == "title"),
            "",
        )
        url = next((p.get("url") for p in props.values() if p.get("type") == "url"), "") or ""
        out.append(
            NotionInput(
                title=title or url, url=url, kind="other", added_at=row.get("created_time", "")
            )
        )
    return out
