#!/usr/bin/python3
"""Camera module for Pilomar astronomical image capture and control.

This module provides classes for managing the camera assembly, including
the lens and sensor, as well as handling image capture, camera settings,
and integration with the rest of the telescope system.
"""

import glob  # file system.
import json
import math  # Math and trig functions.
import os  # OS Command execution.
import random

# Import required libraries
import time  # sleep functionality for pauses in execution.
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, List, Optional, Union  # random number generator.

import cv2  # openCV for image file handling.
import numpy as np

# Pilomar's configuration parameters
from pilomar.core.base import AttributeMaster
from pilomar.core.time_utils import now_hms  # Pilomar's keogram builder
from pilomar.core.time_utils import now_utc, utc_time_stamp
from pilomar.core.timer import ProgressTimer, Timer  # Pilomar's timer classes.
from pilomar.imaging.image import PilomarImage  # Pilomar's IMAGE BUFFER handler
from pilomar.imaging.keogram import PilomarKeogram

from pilomar.session.status import SessionStatus
from pilomar.ui.keyboard import KeyboardScanner
from pilomar.ui.text_color import TextColor
from pilomar.utils.os_command import OsCommand  # Pilomar's OS command executor.

if TYPE_CHECKING:
    from pilomar.config.parameters import Parameters
    from pilomar.core.logger import LogFile
    from pilomar.session.entry import SessionEntry

# from pidng.core import RPICAM2DNG # DNG data extraction from RPi camera RAW images.

try:
    # If picamera2 doesn't exist, don't worry, but the camera_util() class will not be available.
    from picamera2 import Picamera2, Preview
except ImportError:
    pass

# --------------------------------------------------------------------


def ask_yes_no(text, default=True, fg: Optional[int] = None, bg: int = 0):
    """Ask any question that needs a simple Y/N answer.
    Returns logical value ('yes' or 'true' returns True, 'no' or 'false' returns False)
    Returns default value if user just presses ENTER.
    Ignores 2nd and subsequent characters.
    Rejects all other input."""
    while True:  # Loop until a satisfactory answer is given.
        if fg is None:  # Use default color.
            # Ensure 1 character space between text and response cursor.
            temp = input(TextColor.cyan(text.strip() + " "))
        else:
            temp = input(TextColor.fgbgcolor(fg, bg, text.strip() + " "))
        if len(temp) == 0:
            result = default
            break
        elif temp.lower()[0] in ["n"]:  # FALSE and NO recognised.
            result = False
            break
        elif temp.lower()[0] in ["y"]:  # TRUE and YES recognised.
            result = True
            break
        print(TextColor.red("? " + str(temp) + " ?"))
        if default:
            print(TextColor.red("Please answer yes, no or [ENTER]=(YES)"))
        else:
            print(TextColor.red("Please answer yes, no or [ENTER]=(NO)"))
    return result


# --------------------------------------------------------------------


class AstroLens(AttributeMaster):
    """Object representing the LENS being used by the telescope.
    Contains some attributes which are used to convert between
    FIELD OF VIEW and PHOTO DIMENSIONS for example.
    """

    lens_list: list["AstroLens"] = []  # List of declared lenses.

    def __init__(
        self,
        length,
        horizontal_fov,
        vertical_fov,
        aperture=2.8,
        multiplier=5.6,
        logger: Union[LogFile, None] = None,
        parameters=None,
    ):
        super().__init__()
        if logger is not None:
            # CamLog # Handle to the class that handles logging and error tracing.
            self.set_logger(logger)

            self.os_command = OsCommand(
                logger=logger.log
            )  # Create OS command executor.
        else:
            self.os_command = OsCommand()  # Create OS command executor without logger.
        self.os_cmd = self.os_command.execute
        self.camera_window = None
        self.error_window = None
        self.parameters = (
            parameters  # Must define parameter file before using instance.
        )
        self.base_length = (
            length  # The length of the lense WITHOUT any multiplier effect.
        )
        self.length = length  # 'focal length' of the lens.
        self.equiv_multiplier = multiplier
        # EquivLength multiplier depends upon the sensor, 5.6 is for the IMX477
        # From https://www.seeedstudio.com/blog/2020/06/18/a-complete-guide-to-help-you-choose-lenses-for-your-raspberry-pi-high-quality-camera-m/
        # 35mm equivalent focal length (?) (AKA the Crop Factor for the sensor?
        self.equiv_length = self.length * self.equiv_multiplier
        self.fov_horizontal = horizontal_fov
        self.fov_vertical = vertical_fov
        # When calculating the FOV for a survey, use the smaller value.
        self.fov = min(self.fov_horizontal, self.fov_vertical)
        self.aperture = (
            aperture  # FStop of the lens. *Q* Multiplier will impact this too. Hmm...
        )
        self.log(
            f"AstroLens: Length: \n\t"
            f"{self.length} mm (equiv. {self.equiv_length} mm) \n\t"
            f"FoV: {self.fov_horizontal} deg * {self.fov_vertical} deg",
            terminal=False,
        )
        AstroLens.lens_list.append(
            self
        )  # Add this instance to the global list of all defined lenses.

    def estimate_fov(self, _length):
        """Given 35mm equivalent focal length,  this estimates the FoV
        for the lens on the Raspberry Pi Hi Quality sensor.
        This is just an estimation to get you started.
        The FoV can be finetuned by comparing the diameter of
        the moon's disc using AstroCamera.calibrate_foV function.
        """

        # Table entries.
        # [ 35mm focal length, horizontal FoV, vertical FoV ]
        # Table was found online on a couple of forums, there are online calculators too.
        fx_fov_table = [
            [10, 121.9, 100.4],
            [11, 117.1, 95.0],
            [12, 112.6, 90.0],
            [14, 104.3, 81.2],
            [15, 100.4, 77.3],
            [17, 93.3, 70.4],
            [18, 90.0, 67.4],
            [19, 86.9, 64.6],
            [20, 84.0, 61.9],
            [24, 73.7, 53.1],
            [28, 65.5, 46.4],
            [30, 61.9, 43.6],
            [35, 54.4, 37.8],
            [45, 43.6, 29.9],
            [50, 39.6, 27.0],
            [55, 36.2, 24.6],
            [60, 33.4, 22.6],
            [70, 28.8, 19.5],
            [75, 27.0, 18.2],
            [80, 25.3, 17.1],
            [85, 23.9, 16.1],
            [90, 22.6, 15.2],
            [100, 20.4, 13.7],
            [105, 19.5, 13.0],
            [120, 17.1, 11.4],
            [125, 16.4, 11.0],
            [135, 15.2, 10.2],
            [150, 13.7, 9.1],
            [170, 12.1, 8.1],
            [180, 11.4, 7.6],
            [200, 10.3, 6.9],
            [210, 9.8, 6.5],
            [300, 6.9, 4.6],
            [400, 5.2, 3.4],
            [500, 4.1, 2.7],
            [600, 3.4, 2.3],
            [800, 2.6, 1.7],
        ]

        # Search the table for surrounding entries.
        lower_entry = None
        upper_entry = None
        for entry in fx_fov_table:
            if entry[0] <= self.equiv_length:
                lower_entry = entry
            else:
                upper_entry = entry
                break

        if lower_entry is not None:  # We found a reasonable match.
            self.fov_horizontal = lower_entry[1]  # Start with this near match.
            self.fov_vertical = lower_entry[2]
            # See if we can improve it.
            if upper_entry is not None and self.equiv_length != lower_entry[0]:
                # Need to estimate a value between the two known entries.
                len_range = upper_entry[0] - lower_entry[0]
                hor_range = upper_entry[1] - lower_entry[1]
                ver_range = upper_entry[2] - lower_entry[2]
                prop = (self.equiv_length - lower_entry[0]) / len_range
                self.fov_horizontal = prop * hor_range + lower_entry[1]
                self.fov_vertical = prop * ver_range + lower_entry[2]

        self.log(
            "AstroLens.estimate_fov():",
            self.equiv_length,
            self.fov_horizontal,
            self.fov_vertical,
            terminal=False,
        )


# --------------------------------------------------------------------


