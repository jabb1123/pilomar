#!/usr/bin/env python3
"""
Main entry point for the Pilomar application.

This module provides:
- Application initialization
- Main menu loop
- Graceful shutdown handling
"""

import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any

# Ensure project root is on sys.path when this file is run directly
_here = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_here))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from skyfield.api import load
from skyfield.iokit import Loader

# Handle both direct execution and module import
from pilomar.celestial.celestrak import Celestrak
from pilomar.config.parameters import Parameters
from pilomar.core.logger import LogFile
from pilomar.core.time_utils import now_utc

try:
    from ..ui.menu import ListChooser
    from .data_loader import CatalogLoader, CatalogPaths
    from .observation import ObservationContext, ObservationLoop, start_observation
    from .target_chooser import TargetChooser, TargetSelectionContext
except ImportError:
    # Running as script - import directly without triggering pilomar package init
    _app_dir = os.path.dirname(os.path.abspath(__file__))
    _ui_dir = os.path.join(os.path.dirname(_app_dir), "ui")
    if _app_dir not in sys.path:
        sys.path.insert(0, _app_dir)
    from data_loader import CatalogLoader, CatalogPaths
    from observation import ObservationContext, ObservationLoop, start_observation
    from target_chooser import TargetChooser, TargetSelectionContext

    if _ui_dir not in sys.path:
        sys.path.insert(0, _ui_dir)
    from menu import ListChooser


@dataclass
class ApplicationContext:
    """Container for application-wide state and dependencies.

    This provides centralized access to all application components,
    replacing the previous global variable approach.
    """

    # Core configuration
    parameters: Parameters
    project_root: str = ""

    # Skyfield objects
    timescale: Any = None
    planets: Any = None
    skyfield_loader: Loader = None

    # Session state
    session: Any = None
    target: Any = None

    # Hardware interfaces
    camera: Any = None
    lens: Any = None
    sensor: Any = None
    motor_controls: list[Any] = field(default_factory=list)
    mctl: Any = None  # Microcontroller

    # Direct GPIO motor control (pigpio-based, no external MCU)
    direct_driver: Any = None
    direct_tracker: Any = None
    direct_slew: Any = None

    # Threading
    camera_thread: Any = None
    mctl_thread: Any = None
    message_thread: Any = None

    # Queue interfaces
    camera_control_queue: Any = None
    camera_status_queue: Any = None
    uart_control_queue: Any = None

    # Logging
    main_log: Any = None
    camera_log: Any = None

    # Data catalogs
    hipparcos_df: Any = None
    ngc_df: Any = None
    comets_df: Any = None
    messier_dict: dict = field(default_factory=dict)
    meteor_dict: dict = field(default_factory=dict)
    star_names: dict = field(default_factory=dict)
    constellation_links: list = field(default_factory=list)

    # Satellite data
    # CelesTrak satellite TLE handler
    celestrak: Any = None

    # Folder management
    folder_handler: Any = None

    # UI components
    textcolor: Any = None
    menus: dict[str, Any] = field(default_factory=dict)
    windows: dict[str, Any] = field(default_factory=dict)

    # Observation state
    observation_schedule: Any = None
    suggested_targets: Any = None
    drift_tracker: Any = None

    # Storage monitoring
    storage_monitor: Any = None


