#!/usr/bin/python

# This software is published under the GNU General Public License v3.0.
# Also respect any pre-existing terms of any components that this incorporates.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# THIS SOFTWARE CAN CONTROL ELECTRICAL AND MECHANICAL DEVICES.
# THERE IS THEREFORE A RISK OF INJURY FROM INCORRECT ASSEMBLY, OPERATION OR FAILURE OF COMPONENTS.
# IT IS YOUR RESPONSIBILITY TO ENSURE THE SAFETY OF THE DEVICES YOU CHOOSE TO CONTROL WITH THIS SOFTWARE.

import glob  # file system.
import math  # Math and trig functions.
import os  # OS Command execution.
import random

# Import required libraries
from datetime import datetime, timedelta, timezone
from typing import List  # random number generator.

# from pidng.core import RPICAM2DNG # DNG data extraction from RPi camera RAW images. From https://github.com/schoolpost/pidng Needs to be 3.4.6 version. Later versions are not compatible.
import numpy as np  # Fast array handling

from camera.astro_lens import AstroLens
from camera.astro_sensor import AstroSensor
from camera.image import (  # Pilomar's IMAGE BUFFER handler (combines numpy, OpenCV and pilomar specific routines)
    PilomarImage,
    pilomarkeogram,
)
from gpio.micro import Microcontroller
from motor.control import last_reported_alt_az
from oscommand import OSCommand  # Pilomar's OS command executor.
from session.status import SessionStatus
from utils.disk import DiskMonitor
from utils.files.folder import FolderHandler
from utils.logfile import LogFile
from utils.math_func import is_int, text_to_int
from utils.coordinates import (
    alt_az_to_xyz,
    xyz_to_alt_az,
    relative_alt_az,
    plot_relative_alt_az,
    calculate_vector,
)
from utils.params import Parameters
from utils.text.display import ask_yes_no
from utils.text.human_readable import human_readable_seconds
from utils.text.textcolor import (  # Basic colour and cursor control codes for terminal displays.
    KeyboardScanner,
    TextColor,
)
from utils.time_funcs import now_hour_minute_sec, now_utc, utc_time_stamp
from utils.timer import ProgressTimer, Timer  # Pilomar's timer classes.

# ------------------------------------------------------------------------------------------------------


