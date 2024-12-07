"""This module contains the AstroLens class which is used to represent the lens being used by the telescope."""

from oscommand import OSCommand
from utils.logfile import LogFile
from utils.params import Parameters


class AstroLens:
    """Object representing the LENS being used by the telescope.
    Contains some attributes which are used to convert between FIELD OF VIEW and PHOTO DIMENSIONS for example.
    """

    LensList = []  # List of declared lenses.

    def __init__(
        self,
        length,
        horizontal_fov,
        vertical_fov,
        aperture=2.8,
        logger: LogFile = None,
        parameters: Parameters = None,
    ):
        self.set_logger(
            logger
        )  # CamLog # Handle to the class that handles logging and error tracing.
        self.os_command = OSCommand(logger=logger)  # Create OS command executor.
        self.parameters: Parameters = (
            parameters  # Must define parameter file before using instance.
        )
        self.base_length = (
            length  # The length of the lense WITHOUT any multiplier effect.
        )
        self.length = length  # 'focal length' of the lens.
        # pylint: disable=line-too-long
        # From https://www.seeedstudio.com/blog/2020/06/18/a-complete-guide-to-help-you-choose-lenses-for-your-raspberry-pi-high-quality-camera-m/
        # pylint: enable=line-too-long
        # 35mm equivalent focal length (?) (AKA the Crop Factor for the sensor?
        self.equiv_length = self.length * 5.6
        self.fov_horizontal = horizontal_fov
        self.fov_vertical = vertical_fov
        self.fov = min(
            self.fov_horizontal, self.fov_vertical
        )  # When calculating the FOV for a survey, use the smaller value.
        self.aperture = (
            aperture  # FStop of the lens. *Q* Multiplier will impact this too. Hmm...
        )
        self.id = (
            str(self.length)
            + "|"
            + str(self.fov_horizontal)
            + "|"
            + str(self.fov_vertical)
        )  # Unique ID of lens features.
        self.log(
            "AstroLens: Length:",
            str(self.length),
            "mm (equiv.",
            str(self.equiv_length),
            "mm) FoV:",
            str(self.fov_horizontal),
            "deg",
            "*",
            str(self.fov_vertical),
            "deg",
            terminal=False,
        )
        AstroLens.LensList.append(
            self
        )  # Add this instance to the global list of all defined lenses.

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
            self.log = logger  # Log method.
        if hasattr(logger, "ReportException"):
            self.report_exception = (
                logger.report_exception
            )  # Report exception details to logfile.
        if hasattr(logger, "RaiseException"):
            self.raise_exception = logger.raise_exception  # Report and raise exception.
        self.log("AstroLens.set_logger: Linked to this log file.", terminal=False)

    def _null_logger(self, *args, **kwargs):
        """Null logger. Absorbs parameters and .log call but does nothing.
        Use this when there is no logger defined."""
        return

    def estimate_fo_v(self, length):
        """Given 35mm equivalent focal length, this estimates the FoV for the lens on the Raspberry Pi Hi Quality sensor.
        This is just an estimation to get you started.
        The FoV can be finetuned by comparing the diameter of the moon's disc using astrocamera.CalibrateFoV function.
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
            "AstroLens.EstimateFoV():",
            self.equiv_length,
            self.fov_horizontal,
            self.fov_vertical,
            terminal=False,
        )
