#!/usr/bin/env python3
"""Session status tracking for Pilomar telescope control.

This module provides the SessionStatus class for tracking the current
state of an observation session.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Union
from pilomar.core.base import AttributeMaster

if TYPE_CHECKING:
    from pilomar.core.logger import LogFile
    from pilomar.targets.target import Target


class SessionStatus(AttributeMaster):
    """Class to hold current status of the observation.

    Can export status information to a file for remote monitoring.
    These variables handle a single loop in the ObservationRun routine.
    """

    # Motor control mode definitions
    MCM_DICT = {
        "idle": {"description": "motors at rest.", "trajectory": False},
        "direct": {
            "description": "motor movement controlled directly from this software.",
            "trajectory": False,
        },
        "trajectory": {
            "description": "motor movement is autonomous following trajectory.",
            "trajectory": True,
        },
    }

    def __init__(self, logger=None, now_func=None):
        """Initialize session status.

        Args:
            logger: Optional logger instance.
            now_func: Function returning current UTC datetime.
        """
        super().__init__(now_func=now_func)
        self.set_logger(logger)
        self._file_names = []
        # self._init_status()

        self.program_start_time = self._now_func()
        self.target: Target = None  # No target yet

        # FITS/EXIF tag files
        self.tech_fits_tags_file = None
        self.weather_fits_tags_file = None
        self.tech_exif_tags_file = None
        self.weather_exif_tags_file = None

        # Debug and control modes
        self.debug_mode = False
        self.autonomous_control = False
        self.remote_control = False
        self.clock_synchronised = False
        self._observation_running = False
        self._observation_timestamp: Union[None, datetime] = None

        # Communication statistics
        self.mctl_rx_errors = 0
        self.mctl_rx_bytes = 0
        self.mctl_tx_bytes = 0
        self.mctl_exception_count = 0
        self.trajectory_safety_flushes = 0
        self.camera_tx_count = 0
        self.camera_rx_count = 0
        self.mctl_life_seconds = 0
        self.mctl_write_drops = 0

        # Motor control
        self.motor_control_mode = "idle"
        self.maintain_trajectory = False
        self.mctl_pin_dict = {}

        # Controller info
        self.terminate_mctl_handler = False
        self.controller_version = "unknown"
        self.time_diff = None

    def reset(self):
        """Reset status to initial state."""
        self.autonomous_control = False
        self.remote_control = False
        self.clock_synchronised = False
        self.mctl_rx_errors = 0
        self.mctl_rx_bytes = 0
        self.mctl_tx_bytes = 0
        self.mctl_exception_count = 0
        self.mctl_life_seconds = 0
        self.mctl_write_drops = 0
        self.motor_control_mode = "idle"
        self.set_motor_control_mode(self.motor_control_mode)

    def set_motor_control_mode(self, mode):
        """Change the control mode of the motors.

        Supported modes are: idle, direct, trajectory.

        Args:
            mode: The control mode string.
        """
        previous_trajectory = self.maintain_trajectory

        if mode in self.MCM_DICT:
            self.log(
                f"SessionStatus.set_motor_control_mode({mode}) from {self.motor_control_mode} to {mode}",
                terminal=False,
            )
            self.log(
                f'SessionStatus.set_motor_control_mode({mode}) {self.MCM_DICT[mode]["description"]}',
                terminal=False,
            )
            self.motor_control_mode = mode
            self.maintain_trajectory = self.MCM_DICT[mode]["trajectory"]
        else:
            self.log(
                f"SessionStatus.set_motor_control_mode({mode}) is not recognised. Setting to idle.",
                level="error",
            )
            self.motor_control_mode = "idle"
            self.maintain_trajectory = self.MCM_DICT["idle"]["trajectory"]

        # If we've stopped maintaining trajectory, clear existing entries
        if previous_trajectory and not self.maintain_trajectory:
            self.log(
                f"SessionStatus.set_motor_control_mode({mode}) clearing trajectory from motors.",
                terminal=False,
            )
            # Note: External code should handle sending 'clear trajectory' command

    def set_observation_running(self, running):
        """Set the observation running state.

        Args:
            running: True if observation is running.
        """
        self._observation_running = running
        self._observation_timestamp = self._now_func() if running else None

    def observation_running(self):
        """Check if observation is currently running.

        Returns:
            True if observation is active.
        """
        return self._observation_running

    def check_cpu_status(self, line: str):
        """Process CPU status message from microcontroller.

        Message format:
        cpu status TIMESTAMP RESET_REASON CLOCKSPEED VOLTAGE MEM_ALLOC MEM_FREE TEMP [FEATURES]

        Args:
            line: The CPU status message line.

        Returns:
            Dict with parsed values.
        """
        items = line.split(" ")

        result = {
            "reset_reason": items[3] if len(items) > 3 else "UNKNOWN",
            "clockspeed": float(items[4]) * 1e6 if len(items) > 4 else 0.0,
            "voltage": float(items[5]) if len(items) > 5 else 0.0,
            "mem_alloc": int(items[6]) if len(items) > 6 else 0,
            "mem_free": int(items[7]) if len(items) > 7 else 0,
            "temperature": float(items[8]) if len(items) > 8 else 0.0,
            "features": items[9].split("_") if len(items) > 9 else [],
        }

        return result

    def check_session_status(self, line):
        """Process session status message from microcontroller.

        Message format:
        session status TIMESTAMP AUTONOMOUS REMOTE CLOCK_SYNC ... VERSION

        Args:
            line: The session status message line.

        Returns:
            Dict with parsed values.
        """
        items = line.split(" ")

        result = {
            "timestamp": items[2] if len(items) > 2 else None,
            "autonomous": items[3] == "y" if len(items) > 3 else False,
            "remote": items[4] == "y" if len(items) > 4 else False,
            "clock_sync": items[5] == "y" if len(items) > 5 else False,
        }

        # Update our tracking
        self.autonomous_control = result["autonomous"]
        self.remote_control = result["remote"]
        self.clock_synchronised = result["clock_sync"]

        return result

    def get_status_dict(self):
        """Get current status as dictionary.

        Returns:
            Dict with current status values.
        """
        return {
            "program_start": (
                self.program_start_time.isoformat() if self.program_start_time else None
            ),
            "target": str(self.target) if self.target else None,
            "observation_running": self._observation_running,
            "debug_mode": self.debug_mode,
            "autonomous_control": self.autonomous_control,
            "remote_control": self.remote_control,
            "clock_synchronised": self.clock_synchronised,
            "motor_control_mode": self.motor_control_mode,
            "maintain_trajectory": self.maintain_trajectory,
            "controller_version": self.controller_version,
            "mctl_rx_errors": self.mctl_rx_errors,
            "mctl_rx_bytes": self.mctl_rx_bytes,
            "mctl_tx_bytes": self.mctl_tx_bytes,
            "mctl_life_seconds": self.mctl_life_seconds,
        }