class AstroCamera:
    """
    Object representing the camera assembly being used.
    It contains the LENS and SENSOR objects, also various attributes and settings of the overall camera.

    Raises:
        Exception: If the function fails.
    """

    CameraList: List["AstroCamera"] = []  # List of cameras declared.

    # @staticmethod
    # def set_global_folder_list(folderlist):
    #    """ Update FolderList in all declared cameras. """
    #    for camera in astrocamera.CameraList:
    #        camera.FolderList = folderlist

    @staticmethod
    def set_global_folder_handler(folderhandler: FolderHandler):
        """Update FolderHAndler in all declared cameras."""
        for camera in AstroCamera.CameraList:
            camera.folder_handler = folderhandler

    @staticmethod
    def set_global_mctl(mctl: Microcontroller):
        """Update Microcontroller handler in all declared cameras."""
        for camera in AstroCamera.CameraList:
            camera.mctl = mctl

    @staticmethod
    def set_global_keyboard(keyboard: KeyboardScanner):
        """Update Keyboard scanner handle in all declared cameras."""
        for camera in AstroCamera.CameraList:
            camera.keyboard = keyboard

    def __init__(
        self,
        inp_sensor,
        inp_lens,
        exposure=10.0,
        trackingexposure=5.0,
        logger=None,
        parameters=None,
    ):
        self.set_logger(
            logger
        )  # self.log # Handle to the class that handles logging and error tracing.
        self.os_command = OSCommand(logger=logger.log)  # Create OS command executor.
        self.os_cmd = self.os_command.execute
        # Helper functions and attributes, should be set in calling program.
        self.keyboard: KeyboardScanner = (
            None  # Can declare a keyboard scanner (TextColor keyboard scanner instance).
        )
        self.storage_monitor: DiskMonitor = (
            None  # Can declare a storage monitor class here.
        )
        self.parameters: Parameters = (
            parameters  # Must define the parameter file before using the instance.
        )
        self.folder_handler: FolderHandler = (
            None  # Local copy of the FolderList telling where to store files.
        )
        # -
        self.file_types = ["jpg", "dng"]  # List of file types to make available.
        self.object_type = None  # What is the target type? Set by SetObservationParameters() from session information.
        self.mctl: Microcontroller = (
            None  # Handle to the microcontroller. Can monitor it for restarts.
        )
        self.sensor: AstroSensor = inp_sensor  # The sensor that makes up the camera.
        self.lens: AstroLens = inp_lens  # The lens that makes up the camera.
        self.exposure_seconds = (
            exposure  # Exposure seconds per frame for astro photos ('light' frames).
        )
        self.tracking_exposure_seconds = (
            trackingexposure  # Tracking photos are always 5 second exposure.
        )
        self.timelapse_seconds = (
            None  # Delay between successive exposures if taking timelapse images.
        )
        self.timelapse_timer = None  # Handle to timelapse timer if set.
        self.pixels_per_fov_degree_width = 0  # Set by ModeChange() below. How many pixels represent 1 degree image width.
        self.pixels_per_fov_degree_height = 0  # Set by ModeChange() below. How many pixels represent 1 degree image height.
        self.pixel_fov_width = 0  # Set by ModeChange() below. # Approximate field of view of an individual pixel.
        self.pixel_fov_height = 0  # Set by ModeChange() below.
        self.seconds_per_pixel = 0.0  # Set by ModeChange() below. Specifies how long an object takes to traverse one pixel of an image.
        self.mode_change()  # Set values based upon sensor mode.
        self.last_image_date_time = None  # When was the latest image taken? # *Q* How widely is this attribute used?
        self.last_jpg = None  # The filename of the last jpg taken (if saved)
        self.preview_jpg = None  # The filename of the last preview image generated.
        self.image = PilomarImage(
            name="camera", logger=self.logger
        )  # pilomarimage instance for handling OpenCV image buffer.
        self.capture_start = (
            None  # Timestamp when image capture started. Used to detect camera hanging.
        )
        self.capture_end = None  # Timestamp when image capture completed. Used to detect camera hanging.
        self.batch_count = 0  # How many photos taken in the current observation batch?
        self.id = (
            self.sensor.id + "|" + self.lens.i_d
        )  # Unique ID of lens and sensor characteristics.
        self.set_image_type(
            "light"
        )  # The type of image being captured. Links to self.folder_handler. tells HOW to process the image and WHERE to store it.
        self.camera_tasks = []  # No tasks to perform yet.
        self.current_task = None  # The current task being performed by the camera.
        self.last_light_command = (
            ""  # Keep a note of the camera options used for the latest light image.
        )
        # Observation specific settings. These override the general parameters in instances where the general parameters don't make sense. Eg meteor monitoring.
        self.camera_save_dng = True
        self.camera_save_jpg = True
        self.camera_save_fits = False
        self.fast_image_capture = False
        self.camera_options = ""  # The camera options passed to raspistill. These depend upon the image type being captured.
        self.rx_count = 0  # Number of messages received by camera thread.
        self.tx_count = 0  # Number of messages sent by camera thread.
        if self.parameters.camera_driver == "raspistill":
            from pidng.core import (
                RPICAM2DNG,
            )  # DNG data extraction from RPi camera RAW images. From https://github.com/schoolpost/pidng Needs to be 3.4.6 version. Later versions are not compatible.

            self.pi_dng = (
                RPICAM2DNG()
            )  # RPICAM2DNG() needed for Buster O/S raspistill operation.
        else:
            self.pi_dng = None  # RPICAM2DNG() not needed for libcamera operation.
        AstroCamera.CameraList.append(
            self
        )  # Add this instance to the global list of all defined cameras.

    def clean_datetime_string(self, line):
        """Remove all the special characters from a timestamp string.
        Converts things like YYYY-MM-DD HH:MM:SS into YYYYMMDDHHMMSS"""
        try:
            if not isinstance(line, str):
                line = str(line)  # Auto-convert into a string if it isn't already.
            for a in ["-", " ", ":", "."]:
                line = line.replace(a, "")
            line = line[:14]  # Only accurate to SECONDS currently.
        except Exception as e:
            print(e)  # Trap all the exception information in the main log file.
            raise Exception(
                "astrocamera.CleanDatetimeString() failed."
            ) from e  # Continue with regular exception stack.
        return line

    def set_logger(self, logger: LogFile):
        """Set up link to logging class and shortcuts to common methods."""
        # The logging methods default to 'consumers' which will just silently eat any parameters passed.
        self.logger = logger  # Logger instance.
        self.log = self._null_logger  # No log method.
        self.report_exception = (
            self._null_logger
        )  # Cannot report exception details to logfile.
        self.raise_exception = self._null_logger  # Cannor report and raise exception.
        if hasattr(logger, "Log"):
            self.log = logger.log  # Log method.
        if hasattr(logger, "ReportException"):
            self.report_exception = (
                logger.report_exception
            )  # Report exception details to logfile.
        if hasattr(logger, "RaiseException"):
            self.raise_exception = logger.raise_exception  # Report and raise exception.
        # self.log("astrocamera.set_logger: Linked to this log file.",terminal=False)

    def _null_logger(self, *args, **kwargs):
        """Null logger. Absorbs parameters and .log call but does nothing.
        Use this when there is no logger defined."""
        return

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
            "astrocamera.PixelFoV (w/h)",
            self.pixel_fov_width,
            self.pixel_fov_height,
            terminal=False,
        )

    def set_observation_parameters(self, session: SessionStatus):
        """Choose which parameter settings to apply to the observation about to begin.
        These are based upon the general parameter settings, but are overridden
        for some types of targets, such as meteors.

          self.camera_tasks        : What tasks should the camerahandler deal with?
          self.camera_save_dng      : Do we produce DNG raw sensor data?
          self.camera_save_jpg      : Do we create simple JPG images? (Raw data removed)
          self.camera_save_fits     : Do we create FITS files? (Still under development)
          self.fast_image_capture   : Do we perform fast image capture (delay image processing until later).
          self.live_stacking       : Do we perform live stacking?

        """
        # Decide which tasks the camerahandler will deal with.
        self.camera_tasks = ["image", "pause"]
        self.target = session.target  # Keep local pointer to the Target object.
        self.object_type = (
            session.target.object_type
        )  # What type of object are we looking at?
        if self.object_type in [
            "aurora",
            "meteor",
        ]:  # Don't generate preview images for meteors or aurora.
            if self.parameters.camera_window is not None:
                self.parameters.camera_window.print(
                    now_hour_minute_sec()
                    + " No preview's generated for "
                    + self.object_type
                    + " recordings."
                )
            self.log(
                "astrocamera.SetObservationParameters No preview's generated for",
                self.object_type,
                "recordings.",
                terminal=False,
            )
        elif not self.parameters.generate_preview:
            if self.parameters.camera_window is not None:
                print(
                    now_hour_minute_sec()
                    + " Preview generation is disabled in parameters."
                )
            self.log(
                "astrocamera.SetObservationParameters Preview generation is disabled in parameters.",
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
            if self.parameters.camera_window is not None:
                self.parameters.camera_window.print(
                    now_hour_minute_sec()
                    + " No tracking performed for "
                    + self.object_type
                    + " targets."
                )
            self.log(
                "astrocamera.SetObservationParameters No tracking performed for",
                self.object_type,
                "targets.",
                terminal=False,
            )
        else:
            # Do track for targets that rotate with the sky.
            # Always add tracking to the tasklist, even if it's currently disabled.
            # The tracking routine will handle that, and it could be dynamically enabled during the observation.
            self.camera_tasks.append("tracking")
        self.log(
            "astrocamera.SetObservationParameters Target type",
            self.object_type,
            ", Selected tasks:",
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
                    "astrocamera.SetObservationParameters Target type",
                    self.object_type,
                    ", will not capture DNG (raw) images.",
                    terminal=False,
                )
                self.camera_save_dng = False
        else:
            self.camera_save_dng = (
                self.parameters.camera_save_dng
            )  # Revert to parameter preference.
        self.log(
            "astrocamera.SetObservationParameters Target type",
            self.object_type,
            ", CameraSaveDng",
            self.camera_save_dng,
            terminal=False,
        )

        if self.object_type in [
            "aurora",
            "meteor",
        ]:  # Disable DNG generation if taking AURORA or METEOR images.
            if self.camera_save_fits:
                self.log(
                    "astrocamera.SetObservationParameters Target type",
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
            "astrocamera.SetObservationParameters Target type",
            self.object_type,
            ", CameraSaveFits",
            self.camera_save_fits,
            terminal=False,
        )

        if self.object_type in [
            "aurora",
            "meteor",
        ]:  # Turn on JPG generation if not already set.
            if not self.camera_save_jpg:
                self.log(
                    "astrocamera.SetObservationParameters Target type",
                    self.object_type,
                    ", will capture JPG images.",
                    terminal=False,
                )
                self.camera_save_jpg = True
        else:
            self.camera_save_jpg = (
                self.parameters.camera_save_jpg
            )  # Revert to parameter preference.
        self.log(
            "astrocamera.SetObservationParameters Target type",
            self.object_type,
            ", CameraSaveJpg",
            self.camera_save_jpg,
            terminal=False,
        )

        if self.object_type in [
            "aurora",
            "meteor",
        ]:  # Turn on Fast Image Capture if not already set.
            if not self.fast_image_capture:
                self.log(
                    "astrocamera.SetObservationParameters Target type",
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
            "astrocamera.SetObservationParameters Target type",
            self.object_type,
            ", FastImageCapture",
            self.fast_image_capture,
            terminal=False,
        )

        return True

    def calibrate_fov(self):
        """Ask the user to enter the pixel diameter of the moon from a photograph.
        Use this to estimate the FieldOfView of the camera and adjust parameters accordingly.
        """
        self.log("astrocamera.CalibrateFov: Begin", terminal=False)
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
            "Horizontal field of view: " + str(self.lens.fov_horizontal) + "deg",
            "Vertical field of view: " + str(self.lens.fov_vertical) + "deg",
            "Minimum field of view: " + str(self.lens.fov) + "deg",
            "Horizontal pixels per degree FOV: "
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
            self.log("astrocamera.CalibrateFov: Proceeding", terminal=False)
            result = ask_yes_no(
                "Do you have an image of the moon captured with the current lens? [y/N]",
                False,
            )
        if not result:
            self.log(
                "astrocamera.CalibrateFov: Moon image is not available", terminal=False
            )
            listlines = [
                "You must take a photograph of the moon with the current lens.",
                "Measure the pixel diameter of the moon's full disc on that image.",
                "Using that pixel size we can estimate the field of view of the lens.",
            ]
            TextColor.text_box(listlines)
            return  # Do nothing.

        self.log("astrocamera.CalibrateFov: Moon image is available", terminal=False)

        # Can we offer any hints from the last image captured?
        self.log(
            "astrocamera.CalibrateFov: Consider last captured image", terminal=False
        )
        if (
            self.image.image_exists()
        ):  # There's an image in the buffer, what large objects are in there?
            dia_min = 50  # Smallest diameter objects to list.
            dia_max = 600  # Largest diameter objects to list.
            area_min = math.pi * ((dia_min / 2) ** 2)
            area_max = math.pi * ((dia_max / 2) ** 2)
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
                    i,
                    "Centered at (",
                    jx,
                    ",",
                    jy,
                    ") diameter",
                    dia,
                    "pixels",
                    terminal=True,
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
            if is_int(rawtext):
                break  # We have a value to use.

            print(TextColor.red("Please try again. Integer values only."))
            rawtext = None  # Try again.

        if rawtext is None:
            self.log(
                "astrocamera.CalibrateFov: No moon diameter value given", terminal=False
            )
            return  # Nothing to do.

        self.log(
            "astrocamera.CalibrateFov: Moon diameter", rawtext, "pixels", terminal=False
        )

        # We have what we need.
        moonpixels = text_to_int(rawtext)  # Convert the measured diameter into integer.
        print("The camera records the moon as", moonpixels, "pixels in diameter.")
        print("The moon is" + str(moon_mean_dia_deg) + "deg in diameter on average.")
        # Convert to field of view.
        # Lens fields to change...
        self.lens.fov_horizontal = round(
            self.sensor.pixel_width * moon_mean_dia_deg / moonpixels, 1
        )  # FOV to 1 decimal place is enough.
        self.lens.fov_vertical = round(
            self.sensor.pixel_height * moon_mean_dia_deg / moonpixels, 1
        )  # FOV to 1 decimal place is enough.
        self.lens.fov = min(
            self.lens.fov_horizontal, self.lens.fov_vertical
        )  # When calculating the FOV for a survey, use the smaller value.
        self.log(
            "astrocamera.CalibrateFov: Chosen H.FoV:",
            self.lens.fov_horizontal,
            "V.FoV:",
            self.lens.fov_vertical,
            terminal=False,
        )
        # Camera fields to change...
        self.mode_change()  # Set camera's FOV related values just as if the sensor mode had changed.
        expected_dia_pix = int(
            self.pixels_per_fov_degree_width * moon_mean_dia_deg
        )  # How big do we expect the moon to be with current settings?
        listlines = [
            "The lens now has the following characteristics",
            " ",
            "Horizontal field of view: " + str(self.lens.fov_horizontal) + "deg",
            "Vertical field of view: " + str(self.lens.fov_vertical) + "deg",
            "Minimum field of view: " + str(self.lens.fov) + "deg",
            "Horizontal pixels per degree FOV: "
            + str(self.pixels_per_fov_degree_width),
            "Vertical pixels per degree FOV: " + str(self.pixels_per_fov_degree_height),
            " ",
            "The Moon's disc is " + str(moon_mean_dia_deg) + "deg diameter on average.",
            "Expected diameter in an image is about "
            + str(expected_dia_pix)
            + " pixels.",
        ]
        TextColor.text_box(listlines)
        result = ask_yes_no("Do you want to make these changes permanent? [y/N]", False)
        if (
            result
        ):  # Make these changes permanent by setting them in the parameter file.
            self.log("astrocamera.CalibrateFov: Making FoV permanent.", terminal=False)
            self.parameters.lens_horizontal_fov = self.lens.fov_horizontal
            self.parameters.lens_vertical_fov = self.lens.fov_vertical
        else:  # Don't touch the parameter settings, so the system will reset when restarted.
            self.log("astrocamera.CalibrateFov: Making FoV temporary.", terminal=False)
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
            print(TextColor.red("(" + self.parameters.param_filename + ")"))

    def set_image_type(self, imagetype):
        """Validate and set the ImageType attribute.
        The image type must be in the self.folder_list dictionary."""
        # if imagetype in self.folder_list:
        if self.folder_handler is not None and self.folder_handler.valid_key(imagetype):
            self._image_type = imagetype  # OK to accept this image type.
            self.log(
                "astrocamera.SetImageType(",
                imagetype,
                ") new image type set.",
                terminal=False,
            )
        else:  # ImageType has nowhere to go.
            # self.log("astrocamera.SetImageType(",imagetype,") is not recognised. Must be in FolderList. Defaulting to 'light'.",terminal=False)
            self.log(
                "astrocamera.SetImageType(",
                imagetype,
                ") is not recognised. Must be in FolderHandler. Defaulting to 'light'.",
                terminal=False,
            )
            self._image_type = "light"

    def get_image_type(self):
        return self._image_type

    def set_timelapse(self, seconds):
        """Set timelapse delay and initiate timer."""
        if seconds is None or seconds <= 0.0:
            self.timelapse_timer = None
            self.timelapse_seconds = None
        else:
            self.timelapse_timer = Timer(period=seconds)
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
        """Reset camera settings at the beginning of a new session."""
        self.last_image_date_time = None  # When was the latest image taken?
        self.lastjpg = None  # The filename of the last jpg taken (if saved)
        self.previewjpg = None  # The filename of the last preview image generated.
        self.image.clear()  # openCV image buffer. Loaded explicitly when needed.
        self.capture_start = (
            None  # Timestamp when image capture started. Used to detect camera hanging.
        )
        self.capture_end = None  # Timestamp when image capture completed. Used to detect camera hanging.
        self.batch_count = 0  # How many photos taken in the current observation batch?
        if self.parameters.camera_window is not None:
            self.parameters.camera_window.print(
                now_hour_minute_sec() + " astrocamera.Reset"
            )

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
        if self.last_image_date_time is not None:
            result = now_utc() - self.last_image_date_time
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
        NOTE: There are overheads in the camera libraries, the camera takes much longer than just
        the 'exposure' time to complete an image.
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
                faultdelay = max(self.exposure_seconds * 5, 500)
                if (
                    self.capture_start_age_seconds() > faultdelay
                ):  # It has been running too long.
                    result = True  # It looks like there's something wrong.
                    line = (
                        "astrocamera.CameraFault: Image capture time "
                        + str(round(self.capture_start_age_seconds(), 1))
                        + "s is too long. The camera may have hung. Consider power cycling the RPi."
                    )
                    if self.parameters.camera_window is not None:
                        self.parameters.camera_window.print(
                            now_hour_minute_sec() + " " + line
                        )
                    self.log(
                        "astrocamera.CaptureStart", self.capture_start, terminal=False
                    )
                    self.log(
                        "astrocamera.CaptureEnd", self.capture_start, terminal=False
                    )
                    self.log("astrocamera.faultdelay", faultdelay, terminal=False)
                    self.log(
                        "astrocamera.CaptureStartAgeSeconds",
                        self.capture_start_age_seconds(),
                        terminal=False,
                    )
                    self.log(
                        "astrocamera.LastImageDateTime",
                        self.last_image_date_time,
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
            "astrocamera.SetMode(): Mode " + str(mode) + " selected.", terminal=False
        )
        self.log(
            "astrocamera.SetMode(): Sensor pixel dimensions now: "
            + str(self.sensor.pixel_width)
            + "x"
            + str(self.sensor.pixel_height),
            terminal=False,
        )
        self.log(
            "astrocamera.SetMode(): Pixels per degree are now: "
            + str(self.pixels_per_fov_degree_width)
            + "x"
            + str(self.pixels_per_fov_degree_height),
            terminal=False,
        )
        self.log(
            "astrocamera.SetMode(): Seconds per pixel is now: "
            + str(self.seconds_per_pixel),
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
            "astrocamera.ModeChange(): PixelsPerDegree Width/Height "
            + str(self.pixels_per_fov_degree_width)
            + " / "
            + str(self.pixels_per_fov_degree_height),
            terminal=False,
        )
        arc_seconds_per_width = self.lens.fov_horizontal * 60 * 60
        arc_seconds_per_pixel = float(arc_seconds_per_width) / self.sensor.pixel_width
        self.log(
            "astrocamera.ModeChange(): Arcseconds per pixel: "
            + str(round(arc_seconds_per_pixel, 3)),
            terminal=False,
        )
        full_rotation_as = 360 * 60 * 60  # Arcseconds in an entire rotation.
        seconds_per_as = (
            24 * 60 * 60 / float(full_rotation_as)
        )  # How many seconds does a single arcsecond last before earth rotation has moved on.
        self.log(
            "astrocamera.ModeChange(): Seconds per arcsecond: " + str(seconds_per_as),
            terminal=False,
        )
        self.seconds_per_pixel = float(arc_seconds_per_pixel) * seconds_per_as
        self.log(
            "astrocamera.ModeChange(): To avoid blurring the camera needs to move every",
            round(self.seconds_per_pixel, 3),
            "seconds.",
            terminal=False,
        )
        self.log(
            "astrocamera.ModeChange(): Mode " + str(self.sensor.mode) + " selected.",
            terminal=False,
        )
        self.pixel_fov()  # Calculate field of view of an individual pixel (very approximate).

    def cleanup_lastjpg(self):
        """Call this to delete the disc copy of the last jpg file that was generated.
        It also clears the reference to the file that has been deleted."""
        self.log("astrocamera.CleanupLastjpg()", terminal=False)
        if self.lastjpg is not None:
            cmd = "rm " + self.lastjpg
            self.os_cmd(cmd)
            self.lastjpg = None  # Clear the saved filename.

    def fake_aurora(self, srcimg):  # Generate a fake aurora effect.
        """Create a series of aurura like color blocks on an image.
        srcimg = numpy buffer.
        Return combined image."""
        height = self.sensor.pixel_height  # Image dimensions.
        width = self.sensor.pixel_width
        curtain_image = PilomarImage(
            name="auroracurtain", logger=self.logger
        )  # Create empty image.
        auroracolors = [
            PilomarImage.bgr("LightGreen"),
            PilomarImage.bgr("DarkGreen"),
            PilomarImage.bgr("Cyan"),
            PilomarImage.bgr("HotPink"),
        ]
        for i, ac in enumerate(auroracolors):  # Dim all the colors.
            auroracolors[i] = curtain_image.dim_color(
                ac, 0.2
            )  # Reduce color intensity to nnn%
        fieldimg = srcimg.copy().astype(
            np.uint16
        )  # Black image, datatype large enough for multiple layers to be combined.
        curtain_image.new(height, width, imagetype="bgr", datatype=np.uint8)
        if curtain_image.image_missing():
            self.log(
                "astrocamera.FakeAurora: fakeimage.new() failed.",
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
            "astrocamera.FakePollution: Simulating light pollution.", terminal=False
        )
        thickest_value = [
            50,
            50,
            50,
        ]  # How thick is the haze at the horizon? (BGR) (Scale 0-255, higher values = more pollution)
        thinnest_value = [
            10,
            10,
            10,
        ]  # How thick is the haze above pollution_max_alt? (BGR)  (Scale 0-255, higher values = more pollution)
        pollution_max_alt = 15  # Degrees. Pollution fades to thinnest_value at this altitude above the horizon.
        haze_change = []  # What's the delta between the two limits?
        for j in range(len(thickest_value)):
            haze_change.append(thickest_value[j] - thinnest_value[j])
        ave_value = []  # What's the average between the two limits?
        for j in range(len(thickest_value)):
            ave_value.append(int((thickest_value[j] - thinnest_value[j]) / 2))
        self.log("astrocamera.FakePollution: haze_change", haze_change, terminal=False)
        if (
            self.parameters.use_live_location
        ):  # Use the live target location rather than the last reported camera position for image processing.
            centre_az, centre_alt = (
                self.target.az_alt_degrees()
            )  # What is the alt/az location of the centre of the image?
        else:  # Use the last reported camera position. Deprecated.
            centre_alt, centre_az = (
                last_reported_alt_az()
            )  # What is the alt/az location of the centre of the image?
        self.log(
            "astrocamera.FakePollution: CentreAltAz",
            centre_alt,
            centre_az,
            terminal=False,
        )
        rel_alt, rel_az = relative_alt_az(
            0, centre_az, centre_alt, centre_az
        )  # Image pixel height of horizon. (Thickest pollution level).
        _, horizon_y = plot_relative_alt_az(
            rel_alt, rel_az, self.sensor.pixel_height, self.sensor.pixel_width
        )  # Covert to pixel height.
        self.log(
            "astrocamera.FakePollution: HorizonAltAz",
            rel_alt,
            rel_az,
            horizon_y,
            terminal=False,
        )
        rel_alt, rel_az = relative_alt_az(
            pollution_max_alt, centre_az, centre_alt, centre_az
        )  # Image pixel height of pollution upper limit. (Thinnest pollution level)
        _, top_y = plot_relative_alt_az(
            rel_alt, rel_az, self.sensor.pixel_height, self.sensor.pixel_width
        )  # Covert to pixel height.
        self.log(
            "astrocamera.FakePollution: TopAltAz",
            rel_alt,
            rel_az,
            top_y,
            terminal=False,
        )
        self.log(
            "astrocamera.FakePollution: Horizon height", horizon_y, "px", terminal=False
        )
        self.log(
            "astrocamera.FakePollution: Top height",
            top_y,
            "px, (pollution_max_alt",
            pollution_max_alt,
            "deg)",
            terminal=False,
        )
        fieldimg = np.zeros(
            (self.sensor.pixel_height, self.sensor.pixel_width, 3), np.uint16
        )  # Black image.

        fieldimg[:, :] = np.array(thinnest_value).astype(
            np.uint16
        )  # Set ALL pixels to the thinnest haze value by default.

        if horizon_y < self.sensor.pixel_height:  # Horizon is in range.
            # Fill everything below horizon with Thickest pollution value.
            for i in range(max(0, horizon_y), self.sensor.pixel_height):
                fieldimg[i, :] = np.array(thickest_value).astype(np.uint16)

        # Now to calculate the gradient values where the haze builds up as it approaches the horizon.

        # Remember that images count rows from top down.
        rowspan = (
            horizon_y - top_y
        )  # How many rows to fill with the gradient if the image was infinitely tall?

        # Constrain the Top of the gradient to within the image boundary.
        if top_y < 0:
            startrow = 0
        elif top_y > self.sensor.pixel_height:
            startrow = self.sensor.pixel_height
        else:
            startrow = top_y

        # Constrain the Horizon to within the image boundary.
        if horizon_y < 0:
            endrow = 0
        elif horizon_y > self.sensor.pixel_height:
            endrow = self.sensor.pixel_height
        else:
            endrow = horizon_y

        if (
            startrow != endrow
        ):  # There's a band of the image that needs the haze gradient calculating.
            for i in range(
                startrow, endrow
            ):  # Process each row of the gradient in turn.
                gradient_point = (
                    i - top_y
                ) / rowspan  # How thick is the haze? Increasing in thickness towards the horizon.
                new_value = []
                # Calculate strength of each color channel in turn. BGR.
                for j, thinnest_val in enumerate(thinnest_value):
                    thin_val = (
                        (thickest_value[j] - thinnest_val) * gradient_point
                    ) + thinnest_val
                    new_value.append(int(thin_val))
                fieldimg[i, :] = np.array(new_value).astype(np.uint16)

        # TODO: Add some random noise to the pattern. +/- Thinnest value at random to the entire image.

        self.log(
            "astrocamera.FakePollution: Gradient span",
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
        """Generate false disc file to simulate a photograph being captured."""
        self.log(
            "astrocamera.FakePhoto: Simulating photo capture (",
            outputfile,
            ")",
            terminal=False,
        )
        fakeimage = PilomarImage(name="fakephoto", logger=self.logger)
        height = self.sensor.pixel_height
        width = self.sensor.pixel_width
        fakeimage.new(height, width, imagetype="bgr", datatype=np.uint8)
        if fakeimage.image_missing():
            self.log(
                "astrocamera.FakePhoto: fakeimage.new() failed.",
                level="error",
                terminal=True,
            )
        # fakeimage.image_buffer,starcount,starlist = CreateTargetImage(color=True,MinMagnitude=self.parameters.target_min_magnitude,astrotime=astrotime) # Use CreateTargetImage to make fake photo.
        fakeimage.image_buffer, starcount, starlist = self.image_simulator(
            color=True,
            MinMagnitude=self.parameters.target_min_magnitude,
            astrotime=astrotime,
        )  # Use CreateTargetImage to make fake photo.
        if fakeimage.image_missing():
            self.log(
                "astrocamera.FakePhoto: ImageSimulator() failed.",
                level="error",
                terminal=True,
            )
        if self.parameters.fake_noise:  # Simulate fake image noise.
            fakeimage.fake_noise()
            if fakeimage.image_missing():
                self.log(
                    "astrocamera.FakePhoto: FakeNoise() failed.",
                    level="error",
                    terminal=True,
                )
        if (
            self.parameters.fake_field
        ):  # Simulate fake electrical field noise in the image.
            fakeimage.fake_field()
            if fakeimage.image_missing():
                self.log(
                    "astrocamera.FakePhoto: FakeField() failed.",
                    level="error",
                    terminal=True,
                )
        if self.parameters.fake_pollution:  # Simulate fake light pollution.
            fakeimage.image_buffer = self.fake_pollution(fakeimage.image_buffer)
            if fakeimage.image_missing():
                self.log(
                    "astrocamera.FakePhoto: FakePollution() failed.",
                    level="error",
                    terminal=True,
                )
        if (
            self.object_type in ["aurora"] and self.parameters.fake_aurora
        ):  # Simulate aurora
            fakeimage.image_buffer = self.fake_aurora(fakeimage.image_buffer)
            if fakeimage.image_missing():
                self.log(
                    "astrocamera.FakePhoto: FakeAurora() failed.",
                    level="error",
                    terminal=True,
                )
        if (
            self.parameters.fake_meteor
            and random.randint(0, 100) < self.parameters.fake_meteor_percent
        ):  # 2% of images get fake meteor streaks in them.
            fakeimage.fake_meteor()
            if fakeimage.image_missing():
                self.log(
                    "astrocamera.FakePhoto: FakeMeteor() failed.",
                    level="error",
                    terminal=True,
                )
        try:
            fakeimage.save_file(outputfile)
        except Exception as e:
            self.log(
                "astrocamera.FakePhoto failed to write:", outputfile, level="error"
            )
            self.report_exception(e, comment="astrocamera.FakePhoto cv2.imwrite")
        self.log("astrocamera.FakePhoto: Completed.", terminal=False)
        return True

    def fake_dark(self, outputfile):
        """Generate false disc file to simulate a photograph being captured."""
        self.log(
            "astrocamera.FakeDark: Simulating dark photo capture (",
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
        except Exception as e:
            self.log("astrocamera.FakeDark failed to write:", outputfile, level="error")
            self.report_exception(e, comment="astrocamera.FakeDark cv2.imwrite")
        self.log("astrocamera.FakeDark: Completed.", terminal=False)
        return True

    def set_fake_delay(self, camera_options):
        """Extract the exposure time from camera options and pause processing
        to mimic the actual amount of time the camera would take."""
        optlist = camera_options.split(" ")
        delay = 1.0
        for i, opt in enumerate(
            optlist
        ):  # *Q* Doesn't recognise libcamera format parameters yet!
            if opt == "-ss":  # Found exposure time.
                delay = (
                    float(optlist[i + 1]) * 2
                )  # Find the microsecond exposure time and double it to mimic camera.
                delay = delay / 1_000_000  # Convert from microseconds to seconds.
                self.log(
                    "astrocamera.FakeDelay : ", round(delay, 1), "s ...", terminal=False
                )
                break
        delaytimer = Timer(period=delay)  # Create timer.
        return delaytimer

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
        """Take batch of photos. Uses CaptureSetFull or CaptureSetFast depending upon configuration."""
        # Automatic parameter conversion, if not already done before receiving camera_command.
        camera_command = camera_command.replace(
            "{&mode}", str(self.sensor.mode)
        )  # Camera Mode.
        camera_command = camera_command.replace(
            "{&channel}", str(self.sensor.channel)
        )  # Camera channel if multi-camera RPi.
        camera_command = camera_command.replace(
            "{&width}", str(self.sensor.pixel_width)
        )  # Image width.
        camera_command = camera_command.replace(
            "{&height}", str(self.sensor.pixel_height)
        )  # Image height.
        if (
            self.fast_image_capture
        ):  # Just capture the images as fast as possible, don't waste time processing anything else.
            result = self.capture_set_fast(
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
              astrocamera.Lastjpg contains the filename of the .jpg file generated.
        tempfile = True. Means that a single temporary filename is used each time.
        terminal=True. Means that the progress message is shown on the terminal.
        astrotime = the timestamp of the image to be generated if we're faking the result.
        stacker = a handle to a live image stacker object if we're live stacking."""
        result = True
        self.log(
            "astrocamera.CaptureSetFull(): Capturing " + str(batch_size) + " images...",
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
                "astrocamera.CaptureSetFull(): Capturing",
                outputfile,
                "...",
                terminal=False,
            )
            cmd = camera_command.replace(
                "{&output}", outputfile
            )  # *Q* TODO: Perform safety check for remaining & symbols.
            if self.mctl is not None:  # Microcontroller handle is defined.
                remoterestarts = (
                    self.mctl.remote_restarts
                )  # If this changes during exposure, the microcontroller has reset and we should reject the image.
            else:
                remoterestarts = 0
            rejectimage = (
                False  # Set to 'true' if there's a reason to reject the image.
            )
            self.capture_start = now_utc()
            if self.parameters.camera_enabled:  # Camera is enabled. Take real photo.
                self.os_cmd(cmd, output="none")
                retc = (
                    self.os_command.return_code
                )  # What did the camera command exit with ?
                self.log(
                    "astrocamera.CaptureSetFull(): Return code:", retc, terminal=False
                )
                if retc != 0:  # Non zero return code. Did something go wrong?
                    if self.parameters.camera_window is not None:
                        self.parameters.camera_window.print(
                            now_hour_minute_sec() + " Return code " + str(retc),
                            fg=TextColor.YELLOW,
                        )
                    if self.parameters.error_window is not None:
                        self.parameters.error_window.print(
                            now_hour_minute_sec()
                            + " capture returned code "
                            + str(retc),
                            fg=TextColor.YELLOW,
                        )
            else:  # Camera is not in use. Generate fake photo.
                self.log(
                    "astrocamera.CaptureSetFull(): About to call FakePhoto.",
                    terminal=False,
                )
                tr = False  # Fake image generation failed unless we are told otherwise.
                imty = self.get_image_type()  # What type of image are we faking?
                delay_timer = self.set_fake_delay(
                    camera_command
                )  # Create a timer to mimic the expected real camera delay.
                if imty == "dark":
                    tr = self.fake_dark(outputfile=outputfile)  # Fake a dark frame.
                else:
                    tr = self.fake_photo(
                        outputfile=outputfile, astrotime=astrotime
                    )  # Fake a light frame.
                if not tr:  # Image generation failed.
                    self.log(
                        "astrocamera.CaptureSetFull(): Fake image call failed (",
                        imty,
                        ").",
                        terminal=True,
                        level="error",
                    )
                else:  # Fake the expected exposure time if a real image was being captured.
                    delay_timer.wait()  # Wait until the fake delay timer expires. Thread pauses here.
                self.log(
                    "astrocamera.CaptureSetFull(): Returned from FakePhoto.",
                    terminal=False,
                )
            self.capture_end = now_utc()
            self.log(
                "astrocamera.CaptureSetFull(): Capture complete. (",
                (self.capture_end - self.capture_start).total_seconds(),
                "s).",
                terminal=False,
            )
            if self.mctl is not None:  # Microcontroller handle is known.
                if (
                    remoterestarts != self.mctl.remote_restarts
                ):  # Microcontroller reset during exposure.
                    self.log(
                        "astrocamera.CaptureSetFull(): Microcontroller restarted during exposure. Reject",
                        outputfile,
                        level="warning",
                        terminal=False,
                    )
                    if self.parameters.camera_window is not None:
                        self.parameters.camera_window.print(
                            now_hour_minute_sec() + " Motors reset during exposure."
                        )  # Just the filename.
                    if self.parameters.error_window is not None:
                        self.parameters.error_window.print(
                            now_hour_minute_sec() + " Motors reset during exposure."
                        )  # Just the filename.
                    rejectimage = True  # We should reject this image.
            if (
                not tempfile
            ):  # Display the filename if it's permanent, ignore the tempfile.
                if self.parameters.camera_window is not None:
                    self.parameters.camera_window.print(
                        now_hour_minute_sec() + " " + outputfile.split("/")[-1]
                    )  # Just the jpg filename.
            if rejectimage:  # There was reason to reject the image for some cause.
                self.log(
                    "astrocamera.CaptureSetFull(): Image should be rejected.",
                    terminal=False,
                )
            self.lastjpg = (
                outputfile  # The camera can remember this file as the 'last jpg taken'
            )
            self.log(
                "astrocamera.CaptureSetFull(): Load image from " + outputfile,
                terminal=False,
            )
            self.image.load_file(outputfile)  # OpenCV format.
            if (
                self.image.image_missing()
            ):  # imread failed. The capture did not succeed for some reason?
                self.log(
                    "astrocamera.CaptureSetFull(): imread of",
                    outputfile,
                    "failed.",
                    level="error",
                    terminal=False,
                )
            self.last_image_date_time = now_utc()
            # *Q* This timestamp is AFTER the image has been captured.
            # Can it be estimated better? CaptureStart + (CaptureEnd - CaptureStart) / 2 ?
            self.log("astrocamera.CaptureSetFull(): Image loaded.", terminal=False)
            if (
                " -r " in (camera_command + " ") or " --raw " in (camera_command + " ")
            ) and self.parameters.camera_enabled:  # The jpg contains RAW data in the file tags, extract it. Convert it.
                if (
                    self.parameters.camera_driver == "raspistill"
                ):  # We need to manually extract the DNG data.
                    # with raspistill convert to RAW. We have to extract the raw data RAW for .dng files to be saved.
                    self.log(
                        "astrocamera.CaptureSetFull(): Converting to RAW (.DNG) file...",
                        terminal=False,
                    )
                    dngname = outputfile.replace(".jpg", ".dng")
                    try:
                        self.pi_dng.convert(
                            outputfile
                        )  # Convert the saved .jpg file into the raw .dng format.
                    except Exception as e:
                        self.report_exception(
                            e,
                            comment="astrocamera.CaptureSetFull(): PiDNG.convert failed.",
                        )
                    self.log(
                        "astrocamera.CaptureSetFull(): Converted to RAW (.DNG) file.",
                        terminal=False,
                    )
                    # Cleanup. Remove any intermediate files that are nolonger needed.
                    if (
                        self.camera_save_jpg
                    ):  # We should save only the jpg data, stripping out any embedded additional RAW data
                        self.image.save_file(
                            outputfile
                        )  # Save the JPG file, but remove the 'raw' data. This overwrites the original file generated by raspistill.
                    else:  # We're only saving the RAW data, so just delete the original jpg file.
                        self.log(
                            "astrocamera.CaptureSetFull(): Deleting intermediate .jpg file...",
                            terminal=False,
                        )
                        self.cleanup_lastjpg()  # We've finished with the original .jpg on disc.
                    if (
                        not self.camera_save_dng
                    ):  # We don't need to keep the .dng file anymore.
                        self.log(
                            "astrocamera.CaptureSetFull(): DNG nolonger needed.",
                            terminal=False,
                        )
                        cmd = "rm " + dngname
                        self.os_cmd(cmd, output="log")
                    else:
                        if self.parameters.camera_window is not None:
                            self.parameters.camera_window.print(
                                now_hour_minute_sec() + " " + dngname.split("/")[-1]
                            )  # Just the dng filename.
                elif (
                    self.parameters.camera_driver == "pilomarfits"
                ):  # The .fits file will have been made automatically for us.
                    fitsname = outputfile.replace(
                        ".jpg", ".fits"
                    )  # Construct the .fits filename we expect.
                    self.log(
                        "astrocamera.CaptureSetFull(): FITS file should have been generated too.",
                        terminal=False,
                    )
                    if self.parameters.camera_window is not None:
                        self.parameters.camera_window.print(
                            now_hour_minute_sec() + " " + fitsname.split("/")[-1]
                        )  # Just the dng filename.
            if tempfile:  # Delete the temporary file.
                cmd = "rm " + outputfile
                self.os_cmd(cmd, output="log")
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
                        "astrocamera.CaptureSetFull:",
                        str(i + 1),
                        "of",
                        str(batch_size),
                        "(",
                        str(pc_complete),
                        "%), Disc:",
                        str(int(self.storage_monitor.free_mega_bytes())),
                        "Mb, ETA:",
                        str(dt_eta).split(" ")[1].split(".")[0],
                        terminal=terminal,
                    )
                else:
                    self.log(
                        "astrocamera.CaptureSetFull:",
                        str(i + 1),
                        "of",
                        str(batch_size),
                        "(",
                        str(pc_complete),
                        "%), Disc: UNKNOWN, ETA:",
                        str(dt_eta).split(" ")[1].split(".")[0],
                        terminal=terminal,
                    )
                if (
                    i < batch_size - 1
                ):  # If we have more photographs to process, keep the cursor on the same line so that the status line updates neatly.
                    print(
                        TextColor.cursorup() + TextColor.cursorup()
                    )  # Stay on the same line for the CaptureSet message to the terminal.
            if (
                self.storage_monitor is not None and not self.storage_monitor.disc_ok()
            ):  # Check there is enough disc space to continue.
                # Out of free space, stop!
                self.log(
                    "astrocamera.CaptureSetFull(): Out of disc space. Stopping.",
                    level="error",
                )
                result = False
                break
        self.log("astrocamera.CaptureSetFull(): Completed", terminal=False)
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
        This just captures the combined JPG & DNG data file. It does not perform conversion to other file types.
        This is testing if it improves performance for image capture by delaying processing until the observation is over.

        cleanup = True. means that intermediate files (.jpg) are deleted when finished with.
              False. means that the intermediate files (.jpg) are retained for the calling function to deal with.
              astrocamera.Lastjpg contains the filename of the .jpg file generated.
        tempfile = True. Means that a single temporary filename is used each time.
        terminal=True. Means that the progress message is shown on the terminal.
        astrotime = the timestamp of the image to be generated if we're faking the result.
        stacker = a handle to a live image stacker object if we're live stacking."""
        result = True
        self.log(
            "astrocamera.CaptureSetFast(): Capturing " + str(batch_size) + " images...",
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
                "astrocamera.CaptureSetFast(): Capturing",
                outputfile,
                "...",
                terminal=False,
            )
            cmd = camera_command.replace(
                "{&output}", outputfile
            )  # *Q* TODO: Perform safety check for remaining & symbols.
            if self.mctl is not None:  # Microcontroller handle is defined.
                remoterestarts = (
                    self.mctl.remote_restarts
                )  # If this changes during exposure, the microcontroller has reset and we should reject the image.
            else:
                remoterestarts = 0
            rejectimage = (
                False  # Set to 'true' if there's a reason to reject the image.
            )
            self.capture_start = now_utc()
            if self.parameters.camera_enabled:  # Camera is in use. Take real photo.
                self.os_cmd(cmd, output="none")
                retc = (
                    self.os_command.return_code
                )  # What did the camera command exit with ?
                self.log(
                    "astrocamera.CaptureSetFast(): Return code:", retc, terminal=False
                )
                if retc != 0:  # Non zero return code. Did something go wrong?
                    if self.parameters.camera_window is not None:
                        self.parameters.camera_window.print(
                            now_hour_minute_sec() + " Return code " + str(retc),
                            fg=TextColor.YELLOW,
                        )
                    if self.parameters.error_window is not None:
                        self.parameters.error_window.print(
                            now_hour_minute_sec()
                            + " capture returned code "
                            + str(retc),
                            fg=TextColor.YELLOW,
                        )
            else:  # Camera is not in use. Generate fake photo.
                self.log(
                    "astrocamera.CaptureSetFast(): About to call FakePhoto.",
                    terminal=False,
                )
                tr = False  # Fake image generation failed unless we are told otherwise.
                imty = self.get_image_type()  # What type of image are we faking?
                delay_timer = self.set_fake_delay(
                    camera_command
                )  # Create a timer to mimic the expected real camera delay.
                if imty == "dark":
                    tr = self.fake_dark(outputfile=outputfile)  # Fake a dark frame.
                else:
                    tr = self.fake_photo(
                        outputfile=outputfile, astrotime=astrotime
                    )  # Fake a light frame.
                if not tr:  # Image generation failed.
                    self.log(
                        "astrocamera.CaptureSetFast(): Fake image call failed (",
                        imty,
                        ").",
                        terminal=True,
                        level="error",
                    )
                else:  # Fake the expected exposure time if a real image was being captured.
                    delay_timer.wait()  # Wait until the fake delay timer expires. Thread pauses here.
                self.log(
                    "astrocamera.CaptureSetFast(): Returned from FakePhoto.",
                    terminal=False,
                )
            self.capture_end = now_utc()
            self.log(
                "astrocamera.CaptureSetFast(): Capture complete. (",
                (self.capture_end - self.capture_start).total_seconds(),
                "s).",
                terminal=False,
            )
            if self.mctl is not None:  # Microcontroller handle is known.
                if (
                    remoterestarts != self.mctl.remote_restarts
                ):  # Microcontroller reset during exposure.
                    self.log(
                        "astrocamera.CaptureSetFast(): Microcontroller restarted during exposure. Reject",
                        outputfile,
                        level="warning",
                        terminal=False,
                    )
                    if self.parameters.camera_window is not None:
                        self.parameters.camera_window.print(
                            now_hour_minute_sec() + " Motors reset during exposure."
                        )  # Just the filename.
                    if self.parameters.error_window is not None:
                        self.parameters.error_window.print(
                            now_hour_minute_sec() + " Motors reset during exposure."
                        )  # Just the filename.
                    rejectimage = True  # We should reject this image.
            if (
                not tempfile
            ):  # Display the filename if it's permanent, ignore the tempfile.
                if self.parameters.camera_window is not None:
                    self.parameters.camera_window.print(
                        now_hour_minute_sec() + " " + outputfile.split("/")[-1]
                    )  # Just the jpg filename.
            if rejectimage:  # There was reason to reject the image for some cause.
                self.log(
                    "astrocamera.CaptureSetFast(): Image should be rejected.",
                    terminal=False,
                )
            self.lastjpg = (
                outputfile  # The camera can remember this file as the 'last jpg taken'
            )
            self.log(
                "astrocamera.CaptureSetFast(): Load image from " + outputfile,
                terminal=False,
            )
            self.image.load_file(outputfile)  # OpenCV format.
            if (
                self.image.image_missing()
            ):  # imread failed. The capture did not succeed for some reason?
                self.log(
                    "astrocamera.CaptureSetFast(): imread of",
                    outputfile,
                    "failed.",
                    terminal=False,
                )
            self.last_image_date_time = (
                now_utc()
            )  # *Q* This timestamp is AFTER the image has been captured. Can it be estimated better? CaptureStart + (CaptureEnd - CaptureStart) / 2 ?
            self.log("astrocamera.CaptureSetFast(): Image loaded.", terminal=False)
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
                        "astrocamera.CaptureSetFast():",
                        str(i + 1),
                        "of",
                        str(batch_size),
                        "(",
                        str(pc_complete),
                        "%), Disc:",
                        str(int(self.storage_monitor.free_mega_bytes())),
                        "Mb, ETA:",
                        str(dt_eta).split(" ")[1].split(".")[0],
                        terminal=terminal,
                    )
                else:
                    self.log(
                        "astrocamera.CaptureSetFast():",
                        str(i + 1),
                        "of",
                        str(batch_size),
                        "(",
                        str(pc_complete),
                        "%), Disc: UNKNOWN, ETA:",
                        str(dt_eta).split(" ")[1].split(".")[0],
                        terminal=terminal,
                    )
                if (
                    i < batch_size - 1
                ):  # If we have more photographs to process, keep the cursor on the same line so that the status line updates neatly.
                    print(
                        TextColor.cursorup() + TextColor.cursorup()
                    )  # Stay on the same line for the CaptureSet message to the terminal.
            if (
                self.storage_monitor is not None and not self.storage_monitor.disc_ok()
            ):  # Check there is enough disc space to continue.
                # Out of free space, stop!
                self.log(
                    "astrocamera.CaptureSetFast(): Out of disc space. Stopping.",
                    level="error",
                )
                result = False
                break
        self.log("astrocamera.CaptureSetFast(): Completed", terminal=False)
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
        It creates a temporary instance of pilomarkeogram() to process the data.
        At the end it saves a /keogram.jpg file in the same /light folder."""
        self.log("astrocamera.BuildKeogram(): Starting", terminal=False)
        rootfolder = self.folder_handler.get_path(
            "light"
        )  # This is the parent data folder for all Pilomar images.
        filepattern = rootfolder + "/light_*.jpg"
        self.log("astrocamera.BuildKeogram(): Searching", filepattern, terminal=False)
        allfiles = glob.glob(filepattern, recursive=False)  # Every jpg in this folder.
        filecount = len(allfiles)
        start = None  # Earliest image.
        end = None  # Latest image.
        if len(allfiles) > 0:
            keogramfile = self.folder_handler.prep_file(
                "light", "keogram.jpg"
            )  # Target filename.
            prgt = ProgressTimer(
                "keogram", target=filecount
            )  # Report progress and ETA.
            self.log(
                "astrocamera.BuildKeogram(): Processing",
                filecount,
                "images.",
                terminal=False,
            )
            print(" ")
            keo = pilomarkeogram(
                "keogram", self.sensor.pixel_width, self.sensor.pixel_height
            )  # Define new Keogram instance.
            imagehandler = PilomarImage(
                "keogram-input", logger=self.logger
            )  # Load each image in turn.
            for i, file in enumerate(allfiles):  # Go through all the .jpg files found.
                prgt.update_count(
                    i + 1
                )  # How far have we got so far? prgt will then produce ETA and % complete for us.
                self.log("astrocamera.BuildKeogram(): Processing", file, terminal=False)
                print(
                    TextColor.cursorup() + now_hour_minute_sec(),
                    TextColor.white(str(round(prgt.get_percent(), 1))),
                    "%",
                    (i + 1),
                    "of",
                    filecount,
                    "ETA",
                    str(prgt.get_eta()).split(".")[0],
                    "UTC",
                    TextColor.clearlineforward(),
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
                keo.extract(imagehandler)
            # Markup image.
            keo.build_image_buffer()  # Load the resulting raw keogram into a pilomarimage instance. (For markup)
            width = keo.keogram.get_width()
            height = keo.keogram.get_height()
            # Add altitude scale
            base_alt = altitude - (
                self.lens.fov_vertical / 2
            )  # What altitude does the bottom of the image represent?
            top_alt = altitude + (
                self.lens.fov_vertical / 2
            )  # What altitude does the top of the image represent?
            floor_alt = math.floor(
                base_alt
            )  # Lowest integer altitude, will be just below the bottom edge of the image.
            ceiling_alt = math.ceil(
                top_alt
            )  # Heighest integer altitude, will be just above the top edge of the image.
            keo.keogram.draw_line(
                (width - 10, 0), (width - 10, height), color=PilomarImage.bgr("Yellow")
            )  # Draw axis for altitude tick marks.
            keo.keogram.add_text(
                "Altitude", width - 10, 40, color=PilomarImage.bgr("Yellow"), hjust="r"
            )  # Label the altitude axis.
            for a in range(floor_alt, ceiling_alt):  # Mark off each degree of altitude.
                y = height - int(
                    height * (a - base_alt) / (top_alt - base_alt)
                )  # Pixel height up the image for this degree marker.
                keo.keogram.draw_line(
                    (width - 50, y), (width - 10, y), color=PilomarImage.bgr("Yellow")
                )  # Draw tickmark for the degree marker.
                keo.keogram.add_text(
                    str(a) + "deg",
                    width - 50,
                    y,
                    color=PilomarImage.bgr("Yellow"),
                    hjust="r",
                )  # Label the degree marker.
            if len(allfiles) > 1:  # Need at least 2 files in order to add time scale.
                keo.keogram.draw_line(
                    (0, height - 10),
                    (width, height - 10),
                    color=PilomarImage.bgr("Cyan"),
                )  # Draw horizontal axis for the time scale.
                keo.keogram.add_text(
                    "<-" + str(start)[11:19],
                    10,
                    height - 130,
                    color=PilomarImage.bgr("Cyan"),
                    hjust="l",
                )  # Mark START time.
                keo.keogram.add_text(
                    str(end)[11:19] + "->",
                    width - 10,
                    height - 130,
                    color=PilomarImage.bgr("Cyan"),
                    hjust="r",
                )  # Mark END time.
                keo.keogram.add_text(
                    "< Time >",
                    int(width / 2),
                    height - 10,
                    color=PilomarImage.bgr("Cyan"),
                    vjust="t",
                    hjust="c",
                )  # Label the axis.
                # Add time scale
                floor_time = datetime(
                    start.year,
                    start.month,
                    start.day,
                    start.hour,
                    0,
                    0,
                    0,
                    tzinfo=timezone.utc,
                )  # Hour just before observation starts (Just off the left of the image)
                ceiling_time = datetime(
                    end.year, end.month, end.day, end.hour, 0, 0, 0, tzinfo=timezone.utc
                ) + timedelta(
                    hours=1
                )  # Hour just after observation ends (Just off the right of the image)
                range_time = int(
                    (ceiling_time - floor_time).total_seconds()
                )  # What's the timespan of the Floor to Ceiling time (in seconds).
                observation_time = int(
                    (end - start).total_seconds()
                )  # What's the timespan of the actual observation images (in seconds).
                pixels_per_second = (
                    width / observation_time
                )  # How many pixels represent 1 second of time?
                x_offset = (
                    start - floor_time
                ).total_seconds() * pixels_per_second  # Calculate a pixel offset for the time scale, it will start at floor_time to the left of the image.
                if observation_time > 7200:
                    range_step = (
                        3600  # If observation is > 2hrs, label the Hourly tickmarks.
                    )
                elif observation_time > 1200:
                    range_step = 600  # If Observation is > 20 minutes, label in 10 minute tickmarks.
                else:
                    range_step = 300  # Label in 5 minute tickmarks.
                for a in range(
                    0, range_time, range_step
                ):  # Mark significant time steps.
                    x = int(
                        a * pixels_per_second - x_offset
                    )  # X axis location for the tickmark.
                    keo.keogram.draw_line(
                        (x, height - 10),
                        (x, height - 100),
                        color=PilomarImage.bgr("Cyan"),
                    )  # Draw tickmark.
                    text = str(floor_time + timedelta(seconds=a))[
                        11:19
                    ]  # Calculate HH:MM:SS time of the tickmark.
                    keo.keogram.add_text(
                        text, x, height - 100, color=PilomarImage.bgr("Cyan"), hjust="c"
                    )  # Label the tickmark with the HH:MM:SS time.
            # Add key/labels
            linelist = []  # Start assembling a block of text.
            linelist.append("Observation start: " + str(start).split("+")[0] + " UTC")
            linelist.append("Observation end: " + str(end).split("+")[0] + " UTC")
            if start is not None and end is not None:
                linelist.append(
                    "Duration: " + human_readable_seconds((end - start).total_seconds())
                )
            linelist.append("Images captured: " + str(keo.sample_count))
            linelist.append("Target alt: " + str(altitude) + ", az:" + str(azimuth))
            if altitude is not None:
                linelist.append(
                    "Altitude range: "
                    + str(round(base_alt, 1))
                    + "deg to "
                    + str(round(top_alt, 1))
                    + "deg"
                )
            ypos = 50  # Text box at TOP of image.
            keo.keogram.add_text_block(
                linelist,
                20,
                ypos,
                size=1,
                color=PilomarImage.bgr("White"),
                bgcolor=PilomarImage.bgr("Black"),
                border=3,
            )  # Write data.
            # Save resulting image.
            keo.save_file(keogramfile)
        print("")  # Move cursor down so that the stats can be seen.
        return True

    def process_image_files(self):
        """If image conversions were not done during capture, this can find and convert all the
        image files currently in storage. This is used if CaptureSetFast was used to gather
        images as quickly as possible.
        This will convert all image files found the have the characteristics of a jpg with embedded raw data.
        """
        self.log("astrocamera.ProcessImageFiles(): Starting", terminal=True)
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
            "astrocamera.ProcessImageFiles(): Searching", filepattern, terminal=True
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
            "astrocamera.ProcessImageFiles(): Found",
            filecount,
            "files to process.",
            terminal=True,
        )
        tempimage = PilomarImage(name="temp", logger=self.logger)
        if filecount > 0:
            for file in files:
                print(file)
                # Load jpg data into temporary buffer.
                tempimage.LoadFile(file)
                if tempimage.ImageMissing():  # imread failed.
                    self.log(
                        "astrocamera.ProcessImageFiles: imread",
                        file,
                        "failed.",
                        terminal=False,
                    )
                else:  # imread was successful.
                    self.log(
                        "astrocamera.ProcessImageFiles: Converting to RAW (.DNG) file...",
                        terminal=False,
                    )
                    if (
                        self.camera_save_dng
                    ):  # We don't need to keep the .dng file anymore.
                        try:
                            self.pi_dng.convert(
                                file
                            )  # Convert the saved .jpg file into the raw .dng format. The .dng filename is automatically generated.
                        except Exception as e:
                            self.log.ReportException(
                                e,
                                comment="astrocamera.ProcessImageFiles() error when converting to DNG file.",
                            )
                    # Replace the .jpg file with a simpler file, or delete it completely.
                    if (
                        self.camera_save_jpg
                    ):  # We should save 'JUST' the jpg data, effectively stripping out the embedded RAW data
                        tempimage.SaveFile(
                            file
                        )  # Save the JPG file, but remove the 'raw' data. This overwrites the original file generated by raspistill.
                    else:  # We're only saving the RAW data, so just delete the original jpg file.
                        self.log(
                            "astrocamera.ProcessImageFiles: Deleting intermediate .jpg file...",
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
        self.log("astrocamera.ProcessImageFiles(): Done", terminal=True)
        return True

    def clear_camera_options(self):
        """Clear the camera options list."""
        self.log("astrocamera.Clearcamera_options", terminal=False)
        self.camera_options = ""  # Empty the options list.

    def add_camera_option(self, new_option):
        """Add an option to the camera option list.
        This gives possibility to validate options as they are added."""
        self.log("astrocamera.AddCameraOption:", new_option, terminal=False)
        new_option = (
            new_option.strip(" ") + " "
        )  # Make sure there's a single separator character after the option.
        new_key = new_option.split(" ")[0]  # What is the option key we are setting?
        # Split all the existing options into a list.
        option_list_entries = self.camera_options.split("-")
        for ole in option_list_entries:
            ole = "-" + ole  # Add the lost '-' tag back to each entry.
        found = False
        # If the option is already in the list, update it to the new value.
        for ole in option_list_entries:
            if ole.split(" ")[0] == new_key:
                found = True
                ole = new_option
                break
        if not found:  # If the option is NOT in the list, add it now.
            option_list_entries.append(new_option)
        # Construct the new version of the option list ready for returning.
        self.camera_options = ""
        for ole in option_list_entries:
            self.camera_options += ole
        self.log(
            "astrocamera.AddCameraOption: New list:",
            self.camera_options,
            terminal=False,
        )

    def del_camera_option(self, del_option):
        """Remove an option from the camera option list."""
        self.log("astrocamera.DelCameraOption:", del_option, terminal=False)
        del_key = del_option.split(" ")[0]  # What is the option key we are setting?
        # Split all the existing options into a list.
        option_list_entries = self.camera_options.split("-")
        for ole in option_list_entries:
            ole = "-" + ole  # Add the lost '-' tag back to each entry.
        # Construct the new version of the option list ready for returning but ignore the deleted option.
        self.camera_options = ""
        for ole in option_list_entries:
            if ole.split(" ")[0] != del_key:
                self.camera_options += ole
        self.log(
            "astrocamera.DelCameraOption: New list:",
            self.camera_options,
            terminal=False,
        )

    def contains_meteors(self, image):  # In pilomarimage
        """Return TRUE if meteors or aircraft trails are detected in an image."""
        if len(self.image.line_detection()) > 0:
            return True
        else:
            return False

    def take_photo(self, batch_size, terminal=True):
        """Make an observation. This is a LIGHT image of the actual object under observation."""
        self.log("astrocamera.TakePhoto: Begin", terminal=False)
        exposure_microseconds = int(self.exposure_seconds * 1000000)
        self.set_image_type("light")  # Tell the camera we are taking light photos.
        file_root = self.folder_handler.prep_file("light", "light_")
        # raspistill -o {&output} -ex off -t 10 -n -q 100 -md {&mode} -w {&width} -h {&height} -ag 16.0 -ss {&shutter}
        # libcamera-still --output {&output} --timeout 10 --nopreview --quality 100 --width {&width} --height {&height} --denoise off --analoggain 16.0 --shutter {&shutter}
        # python3 pilomarfits.py --output {&output} --quality 100 --width {&width} --height {&height} --denoise off --shutter {&shutter}
        camera_command = self.parameters._camera_light_command
        camera_command = camera_command.replace(
            "{&shutter}", str(int(exposure_microseconds))
        )
        # CaptureSet will automatically set mode,width and height parameters if they are in the command line.
        if (
            self.camera_save_dng or self.camera_save_fits
        ):  # If we intend to produce DNG/FITS raw data at some point, we need to capture the bayer matrix.
            camera_command += (
                " " + self.parameters._camera_raw_switch + " "
            )  # Append RAW data to the image.
        result = self.capture_set(
            file_root=file_root,
            batch_size=batch_size,
            camera_command=camera_command,
            terminal=terminal,
            cleanup=False,
        )
        if not result:
            self.log("astrocamera.TakePhoto: CaptureSet failed.", level="error")
        self.log("astrocamera.TakePhoto: Complete", terminal=False)
        return result

    def prompt_photo_settings(self, batch_size, terminal=True):
        """Take a single image, but prompt the user for the settings."""
        self.log("astrocamera.PromptPhotoSettings: Begin", terminal=False)
        exposure_microseconds = int(self.exposure_seconds * 1000000)
        self.set_image_type("light")  # Tell the camera we are taking light photos.
        file_root = self.folder_handler.prep_file("light", "light_")
        camera_options = ""
        camera_options += "-ex off "  # Exposure control off.
        camera_options += "-t 10 "  # Timeout ms - This is an attempt to take the photo
        # as fast as possible, but pre-photo calculations double the requested time :(
        camera_options += "-n "  # Nopreview
        camera_options += (
            "-md " + str(self.sensor.mode) + " "
        )  # Mode 3 allows exposures over 10.2 seconds apparently.
        camera_options += (
            "-w " + str(self.sensor.pixel_width) + " "
        )  # Specify the pixel size of the image to match the maximum that the mode supports.
        camera_options += (
            "-h " + str(self.sensor.pixel_height) + " "
        )  # Specify the pixel size of the image to match the maximum that the mode supports.
        camera_options += (
            "-ss " + str(exposure_microseconds) + " "
        )  # Use the global SHUTTER time to match the DARK and LIGHT frames.
        if (
            self.camera_save_dng and "-r " not in camera_options
        ):  # If we intend to produce DNG raw data at some point, we need to capture the bayer matrix.
            # *Q* Expand for FITS files too.
            camera_options += (
                "-r "  # Raw is appended to JPEG file. Needs extracting later.
            )
        camera_options += "-ag 16.0 "
        # Set analog gain to 16.0. Apparently this is better
        # for Astro photographs as it increases signal-to-noise ratio significantly.
        # Offer the default settings to the user, but let them enter something else.
        print(
            "PromptPhotoSettings: [ENTER] to accept default settings or create your own."
        )
        print("raspistill " + camera_options)
        newopt = input(TextColor.cyan("raspistill "))
        if len(newopt) > 0:  # User chose to overwrite the default settings.
            camera_options = newopt
            self.log("astrocamera.PromptPhotoSettings:", camera_options, terminal=True)
        self.last_light_options = camera_options  # keep a note of the exposure options, it's reported in the preview images.
        result = self.capture_set(
            file_root=file_root,
            batch_size=batch_size,
            camera_command=camera_options,
            terminal=terminal,
            cleanup=False,
        )
        if not result:
            self.log(
                "astrocamera.PromptPhotoSettings: CaptureSet failed.", level="error"
            )
        else:
            self.log("Photo captured as:", self.lastjpg, terminal=True)
        self.log("astrocamera.PromptPhotoSettings: Complete", terminal=False)
        return result

    def meteor_file_scan(self):
        """If image conversions were not done during capture, this can find and convert all the
        image files currently in storage. This is used if CaptureSetFast was used to gather
        images as quickly as possible.
        This will convert all image files found the have the characteristics of a jpg with embedded raw data.
        """
        self.log("astrocamera.MeteorFileScan(): Starting", terminal=True)
        # Find all image files that need converting.
        rootfolder = self.folder_handler.get_path(
            "imageroot"
        )  # This is the parent data folder for all Pilomar images.
        self.log(
            "astrocamera.MeteorFileScan(): Searching for .jpgs in",
            rootfolder,
            terminal=True,
        )
        allfiles = glob.glob(
            rootfolder + "/**/*.jpg", recursive=True
        )  # Every jpg in every folder and subfolder.
        files = []  # Cleaned list of files to handle.
        folders = ["light"]  # Which subfolders do we want?
        candidatefilename = self.folder_handler.prep_file(
            "imageroot", "MeteorCandidates_" + utc_time_stamp() + ".txt"
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
        meteor_files = []  # Resulting list of meteor files.
        self.log(
            "astrocamera.MeteorFileScan(): Found",
            filecount,
            "files to process.",
            terminal=True,
        )
        print(" ")  # Blank line for incremental counter to occupy.
        if filecount > 0:
            tempimage = PilomarImage(name="temp", logger=self.logger)
            for i, file in enumerate(files):
                # Check for EXIT from keyboard.
                kcl = self.keyboard.check().lower()
                if kcl in ["x", chr(27)]:  # Exit key pressed.
                    print("")
                    print("** Quit **")
                    break
                print(
                    TextColor.cursorup()
                    + TextColor.clearforward()
                    + now_hour_minute_sec(),
                    "Scanning",
                    (i + 1),
                    "of",
                    filecount,
                    "(" + file.split("/")[-1] + ")",
                    "Found",
                    len(meteor_files),
                    "candidates,",
                )
                # Load jpg data into temporary buffer.
                tempimage.LoadFile(file)
                if tempimage.ImageMissing():  # imread failed.
                    self.log(
                        "astrocamera.ProcessImageFiles: imread",
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
                        meteor_files.append(
                            file
                        )  # Add to list of files containing potential meteor trails. (Could be aircraft or satellites too).
        else:  # Filecount == 0
            print(TextColor.yellow("No suitable image files were found."))
        self.log(
            "Found potential meteor trails in",
            len(meteor_files),
            "of",
            len(files),
            "images",
            terminal=True,
        )
        if len(meteor_files) > 0:  # Write file of candidates.
            with open(candidatefilename, "w") as f:
                for file in meteor_files:
                    f.write(file + "\n")
            self.log("Candidate filenames written to", candidatefilename, terminal=True)
        self.log("astrocamera.MeteorFileScan(): Done", terminal=True)
        return meteor_files  # List of candidate files.

    def take_tracking_photo(self, batch_size, terminal=True):
        """Make an observation. This is a TRACKING image of the actual object under observation.
        Similar to TakePhoto, except the exposure is fixed to give a more consistent star count for image matching.
        """
        self.log("astrocamera.TakeTrackingPhoto: Begin", terminal=False)
        exposure_microseconds = self.tracking_exposure_seconds * 1000000
        self.set_image_type(
            "tracking"
        )  # Tell the camera we are taking tracking photos.
        file_root = self.folder_handler.prep_file("tracking", "tracking_")
        camera_command = self.parameters._camera_tracking_command
        # CaptureSet will automatically set mode,width and height parameters if they are in the command line.
        camera_command = camera_command.replace(
            "{&shutter}", str(int(exposure_microseconds))
        )
        result = self.capture_set(
            file_root=file_root,
            batch_size=batch_size,
            camera_command=camera_command,
            tempfile=True,
            terminal=terminal,
            cleanup=False,
        )
        self.log("astrocamera.TakeTrackingPhoto: Complete", terminal=False)
        return result

    def dark_set(self, batch_size):
        """Take a DARK set of images for photo stacking."""
        print(TextColor.yellow("DarkSet"))
        exposure_microseconds = int(self.exposure_seconds * 1000000)
        self.set_image_type("dark")  # Tell the camera we are taking dark photos.
        file_root = self.folder_handler.prep_file("dark", "dark_")
        self.log("Generating DARK image set.")
        self.log(
            "These match the LIGHT exposure time of", self.exposure_seconds, "seconds."
        )
        self.log("These are used to remove electrical noise from the images.")
        self.log("Lens cap must be ON.")
        self.log("Images will be stored in", file_root)
        input(TextColor.cyan("[RETURN] to begin: "))  # Python3
        print("Capturing Dark image set...")
        camera_command = self.parameters._camera_dark_command
        # CaptureSet will automatically set mode,width and height parameters if they are in the command line.
        camera_command = camera_command.replace(
            "{&shutter}", str(int(exposure_microseconds))
        )
        if (
            self.camera_save_dng or self.camera_save_fits
        ):  # If we intend to produce DNG raw data at some point, we need to capture the bayer matrix.
            camera_command += (
                " " + self.parameters._camera_raw_switch + " "
            )  # Append RAW data to the image.
        result = self.capture_set(
            file_root=file_root, batch_size=batch_size, camera_command=camera_command
        )
        return result

    def image_types(self):
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

    def dark_flat_set(self, batch_size):
        """Take a DARK-FLAT set of images for photo stacking."""
        print(TextColor.yellow("DarkFlatSet"))
        exposure_microseconds = int(0.001 * 1000000)  # 1/1000th of a second.
        self.set_image_type(
            "darkflat"
        )  # Tell the camera we are taking darkflat photos.
        file_root = self.folder_handler.prep_file("darkflat", "darkflat_")
        self.log("Generating DARK FLAT image set.")
        self.log(
            "These help remove electrical and manufacturing noise from the images."
        )
        self.log(
            "These match the FLAT exposure time of",
            exposure_microseconds / 1000000.0,
            "seconds.",
        )
        self.log("Lens cap must be ON.")
        self.log("Images will be stored in", file_root)
        input(TextColor.cyan("[RETURN] to begin: "))  # Python3
        print("Capturing Dark-Flat image set...")
        camera_command = self.parameters._camera_dark_flat_command
        # CaptureSet will automatically set mode,width and height parameters if they are in the command line.
        camera_command = camera_command.replace(
            "{&shutter}", str(int(exposure_microseconds))
        )
        if (
            self.camera_save_dng or self.camera_save_fits
        ):  # If we intend to produce DNG raw data at some point, we need to capture the bayer matrix.
            camera_command += (
                " " + self.parameters._camera_raw_switch + " "
            )  # Append RAW data to the image.
        result = self.capture_set(
            file_root=file_root, batch_size=batch_size, camera_command=camera_command
        )
        return result

    def flat_set(self, batch_size):
        """Take a FLAT set of images for photo stacking."""
        print(TextColor.yellow("FlatSet"))
        self.set_image_type("flat")  # Tell the camera we are taking flat photos.
        file_root = self.folder_handler.prep_file("flat", "flat_")
        self.log("Generating FLAT image set.")
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
        self.log("Images will be stored in", file_root)
        input(TextColor.cyan("[RETURN] to begin: "))  # Python3
        print("Capturing Flat image set...")
        camera_command = self.parameters._camera_flat_command
        # CaptureSet will automatically set mode,width and height parameters if they are in the command line.
        if (
            self.camera_save_dng or self.camera_save_fits
        ):  # If we intend to produce DNG raw data at some point, we need to capture the bayer matrix.
            camera_command += (
                " " + self.parameters._camera_raw_switch + " "
            )  # Append RAW data to the image.
        result = self.capture_set(
            file_root=file_root, batch_size=batch_size, camera_command=camera_command
        )
        return result

    def bias_set(self, batch_size):
        """Take a BIAS/OFFSET set of images for photo stacking."""
        print(TextColor.yellow("BiasSet"))
        exposure_microseconds = int(0.001 * 1000000)  # 1/1000th of a second.
        self.set_image_type("bias")  # Tell the camera we are taking bias photos.
        file_root = self.folder_handler.prep_file("bias", "bias_")
        self.log("Generating OFFSET/BIAS image set.")
        self.log(
            "These will be the shortest possible exposure time (FASTEST)",
            exposure_microseconds / 1000000.0,
            "seconds",
        )
        self.log(
            "The temperature and ISO settings must be the same as the LIGHT images."
        )
        self.log(
            "These are used to remove manufacturing defects from the images that the sensor captures."
        )
        self.log("Lens cap must be ON.")
        input(TextColor.cyan("[RETURN] to begin: "))  # Python3
        print("Capturing Bias image set...")
        camera_command = self.parameters._camera_bias_command
        # CaptureSet will automatically set mode,width and height parameters if they are in the command line.
        camera_command = camera_command.replace(
            "{&shutter}", str(int(exposure_microseconds))
        )
        if (
            self.camera_save_dng or self.camera_save_fits
        ):  # If we intend to produce DNG raw data at some point, we need to capture the bayer matrix.
            camera_command += (
                " " + self.parameters._camera_raw_switch + " "
            )  # Append RAW data to the image.
        result = self.capture_set(
            file_root=file_root, batch_size=batch_size, camera_command=camera_command
        )
        return result

    def auto_photo(self):
        print(TextColor.yellow("AutoPhoto"))
        if not self.parameters.camera_enabled:
            self.log(
                "astrocamera.AutoPhoto(): Camera is disabled. No photo attempted.",
                level="warning",
            )
            return False
        file_root = self.folder_handler.prep_file("auto", "autophoto_")
        self.set_image_type("auto")
        print("Taking fully automatic photographs (Good for daylight testing).")
        print("Lens cap must be OFF.")
        print(
            "Camera must already be on-target, it will not track during AutoPhoto functions."
        )
        print("Camera will use automatic exposure settings in AutoPhoto mode.")
        print("Images will be stored in", file_root)
        inp = ""
        while inp != "x":
            inp = input("<RETURN> to begin ('x' to quit): ").lower()  # Python3
            if inp == "x":
                print("quit")
                break
            dt = self.clean_datetime_string(str(now_utc()))
            filename = file_root + dt + ".jpg"
            camera_command = self.parameters._camera_auto_command
            camera_command = camera_command.replace("{&mode}", str(self.sensor.mode))
            camera_command = camera_command.replace(
                "{&width}", str(self.sensor.pixel_width)
            )
            camera_command = camera_command.replace(
                "{&height}", str(self.sensor.pixel_height)
            )
            camera_command = camera_command.replace("{&output}", filename)
            # *Q* TODO: Perform safety check for remaining & symbols.
            self.os_cmd(camera_command)
            print("-", filename)
        return True
