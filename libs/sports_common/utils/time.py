from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def date_diff_days(start: datetime, end: datetime) -> int:
    start_utc = to_utc(start)
    end_utc = to_utc(end)
    return (end_utc - start_utc).days


def format_timestamp(dt: datetime) -> str:
    return to_utc(dt).isoformat()


def parse_timestamp(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return to_utc(dt)


def get_start_of_day(dt: datetime) -> datetime:
    dt_utc = to_utc(dt)
    return dt_utc.replace(hour=0, minute=0, second=0, microsecond=0)


def get_end_of_day(dt: datetime) -> datetime:
    dt_utc = to_utc(dt)
    return dt_utc.replace(hour=23, minute=59, second=59, microsecond=999999)


def is_same_day(dt1: datetime, dt2: datetime) -> bool:
    dt1_utc = to_utc(dt1)
    dt2_utc = to_utc(dt2)
    return (
        dt1_utc.year == dt2_utc.year
        and dt1_utc.month == dt2_utc.month
        and dt1_utc.day == dt2_utc.day
    )
