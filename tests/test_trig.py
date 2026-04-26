"""Tests for pilomar.celestial.trig."""

import math

import pytest

from pilomar.celestial.trig import (
    alt_az_to_xyz,
    angle_to_dms,
    angle_to_hms,
    az_alt_text,
    compass_point,
    dms_to_angle,
    hms_to_angle,
    ra_dec_text,
    xyz_to_alt_az,
)


class TestCompassPoint:
    def test_north(self):
        assert compass_point(0) == "N"

    def test_east(self):
        assert compass_point(90) == "E"

    def test_south(self):
        assert compass_point(180) == "S"

    def test_west(self):
        assert compass_point(270) == "W"

    def test_north_again(self):
        assert compass_point(360) == "N"

    def test_custom_four_point(self):
        result = compass_point(90, points=["N", "E", "S", "W"])
        assert result == "E"

    def test_custom_eight_point(self):
        result = compass_point(45, points=["N", "NE", "E", "SE", "S", "SW", "W", "NW"])
        assert result == "NE"


class TestAngleToHms:
    def test_zero_degrees(self):
        h, m, s = angle_to_hms(0)
        assert h == 0
        assert m == 0
        assert s == pytest.approx(0.0)

    def test_180_degrees(self):
        h, m, s = angle_to_hms(180)
        assert h == 12
        assert m == 0
        assert s == pytest.approx(0.0)

    def test_360_degrees(self):
        h, m, s = angle_to_hms(360)
        assert h == 24
        assert m == 0

    def test_15_degrees(self):
        # 15 degrees = 1 hour exactly
        h, m, s = angle_to_hms(15)
        assert h == 1
        assert m == 0


class TestAngleToDms:
    def test_zero(self):
        d, m, s = angle_to_dms(0)
        assert d == 0
        assert m == 0
        assert s == pytest.approx(0.0)

    def test_positive(self):
        d, m, s = angle_to_dms(1.5)
        assert d == 1
        assert m == 30
        assert s == pytest.approx(0.0)

    def test_negative(self):
        d, m, s = angle_to_dms(-1.5)
        # Signs on d or m should reflect negative
        assert d == -1 or m < 0

    def test_whole_degree(self):
        d, m, s = angle_to_dms(45.0)
        assert d == 45
        assert m == 0


class TestHmsToAngle:
    def test_zero(self):
        result = hms_to_angle(0, 0, 0)
        assert result == pytest.approx(0.0)

    def test_twelve_hours(self):
        result = hms_to_angle(12, 0, 0)
        assert result == pytest.approx(180.0)

    def test_one_hour(self):
        result = hms_to_angle(1, 0, 0)
        assert result == pytest.approx(15.0)

    def test_roundtrip(self):
        original = 123.456
        h, m, s = angle_to_hms(original)
        recovered = hms_to_angle(h, m, s)
        assert recovered == pytest.approx(original, abs=0.001)


class TestDmsToAngle:
    def test_zero(self):
        result = dms_to_angle(0, 0, 0)
        assert result == pytest.approx(0.0)

    def test_one_degree(self):
        result = dms_to_angle(1, 0, 0)
        assert result == pytest.approx(1.0)

    def test_30_minutes(self):
        result = dms_to_angle(0, 30, 0)
        assert result == pytest.approx(0.5)

    def test_roundtrip(self):
        original = 47.123
        d, m, s = angle_to_dms(original)
        recovered = dms_to_angle(d, m, s)
        assert recovered == pytest.approx(original, abs=0.001)


class TestAltAzToXyz:
    def test_zenith(self):
        """Alt=90 (zenith), az=0 should give Z=1."""
        x, y, z = alt_az_to_xyz(90, 0)
        assert z == pytest.approx(1.0, abs=1e-9)

    def test_horizon_north(self):
        """Alt=0, az=0 (north) should give Y=1, X=0, Z=0."""
        x, y, z = alt_az_to_xyz(0, 0)
        assert z == pytest.approx(0.0, abs=1e-9)

    def test_unit_vector(self):
        """Result should always be a unit vector (for distance=1)."""
        x, y, z = alt_az_to_xyz(45, 135)
        magnitude = math.sqrt(x**2 + y**2 + z**2)
        assert magnitude == pytest.approx(1.0, abs=1e-9)

    def test_custom_distance(self):
        x, y, z = alt_az_to_xyz(90, 0, distance=2.0)
        magnitude = math.sqrt(x**2 + y**2 + z**2)
        assert magnitude == pytest.approx(2.0, abs=1e-9)


class TestXyzToAltAz:
    def test_zenith_roundtrip(self):
        x, y, z = alt_az_to_xyz(90, 0)
        alt, az = xyz_to_alt_az(x, y, z)
        assert alt == pytest.approx(90.0, abs=0.001)

    def test_horizon_roundtrip(self):
        x, y, z = alt_az_to_xyz(0, 45)
        alt, az = xyz_to_alt_az(x, y, z)
        assert alt == pytest.approx(0.0, abs=0.001)
        assert az == pytest.approx(45.0, abs=0.001)


class TestAzAltText:
    def test_returns_string(self):
        result = az_alt_text(180.0, 45.0)
        assert isinstance(result, str)
        assert len(result) > 0


class TestRaDecText:
    def test_returns_string(self):
        result = ra_dec_text(12.5, 30.0)
        assert isinstance(result, str)
        assert len(result) > 0
