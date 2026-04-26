"""Tests for pilomar.core.time_utils."""

from datetime import datetime, timezone

import pytest
import pytz

from pilomar.core.time_utils import (
    clean_datetime_string,
    get_clock_offset,
    hr_bytes,
    hr_hertz,
    hr_seconds,
    interpolate,
    local_to_utc,
    now_utc,
    set_clock_offset,
    set_local_timezone,
    utc_to_local,
)


class TestNowUtc:
    def test_returns_datetime(self):
        result = now_utc()
        assert isinstance(result, datetime)

    def test_is_utc_aware(self):
        result = now_utc()
        assert result.tzinfo is not None

    def test_clock_offset_applied(self):
        set_clock_offset(3600)  # +1 hour
        try:
            result = now_utc()
            real = now_utc(real=True)
            diff = (result - real).total_seconds()
            assert abs(diff - 3600) < 2  # within 2 seconds
        finally:
            set_clock_offset(None)

    def test_real_ignores_offset(self):
        set_clock_offset(3600)
        try:
            result = now_utc(real=True)
            assert result.tzinfo is not None
        finally:
            set_clock_offset(None)


class TestClockOffset:
    def test_set_and_get_offset(self):
        set_clock_offset(100.0)
        assert get_clock_offset() == pytest.approx(100.0)
        set_clock_offset(None)
        assert get_clock_offset() is None


class TestTimezoneConversion:
    def test_utc_to_local_no_tz(self):
        """Without a timezone set, utc_to_local returns the input unchanged."""
        dt = datetime(2023, 6, 23, 12, 0, 0, tzinfo=timezone.utc)
        result = utc_to_local(dt)
        assert result == dt

    def test_utc_to_local_with_tz(self):
        tz = pytz.timezone("Europe/Berlin")
        set_local_timezone(tz)
        try:
            dt = datetime(2023, 6, 23, 12, 0, 0, tzinfo=pytz.UTC)
            result = utc_to_local(dt)
            assert result.tzinfo is not None
        finally:
            set_local_timezone(None)

    def test_local_to_utc_no_tz(self):
        dt = datetime(2023, 6, 23, 12, 0, 0)
        result = local_to_utc(dt)
        assert result == dt


class TestHrFormatters:
    def test_hr_seconds_small(self):
        result = hr_seconds(45)
        assert "45" in result

    def test_hr_seconds_minutes(self):
        result = hr_seconds(90)
        assert result  # Just check it returns something

    def test_hr_bytes_bytes(self):
        result = hr_bytes(500)
        assert "500" in result or "B" in result

    def test_hr_bytes_kilobytes(self):
        result = hr_bytes(2048)
        assert result  # Just check it returns something non-empty

    def test_hr_hertz_hz(self):
        result = hr_hertz(500)
        assert result

    def test_hr_hertz_khz(self):
        result = hr_hertz(1500)
        assert result


class TestCleanDatetimeString:
    def test_removes_spaces(self):
        result = clean_datetime_string("2023-06-23 12:30:45")
        assert " " not in result

    def test_removes_colons(self):
        result = clean_datetime_string("2023-06-23 12:30:45")
        assert ":" not in result


class TestInterpolate:
    def test_midpoint(self):
        # interpolate(inp1, res1, inp2, res2, inp3)
        result = interpolate(0.0, 0.0, 1.0, 10.0, 0.5)
        assert result == pytest.approx(5.0)

    def test_at_zero(self):
        result = interpolate(0.0, 0.0, 1.0, 10.0, 0.0)
        assert result == pytest.approx(0.0)

    def test_at_one(self):
        result = interpolate(0.0, 0.0, 1.0, 10.0, 1.0)
        assert result == pytest.approx(10.0)
