#!/usr/bin/env python3
"""Parameter management for Pilomar telescope control.

This module provides the Parameters class for loading, storing,
and managing runtime parameters.
"""

import os
import json

from pilomar.core.base import AttributeMaster


class Parameters(AttributeMaster):
    """Class to load, store and manage parameters for the program.

    The Parameters class allows loading runtime parameters from a file.
    It can reload parameters during a run and automatically writes
    settings back to disc when the program closes.
    """

    def __init__(self, filename, logger=None, now_func=None):
        """Initialize parameters from file.

        Args:
            filename: Path to the JSON parameter file.
            logger: Optional logger instance.
            now_func: Function that returns current UTC datetime.
        """
        super().__init__(now_func=now_func)
        self.set_logger(logger=logger)
        self._dictionary = {}
        self._defaults = {}
        self.param_file_name = filename
        self.require_restart = False

        # Stepper driver data
        self.stepper_driver_data = None

        # Owner and privacy
        self.owner = None
        self.image_privacy = None

        # Batch sizes
        self.batch_size = None
        self.control_batch_size = None

        # Hardware features
        self.board_type = None
        self.uart_override = None
        self.camera_enabled = None
        self.backlash_enabled = None
        self.fault_sensitive = None
        self.mctl_led_status = None
        self.observation_resets_mctl = None
        self.observation_stop_pin = None
        self.ir_control_pin = None
        self.ir_cutoff = None
        self.tune_on_32_bit = None
        self.mctl_reset_pin = None
        self.uart_rx_queue_limit = None

        # Motor parameters
        self.min_azimuth_angle = None
        self.max_azimuth_angle = None
        self.azimuth_driver = None
        self.azimuth_gear_ratio = None
        self.azimuth_motor_steps_per_rev = None
        self.azimuth_slew_microstep_ratio = None
        self.azimuth_microstep_ratio = None
        self.azimuth_rest_angle = None
        self.azimuth_backlash_angle = None
        self.azimuth_orientation = None
        self.azimuth_limit_angle = None

        self.min_altitude_angle = None
        self.max_altitude_angle = None
        self.altitude_driver = None
        self.altitude_gear_ratio = None
        self.altitude_motor_steps_per_rev = None
        self.altitude_microstep_ratio = None
        self.altitude_slew_microstep_ratio = None
        self.altitude_rest_angle = None
        self.altitude_backlash_angle = None
        self.altitude_orientation = None
        self.altitude_limit_angle = None

        self.fast_time = None
        self.slow_time = None
        self.time_delta = None
        self.speed_list = None
        self.motor_status_delay = None
        self.slew_enabled = None
        self.trace_move = None
        self.optimise_moves = None
        self.mctl_comms_timeout = None

        # Image parameters
        self.use_usb_storage = None
        self.sd_path = None
        self.usb_path = None
        self.fast_flush = None
        self.fast_image_capture = None
        self.horizon_altitude = None
        self._horizon = None
        self.camera_save_jpg = None
        self.camera_save_dng = None
        self.camera_save_fits = None

        # Display parameters
        self.color_scheme = None
        self.debug_mode = None
        self.menu_title_fg = None
        self.menu_title_bg = None
        self.menu_subtitle_fg = None
        self.menu_subtitle_bg = None
        self.title_fg = None
        self.title_bg = None
        self.text_fg = None
        self.text_bg = None
        self.text_good = None
        self.text_poor = None
        self.text_bad = None
        self.border_fg = None
        self.border_bg = None

        # Trajectory parameters
        self.trajectory_window = None
        self.use_dynamic_trajectory_periods = None
        self.drift_tracking_enabled = None

        # Filter parameters
        self.scan_for_meteors = None
        self.min_satellite_altitude = None
        self.aurora_camera_altitude = None
        self.suggestion_magnitude = None
        self.suggestion_pixels = None
        self.saved_utc = None

        # Location parameters
        self.home_lat = None
        self.home_lon = None
        self.local_tz = None
        self._home_lat_val = 0.0
        self._home_lon_val = 0.0

        self.load_parameters()

    def load_parameters(self):
        """Load parameters from file if it exists.

        Missing values are defaulted. Called during __init__()
        and can be called again to reload.
        """
        if os.path.isfile(self.param_file_name):
            with open(self.param_file_name, "r", encoding="utf-8") as f:
                self.log("Loading parameters from file:", self.param_file_name)
                self._dictionary = json.load(f)

        self._init_stepper_driver_data()
        self._init_owner_and_privacy()
        self._init_batch_sizes()
        self._init_hardware_features()
        self._init_motor_parameters()
        self._init_image_parameters()
        self._init_display_parameters()
        self._init_trajectory_parameters()
        self._init_filter_parameters()
        self._init_location_parameters()

    def _init_stepper_driver_data(self):
        """Initialize stepper motor driver board data."""
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
        self.stepper_driver_data = self.get_param("StepperDriverData", sdd)

    def _init_owner_and_privacy(self):
        """Initialize owner and privacy settings."""
        self.owner = self.get_param("Owner", "telescope owner")
        self.image_privacy = self.get_param("ImagePrivacy", "high")

    def _init_batch_sizes(self):
        """Initialize batch size parameters."""
        self.batch_size = self.get_param("BatchSize", 100)
        self.control_batch_size = self.get_param("ControlBatchSize", 20)

    def _init_hardware_features(self):
        """Initialize hardware feature parameters."""
        self.board_type = self.get_param("BoardType", None)
        self.uart_override = self.get_param("UARTOverride", None)
        self.camera_enabled = self.get_param("CameraEnabled", True)
        self.backlash_enabled = self.get_param("BacklashEnabled", False)
        self.fault_sensitive = self.get_param("FaultSensitive", False)
        self.mctl_led_status = self.get_param("MctlLedStatus", True)
        self.observation_resets_mctl = self.get_param("ObservationResetsMctl", False)
        self.observation_stop_pin = self.get_param(
            "ObservationStopPin", 25, oldnames=["StopPin"]
        )
        self.ir_control_pin = self.get_param("IRControlPin", None)
        self.ir_cutoff = self.get_param("IRCutoff", True)
        self.tune_on_32_bit = self.get_param("TuneOn32Bit", True)
        self.mctl_reset_pin = self.get_param("MctlResetPin", 4)
        self.uart_rx_queue_limit = self.get_param("UartRxQueueLimit", 50)

    def _init_motor_parameters(self):
        """Initialize motor configuration parameters."""
        # Azimuth motor
        self.min_azimuth_angle = self.get_param("MinAzimuthAngle", 0)
        self.max_azimuth_angle = min(self.get_param("MaxAzimuthAngle", 360), 360)
        self.azimuth_driver = self.get_param("AzimuthDriver", "drv8825")
        self.azimuth_gear_ratio = self.get_param("AzimuthGearRatio", 240)
        self.azimuth_motor_steps_per_rev = self.get_param(
            "AzimuthMotorStepsPerRev", 400
        )
        self.azimuth_slew_microstep_ratio = self.get_param(
            "AzimuthSlewMicrostepRatio", 1
        )
        self.azimuth_microstep_ratio = self.get_param("AzimuthMicrostepRatio", 1)
        self.azimuth_rest_angle = self.get_param("AzimuthRestAngle", 180.0)
        self.azimuth_backlash_angle = self.get_param("AzimuthBacklashAngle", 0.0)
        self.azimuth_orientation = self.get_param("AzimuthOrientation", -1)
        self.azimuth_limit_angle = self.get_param("AzimuthLimitAngle", None)

        # Altitude motor
        self.min_altitude_angle = self.get_param("MinAltitudeAngle", 0)
        self.max_altitude_angle = min(self.get_param("MaxAltitudeAngle", 90), 90)
        self.altitude_driver = self.get_param("AltitudeDriver", "drv8825")
        self.altitude_gear_ratio = self.get_param("AltitudeGearRatio", 240)
        self.altitude_motor_steps_per_rev = self.get_param(
            "AltitudeMotorStepsPerRev", 400
        )
        self.altitude_microstep_ratio = self.get_param("AltitudeMicrostepRatio", 1)
        self.altitude_slew_microstep_ratio = self.get_param(
            "AltitudeSlewMicrostepRatio", 1
        )
        self.altitude_rest_angle = self.get_param("AltitudeRestAngle", 0.0)
        self.altitude_backlash_angle = self.get_param("AltitudeBacklashAngle", 0.0)
        self.altitude_orientation = self.get_param("AltitudeOrientation", -1)
        self.altitude_limit_angle = self.get_param("AltitudeLimitAngle", None)

        # Motor timing
        self.fast_time = self.get_param("FastTime", 0.001)
        self.slow_time = self.get_param("SlowTime", 0.05)
        self.time_delta = self.get_param("TimeDelta", 0.003)

        speed_list = {
            "Slow": {
                "label": "Slow (4ms / step)",
                "FastTime": 0.002,
                "SlowTime": 0.05,
                "TimeDelta": 0.003,
            },
            "Medium": {
                "label": "Medium (2ms / step)",
                "FastTime": 0.001,
                "SlowTime": 0.05,
                "TimeDelta": 0.003,
            },
            "Fast": {
                "label": "Fast (1ms / step)",
                "FastTime": 0.0005,
                "SlowTime": 0.05,
                "TimeDelta": 0.003,
            },
            "Turbo": {
                "label": "Turbo (0.2ms / step)",
                "FastTime": 0.0001,
                "SlowTime": 0.05,
                "TimeDelta": 0.003,
            },
        }
        self.speed_list = self.get_param("SpeedList", speed_list)

        self.motor_status_delay = self.get_param("MotorStatusDelay", 10)
        self.slew_enabled = self.get_param("SlewEnabled", False)
        self.trace_move = self.get_param("TraceMove", False, oldnames=["TraceMotor"])
        self.optimise_moves = self.get_param("OptimiseMoves", False)
        self.mctl_comms_timeout = self.get_param("MctlCommsTimeout", 120)

    def _init_image_parameters(self):
        """Initialize image storage parameters."""
        self.use_usb_storage = self.get_param("UseUSBStorage", True)
        self.sd_path = self.get_param("SDPath", "/")
        self.usb_path = self.get_param("USBPath", "/media/pi")
        self.fast_flush = self.get_param("FastFlush", False)
        self.fast_image_capture = self.get_param("FastImageCapture", False)
        self.horizon_altitude = self.get_param("HorizonAltitude", 0.0)
        self._horizon = max(
            self.horizon_altitude if self.horizon_altitude is not None else 0.0,
            self.min_altitude_angle if self.min_altitude_angle is not None else 0.0,
        )

        # Image file types
        self.camera_save_jpg = self.get_param("CameraSaveJpg", True)
        self.camera_save_dng = self.get_param("CameraSaveDng", True)
        self.camera_save_fits = self.get_param("CameraSaveFits", False)

        if not (self.camera_save_jpg or self.camera_save_dng or self.camera_save_fits):
            self.log(
                "No image types are saved according to the parameters.", level="warning"
            )

    def _init_display_parameters(self):
        """Initialize display and color scheme parameters."""
        self.color_scheme = self.get_param("ColorScheme", "green")
        self.debug_mode = self.get_param("DebugMode", False)

        # Default color scheme values (green)
        self.menu_title_fg = self.get_param("MenuTitleFG", 46)  # LIME
        self.menu_title_bg = self.get_param("MenuTitleBG", 22)  # DARKGREEN
        self.menu_subtitle_fg = self.get_param("MenuSubtitleFG", 0)  # BLACK
        self.menu_subtitle_bg = self.get_param("MenuSubtitleBG", 40)  # GREEN
        self.title_fg = self.get_param("TitleFG", 46)  # LIME
        self.title_bg = self.get_param("TitleBG", 22)  # DARKGREEN
        self.text_fg = self.get_param("TextFG", 40)  # GREEN
        self.text_bg = self.get_param("TextBG", 235)  # GREY15
        self.text_good = self.get_param("TextGood", 119)  # LIGHTGREEN
        self.text_poor = self.get_param("TextPoor", 226)  # YELLOW
        self.text_bad = self.get_param("TextBad", 202)  # ORANGERED1
        self.border_fg = self.get_param("BorderFG", 22)  # DARKGREEN
        self.border_bg = self.get_param("BorderBG", 235)  # GREY15

        # Apply named color scheme if specified
        self.set_color_scheme(self.color_scheme)

    def _init_trajectory_parameters(self):
        """Initialize trajectory calculation parameters."""
        self.trajectory_window = self.get_param("TrajectoryWindow", 1200)
        self.use_dynamic_trajectory_periods = self.get_param(
            "UseDynamicTrajectoryPeriods", True
        )
        self.drift_tracking_enabled = self.get_param("DriftTrackingEnabled", True)

    def _init_filter_parameters(self):
        """Initialize image filter parameters."""
        self.scan_for_meteors = self.get_param("ScanForMeteors", True)
        self.min_satellite_altitude = self.get_param("MinSatelliteAltitude", 30)
        self.aurora_camera_altitude = self.get_param("AuroraCameraAltitude", 5)
        self.suggestion_magnitude = self.get_param("SuggestionMagnitude", 11)
        self.suggestion_pixels = self.get_param("SuggestionPixels", 100)
        self.saved_utc = self.get_param("SavedUTC", self._now_func())

    def _init_location_parameters(self):
        """Initialize observer location parameters."""
        # Location can be string like "51.477 N" or decimal degrees
        self.home_lat = self.get_param("HomeLat", None)  # e.g., "51.477 N"
        self.home_lon = self.get_param("HomeLon", None)  # e.g., "0.0 W"
        self.local_tz = self.get_param("LocalTZ", "utc")

        # Convert to decimal values for calculations
        self._home_lat_val = 0.0
        self._home_lon_val = 0.0

        if self.home_lat is not None:
            try:
                parts = str(self.home_lat).split()
                self._home_lat_val = float(parts[0])
                if len(parts) > 1 and parts[1].upper() == "S":
                    self._home_lat_val = -self._home_lat_val
            except (ValueError, IndexError):
                # Try as direct float
                try:
                    self._home_lat_val = float(self.home_lat)
                except ValueError:
                    pass

        if self.home_lon is not None:
            try:
                parts = str(self.home_lon).split()
                self._home_lon_val = float(parts[0])
                if len(parts) > 1 and parts[1].upper() == "W":
                    self._home_lon_val = -self._home_lon_val
            except (ValueError, IndexError):
                # Try as direct float
                try:
                    self._home_lon_val = float(self.home_lon)
                except ValueError:
                    pass

    def get_param(self, name, default, oldnames=None):
        """Get a value from the parameter file.

        Args:
            name: The parameter name.
            default: The default value if not in dictionary.
            oldnames: Optional list of previous parameter names for migration.

        Returns:
            The parameter value (either from file or default).
        """
        self._defaults[name] = default
        result = default

        # Check for migrating from old parameter names
        if isinstance(oldnames, list):
            for oldname in oldnames:
                if oldname in self._dictionary:
                    result = self._dictionary[oldname]
                    self.log(
                        "Parameters.get_param(",
                        name,
                        ") migrating from",
                        oldname,
                        "with value",
                        result,
                        terminal=False,
                    )
                    break

        # Get current parameter value
        result = self._dictionary.get(name, result)

        if result != default:
            self.log(
                "Parameters.get_param(",
                name,
                ") default",
                default,
                "overridden with",
                result,
                terminal=False,
            )

        return result

    def set_color_scheme(self, scheme="green"):
        """Set color scheme to named preset.

        Args:
            scheme: One of 'white', 'blue', 'green', 'red', or 'custom'.
        """
        # Color values are 256-color terminal codes
        schemes = {
            "white": {
                "MenuTitleFG": 15,
                "MenuTitleBG": 244,
                "MenuSubtitleFG": 15,
                "MenuSubtitleBG": 239,
                "TitleFG": 15,
                "TitleBG": 239,
                "TextFG": 15,
                "TextBG": 0,
                "TextGood": 15,
                "TextPoor": 226,
                "TextBad": 196,
                "BorderFG": 249,
                "BorderBG": 0,
            },
            "blue": {
                "MenuTitleFG": 15,
                "MenuTitleBG": 24,
                "MenuSubtitleFG": 0,
                "MenuSubtitleBG": 39,
                "TitleFG": 15,
                "TitleBG": 24,
                "TextFG": 51,
                "TextBG": 235,
                "TextGood": 117,
                "TextPoor": 226,
                "TextBad": 202,
                "BorderFG": 17,
                "BorderBG": 235,
            },
            "green": {
                "MenuTitleFG": 46,
                "MenuTitleBG": 22,
                "MenuSubtitleFG": 0,
                "MenuSubtitleBG": 40,
                "TitleFG": 46,
                "TitleBG": 22,
                "TextFG": 40,
                "TextBG": 235,
                "TextGood": 119,
                "TextPoor": 226,
                "TextBad": 202,
                "BorderFG": 22,
                "BorderBG": 235,
            },
            "red": {
                "MenuTitleFG": 15,
                "MenuTitleBG": 52,
                "MenuSubtitleFG": 0,
                "MenuSubtitleBG": 124,
                "TitleFG": 15,
                "TitleBG": 124,
                "TextFG": 196,
                "TextBG": 235,
                "TextGood": 218,
                "TextPoor": 226,
                "TextBad": 202,
                "BorderFG": 52,
                "BorderBG": 235,
            },
        }

        if scheme in schemes:
            for key, value in schemes[scheme].items():
                setattr(self, key, value)
            self.color_scheme = scheme

    def save_attributes(self, filename):
        """Save parameters to JSON file.

        Args:
            filename: Path to save the parameter file.
        """
        # Build dictionary from current attributes
        save_dict = {}
        ignore_list = ["Logger", "_Dictionary", "_Defaults", "_now_func"]

        for key, value in vars(self).items():
            if key.startswith("_"):
                continue
            if key in ignore_list:
                continue
            if callable(value):
                continue
            save_dict[key] = value

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(save_dict, f, indent=2, default=str)

        self.log("Parameters saved to:", filename, terminal=False)

    def show(self):
        """Display all parameters to terminal."""
        print("List parameters:")
        print("(*) indicates a modified parameter value.")

        for key, value in sorted(vars(self).items()):
            if key.startswith("_"):
                continue
            if callable(value):
                continue
            if key in ["Logger"]:
                continue

            default_flag = ""
            if key in self._defaults and self._defaults[key] != value:
                default_flag = f" (*) Was {self._defaults[key]}"

            if isinstance(value, dict):
                print(f"{key:>30} : dictionary {default_flag}")
            else:
                print(f"{key:>30} : {value}{default_flag}")
