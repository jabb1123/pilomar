"""Tests for pilomar.core.timer."""

from datetime import timedelta

import pytest

from pilomar.core.time_utils import now_utc
from pilomar.core.timer import ProgressTimer, Timer


class TestTimer:
    def test_not_due_immediately_after_creation(self):
        t = Timer(60)  # 60-second period
        assert t.due() is False

    def test_due_after_period_elapses(self):
        # Create a timer that was triggered 61 seconds ago
        t = Timer(60)
        t.next_trigger = now_utc() - timedelta(seconds=61)
        assert t.due() is True

    def test_due_resets_trigger(self):
        t = Timer(60)
        t.next_trigger = now_utc() - timedelta(seconds=61)
        assert t.due() is True
        # After firing, should not be due again immediately
        assert t.due() is False

    def test_force_trigger(self):
        t = Timer(60)
        t.force_trigger = True
        assert t.due() is True

    def test_skip_events_does_not_queue(self):
        """With skip=True the timer skips missed events so it only fires once."""
        t = Timer(60, skip=True)
        # Manually advance next_trigger into the past to simulate a late trigger
        t.next_trigger = now_utc() - timedelta(seconds=61)
        # First call fires and advances next_trigger to the future
        assert t.due() is True
        # Immediately after, it should NOT fire again
        assert t.due() is False

    def test_set_period_attribute(self):
        t = Timer(60)
        t.period = 120
        assert t.period == 120

    def test_remaining_seconds(self):
        t = Timer(60)
        remaining = t.remaining()
        # Should be 0–60 seconds remaining for a fresh timer
        assert 0 <= remaining <= 61


class TestProgressTimer:
    def test_initial_percent_zero(self):
        pt = ProgressTimer("test", target=100, start=0, initial=0)
        assert pt.get_percent() == pytest.approx(0.0)

    def test_percent_after_increment(self):
        pt = ProgressTimer("test", target=100, start=0, initial=50)
        assert pt.get_percent() == pytest.approx(50.0)

    def test_full_percent(self):
        pt = ProgressTimer("test", target=100, start=0, initial=100)
        assert pt.get_percent() == pytest.approx(100.0)

    def test_increment(self):
        pt = ProgressTimer("test", target=100, start=0)
        pt.increment(10)
        assert pt.current == 10

    def test_update_count(self):
        pt = ProgressTimer("test", target=100, start=0)
        pt.update_count(75)
        assert pt.current == 75

    def test_units_per_second_zero_at_start(self):
        pt = ProgressTimer("test", target=100, start=0, initial=0)
        result = pt.units_per_second()
        assert result == pytest.approx(0.0)

    def test_seconds_to_hms_zero(self):
        pt = ProgressTimer("test", target=100, start=0)
        result = pt.seconds_to_hms(0)
        assert result == "00:00:00"

    def test_seconds_to_hms_one_hour(self):
        pt = ProgressTimer("test", target=100, start=0)
        result = pt.seconds_to_hms(3600)
        assert result == "01:00:00"

    def test_seconds_to_hms_negative(self):
        pt = ProgressTimer("test", target=100, start=0)
        result = pt.seconds_to_hms(-90)
        assert result.startswith("-")
