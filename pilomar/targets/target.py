#!/usr/bin/env python3
"""
Target module for Pilomar.

This module contains the Target class which encapsulates all information
about an observation target including position calculations, rise/set times,
field rotation, and visibility checks.
"""

from __future__ import annotations

import math
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from pilomar.celestial.trig import angle_to_hms, relative_alt_az
from pilomar.core.base import AttributeMaster
from pilomar.core.time_utils import now_utc
from pilomar.ui.text_color import TextColor

from .fixed_point import FixedPoint

# Import context classes
from .sky_context import HardwareContext, SkyContext, TimeContext

if TYPE_CHECKING:
    from pilomar.control.motor import MotorControl
    from pilomar.core.logger import LogFile


class Target(AttributeMaster):
    """Contains all information about an observation target.

    This class handles various observation target types (stars, planets,
    satellites, comets, meteor showers) and provides a common interface
    for position calculations, rise/set times, and field rotation.

    Args:
        handle: Skyfield object for target (Star, planet, satellite, etc.)
        name: name of the object
        sky: SkyContext with Skyfield dependencies
        time_ctx: TimeContext with time-related functions
        hardware: HardwareContext with hardware dependencies
        object_type: Type of object (e.g., 'planet', 'star', 'earth satellite')
        constellation: Constellation the object belongs to
        description: Description of the object
        magnitude: Visual magnitude
        search_group: Which search category was used
        search_term: Search term that identifies this object
        object_diameter: Diameter of object in degrees
        comet_pandas_row: Pandas row for comets (instead of Skyfield handle)
        logger: Optional logging function

    Attributes:
        handle: Skyfield object for the target
        name: name of the object
        ObjectType: Type of object
        Constellation: Constellation
        Description: Description
        Magnitude: Visual magnitude
        DiameterDegrees: Object diameter in degrees
        HomeSite: Skyfield observer location
        HomeSiteTopos: Skyfield Topos for observer
    """

    def __init__(
        self,
        handle: Any,
        name: str,
        sky: SkyContext,
        time_ctx: TimeContext,
        hardware: HardwareContext,
        object_type: str | None = None,
        constellation: str | None = None,
        description: str | None = None,
        magnitude: float = 0.0,
        search_group: str | None = None,
        search_term: str | None = None,
        object_diameter: float | None = None,
        comet_pandas_row: Any | None = None,
        logger: LogFile | None = None,
    ):
        """Initialize the Target instance."""
        # Set up logger first
        super().__init__()
        if logger is not None:
            self.set_logger(logger)

        # Store context objects
        self._sky = sky
        self._time_ctx = time_ctx
        self._hardware = hardware

        # Basic properties
        self.handle = handle
        self.name = name
        self.search_group = search_group
        self.search_term = search_term
        self.object_type = object_type
        self.constellation = constellation
        self.description = description
        self.magnitude = magnitude
        self.diameter_degrees = object_diameter
        self.recommended_exposure = None

        # Observer location (initialized by SetHome)
        self.home_site = None
        self.home_site_topos = None
        self.ts = sky.timescale

        # Initialize home location
        self.set_home()

        # Comet-specific data
        self.comet_pandas_row = comet_pandas_row

        # Position cache
        self.cache_ra_deg = None
        self.cache_dec = None
        self.cache_alt = None
        self.cache_az = None

        # Angular velocity tracking
        self.prev_t = None
        self.az_speed = 0.0
        self.alt_speed = 0.0
        self.prev_az = None
        self.prev_alt = None

        # Field rotation
        self.rotation_point = None

        # Scheduling
        self.scheduled_start = None
        self.scheduled_end = None

        # Star cache for quick calculations
        self.quick_star_cache: dict = {}

        # Tracking map span (read from parameters if available)
        params = hardware.parameters
        self.tracking_map_span = getattr(params, "tracking_map_span", 10.0) if params else 10.0

    # -------------------------------------------------------------------------
    # Properties and shortcuts
    # -------------------------------------------------------------------------

    @property
    def parameters(self):
        """Get parameters from hardware context."""
        return self._hardware.parameters

    @property
    def sensor(self):
        """Get sensor from hardware context."""
        return self._hardware.sensor

    @property
    def camera(self):
        """Get camera from hardware context."""
        return self._hardware.camera

    @property
    def motor_controls(self) -> list[MotorControl]:
        """Get motor controls from hardware context."""
        return self._hardware.motor_controls or []

    @property
    def planets(self):
        """Get planets from sky context."""
        return self._sky.planets

    # -------------------------------------------------------------------------
    # Home site setup
    # -------------------------------------------------------------------------

    def set_home(self) -> None:
        """Initialize the Skyfield home references."""
        params = self._hardware.parameters
        if params is None:
            raise ValueError("Parameters required to set home location")

        home_lat = getattr(params, "home_lat", None)
        home_lon = getattr(params, "home_lon", None)

        if home_lat is None or home_lon is None:
            raise ValueError("home_lat and home_lon must be set in parameters")

        self.home_site_topos = self._sky.topos_class(home_lat, home_lon)
        self.home_site = self._sky.planets["earth"] + self.home_site_topos

    # -------------------------------------------------------------------------
    # Time functions
    # -------------------------------------------------------------------------

    def current_time(self, real: bool = False) -> Any:
        """Return skyfield format current time.

        Args:
            real: If True, ignore clock offset and return true CPU time

        Returns:
            Skyfield timestamp
        """
        result = self._time_ctx.now_skyfield()
        if not real and self._time_ctx.clock_offset is not None:
            dt = self._time_ctx.ts_to_datetime(result)
            dt = dt + timedelta(seconds=self._time_ctx.clock_offset)
            result = self._time_ctx.datetime_to_ts(dt, self.ts)
        return result

    def datetime_to_ts(self, dt) -> Any:
        """Convert datetime into TS (skyfield) timestamp."""
        return self._time_ctx.datetime_to_ts(dt, self.ts)

    def _ts_delta(self, base_ts, **kwargs) -> Any:
        """Add time delta to Skyfield timestamp."""
        return self._time_ctx.ts_delta(base_ts, self.ts, **kwargs)

    # -------------------------------------------------------------------------
    # Position calculations
    # -------------------------------------------------------------------------

    def az_alt_degrees(
        self, time: Any | None = None, updatespeed: bool = False
    ) -> tuple[float, float]:
        """Returns current altitude and azimuth of the target.

        Args:
            time: Optional Skyfield timestamp (uses current time if None)
            updatespeed: If True, update angular velocity figures

        Returns:
            Tuple of (azimuth_degrees, altitude_degrees)
        """
        if self.home_site is None:
            raise RuntimeError(f"Target.az_alt_degrees({self.name}): HomeSite not defined")

        t = time if time is not None else self.current_time()

        # Fixed point handling
        if self.is_fixed_point():
            alt = self.handle.altitude
            az = self.handle.azimuth
            self.alt_speed = 0.0
            self.az_speed = 0.0
            return az, alt

        # Satellite (geocentric) vs natural body (barycentric)
        if hasattr(self.handle, "center") and self.handle.center == 399:
            # Earth satellite
            difference = self.handle - self.home_site_topos
            topocentric = difference.at(t)
            alt, az, _ = topocentric.altaz()
        else:
            # Natural body
            astrometric = self.home_site.at(t).observe(self.handle)
            alt, az, _ = astrometric.apparent().altaz()

        azd = az.degrees
        altd = alt.degrees

        # Meteor shower coordinate adjustment
        if self.object_type == "meteor":
            altd = 45.0  # Point 45 degrees above horizon
            # Choose azimuth 45 degrees from radiant closest to due south
            az1 = azd - 45.0
            az2 = azd + 45.0
            if abs(az1 - 180) < abs(az2 - 180):
                azd = az1
            else:
                azd = az2

        # Update cache
        self.cache_az = azd
        self.cache_alt = altd

        # Update angular velocity if requested
        if updatespeed:
            if self.prev_t is not None:
                timediff = (
                    self._time_ctx.ts_to_datetime(t) - self._time_ctx.ts_to_datetime(self.prev_t)
                ).total_seconds()
                if timediff != 0.0 and self.prev_az is not None and self.prev_alt is not None:
                    self.az_speed = (azd - self.prev_az) / timediff
                    self.alt_speed = (altd - self.prev_alt) / timediff
                else:
                    self.az_speed = self.alt_speed = 0.0
            else:
                self.log(
                    f"target.az_alt_degrees({self.name}) no previous measure yet.",
                    terminal=False,
                )
            self.prev_az = azd
            self.prev_alt = altd
            self.prev_t = t

        return azd, altd

    def ra_dec_hours(self, time: Any | None = None) -> tuple[Any, Any]:
        """Returns RA and Dec as Skyfield Angle objects.

        Args:
            time: Optional Skyfield timestamp

        Returns:
            Tuple of (ra, dec) as Skyfield Angle objects
        """
        if self.home_site is None:
            raise RuntimeError(f"Target.ra_dec_hours({self.name}): HomeSite not defined")

        t = time if time is not None else self.current_time()

        if self.is_fixed_point():
            ra, dec = self.alt_az_to_ra_dec(self.handle.altitude, self.handle.azimuth)
        elif hasattr(self.handle, "center") and self.handle.center == 399:
            # Earth satellite
            difference = self.handle - self.home_site_topos
            topocentric = difference.at(t)
            ra, dec, _ = topocentric.radec()
        else:
            # Natural body
            astrometric = self.home_site.at(t).observe(self.handle)
            ra, dec, _ = astrometric.apparent().radec()

        # Update cache
        self.cache_ra_deg = ra._degrees
        self.cache_dec = dec.degrees

        return ra, dec

    def ra_dec_degrees(self, time: Any | None = None) -> tuple[float, float]:
        """Returns RA and Dec as degree values.

        Args:
            time: Optional Skyfield timestamp

        Returns:
            Tuple of (ra_degrees, dec_degrees)
        """
        ra, dec = self.ra_dec_hours(time=time)
        return ra._degrees, dec.degrees

    def alt_az_to_ra_dec(
        self, alt: float, az: float, time: Any | None = None, asdegrees: bool = False
    ) -> tuple[Any, Any]:
        """Convert alt/az coordinates to RA/Dec.

        Args:
            alt: altitude in degrees
            az: azimuth in degrees
            time: Optional Skyfield timestamp
            asdegrees: If True, return both as degree values

        Returns:
            Tuple of (ra, dec)
        """
        t = time if time is not None else self.ts.now()

        lookingat = self.home_site.at(t).from_altaz(alt_degrees=alt, az_degrees=az)
        ra, dec, _ = lookingat.radec()

        if asdegrees:
            ra = ra._degrees
            dec = dec.degrees

        return ra, dec

    def ra_dec_to_alt_az(
        self, ra: float, dec: float, time: Any | None = None, asdegrees: bool = True
    ) -> tuple[float, float]:
        """Convert RA/Dec to alt/az coordinates.

        Args:
            ra: Right ascension (degrees if asdegrees=True, else [H,M,S])
            dec: Declination in degrees
            time: Optional Skyfield timestamp
            asdegrees: If True, ra is a degree value; if False, ra is [H,M,S]

        Returns:
            Tuple of (altitude_degrees, azimuth_degrees)
        """
        if time is None:
            time = self.current_time()

        if asdegrees:
            # Convert degrees to H,M,S
            rah, ram, ras = angle_to_hms(ra)
        else:
            rah, ram, ras = ra[0], ra[1], ra[2]

        temp_star = self._sky.star_class(
            ra_hours=(rah, ram, ras), dec=self._sky.angle_class(degrees=dec)
        )
        alt, az, _ = self.home_site.at(time).observe(temp_star).apparent().altaz()

        return alt.degrees, az.degrees

    def planet_az_alt_degrees(
        self, name: str = "moon", time: Any | None = None
    ) -> tuple[float, float]:
        """Returns altitude and azimuth of any planetary object.

        Args:
            name: Planet name (default 'moon')
            time: Optional Skyfield timestamp

        Returns:
            Tuple of (azimuth_degrees, altitude_degrees)
        """
        if self.home_site is None:
            raise RuntimeError(f"Target.planet_az_alt_degrees({name}): HomeSite not defined")

        t = time if time is not None else self.current_time()
        solarobject = self._sky.planets[name]

        astrometric = self.home_site.at(t).observe(solarobject)
        alt, az, _ = astrometric.apparent().altaz()

        return az.degrees, alt.degrees

    # -------------------------------------------------------------------------
    # Object type checks
    # -------------------------------------------------------------------------

    def is_fixed_point(self) -> bool:
        """Return True if this is a fixed alt/az point."""
        return isinstance(self.handle, FixedPoint)

    def can_multisession_align(self, acceptable_types: list[str] | None = None) -> bool:
        """Returns True if target can be live stacked across sessions.

        Static objects (against star background) can be aligned for stacking.
        Moving objects (planets, satellites, meteors) cannot.

        Args:
            acceptable_types: List of object types that can be aligned

        Returns:
            True if alignable across sessions
        """
        if acceptable_types is None:
            acceptable_types = ["radec", "messier", "ngc", "hipparcos"]

        return self.object_type in acceptable_types

    # -------------------------------------------------------------------------
    # Visibility and limits
    # -------------------------------------------------------------------------

    def visible(self, time: Any | None = None) -> bool:
        """Return True if target is in observable portion of sky.

        Args:
            time: Optional Skyfield timestamp

        Returns:
            True if visible
        """
        result = True
        az, alt = self.az_alt_degrees(time=time)

        for mc in self.motor_controls:
            if mc.motor_name == "azimuth":
                if az < mc.min_angle or az > mc.max_angle:
                    result = False
            if mc.motor_name == "altitude":
                if alt < mc.min_observation_angle or alt > mc.max_angle:
                    result = False

        return result

    def approaching_limit(self, time: Any | None = None) -> bool:
        """Return True if target is approaching telescope movement limit.

        Args:
            time: Optional Skyfield timestamp

        Returns:
            True if approaching limit
        """
        result = False
        az, alt = self.az_alt_degrees(time=time)

        for mc in self.motor_controls:
            if mc.motor_name == "azimuth":
                if az <= mc.min_warning_angle or az >= mc.max_warning_angle:
                    result = True
            if mc.motor_name == "altitude":
                if alt <= mc.min_warning_angle or alt >= mc.max_warning_angle:
                    result = True

        return result

    # -------------------------------------------------------------------------
    # Rise/Set calculations
    # -------------------------------------------------------------------------

    def next_rise_set_object(self) -> tuple[Any | None, Any | None]:
        """Return next horizon event times for distant objects (Moon and beyond).

        Returns:
            Tuple of (rise_time, set_time) as datetime or None
        """
        risetime = None
        settime = None

        f = self._sky.almanac.risings_and_settings(
            self._sky.planets, self.handle, self.home_site_topos
        )

        tsnow = self.current_time().utc_datetime()
        t0 = self.ts.utc(tsnow.year, tsnow.month, tsnow.day)
        tsnow += timedelta(days=1)
        t1 = self.ts.utc(tsnow.year, tsnow.month, tsnow.day + 1)

        t, y = self._sky.almanac.find_discrete(t0, t1, f)

        for ti, yi in zip(t, y, strict=False):
            self.log(
                f"target.next_rise_set_object({self.name}): zipped",
                ti,
                yi,
                terminal=False,
            )
            tidt = ti.utc_datetime()
            if tidt < now_utc():
                continue
            if yi and risetime is None:
                risetime = tidt
            elif settime is None:
                settime = tidt

        return risetime, settime

    def next_rise_set_satellite(self) -> tuple[Any | None, Any | None]:
        """Return next horizon event times for satellites.

        Returns:
            Tuple of (rise_time, set_time) as datetime or None
        """
        self.log(f"target.next_rise_set_satellite({self.name})", terminal=False)

        if not hasattr(self.handle, "find_events"):
            self.log(
                f"Cannot calculate rise/set for target type ({self.name}, {self.object_type})",
                terminal=True,
            )
            return None, None

        risetime = settime = None
        t_from = self.current_time()
        t_to = self._ts_delta(t_from, dd=1)

        min_alt = getattr(self.parameters, "MinSatellitealtitude", 10.0)
        times, events = self.handle.find_events(self.home_site_topos, t_from, t_to, min_alt)

        for eventtime, eventtype in zip(times, events, strict=False):
            if eventtype == 2 and settime is None and risetime is not None:
                settime = eventtime.utc_datetime()
            if eventtype == 0 and risetime is None:
                risetime = eventtime.utc_datetime()
            if risetime is not None and settime is not None:
                break

        return risetime, settime

    def rise_set(self) -> tuple[Any | None, Any | None]:
        """Return next rise and set times for the object.

        Returns:
            Tuple of (rise_time, set_time) as datetime or None
        """
        risetime = None
        settime = None

        if self.is_fixed_point():
            pass  # No rise/set for fixed points
        elif self.object_type == "earth satellite":
            risetime, settime = self.next_rise_set_satellite()
        else:
            risetime, settime = self.next_rise_set_object()

        self.log(
            f"target.rise_set({self.name}): rise {risetime} set {settime} UTC",
            terminal=False,
        )
        return risetime, settime

    def next_rise_set(self) -> tuple[str | None, Any | None]:
        """Return next horizon event type and time.

        Returns:
            Tuple of (event_type, event_time) where event_type is 'rise', 'set', or None
        """
        risetime, settime = self.rise_set()
        eventtime = None
        eventtype = None

        now = now_utc()

        if risetime is not None and risetime > now:
            eventtime = risetime
            eventtype = "rise"

        if settime is not None and settime > now:
            if eventtime is None or eventtime > settime:
                eventtime = settime
                eventtype = "set"

        return eventtype, eventtime

    def next_rise_set_hhmm(self, window: int | None = None) -> str:
        """Returns next rise or set time as HH:MM string.

        Args:
            window: Hours into future that are acceptable (else '--:--')

        Returns:
            Time string like "14:30↑" or "22:15↓"
        """
        eventtype, eventtime = self.next_rise_set()
        result = ""

        # Get symbol dictionary (use defaults if not available)
        try:
            symbol = TextColor.SYMBOLS
        except ImportError:
            symbol = {"up": "↑", "down": "↓"}

        utc_to_display = self._time_ctx.utc_to_display
        if utc_to_display is None:

            def utc_to_display(x):
                return x  # Identity if not provided

        if eventtype == "rise" and eventtime:
            result = str(utc_to_display(eventtime))[11:16] + symbol.get("up", "↑")
        elif eventtype == "set" and eventtime:
            result = str(utc_to_display(eventtime))[11:16] + symbol.get("down", "↓")

        if window is not None and eventtime is not None:
            cutoff = now_utc() + timedelta(hours=window)
            if eventtime > cutoff:
                result = "--:--"

        return result

    # -------------------------------------------------------------------------
    # Twilight and lunar calculations
    # -------------------------------------------------------------------------

    def twilight_level(self, time: Any | None = None) -> str:
        """Return twilight level for current location.

        NOTE: The target should be the sun for this to be meaningful.

        Args:
            time: Optional Skyfield timestamp

        Returns:
            One of: 'daytime', 'civil twilight', 'nautical twilight',
                    'astronomical twilight', 'nighttime'
        """
        az, alt = self.az_alt_degrees(time=time)

        if alt > 0:
            return "daytime"
        elif alt >= -6:
            return "civil twilight"
        elif alt >= -12:
            return "nautical twilight"
        elif alt >= -18:
            return "astronomical twilight"
        else:
            return "nighttime"

    def lunar_phase(self, time: Any | None = None) -> float:
        """Return the phase of the Moon in degrees.

        0 = New Moon, 180 = Full Moon
        1-179 = Waxing, 181-359 = Waning

        Args:
            time: Optional Skyfield timestamp

        Returns:
            Moon phase in degrees
        """
        if time is None:
            time = self.current_time()
        result = self._sky.almanac.moon_phase(self._sky.planets, time)
        return result.degrees

    def moon_full(self, time: Any | None = None) -> float:
        """Return percentage of full moon (light pollution indicator).

        Args:
            time: Optional Skyfield timestamp

        Returns:
            Percentage of full moon (0-100)
        """
        moonphase = self.lunar_phase(time=time)
        if moonphase > 180:
            moonphase = 360 - moonphase
        return 100 * moonphase / 180

    def moon_waxing(self) -> bool:
        """Return True if moon is waxing, False if waning."""
        return self.lunar_phase() <= 180

    # -------------------------------------------------------------------------
    # Magnitude calculations
    # -------------------------------------------------------------------------

    def current_magnitude(self, time: Any | None = None) -> float:
        """Calculate current apparent magnitude if possible.

        Args:
            time: Optional Skyfield timestamp

        Returns:
            Apparent magnitude
        """
        if time is None:
            time = self.current_time()

        result = self.magnitude  # Default to catalog magnitude

        try:
            astrometric = self.home_site.at(time).observe(self.handle)
            temp = self._sky.planetary_magnitude_func(astrometric)
            if temp is not None:
                result = temp
            self.log(
                f"target.current_magnitude: planetary_magnitude returned {temp}",
                terminal=False,
            )
        except Exception:  # pylint: disable=broad-except
            self.log(
                "target.current_magnitude: planetary_magnitude didn't work",
                terminal=False,
            )

        return result

    def apparent_comet_magnitude_gk(self) -> float:
        """Calculate comet apparent magnitude using GK model.

        Returns:
            Apparent magnitude
        """
        if self.comet_pandas_row is None:
            return self.magnitude

        comets_df = self._sky.comets_df

        # handle different Skyfield versions (field name changes)
        if comets_df is not None and "magnitude_h" in comets_df.columns:
            g_abs = self.comet_pandas_row["magnitude_h"]
            k_lum = self.comet_pandas_row["magnitude_g"]
        else:
            g_abs = self.comet_pandas_row["magnitude_g"]
            k_lum = self.comet_pandas_row["magnitude_k"]

        t = self.current_time()
        _, _, sun_body_dist = self._sky.planets["sun"].at(t).observe(self.handle).radec()
        _, _, earth_body_dist = self.home_site.at(t).observe(self.handle).apparent().altaz()

        apparent_mag = (
            g_abs
            + (5 * math.log10(earth_body_dist.au))
            + (2.5 * k_lum * math.log10(sun_body_dist.au))
        )

        return round(apparent_mag, 1)

    # -------------------------------------------------------------------------
    # Field rotation calculations
    # -------------------------------------------------------------------------

    def choose_rotation_point(self, offset_deg: float = 2.0) -> bool:
        """Setup field rotation reference point.

        This point is offset from the target and used to measure
        field rotation as the sky moves.

        Args:
            offset_deg: Declination offset in degrees

        Returns:
            True on success
        """
        centre_ra, centre_dec = self.ra_dec_hours()
        centre_dec = centre_dec.degrees

        # Offset below in northern hemisphere, above in southern
        params = self._hardware.parameters
        home_lat = getattr(params, "_home_latVal", 0) if params else 0

        if home_lat > 0:
            offset_dec = centre_dec - offset_deg
        else:
            offset_dec = centre_dec + offset_deg

        # Create reference point
        hms = centre_ra.hms()
        self.rotation_point = self._sky.star_class(
            ra_hours=(hms[0], hms[1], hms[2]),
            dec=self._sky.angle_class(degrees=offset_dec),
        )

        return True

    def rotation_point_alt_az_degrees(self, time: Any | None = None) -> tuple[float, float]:
        """Get alt/az of the rotation reference point.

        Args:
            time: Optional Skyfield timestamp

        Returns:
            Tuple of (altitude_degrees, azimuth_degrees)
        """
        if time is None:
            time = self.current_time()
        if self.rotation_point is None:
            self.choose_rotation_point()

        alt, az, _ = self.home_site.at(time).observe(self.rotation_point).apparent().altaz()
        return alt.degrees, az.degrees

    def rotation_point_bearing(self, time: Any | None = None) -> float:
        """Calculate bearing of field rotation reference point relative to target.

        Args:
            time: Optional Skyfield timestamp

        Returns:
            Rotation angle in degrees
        """

        if time is None:
            time = self.current_time()

        rot_alt, rot_az = self.rotation_point_alt_az_degrees(time=time)
        az, alt = self.az_alt_degrees(time=time)

        plot_alt, plot_az = relative_alt_az(rot_alt, rot_az, alt, az)

        sensor = self._hardware.sensor
        if sensor is None:
            # Default sensor dimensions
            pixel_height = 3040
            pixel_width = 4056
        else:
            pixel_height = sensor.pixel_height
            pixel_width = sensor.pixel_width

        star_x, star_y = plot_relative_alt_az(plot_alt, plot_az, pixel_height, pixel_width)

        xpos = round(pixel_width / 2)
        ypos = round(pixel_height / 2)

        opposite = star_x - xpos
        adjacent = star_y - ypos

        return math.degrees(math.atan2(opposite, adjacent))

    def rotation_arc(self, span: int = 3600, time: Any | None = None) -> float:
        """Return field rotation rate scaled to requested time span.

        Args:
            span: Time span in seconds
            time: Optional center time for calculation

        Returns:
            Field rotation in degrees over the span
        """
        if time is None:
            time = self.current_time()

        calcperiod = 3600  # Calculate over an hour
        t1 = self._ts_delta(time, s=-round(calcperiod / 2))
        t2 = self._ts_delta(t1, s=calcperiod)

        a1 = self.rotation_point_bearing(t1)
        a2 = self.rotation_point_bearing(t2)

        rate = (a2 - a1) * span / calcperiod
        return rate

    def rotation_pixels(self, angle: float | None = None, radius: float | None = None) -> float:
        """Convert field rotation to pixel count at image corner.

        Args:
            angle: Rotation angle (calculates from exposure if None)
            radius: Distance from center in pixels (uses corner if None)

        Returns:
            Arc length in pixels
        """
        camera = self._hardware.camera
        sensor = self._hardware.sensor

        if angle is None:
            exposure = camera.exposure_seconds if camera else 1.0
            angle = self.rotation_arc(span=int(exposure))

        if radius is None:
            if sensor:
                pw = sensor.pixel_width
                ph = sensor.pixel_height
            else:
                pw, ph = 4056, 3040
            radius = math.sqrt((pw / 2) ** 2 + (ph / 2) ** 2)

        circumference = radius * 2 * math.pi
        arclength = circumference * angle / 360

        return arclength

    def plot_rotation_point(self, time: Any | None = None) -> tuple[float, float]:
        """Return image x,y coordinates of field rotation reference point.

        Args:
            time: Optional Skyfield timestamp

        Returns:
            Tuple of (x, y) pixel coordinates
        """
        if time is None:
            time = self.current_time()

        rot_alt, rot_az = self.rotation_point_alt_az_degrees(time=time)
        az, alt = self.az_alt_degrees(time=time)

        plot_alt, plot_az = relative_alt_az(rot_alt, rot_az, alt, az)

        sensor = self._hardware.sensor
        if sensor:
            star_x, star_y = plot_relative_alt_az(
                plot_alt, plot_az, sensor.pixel_height, sensor.pixel_width
            )
        else:
            star_x, star_y = plot_relative_alt_az(plot_alt, plot_az, 3040, 4056)

        return star_x, star_y

    # -------------------------------------------------------------------------
    # Target updates
    # -------------------------------------------------------------------------

    def update_location(self, new_handle: Any) -> None:
        """Revise the skyfield target handle.

        Used when performing sky surveys or modifying target coordinates
        while retaining other attributes.

        Args:
            new_handle: New Skyfield object for target
        """
        self.handle = new_handle
        self.rotation_point = None
        self.log("target.update_location(): New coordinates updated.", terminal=False)

    # -------------------------------------------------------------------------
    # Forecast methods
    # -------------------------------------------------------------------------

    def forecast_path(
        self,
        time: Any | None = None,
        days: int = 30,
        step_hours: int = 24,
        fov: float | None = None,
    ) -> list[tuple[Any, float, float]]:
        """Calculate path target will take through sky.

        Args:
            time: Start timestamp
            days: Number of days to forecast
            step_hours: Hours between forecast positions
            fov: Field of view in degrees (uses camera FOV if None)

        Returns:
            List of (timestamp, ra_degrees, dec_degrees) tuples
        """
        points = []

        temp_ts = time if time is not None else self.current_time()
        temp_ts = self._ts_delta(temp_ts, s=0)  # Truncate fractions
        cutoff_ts = self._ts_delta(temp_ts, dd=days)

        if fov is None:
            camera = self._hardware.camera
            if camera and hasattr(camera, "lens"):
                fov = min(camera.lens.fov_horizontal, camera.lens.fov_vertical) * 0.8
            else:
                fov = 5.0  # Default FOV

        min_ra = max_ra = None
        min_dec = max_dec = None

        while temp_ts.utc_datetime() <= cutoff_ts.utc_datetime():
            ra, dec = self.ra_dec_degrees(time=temp_ts)

            # Track span
            if min_ra is None or min_ra > ra:
                min_ra = ra
            if max_ra is None or max_ra < ra:
                max_ra = ra
            if min_dec is None or min_dec > dec:
                min_dec = dec
            if max_dec is None or max_dec < dec:
                max_dec = dec

            # Check if motion exceeds FOV
            if abs(max_ra - min_ra) > fov or abs(max_dec - min_dec) > fov:
                break

            points.append((temp_ts, ra, dec))
            temp_ts = self._ts_delta(temp_ts, h=step_hours)

        return points

    def forecast_range(
        self, time: Any | None = None, days: int = 30
    ) -> tuple[float, float, float, float]:
        """Forecast path and return min/max RA/Dec.

        Args:
            time: Start timestamp
            days: Number of days to forecast

        Returns:
            Tuple of (min_ra, min_dec, max_ra, max_dec)
        """
        points = self.forecast_path(time=time, days=days)

        if not points:
            return 0, 0, 0, 0

        min_ra = max_ra = points[0][1]
        min_dec = max_dec = points[0][2]

        for _, ra, dec in points:
            min_ra = min(min_ra, ra)
            max_ra = max(max_ra, ra)
            min_dec = min(min_dec, dec)
            max_dec = max(max_dec, dec)

        return min_ra, min_dec, max_ra, max_dec

    def forecast_centre(self, time: Any | None = None, days: int = 30) -> tuple[float, float]:
        """Forecast path and return centre of motion.

        Args:
            time: Start timestamp
            days: Number of days to forecast

        Returns:
            Tuple of (ra_degrees, dec_degrees) for centre
        """
        min_ra, min_dec, max_ra, max_dec = self.forecast_range(time=time, days=days)
        return (min_ra + max_ra) / 2, (min_dec + max_dec) / 2
