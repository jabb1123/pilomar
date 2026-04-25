#!/usr/bin/env python3
"""
Constants for the Pilomar application.

This module contains version information, acceptable versions,
and commonly used symbols and constants.
"""

# Version information
# MAJOR.MINOR.MICRO
# - MAJOR = Breaking change. Not compatible with previous versions.
# - MINOR = New features but backwards compatible.
# - MICRO = Development/bugfix releases.
VERSION = "1.2.2"

# Microcontroller versions that this software will work with
# Ignore patch level when comparing
ACCEPTABLE_CONTROLLER_VERSIONS = ["1.0", "1.1", "1.2"]

# Special characters and symbols
# These are used for display and require UTF-8 terminal support
SYMBOLS = {
    "degree": "\u00b0",
    "left": "\u2190",
    "right": "\u2192",
    "up": "\u2191",
    "down": "\u2193",
    "delta": "\u0394",
    "sun": "\u2609",
    "moon": "\u263d",
    "mercury": "\u263f",
    "venus": "\u2640",
    "earth": "\u2641",
    "mars": "\u2642",
    "jupiter": "\u2643",
    "saturn": "\u2644",
    "uranus": "\u2645",
    "neptune": "\u2646",
    "pluto": "\u2647",
    "comet": "\u2604",
    "star": "\u2736",
    "camera": "c",
    "target": "T",
    "iss": "H",
    "css": "#",
}

# Shortcut for the commonly used degree symbol
DEGREE_SYMBOL = SYMBOLS["degree"]

# Menu color scheme defaults
MENU_TITLE_FG = None  # Will be set from Parameters
MENU_TITLE_BG = None  # Will be set from Parameters

# Target type categories
TARGET_TYPES_ALIGNABLE = ["radec", "messier", "ngc", "hipparcos"]
TARGET_TYPES_SOLAR = ["planet", "moon", "sun"]
TARGET_TYPES_SATELLITE = ["earth satellite"]
TARGET_TYPES_FIXED = ["altaz", "aurora"]

# Default values
DEFAULT_HOME_LATITUDE = 51.4769  # Greenwich Observatory
DEFAULT_HOME_LONGITUDE = 0.0
DEFAULT_MIN_SATELLITE_ALTITUDE = 10.0  # degrees
DEFAULT_TRACKING_MAP_SPAN = 10.0  # degrees

# File paths (relative to ProjectRoot)
DATA_DIR = "data"
LOG_DIR = "log"
TEMP_DIR = "temp"

# Data file names
STARNAME_FILE = "starnames.json"
MESSIER_FILE = "messierobjects.json"
METEOR_FILE = "meteors.json"
NGC_FILE = "ngc.json"
HIPPARCOS_CACHE = "hipparcos.pkl"
NGC_CACHE = "ngc.pkl"
SESSIONS_FILE = "pilomar_sessions.json"

# URLs for online data
CELESTRAK_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle"
