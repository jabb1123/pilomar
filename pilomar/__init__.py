"""Pilomar Telescope Control System.

A Pythonic telescope control system for Raspberry Pi with astronomical tracking,
image capture, and motor control capabilities.

Version: 2.0.0 (Refactored)
License: GNU General Public License v3.0
"""

__version__ = "2.0.0"
__author__ = "Pilomar Project"

# Core utilities
# Celestial calculations (always available)
from .celestial.trig import (
    alt_az_to_xyz,
    angle_to_dms,
    angle_to_hms,
    az_alt_text,
    compass_point,
    dms_to_angle,
    hms_to_angle,
    ra_dec_text,
    relative_alt_az,
    xyz_to_alt_az,
)
from .core.base import AttributeMaster
from .core.converters import (
    dts_to_datetime,
    is_float,
    is_int,
    string_to_datetime,
    text_to_float,
    text_to_int,
    utc_string_to_datetime,
)
from .core.logger import LogFile
from .core.timer import ProgressTimer, Timer

# Folders module (always available)
from .folders.folder_handler import FolderHandler
from .session.entry import SessionEntry
from .session.list import SessionList

# Session modules (always available)
from .session.status import SessionStatus

# Target context helpers (always available)
from .targets.fixed_point import FixedPoint
from .targets.sky_context import HardwareContext, SkyContext, TimeContext

# Utilities (always available)
from .utils.os_command import OsCommand

# Hardware interfaces (require RPi GPIO libraries)
try:
    from .hardware.camera import AstroCamera, AstroLens, AstroSensor
    from .hardware.gpio import (
        InputPinGpio,
        InputPinGpiod,
        OutputPinGpio,
        OutputPinGpiod,
    )
except ImportError:
    pass

# System monitoring (require RPi / gpiozero for CPU temperature)
try:
    from .monitoring.cpu import CpuMonitor
    from .monitoring.disk import DiskMonitor
    from .monitoring.memory import MemoryMonitor
except ImportError:
    pass

# Config (may depend on hardware detection)
try:
    from .config.hardware import Hardware
    from .config.parameters import Parameters
except ImportError:
    pass

# Celestrak satellite data (requires requests)
try:
    from .celestial.celestrak import Celestrak
except ImportError:
    pass

# Imaging (requires opencv / cv2)
try:
    from .imaging.data_types import DataPoint, DataSet, FdEdge, FdObject
    from .imaging.fits import FitsCapture, date_to_jd, normalize_array
    from .imaging.image import PilomarImage
    from .imaging.keogram import PilomarKeogram
except ImportError:
    pass

# UI (requires terminal capabilities)
try:
    from .ui.display import BigLetters, CdSprite, ColorDisplay, Field, MessageWindow
    from .ui.keyboard import KeyboardScanner
    from .ui.menu import FileChooser, ListChooser, Menu, OptionMenu, ProcedureMenu
    from .ui.text_color import TextColor
except ImportError:
    pass

# Control (requires serial / motor libraries)
try:
    from .control.microcontroller import Microcontroller
    from .control.motor import MotorControl
except ImportError:
    pass

# Targets requiring Skyfield
try:
    from .targets.local_stars import LocalStars
    from .targets.quickstar import QuickStar
    from .targets.target import Target
except ImportError:
    pass

# ImageTracker (requires astroalign)
try:
    from .targets.image_tracker import ImageTracker
except ImportError:
    pass

__all__ = [
    # Core
    "AttributeMaster",
    "Timer",
    "ProgressTimer",
    "LogFile",
    "utc_string_to_datetime",
    "dts_to_datetime",
    "string_to_datetime",
    "is_float",
    "is_int",
    "text_to_int",
    "text_to_float",
    # Hardware
    "AstroLens",
    "AstroSensor",
    "AstroCamera",
    "InputPinGpio",
    "OutputPinGpio",
    "InputPinGpiod",
    "OutputPinGpiod",
    # Monitoring
    "CpuMonitor",
    "MemoryMonitor",
    "DiskMonitor",
    # Utilities
    "OsCommand",
    # Celestial
    "Celestrak",
    "compass_point",
    "angle_to_hms",
    "angle_to_dms",
    "hms_to_angle",
    "dms_to_angle",
    "alt_az_to_xyz",
    "xyz_to_alt_az",
    "relative_alt_az",
    "az_alt_text",
    "ra_dec_text",
    # Imaging (when available)
    "PilomarImage",
    "PilomarKeogram",
    "DataSet",
    "DataPoint",
    "FdObject",
    "FdEdge",  # FITS (when available)
    "FitsCapture",
    "date_to_jd",
    "normalize_array",
    # UI (when available)
    "KeyboardScanner",
    "TextColor",
    "CdSprite",
    "MessageWindow",
    "BigLetters",
    "Field",
    "ColorDisplay",
    "Menu",
    "ProcedureMenu",
    "OptionMenu",
    "ListChooser",
    "FileChooser",
    # Config (when available)
    "Hardware",
    "Parameters",
    # Control (when available)
    "MotorControl",
    "Microcontroller",
    # Session (when available)
    "SessionStatus",
    "SessionEntry",
    "SessionList",
    # Targets (when available)
    "Target",
    "FixedPoint",
    "QuickStar",
    "LocalStars",
    "ImageTracker",
    "SkyContext",
    "TimeContext",
    "HardwareContext",
    # Folders (when available)
    "FolderHandler",
]