class Application:
    """Main Pilomar application controller.

    This class manages the application lifecycle including:
    - Initialization and configuration loading
    - Menu system setup
    - Main loop execution
    - Graceful shutdown
    """

    def __init__(self, project_root: str):
        """Initialize the application.

        Args:
            project_root: Path to the Pilomar project root directory
        """
        self.ctx = ApplicationContext(project_root=project_root, parameters=None)
        self._running = False
        self._initialized = False
        self._target_chooser: TargetChooser | None = None

    def _log(self, *args, level: str = "info", terminal: bool = True):
        """Log a message."""
        if self.ctx.main_log:
            self.ctx.main_log.Log(*args, level=level, terminal=terminal)
        elif terminal:
            print(*args)

    def _init_target_chooser(self) -> None:
        """Initialize the target chooser with current context."""
        # Build catalog name lists
        messier_numlist = list(self.ctx.messier_dict.keys()) if self.ctx.messier_dict else []
        messier_namelist = (
            [v.get("name", "") for v in self.ctx.messier_dict.values()]
            if self.ctx.messier_dict
            else []
        )
        meteor_namelist = list(self.ctx.meteor_dict.keys()) if self.ctx.meteor_dict else []
        ngc_namelist = list(self.ctx.ngc_df["name"]) if self.ctx.ngc_df is not None else []
        comet_list = (
            list(self.ctx.comets_df["designation"]) if self.ctx.comets_df is not None else []
        )

        # Get satellite list from CelesTrak if available
        satellite_list = []
        if self.ctx.celestrak and hasattr(self.ctx.celestrak, "satellite_list"):
            satellite_list = self.ctx.celestrak.satellite_list

        # Get home latitude from parameters if available
        home_latitude = 0.0
        if self.ctx.parameters:
            home_latitude = getattr(self.ctx.parameters, "_home_lat_val", 0.0)

        ctx = TargetSelectionContext(
            messier=self.ctx.messier_dict,
            meteors=self.ctx.meteor_dict,
            hipparcos_df=self.ctx.hipparcos_df,
            ngc_df=self.ctx.ngc_df,
            comets_df=self.ctx.comets_df,
            messier_numlist=messier_numlist,
            messier_namelist=messier_namelist,
            meteor_namelist=meteor_namelist,
            ngc_namelist=ngc_namelist,
            comet_list=comet_list,
            satellite_list=satellite_list,
            planets=self.ctx.planets,
            timescale=self.ctx.timescale,
            gm_sun=132712440041.93938,  # km^3/s^2 (Skyfield value)
            camera=self.ctx.camera,
            motor_controls=self.ctx.motor_controls,
            home_latitude=home_latitude,
            logger=self.ctx.main_log,
            input_func=input,
            print_func=print,
            textcolor=self.ctx.textcolor,
            list_chooser_class=ListChooser,
        )
        self._target_chooser = TargetChooser(ctx)

    def initialize(self) -> bool:
        """Initialize all application components.

        This performs the full initialization sequence:
        1. Load configuration/parameters
        2. Initialize Skyfield and ephemeris data
        3. Load astronomical catalogs
        4. Initialize hardware interfaces
        5. Set up UI components

        Returns:
            True if initialization successful, False otherwise
        """
        self._log("Initializing Pilomar...")

        try:
            # Find project root if not set
            if not self.ctx.project_root:
                self.ctx.project_root = find_project_root()

            # Load parameters
            self._load_parameters()

            # Initialize direct GPIO motor control
            self._init_direct_motors()

            # Initialize Skyfield
            self._init_skyfield()

            # Load astronomical catalogs
            self._load_catalogs()

            # Initialize target chooser with current context
            self._init_target_chooser()

            self._initialized = True
            self._log("Initialization complete")
            return True

        except Exception as e:
            self._log(f"Initialization failed: {e}", level="error")
            import traceback

            traceback.print_exc()
            return False

    def _init_direct_motors(self) -> None:
        """Initialize the direct-GPIO stepper driver, sky tracker and slew controller.

        Only activates when ``DirectMotorEnabled`` is True in parameters.  Requires
        the pigpio daemon to be running on the Pi.
        """
        if not self.ctx.parameters:
            return
        if not getattr(self.ctx.parameters, "direct_motor_enabled", False):
            return

        try:
            import pigpio
            from pilomar.control.direct_slew import DirectSlewController
            from pilomar.control.direct_stepper import DualStepperDriver
            from pilomar.control.direct_tracker import DirectSkyTracker
        except ImportError as exc:
            self._log(f"Direct motor control not available: {exc}", level="warning")
            return

        try:
            p = self.ctx.parameters
            pi = pigpio.pi()
            if not pi.connected:
                self._log(
                    "pigpio daemon not running — direct motors disabled",
                    level="warning",
                )
                return

            self.ctx.direct_driver = DualStepperDriver(
                pi,
                az_step_pin=p.az_step_pin,
                az_dir_pin=p.az_dir_pin,
                alt_step_pin=p.alt_step_pin,
                alt_dir_pin=p.alt_dir_pin,
                az_steps_per_rev=p.az_steps_per_rev,
                alt_steps_per_rev=p.alt_steps_per_rev,
                flip_az=p.flip_az,
                flip_alt=p.flip_alt,
                home_pin=p.alt_home_pin,
                logger=self.ctx.main_log,
            )

            self.ctx.direct_tracker = DirectSkyTracker(
                driver=self.ctx.direct_driver,
                lat=p._home_lat_val,
                lon=p._home_lon_val,
                logger=self.ctx.main_log,
            )

            self.ctx.direct_slew = DirectSlewController(
                driver=self.ctx.direct_driver,
                tracker=self.ctx.direct_tracker,
                logger=self.ctx.main_log,
            )

            self._log(
                f"Direct GPIO motors initialized "
                f"(AZ step={p.az_step_pin}/dir={p.az_dir_pin}, "
                f"ALT step={p.alt_step_pin}/dir={p.alt_dir_pin}, "
                f"home_pin={p.alt_home_pin})"
            )
        except Exception as exc:  # pylint: disable=broad-except
            self._log(f"Failed to initialize direct motors: {exc}", level="warning")
            import traceback

            traceback.print_exc()

    def _load_parameters(self) -> None:
        """Load parameters from file or create with defaults."""
        if self.ctx.parameters:
            return  # Already loaded

        param_file = os.path.join(self.ctx.project_root, "data", "pilomar_params.json")

        try:
            # Add pilomar package to sys.path temporarily to allow imports
            # without triggering the full pilomar/__init__.py chain
            pilomar_parent = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            path_added = False
            if pilomar_parent not in sys.path:
                sys.path.insert(0, pilomar_parent)
                path_added = True

            try:
                # Import the specific modules we need without full package init
                # import importlib.util

                # First load base module (AttributeMaster)
                # base_path = os.path.join(
                #     self.ctx.project_root, 'pilomar', 'core', 'base.py'
                # )
                # spec = importlib.util.spec_from_file_location("pilomar_base", base_path)
                # base_module = importlib.util.module_from_spec(spec)
                # sys.modules['pilomar.core.base'] = base_module  # Register for import
                # spec.loader.exec_module(base_module)

                # Now load parameters module
                # param_module_path = os.path.join(
                #     self.ctx.project_root, 'pilomar', 'config', 'parameters.py'
                # )
                # spec = importlib.util.spec_from_file_location("parameters", param_module_path)
                # param_module = importlib.util.module_from_spec(spec)
                # spec.loader.exec_module(param_module)
                # Parameters = param_module.Parameters

                if os.path.exists(param_file):
                    self.ctx.parameters = Parameters(param_file, logger=self.ctx.main_log)
                    self._log(f"Parameters loaded from {param_file}")
                else:
                    # First run - prompt user for location and create config
                    self._log("No configuration file found - starting first-time setup")
                    self.ctx.parameters = Parameters(param_file, logger=self.ctx.main_log)
                    self._prompt_for_location()

                    # Save parameters to file for next time
                    self.ctx.parameters.save_attributes(param_file)
                    self._log(f"Configuration saved to {param_file}")

            finally:
                # Clean up sys.path if we modified it
                if path_added and pilomar_parent in sys.path:
                    sys.path.remove(pilomar_parent)

        except Exception as e:  # pylint: disable=broad-except
            self._log(f"Error loading parameters: {e}", level="warning")
            import traceback

            traceback.print_exc()

    def _prompt_for_location(self) -> None:
        """Prompt user for their observer location (lat/lon)."""
        print("\n" + "=" * 50)
        print("PILOMAR FIRST-TIME SETUP")
        print("=" * 50)
        print("\nPlease enter your observation location.")
        print("This is needed for accurate celestial calculations.\n")

        # Common location examples
        print("Example formats:")
        print("  Latitude:  51.477 N  or  -33.86  (negative for South)")
        print("  Longitude: 0.0 W     or  151.21  (negative for West)")
        print()

        # Get latitude
        while True:
            lat_input = input("Enter latitude (e.g., '51.477 N' or '51.477'): ").strip()
            if not lat_input:
                print("Latitude is required.")
                continue

            # Parse latitude
            lat_val, lat_str = self._parse_coordinate(lat_input, is_lat=True)
            if lat_val is not None:
                break
            print("Invalid latitude format. Please try again.")

        # Get longitude
        while True:
            lon_input = input("Enter longitude (e.g., '0.0 W' or '-0.0'): ").strip()
            if not lon_input:
                print("Longitude is required.")
                continue

            # Parse longitude
            lon_val, lon_str = self._parse_coordinate(lon_input, is_lat=False)
            if lon_val is not None:
                break
            print("Invalid longitude format. Please try again.")

        # Set the parameters
        self.ctx.parameters.home_lat = lat_str
        self.ctx.parameters.home_lon = lon_str
        self.ctx.parameters._home_lat_val = lat_val
        self.ctx.parameters._home_lon_val = lon_val

        print(f"\nLocation set to: {lat_str}, {lon_str}")
        print("=" * 50 + "\n")

    def _parse_coordinate(self, value: str, is_lat: bool) -> tuple:
        """Parse a coordinate string into decimal value and display string.

        Args:
            value: Input string like '51.477 N', '-33.86', or '51.477'
            is_lat: True for latitude, False for longitude

        Returns:
            Tuple of (decimal_value, display_string) or (None, None) if invalid
        """
        value = value.strip()
        if not value:
            return None, None

        try:
            parts = value.split()

            if len(parts) == 2:
                # Format: "51.477 N" or "0.0 W"
                num = float(parts[0])
                direction = parts[1].upper()

                if is_lat:
                    if direction not in ("N", "S"):
                        return None, None
                    if not -90 <= num <= 90:
                        return None, None
                    decimal = num if direction == "N" else -num
                    display = f"{abs(num)} {direction}"
                else:
                    if direction not in ("E", "W"):
                        return None, None
                    if not -180 <= num <= 180:
                        return None, None
                    decimal = num if direction == "E" else -num
                    display = f"{abs(num)} {direction}"

                return decimal, display

            elif len(parts) == 1:
                # Format: "-33.86" or "51.477"
                num = float(parts[0])

                if is_lat:
                    if not -90 <= num <= 90:
                        return None, None
                    direction = "N" if num >= 0 else "S"
                    display = f"{abs(num)} {direction}"
                else:
                    if not -180 <= num <= 180:
                        return None, None
                    direction = "E" if num >= 0 else "W"
                    display = f"{abs(num)} {direction}"

                return num, display

        except (ValueError, IndexError):
            pass

        return None, None

    def _init_skyfield(self) -> None:
        """Initialize Skyfield timescale and ephemeris."""
        if self.ctx.timescale and self.ctx.planets:
            return  # Already initialized

        try:
            # Create a loader with cache directory
            skyfield_data_dir = os.path.join(self.ctx.project_root, "data")
            self.ctx.skyfield_loader = Loader(skyfield_data_dir)

            # Load timescale
            self._log("Loading Skyfield timescale...", terminal=False)
            self.ctx.timescale = self.ctx.skyfield_loader.timescale()

            # Load ephemeris (planets)
            self._log("Loading solar system ephemeris...", terminal=False)
            self.ctx.planets = load("de421.bsp")

        except ImportError:
            self._log(
                "Skyfield not available - some features disabled",
                level="warning",
                terminal=True,
            )
        except Exception as e:  # pylint: disable=broad-except
            self._log(f"Skyfield initialization error: {e}", level="warning")

    def _load_catalogs(self) -> None:
        """Load astronomical catalogs."""
        data_dir = os.path.join(self.ctx.project_root, "data")

        if not os.path.isdir(data_dir):
            self._log(f"Data directory not found: {data_dir}", level="warning")
            return

        # Create catalog loader with skyfield loader for online catalogs
        paths = CatalogPaths(data_dir=data_dir)
        loader = CatalogLoader(
            paths, logger=self.ctx.main_log, skyfield_loader=self.ctx.skyfield_loader
        )

        # Load local catalogs (from JSON files)
        try:
            self.ctx.messier_dict = loader.load_messier()
            self._log(f"Loaded {len(self.ctx.messier_dict)} Messier objects", terminal=False)
        except Exception as e:  # pylint: disable=broad-except
            self._log(f"Failed to load Messier catalog: {e}", level="warning")

        try:
            self.ctx.meteor_dict = loader.load_meteors()
            self._log(f"Loaded {len(self.ctx.meteor_dict)} meteor showers", terminal=False)
        except Exception as e:  # pylint: disable=broad-except
            self._log(f"Failed to load meteor catalog: {e}", level="warning")

        try:
            self.ctx.star_names = loader.load_star_names()
            self._log(f"Loaded {len(self.ctx.star_names)} named stars", terminal=False)
        except Exception as e:  # pylint: disable=broad-except
            self._log(f"Failed to load star names: {e}", level="warning")

        try:
            self.ctx.ngc_df = loader.load_ngc()
            if self.ctx.ngc_df is not None:
                self._log(f"Loaded {len(self.ctx.ngc_df)} NGC objects", terminal=False)
        except Exception as e:  # pylint: disable=broad-except
            self._log(f"Failed to load NGC catalog: {e}", level="warning")

        # Load online catalogs (from skyfield/MPC)
        try:
            self.ctx.hipparcos_df = loader.load_hipparcos()
            if self.ctx.hipparcos_df is not None:
                self._log(
                    f"Loaded {len(self.ctx.hipparcos_df)} Hipparcos stars",
                    terminal=False,
                )
        except Exception as e:  # pylint: disable=broad-except
            self._log(f"Failed to load Hipparcos catalog: {e}", level="warning")

        try:
            self.ctx.comets_df = loader.load_comets()
            if self.ctx.comets_df is not None:
                self._log(f"Loaded {len(self.ctx.comets_df)} comets", terminal=False)
        except Exception as e:  # pylint: disable=broad-except
            self._log(f"Failed to load comet catalog: {e}", level="warning")

        # Load satellite data from CelesTrak
        self._load_celestrak()

    def _load_celestrak(self) -> None:
        """Load satellite TLE data from CelesTrak."""
        try:
            celestrak_url = "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle"
            self._log("Loading CelesTrak satellite data...", terminal=False)

            # Create a simple logger adapter if we don't have one
            class LogAdapter(LogFile):
                def __init__(self, log_func):
                    self._log = log_func

                def log(self, *args, **kwargs):
                    self._log(*args, **kwargs)

                def report_exception(self, e, msg):
                    self._log(f"{msg}: {e}", level="error")

                def raise_exception(self, e, msg):
                    self._log(f"{msg}: {e}", level="error")
                    raise e

            logger = LogAdapter(self._log) if not self.ctx.main_log else self.ctx.main_log

            self.ctx.celestrak = Celestrak(
                celestrak_url, logger=logger, projectroot=self.ctx.project_root
            )

            sat_count = len(self.ctx.celestrak.satellite_list) if self.ctx.celestrak else 0
            self._log(f"Loaded {sat_count} satellites from CelesTrak", terminal=False)

        except ImportError:
            self._log("CelesTrak module not available", level="warning", terminal=False)
        except Exception as e:
            self._log(f"Failed to load CelesTrak data: {e}", level="warning")

    def run(self) -> int:
        """Run the main application loop.

        Returns:
            Exit code (0 for success, non-zero for error)
        """
        if not self._initialized:
            if not self.initialize():
                return 1

        self._running = True
        self._log("Starting main loop")

        try:
            # Main loop - in the original code this is:
            # while True:
            #     MainMenu.Prompt()
            #     if AskYesNo("Do you really want to shut down?"): break

            while self._running:
                # Display and handle main menu
                if "main" in self.ctx.menus:
                    self.ctx.menus["main"].Prompt()
                else:
                    # Fallback if menus not set up
                    self._simple_menu_loop()

                # _simple_menu_loop sets _running=False when user picks 'x'
                # Only then do we confirm exit
                if not self._running:
                    if not self._should_exit():
                        # User cancelled exit, continue running
                        self._running = True

            return 0

        except KeyboardInterrupt:
            self._log("Interrupted by user", level="warning")
            return 130  # Standard exit code for Ctrl+C
        except Exception as e:
            self._log(f"Error in main loop: {e}", level="error")
            return 1
        finally:
            self.shutdown()

    def _simple_menu_loop(self) -> None:
        """Simple menu loop for when full UI not available."""
        print("\nPilomar - Main Menu")
        print("=" * 40)
        print("1. Select target")
        print("2. GOTO target (move telescope)")
        print("3. Begin observation (track & photograph)")
        print("4. Status")
        print("-" * 40)
        print("5. Advanced tools")
        print("6. Settings")
        print("x. Exit")

        choice = input("Choice: ").lower().strip()

        if choice == "1":
            self._select_target_menu()
        elif choice == "2":
            self._goto_target()
        elif choice == "3":
            self._begin_observation()
        elif choice == "4":
            self._show_status()
        elif choice == "5":
            self._advanced_menu()
        elif choice == "6":
            self._settings_menu()
        elif choice == "x":
            self._running = False

    def _advanced_menu(self) -> None:
        """Display advanced tools submenu."""
        while True:
            print("\nAdvanced Tools")
            print("=" * 40)
            print("1. Camera tools")
            print("2. Motor tools")
            print("3. Microcontroller tools")
            print("4. Tracking tools")
            print("5. Observation schedule")
            print("6. Home motors")
            print("b. Back to main menu")

            choice = input("Choice: ").lower().strip()

            if choice == "b":
                break
            elif choice == "1":
                self._camera_tools_menu()
            elif choice == "2":
                self._motor_tools_menu()
            elif choice == "3":
                self._microcontroller_menu()
            elif choice == "4":
                self._tracking_tools_menu()
            elif choice == "5":
                self._schedule_menu()
            elif choice == "6":
                self._home_motors()
            else:
                print("Invalid choice")

    def _goto_target(self) -> None:
        """Move telescope to point at the current target."""
        if self.ctx.target is None:
            print("\nNo target selected. Please select a target first.")
            return

        target_name = (
            self.ctx.target.get("name", "Unknown")
            if isinstance(self.ctx.target, dict)
            else str(self.ctx.target)
        )
        print(f"\nGOTO Target: {target_name}")

        # --- Direct GPIO path ---
        if self.ctx.direct_slew is not None:
            self._goto_target_direct()
            return

        # Check if motors are available
        if not self.ctx.motor_controls:
            print("Motors not initialized - cannot move telescope.")
            print("(In simulation mode, this would move to the target position)")
            return

        # Get target position (Alt/Az)
        target_handle = self.ctx.target.get("handle") if isinstance(self.ctx.target, dict) else None

        if target_handle is None:
            print("Target handle not available - cannot calculate position.")
            return

        # Build observation context and use the goto functionality
        obs_ctx = self._build_observation_context()
        obs_loop = ObservationLoop(obs_ctx)

        print("Moving to target position...")
        if obs_loop._goto_target():
            print("Telescope is now pointing at target.")
            print("NOTE: Motors are stopped - not actively tracking.")
        else:
            print("Failed to complete move to target.")

    def _goto_target_direct(self) -> None:
        """GOTO using the direct GPIO slew controller."""
        target = self.ctx.target
        tracker = self.ctx.direct_tracker
        slew = self.ctx.direct_slew

        handle = target.get("handle") if isinstance(target, dict) else None
        searchgroup = target.get("searchgroup", "") if isinstance(target, dict) else ""
        searchterm = target.get("searchterm", "") if isinstance(target, dict) else ""

        if searchgroup == "altaz":
            # Target stored as explicit alt/az degrees
            try:
                alt, az = (float(v) for v in searchterm.split(","))
            except (ValueError, AttributeError):
                print("Could not parse alt/az target coordinates.")
                return
            print(f"Slewing to ALT={alt:.2f}° AZ={az:.2f}°...")
            slew.slew_to_altaz(alt, az, resume_tracking=False)
            print("Slew complete.")
            return

        if handle is None:
            print("Target has no Skyfield handle — cannot compute position.")
            return

        # Point tracker at the target to resolve current alt/az
        tracker.target = handle
        alt, az = tracker.current_altaz()

        if alt < 0:
            print(f"Target is below the horizon (ALT={alt:.1f}°). Cannot slew.")
            return

        print(f"Target position: ALT={alt:.2f}° AZ={az:.2f}°")
        print("Slewing to target (tracking will resume after slew)...")
        slew.slew_to_altaz(alt, az, resume_tracking=True)
        print("Slew complete. Tracking active.")

    def _home_motors(self) -> None:
        """Return motors to home position."""
        if self.ctx.direct_driver is not None:
            print("\nHoming altitude axis via tilt switch...")
            try:
                self.ctx.direct_driver.home_altitude()
                print("Homing complete.")
            except Exception as exc:  # pylint: disable=broad-except
                print(f"Homing failed: {exc}")
            return

        if not self.ctx.motor_controls:
            print("\nMotors not initialized.")
            print("(Would return telescope to home position)")
            return

        print("\nHoming motors...")
        for mc in self.ctx.motor_controls:
            print(f"  Homing {mc.motor_name}...")
        print("Motors homed.")

    def _select_target_menu(self) -> None:
        """Show target selection submenu."""
        while True:
            print("\nSelect Target Type")
            print("=" * 40)
            print("1. Messier object (M1-M110)")
            print("2. NGC object")
            print("3. Hipparcos star catalog")
            print("4. Solar system body")
            print("5. Comet")
            print("6. Meteor shower radiant")
            print("7. Satellite (ISS, etc.)")
            print("8. Custom RA/Dec")
            print("9. Custom Alt/Az")
            print("a. Aurora observation")
            print("b. Back to main menu")

            choice = input("Choice: ").lower().strip()

            if choice == "b":
                break
            elif choice == "1":
                self._select_messier()
            elif choice == "2":
                self._select_ngc()
            elif choice == "3":
                self._select_star()
            elif choice == "4":
                self._select_solar_system()
            elif choice == "5":
                self._select_comet()
            elif choice == "6":
                self._select_meteor()
            elif choice == "7":
                self._select_satellite()
            elif choice == "8":
                self._select_radec()
            elif choice == "9":
                self._select_altaz()
            elif choice == "a":
                self._select_aurora()
            else:
                print("Invalid choice")

    def _set_target(self, result: dict | None) -> None:
        """Set the current target from chooser result."""
        if result:
            self.ctx.target = result
            target_name = result.get("name", "Unknown")
            print(f"Selected target: {target_name}")
        else:
            print("No target selected.")

    def _has_catalog_data(self, catalog: str) -> bool:
        """Check if catalog data is loaded."""
        if catalog == "messier":
            return bool(self.ctx.messier_dict)
        elif catalog == "ngc":
            return self.ctx.ngc_df is not None and len(self.ctx.ngc_df) > 0
        elif catalog == "hipparcos":
            return self.ctx.hipparcos_df is not None and len(self.ctx.hipparcos_df) > 0
        elif catalog == "comets":
            return self.ctx.comets_df is not None and len(self.ctx.comets_df) > 0
        elif catalog == "meteors":
            return bool(self.ctx.meteor_dict)
        elif catalog == "solar":
            return self.ctx.planets is not None
        return False

    def _select_messier(self) -> None:
        """Select a Messier object."""
        if self._target_chooser and self._has_catalog_data("messier"):
            result = self._target_chooser.choose_messier()
            self._set_target(result)
        else:
            # Fallback when no catalog data
            print("(Catalog data not loaded - using simple input)")
            name = input("Enter Messier target (e.g., M31, 'x' to cancel): ").strip()
            if name and name.lower() != "x":
                self.ctx.target = {
                    "name": name,
                    "searchgroup": "messier",
                    "searchterm": name,
                }
                print(f"Selected target: {name}")

    def _select_ngc(self) -> None:
        """Select an NGC object."""
        if self._target_chooser and self._has_catalog_data("ngc"):
            result = self._target_chooser.choose_ngc()
            self._set_target(result)
        else:
            print("(Catalog data not loaded - using simple input)")
            name = input("Enter NGC name (e.g., NGC7000, 'x' to cancel): ").strip()
            if name and name.lower() != "x":
                self.ctx.target = {
                    "name": name,
                    "searchgroup": "ngc",
                    "searchterm": name,
                }
                print(f"Selected target: {name}")

    def _select_star(self) -> None:
        """Select a Hipparcos star."""
        if self._target_chooser and self._has_catalog_data("hipparcos"):
            result = self._target_chooser.choose_hipparcos()
            self._set_target(result)
        else:
            print("(Catalog data not loaded - using simple input)")
            name = input("Enter star name or HIP number ('x' to cancel): ").strip()
            if name and name.lower() != "x":
                self.ctx.target = {
                    "name": name,
                    "searchgroup": "hipparcos",
                    "searchterm": name,
                }
                print(f"Selected target: {name}")

    def _select_solar_system(self) -> None:
        """Select a solar system body."""
        if self._target_chooser and self._has_catalog_data("solar"):
            result = self._target_chooser.choose_solar()
            self._set_target(result)
        else:
            print("\nSolar System Bodies:")
            bodies = [
                "Sun",
                "Moon",
                "Mercury",
                "Venus",
                "Mars",
                "Jupiter",
                "Saturn",
                "Uranus",
                "Neptune",
                "Pluto",
            ]
            for i, body in enumerate(bodies, 1):
                print(f"  {i}. {body}")
            print("  x. Cancel")
            choice = input("Choice: ").strip().lower()
            if choice == "x":
                return
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(bodies):
                    self.ctx.target = {
                        "name": bodies[idx],
                        "searchgroup": "solar",
                        "searchterm": bodies[idx].lower(),
                    }
                    print(f"Selected target: {bodies[idx]}")
            except ValueError:
                print("Invalid choice")

    def _select_comet(self) -> None:
        """Select a comet."""
        if self._target_chooser and self._has_catalog_data("comets"):
            result = self._target_chooser.choose_comet()
            self._set_target(result)
        else:
            print("(Catalog data not loaded - using simple input)")
            name = input("Enter comet designation ('x' to cancel): ").strip()
            if name and name.lower() != "x":
                self.ctx.target = {
                    "name": name,
                    "searchgroup": "comet",
                    "searchterm": name,
                }
                print(f"Selected target: {name}")

    def _select_meteor(self) -> None:
        """Select a meteor shower radiant."""
        if self._target_chooser and self._has_catalog_data("meteors"):
            result = self._target_chooser.choose_meteor()
            self._set_target(result)
        else:
            print("(Catalog data not loaded - using simple input)")
            print("Common showers: Perseids, Geminids, Leonids, Orionids, Quadrantids")
            name = input("Enter shower name ('x' to cancel): ").strip()
            if name and name.lower() != "x":
                self.ctx.target = {
                    "name": name,
                    "objecttype": "meteor",
                    "searchgroup": "meteor",
                    "searchterm": name,
                }
                print(f"Selected target: {name} radiant")

    def _select_satellite(self) -> None:
        """Select a satellite."""
        if self._target_chooser:
            result = self._target_chooser.choose_satellite()
            self._set_target(result)
        else:
            print("(Satellite data not loaded - using simple input)")
            print("Common: ISS, CSS (Tiangong), HST (Hubble)")
            name = input("Enter satellite name ('x' to cancel): ").strip()
            if name and name.lower() != "x":
                self.ctx.target = {
                    "name": name.upper(),
                    "searchgroup": "satellite",
                    "searchterm": name.lower(),
                }
                print(f"Selected target: {name.upper()}")

    def _select_radec(self) -> None:
        """Select a custom RA/Dec position."""
        if self._target_chooser:
            result = self._target_chooser.radec_object()
            self._set_target(result)
        else:
            try:
                ra = input("Enter RA (hours, e.g., 12.5 or 12:30:00, 'x' to cancel): ").strip()
                if ra.lower() == "x":
                    return
                dec = input("Enter Dec (degrees, e.g., +45.5 or +45:30:00): ").strip()
                self.ctx.target = {
                    "name": f"RA{ra}_Dec{dec}",
                    "searchgroup": "radec",
                    "searchterm": f"{ra},{dec}",
                }
                print(f"Selected target: RA={ra}, Dec={dec}")
            except Exception as e:
                print(f"Error: {e}")

    def _select_altaz(self) -> None:
        """Select a custom Alt/Az position."""
        if self._target_chooser:
            result = self._target_chooser.altaz_object()
            self._set_target(result)
        else:
            try:
                alt = input("Enter Altitude (degrees, 0-90, 'x' to cancel): ").strip()
                if alt.lower() == "x":
                    return
                az = input("Enter Azimuth (degrees, 0-360): ").strip()
                self.ctx.target = {
                    "name": f"Alt{alt}_Az{az}",
                    "objecttype": "altaz",
                    "searchgroup": "altaz",
                    "searchterm": f"{alt},{az}",
                }
                print(f"Selected target: Alt={alt}°, Az={az}°")
            except Exception as e:
                print(f"Error: {e}")

    def _select_aurora(self) -> None:
        """Select aurora observation mode."""
        if self._target_chooser:
            result = self._target_chooser.choose_aurora()
            self._set_target(result)
        else:
            # Aurora mode - point camera towards magnetic north at a low angle
            print("Aurora mode: Camera will point towards magnetic north")
            az = input("Enter Azimuth for aurora (default: 0 for north, 'x' to cancel): ").strip()
            if az.lower() == "x":
                return
            if not az:
                az = "0"
            alt = input("Enter Altitude (default: 30): ").strip()
            if not alt:
                alt = "30"
            self.ctx.target = {
                "name": "Aurora",
                "objecttype": "aurora",
                "searchgroup": "aurora",
                "searchterm": f"{alt},{az}",
            }
            print(f"Selected target: Aurora observation (Alt={alt}°, Az={az}°)")

    def _begin_observation(self) -> None:
        """Begin or manage observation."""
        if self.ctx.target is None:
            print("\nNo target selected. Please select a target first.")
            return

        target_name = (
            self.ctx.target.get("name", self.ctx.target)
            if isinstance(self.ctx.target, dict)
            else str(self.ctx.target)
        )
        print(f"\nCurrent target: {target_name}")
        print("Observation options:")
        print("  1. Start tracking")
        print("  2. Single exposure")
        print("  3. Observation run (multiple exposures)")
        print("  b. Back")

        choice = input("Choice: ").lower().strip()
        if choice == "1":
            print("Starting tracking...")
            self._start_tracking_only()
        elif choice == "2":
            print("Taking single exposure...")
            self._take_single_exposure()
        elif choice == "3":
            print("Starting observation run...")
            self._start_observation_run()

    def _build_observation_context(self) -> ObservationContext:
        """Build observation context from application context.

        Returns:
            ObservationContext ready for observation run
        """
        return ObservationContext(
            parameters=self.ctx.parameters,
            target=self.ctx.target,
            session=self.ctx.session,
            camera=self.ctx.camera,
            motor_controls=self.ctx.motor_controls,
            mctl=self.ctx.mctl,
            camera_thread=self.ctx.camera_thread,
            mctl_thread=self.ctx.mctl_thread,
            message_thread=self.ctx.message_thread,
            camera_control_queue=self.ctx.camera_control_queue,
            camera_status_queue=self.ctx.camera_status_queue,
            logger=self.ctx.main_log,
            storage_monitor=self.ctx.storage_monitor,
            drift_tracker=self.ctx.drift_tracker,
        )

    def _start_tracking_only(self) -> None:
        """Start tracking mode without taking photos."""
        obs_ctx = self._build_observation_context()
        obs_loop = ObservationLoop(obs_ctx)

        # Move to target position
        print("Moving to target...")
        if obs_loop._goto_target():
            print("On target. Tracking active. Press Ctrl+C to stop.")
            try:
                # Simple tracking loop without photos
                while True:
                    obs_loop._update_target_position()
                    obs_loop._extend_trajectories()
                    import time

                    time.sleep(0.1)
            except KeyboardInterrupt:
                print("\nTracking stopped.")
                obs_loop._stop_motors()
        else:
            print("Failed to move to target.")

    def _take_single_exposure(self) -> None:
        """Take a single exposure of the current target."""
        if not self.ctx.camera and not self.ctx.camera_thread:
            print("Camera not initialized.")
            return

        # Move to target first
        obs_ctx = self._build_observation_context()
        obs_loop = ObservationLoop(obs_ctx)

        print("Moving to target...")
        if obs_loop._goto_target():
            print("On target. Taking exposure...")
            # Send single photo request to camera
            if self.ctx.camera_control_queue:
                control_msg = {
                    "TimeStamp": now_utc(),
                    "ReadyToObserve": True,
                    "BatchSize": 1,
                }
                self.ctx.camera_control_queue.put(control_msg)
                print("Exposure requested. Check camera status.")
            else:
                print("Camera control queue not available.")
        else:
            print("Failed to move to target.")

    def _start_observation_run(self) -> None:
        """Start a full observation run with multiple exposures."""
        obs_ctx = self._build_observation_context()

        print("\nStarting observation run...")
        print("Press Ctrl+C to stop observation.\n")

        result = start_observation(obs_ctx, batch_mode=False)

        # Show result
        print("\nObservation complete!")
        print(f"  Photos taken: {result.photo_count}")
        print(f"  Duration: {result.duration_seconds:.1f} seconds")
        print(f"  Success: {result.success}")
        if result.status_codes:
            print(f"  Status: {', '.join(str(s) for s in result.status_codes)}")

        input("\nPress Enter to continue...")

    def _show_status(self) -> None:
        """Show current system status."""
        print("\n" + "=" * 40)
        print("PILOMAR STATUS")
        print("=" * 40)

        # Target status
        if self.ctx.target:
            target_name = (
                self.ctx.target.get("name", self.ctx.target)
                if isinstance(self.ctx.target, dict)
                else str(self.ctx.target)
            )
            print(f"Target: {target_name}")
        else:
            print("Target: None selected")

        # Location
        if self.ctx.parameters:
            lat = self.ctx.parameters.home_lat or "Not set"
            lon = self.ctx.parameters.home_lon or "Not set"
            print(f"Location: {lat}, {lon}")

        # Time
        import datetime

        utc_now = datetime.datetime.now(datetime.timezone.utc)
        print(f"UTC Time: {utc_now.strftime('%Y-%m-%d %H:%M:%S')}")

        # Hardware status
        print(f"\nCamera: {'Connected' if self.ctx.camera else 'Not initialized'}")
        if self.ctx.direct_driver is not None:
            driver = self.ctx.direct_driver
            print(
                f"Motors (direct GPIO): AZ={driver.az_degrees():.1f}°  "
                f"ALT={driver.alt_degrees():.1f}°"
            )
        else:
            print(
                f"Motors: {'Ready' if self.ctx.motor_controls else 'Not initialized'}"
            )
        if self.ctx.direct_driver is None:
            print(
                f"Microcontroller: {'Connected' if self.ctx.mctl else 'Not initialized'}"
            )

        # Parameters summary
        if self.ctx.parameters:
            batch = self.ctx.parameters.batch_size
            print(f"\nBatch size: {batch} frames")

        # Session status
        if self.ctx.session:
            print("Session: Active")
        else:
            print("Session: None")

        # Schedule status
        if hasattr(self, "_schedule") and self._schedule:
            print(f"Schedule: {len(self._schedule)} targets queued")

        print("=" * 40)
        input("Press Enter to continue...")

    def _should_exit(self) -> bool:
        """Check if the user wants to exit.

        Returns:
            True if user confirms exit, False otherwise
        """
        try:
            response = input("Do you really want to shut down? [y/N] ").lower().strip()
            return response in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            return True

    # =========================================================================
    # CAMERA TOOLS MENU
    # =========================================================================

    def _camera_tools_menu(self) -> None:
        """Display camera tools submenu."""
        while True:
            print("\nCamera Tools")
            print("=" * 40)
            print("--- Exposure Settings ---")
            print("1. Set exposure time")
            print("2. Set light batch size")
            print("3. Set control batch size")
            print("4. Set timelapse delay")
            print("--- Calibration Frames ---")
            print("5. Take dark frames")
            print("6. Take flat frames")
            print("7. Take bias frames")
            print("8. Take dark flat frames")
            print("--- Capture ---")
            print("9. Take preview frames")
            print("a. Take auto frames")
            print("--- Image Processing ---")
            print("c. Choose image types (JPG/DNG/FITS)")
            print("d. Scan images for meteors")
            print("--- Status ---")
            print("s. Camera status")
            print("e. Enable/disable camera")
            print("b. Back to main menu")

            choice = input("Choice: ").lower().strip()

            if choice == "b":
                break
            elif choice == "1":
                self._set_exposure_time()
            elif choice == "2":
                self._set_batch_size()
            elif choice == "3":
                self._set_control_batch_size()
            elif choice == "4":
                self._set_timelapse_delay()
            elif choice == "5":
                self._take_dark_frames()
            elif choice == "6":
                self._take_flat_frames()
            elif choice == "7":
                self._take_bias_frames()
            elif choice == "8":
                self._take_dark_flat_frames()
            elif choice == "9":
                self._take_preview_frames()
            elif choice == "a":
                self._take_auto_frames()
            elif choice == "c":
                self._choose_image_types()
            elif choice == "d":
                self._scan_for_meteors()
            elif choice == "s":
                self._camera_status()
            elif choice == "e":
                self._toggle_camera()
            else:
                print("Invalid choice")

    def _set_exposure_time(self) -> None:
        """Set the exposure time for light frames."""
        if self.ctx.camera:
            current = getattr(self.ctx.camera, "ExposureSeconds", 1.0)
            print(f"\nCurrent exposure time: {current} seconds")
        else:
            current = (
                getattr(self.ctx.parameters, "ExposureSeconds", 1.0) if self.ctx.parameters else 1.0
            )
            print(f"\nDefault exposure time: {current} seconds")

        try:
            value = input("Enter new exposure time in seconds (or 'x' to cancel): ").strip()
            if value.lower() == "x":
                return

            new_exposure = float(value)
            if new_exposure <= 0:
                print("Exposure time must be positive.")
                return
            if new_exposure > 200:
                print("Warning: Maximum exposure is typically 200 seconds.")
                if input("Continue anyway? [y/N] ").lower() != "y":
                    return

            if self.ctx.camera:
                self.ctx.camera.ExposureSeconds = new_exposure
            if self.ctx.parameters:
                self.ctx.parameters.ExposureSeconds = new_exposure

            print(f"Exposure time set to {new_exposure} seconds")

        except ValueError:
            print("Invalid number. Please enter a decimal value.")

    def _set_batch_size(self) -> None:
        """Set the number of frames per observation batch."""
        current = self.ctx.parameters.batch_size if self.ctx.parameters else 100
        print(f"\nCurrent batch size: {current} frames")

        try:
            value = input("Enter new batch size (or 'x' to cancel): ").strip()
            if value.lower() == "x":
                return

            new_batch = int(value)
            if new_batch < 1:
                print("Batch size must be at least 1.")
                return

            if self.ctx.parameters:
                self.ctx.parameters.BatchSize = new_batch

            print(f"Batch size set to {new_batch} frames")

        except ValueError:
            print("Invalid number. Please enter an integer.")

    def _take_dark_frames(self) -> None:
        """Capture a set of dark frames."""
        if not self.ctx.camera:
            print("\nCamera not initialized.")
            return

        try:
            count = input("Number of dark frames to capture (default 10): ").strip()
            count = int(count) if count else 10

            print(f"\nCapturing {count} dark frames...")
            print("(Keep the lens cap on!)")

            if hasattr(self.ctx.camera, "DarkSet"):
                self.ctx.camera.DarkSet(count)
                print("Dark frames captured successfully.")
            else:
                print("Dark frame capture not available.")

        except ValueError:
            print("Invalid number.")
        except Exception as e:
            print(f"Error capturing dark frames: {e}")

    def _take_flat_frames(self) -> None:
        """Capture a set of flat frames."""
        if not self.ctx.camera:
            print("\nCamera not initialized.")
            return

        try:
            count = input("Number of flat frames to capture (default 10): ").strip()
            count = int(count) if count else 10

            print(f"\nCapturing {count} flat frames...")
            print("(Point at evenly illuminated surface)")

            if hasattr(self.ctx.camera, "FlatSet"):
                self.ctx.camera.FlatSet(count)
                print("Flat frames captured successfully.")
            else:
                print("Flat frame capture not available.")

        except ValueError:
            print("Invalid number.")
        except Exception as e:
            print(f"Error capturing flat frames: {e}")

    def _take_bias_frames(self) -> None:
        """Capture a set of bias/offset frames."""
        if not self.ctx.camera:
            print("\nCamera not initialized.")
            return

        try:
            count = input("Number of bias frames to capture (default 10): ").strip()
            count = int(count) if count else 10

            print(f"\nCapturing {count} bias frames...")
            print("(Keep the lens cap on!)")

            if hasattr(self.ctx.camera, "BiasSet"):
                self.ctx.camera.BiasSet(count)
                print("Bias frames captured successfully.")
            else:
                print("Bias frame capture not available.")

        except ValueError:
            print("Invalid number.")
        except Exception as e:
            print(f"Error capturing bias frames: {e}")

    def _choose_image_types(self) -> None:
        """Choose which image file types to save."""
        if not self.ctx.parameters:
            print("\nParameters not loaded.")
            return

        print("\nImage Types to Save")
        print("-" * 30)

        save_jpg = getattr(self.ctx.parameters, "CameraSaveJpg", True)
        save_dng = getattr(self.ctx.parameters, "CameraSaveDng", True)
        save_fits = getattr(self.ctx.parameters, "CameraSaveFits", False)

        print(f"1. JPG  : {'[X]' if save_jpg else '[ ]'}")
        print(f"2. DNG  : {'[X]' if save_dng else '[ ]'}")
        print(f"3. FITS : {'[X]' if save_fits else '[ ]'}")
        print("x. Done")

        while True:
            choice = input("Toggle (1/2/3) or x to finish: ").strip()
            if choice == "x":
                break
            elif choice == "1":
                self.ctx.parameters.CameraSaveJpg = not save_jpg
                save_jpg = not save_jpg
                print(f"JPG: {'Enabled' if save_jpg else 'Disabled'}")
            elif choice == "2":
                self.ctx.parameters.CameraSaveDng = not save_dng
                save_dng = not save_dng
                print(f"DNG: {'Enabled' if save_dng else 'Disabled'}")
            elif choice == "3":
                self.ctx.parameters.CameraSaveFits = not save_fits
                save_fits = not save_fits
                print(f"FITS: {'Enabled' if save_fits else 'Disabled'}")

        if not (save_jpg or save_dng or save_fits):
            print("\nWarning: No image types are enabled!")

    def _camera_status(self) -> None:
        """Show camera status information."""
        print("\nCamera Status")
        print("=" * 40)

        if self.ctx.camera:
            print("Camera: Connected")
            if hasattr(self.ctx.camera, "ExposureSeconds"):
                print(f"Exposure: {self.ctx.camera.ExposureSeconds}s")
            if hasattr(self.ctx.camera, "TimelapseSeconds"):
                print(f"Timelapse delay: {self.ctx.camera.TimelapseSeconds}s")
            if hasattr(self.ctx.camera, "CameraModel"):
                print(f"Model: {self.ctx.camera.CameraModel}")
            if hasattr(self.ctx.camera, "SensorSize"):
                print(f"Sensor: {self.ctx.camera.SensorSize}")
        else:
            print("Camera: Not initialized")

        if self.ctx.parameters:
            print(f"\nLight batch size: {getattr(self.ctx.parameters, 'BatchSize', 'N/A')}")
            print(f"Control batch size: {getattr(self.ctx.parameters, 'ControlBatchSize', 'N/A')}")
            print(f"Save JPG: {getattr(self.ctx.parameters, 'CameraSaveJpg', 'N/A')}")
            print(f"Save DNG: {getattr(self.ctx.parameters, 'CameraSaveDng', 'N/A')}")
            print(f"Save FITS: {getattr(self.ctx.parameters, 'CameraSaveFits', 'N/A')}")

        input("\nPress Enter to continue...")

    def _toggle_camera(self) -> None:
        """Enable or disable the camera."""
        if not self.ctx.parameters:
            print("\nParameters not loaded.")
            return

        current = getattr(self.ctx.parameters, "CameraEnabled", True)
        print(f"\nCamera is currently: {'Enabled' if current else 'Disabled'}")

        if current:
            if input("Disable camera? [y/N] ").lower() == "y":
                self.ctx.parameters.CameraEnabled = False
                print("Camera disabled. Restart required for change to take effect.")
        else:
            if input("Enable camera? [y/N] ").lower() == "y":
                self.ctx.parameters.CameraEnabled = True
                print("Camera enabled. Restart required for change to take effect.")

    def _set_control_batch_size(self) -> None:
        """Set the control batch size for processing."""
        if not self.ctx.parameters:
            print("\nParameters not loaded.")
            return

        current = getattr(self.ctx.parameters, "ControlBatchSize", 5)
        print(f"\nCurrent control batch size: {current}")
        print("(Number of frames to process together for motion detection)")

        new_value = input("New control batch size (or Enter to keep current): ").strip()
        if new_value:
            try:
                new_value = int(new_value)
                if new_value < 1:
                    print("Batch size must be at least 1.")
                    return
                self.ctx.parameters.ControlBatchSize = new_value
                print(f"Control batch size set to: {new_value}")
            except ValueError:
                print("Invalid number.")

    def _set_timelapse_delay(self) -> None:
        """Set the delay between timelapse frames."""
        if not self.ctx.camera:
            print("\nCamera not initialized.")
            return

        current = getattr(self.ctx.camera, "TimelapseSeconds", 0)
        print(f"\nCurrent timelapse delay: {current}s")
        print("(0 = no delay, frames captured continuously)")

        new_value = input("New timelapse delay in seconds (or Enter to keep current): ").strip()
        if new_value:
            try:
                new_value = float(new_value)
                if new_value < 0:
                    print("Delay must be 0 or positive.")
                    return
                if hasattr(self.ctx.camera, "SetTimelapse"):
                    self.ctx.camera.SetTimelapse(new_value)
                    print(f"Timelapse delay set to: {new_value}s")
                else:
                    print("Timelapse not available on this camera.")
            except ValueError:
                print("Invalid number.")

    def _take_dark_flat_frames(self) -> None:
        """Capture a set of dark flat frames."""
        if not self.ctx.camera:
            print("\nCamera not initialized.")
            return

        try:
            count = input("Number of dark flat frames to capture (default 10): ").strip()
            count = int(count) if count else 10

            print(f"\nCapturing {count} dark flat frames...")
            print("(Cover the lens and use same settings as flat frames)")

            if hasattr(self.ctx.camera, "DarkFlatSet"):
                self.ctx.camera.DarkFlatSet(count)
                print("Dark flat frames captured successfully.")
            else:
                print("Dark flat frame capture not available.")

        except ValueError:
            print("Invalid number.")
        except Exception as e:
            print(f"Error capturing dark flat frames: {e}")

    def _take_preview_frames(self) -> None:
        """Capture preview/live frames for focusing or framing."""
        if not self.ctx.camera:
            print("\nCamera not initialized.")
            return

        print("\nStarting preview mode...")
        print("(Press Ctrl+C to stop)")

        try:
            if hasattr(self.ctx.camera, "LivePreview"):
                self.ctx.camera.LivePreview()
                print("Preview mode ended.")
            else:
                print("Live preview not available on this camera.")
        except KeyboardInterrupt:
            print("\nPreview stopped.")
        except Exception as e:
            print(f"Error during preview: {e}")

    def _take_auto_frames(self) -> None:
        """Automatically capture frames with optimal settings."""
        if not self.ctx.camera:
            print("\nCamera not initialized.")
            return

        print("\nStarting auto capture mode...")
        print("Camera will adjust settings automatically.")
        print("(Press Ctrl+C to stop)")

        try:
            if hasattr(self.ctx.camera, "AutoPhoto"):
                self.ctx.camera.AutoPhoto()
                print("Auto capture completed.")
            else:
                print("Auto capture not available on this camera.")
        except KeyboardInterrupt:
            print("\nAuto capture stopped.")
        except Exception as e:
            print(f"Error during auto capture: {e}")

    def _scan_for_meteors(self) -> None:
        """Scan captured images for meteor traces."""
        if not self.ctx.camera:
            print("\nCamera not initialized.")
            return

        print("\nScanning images for meteors...")
        print("This may take a while depending on the number of images.")

        try:
            if hasattr(self.ctx.camera, "MeteorFileScan"):
                result = self.ctx.camera.MeteorFileScan()
                if result:
                    print(f"Meteor scan complete. Results: {result}")
                else:
                    print("Meteor scan complete. No meteors detected.")
            else:
                print("Meteor scanning not available.")
        except Exception as e:
            print(f"Error during meteor scan: {e}")

    # =========================================================================
    # MOTOR TOOLS MENU
    # =========================================================================

    def _motor_tools_menu(self) -> None:
        """Display motor tools submenu."""
        while True:
            print("\nMotor Tools")
            print("=" * 40)
            print("1. Motor status")
            print("2. Move azimuth to angle")
            print("3. Move altitude to angle")
            print("4. Tune azimuth position")
            print("5. Tune altitude position")
            print("6. Set motor speed")
            print("7. Home all motors")
            print("b. Back to main menu")

            choice = input("Choice: ").lower().strip()

            if choice == "b":
                break
            elif choice == "1":
                self._motor_status()
            elif choice == "2":
                self._move_azimuth()
            elif choice == "3":
                self._move_altitude()
            elif choice == "4":
                self._tune_azimuth()
            elif choice == "5":
                self._tune_altitude()
            elif choice == "6":
                self._set_motor_speed()
            elif choice == "7":
                self._home_motors()
            else:
                print("Invalid choice")

    def _motor_status(self) -> None:
        """Show motor status information."""
        print("\nMotor Status")
        print("=" * 40)

        if self.ctx.direct_driver is not None:
            d = self.ctx.direct_driver
            print(f"\nAzimuth:  {d.az_degrees():.2f}°  ({d.az_position_steps} steps)")
            print(f"Altitude: {d.alt_degrees():.2f}°  ({d.alt_position_steps} steps)")
            print(f"AZ rate:  {d.az_rate:.1f} steps/sec")
            print(f"ALT rate: {d.alt_rate:.1f} steps/sec")
            home_state = "TRIGGERED" if d.home_pin_active() else "clear"
            print(f"Tilt switch (pin {d.home_pin}): {home_state}")
        elif self.ctx.motor_controls:
            for mc in self.ctx.motor_controls:
                name = getattr(mc, "MotorName", "Unknown")
                current_angle = getattr(mc, "CurrentAngle", 0.0)
                rest_angle = getattr(mc, "RestAngle", 0.0)
                print(f"\n{name}:")
                print(f"  Current angle: {current_angle:.2f}°")
                print(f"  Rest angle: {rest_angle:.2f}°")
                if hasattr(mc, "GearRatio"):
                    print(f"  Gear ratio: {mc.GearRatio}")
        else:
            print("Motors not initialized.")

        input("\nPress Enter to continue...")

    def _move_azimuth(self) -> None:
        """Move azimuth motor to a specific angle."""
        if self.ctx.direct_driver is not None:
            d = self.ctx.direct_driver
            slew = self.ctx.direct_slew
            print(f"\nCurrent azimuth: {d.az_degrees():.2f}°")
            try:
                value = input("Enter target angle (0-360, or 'x' to cancel): ").strip()
                if value.lower() == "x":
                    return
                target = float(value)
                if not 0 <= target <= 360:
                    print("Angle must be between 0 and 360.")
                    return
                print(f"Slewing to {target}°...")
                slew.slew_to_altaz(d.alt_degrees(), target, resume_tracking=False)
                print(f"Done. AZ={d.az_degrees():.2f}°")
            except ValueError:
                print("Invalid angle.")
            except Exception as e:
                print(f"Error: {e}")
            return

        if not self.ctx.motor_controls:
            print("\nMotors not initialized.")
            return

        az_motor = None
        for mc in self.ctx.motor_controls:
            name = getattr(mc, "MotorName", "").lower()
            if "az" in name:
                az_motor = mc
                break

        if not az_motor:
            print("Azimuth motor not found.")
            return

        current = getattr(az_motor, "CurrentAngle", 0.0)
        print(f"\nCurrent azimuth: {current:.2f}°")

        try:
            value = input("Enter target angle (0-360, or 'x' to cancel): ").strip()
            if value.lower() == "x":
                return
            target = float(value)
            if not 0 <= target <= 360:
                print("Angle must be between 0 and 360.")
                return
            print(f"Moving to {target}°...")
            if hasattr(az_motor, "GoToAngle"):
                az_motor.GoToAngle(target)
                print("Move complete.")
            else:
                print("GoToAngle method not available.")
        except ValueError:
            print("Invalid angle.")
        except Exception as e:
            print(f"Error: {e}")

    def _move_altitude(self) -> None:
        """Move altitude motor to a specific angle."""
        if self.ctx.direct_driver is not None:
            d = self.ctx.direct_driver
            slew = self.ctx.direct_slew
            min_alt = getattr(self.ctx.parameters, "min_altitude_angle", 0) or 0
            max_alt = getattr(self.ctx.parameters, "max_altitude_angle", 90) or 90
            print(f"\nCurrent altitude: {d.alt_degrees():.2f}°")
            print(f"Range: {min_alt}° to {max_alt}°")
            try:
                value = input(
                    f"Enter target angle ({min_alt}-{max_alt}, or 'x' to cancel): "
                ).strip()
                if value.lower() == "x":
                    return
                target = float(value)
                if not min_alt <= target <= max_alt:
                    print(f"Angle must be between {min_alt} and {max_alt}.")
                    return
                print(f"Slewing to {target}°...")
                slew.slew_to_altaz(target, d.az_degrees(), resume_tracking=False)
                print(f"Done. ALT={d.alt_degrees():.2f}°")
            except ValueError:
                print("Invalid angle.")
            except Exception as e:
                print(f"Error: {e}")
            return

        if not self.ctx.motor_controls:
            print("\nMotors not initialized.")
            return

        alt_motor = None
        for mc in self.ctx.motor_controls:
            name = getattr(mc, "MotorName", "").lower()
            if "alt" in name:
                alt_motor = mc
                break

        if not alt_motor:
            print("Altitude motor not found.")
            return

        current = getattr(alt_motor, "CurrentAngle", 0.0)
        min_alt = getattr(self.ctx.parameters, "MinAltitudeAngle", 0) if self.ctx.parameters else 0
        max_alt = (
            getattr(self.ctx.parameters, "MaxAltitudeAngle", 90) if self.ctx.parameters else 90
        )

        print(f"\nCurrent altitude: {current:.2f}°")
        print(f"Range: {min_alt}° to {max_alt}°")

        try:
            value = input(f"Enter target angle ({min_alt}-{max_alt}, or 'x' to cancel): ").strip()
            if value.lower() == "x":
                return
            target = float(value)
            if not min_alt <= target <= max_alt:
                print(f"Angle must be between {min_alt} and {max_alt}.")
                return
            print(f"Moving to {target}°...")
            if hasattr(alt_motor, "GoToAngle"):
                alt_motor.GoToAngle(target)
                print("Move complete.")
            else:
                print("GoToAngle method not available.")
        except ValueError:
            print("Invalid angle.")
        except Exception as e:
            print(f"Error: {e}")

    def _tune_azimuth(self) -> None:
        """Fine-tune azimuth position with small adjustments."""
        if self.ctx.direct_driver is not None:
            d = self.ctx.direct_driver
            slew = self.ctx.direct_slew
            print("\nAzimuth Tuning")
            print("-" * 30)
            print("Commands: +1, +0.1, -1, -0.1, or absolute angle, 'x' to exit")
            while True:
                print(f"Current: {d.az_degrees():.2f}°")
                cmd = input("Adjust: ").strip()
                if cmd.lower() == "x":
                    break
                try:
                    if cmd.startswith("+") or cmd.startswith("-"):
                        target = (d.az_degrees() + float(cmd)) % 360
                    else:
                        target = float(cmd) % 360
                    slew.slew_to_altaz(d.alt_degrees(), target, resume_tracking=False)
                except ValueError:
                    print("Invalid input.")
            return

        if not self.ctx.motor_controls:
            print("\nMotors not initialized.")
            return

        az_motor = None
        for mc in self.ctx.motor_controls:
            name = getattr(mc, "MotorName", "").lower()
            if "az" in name:
                az_motor = mc
                break

        if not az_motor:
            print("Azimuth motor not found.")
            return

        print("\nAzimuth Tuning")
        print("-" * 30)
        print("Commands: +1, +0.1, -1, -0.1, or angle, 'x' to exit")

        while True:
            current = getattr(az_motor, "CurrentAngle", 0.0)
            print(f"Current: {current:.2f}°")

            cmd = input("Adjust: ").strip()
            if cmd.lower() == "x":
                break

            try:
                if cmd.startswith("+") or cmd.startswith("-"):
                    delta = float(cmd)
                    target = current + delta
                else:
                    target = float(cmd)

                target = target % 360  # Wrap around
                if hasattr(az_motor, "GoToAngle"):
                    az_motor.GoToAngle(target)
            except ValueError:
                print("Invalid input.")

    def _tune_altitude(self) -> None:
        """Fine-tune altitude position with small adjustments."""
        if self.ctx.direct_driver is not None:
            d = self.ctx.direct_driver
            slew = self.ctx.direct_slew
            min_alt = getattr(self.ctx.parameters, "min_altitude_angle", 0) or 0
            max_alt = getattr(self.ctx.parameters, "max_altitude_angle", 90) or 90
            print("\nAltitude Tuning")
            print("-" * 30)
            print("Commands: +1, +0.1, -1, -0.1, or absolute angle, 'x' to exit")
            while True:
                print(f"Current: {d.alt_degrees():.2f}°")
                cmd = input("Adjust: ").strip()
                if cmd.lower() == "x":
                    break
                try:
                    if cmd.startswith("+") or cmd.startswith("-"):
                        target = d.alt_degrees() + float(cmd)
                    else:
                        target = float(cmd)
                    target = max(min_alt, min(max_alt, target))
                    slew.slew_to_altaz(target, d.az_degrees(), resume_tracking=False)
                except ValueError:
                    print("Invalid input.")
            return

        if not self.ctx.motor_controls:
            print("\nMotors not initialized.")
            return

        alt_motor = None
        for mc in self.ctx.motor_controls:
            name = getattr(mc, "MotorName", "").lower()
            if "alt" in name:
                alt_motor = mc
                break

        if not alt_motor:
            print("Altitude motor not found.")
            return

        min_alt = getattr(self.ctx.parameters, "MinAltitudeAngle", 0) if self.ctx.parameters else 0
        max_alt = (
            getattr(self.ctx.parameters, "MaxAltitudeAngle", 90) if self.ctx.parameters else 90
        )

        print("\nAltitude Tuning")
        print("-" * 30)
        print("Commands: +1, +0.1, -1, -0.1, or angle, 'x' to exit")

        while True:
            current = getattr(alt_motor, "CurrentAngle", 0.0)
            print(f"Current: {current:.2f}°")

            cmd = input("Adjust: ").strip()
            if cmd.lower() == "x":
                break

            try:
                if cmd.startswith("+") or cmd.startswith("-"):
                    delta = float(cmd)
                    target = current + delta
                else:
                    target = float(cmd)

                target = max(min_alt, min(max_alt, target))  # Clamp to range
                if hasattr(alt_motor, "GoToAngle"):
                    alt_motor.GoToAngle(target)
            except ValueError:
                print("Invalid input.")

    def _set_motor_speed(self) -> None:
        """Set motor speed preset."""
        if not self.ctx.parameters:
            print("\nParameters not loaded.")
            return

        speed_list = getattr(self.ctx.parameters, "SpeedList", {})
        if not speed_list:
            print("No speed presets available.")
            return

        print("\nMotor Speed Presets")
        print("-" * 30)

        for i, (name, config) in enumerate(speed_list.items(), 1):
            label = config.get("label", name)
            print(f"{i}. {label}")
        print("x. Cancel")

        try:
            choice = input("Select speed: ").strip()
            if choice.lower() == "x":
                return

            idx = int(choice) - 1
            names = list(speed_list.keys())
            if 0 <= idx < len(names):
                selected = speed_list[names[idx]]
                self.ctx.parameters.FastTime = selected.get("FastTime", 0.001)
                self.ctx.parameters.SlowTime = selected.get("SlowTime", 0.05)
                self.ctx.parameters.TimeDelta = selected.get("TimeDelta", 0.003)
                print(f"Speed set to: {selected.get('label', names[idx])}")
            else:
                print("Invalid selection.")

        except ValueError:
            print("Invalid input.")

    # =========================================================================
    # MICROCONTROLLER MENU
    # =========================================================================

    def _microcontroller_menu(self) -> None:
        """Display microcontroller tools submenu."""
        while True:
            print("\nMicrocontroller Tools")
            print("=" * 40)
            print("1. Microcontroller status")
            print("2. Restart microcontroller")
            print("3. LEDs on")
            print("4. LEDs off")
            print("5. GPIO power on")
            print("6. GPIO power off")
            print("b. Back to main menu")

            choice = input("Choice: ").lower().strip()

            if choice == "b":
                break
            elif choice == "1":
                self._mctl_status()
            elif choice == "2":
                self._mctl_restart()
            elif choice == "3":
                self._mctl_leds_on()
            elif choice == "4":
                self._mctl_leds_off()
            elif choice == "5":
                self._mctl_power_on()
            elif choice == "6":
                self._mctl_power_off()
            else:
                print("Invalid choice")

    def _mctl_status(self) -> None:
        """Show microcontroller status."""
        print("\nMicrocontroller Status")
        print("=" * 40)

        if self.ctx.mctl:
            print("Microcontroller: Connected")
            if hasattr(self.ctx.mctl, "DeviceName"):
                print(f"Device: {self.ctx.mctl.DeviceName}")
            if hasattr(self.ctx.mctl, "Version"):
                print(f"Version: {self.ctx.mctl.Version}")
            if hasattr(self.ctx.mctl, "LedStatus"):
                print(f"LEDs: {'On' if self.ctx.mctl.LedStatus else 'Off'}")
        else:
            print("Microcontroller: Not connected")

        input("\nPress Enter to continue...")

    def _mctl_restart(self) -> None:
        """Restart the microcontroller."""
        if not self.ctx.mctl:
            print("\nMicrocontroller not connected.")
            return

        if input("Restart microcontroller? [y/N] ").lower() == "y":
            print("Restarting microcontroller...")
            if hasattr(self.ctx.mctl, "Reset"):
                self.ctx.mctl.Reset(planned=True)
                print("Microcontroller restarted.")
            else:
                print("Reset method not available.")

    def _mctl_leds_on(self) -> None:
        """Turn microcontroller LEDs on."""
        if not self.ctx.mctl:
            print("\nMicrocontroller not connected.")
            return

        if hasattr(self.ctx.mctl, "SetLedStatus"):
            self.ctx.mctl.SetLedStatus(True)
            print("LEDs turned on.")
        elif hasattr(self.ctx.mctl, "LedStatus"):
            self.ctx.mctl.LedStatus = True
            print("LEDs turned on.")
        else:
            print("LED control not available.")

    def _mctl_leds_off(self) -> None:
        """Turn microcontroller LEDs off."""
        if not self.ctx.mctl:
            print("\nMicrocontroller not connected.")
            return

        if hasattr(self.ctx.mctl, "SetLedStatus"):
            self.ctx.mctl.SetLedStatus(False)
            print("LEDs turned off.")
        elif hasattr(self.ctx.mctl, "LedStatus"):
            self.ctx.mctl.LedStatus = False
            print("LEDs turned off.")
        else:
            print("LED control not available.")

    def _mctl_power_on(self) -> None:
        """Turn on microcontroller GPIO power."""
        if not self.ctx.mctl:
            print("\nMicrocontroller not connected.")
            return

        if hasattr(self.ctx.mctl, "PowerOn"):
            self.ctx.mctl.PowerOn()
            print("GPIO power turned on.")
        elif hasattr(self.ctx.mctl, "ResetPin") and hasattr(self.ctx.mctl.ResetPin, "On"):
            self.ctx.mctl.ResetPin.On()
            print("GPIO power turned on.")
        else:
            print("Power control not available.")

    def _mctl_power_off(self) -> None:
        """Turn off microcontroller GPIO power."""
        if not self.ctx.mctl:
            print("\nMicrocontroller not connected.")
            return

        if input("Turn off microcontroller power? [y/N] ").lower() == "y":
            if hasattr(self.ctx.mctl, "PowerOff"):
                self.ctx.mctl.PowerOff()
                print("GPIO power turned off.")
            elif hasattr(self.ctx.mctl, "ResetPin") and hasattr(self.ctx.mctl.ResetPin, "Off"):
                self.ctx.mctl.ResetPin.Off()
                print("GPIO power turned off.")
            else:
                print("Power control not available.")

    # =========================================================================
    # TRACKING TOOLS MENU
    # =========================================================================

    def _tracking_tools_menu(self) -> None:
        """Display tracking tools submenu."""
        while True:
            print("\nTracking Tools")
            print("=" * 40)
            print("1. Set tracking exposure time")
            print("2. Enable/disable drift tracking")
            print("3. Set trajectory window")
            print("4. Take tracking photo")
            print("5. Tracking status")
            print("b. Back to main menu")

            choice = input("Choice: ").lower().strip()

            if choice == "b":
                break
            elif choice == "1":
                self._set_tracking_exposure()
            elif choice == "2":
                self._toggle_drift_tracking()
            elif choice == "3":
                self._set_trajectory_window()
            elif choice == "4":
                self._take_tracking_photo()
            elif choice == "5":
                self._tracking_status()
            else:
                print("Invalid choice")

    def _set_tracking_exposure(self) -> None:
        """Set exposure time for tracking images."""
        if not self.ctx.camera:
            print("\nCamera not initialized.")
            return

        current = getattr(self.ctx.camera, "TrackingExposureSeconds", 5.0)
        print(f"\nCurrent tracking exposure: {current}s")
        print("(Shorter than main exposure for faster drift detection)")

        new_value = input("New tracking exposure in seconds (or Enter to keep current): ").strip()
        if new_value:
            try:
                new_value = float(new_value)
                if new_value <= 0:
                    print("Exposure must be positive.")
                    return
                self.ctx.camera.TrackingExposureSeconds = new_value
                print(f"Tracking exposure set to: {new_value}s")
            except ValueError:
                print("Invalid number.")

    def _toggle_drift_tracking(self) -> None:
        """Enable or disable drift tracking."""
        if not self.ctx.parameters:
            print("\nParameters not loaded.")
            return

        current = getattr(self.ctx.parameters, "DriftTrackingEnabled", True)
        print(f"\nDrift tracking is currently: {'Enabled' if current else 'Disabled'}")
        print("(When enabled, camera adjusts position based on star drift)")

        if current:
            if input("Disable drift tracking? [y/N] ").lower() == "y":
                self.ctx.parameters.DriftTrackingEnabled = False
                print("Drift tracking disabled.")
        else:
            if input("Enable drift tracking? [y/N] ").lower() == "y":
                self.ctx.parameters.DriftTrackingEnabled = True
                print("Drift tracking enabled.")

    def _set_trajectory_window(self) -> None:
        """Set the trajectory calculation window."""
        if not self.ctx.parameters:
            print("\nParameters not loaded.")
            return

        current = getattr(self.ctx.parameters, "TrajectoryWindow", 1200)
        print(f"\nCurrent trajectory window: {current}s")
        print("(Time span for calculating target trajectory, in seconds)")

        new_value = input("New trajectory window in seconds (or Enter to keep current): ").strip()
        if new_value:
            try:
                new_value = int(new_value)
                if new_value < 60:
                    print("Window must be at least 60 seconds.")
                    return
                self.ctx.parameters.TrajectoryWindow = new_value
                print(f"Trajectory window set to: {new_value}s")
            except ValueError:
                print("Invalid number.")

    def _take_tracking_photo(self) -> None:
        """Take a tracking photo for drift detection."""
        if not self.ctx.camera:
            print("\nCamera not initialized.")
            return

        print("\nTaking tracking photo...")

        try:
            if hasattr(self.ctx.camera, "TakeTrackingPhoto"):
                self.ctx.camera.TakeTrackingPhoto(batch_size=1)
                print("Tracking photo captured.")
            else:
                print("Tracking photo not available.")
        except Exception as e:
            print(f"Error taking tracking photo: {e}")

    def _tracking_status(self) -> None:
        """Show tracking status information."""
        print("\nTracking Status")
        print("=" * 40)

        if self.ctx.camera:
            track_exp = getattr(self.ctx.camera, "TrackingExposureSeconds", "N/A")
            print(f"Tracking exposure: {track_exp}s")
        else:
            print("Camera: Not initialized")

        if self.ctx.parameters:
            drift = getattr(self.ctx.parameters, "DriftTrackingEnabled", True)
            window = getattr(self.ctx.parameters, "TrajectoryWindow", 1200)
            print(f"Drift tracking: {'Enabled' if drift else 'Disabled'}")
            print(f"Trajectory window: {window}s")

        input("\nPress Enter to continue...")

    # =========================================================================
    # SETTINGS MENU
    # =========================================================================

    def _settings_menu(self) -> None:
        """Display settings/configuration menu."""
        while True:
            print("\nSettings")
            print("=" * 40)
            print("1. Show all parameters")
            print("2. Change home location")
            print("3. Set color scheme")
            print("4. Toggle debug mode")
            print("5. About Pilomar")
            print("b. Back to main menu")

            choice = input("Choice: ").lower().strip()

            if choice == "b":
                break
            elif choice == "1":
                self._show_parameters()
            elif choice == "2":
                self._change_location()
            elif choice == "3":
                self._set_color_scheme()
            elif choice == "4":
                self._toggle_debug()
            elif choice == "5":
                self._about()
            else:
                print("Invalid choice")

    def _show_parameters(self) -> None:
        """Display all current parameters."""
        print("\nCurrent Parameters")
        print("=" * 40)

        if not self.ctx.parameters:
            print("Parameters not loaded.")
            input("\nPress Enter to continue...")
            return

        # Show key parameters
        params = self.ctx.parameters

        print("\n--- Location ---")
        print(f"HomeLat: {params.home_lat or 'Not set'}")
        print(f"HomeLon: {params.home_lon or 'Not set'}")
        print(f"LocalTZ: {params.local_tz or 'utc'}")

        print("\n--- Camera ---")
        print(f"CameraEnabled: {params.camera_enabled}")
        print(f"BatchSize: {params.batch_size}")
        print(f"SaveJpg: {params.camera_save_jpg}")
        print(f"SaveDng: {params.camera_save_dng}")
        print(f"SaveFits: {params.camera_save_fits}")

        print("\n--- Motors ---")
        print(f"AzimuthGearRatio: {params.azimuth_gear_ratio}")
        print(f"AltitudeGearRatio: {params.altitude_gear_ratio}")
        print(f"AzimuthRestAngle: {params.azimuth_rest_angle}")
        print(f"AltitudeRestAngle: {params.altitude_rest_angle}")
        print(f"MinAltitude: {params.min_altitude_angle}")
        print(f"MaxAltitude: {params.max_altitude_angle}")

        print("\n--- Direct GPIO Motors ---")
        print(f"DirectMotorEnabled: {params.direct_motor_enabled}")
        if params.direct_motor_enabled:
            print(f"AZ step={params.az_step_pin}/dir={params.az_dir_pin}")
            print(
                f"ALT step={params.alt_step_pin}/dir={params.alt_dir_pin}  home={params.alt_home_pin}"
            )

        print("\n--- Display ---")
        print(f"ColorScheme: {params.color_scheme}")
        print(f"DebugMode: {params.debug_mode}")

        input("\nPress Enter to continue...")

    def _change_location(self) -> None:
        """Change the observer location."""
        if not self.ctx.parameters:
            print("\nParameters not loaded.")
            return

        print(
            f"\nCurrent location: {self.ctx.parameters.home_lat}, {self.ctx.parameters.home_lon}"
        )

        if input("Change location? [y/N] ").lower() == "y":
            self._prompt_for_location()

            # Save immediately
            param_file = os.path.join(self.ctx.project_root, "data", "pilomar_params.json")
            self.ctx.parameters.save_attributes(param_file)
            print("Location saved.")

    def _set_color_scheme(self) -> None:
        """Set the terminal color scheme."""
        if not self.ctx.parameters:
            print("\nParameters not loaded.")
            return

        current = getattr(self.ctx.parameters, "ColorScheme", "green")
        print(f"\nCurrent color scheme: {current}")
        print("\nAvailable schemes:")
        print("1. white")
        print("2. blue")
        print("3. green")
        print("4. red")
        print("x. Cancel")

        schemes = ["white", "blue", "green", "red"]
        choice = input("Select scheme: ").strip()

        if choice == "x":
            return

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(schemes):
                if hasattr(self.ctx.parameters, "set_color_scheme"):
                    self.ctx.parameters.set_color_scheme(schemes[idx])
                else:
                    self.ctx.parameters.ColorScheme = schemes[idx]
                print(f"Color scheme set to: {schemes[idx]}")
            else:
                print("Invalid selection.")
        except ValueError:
            print("Invalid input.")

    def _toggle_debug(self) -> None:
        """Toggle debug mode."""
        if not self.ctx.parameters:
            print("\nParameters not loaded.")
            return

        current = getattr(self.ctx.parameters, "DebugMode", False)
        print(f"\nDebug mode is currently: {'ON' if current else 'OFF'}")

        if input("Toggle debug mode? [y/N] ").lower() == "y":
            self.ctx.parameters.DebugMode = not current
            print(f"Debug mode: {'ON' if not current else 'OFF'}")

    def _about(self) -> None:
        """Show about information."""
        print("\n" + "=" * 50)
        print("PILOMAR - Raspberry Pi Telescope Controller")
        print("=" * 50)
        print("\nAn open-source automated telescope control system")
        print("for astrophotography with Raspberry Pi.")
        print("\nFeatures:")
        print("  - Alt-Az mount control with stepper motors")
        print("  - Celestial object tracking")
        print("  - Automated photography sessions")
        print("  - Support for Messier, NGC, Hipparcos catalogs")
        print("  - Satellite tracking via CelesTrak")
        print("  - Comet and meteor shower observation")
        print("\nLicense: GNU General Public License v3.0")
        print("Repository: https://github.com/Short-bus/pilomar")
        print("=" * 50)
        input("\nPress Enter to continue...")

    # =========================================================================
    # OBSERVATION SCHEDULE MENU
    # =========================================================================

    def _schedule_menu(self) -> None:
        """Display observation schedule menu."""
        while True:
            print("\nObservation Schedule")
            print("=" * 40)
            print("1. Add target to schedule")
            print("2. View schedule")
            print("3. Run schedule")
            print("4. Clear schedule")
            print("5. Save schedule")
            print("6. Load schedule")
            print("b. Back to main menu")

            choice = input("Choice: ").lower().strip()

            if choice == "b":
                break
            elif choice == "1":
                self._add_to_schedule()
            elif choice == "2":
                self._view_schedule()
            elif choice == "3":
                self._run_schedule()
            elif choice == "4":
                self._clear_schedule()
            elif choice == "5":
                self._save_schedule()
            elif choice == "6":
                self._load_schedule()
            else:
                print("Invalid choice")

    def _add_to_schedule(self) -> None:
        """Add a target to the observation schedule."""
        # Initialize schedule if needed
        if not hasattr(self, "_schedule"):
            self._schedule = []

        print("\nAdd target to schedule")
        print("-" * 30)

        # Use target selection
        self._select_target_menu()

        if self.ctx.target:
            # Get observation parameters
            try:
                frames = input("Number of frames (default 100): ").strip()
                frames = int(frames) if frames else 100

                exposure = input("Exposure time in seconds (default from settings): ").strip()
                if exposure:
                    exposure = float(exposure)
                else:
                    exposure = (
                        getattr(self.ctx.parameters, "ExposureSeconds", 1.0)
                        if self.ctx.parameters
                        else 1.0
                    )

                # Add to schedule
                entry = {
                    "target": (
                        dict(self.ctx.target)
                        if isinstance(self.ctx.target, dict)
                        else {"name": str(self.ctx.target)}
                    ),
                    "frames": frames,
                    "exposure": exposure,
                }
                self._schedule.append(entry)

                target_name = entry["target"].get("name", "Unknown")
                print(f"Added: {target_name} ({frames} frames @ {exposure}s)")

            except ValueError:
                print("Invalid input.")

    def _view_schedule(self) -> None:
        """View the current observation schedule."""
        if not hasattr(self, "_schedule") or not self._schedule:
            print("\nSchedule is empty.")
            input("Press Enter to continue...")
            return

        print("\nObservation Schedule")
        print("=" * 60)
        print(f"{'#':<3} {'Target':<25} {'Frames':<8} {'Exposure':<10}")
        print("-" * 60)

        for i, entry in enumerate(self._schedule, 1):
            target_name = entry["target"].get("name", "Unknown")[:24]
            frames = entry.get("frames", 100)
            exposure = entry.get("exposure", 1.0)
            print(f"{i:<3} {target_name:<25} {frames:<8} {exposure:<10.1f}s")

        print("=" * 60)
        print(f"Total targets: {len(self._schedule)}")
        input("\nPress Enter to continue...")

    def _run_schedule(self) -> None:
        """Execute the observation schedule."""
        if not hasattr(self, "_schedule") or not self._schedule:
            print("\nSchedule is empty. Add targets first.")
            return

        print(f"\nRunning observation schedule ({len(self._schedule)} targets)")
        print("Press Ctrl+C to abort.\n")

        if input("Start schedule? [y/N] ").lower() != "y":
            return

        try:
            for i, entry in enumerate(self._schedule, 1):
                target_name = entry["target"].get("name", "Unknown")
                frames = entry.get("frames", 100)
                exposure = entry.get("exposure", 1.0)

                print(f"\n[{i}/{len(self._schedule)}] Target: {target_name}")
                print(f"  Frames: {frames}, Exposure: {exposure}s")

                # Set target
                self.ctx.target = entry["target"]

                # Set exposure
                if self.ctx.camera:
                    self.ctx.camera.ExposureSeconds = exposure
                if self.ctx.parameters:
                    self.ctx.parameters.BatchSize = frames

                # Run observation
                obs_ctx = self._build_observation_context()
                result = start_observation(obs_ctx, batch_mode=True)

                print(f"  Completed: {result.photo_count} photos")

                if not result.success:
                    print(f"  Warning: {result.status_codes}")
                    if input("Continue with next target? [Y/n] ").lower() == "n":
                        break

            print("\nSchedule complete!")

        except KeyboardInterrupt:
            print("\n\nSchedule aborted by user.")

        input("Press Enter to continue...")

    def _clear_schedule(self) -> None:
        """Clear the observation schedule."""
        if not hasattr(self, "_schedule") or not self._schedule:
            print("\nSchedule is already empty.")
            return

        if input(f"Clear {len(self._schedule)} scheduled targets? [y/N] ").lower() == "y":
            self._schedule = []
            print("Schedule cleared.")

    def _save_schedule(self) -> None:
        """Save the schedule to a JSON file."""
        import json

        if not hasattr(self, "_schedule") or not self._schedule:
            print("\nSchedule is empty. Nothing to save.")
            return

        default_path = os.path.join(self.ctx.project_root, "data", "schedule.json")
        path = input(f"Save to [{default_path}]: ").strip()
        if not path:
            path = default_path

        try:
            with open(path, "w") as f:
                json.dump(self._schedule, f, indent=2, default=str)
            print(f"Schedule saved to: {path}")
        except Exception as e:
            print(f"Error saving schedule: {e}")

    def _load_schedule(self) -> None:
        """Load a schedule from a JSON file."""

        default_path = os.path.join(self.ctx.project_root, "data", "schedule.json")
        path = input(f"Load from [{default_path}]: ").strip()
        if not path:
            path = default_path

        if not os.path.exists(path):
            print(f"File not found: {path}")
            return

        try:
            with open(path, encoding="utf-8") as f:
                loaded = json.load(f)

            if not isinstance(loaded, list):
                print("Invalid schedule format.")
                return

            self._schedule = loaded
            print(f"Loaded {len(self._schedule)} targets from: {path}")

        except Exception as e:
            print(f"Error loading schedule: {e}")

    def shutdown(self) -> None:
        """Perform graceful shutdown.

        This ensures all resources are properly released:
        - Stop camera thread
        - Stop motor threads
        - Home motors (if requested)
        - Save parameters
        - Clean up GPIO
        """
        self._log("Shutting down...")
        self._running = False

        # Flag observation end
        # FlagObservationEnd()

        # Offer to home camera
        self._offer_home_camera()

        # Stop camera
        self._shutdown_camera()

        # Stop microcontroller
        self._shutdown_microcontroller()

        # Stop message handler
        self._shutdown_message_handler()

        # Save parameters
        self._save_parameters()

        # Cleanup GPIO
        self._cleanup_gpio()

        self._log("Shutdown complete")

    def _offer_home_camera(self) -> None:
        """Offer to return camera to home position if not already home."""
        if not self.ctx.motor_controls:
            return  # No motors to home

        # Check if parameters allow movement (RequireRestart blocks moves)
        if self.ctx.parameters and getattr(self.ctx.parameters, "RequireRestart", False):
            self._log("Parameter changes require restart - cannot home motors")
            return

        # Get current and home positions for each motor
        motors_need_homing = []
        for motor in self.ctx.motor_controls:
            name = getattr(motor, "MotorName", getattr(motor, "motor_name", "unknown"))
            current = getattr(motor, "CurrentAngle", None)
            rest = getattr(motor, "RestAngle", None)

            if current is not None and rest is not None:
                # Check if position differs by more than 0.1 degree
                if abs(current - rest) > 0.1:
                    motors_need_homing.append((name, current, rest))

        if not motors_need_homing:
            print("Motors are already in home position. No homing needed.")
            return

        # Show current positions
        print("\nMotor positions:")
        for name, current, rest in motors_need_homing:
            print(f"  {name}: {current:.1f}° (home: {rest:.1f}°)")

        # Ask user if they want to home
        try:
            response = (
                input("Would you like to home the camera before powering off? [y/N] ")
                .lower()
                .strip()
            )
            if response not in ("y", "yes"):
                print("Camera will resume from its current position when restarted.")
                print("To home the camera now, use the 'Home motors' option on the menu.")
                return
        except (EOFError, KeyboardInterrupt):
            return

        # Perform homing
        print("Returning camera to home position...")
        success = True
        for motor in self.ctx.motor_controls:
            name = getattr(motor, "MotorName", getattr(motor, "motor_name", "unknown"))
            rest = getattr(motor, "RestAngle", None)

            if rest is not None and hasattr(motor, "GoToAngle"):
                self._log(f"Homing {name} motor to {rest}°", terminal=False)
                motor.MonitorMove = True
                result = motor.GoToAngle(rest)
                motor.MonitorMove = False

                if not result:
                    self._log(f"Failed to home {name} motor", level="warning")
                    success = False

        # Store final position
        for motor in self.ctx.motor_controls:
            if hasattr(motor, "StoreRecoveryAngle"):
                motor.StoreRecoveryAngle(force=True)

        if success:
            print("Camera homed successfully.")
        else:
            print("Some motors did not home successfully. Check positions on restart.")

    def _shutdown_camera(self) -> None:
        """Shutdown camera thread gracefully."""
        if self.ctx.camera_thread and self.ctx.camera_thread.is_alive():
            self._log("Stopping camera thread...")
            # Send shutdown signal and wait
            if self.ctx.camera_control_queue:
                self.ctx.camera_control_queue.put({"Shutdown": True})
            self.ctx.camera_thread.join(timeout=10)

    def _shutdown_microcontroller(self) -> None:
        """Shutdown microcontroller communication."""
        if self.ctx.mctl:
            self._log("Stopping microcontroller...")
            if hasattr(self.ctx.mctl, "Reset"):
                self.ctx.mctl.Reset(planned=True)

        if self.ctx.uart_control_queue:
            self.ctx.uart_control_queue.put("stop")

        if self.ctx.mctl_thread and self.ctx.mctl_thread.is_alive():
            self.ctx.mctl_thread.join(timeout=10)

    def _shutdown_message_handler(self) -> None:
        """Shutdown message handler thread."""
        if self.ctx.message_thread and self.ctx.message_thread.is_alive():
            self._log("Stopping message handler...")
            self.ctx.message_thread.join(timeout=10)

    def _save_parameters(self) -> None:
        """Save current parameters to disk."""
        if self.ctx.parameters:
            self._log("Saving parameters...")
            if hasattr(self.ctx.parameters, "SaveAttributes"):
                self.ctx.parameters.SaveAttributes(
                    getattr(self.ctx.parameters, "ParamFileName", "parameters.json")
                )

    def _cleanup_gpio(self) -> None:
        """Clean up GPIO state by releasing all pins."""
        self._log("Cleaning up GPIO...", terminal=False)

        # Stop direct GPIO driver first (stops waveform thread and pigpio)
        if self.ctx.direct_driver is not None:
            try:
                if self.ctx.direct_tracker is not None:
                    self.ctx.direct_tracker.stop()
                self.ctx.direct_driver.stop()
                self.ctx.direct_driver.pi.stop()
                self._log("Direct GPIO driver stopped", terminal=False)
            except Exception as exc:  # pylint: disable=broad-except
                self._log(
                    f"Direct driver cleanup error: {exc}",
                    level="warning",
                    terminal=False,
                )

        # Turn off microcontroller power if available
        if self.ctx.mctl and hasattr(self.ctx.mctl, "ResetPin"):
            reset_pin = self.ctx.mctl.ResetPin
            if hasattr(reset_pin, "Off"):
                reset_pin.Off()
                self._log("Microcontroller power disabled", terminal=False)

        # Try hardware GPIO module cleanup
        try:
            from pilomar.hardware.gpio import InputPinGpiod, OutputPinGpiod

            # Release all gpiod pins
            for pin in getattr(InputPinGpiod, "InputPins", []):
                if hasattr(pin, "Line") and hasattr(pin.Line, "release"):
                    pin.Line.release()

            for pin in getattr(OutputPinGpiod, "OutputPins", []):
                if hasattr(pin, "Line") and hasattr(pin.Line, "release"):
                    pin.Line.release()

            self._log("GPIO pins released", terminal=False)

        except ImportError:
            # gpiod not available - try RPi.GPIO fallback
            try:
                import RPi.GPIO as GPIO

                GPIO.cleanup()
                self._log("RPi.GPIO cleaned up", terminal=False)
            except ImportError:
                pass  # No GPIO available
            except Exception as e:
                self._log(f"RPi.GPIO cleanup error: {e}", level="warning", terminal=False)

        except Exception as e:
            self._log(f"GPIO cleanup error: {e}", level="warning", terminal=False)


