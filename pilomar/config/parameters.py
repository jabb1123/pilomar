#!/usr/bin/env python3
"""Parameter management for Pilomar telescope control.

This module provides the Parameters class for loading, storing,
and managing runtime parameters.
"""

import os
import json
from datetime import datetime

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
        self.set_logger(logger=logger)
        self._Dictionary = {}  # JSON parameter file loaded from disc
        self._Defaults = {}  # Default values for highlighting changes
        self.ParamFileName = filename
        self._now_func = now_func or (lambda: datetime.utcnow())
        self.RequireRestart = False  # Flag if restart needed after param changes
        self.load_parameters()

    def load_parameters(self):
        """Load parameters from file if it exists.
        
        Missing values are defaulted. Called during __init__()
        and can be called again to reload.
        """
        if os.path.isfile(self.ParamFileName):
            with open(self.ParamFileName, 'r') as f:
                self.log("Loading parameters from file:", self.ParamFileName)
                self._Dictionary = json.load(f)
        
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
            'drv8825': {
                'modelist': {
                    '1': {'power': 100, 'modesignals': 'nnn'},
                    '2': {'power': 70, 'modesignals': 'ynn'},
                    '4': {'power': 40, 'modesignals': 'nyn'},
                    '8': {'power': 20, 'modesignals': 'yyn'},
                    '16': {'power': 10, 'modesignals': 'nny'},
                    '32': {'power': 5, 'modesignals': 'yyy'}
                }
            }
        }
        self.StepperDriverData = self.get_param('StepperDriverData', sdd)

    def _init_owner_and_privacy(self):
        """Initialize owner and privacy settings."""
        self.Owner = self.get_param('Owner', 'telescope owner')
        self.ImagePrivacy = self.get_param('ImagePrivacy', 'high')

    def _init_batch_sizes(self):
        """Initialize batch size parameters."""
        self.BatchSize = self.get_param('BatchSize', 100)
        self.ControlBatchSize = self.get_param('ControlBatchSize', 20)

    def _init_hardware_features(self):
        """Initialize hardware feature parameters."""
        self.BoardType = self.get_param('BoardType', None)
        self.UARTOverride = self.get_param('UARTOverride', None)
        self.CameraEnabled = self.get_param('CameraEnabled', True)
        self.BacklashEnabled = self.get_param('BacklashEnabled', False)
        self.FaultSensitive = self.get_param('FaultSensitive', False)
        self.MctlLedStatus = self.get_param('MctlLedStatus', True)
        self.ObservationResetsMctl = self.get_param('ObservationResetsMctl', False)
        self.ObservationStopPin = self.get_param('ObservationStopPin', 25,
                                                  oldnames=['StopPin'])
        self.IRControlPin = self.get_param('IRControlPin', None)
        self.IRCutoff = self.get_param('IRCutoff', True)
        self.TuneOn32Bit = self.get_param('TuneOn32Bit', True)
        self.MctlResetPin = self.get_param('MctlResetPin', 4)
        self.UartRxQueueLimit = self.get_param('UartRxQueueLimit', 50)

    def _init_motor_parameters(self):
        """Initialize motor configuration parameters."""
        # Azimuth motor
        self.MinAzimuthAngle = self.get_param('MinAzimuthAngle', 0)
        self.MaxAzimuthAngle = min(self.get_param('MaxAzimuthAngle', 360), 360)
        self.AzimuthDriver = self.get_param('AzimuthDriver', 'drv8825')
        self.AzimuthGearRatio = self.get_param('AzimuthGearRatio', 240)
        self.AzimuthMotorStepsPerRev = self.get_param('AzimuthMotorStepsPerRev', 400)
        self.AzimuthSlewMicrostepRatio = self.get_param('AzimuthSlewMicrostepRatio', 1)
        self.AzimuthMicrostepRatio = self.get_param('AzimuthMicrostepRatio', 1)
        self.AzimuthRestAngle = self.get_param('AzimuthRestAngle', 180.0)
        self.AzimuthBacklashAngle = self.get_param('AzimuthBacklashAngle', 0.0)
        self.AzimuthOrientation = self.get_param('AzimuthOrientation', -1)
        self.AzimuthLimitAngle = self.get_param('AzimuthLimitAngle', None)
        
        # Altitude motor
        self.MinAltitudeAngle = self.get_param('MinAltitudeAngle', 0)
        self.MaxAltitudeAngle = min(self.get_param('MaxAltitudeAngle', 90), 90)
        self.AltitudeDriver = self.get_param('AltitudeDriver', 'drv8825')
        self.AltitudeGearRatio = self.get_param('AltitudeGearRatio', 240)
        self.AltitudeMotorStepsPerRev = self.get_param('AltitudeMotorStepsPerRev', 400)
        self.AltitudeMicrostepRatio = self.get_param('AltitudeMicrostepRatio', 1)
        self.AltitudeSlewMicrostepRatio = self.get_param('AltitudeSlewMicrostepRatio', 1)
        self.AltitudeRestAngle = self.get_param('AltitudeRestAngle', 0.0)
        self.AltitudeBacklashAngle = self.get_param('AltitudeBacklashAngle', 0.0)
        self.AltitudeOrientation = self.get_param('AltitudeOrientation', -1)
        self.AltitudeLimitAngle = self.get_param('AltitudeLimitAngle', None)
        
        # Motor timing
        self.FastTime = self.get_param('FastTime', 0.001)
        self.SlowTime = self.get_param('SlowTime', 0.05)
        self.TimeDelta = self.get_param('TimeDelta', 0.003)
        
        speed_list = {
            'Slow': {'label': 'Slow (4ms / step)', 'FastTime': 0.002, 
                    'SlowTime': 0.05, 'TimeDelta': 0.003},
            'Medium': {'label': 'Medium (2ms / step)', 'FastTime': 0.001,
                      'SlowTime': 0.05, 'TimeDelta': 0.003},
            'Fast': {'label': 'Fast (1ms / step)', 'FastTime': 0.0005,
                    'SlowTime': 0.05, 'TimeDelta': 0.003},
            'Turbo': {'label': 'Turbo (0.2ms / step)', 'FastTime': 0.0001,
                     'SlowTime': 0.05, 'TimeDelta': 0.003}
        }
        self.SpeedList = self.get_param('SpeedList', speed_list)
        
        self.MotorStatusDelay = self.get_param('MotorStatusDelay', 10)
        self.SlewEnabled = self.get_param('SlewEnabled', False)
        self.TraceMove = self.get_param('TraceMove', False, oldnames=['TraceMotor'])
        self.OptimiseMoves = self.get_param('OptimiseMoves', False)
        self.MctlCommsTimeout = self.get_param('MctlCommsTimeout', 120)

    def _init_image_parameters(self):
        """Initialize image storage parameters."""
        self.UseUSBStorage = self.get_param('UseUSBStorage', True)
        self.SDPath = self.get_param('SDPath', '/')
        self.USBPath = self.get_param('USBPath', '/media/pi')
        self.FastFlush = self.get_param('FastFlush', False)
        self.FastImageCapture = self.get_param('FastImageCapture', False)
        self.HorizonAltitude = self.get_param('HorizonAltitude', 0.0)
        self._Horizon = max(self.HorizonAltitude, self.MinAltitudeAngle)
        
        # Image file types
        self.CameraSaveJpg = self.get_param('CameraSaveJpg', True)
        self.CameraSaveDng = self.get_param('CameraSaveDng', True)
        self.CameraSaveFits = self.get_param('CameraSaveFits', False)
        
        if not (self.CameraSaveJpg or self.CameraSaveDng or self.CameraSaveFits):
            self.log("No image types are saved according to the parameters.",
                    level='warning')

    def _init_display_parameters(self):
        """Initialize display and color scheme parameters."""
        self.ColorScheme = self.get_param('ColorScheme', 'green')
        self.DebugMode = self.get_param('DebugMode', False)
        
        # Default color scheme values (green)
        self.MenuTitleFG = self.get_param('MenuTitleFG', 46)  # LIME
        self.MenuTitleBG = self.get_param('MenuTitleBG', 22)  # DARKGREEN
        self.MenuSubtitleFG = self.get_param('MenuSubtitleFG', 0)  # BLACK
        self.MenuSubtitleBG = self.get_param('MenuSubtitleBG', 40)  # GREEN
        self.TitleFG = self.get_param('TitleFG', 46)  # LIME
        self.TitleBG = self.get_param('TitleBG', 22)  # DARKGREEN
        self.TextFG = self.get_param('TextFG', 40)  # GREEN
        self.TextBG = self.get_param('TextBG', 235)  # GREY15
        self.TextGood = self.get_param('TextGood', 119)  # LIGHTGREEN
        self.TextPoor = self.get_param('TextPoor', 226)  # YELLOW
        self.TextBad = self.get_param('TextBad', 202)  # ORANGERED1
        self.BorderFG = self.get_param('BorderFG', 22)  # DARKGREEN
        self.BorderBG = self.get_param('BorderBG', 235)  # GREY15
        
        # Apply named color scheme if specified
        self.set_color_scheme(self.ColorScheme)

    def _init_trajectory_parameters(self):
        """Initialize trajectory calculation parameters."""
        self.TrajectoryWindow = self.get_param('TrajectoryWindow', 1200)
        self.UseDynamicTrajectoryPeriods = self.get_param(
            'UseDynamicTrajectoryPeriods', True)
        self.DriftTrackingEnabled = self.get_param('DriftTrackingEnabled', True)

    def _init_filter_parameters(self):
        """Initialize image filter parameters."""
        self.ScanForMeteors = self.get_param('ScanForMeteors', True)
        self.MinSatelliteAltitude = self.get_param('MinSatelliteAltitude', 30)
        self.AuroraCameraAltitude = self.get_param('AuroraCameraAltitude', 5)
        self.SuggestionMagnitude = self.get_param('SuggestionMagnitude', 11)
        self.SuggestionPixels = self.get_param('SuggestionPixels', 100)
        self.SavedUTC = self.get_param('SavedUTC', self._now_func())

    def _init_location_parameters(self):
        """Initialize observer location parameters."""
        # Location can be string like "51.477 N" or decimal degrees
        self.HomeLat = self.get_param('HomeLat', None)  # e.g., "51.477 N"
        self.HomeLon = self.get_param('HomeLon', None)  # e.g., "0.0 W"
        self.LocalTZ = self.get_param('LocalTZ', 'utc')
        
        # Convert to decimal values for calculations
        self._HomeLatVal = 0.0
        self._HomeLonVal = 0.0
        
        if self.HomeLat is not None:
            try:
                parts = str(self.HomeLat).split()
                self._HomeLatVal = float(parts[0])
                if len(parts) > 1 and parts[1].upper() == 'S':
                    self._HomeLatVal = -self._HomeLatVal
            except (ValueError, IndexError):
                # Try as direct float
                try:
                    self._HomeLatVal = float(self.HomeLat)
                except ValueError:
                    pass
        
        if self.HomeLon is not None:
            try:
                parts = str(self.HomeLon).split()
                self._HomeLonVal = float(parts[0])
                if len(parts) > 1 and parts[1].upper() == 'W':
                    self._HomeLonVal = -self._HomeLonVal
            except (ValueError, IndexError):
                # Try as direct float
                try:
                    self._HomeLonVal = float(self.HomeLon)
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
        self._Defaults[name] = default
        result = default
        
        # Check for migrating from old parameter names
        if isinstance(oldnames, list):
            for oldname in oldnames:
                if oldname in self._Dictionary:
                    result = self._Dictionary[oldname]
                    self.log("Parameters.get_param(", name, ") migrating from",
                            oldname, "with value", result, terminal=False)
                    break
        
        # Get current parameter value
        result = self._Dictionary.get(name, result)
        
        if result != default:
            self.log("Parameters.get_param(", name, ") default", default,
                    "overridden with", result, terminal=False)
        
        return result

    def set_color_scheme(self, scheme='green'):
        """Set color scheme to named preset.
        
        Args:
            scheme: One of 'white', 'blue', 'green', 'red', or 'custom'.
        """
        # Color values are 256-color terminal codes
        schemes = {
            'white': {
                'MenuTitleFG': 15, 'MenuTitleBG': 244,
                'MenuSubtitleFG': 15, 'MenuSubtitleBG': 239,
                'TitleFG': 15, 'TitleBG': 239,
                'TextFG': 15, 'TextBG': 0,
                'TextGood': 15, 'TextPoor': 226, 'TextBad': 196,
                'BorderFG': 249, 'BorderBG': 0
            },
            'blue': {
                'MenuTitleFG': 15, 'MenuTitleBG': 24,
                'MenuSubtitleFG': 0, 'MenuSubtitleBG': 39,
                'TitleFG': 15, 'TitleBG': 24,
                'TextFG': 51, 'TextBG': 235,
                'TextGood': 117, 'TextPoor': 226, 'TextBad': 202,
                'BorderFG': 17, 'BorderBG': 235
            },
            'green': {
                'MenuTitleFG': 46, 'MenuTitleBG': 22,
                'MenuSubtitleFG': 0, 'MenuSubtitleBG': 40,
                'TitleFG': 46, 'TitleBG': 22,
                'TextFG': 40, 'TextBG': 235,
                'TextGood': 119, 'TextPoor': 226, 'TextBad': 202,
                'BorderFG': 22, 'BorderBG': 235
            },
            'red': {
                'MenuTitleFG': 15, 'MenuTitleBG': 52,
                'MenuSubtitleFG': 0, 'MenuSubtitleBG': 124,
                'TitleFG': 15, 'TitleBG': 124,
                'TextFG': 196, 'TextBG': 235,
                'TextGood': 218, 'TextPoor': 226, 'TextBad': 202,
                'BorderFG': 52, 'BorderBG': 235
            }
        }
        
        if scheme in schemes:
            for key, value in schemes[scheme].items():
                setattr(self, key, value)
            self.ColorScheme = scheme

    def save_attributes(self, filename):
        """Save parameters to JSON file.
        
        Args:
            filename: Path to save the parameter file.
        """
        # Build dictionary from current attributes
        save_dict = {}
        ignore_list = ['Logger', '_Dictionary', '_Defaults', '_now_func']
        
        for key, value in vars(self).items():
            if key.startswith('_'):
                continue
            if key in ignore_list:
                continue
            if callable(value):
                continue
            save_dict[key] = value
        
        with open(filename, 'w') as f:
            json.dump(save_dict, f, indent=2, default=str)
        
        self.log("Parameters saved to:", filename, terminal=False)

    def show(self):
        """Display all parameters to terminal."""
        print("List parameters:")
        print("(*) indicates a modified parameter value.")
        
        for key, value in sorted(vars(self).items()):
            if key.startswith('_'):
                continue
            if callable(value):
                continue
            if key in ['Logger']:
                continue
            
            default_flag = ''
            if key in self._Defaults and self._Defaults[key] != value:
                default_flag = f' (*) Was {self._Defaults[key]}'
            
            if isinstance(value, dict):
                print(f"{key:>30} : dictionary {default_flag}")
            else:
                print(f"{key:>30} : {value}{default_flag}")


# Backward compatibility alias
parameters = Parameters
