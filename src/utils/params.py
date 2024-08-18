

import json
import os

from camera.image import pilomarimage
from utils.textcolor import ListChooser, TextColor


class attributemaster:  # A parent class containing some common methods that other classes can inherit from.
  """General base class that other classes can be based upon.
  Provides useful methods that many classes may use."""

  def SetLogger(self, logger):
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
    # self.Log("attributemaster.SetLogger: Linked to this log file.",terminal=False)

  def _NullLogger(self, *args, **kwargs):
    """Null logger. Absorbs parameters and does nothing.
    Use this when there is no logger defined.
    It prevents logging messages causing failure if no logger is defined."""
    return

  def SaveAttributes(self, filename: str):
    """Pull parameter attribute values out of the object and store back into the parameter dictionary.
    Save the parameter dictionary back to disc.
    If the target file exists it will be overwritten by the 'mv' command."""
    tempfilename = filename.replace(
      ".json", ".tmp"
    )  # During creation, the file is given a temporary filename, so that any reading process doesn't pick it up too soon.
    tempdictionary = self.SaveToDictionary()  # Save to a working dictionary.
    with open(tempfilename, "w") as f:  # Dump as json to disc.
      json.dump(
        tempdictionary, f, indent=4, default=str
      )  # Save the updated dictionary back to disc.
    osCmd(
      "mv " + tempfilename + " " + filename
    )  # When the file is complete, rename it to its proper name.

  def SaveToDictionary(
    self, allowlist=None, denylist=None, initialdictionary={}, nameprefix=None
  ) -> dict:
    """Adds the ability to save attributes of the object to a dictionary.
    It ignores any attributes starting with '_' character.
    allowlist: If specified lists the fieldnames that should be saved. If missing, all fields are saved.
    denylist: If specified lists fieldnames that will NOT be saved, all others are.
    initialdictionary provides initial values that this method will append to.
    nameprefix provides an optional prefix to all the fieldnames.
    It will also ignore certain datatypes which don't save well or are typically very large (numpy arrays).
    """
    confdict = initialdictionary  # Start an empty dictionary.
    methodlist = [
      method for method in dir(self) if callable(getattr(self, method))
    ]  # Don't export callable attributes (= methods).
    for attr, value in vars(self).items():
      if attr[0] == "_":
        continue  # Don't send internals.
      if attr in methodlist:
        continue  # Don't list methods.
      if denylist != None and attr in denylist:
        continue  # Blocked item. Don't save.
      if allowlist is None or attr in allowlist:  # Allowed item, save.
        if nameprefix != None:
          attr = nameprefix + attr  # Add optional prefix to fieldname.
        confdict[attr] = value
    return confdict


# ------------------------------------------------------------------------------------------------------

# ///////////////////////////////////////////////////////////////////////////////////
# Parameter settings
# ///////////////////////////////////////////////////////////////////////////////////


