#!/usr/bin/env python3
"""Date/time and type conversion utilities."""

# This software is published under the GNU General Public License v3.0.

from datetime import datetime
from typing import Optional
import pytz


def utc_string_to_datetime(utc_value: str) -> Optional[datetime]:
    """Accept a UTC string and convert it into datetime.

    Example: 2023-06-23T04:00:00
    Regardless of any timezone info, UTC is assumed.

    Args:
        utc_value: UTC time string

    Returns:
        datetime object or None if conversion fails
    """
    try:
        if "." in utc_value:
            utc_value = utc_value.split(".")[0]
        if utc_value[-1] != "Z":
            utc_value += "Z"
        dt = datetime.strptime(utc_value, "%Y-%m-%dT%H:%M:%SZ")
        dt = dt.replace(tzinfo=pytz.UTC)
    except Exception:  # pylint: disable=broad-except
        dt = None
    return dt


def dts_to_datetime(utc_value: str) -> Optional[datetime]:
    """Accept a str(datetime) string and convert it into datetime.

    Example: 2023-06-23 04:00:00.00000+00:00
    Regardless of any timezone info, UTC is assumed.

    Args:
        utc_value: datetime string representation

    Returns:
        datetime object or None if conversion fails
    """
    try:
        if "+" in utc_value:
            utc_value = utc_value.split("+")[0]
        if "." in utc_value:
            utc_value = utc_value.split(".")[0]
        dt = datetime.strptime(utc_value, "%Y-%m-%d %H:%M:%S")
        dt = dt.replace(tzinfo=pytz.UTC)
    except Exception:  # pylint: disable=broad-except
        dt = None
    return dt


def string_to_datetime(utc_value: str) -> Optional[datetime]:
    """Accept any string containing a timestamp and convert it into datetime.

    Examples:
        2023-06-23 04:00:00.00000+00:00
        2023-06-23T04:00:00.00000
        2023.06.23 04:00:00

    Regardless of any timezone info, UTC is assumed.
    This is less fussy about the format that the string contains.

    Args:
        utc_value: Timestamp string in various formats

    Returns:
        datetime object or None if conversion fails
    """
    try:
        clean = ""
        # Strip all non-digit characters
        for c in utc_value:
            if "0" <= c <= "9":
                clean += c
        clean = clean + "00000000000000000000"  # Pad right with zeros
        clean = clean[:14]  # Take yyyymmddhhmmss portion

        year = int(clean[:4])
        month = int(clean[4:6])
        day = int(clean[6:8])
        hour = int(clean[8:10])
        minute = int(clean[10:12])
        second = int(clean[12:])

        dt = datetime(year, month, day, hour, minute, second, 0)
        dt = dt.replace(tzinfo=pytz.UTC)
    except Exception:  # pylint: disable=broad-except
        dt = None
    return dt


def is_float(text: str) -> bool:
    """Return TRUE if a string can be converted to a float value.

    Args:
        text: String to test

    Returns:
        True if conversion is possible, False otherwise
    """
    try:
        _ = float(text)
        return True
    except ValueError:
        return False


def is_int(text: str) -> bool:
    """Return TRUE if a string can be converted to an integer value.

    Args:
        text: String to test

    Returns:
        True if conversion is possible, False otherwise
    """
    try:
        _ = int(text)
        return True
    except ValueError:
        return False


def text_to_int(text: str) -> Optional[int]:
    """Convert a character string into an INTEGER value.

    Args:
        text: String to convert

    Returns:
        Integer value or None if conversion fails
    """
    try:
        a = int(text)
    except ValueError:
        a = None
    return a


def text_to_float(text: str) -> Optional[float]:
    """Convert a character string into a FLOAT value.

    Args:
        text: String to convert

    Returns:
        Float value or None if conversion fails
    """
    try:
        a = float(text)
    except ValueError:
        a = None
    return a
