

from utils.params import attributemaster


class target(attributemaster):
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
  ):
    self.SetLogger(
      MainLog
    )  # Inherited from attributemaster: Set up references to chosen logger (or disable if no logger defined).
    self.Handle = handle  # Skyfield object for target. This is usually provided directly by the calling routine, but in the case of 'comets' it is calculated here during initialisation.
    self.Name = name  # Name of object.
    self.SearchGroup = searchgroup  # Which search category was used?
    self.SearchTerm = searchterm  # Which search term identifies this object?
    self.ObjectType = objecttype
    self.Constellation = constellation
    self.Description = description
    self.Magnitude = magnitude
    self.DiameterDegrees = objectdiameter  # diameter of the object in the sky. # Used to warn if target is too small.!
    self.RecommendedExposure = None  # Recommended exposure for this object.
    self.HomeSite = None  # Skyfield object for home site.
    self.HomeSiteTopos = None  # Skyfield object for home site.
    self.ts = (
      load.timescale()
    )  # Time handling with astro corrections. ! Don't use this to read current time, always use SkyfieldNow() function!
    self.SetHome(
      Parameters.HomeLat, Parameters.HomeLon
    )  # Use global variables at the moment. Requires that global list 'planets' is available too.
    self.CometPandasRow = cometpandasrow  # Comets don't have a skyfield object in 'Handle', we calculate the position differently, so store their pandas row here.
    self.CacheRADeg = (
      None  # Cached RA value for target. Set each time RaDecDegrees is called.
    )
    self.CacheDec = (
      None  # Cached Dec value for target. Set each time RaDecDegrees is called.
    )
    self.CacheAlt = None  # Cached Altitude value for target. Set each time AzAltDegrees is called.
    self.CacheAz = None  # Cached Azimuth value for target. Set each time AzAltDegrees is called.
    self.PrevT = None  # TS timestamp when location was last checked (for calculating angular velocity)
    self.AzSpeed = 0.0  # Angular speed (deg/sec)
    self.AltSpeed = 0.0  # Angular speed (deg/sec)
    self.PrevAz = None  # Previous location
    self.PrevAlt = None  # Previous location
    self.RotationPoint = None  # Will hold rotation reference point if activated.
    self.ScheduledStart = None  # Holds the UTC timestamp when the observation should start (if one is set).
    self.ScheduledEnd = None  # Holds the UTC timestamp when the observation should end (if one is set).

  def TwilightLevel(self, time=None):
    """Return the twilight level for the current location.
    NOTE: The target needs to be the sun!
    If 'time' parameter given, it's the lightlevel at that time.
    If 'time' is None, then the current time is used."""
    az, alt = self.AzAltDegrees(time=time)
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

  def Datetime2Ts(self, dt):  # Referenced by external dependencies.
    """Convert datetime into TS (skyfield) timestamp."""
    t = Datetime2Ts(dt)  # Convert to skyfield time type.
    return t

  def CurrentMagnitude(self, time=None):
    """Calculate the current magnitude (or for a specific time) if possible."""
    if time is None:
      time = self.CurrentTime()
    result = (
      self.Magnitude
    )  # Default to the standard magnitude for this object if known.
    try:
      astrometric = self.HomeSite.at(time).observe(self.Handle)
      temp = planetary_magnitude(astrometric)
      if temp != None:
        result = temp
      self.Log(
        "target.CurrentMagnitude: planetary_magnitude returned",
        temp,
        terminal=False,
      )
    except Exception:
      self.Log(
        "target.CurrentMagnitude: planetary_magnitude didn't work for this target.",
        terminal=False,
      )
    return result

  def UpdateLocation(self, newhandle):
    """Revise the skyfield target handle.
    Used when performing sky surveys of multiple locations around a target.
    Use this if you need to modify the location of the target for some reason (eg new RADEC) but retain all the other attributes.
    """
    self.Handle = newhandle
    self.RotationPoint = None  # Will hold rotation reference point if activated.
    self.Log(
      "target.UpdateLocation(): New co-ordinates updated to the target.",
      terminal=False,
    )

  def NextRiseSetObject(self):
    """Return next horion event and time for distant objects. (Moon and beyond)"""
    risetime = None  # No RISE time until identified.
    settime = None  # No SET time until identified.
    f = almanac.risings_and_settings(planets, self.Handle, self.HomeSiteTopos)
    tsnow = (
      self.CurrentTime().utc_datetime()
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
      self.Log("target.RiseSet(", self.Name, "): zipped", ti, yi, terminal=False)
      tidt = ti.utc_datetime()
      if tidt < NowUTC():
        continue  # In the past, ignore it.
      if yi and risetime is None:  # First future rise time.
        risetime = tidt
      elif settime is None:  # First future set time.
        settime = tidt
    return risetime, settime

  def NextRiseSetSatellite(self):
    """Return next horizon event and time for satellites."""
    self.Log("target.NextRiseSetSatellite(", self.Name, ")", terminal=False)
    if not hasattr(
      self.Handle, "find_events"
    ):  # This object doesn't support satellite pass calculations.
      self.Log(
        "Cannot calculate next Rise Set times for this type of target(",
        self.Name,
        self.ObjectType,
        ")",
        terminal=True,
      )
      self.Log(
        "target.NextRiseSetSatellite: find_events method not in this target type.",
        terminal=True,
      )
      return
    risetime = settime = None
    t_from = self.CurrentTime()  # Start now.
    t_to = TsDelta(t_from, dd=1)  # Stop in 24hours time.
    self.Log(
      "target.NextRiseSetSatellite: t_from",
      str(t_from),
      "t_to",
      str(t_to),
      terminal=False,
    )
    times, events = self.Handle.find_events(
      self.HomeSiteTopos, t_from, t_to, Parameters.MinSatelliteAltitude
    )  # What events occur above horizon in next 24 hours?
    self.Log(
      "target.NextRiseSetSatellite: times",
      times,
      "events",
      events,
      terminal=False,
    )
    telist = zip(times, events)
    for te in telist:
      self.Log("target.NextRiseSetSatellite: Entry:", te, terminal=False)
      eventtime = te[0]
      eventtype = te[1]  # 0=Rise, 1=Culminate, 2=Set
      if eventtype == 2 and settime is None and risetime != None:
        settime = eventtime.utc_datetime()
      if eventtype == 0 and risetime is None:
        risetime = eventtime.utc_datetime()
      if eventtype == 1:  # Culmination, how high?
        self.Log(
          "target.NextRiseSetSatellite: Checking culmination at",
          eventtime.utc_datetime(),
          terminal=False,
        )
        az, alt = self.AzAltDegrees(time=eventtime)
        self.Log(
          "target.NextRiseSetSatellite: Culmination at",
          eventtime.utc_datetime(),
          "is",
          Deg3dp(alt),
          DegreeSymbol,
          terminal=False,
        )
      if risetime != None and settime != None:
        break  # We have our earliest acceptable set of values.
    self.Log(
      "target.NextRiseSetSatellite: Rise",
      risetime,
      "set",
      settime,
      terminal=False,
    )
    return risetime, settime

  def SatellitePasses(self, window=24):
    """Print table of satellite pass information for next xx hours."""
    self.Log("target.SatellitePasses: NOT YET IMPLEMENTED.", terminal=False)
    t_from = self.CurrentTime()  # Start now.
    t_to = TsDelta(t_from, dd=1)  # Stop in 24hours time.
    self.Log(
      "target.SatellitePasses: t_from",
      str(t_from),
      "t_to",
      str(t_to),
      terminal=False,
    )
    if not hasattr(
      self.Handle, "find_events"
    ):  # This object doesn't support satellite pass calculations.
      self.Log(
        "Cannot calculate next pass times for this type of target(",
        self.Name,
        self.ObjectType,
        ")",
        terminal=True,
      )
      self.Log(
        "target.SatellitePasses: find_events method not in this target type.",
        terminal=True,
      )
      return
    times, events = self.Handle.find_events(
      self.HomeSiteTopos, t_from, t_to, 0.0
    )  # What events occur above horizon in next 24 hours?
    self.Log(
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
      eventaz, eventalt = self.AzAltDegrees(time=eventtime)
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
    print(TextColor.yellow("Satellite: " + self.Name))
    print(
      TextColor.yellow(
        "Passes which culminate above "
        + str(Parameters.MinSatelliteAltitude)
        + DegreeSymbol
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
      if passentry[1][3] < Parameters.MinSatelliteAltitude:
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
        TextColor.green(str(round(riseaz, 0)).rjust(5, " ") + DegreeSymbol)
        + " "
      )  # Where does it rise?
      line += (
        TextColor.yellow(str(round(maxalt, 0)).rjust(4, " ") + DegreeSymbol)
        + " "
      )  # How high does it climb?
      line += (
        TextColor.yellow(HRSeconds(duration)) + " "
      )  # How long is it above the horizon?
      line += (
        TextColor.red(str(settime).split(".")[0].split(" ")[1]) + " "
      )  # When does satellite set.
      line += (
        TextColor.red(str(round(setaz, 0)).rjust(5, " ") + DegreeSymbol) + " "
      )  # Where does it set?
      print(line)
    return

  def NextRiseSet(self):
    """Return next horizon event and time.
    Rise, Set, None"""
    risetime, settime = self.RiseSet()
    eventtime = None
    eventtype = None
    if risetime != None and risetime > NowUTC():
      eventtime = risetime
      eventtype = "rise"
    if settime != None and settime > NowUTC():
      if eventtime is None or eventtime > settime:
        eventtime = settime
        eventtype = "set"
    self.Log(
      "target.NextRiseSet(",
      self.Name,
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

  def NextRiseSetHHMM(self, window=None):
    """Returns next RISE or SET time as HH:MM string.
    window says how many hours into the future is acceptable.
    Outside this window it returns '--:--'"""
    eventtype, eventtime = self.NextRiseSet()
    result = ""
    if eventtype == "rise":
      result = str(eventtime)[11:16] + Symbol["up"]
    elif eventtype == "set":
      result = str(eventtime)[11:16] + Symbol["down"]
    if window != None and eventtime != None:
      cutoff = NowUTC() + timedelta(hours=window)
      if eventtime > cutoff:  # Outside window.
        result = "--:--"
    self.Log(
      "target.NextRiseSetHHMM(",
      self.Name,
      "): eventtime",
      eventtime,
      "eventtype",
      eventtype,
      "result",
      result,
      terminal=False,
    )
    return result

  def RiseSet(self):
    """Return next rise and set times for the object.
    Uses Skyfield's almanac functions for this."""
    risetime = None  # No RISE time until identified.
    settime = None  # No SET time until identified.
    if self.IsFixedPoint():  # No risetime/settime time for fixed point.
      pass
    elif self.ObjectType == "earth satellite":
      risetime, settime = self.NextRiseSetSatellite()
    else:  # Moving target, so check for rise/set times.
      risetime, settime = self.NextRiseSetObject()
    self.Log(
      "target.RiseSet(",
      self.Name,
      "): rise",
      risetime,
      "set",
      settime,
      terminal=False,
    )
    return risetime, settime

  def CurrentTime(self, real=False):
    """Return skyfield format current time.
    Available as a method so that offsets or other features can be added if needed.
    if ClockOffset is set, that many seconds are added to the result. Allowing you to run the program against other dates/times.
    if real == True, then the Clockoffset is not applied, giving the true CPU time.
    """
    result = SkyfieldNow()  # Now. # Offset supported.
    if real == False and ClockOffset != None:  # Can apply time offset.
      dt = Ts2Datetime(result)
      dt + timedelta(seconds=ClockOffset)
      result = Datetime2Ts(dt)
    return result

  def AltAzToRaDec(self, alt, az, time=None, asdegrees=False):
    """Given alt,az coordinates (in degrees), return the current ra/dec values.

    Code based upon
      https://stackoverflow.com/questions/54827466/find-ra-dec-from-an-azimuth-elevation-in-skyfield by rfkortekaas

    asdegrees = True, both RA and DEC are returned as an angle rather than the RA object.
    """

    if time != None:
      t = time
    else:
      t = ts.now()
    lookingat = HomeSite.at(t).from_altaz(alt_degrees=alt, az_degrees=az)
    ra, dec, _ = lookingat.radec()
    if asdegrees:  # Convert to pure degree values.
      ra = ra._degrees
      dec = dec.degrees
    return ra, dec

  def RaDecToAltAz(self, ra, dec, time=None, asdegrees=True):
    """Given any ra,dec coordinates (in degrees) return alt-az values.
    asdegrees TRUE = ra is a float degree value.
    asdegrees FALSE = ra is a list of H,M,S values."""
    if time is None:
      time = self.CurrentTime()  # Current time.
    if asdegrees:  # Receiving input parameters as degree values.
      rah, ram, ras = AngleToHMS(ra)
    else:  # Receiving input as list.
      rah = ra[0]
      ram = ra[1]
      ras = ra[2]
    TempStar = Star(
      ra_hours=(rah, ram, ras), dec=Angle(degrees=dec)
    )  # Create a Skyfield target object.
    TempStarAlt, TempStarAz, TempStardistance = (
      HomeSite.at(time).observe(TempStar).apparent().altaz()
    )
    return TempStarAlt.degrees, TempStarAz.degrees

  def ChooseRotationPoint(self, offsetdeg=2.0):
    """Setup the rotation reference point that we measure field rotation against.
    This is a point in the sky offset from the main target.
    We measure the relative position of this point to establish field rotation metrics.
    offsetdeg is the declination offset (in degrees) from the primary target's location.
    """
    # Calculate field rotation for target.
    CentreRa, CentreDec = (
      self.RaDecHours()
    )  # Calculations for target from observer's location.
    CentreDec = CentreDec.degrees  # Convert to pure float degree value.
    # Offset by offsetdeg declination from the target. We'll measure how this point moves around the target to calculate the rotation rate.
    # Offset BELOW if we're in the northern hemisphere, ABOVE if we're in the southern hemisphere.
    if Parameters._HomeLatVal > 0:
      OffsetDec = CentreDec - offsetdeg
    else:
      OffsetDec = CentreDec + offsetdeg
    # Define a fixed radec point offset from the target, we use this to measure field rotation.
    self.RotationPoint = Star(
      ra_hours=(CentreRa.hms()[0], CentreRa.hms()[1], CentreRa.hms()[2]),
      dec=Angle(degrees=OffsetDec),
    )  # Create an offset point relative to the main target.
    return True

  def RotationPointAltAzDegrees(self, time=None):
    if time is None:
      time = self.CurrentTime()  # Current time.
    if self.RotationPoint is None:
      self.ChooseRotationPoint()  # Choose a rotation point if not already done.
    TempStarAlt, TempStarAz, TempStardistance = (
      HomeSite.at(time).observe(self.RotationPoint).apparent().altaz()
    )  # Work out where the rotation point is.
    return TempStarAlt.degrees, TempStarAz.degrees

  def PlotRotationPoint(self, time=None):
    """Return the image x,y co-ordinates of the field rotation reference point."""
    if time is None:
      time = self.CurrentTime()  # Current time.
    RotationAltDeg, RotationAzDeg = self.RotationPointAltAzDegrees(
      time=time
    )  # Altitude and Azimuth in degrees of the field rotation reference point.
    az_degree, alt_degree = self.AzAltDegrees(
      time=time
    )  # Get current position of the target.
    PlotStarAlt, PlotStarAz = RelativeAltAz(
      RotationAltDeg, RotationAzDeg, alt_degree, az_degree
    )  # Location of rotation reference point relative to the observation target.
    TempStarX, TempStarY = PlotRelativeAltAz(
      PlotStarAlt, PlotStarAz, SensorInUse.PixelHeight, SensorInUse.PixelWidth
    )
    return TempStarX, TempStarY

  def RotationPointBearing(self, time=None):
    """Calculate the bearing of the field rotation reference point relative to the target."""
    # AltAz mounts suffer from a characteristic rotation of the field of view as the telescope tracks an object.
    # - This field rotation can cause star trails to appear in stars on the outer edges of the image if the exposure is too long.
    # The calculated point is xx degrees of declination above/below the target object.
    if time is None:
      time = self.CurrentTime()  # Current time.
    RotationAltDeg, RotationAzDeg = self.RotationPointAltAzDegrees(
      time=time
    )  # Altitude and Azimuth in degrees of the field rotation reference point.
    az_degree, alt_degree = self.AzAltDegrees(
      time=time
    )  # Get current position of the target.
    PlotStarAlt, PlotStarAz = RelativeAltAz(
      RotationAltDeg, RotationAzDeg, alt_degree, az_degree
    )  # Location of rotation reference point relative to the observation target.
    TempStarX, TempStarY = PlotRelativeAltAz(
      PlotStarAlt, PlotStarAz, SensorInUse.PixelHeight, SensorInUse.PixelWidth
    )
    xpos = round(SensorInUse.PixelWidth / 2)
    ypos = round(SensorInUse.PixelHeight / 2)
    # Calculate rotation angle.
    opposite = TempStarX - xpos
    adjacent = TempStarY - ypos
    rotation = math.degrees(math.atan2(opposite, adjacent))
    return rotation

  def RotationPixels(self, angle=None, radius=None):
    """Convert a field rotation into worst-case pixel count in the corner of the image.
    radius parameter is the number of pixels radius from the centre of the image. If None, sensor size is used.
    span is the timespan to calculate rotation over."""
    # Convert the field rotation angle into the number of pixels in the most extreme corner of the image. That will show the maximum smearing due to rotation.
    # If no angle, calculate one based upon current selected exposure.
    if angle is None:
      angle = self.RotationArc(span=CameraInUse.ExposureSeconds)
    # Radius of worst case rotation is the distance from the centre of the image to the corner.
    if radius is None:
      radius = math.sqrt(
        ((SensorInUse.PixelWidth / 2) ** 2)
        + ((SensorInUse.PixelHeight / 2) ** 2)
      )
    self.Log("target.RotationPixels: radius", radius, terminal=False)
    circumference = (
      radius * 2 * math.pi
    )  # How many pixels in total for the circumference of the circle defined by radius?
    arclength = (
      circumference * angle / 360
    )  # How many pixels in the arc defined by radius and angle.
    return arclength

  def RotationArc(self, span=3600, time=None):
    """Return field rotation rate.
    This calculates the rate over an hour, but returns a result scaled to the requested time span.
    Calculation is centred upon the current time unless time parameter has a value.
    """
    if time is None:
      time = self.CurrentTime()
    calcperiod = 3600  # Calculate the rotation over an hour and then scale to the requested period. This reduces some inherent precision issues with small periods.
    t1 = TsDelta(
      time, s=-1 * round(calcperiod / 2)
    )  # Start rotation at 30minutes ago.
    t2 = TsDelta(t1, s=calcperiod)  # End rotation 30minutes ahead.
    self.Log(
      "target.RotationArc: Times",
      t1.utc_strftime(),
      t2.utc_strftime(),
      terminal=False,
    )
    a1 = self.RotationPointBearing(t1)  # Rotation angle at start.
    a2 = self.RotationPointBearing(t2)  # Rotation angle at end.
    rate = a2 - a1  # Delta of rotation angle.
    self.Log("target.RotationArc: gross rate=", rate, DegreeSymbol, terminal=False)
    rate = rate * span / calcperiod
    return rate  # Field rotates at 'rate' degrees per 'span' seconds.

  def PlanetAzAltDegrees(self, name="moon", time=None):
    """Returns the current altitude and azimuth of any planetary object from Skyfield calculations.
    - Default is the Moon.
    An optional SKYFIELD timestamp can be given. If missing then the current timestamp is used.
    """
    if self.HomeSite is None:
      raise Exception(
        "Target.AzAltDegrees:",
        name,
        " HomeSite is not defined. Set Target.HomeSite before calling this function.",
      )
    if time != None:
      t = time  # Use a given timestamp.
    else:
      t = self.CurrentTime()  # Now.
    solarobject = planets[name]
    # Sun centered vectors. (Barycentric)
    # Calculations for a natural body.
    astrometric = self.HomeSite.at(t).observe(solarobject)
    alt, az, d2 = astrometric.apparent().altaz()
    azd = az.degrees  # Convert from Skyfield 'angle' to simple float degree value.
    altd = alt.degrees
    return azd, altd

  def SetHome(self, homelat, homelon):
    self.HomeSiteTopos = Topos(homelat, homelon)
    self.HomeSite = (
      planets["earth"] + self.HomeSiteTopos
    )  # Define HomeSite as a point on earth. Could be from GPS too.

  def AzAltDegrees(self, time=None, updatespeed=False):
    """Returns the current altitude and azimuth of the target from Skyfield calculations.
    An optional SKYFIELD timestamp can be given. If missing then the current timestamp is used.
    updatespeed = True The angular velocity of the target is updated too."""
    if self.HomeSite is None:
      raise Exception(
        "Target.AzAltDegrees(",
        self.Name,
        "): HomeSite is not defined. Set Target.HomeSite before calling this function.",
      )
    if time != None:
      t = time  # Use a given timestamp.
    else:
      t = self.CurrentTime()  # Now.
    if (
      self.IsFixedPoint()
    ):  # Telescope is following fixed alt/az position. Ignoring sky movement.
      alt = self.Handle.Altitude
      az = self.Handle.Azimuth
      self.AltVelocity = 0.0
      self.AzVelocity = 0.0
      return az, alt
    elif (
      hasattr(self.Handle, "center") and self.Handle.center == 399
    ):  # Earth centered vectors. (Geocentric)
      # Calculations for a manmade satellite.
      difference = (
        self.Handle - self.HomeSiteTopos
      )  # Can't use HomeSite because that's the wrong vector type !?!
      topocentric = difference.at(t)
      alt, az, d2 = topocentric.altaz()
    else:  # Sun centered vectors. (Barycentric)
      # Calculations for a natural body.
      astrometric = self.HomeSite.at(t).observe(self.Handle)
      alt, az, d2 = astrometric.apparent().altaz()
    azd = az.degrees  # Convert from Skyfield 'angle' to simple float degree value.
    altd = alt.degrees
    # METEOR SHOWER co-ordinates are shifted to a likely area of the sky to see the meteors.
    # The catalog contains the radiant point, but this is not the best place to look.
    # - Online recommendations say to use azimuth 45 degrees from radiant point and altitude of 45 degrees.
    # - Here I choose the azimuth 45 degrees from the radiant point and closest to due south.
    if self.ObjectType == "meteor":  # Meteor shower mode.
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
    self.CacheAz = azd  # Cached azimuth value for target. Set each time AzAltDegrees is called.
    self.CacheAlt = altd  # Cached altitude value for target. Set each time AzAltDegrees is called.
    if updatespeed:  # Update the angular velocity figures too.
      if self.PrevT != None:
        timediff = (Ts2Datetime(t) - Ts2Datetime(self.PrevT)).total_seconds()
        if timediff != 0.0:
          self.AzSpeed = (azd - self.PrevAz) / timediff
          self.AltSpeed = (altd - self.PrevAlt) / timediff
        else:
          self.AzSpeed = self.AltSpeed = 0.0
      else:
        self.Log(
          "target.AzAltDegrees(",
          self.Name,
          ") no previous measure yet.",
          terminal=False,
        )
      self.PrevAz = azd
      self.PrevAlt = altd
      self.PrevT = t
    return azd, altd

  def IsFixedPoint(self):
    """Return TRUE if this is a fixed point. Else False.
    This is used in places to allow the telescope to take photos even though
    it is not following a trajectory."""
    if isinstance(self.Handle, FixedPoint):
      return True
    else:
      return False

  def CanMultisessionAlign(
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
    if self.ObjectType in acceptabletypes:
      result = True  # These object types can be aligned for stacking across multiple sessions.
    else:  # Other objects will move against the background, so cannot be aligned reliably between sessions.
      result = False
    return result

  def Visible(self, time=None):
    """Return TRUE if the target is currently in a portion of the sky that the telescope can observe.
    Return FALSE if the target is outside the observable portion of the sky."""
    result = True
    az, alt = self.AzAltDegrees(time=time)
    for i in MotorControls:
      if i.MotorName == "azimuth":
        if az < i.MinAngle or az > i.MaxAngle:
          result = False
      if i.MotorName == "altitude":
        # if alt < i.MinAngle or alt > i.MaxAngle: result = False # *!*
        if alt < i.MinObservationAngle or alt > i.MaxAngle:
          result = False  # *!*
    return result

  def ApproachingLimit(self, time=None):
    """Return TRUE if the target is approaching the limit of telescope movement.
    else FALSE."""
    result = False
    az, alt = self.AzAltDegrees(time=time)
    for i in MotorControls:
      if i.MotorName == "azimuth":
        if az <= i.MinWarningAngle or az >= i.MaxWarningAngle:
          result = True
      if i.MotorName == "altitude":
        if alt <= i.MinWarningAngle or alt >= i.MaxWarningAngle:
          result = True
    return result

  def RaDecHours(self, time=None):
    """Returns the current Right Ascension and Declination of the target from Skyfield calculations, RA and Dec in Skyfield Angle objects.
    An optional SKYFIELD timestamp can be given. If missing then the current timestamp is used.
    """
    if self.HomeSite is None:
      raise Exception(
        "Target.RaDecHours",
        self.Name,
        ": HomeSite is not defined. Set Target.HomeSite before calling this function.",
      )
    if time != None:
      t = time  # Use a given timestamp.
    else:
      t = self.CurrentTime()  # Now.
    if (
      self.IsFixedPoint()
    ):  # Telescope is following fixed alt/az position. Ignoring sky movement.
      ra, dec = self.AltAzToRaDec(self.Handle.Altitude, self.Handle.Azimuth)
    elif (
      hasattr(self.Handle, "center") and self.Handle.center == 399
    ):  # Earth centered vectors. (Geocentric)
      # Calculations for a manmade satellite. # *Q* Could check searchgroup = 'satellite' instead?
      difference = (
        self.Handle - self.HomeSiteTopos
      )  # Can't use HomeSite because that's the wrong vector type !?!
      topocentric = difference.at(t)
      ra, dec, _ = topocentric.radec()
    else:  # Sun centered vectors. (Barycentric)
      # Calculations for a natural body.
      astrometric = self.HomeSite.at(t).observe(self.Handle)
      ra, dec, _ = astrometric.apparent().radec()
    self.CacheRADeg = (
      ra._degrees
    )  # Cached RA value for target. Set each time RaDecDegrees is called.
    self.CacheDec = (
      dec.degrees
    )  # Cached Dec value for target. Set each time RaDecDegrees is called.
    return ra, dec

  def RaDecDegrees(self, time=None):
    """Returns the current Right Ascension and Declination of the target from Skyfield calculations as degrees.
    An optional SKYFIELD timestamp can be given. If missing then the current timestamp is used.
    """
    if self.HomeSite is None:
      raise Exception(
        "Target.RaDecDegrees:",
        self.Name,
        ": HomeSite is not defined. Set Target.HomeSite before calling this function.",
      )
    if time != None:
      t = time  # Use a given timestamp.
    else:
      t = self.CurrentTime()  # Now.
    if (
      self.IsFixedPoint()
    ):  # Telescope is following fixed alt/az position. Ignoring sky movement.
      ra, dec = self.AltAzToRaDec(self.Handle.Altitude, self.Handle.Azimuth)
    elif (
      hasattr(self.Handle, "center") and self.Handle.center == 399
    ):  # Earth centered vectors. (Geocentric)
      # Calculations for a manmade satellite. # *Q* Could check searchgroup = 'satellite' instead?
      difference = (
        self.Handle - self.HomeSiteTopos
      )  # Can't use HomeSite because that's the wrong vector type !?!
      topocentric = difference.at(t)
      ra, dec, d2 = topocentric.radec()
    else:  # Sun centered vectors. (Barycentric)
      # Calculations for a natural body.
      astrometric = self.HomeSite.at(t).observe(self.Handle)
      ra, dec, d2 = astrometric.apparent().radec()
    self.CacheRADeg = (
      ra._degrees
    )  # Cached RA value for target. Set each time RaDecDegrees is called.
    self.CacheDec = (
      dec.degrees
    )  # Cached Dec value for target. Set each time RaDecDegrees is called.
    return ra._degrees, dec.degrees

  def LunarPhase(self, time=None):
    """Return the phase of the Moon.
    0degrees = New Moon.
    1-179degrees = Waxing.
    180degrees = Full Moon.
    181-359degrees = Waning."""
    result = None  # No result unless successful
    if time is None:
      time = self.CurrentTime()
    result = almanac.moon_phase(planets, time)
    return result.degrees

  def MoonFull(self, time=None):
    """Return the % of full moon.
    Used to indicate light pollution from the moon."""
    moonphase = self.LunarPhase(time=time)
    # Convert moonphase into an approximate % full. We're interested in light pollution levels.
    if moonphase > 180:
      moonphase = 360 - moonphase
    moonphase = 100 * moonphase / 180
    return moonphase

  def MoonWaxing(self):
    """Return TRUE if moon is Waxing.
    Return FALSE if moon is Waning."""
    if self.LunarPhase() <= 180:
      result = True
    else:
      result = False
    return result

  def ForecastPath(self, time=None, days=30, stephours=24, fov=None):
    """Calculate the path that the target will take through the sky for the next xxx days.
    Returns list of timestamps, ra and dec co-ordinates (both as degree values).
    time = start timestamp for forecast.
    days = number of days to forecast.
    stephours = number of hours between each forecast position.
    fov = field of view (degrees). Forecast stops when path leaves FOV.
        If None, the camera values are used as a basis."""
    Points = []  # List of points on the path.
    if time != None:
      temp_ts = time
    else:
      temp_ts = self.CurrentTime()
    temp_ts = TsDelta(
      self.CurrentTime(), s=0
    )  # This truncates the fractions of a second from the timestamp, makes display cleaner.
    cutoff_ts = TsDelta(temp_ts, dd=days)  # When does the forecast stop?
    if fov is None:  # Default the field of view.
      # Use 80% of the narrowest field-of-view of the configured lens.
      fov = (
        min(CameraInUse.Lens.FovHorizontal, CameraInUse.Lens.FovHorizontal)
        * 0.8
      )
    min_ra = max_ra = None
    min_dec = max_dec = None
    while (
      temp_ts.utc_datetime() <= cutoff_ts.utc_datetime()
    ):  # Run forwards xxx days.
      ra, dec = self.RaDecDegrees(time=temp_ts)
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
      Points.append((temp_ts, ra, dec))
      temp_ts = TsDelta(
        temp_ts, h=stephours
      )  # Roll forward xxx hours for the next position.
    print("ForecastPath", self.Name, ":")
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
    iah, iam, ias = AngleToHMS(min_ra)  # Convert degrees to H,M,S units.
    aah, aam, aas = AngleToHMS(max_ra)
    for tt, ra, dec in Points:
      rah, ram, ras = AngleToHMS(ra)  # Convert degrees to H,M,S units.
      self.Log(
        str(tt.utc_datetime()).split(" ")[0],
        DisplayHMS(rah, ram, ras, 14),
        DisplayDegree(dec, 9) + DegreeSymbol,
        DisplayHMS(iah, iam, ias, 14),
        DisplayHMS(aah, aam, aas, 14),
        DisplayDegree(min_dec, 9) + DegreeSymbol,
        DisplayDegree(max_dec, 9) + DegreeSymbol,
        sep="\t",
        terminal=False,
      )
    return Points

  def ForecastRange(self, time=None, days=30):
    """Forecast the path of the target for xxx days and return the min/max ra/dec of the target during that period."""
    Points = self.ForecastPath(time=time, days=days)
    min_ra = max_ra = Points[0][1]
    min_dec = max_dec = Points[0][2]
    for tt, ra, dec in Points:
      min_ra = min(min_ra, ra)
      iah, iam, ias = AngleToHMS(min_ra)
      max_ra = max(max_ra, ra)
      aah, aam, aas = AngleToHMS(max_ra)
      min_dec = min(min_dec, dec)
      max_dec = max(max_dec, dec)
    return min_ra, min_dec, max_ra, max_dec

  def ForecastCentre(self, time=None, days=30):
    """Forecast the path of the target for xxx days and return the centre of it's motion during that period.
    Returned as ra/dec (both as degree values)"""
    min_ra, min_dec, max_ra, max_dec = self.ForecastRange(time=time, days=days)
    return ((min_ra + max_ra) / 2), ((min_dec + max_dec) / 2)

  def ApparentCometMagnitudeGK(self):
    """ Calculate comet apparent magnitude using GK model. 
    
      Code based upon example by Bernmeister https://github.com/skyfielders/python-skyfield/issues/416 

       def getApparentMagnitude_gk( g_absoluteMagnitude, k_luminosityIndex, bodyEarthDistanceAU, bodySunDistanceAU ):
         return g_absoluteMagnitude + \
            5 * math.log10( bodyEarthDistanceAU ) + \
            2.5 * k_luminosityIndex * math.log10( bodySunDistanceAU ) 
            
      """

    # *Q* Field names for MPC comet data were corrected in Skyfield after Nov.2020, _h and _g column names have been corrected to _g, _k
    if (
      "magnitude_h" in comets.columns
    ):  # Old format field names. Pre Nov.2020 version of Skyfield.
      g_absoluteMagnitude = self.CometPandasRow["magnitude_h"]
      k_luminosityIndex = self.CometPandasRow["magnitude_g"]
      self.Log(
        "target.ApparentCometMagnitudeGK(",
        self.Name,
        "): Using OLD format fieldnames.",
        terminal=False,
      )
    else:  # Post Nov.2020 version of Skyfield. To be verified.
      g_absoluteMagnitude = self.CometPandasRow["magnitude_g"]
      k_luminosityIndex = self.CometPandasRow["magnitude_k"]
      self.Log(
        "target.ApparentCometMagnitudeGK(",
        self.Name,
        "): Using NEW format fieldnames.",
        terminal=False,
      )
    t = self.CurrentTime()
    temp_ra, temp_dec, sunBodyDistance = (
      planets["sun"].at(t).observe(self.Handle).radec()
    )
    temp_alt, temp_az, earthBodyDistance = (
      self.HomeSite.at(t).observe(self.Handle).apparent().altaz()
    )
    temp_alt, temp_az, earthSunDistance = (
      self.HomeSite.at(t).observe(planets["sun"]).apparent().altaz()
    )
    apparentMagnitude = (
      g_absoluteMagnitude
      + (5 * math.log10(earthBodyDistance.au))
      + (2.5 * k_luminosityIndex * math.log10(sunBodyDistance.au))
    )
    apparentMagnitude = round(apparentMagnitude, 1)  # Magnitude to 1 decimal place.
    self.Log(
      "target.ApparentCometMagnitudeGK(",
      self.Name,
      "): Apparent magnitude:",
      apparentMagnitude,
      terminal=False,
    )
    return apparentMagnitude

