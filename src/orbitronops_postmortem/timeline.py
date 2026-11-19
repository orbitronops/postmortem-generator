"""Timeline helpers: sorting, duration, and phase gaps.

All times are ISO 8601. A timeline with fewer than two parseable
timestamps has no computable duration — the generator says so plainly
instead of inventing one.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .models import TimelineEvent


def parse_ts(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def sort_timeline(events: list[TimelineEvent]) -> list[TimelineEvent]:
    """Sort by timestamp; events without a parseable timestamp go last, in input order."""

    def key(event: TimelineEvent):
        dt = parse_ts(event.ts)
        return (dt is None, dt or datetime.min.replace(tzinfo=timezone.utc))

    return sorted(events, key=key)


def duration_seconds(events: list[TimelineEvent]) -> int | None:
    """Seconds between the first and last parseable timeline events, or None."""
    times = [parse_ts(e.ts) for e in events]
    times = [t for t in times if t is not None]
    if len(times) < 2:
        return None
    return int((max(times) - min(times)).total_seconds())


def format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "unknown — fewer than two timestamped events in the timeline"
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def first_event_of_phase(events: list[TimelineEvent], phase: str) -> TimelineEvent | None:
    for event in sort_timeline(events):
        if event.phase == phase:
            return event
    return None


def phase_gap_seconds(events: list[TimelineEvent], from_phase: str, to_phase: str) -> int | None:
    """Seconds between the first event of one phase and the first of another, or None."""
    start = first_event_of_phase(events, from_phase)
    end = first_event_of_phase(events, to_phase)
    if start is None or end is None:
        return None
    start_dt, end_dt = parse_ts(start.ts), parse_ts(end.ts)
    if start_dt is None or end_dt is None:
        return None
    return int((end_dt - start_dt).total_seconds())
