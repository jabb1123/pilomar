import math
from datetime import timedelta
from typing import TYPE_CHECKING

from skyfield import almanac
from skyfield.api import Angle, Star, Time, Timescale, Topos, load
from skyfield.data import mpc  # For comet trajectory handling.
from skyfield.magnitudelib import planetary_magnitude

from camera.targets.fixed import FixedPoint
from utils.coordinates import plot_relative_alt_az, relative_alt_az
from utils.logfile import LogFile

if TYPE_CHECKING:
    from camera import AstroCamera
from utils.math_func import angle_to_hms, deg_3dp, display_degree, display_hms
from utils.params import AttributeMaster, Parameters
from utils.statics import DEGREE_SYMBOL, SYMBOLS
from utils.text.human_readable import human_readable_seconds
from utils.text.textcolor import TextColor
from utils.time_funcs import datetime2_ts, now_utc, ts_delta, ts_to_datetime


class AstroTarget(AttributeMaster):
    """Class that contains all the information we need about an observation target.
    There are some variations in the way different observation targets are handled,
    this wrapper should hide those differences from the rest of the program and
    present a common interface."""

    def __init__(
        self,
        handle,
        name,
        objecttype=None,
        constellation=None,
        description=None,
        magnitude=0.0,
        searchgroup=None,
        searchterm=None,
        objectdiameter=None,
        cometpandasrow=None,
        parameters=None,
        logger: LogFile = None,
    ):
        self.set_logger(
            logger
        )  # Inherited from attributemaster: Set up references to chosen logger (or disable if no logger defined).
        self.handle = handle  # Skyfield object for target. This is usually provided directly by the calling routine, but in the case of 'comets' it is calculated here during initialisation.
        self.name = name  # Name of object.
        self.search_group = searchgroup  # Which search category was used?
        self.search_term = searchterm  # Which search term identifies this object?
        self.object_type = objecttype
        self.constellation = constellation
        self.description = description
        self.magnitude = magnitude
        self.diameter_degrees = objectdiameter  # diameter of the object in the sky. # Used to warn if target is too small.!
        self.recommended_exposure = None  # Recommended exposure for this object.
        self.home_site = None  # Skyfield object for home site.
        self.home_site_topos = None  # Skyfield object for home site.
        self.camera_in_use: AstroCamera = None  # Camera in use for this observation.
        self.parameters: Parameters = (
            parameters  # Reference to the global parameters object.
        )
        self.ts: Timescale = (
            load.timescale()
        )  # Time handling with astro corrections. ! Don't use this to read current time, always use SkyfieldNow() function!
        self.set_home(
            parameters.home_lat, parameters.home_lon
        )  # Use global variables at the moment. Requires that global list 'planets' is available too.
        self.comet_pandas_row = cometpandasrow  # Comets don't have a skyfield object in 'Handle', we calculate the position differently, so store their pandas row here.
        self.cache_ra_deg = (
            None  # Cached RA value for target. Set each time RaDecDegrees is called.
        )
        self.cache_dec = (
            None  # Cached Dec value for target. Set each time RaDecDegrees is called.
        )
        self.cache_alt = None  # Cached Altitude value for target. Set each time AzAltDegrees is called.
        self.cache_az = None  # Cached Azimuth value for target. Set each time AzAltDegrees is called.
        self.prev_t = None  # TS timestamp when location was last checked (for calculating angular velocity)
        self.az_speed = 0.0  # Angular speed (deg/sec)
        self.alt_speed = 0.0  # Angular speed (deg/sec)
        self.prev_az = None  # Previous location
        self.prev_alt = None  # Previous location
        self.rotation_point = None  # Will hold rotation reference point if activated.
        self.scheduled_start = None  # Holds the UTC timestamp when the observation should start (if one is set).
        self.scheduled_end = None  # Holds the UTC timestamp when the observation should end (if one is set).
        reload_data = False  # Set this to TRUE to cause the data files to be reloaded from the online resources. Can be set by 'reload' runtime argument too.
        self.planets = load("de421.bsp")
        with load.open(
            mpc.COMET_URL, reload=reload_data
        ) as f:  # Don't keep reloading it if it is already on disc.
            comets = mpc.load_comets_dataframe(f)
        self.comets = comets = (
            comets.sort_values("reference")
            .groupby("designation", as_index=False)
            .last()
            .set_index("designation", drop=False)
        )

    def twilight_level(self, time=None):
        """Return the twilight level for the current location.
        NOTE: The target needs to be the sun!
        If 'time' parameter given, it's the lightlevel at that time.
        If 'time' is None, then the current time is used."""
        az, alt = self.az_alt_degrees(time=time)
        if alt > 0:
            result = "daytime"
        elif alt >= -6:
            result = "civil twilight"
        elif alt >= -12:
            result = "nautical twilight"
        elif alt >= -18:
            result = "astronomical twilight"
        else:
            result = "nighttime"
        return result

    def datetime2_ts(self, dt):  # Referenced by external dependencies.
        """Convert datetime into TS (skyfield) timestamp."""
        t = datetime2_ts(dt)  # Convert to skyfield time type.
        return t

    def current_magnitude(self, time=None):
        """Calculate the current magnitude (or for a specific time) if possible."""
        if time is None:
            time = self.current_time()
        result = (
            self.magnitude
        )  # Default to the standard magnitude for this object if known.
        try:
            astrometric = self.home_site.at(time).observe(self.handle)
            temp = planetary_magnitude(astrometric)
            if temp is not None:
                result = temp
            self.log(
                "target.CurrentMagnitude: planetary_magnitude returned",
                temp,
                terminal=False,
            )
        except Exception:
            self.log(
                "target.CurrentMagnitude: planetary_magnitude didn't work for this target.",
                terminal=False,
            )
        return result

    def update_location(self, newhandle):
        """Revise the skyfield target handle.
        Used when performing sky surveys of multiple locations around a target.
        Use this if you need to modify the location of the target for some reason (eg new RADEC) but retain all the other attributes.
        """
        self.handle = newhandle
        self.rotation_point = None  # Will hold rotation reference point if activated.
        self.log(
            "target.UpdateLocation(): New co-ordinates updated to the target.",
            terminal=False,
        )

    def next_rise_set_object(self):
        """Return next horion event and time for distant objects. (Moon and beyond)"""
        risetime = None  # No RISE time until identified.
        settime = None  # No SET time until identified.
        f = almanac.risings_and_settings(
            self.planets, self.handle, self.home_site_topos
        )
        tsnow = (
            self.current_time().utc_datetime()
        )  # Current Timestamp as conventional Python UTC datetime value.
        t0 = self.ts.utc(
            tsnow.year, tsnow.month, tsnow.day
        )  # Generate skyfield UTC timestamp for start of day. # Doesn't need offset support.
        tsnow += timedelta(days=1)  # Move forward 24 hours.
        t1 = self.ts.utc(
            tsnow.year, tsnow.month, tsnow.day + 1
        )  # Generate skyfield UTC timestamp for start of following day. # Doesn't need offset support.
        t, y = almanac.find_discrete(
            t0, t1, f
        )  # Return list of rise/set times within window.
        # If the object never rises/sets in the timeperiod checked, there are not values here, so None,None will be returned.
        for ti, yi in zip(t, y):  # Combine t and y lists.
            self.log("target.RiseSet(", self.name, "): zipped", ti, yi, terminal=False)
            tidt = ti.utc_datetime()
            if tidt < now_utc():
                continue  # In the past, ignore it.
            if yi and risetime is None:  # First future rise time.
                risetime = tidt
            elif settime is None:  # First future set time.
                settime = tidt
        return risetime, settime

    def next_rise_set_satellite(self):
        """Return next horizon event and time for satellites."""
        self.log("target.NextRiseSetSatellite(", self.name, ")", terminal=False)
        if not hasattr(
            self.handle, "find_events"
        ):  # This object doesn't support satellite pass calculations.
            self.log(
                "Cannot calculate next Rise Set times for this type of target(",
                self.name,
                self.object_type,
                ")",
                terminal=True,
            )
            self.log(
                "target.NextRiseSetSatellite: find_events method not in this target type.",
                terminal=True,
            )
            return
        risetime = settime = None
        t_from = self.current_time()  # Start now.
        t_to = ts_delta(t_from, dd=1)  # Stop in 24hours time.
        self.log(
            "target.NextRiseSetSatellite: t_from",
            str(t_from),
            "t_to",
            str(t_to),
            terminal=False,
        )
        times, events = self.handle.find_events(
            self.home_site_topos, t_from, t_to, self.parameters.min_satellite_altitude
        )  # What events occur above horizon in next 24 hours?
        self.log(
            "target.NextRiseSetSatellite: times",
            times,
            "events",
            events,
            terminal=False,
        )
        telist = zip(times, events)
        for te in telist: 
            self.log("target.NextRiseSetSatellite: Entry:", te, terminal=False)
            eventtime: Time = te[0]
            eventtype = te[1]  # 0=Rise, 1=Culminate, 2=Set
            if eventtype == 2 and settime is None and risetime is not None:
                settime = eventtime.utc_datetime()
            if eventtype == 0 and risetime is None:
                risetime = eventtime.utc_datetime()
            if eventtype == 1:  # Culmination, how high?
                self.log(
                    "target.NextRiseSetSatellite: Checking culmination at",
                    eventtime.utc_datetime(),
                    terminal=False,
                )
                az, alt = self.az_alt_degrees(time=eventtime)
                self.log(
                    "target.NextRiseSetSatellite: Culmination at",
                    eventtime.utc_datetime(),
                    "is",
                    deg_3dp(alt),
                    DEGREE_SYMBOL,
                    terminal=False,
                )
            if risetime is not None and settime is not None:
                break  # We have our earliest acceptable set of values.
        self.log(
            "target.NextRiseSetSatellite: Rise",
            risetime,
            "set",
            settime,
            terminal=False,
        )
        return risetime, settime

    def satellite_passes(self, window=24):
        """Print table of satellite pass information for next xx hours."""
        self.log("target.SatellitePasses: NOT YET IMPLEMENTED.", terminal=False)
        t_from = self.current_time()  # Start now.
        t_to = ts_delta(t_from, dd=1)  # Stop in 24hours time.
        self.log(
            "target.SatellitePasses: t_from",
            str(t_from),
            "t_to",
            str(t_to),
            terminal=False,
        )
        if not hasattr(
            self.handle, "find_events"
        ):  # This object doesn't support satellite pass calculations.
            self.log(
                "Cannot calculate next pass times for this type of target(",
                self.name,
                self.object_type,
                ")",
                terminal=True,
            )
            self.log(
                "target.SatellitePasses: find_events method not in this target type.",
                terminal=True,
            )
            return
        times, events = self.handle.find_events(
            self.home_site_topos, t_from, t_to, 0.0
        )  # What events occur above horizon in next 24 hours?
        self.log(
            "target.SatellitePasses: times", times, "events", events, terminal=False
        )
        passelements = (
            []
        )  # List of the 3 elements of a pass. [[eventdetails],[eventdetails],[eventdetails]]
        listofpasses = (
            []
        )  # List of all the passes. [[passelements].[passelements],[passelements],...]
        for i, eventtime in enumerate(times):
            eventtype = events[i]
            eventdatetime = eventtime.utc_datetime()
            eventaz, eventalt = self.az_alt_degrees(time=eventtime)
            eventdetails = (
                []
            )  # List of the event details. (3 of these per pass) [eventtype,eventdatetime,eventaz,eventalt]
            eventdetails.append(eventtype)
            eventdetails.append(eventdatetime)
            eventdetails.append(eventaz)
            eventdetails.append(eventalt)
            passelements.append(
                eventdetails
            )  # Add event details to the list of events in this pass.
            if (
                eventtype == 2 and len(passelements) == 3
            ):  # We have the last entry of a complete set of three entries.
                listofpasses.append(
                    passelements
                )  # Append to list of passes and start constructing the next event.
                passelements = []

        # Now show the list of passes as a table.
        print(TextColor.yellow("Satellite: " + self.name))
        print(
            TextColor.yellow(
                "Passes which culminate above "
                + str(self.parameters.min_satellite_altitude)
                + DEGREE_SYMBOL
            )
        )
        print(TextColor.yellow("Matching passes within next " + str(window) + "hrs."))
        print("Pass rises             Az   Alt     Duration     Sets    Az")
        #     "2023-05-12 00:52:42 246.0° 53.0° 00h:02m:43s 00:55:26 121.0°"

        for passentry in listofpasses:
            risetime = passentry[0][1]  # 0 = Rise, 1 = datetime
            settime = passentry[2][1]  # 2 = Set, 1 = datetime
            duration = (settime - risetime).total_seconds()
            if duration < 60:
                continue  # Less than 1 minute above horizon, so don't bother.
            if passentry[1][3] < self.parameters.min_satellite_altitude:
                continue  # It doesn't get high enough.
            riseaz = passentry[0][2]  # 0 = Rise, 2 = azimuth
            maxalt = passentry[1][3]  # 1 = Culmination, 3 = altitude
            setaz = passentry[2][2]  # 2 = Set, 2 = azimuth
            duration = (settime - risetime).total_seconds()
            line = ""
            line += (
                TextColor.green(str(risetime).split(".")[0]) + " "
            )  # When does satellite rise.
            line += (
                TextColor.green(str(round(riseaz, 0)).rjust(5, " ") + DEGREE_SYMBOL)
                + " "
            )  # Where does it rise?
            line += (
                TextColor.yellow(str(round(maxalt, 0)).rjust(4, " ") + DEGREE_SYMBOL)
                + " "
            )  # How high does it climb?
            line += (
                TextColor.yellow(human_readable_seconds(duration)) + " "
            )  # How long is it above the horizon?
            line += (
                TextColor.red(str(settime).split(".")[0].split(" ")[1]) + " "
            )  # When does satellite set.
            line += (
                TextColor.red(str(round(setaz, 0)).rjust(5, " ") + DEGREE_SYMBOL) + " "
            )  # Where does it set?
            print(line)
        return

    def next_rise_set(self):
        """Return next horizon event and time.
        Rise, Set, None"""
        risetime, settime = self.rise_set()
        eventtime = None
        eventtype = None
        if risetime is not None and risetime > now_utc():
            eventtime = risetime
            eventtype = "rise"
        if settime is not None and settime > now_utc():
            if eventtime is None or eventtime > settime:
                eventtime = settime
                eventtype = "set"
        self.log(
            "target.NextRiseSet(",
            self.name,
            "): rise",
            risetime,
            "set",
            settime,
            "eventtime",
            eventtime,
            "eventtype",
            eventtype,
            terminal=False,
        )
        return eventtype, eventtime

    def next_rise_set_hhmm(self, window=None):
        """Returns next RISE or SET time as HH:MM string.
        window says how many hours into the future is acceptable.
        Outside this window it returns '--:--'"""
        eventtype, eventtime = self.next_rise_set()
        result = ""
        if eventtype == "rise":
            result = str(eventtime)[11:16] + SYMBOLS["up"]
        elif eventtype == "set":
            result = str(eventtime)[11:16] + SYMBOLS["down"]
        if window is not None and eventtime is not None:
            cutoff = now_utc() + timedelta(hours=window)
            if eventtime > cutoff:  # Outside window.
                result = "--:--"
        self.log(
            "target.NextRiseSetHHMM(",
            self.name,
            "): eventtime",
            eventtime,
            "eventtype",
            eventtype,
            "result",
            result,
            terminal=False,
        )
        return result

    def rise_set(self):
        """Return next rise and set times for the object.
        Uses Skyfield's almanac functions for this."""
        risetime = None  # No RISE time until identified.
        settime = None  # No SET time until identified.
        if self.is_fixed_point():  # No risetime/settime time for fixed point.
            pass
        elif self.object_type == "earth satellite":
            risetime, settime = self.next_rise_set_satellite()
        else:  # Moving target, so check for rise/set times.
            risetime, settime = self.next_rise_set_object()
        self.log(
            "target.RiseSet(",
            self.name,
            "): rise",
            risetime,
            "set",
            settime,
            terminal=False,
        )
        return risetime, settime

    def current_time(self, real: bool = False, clock_offset: int = None):
        """Return skyfield format current time.
        Available as a method so that offsets or other features can be added if needed.
        if ClockOffset is set, that many seconds are added to the result. Allowing you to run the program against other dates/times.
        if real == True, then the Clockoffset is not applied, giving the true CPU time.
        """

        result = skyfield_now()  # Now. # Offset supported.
        if not real and clock_offset is not None:  # Can apply time offset.
            dt = ts_to_datetime(result)
            dt += timedelta(seconds=clock_offset)
            result = datetime2_ts(dt)
        return result

    def alt_az_to_ra_dec(self, alt, az, time=None, asdegrees=False):
        """Given alt,az coordinates (in degrees), return the current ra/dec values.

        Code based upon
          https://stackoverflow.com/questions/54827466/find-ra-dec-from-an-azimuth-elevation-in-skyfield by rfkortekaas

        asdegrees = True, both RA and DEC are returned as an angle rather than the RA object.
        """

        if time is not None:
            t = time
        else:
            t = self.ts.now()
        lookingat = self.home_site.at(t).from_altaz(alt_degrees=alt, az_degrees=az)
        ra, dec, _ = lookingat.radec()
        if asdegrees:  # Convert to pure degree values.
            ra = ra._degrees
            dec = dec.degrees
        return ra, dec

    def ra_dec_to_alt_az(self, ra, dec, time=None, asdegrees=True):
        """Given any ra,dec coordinates (in degrees) return alt-az values.
        asdegrees TRUE = ra is a float degree value.
        asdegrees FALSE = ra is a list of H,M,S values."""
        if time is None:
            time = self.current_time()  # Current time.
        if asdegrees:  # Receiving input parameters as degree values.
            rah, ram, ras = angle_to_hms(ra)
        else:  # Receiving input as list.
            rah = ra[0]
            ram = ra[1]
            ras = ra[2]
        TempStar = Star(
            ra_hours=(rah, ram, ras), dec=Angle(degrees=dec)
        )  # Create a Skyfield target object.
        temp_star_alt, temp_star_az, temp_stardistance = (
            self.home_site.at(time).observe(TempStar).apparent().altaz()
        )
        return temp_star_alt.degrees, temp_star_az.degrees

    def choose_rotation_point(self, offsetdeg=2.0):
        """Setup the rotation reference point that we measure field rotation against.
        This is a point in the sky offset from the main target.
        We measure the relative position of this point to establish field rotation metrics.
        offsetdeg is the declination offset (in degrees) from the primary target's location.
        """
        # Calculate field rotation for target.
        centre_ra, centre_dec = (
            self.ra_dec_hours()
        )  # Calculations for target from observer's location.
        centre_dec = centre_dec.degrees  # Convert to pure float degree value.
        # Offset by offsetdeg declination from the target. We'll measure how this point moves around the target to calculate the rotation rate.
        # Offset BELOW if we're in the northern hemisphere, ABOVE if we're in the southern hemisphere.
        if self.parameters._home_lat_val > 0:
            offset_dec = centre_dec - offsetdeg
        else:
            offset_dec = centre_dec + offsetdeg
        # Define a fixed radec point offset from the target, we use this to measure field rotation.
        self.rotation_point = Star(
            ra_hours=(centre_ra.hms()[0], centre_ra.hms()[1], centre_ra.hms()[2]),
            dec=Angle(degrees=offset_dec),
        )  # Create an offset point relative to the main target.
        return True

    def rotation_point_alt_az_degrees(self, time=None):
        if time is None:
            time = self.current_time()  # Current time.
        if self.rotation_point is None:
            self.choose_rotation_point()  # Choose a rotation point if not already done.
        temp_star_alt, temp_star_az, temp_stardistance = (
            self.home_site.at(time).observe(self.rotation_point).apparent().altaz()
        )  # Work out where the rotation point is.
        return temp_star_alt.degrees, temp_star_az.degrees

    def plot_rotation_point(self, time=None):
        """Return the image x,y co-ordinates of the field rotation reference point."""
        if time is None:
            time = self.current_time()  # Current time.
        rotation_alt_deg, rotation_az_deg = self.rotation_point_alt_az_degrees(
            time=time
        )  # Altitude and Azimuth in degrees of the field rotation reference point.
        az_degree, alt_degree = self.az_alt_degrees(
            time=time
        )  # Get current position of the target.
        plot_star_alt, plot_star_az = relative_alt_az(
            rotation_alt_deg, rotation_az_deg, alt_degree, az_degree
        )  # Location of rotation reference point relative to the observation target.
        temp_star_x, temp_star_y = plot_relative_alt_az(
            plot_star_alt,
            plot_star_az,
            self.camera_in_use.sensor.pixel_height,
            self.camera_in_use.sensor.pixel_width,
            self.camera_in_use.pixels_per_fov_degree_height,
            self.camera_in_use.pixels_per_fov_degree_width,
        )
        return temp_star_x, temp_star_y

    def rotation_point_bearing(self, time=None):
        """Calculate the bearing of the field rotation reference point relative to the target."""
        # AltAz mounts suffer from a characteristic rotation of the field of view as the telescope tracks an object.
        # - This field rotation can cause star trails to appear in stars on the outer edges of the image if the exposure is too long.
        # The calculated point is xx degrees of declination above/below the target object.
        if time is None:
            time = self.current_time()  # Current time.
        rotation_alt_deg, rotation_az_deg = self.rotation_point_alt_az_degrees(
            time=time
        )  # Altitude and Azimuth in degrees of the field rotation reference point.
        az_degree, alt_degree = self.az_alt_degrees(
            time=time
        )  # Get current position of the target.
        plot_star_alt, plot_star_az = relative_alt_az(
            rotation_alt_deg, rotation_az_deg, alt_degree, az_degree
        )  # Location of rotation reference point relative to the observation target.
        temp_star_x, temp_star_y = plot_relative_alt_az(
            plot_star_alt,
            plot_star_az,
            self.camera_in_use.sensor.pixel_height,
            self.camera_in_use.sensor.pixel_width,
            self.camera_in_use.pixels_per_fov_degree_height,
            self.camera_in_use.pixels_per_fov_degree_width,
        )
        xpos = round(self.camera_in_use.sensor.pixel_width / 2)
        ypos = round(self.camera_in_use.sensor.pixel_height / 2)
        # Calculate rotation angle.
        opposite = temp_star_x - xpos
        adjacent = temp_star_y - ypos
        rotation = math.degrees(math.atan2(opposite, adjacent))
        return rotation

    def rotation_pixels(self, angle=None, radius=None):
        """Convert a field rotation into worst-case pixel count in the corner of the image.
        radius parameter is the number of pixels radius from the centre of the image. If None, sensor size is used.
        span is the timespan to calculate rotation over."""
        # Convert the field rotation angle into the number of pixels in the most extreme corner of the image. That will show the maximum smearing due to rotation.
        # If no angle, calculate one based upon current selected exposure.
        if angle is None:
            angle = self.rotation_arc(span=self.camera_in_use.ExposureSeconds)
        # Radius of worst case rotation is the distance from the centre of the image to the corner.
        if radius is None:
            radius = math.sqrt(
                ((self.camera_in_use.sensor.pixel_width / 2) ** 2)
                + ((self.camera_in_use.sensor.pixel_height / 2) ** 2)
            )
        self.log("target.RotationPixels: radius", radius, terminal=False)
        circumference = (
            radius * 2 * math.pi
        )  # How many pixels in total for the circumference of the circle defined by radius?
        arclength = (
            circumference * angle / 360
        )  # How many pixels in the arc defined by radius and angle.
        return arclength

    def rotation_arc(self, span=3600, time=None):
        """Return field rotation rate.
        This calculates the rate over an hour, but returns a result scaled to the requested time span.
        Calculation is centred upon the current time unless time parameter has a value.
        """
        if time is None:
            time = self.current_time()
        calcperiod = 3600  # Calculate the rotation over an hour and then scale to the requested period. This reduces some inherent precision issues with small periods.
        t1 = ts_delta(
            time, s=-1 * round(calcperiod / 2)
        )  # Start rotation at 30minutes ago.
        t2 = ts_delta(t1, s=calcperiod)  # End rotation 30minutes ahead.
        self.log(
            "target.RotationArc: Times",
            t1.utc_strftime(),
            t2.utc_strftime(),
            terminal=False,
        )
        a1 = self.rotation_point_bearing(t1)  # Rotation angle at start.
        a2 = self.rotation_point_bearing(t2)  # Rotation angle at end.
        rate = a2 - a1  # Delta of rotation angle.
        self.log("target.RotationArc: gross rate=", rate, DEGREE_SYMBOL, terminal=False)
        rate = rate * span / calcperiod
        return rate  # Field rotates at 'rate' degrees per 'span' seconds.

    def planet_az_alt_degrees(self, name="moon", time=None):
        """Returns the current altitude and azimuth of any planetary object from Skyfield calculations.
        - Default is the Moon.
        An optional SKYFIELD timestamp can be given. If missing then the current timestamp is used.
        """
        if self.home_site is None:
            raise Exception(
                "Target.AzAltDegrees:",
                name,
                " self.home_site is not defined. Set Target.self.home_site before calling this function.",
            )
        if time is not None:
            t = time  # Use a given timestamp.
        else:
            t = self.current_time()  # Now.
        solarobject = self.planets[name]
        # Sun centered vectors. (Barycentric)
        # Calculations for a natural body.
        astrometric = self.home_site.at(t).observe(solarobject)
        alt, az, d2 = astrometric.apparent().altaz()
        azd = az.degrees  # Convert from Skyfield 'angle' to simple float degree value.
        altd = alt.degrees
        return azd, altd

    def set_home(self, homelat, homelon):
        self.home_site_topos = Topos(homelat, homelon)
        self.home_site = (
            self.planets["earth"] + self.home_site_topos
        )  # Define self.home_site as a point on earth. Could be from GPS too.

    def az_alt_degrees(self, time=None, updatespeed=False):
        """Returns the current altitude and azimuth of the target from Skyfield calculations.
        An optional SKYFIELD timestamp can be given. If missing then the current timestamp is used.
        updatespeed = True The angular velocity of the target is updated too."""
        if self.home_site is None:
            raise Exception(
                "Target.AzAltDegrees(",
                self.name,
                "): self.home_site is not defined. Set Target.self.home_site before calling this function.",
            )
        if time is not None:
            t = time  # Use a given timestamp.
        else:
            t = self.current_time()  # Now.
        if (
            self.is_fixed_point()
        ):  # Telescope is following fixed alt/az position. Ignoring sky movement.
            alt = self.handle.Altitude
            az = self.handle.Azimuth
            self.alt_velocity = 0.0
            self.az_velocity = 0.0
            return az, alt
        elif (
            hasattr(self.handle, "center") and self.handle.center == 399
        ):  # Earth centered vectors. (Geocentric)
            # Calculations for a manmade satellite.
            difference = (
                self.handle - self.home_site_topos
            )  # Can't use self.home_site because that's the wrong vector type !?!
            topocentric = difference.at(t)
            alt, az, d2 = topocentric.altaz()
        else:  # Sun centered vectors. (Barycentric)
            # Calculations for a natural body.
            astrometric = self.home_site.at(t).observe(self.handle)
            alt, az, d2 = astrometric.apparent().altaz()
        azd = az.degrees  # Convert from Skyfield 'angle' to simple float degree value.
        altd = alt.degrees
        # METEOR SHOWER co-ordinates are shifted to a likely area of the sky to see the meteors.
        # The catalog contains the radiant point, but this is not the best place to look.
        # - Online recommendations say to use azimuth 45 degrees from radiant point and altitude of 45 degrees.
        # - Here I choose the azimuth 45 degrees from the radiant point and closest to due south.
        if self.object_type == "meteor":  # Meteor shower mode.
            altd = 45.0  # Always point to 45 degrees above the horizon.
            # Check 45 degrees either side of the radiant point.
            az1 = azd - 45.0
            az2 = azd + 45.0
            if abs(az1 - 180) < abs(
                az2 - 180
            ):  # az1 is closest to due south. Use that.
                azd = az1
            else:  # az2 is closest to due south. Use that.
                azd = az2
        self.cache_az = azd  # Cached azimuth value for target. Set each time AzAltDegrees is called.
        self.cache_alt = altd  # Cached altitude value for target. Set each time AzAltDegrees is called.
        if updatespeed:  # Update the angular velocity figures too.
            if self.prev_t is not None:
                timediff = (
                    ts_to_datetime(t) - ts_to_datetime(self.prev_t)
                ).total_seconds()
                if timediff != 0.0:
                    self.az_speed = (azd - self.prev_az) / timediff
                    self.alt_speed = (altd - self.prev_alt) / timediff
                else:
                    self.az_speed = self.alt_speed = 0.0
            else:
                self.log(
                    "target.AzAltDegrees(",
                    self.name,
                    ") no previous measure yet.",
                    terminal=False,
                )
            self.prev_az = azd
            self.prev_alt = altd
            self.prev_t = t
        return azd, altd

    def is_fixed_point(self):
        """Return TRUE if this is a fixed point. Else False.
        This is used in places to allow the telescope to take photos even though
        it is not following a trajectory."""
        if isinstance(self.handle, FixedPoint):
            return True
        else:
            return False

    def can_multisession_align(
        self, acceptabletypes=["radec", "messier", "ngc", "hipparcos"]
    ):
        """Returns TRUE if the current target can be live stacked across sessions.
          These are objects which remain static against the sky as it moves,
          this allows astroalign to work across multiple sessions because it's based upon star matching.
        Returns FALSE otherwise.
          These are objects which do not move with the sky.
          Targets like planets, meteor showers or ALT AZ targets all shift against the star background.
          They will not stack nicely across multiple sessions because the target drifts too much.
        """
        if self.object_type in acceptabletypes:
            result = True  # These object types can be aligned for stacking across multiple sessions.
        else:  # Other objects will move against the background, so cannot be aligned reliably between sessions.
            result = False
        return result

    def visible(self, time=None):
        """Return TRUE if the target is currently in a portion of the sky that the telescope can observe.
        Return FALSE if the target is outside the observable portion of the sky."""
        result = True
        az, alt = self.az_alt_degrees(time=time)
        for i in MotorControls:
            if i.MotorName == "azimuth":
                if az < i.MinAngle or az > i.MaxAngle:
                    result = False
            if i.MotorName == "altitude":
                # if alt < i.MinAngle or alt > i.MaxAngle: result = False # *!*
                if alt < i.MinObservationAngle or alt > i.MaxAngle:
                    result = False  # *!*
        return result

    def approaching_limit(self, time=None):
        """Return TRUE if the target is approaching the limit of telescope movement.
        else FALSE."""
        result = False
        az, alt = self.az_alt_degrees(time=time)
        for i in MotorControls:
            if i.MotorName == "azimuth":
                if az <= i.MinWarningAngle or az >= i.MaxWarningAngle:
                    result = True
            if i.MotorName == "altitude":
                if alt <= i.MinWarningAngle or alt >= i.MaxWarningAngle:
                    result = True
        return result

    def ra_dec_hours(self, time=None):
        """Returns the current Right Ascension and Declination of the target from Skyfield calculations,
        RA and Dec in Skyfield Angle objects.
        An optional SKYFIELD timestamp can be given. If missing then the current timestamp is used.
        """
        if self.home_site is None:
            raise Exception(
                "Target.RaDecHours",
                self.name,
                ": self.home_site is not defined. Set Target.self.home_site before calling this function.",
            )
        if time is not None:
            t = time  # Use a given timestamp.
        else:
            t = self.current_time()  # Now.
        if (
            self.is_fixed_point()
        ):  # Telescope is following fixed alt/az position. Ignoring sky movement.
            ra, dec = self.alt_az_to_ra_dec(self.handle.Altitude, self.handle.Azimuth)
        elif (
            hasattr(self.handle, "center") and self.handle.center == 399
        ):  # Earth centered vectors. (Geocentric)
            # Calculations for a manmade satellite. # *Q* Could check searchgroup = 'satellite' instead?
            difference = (
                self.handle - self.home_site_topos
            )  # Can't use self.home_site because that's the wrong vector type !?!
            topocentric = difference.at(t)
            ra, dec, _ = topocentric.radec()
        else:  # Sun centered vectors. (Barycentric)
            # Calculations for a natural body.
            astrometric = self.home_site.at(t).observe(self.handle)
            ra, dec, _ = astrometric.apparent().radec()
        self.cache_ra_deg = (
            ra._degrees
        )  # Cached RA value for target. Set each time RaDecDegrees is called.
        self.cache_dec = (
            dec.degrees
        )  # Cached Dec value for target. Set each time RaDecDegrees is called.
        return ra, dec

    def ra_dec_degrees(self, time=None):
        """Returns the current Right Ascension and Declination of the target from Skyfield calculations as degrees.
        An optional SKYFIELD timestamp can be given. If missing then the current timestamp is used.
        """
        if self.home_site is None:
            raise Exception(
                "Target.RaDecDegrees:",
                self.name,
                ": self.home_site is not defined. Set Target.self.home_site before calling this function.",
            )
        if time is not None:
            t = time  # Use a given timestamp.
        else:
            t = self.current_time()  # Now.
        if (
            self.is_fixed_point()
        ):  # Telescope is following fixed alt/az position. Ignoring sky movement.
            ra, dec = self.alt_az_to_ra_dec(self.handle.Altitude, self.handle.Azimuth)
        elif (
            hasattr(self.handle, "center") and self.handle.center == 399
        ):  # Earth centered vectors. (Geocentric)
            # Calculations for a manmade satellite. # *Q* Could check searchgroup = 'satellite' instead?
            difference = (
                self.handle - self.home_site_topos
            )  # Can't use self.home_site because that's the wrong vector type !?!
            topocentric = difference.at(t)
            ra, dec, d2 = topocentric.radec()
        else:  # Sun centered vectors. (Barycentric)
            # Calculations for a natural body.
            astrometric = self.home_site.at(t).observe(self.handle)
            ra, dec, d2 = astrometric.apparent().radec()
        self.cache_ra_deg = (
            ra._degrees
        )  # Cached RA value for target. Set each time RaDecDegrees is called.
        self.cache_dec = (
            dec.degrees
        )  # Cached Dec value for target. Set each time RaDecDegrees is called.
        return ra._degrees, dec.degrees

    def lunar_phase(self, time=None):
        """Return the phase of the Moon.
        0degrees = New Moon.
        1-179degrees = Waxing.
        180degrees = Full Moon.
        181-359degrees = Waning."""
        result = None  # No result unless successful
        if time is None:
            time = self.current_time()
        result = almanac.moon_phase(self.planets, time)
        return result.degrees

    def moon_full(self, time=None):
        """Return the % of full moon.
        Used to indicate light pollution from the moon."""
        moonphase = self.lunar_phase(time=time)
        # Convert moonphase into an approximate % full. We're interested in light pollution levels.
        if moonphase > 180:
            moonphase = 360 - moonphase
        moonphase = 100 * moonphase / 180
        return moonphase

    def moon_waxing(self):
        """Return TRUE if moon is Waxing.
        Return FALSE if moon is Waning."""
        if self.lunar_phase() <= 180:
            result = True
        else:
            result = False
        return result

    def forecast_path(self, time=None, days=30, stephours=24, fov=None):
        """Calculate the path that the target will take through the sky for the next xxx days.
        Returns list of timestamps, ra and dec co-ordinates (both as degree values).
        time = start timestamp for forecast.
        days = number of days to forecast.
        stephours = number of hours between each forecast position.
        fov = field of view (degrees). Forecast stops when path leaves FOV.
            If None, the camera values are used as a basis."""
        points = []  # List of points on the path.
        if time is not None:
            temp_ts = time
        else:
            temp_ts = self.current_time()
        temp_ts = ts_delta(
            self.current_time(), s=0
        )  # This truncates the fractions of a second from the timestamp, makes display cleaner.
        cutoff_ts = ts_delta(temp_ts, dd=days)  # When does the forecast stop?
        if fov is None:  # Default the field of view.
            # Use 80% of the narrowest field-of-view of the configured lens.
            fov = (
                min(
                    self.camera_in_use.lens.fov_horizontal,
                    self.camera_in_use.lens.fov_horizontal,
                )
                * 0.8
            )
        min_ra = max_ra = None
        min_dec = max_dec = None
        while (
            temp_ts.utc_datetime() <= cutoff_ts.utc_datetime()
        ):  # Run forwards xxx days.
            ra, dec = self.ra_dec_degrees(time=temp_ts)
            # Check the span of motion. It cannot exceed the image field of view.
            if min_ra is None or min_ra > ra:
                min_ra = ra
            if max_ra is None or max_ra < ra:
                max_ra = ra
            if min_dec is None or min_dec > dec:
                min_dec = dec
            if max_dec is None or max_dec < dec:
                max_dec = dec
            if (
                abs(max_ra - min_ra) > fov or abs(max_dec - min_dec) > fov
            ):  # Motion exceeds the field of view.
                break  # Quit the loop.
            points.append((temp_ts, ra, dec))
            temp_ts = ts_delta(
                temp_ts, h=stephours
            )  # Roll forward xxx hours for the next position.
        print("ForecastPath", self.name, ":")
        print(
            "Date".rjust(10),
            "RA".rjust(14),
            "Dec".rjust(10),
            "Min RA".rjust(14),
            "Max RA".rjust(14),
            "Min Dec".rjust(10),
            "Max Dec".rjust(10),
            sep="\t",
        )
        iah, iam, ias = angle_to_hms(min_ra)  # Convert degrees to H,M,S units.
        aah, aam, aas = angle_to_hms(max_ra)
        for tt, ra, dec in points:
            rah, ram, ras = angle_to_hms(ra)  # Convert degrees to H,M,S units.
            self.log(
                str(tt.utc_datetime()).split(" ")[0],
                display_hms(rah, ram, ras, 14),
                display_degree(dec, 9) + DEGREE_SYMBOL,
                display_hms(iah, iam, ias, 14),
                display_hms(aah, aam, aas, 14),
                display_degree(min_dec, 9) + DEGREE_SYMBOL,
                display_degree(max_dec, 9) + DEGREE_SYMBOL,
                sep="\t",
                terminal=False,
            )
        return points

    def forecast_range(self, time=None, days=30):
        """Forecast the path of the target for xxx days and return the min/max ra/dec of the target during that period."""
        points = self.forecast_path(time=time, days=days)
        min_ra = max_ra = points[0][1]
        min_dec = max_dec = points[0][2]
        for tt, ra, dec in points:
            min_ra = min(min_ra, ra)
            iah, iam, ias = angle_to_hms(min_ra)
            max_ra = max(max_ra, ra)
            aah, aam, aas = angle_to_hms(max_ra)
            min_dec = min(min_dec, dec)
            max_dec = max(max_dec, dec)
        return min_ra, min_dec, max_ra, max_dec

    def forecast_centre(self, time=None, days=30):
        """Forecast the path of the target for xxx days and return the centre of it's motion during that period.
        Returned as ra/dec (both as degree values)"""
        min_ra, min_dec, max_ra, max_dec = self.forecast_range(time=time, days=days)
        return ((min_ra + max_ra) / 2), ((min_dec + max_dec) / 2)

    def apparent_comet_magnitude_gk(self):
        """ Calculate comet apparent magnitude using GK model. 
    
      Code based upon example by Bernmeister https://github.com/skyfielders/python-skyfield/issues/416 

       def get_apparent_magnitude_gk( g_absoluteMagnitude, k_luminosityIndex, bodyEarthDistanceAU, bodySunDistanceAU ):
         return g_absoluteMagnitude + \
            5 * math.log10( bodyEarthDistanceAU ) + \
            2.5 * k_luminosityIndex * math.log10( bodySunDistanceAU ) 
            
      """

        # *Q* Field names for MPC comet data were corrected in Skyfield after Nov.2020, _h and _g column names have been corrected to _g, _k
        if (
            "magnitude_h" in comets.columns
        ):  # Old format field names. Pre Nov.2020 version of Skyfield.
            g_absoluteMagnitude = self.comet_pandas_row["magnitude_h"]
            k_luminosityIndex = self.comet_pandas_row["magnitude_g"]
            self.log(
                "target.ApparentCometMagnitudeGK(",
                self.name,
                "): Using OLD format fieldnames.",
                terminal=False,
            )
        else:  # Post Nov.2020 version of Skyfield. To be verified.
            g_absoluteMagnitude = self.comet_pandas_row["magnitude_g"]
            k_luminosityIndex = self.comet_pandas_row["magnitude_k"]
            self.log(
                "target.ApparentCometMagnitudeGK(",
                self.name,
                "): Using NEW format fieldnames.",
                terminal=False,
            )
        t = self.current_time()
        temp_ra, temp_dec, sunBodyDistance = (
            self.planets["sun"].at(t).observe(self.handle).radec()
        )
        temp_alt, temp_az, earthBodyDistance = (
            self.home_site.at(t).observe(self.handle).apparent().altaz()
        )
        temp_alt, temp_az, earthSunDistance = (
            self.home_site.at(t).observe(self.planets["sun"]).apparent().altaz()
        )
        apparentMagnitude = (
            g_absoluteMagnitude
            + (5 * math.log10(earthBodyDistance.au))
            + (2.5 * k_luminosityIndex * math.log10(sunBodyDistance.au))
        )
        apparentMagnitude = round(apparentMagnitude, 1)  # Magnitude to 1 decimal place.
        self.log(
            "target.ApparentCometMagnitudeGK(",
            self.name,
            "): Apparent magnitude:",
            apparentMagnitude,
            terminal=False,
        )
        return apparentMagnitude