def find_project_root() -> str:
    """Find the Pilomar project root directory.

    Searches up from current directory looking for markers like
    'pilomar.py', 'data/' directory, etc.

    Returns:
        Path to project root, or current directory if not found
    """
    # Check environment variable first
    if "PILOMAR_ROOT" in os.environ:
        return os.environ["PILOMAR_ROOT"]

    # Look for markers in current directory and parents
    markers = ["data", "pilomar", "parameters.json"]
    current = os.getcwd()

    for _ in range(5):  # Don't search too far up
        for marker in markers:
            if os.path.exists(os.path.join(current, marker)):
                return current
        parent = os.path.dirname(current)
        if parent == current:  # Reached root
            break
        current = parent

    return os.getcwd()


def main(args: list[str] | None = None) -> int:
    """Main entry point for Pilomar.

    Args:
        args: Command line arguments (uses sys.argv if None)

    Returns:
        Exit code
    """
    if args is None:
        args = sys.argv[1:]

    # Parse any command line arguments
    project_root = find_project_root()
    web_mode = False
    web_port = 8080

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--root", "-r") and i + 1 < len(args):
            project_root = args[i + 1]
            i += 2
        elif arg in ("--web", "web"):
            web_mode = True
            i += 1
        elif arg.startswith("--port=") or arg.startswith("port="):
            try:
                web_port = int(arg.split("=")[1])
            except ValueError:
                pass
            i += 1
        elif arg in ("--help", "-h"):
            print("Pilomar - Astronomical observation control")
            print()
            print("Usage: pilomar/app/main.py [options]")
            print()
            print("Options:")
            print("  -r, --root DIR    Set project root directory")
            print("  --web             Start web UI (FastAPI + HTMX)")
            print("  --port=PORT       Web UI port (default 8080)")
            print("  -h, --help        Show this help message")
            return 0
        else:
            i += 1

    app = Application(project_root)

    if web_mode:
        try:
            from pilomar.web.server import create_app, run as web_run
        except ImportError as exc:
            print(f"Web modules not available: {exc}")
            print("Install with: pip install fastapi uvicorn jinja2")
            return 1

        if not app.initialize():
            return 1

        fastapi_app = create_app(app)
        print(f"Starting web UI at http://0.0.0.0:{web_port}/")
        print("Press Ctrl+C to stop.")
        try:
            web_run(fastapi_app, host="0.0.0.0", port=web_port)
        except KeyboardInterrupt:
            pass
        finally:
            app.shutdown()
        return 0

    return app.run()


# Entry point
if __name__ == "__main__":
    sys.exit(main())
