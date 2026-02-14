#!/usr/bin/env python3
"""Motor control for Pilomar telescope.

This module provides the MotorControl class for managing stepper motor
movements for telescope altitude/azimuth positioning.
"""

import os
from datetime import datetime

from pilomar.core.base import AttributeMaster


class MotorControl(AttributeMaster):
    """Representation of a remote motor controlled via microcontroller.
    
    The actual motor is controlled in the microcontroller software,
    this class contains an image of important parameters for
    the motor so that this program can direct it.
    """
    
    # Class-level list of all motor instances
    AllMotors = []

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
        driver='drv8825',
        slew_microsteps=1,
        optimise_moves=False,
        stepper_driver_data=None,
        project_root=None,
        now_func=None,
        logger=None
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
        self.set_logger(logger)
        self._now_func = now_func or (lambda: datetime.utcnow())
        
        # Motor identification
        self.MotorName = name
        self.Driver = driver
        
        # Movement tracking
        self.TuneCommandCount = 0
        self.OpenTuneCommands = []
        self.OptimiseMoves = optimise_moves
        
        # Gearing configuration
        self.GearRatio = gear_ratio
        motor_steps_per_rev = full_steps_per_rev * microstep_ratio
        self.MotorStepsPerRev = motor_steps_per_rev
        self.MicrostepRatio = microstep_ratio
        
        # Slew configuration
        self.SlewMicrosteps = min(slew_microsteps, microstep_ratio)
        self.SlewStepMultiplier = int(round(microstep_ratio / self.SlewMicrosteps, 0))
        
        self.Log("MotorControl(", name, ") microstepping=", self.MicrostepRatio,
                "(observation), slew=", self.SlewMicrosteps, "(goto), multiplier=",
                self.SlewStepMultiplier, terminal=False)
        
        # Mode signals for driver board
        self.ModeSignals = 'nnn'  # Default full-step
        self.SlewSignals = 'nnn'  # Default full-step
        
        if stepper_driver_data and driver in stepper_driver_data:
            modelist = stepper_driver_data[driver]['modelist']
            if str(microstep_ratio) in modelist:
                self.ModeSignals = modelist[str(microstep_ratio)]['modesignals']
            if str(self.SlewMicrosteps) in modelist:
                self.SlewSignals = modelist[str(self.SlewMicrosteps)]['modesignals']
        
        # Angle limits
        self.WarningAngle = 10
        self.Horizon = horizon
        self.MinAngle = min_angle
        self.MinObservationAngle = min_angle
        if horizon is not None:
            self.MinObservationAngle = max(min_angle, horizon)
        self.MinWarningAngle = self.MinObservationAngle + self.WarningAngle
        self.MaxAngle = max_angle
        self.MaxWarningAngle = max_angle - self.WarningAngle
        self.LimitAngle = limit_angle
        
        # Motor state
        self.Orientation = orientation
        self.BacklashAngle = backlash_angle
        self.CurrentAngle = current_angle
        self.PreviousAngle = None
        self.PreviousMctlTimestamp = None
        self.RestAngle = rest_angle
        
        # Calculated values
        self.MotorStepsPerAxisDegree = self.MotorStepsPerRev / 360.0
        self.AxisStepsPerRev = self.MotorStepsPerRev * gear_ratio
        
        # Configuration state
        self.MotorConfigured = False
        self.FastTime = fast_time
        self.SlowTime = slow_time
        self.TimeDelta = time_delta
        
        # Trajectory state
        self.TrajectorySegmentSize = 60
        self.TrajectoryValid = False
        self.TrajectoryEntries = 0
        self.TrajectoryValidUntil = None
        self.LastSentTrajectoryKey = None
        self.LastSentTrajectoryData = None
        
        # Movement state
        self.OnTarget = False
        self.LatestTuneStart = None
        self.LatestTuneTime = None
        self.LatestTuneSteps = 0
        
        # Recovery file handling
        self._project_root = project_root or '/home/pi/pilomar'
        self.RecoveryFolder = f"{self._project_root}/data/{self.MotorName}_angle"
        self._ensure_recovery_folder()
        self.RecoveryFileName = f"{self.RecoveryFolder}/{self._timestamp_string()}.log"
        
        # Try to restore previous position
        self.restore_angle()
        self.LastRecoveryAngle = self.CurrentAngle
        
        self.Log('Motor', self.MotorName, 'recovered to',
                round(self.CurrentAngle, 5), '°', terminal=False)
        
        # Register this motor
        MotorControl.AllMotors.append(self)
        
        # Status tracking
        self.StatusMctlTimestamp = None
        self.StatusLocalTimestamp = None
        self.AxisSpeed = 0.0
        self.MonitorMove = False
        
        # Initialize as not configured
        self.restarted()

    def __del__(self):
        """Remove this motor from global list when deleted."""
        if self in MotorControl.AllMotors:
            MotorControl.AllMotors.remove(self)

    def _timestamp_string(self):
        """Return timestamp string for file naming."""
        return self._now_func().strftime('%Y%m%d%H%M%S')

    def _ensure_recovery_folder(self):
        """Create recovery folder if it doesn't exist."""
        if not os.path.exists(self.RecoveryFolder):
            os.makedirs(self.RecoveryFolder, exist_ok=True)

    def restarted(self):
        """Reset status flags for a fresh/unconfigured motor."""
        self.MotorConfigured = False
        self.TrajectoryValid = False
        self.TrajectoryEntries = 0
        self.TrajectoryValidUntil = None
        self.OnTarget = False

    def angle_to_step(self, angle):
        """Convert an angle to motor step count.
        
        Args:
            angle: The angle in degrees.
            
        Returns:
            The step count.
        """
        step = int(round(angle * self.AxisStepsPerRev / 360.0, 0))
        return step

    def step_to_angle(self, step):
        """Convert motor step count to angle.
        
        Args:
            step: The step count.
            
        Returns:
            The angle in degrees.
        """
        angle = float(step) * 360.0 / self.AxisStepsPerRev
        return angle

    def restore_angle(self):
        """Restore angle from most recent recovery file."""
        try:
            files = sorted(os.listdir(self.RecoveryFolder))
            if files:
                latest_file = os.path.join(self.RecoveryFolder, files[-1])
                with open(latest_file, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        # Last line contains the angle
                        last_line = lines[-1].strip()
                        if last_line:
                            parts = last_line.split()
                            if len(parts) >= 2:
                                self.CurrentAngle = float(parts[1])
                                self.Log("MotorControl.restore_angle(",
                                        self.MotorName, "):", self.CurrentAngle,
                                        terminal=False)
        except Exception as e:
            self.Log("MotorControl.restore_angle(", self.MotorName,
                    ") failed:", str(e), terminal=False)

    def store_recovery_angle(self, force=False):
        """Store current angle to recovery file.
        
        Args:
            force: If True, write even if angle hasn't changed.
        """
        if not force and self.CurrentAngle == self.LastRecoveryAngle:
            return  # No change
        
        try:
            timestamp = self._timestamp_string()
            with open(self.RecoveryFileName, 'a') as f:
                f.write(f"{timestamp} {self.CurrentAngle}\n")
            self.LastRecoveryAngle = self.CurrentAngle
        except Exception as e:
            self.Log("MotorControl.store_recovery_angle(", self.MotorName,
                    ") failed:", str(e), level='error')

    def receive_status(self, line):
        """Process status message from microcontroller.
        
        Message format:
        motor status TIMESTAMP NAME CONFIGURED MCTL_TIMESTAMP STEPS ACTUAL_STEPS ANGLE ON_TARGET
        
        Args:
            line: The motor status message line.
        """
        items = line.split(' ')
        
        if len(items) < 9:
            self.Log("MotorControl.receive_status: Invalid message:", line,
                    level='error')
            return
        
        motor_name = items[3]
        if motor_name != self.MotorName:
            return
        
        configured = items[4] == 'y'
        mctl_timestamp = items[5]
        steps = int(items[6])
        actual_steps = int(items[7])
        angle = float(items[8])
        on_target = items[9] == 'y' if len(items) > 9 else False
        
        # Update state
        self.PreviousAngle = self.CurrentAngle
        self.PreviousMctlTimestamp = self.StatusMctlTimestamp
        
        self.MotorConfigured = configured
        self.StatusMctlTimestamp = mctl_timestamp
        self.StatusLocalTimestamp = self._now_func()
        self.CurrentAngle = angle
        self.OnTarget = on_target
        
        # Calculate speed if we have previous data
        if self.PreviousAngle is not None and self.PreviousMctlTimestamp is not None:
            try:
                # Parse timestamps and calculate delta
                # This is simplified - actual implementation would parse timestamps
                self.AxisSpeed = 0.0  # Placeholder
            except Exception:
                self.AxisSpeed = 0.0

    def show_motor_status(self):
        """Print general status of the motor."""
        print(f"Motor: {self.MotorName}")
        print(f"- RecoveryFileName: {self.RecoveryFileName}")
        print(f"- Driver: {self.Driver}")
        print("Current status:")
        print(f"- MotorConfigured: {self.MotorConfigured}")
        print(f"- CurrentAngle: {self.CurrentAngle:.3f}°")
        print(f"- Position: {self.angle_to_step(self.CurrentAngle)} steps")
        print(f"- AxisSpeed: {self.AxisSpeed}°/s")
        print("Gearing:")
        print(f"- GearRatio: {self.GearRatio}")
        print(f"- MotorStepsPerRev: {self.MotorStepsPerRev}")
        print(f"- MicrostepRatio: {self.MicrostepRatio}")
        print("Configuration:")
        print(f"- MinAngle: {self.MinAngle:.3f}°")
        print(f"- MaxAngle: {self.MaxAngle:.3f}°")
        print(f"- RestAngle: {self.RestAngle:.3f}°")
        print(f"- Orientation: {self.Orientation}")


# Backward compatibility alias
motorcontrol = MotorControl