class AstroSensor(AttributeMaster):
    """Object representing the IMAGE SENSOR being used by the telescope.
    Default values are for the V1 RPi High Quality Camera (Sony sensor)?
    Individual characteristics can be specified, or a specific sensor type can be given.
    Contains some attributes which are used to convert between FIELD OF VIEW
    and PHOTO DIMENSIONS for example.
    """

    # Can create a dictionary of sensor types and capabilities here.
    # width = image width in pixels.
    # height = image height in pixels.
    # video = Can take video in this mode.
    # image = Can take photo in this mode.
    # fov = full or partial field of view. partial means only the
    # centre of the sensor is used. full means the whole sensor is used.
    # maxseconds = Longest exposure time supported.
    # raw = Can capture raw bayer data.
    # (*Q* This may not be needed in the future if libcamera
    # can recognise the capabilities automatically.)
    sensor_dict = {
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
    sensor_list: list["AstroSensor"] = []  # List of declared sensors.

    def denoise_status(self):
        """With libcamera the denoise / onchip cleanup is set
        via the command template rather than the parameter file."""
        if (
            self.parameters.camera_driver == "raspistill"
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
        except Exception:  # pylint: disable=broad-except
            self.log(
                "AstroSensor.denoise_status(): Command template is incomplete.",
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
        logger: Union[LogFile, None] = None,
        parameters: Parameters = None,
        channel=None,
    ):
        """Create new instance of AstroSensor.

        sensor_type: Optional sensor type, can set some parameters
        automatically if recognised. eg imx477
        pixel_width: image format - width.
        pixel_height: image format - height.
        max_seconds: Longest exposure time supported by the sensor (seconds).
        min_seconds: Shortest exposure time supported by the sensor (seconds).
        logger: Point to logfile instance. eg MainLog or CamLog
        parameters: Point to parameter instance. eg Parameters
        driver: Use raspistill or libcamera support on the RPi?
        channel: Optional channel number if RPi5 with multiple cameras supported.

        """
        super().__init__()
        if logger is not None:
            self.set_logger(
                logger
            )  # CamLog # Handle to the class that handles logging and error tracing.
            self.os_command = OsCommand(
                logger=logger.log
            )  # Create OS command executor.
        else:
            self.os_command = OsCommand()  # Create OS command executor without logger.
        self.os_cmd = self.os_command.execute
        self.camera_window = None
        self.error_window = None
        # Must declare the parameter file before you can use the instance.
        self.parameters: Parameters = parameters
        self.pixel_width = pixel_width
        self.pixel_height = pixel_height
        self.max_exposure_seconds = max_seconds
        self.min_exposure_seconds = min_seconds
        self.sensor_type = sensor_type
        # If the sensor type is recognised then set the value automatically.
        if self.sensor_type == "imx477":
            self.log(
                f"AstroSensor: Recognised {self.sensor_type} setting other characteristics automatically.",
                terminal=False,
            )
            self.pixel_width = 4056
            self.pixel_height = 3040
            # 200 seconds is the longest exposure time that raspistill can deliver.
            self.max_exposure_seconds = 200
            # 1 microsecond is the fastest exposure time that raspistill can deliver.
            self.min_exposure_seconds = 1e-6
        # Unique ID of lens features.
        # self.ID = str(self.pixel_width) + "|" + str(self.pixel_height)
        self.mode = 3
        # If RPi has multiple camera channels, indicate the channel here.
        self.channel = channel
        # Records whether we've got the on-chip cleanup enabled or not.
        # Raspistill feature. Libcamera does it through the command line.
        self.on_chip_cleanup = self.denoise_status()
        if self.sensor_type in AstroSensor.sensor_dict:
            # Select mode information for the chosen sensor.
            self.mode_dict = AstroSensor.sensor_dict[self.sensor_type]
        else:
            # Default sensor for the telescope design.
            self.mode_dict = AstroSensor.sensor_dict["imx477"]
        self.log(
            f"AstroSensor: Size, {self.pixel_width}*{self.pixel_height}",
            terminal=False,
        )
        # Add this instance to the global list of all defined sensors.
        AstroSensor.sensor_list.append(self)

    def get_center(self):
        """Return the X and Y co-ordinates of the centre of the image."""
        return int(round(self.pixel_width / 2, 0)), int(round(self.pixel_height / 2, 0))

    def _set_mode(self, mode: int):
        """Given a new mode, validate it and then update the dependent values in the sensor.
        There are dependencies in AstroCamera that should be updated afterwards, so this
        should be called via AstroCamera.Setmode(mode)."""
        if mode in self.mode_dict:
            # Update maximum image pixel width
            self.pixel_width = self.mode_dict[mode]["width"]
            # Update maximum image pixel height
            self.pixel_height = self.mode_dict[mode]["height"]
            self.mode = mode
            # Update maximum exposure time.
            self.max_exposure_seconds = self.mode_dict[mode]["maxseconds"]
            if not self.mode_dict[mode]["image"]:
                self.log(
                    f"AstroSensor._set_mode: mode {self.mode} is not recommended for still images.",
                    level="warning",
                )
            if self.mode_dict[mode]["binning"]:
                self.log(
                    f"AstroSensor._set_mode: mode {self.mode} activates binning for increased sensitivity.",
                    level="info",
                    terminal=False,
                )
            if not self.mode_dict[mode]["raw"]:
                self.log(
                    f"AstroSensor._set_mode: mode {self.mode} does not support RAW data correctly. Processing may fail.",
                    level="error",
                )
        else:
            self.log(
                f"AstroSensor._set_mode: mode {mode} is not recognised, ignored.",
                level="warning",
            )
        self.log(f"AstroSensor._set_mode: mode {mode} selected.", terminal=False)
        if self.camera_window is not None:
            self.camera_window.print(f"Sensor mode: {mode}")
        self.log(
            f"AstroSensor: Pixel dimensions now: {self.pixel_width}x{self.pixel_height}",
            terminal=False,
        )

    def disable_cleanup(self):
        """Disable the on-chip image cleanup for the sensor.
        Even in RAW capture mode, the sensor will perform some image cleanup by default.
        This cleanup degrades the raw data that astro photo stacking software will work with.
        Therefore it is advisable to disable this cleanup before taking photos for stacking.
        """
        if self.parameters.camera_driver == "raspistill":  # if OS_name in ['buster']:
            print(
                TextColor.yellow(
                    "Disabling sensor cleanup to improve purity of sensor raw data."
                )
            )
            # Check that the sensor cleanup function actually can be disabled
            if self.sensor_type not in ["imx477"]:
                self.log(
                    f"AstroSensor.disable_cleanup is not supported for {self.sensor_type} sensors. Ignored.",
                    level="warning",
                )
                return False
            # Turn off on-chip cleaning of the image.
            cmd = "sudo vcdbg set imx477.dpc 0"
            # This raises some error messages like this...
            #    debug_sym: vc_mem_copy: Unable to open '/dev/fb0': No such file or directory.
            # According to raspberry pi forum, these can be ignored.
            # The output is not displayed, however pilomar logs it in case other errors occur in the future.
            self.log(cmd, terminal=False)
            self.os_cmd(cmd)
            # raspistill feature. Libcamera does it through the command line.
            self.on_chip_cleanup = False
            # Cleanup is disabled.
            self.parameters.disable_cleanup = True
            self.log(
                "Raspberry Pi High Quality Camera, on chip image cleanup DISABLED.",
                terminal=False,
            )
            if self.camera_window is not None:
                self.camera_window.print(f"{now_hms()} On Chip Cleanup - OFF")
        # libcamera has a command line option to disable cleanup.
        else:
            self.log(
                "AstroSensor.disable_cleanup disable cleanup via the CameraCommands parameters for libcamera.",
                terminal=False,
            )
            self.log(
                "AstroSensor.disable_cleanup cleanup is always disabled for pilomarfits.",
                terminal=False,
            )
            self.log(
                "AstroSensor.disable_cleanup: Please check the '--denoise off ' option in the command templates in the parameter file.",
                terminal=False,
            )
        return True

    def enable_cleanup(self):
        """Enable the on-chip image cleanup for the sensor.
        This returns the on-chip image cleanup back to the default state (ON)
        It is recommended to have it disabled for image stacking of raw images."""
        # if OS_name in ['buster']:
        if self.parameters.camera_driver == "raspistill":
            print(
                TextColor.yellow(
                    "Enabling sensor cleanup to restore factory functionality."
                )
            )
            if self.sensor_type not in ["imx477"]:
                self.log(
                    f"AstroSensor.EnableCleanup is not supported for {self.sensor_type} sensors. Ignored.",
                    level="warning",
                )
                return False
            # Turn on on-chip cleaning of the image.
            cmd = "sudo vcdbg set imx477.dpc 3"
            # This raises some error messages like this...
            #    debug_sym: vc_mem_copy: Unable to open '/dev/fb0': No such file or directory.
            # According to raspberry pi forum, these can be ignored.
            # The output is logged but not displayed in case other errors occur in the future.
            self.log(cmd, terminal=False)
            self.os_cmd(cmd)
            # Raspistill feature, libcamera does it through the command line.
            self.on_chip_cleanup = True
            self.parameters.disable_cleanup = False
            self.log(
                "Raspberry Pi High Quality Camera, on chip image cleanup ENABLED.",
                terminal=False,
            )
            if self.camera_window is not None:
                self.camera_window.print(f"{now_hms()} On Chip Cleanup - ON")
        # libcamera has a command line option to disable cleanup.
        else:
            self.log(
                "AstroSensor.EnableCleanup(): Please check the '--denoise off ' option is removed in the command templates in the parameter file.",
                terminal=False,
            )
        return True


# --------------------------------------------------------------------


class AstroCamera(AttributeMaster):
    """Object representing the camera assembly being used.
    It contains the LENS and SENSOR objects, also various attributes
    and settings of the overall camera.
    """

    camera_list: List["AstroCamera"] = []  # List of cameras declared.

    # @staticmethod
    # def SetGlobalFolderList(folderlist):
    #    """ Update FolderList in all declared cameras. """
    #    for camera in AstroCamera.camera_list:
    #        camera.FolderList = folderlist

    @staticmethod
    def set_global_folder_handler(folderhandler):
        """Update FolderHandler in all declared cameras."""
        for camera in AstroCamera.camera_list:
            camera.folder_handler = folderhandler

    @staticmethod
    def set_global_mctl(mctl):
        """Update Microcontroller handler in all declared cameras."""
        for camera in AstroCamera.camera_list:
            camera.mctl = mctl

    @staticmethod
    def set_global_keyboard(keyboard):
        """Update Keyboard scanner handle in all declared cameras."""
        for camera in AstroCamera.camera_list:
            camera.keyboard = keyboard

    def __init__(
        self,
        inp_sensor,
        inp_lens,
        exposure=10.0,
        trackingexposure=5.0,
        logger: Union[LogFile, None] = None,
        parameters: Union[Parameters, None] = None,
        image_simulator=None,
    ):
        super().__init__()
        if logger is not None:
            # CamLog # Handle to the class that handles logging and error tracing.
            self.set_logger(logger)
            # Create OS command executor.
            self.os_command = OsCommand(logger=logger.log)
        else:
            self.os_command = OsCommand()  # Create OS command executor without logger.
        self.os_cmd = self.os_command.execute
        # Helper functions and attributes, should be set in calling program.
        # Can be handle to image simulation procedure. Must match CreatetargetImage() signature.
        self.image_simulator = None
        # Can be handle to relative_alt_az calculation. Must match relative_alt_az() signature.
        self.relative_alt_az = None
        # Can be handle to plot_relative_alt_az calculation. Must match plot_relative_alt_az() signature.
        self.plot_relative_alt_az = None
        # Can declare a keyboard scanner (TextColor keyboard scanner instance).
        self.keyboard = None
        # Can declare an error window (TextColor library) to copy error messages to
        self.error_window = None
        # Can declare a camera window (TextColor library) to copy camera events to.
        self.camera_window = None
        # Can declare a storage monitor class here.
        self.storage_monitor = None
        if parameters is not None:
            self.parameters: Parameters = parameters
        else:
            raise _valueError(
                "AstroCamera.__init__(): Parameters instance must be provided."
            )
        # Can define the session instance.
        # Must be set externally when SESSION and CAMERA instances are both known.
        self.session: SessionStatus = None
        # Local copy of the FolderList telling where to store files.
        self.folder_handler = None
        # List of file types to make available.
        self.file_types = ["jpg", "dng"]
        # What is the target type? Set by SetObservationParameters() from session information.
        self.object_type = None
        # Handle to the microcontroller. Can monitor it for restarts.
        self.mctl = None
        # The sensor that makes up the camera.
        self.sensor: AstroSensor = inp_sensor
        # The lens that makes up the camera.
        self.lens: AstroLens = inp_lens
        # Exposure seconds per frame for astro photos ('light' frames).
        self.exposure_seconds = exposure
        # Tracking photos are always 5 second exposure.
        self.tracking_exposure_seconds = trackingexposure
        # Delay between successive exposures if taking timelapse images.
        self.timelapse_seconds = None
        # Handle to timelapse timer if set.
        self.timelapse_timer = None
        # Set by modeChange() below. How many pixels represent 1 degree image width.
        self.pixels_per_fov_degree_width = 0
        # Set by modeChange() below. How many pixels represent 1 degree image height.
        self.pixels_per_fov_degree_height = 0
        # Set by modeChange() below. # Approximate field of view of an individual pixel.
        self.pixel_fov_width = 0
        # Set by modeChange() below.
        self.pixel_fov_height = 0
        # Set by modeChange() below. Specifies how long an object takes to traverse one pixel of an image.
        self.seconds_per_pixel = 0.0
        # Set values based upon sensor mode.
        self.mode_change()
        # When was the latest image taken? # *Q* How widely is this attribute used?
        self.last_image_date_time = None
        # The filename of the last jpg taken (if saved)
        self.last_jpg = None
        # The filename of the last preview image generated.
        self.preview_jpg = None
        # The filename of the last overlay image generated.
        self.overlay_jpg = None
        # PilomarImage instance for handling OpenCV image buffer.
        self.image = PilomarImage(name="camera", logger=self.logger)
        # Timestamp when image capture started. Used to detect camera hanging.
        self.capture_start = None
        # Timestamp when image capture completed. Used to detect camera hanging.
        self.capture_end = None
        # How many photos taken in the current observation batch?
        self.batch_count = 0
        # self.ID = self.sensor.ID + "|" + self.lens.ID # Unique ID of lens and sensor characteristics.
        # The type of image being captured. Links to self.folder_handler. Tells HOW to process the image and WHERE to store it.
        self.set_image_type("light")
        # No tasks to perform yet.
        self.camera_tasks = []
        # The current task being performed by the camera.
        self.current_task = None
        # Keep a note of the camera options used for the latest light image.
        self.last_light_command = ""
        # Observation specific settings. These override the general parameters in instances where the general parameters don't make sense. Eg meteor monitoring.
        self.camera_save_dng = True
        self.camera_save_jpg = True
        self.camera_save_fits = False
        self.fast_image_capture = False
        # The camera options passed to raspistill. These depend upon the image type being captured.
        self.camera_options = ""
        # Number of messages received by camera thread.
        self.rx_count = 0
        # Number of messages sent by camera thread.
        self.tx_count = 0
        # Dictionary of captured images and metadata.
        self.batch_data = {}
        # Max pixel delta when trying to identify a star from PhotometrytargetLocations list.
        # self.PTL_Tolerance = 10
        # Record Star label and location in target image (for potential photometry experiments)
        # self.PTL_Clear()
        if self.parameters.camera_driver == "raspistill":
            # DNG data extraction from RPi camera RAW images.
            # From https://github.com/schoolpost/pidng Needs to be 3.4.6 version.
            # Later versions are not compatible.
            from pidng.core import (
                RPICAM2DNG,
            )

            # RPICAM2DNG() needed for Buster O/S raspistill operation.
            self.PiDNG = RPICAM2DNG()
        else:
            # RPICAM2DNG() not needed for libcamera operation.
            self.PiDNG = None
        # Add this instance to the global list of all defined cameras.
        AstroCamera.camera_list.append(self)

    # def PTL_AddStar(self,label,x,y):
    #    """ Add a star to the PhotometrytargetLocations list. """
    #    self.PhotometrytargetLocations[label] = (x,y)
    #
    # def PTL_Clear(self):
    #    """ reset the list of PhotometrytargetLocations. """
    #    self.PhotometrytargetLocations = {}
    #
    # def PTL_IdentifyStar(self,x,y):
    #    """ Given an image x,y position in the PhotometrytargetLocations list, return the star ID if it's known.
    #        Returns the closest match for any stars within 10 pixels of the requested location. """
    #    result = None
    #    closest = None
    #    for key,value in self.PhotometrytargetLocations.items(): # Go through the list of stars known in the target list. Try to find a match.
    #        delta = math.sqrt((x - value[0]) ** 2 + (y - value[1]) ** 2)
    #        if delta < self.PTL_Tolerance: # Consider this as a potential match, because it's within the pixel tolerance.
    #            if closest == None or closest > delta: # Closest match so far, use that.
    #                result = key # Get the ID to return to the calling procedure.
    #                closest = delta
    #    return result

    def pixel_fov(self):
        """Return the approximate Field Of View of a single pixel.
        This measure is useful for calibrating the tolerance of trajectory segments."""
        if self.pixels_per_fov_degree_width != 0:
            self.pixel_fov_width = 1 / self.pixels_per_fov_degree_width
        else:
            self.pixel_fov_width = 0
        if self.pixels_per_fov_degree_height != 0:
            self.pixel_fov_height = 1 / self.pixels_per_fov_degree_height
        else:
            self.pixel_fov_height = 0
        self.log(
            f"AstroCamera.pixel_fov (w/h) = {self.pixel_fov_width} deg * {self.pixel_fov_height} deg",
            terminal=False,
        )

    def set_observation_parameters(self):
        """Choose which parameter settings to apply to the observation about to begin.
        These are based upon the general parameter settings, but are overridden
        for some types of targets, such as meteors.

            self.CameraTasks          : What tasks should the camerahandler deal with?
            self.camera_save_dng        : Do we produce DNG raw sensor data?
            self.camera_save_jpg        : Do we create simple JPG images? (Raw data removed)
            self.camera_save_fits       : Do we create FITS files? (Still under development)
            self.fast_image_capture     : Do we perform fast image capture (delay image processing until later).
            self.LiveStacking         : Do we perform live stacking?

        """
        # Decide which tasks the camerahandler will deal with.
        self.camera_tasks = ["image", "pause"]
        self.target = self.session.target  # Keep local pointer to the target object.
        # What type of object are we looking at?
        self.object_type = self.session.target.object_type
        if self.object_type in [
            "aurora",
            "meteor",
        ]:  # Don't generate preview images for meteors or aurora.
            if self.camera_window is not None:
                self.camera_window.print(
                    now_hms()
                    + " No preview's generated for "
                    + self.object_type
                    + " recordings."
                )
            self.log(
                "AstroCamera.SetObservationParameters No preview's generated for",
                self.object_type,
                "recordings.",
                terminal=False,
            )
        elif not self.parameters.generate_preview:
            if self.camera_window is not None:
                self.camera_window.print(
                    f"{now_hms()} Preview generation is disabled in parameters."
                )
            self.log(
                "AstroCamera.SetObservationParameters Preview generation is disabled in parameters.",
                terminal=False,
            )
        else:
            self.camera_tasks.append("preview")
        if self.object_type in [
            "meteor",
            "altaz",
            "earth satellite",
            "aurora",
        ]:  # No need to perform drift tracking for these targets.
            # Don't track for fixed targets or fast moving targets.
            if self.camera_window is not None:
                self.camera_window.print(
                    f"{now_hms()} No tracking performed for {self.object_type} targets."
                )
            self.log(
                f"AstroCamera.SetObservationParameters No tracking performed for {self.object_type} targets.",
                terminal=False,
            )
        else:  # Do track for targets that rotate with the sky. Always add tracking to the tasklist, even if it's currently disabled. The tracking routine will handle that, and it could be dynamically enabled during the observation.
            self.camera_tasks.append("tracking")
        self.log(
            f"AstroCamera.SetObservationParameters target type {self.object_type}, Selected tasks: {self.camera_tasks}",
            self.camera_tasks,
            terminal=False,
        )

        # Set observation specific parameters for the camera based upon general parameter settings.
        # Eg 'meteor' mode can override some settings, but we don't want to disturb the general settings used for other targets.
        if self.object_type in [
            "aurora",
            "meteor",
        ]:  # Disable DNG generation if taking AURORA or METEOR images.
            if self.camera_save_dng:
                self.log(
                    f"AstroCamera.SetObservationParameters target type {self.object_type}, will not capture DNG (raw) images.",
                    terminal=False,
                )
                self.camera_save_dng = False
        else:
            self.camera_save_dng = (
                self.parameters.camera_save_dng
            )  # Revert to parameter preference.
        self.log(
            f"AstroCamera.SetObservationParameters target type {self.object_type}, camera_save_dng {self.camera_save_dng}",
            self.camera_save_dng,
            terminal=False,
        )

        if self.object_type in [
            "aurora",
            "meteor",
        ]:  # Disable DNG generation if taking AURORA or METEOR images.
            if self.camera_save_fits:
                self.log(
                    "AstroCamera.SetObservationParameters target type",
                    self.object_type,
                    ", will not capture FITS (raw) images.",
                    terminal=False,
                )
                self.camera_save_fits = False
        else:
            self.camera_save_fits = (
                self.parameters.camera_save_fits
            )  # Revert to parameter preference.
        self.log(
            f"AstroCamera.SetObservationParameters target type {self.object_type}, camera_save_fits {self.camera_save_fits}",
            terminal=False,
        )

        if self.object_type in [
            "aurora",
            "meteor",
        ]:  # Turn on JPG generation if not already set.
            if not self.camera_save_jpg:
                self.log(
                    f"AstroCamera.SetObservationParameters target type {self.object_type}, will capture JPG images.",
                    terminal=False,
                )
                self.camera_save_jpg = True
        else:
            self.camera_save_jpg = (
                self.parameters.camera_save_jpg
            )  # Revert to parameter preference.
        self.log(
            f"AstroCamera.SetObservationParameters target type {self.object_type}, camera_save_jpg {self.camera_save_jpg}",
            terminal=False,
        )

        if self.object_type in [
            "aurora",
            "meteor",
        ]:  # Turn on Fast image Capture if not already set.
            if not self.fast_image_capture:
                self.log(
                    "AstroCamera.SetObservationParameters target type",
                    self.object_type,
                    ", will use FAST image capture. (Minimal processing)",
                    terminal=False,
                )
                self.fast_image_capture = True
        else:
            self.fast_image_capture = (
                self.parameters.fast_image_capture
            )  # Revert to parameter preference.
        self.log(
            f"AstroCamera.SetObservationParameters target type {self.object_type}, fast_image_capture {self.fast_image_capture}",
            terminal=False,
        )

        return True

    def calibrate_fov(self):
        """Ask the user to enter the pixel diameter of the moon from a photograph.
        Use this to estimate the FieldOfView of the camera and adjust parameters accordingly.
        """
        self.log("AstroCamera.calibrate_fov: Begin", terminal=False)
        print(TextColor.yellow("Calibrate lens"))
        moon_mean_dia_deg = 0.5286
        expected_dia_pix = int(
            self.pixels_per_fov_degree_width * moon_mean_dia_deg
        )  # How big do we expect the moon to be with current settings?
        listlines = [
            "Currently the lens has the following characteristics",
            " ",
            "Focal length: " + str(self.lens.length) + "mm",
            "35mm equivalent: " + str(self.lens.equiv_length) + "mm",
            "horizontal field of view: " + str(self.lens.fov_horizontal) + "deg",
            "Vertical field of view: " + str(self.lens.fov_vertical) + "deg",
            "Minimum field of view: " + str(self.lens.fov) + "deg",
            "horizontal pixels per degree FOV: "
            + str(self.pixels_per_fov_degree_width),
            "Vertical pixels per degree FOV: " + str(self.pixels_per_fov_degree_height),
            "",
            "The Moon's disc is " + str(moon_mean_dia_deg) + "deg diameter on average.",
            "Expected diameter in an image is about "
            + str(expected_dia_pix)
            + " pixels.",
        ]
        TextColor.text_box(listlines)
        result = ask_yes_no(
            "Do you want to calibrate the field of view of the lens? [y/N]", False
        )
        if result:
            self.log("AstroCamera.calibrate_fov: Proceeding", terminal=False)
            result = ask_yes_no(
                "Do you have an image of the moon captured with the current lens? [y/N]",
                False,
            )
        if not result:
            self.log(
                "AstroCamera.calibrate_fov: Moon image is not available", terminal=False
            )
            listlines = [
                "You must take a photograph of the moon with the current lens.",
                "Measure the pixel diameter of the moon's full disc on that image.",
                "Using that pixel size we can estimate the field of view of the lens.",
            ]
            TextColor.text_box(listlines)
            return  # Do nothing.

        self.log("AstroCamera.calibrate_fov: Moon image is available", terminal=False)

        # Can we offer any hints from the last image captured?
        self.log(
            "AstroCamera.calibrate_fov: Consider last captured image", terminal=False
        )
        if (
            self.image.image_exists()
        ):  # There's an image in the buffer, what large objects are in there?
            dia_min = 50  # Smallest diameter objects to list.
            dia_max = 600  # Largest diameter objects to list.
            area_min = int(math.pi * ((dia_min / 2) ** 2))
            area_max = int(math.pi * ((dia_max / 2) ** 2))
            bc_count, bc_list = self.image.count_stars(
                minval=area_min, maxval=area_max
            )  # Count objects with large pixel areas (100-600 pixel radius).
        else:  # No objects identified.
            bc_count = 0
            bc_list = []
        if bc_count > 0:
            self.log(
                "The last image has", bc_count, "large objects in it.", terminal=True
            )
            for i, j in enumerate(bc_list):  # List all the large objects found.
                jx = j[0]  # x value for centre of object.
                jy = j[1]  # y value for centre of object.
                dia = int(j[2] * 2)  # Pixel diameter of the object.
                self.log(
                    f"{i} Centered at ({jx},{jy}) diameter {dia} pixels", terminal=True
                )
        else:  # There is no existing image in the buffer, so we cannot offer any clues.
            self.log(
                "There is no recent image loaded, cannot list any large objects.",
                terminal=True,
            )

        # We want to continue.
        rawtext = None
        while rawtext is None:
            rawtext = input(
                TextColor.cyan(
                    "How many pixels is the diameter of the Moon's full disc? ('x' to quit): "
                )
            )
            rawtext = rawtext.lower()
            if rawtext == "x":
                rawtext = None
                break  # Quit
            if rawtext.isdigit():
                rawtext = int(rawtext)
                break  # We have a value to use.

            print(TextColor.red("Please try again. Integer values only."))
            rawtext = None  # Try again.

        if rawtext is None:
            self.log(
                "AstroCamera.calibrate_fov: No moon diameter value given",
                terminal=False,
            )
            return  # Nothing to do.

        self.log(
            f"AstroCamera.calibrate_fov: Moon diameter {rawtext} pixels",
            terminal=False,
        )

        # We have what we need.
        moonpixels = int(rawtext)  # Convert the measured diameter into integer.
        print("The camera records the moon as", moonpixels, "pixels in diameter.")
        print("The moon is" + str(moon_mean_dia_deg) + "deg in diameter on average.")
        # Convert to field of view.
        # Lens fields to change...
        # FOV to 1 decimal place is enough.
        self.lens.fov_horizontal = round(
            self.sensor.pixel_width * moon_mean_dia_deg / moonpixels, 1
        )
        # FOV to 1 decimal place is enough.
        self.lens.fov_vertical = round(
            self.sensor.pixel_height * moon_mean_dia_deg / moonpixels, 1
        )
        # When calculating the FOV for a survey, use the smaller value.
        self.lens.fov = min(self.lens.fov_horizontal, self.lens.fov_vertical)
        self.log(
            "AstroCamera.calibrate_fov: Chosen H.FoV:",
            self.lens.fov_horizontal,
            "V.FoV:",
            self.lens.fov_vertical,
            terminal=False,
        )
        # Camera fields to change...
        # Set camera's FOV related values just as if the sensor mode had changed.
        self.mode_change()
        # How big do we expect the moon to be with current settings?
        expected_dia_pix = int(self.pixels_per_fov_degree_width * moon_mean_dia_deg)
        listlines = [
            "The lens now has the following characteristics",
            " ",
            f"horizontal field of view: {self.lens.fov_horizontal}deg",
            f"Vertical field of view: {self.lens.fov_vertical}deg",
            f"Minimum field of view: {self.lens.fov}deg",
            f"horizontal pixels per degree FOV: {self.pixels_per_fov_degree_width}",
            f"Vertical pixels per degree FOV: {self.pixels_per_fov_degree_height}",
            " ",
            f"The Moon's disc is {moon_mean_dia_deg}deg diameter on average.",
            f"Expected diameter in an image is about {expected_dia_pix} pixels.",
        ]
        TextColor.text_box(listlines)
        result = ask_yes_no("Do you want to make these changes permanent? [y/N]", False)
        if (
            result
        ):  # Make these changes permanent by setting them in the parameter file.
            self.log("AstroCamera.calibrate_fov: Making FoV permanent.", terminal=False)
            self.parameters.lens_horizontal_fov = self.lens.fov_horizontal
            self.parameters.lens_vertical_fov = self.lens.fov_vertical
        else:  # Don't touch the parameter settings, so the system will reset when restarted.
            self.log("AstroCamera.calibrate_fov: Making FoV temporary.", terminal=False)
            print(
                TextColor.yellow(
                    "These values are temporary. They will reset when you restart the software."
                )
            )
            print(
                TextColor.red(
                    "To make these values permanent please edit lens_horizontal_fov and lens_vertical_fov values in the parameters file."
                )
            )
            print(TextColor.red(f"({self.parameters.param_file_name})"))

    def set_image_type(self, imagetype):
        """Validate and set the ImageType attribute.
        The image type must be in the self.FolderList dictionary."""
        # if imagetype in self.FolderList:
        if self.folder_handler is not None and self.folder_handler.ValidKey(imagetype):
            self._image_type = imagetype  # OK to accept this image type.
            self.log(
                f"AstroCamera.set_image_type({imagetype}) new image type set.",
                terminal=False,
            )
        else:  # ImageType has nowhere to go.
            # self.log("AstroCamera.set_image_type(",imagetype,") is not recognised. Must be in FolderList. Defaulting to 'light'.",terminal=False)
            self.log(
                f"AstroCamera.set_image_type({imagetype}) is not recognised. Must be in FolderHandler. Defaulting to 'light'.",
                terminal=False,
            )
            self._image_type = "light"

    def get_image_type(self):
        return self._image_type

    def set_timelapse(self, seconds):
        """Set timelapse delay and initiate timer."""
        if seconds is None or seconds <= 0.0:
            self.timelapse_timer: Union[Timer, None] = None
            self.timelapse_seconds = None
        else:
            self.timelapse_timer: Timer = Timer(period=seconds)
            self.timelapse_seconds = seconds

    def timelapse_due(self):
        """Return TRUE if the camera timelapse is active and due.
        Return TRUE if the camera timelapse is not active at all.
        Return FALSE if the camera timelapse is active but not due."""
        if self.timelapse_timer is None:
            return True  # No timer, so always due.
        else:
            return self.timelapse_timer.due()  # Use the real timer.

    def reset(self):
        """reset camera settings at the beginning of a new session."""
        self.last_image_datetime = None  # When was the latest image taken?
        self.last_jpg = None  # The filename of the last jpg taken (if saved)
        self.preview_jpg = None  # The filename of the last preview image generated.
        self.overlay_jpg = None  # The filename of the last overlay image generated.
        self.image.clear()  # openCV image buffer. Loaded explicitly when needed.
        self.capture_start = (
            None  # Timestamp when image capture started. Used to detect camera hanging.
        )
        self.capture_end = None  # Timestamp when image capture completed. Used to detect camera hanging.
        self.batch_count = 0  # How many photos taken in the current observation batch?
        self.batch_data = {}  # Dictionary of captured images and metadata.
        if self.camera_window is not None:
            self.camera_window.print(now_hms() + " AstroCamera.reset")

    def save_batch_data(self, filename):
        """Dump the batch_data dictionary as a json file to disc."""
        with open(filename, "w") as f:
            json.dump(self.batch_data, f, indent=4, default=str)

    def capture_start_age(self):
        """Return a timedelta object showing how long ago the last image capture began.
        Returns None if no image captured yet."""
        result = None
        if self.capture_start is not None:
            result = now_utc() - self.capture_start
        return result

    def capture_start_age_seconds(self):
        """Number of seconds since last camera capture began.
        Returns None if no image."""
        result = self.capture_start_age()
        if result is not None:
            result = result.total_seconds()
        return result

    def last_image_age(self):
        """Return a timedelta object with the age of the last image.
        Returns None if no image captured yet."""
        result = None
        if self.last_image_datetime is not None:
            result = now_utc() - self.last_image_datetime
        return result

    def last_image_age_seconds(self):
        """Return age of last image in seconds.
        Returns None if no image."""
        result = self.last_image_age()
        if result is not None:
            result = result.total_seconds()
        return result

    def camera_fault(self):
        """Return true if it looks like the camera has hung.
        This usually requires an entire reboot of the RPi.
        The hang is somewhere in the camera subsystem.
        Suspect it is related to memory problems, but cause or effect?
        NOTE: There are overheads in the camera libraries, the camera takes much longer than just the 'exposure' time to complete an image.
              Typically a call to raspistill will take at least DOUBLE the exposure time to complete a capture.
        """
        result = False  # no fault detected yet.
        if (
            self.parameters.camera_enabled and self.capture_start is not None
        ):  # An attempt has been made and the camera is on!
            if (
                self.capture_end is None or self.capture_end <= self.capture_start
            ):  # It hasn't completed yet.
                # Decide upon a sensible 'failure' delay to accept. At least 300seconds(5 minutes)
                # We have to be very generous here because this is a linux system and can sometimes pause a lot!
                faultdelay = max(self.ExposureSeconds * 5, 500)
                if (
                    self.capture_start_age_seconds() > faultdelay
                ):  # It has been running too long.
                    result = True  # It looks like there's something wrong.
                    line = (
                        "AstroCamera.camera_fault: image capture time "
                        + str(round(self.capture_start_age_seconds(), 1))
                        + "s is too long. The camera may have hung. Consider power cycling the RPi."
                    )
                    if self.camera_window is not None:
                        self.camera_window.print(now_hms() + " " + line)
                    self.log(
                        "AstroCamera.capture_start", self.capture_start, terminal=False
                    )
                    self.log(
                        "AstroCamera.capture_end", self.capture_start, terminal=False
                    )
                    self.log("AstroCamera.faultdelay", faultdelay, terminal=False)
                    self.log(
                        "AstroCamera.capture_start_age_seconds",
                        self.capture_start_age_seconds(),
                        terminal=False,
                    )
                    self.log(
                        "AstroCamera.last_image_datetime",
                        self.last_image_datetime,
                        terminal=False,
                    )
                    self.log(line, level="error")
        return result

    def set_mode(self, mode):
        """Change the sensor mode.
        This may change the format and other characteristics of the images recorded.
        It does not have any impact on the RAW data collected."""
        self.sensor._set_mode(mode)  # Update the sensor to the new mode first.
        self.mode_change()  # Update dependent values in the camera to reflect the new change.
        self.log(
            "AstroCamera.set_mode(): mode " + str(mode) + " selected.", terminal=False
        )
        self.log(
            "AstroCamera.set_mode(): Sensor pixel dimensions now: "
            + str(self.sensor.pixel_width)
            + "x"
            + str(self.sensor.pixel_height),
            terminal=False,
        )
        self.log(
            "AstroCamera.set_mode(): Pixels per degree are now: "
            + str(self.pixels_per_fov_degree_width)
            + "x"
            + str(self.pixels_per_fov_degree_height),
            terminal=False,
        )
        self.log(
            "AstroCamera.set_mode(): Seconds per pixel is now: "
            + str(self.SecondsPerPixel),
            terminal=False,
        )

    def mode_change(self):
        """Call this whenever the sensor changes mode."""
        self.pixels_per_fov_degree_width = int(
            self.sensor.pixel_width / self.lens.fov_horizontal
        )  # Conversion value between ANGLE and PIXELS.
        self.pixels_per_fov_degree_height = int(
            self.sensor.pixel_height / self.lens.fov_vertical
        )  # Conversion value between ANGLE and PIXELS.
        self.exposure_seconds = (
            1.0  # Default 1 second exposure per frame for astro photos.
        )
        self.log(
            "AstroCamera.mode_change(): PixelsPerDegree Width/Height "
            + str(self.pixels_per_fov_degree_width)
            + " / "
            + str(self.pixels_per_fov_degree_height),
            terminal=False,
        )
        arc_seconds_per_width = self.lens.fov_horizontal * 60 * 60
        arc_seconds_per_pixel = float(arc_seconds_per_width) / self.sensor.pixel_width
        self.log(
            "AstroCamera.mode_change(): Arcseconds per pixel: "
            + str(round(arc_seconds_per_pixel, 3)),
            terminal=False,
        )
        full_rotation_as = 360 * 60 * 60  # Arcseconds in an entire rotation.
        seconds_per_as = (
            24 * 60 * 60 / float(full_rotation_as)
        )  # How many seconds does a single arcsecond last before earth rotation has moved on.
        self.log(
            "AstroCamera.mode_change(): Seconds per arcsecond: " + str(seconds_per_as),
            terminal=False,
        )
        self.seconds_per_pixel = float(arc_seconds_per_pixel) * seconds_per_as
        self.log(
            "AstroCamera.mode_change(): To avoid blurring the camera needs to move every",
            round(self.seconds_per_pixel, 3),
            "seconds.",
            terminal=False,
        )
        self.log(
            "AstroCamera.mode_change(): mode " + str(self.sensor.mode) + " selected.",
            terminal=False,
        )
        self.pixel_fov()  # Calculate field of view of an individual pixel (very approximate).

    def cleanup_last_jpg(self):
        """Call this to delete the disc copy of the last jpg file that was generated.
        It also clears the reference to the file that has been deleted."""
        self.log("AstroCamera.cleanup_last_jpg()", terminal=False)
        if self.last_jpg is not None:
            cmd = "rm " + self.last_jpg
            self.os_cmd(cmd)
            self.last_jpg = None  # Clear the saved filename.

    def fake_aurora(self, srcimg):  # Generate a fake aurora effect.
        """Create a series of aurura like color blocks on an image.
        srcimg = numpy buffer.
        Return combined image."""
        height = self.sensor.pixel_height  # image dimensions.
        width = self.sensor.pixel_width
        curtain_image = PilomarImage(
            name="auroracurtain", logger=self.logger
        )  # Create empty image.
        auroracolors = [
            PilomarImage.BGR("LightGreen"),
            PilomarImage.BGR("DarkGreen"),
            PilomarImage.BGR("Cyan"),
            PilomarImage.BGR("HotPink"),
        ]
        for i, ac in enumerate(auroracolors):  # Dim all the colors.
            auroracolors[i] = curtain_image.DimColor(
                ac, 0.2
            )  # Reduce color intensity to nnn%
        fieldimg = srcimg.copy().astype(
            np.uint16
        )  # Black image, datatype large enough for multiple layers to be combined.
        curtain_image.new(height, width, imagetype="bgr", datatype=np.uint8)
        if curtain_image.image_missing():
            self.log(
                "AstroCamera.fake_aurora: fakeimage.new() failed.",
                level="error",
                terminal=True,
            )
        cornerlist = []  # Build cornerlist for polygon.
        for j in range(5):  # Build polygon random corners. Start with bottom edge.
            cornerlist.append(
                (
                    int(width * j / 4),
                    random.randint(int(height * 0.6), int(height * 0.8)),
                )
            )
        multiplier = 0.75
        revlist = cornerlist[
            ::-1
        ]  # Reverse the bottom edge to produce the top edge of the polygon.
        for (
            corner
        ) in (
            revlist
        ):  # Scale all the top edge values so they are higher in the image by 20%.
            y = int(corner[1] * multiplier)
            cornerlist.append((corner[0], y))
        for i, color in enumerate(auroracolors):  # Poll through the colors.
            curtaincolor = color  # Select color for this layer.
            curtain_image.new(
                height, width, imagetype="bgr", datatype=np.uint8
            )  # Empty the buffer for each curtain.
            for j in range(1, len(cornerlist)):
                curtain_image.fill_polygon(cornerlist, color=curtaincolor)
            fieldimg = np.add(
                fieldimg, curtain_image.image_buffer
            )  # Apply the curtain object on top of the base image.
            # Reduce height of all corners for next color.
            cornerlist = [
                (corner[0], int(corner[1] * multiplier)) for corner in cornerlist
            ]
        fieldimg = np.clip(fieldimg, 0, 255).astype(np.uint8)  # Clip to uint8 values.
        return fieldimg

    def fake_pollution(self, srcimg):  # Generate fake light pollution.
        """Create a small blank image and add some fake light pollution to it.
        srcimg = numpy buffer.
        Return the combined image."""
        self.log(
            "AstroCamera.fake_pollution: Simulating light pollution.", terminal=False
        )
        # How thick is the haze at the horizon? (BGR) (Scale 0-255, higher values = more pollution)
        thickest_value = [
            50,
            50,
            50,
        ]
        # How thick is the haze above pollution_max_alt? (BGR)  (Scale 0-255, higher values = more pollution)
        thinnest_value = [
            10,
            10,
            10,
        ]
        # Degrees. Pollution fades to thinnest_value at this altitude above the horizon.
        pollution_max_alt = 15
        haze_change = []  # What's the delta between the two limits?
        for j, thick in enumerate(thickest_value):
            haze_change.append(thick - thinnest_value[j])
        avg_value = []  # What's the average between the two limits?
        for j, thick in enumerate(thickest_value):
            avg_value.append(int((thick - thinnest_value[j]) / 2))
        self.log("AstroCamera.fake_pollution: haze_change", haze_change, terminal=False)
        # Use the live target location rather than the last reported camera position for image processing.
        if self.parameters.use_live_location:
            # What is the alt/az location of the centre of the image?
            center_az, center_alt = self.target.az_alt_degrees()
        else:  # Use the last reported camera position. Deprecated.
            # What is the alt/az location of the centre of the image?
            center_alt, center_az = last_reported_alt_az()
        self.log(
            "AstroCamera.fake_pollution: center_altAz",
            center_alt,
            center_az,
            terminal=False,
        )
        # image pixel height of horizon. (Thickest pollution level).
        rel_alt, rel_az = self.relative_alt_az(0, center_az, center_alt, center_az)
        # Covert to pixel height.
        _, horizon_y = self.plot_relative_alt_az(
            rel_alt, rel_az, self.sensor.pixel_height, self.sensor.pixel_width
        )
        self.log(
            "AstroCamera.fake_pollution: horizonAltAz",
            rel_alt,
            rel_az,
            horizon_y,
            terminal=False,
        )
        rel_alt, rel_az = self.relative_alt_az(
            pollution_max_alt, center_az, center_alt, center_az
        )  # image pixel height of pollution upper limit. (thinnest pollution level)
        _, top_y = self.plot_relative_alt_az(
            rel_alt, rel_az, self.sensor.pixel_height, self.sensor.pixel_width
        )  # Covert to pixel height.
        self.log(
            "AstroCamera.fake_pollution: TopAltAz",
            rel_alt,
            rel_az,
            top_y,
            terminal=False,
        )
        self.log(
            "AstroCamera.fake_pollution: horizon height",
            horizon_y,
            "px",
            terminal=False,
        )
        self.log(
            "AstroCamera.fake_pollution: Top height",
            top_y,
            "px, (pollution_max_alt",
            pollution_max_alt,
            "deg)",
            terminal=False,
        )
        # Black image.
        fieldimg = np.zeros(
            (self.sensor.pixel_height, self.sensor.pixel_width, 3), np.uint16
        )
        # Set ALL pixels to the thinnest haze value by default.
        fieldimg[:, :] = np.array(thinnest_value).astype(np.uint16)
        # horizon is in range.
        if horizon_y < self.sensor.pixel_height:
            # Fill everything below horizon with Thickest pollution value.
            for i in range(max(0, horizon_y), self.sensor.pixel_height):
                fieldimg[i, :] = np.array(thickest_value).astype(np.uint16)

        # Now to calculate the gradient values where the
        # haze builds up as it approaches the horizon.

        # Remember that images count rows from top down.
        # How many rows to fill with the gradient if the image was infinitely tall?
        rowspan = horizon_y - top_y

        # Constrain the Top of the gradient to within the image boundary.
        if top_y < 0:
            startrow = 0
        elif top_y > self.sensor.pixel_height:
            startrow = self.sensor.pixel_height
        else:
            startrow = top_y

        # Constrain the horizon to within the image boundary.
        if horizon_y < 0:
            endrow = 0
        elif horizon_y > self.sensor.pixel_height:
            endrow = self.sensor.pixel_height
        else:
            endrow = horizon_y

        # There's a band of the image that needs the haze gradient calculating.
        if startrow != endrow:
            # Process each row of the gradient in turn.
            for i in range(startrow, endrow):
                # How thick is the haze? Increasing in thickness towards the horizon.
                gradient_point = (i - top_y) / rowspan
                new_value = []
                # Calculate strength of each color channel in turn. BGR.
                for j, thin in enumerate(thinnest_value):
                    tV = ((thickest_value[j] - thin) * gradient_point) + thin
                    new_value.append(int(tV))
                fieldimg[i, :] = np.array(new_value).astype(np.uint16)

        # TODO: Add some random noise to the pattern. +/- thinnest value at random to the entire image.

        self.log(
            "AstroCamera.fake_pollution: Gradient span",
            startrow,
            endrow,
            rowspan,
            terminal=False,
        )

        # Pollution is a gradient at a fixed altitude parallel to the horizon.
        fieldimg = np.add(fieldimg, srcimg)
        fieldimg = np.clip(fieldimg, 0, 255).astype(np.uint8)  # Clip to uint8 values.
        return fieldimg

    def fake_photo(self, outputfile, astrotime=None):
        # Generate false disc file to simulate a photograph being captured.
        self.log(
            f"AstroCamera.fake_photo: Simulating photo capture ({outputfile})",
            terminal=False,
        )
        fakeimage = PilomarImage(name="fakephoto", logger=self.logger)
        height = self.sensor.pixel_height
        width = self.sensor.pixel_width
        fakeimage.new(height, width, imagetype="bgr", datatype=np.uint8)
        if fakeimage.image_missing():
            self.log(
                "AstroCamera.fake_photo: fakeimage.new() failed.",
                level="error",
                terminal=True,
            )
        # Use CreatetargetImage to make fake photo.
        # fakeimage.image_buffer,starcount,starlist = CreatetargetImage(
        #    color=True,min_magnitude=self.parameters.target_min_magnitude,astrotime=astrotime
        # )
        # Use CreatetargetImage to make fake photo.
        fakeimage.image_buffer, starcount, starlist = self.image_simulator(
            color=True,
            min_magnitude=self.parameters.target_min_magnitude,
            mark_all_stars=self.parameters.mark_all_stars,
            astrotime=astrotime,
        )
        if fakeimage.image_missing():
            self.log(
                "AstroCamera.fake_photo: image_simulator() failed.",
                level="error",
                terminal=True,
            )
        if self.parameters.fake_noise:  # Simulate fake image noise.
            fakeimage.fake_noise()
            if fakeimage.image_missing():
                self.log(
                    "AstroCamera.fake_photo: fake_noise() failed.",
                    level="error",
                    terminal=True,
                )
        if (
            self.parameters.fake_field
        ):  # Simulate fake electrical field noise in the image.
            fakeimage.fake_field()
            if fakeimage.image_missing():
                self.log(
                    "AstroCamera.fake_photo: fake_field() failed.",
                    level="error",
                    terminal=True,
                )
        if self.parameters.fake_pollution:  # Simulate fake light pollution.
            fakeimage.image_buffer = self.fake_pollution(fakeimage.image_buffer)
            if fakeimage.image_missing():
                self.log(
                    "AstroCamera.fake_photo: fake_pollution() failed.",
                    level="error",
                    terminal=True,
                )
        if (
            self.object_type in ["aurora"] and self.parameters.fake_aurora
        ):  # Simulate aurora
            fakeimage.image_buffer = self.fake_aurora(fakeimage.image_buffer)
            if fakeimage.image_missing():
                self.log(
                    "AstroCamera.fake_photo: fake_aurora() failed.",
                    level="error",
                    terminal=True,
                )
        if (
            self.parameters.fake_meteor_percent > 0
            and random.randint(0, 100) < self.parameters.fake_meteor_percent
        ):  # xxx% of images get fake meteor streaks in them.
            fakeimage.fake_meteor()
            if fakeimage.image_missing():
                self.log(
                    "AstroCamera.fake_photo: fake_meteor() failed.",
                    level="error",
                    terminal=True,
                )
        try:
            fakeimage.save_file(outputfile)
        except Exception as e:  # pylint: disable=broad-except
            self.log(
                "AstroCamera.fake_photo failed to write:", outputfile, level="error"
            )
            self.report_exception(e, comment="AstroCamera.fake_photo cv2.imwrite")
        self.log("AstroCamera.fake_photo: Completed.", terminal=False)
        return True

    def fake_dark(self, outputfile):
        """Create a fake dark frame image and save it to the specified output file.
        This simulates the process of capturing a dark frame photograph,
        which is used for calibration in astrophotography."""
        # Generate false disc file to simulate a photograph being captured.
        self.log(
            "AstroCamera.fake_dark: Simulating dark photo capture (",
            outputfile,
            ")",
            terminal=False,
        )
        fakeimage = PilomarImage(name="fakedark", logger=self.logger)
        height = self.sensor.pixel_height
        width = self.sensor.pixel_width
        fakeimage.new(height, width, imagetype="bgr", datatype=np.uint8)
        fakeimage.fill_color((0, 0, 0))  # Black.
        if self.parameters.fake_noise:  # Simulate fake image noise.
            fakeimage.fake_noise()
        if (
            self.parameters.fake_field
        ):  # Simulate fake electrical field noise in the image.
            fakeimage.fake_field()
        try:
            fakeimage.save_file(outputfile)
        except Exception as e:  # pylint: disable=broad-except
            self.log(
                "AstroCamera.fake_dark failed to write:", outputfile, level="error"
            )
            self.report_exception(e, comment="AstroCamera.fake_dark cv2.imwrite")
        self.log("AstroCamera.fake_dark: Completed.", terminal=False)
        return True

    def set_fake_delay(self, camera_options):
        """Extract the exposure time from camera options and pause processing
        to mimic the actual amount of time the camera would take."""
        optlist = camera_options.split(" ")
        delay = 1.0
        for i, opt in enumerate(
            optlist
        ):  # *Q* Doesn't recognise libcamera format parameters yet!
            if opt in ["-ss", "--shutter"]:  # Found exposure time.
                delay = (
                    float(optlist[i + 1]) * 2
                )  # Find the microsecond exposure time and double it to mimic camera.
                delay = delay / 1_000_000  # Convert from microseconds to seconds.
                self.log(
                    "AstroCamera.FakeDelay : ", round(delay, 1), "s ...", terminal=False
                )
                break
        delay_timer = Timer(period=int(delay))  # Create timer.
        return delay_timer

    def append_batch_data(self, image_filename):
        """Create new entry in batch_data for the current image.
        image_filename : String with the name of the image file on disc."""
        new_rec = {}
        new_rec["start"] = self.capture_start
        new_rec["end"] = self.capture_end
        new_rec["length"] = self.lens.length
        new_rec["fov_horizontal"] = self.lens.fov_horizontal
        new_rec["fov_vertical"] = self.lens.fov_vertical
        new_rec["exposure"] = self.exposure_seconds
        # Set by modeChange() below. How many pixels represent 1 degree image width.
        new_rec["pixels_per_horizontal_degree"] = self.pixels_per_fov_degree_width
        # Set by modeChange() below. How many pixels represent 1 degree image height.
        new_rec["pixels_per_vertical_degree"] = self.pixels_per_fov_degree_height
        # Set by modeChange() below. # Approximate field of view of an individual pixel.
        new_rec["degrees_per_horizontal_pixel"] = self.pixel_fov_width
        # Set by modeChange() below.
        new_rec["degrees_per_vertical_pixel"] = self.pixel_fov_height
        if hasattr(self.session, "target"):
            # Session has a pointer to the current target. Get data from there.
            if hasattr(self.session.target, "az_alt_degrees"):
                # Current position in the sky.
                az, alt = self.session.target.az_alt_degrees()
                new_rec["az"] = az
                new_rec["alt"] = alt
            # Current position in the sky.
            if hasattr(self.session.target, "ra_dec_hours"):
                ra, dec = self.session.target.ra_dec_hours()  #
                new_rec["ra"] = ra
                new_rec["dec"] = dec
            # Append details of the target.
            new_rec["target_name"] = self.session.target.name  # Name of object.
            # Which search category was used?
            new_rec["target_group"] = self.session.target.search_group
            # Which search term identifies this object?
            new_rec["target_term"] = self.session.target.search_term
            # What type of object is it?
            new_rec["target_type"] = self.session.target.object_type
        new_rec["path"] = image_filename
        if hasattr(self.folder_handler, "name_only"):
            # Can remove directory structure.
            image_filename = self.folder_handler.name_only(image_filename)
        # Append metadata of this frame to the list of images captured.
        self.batch_data[image_filename] = new_rec

    def capture_set(
        self,
        file_root,
        batch_size,
        camera_command,
        tempfile=False,
        terminal=True,
        cleanup=True,
        astrotime=None,
    ):
        """Take batch of photos. Uses capture_set_full or CaptureSetFast depending upon configuration."""
        # Automatic parameter conversion, if not already done before receiving camera_command.
        camera_command = camera_command.replace(
            "{&mode}", str(self.sensor.mode)
        )  # Camera mode.
        camera_command = camera_command.replace(
            "{&channel}", str(self.sensor.channel)
        )  # Camera channel if multi-camera RPi.
        camera_command = camera_command.replace(
            "{&width}", str(self.sensor.pixel_width)
        )  # image width.
        camera_command = camera_command.replace(
            "{&height}", str(self.sensor.pixel_height)
        )  # image height.
        camera_command = camera_command.replace(
            "{&fitstech}", str(self.session.tech_fits_tags_file)
        )  # Point to FITS technical tags file.
        camera_command = camera_command.replace(
            "{&exiftech}", str(self.session.tech_exif_tags_file)
        )  # Point to FITS technical tags file.
        camera_command = camera_command.replace(
            "{&fitsweather}", str(self.session.weather_fits_tags_file)
        )  # Point to FITS weather tags file.
        camera_command = camera_command.replace(
            "{&exifweather}", str(self.session.weather_exif_tags_file)
        )  # Point to FITS weather tags file.
        camera_command = camera_command.replace(
            "{&logfile}", self.logger.file_name
        )  # Log file to write to.
        camera_command = camera_command.replace(
            "{&imagetype}", self._image_type
        )  # Type of image being created.
        if (
            self.fast_image_capture
        ):  # Just capture the images as fast as possible, don't waste time processing anything else.
            result = self.CaptureSetFast(
                file_root,
                batch_size,
                camera_command,
                tempfile=tempfile,
                terminal=terminal,
                cleanup=cleanup,
                astrotime=astrotime,
            )
        else:  # Complete image capture and processing at the same time.
            result = self.capture_set_full(
                file_root,
                batch_size,
                camera_command,
                tempfile=tempfile,
                terminal=terminal,
                cleanup=cleanup,
                astrotime=astrotime,
            )
        return result

    def capture_set_full(
        self,
        file_root,
        batch_size,
        camera_command,
        tempfile=False,
        terminal=True,
        cleanup=True,
        astrotime=None,
    ):
        """Take a batch of photos...
        This captures and processes each image in turn.
        cleanup = True. means that intermediate files (.jpg) are deleted when finished with.
                  False. means that the intermediate files (.jpg) are retained for the calling function to deal with.
                  AstroCamera.last_jpg contains the filename of the .jpg file generated.
        tempfile = True. Means that a single temporary filename is used each time.
        terminal=True. Means that the progress message is shown on the terminal.
        astrotime = the timestamp of the image to be generated if we're faking the result.
        stacker = a handle to a live image stacker object if we're live stacking."""
        result = True
        self.log(
            "AstroCamera.capture_set_full(): Capturing "
            + str(batch_size)
            + " images...",
            terminal=False,
        )
        dt_start = now_utc()
        self.last_light_command = camera_command  # keep a note of the exposure options, it's reported in the preview images.
        for i in range(batch_size):
            # Generate unique image filename, session timestamp + incremental frame number.
            frame = str(i).zfill(
                2
            )  # Create zerofilled frame count for filename, this keeps images unique if several are taken in the same second.
            if tempfile:
                outputfile = (
                    file_root + "temp.jpg"
                )  # This is the 'intermediate' jpg generated by the camera.
            else:
                outputfile = (
                    file_root + utc_time_stamp() + "_" + frame + ".jpg"
                )  # This is the 'intermediate' jpg generated by the camera.
            self.log(
                f"AstroCamera.capture_set_full(): Capturing {outputfile} ...",
                terminal=False,
            )
            cmd = camera_command.replace(
                "{&output}", outputfile
            )  # *Q* TODO: Perform safety check for remaining & symbols.
            if "{&" in cmd:  # Some remaining tags remain which have not been replaced.
                self.log(
                    "AstroCamera.capture_set_full(): camera_command contains unconverted options.",
                    terminal=True,
                )
            if self.mctl is not None:  # Microcontroller handle is defined.
                remote_restarts = (
                    self.mctl.remote_restarts
                )  # If this changes during exposure, the microcontroller has reset and we should reject the image.
            else:
                remote_restarts = 0
            rejectimage = (
                False  # Set to 'true' if there's a reason to reject the image.
            )
            imty = self.get_image_type()  # What type of image are we faking?
            self.capture_start = now_utc()
            if self.parameters.camera_enabled:  # Camera is enabled. Take real photo.
                self.os_cmd(cmd, output="none")
                retc = (
                    self.os_command.return_code
                )  # What did the camera command exit with ?
                self.log(
                    "AstroCamera.capture_set_full(): Return code:", retc, terminal=False
                )
                if retc != 0:  # Non zero return code. Did something go wrong?
                    if self.camera_window is not None:
                        self.camera_window.print(
                            f"{now_hms()} Return code {retc}", fg=TextColor.YELLOW
                        )
                    if self.error_window is not None:
                        self.error_window.print(
                            f"{now_hms()} capture returned code {retc}",
                            fg=TextColor.YELLOW,
                        )
            else:  # Camera is not in use. Generate fake photo.
                self.log(
                    "AstroCamera.capture_set_full(): About to call fake_photo.",
                    terminal=False,
                )
                tr = False  # Fake image generation failed unless we are told otherwise.
                delay_timer = self.set_fake_delay(
                    camera_command
                )  # Create a timer to mimic the expected real camera delay.
                if imty == "dark":
                    tr = self.fake_dark(outputfile=outputfile)  # Fake a dark frame.
                else:
                    tr = self.fake_photo(
                        outputfile=outputfile, astrotime=astrotime
                    )  # Fake a light frame.
                if not tr:  # image generation failed.
                    self.log(
                        f"AstroCamera.capture_set_full(): Fake image call failed ({imty}).",
                        terminal=True,
                        level="error",
                    )
                else:  # Fake the expected exposure time if a real image was being captured.
                    delay_timer.wait()  # wait until the fake delay timer expires. Thread pauses here.
                self.log(
                    "AstroCamera.capture_set_full(): Returned from fake_photo.",
                    terminal=False,
                )
            self.capture_end = now_utc()
            self.log(
                f"AstroCamera.capture_set_full(): Capture complete. ({(self.capture_end - self.capture_start).total_seconds()}s).",
                terminal=False,
            )
            if imty in ["light"]:
                self.append_batch_data(
                    image_filename=outputfile
                )  # Record metadata about 'light' images for post-processing.
            if self.mctl is not None:  # Microcontroller handle is known.
                if (
                    remote_restarts != self.mctl.remote_restarts
                ):  # Microcontroller reset during exposure.
                    self.log(
                        f"AstroCamera.capture_set_full(): Microcontroller restarted during exposure. Reject {outputfile}",
                        level="warning",
                        terminal=False,
                    )
                    if self.camera_window is not None:
                        self.camera_window.print(
                            f"{now_hms()} Motors reset during exposure."
                        )  # Just the filename.
                    if self.error_window is not None:
                        self.error_window.print(
                            f"{now_hms()} Motors reset during exposure."
                        )  # Just the filename.
                    rejectimage = True  # We should reject this image.
            if (
                not tempfile
            ):  # Display the filename if it's permanent, ignore the tempfile.
                if self.camera_window is not None:
                    self.camera_window.print(
                        f"{now_hms()} {outputfile.split('/')[-1]}"
                    )  # Just the jpg filename.
            if rejectimage:  # There was reason to reject the image for some cause.
                self.log(
                    "AstroCamera.capture_set_full(): image should be rejected.",
                    terminal=False,
                )
            self.last_jpg = (
                outputfile  # The camera can remember this file as the 'last jpg taken'
            )
            self.log(
                "AstroCamera.capture_set_full(): Load image buffer from",
                outputfile,
                terminal=False,
            )
            self.image.load_file(outputfile)  # OpenCV format.
            if (
                self.image.image_missing()
            ):  # imread failed. The capture did not succeed for some reason?
                self.log(
                    f"AstroCamera.capture_set_full(): imread of {outputfile} failed.",
                    level="error",
                    terminal=False,
                )
            # *Q* This timestamp is AFTER the image has been captured. Can it be estimated better? capture_start + (CaptureEnd - capture_start) / 2 ?
            self.last_image_datetime = now_utc()
            self.log("AstroCamera.capture_set_full(): image loaded.", terminal=False)

            # The jpg contains RAW data in the file tags, extract it. Convert it.
            if (
                " -r " in (camera_command + " ") or " --raw " in (camera_command + " ")
            ) and self.parameters.camera_enabled:
                # We need to manually extract the DNG data.
                if self.parameters.camera_driver == "raspistill":
                    # with raspistill convert to RAW. We have to extract the raw data RAW for .dng files to be saved.
                    self.log(
                        "AstroCamera.capture_set_full(): Converting to RAW (.DNG) file...",
                        terminal=False,
                    )
                    dngname = outputfile.replace(".jpg", ".dng")
                    try:
                        # Convert the saved .jpg file into the raw .dng format.
                        self.PiDNG.convert(outputfile)
                    except Exception as e:  # pylint: disable=broad-except
                        self.report_exception(
                            e,
                            comment="AstroCamera.capture_set_full(): PiDNG.convert failed.",
                        )
                    self.log(
                        "AstroCamera.capture_set_full(): Converted to RAW (.DNG) file.",
                        terminal=False,
                    )
                    # Cleanup. Remove any intermediate files that are nolonger needed.
                    # We should save only the jpg data, stripping out any embedded additional RAW data
                    if self.camera_save_jpg:
                        # Save the JPG file, but remove the 'raw' data. This overwrites the original file generated by raspistill.
                        self.image.save_file(outputfile)
                    # We're only saving the RAW data, so just delete the original jpg file.
                    else:
                        self.log(
                            "AstroCamera.capture_set_full(): Deleting intermediate .jpg file...",
                            terminal=False,
                        )
                        self.cleanup_last_jpg()  # We've finished with the original .jpg on disc.
                    # We don't need to keep the .dng file anymore.
                    if not self.camera_save_dng:
                        self.log(
                            "AstroCamera.capture_set_full(): DNG nolonger needed.",
                            terminal=False,
                        )
                        cmd = "rm " + dngname
                        self.os_cmd(cmd, output="log")
                    else:
                        if self.camera_window is not None:
                            # Just the dng filename.
                            self.camera_window.print(
                                f"{now_hms()} {dngname.split('/')[-1]}"
                            )
                # The .fits file will have been made automatically for us.
                elif self.parameters.camera_driver == "pilomarfits":
                    # Construct the .fits filename we expect.
                    fitsname = outputfile.replace(".jpg", ".fits")
                    self.log(
                        "AstroCamera.capture_set_full(): FITS file should have been generated too.",
                        terminal=False,
                    )
                    if self.camera_window is not None:
                        # Just the dng filename.
                        self.camera_window.print(
                            f"{now_hms()} {fitsname.split('/')[-1]}"
                        )
            # Delete the temporary file.
            if tempfile:
                self.log(
                    "AstroCamera.capture_set_full(): Remove temporary outputfile",
                    outputfile,
                    terminal=False,
                )
                cmd = "rm " + outputfile
                self.os_cmd(cmd, output="log")
            # Estimate ETA. If we're looping through a batch of photos.
            if batch_size > 1:
                dt_now = now_utc()  # Current time.
                td_elapsed = dt_now - dt_start  # Elapsed time.
                # Estimate completion time.
                dt_eta = dt_start + (batch_size * td_elapsed / (i + 1))
                # Estimate how far through the batch of photos we are
                pc_complete = int(100 * (i + 1.0) / batch_size)
                if self.storage_monitor is not None:
                    self.log(
                        f"AstroCamera.capture_set_full: {i + 1} of {batch_size} ({pc_complete}%), Disc: {int(self.storage_monitor.FreeMegaBytes())}Mb, ETA: {str(dt_eta).split(' ')[1].split('.')[0]}",
                        terminal=terminal,
                    )
                else:
                    self.log(
                        f"AstroCamera.capture_set_full: {i + 1} of {batch_size} ({pc_complete}%), Disc: UNKNOWN, ETA: {str(dt_eta).split(' ')[1].split('.')[0]}",
                        terminal=terminal,
                    )
                # If we have more photographs to process, keep the cursor on the same line so that the status line updates neatly.
                if i < batch_size - 1:
                    # Stay on the same line for the CaptureSet message to the terminal.
                    print(TextColor.cursorup() + TextColor.cursorup())
            # Check there is enough disc space to continue.
            if self.storage_monitor is not None and not self.storage_monitor.DiscOK():
                # Out of free space, stop!
                self.log(
                    "AstroCamera.capture_set_full(): Out of disc space. Stopping.",
                    level="error",
                )
                result = False
                break
        self.log("AstroCamera.capture_set_full(): Completed", terminal=False)
        return result

    def capture_set_fast(
        self,
        file_root,
        batch_size,
        camera_command,
        tempfile=False,
        terminal=True,
        cleanup=True,
        astrotime=None,
    ):
        """Take a batch of photos...
        This just captures the combined JPG & DNG data file.
        It does not perform conversion to other file types.
        This is testing if it improves performance for image
        capture by delaying processing until the observation is over.

        cleanup = True. means that intermediate files (.jpg) are deleted when finished with.
                  False. means that the intermediate files (.jpg)
                  are retained for the calling function to deal with.
                  AstroCamera.last_jpg contains the filename of the .jpg file generated.
        tempfile = True. Means that a single temporary filename is used each time.
        terminal=True. Means that the progress message is shown on the terminal.
        astrotime = the timestamp of the image to be generated if we're faking the result.
        stacker = a handle to a live image stacker object if we're live stacking."""
        result = True
        self.log(
            "AstroCamera.capture_set_fast(): Capturing "
            + str(batch_size)
            + " images...",
            terminal=False,
        )
        dt_start = now_utc()
        self.last_light_command = camera_command  # keep a note of the exposure options, it's reported in the preview images.
        for i in range(batch_size):
            # Generate unique image filename, session timestamp + incremental frame number.
            frame = str(i).zfill(
                2
            )  # Create zerofilled frame count for filename, this keeps images unique if several are taken in the same second.
            if tempfile:
                outputfile = (
                    file_root + "temp.jpg"
                )  # This is the 'intermediate' jpg generated by the camera.
            else:
                outputfile = (
                    file_root + utc_time_stamp() + "_" + frame + ".jpg"
                )  # This is the 'intermediate' jpg generated by the camera.
            self.log(
                "AstroCamera.CaptureSetFast(): Capturing",
                outputfile,
                "...",
                terminal=False,
            )
            cmd = camera_command.replace(
                "{&output}", outputfile
            )  # *Q* TODO: Perform safety check for remaining & symbols.
            if (
                "{&" in camera_command
            ):  # Some remaining tags remain which have not been replaced.
                self.log(
                    "AstroCamera.capture_set_full(): camera_command contains unconverted options.",
                    terminal=True,
                )
            if self.mctl is not None:  # Microcontroller handle is defined.
                # If this changes during exposure, the microcontroller has reset and we should reject the image.
                remote_restarts = self.mctl.remote_restarts
            else:
                remote_restarts = 0
            rejectimage = (
                False  # Set to 'true' if there's a reason to reject the image.
            )
            self.capture_start = now_utc()
            if self.parameters.camera_enabled:  # Camera is in use. Take real photo.
                self.os_cmd(cmd, output="none")
                # What did the camera command exit with ?
                retc = self.os_command.return_code
                self.log(
                    "AstroCamera.capture_set_fast(): Return code:", retc, terminal=False
                )
                if retc != 0:  # Non zero return code. Did something go wrong?
                    if self.camera_window is not None:
                        self.camera_window.print(
                            f"{now_hms()} Return code {retc}", fg=TextColor.YELLOW
                        )
                    if self.error_window is not None:
                        self.error_window.print(
                            f"{now_hms()} capture returned code {retc}",
                            fg=TextColor.YELLOW,
                        )
            else:  # Camera is not in use. Generate fake photo.
                self.log(
                    "AstroCamera.capture_set_fast(): About to call fake_photo.",
                    terminal=False,
                )
                tr = False  # Fake image generation failed unless we are told otherwise.
                imty = self.get_image_type()  # What type of image are we faking?
                # Create a timer to mimic the expected real camera delay.
                delay_timer = self.set_fake_delay(camera_command)
                if imty == "dark":
                    # Fake a dark frame.
                    tr = self.fake_dark(outputfile=outputfile)
                else:
                    # Fake a light frame.
                    tr = self.fake_photo(outputfile=outputfile, astrotime=astrotime)
                # image generation failed.
                if not tr:
                    self.log(
                        f"AstroCamera.capture_set_fast(): Fake image call failed ({imty}).",
                        terminal=True,
                        level="error",
                    )
                else:  # Fake the expected exposure time if a real image was being captured.
                    delay_timer.wait()  # wait until the fake delay timer expires. Thread pauses here.
                self.log(
                    "AstroCamera.capture_set_fast(): Returned from fake_photo.",
                    terminal=False,
                )
            self.capture_end = now_utc()
            self.log(
                "AstroCamera.capture_set_fast(): Capture complete. (",
                (self.capture_end - self.capture_start).total_seconds(),
                "s).",
                terminal=False,
            )
            # Microcontroller handle is known.
            if self.mctl is not None:
                # Microcontroller reset during exposure.
                if remote_restarts != self.mctl.remote_restarts:
                    self.log(
                        "AstroCamera.capture_set_fast(): Microcontroller restarted during exposure. Reject",
                        outputfile,
                        level="warning",
                        terminal=False,
                    )
                    # Just the filename.
                    if self.camera_window is not None:
                        self.camera_window.print(
                            f"{now_hms()} Motors reset during exposure."
                        )
                    # Just the filename.
                    if self.error_window is not None:
                        self.error_window.print(
                            f"{now_hms()} Motors reset during exposure."
                        )
                    rejectimage = True  # We should reject this image.
            # Display the filename if it's permanent, ignore the tempfile.
            if not tempfile:
                if self.camera_window is not None:
                    # Just the jpg filename.
                    self.camera_window.print(f"{now_hms()} {outputfile.split('/')[-1]}")
            if rejectimage:  # There was reason to reject the image for some cause.
                self.log(
                    "AstroCamera.CaptureSetFast(): image should be rejected.",
                    terminal=False,
                )
            # The camera can remember this file as the 'last jpg taken'
            self.last_jpg = outputfile
            self.log(
                "AstroCamera.CaptureSetFast(): Load image from " + outputfile,
                terminal=False,
            )
            # imread failed. The capture did not succeed for some reason?
            if self.image.load_file(outputfile):
                self.log(
                    f"AstroCamera.CaptureSetFast(): imread of {outputfile} failed.",
                    terminal=False,
                )
            # *Q* This timestamp is AFTER the image has been captured. Can it be estimated better? capture_start + (CaptureEnd - capture_start) / 2 ?
            self.last_image_datetime = now_utc()
            self.log("AstroCamera.CaptureSetFast(): image loaded.", terminal=False)
            # Estimate ETA. If we're looping through a batch of photos.
            if batch_size > 1:
                dt_now = now_utc()  # Current time.
                td_elapsed = dt_now - dt_start  # Elapsed time.
                dt_eta = dt_start + (
                    batch_size * td_elapsed / (i + 1)
                )  # Estimate completion time.
                pc_complete = int(
                    100 * (i + 1.0) / batch_size
                )  # Estimate how far through the batch of photos we are.
                if self.storage_monitor is not None:
                    self.log(
                        f"AstroCamera.CaptureSetFast(): {i + 1} of {batch_size} ({pc_complete}%), Disc: {int(self.storage_monitor.FreeMegaBytes())}Mb, ETA: {str(dt_eta).split(' ')[1].split('.')[0]}",
                        terminal=terminal,
                    )
                else:
                    self.log(
                        f"AstroCamera.CaptureSetFast(): {i + 1} of {batch_size} ({pc_complete}%), Disc: UNKNOWN, ETA: {str(dt_eta).split(' ')[1].split('.')[0]}",
                        terminal=terminal,
                    )
                if (
                    i < batch_size - 1
                ):  # If we have more photographs to process, keep the cursor on the same line so that the status line updates neatly.
                    print(
                        TextColor.cursorup() + TextColor.cursorup()
                    )  # Stay on the same line for the CaptureSet message to the terminal.
            if (
                self.storage_monitor is not None and not self.storage_monitor.DiscOK()
            ):  # Check there is enough disc space to continue.
                # Out of free space, stop!
                self.log(
                    "AstroCamera.CaptureSetFast(): Out of disc space. Stopping.",
                    level="error",
                )
                result = False
                break
        self.log("AstroCamera.CaptureSetFast(): Completed", terminal=False)
        return result

    def datetime_from_filename(self, filename):
        """Construct a datetime value from a filename.
        eg "light_YYYYMMDDHHMMSS_nn.jpg" """
        filename = filename.split("/")[-1]  # Get file from full path.
        filename = filename.split("_")[1]  # Get the timestamp from full path.
        year = int(filename[:4])
        month = int(filename[4:6])
        day = int(filename[6:8])
        hour = int(filename[8:10])
        minute = int(filename[10:12])
        second = int(filename[12:14])
        dt = datetime(year, month, day, hour, minute, second, 0, tzinfo=timezone.utc)
        return dt

    def build_keogram(self, altitude=None, azimuth=None):
        """Build keogram for current /light folder contents.
        This extracts data from all /light_*.jpg files found in the folder.
        It creates a temporary instance of PilomarKeogram() to process the data.
        At the end it saves a /keogram.jpg file in the same /light folder."""
        self.log("AstroCamera.build_keogram(): Starting", terminal=False)
        rootfolder = self.folder_handler.get_path(
            "light"
        )  # This is the parent data folder for all Pilomar images.
        filepattern = rootfolder + "/light_*.jpg"
        self.log("AstroCamera.build_keogram(): Searching", filepattern, terminal=False)
        allfiles = glob.glob(filepattern, recursive=False)  # Every jpg in this folder.
        filecount = len(allfiles)
        start = None  # Earliest image.
        end = None  # Latest image.
        if len(allfiles) > 0:
            keogramfile = self.folder_handler.prep_file(
                "light", "keogram.jpg"
            )  # target filename.
            prgt = ProgressTimer(
                "keogram", target=filecount
            )  # Report progress and ETA.
            self.log(
                "AstroCamera.build_keogram(): Processing",
                filecount,
                "images.",
                terminal=False,
            )
            print(" ")
            Keo = PilomarKeogram(
                "keogram", self.sensor.pixel_width, self.sensor.pixel_height
            )  # Define new Keogram instance.
            imagehandler = PilomarImage(
                "keogram-input", logger=self.logger
            )  # Load each image in turn.
            for i, file in enumerate(allfiles):  # Go through all the .jpg files found.
                prgt.update_count(
                    i + 1
                )  # How far have we got so far? prgt will then produce ETA and % complete for us.
                self.log(
                    "AstroCamera.build_keogram(): Processing", file, terminal=False
                )
                # print(TextColor.cursorup() +
                #      NowHMS(),
                #      TextColor.white(str(round(prgt.GetPercent(),1))),"%",
                #      (i + 1),"of",filecount,
                #      "ETA",str(prgt.GetETA()).split('.')[0],
                #      "UTC",TextColor.clearlineforward())
                print(
                    prgt.MakeProgressBar(
                        color=True, text="", length=20, show_start=True, show_eta=True
                    )
                )
                dt = self.datetime_from_filename(
                    file
                )  # Get the UTC timestamp of the image from the filename.
                if dt is not None:
                    if start is None or start > dt:
                        start = dt
                    if end is None or end < dt:
                        end = dt
                imagehandler.load_file(file)
                Keo.Extract(imagehandler)
            # Markup image.
            Keo.BuildImageBuffer()  # Load the resulting raw keogram into a PilomarImage instance. (For markup) Refer to it as "Keo.Keogram.{PilomarImage methods/attributes}"
            width = Keo.Keogram.GetWidth()
            height = Keo.Keogram.GetHeight()
            # Add altitude scale
            BaseAlt = altitude - (
                self.lens.fov_vertical / 2
            )  # What altitude does the bottom of the image represent?
            TopAlt = altitude + (
                self.lens.fov_vertical / 2
            )  # What altitude does the top of the image represent?
            FloorAlt = math.floor(
                BaseAlt
            )  # Lowest integer altitude, will be just below the bottom edge of the image.
            CeilingAlt = math.ceil(
                TopAlt
            )  # Heighest integer altitude, will be just above the top edge of the image.
            Keo.Keogram.DrawLine(
                (width - 10, 0), (width - 10, height), color=PilomarImage.BGR("Yellow")
            )  # Draw axis for altitude tick marks.
            Keo.Keogram.AddText(
                "Altitude", width - 10, 40, color=PilomarImage.BGR("Yellow"), hjust="r"
            )  # Label the altitude axis.
            for a in range(FloorAlt, CeilingAlt):  # Mark off each degree of altitude.
                y = height - int(
                    height * (a - BaseAlt) / (TopAlt - BaseAlt)
                )  # Pixel height up the image for this degree marker.
                Keo.Keogram.DrawLine(
                    (width - 50, y), (width - 10, y), color=PilomarImage.BGR("Yellow")
                )  # Draw tickmark for the degree marker.
                Keo.Keogram.AddText(
                    str(a) + "deg",
                    width - 50,
                    y,
                    color=PilomarImage.BGR("Yellow"),
                    hjust="r",
                )  # Label the degree marker.
            if len(allfiles) > 1:  # Need at least 2 files in order to add time scale.
                Keo.Keogram.DrawLine(
                    (0, height - 10),
                    (width, height - 10),
                    color=PilomarImage.BGR("Cyan"),
                )  # Draw horizontal axis for the time scale.
                Keo.Keogram.AddText(
                    "<-" + str(start)[11:19],
                    10,
                    height - 130,
                    color=PilomarImage.BGR("Cyan"),
                    hjust="l",
                )  # Mark START time.
                Keo.Keogram.AddText(
                    str(end)[11:19] + "->",
                    width - 10,
                    height - 130,
                    color=PilomarImage.BGR("Cyan"),
                    hjust="r",
                )  # Mark END time.
                Keo.Keogram.AddText(
                    "< Time >",
                    int(width / 2),
                    height - 10,
                    color=PilomarImage.BGR("Cyan"),
                    vjust="t",
                    hjust="c",
                )  # Label the axis.
                # Add time scale
                FloorTime = datetime(
                    start.year,
                    start.month,
                    start.day,
                    start.hour,
                    0,
                    0,
                    0,
                    tzinfo=timezone.utc,
                )  # Hour just before observation starts (Just off the left of the image)
                CeilingTime = datetime(
                    end.year, end.month, end.day, end.hour, 0, 0, 0, tzinfo=timezone.utc
                ) + timedelta(
                    hours=1
                )  # Hour just after observation ends (Just off the right of the image)
                RangeTime = int(
                    (CeilingTime - FloorTime).total_seconds()
                )  # What's the timespan of the Floor to Ceiling time (in seconds).
                ObservationTime = int(
                    (end - start).total_seconds()
                )  # What's the timespan of the actual observation images (in seconds).
                PixelsPerSecond = (
                    width / ObservationTime
                )  # How many pixels represent 1 second of time?
                x_offset = (
                    start - FloorTime
                ).total_seconds() * PixelsPerSecond  # Calculate a pixel offset for the time scale, it will start at FloorTime to the left of the image.
                if ObservationTime > 7200:
                    RangeStep = (
                        3600  # If observation is > 2hrs, label the Hourly tickmarks.
                    )
                elif ObservationTime > 1200:
                    RangeStep = 600  # If Observation is > 20 minutes, label in 10 minute tickmarks.
                else:
                    RangeStep = 300  # Label in 5 minute tickmarks.
                for a in range(0, RangeTime, RangeStep):  # Mark significant time steps.
                    x = int(
                        a * PixelsPerSecond - x_offset
                    )  # X axis location for the tickmark.
                    Keo.Keogram.DrawLine(
                        (x, height - 10),
                        (x, height - 100),
                        color=PilomarImage.BGR("Cyan"),
                    )  # Draw tickmark.
                    text = str(FloorTime + timedelta(seconds=a))[
                        11:19
                    ]  # Calculate HH:MM:SS time of the tickmark.
                    Keo.Keogram.AddText(
                        text, x, height - 100, color=PilomarImage.BGR("Cyan"), hjust="c"
                    )  # Label the tickmark with the HH:MM:SS time.
            # Add key/labels
            linelist = []  # Start assembling a block of text.
            linelist.append("Observation start: " + str(start).split("+")[0] + " UTC")
            linelist.append("Observation end: " + str(end).split("+")[0] + " UTC")
            if start is not None and end is not None:
                linelist.append(
                    "Duration: " + self.HRSeconds((end - start).total_seconds())
                )
            linelist.append("Images captured: " + str(Keo.SampleCount))
            linelist.append("target alt: " + str(altitude) + ", az:" + str(azimuth))
            if altitude is not None:
                linelist.append(
                    "Altitude range: "
                    + str(round(BaseAlt, 1))
                    + "deg to "
                    + str(round(TopAlt, 1))
                    + "deg"
                )
            ypos = 50  # Text box at TOP of image.
            Keo.Keogram.AddTextBlock(
                linelist,
                20,
                ypos,
                size=1,
                color=PilomarImage.BGR("White"),
                bgcolor=PilomarImage.BGR("Black"),
                border=3,
            )  # Write data.
            # Save resulting image.
            Keo.save_file(keogramfile)
        print("")  # Move cursor down so that the stats can be seen.
        return True

    def ProcessImageFiles(self):
        """If image conversions were not done during capture, this can find and convert all the
        image files currently in storage. This is used if CaptureSetFast was used to gather
        images as quickly as possible.
        This will convert all image files found the have the characteristics of a jpg with embedded raw data.
        """
        self.log("AstroCamera.ProcessImageFiles(): Starting", terminal=True)
        rawfilesize = (
            1024 * 1024 * 20
        )  # Files containing raw data are quite large, set the threshold at 20Mb
        # Find all image files that need converting.
        rootfolder = self.folder_handler.get_path(
            "imageroot"
        )  # This is the parent data folder for all Pilomar images.
        # allfiles = glob.glob(rootfolder + '**/*.jpg', recursive=True) # Every jpg in every folder and subfolder.
        filepattern = rootfolder + "/**/*.jpg"
        self.log(
            "AstroCamera.ProcessImageFiles(): Searching", filepattern, terminal=True
        )
        allfiles = glob.glob(
            filepattern, recursive=True
        )  # Every jpg in every folder and subfolder.
        files = []  # Cleaned list of files to handle.
        folders = [
            "/flat/",
            "/bias/",
            "/light/",
            "/darkflat/",
            "/dark/",
        ]  # Which subfolders do we want?
        for file in allfiles:  # Go through all the .jpg files found.
            for folder in folders:  # Check all the image folder/types.
                if (
                    folder in file
                ):  # This is an image/type that we should consider converting.
                    # How big is the file? Large ones need converting.
                    if (
                        os.stat(file).st_size > rawfilesize
                    ):  # File is large enough to convert.
                        files.append(file)  # Add to list of files to process.
                    break  # No need to check anything else in the folder list.
        # Convert them.
        filecount = len(files)
        self.log(
            "AstroCamera.ProcessImageFiles(): Found",
            filecount,
            "files to process.",
            terminal=True,
        )
        tempimage = PilomarImage(name="temp", logger=self.logger)
        if filecount > 0:
            for file in files:
                print(file)
                # Load jpg data into temporary buffer.
                tempimage.load_file(file)
                if tempimage.image_missing():  # imread failed.
                    self.log(
                        "AstroCamera.ProcessImageFiles: imread",
                        file,
                        "failed.",
                        terminal=False,
                    )
                else:  # imread was successful.
                    self.log(
                        "AstroCamera.ProcessImageFiles: Converting to RAW (.DNG) file...",
                        terminal=False,
                    )
                    if (
                        self.camera_save_dng
                    ):  # We don't need to keep the .dng file anymore.
                        try:
                            self.PiDNG.convert(
                                file
                            )  # Convert the saved .jpg file into the raw .dng format. The .dng filename is automatically generated.
                        except Exception as e:
                            CamLog.report_exception(
                                e,
                                comment="AstroCamera.ProcessImageFiles() error when converting to DNG file.",
                            )
                    # Replace the .jpg file with a simpler file, or delete it completely.
                    if (
                        self.camera_save_jpg
                    ):  # We should save 'JUST' the jpg data, effectively stripping out the embedded RAW data
                        tempimage.save_file(
                            file
                        )  # Save the JPG file, but remove the 'raw' data. This overwrites the original file generated by raspistill.
                    else:  # We're only saving the RAW data, so just delete the original jpg file.
                        self.log(
                            "AstroCamera.ProcessImageFiles: Deleting intermediate .jpg file...",
                            terminal=False,
                        )
                        cmd = "rm " + file
                        self.os_cmd(cmd, output="log")
        else:
            print(TextColor.yellow("No suitable unprocessed files were found."))
            print(
                "- There is no RAW data in simulated images (Is the camera disabled?)"
            )
            print("- There must still be observation images on disc to process.")
        self.log("AstroCamera.ProcessImageFiles(): Done", terminal=True)
        return True

    def ClearCameraOptions(self):
        """Clear the camera options list."""
        self.log("AstroCamera.ClearCameraOptions", terminal=False)
        self.CameraOptions = ""  # Empty the options list.

    def AddCameraOption(self, NewOption):
        """Add an option to the camera option list.
        This gives possibility to validate options as they are added."""
        self.log("AstroCamera.AddCameraOption:", NewOption, terminal=False)
        NewOption = (
            NewOption.strip(" ") + " "
        )  # Make sure there's a single separator character after the option.
        NewKey = NewOption.split(" ")[0]  # What is the option key we are setting?
        # Split all the existing options into a list.
        OptionListEntries = self.CameraOptions.split("-")
        for OLE in OptionListEntries:
            OLE = "-" + OLE  # Add the lost '-' tag back to each entry.
        found = False
        # If the option is already in the list, update it to the new value.
        for OLE in OptionListEntries:
            if OLE.split(" ")[0] == NewKey:
                found = True
                OLE = NewOption
                break
        if not found:  # If the option is NOT in the list, add it now.
            OptionListEntries.append(NewOption)
        # Construct the new version of the option list ready for returning.
        self.CameraOptions = ""
        for OLE in OptionListEntries:
            self.CameraOptions += OLE
        self.log(
            "AstroCamera.AddCameraOption: New list:", self.CameraOptions, terminal=False
        )

    def DelCameraOption(self, DelOption):
        """Remove an option from the camera option list."""
        self.log("AstroCamera.DelCameraOption:", DelOption, terminal=False)
        DelKey = DelOption.split(" ")[0]  # What is the option key we are setting?
        # Split all the existing options into a list.
        OptionListEntries = self.CameraOptions.split("-")
        for OLE in OptionListEntries:
            OLE = "-" + OLE  # Add the lost '-' tag back to each entry.
        # Construct the new version of the option list ready for returning but ignore the deleted option.
        self.CameraOptions = ""
        for OLE in OptionListEntries:
            if OLE.split(" ")[0] != DelKey:
                self.CameraOptions += OLE
        self.log(
            "AstroCamera.DelCameraOption: New list:", self.CameraOptions, terminal=False
        )

    # def ContainsMeteors(self,image): # In PilomarImage
    #    """ Return TRUE if meteors or aircraft trails are detected in an image. """
    #    if len(self.LineDetection(image)) > 0: return True
    #    else: return False

    def TakePhoto(self, batch_size, terminal=True):
        """Make an observation. This is a LIGHT image of the actual object under observation."""
        self.log("AstroCamera.TakePhoto: Begin", terminal=False)
        ExposureMicroseconds = int(self.ExposureSeconds * 1000000)
        self.set_image_type("light")  # Tell the camera we are taking light photos.
        FileRoot = self.folder_handler.prep_file("light", "light_")
        # raspistill -o {&output} -ex off -t 10 -n -q 100 -md {&mode} -w {&width} -h {&height} -ag 16.0 -ss {&shutter}
        # libcamera-still --output {&output} --timeout 10 --nopreview --quality 100 --width {&width} --height {&height} --denoise off --analoggain 16.0 --shutter {&shutter}
        # python3 pilomarfits.py --output {&output} --quality 100 --width {&width} --height {&height} --denoise off --shutter {&shutter}
        camera_command = self.parameters._camera_light_command
        camera_command = camera_command.replace(
            "{&shutter}", str(int(ExposureMicroseconds))
        )
        # CaptureSet will automatically set mode,width and height parameters if they are in the command line.
        if (
            self.camera_save_dng or self.camera_save_fits
        ):  # If we intend to produce DNG/FITS raw data at some point, we need to capture the bayer matrix.
            camera_command += (
                " " + self.parameters._CameraRawSwitch + " "
            )  # Append RAW data to the image.
        result = self.capture_set(
            file_root=FileRoot,
            batch_size=batch_size,
            camera_command=camera_command,
            terminal=terminal,
            cleanup=False,
        )
        if not result:
            self.log("AstroCamera.TakePhoto: CaptureSet failed.", level="error")
        self.log("AstroCamera.TakePhoto: Complete", terminal=False)
        return result

    def PromptPhotoSettings(self, batch_size, terminal=True):
        """Take a single image, but prompt the user for the settings."""
        self.log("AstroCamera.PromptPhotoSettings: Begin", terminal=False)
        ExposureMicroseconds = int(self.ExposureSeconds * 1000000)
        self.set_image_type("light")  # Tell the camera we are taking light photos.
        FileRoot = self.folder_handler.prep_file("light", "light_")
        CameraOptions = ""
        if (
            self.parameters.camera_driver == "raspistill"
        ):  # Prompt for raspistill format options.
            CameraOptions += "-ex off "  # Exposure control off.
            CameraOptions += "-t 10 "  # Timeout ms - This is an attempt to take the photo as fast as possible, but pre-photo calculations double the requested time :(
            CameraOptions += "-n "  # Nopreview
            CameraOptions += (
                "-md " + str(self.sensor.mode) + " "
            )  # mode 3 allows exposures over 10.2 seconds apparently.
            CameraOptions += (
                "-w " + str(self.sensor.pixel_width) + " "
            )  # Specify the pixel size of the image to match the maximum that the mode supports.
            CameraOptions += (
                "-h " + str(self.sensor.pixel_height) + " "
            )  # Specify the pixel size of the image to match the maximum that the mode supports.
            CameraOptions += (
                "-ss " + str(ExposureMicroseconds) + " "
            )  # Use the global SHUTTER time to match the DARK and LIGHT frames.
            if (
                self.camera_save_dng and "-r " not in CameraOptions
            ):  # If we intend to produce DNG raw data at some point, we need to capture the bayer matrix.
                # *Q* Expand for FITS files too.
                CameraOptions += (
                    "-r "  # Raw is appended to JPEG file. Needs extracting later.
                )
            CameraOptions += "-ag 16.0 "  # Set analog gain to 16.0. Apparently this is better for Astro photographs as it increases signal-to-noise ratio significantly.
        else:
            self.log(
                "AstroCamera.PromptPhotoSettings: Only supports raspistll at the moment.",
                terminal=True,
                level="warning",
            )  # *Q* Add support for other drivers.
            return False
        # Offer the default settings to the user, but let them enter something else.
        print(
            "PromptPhotoSettings: [ENTER] to accept default settings or create your own."
        )
        print(self.parameters.camera_driver + " " + CameraOptions)
        newopt = input(TextColor.cyan(self.parameters.camera_driver + " "))
        if len(newopt) > 0:  # User chose to overwrite the default settings.
            CameraOptions = newopt
            self.log("AstroCamera.PromptPhotoSettings:", CameraOptions, terminal=True)
        self.LastLightOptions = CameraOptions  # keep a note of the exposure options, it's reported in the preview images.
        result = self.capture_set(
            file_root=FileRoot,
            batch_size=batch_size,
            camera_options=CameraOptions,
            terminal=terminal,
            cleanup=False,
        )
        if not result:
            self.log(
                "AstroCamera.PromptPhotoSettings: CaptureSet failed.", level="error"
            )
        else:
            self.log("Photo captured as:", self.last_jpg, terminal=True)
        self.log("AstroCamera.PromptPhotoSettings: Complete", terminal=False)
        return result

    def MeteorFileScan(self):
        """If image conversions were not done during capture, this can find and convert all the
        image files currently in storage. This is used if CaptureSetFast was used to gather
        images as quickly as possible.
        This will convert all image files found the have the characteristics of a jpg with embedded raw data.
        """
        self.log("AstroCamera.MeteorFileScan(): Starting", terminal=True)
        # Find all image files that need converting.
        rootfolder = self.folder_handler.get_path(
            "imageroot"
        )  # This is the parent data folder for all Pilomar images.
        self.log(
            "AstroCamera.MeteorFileScan(): Searching for .jpgs in",
            rootfolder,
            terminal=True,
        )
        allfiles = glob.glob(
            rootfolder + "/**/*.jpg", recursive=True
        )  # Every jpg in every folder and subfolder.
        files = []  # Cleaned list of files to handle.
        folders = ["light"]  # Which subfolders do we want?
        candidatefilename = self.folder_handler.prep_file(
            "imageroot", "MeteorCandidates_" + utc_timestamp() + ".txt"
        )
        for file in allfiles:  # Go through all the .jpg files found.
            for folder in folders:  # Check all the image folder/types.
                temp = (
                    "/" + folder + "/" + folder + "_"
                )  # Key to an image file we are interested in.
                if (
                    temp in file
                ):  # This is an image/type that we should consider converting.
                    files.append(file)  # Add to list of files to process.
                    break  # No need to check anything else in the list.
        # Convert them.
        filecount = len(files)
        MeteorFiles = []  # Resulting list of meteor files.
        self.log(
            "AstroCamera.MeteorFileScan(): Found",
            filecount,
            "files to process.",
            terminal=True,
        )
        print(" ")  # Blank line for incremental counter to occupy.
        if filecount > 0:
            tempimage = PilomarImage(name="temp", logger=self.logger)
            for i, file in enumerate(files):
                # Check for EXIT from keyboard.
                kcl = self.Keyboard.Check().lower()
                if kcl in ["x", chr(27)]:  # Exit key pressed.
                    print("")
                    print("** Quit **")
                    break
                print(
                    TextColor.cursorup() + TextColor.clearforward() + now_hms(),
                    "Scanning",
                    (i + 1),
                    "of",
                    filecount,
                    "(" + file.split("/")[-1] + ")",
                    "Found",
                    len(MeteorFiles),
                    "candidates,",
                )
                # Load jpg data into temporary buffer.
                tempimage.load_file(file)
                if tempimage.image_missing():  # imread failed.
                    self.log(
                        "AstroCamera.ProcessImageFiles: imread",
                        file,
                        "failed.",
                        terminal=False,
                    )
                else:  # imread was successful.
                    if (
                        len(tempimage.LineDetection()) > 0
                    ):  # Potential meteor lines were found.
                        self.log(
                            file, "potentially contains meteor trail.", terminal=True
                        )
                        MeteorFiles.append(
                            file
                        )  # Add to list of files containing potential meteor trails. (Could be aircraft or satellites too).
        else:  # Filecount == 0
            print(TextColor.yellow("No suitable image files were found."))
        self.log(
            "Found potential meteor trails in",
            len(MeteorFiles),
            "of",
            len(files),
            "images",
            terminal=True,
        )
        if len(MeteorFiles) > 0:  # Write file of candidates.
            with open(candidatefilename, "w") as f:
                for file in MeteorFiles:
                    f.write(file + "\n")
            self.log("Candidate filenames written to", candidatefilename, terminal=True)
        self.log("AstroCamera.MeteorFileScan(): Done", terminal=True)
        return MeteorFiles  # List of candidate files.

    def TakeTrackingPhoto(self, batch_size, terminal=True):
        """Make an observation. This is a TRACKING image of the actual object under observation.
        Similar to TakePhoto, except the exposure is fixed to give a more consistent star count for image matching.
        """
        self.log("AstroCamera.TakeTrackingPhoto: Begin", terminal=False)
        ExposureMicroseconds = self.TrackingExposureSeconds * 1000000
        self.set_image_type(
            "tracking"
        )  # Tell the camera we are taking tracking photos.
        FileRoot = self.folder_handler.prep_file("tracking", "tracking_")
        camera_command = self.parameters._CameraTrackingCommand
        # CaptureSet will automatically set mode,width and height parameters if they are in the command line.
        camera_command = camera_command.replace(
            "{&shutter}", str(int(ExposureMicroseconds))
        )
        result = self.capture_set(
            file_root=FileRoot,
            batch_size=batch_size,
            camera_command=camera_command,
            tempfile=True,
            terminal=terminal,
            cleanup=False,
        )
        self.log("AstroCamera.TakeTrackingPhoto: Complete", terminal=False)
        return result

    def DarkSet(self, batch_size):
        """Take a DARK set of images for photo stacking."""
        print(TextColor.yellow("DarkSet"))
        ExposureMicroseconds = int(self.ExposureSeconds * 1000000)
        self.set_image_type("dark")  # Tell the camera we are taking dark photos.
        FileRoot = self.folder_handler.prep_file("dark", "dark_")
        self.log("Generating DARK image set of", batch_size, "images.")
        self.log(
            "These match the LIGHT exposure time of", self.ExposureSeconds, "seconds."
        )
        self.log("These are used to remove electrical noise from the images.")
        self.log("Lens cap must be ON.")
        self.log(batch_size, "Images will be stored in", FileRoot)
        input(TextColor.cyan("[RETURN] to begin: "))  # Python3
        print("Capturing Dark image set...")
        camera_command = self.parameters._CameraDarkCommand
        # CaptureSet will automatically set mode,width and height parameters if they are in the command line.
        camera_command = camera_command.replace(
            "{&shutter}", str(int(ExposureMicroseconds))
        )
        if (
            self.camera_save_dng or self.camera_save_fits
        ):  # If we intend to produce DNG raw data at some point, we need to capture the bayer matrix.
            camera_command += (
                " " + self.parameters._CameraRawSwitch + " "
            )  # Append RAW data to the image.
        result = self.capture_set(
            file_root=FileRoot, batch_size=batch_size, camera_command=camera_command
        )
        return result

    def ImageTypes(self):
        """Return a text list of image types being captured."""
        result = ""
        if self.camera_save_jpg:
            result += "jpg,"
        if self.camera_save_dng:
            result += "dng,"
        if self.camera_save_fits:
            result += "fits,"
        result = result.strip(",")
        return result

    def DarkFlatSet(self, batch_size):
        """Take a DARK-FLAT set of images for photo stacking."""
        print(TextColor.yellow("DarkFlatSet"))
        ExposureMicroseconds = int(0.001 * 1000000)  # 1/1000th of a second.
        self.set_image_type(
            "darkflat"
        )  # Tell the camera we are taking darkflat photos.
        FileRoot = self.folder_handler.prep_file("darkflat", "darkflat_")
        self.log("Generating DARK FLAT image set of", batch_size, "images.")
        self.log(
            "These help remove electrical and manufacturing noise from the images."
        )
        self.log(
            "These match the FLAT exposure time of",
            ExposureMicroseconds / 1000000.0,
            "seconds.",
        )
        self.log("Lens cap must be ON.")
        self.log(batch_size, "Images will be stored in", FileRoot)
        input(TextColor.cyan("[RETURN] to begin: "))  # Python3
        print("Capturing Dark-Flat image set...")
        camera_command = self.parameters._CameraDarkFlatCommand
        # CaptureSet will automatically set mode,width and height parameters if they are in the command line.
        camera_command = camera_command.replace(
            "{&shutter}", str(int(ExposureMicroseconds))
        )
        if (
            self.camera_save_dng or self.camera_save_fits
        ):  # If we intend to produce DNG raw data at some point, we need to capture the bayer matrix.
            camera_command += (
                " " + self.parameters._CameraRawSwitch + " "
            )  # Append RAW data to the image.
        result = self.capture_set(
            file_root=FileRoot, batch_size=batch_size, camera_command=camera_command
        )
        return result

    def FlatSet(self, batch_size):
        """Take a FLAT set of images for photo stacking."""
        print(TextColor.yellow("FlatSet"))
        self.set_image_type("flat")  # Tell the camera we are taking flat photos.
        FileRoot = self.folder_handler.prep_file("flat", "flat_")
        self.log("Generating FLAT image set of", batch_size, "images.")
        self.log("These are flat white unfocused images.")
        self.log("These will be a short exposure time (Auto exposure)")
        self.log(
            "Flat images are used to compensate for vignetting and dealing with dust and dead pixels."
        )
        self.log(
            "The lens cap must be OFF. You need a evenly lit neutral white target."
        )
        self.log(
            "People often stretch a white t-shirt over the lens and point at a bright area of sky."
        )
        self.log("You can re-use the flat image set across multiple campaigns.")
        self.log(batch_size, "Images will be stored in", FileRoot)
        input(TextColor.cyan("[RETURN] to begin: "))  # Python3
        print("Capturing Flat image set...")
        camera_command = self.parameters._CameraFlatCommand
        # CaptureSet will automatically set mode,width and height parameters if they are in the command line.
        if (
            self.camera_save_dng or self.camera_save_fits
        ):  # If we intend to produce DNG raw data at some point, we need to capture the bayer matrix.
            camera_command += (
                " " + self.parameters._CameraRawSwitch + " "
            )  # Append RAW data to the image.
        result = self.capture_set(
            file_root=FileRoot, batch_size=batch_size, camera_command=camera_command
        )
        return result

    def BiasSet(self, batch_size):
        """Take a BIAS/OFFSET set of images for photo stacking."""
        print(TextColor.yellow("BiasSet"))
        ExposureMicroseconds = int(0.001 * 1000000)  # 1/1000th of a second.
        self.set_image_type("bias")  # Tell the camera we are taking bias photos.
        FileRoot = self.folder_handler.prep_file("bias", "bias_")
        self.log("Generating OFFSET/BIAS image set of", batch_size, "images.")
        self.log(
            "These will be the shortest possible exposure time (FASTEST)",
            ExposureMicroseconds / 1000000.0,
            "seconds",
        )
        self.log(
            "The temperature and ISO settings must be the same as the LIGHT images."
        )
        self.log(
            "These are used to remove manufacturing defects from the images that the sensor captures."
        )
        self.log("Lens cap must be ON.")
        self.log(batch_size, "Images will be stored in", FileRoot)
        input(TextColor.cyan("[RETURN] to begin: "))  # Python3
        print("Capturing Bias image set...")
        camera_command = self.parameters._camera_bias_command
        # CaptureSet will automatically set mode,width and height parameters if they are in the command line.
        camera_command = camera_command.replace(
            "{&shutter}", str(int(ExposureMicroseconds))
        )
        if (
            self.camera_save_dng or self.camera_save_fits
        ):  # If we intend to produce DNG raw data at some point, we need to capture the bayer matrix.
            camera_command += (
                " " + self.parameters._CameraRawSwitch + " "
            )  # Append RAW data to the image.
        result = self.capture_set(
            file_root=FileRoot, batch_size=batch_size, camera_command=camera_command
        )
        return result

    def AutoPhoto(self):
        print(TextColor.yellow("AutoPhoto"))
        if not self.parameters.camera_enabled:
            self.log(
                "AstroCamera.AutoPhoto(): Camera is disabled. No photo attempted.",
                level="warning",
            )
            return False
        FileRoot = self.folder_handler.prep_file("auto", "autophoto_")
        self.set_image_type("auto")
        print("Taking fully automatic photographs (Good for daylight testing).")
        print("Lens cap must be OFF.")
        print(
            "Camera must already be on-target, it will not track during AutoPhoto functions."
        )
        print("Camera will use automatic exposure settings in AutoPhoto mode.")
        print("Images will be stored in", FileRoot)
        inp = ""
        while inp != "x":
            inp = input("<RETURN> to begin ('x' to quit): ").lower()  # Python3
            if inp == "x":
                print("quit")
                break
            dt = CleanDatetimeString(str(now_utc()))
            filename = FileRoot + dt + ".jpg"
            camera_command = self.parameters._CameraAutoCommand
            camera_command = camera_command.replace("{&mode}", str(self.sensor.mode))
            camera_command = camera_command.replace(
                "{&width}", str(self.sensor.pixel_width)
            )
            camera_command = camera_command.replace(
                "{&height}", str(self.sensor.pixel_height)
            )
            camera_command = camera_command.replace("{&output}", filename)
            camera_command = camera_command.replace(
                "{&logfile}", self.logger.FileName
            )  # Point to a log file.
            if (
                self.camera_save_dng or self.camera_save_fits
            ):  # If we intend to produce DNG/FITS raw data at some point, we need to capture the bayer matrix.
                camera_command += (
                    " " + self.parameters._CameraRawSwitch + " "
                )  # Append RAW data to the image.
            self.log("AstroCamera.AutoPhoto():", camera_command, terminal=True)
            # *Q* TODO: Perform safety check for remaining & symbols.
            if (
                "{&" in camera_command
            ):  # Some remaining tags remain which have not been replaced.
                self.log(
                    "AstroCamera.AutoPhoto(): camera_command contains unconverted options.",
                    terminal=True,
                )
            self.os_cmd(camera_command)
            print("-", filename)
        return True


class CameraUtil:
    """Utilities for camera handling."""

    def __init__(self, name=None, channel=None):
        # from libcamera import Transform
        self.Name = name
        self.channel = channel
        self.Camera = None
        self.PreviewX = 100
        self.PreviewY = 200
        self.PreviewHeight = 600
        self.PreviewWidth = 800
        self.Overlay = None  # np array of overlay image in RGBA format.
        self.Rebuild = True  # Preview window needs rebuilding.

    def CreateCamera(self):
        if self.Camera is None:
            self.Camera = Picamera2()

    def MoveLeft(self):
        """Move preview window left."""
        self.PreviewX -= 100
        self.Rebuild = True

    def MoveRight(self):
        """Move preview window right."""
        self.PreviewX += 100
        self.Rebuild = True

    def MoveUp(self):
        """Move preview window up."""
        self.PreviewY += 100
        self.Rebuild = True

    def MoveDown(self):
        """Move preview window down."""
        self.PreviewY -= 100
        self.Rebuild = True

    def MoveUpLeft(self):
        """Move preview window towards corner."""
        self.MoveUp()
        self.MoveLeft()

    def MoveUpRight(self):
        """Move preview window towards corner."""
        self.MoveUp()
        self.MoveRight()

    def MoveDownLeft(self):
        """Move preview window towards corner."""
        self.MoveDown()
        self.MoveLeft()

    def MoveDownRight(self):
        """Move preview window towards corner."""
        self.MoveDown()
        self.MoveRight()

    def GrowPreview(self):
        """Make preview window larger."""
        self.PreviewWidth = int(self.PreviewWidth * 1.1)
        self.PreviewHeight = int(self.PreviewHeight * 1.1)
        self.Rebuild = True

    def ShrinkPreview(self):
        """Make preview window smaller."""
        self.PreviewWidth = int(self.PreviewWidth / 1.1)
        self.PreviewHeight = int(self.PreviewHeight / 1.1)
        self.Rebuild = True

    def LoadOverlay(self, filename=None):
        if filename is not None:  # Overlay specified.
            self.Overlay = cv2.imread(
                filename, cv2.IMREAD_UNCHANGED
            )  # Retain transparency when reading file.
            self.Overlay = cv2.cvtColor(
                self.Overlay, cv2.COLOR_BGRA2RGBA
            )  # Convert from BGRA to RGBA for picamera2 overlays.
        else:
            self.ClearOverlay()

    def ClearOverlay(self):
        self.Overlay = None

    def LivePreview(self, filename=None):
        """Create live preview image.
        This is a live image from the camera, with an optional overlay added.
        libcamera/picamera2 utility only."""
        KeyboardActions = {
            "+": self.GrowPreview,
            "-": self.ShrinkPreview,
            "6": self.MoveRight,
            "4": self.MoveLeft,
            "8": self.MoveUp,
            "9": self.MoveUpRight,
            "7": self.MoveUpLeft,
            "2": self.MoveDown,
            "1": self.MoveDownLeft,
            "3": self.MoveDownRight,
        }
        keyboard = KeyboardScanner()
        self.CreateCamera()
        self.LoadOverlay(filename)
        self.Camera.configure(self.Camera.create_preview_configuration())
        self.Camera.shutter_speed = 1 * 1000
        self.Camera.start()
        print("Press +,- for scale")
        print("Press num pad to move")
        print("Press 'x' to quit")
        while True:
            if self.Rebuild:
                try:
                    self.Camera.stop_preview()
                except:
                    pass
                self.Camera.start_preview(
                    Preview.QTGL,
                    x=self.PreviewX,
                    y=self.PreviewY,
                    width=self.PreviewWidth,
                    height=self.PreviewHeight,
                )
                self.Camera.set_overlay(self.Overlay)
                self.Camera.title_fields = ["ExposureTime", "AnalogueGain", "Lux"]
                self.Rebuild = False
            time.sleep(1)
            keypress = keyboard.check().lower()  # Non-blocking scan for keyboard input.
            if keypress == "x":
                break
            elif keypress in KeyboardActions:
                print("Actioning:", keypress)
                KeyboardActions[keypress]()
        self.Camera.stop()
        self.Camera.stop_preview()
