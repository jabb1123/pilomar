from datetime import datetime, timedelta, timezone

import pytz
import os

from utils.text.human_readable import CleanDatetimeString, source_code

clock_offset = None


def ts_to_datetime(tsvalue: object) -> datetime:
    """Convert skyfield time value into datetime value."""
    dtvalue = tsvalue.utc_datetime()
    return dtvalue


def Datetime2Ts(dtvalue):
    """Convert datetime value into skyfield time value."""
    if dtvalue.tzinfo is None:
        dtvalue = dtvalue.replace(
            tzinfo=pytz.UTC
        )  # If timezone is not set, assign UTC.
    tsvalue = ts_from_datetime(dtvalue)
    return tsvalue


def TsDelta(basets, yyyy=0, mm=0, dd=0, h=0, m=0, s=0):
    """A basic 'timedelta' functionality for Skyfield timestamps.
    yyyy = Number of YEARS to add/subtract.
    mm = Number of MONTHS to add/subtract.
    dd = Number of DAYS to add/subtract.
    h = Number of HOURS to add/subtract.
    m = Number of MINUTES to add/subtract.
    s = Number of SECONDS to add/subtract.
    These can be +ve or -ve and of any size, Skyfield will evaluate them to a correct timestamp.
    """
    WorkTs = (
        basets.utc_datetime()
    )  # Convert to DateTime to extract components of the date.
    NewTs = ts.utc(
        WorkTs.year + yyyy,
        WorkTs.month + mm,
        WorkTs.day + dd,
        WorkTs.hour + h,
        WorkTs.minute + m,
        WorkTs.second + s,
    )
    return NewTs


def HmsFromStamp(timestamp: datetime, dateaware=False) -> str:
    """Return the HH:MM:SS part of a timestamp as a string.
    Works with datetime input.
    dateaware = True. If the date is not today, then it shows 'DD HH:MM' instead."""
    result = None
    try:
        if timestamp is None:  # Protect from null values.
            result = ""
        else:
            result = str(timestamp)
            if (
                dateaware and timestamp.date() != now_utc().date()
            ):  # The date is not today.
                result = result[8:16]  # Extract "DD HH:MM"
            else:  # The date is today. Extract "HH:MM:SS"
                result = result.split(" ")[1]
                result = result.split(".")[0]
    except Exception as e:
        print(e)  # Trap all the exception information in the main log file.
        raise Exception(
            "HmsFromStamp() failed."
        ) from e  # Continue with regular exception stack.
    return result


def dts_to_datetime(utcvalue) -> datetime:
    """Accept a str(datetime) string and convert it into datetime.
    Eg 2023-06-23 04:00:00.00000+00:00
    Regardless of any timezone info, UTC is assumed."""
    try:
        if "+" in utcvalue:
            utcvalue = utcvalue.split("+")[0]  # Remove timezone.
        if "." in utcvalue:
            utcvalue = utcvalue.split(".")[0]  # Remove decimal seconds.
        dt = datetime.strptime(utcvalue, "%Y-%m-%d %H:%M:%S")
        dt = dt.replace(tzinfo=pytz.UTC)  # Add UTC timezone.
    except:
        dt = None
    return dt


def now_hour_minute_sec() -> str:
    """Return current time as formatted string.
    Returns HH:MM:SS string for the current time (UTC)"""
    return HmsFromStamp(now_utc())


def UTCStringToDatetime(utcvalue) -> datetime:
    """Accept a UTC string and convert it into datetime.
    Eg 2023-06-23T04:00:00
    Regardless of any timezone info, UTC is assumed."""
    try:
        if "." in utcvalue:
            utcvalue = utcvalue.split(".")[0]  # Remove decimal seconds.
        if utcvalue[-1] != "Z":
            utcvalue += "Z"  # Add missing 'Z' timezone marker.
        dt = datetime.strptime(utcvalue, "%Y-%m-%dT%H:%M:%SZ")
        dt = dt.replace(tzinfo=pytz.UTC)  # Add UTC timezone.
    except:
        dt = None
    return dt


def SetTimeOffset(starttime=None):
    """Given a UTC format datetime string, set the clocks to that time.
    eg 2023-06-23T04:00:00
    This actually calculates a timeoffset which is then applied by all clocks."""
    global clock_offset
    if starttime is not None:  # Offset given.
        # Convert string into datetime type.
        dt = UTCStringToDatetime(starttime)  # Convert to datetime type.
        if dt is not None:  # Successful conversion.
            td = dt - datetime.now(
                timezone.utc
            )  # What's the difference between the clocks.
            clock_offset = td.total_seconds()  # Store offset as total seconds.
        else:  # Didn't convert.
            print(
                "SetTimeOffset(",
                starttime,
                ") Failed to translate into valid datetime. Not changed.",
            )
    else:  # Reset the clock offset.
        clock_offset = None


def now_utc(real=False) -> datetime:  # Many references.
    """Get system clock as UTC (timezone aware)
    Microcontroller and Skyfield are operated in UTC vales.
    All clock-times used in this program use the UTC timestamped clock.
    This should be the only reference to datetime.now() method in the entire
    program. All other uses should refer to this NowUTC() function.
    real=True means that no time offset is applied, you get the true realtime clock value.
    real=False means that any time offset is applied, making the clock run at some other point in time.
    """
    dt = datetime.now(timezone.utc)  # Offset supported.
    if not real and clock_offset is not None:  # Can apply time offset.
        dt = dt + timedelta(seconds=clock_offset)
    return dt


def SourceDate() -> datetime:
    """Return datetime of the modified timestamp of the source file.
    As close as I get to 'version' stamping :)"""
    try:
        sourcefile = source_code()
        t = os.path.getmtime(sourcefile)
        d = datetime.fromtimestamp(t)
    except Exception as e:
        print(e)  # Trap all the exception information in the main log file.
        raise Exception(
            "SourceDate() failed"
        ) from e  # Continue with regular exception handling.
    return d


print("Current time is:", now_utc(), " UTC, offset is", clock_offset, "seconds.")


def UtcTimeStamp() -> str:
    """Return current UTC datetime value as a string of digits. Discard fractions of a second.
    Returns value in string format YYYYMMDDHHMMSS."""
    ds = None
    try:
        ds = str(now_utc()).split(".")[0]
        ds = CleanDatetimeString(ds)
    except Exception as e:
        print(e)  # Trap all the exception information in the main log file.
        raise Exception(
            "UtcTimeStamp() failed."
        ) from e  # Continue with regular exception stack.
    return ds
