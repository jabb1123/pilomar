#!/usr/bin/env python3
"""Parameter management for Pilomar telescope control.

This module provides the Parameters class for loading, storing,
and managing runtime parameters.
"""

import json
import os

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

        # Direct GPIO motor parameters (DualStepperDriver — no external MCU)
        self.direct_motor_enabled = None
        self.az_step_pin = None
        self.az_dir_pin = None
        self.alt_step_pin = None
        self.alt_dir_pin = None
        self.alt_home_pin = None  # tilt-switch on altitude/pitch axis
        self.az_steps_per_rev = None
        self.alt_steps_per_rev = None
        self.flip_az = None
        self.flip_alt = None

        self.load_parameters()

    def load_parameters(self):
        """Load parameters from file if it exists.

        Missing values are defaulted. Called during __init__()
        and can be called again to reload.
        """
        if os.path.isfile(self.param_file_name):
            with open(self.param_file_name, encoding="utf-8") as f:
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
        self._init_direct_motor_parameters()

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
        self.stepper_driver_data = self.get_param("stepper_driver_data", sdd)

    def _init_owner_and_privacy(self):
        """Initialize owner and privacy settings."""
        self.owner = self.get_param("owner", "telescope owner")
        self.image_privacy = self.get_param("image_privacy", "high")

    def _init_batch_sizes(self):
        """Initialize batch size parameters."""
        self.batch_size = self.get_param("batch_size", 100)
        self.control_batch_size = self.get_param("control_batch_size", 20)

    def _init_hardware_features(self):
        """Initialize hardware feature parameters."""
        self.board_type = self.get_param("board_type", None)
        self.uart_override = self.get_param("uart_override", None)
        self.camera_enabled = self.get_param("camera_enabled", True)
        self.backlash_enabled = self.get_param("backlash_enabled", False)
        self.fault_sensitive = self.get_param("fault_sensitive", False)
        self.mctl_led_status = self.get_param("mctl_led_status", True)
        self.observation_resets_mctl = self.get_param("observation_resets_mctl", False)
        self.observation_stop_pin = self.get_param(
            "observation_stop_pin", 25, oldnames=["StopPin"]
        )
        self.ir_control_pin = self.get_param("ir_control_pin", None)
        self.ir_cutoff = self.get_param("ir_cutoff", True)
        self.tune_on_32_bit = self.get_param("tune_on_32_bit", True)
        self.mctl_reset_pin = self.get_param("mctl_reset_pin", 4)
        self.uart_rx_queue_limit = self.get_param("uart_rx_queue_limit", 50)

    def _init_motor_parameters(self):
        """Initialize motor configuration parameters."""
        # Azimuth motor
        self.min_azimuth_angle = self.get_param("min_azimuth_angle", 0)
        self.max_azimuth_angle = min(self.get_param("max_azimuth_angle", 360), 360)
        self.azimuth_driver = self.get_param("azimuth_driver", "drv8825")
        self.azimuth_gear_ratio = self.get_param("azimuth_gear_ratio", 240)
        self.azimuth_motor_steps_per_rev = self.get_param(
            "azimuth_motor_steps_per_rev", 400
        )
        self.azimuth_slew_microstep_ratio = self.get_param(
            "azimuth_slew_microstep_ratio", 1
        )
        self.azimuth_microstep_ratio = self.get_param("azimuth_microstep_ratio", 1)
        self.azimuth_rest_angle = self.get_param("azimuth_rest_angle", 180.0)
        self.azimuth_backlash_angle = self.get_param("azimuth_backlash_angle", 0.0)
        self.azimuth_orientation = self.get_param("azimuth_orientation", -1)
        self.azimuth_limit_angle = self.get_param("azimuth_limit_angle", None)

        # Altitude motor
        self.min_altitude_angle = self.get_param("min_altitude_angle", 0)
        self.max_altitude_angle = min(self.get_param("max_altitude_angle", 90), 90)
        self.altitude_driver = self.get_param("altitude_driver", "drv8825")
        self.altitude_gear_ratio = self.get_param("altitude_gear_ratio", 240)
        self.altitude_motor_steps_per_rev = self.get_param(
            "altitude_motor_steps_per_rev", 400
        )
        self.altitude_microstep_ratio = self.get_param("altitude_microstep_ratio", 1)
        self.altitude_slew_microstep_ratio = self.get_param(
            "altitude_slew_microstep_ratio", 1
        )
        self.altitude_rest_angle = self.get_param("altitude_rest_angle", 0.0)
        self.altitude_backlash_angle = self.get_param("altitude_backlash_angle", 0.0)
        self.altitude_orientation = self.get_param("altitude_orientation", -1)
        self.altitude_limit_angle = self.get_param("altitude_limit_angle", None)

        # Motor timing
        self.fast_time = self.get_param("fast_time", 0.001)
        self.slow_time = self.get_param("slow_time", 0.05)
        self.time_delta = self.get_param("time_delta", 0.003)

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
        self.speed_list = self.get_param("speed_list", speed_list)

        self.motor_status_delay = self.get_param("motor_status_delay", 10)
        self.slew_enabled = self.get_param("slew_enabled", False)
        self.trace_move = self.get_param("trace_move", False, oldnames=["TraceMotor"])
        self.optimise_moves = self.get_param("optimise_moves", False)
        self.mctl_comms_timeout = self.get_param("mctl_comms_timeout", 120)

    def _init_image_parameters(self):
        """Initialize image storage parameters."""
        self.use_usb_storage = self.get_param("use_usb_storage", True)
        self.sd_path = self.get_param("sd_path", "/")
        self.usb_path = self.get_param("usb_path", "/media/pi")
        self.fast_flush = self.get_param("fast_flush", False)
        self.fast_image_capture = self.get_param("fast_image_capture", False)
        self.horizon_altitude = self.get_param("horizon_altitude", 0.0)
        self._horizon = max(
            self.horizon_altitude if self.horizon_altitude is not None else 0.0,
            self.min_altitude_angle if self.min_altitude_angle is not None else 0.0,
        )

        # Image file types
        self.camera_save_jpg = self.get_param("camera_save_jpg", True)
        self.camera_save_dng = self.get_param("camera_save_dng", True)
        self.camera_save_fits = self.get_param("camera_save_fits", False)

        if not (self.camera_save_jpg or self.camera_save_dng or self.camera_save_fits):
            self.log("No image types are saved according to the parameters.", level="warning")

    def _init_display_parameters(self):
        """Initialize display and color scheme parameters."""
        self.color_scheme = self.get_param("color_scheme", "green")
        self.debug_mode = self.get_param("debug_mode", False)

        # Default color scheme values (green)
        self.menu_title_fg = self.get_param("menu_title_fg", 46)  # LIME
        self.menu_title_bg = self.get_param("menu_title_bg", 22)  # DARKGREEN
        self.menu_subtitle_fg = self.get_param("menu_subtitle_fg", 0)  # BLACK
        self.menu_subtitle_bg = self.get_param("menu_subtitle_bg", 40)  # GREEN
        self.title_fg = self.get_param("title_fg", 46)  # LIME
        self.title_bg = self.get_param("title_bg", 22)  # DARKGREEN
        self.text_fg = self.get_param("text_fg", 40)  # GREEN
        self.text_bg = self.get_param("text_bg", 235)  # GREY15
        self.text_good = self.get_param("text_good", 119)  # LIGHTGREEN
        self.text_poor = self.get_param("text_poor", 226)  # YELLOW
        self.text_bad = self.get_param("text_bad", 202)  # ORANGERED1
        self.border_fg = self.get_param("border_fg", 22)  # DARKGREEN
        self.border_bg = self.get_param("border_bg", 235)  # GREY15

        # Apply named color scheme if specified
        self.set_color_scheme(self.color_scheme)

    def _init_trajectory_parameters(self):
        """Initialize trajectory calculation parameters."""
        self.trajectory_window = self.get_param("trajectory_window", 1200)
        self.use_dynamic_trajectory_periods = self.get_param(
            "use_dynamic_trajectory_periods", True
        )
        self.drift_tracking_enabled = self.get_param("drift_tracking_enabled", True)

    def _init_filter_parameters(self):
        """Initialize image filter parameters."""
        self.scan_for_meteors = self.get_param("scan_for_meteors", True)
        self.min_satellite_altitude = self.get_param("min_satellite_altitude", 30)
        self.aurora_camera_altitude = self.get_param("aurora_camera_altitude", 5)
        self.suggestion_magnitude = self.get_param("suggestion_magnitude", 11)
        self.suggestion_pixels = self.get_param("suggestion_pixels", 100)
        self.saved_utc = self.get_param("saved_utc", self._now_func())

    def _init_location_parameters(self):
        """Initialize observer location parameters."""
        # Location can be string like "51.477 N" or decimal degrees
        self.home_lat = self.get_param("home_lat", None)  # e.g., "51.477 N"
        self.home_lon = self.get_param("home_lon", None)  # e.g., "0.0 W"
        self.local_tz = self.get_param("local_tz", "utc")

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

    def _init_direct_motor_parameters(self):
        """Initialize direct GPIO stepper motor parameters."""
        self.direct_motor_enabled = self.get_param("direct_motor_enabled", False)
        self.az_step_pin = self.get_param("az_step_pin", 21)
        self.az_dir_pin = self.get_param("az_dir_pin", 20)
        self.alt_step_pin = self.get_param("alt_step_pin", 6)
        self.alt_dir_pin = self.get_param("alt_dir_pin", 5)
        self.alt_home_pin = self.get_param(
            "alt_home_pin", 23
        )  # tilt switch (active LOW)
        self.az_steps_per_rev = self.get_param("az_steps_per_rev", 384000)
        self.alt_steps_per_rev = self.get_param("alt_steps_per_rev", 384000)
        self.flip_az = self.get_param("flip_az", True)
        self.flip_alt = self.get_param("flip_alt", False)

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
                "menu_title_fg": 15,
                "menu_title_bg": 244,
                "menu_subtitle_fg": 15,
                "menu_subtitle_bg": 239,
                "title_fg": 15,
                "title_bg": 239,
                "text_fg": 15,
                "text_bg": 0,
                "text_good": 15,
                "text_poor": 226,
                "text_bad": 196,
                "border_fg": 249,
                "border_bg": 0,
            },
            "blue": {
                "menu_title_fg": 15,
                "menu_title_bg": 24,
                "menu_subtitle_fg": 0,
                "menu_subtitle_bg": 39,
                "title_fg": 15,
                "title_bg": 24,
                "text_fg": 51,
                "text_bg": 235,
                "text_good": 117,
                "text_poor": 226,
                "text_bad": 202,
                "border_fg": 17,
                "border_bg": 235,
            },
            "green": {
                "menu_title_fg": 46,
                "menu_title_bg": 22,
                "menu_subtitle_fg": 0,
                "menu_subtitle_bg": 40,
                "title_fg": 46,
                "title_bg": 22,
                "text_fg": 40,
                "text_bg": 235,
                "text_good": 119,
                "text_poor": 226,
                "text_bad": 202,
                "border_fg": 22,
                "border_bg": 235,
            },
            "red": {
                "menu_title_fg": 15,
                "menu_title_bg": 52,
                "menu_subtitle_fg": 0,
                "menu_subtitle_bg": 124,
                "title_fg": 15,
                "title_bg": 124,
                "text_fg": 196,
                "text_bg": 235,
                "text_good": 218,
                "text_poor": 226,
                "text_bad": 202,
                "border_fg": 52,
                "border_bg": 235,
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
