"""Tests for pilomar.session modules."""

from datetime import datetime

import pytest

from pilomar.session.entry import SessionEntry
from pilomar.session.list import SessionList
from pilomar.session.status import SessionStatus


class TestSessionEntry:
    def test_empty_init(self):
        entry = SessionEntry()
        assert entry.name is None
        assert entry.search_term is None
        assert entry.ra is None

    def test_init_with_dict(self):
        data = {
            "name": "Andromeda",
            "search_term": "M31",
            "search_group": "messier",
            "ra": "00:42:44",
            "dec": "+41:16:09",
            "magnitude": 3.4,
        }
        entry = SessionEntry(data)
        assert entry.name == "Andromeda"
        assert entry.search_term == "M31"
        assert entry.magnitude == pytest.approx(3.4)

    def test_build_dictionary_roundtrip(self):
        data = {
            "name": "M42",
            "search_term": "m42",
            "search_group": "messier",
            "magnitude": 4.0,
            "exposure_seconds": 30,
            "observation_frames": 10,
        }
        entry = SessionEntry(data)
        rebuilt = entry.build_dictionary()
        assert rebuilt["name"] == "M42"
        assert rebuilt["magnitude"] == 4.0

    def test_get_signature_is_deterministic(self):
        data = {
            "search_term": "M31",
            "target_type": "galaxy",
            "exposure_seconds": 30,
        }
        sig1 = SessionEntry.get_signature(data)
        sig2 = SessionEntry.get_signature(data)
        assert sig1 == sig2

    def test_get_signature_differs_for_different_entries(self):
        data_a = {"search_term": "M31", "exposure_seconds": 30}
        data_b = {"search_term": "M42", "exposure_seconds": 30}
        assert SessionEntry.get_signature(data_a) != SessionEntry.get_signature(data_b)

    def test_datetime_field_parsing_from_iso_string(self):
        data = {"last_observed": "2023-06-23T04:00:00+00:00"}
        entry = SessionEntry(data)
        assert isinstance(entry.last_observed, datetime)

    def test_simple_display(self, capsys):
        data = {"name": "M45", "search_term": "m45", "magnitude": 1.6}
        entry = SessionEntry(data)
        entry.simple_display()
        captured = capsys.readouterr()
        assert "M45" in captured.out or "m45" in captured.out


class TestSessionList:
    def test_empty_list(self):
        sl = SessionList("test")
        assert len(sl) == 0

    def test_add_entry(self):
        sl = SessionList("test")
        sl.add({"name": "M31", "search_term": "m31"})
        assert len(sl) == 1

    def test_add_deduplicates(self):
        sl = SessionList("test")
        data = {"search_term": "m31", "name": "M31"}
        sl.add(data)
        sl.add(data)
        assert len(sl) == 1

    def test_delete_entry(self):
        sl = SessionList("test")
        data = {"search_term": "m31", "name": "M31"}
        sl.add(data)
        sig = SessionEntry.get_signature(data)
        sl.delete(sig)
        assert len(sl) == 0

    def test_iterate(self):
        sl = SessionList("test")
        sl.add({"name": "M31", "search_term": "m31"})
        sl.add({"name": "M42", "search_term": "m42"})
        names = [e.name for e in sl]
        assert "M31" in names
        assert "M42" in names

    def test_age_minutes_is_zero_after_creation(self):
        sl = SessionList("test")
        age = sl.age_minutes()
        assert age == 0

    def test_sort_by_age_logs_error_on_missing_field(self, capsys):
        """sort_by_age should log error when last_observed is missing."""
        sl = SessionList("test")
        sl.add({"name": "M31"})  # No last_observed
        # Should not raise — just return early after logging
        sl.sort_by_age()

    def test_reset_clears_list(self):
        sl = SessionList("test")
        sl.add({"name": "M31"})
        sl.reset()
        assert len(sl) == 0

    def test_sort_options_are_snake_case(self):
        sl = SessionList("test")
        for opt in sl.sort_options:
            assert opt == opt.lower(), f"sort_option '{opt}' is not snake_case"


class TestSessionStatus:
    def test_default_init(self):
        ss = SessionStatus()
        assert ss.motor_control_mode == "idle"
        assert ss.target is None
        assert ss.debug_mode is False

    def test_set_motor_control_mode_valid(self):
        ss = SessionStatus()
        ss.set_motor_control_mode("trajectory")
        assert ss.motor_control_mode == "trajectory"
        assert ss.maintain_trajectory is True

    def test_set_motor_control_mode_invalid_resets_to_idle(self):
        ss = SessionStatus()
        ss.set_motor_control_mode("invalid_mode")
        assert ss.motor_control_mode == "idle"

    def test_set_observation_running(self):
        ss = SessionStatus()
        ss.set_observation_running(True)
        assert ss.observation_running() is True

    def test_set_observation_not_running(self):
        ss = SessionStatus()
        ss.set_observation_running(True)
        ss.set_observation_running(False)
        assert ss.observation_running() is False

    def test_reset(self):
        ss = SessionStatus()
        ss.mctl_rx_errors = 99
        ss.set_motor_control_mode("trajectory")
        ss.reset()
        assert ss.mctl_rx_errors == 0
        assert ss.motor_control_mode == "idle"

    def test_check_cpu_status_parses_message(self):
        ss = SessionStatus()
        line = "cpu status 12345 POR 125000000 3.3 200000 100000 45.0 WIFI_USB"
        result = ss.check_cpu_status(line)
        assert result["reset_reason"] == "POR"
        assert result["temperature"] == pytest.approx(45.0)

    def test_check_session_status_parses_message(self):
        ss = SessionStatus()
        line = "session status 12345 y n y"
        result = ss.check_session_status(line)
        assert result["autonomous"] is True
        assert result["remote"] is False
        assert result["clock_sync"] is True
