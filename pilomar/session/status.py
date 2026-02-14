#!/usr/bin/env python3
"""Session status tracking for Pilomar telescope control.

This module provides the SessionStatus class for tracking the current
state of an observation session.
"""

from datetime import datetime

from pilomar.core.base import AttributeMaster


class SessionStatus(AttributeMaster):
    """Class to hold current status of the observation.
    
    Can export status information to a file for remote monitoring.
    These variables handle a single loop in the ObservationRun routine.
    """

    # Motor control mode definitions
    MCM_DICT = {
        'idle': {
            'description': 'motors at rest.',
            'trajectory': False
        },
        'direct': {
            'description': 'motor movement controlled directly from this software.',
            'trajectory': False
        },
        'trajectory': {
            'description': 'motor movement is autonomous following trajectory.',
            'trajectory': True
        }
    }

    def __init__(self, logger=None, now_func=None):
        """Initialize session status.
        
        Args:
            logger: Optional logger instance.
            now_func: Function returning current UTC datetime.
        """
        self.set_logger(logger)
        self._now_func = now_func or (lambda: datetime.utcnow())
        self._FileNames = []
        self._init_status()

    def _init_status(self):
        """Initialize all status fields."""
        self.ProgramStartTime = self._now_func()
        self.Target = None  # No target yet
        
        # FITS/EXIF tag files
        self.TechFitsTagsFile = None
        self.WeatherFitsTagsFile = None
        self.TechExifTagsFile = None
        self.WeatherExifTagsFile = None
        
        # Debug and control modes
        self.DebugMode = False
        self.AutonomousControl = False
        self.RemoteControl = False
        self.ClockSynchronised = False
        self._ObservationRunning = False
        
        # Communication statistics
        self.MctlRxErrors = 0
        self.MctlRxBytes = 0
        self.MctlTxBytes = 0
        self.MctlExceptionCount = 0
        self.TrajectorySafetyFlushes = 0
        self.CameraTxCount = 0
        self.CameraRxCount = 0
        self.MctlLifeSeconds = 0
        self.MctlWriteDrops = 0
        
        # Motor control
        self.MotorControlMode = 'idle'
        self.MaintainTrajectory = False
        self.MctlPinDict = {}
        
        # Controller info
        self.TerminateMctlHandler = False
        self.ControllerVersion = 'unknown'
        self.TimeDiff = None

    def reset(self):
        """Reset status to initial state."""
        self.AutonomousControl = False
        self.RemoteControl = False
        self.ClockSynchronised = False
        self.MctlRxErrors = 0
        self.MctlRxBytes = 0
        self.MctlTxBytes = 0
        self.MctlExceptionCount = 0
        self.MctlLifeSeconds = 0
        self.MctlWriteDrops = 0
        self.MotorControlMode = 'idle'
        self.set_motor_control_mode(self.MotorControlMode)

    def set_motor_control_mode(self, mode):
        """Change the control mode of the motors.
        
        Supported modes are: idle, direct, trajectory.
        
        Args:
            mode: The control mode string.
        """
        previous_trajectory = self.MaintainTrajectory
        
        if mode in self.MCM_DICT:
            self.Log('SessionStatus.set_motor_control_mode(', mode, ') from',
                    self.MotorControlMode, 'to', mode, terminal=False)
            self.Log('SessionStatus.set_motor_control_mode(', mode, ')',
                    self.MCM_DICT[mode]['description'], terminal=False)
            self.MotorControlMode = mode
            self.MaintainTrajectory = self.MCM_DICT[mode]['trajectory']
        else:
            self.Log('SessionStatus.set_motor_control_mode(', mode,
                    ') is not recognised. Setting to idle.', level='error')
            self.MotorControlMode = 'idle'
            self.MaintainTrajectory = self.MCM_DICT['idle']['trajectory']
        
        # If we've stopped maintaining trajectory, clear existing entries
        if previous_trajectory and not self.MaintainTrajectory:
            self.Log('SessionStatus.set_motor_control_mode(', mode,
                    ') clearing trajectory from motors.', terminal=False)
            # Note: External code should handle sending 'clear trajectory' command

    def set_observation_running(self, running):
        """Set the observation running state.
        
        Args:
            running: True if observation is running.
        """
        self._ObservationRunning = running
        self._observation_timestamp = self._now_func() if running else None

    def observation_running(self):
        """Check if observation is currently running.
        
        Returns:
            True if observation is active.
        """
        return self._ObservationRunning

    def check_cpu_status(self, line):
        """Process CPU status message from microcontroller.
        
        Message format:
        cpu status TIMESTAMP RESET_REASON CLOCKSPEED VOLTAGE MEM_ALLOC MEM_FREE TEMP [FEATURES]
        
        Args:
            line: The CPU status message line.
            
        Returns:
            Dict with parsed values.
        """
        items = line.split(' ')
        
        result = {
            'reset_reason': items[3] if len(items) > 3 else 'UNKNOWN',
            'clockspeed': float(items[4]) * 1e6 if len(items) > 4 else 0.0,
            'voltage': float(items[5]) if len(items) > 5 else 0.0,
            'mem_alloc': int(items[6]) if len(items) > 6 else 0,
            'mem_free': int(items[7]) if len(items) > 7 else 0,
            'temperature': float(items[8]) if len(items) > 8 else 0.0,
            'features': items[9].split('_') if len(items) > 9 else []
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
        items = line.split(' ')
        
        result = {
            'timestamp': items[2] if len(items) > 2 else None,
            'autonomous': items[3] == 'y' if len(items) > 3 else False,
            'remote': items[4] == 'y' if len(items) > 4 else False,
            'clock_sync': items[5] == 'y' if len(items) > 5 else False,
        }
        
        # Update our tracking
        self.AutonomousControl = result['autonomous']
        self.RemoteControl = result['remote']
        self.ClockSynchronised = result['clock_sync']
        
        return result

    def get_status_dict(self):
        """Get current status as dictionary.
        
        Returns:
            Dict with current status values.
        """
        return {
            'program_start': self.ProgramStartTime.isoformat() if self.ProgramStartTime else None,
            'target': str(self.Target) if self.Target else None,
            'observation_running': self._ObservationRunning,
            'debug_mode': self.DebugMode,
            'autonomous_control': self.AutonomousControl,
            'remote_control': self.RemoteControl,
            'clock_synchronised': self.ClockSynchronised,
            'motor_control_mode': self.MotorControlMode,
            'maintain_trajectory': self.MaintainTrajectory,
            'controller_version': self.ControllerVersion,
            'mctl_rx_errors': self.MctlRxErrors,
            'mctl_rx_bytes': self.MctlRxBytes,
            'mctl_tx_bytes': self.MctlTxBytes,
            'mctl_life_seconds': self.MctlLifeSeconds,
        }


# Backward compatibility alias
sessionstatus = SessionStatus
