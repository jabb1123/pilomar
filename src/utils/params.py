"""This module contains the Parameters class which is used to load, store and manage parameters for the program."""

import json
import os

from camera.image import PilomarImage
from utils.logfile import LogFile
from utils.math_func import is_int
from utils.text.display import ColorDisplay
from utils.text.textcolor import ListChooser, TextColor


class AttributeMaster:  # A parent class containing some common methods that other classes can inherit from.
    """General base class that other classes can be based upon.
    Provides useful methods that many classes may use."""

    def __init__(self):
        self.logger: LogFile = None  # Logger instance.
        self.log = self._null_logger  # No log method.
        # Cannot report exception details to logfile.
        self.report__exception = self._null_logger
        self.raise_exception = self._null_logger  # Cannor report and raise exception.

        self.menu_title_fg = TextColor.WHITE
        self.menu_title_bg = TextColor.DARKRED
        self.menu_subtitle_fg = TextColor.BLACK
        self.menu_subtitle_bg = TextColor.RED3
        self.title_fg = TextColor.WHITE
        self.title_bg = TextColor.RED3
        self.text_fg = TextColor.RED
        self.text_bg = TextColor.GREY15
        self.text_good = TextColor.LIGHTPINK1
        self.text_poor = TextColor.YELLOW
        self.text_bad = TextColor.ORANGERED1
        self.border_fg = TextColor.DARKRED
        self.border_bg = TextColor.GREY15
        self.color_scheme = "white"

    def set_logger(self, logger: LogFile):
        """Set up link to logging class and shortcuts to common methods."""
        # The logging methods default to 'consumers' which will just silently eat any parameters passed.
        self.logger: LogFile = logger  # Logger instance.
        self.log = self._null_logger  # No log method.
        # Cannot report exception details to logfile.
        self.report__exception = self._null_logger
        self.raise_exception = self._null_logger  # Cannor report and raise exception.
        if hasattr(logger, "Log"):
            self.log = logger.Log  # Log method.
        if hasattr(logger, "ReportException"):
            # Report exception details to logfile.
            self.report__exception = logger.report_exception
        if hasattr(logger, "RaiseException"):
            self.raise_exception = logger.raise_exception  # Report and raise exception.
        # self.log("attributemaster.SetLogger: Linked to this log file.",terminal=False)

    def _null_logger(self, *args, **kwargs):
        """Null logger. Absorbs parameters and does nothing.
        Use this when there is no logger defined.
        It prevents logging messages causing failure if no logger is defined."""
        return

    def save_attributes(self, filename: str):
        """Pull parameter attribute values out of the object and store back into the parameter dictionary.
        Save the parameter dictionary back to disc.
        If the target file exists it will be overwritten by the 'mv' command."""
        # During creation, the file is given a temporary filename, so that any reading process doesn't pick it up too soon.
        tempfilename = filename.replace(".json", ".tmp")
        tempdictionary = self.save_to_dictionary()  # Save to a working dictionary.
        with open(tempfilename, "w") as f:  # Dump as json to disc.
            # Save the updated dictionary back to disc.
            json.dump(tempdictionary, f, indent=4, default=str)
        # When the file is complete, rename it to its proper name.
        osCmd("mv " + tempfilename + " " + filename)

    def save_to_dictionary(
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
        # Don't export callable attributes (= methods).
        methodlist = [method for method in dir(self) if callable(getattr(self, method))]
        for attr, value in vars(self).items():
            if attr[0] == "_":
                continue  # Don't send internals.
            if attr in methodlist:
                continue  # Don't list methods.
            if denylist is not None and attr in denylist:
                continue  # Blocked item. Don't save.
            if allowlist is None or attr in allowlist:  # Allowed item, save.
                if nameprefix is not None:
                    attr = nameprefix + attr  # Add optional prefix to fieldname.
                confdict[attr] = value
        return confdict

    def set_color_scheme(self, scheme="green"):
        """Set the color scheme for the display."""
        if scheme == "white":  # Chosen schemes.
            self.menu_title_fg = TextColor.GREY66
            self.menu_title_bg = TextColor.GREY11
            self.menu_subtitle_fg = TextColor.GREY66
            self.menu_subtitle_bg = TextColor.GREY7
            self.title_fg = TextColor.GREY66
            self.title_bg = TextColor.GREY11
            self.text_fg = TextColor.WHITE
            self.text_bg = TextColor.BLACK
            self.text_good = TextColor.WHITE
            self.text_poor = TextColor.YELLOW
            self.text_bad = TextColor.RED
            self.border_fg = TextColor.GREY66
            self.border_bg = TextColor.BLACK
        elif scheme == "blue":  # Chosen schemes.
            self.menu_title_fg = TextColor.WHITE
            self.menu_title_bg = TextColor.DEEPSKYBLUE4A
            self.menu_subtitle_fg = TextColor.BLACK
            self.menu_subtitle_bg = TextColor.DEEPSKYBLUE3
            self.title_fg = TextColor.WHITE
            self.title_bg = TextColor.DEEPSKYBLUE4A
            self.text_fg = TextColor.CYAN
            self.text_bg = TextColor.GREY15
            self.text_good = TextColor.LIGHTSKYBLUE1
            self.text_poor = TextColor.YELLOW
            self.text_bad = TextColor.ORANGERED1
            self.border_fg = TextColor.NAVYBLUE
            self.border_bg = TextColor.GREY15
        elif scheme == "green":  # Chosen schemes.
            self.menu_title_fg = TextColor.LIME
            self.menu_title_bg = TextColor.DARKGREEN
            self.menu_subtitle_fg = TextColor.BLACK
            self.menu_subtitle_bg = TextColor.GREEN
            self.title_fg = TextColor.LIME
            self.title_bg = TextColor.DARKGREEN
            self.text_fg = TextColor.GREEN
            self.text_bg = TextColor.GREY15
            self.text_good = TextColor.LIGHTGREEN
            self.text_poor = TextColor.YELLOW
            self.text_bad = TextColor.ORANGERED1
            self.border_fg = TextColor.DARKGREEN
            self.border_bg = TextColor.GREY15
        elif scheme == "red":  # Chosen schemes.
            self.menu_title_fg = TextColor.WHITE
            self.menu_title_bg = TextColor.DARKRED
            self.menu_subtitle_fg = TextColor.BLACK
            self.menu_subtitle_bg = TextColor.RED3
            self.title_fg = TextColor.WHITE
            self.title_bg = TextColor.RED3
            self.text_fg = TextColor.RED
            self.text_bg = TextColor.GREY15
            self.text_good = TextColor.LIGHTPINK1
            self.text_poor = TextColor.YELLOW
            self.text_bad = TextColor.ORANGERED1
            self.border_fg = TextColor.DARKRED
            self.border_bg = TextColor.GREY15
        else:
            return  # Assume custom settings, don't override them.
        self.color_scheme = scheme
        return


# ------------------------------------------------------------------------------------------------------

# ///////////////////////////////////////////////////////////////////////////////////
# Parameter settings
# ///////////////////////////////////////////////////////////////////////////////////


class Parameters(AttributeMaster):  # Common
    """Class to load, store and manage parameters for the program.
    The parameters() class allows you to load runtime parameters from a file.
    It can also reload parameters during a run if you want to change them without restarting the program.
    The latest parameter settings are automatically written back to disc when the program closes.
    - So if you change any of these parameters during the run, they will remain active the next time the program is started.
    These parameters are generally those which you may want to modify during development or testing.
    """

    def __init__(
        self,
        filename,
        logger=None,
        dev_window: ColorDisplay = None,
        error_window: ColorDisplay = None,
        camera_window: ColorDisplay = None,
        drift_window: ColorDisplay = None,
        session_window: ColorDisplay = None,
    ):
        super().__init__()
        self.set_logger(
            logger=logger
        )  # Inherited from attributemaster: Set up references to chosen logger (or disable if no logger defined).
        self._dictionary = (
            {}
        )  # The json parameter file loaded from disc at start, saved to disc at end.
        self._defaults = (
            {}
        )  # Maintain a list of default values, used to highlight changes when reviewing parameters.
        self.dev_window: ColorDisplay = dev_window
        self.error_window: ColorDisplay = error_window
        self.camera_window: ColorDisplay = camera_window
        self.drift_window: ColorDisplay = drift_window
        self.session_window: ColorDisplay = session_window
        self.param_filename = filename  # The disc copy of the parameter file. This is overwritten if the program completes correctly.
        self.load_parameters()
        self.require_restart = False  # These parameters are safe to consistently configure microcontroller and run observations.
        # Set to FALSE if they change and require a software restart.

    def load_parameters(self):
        """If parameter file exists, it's loaded into the parameters.
        If anything is missing it's defaulted to initial values.
        Called during __init__(), and can be called again if needed."""
        if os.path.isfile(
            self.param_filename
        ):  # If the dictionary file exists, we'll import it now.
            with open(self.param_filename, "r", encoding="utf-8") as f:
                self.log("Loading parameters from file: " + self.param_filename)
                self._dictionary = json.load(
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
        self.stepper_driver_data = self.get_parm_val(
            "StepperDriverData", sdd
        )  # Dictionary containing stepper driver types and parameters.
        self.board_type = self.get_parm_val(
            "BoardType", None
        )  # Define alternative motorcontroller board type here. Changes behaviour of board/microcontroller.
        self.batch_size = self.get_parm_val(
            "BatchSize", 100
        )  # How many photos to take in a batch.
        self.control_batch_size = self.get_parm_val(
            "ControlBatchSize", 20
        )  # How many images to capture in each 'control set' (DARK, BIAS etc). High values offer limited gains.
        self.color_scheme = self.get_parm_val(
            "ColorScheme", "green"
        )  # What colour scheme to use? (green, blue, red, white)

        # The following parameters control hardware features.
        self.camera_enabled = self.get_parm_val(
            "CameraEnabled", True
        )  # Is the camera on?
        self.backlash_enabled = self.get_parm_val(
            "BacklashEnabled", False
        )  # ENABLE to let the motors make extra moves to cope with gear backlash.
        self.fault_sensitive = self.get_parm_val(
            "FaultSensitive", False
        )  # ENABLE to make motorcontroller respect the DRV8825 'fault' signal.
        self.mctl_led_status = self.get_parm_val(
            "MctlLedStatus", True
        )  # Turn on STATUS LEDs on microcontroller.
        self.observation_resets_mctl = self.get_parm_val(
            "ObservationResetsMctl", False
        )  # Force a reset of the microcontroller each time a new ObservationRun begins?
        self.mctl_reset_pin = self.get_parm_val(
            "MctlResetPin", 4
        )  # Which RPi4 GPIO pin is used to RESET the microcontroller?
        self.stop_pin = self.get_parm_val(
            "StopPin", 25
        )  # Which RPi4 GPIO pin is used as a STOP button?
        self.uart_rx_queue_limit = self.get_parm_val(
            "UartRxQueueLimit", 50
        )  # How many messages can be held in the input queue from the Microcontroller? Kill older entries.
        # Azimuth motor parameters.
        self.min_azimuth_angle = self.get_parm_val("MinAzimuthAngle", 0)
        self.max_azimuth_angle = min(self.get_parm_val("MaxAzimuthAngle", 360), 360)
        self.azimuth_driver = self.get_parm_val(
            "AzimuthDriver", "drv8825"
        )  # Which steppermotor driver does the Azimuth motor use?
        self.azimuth_gear_ratio = self.get_parm_val("AzimuthGearRatio", 240)
        self.azimuth_motor_steps_per_rev = self.get_parm_val(
            "AzimuthMotorStepsPerRev", 400
        )  # Full step count for the motor (ignore any microstepping multiplier)
        self.azimuth_slew_microstep_ratio = self.get_parm_val(
            "AzimuthSlewMicrostepRatio", 1
        )  # 1 = Full steps, 2 = 1/2 steps, 4 = 1/4 steps.
        self.azimuth_microstep_ratio = self.get_parm_val(
            "AzimuthMicrostepRatio", 1
        )  # 1 = Full steps, 2 = 1/2 steps, 4 = 1/4 steps.
        self.azimuth_rest_angle = self.get_parm_val("AzimuthRestAngle", 180.0)
        self.azimuth_backlash_angle = self.get_parm_val("AzimuthBacklashAngle", 0.0)
        self.azimuth_orientation = self.get_parm_val("AzimuthOrientation", -1)
        self.azimuth_limit_angle = self.get_parm_val(
            "AzimuthLimitAngle", None
        )  # Set motion limit for rotation.
        # Altitude motor parameters.
        self.min_altitude_angle = self.get_parm_val(
            "MinAltitudeAngle", 0
        )  # Fixed Issue #38
        self.max_altitude_angle = min(
            self.get_parm_val("MaxAltitudeAngle", 90), 90
        )  # Fixed Issue #38
        self.altitude_driver = self.get_parm_val(
            "AltitudeDriver", "drv8825"
        )  # Which steppermotor driver does the Altitude motor use?
        self.altitude_gear_ratio = self.get_parm_val("AltitudeGearRatio", 240)
        self.altitude_motor_steps_per_rev = self.get_parm_val(
            "AltitudeMotorStepsPerRev", 400
        )  # Full step count for the motor (ignore any microstepping multiplier)
        self.altitude_microstep_ratio = self.get_parm_val(
            "AltitudeMicrostepRatio", 1
        )  # 1 = Full steps, 2 = 1/2 steps, 4 = 1/4 steps.
        self.altitude_slew_microstep_ratio = self.get_parm_val(
            "AltitudeSlewMicrostepRatio", 1
        )  # 1 = Full steps, 2 = 1/2 steps, 4 = 1/4 steps.
        self.altitude_rest_angle = self.get_parm_val("AltitudeRestAngle", 0.0)
        self.altitude_backlash_angle = self.get_parm_val("AltitudeBacklashAngle", 0.0)
        self.altitude_orientation = self.get_parm_val("AltitudeOrientation", -1)
        self.altitude_limit_angle = self.get_parm_val(
            "AltitudeLimitAngle", None
        )  # Set motion limit for rotation.
        # Motor pulse speed and acceleration (applies to both motors)
        self.fast_time = self.get_parm_val(
            "FastTime", 0.001
        )  # Fastest pulse to the motor STEP signal. (Full speed in large move.)
        self.slow_time = self.get_parm_val(
            "SlowTime", 0.05
        )  # Slowest pulse to the motor STEP signal. (Initial speed at start of move.)
        self.time_delta = self.get_parm_val(
            "TimeDelta", 0.003
        )  # Acceleration rate for the motor STEP signal.

        self.motor_status_delay = self.get_parm_val(
            "MotorStatusDelay", 10
        )  # Microcontroller should send motor status messages every 'xxx' seconds. (Don't overload UART comms!)
        self.slew_enabled = self.get_parm_val(
            "SlewEnabled", False
        )  # Do we allow microstepping to be replaced by FULL STEPS when moving large distances?
        self.optimise_moves = self.get_parm_val(
            "OptimiseMoves", False
        )  # Can the motorcontroller optimise large moves? (ie switch direction if it's faster)
        self.mctl_comms_timeout = self.get_parm_val(
            "MctlCommsTimeout", 120
        )  # How many seconds of inactivity before resetting microcontroller communication?
        self.use_usb_storage = self.get_parm_val(
            "UseUSBStorage", True
        )  # If USB storage is mounted then images are stored there instead of the SD card.
        self.sd_path = self.get_parm_val(
            "SDPath", "/"
        )  # The 'path' used by discmonitor for monitoring space on the SD card.
        self.usb_path = self.get_parm_val(
            "USBPath", "/media/pi"
        )  # The 'path' used by discmonitor for monitoring space on attached USB storage.
        self.fast_flush = self.get_parm_val(
            "FastFlush", False
        )  # When TRUE disc writes are flushed immediately - That hits the SD card hard, but may catch more info for fatal errors.
        self.fast_image_capture = self.get_parm_val(
            "FastImageCapture", False
        )  # Do not extract raw data during observation, do it later. Captures data more quickly.
        self.horizon_altitude = self.get_parm_val(
            "HorizonAltitude", 0.0
        )  # What altitude angle is considered the horizon? Observations cannot go below this even if the motor allows it.
        self._horizon = max(
            self.horizon_altitude, self.min_altitude_angle
        )  # Targets will not be followed below this altitude.

        # The following parameters control how bright the stars are if they are selected in the LocalStars or ConstellationStars lists.
        self.local_stars_magnitude = self.get_parm_val(
            "LocalStarsMagnitude", 7.0
        )  # Max magnitude when selecting local stars.
        self.constellation_stars_magnitude = self.get_parm_val(
            "ConstellationStarsMagnitude", 7.0
        )  # Max magnitude when selecting stars in a constellation.

        # The following parameters decide which types of images are stored.
        # Save the jpg image from observations, but will strip out the embedded RAW data.
        self.camera_save_jpg = self.get_parm_val("CameraSaveJpg", True)
        # Save the raw image data as .dng file.
        self.camera_save_dng = self.get_parm_val("CameraSaveDng", True)
        # Save the raw image data as a .fit file. # Needs libcamera & Picamera2.
        self.camera_save_fits = self.get_parm_val("CameraSaveFits", False)
        if self.camera_save_jpg or self.camera_save_dng or self.camera_save_fits:
            pass  # OK
        else:
            self.log(
                "No image types are saved according to the parameters.", level="warning"
            )

        # pylint: disable=line-too-long
        camera_commands = {
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
        # pylint: enable=line-too-long
        self.camera_commands = self.get_parm_val("CameraCommands", camera_commands)
        # Set to TRUE to disable the on-chip cleanup. (More pure RAW image is captured.)
        # Applies to raspistill only!
        self.disable_cleanup = self.get_parm_val("DisableCleanup", True)
        self.camera_driver = self.get_parm_val(
            "camera_driver", camera_driver
        )  # Set outside the Parameters object.
        self.set_camera_driver(
            self.camera_driver
        )  # Load appropriate camera commands into working fields.

        # The following parameters control DriftTracking activity.
        self.use_tracking = self.get_parm_val(
            "UseTracking", True
        )  # TRUE = Use image tracking. FALSE = No tracking.
        # LatestTrackingFilter and RunFilterScript are new features being tested.
        # If used, they override PrepImagesForTracking and TrackingUrbanFilter parameters.
        self.tracking_target_grayscale = self.get_parm_val(
            "TrackingTargetGrayscale", False
        )  # Generate grayscale tracking target?
        # The following 2 parameters are replaced by the general purpose LatestTrackingFilter parameter.
        # This upgrades automatically.
        prep_images_for_tracking = self.get_parm_val(
            "PrepImagesForTracking", False
        )  # TRUE = latest image is simplified. FALSE = latest image is used as is.
        tracking_urban_filter = self.get_parm_val(
            "TrackingUrbanFilter", False
        )  # Apply the 'UrbanFilter' method to live images before passing to the drift tracking calculation.
        self.latest_tracking_filter = self.get_parm_val(
            "LatestTrackingFilter", None
        )  # Which (if any) script is run through pilomarimage.RunFilterScript() when LATEST tracking images are taken.
        if (
            self.latest_tracking_filter is None
        ):  # No LatestTrackingFilter is set. Look for old parameters to upgrade.
            if (
                prep_images_for_tracking
            ):  # The old PrepImagesForTracking was in use, convert this to the EnhanceStars filter script.
                self.latest_tracking_filter = (
                    "EnhanceStars"  # This is the equivalent to the previous behaviour.
                )
                self.log(
                    "parameters.__init__(): Upgrading old PrepImagesForTracking parameter to new LatestTrackingFilter parameter.",
                    terminal=True,
                )
            elif (
                tracking_urban_filter
            ):  # The old TrackingUrbanFilter was in use, convert this to the UrbanFilter script.
                self.latest_tracking_filter = "UrbanFilter"
                self.log(
                    "parameters.__init__(): Upgrading old TrackingUrbanFilter parameter to new LatestTrackingFilter parameter.",
                    terminal=True,
                )
        self.tracking_prediction = self.get_parm_val(
            "TrackingPrediction", False
        )  # Adjust tracking offsets by the elapsed time. Predicting a new offset.
        self.tracking_match_threshold = self.get_parm_val(
            "TrackingMatchThreshold", 5
        )  # Minimum number of stars that must be matched before drift calculation is trusted.
        self.minimum_drift_correction = self.get_parm_val(
            "MinimumDriftCorrection", 50
        )  # Minimum number of drift pixels that's worth compensating. Doesn't need to be too small.
        self.tracking_interval = self.get_parm_val(
            "TrackingInterval", 600
        )  # How many seconds between each target tracking check?
        self.tracking_star_radius = self.get_parm_val(
            "TrackingStarRadius", 3
        )  # Pixel radius of stars in clean targetting images.
        self.tracking_exposure_seconds = self.get_parm_val(
            "TrackingExposureSeconds", 5.0
        )  # How long is the exposure when capturing a tracking photo. It must be standardised rather than using the variable 'light' image exposure time.
        self.generate_preview = self.get_parm_val(
            "GeneratePreview", True
        )  # TRUE = Preview images are generated periodically, and can be turned into AVI file when observation ends.
        self.generate_keogram = self.get_parm_val(
            "GenerateKeogram", False
        )  # TRUE = Keogram is generated at the end of all observations automatically. Aurora always does.
        self.initial_go_to = self.get_parm_val(
            "InitialGoTo", True
        )  # Perform initial GOTO before downloading the trajectory. (Eases comms with microcontroller.)
        self.target_inclusion_radius = self.get_parm_val(
            "TargetInclusionRadius", 15
        )  # Angle (radius) for inclusion of neighbouring stars when generating target image.
        self.target_min_magnitude = self.get_parm_val(
            "TargetMinMagnitude", 7.0
        )  # Minimum magnitude for stars to display. At a 2 second exposure, Magnitude 5.0 is a good value, at 5 seconds, Mag 9, over 10 seconds, Mag 10 is about as good as it gets.
        self.use_live_location = self.get_parm_val(
            "UseLiveLocation", True
        )  # Use live target location rather than last reported location for image processing.
        self.debug_mode = self.get_parm_val(
            "DebugMode", True
        )  # In DebugMode ObservationRun does not display the status windows. This makes error messages easier to read.
        self.keyboard_scan_delay = self.get_parm_val(
            "KeyboardScanDelay", 2
        )  # How many seconds between keyboard scans when running an observation?
        self.session_history_limit = self.get_parm_val(
            "SessionHistoryLimit", 30
        )  # How many recent session targets are kept in history?

        # Warn if magnitude limits are incorrectly set.
        if self.target_min_magnitude > self.local_stars_magnitude:
            self.log(
                "parameters.__init__(): TargetMinMagnitude",
                self.target_min_magnitude,
                "is dimmer than stars listed in Hipparcos catalog (",
                self.local_stars_magnitude,
                ").",
                level="warning",
                terminal=True,
            )

        # The following parameters set position and localisation.
        self.local_tz = self.get_parm_val(
            "LocalTZ", "Europe/London"
        )  # What's the local timezone (pytz values). pytz.all_timezones() lists all available. Info only at present.
        self.home_lat = self.get_parm_val("HomeLat", None)  # Latitude of the observer.
        self.home_lon = self.get_parm_val("HomeLon", None)  # Longitude of the observer.
        self._home_lat_val = 0.0
        if self.home_lat is not None:
            self._home_lat_val = float(
                self.home_lat.split(" ")[0]
            )  # Convert to float value.
            if self.home_lat.split(" ")[1] == "S":
                self._home_lat_val = (
                    self._home_lat_val * -1
                )  # -ve for southern hemisphere in Skyfield.
        self._home_lon_val = 0.0
        if self.home_lon is not None:
            self._home_lon_val = float(
                self.home_lon.split(" ")[0]
            )  # Convert to float value.
            if self.home_lon.split(" ")[1] == "W":
                self._home_lon_val = (
                    self._home_lon_val * -1
                )  # -ve for western hemisphere in Skyfield.
        self.log(
            "Parameters: Home:",
            self.home_lat,
            self.home_lon,
            ":",
            self._home_lat_val,
            self._home_lon_val,
            terminal=False,
        )

        # The following parameters dictate how various graphical images are generated.
        self.markup_interval = self.get_parm_val(
            "MarkupInterval", 300
        )  # How often do we generate a preview image (seconds).
        self.markup_show_labels = self.get_parm_val(
            "MarkupShowLabels", True
        )  # Add labels to markup images, such as locations.
        self.markup_show_names = self.get_parm_val(
            "MarkupShowNames", True
        )  # Add names to markup images, such as star names.
        self.markup_star_label_limit = self.get_parm_val(
            "MarkupStarLabelLimit", 100
        )  # Maximum number of star labels to add to the image. Keep it readable.
        self.markup_avoid_collisions = self.get_parm_val(
            "MarkupAvoidCollisions", False
        )  # Does image markup avoid text overlaps?
        self.fake_stars = self.get_parm_val(
            "FakeStars", True
        )  # Do simulated images includes stars, nebulae etc?
        self.fake_noise = self.get_parm_val(
            "FakeNoise", False
        )  # Do simulated images also simulate sensor noise?
        self.fake_field = self.get_parm_val(
            "FakeField", False
        )  # Do simulated images also simulate electronic field noise?
        self.fake_pollution = self.get_parm_val(
            "FakePollution", False
        )  # Do simulated images also simulate light pollution?
        self.fake_aurora = self.get_parm_val(
            "FakeAurora", True
        )  # Does simulated aurora target actually fake an aurora?
        self.fake_meteor = self.get_parm_val(
            "FakeMeteor", True
        )  # Do simulated images also fake meteor streaks?
        self.fake_meteor_percent = self.get_parm_val(
            "FakeMeteorPercent", 2
        )  # What percentage of images get fake meteor streaks?

        # The following parameters describe the camera and lens.
        self.lens_length = self.get_parm_val("LensLength", 16.0)  # Focal length of lens
        self.lens_horizontal_fov = self.get_parm_val(
            "LensHorizontalFov", 21.8
        )  # Degrees FoV horizontally
        self.lens_vertical_fov = self.get_parm_val(
            "LensVerticalFov", 16.4
        )  # Degrees FoV vertically.
        self.sensor_type = self.get_parm_val("SensorType", "imx477")  # Sensor type.
        self.ir_filter = self.get_parm_val(
            "IRFilter", True
        )  # Is Infrared filter fitted?
        self.pollution_filter = self.get_parm_val(
            "PollutionFilter", False
        )  # Is light pollution filter fitted?

        # The following parameters dictate how the trajectory is calculated for the motorcontroller.
        self.trajectory_window = self.get_parm_val(
            "TrajectoryWindow", 1200
        )  # How many seconds into the future should the motor trajectory last?
        self.use_dynamic_trajectory_periods = self.get_parm_val(
            "UseDynamicTrajectoryPeriods", True
        )  # Can we use flexible time periods in the trajectory plan?

        # The following parameters dictate the color scheme for the user interface.
        # Display colorscheme.
        self.menu_title_fg = self.get_parm_val("MenuTitleFG", TextColor.LIME)
        self.menu_title_bg = self.get_parm_val("MenuTitleBG", TextColor.DARKGREEN)
        self.menu_subtitle_fg = self.get_parm_val("MenuSubtitleFG", TextColor.BLACK)
        self.menu_subtitle_bg = self.get_parm_val("MenuSubtitleBG", TextColor.GREEN)
        # - ObservationStatusWindow
        self.title_fg = self.get_parm_val("TitleFG", TextColor.LIME)
        self.title_bg = self.get_parm_val("TitleBG", TextColor.DARKGREEN)
        self.text_fg = self.get_parm_val("TextFG", TextColor.GREEN)
        self.text_bg = self.get_parm_val("TextBG", TextColor.BLACK)
        self.text_good = self.get_parm_val("TextGood", TextColor.LIGHTGREEN)
        self.text_poor = self.get_parm_val("TextPoor", TextColor.YELLOW)
        self.text_bad = self.get_parm_val("TextBad", TextColor.ORANGERED1)
        self.border_fg = self.get_parm_val("BorderFG", TextColor.DARKGREEN)
        self.border_bg = self.get_parm_val("BorderBG", TextColor.BLACK)
        self.set_color_scheme(self.color_scheme)

        self.scan_for_meteors = self.get_parm_val(
            "ScanForMeteors", True
        )  # Scan light images for streaks, report them if found.
        self.min_satellite_altitude = self.get_parm_val(
            "MinSatelliteAltitude", 30
        )  # Satellite's are only considered to RISE if they will culminate above this altitude. (Else too brief and low to see)
        self.aurora_camera_altitude = self.get_parm_val(
            "AuroraCameraAltitude", 5
        )  # When selecting an AURORA target this is the altitude for the camera position.
        # Load/Save image filters for pilomarimage objects.
        self.filter_scripts = self.get_parm_val(
            "FilterScripts", PilomarImage.FILTERSCRIPTS
        )  # Default is the initial set of filter scripts defined in the pilomarimage class.
        PilomarImage.FILTERSCRIPTS = (
            self.filter_scripts
        )  # Now assign whatever we have loaded back to pilomarimage.

    def set_camera_driver(self, camera_driver):
        """This will set camera_driver (raspistill,libcamera,pilomarfits) then
        load the correct camera commands from the Parameters table."""
        if camera_driver in self.camera_commands:  # camera_driver is recognised.
            self.camera_driver = camera_driver  # Select the camera driver.
            self.camera_image_types = self.camera_commands[self.camera_driver][
                "imagetypes"
            ]
            # Camera settings for 'light' images.
            self._camera_light_command = self.camera_commands[self.camera_driver][
                "light"
            ]
            # Camera settings for 'dark' images.
            self._camera_dark_command = self.camera_commands[self.camera_driver]["dark"]
            # Camera settings for 'bias' images.
            self._camera_bias_command = self.camera_commands[self.camera_driver]["bias"]
            # Camera settings for 'flat' images.
            self._camera_flat_command = self.camera_commands[self.camera_driver]["flat"]
            # Camera settings for 'darkflat' images.
            self._camera_dark_flat_command = self.camera_commands[self.camera_driver][
                "darkflat"
            ]
            # Camera settings for 'auto' images.
            self._camera_auto_command = self.camera_commands[self.camera_driver]["auto"]
            # Camera settings for 'tracking' images.
            self._camera_tracking_command = self.camera_commands[self.camera_driver][
                "tracking"
            ]
            # How do you turn on RAW image extraction?
            self._camera_raw_switch = self.camera_commands[self.camera_driver][
                "rawswitch"
            ]
        else:
            self.logger.log(
                "**ERROR**: parameters.Setcamera_driver: Does not recognise:",
                self.camera_driver,
                level="error",
                terminal=True,
            )
            exit()

    def get_parm_val(self, name, default, oldnames=None):
        """Get a value from the parameter file.

        name: The parameter name.
        default: The default parameter value if it is not in the dictionary yet.
        oldnames: optional list of previous parameter names, these are used to migrate values from old parameter names to new ones.

        If the value does not exist, create it with the default value.
        If the value is different to the default value, report that in the log file."""
        # Maintain a list of default values, used to highlight changes when reviewing parameters.
        self._defaults[name] = default
        result = default
        if isinstance(oldnames, list):  # Check for earlier parameter values.
            for oldname in oldnames:  # Check each name in turn.
                # oldname exists in the dictionary (can migrate from oldname to new name).
                if oldname in self._dictionary:
                    # Retrieve the value from the oldname entry.
                    result = self._dictionary[oldname]
                    self.log(
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
        result = self._dictionary.get(name, result)
        if result != default:  # Default value has been overridden.
            self.log(
                "parameters.GetParmVal(",
                name,
                ") default",
                default,
                "overridden with",
                result,
                terminal=False,
            )
        return result

    def choose_color_scheme(self):
        """Prompt for and set a standard color scheme."""
        item_list = ["white", "blue", "green", "red"]
        # Always show the full list.
        objectchooser = ListChooser(item_list, compress=False)
        print(TextColor.yellow("Choose color scheme to apply."))
        chosen_item = objectchooser.prompt()
        if chosen_item is None:
            return  # Nothing to change.
        else:
            self.set_color_scheme(chosen_item)
        self.show_color_scheme()  # Show the current color scheme.
        print(
            TextColor.yellow(
                "Please restart the program for these changes to take effect."
            )
        )
        return

    def choose_color(self):
        """Prompt for color and update display characteristics to match."""
        # Prompt for color item to change.
        item_list = [
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
        # Always show the full list.
        objectchooser = ListChooser(item_list, compress=False)
        print(TextColor.yellow("Choose color item to change."))
        chosen_item = objectchooser.prompt()
        if chosen_item is None:
            return  # Nothing to change.
        print(TextColor.yellow("Chosen", chosen_item))
        print(TextColor.yellow("Available colors:-"))
        TextColor.listcolors()
        result = None
        while result is None:
            result = input(TextColor.cyan("Color (0-255), x to quit, ? for list: "))
            if result.lower() == "x":
                result = None
                break  # Quit
            if result == "?":
                TextColor.listcolors()
                continue  # Try again
            if is_int(result):
                i = int(result)
                if i < 0 or i > 255:  # Out of range.
                    print(TextColor.red("Must be in the range 0 - 255"))
                    result = None
                    continue  # Try again.
                # Good value, assign it.
                print("Setting", chosen_item, result)
                # Dynamically set the value in the parameter class.
                setattr(self, chosen_item, result)
                self.color_scheme = "custom"
                print(
                    "Example choice on white: ",
                    TextColor.fgbgcolor(
                        result, TextColor.WHITE, " Lorem ipsum dolor sit amet "
                    ),
                )
                print(
                    "Example choice on black: ",
                    TextColor.fgbgcolor(
                        result, TextColor.BLACK, " Lorem ipsum dolor sit amet "
                    ),
                )
                print(
                    "Example white on choice: ",
                    TextColor.fgbgcolor(
                        TextColor.WHITE, result, " Lorem ipsum dolor sit amet "
                    ),
                )
                print(
                    "Example black on choice: ",
                    TextColor.fgbgcolor(
                        TextColor.BLACK, result, " Lorem ipsum dolor sit amet "
                    ),
                )
            else:
                result = None
                continue  # Try again
        self.show_color_scheme()  # Show the current color scheme.
        TextColor.text_box(
            "You must restart the program for these changes to take effect.",
            fg=TextColor.YELLOW,
            bg=TextColor.BLACK,
        )
        return

    def show_color_scheme(self):
        """Demonstrate current color scheme."""
        print(
            TextColor.yellow("Current color scheme (" + str(self.color_scheme) + "):")
        )
        print(
            TextColor.fgbgcolor(
                self.menu_title_fg, self.menu_title_bg, " Menu title    "
            ),
            self.menu_title_fg,
            "/",
            self.menu_title_bg,
        )
        print(
            TextColor.fgbgcolor(
                self.menu_subtitle_fg, self.menu_subtitle_bg, " Menu subtitle "
            ),
            self.menu_subtitle_fg,
            "/",
            self.menu_subtitle_bg,
        )
        print(
            TextColor.fgbgcolor(self.title_fg, self.title_bg, " Title         "),
            self.title_fg,
            "/",
            self.title_bg,
        )
        print(
            TextColor.fgbgcolor(self.text_fg, self.text_bg, " Text          "),
            self.text_fg,
            "/",
            self.text_bg,
        )
        print(
            TextColor.fgbgcolor(self.text_good, self.text_bg, " Good value    "),
            self.text_good,
            "/",
            self.text_bg,
        )
        print(
            TextColor.fgbgcolor(self.text_poor, self.text_bg, " Poor value    "),
            self.text_poor,
            "/",
            self.text_bg,
        )
        print(
            TextColor.fgbgcolor(self.text_bad, self.text_bg, " Bad value     "),
            self.text_bad,
            "/",
            self.text_bg,
        )
        print(
            TextColor.fgbgcolor(self.border_fg, self.border_bg, " Border        "),
            self.border_fg,
            "/",
            self.border_bg,
        )
        return

    def show(self):
        """List parameters."""
        print(TextColor.yellow("List parameters", "", "", ":"))
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
            if isinstance(value, dict):  # Don't show dictionaries, they can be large.
                if key in self._defaults:  # A default value is known.
                    if (
                        self._defaults[key] != value
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
                if key in self._defaults:  # A default value is known.
                    if (
                        self._defaults[key] != value
                    ):  # The default is different to the current value.
                        defaultflag = TextColor.red(
                            " (*) Was " + str(self._defaults[key])
                        )
                print(
                    TextColor.yellow(key.rjust(30)) + " : " + str(value) + defaultflag
                )
        input(TextColor.cyan("Press [enter] to continue:"))
