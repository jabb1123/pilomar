"""Motor and microcontroller control for Pilomar telescope."""

from .microcontroller import Microcontroller
from .motor import MotorControl

# Direct-GPIO motor control (no external MCU required — uses pigpio)
try:
    from .direct_slew import DirectSlewController
    from .direct_stepper import DualStepperDriver
    from .direct_tracker import DirectSkyTracker

    _DIRECT_MOTOR_AVAILABLE = True
except ImportError:
    _DIRECT_MOTOR_AVAILABLE = False

__all__ = [
    "MotorControl",
    "Microcontroller",
    # Direct GPIO (Pi only)
    "DualStepperDriver",
    "DirectSkyTracker",
    "DirectSlewController",
]
