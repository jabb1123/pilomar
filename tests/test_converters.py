"""Tests for pilomar.core.converters."""

import pytest

from pilomar.core.converters import (
    dts_to_datetime,
    is_float,
    is_int,
    string_to_datetime,
    text_to_float,
    text_to_int,
    utc_string_to_datetime,
)


class TestUtcStringToDatetime:
    def test_basic_iso_string(self):
        result = utc_string_to_datetime("2023-06-23T04:00:00")
        assert result is not None
        assert result.year == 2023
        assert result.month == 6
        assert result.day == 23
        assert result.hour == 4
        assert result.tzinfo is not None

    def test_string_with_fractional_seconds(self):
        result = utc_string_to_datetime("2023-06-23T04:00:00.123456")
        assert result is not None
        assert result.year == 2023

    def test_string_already_has_z(self):
        result = utc_string_to_datetime("2023-06-23T04:00:00Z")
        assert result is not None

    def test_invalid_string_returns_none(self):
        result = utc_string_to_datetime("not-a-date")
        assert result is None

    def test_empty_string_returns_none(self):
        result = utc_string_to_datetime("")
        assert result is None


class TestDtsToDatetime:
    def test_basic_datetime_string(self):
        result = dts_to_datetime("2023-06-23 04:00:00.000000+00:00")
        assert result is not None
        assert result.year == 2023

    def test_no_fractional_no_tz(self):
        result = dts_to_datetime("2023-06-23 04:00:00")
        assert result is not None
        assert result.hour == 4

    def test_invalid_string_returns_none(self):
        result = dts_to_datetime("bad input")
        assert result is None


class TestStringToDatetime:
    def test_iso_string(self):
        result = string_to_datetime("2023-06-23T04:00:00")
        assert result is not None
        assert result.year == 2023

    def test_spaced_format(self):
        result = string_to_datetime("2023-06-23 04:00:00")
        assert result is not None
        assert result.month == 6

    def test_dotted_format(self):
        result = string_to_datetime("2023.06.23 04:00:00")
        assert result is not None
        assert result.day == 23

    def test_invalid_string_returns_none(self):
        result = string_to_datetime("xyz")
        assert result is None


class TestIsFloat:
    def test_integer_string(self):
        assert is_float("42") is True

    def test_float_string(self):
        assert is_float("3.14") is True

    def test_negative_string(self):
        assert is_float("-1.5") is True

    def test_non_numeric(self):
        assert is_float("hello") is False

    def test_empty_string(self):
        assert is_float("") is False


class TestIsInt:
    def test_integer_string(self):
        assert is_int("42") is True

    def test_negative_integer(self):
        assert is_int("-7") is True

    def test_float_string(self):
        assert is_int("3.14") is False

    def test_non_numeric(self):
        assert is_int("hello") is False


class TestTextToInt:
    def test_valid_integer(self):
        assert text_to_int("42") == 42

    def test_negative_integer(self):
        assert text_to_int("-5") == -5

    def test_invalid_returns_none(self):
        assert text_to_int("hello") is None

    def test_float_string_returns_none(self):
        assert text_to_int("3.14") is None


class TestTextToFloat:
    def test_valid_float(self):
        assert text_to_float("3.14") == pytest.approx(3.14)

    def test_integer_string(self):
        assert text_to_float("42") == pytest.approx(42.0)

    def test_invalid_returns_none(self):
        assert text_to_float("hello") is None
