"""D — the synthesis brain.

Takes the week's source bundles and produces the structured weekly review. Two correctness rules
the phase-gate locked in:

  - **Citations are built in code**, never by the LLM. We hand the model a numbered index of REAL
    items (commit SHAs, PR urls, journal entries, corrections, links); the model references them by
    [n]; we map [n] back to the real item. The model cannot invent a citation.
  - **Themes are bounded 2..6** with one optional recurring-lesson callback (the 3+-occurrences
    rule). An empty week takes the floor path (a short honest digest, not a fabricated review).

The LLM is injected as `Callable[[str], str]` returning JSON, so production uses Anthropic and the
prompt can be validated against any caller.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field

from .sources.github import GitHubBundle
from .sources.notion_read import NotionBundle
from .sources.vault import VaultBundle
from .timeweek import WeekWindow

LLM = Callable[[str], str]
_AUTOMATED = ("daily outreach health check", "health check", "auto-", "[bot]")


@dataclass
class Citation:
    idx: int
    kind: str  # commit | pr | journal | correction | input
    label: str
    url: str | None = None


@dataclass
class Theme:
    title: str
    summary: str
    cite_ids: list[int] = field(default_factory=list)


@dataclass
class Synthesis:
    window_key: str
    headline: str
    themes: list[Theme]
    recurring_lesson: str | None
    mistake_to_lesson: str | None
    keep_relearning: str | None
    stats: dict
    citations: dict[int, Citation]
    is_floor: bool = False


@dataclass
class SourceBundle:
    window: WeekWindow
    github: GitHubBundle | None = None
    vault: VaultBundle | None = None
    notion: NotionBundle | None = None


# ----------------------------- citation index -----------------------------
def build_index(bundle: SourceBundle) -> list[Citation]:
    """A numbered index of the week's REAL items. Automated commits are collapsed, not listed."""
    cites: list[Citation] = []
    n = 0

    def add(kind: str, label: str, url: str | None = None) -> None:
        nonlocal n
        n += 1
        cites.append(Citation(n, kind, label, url))

    gh = bundle.github
    if gh:
        for pr in gh.prs_merged:
            add("pr", f"PR #{pr.number} {pr.title} ({pr.repo})", pr.url)
        for c in gh.commits:
            if any(tok in c.message.lower() for tok in _AUTOMATED):
                continue  # de-noise: automated commits are counted in stats, not cited
            add("commit", f"{c.repo.split('/')[-1]}: {c.message}", None)
    if bundle.vault:
        for j in bundle.vault.journals:
            add("journal", f"journal {j['date']}: {j['text'][:80].strip()}")
        for corr in bundle.vault.new_corrections:
            add("correction", f"correction: {corr[:90]}")
    if bundle.notion:
        for inp in bundle.notion.inputs:
            add("input", f"consumed: {inp.title}", inp.url)
    return cites


def compute_stats(bundle: SourceBundle) -> dict:
    gh = bundle.github
    automated = 0
    substantive = 0
    if gh:
        for c in gh.commits:
            if any(tok in c.message.lower() for tok in _AUTOMATED):
                automated += 1
            else:
                substantive += 1
    return {
        "repos_touched": len(gh.repos_touched) if gh else 0,
        "commits_substantive": substantive,
        "commits_automated": automated,
        "prs_merged": len(gh.prs_merged) if gh else 0,
        "journals": len(bundle.vault.journals) if bundle.vault else 0,
        "new_corrections": len(bundle.vault.new_corrections) if bundle.vault else 0,
        "new_patterns": len(bundle.vault.new_patterns) if bundle.vault else 0,
        "inputs": len(bundle.notion.inputs) if bundle.notion else 0,
    }


def is_empty(stats: dict) -> bool:
    keys = ("commits_substantive", "prs_merged", "journals", "new_corrections", "inputs")
    return not any(stats[k] for k in keys)


# ----------------------------- prompt -----------------------------
def build_prompt(bundle: SourceBundle, index: list[Citation], language: str = "bilingual") -> str:
    lines = "\n".join(f"[{c.idx}] ({c.kind}) {c.label}" for c in index)
    journal = (bundle.notion.journal_text if bundle.notion else None) or "(no journal this week)"
    corrections = "\n".join(
        f"- {c}" for c in (bundle.vault.new_corrections if bundle.vault else [])
    ) or "(none)"
    lang_note = {
        "en": "Write in English.",
        "zh": "用中文写。",
        "bilingual": "English, mirroring key phrases in 中文 if the journal is Chinese.",
    }.get(language, "Write in English.")

    return f"""You are JJ's weekly-evolution synthesizer. Turn a week of real work + reflection
into a tight, honest review she can read in 30 seconds and hear on a walk. {lang_note}

THE WEEK ({bundle.window.key}, {bundle.window.start.date()} to {bundle.window.next_start.date()}).

Numbered source items (cite ONLY by these numbers, never invent one):
{lines}

Her Notion weekly-journal entry (her own words):
\"\"\"{journal[:1500]}\"\"\"

Corrections/lessons logged this week:
{corrections[:1200]}

Rules:
- Cluster into 2 to 6 THEMES (not more). Each theme: a short title, a 1-2 sentence summary in plain
  language (no jargon, no IDs), and the citation numbers it draws from.
- Down-weight repetitive automated commits; focus on substantive work and what she learned.
- If a lesson recurs 3+ times (across corrections/journal), surface ONE recurring-lesson callback;
  else null.
- Name "the mistake that became a lesson" and "what you keep relearning" if present, else null.
- Lead with a single headline takeaway.

Return ONLY this JSON (no prose around it):
{{"headline": "...",
  "themes": [{{"title": "...", "summary": "...", "cites": [1,2]}}],
  "recurring_lesson": "..." or null,
  "mistake_to_lesson": "..." or null,
  "keep_relearning": "..." or null}}"""


