from datetime import datetime, timezone
from oscommand import OSCommand
from utils.params import Parameters
from utils.text.textcolor import TextColor
from utils.time_funcs import now_hour_minute_sec


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

    def denoise_status(self):
        """With libcamera the denoise / onchip cleanup is set via the command template rather than the parameter file."""
        if (
            self.parameters.CameraDriver == "raspistill"
        ):  # These are the default commands for raspistill captures.
            result = (
                not self.parameters.disable_cleanup
            )  # Onchip cleanup is ENABLED unless we can prove otherwise.
        else:
            result = True  # Denoise is ON unless explicitly turned off in the command line (checked next).
        try:
            elements = self.parameters._camera_light_command.split(
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
            self.log(
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
        self.os_cmd = self.oscommand.execute
        self.camera_window = None
        self.error_window = None
        self.parameters: Parameters = (
            parameters  # Must declare the parameter file before you can use the instance.
        )
        self.pixel_width = pixel_width
        self.pixel_height = pixel_height
        self.max_exposure_seconds = max_seconds
        self.min_exposure_seconds = min_seconds
        self.type = sensor_type
        if (
            self.type == "imx477"
        ):  # If the sensor type is recognised then set the value automatically.
            self.log(
                "AstroSensor: Recognised "
                + self.type
                + " setting other characteristics automatically.",
                terminal=False,
            )
            self.pixel_width = 4056
            self.pixel_height = 3040
            self.max_exposure_seconds = 200  # 200 seconds is the longest exposure time that raspistill can deliver.
            self.min_exposure_seconds = 1e-6  # 1 microsecond is the fastest exposure time that raspistill can deliver.
        self.id = (
            str(self.pixel_width) + "|" + str(self.pixel_height)
        )  # Unique ID of lens features.
        self.mode = 3
        self.channel = (
            channel  # If RPi has multiple camera channels, indicate the channel here.
        )
        self.on_chip_cleanup = self.denoise_status()
        # Records whether we've got the on-chip cleanup enabled or not.
        # Raspistill feature. Libcamera does it through the command line.
        if self.type in AstroSensor.SensorDict:
            self.mode_dict = AstroSensor.SensorDict[
                self.type
            ]  # Select mode information for the chosen sensor.
        else:
            self.mode_dict = AstroSensor.SensorDict[
                "imx477"
            ]  # Default sensor for the telescope design.
        self.log(
            "AstroSensor: Size, "
            + str(self.pixel_width)
            + "*"
            + str(self.pixel_height),
            terminal=False,
        )
        AstroSensor.SensorList.append(
            self
        )  # Add this instance to the global list of all defined sensors.

    def set_logger(self, logger):
        """Set up link to logging class and shortcuts to common methods."""
        # The logging methods default to 'consumers' which will just silently eat any parameters passed.
        self.logger = logger  # Logger instance.
        self.log = self._null_logger  # No log method.
        self.report_exception = (
            self._null_logger
        )  # Cannot report exception details to logfile.
        self.raise_exception = self._null_logger  # Cannor report and raise exception.
        if hasattr(logger, "Log"):
            self.log = logger.Log  # Log method.
        if hasattr(logger, "report_exception"):
            self.report_exception = (
                logger.report_exception
            )  # Report exception details to logfile.
        if hasattr(logger, "raise_exception"):
            self.raise_exception = logger.raise_exception  # Report and raise exception.
        self.log("AstroSensor.set_logger: Linked to this log file.", terminal=False)

    def _null_logger(self, *args, **kwargs):
        """Null logger. Absorbs parameters and .log call but does nothing.
        Use this when there is no logger defined."""
        return

    def get_centre(self):
        """Return the X and Y co-ordinates of the centre of the image."""
        return int(round(self.pixel_width / 2, 0)), int(round(self.pixel_height / 2, 0))

    def _set_mode(self, mode: int):
        """Given a new mode, validate it and then update the dependent values in the sensor.
        There are dependencies in AstroCamera that should be updated afterwards, so this
        should be called via astrocamera.SetMode(mode)."""
        if mode in self.mode_dict:
            self.pixel_width = self.mode_dict[mode][
                "width"
            ]  # Update maximum image pixel width
            self.pixel_height = self.mode_dict[mode][
                "height"
            ]  # Update maximum image pixel height
            self.mode = mode
            self.max_exposure_seconds = self.mode_dict[mode][
                "maxseconds"
            ]  # Update maximum exposure time.
            if self.mode_dict[mode]["image"] is False:
                self.log(
                    "AstroSensor._set_mode: Mode "
                    + str(self.mode)
                    + ") is not recommended for still images.",
                    level="warning",
                )
            if self.mode_dict[mode]["binning"] is True:
                self.log(
                    "AstroSensor._set_mode: Mode "
                    + str(self.mode)
                    + ") activates binning for increased sensitivity.",
                    level="info",
                    terminal=False,
                )
            if self.mode_dict[mode]["raw"] is False:
                self.log(
                    "AstroSensor._set_mode: Mode "
                    + str(self.mode)
                    + ") does not support RAW data correctly. Processing may fail.",
                    level="error",
                )
        else:
            self.log(
                "AstroSensor._set_mode: Mode "
                + str(mode)
                + " is not recognised, ignored.",
                level="warning",
            )
        self.log(
            "AstroSensor._set_mode: Mode " + str(mode) + " selected.", terminal=False
        )
        if self.camera_window is not None:
            self.camera_window.Print("Sensor mode: " + str(mode))
        self.log(
            "AstroSensor: Pixel dimensions now: "
            + str(self.pixel_width)
            + "x"
            + str(self.pixel_height),
            terminal=False,
        )

    def disable_cleanup(self):
        """Disable the on-chip image cleanup for the sensor.
        Even in RAW capture mode, the sensor will perform some image cleanup by default.
        This cleanup degrades the raw data that astro photo stacking software will work with.
        Therefore it is advisable to disable this cleanup before taking photos for stacking.
        """
        if self.parameters.CameraDriver == "raspistill":  # if OS_name in ['buster']:
            print(
                TextColor.yellow(
                    "Disabling sensor cleanup to improve purity of sensor raw data."
                )
            )
            if self.type not in [
                "imx477"
            ]:  # Check that the sensor cleanup function actually can be disabled.
                self.log(
                    "AstroSensor.disable_cleanup is not supported for "
                    + self.type
                    + " sensors. Ignored.",
                    level="warning",
                )
                return False
            cmd = (
                "sudo vcdbg set imx477.dpc 0"  # Turn off on-chip cleaning of the image.
            )
            # This raises some error messages like this...
            #    debug_sym: vc_mem_copy: Unable to open '/dev/fb0': No such file or directory.
            # According to raspberry pi forum, these can be ignored.
            # The output is not displayed, however pilomar logs it in case other errors occur in the future.
            self.log(cmd, terminal=False)
            self.os_cmd(cmd)
            self.on_chip_cleanup = (
                False  # raspistill feature. Libcamera does it through the command line.
            )
            self.parameters.disable_cleanup = True  # Cleanup is disabled.
            self.log(
                "Raspberry Pi High Quality Camera, on chip image cleanup DISABLED.",
                terminal=False,
            )
            if self.camera_window is not None:
                self.camera_window.Print(
                    now_hour_minute_sec() + " On Chip Cleanup - OFF"
                )
        else:  # libcamera has a command line option to disable cleanup.
            self.log(
                "AstroSensor.disable_cleanup: Please check the '--denoise off ' option in the command templates in the parameter file.",
                terminal=False,
            )
        return True

    def enable_cleanup(self):
        """Enable the on-chip image cleanup for the sensor.
        This returns the on-chip image cleanup back to the default state (ON)
        It is recommended to have it disabled for image stacking of raw images."""
        if self.parameters.CameraDriver == "raspistill":  # if OS_name in ['buster']:
            print(
                TextColor.yellow(
                    "Enabling sensor cleanup to restore factory functionality."
                )
            )
            if self.type not in ["imx477"]:
                self.log(
                    "AstroSensor.enable_cleanup is not supported for "
                    + self.type
                    + " sensors. Ignored.",
                    level="warning",
                )
                return False
            cmd = (
                "sudo vcdbg set imx477.dpc 3"  # Turn on on-chip cleaning of the image.
            )
            # This raises some error messages like this...
            #    debug_sym: vc_mem_copy: Unable to open '/dev/fb0': No such file or directory.
            # According to raspberry pi forum, these can be ignored.
            # The output is logged but not displayed in case other errors occur in the future.
            self.log(cmd, terminal=False)
            self.os_cmd(cmd)
            self.on_chip_cleanup = (
                True  # Raspistill feature, libcamera does it through the command line.
            )
            self.parameters.disable_cleanup = False
            self.log(
                "Raspberry Pi High Quality Camera, on chip image cleanup ENABLED.",
                terminal=False,
            )
            if self.camera_window is not None:
                self.camera_window.Print(
                    now_hour_minute_sec() + " On Chip Cleanup - ON"
                )
        else:  # libcamera has a command line option to disable cleanup.
            self.log(
                "AstroSensor.enable_cleanup(): Please check the '--denoise off ' option is removed in the command templates in the parameter file.",
                terminal=False,
            )
        return True
