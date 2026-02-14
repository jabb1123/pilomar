"""Pilomar Telescope Control System.

A Pythonic telescope control system for Raspberry Pi with astronomical tracking,
image capture, and motor control capabilities.

Version: 2.0.0 (Refactored)
License: GNU General Public License v3.0
"""

__version__ = '2.0.0'
__author__ = 'Pilomar Project'

# Core utilities
from .core.base import AttributeMaster
from .core.timer import Timer, ProgressTimer
from .core.logger import LogFile
from .core.converters import (
    utc_string_to_datetime,
    dts_to_datetime,
    string_to_datetime,
    is_float,
    is_int,
    text_to_int,
    text_to_float,
)

# Hardware interfaces
from .hardware.camera import AstroLens, AstroSensor, AstroCamera
from .hardware.gpio import InputPinGpio, OutputPinGpio, InputPinGpiod, OutputPinGpiod

# System monitoring
from .monitoring.cpu import CpuMonitor
from .monitoring.memory import MemoryMonitor  
from .monitoring.disk import DiskMonitor

# Utilities
from .utils.os_command import OsCommand

# Celestial calculations
from .celestial.celestrak import Celestrak
from .celestial.trig import (
    CompassPoint, AngleToHMS, AngleToDMS, HMSToAngle, DMSToAngle,
    AltAzToXYZ, XYZToAltAz, RelativeAltAz, AzAltText, RaDecText,
)

# Imaging (requires opencv)
try:
    from .imaging.image import PilomarImage
    from .imaging.keogram import PilomarKeogram
    from .imaging.data_types import DataSet, DataPoint, FdObject, FdEdge
    _IMAGING_AVAILABLE = True
except ImportError:
    _IMAGING_AVAILABLE = False

# FITS support (requires astropy)
try:
    from .imaging.fits import FitsCapture, date_to_jd, normalize_array
    _FITS_AVAILABLE = True
except ImportError:
    _FITS_AVAILABLE = False

# UI components (requires curses)
try:
    from .ui.keyboard import KeyboardScanner
    from .ui.text_color import TextColor
    from .ui.display import CdSprite, MessageWindow, BigLetters, Field, ColorDisplay
    from .ui.menu import Menu, ProcedureMenu, OptionMenu, ListChooser, FileChooser
    _UI_AVAILABLE = True
except ImportError:
    _UI_AVAILABLE = False

# Config modules
try:
    from .config.hardware import Hardware
    from .config.parameters import Parameters
    _CONFIG_AVAILABLE = True
except ImportError:
    _CONFIG_AVAILABLE = False

# Control modules
try:
    from .control.motor import MotorControl
    from .control.microcontroller import Microcontroller
    _CONTROL_AVAILABLE = True
except ImportError:
    _CONTROL_AVAILABLE = False

# Session modules
try:
    from .session.status import SessionStatus
    from .session.entry import SessionEntry
    from .session.list import SessionList
    _SESSION_AVAILABLE = True
except ImportError:
    _SESSION_AVAILABLE = False

# Targets modules
try:
    from .targets.fixed_point import FixedPoint
    from .targets.quickstar import QuickStar
    from .targets.local_stars import LocalStars
    from .targets.sky_context import SkyContext, TimeContext, HardwareContext
    _TARGETS_AVAILABLE = True
except ImportError:
    _TARGETS_AVAILABLE = False

# Targets - Target (requires Skyfield)
try:
    from .targets.target import Target
    _TARGET_AVAILABLE = True
except ImportError:
    _TARGET_AVAILABLE = False
    Target = None

# Targets - ImageTracker (requires astroalign)
try:
    from .targets.image_tracker import ImageTracker
    _IMAGETRACKER_AVAILABLE = True
except ImportError:
    _IMAGETRACKER_AVAILABLE = False
    ImageTracker = None

# Folders module
try:
    from .folders.folder_handler import FolderHandler
    _FOLDERS_AVAILABLE = True
except ImportError:
    _FOLDERS_AVAILABLE = False

__all__ = [
    # Core
    'AttributeMaster',
    'Timer',
    'ProgressTimer',
    'LogFile',
    'utc_string_to_datetime',
    'dts_to_datetime',
    'string_to_datetime',
    'is_float',
    'is_int',
    'text_to_int',
    'text_to_float',
    # Hardware
    'AstroLens',
    'AstroSensor',
    'AstroCamera',
    'InputPinGpio',
    'OutputPinGpio',
    'InputPinGpiod',
    'OutputPinGpiod',
    # Monitoring
    'CpuMonitor',
    'MemoryMonitor',
    'DiskMonitor',
    # Utilities 
    'OsCommand',
    # Celestial
    'Celestrak',
    'CompassPoint',
    'AngleToHMS',
    'AngleToDMS',
    'HMSToAngle',
    'DMSToAngle',
    'AltAzToXYZ',
    'XYZToAltAz',
    'RelativeAltAz',
    'AzAltText',
    'RaDecText',
    # Imaging (when available)
    'PilomarImage',
    'PilomarKeogram',
    'DataSet',
    'DataPoint',
    'FdObject',
    'FdEdge',    # FITS (when available)
    'FitsCapture',
    'date_to_jd',
    'normalize_array',
    # UI (when available)
    'KeyboardScanner',
    'TextColor',
    'CdSprite',
    'MessageWindow',
    'BigLetters',
    'Field',
    'ColorDisplay',
    'Menu',
    'ProcedureMenu',
    'OptionMenu',
    'ListChooser',
    'FileChooser',
    # Config (when available)
    'Hardware',
    'Parameters',
    # Control (when available)
    'MotorControl',
    'Microcontroller',
    # Session (when available)
    'SessionStatus',
    'SessionEntry',
    'SessionList',
    # Targets (when available)
    'Target',
    'FixedPoint',
    'QuickStar',
    'LocalStars',
    'ImageTracker',
    'SkyContext',
    'TimeContext',
    'HardwareContext',
    # Folders (when available)
    'FolderHandler',
]