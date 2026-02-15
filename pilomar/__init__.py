"""Pilomar Telescope Control System.

A Pythonic telescope control system for Raspberry Pi with astronomical tracking,
image capture, and motor control capabilities.

Version: 2.0.0 (Refactored)
License: GNU General Public License v3.0
"""

__version__ = "2.0.0"
__author__ = "Pilomar Project"

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
    compass_point,
    angle_to_hms,
    angle_to_dms,
    hms_to_angle,
    dms_to_angle,
    alt_az_to_xyz,
    xyz_to_alt_az,
    relative_alt_az,
    az_alt_text,
    ra_dec_text,
)

# Imaging (requires opencv)
from .imaging.image import PilomarImage
from .imaging.keogram import PilomarKeogram
from .imaging.data_types import DataSet, DataPoint, FdObject, FdEdge
from .imaging.fits import FitsCapture, date_to_jd, normalize_array

from .ui.keyboard import KeyboardScanner
from .ui.text_color import TextColor
from .ui.display import CdSprite, MessageWindow, BigLetters, Field, ColorDisplay
from .ui.menu import Menu, ProcedureMenu, OptionMenu, ListChooser, FileChooser


from .config.hardware import Hardware
from .config.parameters import Parameters


from .control.motor import MotorControl
from .control.microcontroller import Microcontroller

# Session modules

from .session.status import SessionStatus
from .session.entry import SessionEntry
from .session.list import SessionList

from .targets.fixed_point import FixedPoint
from .targets.quickstar import QuickStar
from .targets.local_stars import LocalStars
from .targets.sky_context import SkyContext, TimeContext, HardwareContext


from .targets.target import Target


# Targets - ImageTracker (requires astroalign)

from .targets.image_tracker import ImageTracker


# Folders module

from .folders.folder_handler import FolderHandler

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
