"""Tests for week_window() — the one source of truth for 'the week'.

Covers the failure modes the phase-gate reviewers flagged: DST spring-forward / fall-back,
ISO year boundary (week 53), the completed-vs-in-progress flag, and the half-open boundary.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from personal_evolver.timeweek import ET, week_window

UTC = ZoneInfo("UTC")


def _hours(w) -> float:
    # Subtracting two aware datetimes with the SAME ZoneInfo ignores the offset (naive diff),
    # so convert to UTC to measure the TRUE elapsed time across a DST boundary.
    return (w.next_start.astimezone(UTC) - w.start.astimezone(UTC)).total_seconds() / 3600.0


def test_completed_is_the_prior_full_week() -> None:
    # Wed 2026-06-03; the completed week is Mon 05-25 .. Mon 06-01.
    now = datetime(2026, 6, 3, 9, 0, tzinfo=ET)
    w = week_window(now, completed=True)
    assert w.start == datetime(2026, 5, 25, tzinfo=ET)
    assert w.next_start == datetime(2026, 6, 1, tzinfo=ET)
    assert w.key == "2026-W22"


def test_in_progress_week_contains_now() -> None:
    now = datetime(2026, 6, 3, 9, 0, tzinfo=ET)
    w = week_window(now, completed=False)
    assert w.start == datetime(2026, 6, 1, tzinfo=ET)
    assert w.next_start == datetime(2026, 6, 8, tzinfo=ET)
    assert w.key == "2026-W23"
    assert w.contains(now)


def test_half_open_boundary() -> None:
    now = datetime(2026, 6, 3, 9, 0, tzinfo=ET)
    w = week_window(now, completed=False)
    assert w.contains(w.start)  # start is inclusive
    assert not w.contains(w.next_start)  # next_start is exclusive
    # one microsecond before next_start is still in-window
    assert w.contains(w.next_start - timedelta(microseconds=1))


def test_dst_spring_forward_week_is_167_hours() -> None:
    # US DST starts Sun 2026-03-08. Week Mon 03-02 .. Mon 03-09 loses one hour.
    now = datetime(2026, 3, 10, 9, 0, tzinfo=ET)  # the week after, completed -> 03-02..03-09
    w = week_window(now, completed=True)
    assert w.start == datetime(2026, 3, 2, tzinfo=ET)
    assert w.next_start == datetime(2026, 3, 9, tzinfo=ET)
    assert w.start.utcoffset() == timedelta(hours=-5)  # EST
    assert w.next_start.utcoffset() == timedelta(hours=-4)  # EDT
    assert _hours(w) == 167.0


def test_dst_fall_back_week_is_169_hours() -> None:
    # US DST ends Sun 2026-11-01. Week Mon 10-26 .. Mon 11-02 gains one hour.
    now = datetime(2026, 11, 3, 9, 0, tzinfo=ET)  # completed -> 10-26..11-02
    w = week_window(now, completed=True)
    assert w.start == datetime(2026, 10, 26, tzinfo=ET)
    assert w.next_start == datetime(2026, 11, 2, tzinfo=ET)
    assert w.start.utcoffset() == timedelta(hours=-4)  # EDT
    assert w.next_start.utcoffset() == timedelta(hours=-5)  # EST
    assert _hours(w) == 169.0


def test_iso_year_boundary_week_53() -> None:
    # 2026-12-28 is a Monday and ISO week 53 of 2026; the next Monday is 2027-W01.
    now = datetime(2026, 12, 31, 9, 0, tzinfo=ET)  # in-progress week starting 12-28
    w = week_window(now, completed=False)
    assert w.start == datetime(2026, 12, 28, tzinfo=ET)
    assert w.key == "2026-W53"
    nxt = week_window(datetime(2027, 1, 5, 9, 0, tzinfo=ET), completed=False)
    assert nxt.key == "2027-W01"


def test_accepts_utc_input_and_normalizes() -> None:
    # 2026-06-01 03:00 UTC == 2026-05-31 23:00 ET (still the prior in-progress week).
    now_utc = datetime(2026, 6, 1, 3, 0, tzinfo=UTC)
    w = week_window(now_utc, completed=False)
    assert w.start == datetime(2026, 5, 25, tzinfo=ET)  # week of Sun 05-31 starts Mon 05-25
    assert w.key == "2026-W22"
