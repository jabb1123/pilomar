#!/usr/bin/env python3
"""Motor control for Pilomar telescope.

This module provides the MotorControl class for managing stepper motor
movements for telescope altitude/azimuth positioning.
"""

import os

from pilomar.core.base import AttributeMaster


class MotorControl(AttributeMaster):
    """Representation of a remote motor controlled via microcontroller.

    The actual motor is controlled in the microcontroller software,
    this class contains an image of important parameters for
    the motor so that this program can direct it.
    """

    # Class-level list of all motor instances
    all_motors = []

    def __init__(
        self,
        name,
        gear_ratio,
        full_steps_per_rev,
        microstep_ratio,
        min_angle,
        max_angle,
        rest_angle,
        current_angle,
        backlash_angle,
        orientation=1,
        limit_angle=None,
        horizon=None,
        fast_time=0.001,
        slow_time=0.05,
        time_delta=0.003,
        driver="drv8825",
        slew_microsteps=1,
        optimise_moves=False,
        stepper_driver_data=None,
        project_root=None,
        now_func=None,
        logger=None,
    ):
        """Create an instance of a stepper motor control.

        Args:
            name: Unique name for the motor (must match microcontroller).
            gear_ratio: Gear reduction ratio.
            full_steps_per_rev: Motor steps per revolution (ignoring microstepping).
            microstep_ratio: Microstepping multiplier (1, 2, 4, 8, 16, 32).
            min_angle: Minimum allowed angle.
            max_angle: Maximum allowed angle.
            rest_angle: Home/rest position angle.
            current_angle: Current angle position.
            backlash_angle: Backlash compensation angle.
            orientation: Direction multiplier (+1 or -1).
            limit_angle: Optional rotation limit angle.
            horizon: Minimum observation altitude angle.
            fast_time: Fastest step pulse time (seconds).
            slow_time: Slowest step pulse time (seconds).
            time_delta: Acceleration rate for step timing.
            driver: Stepper driver type (e.g., 'drv8825').
            slew_microsteps: Microstepping for fast slew moves.
            optimise_moves: Allow crossing 0/360 boundary.
            stepper_driver_data: Dict of driver configurations.
            project_root: Project root directory path.
            now_func: Function returning current UTC datetime.
            logger: Optional logger instance.
        """
        super().__init__(now_func=now_func)
        self.set_logger(logger)

        # Motor identification
        self.motor_name = name
        self.driver = driver

        # Movement tracking
        self.tune_command_count = 0
        self.open_tune_commands = []
        self.optimise_moves = optimise_moves

        # Gearing configuration
        self.gear_ratio = gear_ratio
        motor_steps_per_rev = full_steps_per_rev * microstep_ratio
        self.motor_steps_per_rev = motor_steps_per_rev
        self.microstep_ratio = microstep_ratio

        # Slew configuration
        self.slew_microsteps = min(slew_microsteps, microstep_ratio)
        self.slew_step_multiplier = int(
            round(microstep_ratio / self.slew_microsteps, 0)
        )

        self.log(
            f"MotorControl({name}) microstepping={self.microstep_ratio} "
            f"(observation), slew={self.slew_microsteps} (goto), "
            f"multiplier={self.slew_step_multiplier}",
            terminal=False,
        )

        # Mode signals for driver board
        self.mode_signals = "nnn"  # Default full-step
        self.slew_signals = "nnn"  # Default full-step

        if stepper_driver_data and driver in stepper_driver_data:
            modelist = stepper_driver_data[driver]["modelist"]
            if str(microstep_ratio) in modelist:
                self.mode_signals = modelist[str(microstep_ratio)]["modesignals"]
            if str(self.slew_microsteps) in modelist:
                self.slew_signals = modelist[str(self.slew_microsteps)]["modesignals"]

        # Angle limits
        self.warning_angle = 10
        self.horizon = horizon
        self.min_angle = min_angle
        self.min_observation_angle = min_angle
        if horizon is not None:
            self.min_observation_angle = max(min_angle, horizon)
        self.min_warning_angle = self.min_observation_angle + self.warning_angle
        self.max_angle = max_angle
        self.max_warning_angle = max_angle - self.warning_angle
        self.limit_angle = limit_angle

        # Motor state
        self.orientation = orientation
        self.backlash_angle = backlash_angle
        self.current_angle = current_angle
        self.previous_angle = None
        self.previous_mctl_timestamp = None
        self.rest_angle = rest_angle

        # Calculated values
        self.motor_steps_per_axis_degree = self.motor_steps_per_rev / 360.0
        self.axis_steps_per_rev = self.motor_steps_per_rev * gear_ratio

        # Configuration state
        self.motor_configured = False
        self.fast_time = fast_time
        self.slow_time = slow_time
        self.time_delta = time_delta

        # Trajectory state
        self.trajectory_segment_size = 60
        self.trajectory_valid = False
        self.trajectory_entries = 0
        self.trajectory_valid_until = None
        self.last_sent_trajectory_key = None
        self.last_sent_trajectory_data = None

        # Movement state
        self.on_target = False
        self.latest_tune_start = None
        self.latest_tune_time = None
        self.latest_tune_steps = 0

        # Recovery file handling
        self._project_root = project_root or "/home/pi/pilomar"
        self.recovery_folder = f"{self._project_root}/data/{self.motor_name}_angle"
        self._ensure_recovery_folder()
        self.recovery_file_name = (
            f"{self.recovery_folder}/{self._timestamp_string()}.log"
        )

        # Try to restore previous position
        self.restore_angle()
        self.last_recovery_angle = self.current_angle

        self.log(
            f"Motor {self.motor_name} recovered to {round(self.current_angle, 5)}°",
            terminal=False,
        )

        # Register this motor
        MotorControl.all_motors.append(self)

        # Status tracking
        self.status_mctl_timestamp = None
        self.status_local_timestamp = None
        self.axis_speed = 0.0
        self.monitor_move = False

        # Initialize as not configured
        self.restarted()

    def __del__(self):
        """Remove this motor from global list when deleted."""
        if self in MotorControl.all_motors:
            MotorControl.all_motors.remove(self)

    def _timestamp_string(self):
        """Return timestamp string for file naming."""
        return self._now_func().strftime("%Y%m%d%H%M%S")

    def _ensure_recovery_folder(self):
        """Create recovery folder if it doesn't exist."""
        if not os.path.exists(self.recovery_folder):
            os.makedirs(self.recovery_folder, exist_ok=True)

    def restarted(self):
        """Reset status flags for a fresh/unconfigured motor."""
        self.motor_configured = False
        self.trajectory_valid = False
        self.trajectory_entries = 0
        self.trajectory_valid_until = None
        self.on_target = False

    def angle_to_step(self, angle):
        """Convert an angle to motor step count.

        Args:
            angle: The angle in degrees.

        Returns:
            The step count.
        """
        step = int(round(angle * self.axis_steps_per_rev / 360.0, 0))
        return step

    def step_to_angle(self, step):
        """Convert motor step count to angle.

        Args:
            step: The step count.

        Returns:
            The angle in degrees.
        """
        angle = float(step) * 360.0 / self.axis_steps_per_rev
        return angle

    def restore_angle(self):
        """Restore angle from most recent recovery file."""
        try:
            files = sorted(os.listdir(self.recovery_folder))
            if files:
                latest_file = os.path.join(self.recovery_folder, files[-1])
                with open(latest_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    if lines:
                        # Last line contains the angle
                        last_line = lines[-1].strip()
                        if last_line:
                            parts = last_line.split()
                            if len(parts) >= 2:
                                self.current_angle = float(parts[1])
                                self.log(
                                    f"MotorControl.restore_angle({self.motor_name}):"
                                    f" {self.current_angle}",
                                    terminal=False,
                                )
        except Exception as e:  # pylint: disable=broad-except
            self.log(
                f"MotorControl.restore_angle({self.motor_name}) failed: {str(e)}",
                terminal=False,
            )

    def store_recovery_angle(self, force=False):
        """Store current angle to recovery file.

        Args:
            force: If True, write even if angle hasn't changed.
        """
        if not force and self.current_angle == self.last_recovery_angle:
            return  # No change

        try:
            timestamp = self._timestamp_string()
            with open(self.recovery_file_name, "a", encoding="utf-8") as f:
                f.write(f"{timestamp} {self.current_angle}\n")
            self.last_recovery_angle = self.current_angle
        except Exception as e:  # pylint: disable=broad-except
            self.log(
                f"MotorControl.store_recovery_angle({self.motor_name}) failed: {str(e)}",
                level="error",
            )

    def receive_status(self, line):
        """Process status message from microcontroller.

        Message format:
        motor status TIMESTAMP NAME CONFIGURED MCTL_TIMESTAMP STEPS ACTUAL_STEPS ANGLE ON_TARGET

        Args:
            line: The motor status message line.
        """
        items = line.split(" ")

        if len(items) < 9:
            self.log(
                "MotorControl.receive_status: Invalid message:", line, level="error"
            )
            return

        motor_name = items[3]
        if motor_name != self.motor_name:
            return

        configured = items[4] == "y"
        mctl_timestamp = items[5]
        _steps = int(items[6])
        _actual_steps = int(items[7])
        angle = float(items[8])
        on_target = items[9] == "y" if len(items) > 9 else False

        # Update state
        self.previous_angle = self.current_angle
        self.previous_mctl_timestamp = self.status_mctl_timestamp

        self.motor_configured = configured
        self.status_mctl_timestamp = mctl_timestamp
        self.status_local_timestamp = self._now_func()
        self.current_angle = angle
        self.on_target = on_target

        # Calculate speed if we have previous data
        if self.previous_angle is not None and self.previous_mctl_timestamp is not None:
            try:
                # Parse timestamps and calculate delta
                # This is simplified - actual implementation would parse timestamps
                self.axis_speed = 0.0  # Placeholder
            except Exception:  # pylint: disable=broad-except
                self.axis_speed = 0.0

    def show_motor_status(self):
        """Print general status of the motor."""
        print(f"Motor: {self.motor_name}")
        print(f"- RecoveryFileName: {self.recovery_file_name}")
        print(f"- Driver: {self.driver}")
        print("Current status:")
        print(f"- MotorConfigured: {self.motor_configured}")
        print(f"- CurrentAngle: {self.current_angle:.3f}°")
        print(f"- Position: {self.angle_to_step(self.current_angle)} steps")
        print(f"- AxisSpeed: {self.axis_speed}°/s")
        print("Gearing:")
        print(f"- GearRatio: {self.gear_ratio}")
        print(f"- MotorStepsPerRev: {self.motor_steps_per_rev}")
        print(f"- MicrostepRatio: {self.microstep_ratio}")
        print("Configuration:")
        print(f"- MinAngle: {self.min_angle:.3f}°")
        print(f"- MaxAngle: {self.max_angle:.3f}°")
        print(f"- RestAngle: {self.rest_angle:.3f}°")
        print(f"- Orientation: {self.orientation}")