class parameters(attributemaster):  # Common
  """Class to load, store and manage parameters for the program.
  The parameters() class allows you to load runtime parameters from a file.
  It can also reload parameters during a run if you want to change them without restarting the program.
  The latest parameter settings are automatically written back to disc when the program closes.
  - So if you change any of these parameters during the run, they will remain active the next time the program is started.
  These parameters are generally those which you may want to modify during development or testing.
  """

  def __init__(self, filename, logger=None):
    self.SetLogger(
      logger=logger
    )  # Inherited from attributemaster: Set up references to chosen logger (or disable if no logger defined).
    self._Dictionary = (
      {}
    )  # The json parameter file loaded from disc at start, saved to disc at end.
    self._Defaults = (
      {}
    )  # Maintain a list of default values, used to highlight changes when reviewing parameters.
    self.ParamFileName = filename  # The disc copy of the parameter file. This is overwritten if the program completes correctly.
    self.LoadParameters()
    self.RequireRestart = False  # These parameters are safe to consistently configure microcontroller and run observations.
    # Set to FALSE if they change and require a software restart.

  def LoadParameters(self):
    """If parameter file exists, it's loaded into the parameters.
    If anything is missing it's defaulted to initial values.
    Called during __init__(), and can be called again if needed."""
    if os.path.isfile(
      self.ParamFileName
    ):  # If the dictionary file exists, we'll import it now.
      with open(self.ParamFileName, "r") as f:
        self.Log("Loading parameters from file: " + self.ParamFileName)
        self._Dictionary = json.load(
          f
        )  # Overwrite the default parameter values with anything from file.
    # Pull parameter values from the dictionary, and update the dictionary with defaults if necessary.
    # - Define data about stepper motor driver boards and capabilities.
    sdd = {
      "drv8825": {
        "modelist": {
          "1": {"power": 100, "modesignals": "nnn"},
          "2": {"power": 70, "modesignals": "ynn"},
          "4": {"power": 40, "modesignals": "nyn"},
          "8": {"power": 20, "modesignals": "yyn"},
          "16": {"power": 10, "modesignals": "nny"},
          "32": {"power": 5, "modesignals": "yyy"},
        }
      }
    }
    self.StepperDriverData = self.GetParmVal(
      "StepperDriverData", sdd
    )  # Dictionary containing stepper driver types and parameters.
    self.BoardType = self.GetParmVal(
      "BoardType", None
    )  # Define alternative motorcontroller board type here. Changes behaviour of board/microcontroller.
    self.BatchSize = self.GetParmVal(
      "BatchSize", 100
    )  # How many photos to take in a batch.
    self.ControlBatchSize = self.GetParmVal(
      "ControlBatchSize", 20
    )  # How many images to capture in each 'control set' (DARK, BIAS etc). High values offer limited gains.
    self.ColorScheme = self.GetParmVal(
      "ColorScheme", "green"
    )  # What colour scheme to use? (green, blue, red, white)

    # The following parameters control hardware features.
    self.CameraEnabled = self.GetParmVal("CameraEnabled", True)  # Is the camera on?
    self.BacklashEnabled = self.GetParmVal(
      "BacklashEnabled", False
    )  # ENABLE to let the motors make extra moves to cope with gear backlash.
    self.FaultSensitive = self.GetParmVal(
      "FaultSensitive", False
    )  # ENABLE to make motorcontroller respect the DRV8825 'fault' signal.
    self.MctlLedStatus = self.GetParmVal(
      "MctlLedStatus", True
    )  # Turn on STATUS LEDs on microcontroller.
    self.ObservationResetsMctl = self.GetParmVal(
      "ObservationResetsMctl", False
    )  # Force a reset of the microcontroller each time a new ObservationRun begins?
    self.MctlResetPin = self.GetParmVal(
      "MctlResetPin", 4
    )  # Which RPi4 GPIO pin is used to RESET the microcontroller?
    self.StopPin = self.GetParmVal(
      "StopPin", 25
    )  # Which RPi4 GPIO pin is used as a STOP button?
    self.UartRxQueueLimit = self.GetParmVal(
      "UartRxQueueLimit", 50
    )  # How many messages can be held in the input queue from the Microcontroller? Kill older entries.
    # Azimuth motor parameters.
    self.MinAzimuthAngle = self.GetParmVal("MinAzimuthAngle", 0)
    self.MaxAzimuthAngle = min(self.GetParmVal("MaxAzimuthAngle", 360), 360)
    self.AzimuthDriver = self.GetParmVal(
      "AzimuthDriver", "drv8825"
    )  # Which steppermotor driver does the Azimuth motor use?
    self.AzimuthGearRatio = self.GetParmVal("AzimuthGearRatio", 240)
    self.AzimuthMotorStepsPerRev = self.GetParmVal(
      "AzimuthMotorStepsPerRev", 400
    )  # Full step count for the motor (ignore any microstepping multiplier)
    self.AzimuthSlewMicrostepRatio = self.GetParmVal(
      "AzimuthSlewMicrostepRatio", 1
    )  # 1 = Full steps, 2 = 1/2 steps, 4 = 1/4 steps.
    self.AzimuthMicrostepRatio = self.GetParmVal(
      "AzimuthMicrostepRatio", 1
    )  # 1 = Full steps, 2 = 1/2 steps, 4 = 1/4 steps.
    self.AzimuthRestAngle = self.GetParmVal("AzimuthRestAngle", 180.0)
    self.AzimuthBacklashAngle = self.GetParmVal("AzimuthBacklashAngle", 0.0)
    self.AzimuthOrientation = self.GetParmVal("AzimuthOrientation", -1)
    self.AzimuthLimitAngle = self.GetParmVal(
      "AzimuthLimitAngle", None
    )  # Set motion limit for rotation.
    # Altitude motor parameters.
    self.MinAltitudeAngle = self.GetParmVal(
      "MinAltitudeAngle", 0
    )  # Fixed Issue #38
    self.MaxAltitudeAngle = min(
      self.GetParmVal("MaxAltitudeAngle", 90), 90
    )  # Fixed Issue #38
    self.AltitudeDriver = self.GetParmVal(
      "AltitudeDriver", "drv8825"
    )  # Which steppermotor driver does the Altitude motor use?
    self.AltitudeGearRatio = self.GetParmVal("AltitudeGearRatio", 240)
    self.AltitudeMotorStepsPerRev = self.GetParmVal(
      "AltitudeMotorStepsPerRev", 400
    )  # Full step count for the motor (ignore any microstepping multiplier)
    self.AltitudeMicrostepRatio = self.GetParmVal(
      "AltitudeMicrostepRatio", 1
    )  # 1 = Full steps, 2 = 1/2 steps, 4 = 1/4 steps.
    self.AltitudeSlewMicrostepRatio = self.GetParmVal(
      "AltitudeSlewMicrostepRatio", 1
    )  # 1 = Full steps, 2 = 1/2 steps, 4 = 1/4 steps.
    self.AltitudeRestAngle = self.GetParmVal("AltitudeRestAngle", 0.0)
    self.AltitudeBacklashAngle = self.GetParmVal("AltitudeBacklashAngle", 0.0)
    self.AltitudeOrientation = self.GetParmVal("AltitudeOrientation", -1)
    self.AltitudeLimitAngle = self.GetParmVal(
      "AltitudeLimitAngle", None
    )  # Set motion limit for rotation.
    # Motor pulse speed and acceleration (applies to both motors)
    self.FastTime = self.GetParmVal(
      "FastTime", 0.001
    )  # Fastest pulse to the motor STEP signal. (Full speed in large move.)
    self.SlowTime = self.GetParmVal(
      "SlowTime", 0.05
    )  # Slowest pulse to the motor STEP signal. (Initial speed at start of move.)
    self.TimeDelta = self.GetParmVal(
      "TimeDelta", 0.003
    )  # Acceleration rate for the motor STEP signal.

    self.MotorStatusDelay = self.GetParmVal(
      "MotorStatusDelay", 10
    )  # Microcontroller should send motor status messages every 'xxx' seconds. (Don't overload UART comms!)
    self.SlewEnabled = self.GetParmVal(
      "SlewEnabled", False
    )  # Do we allow microstepping to be replaced by FULL STEPS when moving large distances?
    self.OptimiseMoves = self.GetParmVal(
      "OptimiseMoves", False
    )  # Can the motorcontroller optimise large moves? (ie switch direction if it's faster)
    self.MctlCommsTimeout = self.GetParmVal(
      "MctlCommsTimeout", 120
    )  # How many seconds of inactivity before resetting microcontroller communication?
    self.UseUSBStorage = self.GetParmVal(
      "UseUSBStorage", True
    )  # If USB storage is mounted then images are stored there instead of the SD card.
    self.SDPath = self.GetParmVal(
      "SDPath", "/"
    )  # The 'path' used by discmonitor for monitoring space on the SD card.
    self.USBPath = self.GetParmVal(
      "USBPath", "/media/pi"
    )  # The 'path' used by discmonitor for monitoring space on attached USB storage.
    self.FastFlush = self.GetParmVal(
      "FastFlush", False
    )  # When TRUE disc writes are flushed immediately - That hits the SD card hard, but may catch more info for fatal errors.
    self.FastImageCapture = self.GetParmVal(
      "FastImageCapture", False
    )  # Do not extract raw data during observation, do it later. Captures data more quickly.
    self.HorizonAltitude = self.GetParmVal(
      "HorizonAltitude", 0.0
    )  # What altitude angle is considered the horizon? Observations cannot go below this even if the motor allows it.
    self._Horizon = max(
      self.HorizonAltitude, self.MinAltitudeAngle
    )  # Targets will not be followed below this altitude.

    # The following parameters control how bright the stars are if they are selected in the LocalStars or ConstellationStars lists.
    self.LocalStarsMagnitude = self.GetParmVal(
      "LocalStarsMagnitude", 7.0
    )  # Max magnitude when selecting local stars.
    self.ConstellationStarsMagnitude = self.GetParmVal(
      "ConstellationStarsMagnitude", 7.0
    )  # Max magnitude when selecting stars in a constellation.

    # The following parameters decide which types of images are stored.
    self.CameraSaveJpg = self.GetParmVal(
      "CameraSaveJpg", True
    )  # Save the jpg image from observations, but will strip out the embedded RAW data.
    self.CameraSaveDng = self.GetParmVal(
      "CameraSaveDng", True
    )  # Save the raw image data as .dng file.
    self.CameraSaveFits = self.GetParmVal(
      "CameraSaveFits", False
    )  # Save the raw image data as a .fit file. # Needs libcamera & Picamera2.
    if self.CameraSaveJpg or self.CameraSaveDng or self.CameraSaveFits:
      pass  # OK
    else:
      self.Log(
        "No image types are saved according to the parameters.", level="warning"
      )

    cameracommands = {
      "raspistill": {  # These are the default commands for raspistill captures.
        "light": "raspistill -o {&output} -ex off -t 10 -n -q 100 -md {&mode} -w {&width} -h {&height} -ag 16.0 -ss {&shutter}",
        "dark": "raspistill -o {&output} -ex off -t 10 -n -q 100 -md {&mode} -w {&width} -h {&height} -ag 16.0 -ss {&shutter}",
        "bias": "raspistill -o {&output} -ex off -t 10 -n -q 100 -md {&mode} -w {&width} -h {&height} -ag 16.0 -ss {&shutter}",
        "flat": "raspistill -o {&output} -t 10 -n -q 100 -md {&mode} -w {&width} -h {&height} -ag 16.0",
        "darkflat": "raspistill -o {&output} -ex off -t 10 -n -q 100 -md {&mode} -w {&width} -h {&height} -ag 16.0 -ss {&shutter}",
        "auto": "raspistill -o {&output} -t 10 -n -q 100 -md {&mode} -w {&width} -h {&height}",
        "tracking": "raspistill -o {&output} -ex off -t 10 -n -q 100 -md {&mode} -w {&width} -h {&height} -ss {&shutter}",
        "imagetypes": ["jpg", "dng"],
        "osnames": ["buster"],
        "rawswitch": "-r",
      },
      "pilomarfits": {  # If picamera2 and astropy are installed you can get 'fits' images with pilomarfits.py
        "light": "python3 pilomarfits.py --output {&output} --quality 100 --width {&width} --height {&height} --shutter {&shutter} --tuning-file imx477_noir.json",
        "dark": "python3 pilomarfits.py --output {&output} --quality 100 --width {&width} --height {&height} --shutter {&shutter} --tuning-file imx477_noir.json",
        "bias": "python3 pilomarfits.py --output {&output} --quality 100 --width {&width} --height {&height} --shutter {&shutter} --tuning-file imx477_noir.json",
        "flat": "python3 pilomarfits.py --output {&output} --quality 100 --width {&width} --height {&height} --tuning-file imx477_noir.json",
        "darkflat": "python3 pilomarfits.py --output {&output} --quality 100 --width {&width} --height {&height} --shutter {&shutter} --tuning-file imx477_noir.json",
        "auto": "python3 pilomarfits.py --output {&output} --quality 100 --width {&width} --height {&height} --tuning-file imx477_noir.json",
        "tracking": "python3 pilomarfits.py --output {&output} --quality 100 --width {&width} --height {&height} --shutter {&shutter} --tuning-file imx477_noir.json",
        "imagetypes": ["jpg", "fits"],
        "osnames": ["bullseye", "bookworm"],
        "rawswitch": "--raw",
      },  # No raw image extraction switch needed.
      "libcamera": {  # These are the default Commands for libcamera-still captures.
        "light": "rpicam-still --output {&output} --timeout 1 --nopreview --quality 100 --width {&width} --height {&height} --denoise off --analoggain 16.0 --shutter {&shutter}",
        "dark": "rpicam-still --output {&output} --timeout 1 --nopreview --quality 100 --width {&width} --height {&height} --denoise off --analoggain 16.0 --shutter {&shutter}",
        "bias": "rpicam-still --output {&output} --timeout 1 --nopreview --quality 100 --width {&width} --height {&height} --denoise off --analoggain 16.0 --shutter {&shutter}",
        "flat": "rpicam-still --output {&output} --timeout 1 --nopreview --quality 100 --width {&width} --height {&height} --denoise off --analoggain 16.0",
        "darkflat": "rpicam-still --output {&output} --timeout 1 --nopreview --quality 100 --width {&width} --height {&height} --denoise off --analoggain 16.0 --shutter {&shutter}",
        "auto": "rpicam-still --output {&output} --timeout 1 --nopreview --quality 100 --width {&width} --height {&height} --denoise off",
        "tracking": "rpicam-still --output {&output} --timeout 1 --nopreview --quality 100 --width {&width} --height {&height} --denoise off --shutter {&shutter}",
        "imagetypes": ["jpg", "dng"],
        "osnames": ["bullseye", "bookworm"],
        "rawswitch": "--raw",
      },  # How do you turn on RAW image extraction?
    }
    self.CameraCommands = self.GetParmVal("CameraCommands", cameracommands)
    self.DisableCleanup = self.GetParmVal(
      "DisableCleanup", True
    )  # Set to TRUE to disable the on-chip cleanup. (More pure RAW image is captured.) # Applies to raspistill only!
    self.CameraDriver = self.GetParmVal(
      "CameraDriver", CameraDriver
    )  # Set outside the Parameters object.
    self.SetCameraDriver(
      self.CameraDriver
    )  # Load appropriate camera commands into working fields.

    # The following parameters control DriftTracking activity.
    self.UseTracking = self.GetParmVal(
      "UseTracking", True
    )  # TRUE = Use image tracking. FALSE = No tracking.
    # LatestTrackingFilter and RunFilterScript are new features being tested. If used, they override PrepImagesForTracking and TrackingUrbanFilter parameters.
    self.TrackingTargetGrayscale = self.GetParmVal(
      "TrackingTargetGrayscale", False
    )  # Generate grayscale tracking target?
    # The following 2 parameters are replaced by the general purpose LatestTrackingFilter parameter. This upgrades automatically.
    PrepImagesForTracking = self.GetParmVal(
      "PrepImagesForTracking", False
    )  # TRUE = latest image is simplified. FALSE = latest image is used as is.
    TrackingUrbanFilter = self.GetParmVal(
      "TrackingUrbanFilter", False
    )  # Apply the 'UrbanFilter' method to live images before passing to the drift tracking calculation.
    self.LatestTrackingFilter = self.GetParmVal(
      "LatestTrackingFilter", None
    )  # Which (if any) script is run through pilomarimage.RunFilterScript() when LATEST tracking images are taken.
    if (
      self.LatestTrackingFilter is None
    ):  # No LatestTrackingFilter is set. Look for old parameters to upgrade.
      if (
        PrepImagesForTracking
      ):  # The old PrepImagesForTracking was in use, convert this to the EnhanceStars filter script.
        self.LatestTrackingFilter = (
          "EnhanceStars"  # This is the equivalent to the previous behaviour.
        )
        self.Log(
          "parameters.__init__(): Upgrading old PrepImagesForTracking parameter to new LatestTrackingFilter parameter.",
          terminal=True,
        )
      elif (
        TrackingUrbanFilter
      ):  # The old TrackingUrbanFilter was in use, convert this to the UrbanFilter script.
        self.LatestTrackingFilter = "UrbanFilter"
        self.Log(
          "parameters.__init__(): Upgrading old TrackingUrbanFilter parameter to new LatestTrackingFilter parameter.",
          terminal=True,
        )
    self.TrackingPrediction = self.GetParmVal(
      "TrackingPrediction", False
    )  # Adjust tracking offsets by the elapsed time. Predicting a new offset.
    self.TrackingMatchThreshold = self.GetParmVal(
      "TrackingMatchThreshold", 5
    )  # Minimum number of stars that must be matched before drift calculation is trusted.
    self.MinimumDriftCorrection = self.GetParmVal(
      "MinimumDriftCorrection", 50
    )  # Minimum number of drift pixels that's worth compensating. Doesn't need to be too small.
    self.TrackingInterval = self.GetParmVal(
      "TrackingInterval", 600
    )  # How many seconds between each target tracking check?
    self.TrackingStarRadius = self.GetParmVal(
      "TrackingStarRadius", 3
    )  # Pixel radius of stars in clean targetting images.
    self.TrackingExposureSeconds = self.GetParmVal(
      "TrackingExposureSeconds", 5.0
    )  # How long is the exposure when capturing a tracking photo. It must be standardised rather than using the variable 'light' image exposure time.
    self.GeneratePreview = self.GetParmVal(
      "GeneratePreview", True
    )  # TRUE = Preview images are generated periodically, and can be turned into AVI file when observation ends.
    self.GenerateKeogram = self.GetParmVal(
      "GenerateKeogram", False
    )  # TRUE = Keogram is generated at the end of all observations automatically. Aurora always does.
    self.InitialGoTo = self.GetParmVal(
      "InitialGoTo", True
    )  # Perform initial GOTO before downloading the trajectory. (Eases comms with microcontroller.)
    self.TargetInclusionRadius = self.GetParmVal(
      "TargetInclusionRadius", 15
    )  # Angle (radius) for inclusion of neighbouring stars when generating target image.
    self.TargetMinMagnitude = self.GetParmVal(
      "TargetMinMagnitude", 7.0
    )  # Minimum magnitude for stars to display. At a 2 second exposure, Magnitude 5.0 is a good value, at 5 seconds, Mag 9, over 10 seconds, Mag 10 is about as good as it gets.
    self.UseLiveLocation = self.GetParmVal(
      "UseLiveLocation", True
    )  # Use live target location rather than last reported location for image processing.
    self.DebugMode = self.GetParmVal(
      "DebugMode", True
    )  # In DebugMode ObservationRun does not display the status windows. This makes error messages easier to read.
    self.KeyboardScanDelay = self.GetParmVal(
      "KeyboardScanDelay", 2
    )  # How many seconds between keyboard scans when running an observation?
    self.SessionHistoryLimit = self.GetParmVal(
      "SessionHistoryLimit", 30
    )  # How many recent session targets are kept in history?

    # Warn if magnitude limits are incorrectly set.
    if self.TargetMinMagnitude > self.LocalStarsMagnitude:
      self.Log(
        "parameters.__init__(): TargetMinMagnitude",
        self.TargetMinMagnitude,
        "is dimmer than stars listed in Hipparcos catalog (",
        self.LocalStarsMagnitude,
        ").",
        level="warning",
        terminal=True,
      )

    # The following parameters set position and localisation.
    self.LocalTZ = self.GetParmVal(
      "LocalTZ", "Europe/London"
    )  # What's the local timezone (pytz values). pytz.all_timezones() lists all available. Info only at present.
    self.HomeLat = self.GetParmVal("HomeLat", None)  # Latitude of the observer.
    self.HomeLon = self.GetParmVal("HomeLon", None)  # Longitude of the observer.
    self._HomeLatVal = 0.0
    if self.HomeLat != None:
      self._HomeLatVal = float(
        self.HomeLat.split(" ")[0]
      )  # Convert to float value.
      if self.HomeLat.split(" ")[1] == "S":
        self._HomeLatVal = (
          self._HomeLatVal * -1
        )  # -ve for southern hemisphere in Skyfield.
    self._HomeLonVal = 0.0
    if self.HomeLon != None:
      self._HomeLonVal = float(
        self.HomeLon.split(" ")[0]
      )  # Convert to float value.
      if self.HomeLon.split(" ")[1] == "W":
        self._HomeLonVal = (
          self._HomeLonVal * -1
        )  # -ve for western hemisphere in Skyfield.
    self.Log(
      "Parameters: Home:",
      self.HomeLat,
      self.HomeLon,
      ":",
      self._HomeLatVal,
      self._HomeLonVal,
      terminal=False,
    )

    # The following parameters dictate how various graphical images are generated.
    self.MarkupInterval = self.GetParmVal(
      "MarkupInterval", 300
    )  # How often do we generate a preview image (seconds).
    self.MarkupShowLabels = self.GetParmVal(
      "MarkupShowLabels", True
    )  # Add labels to markup images, such as locations.
    self.MarkupShowNames = self.GetParmVal(
      "MarkupShowNames", True
    )  # Add names to markup images, such as star names.
    self.MarkupStarLabelLimit = self.GetParmVal(
      "MarkupStarLabelLimit", 100
    )  # Maximum number of star labels to add to the image. Keep it readable.
    self.MarkupAvoidCollisions = self.GetParmVal(
      "MarkupAvoidCollisions", False
    )  # Does image markup avoid text overlaps?
    self.FakeStars = self.GetParmVal(
      "FakeStars", True
    )  # Do simulated images includes stars, nebulae etc?
    self.FakeNoise = self.GetParmVal(
      "FakeNoise", False
    )  # Do simulated images also simulate sensor noise?
    self.FakeField = self.GetParmVal(
      "FakeField", False
    )  # Do simulated images also simulate electronic field noise?
    self.FakePollution = self.GetParmVal(
      "FakePollution", False
    )  # Do simulated images also simulate light pollution?
    self.FakeAurora = self.GetParmVal(
      "FakeAurora", True
    )  # Does simulated aurora target actually fake an aurora?
    self.FakeMeteor = self.GetParmVal(
      "FakeMeteor", True
    )  # Do simulated images also fake meteor streaks?
    self.FakeMeteorPercent = self.GetParmVal(
      "FakeMeteorPercent", 2
    )  # What percentage of images get fake meteor streaks?

    # The following parameters describe the camera and lens.
    self.LensLength = self.GetParmVal("LensLength", 16.0)  # Focal length of lens
    self.LensHorizontalFov = self.GetParmVal(
      "LensHorizontalFov", 21.8
    )  # Degrees FoV horizontally
    self.LensVerticalFov = self.GetParmVal(
      "LensVerticalFov", 16.4
    )  # Degrees FoV vertically.
    self.SensorType = self.GetParmVal("SensorType", "imx477")  # Sensor type.
    self.IRFilter = self.GetParmVal("IRFilter", True)  # Is Infrared filter fitted?
    self.PollutionFilter = self.GetParmVal(
      "PollutionFilter", False
    )  # Is light pollution filter fitted?

    # The following parameters dictate how the trajectory is calculated for the motorcontroller.
    self.TrajectoryWindow = self.GetParmVal(
      "TrajectoryWindow", 1200
    )  # How many seconds into the future should the motor trajectory last?
    self.UseDynamicTrajectoryPeriods = self.GetParmVal(
      "UseDynamicTrajectoryPeriods", True
    )  # Can we use flexible time periods in the trajectory plan?

    # The following parameters dictate the color scheme for the user interface.
    # Display colorscheme.
    self.MenuTitleFG = self.GetParmVal("MenuTitleFG", TextColor.LIME)
    self.MenuTitleBG = self.GetParmVal("MenuTitleBG", TextColor.DARKGREEN)
    self.MenuSubtitleFG = self.GetParmVal("MenuSubtitleFG", TextColor.BLACK)
    self.MenuSubtitleBG = self.GetParmVal("MenuSubtitleBG", TextColor.GREEN)
    # - ObservationStatusWindow
    self.TitleFG = self.GetParmVal("TitleFG", TextColor.LIME)
    self.TitleBG = self.GetParmVal("TitleBG", TextColor.DARKGREEN)
    self.TextFG = self.GetParmVal("TextFG", TextColor.GREEN)
    self.TextBG = self.GetParmVal("TextBG", TextColor.BLACK)
    self.TextGood = self.GetParmVal("TextGood", TextColor.LIGHTGREEN)
    self.TextPoor = self.GetParmVal("TextPoor", TextColor.YELLOW)
    self.TextBad = self.GetParmVal("TextBad", TextColor.ORANGERED1)
    self.BorderFG = self.GetParmVal("BorderFG", TextColor.DARKGREEN)
    self.BorderBG = self.GetParmVal("BorderBG", TextColor.BLACK)
    self.SetColorScheme(self.ColorScheme)

    self.ScanForMeteors = self.GetParmVal(
      "ScanForMeteors", True
    )  # Scan light images for streaks, report them if found.
    self.MinSatelliteAltitude = self.GetParmVal(
      "MinSatelliteAltitude", 30
    )  # Satellite's are only considered to RISE if they will culminate above this altitude. (Else too brief and low to see)
    self.AuroraCameraAltitude = self.GetParmVal(
      "AuroraCameraAltitude", 5
    )  # When selecting an AURORA target this is the altitude for the camera position.
    # Load/Save image filters for pilomarimage objects.
    self.FilterScripts = self.GetParmVal(
      "FilterScripts", pilomarimage.FILTERSCRIPTS
    )  # Default is the initial set of filter scripts defined in the pilomarimage class.
    pilomarimage.FILTERSCRIPTS = (
      self.FilterScripts
    )  # Now assign whatever we have loaded back to pilomarimage.

  def SetCameraDriver(self, cameradriver):
    """This will set cameradriver (raspistill,libcamera,pilomarfits) then
    load the correct camera commands from the Parameters table."""
    if cameradriver in self.CameraCommands:  # CameraDriver is recognised.
      self.CameraDriver = cameradriver  # Select the camera driver.
      self.CameraImageTypes = self.CameraCommands[self.CameraDriver]["imagetypes"]
      self._CameraLightCommand = self.CameraCommands[self.CameraDriver][
        "light"
      ]  # Camera settings for 'light' images.
      self._CameraDarkCommand = self.CameraCommands[self.CameraDriver][
        "dark"
      ]  # Camera settings for 'dark' images.
      self._CameraBiasCommand = self.CameraCommands[self.CameraDriver][
        "bias"
      ]  # Camera settings for 'bias' images.
      self._CameraFlatCommand = self.CameraCommands[self.CameraDriver][
        "flat"
      ]  # Camera settings for 'flat' images.
      self._CameraDarkFlatCommand = self.CameraCommands[self.CameraDriver][
        "darkflat"
      ]  # Camera settings for 'darkflat' images.
      self._CameraAutoCommand = self.CameraCommands[self.CameraDriver][
        "auto"
      ]  # Camera settings for 'auto' images.
      self._CameraTrackingCommand = self.CameraCommands[self.CameraDriver][
        "tracking"
      ]  # Camera settings for 'tracking' images.
      self._CameraRawSwitch = self.CameraCommands[self.CameraDriver][
        "rawswitch"
      ]  # How do you turn on RAW image extraction?
    else:
      MainLog.Log(
        "**ERROR**: parameters.SetCameraDriver: Does not recognise:",
        cameradriver,
        level="error",
        terminal=True,
      )
      exit()

  def GetParmVal(self, name, default, oldnames=None):
    """Get a value from the parameter file.

    name: The parameter name.
    default: The default parameter value if it is not in the dictionary yet.
    oldnames: optional list of previous parameter names, these are used to migrate values from old parameter names to new ones.

    If the value does not exist, create it with the default value.
    If the value is different to the default value, report that in the log file."""
    self._Defaults[name] = (
      default  # Maintain a list of default values, used to highlight changes when reviewing parameters.
    )
    result = default
    if type(oldnames) == list:  # Check for earlier parameter values.
      for oldname in oldnames:  # Check each name in turn.
        if (
          oldname in self._Dictionary
        ):  # oldname exists in the dictionary (can migrate from oldname to new name).
          result = self._Dictionary[
            oldname
          ]  # Retrieve the value from the oldname entry.
          self.Log(
            "parameters.GetParmVal(",
            name,
            ") migrating from",
            oldname,
            "with value",
            result,
            terminal=False,
          )
          break  # Look no further.
    # Now get/initialise the current parameter name.
    result = self._Dictionary.get(name, result)
    if result != default:  # Default value has been overridden.
      self.Log(
        "parameters.GetParmVal(",
        name,
        ") default",
        default,
        "overridden with",
        result,
        terminal=False,
      )
    return result

  def ChooseColorScheme(self):
    """Prompt for and set a standard color scheme."""
    ItemList = ["white", "blue", "green", "red"]
    objectchooser = ListChooser(
      ItemList, compress=False
    )  # Always show the full list.
    print(TextColor.yellow("Choose color scheme to apply."))
    ChosenItem = objectchooser.prompt()
    if ChosenItem is None:
      return  # Nothing to change.
    else:
      self.SetColorScheme(ChosenItem)
    self.ShowColorScheme()  # Show the current color scheme.
    print(
      TextColor.yellow(
        "Please restart the program for these changes to take effect."
      )
    )
    return

  def ChooseColor(self):
    """Prompt for color and update display characteristics to match."""
    # Prompt for color item to change.
    ItemList = [
      "MenuTitleFG",
      "MenuTitleBG",
      "MenuSubtitleFG",
      "MenuSubtitleBG",
      "TitleFG",
      "TitleBG",
      "TextFG",
      "TextBG",
      "TextGood",
      "TextPoor",
      "TextBad",
      "BorderFG",
      "BorderBG",
    ]
    objectchooser = ListChooser(
      ItemList, compress=False
    )  # Always show the full list.
    print(TextColor.yellow("Choose color item to change."))
    ChosenItem = objectchooser.prompt()
    if ChosenItem is None:
      return  # Nothing to change.
    print(TextColor.yellow("Chosen", ChosenItem))
    print(TextColor.yellow("Available colors:-"))
    TextColor.listcolors()
    Result = None
    while Result is None:
      Result = input(TextColor.cyan("Color (0-255), x to quit, ? for list: "))
      if Result.lower() == "x":
        Result = None
        break  # Quit
      if Result == "?":
        TextColor.listcolors()
        continue  # Try again
      if IsInt(Result):
        i = int(Result)
        if i < 0 or i > 255:  # Out of range.
          print(TextColor.red("Must be in the range 0 - 255"))
          Result = None
          continue  # Try again.
        # Good value, assign it.
        print("Setting", ChosenItem, Result)
        setattr(
          self, ChosenItem, Result
        )  # Dynamically set the value in the parameter class.
        self.ColorScheme = "custom"
        print(
          "Example choice on white: ",
          TextColor.fgbgcolor(
            Result, TextColor.WHITE, " Lorem ipsum dolor sit amet "
          ),
        )
        print(
          "Example choice on black: ",
          TextColor.fgbgcolor(
            Result, TextColor.BLACK, " Lorem ipsum dolor sit amet "
          ),
        )
        print(
          "Example white on choice: ",
          TextColor.fgbgcolor(
            TextColor.WHITE, Result, " Lorem ipsum dolor sit amet "
          ),
        )
        print(
          "Example black on choice: ",
          TextColor.fgbgcolor(
            TextColor.BLACK, Result, " Lorem ipsum dolor sit amet "
          ),
        )
      else:
        Result = None
        continue  # Try again
    self.ShowColorScheme()  # Show the current color scheme.
    TextColor.text_box(
      "You must restart the program for these changes to take effect.",
      fg=TextColor.YELLOW,
      bg=TextColor.BLACK,
    )
    return

  def SetColorScheme(self, scheme="green"):
    if scheme == "white":  # Chosen schemes.
      self.MenuTitleFG = TextColor.GREY66
      self.MenuTitleBG = TextColor.GREY11
      self.MenuSubtitleFG = TextColor.GREY66
      self.MenuSubtitleBG = TextColor.GREY7
      self.TitleFG = TextColor.GREY66
      self.TitleBG = TextColor.GREY11
      self.TextFG = TextColor.WHITE
      self.TextBG = TextColor.BLACK
      self.TextGood = TextColor.WHITE
      self.TextPoor = TextColor.YELLOW
      self.TextBad = TextColor.RED
      self.BorderFG = TextColor.GREY66
      self.BorderBG = TextColor.BLACK
    elif scheme == "blue":  # Chosen schemes.
      self.MenuTitleFG = TextColor.WHITE
      self.MenuTitleBG = TextColor.DEEPSKYBLUE4A
      self.MenuSubtitleFG = TextColor.BLACK
      self.MenuSubtitleBG = TextColor.DEEPSKYBLUE3
      self.TitleFG = TextColor.WHITE
      self.TitleBG = TextColor.DEEPSKYBLUE4A
      self.TextFG = TextColor.CYAN
      self.TextBG = TextColor.GREY15
      self.TextGood = TextColor.LIGHTSKYBLUE1
      self.TextPoor = TextColor.YELLOW
      self.TextBad = TextColor.ORANGERED1
      self.BorderFG = TextColor.NAVYBLUE
      self.BorderBG = TextColor.GREY15
    elif scheme == "green":  # Chosen schemes.
      self.MenuTitleFG = TextColor.LIME
      self.MenuTitleBG = TextColor.DARKGREEN
      self.MenuSubtitleFG = TextColor.BLACK
      self.MenuSubtitleBG = TextColor.GREEN
      self.TitleFG = TextColor.LIME
      self.TitleBG = TextColor.DARKGREEN
      self.TextFG = TextColor.GREEN
      self.TextBG = TextColor.GREY15
      self.TextGood = TextColor.LIGHTGREEN
      self.TextPoor = TextColor.YELLOW
      self.TextBad = TextColor.ORANGERED1
      self.BorderFG = TextColor.DARKGREEN
      self.BorderBG = TextColor.GREY15
    elif scheme == "red":  # Chosen schemes.
      self.MenuTitleFG = TextColor.WHITE
      self.MenuTitleBG = TextColor.DARKRED
      self.MenuSubtitleFG = TextColor.BLACK
      self.MenuSubtitleBG = TextColor.RED3
      self.TitleFG = TextColor.WHITE
      self.TitleBG = TextColor.RED3
      self.TextFG = TextColor.RED
      self.TextBG = TextColor.GREY15
      self.TextGood = TextColor.LIGHTPINK1
      self.TextPoor = TextColor.YELLOW
      self.TextBad = TextColor.ORANGERED1
      self.BorderFG = TextColor.DARKRED
      self.BorderBG = TextColor.GREY15
    else:
      return  # Assume custom settings, don't override them.
    self.ColorScheme = scheme
    return

  def ShowColorScheme(self):
    """Demonstrate current color scheme."""
    print(TextColor.yellow("Current color scheme (" + str(self.ColorScheme) + "):"))
    print(
      TextColor.fgbgcolor(self.MenuTitleFG, self.MenuTitleBG, " Menu title    "),
      self.MenuTitleFG,
      "/",
      self.MenuTitleBG,
    )
    print(
      TextColor.fgbgcolor(
        self.MenuSubtitleFG, self.MenuSubtitleBG, " Menu subtitle "
      ),
      self.MenuSubtitleFG,
      "/",
      self.MenuSubtitleBG,
    )
    print(
      TextColor.fgbgcolor(self.TitleFG, self.TitleBG, " Title         "),
      self.TitleFG,
      "/",
      self.TitleBG,
    )
    print(
      TextColor.fgbgcolor(self.TextFG, self.TextBG, " Text          "),
      self.TextFG,
      "/",
      self.TextBG,
    )
    print(
      TextColor.fgbgcolor(self.TextGood, self.TextBG, " Good value    "),
      self.TextGood,
      "/",
      self.TextBG,
    )
    print(
      TextColor.fgbgcolor(self.TextPoor, self.TextBG, " Poor value    "),
      self.TextPoor,
      "/",
      self.TextBG,
    )
    print(
      TextColor.fgbgcolor(self.TextBad, self.TextBG, " Bad value     "),
      self.TextBad,
      "/",
      self.TextBG,
    )
    print(
      TextColor.fgbgcolor(self.BorderFG, self.BorderBG, " Border        "),
      self.BorderFG,
      "/",
      self.BorderBG,
    )
    return

  def Show(self):
    """List parameters."""
    print(TextColor.yellow("List parameters", ProgramTitle, VERSION, ":"))
    print(TextColor.red("(*)"), "indicates a modified parameter value.")
    tempd = vars(self)  # Load instance variables into a temporary dictionary.
    ignorelist = [
      method for method in dir(self) if callable(getattr(self, method))
    ]  # Don't export callable attributes (= methods).
    ignorelist.append("Logger")  # Ignore the Logger attribute too.
    for key, value in tempd.items():
      if key.startswith("_"):
        continue  # Ignore internals.
      if key in ignorelist:
        continue  # Ignore the link to the Log instance.
      defaultflag = ""  # Mark if the value is not the default.
      if type(value) == dict:  # Don't show dictionaries, they can be large.
        if key in self._Defaults:  # A default value is known.
          if (
            self._Defaults[key] != value
          ):  # The default is different to the current value.
            defaultflag = TextColor.red(" (*) Has changed from default.")
        print(
          TextColor.yellow(key.rjust(30))
          + " : "
          + TextColor.yellow(
            "dictionary " + defaultflag + "(for detail open in editor)"
          )
        )
      else:
        if key in self._Defaults:  # A default value is known.
          if (
            self._Defaults[key] != value
          ):  # The default is different to the current value.
            defaultflag = TextColor.red(
              " (*) Was " + str(self._Defaults[key])
            )
        print(
          TextColor.yellow(key.rjust(30)) + " : " + str(value) + defaultflag
        )
    input(TextColor.cyan("Press [enter] to continue:"))
