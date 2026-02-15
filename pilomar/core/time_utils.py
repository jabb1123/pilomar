#!/usr/bin/env python3
# -*- coding: utf-8 -*-ng.

"""
Time utilities for the Pilomar application.

This module provides time handling functions including UTC/local timezone
conversions, Skyfield timestamp utilities, and human-readable formatting.
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Optional
import pytz


def time_func():
    """
    Returns the current UTC time as a timezone-aware datetime object.
    This function can be overridden for testing or simulation purposes.
    """
    return datetime.now(timezone.utc)


class TimeUtilsState:
    """Internal state for time utilities."""

    def __init__(self):
        self.clock_offset: Optional[float] = None
        self.timescale: Optional[Any] = None
        self.local_tz: Optional[Any] = None
        self.display_tz: Optional[Any] = None


state = TimeUtilsState()


def set_timescale(ts: Any) -> None:
    """Set the global Skyfield timescale object.

    Args:
        ts: Skyfield timescale from load.timescale()
    """
    state.timescale = ts


def set_clock_offset(offset: Optional[float]) -> None:
    """Set the global clock offset for testing/simulation.

    Args:
        offset: Seconds to add to current time, or None to disable
    """
    state.clock_offset = offset


def get_clock_offset() -> Optional[float]:
    """Get the current clock offset."""
    return state.clock_offset


def set_local_timezone(tz: Any) -> None:
    """Set the local timezone.

    Args:
        tz: pytz timezone object
    """
    state.local_tz = tz


def set_display_timezone(tz: Any) -> None:
    """Set the display timezone.

    Args:
        tz: pytz timezone object
    """
    state.display_tz = tz


def now_utc(real: bool = False) -> datetime:
    """Return current UTC datetime.

    This handles the clock offset for simulation purposes.
    Use real=True to get the actual CPU clock time.

    Args:
        real: If True, ignore clock offset and return true current time

    Returns:
        Current UTC datetime
    """
    dt = datetime.now(timezone.utc)
    if not real and state.clock_offset is not None:
        dt = dt + timedelta(seconds=state.clock_offset)
    return dt


def now_utc_str(real: bool = False) -> str:
    """Return current UTC datetime as ISO string.

    Args:
        real: If True, ignore clock offset and return true current time
    """
    return now_utc(real=real).isoformat()


def skyfield_now(real: bool = False) -> Any:
    """Return current time as a Skyfield timestamp.

    Args:
        real: If True, ignore clock offset

    Returns:
        Skyfield Time object
    """
    if state.timescale is None:
        raise RuntimeError("Timescale not initialized. Call set_timescale() first.")

    result = state.timescale.now()
    if not real and state.clock_offset is not None:
        dt = ts_2_datetime(result)
        dt = dt + timedelta(seconds=state.clock_offset)
        result = datetime_2_ts(dt)
    return result


def ts_2_datetime(ts_value: Any) -> datetime:
    """Convert Skyfield timestamp to Python datetime.

    Args:
        ts_value: Skyfield Time object

    Returns:
        UTC datetime
    """
    return ts_value.utc_datetime()


def datetime_2_ts(dt_value: datetime) -> Any:
    """Convert Python datetime to Skyfield timestamp.

    Args:
        dt_value: Python datetime (will assume UTC if no timezone)

    Returns:
        Skyfield Time object
    """
    if state.timescale is None:
        raise RuntimeError("Timescale not initialized. Call set_timescale() first.")

    if dt_value.tzinfo is None:
        dt_value = dt_value.replace(tzinfo=pytz.UTC)
    return state.timescale.from_datetime(dt_value)


def ts_delta(
    base_ts: Any,
    yyyy: int = 0,
    mm: int = 0,
    dd: int = 0,
    h: int = 0,
    m: int = 0,
    s: int = 0,
) -> Any:
    """Add time delta to a Skyfield timestamp.

    Args:
        base_ts: Base Skyfield timestamp
        yyyy: Years to add/subtract
        mm: Months to add/subtract
        dd: Days to add/subtract
        h: Hours to add/subtract
        m: Minutes to add/subtract
        s: Seconds to add/subtract

    Returns:
        New Skyfield timestamp
    """
    if state.timescale is None:
        raise RuntimeError("Timescale not initialized. Call set_timescale() first.")

    work_ts = base_ts.utc_datetime()
    return state.timescale.utc(
        work_ts.year + yyyy,
        work_ts.month + mm,
        work_ts.day + dd,
        work_ts.hour + h,
        work_ts.minute + m,
        work_ts.second + s,
    )


def utc_to_local(dt: datetime) -> datetime:
    """Convert UTC datetime to local timezone.

    Args:
        dt: UTC datetime

    Returns:
        Local datetime
    """
    if state.local_tz is None:
        return dt  # No conversion if timezone not set

    dt_utc = dt.replace(tzinfo=pytz.UTC)
    return dt_utc.astimezone(state.local_tz)


def utc_to_display(dt: datetime) -> datetime:
    """Convert UTC datetime to display timezone.

    Display timezone can be different from local timezone.

    Args:
        dt: UTC datetime

    Returns:
        Datetime in display timezone
    """
    tz = state.display_tz if state.display_tz is not None else state.local_tz
    if tz is None:
        return dt  # No conversion if timezone not set

    dt_utc = dt.replace(tzinfo=pytz.UTC)
    return dt_utc.astimezone(tz)


def local_to_utc(dt: datetime) -> datetime:
    """Convert local datetime to UTC.

    Args:
        dt: Local datetime

    Returns:
        UTC datetime
    """
    if state.local_tz is None:
        return dt  # No conversion if timezone not set

    dt_local = state.local_tz.localize(dt)
    return dt_local.astimezone(pytz.UTC)


def clean_datetime_string(line: str) -> str:
    """Clean a datetime string for use in filenames or commands.

    Removes characters that may cause issues: spaces, colons, etc.

    Args:
        line: Datetime string like "2024-01-15 12:30:45.123456"

    Returns:
        Clean string like "20240115123045"
    """
    result = str(line)
    # Remove fractional seconds
    result = result.split(".", maxsplit=1)[0]
    # Remove problematic characters
    result = result.replace(" ", "")
    result = result.replace(":", "")
    result = result.replace("-", "")
    return result


def hms_from_stamp(timestamp: datetime, dateaware: bool = False) -> str:
    """Extract HH:MM:SS from a timestamp.

    Args:
        timestamp: Datetime object
        dateaware: If True, show date if not today

    Returns:
        Time string "HH:MM:SS" or "DD HH:MM:SS"
    """
    if timestamp is None:
        return "--:--:--"

    try:
        time_str = str(timestamp)[11:19]  # Extract HH:MM:SS
        if dateaware and timestamp.date() != now_utc().date():
            # Add day number if date is not today
            day_str = str(timestamp.day).zfill(2)
            time_str = day_str + " " + time_str
        return time_str
    except Exception:  # pylint: disable=broad-except
        return "--:--:--"


def display_hms_from_stamp(timestamp: datetime, dateaware: bool = False) -> str:
    """Extract HH:MM:SS from a timestamp in display timezone.

    Args:
        timestamp: Datetime object (assumed UTC)
        dateaware: If True, show date if not today

    Returns:
        Time string "HH:MM:SS" or "DD HH:MM:SS"
    """
    if timestamp is None:
        return "--:--:--"

    try:
        display_ts = utc_to_display(timestamp)
        time_str = str(display_ts)[11:19]
        if dateaware:
            now_display = utc_to_display(now_utc())
            if display_ts.date() != now_display.date():
                day_str = str(display_ts.day).zfill(2)
                time_str = day_str + " " + time_str
        return time_str
    except Exception:  # pylint: disable=broad-except
        return "--:--:--"


def now_hms() -> str:
    """Return current UTC time as HH:MM:SS string."""
    return hms_from_stamp(now_utc())


def display_now_hms() -> str:
    """Return current time in display timezone as HH:MM:SS string."""
    return display_hms_from_stamp(now_utc())


def hr_seconds(seconds: int) -> str:
    """Format seconds as human-readable duration string.

    Args:
        seconds: Number of seconds

    Returns:
        String like "02h:30m:45s" or "1d:12h:30m:45s"
    """
    if seconds is None:
        return "--h:--m:--s"

    try:
        seconds = int(seconds)
        days = seconds // 86400
        seconds = seconds % 86400
        hours = seconds // 3600
        seconds = seconds % 3600
        minutes = seconds // 60
        seconds = seconds % 60

        if days > 0:
            return f"{days}d:{hours:02d}h:{minutes:02d}m:{seconds:02d}s"
        else:
            return f"{hours:02d}h:{minutes:02d}m:{seconds:02d}s"
    except Exception:  # pylint: disable=broad-except
        return "--h:--m:--s"


def hr_bytes(byte_count: int) -> str:
    """Format byte count as human-readable size string.

    Args:
        byte_count: Number of bytes

    Returns:
        String like "1.5GB" or "256MB"
    """
    if byte_count is None:
        return "--"

    try:
        byte_count = int(byte_count)
        if byte_count >= 1e12:
            return f"{byte_count / 1e12:.1f}TB"
        elif byte_count >= 1e9:
            return f"{byte_count / 1e9:.1f}GB"
        elif byte_count >= 1e6:
            return f"{byte_count / 1e6:.1f}MB"
        elif byte_count >= 1e3:
            return f"{byte_count / 1e3:.1f}KB"
        else:
            return f"{byte_count}B"
    except Exception:  # pylint: disable=broad-except
        return "--"


def hr_hertz(hertz: int) -> str:
    """Format frequency as human-readable string.

    Args:
        hertz: Frequency in Hz

    Returns:
        String like "1.5GHz" or "800MHz"
    """
    if hertz is None:
        return "--"

    try:
        hertz = int(hertz)
        if hertz >= 1e9:
            return f"{hertz / 1e9:.1f}GHz"
        elif hertz >= 1e6:
            return f"{hertz / 1e6:.1f}MHz"
        elif hertz >= 1e3:
            return f"{hertz / 1e3:.1f}KHz"
        else:
            return f"{hertz}Hz"
    except Exception:  # pylint: disable=broad-except
        return "--"


def utc_time_stamp() -> str:
    """Return current UTC as a timestamp string for filenames.

    Returns:
        String like "20240115_123045"
    """
    ds = str(now_utc()).split(".", maxsplit=1)[0]
    ds = ds.replace(" ", "_").replace(":", "").replace("-", "")
    return ds[:15]  # YYYYMMDD_HHMMSS


def set_time_offset(start_time: Optional[str] = None) -> None:
    """Set the clock offset from a datetime string.

    Args:
        start_time: ISO format datetime string, or None to clear offset
    """
    if start_time is None:
        state.clock_offset = None
    else:
        try:
            target_dt = datetime.fromisoformat(start_time)
            if target_dt.tzinfo is None:
                target_dt = target_dt.replace(tzinfo=timezone.utc)
            td = target_dt - datetime.now(timezone.utc)
            state.clock_offset = td.total_seconds()
        except Exception:  # pylint: disable=broad-except
            state.clock_offset = None


def display_dt(
    dt: datetime, zone_name: Optional[str] = None, decimals: bool = False
) -> str:
    """Format datetime for display.

    Args:
        dt: Datetime to format
        zone_name: Optional timezone name to append
        decimals: If True, include milliseconds

    Returns:
        Formatted datetime string
    """
    if dt is None:
        return "--"

    try:
        if decimals:
            result = str(dt)
        else:
            result = str(dt).split(".", maxsplit=1)[0]

        if zone_name:
            result = f"{result} {zone_name}"

        return result
    except Exception:  # pylint: disable=broad-except
        return "--"


def interpolate(
    inp1: float, res1: float, inp2: float, res2: float, inp3: float
) -> float:
    """Linear interpolation.

    Given inp1 -> res1 and inp2 -> res2 relationship,
    calculate res3 for inp3.

    Args:
        inp1: First input value
        res1: First result value
        inp2: Second input value
        res2: Second result value
        inp3: Input value to interpolate

    Returns:
        Interpolated result
    """
    inp_delta = inp2 - inp1
    res_delta = res2 - res1

    if inp_delta != 0.0:
        return ((inp3 - inp1) * (res_delta / inp_delta)) + res1
    else:
        return res1  # Default to first result if inputs are same
