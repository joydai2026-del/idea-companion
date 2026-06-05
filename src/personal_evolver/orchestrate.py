"""E — the weekly orchestrator (pure logic; the Modal cron in app.py is a thin wrapper).

Crash-safe idempotency (locked §10): Notion is the source of truth. Before writing we query Notion
for a page carrying this `week_key`; if it exists we UPDATE it, else we CREATE one. So a crash
between create and the ledger write cannot duplicate the page, the next run finds it by week_key.

Everything external (sources, the LLM, the Notion writer, the clock) is injected, so the whole
orchestration is unit-testable with fakes and has no Modal/network dependency.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from .state import LedgerStore, RunLedger
from .synthesize import LLM, SourceBundle, Synthesis, synthesis_to_dict, synthesize
from .timeweek import WeekWindow


class NotionWriter(Protocol):
    def find_page_by_week_key(self, week_key: str) -> str | None: ...
    def create_review(self, week_key: str, synthesis: Synthesis) -> str: ...
    def update_review(self, page_id: str, synthesis: Synthesis) -> None: ...
    def send_digest(self, text: str) -> None: ...


@dataclass
class RunResult:
    week_key: str
    notion_page_id: str
    created: bool
    synthesis: Synthesis


def run_week(
    window: WeekWindow,
    *,
    sources: Callable[[WeekWindow], SourceBundle],
    llm: LLM,
    notion: NotionWriter,
    ledger: LedgerStore,
    now_iso: str,
    language: str = "bilingual",
) -> RunResult:
    bundle = sources(window)
    synth = synthesize(bundle, llm, language=language)

    prev = ledger.load(window.key)
    led = prev or RunLedger(week_key=window.key)
    if prev:
        led.retry_count += 1
    led.status = "writing"
    led.updated_at = now_iso
    ledger.save(led)
    ledger.save_synthesis(window.key, json.dumps(synthesis_to_dict(synth), ensure_ascii=False))

    # Notion is the idempotency source of truth, not the ledger.
    existing = notion.find_page_by_week_key(window.key)
    if existing:
        notion.update_review(existing, synth)
        page_id, created = existing, False
    else:
        page_id = notion.create_review(window.key, synth)
        created = True

    led.notion_page_id = page_id
    led.status = "complete"
    led.updated_at = now_iso
    ledger.save(led)
    return RunResult(window.key, page_id, created, synth)
