"""Utility modules for the Pilomar telescope control system."""

# Avoid circular imports by not importing from utils.params here
# Import what you need directly in your modules
from utils.conversion import bool_to_string, string_to_bool
from utils.statics import DEGREE_SYMBOL
from utils.version import VERSION, ACCEPTABLECONTROLLERVERSIONS

__all__ = [
    "bool_to_string",
    "string_to_bool",
    "DEGREE_SYMBOL",
    "VERSION",
    "ACCEPTABLECONTROLLERVERSIONS",
]
