
from datetime import datetime, timezone
from oscommand import OSCommand
from utils.textcolor import TextColor


class AstroSensor:
  """Object representing the IMAGE SENSOR being used by the telescope.
  Default values are for the V1 RPi High Quality Camera (Sony sensor)?
  Individual characteristics can be specified, or a specific sensor type can be given.
  Contains some attributes which are used to convert between FIELD OF VIEW and PHOTO DIMENSIONS for example.
  """

  # Can create a dictionary of sensor types and capabilities here.
  # width = image width in pixels.
  # height = image height in pixels.
  # video = Can take video in this mode.
  # image = Can take photo in this mode.
  # fov = full or partial field of view. partial means only the centre of the sensor is used. full means the whole sensor is used.
  # maxseconds = Longest exposure time supported.
  # raw = Can capture raw bayer data.
  # (*Q* This may not be needed in the future if libcamera can recognise the capabilities automatically.)
  SensorDict = {
    "imx477": {
      1: {
        "width": 2028,
        "height": 1080,
        "video": True,
        "image": False,
        "aspect": "169:90",
        "framerate": {"min": 0.1, "max": 50},
        "fov": "partial",
        "binning": True,
        "scaled": False,
        "maxseconds": 10.2,
        "raw": False,
      },
      2: {
        "width": 2028,
        "height": 1520,
        "video": True,
        "image": False,
        "aspect": "4:3",
        "framerate": {"min": 0.1, "max": 50},
        "fov": "full",
        "binning": True,
        "scaled": False,
        "maxseconds": 10.2,
        "raw": True,
      },
      3: {
        "width": 4056,
        "height": 3040,
        "video": True,
        "image": True,
        "aspect": "4:3",
        "framerate": {"min": 0.005, "max": 10},
        "fov": "full",
        "binning": False,
        "scaled": False,
        "maxseconds": 200.0,
        "raw": False,
      },
      4: {
        "width": 1012,
        "height": 760,
        "video": True,
        "image": True,
        "aspect": "4:3",
        "framerate": {"min": 50.1, "max": 120},
        "fov": "full",
        "binning": False,
        "scaled": True,
        "maxseconds": 10.2,
        "raw": False,
      },
    }
  }
  SensorList = []  # List of declared sensors.

  def DenoiseStatus(self):
    """With libcamera the denoise / onchip cleanup is set via the command template rather than the parameter file."""
    if (
      self.Parameters.CameraDriver == "raspistill"
    ):  # These are the default commands for raspistill captures.
      result = (
        not self.Parameters.DisableCleanup
      )  # Onchip cleanup is ENABLED unless we can prove otherwise.
    else:
      result = True  # Denoise is ON unless explicitly turned off in the command line (checked next).
    try:
      elements = self.Parameters._CameraLightCommand.split(
        " "
      )  # Check all the options.
      for i, element in enumerate(elements):
        if (
          element == "--denoise"
        ):  # We've found a denoise instruction in the camera command template.
          if elements[i + 1] == "off":  # Onchip cleanup is disabled.
            result = False
          else:
            result = True
          break  # Look no further.
    except:
      self.Log(
        "AstroSensor.DenoiseStatus(): Command template is incomplete.",
        terminal=False,
      )
    return result

  def __init__(
    self,
    sensor_type="",
    pixel_width=4056,
    pixel_height=3040,
    max_seconds=200,
    min_seconds=0.0000001,
    logger=None,
    parameters=None,
    channel=None,
  ):
    """Create new instance of AstroSensor.

    sensor_type: Optional sensor type, can set some parameters automatically if recognised. eg imx477
    pixel_width: Image format - width.
    pixel_height: Image format - height.
    max_seconds: Longest exposure time supported by the sensor (seconds).
    min_seconds: Shortest exposure time supported by the sensor (seconds).
    logger: Point to logfile instance. eg MainLog or CamLog
    parameters: Point to parameter instance. eg Parameters
    driver: Use raspistill or libcamera support on the RPi?
    channel: Optional channel number if RPi5 with multiple cameras supported.

    """
    self.set_logger(
      logger
    )  # CamLog # Handle to the class that handles logging and error tracing.
    self.oscommand = OSCommand(logger=logger.Log)  # Create OS command executor.
    self.osCmd = self.oscommand.Execute
    self.CameraWindow = None
    self.ErrorWindow = None
    self.Parameters = parameters  # Must declare the parameter file before you can use the instance.
    self.PixelWidth = pixel_width
    self.PixelHeight = pixel_height
    self.MaxExposureSeconds = max_seconds
    self.MinExposureSeconds = min_seconds
    self.Type = sensor_type
    if (
      self.Type == "imx477"
    ):  # If the sensor type is recognised then set the value automatically.
      self.Log(
        "AstroSensor: Recognised "
        + self.Type
        + " setting other characteristics automatically.",
        terminal=False,
      )
      self.PixelWidth = 4056
      self.PixelHeight = 3040
      self.MaxExposureSeconds = 200  # 200 seconds is the longest exposure time that raspistill can deliver.
      self.MinExposureSeconds = 1e-6  # 1 microsecond is the fastest exposure time that raspistill can deliver.
    self.ID = (
      str(self.PixelWidth) + "|" + str(self.PixelHeight)
    )  # Unique ID of lens features.
    self.Mode = 3
    self.Channel = (
      channel  # If RPi has multiple camera channels, indicate the channel here.
    )
    self.OnChipCleanup = (
      self.DenoiseStatus()
    )  # Records whether we've got the on-chip cleanup enabled or not. Raspistill feature. Libcamera does it through the command line.
    if self.Type in AstroSensor.SensorDict:
      self.ModeDict = AstroSensor.SensorDict[
        self.Type
      ]  # Select mode information for the chosen sensor.
    else:
      self.ModeDict = AstroSensor.SensorDict[
        "imx477"
      ]  # Default sensor for the telescope design.
    self.Log(
      "AstroSensor: Size, " + str(self.PixelWidth) + "*" + str(self.PixelHeight),
      terminal=False,
    )
    AstroSensor.SensorList.append(
      self
    )  # Add this instance to the global list of all defined sensors.

  def set_logger(self, logger):
    """Set up link to logging class and shortcuts to common methods."""
    # The logging methods default to 'consumers' which will just silently eat any parameters passed.
    self.Logger = logger  # Logger instance.
    self.Log = self._NullLogger  # No log method.
    self.ReportException = (
      self._NullLogger
    )  # Cannot report exception details to logfile.
    self.RaiseException = self._NullLogger  # Cannor report and raise exception.
    if hasattr(logger, "Log"):
      self.Log = logger.Log  # Log method.
    if hasattr(logger, "ReportException"):
      self.ReportException = (
        logger.ReportException
      )  # Report exception details to logfile.
    if hasattr(logger, "RaiseException"):
      self.RaiseException = logger.RaiseException  # Report and raise exception.
    self.Log("AstroSensor.set_logger: Linked to this log file.", terminal=False)

  def _NullLogger(self, *args, **kwargs):
    """Null logger. Absorbs parameters and .log call but does nothing.
    Use this when there is no logger defined."""
    return

  def HmsFromStamp(self, timestamp, dateaware=False):
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
          dateaware and timestamp.date() != self.NowUTC().date()
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

  def NowHMS(self):
    """Return current time as formatted string.
    Returns HH:MM:SS string for the current time (UTC)"""
    return self.HmsFromStamp(self.NowUTC())

  def NowUTC(self):
    """Return system UTC timestamp as a datetime object."""
    return datetime.now(timezone.utc)

  def GetCentre(self):
    """Return the X and Y co-ordinates of the centre of the image."""
    return int(round(self.PixelWidth / 2, 0)), int(round(self.PixelHeight / 2, 0))

  def _SetMode(self, mode: int):
    """Given a new mode, validate it and then update the dependent values in the sensor.
    There are dependencies in AstroCamera that should be updated afterwards, so this
    should be called via astrocamera.SetMode(mode)."""
    if mode in self.ModeDict:
      self.PixelWidth = self.ModeDict[mode][
        "width"
      ]  # Update maximum image pixel width
      self.PixelHeight = self.ModeDict[mode][
        "height"
      ]  # Update maximum image pixel height
      self.Mode = mode
      self.MaxExposureSeconds = self.ModeDict[mode][
        "maxseconds"
      ]  # Update maximum exposure time.
      if self.ModeDict[mode]["image"] == False:
        self.Log(
          "AstroSensor._SetMode: Mode "
          + str(self.Mode)
          + ") is not recommended for still images.",
          level="warning",
        )
      if self.ModeDict[mode]["binning"] == True:
        self.Log(
          "AstroSensor._SetMode: Mode "
          + str(self.Mode)
          + ") activates binning for increased sensitivity.",
          level="info",
          terminal=False,
        )
      if self.ModeDict[mode]["raw"] == False:
        self.Log(
          "AstroSensor._SetMode: Mode "
          + str(self.Mode)
          + ") does not support RAW data correctly. Processing may fail.",
          level="error",
        )
    else:
      self.Log(
        "AstroSensor._SetMode: Mode "
        + str(mode)
        + " is not recognised, ignored.",
        level="warning",
      )
    self.Log(
      "AstroSensor._SetMode: Mode " + str(mode) + " selected.", terminal=False
    )
    if self.CameraWindow != None:
      self.CameraWindow.Print("Sensor mode: " + str(mode))
    self.Log(
      "AstroSensor: Pixel dimensions now: "
      + str(self.PixelWidth)
      + "x"
      + str(self.PixelHeight),
      terminal=False,
    )

  def DisableCleanup(self):
    """Disable the on-chip image cleanup for the sensor.
    Even in RAW capture mode, the sensor will perform some image cleanup by default.
    This cleanup degrades the raw data that astro photo stacking software will work with.
    Therefore it is advisable to disable this cleanup before taking photos for stacking.
    """
    if self.Parameters.CameraDriver == "raspistill":  # if OS_name in ['buster']:
      print(
        TextColor.yellow(
          "Disabling sensor cleanup to improve purity of sensor raw data."
        )
      )
      if not self.Type in [
        "imx477"
      ]:  # Check that the sensor cleanup function actually can be disabled.
        self.Log(
          "AstroSensor.DisableCleanup is not supported for "
          + self.Type
          + " sensors. Ignored.",
          level="warning",
        )
        return False
      cmd = (
        "sudo vcdbg set imx477.dpc 0"  # Turn off on-chip cleaning of the image.
      )
      # This raises some error messages like this...
      #    debug_sym: vc_mem_copy: Unable to open '/dev/fb0': No such file or directory.
      # According to raspberry pi forum, these can be ignored. The output is not displayed, however pilomar logs it in case other errors occur in the future.
      self.Log(cmd, terminal=False)
      self.osCmd(cmd)
      self.OnChipCleanup = (
        False  # raspistill feature. Libcamera does it through the command line.
      )
      self.Parameters.DisableCleanup = True  # Cleanup is disabled.
      self.Log(
        "Raspberry Pi High Quality Camera, on chip image cleanup DISABLED.",
        terminal=False,
      )
      if self.CameraWindow != None:
        self.CameraWindow.Print(self.NowHMS() + " On Chip Cleanup - OFF")
    else:  # libcamera has a command line option to disable cleanup.
      self.Log(
        "AstroSensor.DisableCleanup: Please check the '--denoise off ' option in the command templates in the parameter file.",
        terminal=False,
      )
    return True

  def EnableCleanup(self):
    """Enable the on-chip image cleanup for the sensor.
    This returns the on-chip image cleanup back to the default state (ON)
    It is recommended to have it disabled for image stacking of raw images."""
    if self.Parameters.CameraDriver == "raspistill":  # if OS_name in ['buster']:
      print(
        TextColor.yellow(
          "Enabling sensor cleanup to restore factory functionality."
        )
      )
      if not self.Type in ["imx477"]:
        self.Log(
          "AstroSensor.EnableCleanup is not supported for "
          + self.Type
          + " sensors. Ignored.",
          level="warning",
        )
        return False
      cmd = (
        "sudo vcdbg set imx477.dpc 3"  # Turn on on-chip cleaning of the image.
      )
      # This raises some error messages like this...
      #    debug_sym: vc_mem_copy: Unable to open '/dev/fb0': No such file or directory.
      # According to raspberry pi forum, these can be ignored. The output is logged but not displayed in case other errors occur in the future.
      self.Log(cmd, terminal=False)
      self.osCmd(cmd)
      self.OnChipCleanup = (
        True  # Raspistill feature, libcamera does it through the command line.
      )
      self.Parameters.DisableCleanup = False
      self.Log(
        "Raspberry Pi High Quality Camera, on chip image cleanup ENABLED.",
        terminal=False,
      )
      if self.CameraWindow != None:
        self.CameraWindow.Print(self.NowHMS() + " On Chip Cleanup - ON")
    else:  # libcamera has a command line option to disable cleanup.
      self.Log(
        "AstroSensor.EnableCleanup(): Please check the '--denoise off ' option is removed in the command templates in the parameter file.",
        terminal=False,
      )
    return True
