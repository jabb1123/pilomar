#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sky context module for Pilomar.

This module provides a context object that bundles Skyfield-related
dependencies needed by the Target class. This enables dependency
injection rather than relying on global objects.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional
from datetime import datetime

import pytz

from pilomar.config.parameters import Parameters
from pilomar.control.motor import MotorControl
from pilomar.hardware.camera import AstroCamera, AstroSensor


@dataclass
class SkyContext:
    """Bundles Skyfield dependencies for injection into Target class.

    This class encapsulates all the astronomical calculation dependencies
    that the Target class needs, allowing for cleaner dependency injection
    and easier testing.

    Attributes:
        planets: Skyfield planetary ephemeris (e.g., load('de421.bsp'))
        timescale: Skyfield timescale object (ts = load.timescale())
        almanac: Skyfield almanac module for rise/set calculations
        mpc: Skyfield MPC module for comet data
        star_class: Skyfield Star class for creating fixed RA/Dec points
        topos_class: Skyfield Topos class for observer locations
        angle_class: Skyfield Angle class
        planetary_magnitude_func: Function to calculate apparent magnitude
        gm_sun: Gravitational constant for sun (for comet orbits)
        comets_df: Pandas DataFrame of comet data (optional)
    """

    planets: Any
    timescale: Any
    almanac: Any
    mpc: Any
    star_class: Any
    topos_class: Any
    angle_class: Any
    planetary_magnitude_func: Callable
    gm_sun: float
    comets_df: Optional[Any] = None


@dataclass
class TimeContext:
    """Bundles time-related functions for injection.

    Attributes:
        now_skyfield: Callable returning current Skyfield timestamp
        clock_offset: Optional clock offset in seconds for simulation
        utc_to_display: Callable to convert UTC to display timezone
    """

    now_skyfield: Callable[[], Any]
    clock_offset: Optional[float] = None
    utc_to_display: Optional[Callable[[datetime], datetime]] = None

    def ts_to_datetime(self, ts_value) -> datetime:
        """Convert Skyfield time to datetime."""
        return ts_value.utc_datetime()

    def datetime_to_ts(self, dt_value, timescale) -> Any:
        """Convert datetime to Skyfield time."""
        if dt_value.tzinfo is None:
            dt_value = dt_value.replace(tzinfo=pytz.UTC)
        return timescale.from_datetime(dt_value)

    def ts_delta(self, base_ts, timescale, yyyy=0, mm=0, dd=0, h=0, m=0, s=0) -> Any:
        """Add time delta to Skyfield timestamp.

        Args:
            base_ts: Base Skyfield timestamp
            timescale: Skyfield timescale object
            yyyy: Years to add
            mm: Months to add
            dd: Days to add
            h: Hours to add
            m: Minutes to add
            s: Seconds to add

        Returns:
            New Skyfield timestamp
        """
        work_ts = base_ts.utc_datetime()
        return timescale.utc(
            work_ts.year + yyyy,
            work_ts.month + mm,
            work_ts.day + dd,
            work_ts.hour + h,
            work_ts.minute + m,
            work_ts.second + s,
        )


@dataclass
class HardwareContext:
    """Bundles hardware-related dependencies for Target.

    Attributes:
        sensor: Camera sensor object (for pixel dimensions)
        camera: Camera object (for FOV and exposure info)
        motor_controls: List of motor control objects (for visibility checks)
        parameters: Application parameters object
    """

    sensor: Optional[AstroSensor] = None
    camera: Optional[AstroCamera] = None
    motor_controls: Optional[List[MotorControl]] = field(default_factory=list)
    parameters: Optional[Parameters] = None
