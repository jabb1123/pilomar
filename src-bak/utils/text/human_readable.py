import sys
from utils.text.textcolor import TextColor


def human_readable_bytes(bytecount: int) -> str:
    """Turn a large number into human readable format.
    Turns 1024 * 1024 into 1MB etc."""
    try:
        line, _, _ = TextColor.human_readable_number(bytecount, base=1024, decimals=1)
        line += "b"
    except Exception as e:
        print(e)  # Trap all the exception information iWn the main log file.
        print("HRBytes: textcolor.HRNumber(", bytecount, ") failed.")
        raise Exception(
            "HRBytes() failed."
        ) from e  # Continue with regular exception stack.
    return line


def human_readable_hertz(hertz: int) -> str:
    """Turn a large number into human readable format.
    Turns 1,000,000 into 1MHz etc."""
    try:
        line, _, _ = TextColor.human_readable_number(hertz, base=1000, decimals=1)
        line += "Hz"
    except Exception as e:
        print(e)  # Trap all the exception information in the main log file.
        print("HRHertz: textcolor.HRNumber(", hertz, ") failed.")
        raise Exception(
            "HRHertz() failed."
        ) from e  # Continue with regular exception stack.
    return line


def human_readable_seconds(seconds: int) -> str:
    """Turn a number of seconds into days:hours:minutes:seconds"""
    line = None
    try:
        d, remainder = divmod(seconds, 24 * 60 * 60)
        h, remainder = divmod(remainder, 60 * 60)
        m, s = divmod(remainder, 60)
        line = (
            str(int(h)).rjust(2, "0")
            + "h:"
            + str(int(m)).rjust(2, "0")
            + "m:"
            + str(int(s)).rjust(2, "0")
            + "s"
        )
        if d > 0:  # Only show days if needed.
            line = str(int(d)) + "d:" + line
    except Exception as e:
        print(e)  # Trap all the exception information in the main log file.
        raise Exception(
            "HRSeconds() failed."
        ) from e  # Continue with regular exception stack.
    return line


def source_code() -> str:
    """Return the filename of the source code being executed."""
    return sys.argv[0]


def clean_datetime_string(line: str) -> str:  # Many references.
    """Remove all the special characters from a timestamp string.
    Converts things like YYYY-MM-DD HH:MM:SS into YYYYMMDDHHMMSS"""
    try:
        if not isinstance(line, str):
            line = str(line)  # Auto-convert into a string if it isn't already.
        for a in ["-", " ", ":", "."]:
            line = line.replace(a, "")
        line = line[:14]  # Only accurate to SECONDS currently.
    except Exception as e:
        print(e)  # Trap all the exception information in the main log file.
        raise Exception(
            "CleanDatetimeString() failed."
        ) from e  # Continue with regular exception stack.
    return line


def safe_name(text: str) -> str:
    """Convert text into a 'safe' set of characters for the disc operations."""
    if not isinstance(text, str):
        text = str(text)  # Convert to string if it isn't already.
    replacelist = [" ", "/"]  # Characters that will be replaced with '_'
    removelist = ["'", '"', "(", ")"]  # Characters that will be removed.
    try:
        for c in replacelist:
            text = text.replace(c, "_")
        for c in removelist:
            text = text.replace(c, "")
    except Exception as e:
        print(e)  # Trap all the exception information in the main log file.
        raise Exception(
            "SafeName() failed."
        ) from e  # Continue with regular exception stack.
    return text


def dictionary_to_string(rawdict: dict) -> str:
    """Convert Python dictionary into simpler string for display purposes."""
    try:
        result = ""
        for key, value in rawdict.items():
            if len(result) > 0:
                result += ", "
            result += str(key) + "=" + str(value)
    except Exception as e:
        print("DictionaryToString:", str(e), ":", str(rawdict))
        result = ""
    return result
