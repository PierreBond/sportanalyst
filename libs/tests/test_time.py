import pytest
from datetime import datetime, timezone

from sports_common.utils.time import (
    utc_now,
    to_utc,
    date_diff_days,
    format_timestamp,
    parse_timestamp,
    get_start_of_day,
    get_end_of_day,
    is_same_day,
)


class TestTimeUtils:
    def test_utc_now_returns_utc_timezone(self):
        result = utc_now()
        assert result.tzinfo is not None

    def test_to_utc_adds_timezone_if_none(self):
        dt = datetime(2026, 3, 4, 12, 0, 0)
        result = to_utc(dt)
        assert result.tzinfo is not None
        assert result == datetime(2026, 3, 4, 12, 0, 0, tzinfo=timezone.utc)

    def test_to_utc_converts_existing_timezone(self):
        est = timezone.utc
        dt = datetime(2026, 3, 4, 12, 0, 0, tzinfo=est)
        result = to_utc(dt)
        assert result.tzinfo is not None

    def test_date_diff_days(self):
        start = datetime(2026, 3, 1, tzinfo=timezone.utc)
        end = datetime(2026, 3, 4, tzinfo=timezone.utc)
        assert date_diff_days(start, end) == 3

    def test_format_timestamp(self):
        dt = datetime(2026, 3, 4, 12, 0, 0, tzinfo=timezone.utc)
        result = format_timestamp(dt)
        assert "2026-03-04" in result
        assert "12:00:00" in result

    def test_parse_timestamp(self):
        ts = "2026-03-04T12:00:00+00:00"
        result = parse_timestamp(ts)
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 4
        assert result.tzinfo is not None

    def test_get_start_of_day(self):
        dt = datetime(2026, 3, 4, 15, 30, 0, tzinfo=timezone.utc)
        result = get_start_of_day(dt)
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0

    def test_get_end_of_day(self):
        dt = datetime(2026, 3, 4, 15, 30, 0, tzinfo=timezone.utc)
        result = get_end_of_day(dt)
        assert result.hour == 23
        assert result.minute == 59
        assert result.second == 59

    def test_is_same_day_true(self):
        dt1 = datetime(2026, 3, 4, 10, 0, 0, tzinfo=timezone.utc)
        dt2 = datetime(2026, 3, 4, 20, 0, 0, tzinfo=timezone.utc)
        assert is_same_day(dt1, dt2) is True

    def test_is_same_day_false(self):
        dt1 = datetime(2026, 3, 4, 10, 0, 0, tzinfo=timezone.utc)
        dt2 = datetime(2026, 3, 5, 10, 0, 0, tzinfo=timezone.utc)
        assert is_same_day(dt1, dt2) is False
