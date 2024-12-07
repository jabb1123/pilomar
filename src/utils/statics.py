# ///////////////////////////////////////////////////////////////////////////////////
# Utility functions.
# ///////////////////////////////////////////////////////////////////////////////////

VERSION = "1.1.0"  # Shared with microcontroller. # Make sure the microcontroller accepts any new version number.
# print("Version:",VERSION)
ACCEPTABLECONTROLLERVERSIONS = [
    "1.0"
]  # Microcontroller versions that this will work with. Ignore patch level.

RASPISTILL_SYSTEMS = [
    "wheezy",
    "jessie",
    "stretch",
    "buster",
]  # These all came with raspistill for camera support.

SUPPORTED_SYSTEMS = [
    "3/buster/32",
    "4/buster/32",
    "4/bookworm/64",
    "5/bookworm/64",
]  # The software is designed to run under these hardware/os combinations.


# Special characters.
# The terminal will need to be UTF-8 too. If not, these will look corrupted.
SYMBOLS = {
    "degree": "\u00B0",
    "left": "\u2190",
    "right": "\u2192",
    "up": "\u2191",
    "down": "\u2193",
    "delta": "\u0394",
    "sun": "\u2609",
    "moon": "\u263D",
    "mercury": "\u263F",
    "venus": "\u2640",
    "earth": "\u2641",
    "mars": "\u2642",
    "jupiter": "\u2643",
    "saturn": "\u2644",
    "uranus": "\u2645",
    "neptune": "\u2646",
    "pluto": "\u2647",
    "ceres": "\u26B3",
    "pallas": "\u26B4",
    "juno": "\u26B5",
    "vesta": "\u26B6",
    "astraea": "\u2BD9",
    "flora": "\u2698",
    "hygiea": "\u2695",
    "chiron": "\u26B7",
    "pholus": "\u2BDB",
    "aries": "\u2648",
    "taurus": "\u2649",
    "gemini": "\u264A",
    "cancer": "\u264B",
    "leo": "\u264C",
    "virgo": "\u264D",
    "libra": "\u264E",
    "scorpio": "\u264F",
    "sagittarius": "\u2650",
    "capricorn": "\u2651",
    "aquarius": "\u2652",
    "pisces": "\u2653",
    "ophiuchus": "\u26CE",
    "comet": "\u2604",
    "star": "\u2736",
    "camera": "\u00A9",
    "target": "T",
    "iss": "H",
    "css": "#",
}

DEGREE_SYMBOL = SYMBOLS["degree"]  # For typing speed, it's used a lot.
