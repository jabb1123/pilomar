#!/usr/bin/env python3
"""
Target chooser module for the Pilomar application.

This module provides functions for selecting observation targets from
various catalogs:
- Messier objects
- NGC objects
- Hipparcos stars
- Comets (from Minor Planet Center)
- Meteor showers
- Solar system objects
- Satellites
- Custom RA/Dec or Alt/Az positions
- Aurora observation points
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from skyfield.api import Star
from skyfield.data import mpc

from pilomar.core.base import AttributeMaster


@dataclass
class TargetSelectionContext:
    """Context for target selection operations.

    This provides the dependencies needed by target chooser functions,
    avoiding global state.
    """

    # Catalog data
    messier: dict[str, dict]
    meteors: dict[str, dict]
    hipparcos_df: Any  # pandas DataFrame
    ngc_df: Any  # pandas DataFrame
    comets_df: Any  # pandas DataFrame

    # Name lists for selection menus
    messier_numlist: list[str]
    messier_namelist: list[str]
    meteor_namelist: list[str]
    ngc_namelist: list[str]
    comet_list: list[str]
    satellite_list: list[str]

    # Skyfield objects
    planets: Any  # Skyfield ephemeris
    timescale: Any  # Skyfield timescale

    # Constants
    gm_sun: float  # Solar gravitational parameter

    # Hardware context
    camera: Any | None = None
    motor_controls: list[Any] | None = None
    home_latitude: float = 0.0

    # Callbacks for logging and UI
    logger: Any | None = None
    input_func: Callable = input  # Can be replaced for testing
    print_func: Callable = print  # Can be replaced for testing

    # UI components (text color, etc.)
    textcolor: Any | None = None
    list_chooser_class: type | None = None


def _safe_name(name: str) -> str:
    """Convert a name to a safe format for filenames.

    Removes spaces and special characters.
    """
    result = str(name).replace(" ", "_")
    # Remove other problematic characters
    for char in ["/", "\\", ":", "*", "?", '"', "<", ">", "|", "(", ")"]:
        result = result.replace(char, "")
    return result


def _text_to_int(text: str) -> int | None:
    """Convert text to integer, returning None if invalid."""
    try:
        return int(text)
    except (ValueError, TypeError):
        return None


def _text_to_float(text: str) -> float | None:
    """Convert text to float, returning None if invalid."""
    try:
        return float(text)
    except (ValueError, TypeError):
        return None


def _hms_to_angle(h: float, m: float, s: float) -> float:
    """Convert hours/minutes/seconds to degrees."""
    total_hours = h + m / 60 + s / 3600
    return total_hours * 15


def _dms_to_angle(d: float, m: float, s: float) -> float:
    """Convert degrees/minutes/seconds to decimal degrees."""
    sign = 1 if d >= 0 else -1
    return sign * (abs(d) + m / 60 + s / 3600)


def _create_star(ra_hours: tuple, dec_degrees: tuple) -> Any:
    """Create a Skyfield Star object (lazy import).

    Args:
        ra_hours: Tuple of (hours, minutes, seconds)
        dec_degrees: Tuple of (degrees, minutes, seconds)

    Returns:
        Skyfield Star object
    """
    return Star(ra_hours=ra_hours, dec_degrees=dec_degrees)


def _star_from_dataframe(row: Any) -> Any:
    """Create a Skyfield Star from a DataFrame row (lazy import).

    Args:
        row: Pandas DataFrame row with star data

    Returns:
        Skyfield Star object
    """
    return Star.from_dataframe(row)


def _get_comet_orbit(row: Any, timescale: Any, gm_sun: float) -> Any:
    """Create a comet orbit object (lazy import).

    Args:
        row: Pandas row with comet data
        timescale: Skyfield timescale
        gm_sun: Solar gravitational parameter

    Returns:
        Skyfield comet orbit
    """
    return mpc.comet_orbit(row, timescale, gm_sun)


class TargetChooser(AttributeMaster):
    """Provides methods for selecting observation targets from various catalogs."""

    def __init__(self, ctx: TargetSelectionContext):
        """Initialize with context containing catalog data and dependencies.

        Args:
            ctx: Context with all required dependencies
        """
        super().__init__()
        self.ctx = ctx

    def log(self, *args, level: str = "info", terminal: bool = True):
        """Log a message via ctx.logger, falling back to print."""
        if self.ctx.logger:
            self.ctx.logger.Log(*args, level=level, terminal=terminal)
        elif terminal:
            self.ctx.print_func(*args)

    def _input(self, prompt: str) -> str:
        """Get input from user."""
        if self.ctx.textcolor:
            prompt = self.ctx.textcolor.cyan(prompt)
        return self.ctx.input_func(prompt)

    def _print(self, *args, **kwargs):
        """Print output."""
        self.ctx.print_func(*args, **kwargs)

    def _make_list_chooser(self, items: list[str], compress: bool = True):
        """Create a list chooser for selection."""
        if self.ctx.list_chooser_class:
            return self.ctx.list_chooser_class(items, compress=compress)
        return None

    def choose_messier(
        self, prechosen: str | None = None, size_warning: bool = True
    ) -> dict | None:
        """Select a Messier object.

        Args:
            prechosen: Pre-selected target name (skip prompt if valid)
            size_warning: Warn if object is small in resulting images

        Returns:
            Target information dict, or None if cancelled
        """
        result = ""

        while result == "":
            if prechosen is None:
                search = self._input("Enter Messier target (number, name, ? or 'x'): ")
            else:
                search = prechosen

            if search == "?":
                self._print(f"Recognised catalog IDs: {self.ctx.messier_numlist}")
                self._print(f"Recognised names: {self.ctx.messier_namelist}")
                continue

            search = search.lower()
            if search == "x":
                return None

            # Search by catalog number or name
            for key, value in self.ctx.messier.items():
                if key.lower() == search:
                    result = key.lower()
                    self.log(
                        f"ChooseMessier: Found by catalog number {key}", terminal=False
                    )
                    break
                name = value.get("name", "")
                if name[: len(search)].lower() == search:
                    result = key.lower()
                    self.log(
                        f"ChooseMessier: Found by name {name}, catalog {key}",
                        terminal=False,
                    )
                    break

            if result == "":
                if prechosen is not None:
                    self.log(
                        f"ChooseMessier: Prechosen {prechosen} not recognised",
                        terminal=False,
                    )
                    return None
                self._print("Messier: Nothing matched, try again.")

        # Build target info
        entry = (
            self.ctx.messier[result.upper()]
            if result.upper() in self.ctx.messier
            else self.ctx.messier.get(result, {})
        )

        # Calculate target size
        width = entry.get("width")
        height = entry.get("height")
        size_deg = None
        if width or height:
            size_arcmin = max(width or 0, height or 0)
            size_deg = _dms_to_angle(0, size_arcmin, 0)

            if size_warning and self.ctx.camera:
                size_pix = size_deg * getattr(
                    self.ctx.camera, "PixelsPerFovDegreeWidth", 1
                )
                if size_pix < 10:
                    self.log(
                        f"Target is quite small, about {int(size_pix)} pixels",
                        terminal=True,
                    )

        return {
            "name": _safe_name(result),
            "handle": _create_star(
                (entry["ra"][0], entry["ra"][1], entry["ra"][2]),
                (entry["dec"][0], entry["dec"][1], entry["dec"][2]),
            ),
            "objecttype": entry.get("type"),
            "constellation": entry.get("constellation"),
            "description": entry.get("description"),
            "magnitude": entry.get("magnitude"),
            "searchgroup": "messier",
            "searchterm": result,
            "diameter": size_deg,
        }

    def choose_ngc(self, prechosen: str | None = None) -> dict | None:
        """Select an NGC object.

        Args:
            prechosen: Pre-selected target name (skip prompt if valid)

        Returns:
            Target information dict, or None if cancelled
        """
        result = ""
        df_row = {}
        search = None

        while result == "":
            if prechosen is None:
                chooser = self._make_list_chooser(self.ctx.ngc_namelist)
                search = (
                    chooser.Prompt() if chooser else self._input("Enter NGC name: ")
                )
            else:
                search = prechosen

            if search is None:
                return None

            # Search in NGC name list
            for name in self.ctx.ngc_namelist:
                if name == search:
                    result = name.lower()
                    df_row = self.ctx.ngc_df.loc[self.ctx.ngc_df["name"] == name].iloc[
                        0
                    ]
                    self.log(f"ChooseNGC: Found {name}", terminal=False)
                    break

            if result == "":
                if prechosen is not None:
                    self.log(
                        f"ChooseNGC: Prechosen {prechosen} not recognised",
                        terminal=False,
                    )
                    return None
                self._print(f"NGC: {search} Nothing matched, try again.")

        return {
            "name": _safe_name(result),
            "handle": _create_star(
                (df_row["rah"], df_row["ram"], df_row["ras"]),
                (df_row["ded"], df_row["dem"], df_row["des"]),
            ),
            "objecttype": "ngc",
            "constellation": None,
            "description": f"{result} NGC",
            "magnitude": df_row["magnitude"],
            "searchgroup": "ngc",
            "searchterm": search,
        }

    def choose_hipparcos(self, prechosen: str | None = None) -> dict | None:
        """Select a Hipparcos star.

        Args:
            prechosen: Pre-selected HIP number (skip prompt if valid)

        Returns:
            Target information dict, or None if cancelled
        """
        result = ""
        star_row = None  # Ensure star_row is always defined
        hip_num = None

        while result == "":
            if prechosen is None:
                search = self._input("Enter Hipparcos target (number, ? or 'x'): ")
            else:
                search = prechosen

            search = search.lower()
            if search == "?":
                self._print("Enter the integer part of the Hipparcos number.")
                continue
            if search == "x":
                return None

            hip_num = _text_to_int(search)
            if hip_num is not None and hip_num in self.ctx.hipparcos_df.index:
                result = f"HIP_{hip_num}"
                star_row = self.ctx.hipparcos_df.loc[
                    self.ctx.hipparcos_df.hip == hip_num
                ].iloc[0]
                self.log("ChooseHipparcos: Found", result, terminal=False)

            if result == "":
                if prechosen is not None:
                    self.log(
                        f"ChooseHipparcos: Prechosen {prechosen} not recognised",
                        terminal=False,
                    )
                    return None
                self._print("Hipparcos: Nothing matched, try again.")

        if star_row is None:
            return None  # Defensive: should not happen, but avoids unbound error

        return {
            "name": _safe_name(result),
            "handle": _star_from_dataframe(star_row),
            "objecttype": "star",
            "constellation": star_row.get("constellation"),
            "description": f"Star {result} (Hipparcos)",
            "magnitude": star_row["magnitude"],
            "searchgroup": "hipparcos",
            "searchterm": str(hip_num),
        }

    def choose_comet(self, prechosen: str | None = None) -> dict | None:
        """Select a comet from Minor Planet Center data.

        Args:
            prechosen: Pre-selected comet designation (skip prompt if valid)

        Returns:
            Target information dict, or None if cancelled
        """
        result = ""
        comet_row = None
        handle = None
        search = None

        while result == "":
            if prechosen is None:
                chooser = self._make_list_chooser(self.ctx.comet_list)
                search = (
                    chooser.prompt() if chooser else self._input("Enter comet name: ")
                )
            else:
                search = prechosen

            if search is None:
                return None

            # Search in comet list
            for designation in self.ctx.comets_df["designation"]:
                if designation == search:
                    result = search.lower()
                    comet_row = self.ctx.comets_df.loc[designation]
                    handle = self.ctx.planets["sun"] + _get_comet_orbit(
                        comet_row, self.ctx.timescale, self.ctx.gm_sun
                    )
                    self.log(f"ChooseComet: Found {designation}", terminal=False)
                    break

            if result == "":
                if prechosen is not None:
                    self.log(
                        f"ChooseComet: Prechosen {prechosen} not recognised",
                        terminal=False,
                    )
                    return None
                self._print("Comet: Nothing matched, try again.")

        return {
            "name": _safe_name(result),
            "handle": handle,
            "objecttype": "comet",
            "constellation": None,
            "description": f"Comet {search}",
            "magnitude": None,  # Calculated later from GK model
            "searchgroup": "comet",
            "searchterm": search,
            "comet_row": comet_row,  # For magnitude calculation
        }

    def choose_meteor(self, prechosen: str | None = None) -> dict | None:
        """Select a meteor shower.

        Args:
            prechosen: Pre-selected shower name (skip prompt if valid)

        Returns:
            Target information dict (fixed point), or None if cancelled
        """
        result = ""
        search = None

        while result == "":
            if prechosen is None:
                chooser = self._make_list_chooser(self.ctx.meteor_namelist)
                search = (
                    chooser.prompt()
                    if chooser
                    else self._input("Enter meteor shower name: ")
                )
            else:
                search = prechosen

            if search is None:
                return None

            # Search in meteor list
            for name, _value in self.ctx.meteors.items():
                if name == search:
                    result = name.lower()
                    self.log(f"ChooseMeteor: Found {name}", terminal=False)
                    break

            if result == "":
                if prechosen is not None:
                    self.log(
                        f"ChooseMeteor: Prechosen {prechosen} not recognised",
                        terminal=False,
                    )
                    return None
                self._print("Meteor: Nothing matched, try again.")

        entry = self.ctx.meteors[str(search)]

        # Create initial star position for radiant
        radiant = _create_star((entry["rah"], entry["ram"], 0), (entry["dec"], 0, 0))

        return {
            "name": _safe_name(result),
            "handle": radiant,  # Note: Will be converted to fixed point
            "objecttype": "meteor",
            "constellation": entry.get("constellation"),
            "description": f"{search} meteor shower",
            "magnitude": 0.0,
            "searchgroup": "meteor",
            "searchterm": search,
            "is_fixed_point": True,  # Meteor observation uses fixed pointing
        }

    def choose_solar(self, prechosen: str | None = None) -> dict | None:
        """Select a solar system object.

        Args:
            prechosen: Pre-selected planet name (skip prompt if valid)

        Returns:
            Target information dict, or None if cancelled
        """
        targets = {
            "sun": ("sun", "sun", -26.7),
            "mercury": ("mercury barycenter", "planet", 0.23),
            "venus": ("venus barycenter", "planet", -4.4),
            "moon": ("moon", "moon", -12.5),
            "mars": ("mars barycenter", "planet", -2.91),
            "jupiter": ("jupiter barycenter", "planet", -2.7),
            "saturn": ("saturn barycenter", "planet", -0.55),
            "uranus": ("uranus barycenter", "planet", 5.68),
            "neptune": ("neptune barycenter", "planet", 7.78),
            "pluto": ("pluto barycenter", "planet", 15.1),
        }
        target_list = list(targets.keys())

        result = ""
        while result == "":
            if prechosen is None:
                chooser = self._make_list_chooser(target_list, compress=False)
                search = (
                    chooser.Prompt()
                    if chooser
                    else self._input("Enter planet name: ").lower()
                )
            else:
                search = prechosen

            if search is None:
                return None

            if search in targets:
                result = search
            else:
                if prechosen is not None:
                    self.log(
                        f"ChooseSolar: Prechosen {prechosen} not recognised",
                        terminal=False,
                    )
                    return None
                self._print(f"'{search}' is not recognised. Try again.")

        ephemeris_name, obj_type, magnitude = targets[result]

        return {
            "name": result,
            "handle": self.ctx.planets[ephemeris_name],
            "objecttype": obj_type,
            "constellation": None,
            "description": result.capitalize(),
            "magnitude": magnitude,
            "searchgroup": "solar",
            "searchterm": result,
        }

    def choose_satellite(self, prechosen: str | None = None) -> dict | None:
        """Select a satellite.

        Args:
            prechosen: Pre-selected satellite name (skip prompt if valid)

        Returns:
            Target information dict, or None if cancelled
        """
        result = ""

        while result == "":
            if prechosen is None:
                chooser = self._make_list_chooser(
                    self.ctx.satellite_list, compress=False
                )
                search = (
                    chooser.Prompt()
                    if chooser
                    else self._input("Enter satellite name: ")
                )
            else:
                search = prechosen

            if search is None:
                return None

            if search in self.ctx.satellite_list:
                result = search
                self.log(f"ChooseSatellite: Found {result}", terminal=False)
            else:
                if prechosen is not None:
                    self.log(
                        f"ChooseSatellite: Prechosen {prechosen} not recognised",
                        terminal=False,
                    )
                    return None
                self._print(f"'{search}' is not recognised. Try again.")

        # Note: TLE lines need to be fetched from CelesTrak
        return {
            "name": result,
            "handle": None,  # Will be populated with EarthSatellite
            "objecttype": "earth satellite",
            "constellation": None,
            "description": f"Spacestation: {result}",
            "magnitude": -6.0,
            "searchgroup": "satellite",
            "searchterm": result,
            "needs_tle": True,  # Flag that TLE data is needed
        }

    def radec_object(self, prechosen: str | None = None) -> dict | None:
        """Create a target from RA/Dec coordinates.

        Format: "RA hh mm ss DEC ddd mm ss name"

        Args:
            prechosen: Pre-defined coordinate string (skip prompt if valid)

        Returns:
            Target information dict, or None if cancelled
        """
        if prechosen is None:
            self._print("Create a target from RA and DEC values.")
            self._print("Format: RA hh mm ss DEC ddd mm ss name")

        while True:
            if prechosen is not None:
                line = prechosen
                prechosen = None  # Reset so we ask user if invalid
            else:
                line = self._input("Definition (x to quit): ")

            if len(line) < 1:
                continue
            if line.lower() == "x":
                return None

            parts = line.lower().split()
            try:
                if parts[0] != "ra":
                    self._print("1st term must be 'ra'. Try again")
                    continue
                if parts[4] != "dec":
                    self._print("5th term must be 'dec'. Try again")
                    continue

                rah = _text_to_int(parts[1])
                ram = _text_to_int(parts[2])
                ras = _text_to_float(parts[3])
                ded = _text_to_int(parts[5])
                dem = _text_to_int(parts[6])
                des = _text_to_float(parts[7])
                name = parts[8]

                # Validate ranges
                if rah is None or not 0 <= rah <= 23:
                    self._print("RA hours must be 0-23")
                    continue
                if ram is None or not 0 <= ram <= 59:
                    self._print("RA minutes must be 0-59")
                    continue
                if ras is None or not 0 <= ras < 60:
                    self._print("RA seconds must be 0-59.999")
                    continue
                if ded is None or not -90 <= ded <= 90:
                    self._print("Dec degrees must be -90 to 90")
                    continue
                if dem is None or not -59 <= dem <= 59:
                    self._print("Dec minutes must be -59 to 59")
                    continue
                if des is None or not -60 < des < 60:
                    self._print("Dec seconds must be -59.999 to 59.999")
                    continue

                break
            except (IndexError, ValueError):
                self._print("Invalid format. Try again.")
                continue

        # If any declination components are negative, all must be
        if ded < 0 or dem < 0 or des < 0:
            ded = -abs(ded)
            dem = -abs(dem) if dem != 0 else 0
            des = -abs(des) if des != 0 else 0

        return {
            "name": _safe_name(name),
            "handle": _create_star((rah, ram, ras), (ded, dem, des)),
            "objecttype": "radec location",
            "constellation": None,
            "description": name,
            "magnitude": 0.0,
            "searchgroup": "radec",
            "searchterm": line,
        }

    def altaz_object(self, prechosen: str | None = None) -> dict | None:
        """Create a fixed target from Alt/Az coordinates.

        Format: "ALT ddd.dddd AZ ddd.dddd name"

        Args:
            prechosen: Pre-defined coordinate string (skip prompt if valid)

        Returns:
            Target information dict (fixed point), or None if cancelled
        """
        if prechosen is None:
            self._print("Create a target from Altitude and Azimuth values.")
            self._print("Format: ALT ddd.dddd AZ ddd.dddd name")

        # Get motor limits
        min_az, max_az = 0, 360
        min_alt, max_alt = -90, 90
        if self.ctx.motor_controls:
            for motor in self.ctx.motor_controls:
                name = getattr(motor, "MotorName", "")
                if name == "azimuth":
                    min_az = getattr(motor, "MinAngle", 0)
                    max_az = getattr(motor, "MaxAngle", 360)
                elif name == "altitude":
                    min_alt = getattr(motor, "MinAngle", -90)
                    max_alt = getattr(motor, "MaxAngle", 90)

        while True:
            if prechosen is not None:
                line = prechosen
                prechosen = None
            else:
                line = self._input("Definition ('x' to quit): ")

            if len(line) < 1:
                continue
            if line.lower() == "x":
                return None

            parts = line.lower().split()
            try:
                if parts[0] != "alt":
                    self._print("1st term must be 'alt'. Try again")
                    continue
                if parts[2] != "az":
                    self._print("3rd term must be 'az'. Try again")
                    continue

                alt = _text_to_float(parts[1])
                az = _text_to_float(parts[3])
                name = parts[4]

                if alt is None or not min_alt <= alt <= max_alt:
                    self._print(f"Altitude must be {min_alt} to {max_alt}")
                    continue
                if az is None or not min_az <= az <= max_az:
                    self._print(f"Azimuth must be {min_az} to {max_az}")
                    continue

                break
            except (IndexError, ValueError):
                self._print("Invalid format. Try again.")
                continue

        return {
            "name": _safe_name(name),
            "handle": None,  # Will be FixedPoint
            "alt": alt,
            "az": az,
            "objecttype": "altaz",
            "constellation": None,
            "description": name,
            "magnitude": 0.0,
            "searchgroup": "altaz",
            "searchterm": line,
            "is_fixed_point": True,
        }

    def choose_aurora(self, _prechosen: str | None = None) -> dict | None:
        """Set up for Aurora observation.

        Points camera north or south depending on latitude.

        Args:
            prechosen: Not used, for API consistency

        Returns:
            Target information dict (fixed point)
        """
        # Determine direction based on latitude
        if self.ctx.home_latitude >= 0:
            # Northern hemisphere - look north
            min_az = 0
            if self.ctx.motor_controls:
                for motor in self.ctx.motor_controls:
                    if getattr(motor, "MotorName", "") == "azimuth":
                        min_az = max(0.0, getattr(motor, "MinAngle", 0))
            target_az = min_az
            name = "aurora_borealis"
        else:
            # Southern hemisphere - look south
            max_az = 180
            if self.ctx.motor_controls:
                for motor in self.ctx.motor_controls:
                    if getattr(motor, "MotorName", "") == "azimuth":
                        max_az = min(180, getattr(motor, "MaxAngle", 360))
            target_az = max_az
            name = "aurora_australis"

        # Default altitude for aurora viewing
        target_alt = 30.0  # Can be made configurable
        if self.ctx.motor_controls:
            for motor in self.ctx.motor_controls:
                if getattr(motor, "MotorName", "") == "altitude":
                    min_obs = getattr(motor, "MinObservationAngle", 0)
                    target_alt = max(target_alt, min_obs)

        return {
            "name": name,
            "handle": None,  # Will be FixedPoint
            "alt": target_alt,
            "az": target_az,
            "objecttype": "aurora",
            "constellation": None,
            "description": name,
            "magnitude": 2.0,
            "searchgroup": "aurora",
            "searchterm": "aurora",
            "is_fixed_point": True,
        }

    def get_target(self, searchgroup: str, searchterm: str) -> dict | None:
        """Get a target by searchgroup and searchterm.

        This is a dispatch function that calls the appropriate chooser.

        Args:
            searchgroup: Type of target ('solar', 'satellite', 'messier', etc.)
            searchterm: Search term to pass to the chooser

        Returns:
            Target information dict, or None if not found
        """
        choosers = {
            "solar": self.choose_solar,
            "satellite": self.choose_satellite,
            "hipparcos": self.choose_hipparcos,
            "messier": lambda p: self.choose_messier(p, size_warning=False),
            "radec": self.radec_object,
            "altaz": self.altaz_object,
            "aurora": self.choose_aurora,
            "meteor": self.choose_meteor,
            "comet": self.choose_comet,
            "ngc": self.choose_ngc,
        }

        chooser = choosers.get(searchgroup)
        if chooser:
            return chooser(searchterm)
        return None


# Convenience function for creating a TargetChooser
def create_target_chooser(
    messier: dict,
    meteors: dict,
    hipparcos_df: Any,
    ngc_df: Any,
    comets_df: Any,
    planets: Any,
    timescale: Any,
    gm_sun: float,
    satellite_list: list[str],
    logger: Any | None = None,
    **kwargs,
) -> TargetChooser:
    """Create a TargetChooser with the provided catalog data.

    Args:
        messier: Messier catalog dictionary
        meteors: Meteor shower dictionary
        hipparcos_df: Hipparcos DataFrame
        ngc_df: NGC DataFrame
        comets_df: Comets DataFrame
        planets: Skyfield ephemeris
        timescale: Skyfield timescale
        gm_sun: Solar gravitational parameter
        satellite_list: List of satellite names
        logger: Optional logger
        **kwargs: Additional context parameters

    Returns:
        Configured TargetChooser instance
    """
    # Build name lists from catalogs
    messier_numlist = list(messier.keys())
    messier_namelist = [v.get("name", "") for v in messier.values() if v.get("name")]
    meteor_namelist = list(meteors.keys())
    ngc_namelist = ngc_df["name"].tolist() if ngc_df is not None else []
    comet_list = comets_df["designation"].tolist() if comets_df is not None else []

    ctx = TargetSelectionContext(
        messier=messier,
        meteors=meteors,
        hipparcos_df=hipparcos_df,
        ngc_df=ngc_df,
        comets_df=comets_df,
        messier_numlist=messier_numlist,
        messier_namelist=messier_namelist,
        meteor_namelist=meteor_namelist,
        ngc_namelist=ngc_namelist,
        comet_list=comet_list,
        satellite_list=satellite_list,
        planets=planets,
        timescale=timescale,
        gm_sun=gm_sun,
        logger=logger,
        **kwargs,
    )

    return TargetChooser(ctx)