# ----------------------------- run + parse -----------------------------
def synthesize(bundle: SourceBundle, llm: LLM, *, language: str = "bilingual") -> Synthesis:
    stats = compute_stats(bundle)
    if is_empty(stats):
        return Synthesis(
            window_key=bundle.window.key,
            headline="A quiet week, nothing substantial logged.",
            themes=[],
            recurring_lesson=None,
            mistake_to_lesson=None,
            keep_relearning=None,
            stats=stats,
            citations={},
            is_floor=True,
        )
    index = build_index(bundle)
    raw = llm(build_prompt(bundle, index, language))
    return parse_synthesis(raw, index, bundle.window, stats)


def parse_synthesis(raw: str, index: list[Citation], window: WeekWindow, stats: dict) -> Synthesis:
    data = json.loads(_strip_fences(raw))
    by_idx = {c.idx: c for c in index}
    used: dict[int, Citation] = {}
    themes: list[Theme] = []
    for t in data.get("themes", [])[:6]:  # enforce the 6-theme ceiling defensively
        cites = [i for i in t.get("cites", []) if i in by_idx]
        for i in cites:
            used[i] = by_idx[i]
        themes.append(Theme(title=t["title"], summary=t["summary"], cite_ids=cites))
    return Synthesis(
        window_key=window.key,
        headline=data.get("headline", ""),
        themes=themes,
        recurring_lesson=data.get("recurring_lesson"),
        mistake_to_lesson=data.get("mistake_to_lesson"),
        keep_relearning=data.get("keep_relearning"),
        stats=stats,
        citations=used,
    )


def synthesis_to_dict(s: Synthesis) -> dict:
    """Serialize for the Volume (`synthesis.json`); doubles as the Phase-2 voice-agent grounding."""
    return {
        "window_key": s.window_key,
        "headline": s.headline,
        "themes": [
            {"title": t.title, "summary": t.summary, "cite_ids": t.cite_ids} for t in s.themes
        ],
        "recurring_lesson": s.recurring_lesson,
        "mistake_to_lesson": s.mistake_to_lesson,
        "keep_relearning": s.keep_relearning,
        "stats": s.stats,
        "citations": {
            str(i): {"kind": c.kind, "label": c.label, "url": c.url} for i, c in s.citations.items()
        },
        "is_floor": s.is_floor,
    }


def _strip_fences(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        s = s.rsplit("```", 1)[0]
    return s.strip()


# ----------------------------- renders -----------------------------
def render_digest(s: Synthesis) -> str:
    """The phone (Telegram) digest: lead with the takeaway, <=6 lines, no IDs."""
    if s.is_floor:
        return f"🧘 Week {s.window_key}\n{s.headline}\nNothing much to review this week."
    st = s.stats
    head = (
        f"🧠 Your week {s.window_key}\n"
        f"{st['commits_substantive']} commits · {st['prs_merged']} PRs · "
        f"{st['journals']} journals · {st['new_corrections']} lessons · {st['inputs']} links"
    )
    body = "\n".join(f"• {t.title}" for t in s.themes[:3])
    extra = f"\n🔁 You keep relearning: {s.keep_relearning}" if s.keep_relearning else ""
    return f"{head}\n{s.headline}\n{body}{extra}"


def render_notion_markdown(s: Synthesis) -> str:
    """The Notion Weekly Review page body (skimmable; tables/headers > prose)."""
    out = [f"# Week {s.window_key} — {s.headline}", ""]
    st = s.stats
    out += [
        "**Stats:** "
        f"{st['commits_substantive']} substantive commits ({st['commits_automated']} automated) · "
        f"{st['prs_merged']} PRs · {st['repos_touched']} repos · {st['journals']} journals · "
        f"{st['new_corrections']} lessons · {st['new_patterns']} patterns · {st['inputs']} inputs",
        "",
        "## Themes",
    ]
    for t in s.themes:
        cited = ", ".join(_cite_label(s.citations.get(i)) for i in t.cite_ids if i in s.citations)
        out.append(f"### {t.title}\n{t.summary}" + (f"\n_Sources: {cited}_" if cited else ""))
    if s.recurring_lesson:
        out += ["", f"> 🔁 **Recurring lesson:** {s.recurring_lesson}"]
    if s.mistake_to_lesson:
        out += ["", f"> ⚠️ **Mistake → lesson:** {s.mistake_to_lesson}"]
    if s.keep_relearning:
        out += ["", f"> 🔂 **You keep relearning:** {s.keep_relearning}"]
    return "\n".join(out)


def _cite_label(c: Citation | None) -> str:
    if not c:
        return ""
    return f"[{c.label}]({c.url})" if c.url else c.label
