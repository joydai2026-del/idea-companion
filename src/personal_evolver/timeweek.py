"""The single source of truth for "the week".

Every connector (GitHub, vault, Notion journal, Inputs) and the orchestrator derive their
window from `week_window()`. The interval is half-open `[Mon 00:00, next Mon 00:00)` in
America/New_York, aligned with ISO weeks (which start Monday), so there is no gap, no overlap,
and no dropped Sunday-evening tail.

DST correctness: we never do `timedelta(days=7)` arithmetic on an aware datetime (that subtracts
exactly 168 hours and lands on the wrong wall-clock across a DST boundary). Instead we do the
arithmetic on naive `date` objects and construct a fresh aware `datetime` at midnight, which lets
zoneinfo apply the correct UTC offset for that calendar date.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class WeekWindow:
    """A half-open `[start, next_start)` week in America/New_York."""

    start: datetime  # Monday 00:00 ET, inclusive
    next_start: datetime  # the following Monday 00:00 ET, exclusive
    key: str  # ISO "YYYY-Www" of `start`

    def contains(self, dt: datetime) -> bool:
        """True if tz-aware `dt` falls in the half-open interval."""
        return self.start <= dt.astimezone(ET) < self.next_start

    @property
    def start_iso(self) -> str:
        return self.start.isoformat()

    @property
    def next_start_iso(self) -> str:
        return self.next_start.isoformat()


def _midnight_et(d: date) -> datetime:
    """Midnight ET on calendar date `d`, with the correct (DST-aware) offset for that date."""
    return datetime(d.year, d.month, d.day, tzinfo=ET)


def week_window(now: datetime | None = None, *, completed: bool = True) -> WeekWindow:
    """Return the week as a half-open `[Mon 00:00, next Mon 00:00)` interval in ET.

    completed=True (default): the most-recently-*completed* week, i.e. the one ending at the
    Monday on/just-before `now`. This is what the Monday-morning cron reviews.
    completed=False: the in-progress week containing `now`.
    """
    if now is None:
        now = datetime.now(ET)
    now = now.astimezone(ET)

    # Monday (date) of the week containing `now`. weekday(): Mon=0 .. Sun=6.
    this_monday = now.date() - timedelta(days=now.weekday())

    if completed:
        start_d = this_monday - timedelta(days=7)
        next_d = this_monday
    else:
        start_d = this_monday
        next_d = this_monday + timedelta(days=7)

    iso = start_d.isocalendar()  # (year, week, weekday)
    return WeekWindow(
        start=_midnight_et(start_d),
        next_start=_midnight_et(next_d),
        key=f"{iso[0]}-W{iso[1]:02d}",
    )
