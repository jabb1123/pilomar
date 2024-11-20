#!/usr/bin/python
"""This is the main program for the Pilomar telescope control system."""
# This software is published under the GNU General Public License v3.0.
# Also respect any pre-existing terms of any components that this incorporates.
# Examples
# - SKYFIELD is issued and used under the "MIT License" terms.
# - HIPPARCOS data is used under Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International License.
# - JPL data for planet positions will have its own licence.
# - NGC (New General Catalog) is gathered from multiple sources including the Saguaro Astronomy Club Database version 8.1
# - The MESSIER catalog is gathered from multiple sources.
# - The MeteorShower list is based upon the Wikipedia list (2021).
# - Space station data comes from the celestrak.org website (using NORAD public data).
# - The Comet list comes from the Minor Planet Center.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# THIS SOFTWARE CAN CONTROL ELECTRICAL AND MECHANICAL DEVICES.
# THERE IS THEREFORE A RISK OF INJURY FROM INCORRECT ASSEMBLY, OPERATION OR FAILURE OF COMPONENTS.
# IT IS YOUR RESPONSIBILITY TO ENSURE THE SAFETY OF THE DEVICES YOU CHOOSE TO CONTROL WITH THIS SOFTWARE.

# The Skyfield API is described here: https://rhodesmill.org/skyfield/api.html

# This version expects the following hardware:
# - RaspberryPi microcomputer (V3 or V4) 2GB or greater.
# - Raspbian BUSTER 32BIT or BOOKWORM 64BIT operating system.
# - Pimoroni Tiny2040 8MB as a microcontroller of the motors
# - Nema 17 stepper motors (0.9degree per full step).
# - DRV8825 stepper motor driver chips.
# - Raspberry Pi High Quality Camera Sensor V1.0
# - Raspberry Pi 16mm 'telephoto' lens.
# - - You can use other lenses, the program will generally try to adapt to
# the lens length defined in the parameter file, do not exceed 50mm.

# Recommended exposures.
# = Full Moon = 1e-6 seconds
# = M31 Andromeda Galaxy = 10.0 seconds = Magnitude 3.44
# = M27 Dumbbell Nebula = 20.0 seconds = Magnitude 7.50
# Fastest possible exposure is 1e-6 seconds.

# ============================================================
# This version runs on only certain Raspberry Pi configurations.
# Working combinations :-
#   RASPBERRY PI 3B + BUSTER 32Bit
#   RASPBERRY PI 4B + BUSTER 32Bit
#   RASPBERRY PI 4B + BOOKWORM 64Bit <------------ RECOMMENDED
# Unsupported combinations :-
#   RASPBERRY PI
#   RASPBERRY PI 2
#   RASPBERRY PI 3B + BULLSEYE
#   RASPBERRY PI 4B + BULLSEYE
#   RASPBERRY PI 5B (Not ready yet)
# ============================================================

# BEWARE! This program uses THREADS. It has to handle UI, MOVEMENT, COMMUNICATIONS and PHOTOGRAPHY in parallel.
# Thread 1 (MAIN Process) handles:
#   - User interface, astro calculations, observation control.
# Thread 2 handles:
#   - Image capture, image preparation, preview generation, tracking image processing, motor position tuning.
# Thread 3 handles:
#   - UART communication flow between RPi and microcontroller, including trajectory calculation and updates.

# KNOWN ISSU-----------------------------------------------------
# *Q* On rare occasions, the camera process can hang completely, it does
# not complete image capture, requiring a power cycle of the RPi.
#     The cause is not known, but the camera board stops responding for a very long time.
#     I have read online that power problems to the camera can cause this.
#     This is detected and reported, but this does not recover the situation programmatically.
#     Problem is more rare in builds from 2023 onwards.
# *Q* Some microcontrollers sometimes randomly reset. The software is relatively reset
# tolerant and recovers automatically, but the cause of the resets is not yet identified.
#     Resets are reported, and generally only cause brief delays while the system recovers.
#     Resets are more common with RPi Pico 2040 and Adafruit Feather 2040.
#     Resets do not occur with Pimoroni Tiny2040 8MB.
# *Q* During observations the keyboard scanning routine can the display to blink sometimes over telnet connections.
#     If you are sensitive to flashing images you can slow down the keyboard scanning
# so that the image is more stable, but it will react to keyboard input more slowly.

# Version
# 0.1.1    29.11.2023 Removed out of date references to MotorRunningSeconds.
#                     Stopped eternal looping if recoveryfile write had continuous failure.
#                     markup_preview now tolerates older format ngc.json datafile.
# 0.1.2    29.11.2023 Remaining references to onboard LEDs removed as they
# are not required in the running system, and simplify the PCB build.
#          11.12.2023 ProjectRoot is respected across the program, there were some
# hardcoded /home/pi directory names still in the code. (GitHub Issue #35)
#          11.12.2023 Min/MaxAltitudeAngle initialisation was wrong. (GitHub Issue #38)
#          18.12.2023 Version validation only considers first 2 elements.
#                     set_motor_angle() now states current motor angle.
# 0.2.0    13.01.2024 GoToAngle, go_to_target show progress during large moves.
#          31.01.2024 2024-01-issues items addressed.
# 0.3.0    12.03.2024 2024-03-issues items addressed.
# 1.0.0    20.04.2024 Refactored code.
#                     Preparations for RPi5 support.
# 1.1.0    07.05.2024 Bookworm/64bit can now generate .fits image files.


# Versioning
# MAJOR.MINOR.MICRO
# - MAJOR = Breaking change. Not fully compatible with previous versions. Usually requires RPI and MICROCONTROLLER updates together.
# - MINOR = New features but backwards compatible. Usually allows RPI or MICROCONTROLLER to be updated independently.
# - MICRO = Development/bugfix releases.
VERSION = "1.1.0"  # Shared with microcontroller. # Make sure the microcontroller accepts any new version number.

import sys

from motor.control import MotorControl
from utils.math_func import (
    angle_to_dms,
    angle_to_hms,
    compass_point,
    deg_3dp,
    display_degree,
    display_hms,
    dms_to_angle,
    hms_to_angle,
    interpolate,
)
from utils.statics import DEGREE_SYMBOL, SYMBOLS
from utils.text.human_readable import (
    clean_datetime_string,
    dictionary_to_string,
    human_readable_bytes,
    human_readable_seconds,
    safe_name,
    source_code,
)
from utils.time_funcs import (
    datetime2_ts,
    hms_from_stamp,
    now_hour_minute_sec,
    now_utc,
    source_date,
    ts_to_datetime,
    utc_time_stamp,
)

ProgramTitle = (
    source_code().split("/")[-1].split(".")[0].lower()
)  # Used in display titles and also filenaming to separate different generations of the program.
print(ProgramTitle, VERSION)

# print("Version:",VERSION)
ACCEPTABLECONTROLLERVERSIONS = [
    "1.0"
]  # Microcontroller versions that this will work with. Ignore patch level.

import glob  # file system.
import json  # json file handling.
import math  # Math and trig functions.
import os  # OS Command execution.

# import sep # This is used by astroalign, it is only imported here to flush out any problems with the package. (It has suffered from the classic 'numpy.ndarray size changed' in the past.)
import threading  # Run the image capture in a separate thread so that motor movement can continue. *Q* Drift calculation and targetting could also move to separate thread.
import time  # sleep functionality for pauses in execution.
from datetime import datetime, timedelta
from queue import (
    Queue,
)  # Use queue mechanism to communicate between observation_run and Camera threads because they run in parallel.

# Import required libraries
from typing import Tuple  # For type hinting.

import astroalign  # Image alignment routines.
import numpy as np  # Fast array handling
import pandas  # Dataframe handling.
import pytz  # Timezone handling.
from skyfield import VERSION as SkyfieldVersion
from skyfield.data import mpc  # For comet trajectory handling.
from skyfield.api import EarthSatellite, Loader, Star, Topos, load_constellation_names
from skyfield.constants import (
    GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN,
)  # Used for calculating Comet positions relative to sun.
from skyfield.data import (
    stellarium,
)  # For constellation mapping. *Q* Can replace homegrown solution.

import gpio  # GPIO wrappers to support different GPIO libraries.
from camera import AstroCamera, AstroLens, AstroSensor  # Pilomar's CAMERA elements.
from camera.image import (
    pilomarimage,
)  # Pilomar's IMAGE BUFFER handler (combines numpy, OpenCV and pilomar specific routines)
from camera.targets.fixed import FixedPoint  # Pilomar's FIXED POINT target.
from camera.targets.local import LocalStars  # Pilomar's LOCAL STAR cache.
from camera.targets.target import AstroTarget  # Pilomar's TARGET handling.
from camera.targets.track import imagetracker  # Pilomar's IMAGE TRACKER.
from gpio import Microcontroller  # Pilomar's microcontroller handler.
from oscommand import OSCommand  # Pilomar's OS command executor.
from pilomarcelestrak import Celestrack  # Pilomar's CELESTRAK satellite data handler.
from session.list import SessionList
from session.status import SessionStatus  # Pilomar's session handling.
from utils.disk import DiskMonitor, DiskType  # Pilomar's disc storage monitor.
from utils.files import FolderHandler  # File handling routines.
from utils.logfile import LogFile  # Pilomar's logging class.
from utils.menus import OptionMenu, ProcedureMenu  # Basic menu handlers.
from utils.params import Parameters
from utils.text.display import (
    ColorDisplay,
)  # Basic colour character graphics for window display on terminal.

# textcolor is a homegrown simplified terminal display library.
# There are other libraries available for groovy character displays ('colorama', 'termcolor', 'blessing', 'rich' etc).
from utils.text.textcolor import (  # Basic colour and cursor control codes for terminal displays.; Simple non-blocking keyboard scanner.; Allow user to filter through a list of names.
    KeyboardScanner,
    ListChooser,
    TextColor,
)
from utils.timer import Timer  # Pilomar's timer classes.

if gpio.GPIO_DRIVER == "GPIO":  # Original GPIO handlers needed for IO.
    # Select the GPIO specific drivers for IO functions.
    inputpin = gpio.InputPinGPIO
    outputpin = gpio.OutputPinGPIO
    GPIOCleanup = gpio.cleanup_gpio
elif gpio.GPIO_DRIVER == "GPIOD":  # Bookworm GPIOD handlers needed for IO.
    # Select the GPIOD specific drivers for IO functions.
    inputpin = gpio.InputPinGPIO
    outputpin = gpio.OutputPinGPIO
    GPIOCleanup = gpio.cleanup_gpio
else:
    raise ImportError(
        "Could not identify a suitable GPIO driver for this installation."
    )
print("Got through imports")

# Dictionary of 'toggles' so that warnings do not repeat too often.
ResumeObservation = (
    False  # Set this to TRUE to automatically load the previous observation and resume.
)
StartupClock = None  # No initial datetime set for start of program. Means we use the current system clock.
ClockOffset = None  # Number of seconds to apply to clocks to make the program appear to run in a different period of time.  Use with caution.

# During an observation run we need to interrupt the processing. Python doesn't do this natively and
# <ctrl-c> will stop the program brutally, so we use the curses library to provide a keyboard scanner.
Keyboard = (
    KeyboardScanner()
)  # Non-Blocking reader of the keyboard (via curses library).

# Identify the program and version to the user.
print(TextColor.yellow(source_code() + " " + str(source_date())))

ProjectRoot = os.path.dirname("/home/pi/pilomar")  # Root directory of the project.

reload_data = False  # Set to True to reload the data files.

# Initialize Logging.
logdir = ProjectRoot + "/log"
# Main log file.
LogFileName = logdir + "/" + ProgramTitle + "_" + utc_time_stamp() + ".log"
print("Main log to", LogFileName)
main_log = LogFile(
    LogFileName, clockoffset=ClockOffset
)  # Create a MAIN log file object.

# Camera log file.
CamLogFileName = logdir + "/" + ProgramTitle + "_camera_" + utc_time_stamp() + ".log"
print("Camera log to", CamLogFileName)
cam_log = LogFile(
    CamLogFileName, clockoffset=ClockOffset
)  # Create a CAMERA specific log file. (This runs in separate thread, unsure if logging would be thread-safe.)

main_log.log("Python version:", sys.version, terminal=False)
main_log.log(
    "Main: reload_data", reload_data, terminal=False
)  # Record that 'reload' has been triggered.

main_log.log("Startup parameters:", run_args, terminal=False)
HistoryJsonFile = (
    ProjectRoot + "/data/" + ProgramTitle + "_sessions.json"
)  # Chosen observation targets and settings are stored in this file.


OSCommand = OSCommand(main_log.log)  # Create OS Command executor.
osCmd = (
    OSCommand.execute
)  # Shortcut point to the execution method which returns the output.
osCmdCode = (
    OSCommand.execute_code
)  # Shortcut point to the execution method which returns the termination code.


def os_version():
    """Return the version of operating system.
    Returns
      versionid       eg  10
      versioncodename eg  buster
      ostype          eg  debian
    """
    versionid = None
    versioncodename = None
    ostype = None
    for line in osCmd("cat /etc/os-release"):
        if len(line) > 0:
            elements = line.split("=")
            if elements[0] == "VERSION_ID":
                versionid = int(elements[1].replace('"', ""))
            elif elements[0] == "VERSION_CODENAME":
                versioncodename = elements[1]
            elif elements[0] == "ID":
                ostype = elements[1]
    osbits = int(osCmd("getconf LONG_BIT")[0])  # Check 32 vs 64 bit O/S
    osproc = osCmd("uname -m")[0]
    return versionid, versioncodename, ostype, osbits, osproc


def r_pi_model():
    """Calculate a label for the model of RPI in use."""
    lines = osCmd("cat /sys/firmware/devicetree/base/model")
    rpimodel = "Raspberry Pi"
    for line in lines:
        if len(line) > 0:
            rpimodel = line
    rpimodel = rpimodel.replace("Raspberry Pi ", "RPi ")
    rpimodel = rpimodel.replace("Model ", "")
    rpimodel = rpimodel.replace("Rev ", "")
    # Remove non printing characters.
    temp = ""
    for char in rpimodel:
        if char >= " ":
            temp += char
    rpimodel = temp
    rpinum = rpimodel.split(" ")[
        1
    ]  # Pull the '4' out of "RPi 4 B 1.4" format response.
    return rpimodel, rpinum


RPIMODEL, RPiNum = r_pi_model()
OS_id, OS_name, OS_type, OS_bits, OS_processor = os_version()
OS_systemkey = RPiNum + "/" + OS_name + "/" + str(OS_bits)
main_log.log(
    "RPi: Model:",
    RPIMODEL,
    "Num:",
    RPiNum,
    "OStype:",
    OS_type,
    "OSid:",
    OS_id,
    "OSname:",
    OS_name,
    "OSbits:",
    OS_bits,
    "OSproc:",
    OS_processor,
    "SysKey:",
    OS_systemkey,
    terminal=True,
)
RASPISTILL_SYSTEMS = [
    "wheezy",
    "jessie",
    "stretch",
    "buster",
]  # These all came with raspistill for camera support.
SUPPORTED_SYSTEMS = [
    "3/buster/32",
    "4/buster/32",
    "4/bookworm/64",
    "5/bookworm/64",
]  # The software is designed to run under these hardware/os combinations.
if OS_name in RASPISTILL_SYSTEMS:
    camera_driver = "raspistill"
else:
    camera_driver = (
        "libcamera"  # 'bullseye' and 'bookworm' come with libcamera installed.
    )
main_log.log(
    OS_name, "O/S found, assuming camera driver is", camera_driver, terminal=False
)
main_log.log("GPIO driver chosen:", gpio.GPIO_DRIVER, terminal=False)
if OS_systemkey in SUPPORTED_SYSTEMS:
    main_log.log(ProgramTitle, "OK to run under", OS_systemkey, terminal=False)
else:  # Cannot proceed, wrong O/S & hardware combination.
    main_log.log(
        ProgramTitle,
        "is only designed to run under",
        SUPPORTED_SYSTEMS,
        level="error",
        terminal=True,
    )
    main_log.log(
        ProgramTitle,
        "is not designed to run under",
        OS_name,
        OS_bits,
        "bit on",
        RPIMODEL,
        "(",
        OS_systemkey,
        ")",
        level="error",
        terminal=True,
    )
    raise Exception(
        str(ProgramTitle)
        + " is not designed to run under this combination of hardware and O/S."
    )


# Remove out of date log files to preserve disc space.
print(TextColor.yellow("Removing out of date log files to preserve disc space..."))
# Show what will be deleted.
cmd = "find " + logdir + " -type f -name '" + ProgramTitle + "_*.log' -mtime +2 -print"
linelist = osCmd(cmd)
for line in linelist:
    if len(line) > 0:
        print(TextColor.orange("Deleting", line))
# Now delete.
cmd = "find " + logdir + " -type f -name '" + ProgramTitle + "_*.log' -mtime +2 -delete"
print(cmd)  # Show the user the command being executed.
osCmd(cmd)
print("Done.")

# Log details about the environment.
main_log.log("Skyfield version:", SkyfieldVersion, terminal=False)
if SkyfieldVersion[0] > 1 or SkyfieldVersion[1] > 39:
    main_log.log(
        "Pilomar is developed with Skyfield version 1.39: This version",
        str(SkyfieldVersion[0]) + "." + str(SkyfieldVersion[1]),
        terminal=False,
    )

TextColor.get_term_type()
main_log.log("Terminal type:", TextColor.TermType, TextColor.Mode, terminal=False)


# Establish the filename of the parameters file that will be loaded.
ParameterFileName = ProjectRoot + "/data/" + ProgramTitle + "_params.json"
params = Parameters(
    filename=ParameterFileName, logger=main_log
)  # Create and load parameters.

# Set the log file flush strategy from the parameter file.
main_log.fast_flush = cam_log.fast_flush = params.fast_flush

# Issue any warnings about specific parameter settings.
if params.home_lat is None or params.home_lon is None:
    # Home location is not yet set. Save the parameter file for editing then quit.
    # The user has to manually enter the home latitude and longitude into the paramter file.
    params.save_attributes(
        params.param_filename
    )  # Write current operating parameters back to disc.
    lines = [
        "HOME LOCATION IS NOT SET",
        " ",
        params.param_filename,
        " ",
        "Edit the HomeLat and HomeLon values in the parameter file.",
        "Give the co-ordinates of your location.",
        "Then restart this program.",
    ]
    TextColor.text_box(lines, fg=TextColor.WHITE, bg=TextColor.RED, justify="c")
    print(" ")
    print(TextColor.yellow("Eg: Paris, France :"))
    print(TextColor.yellow('            "HomeLat" : "48.864 N",'))
    print(TextColor.yellow('            "HomeLon" : "2.349 E",'))
    print(" ")
    print(TextColor.yellow("    Atlanta, USA :"))
    print(TextColor.yellow('            "HomeLat" : "33.753 N",'))
    print(TextColor.yellow('            "HomeLon" : "84.386 W",'))
    print(" ")
    print(TextColor.yellow("    Tokyo, Japan :"))
    print(TextColor.yellow('            "HomeLat" : "35.652 N",'))
    print(TextColor.yellow('            "HomeLon" : "139.839 E",'))
    print(" ")
    print(TextColor.yellow("    Alice Springs, Australia :"))
    print(TextColor.yellow('            "HomeLat" : "23.810 S",'))
    print(TextColor.yellow('            "HomeLon" : "133.902 E",'))
    print(" ")
    exit()  # Quit the program.


if (
    params._home_lat_val < 0 and not params.optimise_moves
):  # We're in the Southern Hemisphere.
    linelist = [
        "Home Latitude ("
        + str(params._home_lat_val)
        + DEGREE_SYMBOL
        + ") is in the Southern Hemisphere.",
        "NOTE: Pi-lomar may perform an unwinding manoeuvre as targets pass through due North.",
        "      This is normal behaviour, but will pause image capture while it happens.",
        "Consider enabling the OptimiseMoves parameter to prevent this.",
    ]
    TextColor.text_box(linelist, fg=TextColor.YELLOW, bg=TextColor.BLACK)
    # exit() # Quit the program.
if abs(params._home_lat_val) >= 90.0:  # Things break down at the poles.
    linelist = [
        "Home Latitude ("
        + str(params._home_lat_val)
        + DEGREE_SYMBOL
        + ") is at a pole.",
        "Please use the 0" + DEGREE_SYMBOL + " longitude line as due North/South.",
    ]
    TextColor.text_box(linelist, fg=TextColor.YELLOW, bg=TextColor.BLACK)

if params.slew_enabled:  # If allowed to mix full and microsteps, warn the user.
    lines = [
        "SlewEnabled PARAMETER IS ENABLED",
        "The motors can switch between microstepping and full steps",
        "so that the telescope can get into position more quickly.",
        "This is an experimental feature.",
    ]
    TextColor.text_box(lines, fg=TextColor.WHITE, bg=TextColor.ORANGERED1, justify="c")

if params.optimise_moves:  # If allowed to optimise moves, warn the user.
    lines = [
        "OptimiseMoves PARAMETER IS ENABLED",
        "The telescope has more  flexibility  about how it moves.",
        "Take care that continuous rotation in the same direction",
        "may eventually twist the power cables.",
        "It is  recommended  to check the cables are untangled at",
        "the start of each observation session.",
    ]
    TextColor.text_box(lines, fg=TextColor.WHITE, bg=TextColor.ORANGERED1, justify="c")

# Create global timers.
PreviewTimer = Timer(
    period=params.markup_interval
)  # observation_run will generate a Preview image every nnn seconds.

# Colour scheme for displays.
MENU_TITLE_FG = params.menu_title_fg
MENU_TITLE_BG = params.menu_title_bg
MENU_SUBTITLE_FG = params.menu_subtitle_fg
MENU_SUBTITLE_BG = params.menu_subtitle_bg
OSW_TITLE_FG = params.title_fg
OSW_TITLE_BG = params.title_bg
OSW_TEXT_FG = params.text_fg
OSW_TEXT_BG = params.text_bg
OSW_TEXT_GOOD = params.text_good
OSW_TEXT_POOR = params.text_poor
OSW_TEXT_BAD = params.text_bad
OSW_BORDER_FG = params.border_fg
OSW_BORDER_BG = params.border_bg


# Create a timer for the keyboard scanner.
KeyboardTimer = Timer(
    period=params.keyboard_scan_delay
)  # This says how frequently the keyboard is checked for input during observations.


def restart_required():
    lines = [
        "THE PARAMETER FILE HAS BEEN EDITED",
        " ",
        "For safety you must restart the software to make",
        "sure all new values are consistently applied.",
    ]
    TextColor.text_box(lines, fg=TextColor.YELLOW, bg=TextColor.BLACK, justify="c")


def utc_to_local(dt: datetime) -> datetime:
    """Convert a timezone aware datetime into the local timezone.
    Will only convert the timezone if the value is timezone aware.
    If the timezone is missing (naive) then nothing changes."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(pytz.timezone(params.local_tz))
    return dt


def now_local(real=False) -> datetime:  # Many references.
    """Get system clock in local timezone.
    Microcontroller and Skyfield are operated in UTC vales.
    All clock-times used in this program use the UTC timestamped clock.
    But this can return the current timestamp in local time for user displays etc.
    real=True means that no time offset is applied, you get the true realtime clock value.
    real=False means that any time offset is applied, making the clock run at some other point in time.
    """
    dt = utc_to_local(
        now_utc(real=real)
    )  # Offset supported, Convert to local timezone.
    if not real and ClockOffset is not None:  # Can apply time offset.
        dt = dt + timedelta(seconds=ClockOffset)
    return dt


def local_to_utc(dt: datetime) -> datetime:
    """Convert a timezone aware datetime into UTC timezone.
    Will only convert the timezone if the value is timezone aware.
    If the timezone is missing (naive) then nothing changes."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(pytz.timezone("UTC"))
    return dt


date_time = now_utc()
print("Current UTC time is:", date_time)
date_time = utc_to_local(date_time)
print("Local time is:", date_time)

# ///////////////////////////////////////////////////////////////////////////////////
# Trigonometry functions.
# ///////////////////////////////////////////////////////////////////////////////////


def alt_az_to_xyz(
    alt: float, az: float, distance: float = 1.0
) -> Tuple[float, float, float]:
    """Convert alt,az angles to XYZ coordinates. Based upon originlab definition on web.
    X and Y web definitions are swapped to match alignment in Pilomar space."""
    if not type(alt) in [int, float, np.float64]:
        main_log.log(
            "AltAzToXYZ: Received bad alt datatype", alt, type(alt), level="error"
        )
    if not type(az) in [int, float, np.float64]:
        main_log.log(
            "AltAzToXYZ: Received bad az datatype", az, type(az), level="error"
        )
    try:
        y = distance * math.cos(math.radians(alt)) * math.cos(math.radians(az))
        x = distance * math.cos(math.radians(alt)) * math.sin(math.radians(az))
        z = distance * math.sin(math.radians(alt))
    except Exception as e:
        main_log.raise_exception(
            e, comment="AltAzToXYZ"
        )  # Trap all the exception information in the main log file.
    return x, y, z


def xyz_to_alt_az(x: float, y: float, z: float) -> Tuple[float, float]:
    """Convert 3D coordinates into altitude and azimuth."""
    if not type(x) in [int, float, np.float64]:
        main_log.log("XYZToAltAz: Received bad x datatype", x, type(x), level="error")
    if not type(y) in [int, float, np.float64]:
        main_log.log("XYZToAltAz: Received bad y datatype", y, type(y), level="error")
    if not type(z) in [int, float, np.float64]:
        main_log.log("XYZToAltAz: Received bad z datatype", z, type(z), level="error")
    try:
        r = math.sqrt(x * x + y * y)
        alt = math.degrees(math.atan2(z, r))
        az = math.degrees(math.atan2(x, y)) % 360
    except Exception as e:
        main_log.raise_exception(
            e, comment="XYZToAltAz"
        )  # Trap all the exception information in the main log file.
    return alt, az


def relative_alt_az(star_alt, star_az, look_at_alt, look_at_az):
    """Calculate the angles of a star relative to some look-at position.
    There will be some wonderfully clever maths to do this cleanly, quickly and precisely.
    But this was developed with trial and error, and it works well enough for me and is modifiable as required.
    """
    plot_x, plot_y, plot_z = alt_az_to_xyz(
        star_alt, star_az
    )  # Place star on celestial sphere (unit 1)

    # Swing round to LOOK-AT Azimuth.
    new_y = plot_y * math.cos(math.radians(-1 * look_at_az)) - plot_x * math.sin(
        math.radians(-1 * look_at_az)
    )  # 0degrees is due north on Y axis. 90degrees is due east on X axis.
    new_x = plot_x * math.cos(math.radians(-1 * look_at_az)) + plot_y * math.sin(
        math.radians(-1 * look_at_az)
    )
    plot_x = new_x
    plot_y = new_y

    # Drop down to LOOK-AT Altitude.
    new_y = plot_y * math.cos(math.radians(-1 * look_at_alt)) - plot_z * math.sin(
        math.radians(-1 * look_at_alt)
    )  # 0degrees is due north on Y axis. 90degrees is straight up on Z axis.
    new_z = plot_z * math.cos(math.radians(-1 * look_at_alt)) + plot_y * math.sin(
        math.radians(-1 * look_at_alt)
    )
    plot_y = new_y
    plot_z = new_z

    plot_star_alt, plot_star_az = xyz_to_alt_az(
        plot_x, plot_y, plot_z
    )  # Convert from an x,y,z location back into Alt/Az combination.
    # Clip result to +/- 180Degrees because we're relative to the 'centre' of the map we're drawing.
    plot_star_az = plot_star_az % 360
    if plot_star_az > 180:
        plot_star_az -= 360
    plot_star_alt = plot_star_alt % 360
    if plot_star_alt > 180:
        plot_star_alt -= 360
    return plot_star_alt, plot_star_az


def calculate_vector(from_x, from_y, to_x, to_y):
    """Return ANGLE and PIXEL DISTANCE from 1 point to another."""
    x_dist = to_x - from_x
    y_dist = to_y - from_y
    pix_dist = round(math.sqrt((x_dist**2) + (y_dist**2)), 0)
    pix_angle = round(math.degrees(math.atan2(x_dist, y_dist)), 0)
    return pix_dist, pix_angle


def distortion_table_index(pix_dist, pix_angle):
    """Given DISTANCE and ANGLE values, calculate the index to the lens distortion table."""
    dist_range = round(pix_dist / 50, 0) * 50  # Nearest 50 pixels.
    angle_range = round(pix_angle / 5, 0) * 5  # Nearest 5 degrees.
    return dist_range, angle_range


def vector_to_pixel(FromX, FromY, PixDist, PixAngle):
    """Given ANGLE and PIXEL DISTANCE from 1 point, return the resulting point."""
    rad = math.radians(PixAngle)
    ToX = PixDist * math.sin(rad) + FromX
    ToY = PixDist * math.cos(rad) + FromY
    return int(ToX), int(ToY)


def pixel_to_centre_vector(ToX, ToY, width, height):
    """Given any pixel location in an image, return its vector relative to the centre of the image."""
    PixDist, PixAngle = calculate_vector(int(width / 2), int(height / 2), ToX, ToY)
    return PixDist, PixAngle


def convert_arcseconds_to_pixels(arcseconds):
    """Convert an arcsecond value into a pixel count.
    Used for calculating the size of objects in an image."""
    return arcseconds * camera_in_use.pixels_per_fov_degree_width / 3600


def plot_relative_alt_az(PlotStarAlt, PlotStarAz, height, width):
    """Given a relative altitude and azimuth, return the X,Y co-ordinates on the image of dimensions (height*width)
    PlotStarAlt = +/- degrees from the centre of the image.
    PlotStarAz = +/- degrees from the centre of the image.
    height = pixel height of the image.
    width = pixel width of the image.
    applydistortion = Position will be modified to simulate lens distortion."""
    # Convert relative AltAz to a location on an image.
    try:
        TempStarX = int(
            (width / 2) + (PlotStarAz * camera_in_use.pixels_per_fov_degree_width)
        )  # Raw position
        TempStarY = int(
            (height / 2) - (PlotStarAlt * camera_in_use.pixels_per_fov_degree_height)
        )  # SUBTRACT rather than ADD because Y axis in image counts down from the top, whereas ALTITUDE counts up from the bottom.
    except Exception as e:
        main_log.raise_exception(
            e, comment="plot_relative_alt_az"
        )  # Trap all the exception information in the main log file.
    return TempStarX, TempStarY


print(
    TextColor.yellow(
        "Python3 is UTF-8 compliant, make sure that the terminal is in UTF-8 mode too."
    )
)


def az_alt_text(az, alt, symbol=None) -> str:
    """Return standardised string of Altitude and Azimuth coordinates."""
    if symbol is None:
        symbol = DEGREE_SYMBOL
    return "az: " + deg_3dp(az) + symbol + " alt: " + deg_3dp(alt) + symbol


def ra_dec_text(radeg, decdeg, symbol=None):
    th, tm, ts = angle_to_hms(radeg)  # Convert deg to hms.
    temp = display_hms(th, tm, ts).strip()  # Convert to string.
    return "RA: " + temp + " Dec: " + deg_3dp(decdeg) + symbol  # Return entire string.


def get_terminal_size():
    """Return tuple of the current screen dimensions. (cols,rows)
    This is used to dynamically build the observation_run display.
    More information can be shown if the screen is large enough,
    but the system still works on a relatively small display space."""
    return TextColor.terminalsize()  # returns (cols,rows)


# sd_card_monitor = discmonitor(name='root',devname='/dev/root',path='/',disk_type='boot',logger=main_log.log) # Create new disc space monitor for the SD card.
sd_card_monitor = DiskMonitor(
    name="root",
    devname="/dev/root",
    path=params.sd_path,
    disk_type="boot",
    logger=main_log.log,
)  # Create new disc space monitor for the SD card.
main_log.log(
    "Defaulting to SD card for images.", sd_card_monitor.df_path, terminal=False
)  # Default to SD card for images unless we then find a USB storage device.
ImageStorageMonitor = (
    sd_card_monitor  # Point to the SD card storage when checking available space.
)


# Use discmonitor to find any potential USB memory too.
def choose_usb_memory():
    """If a USB memory stick is attached, find it."""
    usbdev = None  # Default USB memory device.
    UsbList = sd_card_monitor.list_us_bdevices()  # List all the potential devices.
    for dn, dl in UsbList:
        main_log.log("ChooseUSBMemory: Considering:", dn, dl, terminal=False)
        if (
            dl in sd_card_monitor.usb_alarm_labels
        ):  # This device signifies a problem! Proceed no further.
            main_log.log(
                "ChooseUSBMemory: Suspect the microcontroller is also connected via USB (",
                dn,
                dl,
                ").",
                terminal=False,
            )
        else:
            main_log.log("ChooseUSBMemory: Selecting:", dn, dl, terminal=False)
            usbdev = dn  # Try this device as the USB memory.
    main_log.log("ChooseUSBMemory: Chosen", usbdev, terminal=False)
    return usbdev


# Try to create a disc monitor for any attached USB memory.
try:
    usbdev = choose_usb_memory()
    usb_disc_monitor = DiskMonitor(
        name="usb",
        devname=usbdev,
        path=params.usb_path,
        disk_type=DiskType.USB,
        logger=main_log.log,
    )  # Create USB memory card monitor (if it exists).
    # Decide which of the two above monitors will be the one that images are stored in. Create a pointer to that one for the status monitoring later on.
    if params.use_usb_storage and usb_disc_monitor.drive_available:
        main_log.log(
            "Switching to USB storage for images.",
            usb_disc_monitor.df_path,
            terminal=False,
        )
        ImageStorageMonitor = (
            usb_disc_monitor  # Point to USB storage when checking available space.
        )
except Exception as exp:  # Failed to create usb_disc_monitor. could be many reasons.
    main_log.report_exception(
        exp,
        comment="Failed to create usb_disc_monitor. a suitable USB device was not successfully selected.",
    )
    ImageStorageMonitor = (
        usb_disc_monitor  # Point to USB storage when checking available space.
    )
except Exception as exp:  # Failed to create usb_disc_monitor. could be many reasons.
    main_log.report_exception(
        exp,
        comment="Failed to create usb_disc_monitor. a suitable USB device was not successfully selected.",
    )
    textlist = [
        "usb_disc_monitor can fail for many reasons.",
        "Common causes are:",
        "1) USB device is not formatted suitably.",
        "2) USB device does not have a suitable volume name.",
        "   'USBMEMORY' is expected.",
        "3) USB memory may be mounted in an unexpected path.",
        "   '/media/pi' is expected.",
        " ",
        "The log file will show which devices were considered.",
    ]
    TextColor.text_box(textlist, fg=TextColor.ORANGERED1, bg=TextColor.BLACK)

main_log.log("Image storage:", ImageStorageMonitor.DfPath, terminal=True)


def recheck_disc():
    """This will reset/recheck disc availability.
    Useful if USB memory stick didn't mount first time, or if it's added while the system's running.
    """
    global sd_card_monitor
    global usb_disc_monitor
    global ImageStorageMonitor
    sd_card_monitor = DiskMonitor(
        name="root",
        devname="/dev/root",
        path="/",
        disk_type=DiskType.BOOT,
        logger=main_log.log,
    )  # Create new disc space monitor for the SD card.
    usbdev = choose_usb_memory()
    usb_disc_monitor = DiskMonitor(
        name="usb",
        devname=usbdev,
        path="/media/pi",
        disk_type=DiskType.USB,
        logger=main_log.log,
    )  # Create USB memory card monitor (if it exists).
    # Decide which of the two above monitors will be the one that images are stored in. Create a pointer to that one for the status monitoring later on.
    if params.use_usb_storage and usb_disc_monitor.drive_available:
        main_log.log(
            "RecheckDisc: Using USB storage for images.",
            usb_disc_monitor.df_path,
            terminal=True,
        )
        ImageStorageMonitor = (
            usb_disc_monitor  # Point to USB storage when checking available space.
        )
    else:
        main_log.log(
            "RecheckDisc: Using SD card for images.",
            sd_card_monitor.df_path,
            terminal=True,
        )
        ImageStorageMonitor = sd_card_monitor  # Point to the SD card storage when checking available space.
    return True


def is_float(text) -> bool:
    """Return TRUE if a string can be converted to a float value."""
    try:
        _ = float(text)
        return True
    except ValueError:
        return False


def is_int(text) -> bool:
    """Return TRUE if a string can be converted to an integer value."""
    try:
        _ = int(text)
        return True
    except ValueError:
        return False


def text_to_int(text) -> int:
    """Convert a character string into an INTEGER value.
    Returns None if it can't be done."""
    try:
        a = int(text)
    except ValueError:
        a = None
    return a


def text_to_float(text) -> float:
    """Convert a character string into a FLOAT value.
    Returns None if it can't be done."""
    try:
        a = float(text)
    except ValueError:
        a = None
    return a


def verify_folder(FN):
    """Check that all directorys in the list exist.
    If they don't create them."""
    result = False
    try:
        if FN[-1:] == "/":
            FN = FN[:-1]  # Remove trailing directory separator if found.
        if os.path.isdir(FN):  # Directory exists already.
            main_log.log("VerifyFolder: Found", FN, terminal=False)
        else:
            main_log.log("VerifyFolder: Missing", FN, terminal=False)
            cmd = "mkdir " + FN  # Create the directory.
            osCmd(cmd)
            cmd = (
                "chown pi:pi " + FN
            )  # Make sure that the directory's owner is the pi user.
            osCmd(cmd)
            cmd = "chmod +w " + FN  # Make sure there is write access to the directory.
            osCmd(cmd)
            result = True
    except Exception as e:
        main_log.report_exception(
            e, comment="VerifyFolder"
        )  # Trap all the exception information in the main log file.
    return result


def define_session_folders(campaign_name, exposure=None):
    """Given a campaign name, generate the hierarchy of folders for this specific observation session.
    /home/pi/pilomar/
           campaign_{name}_{exposure}/
                   session_{timestamp}/
                             dark/ # Dark images stored here.
                             light/ # Light images stored here.
                             flat/ # Flat images stored here.
                             darkflat/ # Dark Flat images stored here.
                             bias/ # Bias images stored here.
                             preview/ # Preview images stored here.
                             tracking/ # Tracking images stored here.
    If exposure time is provided as 2nd parameter it is combined into the campaign folder name.
    """
    # FolderHandler :-
    sessionvalue = "session_" + utc_time_stamp()
    if exposure is None:  # No exposure, so don't include it in the campaign name.
        campaign = (
            "campaign_" + campaign_name + "/"
        )  # Folder specific to the campaign (the target). All images related to the campaign are stored here.
    else:  # We know the exposure, so include it in the campaign name.
        campaign = (
            "campaign_" + campaign_name + "_e" + str(exposure) + "s/"
        )  # Folder specific to the campaign (the target). All images related to the campaign are stored here.
    # session = campaign + "session_" + utc_time_stamp() + "/" # Folder specific to the current batch of photos being taken.
    campaignvalue = campaign
    FolderHandler.new_session(
        campaign=campaignvalue, session=sessionvalue
    )  # Update folder structures for the current target and session.


def ask_yes_no(text, default=True, fg=None, bg=None):
    """Ask any question that needs a simple Y/N answer.
    Returns logical value ('yes' or 'true' returns True, 'no' or 'false' returns False)
    Returns default value if user just presses ENTER.
    Ignores 2nd and subsequent characters.
    Rejects all other input."""
    while True:  # Loop until a satisfactory answer is given.
        if fg is None:  # Use default color.
            temp = input(
                TextColor.cyan(text.strip() + " ")
            )  # Ensure 1 character space between text and response cursor.
        else:
            temp = input(TextColor.fgbgcolor(fg, bg, text.strip() + " "))
        if len(temp) == 0:
            result = default
            break
        elif temp.lower()[0] in ["n"]:  # FALSE and NO recognised.
            result = False
            break
        elif temp.lower()[0] in ["y"]:  # TRUE and YES recognised.
            result = True
            break
        print(TextColor.red("? " + str(temp) + " ?"))
        if default:
            print(TextColor.red("Please answer yes, no or [ENTER]=(YES)"))
        else:
            print(TextColor.red("Please answer yes, no or [ENTER]=(NO)"))
    return result


if params.use_live_location:  # Using live target location to process images and maps.
    main_log.log("Using live target location to align images and maps.", terminal=False)
else:  # Using last reported camera location to process images and maps.
    main_log.log(
        "Using last reported camera location to align images and maps.", terminal=False
    )

# Create 3 window columns. The sub-windows for the dashboard will be automatically stacked in these three columns.
ColorDisplay.add_color_display_entry(colwidth=87, startcol=1)
ColorDisplay.add_color_display_entry(colwidth=80, startcol=None)
ColorDisplay.add_color_display_entry(colwidth=55, startcol=None)

observation_status_window = ColorDisplay(
    rows=14,
    cdlayout=0,
    name="OSW",
    fg=OSW_TEXT_FG,
    bg=OSW_TEXT_BG,
    titlefg=OSW_TITLE_FG,
    titlebg=OSW_TITLE_BG,
    title="Observation status " + ProgramTitle.upper() + " " + VERSION,
)  # This is the text window that displays current progress of an observation.
observation_status_window.draw_border = True  # Draw border around window.
observation_status_window.set_border_colors(
    OSW_BORDER_FG, OSW_BORDER_BG
)  # Set border colors.
# Clip the display if the terminal area is insufficient. This means we see at least something.
observation_status_window.clip_window = True
observation_status_window.place_string(
    "           Target: [TARGET                                                           ]",
    row=1,
    col=0,
)
observation_status_window.place_string(
    "   Session folder: [FOLDER                                                           ]",
    row=2,
    col=0,
)
observation_status_window.place_string(
    "   Tracking clock: [CLOCK                    ]UTC Duration: [DURATION         ]       ",
    row=3,
    col=0,
)
observation_status_window.place_string(
    "Storage available: [STORAGE               ]    Image types: [IMAGETYPES             ] ",
    row=5,
    col=0,
)
observation_status_window.place_string(
    "   Camera Enabled: [CEN ] Exposure: [EXP       ] Timelapse: [TLAPSE   ] Capture:[FAST]",
    row=6,
    col=0,
)
observation_status_window.place_string(
    "   OnChip cleanup: [OCC ]                     Control mode: [CMODE           ]        ",
    row=7,
    col=0,
)
observation_status_window.place_string(
    "    Target status: [TSTATUS] [TSDESC                                                 ]",
    row=8,
    col=0,
)
observation_status_window.place_string(
    "                                                                                      ",
    row=9,
    col=0,
)
observation_status_window.place_string(
    "Camera: Latest azimuth: [CAMAZ        ]          Latest altitude: [CAMALT       ]     ",
    row=10,
    col=0,
)
observation_status_window.place_string(
    "     Estimated azimuth: [ESTAZ        ]       Estimated altitude: [ESTALT       ]     ",
    row=11,
    col=0,
)
observation_status_window.place_string(
    "Target:        Azimuth: [TARAZ        ] [COMP]          Altitude: [TARALT       ]     ",
    row=12,
    col=0,
)
observation_status_window.place_string(
    "                    RA: [RA                  ]       Declination: [DEC          ]     ",
    row=13,
    col=0,
)
observation_status_window.scan_for_fields()  # Scan the current image for field markers.
swFields = observation_status_window.list_fields()  # Colour the data fields.
for key, value in swFields.items():
    observation_status_window.field_color(key, fg=OSW_TEXT_GOOD, bg=OSW_TEXT_BG)
observation_status_window.field_color("TSDESC", fg=OSW_TEXT_FG, bg=OSW_TEXT_BG)
observation_status_window.field_color("ESTAZ", fg=OSW_TEXT_FG, bg=OSW_TEXT_BG)
observation_status_window.field_color("ESTALT", fg=OSW_TEXT_FG, bg=OSW_TEXT_BG)
observation_status_window.set_default()  # Store this 'blank' template to be reused when clearing the display.

PrintColorList = [
    OSW_TEXT_FG,
    OSW_TEXT_GOOD,
]  # Scrolling text windows use alternating colors for each line to aid readability in busy displays.

# Define some debugging windows. These appear when the terminal window is maximised.

# - The SESSION WINDOW shows the condition of the RPi <> Microcontroller control.
SessionWindow = ColorDisplay(
    rows=12,
    cdlayout=1,
    name="SESSION",
    fg=OSW_TEXT_FG,
    bg=OSW_TEXT_BG,
    titlefg=OSW_TITLE_FG,
    titlebg=OSW_TITLE_BG,
    title="Communication status",
)
SessionWindow.clip_window = True  # Allow the display to be clipped if there's not enough terminal space available for the entire display.
SessionWindow.draw_border = True  # Draw border around window.
SessionWindow.set_border_colors(OSW_BORDER_FG, OSW_BORDER_BG)  # Set border colors.
#                                    1         2         3         4         5         6         7
#                          0123456789012345678901234567890123456789012345678901234567890123456789012345678
SessionWindow.place_string(
    "  Messages:Rx queued:[RQ]     Rx tot:[RT   ]       Tx queued:[TQ] Tx tot:[TT  ]",
    row=1,
    col=0,
)
SessionWindow.place_string(
    "     State:   Resets:[SR]    DevFail:[DF ]           Last Rx:[LR         ]     ",
    row=2,
    col=0,
)
SessionWindow.place_string(
    " RPi Bytes:Rx:[BX    ]            Tx:[TX    ]         RxErrs:[RE]              ",
    row=3,
    col=0,
)
SessionWindow.place_string(
    "MCtl Bytes:Rx:[MRX   ] [MRXR ]    Tx:[MTX   ] [MTXR ] RxErrs:[R2] TxDrops:[TD] ",
    row=4,
    col=0,
)
SessionWindow.place_string(
    "      MCtl:  AutoCtl:[AC ]        RemCtl:[RCL]        ClkSyn:[CS ] Exc:[EXCEPT]",
    row=5,
    col=0,
)
SessionWindow.place_string(
    "            Restarts:Forced:[FR]  Remote:[RR]          Alive:[ALIVE    ]       ",
    row=6,
    col=0,
)
SessionWindow.place_string(
    "   azimuth:Conf:[ZC ]     Angle:[ZA     ] [CAZA  ]  OnTarget:[ZT ] [ZDPS    ]/s",
    row=7,
    col=0,
)
SessionWindow.place_string(
    "                [ZMODE           ]:[ZD]   Expires:[ZU    ] UTC [ZRM         ]  ",
    row=8,
    col=0,
)
SessionWindow.place_string(
    "  altitude:Conf:[LC ]     Angle:[LA     ] [CALTA ]  OnTarget:[LT ] [LDPS    ]/s",
    row=9,
    col=0,
)
SessionWindow.place_string(
    "                [LMODE           ]:[LD]   Expires:[LU    ] UTC [LRM         ]  ",
    row=10,
    col=0,
)
SessionWindow.place_string(
    "   Traj.flushes:[MTSF ]   Clk diff:[CLKDIF      ] Connection:[CMODE           ]",
    row=11,
    col=0,
)
SessionWindow.scan_for_fields()  # Scan the current image for field markers.
swFields = SessionWindow.list_fields()
for key, value in swFields.items():
    SessionWindow.field_color(key, fg=OSW_TEXT_GOOD, bg=OSW_TEXT_BG)
SessionWindow.field_format("ZDPS", justify="right")
SessionWindow.field_format("LDPS", justify="right")
for i in [
    "SR",
    "RE",
    "R2",
    "FR",
    "RR",
]:  # Set range colours on some fields to automatically color as the value changes.
    if not SessionWindow.initialize_color_range(
        i,
        badfg=OSW_TEXT_BAD,
        badbg=OSW_TEXT_BG,
        poorfg=OSW_TEXT_POOR,
        poorbg=OSW_TEXT_BG,
    ):
        main_log.log(
            "Unable to SetFieldColorRange for", i, "in SessionWindow.", level="error"
        )
SessionWindow.set_default()  # Store this 'blank' template to be reused when clearing the display.

# - The MICROCONTROLLER RX WINDOW shows the latest messages received from the microcontroller.
MctlRxWindow = ColorDisplay(
    rows=17,
    cdlayout=1,
    name="MCTLRX",
    fg=PrintColorList,
    bg=OSW_TEXT_BG,
    titlefg=OSW_TITLE_FG,
    titlebg=OSW_TITLE_BG,
    title="Receive from microcontroller",
)
MctlRxWindow.clip_window = True  # Allow the display to be clipped if there's not enough terminal space available for the entire display.
MctlRxWindow.draw_border = True  # Draw border around window.
MctlRxWindow.set_border_colors(OSW_BORDER_FG, OSW_BORDER_BG)  # Set border colors.

# - The MICROCONTROLLER TX WINDOW shows the latest messages sent to the microcontroller.
MctlTxWindow = ColorDisplay(
    rows=13,
    cdlayout=1,
    name="MCTLTX",
    fg=PrintColorList,
    bg=OSW_TEXT_BG,
    titlefg=OSW_TITLE_FG,
    titlebg=OSW_TITLE_BG,
    title="Transmit to microcontroller",
)
MctlTxWindow.clip_window = True  # Allow the display to be clipped if there's not enough terminal space available for the entire display.
MctlTxWindow.draw_border = True  # Draw border around window.
MctlTxWindow.set_border_colors(OSW_BORDER_FG, OSW_BORDER_BG)  # Set border colors.

# - The CAMERA WINDOW shows the activities of the CAMERA THREAD which runs separately to the main thread of the software.
CameraWindow = ColorDisplay(
    rows=11,
    cdlayout=2,
    name="CAMERA",
    fg=PrintColorList,
    bg=OSW_TEXT_BG,
    titlefg=OSW_TITLE_FG,
    titlebg=OSW_TITLE_BG,
    title="Camera events",
)
CameraWindow.clip_window = True  # Allow the display to be clipped if there's not enough terminal space available for the entire display.
CameraWindow.draw_border = True  # Draw border around window.
CameraWindow.set_border_colors(OSW_BORDER_FG, OSW_BORDER_BG)  # Set border colors.

image_status_window = ColorDisplay(
    rows=9,
    cdlayout=0,
    name="IMAGE",
    fg=OSW_TEXT_FG,
    bg=OSW_TEXT_BG,
    titlefg=OSW_TITLE_FG,
    titlebg=OSW_TITLE_BG,
    title="Image Status",
)
image_status_window.clip_window = True  # Allow the display to be clipped if there's not enough terminal space available for the entire display.
image_status_window.draw_border = True  # Draw border around window.
image_status_window.set_border_colors(
    OSW_BORDER_FG, OSW_BORDER_BG
)  # Set border colors.
# This is the text window that displays image and tracking progress of an observation.
image_status_window.place_string(
    "       Capture state: [CAMERASTATE   ][STATETIMES       ] UTC [STATEAGE           ]   ",
    row=1,
    col=0,
)
image_status_window.place_string(
    "        Image buffer: [OCVIB                            ] Camera task: [CTASK     ]   ",
    row=2,
    col=0,
)
image_status_window.place_string(
    "  Drift target image: [DTI                                                        ]   ",
    row=3,
    col=0,
)
image_status_window.place_string(
    "  Drift latest image: [DLI                                                        ]   ",
    row=4,
    col=0,
)
image_status_window.place_string(
    " Last azimuth tuning: [LAZT                                                       ]   ",
    row=5,
    col=0,
)
image_status_window.place_string(
    "Last altitude tuning: [LALT                                                       ]   ",
    row=6,
    col=0,
)
image_status_window.place_string(
    "      Session images: [IMAGES                                                     ]   ",
    row=7,
    col=0,
)
image_status_window.place_string(
    "   Current image run: [RUN                  ] Acc:[ACCTIME  ] ETA:[ETA           ] UTC",
    row=8,
    col=0,
)

image_status_window.scan_for_fields()  # Scan the current image for field markers.
image_status_window.field_format("CTASK", justify="center")
swFields = image_status_window.list_fields()
for key, value in swFields.items():
    image_status_window.field_color(key, fg=OSW_TEXT_GOOD, bg=OSW_TEXT_BG)
image_status_window.set_default()  # Store this 'blank' template to be reused when clearing the display.

instruction_window = ColorDisplay(
    rows=3,
    cdlayout=0,
    fg=PrintColorList,
    bg=OSW_TEXT_BG,
    titlefg=OSW_TITLE_FG,
    titlebg=OSW_TITLE_BG,
    title="Commands",
)
# Instruction summary window.
#                             '12345678901234567890123456789012345678901234567890123456789012345678901234567890123456'
instruction_window.place_string(
    "  [r]Refresh    [t]Tracking on/off     [p]Preview      [m]Menu      [d]Debug on/off   ",
    row=1,
    col=0,
)
instruction_window.place_string(
    "  [+]/[-]Exposure                                                   [x]Quit           ",
    row=2,
    col=0,
)
instruction_window.clip_window = True  # Allow the display to be clipped if there's not enough terminal space available for the entire display.
instruction_window.set_border_colors(OSW_BORDER_FG, OSW_BORDER_BG)  # Set border colors.
instruction_window.draw_border = True  # Draw border around window.

# - The ERROR WINDOW shows any error messages raised by the software.
error_window = ColorDisplay(
    rows=6,
    cdlayout=0,
    name="ERROR",
    fg=PrintColorList,
    bg=OSW_TEXT_BG,
    titlefg=OSW_TITLE_FG,
    titlebg=OSW_TITLE_BG,
    title="Error messages",
)
error_window.clip_window = True  # Allow the display to be clipped if there's not enough terminal space available for the entire display.
error_window.draw_border = True  # Draw border around window.
error_window.set_border_colors(OSW_BORDER_FG, OSW_BORDER_BG)  # Set border colors.

# General purpose window where developer messages can be written during observations.
DevWindow = ColorDisplay(
    rows=8,
    cdlayout=0,
    name="DEVELOPER",
    fg=PrintColorList,
    bg=OSW_TEXT_BG,
    titlefg=OSW_TITLE_FG,
    titlebg=OSW_TITLE_BG,
    title="Developer events",
)
DevWindow.clip_window = True  # Allow the display to be clipped if there's not enough terminal space available for the entire display.
DevWindow.draw_border = True  # Draw border around window.
DevWindow.set_border_colors(OSW_BORDER_FG, OSW_BORDER_BG)  # Set border colors.

# - The LOG objects can be told to output error messages to a specific window too.
main_log.error_window = error_window  # Tell the MAIN logging mechanism that error messages can be replicated to the ERROR WINDOW.
cam_log.error_window = CameraWindow  # Tell the CAMERA logging mechanism that error messages can be replicated to the CAMERA WINDOW.
# - Drift tracker debugging window.
# Events and decisions made by the drift tracking routine.
DriftWindow = ColorDisplay(
    rows=10,
    cdlayout=2,
    name="DRIFT",
    fg=PrintColorList,
    bg=OSW_TEXT_BG,
    titlefg=OSW_TITLE_FG,
    titlebg=OSW_TITLE_BG,
    title="Drift tracking",
)
DriftWindow.clip_window = True  # Allow the display to be clipped if there's not enough terminal space available for the entire display.
DriftWindow.draw_border = True  # Draw border around window.
DriftWindow.set_border_colors(OSW_BORDER_FG, OSW_BORDER_BG)  # Set border colors.
# - Camera thread communications windows.
# Window showing communication from the camera handler thread to the main observation routine.
CameraRxWindow = ColorDisplay(
    rows=10,
    cdlayout=2,
    name="CAMERARX",
    fg=PrintColorList,
    bg=OSW_TEXT_BG,
    titlefg=OSW_TITLE_FG,
    titlebg=OSW_TITLE_BG,
    title="Receive from camera handler",
)
CameraRxWindow.clip_window = True  # Allow the display to be clipped if there's not enough terminal space available for the entire display.
CameraRxWindow.draw_border = True  # Draw border around window.
CameraRxWindow.set_border_colors(OSW_BORDER_FG, OSW_BORDER_BG)  # Set border colors.
# Window showing communications sent TO the camera handler from the main observation routine.
CameraTxWindow = ColorDisplay(
    rows=10,
    cdlayout=2,
    name="CAMERATX",
    fg=PrintColorList,
    bg=OSW_TEXT_BG,
    titlefg=OSW_TITLE_FG,
    titlebg=OSW_TITLE_BG,
    title="Transmit to camera handler",
)
CameraTxWindow.clip_window = True  # Allow the display to be clipped if there's not enough terminal space available for the entire display.
CameraTxWindow.draw_border = True  # Draw border around window.
CameraTxWindow.set_border_colors(OSW_BORDER_FG, OSW_BORDER_BG)  # Set border colors.

# All windows are defined. Turn on the 'reduceio' feature in them all.
ColorDisplay.global_reduce_io(
    True
)  # When redrawing windows, only the changed lines are repainted.


FolderHandler = FolderHandler(
    projectroot=ProjectRoot, logger=main_log
)  # Create FolderHandler instance. Defines folder structures and creates them as needed.

# ///////////////////////////////////////////////////////////////////////////////////
# Camera assets.
# ///////////////////////////////////////////////////////////////////////////////////

# Create camera related objects.
# Parameters taken from https://www.seeedstudio.com/blog/2020/06/18/a-complete-guide-to-help-you-choose-lenses-for-your-raspberry-pi-high-quality-camera-m/
# RPiHQ16mm
#    Lens Length = 16.0 # Official lens focal length.
#    Lens horizontal field of view 21.8 degrees.
#    Lens vertical field of view 16.4 degrees.
# Arducam50mm
#    Lens Length = 50.0 # Official lens focal length.
#    Lens horizontal field of view 7.0 degrees.
#    Lens vertical field of view 5.2 degrees.
# Sensor image width 4056 pixels
# Sensor image height 3040 pixels
lens_in_use = AstroLens(
    length=params.lens_length,
    horizontal_fov=params.lens_horizontal_fov,
    vertical_fov=params.lens_vertical_fov,
    logger=cam_log,
    parameters=params,
)
lens_in_use.error_window = (
    error_window  # Point LensInUse to a window for displaying error messages.
)
lens_in_use.camera_window = (
    CameraWindow  # Point LensInUse to a window for displaying camera events.
)
sensor_in_use = AstroSensor(
    sensor_type=params.sensor_type, logger=cam_log, parameters=params
)
sensor_in_use.error_window = (
    error_window  # Point SensorInUse to a window for displaying error messages.
)
sensor_in_use.camera_window = (
    CameraWindow  # Point SensorInUse to a window for displaying camera events.
)
camera_in_use = AstroCamera(
    inp_sensor=sensor_in_use,
    inp_lens=lens_in_use,
    exposure=10.0,
    trackingexposure=params.tracking_exposure_seconds,
    logger=cam_log,
    parameters=params,
)
camera_in_use.error_window = (
    error_window  # Point CameraInUse to a window for displaying error messages.
)
camera_in_use.camera_window = (
    CameraWindow  # Point CameraInUse to a window for displaying camera events.
)
camera_in_use.storage_monitor = ImageStorageMonitor  # Point CameraInUse to the ImageStorageMonitor instance to check available storage.
AstroCamera.set_global_folder_handler(
    FolderHandler
)  # Update all the declared cameras with the latest copy of FolderHandler. This doesn't need explicitly refreshing if target changes.
AstroCamera.set_global_keyboard(
    Keyboard
)  # Point the cameras to the keyboard handler (to allow user to interrupt processes).

# Summarise camera settings...
CameraWindow.print(
    "Lens:", lens_in_use.length, "mm (35mm equiv.", lens_in_use.equiv_length, "mm)"
)
CameraWindow.print(
    "Lens: FoV:",
    str(lens_in_use.fov_horizontal) + DEGREE_SYMBOL,
    "*",
    str(lens_in_use.fov_vertical) + DEGREE_SYMBOL,
)
CameraWindow.print(
    "Sensor: Width",
    sensor_in_use.pixel_width,
    "* Height",
    sensor_in_use.pixel_height,
    "pixels",
)

# ----------------------------------------------------------------------------------------------------


def detect_raspistill(canenable=False, candisable=False):
    """Test to see if the camera is connected and active via raspistill.
    This is used in BUSTER operating system builds.
    candisable = True: If the camera is not found, then automatically disable it in parameters.
    canenable = True: If the camera is found, then automatically enable it in parameters.
    """
    filename = (
        ProjectRoot + "/temp/testraspistill.jpg"
    )  # Or use /dev/null ? We don't need this file.
    # Remove any earlier copy of the file.
    tempcmd = "rm " + filename
    _ = osCmd(tempcmd)
    tempcmd = "raspistill -o " + filename  # Simple command to test the camera.
    main_log.log("DetectRaspistill:", tempcmd, terminal=False)
    templist = osCmd(tempcmd)
    if os.path.exists(filename):  # file exists so assume camera is available.
        tempresult = True
    else:  # file doesn't exist, so assume camera is unavailable.
        tempresult = False
    if tempresult:  # Camera appears to be working.
        if params.camera_enabled:  # Camera is enabled and available.
            main_log.log("Camera is accessible and enabled.", terminal=False)
        else:  # Camera is available but not accessible. Warn that it will need to be enabled from the menu.
            if canenable:
                params.camera_enabled = True
                main_log.log("Camera has been automatically enabled.", level="warning")
            else:
                main_log.log(
                    "Camera is accessible, but disabled. You can enable it from the Camera Tools menu."
                )
    else:  # Camera does not appear to be available.
        main_log.log("DetectRaspistill: Camera not found.", level="warning")
        if candisable:
            if (
                params.camera_enabled
            ):  # Warn the user that the camera is automatically disabled.
                params.camera_enabled = False
                main_log.log("Camera has been automatically disabled.", level="warning")
                main_log.log(
                    "When the camera is available, you can re-enable it from the Camera Tools menu.",
                    level="warning",
                )
    templist = osCmd("rm " + filename)  # Cleanup. Ignore errors.
    main_log.log("DetectRaspistill:", tempresult, terminal=False)
    return tempresult


# ----------------------------------------------------------------------------------------------------


def detect_libcamera(canenable=False, candisable=False):
    """Test to see if the camera is connected and active via libcamera.
    This is used in BOOKWORM operating system builds.
    candisable = True: If the camera is not found, then automatically disable it in parameters.
    canenable = True: If the camera is found, then automatically enable it in parameters.
    """
    filename = (
        ProjectRoot + "/temp/testlibcamera-still.jpg"
    )  # Or use /dev/null ? We don't need this file.
    # Remove any earlier copy of the file.
    tempcmd = "rm " + filename
    _ = osCmd(tempcmd)
    tempcmd = (
        "libcamera-still --output " + filename + " --nopreview --timeout 10"
    )  # Simple command to test the camera.
    main_log.log("DetectLibcamera:", tempcmd, terminal=False)
    templist = osCmd(tempcmd)
    if os.path.exists(filename):  # file exists so assume camera is available.
        tempresult = True
    else:  # file doesn't exist, so assume camera is unavailable.
        tempresult = False
    if tempresult:  # Camera appears to be working.
        if params.camera_enabled:  # Camera is enabled and available.
            main_log.log("Camera is accessible and enabled.", terminal=False)
        else:  # Camera is available but not accessible. Warn that it will need to be enabled from the menu.
            if canenable:
                params.camera_enabled = True
                main_log.log("Camera has been automatically enabled.", level="warning")
            else:
                main_log.log(
                    "Camera is accessible, but disabled. You can enable it from the Camera Tools menu."
                )
    else:  # Camera does not appear to be available.
        main_log.log("DetectLibcamera: Camera not found.", level="warning")
        if candisable:
            if (
                params.camera_enabled
            ):  # Warn the user that the camera is automatically disabled.
                params.camera_enabled = False
                main_log.log("Camera has been automatically disabled.", level="warning")
                main_log.log(
                    "When the camera is available, you can re-enable it from the Camera Tools menu.",
                    level="warning",
                )
    templist = osCmd("rm " + filename)  # Cleanup. Ignore errors.
    main_log.log("DetectLibcamera:", tempresult, terminal=False)
    return tempresult


# ----------------------------------------------------------------------------------------------------


def detect_camera(canenable=False, candisable=False):
    """Test for presence of a camera via raspistill or libcamera."""
    if params.camera_driver == "raspistill":  # if OS_name in ['buster']:
        return detect_raspistill(canenable=canenable, candisable=candisable)
    else:  # Expect libcamera.
        return detect_libcamera(canenable=canenable, candisable=candisable)


# ----------------------------------------------------------------------------------------------------


def auto_detect_camera():
    """This tests the telescope camera.
    If found, it enables the camera.
    If missing, it disables the camera."""
    detect_camera(canenable=True, candisable=True)


# ----------------------------------------------------------------------------------------------------


def calibrate_fov_menu():
    """Use the diameter of the full moon to calibrate the field of view of the lens.
    the moon is a relatively stable known angular diameter in the sky.
    By taking a photograph of the moon and measuring the number of pixels that the
    moon occupies we can work backwards to estimate the field of view of the lens."""
    if check_image_set():  # Only allow a change if the current image set is acceptable.
        camera_in_use.calibrate_fov()
        camera_in_use.set_observation_parameters(
            session
        )  # Set target specific parameters for the camera.
        define_session_folders(
            session.target.name, camera_in_use.exposure_seconds
        )  # This assigns folder names for all the image types.
        document_session()
        DriftTracker.Reset()


# ----------------------------------------------------------------------------------------------------


def camera_enabled_change():
    """Call this when setting CameraEnabled flag.
    It handles some related changes and messages."""
    if params.camera_enabled:
        print(TextColor.green("Camera enabled"))
        main_log.log(
            "The camera can be disabled in the parameters file if you don't want to take actual photographs.",
            terminal=False,
        )
        if (
            params.camera_driver == "raspistill"
        ):  # Only raspistill does this, libcamera handles denoise via the command line.
            if params.disable_cleanup:
                sensor_in_use.disable_cleanup()
            else:
                main_log.log(
                    "NOTE: on-chip cleanup has not changed state.", terminal=True
                )
        if not detect_camera():  # Check there really IS a camera connected!
            main_log.log(
                "camera_enabled_change(): Camera has been enabled. But there is no camera detected. You may get errors.",
                level="error",
            )
    else:
        print(TextColor.red("Camera disabled"))
        main_log.log(
            "The program will generate simulated images instead.", terminal=False
        )
        lines = [
            "The camera is disabled . The program will generate  simulated  images",
            "instead . The simulated images will show approximate  star and target",
            "locations.",
            "Simulated images may take longer to calculate  than a true photograph",
            "would take . Therefore the  telescope  may gather 'light' images more",
            "slowly than you would expect.",
        ]
        TextColor.text_box(lines, fg=TextColor.YELLOW, bg=TextColor.BLACK)


# Check if camera is available.
tempresult = detect_camera(candisable=True)
camera_enabled_change()  # Handle related changes.

# ----------------------------------------------------------------------------------------------------


def enable_camera():
    """This enables the camera, even if it is not installed."""
    params.camera_enabled = True
    main_log.log("Camera has been manually enabled.", level="warning", terminal=True)
    camera_enabled_change()  # Handle related changes.


# ----------------------------------------------------------------------------------------------------


def disable_camera():
    """This disables the camera."""
    params.camera_enabled = False
    main_log.log("Camera has been manually disabled.", level="warning", terminal=True)
    camera_enabled_change()  # Handle related changes.


# ----------------------------------------------------------------------------------------------------

# ///////////////////////////////////////////////////////////////////////////////////
# GPIO setup.
# ///////////////////////////////////////////////////////////////////////////////////

# Use BCM GPIO references instead of physical pin numbers.
# GPIO must be enabled via raspi-config.
# GPIO.setmode(GPIO.BCM)

# Create a stop button.
if params.stop_pin is not None:
    StopButton = inputpin(
        params.stop_pin, "StopButton", pull="up"
    )  # Pin is HIGH by default, must be grounded to trigger.
else:
    StopButton = None
UartControlQueue = (
    Queue()
)  # Command queue to the CommsLoop, use this to shut it down by sending 'stop'.


def initiate_mctl():
    """Start up fresh communication with the microcontroller."""
    main_log.log(
        "Establishing serial UART communication with microcontroller...", terminal=False
    )
    mctl = None
    try:
        if RPiNum in ["3", "4"]:
            mctl = Microcontroller(
                port="/dev/serial0",
                resetpin=params.mctl_reset_pin,
                boardtype=params.board_type,
                logger=main_log,
            )  # Create communication with microcontroller over uart0 serial port.
        else:
            mctl = Microcontroller(
                port="/dev/ttyAMA0",
                resetpin=params.mctl_reset_pin,
                boardtype=params.board_type,
                logger=main_log,
            )  # Create communication with microcontroller over uart0 serial port.
        mctl.ReportBoard()  # Log the board type now that the log file is defined.
        mctl.Initiate()  # Initiate communication.

    except PermissionError as e:
        main_log.log("initiate_mctl: Failed: PermissionError.", level="error")
        print("")
        linelist = [
            "           THE MICROCONTROLLER FAILED TO INITIALISE.",
            "                    PERMISSION ERROR.",
            "This may be because the permissions are incorrectly set in"
            "raspi-config. ",
            "1) Check SERIAL PORT is ENABLED" "2) Check SERIAL CONSOLE is DISABLED",
        ]
        TextColor.text_box(linelist, fg=TextColor.WHITE, bg=TextColor.RED)
        print("")
        main_log.raise_exception(
            e, comment="initiate_mctl:PermissionError"
        )  # Trap all the exception information in the main log file.
    except Exception as e:
        main_log.log(
            "initiate_mctl: Failed: Is another instance already running?", level="error"
        )
        print("")
        linelist = [
            "           THE MICROCONTROLLER FAILED TO INITIALISE.",
            "                    EXCEPTION.",
            "This may be because another copy of pilomar is already running.",
            "or because the Serial Port is misconfigured in raspi-config.",
            "1) Check for duplicate processes and terminate them if needed.",
            "2) Check SERIAL PORT is ENABLED" "3) Check SERIAL CONSOLE is DISABLED",
        ]
        TextColor.text_box(linelist, fg=TextColor.WHITE, bg=TextColor.RED)
        print("")
        print(TextColor.yellow("pilomar processes currently running:-"))
        osCmd("ps -ef | grep pilomar", output="terminal")
        print(TextColor.yellow("This copy of the pilomar is pid", os.getpid()))
        main_log.raise_exception(
            e, comment="initiate_mctl:Exception"
        )  # Trap all the exception information in the main log file.
    return mctl


Mctl = initiate_mctl()  # Create new microcontroller instance.
if Mctl is None:  # Microcontroller couldn't start.
    main_log.log(
        "initiate_mctl failed to create Microcontroller instance.", level="error"
    )
    exit()  # Quit the program.

AstroCamera.set_global_mctl(
    Mctl
)  # Point the cameras to the microcontroller instance (to monitor restarts)


def set_global_led_status():
    try:
        Mctl.SetLedStatus(
            params.mctl_led_status
        )  # Set the LED status on the microcontroller.
    except Exception as e:
        main_log.raise_exception(
            e, comment="set_global_led_status"
        )  # Trap all the exception information in the main log file.


def start_mctl_comms():
    """This runs the microcontroller communications in a separate thread.
    This should keep communication flowing even if the main thread
    is busy with other tasks.
    (Python does not have truly concurrent threads, so it may still pause sometimes.)
    This does not generate or process messages in either direction, it ONLY handles the
    transfer of queued messages between the RPi and Microcontroller via the UART channel.

    To see where the messages are analysed and processed you need to view the Session.mctl_handler method.
    """
    # Communication between the MctlComms thread and the main thread is through the UartControlQueue.
    Mctl.CommsLoop(UartControlQueue)


# Run the microcontroller communications in a separate thread.
MctlThread = threading.Thread(
    target=start_mctl_comms, args=(), daemon=True
)  # Run microcontroller communication independently, quit automatically.
MctlThread.start()

# ============================================================

main_log.log("Preparing motor control...", terminal=False)


# Create and initialize motor instances.
AzimuthControl = MotorControl(
    "azimuth",
    gearratio=params.azimuth_gear_ratio,  # 240 # Gearing of the drive system ignoring motor steps.
    fullstepsperrev=params.azimuth_motor_steps_per_rev,  # 400 # FullStep count of the motor before microstepping added.
    microstepratio=params.azimuth_microstep_ratio,  # 1 # Level of microstepping to be added for observations. 1 = Full steps, 2 = 1/2 steps, 4 = 1/4 steps etc.
    minangle=params.min_azimuth_angle,  # 0 - Physical minimum angle motor will move to.
    maxangle=params.max_azimuth_angle,  # 360 - Physical maximum angle motor will move to.
    restangle=params.azimuth_rest_angle,  # 180.0,
    currentangle=params.azimuth_rest_angle,  # 180.0 # Yes it's the same as above!
    backlashangle=params.azimuth_backlash_angle,  # 0.0
    orientation=params.azimuth_orientation,  # -1,
    limitangle=params.azimuth_limit_angle,
    horizon=None,  # None # There is no tracking horizon applied to this motor.
    fasttime=params.fast_time,
    slowtime=params.slow_time,
    timedelta=params.time_delta,
    slewmicrosteps=params.azimuth_slew_microstep_ratio,  # 1 # Level of microstepping to be added for GOTO/HOME moves. 1 = Full steps, 2 = 1/2 steps, 4 = 1/4 steps etc.
    optimisemoves=params.optimise_moves,  # Can motor move freely across the 0-360 limit to keep tracking targets?
    logger=main_log,
)
AltitudeControl = MotorControl(
    "altitude",
    gearratio=params.altitude_gear_ratio,  # 240,
    fullstepsperrev=params.altitude_motor_steps_per_rev,  # 400 # FullStep count of the motor before microstepping added.
    microstepratio=params.altitude_microstep_ratio,  # 1 # Level of microstepping to be added for observations. 1 = Full steps, 2 = 1/2 steps, 4 = 1/4 steps etc.
    minangle=params.min_altitude_angle,  # 0 - Physical minimum angle motor will move to.
    maxangle=params.max_altitude_angle,  # 90 - Physical maximum angle motor will move to.
    restangle=params.altitude_rest_angle,  # 0.0,
    currentangle=params.altitude_rest_angle,  # 0.0,
    backlashangle=params.altitude_backlash_angle,  # 0.0,
    orientation=params.altitude_orientation,  # -1,
    limitangle=params.altitude_limit_angle,
    horizon=params._horizon,  # 0 # There is a tracking horizon. Even if motor can physically move below the horizon, observations are not made.
    fasttime=params.fast_time,
    slowtime=params.slow_time,
    timedelta=params.time_delta,
    slewmicrosteps=params.altitude_slew_microstep_ratio,  # 1 # Level of microstepping to be added for GOTO/HOME moves. 1 = Full steps, 2 = 1/2 steps, 4 = 1/4 steps etc.
    optimisemoves=False,  # Motor must respect movement limits.
    logger=main_log,
)
MotorControls = (
    MotorControl.AllMotors
)  #  Alias for the list of ALL defined motors held in the motorcontrol class.

# Assign filename for the 'observation running' flag file. Thie file indicates that an observation started, but has not yet cleanly finished.
ObservationRunningFile = FolderHandler.prep_file(
    "dataroot", "observationrunningflag.txt"
)  # Work out where to store the ObservationRunning file.


def last_reported_location_datetime():
    """What's the oldest datetime stamp of the reported camera locations?"""
    result = None
    for i in MotorControls:
        if result is None or (
            i.StatusMctlTimestamp is not None and result > i.StatusMctlTimestamp
        ):
            result = i.StatusMctlTimestamp
    return result


def last_reported_alt_az():
    """Retrieve the current physical position of the camera.
    Returns values based upon the data stored in the MotorControl objects."""
    az_degree = 0.0
    alt_degree = 0.0
    for i in MotorControls:
        WarningFlagName = (
            "LastReportedAltAz_Stale_" + i.MotorName
        )  # Which warning message are we considering?
        if i.StatusMctlTimestamp is not None:
            td = abs(now_utc() - i.StatusMctlTimestamp).total_seconds()
            if (
                td > 20
            ):  # Position is > 20 seconds old. Expect an update more regularly than this.
                if WarningFlags.first_warning_flag(
                    WarningFlagName
                ):  # Only issue the warning message once, don't keep repeating it.
                    main_log.log(
                        "last_reported_alt_az(",
                        i.MotorName,
                        ") position ",
                        deg_3dp(i.CurrentAngle),
                        "deg is stale.",
                        td,
                        "s since",
                        i.StatusMctlTimestamp,
                        "UTC",
                        terminal=False,
                    )
            else:
                reset_warning_flag(
                    WarningFlagName
                )  # Reset so that warning will be reissued if the condition arises again.
        else:
            main_log.log(
                "last_reported_alt_az(",
                i.MotorName,
                ") StatusMctlTimestamp is None.",
                terminal=False,
            )
        if i.MotorName == "azimuth":
            az_degree = i.CurrentAngle
        elif i.MotorName == "altitude":
            alt_degree = i.CurrentAngle
    return alt_degree, az_degree


def estimated_alt_az():
    """Retrieve the current physical position of the camera.
    Returns values based upon the data stored in the MotorControl objects.
    *Q* Currently this continues the current speed, but that becomes inaccurate when target is moving very fast, especially as passing the zenith.
      Needs to be smarter, or simply use the current target location at the chosen time.
    """
    az_degree = 0.0
    alt_degree = 0.0
    for i in MotorControls:
        if i.MotorName == "azimuth":
            az_degree = i.EstimateCurrentAngle()
        elif i.MotorName == "altitude":
            alt_degree = i.EstimateCurrentAngle()
    return alt_degree, az_degree


# Warn if the previous observation_run didn't complete, it may have left things in a mess.
if os.path.exists(ObservationRunningFile):
    t_alt, t_az = (
        last_reported_alt_az()
    )  # Where does the program THINK the camera is pointing?
    lines = [
        "The previous observation run did not complete properly.",
        "This may have left the camera positions out of date.",
        "You may need to reset the camera altitude and azimuth",
        "before starting a new observation.",
        " ",
        az_alt_text(t_az, t_alt, DEGREE_SYMBOL),
        " ",
        "If the microcontroller continued running after the program",
        "failed Pi-lomar may not have recorded later movement.",
    ]
    TextColor.text_box(lines, fg=TextColor.WHITE, bg=TextColor.ORANGERED1)
    result = input(TextColor.cyan("[ENTER] to continue."))


def home_alt_az():
    """Return the home positions of the motors."""
    home_alt = home_az = 0.0
    for i in MotorControls:
        if i.MotorName == "altitude":
            home_alt = i.RestAngle
        elif i.MotorName == "azimuth":
            home_az = i.RestAngle
    return home_alt, home_az


# Calculate some useful conversion factors from the various elements defined.
for i in MotorControls:
    if i.MotorName == "azimuth":
        az_pixels_per_fullstep = float(camera_in_use.pixels_per_fov_degree_width) / (
            i.MotorStepsPerAxisDegree * i.GearRatio
        )
    elif i.MotorName == "altitude":
        alt_pixels_per_fullstep = float(camera_in_use.pixels_per_fov_degree_height) / (
            i.MotorStepsPerAxisDegree * i.GearRatio
        )

session = SessionStatus(logger=main_log)  # Create new session status object.

DriftTracker = imagetracker(
    logger=cam_log
)  # Create an instance of the image tracker to measure drift between subsequent images.


# ///////////////////////////////////////////////////////////////////////////////////
# Initialize Skyfield
# ///////////////////////////////////////////////////////////////////////////////////

# Set up observer location.
main_log.log(
    "Home location Latitude " + params.home_lat + ", Longitude " + params.home_lon
)
HomeSiteTopos = Topos(params.home_lat, params.home_lon)

# Load dictionary listing star NAMES, CONSTELLATION and Hipparcos catalog number.
load = Loader(
    ProjectRoot + "/data"
)  # Create own version of Skyfield 'load' object. This version saves cache files in the data directory.
StarNameUrl = ProjectRoot + "/data/starnames.json"
MessierDictUrl = ProjectRoot + "/data/messierobjects.json"
MeteorDictUrl = ProjectRoot + "/data/meteors.json"
NGCCacheFile = ProjectRoot + "/data/ngc.pkl"
NGCUrl = ProjectRoot + "/data/ngc.json"


def dictionary_loader(filename):
    """Given a json filename on disc, load it as a Python dictionary.
    Return empty dictionary if file does not exist."""
    if os.path.exists(filename):
        with open(filename, "r") as f:
            dictionary = json.load(f)
    else:
        main_log.log(
            "dictionary_loader(",
            filename,
            ") does not exist. Empty dictionary returned.",
            level="error",
        )
        dictionary = {}
    return dictionary


# Load starname dictionary.
main_log.log("Loading StarName dictionary from " + StarNameUrl + "...", terminal=False)
StarName_dictionary = dictionary_loader(StarNameUrl)


def b_vto_bgr(BV):
    """Convert a B-V color value from Hipparcos catalog to an approximate BGR color code.
    B-V     R G B (hex)
    -0.33   706ffe
    -0.3    519ffe
    -0.02   bfd0ff
    0.3     cdfdff
    0.58    eeffdf
    0.81    ffff7f
    1.40    fe7f7d
    """
    r = g = b = 255
    # List of sample B-V values and their approximate R,G,B equivalents. Found online.
    ColorPoints = [
        (-0.33, [0x70, 0x6F, 0xFE]),
        (-0.3, [0x51, 0x9F, 0xFE]),
        (-0.02, [0xBF, 0xD0, 0xFF]),
        (0.3, [0xCD, 0xFD, 0xFF]),
        (0.58, [0xEE, 0xFF, 0xDF]),
        (0.81, [0xFF, 0xFF, 0x7F]),
        (1.4, [0xFE, 0x7F, 0x7D]),
    ]

    def b_vrange(BV):
        # Given a B-V value, pick the pair of ColorPoints that will be used to calculate the RGB equivalent.
        fromi = 0
        toi = 1  # If BV is too low, we use the lowest pair of entries. (We will extrapolate a value)
        try:
            for i, cp in enumerate(ColorPoints):  # Consider each sample point in turn.
                if BV >= cp[0]:  # Above lower threshold of this sample point.
                    fromi = i  # Interpolation starts with this lower entry.
                    toi = i + 1  # Interpolation ends with the next entry.
            if toi >= len(
                ColorPoints
            ):  # If BV is too high, we are off the end of the list, so use the highest pair of entries.
                toi = len(ColorPoints) - 1
                fromi = toi - 1
        except Exception as e:
            main_log.log("BVRange:", str(BV), "failed:", str(e), level="error")
            fromi = 0
            toi = 1
        return fromi, toi

    def b_vd_x(fromi, toi):
        # Span of BV values from LOWER to UPPER sample limits.
        try:
            result = ColorPoints[toi][0] - ColorPoints[fromi][0]
        except Exception as e:
            main_log.log(
                "BVdX:", str(fromi), str(toi), "failed:", str(e), level="error"
            )
            result = 0
        return result

    def b_vd_r(fromi, toi):
        # Span of BLUE channel values from LOWER to UPPER sample limits.
        try:
            result = ColorPoints[toi][1][0] - ColorPoints[fromi][1][0]
        except Exception as e:
            main_log.log(
                "BVdR:", str(fromi), str(toi), "failed:", str(e), level="error"
            )
            result = 0
        return result

    def b_vd_g(fromi, toi):
        # Span of GREEN channel values from LOWER to UPPER sample limits.
        try:
            result = ColorPoints[toi][1][1] - ColorPoints[fromi][1][1]
        except Exception as e:
            main_log.log(
                "BVdG:", str(fromi), str(toi), "failed:", str(e), level="error"
            )
            result = 0
        return result

    def b_vd_b(fromi, toi):
        try:
            result = ColorPoints[toi][1][2] - ColorPoints[fromi][1][2]
        except Exception as e:
            main_log.log(
                "BVdB:", str(fromi), str(toi), "failed:", str(e), level="error"
            )
            result = 0
        return result

    def bv_interpolate(BV, fromi, toi):
        try:
            BVProportion = (BV - ColorPoints[fromi][0]) / b_vd_x(
                fromi, toi
            )  # Position of our point between the two reference points. This is the scale applied to R,G,B channels.
            r = round(
                (BVProportion * b_vd_r(fromi, toi)) + ColorPoints[fromi][1][0], 0
            )  # Scale RED channel relative to the BV position.
            r = max(0, r)  # Colour channel values must be 0-255
            r = min(255, r)
            g = round(
                (BVProportion * b_vd_g(fromi, toi)) + ColorPoints[fromi][1][1], 0
            )  # Scale GREEN channel relative to the BV position.
            g = max(0, g)
            g = min(255, g)
            b = round(
                (BVProportion * b_vd_b(fromi, toi)) + ColorPoints[fromi][1][2], 0
            )  # Scale BLUE channel relative to the BV position.
            b = max(0, b)
            b = min(255, b)
        except Exception as e:
            main_log.log(
                "BVInterpolate:",
                str(BV),
                str(fromi),
                str(toi),
                "failed:",
                str(e),
                level="error",
            )
            r = b = g = 255
        return (int(b), int(g), int(r))

    try:
        fromi, toi = b_vrange(
            BV
        )  # Which pair of sample colour points do we interpolate from?
        b, g, r = bv_interpolate(BV, fromi, toi)
    except Exception as e:
        main_log.log("BVtoBGR:", str(BV), "failed:", str(e), level="warning")
        b = g = r = 255
    return (b, g, r)


# -----------------------------------------------------------------------------------------------------


def pandas_float(inputvalue, failvalue=None):
    """Convert a Pandas value into a float, or return None if impossible.
    inputvalue = The pandas value to convert.
    failvalue = The return value if inputvalue cannot be converted."""
    try:
        result = float(str(inputvalue))
    except:
        result = failvalue
    if str(result) == "nan":  # This is unacceptable too.
        result = failvalue
    return result


# -----------------------------------------------------------------------------------------------------


def hip_color(bv):
    """Return b,g,r values for the color of any star given its B-V value from the hipparcos catalog."""
    bv = pandas_float(bv)  # Make sure it's a float, trap NaN values.
    try:
        if is_float(bv):  # Some entries are BLANK in Hipparcos data set.
            ColorBV = float(bv)
            b, g, r = b_vto_bgr(ColorBV)
            # Make all the stars quite bright, so rescale the values to 128 - 255.
            b = int(b / 2) + 127
            g = int(g / 2) + 127
            r = int(r / 2) + 127
        else:
            main_log.log(
                "HipColor:",
                str(bv),
                "isn't float, setting (255,255,255)",
                terminal=False,
            )
            b = g = r = 255
    except Exception as e:
        main_log.log("HipColor:", str(bv), "failed:", str(e), level="warning")
        b = g = r = 255
    return (b, g, r)


def magnitude2_radius(mag, dimmest, brightest=-6, radius_max=20):
    """Calculate star radius based upon a sliding scale of magnitudes.
    Returns a scaled 'radius' and a 'ratio' for dimming colours based upon the magnitude of the item.
    dimmest = High value magnitude (dimmest star to represent). (Radius 1)
    brightest = Low value magnitude (brightest star to represent). (Radius 10)
    NOTE: If you are tempted to alter this, test it carefully first. Magnitudes run negatively!
    """
    rmag = min(mag, dimmest)  # Magnitudes are inverted!
    rmag = max(rmag, brightest)  # Magnitudes are inverted!
    span = dimmest - brightest  # Span of magnitudes to be handled.
    offset = rmag - brightest  # Start point on magnitude scale.
    ratio = round(
        (radius_max - 1) * (offset / span), 0
    )  # How far along the magnitude scale is this item?
    radius = int(radius_max - ratio)  # Convert to a radius.
    brightnessratio = float(offset) / float(
        span
    )  # How far along the brightest - dimmest scale are we?
    brightnessratio = 1.0 - (
        brightnessratio / 2
    )  # Invert the scale and make sure we don't dim below 50% so stuff stays visible.
    return radius, brightnessratio


def dim_channel(channel, ratio):
    """simple multiplier for single color channel."""
    channel = channel * ratio
    channel = max(channel, 0)  # Cannot be < 0
    channel = min(channel, 255)  # Cannot be > 255
    return int(channel)


# If Hipparcos data already cached, use that, otherwise load and prepare the data cache now.
local_dataset = LocalStars()

# These files come from JPL, they list the rules for positions of planets for hundreds of years.
main_log.log("Loading solar system ephemeris from JPL...", terminal=False)
# This requires an internet connection the first time it runs, after that it uses cached data.
# *Q* Oct.2020 - skyfield log suggests this may nolonger automatically update, may need manual flush and reload every few months.
planets = load(
    "de421.bsp"
)  # Compact list of inner planets. *Q* Does this have a 'reload' option like load.open does?

# Load Messier object list.
main_log.log("Loading Messier catalog from", MessierDictUrl, "...", terminal=True)
Messier_dictionary = dictionary_loader(MessierDictUrl)
# Add some precalculated fields to simplify life later on.
for key, TempStarParms in Messier_dictionary.items():
    TempRAH = TempStarParms["ra"][0]  # Right Ascension HOURS
    TempRAM = TempStarParms["ra"][1]  # Right Ascension MINUTES
    TempRAS = TempStarParms["ra"][2]  # Right Ascension SECONDS
    TempStarParms["rah"] = TempRAH
    TempStarParms["ram"] = TempRAM
    TempStarParms["ras"] = TempRAS
    TempStarParms["radeg"] = hms_to_angle(TempRAH, TempRAM, TempRAS)
    TempDED = TempStarParms["dec"][0]  # Declination whole degrees
    TempDEM = TempStarParms["dec"][1]  # Declination MINUTES
    TempDES = TempStarParms["dec"][2]  # Declination SECONDS
    TempStarParms["ded"] = TempDED
    TempStarParms["dem"] = TempDEM
    TempStarParms["des"] = TempDES
    TempStarParms["decdeg"] = dms_to_angle(TempDED, TempDEM, TempDES)
    TempStarParms["ralabel"] = (
        str(int(TempRAH))
        + "h "
        + str(int(TempRAM))
        + "m "
        + str(round(TempRAS, 1))
        + "s"
    )
    TempStarParms["declabel"] = (
        str(int(TempDED))
        + "d "
        + str(int(TempDEM))
        + "' "
        + str(round(TempDES, 1))
        + '"'
    )
    TempStarParms["widthdeg"] = float(
        TempStarParms["width"] / 60
    )  # Convert from arcminutes to degrees
    TempStarParms["heightdeg"] = float(
        TempStarParms["height"] / 60
    )  # Convert from arcminutes to degrees

StellariumUrl = "https://raw.githubusercontent.com/Stellarium/stellarium/master/skycultures/modern/constellationship.fab"
main_log.log(
    "Loading Stellarium constellation patterns from", StellariumUrl, terminal=False
)
with load.open(StellariumUrl) as f:
    StellariumConstellations = stellarium.parse_constellations(f)

# Create internal list of the stars in each constellation. This indicates which stars to 'join up' in order to draw a constellation pattern.
main_log.log("Loading constellation patterns...", terminal=True)
ConstellationLinks = (
    []
)  # Start new empty list of constellation patterns. [ [from hip num, to hip num, constellation], [from hip num, to hip num, constellation], ... ]
ConstellationCodes = dict(
    load_constellation_names()
)  # Used to turn abbreviations into full names.
ConstellationStarList = (
    []
)  # List of HIP numbers for stars in constellation patterns. Used to find markup_preview stars which can be joined up.
for cons in StellariumConstellations:  # Process each constellation in turn.
    # cons contains something like 'And',[(star1, star2), (star3, star4),...]
    c_name = cons[0]  # Constellation name ('And')
    # Expand constellation code into a name if possible.
    if (
        c_name in ConstellationCodes
    ):  # A translation exists. Convert from UMa => Ursa Major for example.
        c_name = ConstellationCodes[c_name]  # Use the translation instead.
    c_name = (
        c_name.lower()
    )  # Lower case to match other references elsewhere in the program.
    c_edge = cons[
        1
    ]  # Constellation pattern edges as a list [(star1, star2),(star3, star4),...]
    for c_pair in c_edge:  # Process each star pair in turn.
        # c_pair format is (star1,star2) - star1/2 are Hipparcos references.
        star1 = str(c_pair[0])
        star2 = str(c_pair[1])
        entry = [star1, star2, c_name]  # New entry for internal format list.
        if not star1 in ConstellationStarList:
            ConstellationStarList.append(star1)
        if not star2 in ConstellationStarList:
            ConstellationStarList.append(star2)
        ConstellationLinks.append(entry)
main_log.log(
    "ConstellationLinks:", len(ConstellationLinks), "star pairs.", terminal=False
)
main_log.log(
    "ConstellationLinks:", len(ConstellationStarList), "unique stars.", terminal=False
)

# Load NGC list.
main_log.log(
    "Loading New General Catalog (NGC) entries from", NGCUrl, "...", terminal=True
)
NGCDict = dictionary_loader(NGCUrl)
NGC_Namelist = []  # List of names.
for key, value in NGCDict.items():
    NGC_Namelist.append(key)


def generate_ngc_dataframe(NGCDict):
    """Use the Python dictionary to generate a Pandas dataframe.
    Having the data in a dataframe can speed up selection and
    processing of large lists, and moves closer to having common
    routines for handling all the different object lists."""
    main_log.log("generate_ngc_dataframe...", terminal=False)
    # The types of NGC objects as defined in the Saguaro database.
    NGCTypes = {
        "aster": "Asterism",
        "brtnb": "Bright nebula",
        "cl+nb": "Cluster with nebulosity",
        "drknb": "Dark nebula",
        "galcl": "Galaxy cluster",
        "galxy": "Galaxy",
        "glocl": "Globular cluster",
        "gx+dn": "Diffuse nebula in a galaxy",
        "gx+gc": "Globular cluster in a galaxy",
        "g+c+n": "Cluster with nebulosity in a galaxy",
        "lmccn": "LMC cluster with nebulosity",
        "lmcdn": "LMC diffuse nebula",
        "lmcgc": "LMC globular cluster",
        "lmcoc": "LMC open cluster",
        "nonex": "Nonexistent",
        "opncl": "Open cluster",
        "plnnb": "Planetary nebula",
        "smccn": "SMC cluster with nebulosity",
        "smcdn": "SMC diffuse nebula",
        "smcgc": "SMC globular cluster",
        "smcoc": "SMC open cluster",
        "snrem": "Supernova remnant",
        "quasr": "Quasar",
        "1star": "Star",
        "2star": "2 Stars",
        "3star": "3 Stars",
        "4star": "4 Stars",
        "5star": "5 Stars",
        "6star": "6 Stars",
        "7star": "7 Stars",
    }

    # Store some repeated calculations in the dictionary to improve performance later on.
    count = 0
    for NGCEntry, NGCValues in NGCDict.items():
        # main_log.log("generate_ngc_dataframe: Loading:",NGCEntry,terminal=False)
        TempRAH = NGCValues["rah"]  # Right Ascension HOURS
        TempRAM = NGCValues["ram"]  # Right Ascension MINUTES
        TempRAS = NGCValues["ras"]  # Right Ascension SECONDS
        NGCValues["radeg"] = hms_to_angle(
            TempRAH, TempRAM, TempRAS
        )  # Create new 'degrees' right ascension value.
        TempDED = NGCValues["ded"]  # Declination DEGREES
        TempDEM = NGCValues["dem"]  # Declination MINUTES
        TempDES = NGCValues["des"]  # Declination SECONDS
        NGCValues["decdeg"] = dms_to_angle(
            TempDED, TempDEM, TempDES
        )  # Create new 'degrees' declination value.
        tempw = float(NGCValues["width"]) / (
            60**2
        )  # Convert from arcseconds to degrees
        temph = float(NGCValues["height"]) / (60**2)
        if temph == 0.0:
            temph = tempw  # Use WIDTH if HEIGHT is not specified.
        if tempw == 0.0:
            tempw = temph  # Use HEIGHT if WIDTH is not specified.
        if temph == 0.0:
            temph = tempw = 1 / (
                60**2
            )  # Default to 1 arc-second if dimensions are not known.
        NGCValues["widthdeg"] = tempw  # Convert from arcseconds to degrees
        NGCValues["heightdeg"] = temph
        NGCValues["name"] = NGCEntry
        n_type = NGCValues["type"].lower()
        if n_type in NGCTypes:
            NGCValues["typelabel"] = NGCTypes[n_type]
        else:
            NGCValues["typelabel"] = n_type
        NGCValues["ralabel"] = (
            str(TempRAH) + "h " + str(TempRAM) + "m " + str(TempRAS) + "s"
        )
        NGCValues["declabel"] = (
            str(TempDED) + "d " + str(TempDEM) + "' " + str(TempDES) + '"'
        )
        # main_log.log("generate_ngc_dataframe: Record",count,":",NGCEntry,": RA deg",NGCValues['radeg'],"Dec deg",NGCValues['decdeg'],n_type,NGCValues['typelabel'],terminal=False)
        count += 1

    # Convert the dictionary to a pandas dataframe.
    NGC_DF = pandas.DataFrame.from_dict(
        NGCDict
    )  # Convert from dictionary to pandas dataframe (but the rows/columns are transposed).
    NGC_DF = NGC_DF.transpose()  # Swap rows/columns the right way round.

    # Eliminate any entries which will never be selected.
    main_log.log(
        "generate_ngc_dataframe: Before removing dim objects.",
        len(NGC_DF),
        "records.",
        terminal=False,
    )
    # Filter out dim NGC objects, but make the limit dimmer than the star selection because they are interesting objects.
    boolseries = NGC_DF["magnitude"].between(
        -100, params.target_min_magnitude * 1.5, inclusive="both"
    )  # Create filter for items within Magnitude range.
    NGC_DF = NGC_DF[boolseries]  # Apply filter.
    main_log.log(
        "generate_ngc_dataframe: After removing dim objects.",
        len(NGC_DF),
        "records. (Magnitude",
        params.target_min_magnitude,
        ")",
        terminal=False,
    )
    main_log.log(
        "generate_ngc_dataframe: Dataframe contains: Rows",
        len(NGC_DF),
        "Columns",
        NGC_DF.columns,
        terminal=False,
    )

    #  Index(['magnitude', 'rah', 'ram', 'ras', 'ded', 'dem', 'des', 'width',
    #         'height','radeg','decdeg','widthdeg','heightdeg'],
    #        dtype='object')
    #  Data columns (total 13 columns):
    #   #   Column
    #  ---  ------
    #   0   magnitude
    #   1   rah
    #   2   ram
    #   3   ras
    #   4   ded
    #   5   dem
    #   6   des
    #   7   width
    #   8   height
    #   9   radeg
    #   10  decdeg
    #   11  widthdeg
    #   12  heightdeg
    #   13  name
    #   14  ralabel
    #   15  declabel
    NGC_DF.to_pickle(
        NGCCacheFile
    )  # Save the processed file as a cache to speed things up next time.

    return NGC_DF


if not reload_data and os.path.exists(
    NGCCacheFile
):  # A cache of the NGC data already exists, use it.
    main_log.log("NGC data cache exists, using that.", terminal=True)
    NGC_DF = pandas.read_pickle(NGCCacheFile)
else:
    main_log.log("No NGC data cache, creating one now.", terminal=True)
    NGC_DF = generate_ngc_dataframe(NGCDict)
main_log.log(
    "NGC dataframe contains: Rows",
    len(NGC_DF),
    "Columns",
    NGC_DF.columns,
    terminal=False,
)

# Load Meteor shower list.
main_log.log("Loading meteor shower list from", MeteorDictUrl, "...", terminal=True)
Meteor_dictionary = dictionary_loader(MeteorDictUrl)

# Load comet data.
# Comet data comes from the Minor Planet Center.
# Format is :-
#     CJ95O010  1997 03 30.7270  0.890333  0.994981  130.2195  282.3128   89.4615  20240223  -2.0  4.0  C/1995 O1 (Hale-Bopp)                                    MPEC 2022-S20
# 012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012
#           1         2         3         4         5         6         7         8         9        10        11        12        13        14        15        16        17        18
#                                                                                  YYYYMMDD stamp of the data.
main_log.log("Loading comet list from", mpc.COMET_URL, "...", terminal=True)
# Comet data loaded as a Pandas dataframe.
main_log.log(len(comets), "comets loaded.", terminal=False)
main_log.log("Comet dataframe contents:", comets.columns.tolist(), terminal=False)
# Keep only the most recent comet trajectory and index by designation for fast lookup.
comets = (
    comets.sort_values("reference")
    .groupby("designation", as_index=False)
    .last()
    .set_index("designation", drop=False)
)
# Example lookups.
# row = comets.loc['1P/Halley']
# row = comets.loc['C/1995 O1 (Hale-Bopp)']

CometList = comets[
    "designation"
].tolist()  # Convert comet designations column into a list for searching later on.


def comet_data_age():
    """Report the age of the comet trajectory data from the Minor Planet Center.
    warn = True : Will issue warning here."""
    filename = ProjectRoot + "/data/CometEls.txt"
    filedays = None
    if os.path.exists(filename):  # The cache data exists, check its age.
        with open(filename, "r") as f:
            line = f.readline()  # Take 1st line as an example.
            filedt = mctl_string_to_datetime(
                line[81:89] + "000000"
            )  # YYYYMMDD portion of the record.
            filedays = round((now_utc() - filedt).total_seconds() / (24 * 60 * 60), 0)
            main_log.log(
                "Comet data cache is from",
                filedt,
                ",",
                filedays,
                "days old.",
                terminal=False,
            )
            if filedays > 60:  # After 2 months, consider refreshing the file.
                main_log.log(
                    "Comet data cache is",
                    filedays,
                    "days old. Consider refreshing it to maintain accuracy.",
                    level="warning",
                    terminal=True,
                )
    return filedays


comet_data_age()  # If the data cache exists, how old is the content?

# This uses built in astro corrected time functions rather than going to the web for them.
# I think these corrections will gradually fall out of date unless Skyfield is updated periodically.
ts = load.timescale()  # Time handling with astro corrections.


def skyfield_now(real=False):
    """Return skyfield format current time.
    Available as a method so that offsets or other features can be added if needed.
    if ClockOffset is set, that many seconds are added to the result. Allowing you to run the program against other dates/times.
    if real == True, then the Clockoffset is not applied, giving the true CPU time."""
    global ClockOffset
    result = ts.now()  # Now. # *Q* Offset supported.
    if not real and ClockOffset is not None:  # Can apply time offset.
        dt = ts_to_datetime(result)
        dt + timedelta(seconds=ClockOffset)
        result = datetime2_ts(dt)
    return result


t = skyfield_now()  # Now. # Offset supported.

# Use camera FOV to establish the selection radius of stars.
# Establish a list of stars which surround the target.
# If needed the list updates itself automatically each time it's queried via the Get() method.
# - 2 lists are built.
# - LocalStars is a list of stars within the narrow field of view of the camera. These are the ones we expect to see in the images.
# - ConstellationStars is a list of stars from a wider field of view, but which are part of constellation patterns. These are used to help markup constellation lines in preview images.
inclusionradius = (
    math.sqrt(
        (camera_in_use.lens.fov_horizontal**2) + (camera_in_use.lens.fov_vertical**2)
    )
    * 2
)
local_stars = LocalStars(
    ra=0.0,
    dec=0.0,
    radius=inclusionradius,
    magnitude=params.local_stars_magnitude,
    maxstars=10000,
    logger=cam_log,
)  # Narrow field of view, list of all visible stars.
ConstellationStars = LocalStars(
    ra=0.0,
    dec=0.0,
    radius=inclusionradius + 5,
    magnitude=params.constellation_stars_magnitude,
    maxstars=10000,
    logger=cam_log,
)  # Wider field of view, but filtered to just key constellation stars.
ConstellationStars.set_filter(
    ConstellationStarList
)  # The ConstellationStars list is filtered by this list.

# Construct hint lists for search functions. Lists of stars and messier objects.
Messier_namelist = []  # Empty list of Messier object names.
Messier_numlist = []  # Empty list of Messier object numbers.
for (
    key,
    value,
) in Messier_dictionary.items():  # Python3: Check every item in the starname list.
    sub_dictionary = value
    Messier_numlist.append(key)
    if len(sub_dictionary["name"]) > 0:
        Messier_namelist.append(sub_dictionary["name"].lower())
Hipparcos_StarList = []  # Empty list of all the star names in the Hipparcos catalog.
Hipparcos_ConsList = (
    []
)  # Empty list of all the constellation names in the Hipparcos catalog.
for (
    key,
    value,
) in StarName_dictionary.items():  # Python3: Make a list of recognised names.
    tName = value["name"]
    tCons = value["constellation"]
    if len(tName) > 0 and not (tName in Hipparcos_StarList):
        Hipparcos_StarList.append(tName)
    if len(tCons) > 0 and not (tCons in Hipparcos_ConsList):
        Hipparcos_ConsList.append(tCons)
Meteor_namelist = []  # Empty list of all meteor shower names.
for (
    key,
    value,
) in Meteor_dictionary.items():  # Python3: Check every item in the meteor list.
    Meteor_namelist.append(key)
main_log.log("Meteor shower list:", Meteor_namelist, terminal=False)

# And ISS position from celes_trak data (TLE lines).
celestrakurl = "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle"
main_log.log("Loading celes_trak station data from", celestrakurl, terminal=True)
celes_trak = Celestrack(celestrakurl, logger=main_log, projectroot=ProjectRoot)


if (
    reload_data
):  # We reloaded the data, quit here because STDIN can sometimes close during all the processing.
    print(TextColor.yellow("Reload complete: Please restart the program."))
    exit()  # Quit the program. This is a workaround to a problem where the Python 'input' statements fail after the hipex_load_dataframe() function has executed for a long time.


main_log.log(
    "Establish observer's location:",
    params.home_lat,
    params.home_lon,
    terminal=False,
)
HomeSite = (
    planets["earth"] + HomeSiteTopos
)  # Define HomeSite as a point on earth. Could be from GPS too.
RadecBase = Star(
    ra_hours=(0, 0, 0.0), dec_degrees=(0, 0, 0.0)
)  # To calculate where Radec ZERO point is. (For Equatorial mount positioning)


def choose_messier(prechosen=None, sizewarning=True):
    """Select an object from the Messier catalog by Catalog number or name.
    'prechosen' means that the input is provided externally, the function will not prompt.
    If the prechosen parameter is not recognised, the user is asked for a value instead.
    """
    Result = ""
    desc = None
    const = None
    objecttype = None
    magnitude = 0.0
    obstarget = None
    while Result == "":  # Loop until a target has been selected.
        if prechosen is None:
            SearchValue = input(
                TextColor.cyan("Enter Messier target (number, name, ? or 'x'): ")
            )
        else:
            SearchValue = prechosen
        if SearchValue == "?":  # Help
            print(TextColor.yellow("Recognised catalog IDs: ") + str(Messier_numlist))
            print(TextColor.yellow("Recognised names: ") + str(Messier_namelist))
            continue
        SearchValue = SearchValue.lower()  # Lower case character matching.
        if SearchValue == "x":  # Cancel
            return None
        for (
            key,
            value,
        ) in (
            Messier_dictionary.items()
        ):  # Python3: Check every item in the starname list.
            sub_dictionary = value
            if key.lower() == SearchValue:  # Messier catalog number matches.
                Result = key.lower()
                p = Star(
                    ra_hours=(
                        sub_dictionary["ra"][0],
                        sub_dictionary["ra"][1],
                        sub_dictionary["ra"][2],
                    ),
                    dec_degrees=(
                        sub_dictionary["dec"][0],
                        sub_dictionary["dec"][1],
                        sub_dictionary["dec"][2],
                    ),
                )
                const = sub_dictionary["constellation"]
                desc = sub_dictionary["description"]
                objecttype = sub_dictionary["type"]
                magnitude = sub_dictionary["magnitude"]
                width = sub_dictionary["width"]
                height = sub_dictionary["height"]
                main_log.log(
                    "choose_messier: Found by catalog number (" + key + ")",
                    terminal=False,
                )
                break
            if sub_dictionary["name"][: len(SearchValue)] == SearchValue:
                Result = key.lower()
                p = Star(
                    ra_hours=(
                        sub_dictionary["ra"][0],
                        sub_dictionary["ra"][1],
                        sub_dictionary["ra"][2],
                    ),
                    dec_degrees=(
                        sub_dictionary["dec"][0],
                        sub_dictionary["dec"][1],
                        sub_dictionary["dec"][2],
                    ),
                )
                const = sub_dictionary["constellation"]
                desc = sub_dictionary["description"]
                objecttype = sub_dictionary["type"]
                magnitude = sub_dictionary["magnitude"]
                width = sub_dictionary["width"]
                height = sub_dictionary["height"]
                main_log.log(
                    "choose_messier: Found by object name ("
                    + sub_dictionary["name"]
                    + ") catalog number "
                    + key
                    + ".",
                    terminal=False,
                )
                break
        if Result == "":  # Still no match. Give up and ask again.
            if prechosen is not None:
                main_log.log(
                    "choose_messier: Prechosen "
                    + str(prechosen)
                    + " not recognised. Ignored.",
                    terminal=False,
                )
                return None  # Scrap the attempt.
            print("Messier: Nothing matched, try again.")
    NeatName = safe_name(Result)
    # Establish a size for the object if known.
    sizemin = None
    if width is not None:
        if sizemin is None or width > sizemin:
            sizemin = width
    if height is not None:
        if sizemin is None or height > sizemin:
            sizemin = height
    main_log.log(
        "choose_messier: Selected target is width",
        width,
        "minutes, height",
        height,
        "minutes, size",
        sizemin,
        "minutes.",
        terminal=False,
    )
    if sizemin is not None:
        sizedeg = dms_to_angle(minutes=sizemin)  # Convert from minutes to degrees.
        main_log.log(
            "choose_messier: Selected target size is",
            sizedeg,
            "degrees.",
            terminal=False,
        )
        sizepix = (
            sizedeg * camera_in_use.pixels_per_fov_degree_width
        )  # How many pixels is this size?
        main_log.log(
            "choose_messier: Selected target is about",
            sizepix,
            "pixels across.",
            terminal=False,
        )
        if (
            sizepix < 10 and sizewarning
        ):  # Warn if the object is quite small in the resulting images.
            main_log.log(
                "choose_messier: The target is quite small, only about",
                sizepix,
                "pixels across.",
                terminal=True,
            )
    else:
        main_log.log("choose_messier: The target is unknown size.", terminal=False)
    obstarget = AstroTarget(
        p,
        name=NeatName,
        objecttype=objecttype,
        constellation=const,
        description=desc,
        magnitude=magnitude,
        searchgroup="messier",
        searchterm=Result,
        objectdiameter=sizedeg,
    )
    return obstarget


def choose_meteor(prechosen=None):
    """Select a meteor shower.
    'prechosen' means that the input is provided externally, the function will not prompt.
    If the prechosen parameter is not recognised, the user is asked for a value instead.
    """
    main_log.log("choose_meteor:Begin, prechosen:", prechosen, terminal=False)
    Result = ""
    desc = None
    const = None
    magnitude = 0.0
    obstarget = None
    main_log.log("choose_meteor:Create MeteorChooser", terminal=False)
    MeteorChooser = ListChooser(Meteor_namelist)
    main_log.log("choose_meteor:Begin prompt loop", terminal=False)
    while Result == "":  # Loop until a target has been selected.
        if prechosen is None:
            main_log.log("choose_meteor:Prompting", terminal=False)
            SearchValue = MeteorChooser.prompt()
            main_log.log("choose_meteor:Prompt returned", SearchValue, terminal=False)
        else:
            SearchValue = prechosen
        main_log.log("choose_meteor:Search for", SearchValue, terminal=False)
        for (
            key,
            value,
        ) in (
            Meteor_dictionary.items()
        ):  # Python3: Check every item in the meteor shower list.
            sub_dictionary = value
            if key == SearchValue:
                Result = key.lower()
                p = Star(
                    ra_hours=(sub_dictionary["rah"], sub_dictionary["ram"], 0),
                    dec_degrees=(sub_dictionary["dec"], 0, 0),
                )
                const = sub_dictionary["constellation"]
                desc = key + " meteor shower"
                main_log.log(
                    "choose_meteor: Found by meteor shower name (" + key + ").",
                    terminal=False,
                )
                break
        main_log.log("choose_meteor:Search returned", Result, terminal=False)
        if Result == "":  # Still no match. Give up and ask again.
            if prechosen is not None:
                main_log.log(
                    "choose_meteor: Prechosen "
                    + str(prechosen)
                    + " not recognised. Ignored.",
                    terminal=False,
                )
                return None  # Scrap the attempt.
            print("Meteor: Nothing matched, try again.")
    NeatName = safe_name(
        Result
    )  # No spaces in name, it is used to create folders, keep it simple.
    # Find location of origin.
    main_log.log("choose_meteor:Establish radec position", terminal=False)
    obstarget = AstroTarget(
        handle=p,
        name=NeatName,
        objecttype="meteor",
        constellation=const,
        description=desc,
        magnitude=magnitude,
        searchgroup="meteor",
        searchterm=SearchValue,
    )
    az, alt = (
        obstarget.az_alt_degrees()
    )  # Get initial position in the sky. We'll turn this into a fixed point.
    # Move a useful angle away from the origin.
    main_log.log("choose_meteor:Establish fixed point", terminal=False)
    es = FixedPoint(
        name=NeatName, alt=alt, az=az
    )  # Set a fixed point in the sky. The telescope will remain under direct control and not use trajectories.
    obstarget = AstroTarget(
        es,
        name=NeatName,
        objecttype="meteor",
        description=desc,
        magnitude=0.0,
        searchgroup="meteor",
        searchterm=SearchValue,
    )
    main_log.log(
        "NOTE: Meteor shower selected. Camera will point to a likely area of the sky to capture meteors, not the radiant point.",
        terminal=False,
    )
    return obstarget


def choose_ngc(prechosen=None):
    """Select a NGC object.
    'prechosen' means that the input is provided externally, the function will not prompt.
    If the prechosen parameter is not recognised, the user is asked for a value instead.
    """
    Result = ""
    desc = None
    const = None
    magnitude = 0.0
    obstarget = None
    while Result == "":  # Loop until a target has been selected.
        if prechosen is None:
            NGCChooser = ListChooser(NGC_Namelist)
            SearchValue = NGCChooser.prompt()
        else:
            SearchValue = prechosen
        if SearchValue is None:  # User quit the search.
            return None  # Scrap the attempt.
        for key, value in NGCDict.items():  # Python3: Check every item in the NGC list.
            sub_dictionary = value
            if key == SearchValue:
                Result = key.lower()
                p = Star(
                    ra_hours=(
                        sub_dictionary["rah"],
                        sub_dictionary["ram"],
                        sub_dictionary["ras"],
                    ),
                    dec_degrees=(
                        sub_dictionary["ded"],
                        sub_dictionary["dem"],
                        sub_dictionary["des"],
                    ),
                )
                magnitude = sub_dictionary["magnitude"]
                desc = key + " NGC"
                main_log.log(
                    "choose_ngc: Found by NGC number (" + key + ").", terminal=False
                )
                break
        if Result == "":  # Still no match. Ask again.
            if prechosen is not None:
                main_log.log(
                    "choose_ngc: Prechosen "
                    + str(prechosen)
                    + " not recognised. Ignored.",
                    terminal=False,
                )
                return None  # Scrap the attempt.
            print("NGC: (", str(SearchValue), ") Nothing matched, try again.")
    NeatName = safe_name(
        Result
    )  # No spaces in name, it is used to create folders, keep it simple.
    obstarget = AstroTarget(
        handle=p,
        name=NeatName,
        objecttype="ngc",
        constellation=const,
        description=desc,
        magnitude=magnitude,
        searchgroup="ngc",
        searchterm=SearchValue,
    )
    return obstarget


def choose_comet(prechosen=None):
    """Select a comet from the comet catalog by comet name.
    'prechosen' means that the input is provided externally, the function will not prompt.
    If the prechosen parameters is not recognised, the user is asked fora value instead.
    """

    comet_data_age()  # If the data cache exists, how old is the content?
    Result = ""
    desc = None
    obstarget = None
    p = None
    while Result == "":  # Loop until a target has been selected.
        if prechosen is None:
            CometChooser = ListChooser(CometList)
            SearchValue = CometChooser.prompt()
        else:
            SearchValue = prechosen
        if SearchValue is None:  # User quit the search.
            return None  # Scrap the attempt.
        if Result == "":  # No match yet.
            for c in comets[
                "designation"
            ]:  # Python3: Check every item in the comet list.
                if c == SearchValue:
                    Result = SearchValue.lower()
                    row = comets.loc[
                        c
                    ]  # Store the Pandas row in the TargetObject because we don't immediately create the 'Star' object.
                    main_log.log(
                        "choose_comet: Pandas row available data for the comet:",
                        str(list(comets.columns)),
                        terminal=False,
                    )  # Show available data.
                    p = planets["sun"] + mpc.comet_orbit(row, ts, GM_SUN)
                    desc = "Comet " + c
                    main_log.log(
                        "choose_comet: Found by comet name (" + c + ")", terminal=False
                    )
                    break
        if Result == "":  # Still no match. Give up and ask again.
            if prechosen is not None:
                main_log.log(
                    "choose_comet: Prechosen "
                    + str(prechosen)
                    + " not recognised. Ignored.",
                    terminal=False,
                )
                return None  # Scrap the attempt.
            print("Comet: Nothing matched, try again.")

    main_log.log(
        "choose_comet: NOTE: obstarget.handle() is populated in the target.__init__() method in the case of comets.",
        terminal=False,
    )

    NeatName = safe_name(
        Result
    )  # No spaces in name, it is used to create folders, keep it simple.
    obstarget = AstroTarget(
        handle=p,
        name=NeatName,
        objecttype="comet",
        description=desc,
        constellation=None,
        magnitude=None,
        searchgroup="comet",
        searchterm=SearchValue,
        cometpandasrow=row,
    )
    obstarget.magnitude = obstarget.apparent_comet_magnitude_gk()
    return obstarget


def choose_hipparcos(prechosen=None):
    """Select a star from the Hipparcos catalog by Catalog number, star name or constellation.
    'prechosen' means that the input is provided externally, the function will not prompt.
    If the prechosen parameter is not recognised, the user is asked for a value instead.
    """
    Result = ""
    desc = None
    const = None
    obstarget = None
    while Result == "":  # Loop until a target has been selected.
        if prechosen is None:  # We've not received a target name, so ask the user.
            SearchValue = input(
                TextColor.cyan("Enter Hipparcos target (number,? or 'x'): ")
            )  # Python3
        else:  # We've received a target name, use that for selection.
            SearchValue = prechosen
        SearchValue = SearchValue.lower()  # Lower case character matching.
        if SearchValue == "?":  # Help
            print("Enter the integer part of the hipparcos number.")
            continue
        if SearchValue == "x":  # Cancel
            return None
        # First and easiest check is for a direct entry in the catalog. Check for the HIP number durectly.
        SearchInt = text_to_int(SearchValue)
        if SearchInt is not None and SearchInt in HipparcosDf.index:
            Result = "HIP_" + str(SearchInt)
            main_log.log(
                "choose_hipparcos: Pandas row available data for the star:",
                str(list(HipparcosDf.columns)),
                terminal=False,
            )  # Show available data.
            starrec = HipparcosDf.loc[HipparcosDf.hip == SearchInt].iloc[
                0
            ]  # Return just the 1st record from the result.
            p = Star.from_dataframe(starrec)
            desc = "Star HIP_" + str(SearchInt) + " (Hipparcos)."
            const = starrec["constellation"]
            magnitude = starrec["magnitude"]
            main_log.log("choose_hipparcos: Found by catalog number.", terminal=False)
        if Result == "":  # No match yet.
            if prechosen is not None:
                main_log.log(
                    "choose_hipparcos: Prechosen "
                    + str(prechosen)
                    + " not recognised. Ignored.",
                    terminal=False,
                )
                return None  # Return to calling routine.
            print("Hipparcos: Nothing matched, try again.")

    NeatName = safe_name(
        Result
    )  # No spaces in name, it is used to create folders, keep it simple.
    obstarget = AstroTarget(
        handle=p,
        name=NeatName,
        objecttype="star",
        description=desc,
        constellation=const,
        magnitude=magnitude,
        searchgroup="hipparcos",
        searchterm=str(SearchInt),
    )
    return obstarget


def choose_solar(prechosen=None):
    """Choose a solar system target.
    'prechosen' means that the input is provided externally, the function will not prompt.
    If the prechosen parameter is not recognised, the user is asked for a value instead.
    """
    Result = ""
    main_log.log("choose_solar: Begin", terminal=False)
    AvailableTargets = [
        "sun",
        "mercury",
        "venus",
        "moon",
        "mars",
        "jupiter",
        "saturn",
        "uranus",
        "neptune",
        "pluto",
    ]
    PlanetChooser = ListChooser(
        AvailableTargets, compress=False
    )  # Always show the full list.
    obstarget = None
    while Result == "":
        if prechosen is None:  # We've not received a prechosen name, so ask the user.
            Result = PlanetChooser.prompt()
        else:  # We've received a prechosen name. Don't ask the user.
            Result = prechosen
        if Result is None:  # Nothing selected.
            return None  # Quit.
        main_log.log("choose_solar: Observation target input:" + Result, terminal=False)
        if Result not in AvailableTargets:
            if prechosen is not None:
                main_log.log(
                    "choose_solar: Prechosen not "
                    + str(prechosen)
                    + " recognised. Ignored.",
                    terminal=False,
                )
                return None  # Scrap the attempt.
            print(
                TextColor.red(
                    "'" + Result + "' is not a recognised target name. Try again."
                )
            )
            Result = ""
    if Result == "sun":
        obstarget = AstroTarget(
            planets["sun"],
            name=Result,
            objecttype="sun",
            description="The Sun",
            magnitude=-26.7,
            searchgroup="solar",
            searchterm=Result,
        )
    elif Result == "mercury":
        obstarget = AstroTarget(
            planets["mercury barycenter"],
            name=Result,
            objecttype="planet",
            description=Result,
            magnitude=0.23,
            searchgroup="solar",
            searchterm=Result,
        )
    elif Result == "venus":
        obstarget = AstroTarget(
            planets["venus barycenter"],
            name=Result,
            objecttype="planet",
            description=Result,
            magnitude=-4.4,
            searchgroup="solar",
            searchterm=Result,
        )
    elif Result == "moon":
        obstarget = AstroTarget(
            planets["moon"],
            name=Result,
            objecttype="moon",
            description=Result,
            magnitude=-12.5,
            searchgroup="solar",
            searchterm=Result,
        )
    elif Result == "mars":
        obstarget = AstroTarget(
            planets["mars barycenter"],
            name=Result,
            objecttype="planet",
            description=Result,
            magnitude=-2.91,
            searchgroup="solar",
            searchterm=Result,
        )
    elif Result == "jupiter":
        obstarget = AstroTarget(
            planets["jupiter barycenter"],
            name=Result,
            objecttype="planet",
            description=Result,
            magnitude=-2.7,
            searchgroup="solar",
            searchterm=Result,
        )
    elif Result == "saturn":
        obstarget = AstroTarget(
            planets["saturn barycenter"],
            name=Result,
            objecttype="planet",
            description=Result,
            magnitude=-0.55,
            searchgroup="solar",
            searchterm=Result,
        )
    elif Result == "uranus":
        obstarget = AstroTarget(
            planets["uranus barycenter"],
            name=Result,
            objecttype="planet",
            description=Result,
            magnitude=5.68,
            searchgroup="solar",
            searchterm=Result,
        )
    elif Result == "neptune":
        obstarget = AstroTarget(
            planets["neptune barycenter"],
            name=Result,
            objecttype="planet",
            description=Result,
            magnitude=7.78,
            searchgroup="solar",
            searchterm=Result,
        )
    elif Result == "pluto":
        obstarget = AstroTarget(
            planets["pluto barycenter"],
            name=Result,
            objecttype="planet",
            description=Result,
            magnitude=15.1,
            searchgroup="solar",
            searchterm=Result,
        )
    else:
        main_log.log(
            "choose_solar: Could not initialize target (" + Result + ")", level="error"
        )
        raise Exception("choose_solar: Could not initialize target (" + Result + ")")
    main_log.log("choose_solar: End " + obstarget.name, terminal=False)
    return obstarget


def choose_local_tz(default=None):
    """Allow the user to choose the local timezone from the available list."""
    Result = ""
    main_log.log("choose_local_tz: Begin", terminal=False)
    TZChooser = ListChooser(
        pytz.all_timezones, compress=False
    )  # Always show the full list.
    while Result == "":
        Result = TZChooser.prompt()
        if Result is None:
            return default
        if not Result in pytz.all_timezones:
            print(TextColor.red("'" + Result + "' is not recognised. Try again."))
            Result = ""
    return Result


def define_local_tz():
    """Allow the user to set the local timezone in the Parameter file."""
    main_log.log("define_local_tz: Begin", terminal=False)
    print(TextColor.yellow("Define local Timezone"))
    print("Pi-lomar operates in UTC time, you can define a local timezone here")
    print("however beware that this is currently for information only.")
    print("Most of the displays will continue to show UTC values.")
    Result = choose_local_tz(params.local_tz)
    if Result is not None:
        main_log.log("define_local_tz: Setting", Result, terminal=False)
        params.local_tz = Result
        print("Local Timezone set to", params.local_tz)
        nutc = now_utc()
        print("UTC time is", nutc)
        print("Local time is", utc_to_local(nutc))
    main_log.log("define_local_tz: End", terminal=False)


def choose_satellite(prechosen=None):
    """Choose a satellite target (eg space stations).
    'prechosen' means that the input is provided externally, the function will not prompt.
    If the prechosen parameter is not recognised, the user is asked for a value instead.
    """
    Result = ""
    main_log.log("choose_satellite: Begin", terminal=False)
    AvailableTargets = celes_trak.satellite_list
    SatelliteChooser = ListChooser(
        AvailableTargets, compress=False
    )  # Always show the full list.
    obstarget = None
    while Result == "":
        if prechosen is None:  # We've not received a prechosen name, so ask the user.
            Result = SatelliteChooser.prompt()
        else:  # We've received a prechosen name. Don't ask the user.
            Result = prechosen
        if Result is None:  # Nothing selected.
            return None  # Quit.
        main_log.log(
            "choose_satellite: Observation target input:" + Result, terminal=False
        )
        if Result not in AvailableTargets:
            if prechosen is not None:
                main_log.log(
                    "choose_satellite: Prechosen '"
                    + str(prechosen)
                    + "' not recognised. Ignored.",
                    terminal=False,
                )
                main_log.log(
                    "choose_satellite: Recognised list:",
                    str(AvailableTargets),
                    terminal=False,
                )
                return None  # Scrap the attempt.
            print(
                TextColor.red(
                    "'" + Result + "' is not a recognised target name. Try again."
                )
            )
            Result = ""
    line1, line2 = celes_trak.get_tle_lines(
        Result
    )  # Get the TLE entry for the chosen satellite.
    if line1 is not None:
        es = EarthSatellite(line1, line2, Result, ts)
        obstarget = AstroTarget(
            es,
            name=Result,
            objecttype="earth satellite",
            description="Spacestation:" + Result,
            magnitude=-6.0,
            searchgroup="satellite",
            searchterm=Result,
        )
    else:
        main_log.log(
            "choose_satellite: Could not initialize target (" + Result + ")",
            level="error",
        )
        raise Exception(
            "choose_satellite: Could not initialize target (" + Result + ")"
        )
    main_log.log("choose_satellite: End " + obstarget.name, terminal=False)
    return obstarget


def radec_object(prechosen=None):
    """Create a target from RA and DEC values."""
    if prechosen is None:
        print("radec_object: Create a target from RA and DEC values.")
        print("Definition format: RA hh mm ss DEC ddd mm ss name")
    line = ""
    obstarget = None
    while True:
        if (
            prechosen is not None
        ):  # We're receiving a prechosen target description, don't ask user.
            line = prechosen
            prechosen = None  # If there's a problem, then we'll ask the user instead.
        else:
            line = input("Definition (x to quit): ")  # As user for target description.
        if len(line) < 1:
            continue  # No input, ask again.
        if line.lower() == "x":  # Cancel
            return None
        lineitems = line.lower().split()
        if lineitems[0] != "ra":
            print(TextColor.red("1st term must be 'ra'. Try again"))
            continue  # Try again.
        if lineitems[4] != "dec":
            print(TextColor.red("5th term must be 'dec'. Try again"))
            continue  # Try again.
        name = lineitems[8]
        rah = text_to_int(lineitems[1])
        if rah is None or rah < 0 or rah > 23:
            print(
                TextColor.red(
                    "2nd term must be integer RIGHT ASCENSION hours (0 to 23). Try again"
                )
            )
            continue  # Try again.
        ram = text_to_int(lineitems[2])
        if ram is None or ram < 0 or ram > 59:
            print(
                TextColor.red(
                    "3rd term must be integer RIGHT ASCENSION minutes (0 to 59). Try again"
                )
            )
            continue  # Try again.
        ras = text_to_float(lineitems[3])
        if ras is None or ras < 0 or ras >= 60:
            print(
                TextColor.red(
                    "4th term must be decimal RIGHT ASCENSION seconds (0.000 to 59.999). Try again"
                )
            )
            continue  # Try again.
        ded = text_to_int(lineitems[5])
        if ded is None or ded < -90 or ded > 90:
            print(
                TextColor.red(
                    "6th term must be integer DECLINATION degrees (-90 to 90). Try again"
                )
            )
            continue  # Try again.
        dem = text_to_int(lineitems[6])
        if dem is None or dem <= -60 or dem >= 60:
            print(
                TextColor.red(
                    "7th term must be integer DECLINATION minutes (-59 to 59). Try again"
                )
            )
            continue  # Try again.
        des = text_to_float(lineitems[7])
        if des is None or des <= -60 or des >= 60:
            print(
                TextColor.red(
                    "8th term must be decimal DECLINATION seconds (-59.999 to 59.999). Try again"
                )
            )
            continue  # Try again.
        break  # Use these parameters to create the target object.
    if (
        ded < 0 or dem < 0 or des < 0
    ):  # If any values are negative, all must be. That's how Skyfield wants the parameters.
        if ded > 0:
            ded = -1 * ded
        if dem > 0:
            dem = -1 * dem
        if des > 0:
            des = -1 * des
    main_log.log(
        "radec_object: Coordinates of",
        name,
        "are RA",
        str(rah) + "h",
        str(ram) + "m",
        str(ras) + "s",
        "DEC",
        str(ded) + DEGREE_SYMBOL,
        str(dem) + "m",
        str(des) + "s",
        terminal=False,
    )
    es = Star(ra_hours=(rah, ram, ras), dec_degrees=(ded, dem, des))
    obstarget = AstroTarget(
        es,
        name=name,
        objecttype="radec location",
        description=name,
        magnitude=0.0,
        searchgroup="radec",
        searchterm=line,
    )
    return obstarget


def altaz_object(prechosen=None):
    """Create a target from Altitude and Azimuth values.
    These is a fixed point for the telescope, it will not move as the earth rotates.
    Useful for meteor watching, or timelapse capture of something moving."""
    if prechosen is None:
        print("altaz_object: Create a target from Altitude and Azimuth values.")
        print("Definition format: ALT ddd.dddd AZ ddd.dddd name")
    line = ""
    obstarget = None
    while True:
        if (
            prechosen is not None
        ):  # We're receiving a prechosen target description, don't ask user.
            line = prechosen
            prechosen = None  # If there's a problem, then we'll ask the user instead.
        else:
            line = input(
                "Definition ('x' to quit): "
            )  # As user for target description.
        if len(line) < 1:
            continue  # No input, ask again.
        if line.lower() == "x":  # Cancel
            return None
        lineitems = line.lower().split()
        if lineitems[0] != "alt":
            print(TextColor.red("1st term must be 'alt'. Try again"))
            continue  # Try again.
        if lineitems[2] != "az":
            print(TextColor.red("5th term must be 'az'. Try again"))
            continue  # Try again.
        name = lineitems[4]
        alt = text_to_float(lineitems[1])
        # Set default limits on positions available. Will be used if motor configurations are unavailable.
        minaz = 0
        maxaz = 360
        minalt = -90
        maxalt = 90
        for (
            i
        ) in (
            MotorControls
        ):  # Use the motor configurations to limit the positions available.
            if i.MotorName == "azimuth":
                minaz = i.MinAngle
                maxaz = i.MaxAngle
            elif i.MotorName == "altitude":
                minalt = i.MinAngle
                maxalt = i.MaxAngle
        if alt is None or alt < minalt or alt > maxalt:
            print(
                TextColor.red(
                    "2nd term must be float ALTITUDE degrees (",
                    minalt,
                    "to",
                    maxalt,
                    "). Try again",
                )
            )
            continue  # Try again.
        az = text_to_float(lineitems[3])
        if az is None or az < minaz or az > maxaz:
            print(
                TextColor.red(
                    "4th term must be float AZIMUTH degrees (",
                    minaz,
                    "to",
                    maxaz,
                    "). Try again",
                )
            )
            continue  # Try again.
        break
    main_log.log(
        "altaz_object: Coordinates of",
        name,
        "are",
        az_alt_text(az, alt),
        terminal=False,
    )
    es = FixedPoint(name=name, alt=alt, az=az)
    obstarget = AstroTarget(
        es,
        name=name,
        objecttype="altaz",
        description=name,
        magnitude=0.0,
        searchgroup="altaz",
        searchterm=line,
    )
    return obstarget


def choose_filter_script(default=None):
    """From the available filter scripts, choose one to apply to a task."""
    option = None
    FilterOptions = {"None": {"label": "None", "value": None}}
    for key, item in pilomarimage.FILTERSCRIPTS.items():
        FilterOptions[key] = {"label": key, "value": key}
    FilterMenu = OptionMenu(
        FilterOptions, "Select filter", titlefg=MENU_TITLE_FG, titlebg=MENU_TITLE_BG
    )

    option, found = (
        FilterMenu.prompt()
    )  # Ask the user to select an option from the menu.
    if not found:  # Nothing was selected. Return the default value instead.
        option = default
    return option


def select_latest_filter():
    """Prompt the user to select a Tracking image filter."""
    print("Choose the filter script to use for processing LATEST TRACKING images.")
    params.latest_tracking_filter = choose_filter_script(
        default=params.latest_tracking_filter
    )
    print("You chose:", params.latest_tracking_filter)
    if params.latest_tracking_filter is None:
        print("LATEST TRACKING images will not be filtered.")
    else:
        print("LATEST TRACKING images will have the following filters applied.")
        ftemp = pilomarimage.FILTERSCRIPTS[
            params.latest_tracking_filter
        ]  # Get the filter details.
        # List the filter steps.
        for key, value in ftemp.items():
            method = value.get("method", None)
            comment = value.get("comment", "")
            if comment != "":
                comment = "(" + comment + ")"
            print(" -", key, "step applies", method, "filter", comment)
    main_log.log(
        "SelectLatestFilter: has set", params.latest_tracking_filter, terminal=False
    )


def test_latest_filter():
    """Test the result of the LATESTTRACKING image filter on an example image."""
    print(
        TextColor.yellow(
            "Test the LATEST TRACKING image filter script on an example image."
        )
    )
    print("Choose an image to process:")
    sourcefile = ""
    outputfile = FolderHandler.prep_file("temp", "TestLatestFilter.jpg")
    while not os.path.exists(sourcefile):
        sourcefile = input(TextColor.cyan("Filepath ('x' to quit): "))
        if sourcefile.lower() == "x":
            return  # Quit.
        if not os.path.exists(sourcefile):
            print(TextColor.red(sourcefile, "does not exist, try again."))
    # Create pilomarimage instance for the file.
    image = pilomarimage(name="testlatestfilter", logger=main_log)
    image.LoadFile(sourcefile)
    print("Running", params.latest_tracking_filter, "against", sourcefile, "...")
    image.RunFilterScript(params.latest_tracking_filter)
    image.SaveFile(outputfile)
    print("Result is saved in", outputfile)


def choose_aurora(prechosen=None):
    """Set up to create a video of the Aurora."""
    if prechosen is None:
        print(TextColor.yellow("Choosing Aurora:"))
    if params._home_lat_val >= 0:  # Due North.
        TargetAz = max(
            0.0, AzimuthControl.min_angle
        )  # Cannot be below minimum allowed angle.
        Name = "aurora_borealis"
    else:  # Due South.
        TargetAz = min(180, AzimuthControl.max_angle)
        Name = "aurora_australis"
    TargetAlt = params.aurora_camera_altitude  # Altitude angle for the camera.
    # TargetAlt = max(TargetAlt,AltitudeControl.MinAngle) # Cannot be below the minimum allowed angle. *!*
    TargetAlt = max(
        TargetAlt, AltitudeControl.min_observation_angle
    )  # Cannot be below the minimum allowed angle. *!*
    es = FixedPoint(name=Name, alt=TargetAlt, az=TargetAz)
    obstarget = AstroTarget(
        es,
        name=Name,
        objecttype="aurora",
        description=Name,
        magnitude=2.0,
        searchgroup="aurora",
        searchterm="aurora",
    )
    if prechosen is None:
        print(TextColor.yellow("Choosen:", Name))
        print(
            "Camera will point at",
            az_alt_text(TargetAz, TargetAlt, symbol=DEGREE_SYMBOL),
            "to capture potential aurora.",
        )
    return obstarget


session_history = SessionList("History")  # Create a session history instance.
session_history.load_from_json(
    HistoryJsonFile
)  # Load any previous history entries from the json disc file.


def choose_history(selection=None):
    """User can retrieve earlier target selections and the exposure time.
    This allows resuming earlier observations more safely."""
    obstarget = None  # No target selected yet.
    cols, rows = (
        get_terminal_size()
    )  # How wide is the display? Format the options list to fit. *Q* TO COMPLETE
    print(TextColor.yellow("Choose an object from an earlier observation."))
    print("Listing from " + HistoryJsonFile)
    if not os.path.exists(HistoryJsonFile):
        print(
            TextColor.red("choose_history: " + HistoryJsonFile + " does not yet exist.")
        )
        print(TextColor.red("You have not chosen any targets yet."))
        print(TextColor.red("Choose a target some other way first."))
        return obstarget
    # Construct a list of unique observation options from history.
    session_history.load_from_json(HistoryJsonFile)  # Refresh the history list.

    # List the unique options. 'Lines' contains the unique observation details on offer.
    print("")
    temptime = (
        skyfield_now()
    )  # Use the same timestamp for everything in the list, otherwise repeated objects show inconsistent positions.
    print(
        " Line  Last used (UTC)     Name                 Category   Exposure  Current alt / az       RiseSet Other"
    )
    #       123456 1234567890123456789 12345678901234567890 1234567890 12345678901234567890123456789012345678901234567890
    spacecount = 0  # Put a gap every 5 lines for readability.
    count = 0
    for se in session_history.session_list:
        displine = ""  # Empty line until we have constructed all the details.
        displine = str(se.LastObserved)[:19] + " "  # Timestamp
        displine += se.Name.ljust(20)[:20] + " "  # Name
        displine += se.SearchGroup.ljust(10)[:10] + " "  # Category
        displine += str(se.ExposureSeconds).rjust(5)[:5] + "s. "  # Exposure
        miscline = ""  # Miscellaneous info.
        if (
            se.TimelapsePeriod is not None and se.TimelapsePeriod > 0
        ):  # Timelapse is available.
            miscline += "Timelapse " + str(se.TimelapsePeriod) + "s. "
        if se.SearchGroup == "solar":
            temptarget = choose_solar(se.SearchTerm)  # Create a solar system target.
        elif se.SearchGroup == "satellite":
            temptarget = choose_satellite(se.SearchTerm)  # Create a satellite target.
        elif se.SearchGroup == "hipparcos":
            temptarget = choose_hipparcos(
                se.SearchTerm
            )  # Create a hipparcos star target.
        elif se.SearchGroup == "messier":
            temptarget = choose_messier(
                se.SearchTerm, sizewarning=False
            )  # Create a Messier object target. Don't warn about small targets at this point.
        elif se.SearchGroup == "radec":
            temptarget = radec_object(
                se.SearchTerm
            )  # Create an object from radec co-ordinates.
        elif se.SearchGroup == "altaz":
            temptarget = altaz_object(
                se.SearchTerm
            )  # Create an object from alt/az co-ordinates.
        elif se.SearchGroup == "aurora":
            temptarget = choose_aurora(
                se.SearchTerm
            )  # Create an object from alt/az co-ordinates.
        elif se.SearchGroup == "meteor":
            temptarget = choose_meteor(
                se.SearchTerm
            )  # Create an object from meteor shower details.
        elif se.SearchGroup == "comet":
            temptarget = choose_comet(
                se.SearchTerm
            )  # Create an object from comet data.
        elif se.SearchGroup == "ngc":
            temptarget = choose_ngc(se.SearchTerm)  # Create an object from ngc data.
        else:
            temptarget = None
        if temptarget is not None:  # Work out where it is in the sky at the moment.
            az, alt = temptarget.az_alt_degrees(time=temptime)  # Where is it?
            if az <= 180:
                direction = SYMBOLS[
                    "up"
                ]  # Indicate if it's rising or setting. In northern hemisphere the azimuth is usually enough.
            else:
                direction = SYMBOLS["down"]
            visline = (
                "   "
                + deg_3dp(alt).rjust(7)
                + " "
                + direction
                + " / "
                + deg_3dp(az).rjust(8)
            )
            risesetline = temptarget.next_rise_set_hhmm(window=24).ljust(7)[
                :7
            ]  # When is next RISE/SET?
            if not temptarget.visible(time=temptime):
                print(
                    TextColor.red(str(count).rjust(6)[:6]),
                    displine,
                    TextColor.red(visline),
                    risesetline,
                    miscline,
                )
            elif temptarget.approaching_limit(time=temptime):
                print(
                    TextColor.yellow(str(count).rjust(6)[:6]),
                    displine,
                    TextColor.yellow(visline),
                    risesetline,
                    miscline,
                )
            else:
                print(
                    TextColor.green(str(count).rjust(6)[:6]),
                    displine,
                    TextColor.green(visline),
                    risesetline,
                    miscline,
                )
        else:
            print(
                TextColor.yellow(str(count).rjust(6)[:6]), displine
            )  # No temptarget set.
        count += 1
        if count % 5 == 0:
            print("")  # Blank line to make the table more readable if it is very large.
    main_log.log(
        "choose_history: Selected " + str(count) + " unique options from history.",
        terminal=False,
    )
    # User must select one of the listed options.
    temp = ""  # No choice made yet.
    while temp == "":
        temp = input(TextColor.cyan("Select history line (x to quit): "))
        if temp.lower() == "x":  # Cancel selection.
            break
        i = text_to_int(temp)  # Make sure it is a valid choice.
        if i is not None and i >= 0 and i < count:
            main_log.log("choose_history: Selected entry ", i, terminal=False)
            # Get the record.
            se = None
            for j, sf in enumerate(session_history.session_list):
                if i == j:
                    se = sf  # Found the requested entry.
            if se == None:  # Didn't select an entry.
                main_log.log("choose_history: Failed to select line", i, level="error")
                break
            camera_in_use.set_timelapse(se.TimelapsePeriod)
            camera_in_use.exposure_seconds = se.ExposureSeconds
            if se.SearchGroup == "solar":
                obstarget = choose_solar(se.SearchTerm)  # Create a solar system target.
                break
            elif se.SearchGroup == "satellite":
                obstarget = choose_satellite(
                    se.SearchTerm
                )  # Create a satellite target.
                break
            elif se.SearchGroup == "hipparcos":
                obstarget = choose_hipparcos(
                    se.SearchTerm
                )  # Create a hipparcos star target.
                break
            elif se.SearchGroup == "messier":
                obstarget = choose_messier(
                    se.SearchTerm
                )  # Create a Messier object target.
                break
            elif se.SearchGroup == "radec":
                obstarget = radec_object(
                    se.SearchTerm
                )  # Create an object from radec co-ordinates.
                break
            elif se.SearchGroup == "altaz":
                obstarget = altaz_object(
                    se.SearchTerm
                )  # Create an object from alt/az co-ordinates.
                break
            elif se.SearchGroup == "aurora":
                obstarget = choose_aurora(
                    se.SearchTerm
                )  # Create an object from alt/az co-ordinates.
                break
            elif se.SearchGroup == "meteor":
                obstarget = choose_meteor(
                    se.SearchTerm
                )  # Create an object from meteor shower details.
                break
            elif se.SearchGroup == "comet":
                obstarget = choose_comet(
                    se.SearchTerm
                )  # Create an object from comet details.
                break
            elif se.SearchGroup == "ngc":
                obstarget = choose_ngc(
                    se.SearchTerm
                )  # Create an object from NGC details.
                break
            else:
                main_log.log(
                    "choose_history: Unrecognised searchgroup: Line " + str(temp),
                    level="error",
                )
        # If we got this far, the choice was not valid. Reset and ask again.
        temp = ""  # Reset and ask again.
    return obstarget


def choose_last_target():
    """Quick resume of previous observation target and settings."""
    main_log.log("choose_last_target: Begin", terminal=False)
    obstarget = None  # No target selected yet.
    if not os.path.exists(HistoryJsonFile):  # No file to process yet.
        print(
            TextColor.red(
                "choose_last_target: " + HistoryJsonFile + " does not yet exist."
            )
        )
        print(TextColor.red("You have not chosen any targets yet."))
        print(TextColor.red("Choose a target some other way first."))
        return obstarget
    # Construct a list of unique observation options from history.
    session_history.load_from_json(HistoryJsonFile)  # Refresh the history list.

    se = session_history.session_list[0]  # Read first entry.
    camera_in_use.set_timelapse(se.TimelapsePeriod)
    camera_in_use.exposure_seconds = se.ExposureSeconds
    main_log.log("choose_last_target: Selected " + line, terminal=False)
    if se.SearchGroup == "solar":
        obstarget = choose_solar(se.SearchTerm)  # Create a solar system target.
    elif se.SearchGroup == "satellite":
        obstarget = choose_satellite(se.SearchTerm)  # Create a satellite target.
    elif se.SearchGroup == "hipparcos":
        obstarget = choose_hipparcos(se.SearchTerm)  # Create a hipparcos star target.
    elif se.SearchGroup == "messier":
        obstarget = choose_messier(se.SearchTerm)  # Create a Messier object target.
    elif se.SearchGroup == "radec":
        obstarget = radec_object(
            se.SearchTerm
        )  # Create an object from radec co-ordinates.
    elif se.SearchGroup == "altaz":
        obstarget = altaz_object(
            se.SearchTerm
        )  # Create an object from alt/az co-ordinates.
    elif se.SearchGroup == "aurora":
        obstarget = choose_aurora(
            se.SearchTerm
        )  # Create an object from alt/az co-ordinates.
    elif se.SearchGroup == "meteor":
        obstarget = choose_meteor(
            se.SearchTerm
        )  # Create an object from meteor shower details.
    elif se.SearchGroup == "comet":
        obstarget = choose_comet(se.SearchTerm)  # Create an object from comet details.
    elif se.SearchGroup == "ngc":
        obstarget = choose_ngc(se.SearchTerm)  # Create an object from NGC details.
    else:
        main_log.log(
            "choose_last_target: Unrecognised searchgroup: Line " + str(line),
            level="error",
        )
    return obstarget


def rise_set_string(otarget: AstroTarget):
    """Return a string listing RISE and SET times of target.
    otarget should be an instance of the target class.
    EARTH CENTRIC objects raise an error here. So they are ignored."""
    try:
        rise, set = otarget.rise_set()
    except Exception:
        rise = set = None
        main_log.log(
            "rise_set_string(): Failed. rise/set set to None.",
            terminal=False,
            level="warning",
        )
    if rise is not None:
        if rise < set:  # Put resulting RISE and SET times in chronological sequence.
            RS = (
                " Target Rise: "
                + str(rise).split(".")[0]
                + " UTC , Set: "
                + str(set).split(".")[0]
                + " UTC"
            )
        else:
            RS = (
                " Target Set: "
                + str(set).split(".")[0]
                + " UTC , Rise: "
                + str(rise).split(".")[0]
                + " UTC"
            )
    else:
        if otarget.visible():
            RS = " Target is permanently above the horizon, it will not set."
        else:
            RS = " Target is permanently below the horizon, it will not rise."
    return RS


def target_selection():
    """Submenu to allow target selection.
    Several different groups of target are available.
    Select the group here, then pass control to a specific selection routine."""
    option = None
    TargetOptions = {
        "ResumeLastObservation": {"label": "Resume last observation", "value": "LAST"},
        "RepeatEarlierObservations": {
            "label": "Repeat earlier observations",
            "value": "HISTORY",
        },
        "SolarSystemObject": {"label": "Solar system object", "value": "SOLAR"},
        "HipparcosObject": {"label": "Hipparcos star catalog", "value": "HIP"},
        "MessierObject": {"label": "Messier catalog", "value": "MESSIER"},
        "NGC": {"label": "New General Catalog (NGC)", "value": "NGC"},
        "Comet": {"label": "Comet", "value": "COMET"},
        "Meteor": {"label": "Meteor shower", "value": "METEOR"},
        "Aurora": {"label": "Aurora", "value": "AURORA"},
        "EarthSatellite": {"label": "Space stations/satellites", "value": "SATELLITE"},
        "RADEC": {"label": "RA-DEC co-ordinates", "value": "RADEC"},
        "ALTAZ": {"label": "Fixed ALT-AZ point", "value": "ALTAZ"},
    }
    TargetMenu = OptionMenu(
        TargetOptions, "Select target", titlefg=MENU_TITLE_FG, titlebg=MENU_TITLE_BG
    )

    while option is None:
        obstarget = None
        option, _ = (
            TargetMenu.prompt()
        )  # Ask the user to select an option from the menu.
        # option contains the selected target, or None.
        if option is None:
            option = "LAST"  # If the user quit the menu without selecting anything, default to the last target.
        if option == "LAST":
            obstarget = choose_last_target()
        elif option == "HISTORY":
            obstarget = choose_history()
        elif option == "SOLAR":
            obstarget = choose_solar()
        elif option == "SATELLITE":
            obstarget = choose_satellite()
        elif option == "HIP":
            obstarget = choose_hipparcos()
        elif option == "MESSIER":
            obstarget = choose_messier()
        elif option == "RADEC":
            obstarget = radec_object()
        elif option == "METEOR":
            obstarget = choose_meteor()
        elif option == "COMET":
            obstarget = choose_comet()
        elif option == "AURORA":
            obstarget = choose_aurora()
        elif option == "ALTAZ":
            obstarget = altaz_object()
        elif option == "NGC":
            obstarget = choose_ngc()
        else:
            option = None
        if (
            obstarget is not None and not obstarget.visible()
        ):  # Target was chosen, but is not currently visible.
            if option == "SATELLITE" or obstarget.name in [
                "iss",
                "css",
            ]:  # RiseSet calc does not work for these yet.
                pass  # Satellites don't matter, they may become visible very soon.
            else:  # Other targets probably are not visible for some time, warn the user.
                az, alt = obstarget.az_alt_degrees()  # Current az/alt of the target.
                ra, dec = obstarget.ra_dec_degrees()  # Current RA/DEC of the target.
                rh, rm, rs = angle_to_hms(ra)  # Convert RA degrees into Hrs, Mins, Secs
                dd, dm, ds = angle_to_dms(
                    dec
                )  # Convert DEC degrees into Deg, Mins, Secs
                linelist = [
                    obstarget.name
                    + " is not currently in range ("
                    + az_alt_text(az, alt)
                    + ").",
                    "RA: "
                    + str(rh)
                    + "h "
                    + str(rm)
                    + "' "
                    + str(round(rs, 3))
                    + '" '
                    + "Dec: "
                    + str(dd)
                    + DEGREE_SYMBOL
                    + " "
                    + str(dm)
                    + "' "
                    + str(round(ds, 3))
                    + '"',
                    rise_set_string(obstarget),
                ]
                TextColor.text_box(linelist, fg=TextColor.RED, bg=TextColor.BLACK)
                temp = ask_yes_no(
                    TextColor.cyan("Do you want to continue ?[y/N]"), False
                )
                if not temp:
                    option = None  # User wants to try a different target, ask the user again.
        if obstarget is None:
            option = None  # No target selected, so ask the user again.
        if option is None:
            print(
                TextColor.red("No target selected: Please try again.")
            )  # No success, so ask the user again.

    return obstarget


# User MUST select a target to proceed.
session.target = None  # No target yet.
if ResumeObservation:  # Try to resume with last known target.
    session.target = choose_last_target()
if session.target is None:  # Still no valid target. Ask the user.
    print(TextColor.yellow("You must select a target to start the program."))
    session.target = target_selection()
camera_in_use.set_observation_parameters(
    session
)  # Set target specific parameters for the camera.
# Create some other major objects to be included in the TargetChart window.
define_session_folders(
    session.target.name, camera_in_use.exposure_seconds
)  # # This assigns folder names for all the image types.

# ----------------------------------------------------------
# Menu options
# ----------------------------------------------------------


def home_position():
    """Return the whole mechanism to its home position.
    If the Microcontroller resets at any time, this repeats until successful."""
    print(TextColor.yellow("home_position"))
    if params.require_restart:
        restart_required()
        return

    stop_motors()  # Clear anything that's still programmed for the motors.
    session.set_motor_control_mode(
        "direct"
    )  # We will directly control the movement of the microcontroller, no trajectory needs sending.
    main_log.log("home_position begin", terminal=False)
    loopcounter = 0
    looplimit = 50
    for i in MotorControls:  # Handle each motor in turn.
        main_log.log("home_position: Homing ", i.MotorName, "motor.", terminal=False)
        i.MonitorMove = True  # Display movement progress on the terminal.
        while not i.CompareAngles(
            i.CurrentAngle, i.RestAngle
        ):  # Repeat until the motor is in position.
            main_log.log(
                "home_position:",
                i.MotorName,
                "motor from",
                deg_3dp(i.CurrentAngle) + DEGREE_SYMBOL,
                "to home",
                deg_3dp(i.RestAngle) + DEGREE_SYMBOL,
                terminal=True,
            )
            i.GoToAngle(i.RestAngle)
            main_log.log(
                "home_position:",
                i.MotorName,
                "motor parked at",
                deg_3dp(i.CurrentAngle) + DEGREE_SYMBOL + ".",
                terminal=False,
            )
            loopcounter += 1
            if loopcounter >= looplimit:
                main_log.log(
                    "home_position:",
                    i.MotorName,
                    "After",
                    looplimit,
                    "attempts, motor still not homed. Abandoning the move at",
                    deg_3dp(i.CurrentAngle) + DEGREE_SYMBOL,
                    ".",
                    level="error",
                )
                break
        i.MonitorMove = False  # Suppress movement progress on the terminal.
    print(TextColor.yellow("Done.") + TextColor.clearlineforward())
    main_log.log("home_position end", terminal=False)
    return True


def set_motor_angle(motor_name=None):
    """Move motor to specific angle."""
    print(TextColor.yellow("set_motor_angle " + str(motor_name) + "."))
    if (
        params.require_restart
    ):  # Warn that movements cannot be made until software is restarted.
        restart_required()
        return
    print("(The motor will physically move.)")
    c = ""
    for i in MotorControls:  # Scan all the motors available.
        if i.MotorName == motor_name:  # Select the correct motor.
            while c.lower() != "x":  # Loop until user quits.
                print(
                    i.MotorName,
                    "is currently at",
                    deg_3dp(i.CurrentAngle) + DEGREE_SYMBOL,
                )
                print(
                    "Enter target angle between "
                    + str(i.MinAngle)
                    + DEGREE_SYMBOL
                    + " and "
                    + str(i.MaxAngle)
                    + DEGREE_SYMBOL
                )
                c = input(TextColor.cyan("Enter angle (or 'x' to exit) : "))  # Python3
                if len(c) < 1:  # No valid input.
                    print("Try again.")
                    continue  # Restart loop.
                if c.lower() == "x":
                    print("Done.")
                    break  # Quit loop.
                v = text_to_float(c)
                if v is not None:  # It is not a valid float.
                    if (
                        v < i.MinAngle or v > i.MaxAngle
                    ):  # It is out of range for the motor.
                        print("Out of range. Try again.")
                        continue  # Restart loop.
                    # Value is acceptable, let's move the motor.
                    i.MonitorMove = True
                    i.GoToAngle(v)  # Set the new target position.
                    i.MonitorMove = False
                    continue  # Restart loop.
                print("'" + c + "' is not recognised. Try again.")
            print(
                i.MotorName, "is currently at", deg_3dp(i.CurrentAngle) + DEGREE_SYMBOL
            )
    stop_motors()  # Reset motor condition to prevent further movement.
    main_log.log("set_motor_angle " + motor_name + " Completed.", terminal=False)
    print(TextColor.yellow("Done.") + TextColor.clearlineforward())
    return True


def azimuth_angle():  # For menu
    set_motor_angle("azimuth")


def altitude_angle():  # For menu
    set_motor_angle("altitude")


def exercise_motor(motor_name=None):
    print(TextColor.yellow("exercise_motor " + str(motor_name) + "."))
    if (
        params.require_restart
    ):  # Warn that movements cannot be made until software is restarted.
        restart_required()
        return
    a = ""
    sweep = 0
    lFound = False
    stop_motors()  # Clear anything that's already programmed for the motors.

    session.set_motor_control_mode(
        "direct"
    )  # We will directly control the movement of the microcontroller. no trajectory needs sending.
    while a != "x":
        sweep += 1
        for i in MotorControls:
            if i.MotorName == motor_name:
                print(str(now_utc()) + " Begin sweep " + str(sweep))
                print(
                    str(now_utc())
                    + " - Move to min angle ("
                    + str(i.MinAngle)
                    + DEGREE_SYMBOL
                    + ")"
                )
                i.GoToAngle(i.MinAngle)
                print(str(now_utc()) + " - Home the motor.")
                i.GoToAngle(i.RestAngle)
                print(
                    str(now_utc())
                    + " - Move to max angle ("
                    + str(i.MaxAngle)
                    + DEGREE_SYMBOL
                    + ")"
                )
                i.GoToAngle(i.MaxAngle)
                print(str(now_utc()) + " - Home the motor.")
                i.GoToAngle(i.RestAngle)
                lFound = True
        a = input("Press [ENTER] to repeat, 'x' to quit.")  # Python3
        a = a.lower()
    print(str(now_utc()) + " Completed.")
    stop_motors()  # Reset motor condition to prevent further movement.
    if lFound != True:  # We didn't find the motor!
        main_log.log(
            "exercise_motor: Motor '"
            + str(motor_name)
            + "' was not recognised. Nothing moved.",
            level="error",
        )
    main_log.log("exercise_motor " + motor_name + " completed.", terminal=False)
    print(TextColor.yellow("Done.") + TextColor.clearlineforward())
    return True


def exercise_motor_azimuth():  # For menu
    exercise_motor("azimuth")


def exercise_motor_altitude():  # For menu
    exercise_motor("altitude")


def tune_position(motor_name=None):
    """Finetune the position of the mechanism. This version asks the user to enter the adjustment parameter.
    You can move a motor with this function, but its virtual position will not be updated.
    It physically moves the motor, but registers the position as it was at the START of the move.
    Use this to finetune the position if the telescope hasn't been placed properly, or the positioning is wrong.
    Scenarios are when you are initially setting up the telescope and finetuning the physical alignment to match the theoretical one.
    Or if the motor has slipped during an observation and you want to correct for that.
    The optical drift tracking mechanism uses this function to keep the target centered too.
    """
    main_log.log("tune_position:", motor_name, "begin", terminal=False)
    if (
        params.require_restart
    ):  # Warn that movements cannot be made until software is restarted.
        restart_required()
        return
    print(TextColor.yellow("tune_position " + str(motor_name) + "."))
    print(
        TextColor.white(
            "This will move the motor to match where the computer thinks it is pointing.",
            invert=True,
        )
    )
    print(
        TextColor.white(
            "This will finetune the physical position of the motor, but leave its logical position unchanged."
        )
    )
    print(
        TextColor.white(
            "You are making the motor physically point to where the computer already THINKS it is pointing."
        )
    )
    lFound = False
    for i in MotorControls:
        if i.MotorName == motor_name:
            print("Motor enabled.")
            fullrevsteps = i.AngleToStep(360.0)
            print("- A full revolution is " + str(fullrevsteps) + " steps.")
            print("- 1 degree is " + str(i.AngleToStep(1.0)) + " steps.")
            print("- 100 steps is " + str(i.StepToAngle(100)) + DEGREE_SYMBOL + ".")
            circumference = math.pi * 300.0  # Dome is 300mm outside diameter.
            print(
                "- Circumference of body circle is "
                + str(round(circumference, 0))
                + "mm."
            )
            print(
                "- 10mm of circumference movement is "
                + str(round(10 * fullrevsteps / circumference, 0))
                + "steps."
            )
            adj = None
            while adj != "x":
                adj = (
                    input(
                        TextColor.cyan(
                            motor_name.capitalize()
                            + " steps to move (+/-), 'x' to exit : "
                        )
                    )
                    .strip()
                    .lower()
                )  # Python3
                if adj == "x":
                    break
                delta = text_to_int(adj)
                if delta is None:
                    print("Not an integer. Try again or 'x' to exit")
                else:
                    print("Moving", delta, "steps")
                    i.tune_position(delta)
            lFound = True
    if lFound:
        DriftTracker.Reset()  # Reset optical tracking because we've moved the camera.
    else:  # We didn't find the motor!
        main_log.log(
            "tune_position: Motor '",
            str(motor_name),
            "' was not recognised. Nothing moved.",
            level="error",
        )
    print(TextColor.yellow("Done.") + TextColor.clearlineforward())
    main_log.log("tune_position", motor_name, "complete.", terminal=False)
    return True


def tune_position_azimuth():  # For menu call.
    tune_position("azimuth")


def tune_position_altitude():  # For menu call
    tune_position("altitude")


def ask_exposure_time(p):
    print(TextColor.yellow("SetExposureTime (Currently " + str(p) + " seconds)."))
    v = input(TextColor.cyan("New exposure time in seconds (or RETURN) : "))  # Python3
    if len(v) > 0:
        v = text_to_float(v)
        if v is not None:
            p = v
    if p > sensor_in_use.max_exposure_seconds:
        print(
            "Exposure cannot exceed "
            + str(sensor_in_use.max_exposure_seconds)
            + "seconds. Clipped."
        )
        p = sensor_in_use.max_exposure_seconds
    if p < sensor_in_use.min_exposure_seconds:
        print(
            "Exposure cannot be below "
            + str(sensor_in_use.min_exposure_seconds)
            + "seconds. Clipped."
        )
        p = sensor_in_use.min_exposure_seconds
    main_log.log("SetExposureTime: Value=" + str(p) + " seconds.", terminal=False)
    return p


def adjust_exposure_time(factor=1.0):  # Double exposure time.
    oldtime = camera_in_use.exposure_seconds
    newtime = round(min(sensor_in_use.max_exposure_seconds, oldtime * float(factor)), 7)
    cam_log.log(
        "adjust_exposure_time(): From", oldtime, "s", "to", newtime, "s", terminal=False
    )
    camera_in_use.exposure_seconds = newtime
    define_session_folders(
        session.target.name, camera_in_use.exposure_seconds
    )  # This assigns folder names for all the image types.
    document_session()
    if factor >= 1.0:
        CameraWindow.print(
            now_hour_minute_sec()
            + " Increase exposure to "
            + str(camera_in_use.exposure_seconds)
            + "s"
        )
        DevWindow.print(
            now_hour_minute_sec()
            + " Increase exposure to "
            + str(camera_in_use.exposure_seconds)
            + "s"
        )
    else:
        CameraWindow.print(
            now_hour_minute_sec()
            + " Decrease exposure to "
            + str(camera_in_use.exposure_seconds)
            + "s"
        )
        DevWindow.print(
            now_hour_minute_sec()
            + " Decrease exposure to "
            + str(camera_in_use.exposure_seconds)
            + "s"
        )


def menu_set_exposure_time():  # For menu
    if check_image_set():  # Only allow a change if the current image set is acceptable.
        camera_in_use.exposure_seconds = ask_exposure_time(
            camera_in_use.exposure_seconds
        )
        define_session_folders(
            session.target.name, camera_in_use.exposure_seconds
        )  # This assigns folder names for all the image types.
        document_session()
        DriftTracker.Reset()


def set_camera_timelapse(p):
    print(TextColor.yellow("SetTimelapse (Currently " + str(p) + " seconds)."))
    print("This is the number of seconds BETWEEN each LIGHT image captured.")
    print("0 means there is no delay.")
    v = input(
        TextColor.cyan("New timelapse delay in seconds (or RETURN) : ")
    )  # Python3
    if len(v) > 0:  # Input given
        v = text_to_float(v)  # Convert to float or None.
        if v is not None:  # Can use the value.
            p = v
    if p == 0.0:
        p = None  # 0 values stored as None, 'inactive'.
    if p < 0:
        print("Timelapse delay cannot be negative.")
        p = camera_in_use.timelapse_seconds
    main_log.log("SetTimelapse: Value=" + str(p) + " seconds.", terminal=True)
    return p


def set_batch_size(p):
    print(TextColor.yellow("set_batch_size (Currently " + str(p) + " frames)."))
    print("This is the number of frames to capture when taking LIGHT images.")
    print("These are the actual observation images.")
    print(
        "This does not change the number of CONTROL images taken for FLAT, DARK or BIAS images."
    )
    v = input(TextColor.cyan("Light images batch size (or RETURN) : "))  # Python3
    if len(v) > 0:
        v = text_to_int(v)
        if v is not None:
            p = v
    main_log.log("set_batch_size: Value=" + str(p), terminal=False)
    return p


def set_control_batch_size(p):
    print(TextColor.yellow("set_control_batch_size (Currently " + str(p) + " frames)."))
    print(
        "This is the number of frames to capture when taking FLAT, DARK & BIAS images."
    )
    print("This does not change the number of LIGHT (observation) images taken.")
    print("HINT: A good number is around 15-20 images.")
    v = input(TextColor.cyan("Control batch size (or RETURN) : "))  # Python3
    if len(v) > 0:
        v = text_to_int(v)
        if v is not None:
            p = v
    main_log.log("set_control_batch_size: Value=" + str(p), terminal=False)
    return p


def dynamic_scale(targetpix, pixelsperstep):
    """For markup_preview: Calculate an appropriate stepscale depending upon the movement mechanism resolution.

    The Preview images show a scale indicating how far motor steps will move the camera relative to the image.
    Depending upon the gearing, motor and microstepping chosen this scale can be very variable.
    - Some scales can be too large to help the user choose values.
    - Some scales can be too small to make out the scales at all.
    This function tries to find a scale that is readable on the image. Typically showing labels at least every 200pixels apart.

    targetpix = An initial target pixel gap between tick marks.
    pixelsperstep = How many image pixels represent a single stepper motor step in the current arrangement.

    Returns the number of motor steps to use between tickmarks.
    - The value is returned as semi-logarithmic to be useful to the users.
      It will be multiples of 1,2 or 5 at an appropriate power of 10.
      100,200,500,1000,2000,5000,10000,20000,50000,... etc
    """
    try:
        stepsperpixel = 1 / pixelsperstep  # How many steps represent a single pixel?
    except:
        stepsperpixel = targetpix  # If the above fails, use the target anyway.
    stepspertargetpixels = (
        stepsperpixel * targetpix
    )  # How many steps represent the ideal tick mark gap?
    # Clean the steps to a rounded value (1,2,5,10,20,50,100,200,500,1000,2000,5000,10000,20000,50000,...)
    gaps = [
        100,
        200,
        500,
        1000,
        2000,
        5000,
        10000,
        20000,
        50000,
        100000,
    ]  # These are acceptable gaps, they would make sense to a user.
    for gap in gaps:
        if stepspertargetpixels < gap:
            stepspertargetpixels = gap  # Round up to nearest acceptable gap.
            break
    cam_log.log(
        "dynamic_scale: tp",
        targetpix,
        "pps",
        pixelsperstep,
        "ip",
        stepsperpixel,
        "sptp",
        stepspertargetpixels,
        terminal=False,
    )
    cam_log.log(
        "dynamic_scale: For step labels to be at least",
        targetpix,
        "pixels apart, labels will be every",
        stepspertargetpixels,
        "steps",
        terminal=False,
    )
    cam_log.log(
        "dynamic_scale: Labels will be every",
        int(pixelsperstep * stepspertargetpixels),
        "pixels",
        terminal=False,
    )
    return int(stepspertargetpixels)


def markup_preview(drift_pixels_x=None, drift_pixels_y=None, astrotime=None):
    """Take the last image registered in camera_in_use.image and mark up various alignment indicators and labels.
    OpenCV version of markup_preview.
    astrotime = You can specify the date/time that the preview is calculated for.
    applydistortion = The image can be artificially distorted to try to match an actual photo more closely.
    """
    cam_log.log(
        "markup_preview: Start(",
        drift_pixels_x,
        drift_pixels_y,
        astrotime,
        ")",
        terminal=False,
    )
    RoutineStart = now_utc()  # Note the time that this routine starts.
    if astrotime is not None:  # Calculate for a specific timestamp.
        t = astrotime
    else:
        t = (
            skyfield_now()
        )  # Current timestamp in 'astro' time. If there's a delay then there may be some mismatch in placing objects. # Offset supported.
    cam_log.log("markup_preview: MarkupTime:", ts_to_datetime(t), terminal=False)
    cam_log.log(
        "markup_preview: camera_in_use.capture_start:",
        camera_in_use.capture_start,
        terminal=False,
    )
    cam_log.log(
        "markup_preview: camera_in_use.capture_end:",
        camera_in_use.capture_end,
        terminal=False,
    )
    # The time should be the time of the actual photo! If several seconds have passed, then things will already have drifted!
    if (
        params.use_live_location
    ):  # Use the live target location rather than the last reported camera position for image processing.
        CentreAz, CentreAlt = (
            session.target.az_alt_degrees()
        )  # What is the alt/az location of the centre of the image?
    else:  # Use the last reported camera position. Deprecated.
        CentreAlt, CentreAz = (
            last_reported_alt_az()
        )  # What is the alt/az location of the centre of the image?
    CentreRa, CentreDec = (
        session.target.ra_dec_degrees()
    )  # Calculations for target from observer's location. Returns decimal degree values. *Q* Does this ever vary with time?
    cam_log.log(
        "markup_preview: Centre coordinates: alt/az:",
        CentreAlt,
        "/",
        CentreAz,
        "ra/dec:",
        CentreRa,
        CentreDec,
        terminal=False,
    )
    # load the image
    NewImageBuffer = pilomarimage(name="preview", logger=cam_log)
    NewImageBuffer.LoadBuffer(
        camera_in_use.image.ImageBuffer
    )  # Take it directly from memory
    NewImageBuffer.ChangeType("bgr")  # Make sure it's a colour image.
    width = NewImageBuffer.GetWidth()
    height = NewImageBuffer.GetHeight()
    centrex = int(width / 2)
    centrey = int(height / 2)
    filename = FolderHandler.prep_file(
        "preview", "preview_" + utc_time_stamp() + ".jpg"
    )
    lineheight = 40  # Pixels high per line of text.
    ## Find Hipparcos objects with specific ra/dec values (+/- 10degrees)
    MinRADeg = CentreRa - params.target_inclusion_radius
    MaxRADeg = CentreRa + params.target_inclusion_radius
    MinDecDeg = CentreDec - params.target_inclusion_radius
    MaxDecDeg = CentreDec + params.target_inclusion_radius

    if True:  # Alt/Az spherical grid.
        cam_log.log("markup_preview: ShowGrid", terminal=False)
        linestep = 1  # Grid lines every 1 degree
        compasslabels = {
            0: "NORTH",
            45: "NORTH-EAST",
            90: "EAST",
            135: "SOUTH-EAST",
            180: "SOUTH",
            225: "SOUTH-WEST",
            270: "WEST",
            315: "NORTH-WEST",
        }
        for iAlt in range(-10, 90, linestep):
            for iAz in range(0, 360, linestep):
                PlotAlt, PlotAz = relative_alt_az(
                    iAlt, iAz, CentreAlt, CentreAz
                )  # Plot point relative to centre of image.
                if abs(PlotAz) > params.target_inclusion_radius:
                    continue  # Outside the image, skip it.
                if abs(PlotAlt) > params.target_inclusion_radius:
                    continue  # Outside the image, skip it.
                PlotAlt2, PlotAz2 = relative_alt_az(
                    iAlt, iAz + linestep, CentreAlt, CentreAz
                )  # Plot point relative to centre of image + 1 unit of Azimuth.
                PlotAlt3, PlotAz3 = relative_alt_az(
                    iAlt + linestep, iAz, CentreAlt, CentreAz
                )  # Plot point relative to centre of image + 1 unit of Altitude.
                TempStarX, TempStarY = plot_relative_alt_az(
                    PlotAlt, PlotAz, height, width
                )
                TempStarX2, TempStarY2 = plot_relative_alt_az(
                    PlotAlt2, PlotAz2, height, width
                )  # From x,y
                TempStarX3, TempStarY3 = plot_relative_alt_az(
                    PlotAlt3, PlotAz3, height, width
                )  # To x,y
                if iAlt == 0:
                    h_thick, h_color = 5, (0, 0, 127)  # Horizon
                elif iAlt % 10 == 0:
                    h_thick, h_color = 2, (90, 90, 90)  # 10 degree line
                elif iAlt % 5 == 0:
                    h_thick, h_color = 2, (60, 60, 60)  # 5 degree line
                else:
                    h_thick, h_color = 1, (40, 40, 40)  # Default 1 degree line
                if iAz % 90 == 0:
                    v_thick, v_color = 3, (100, 100, 100)  # 90 degree line (N,S,E,W)
                elif iAz % 10 == 0:
                    v_thick, v_color = 2, (90, 90, 90)  # 10 degree line
                elif iAz % 5 == 0:
                    v_thick, v_color = 2, (60, 60, 60)  # 5 degree line
                else:
                    v_thick, v_color = 1, (40, 40, 40)  # Default 1 degree line
                # Tint sectors which are below the horizon deep red.
                if iAlt < 0:
                    polygon = [
                        (TempStarX, TempStarY),
                        (TempStarX2, TempStarY2),
                        (TempStarX2, TempStarY3),
                        (TempStarX, TempStarY3),
                    ]
                    NewImageBuffer.FillPolygon(polygon, color=(0, 0, 30))
                # Plot grid lines.
                NewImageBuffer.DrawLine(
                    (TempStarX, TempStarY),
                    (TempStarX2, TempStarY2),
                    color=h_color,
                    thickness=h_thick,
                )  # DIMGREY Link to neighbouring grid intersections. # Horizontal part of grid (B-C)
                NewImageBuffer.DrawLine(
                    (TempStarX, TempStarY),
                    (TempStarX3, TempStarY3),
                    color=v_color,
                    thickness=v_thick,
                )  # DIMGREY Link to neighbouring grid intersections. # Vertical part of grid (A-B)
                if (
                    iAlt % 5 == iAz % 5 == 0
                ):  # Show co-ordinates at major grid crossing points.
                    text = str(iAlt) + "," + str(iAz)
                    NewImageBuffer.AddText(
                        text, TempStarX, TempStarY - 10, color=(127, 127, 127)
                    )
                # Label compass points. Consider any vertical (azimuth) lines which cross the bottom of the screen. Mark those which represent compass points.
                if (
                    TempStarY > height and TempStarY3 <= height
                ):  # Place the label on the line crosses the bottom of the image.
                    label = compasslabels.get(
                        iAz, ""
                    )  # Does this azimuth line lie on a compass point?
                    if label != "":  # If it's a recognised compass point, add a label.
                        y = int(height - 200)
                        x = int(
                            interpolate(
                                inp1=TempStarY,
                                res1=TempStarX,
                                inp2=TempStarY3,
                                res2=TempStarX3,
                                inp3=y,
                            )
                        )  # Where does line cross bottom of the screen?
                        NewImageBuffer.AddText(
                            label,
                            x,
                            y,
                            color=pilomarimage.BGR("Black"),
                            bgcolor=pilomarimage.BGR("Green"),
                            size=2,
                            thickness=2,
                            border=10,
                            vjust="c",
                            hjust="c",
                        )

    if True:  # Mark Right Ascension direction on the image.
        cam_log.log("markup_preview: Show ra/dec grid.", terminal=False)
        # Given target RA/DEC values - establish points either side to show the plane of equal Right Ascension values.
        NewImageBuffer.SetPenColor(pilomarimage.BGR("LightBlue"))
        ra_unit = (
            camera_in_use.lens.fov_vertical / 6
        )  # Scale the size of the RA markers, keep centre clear but don't go off edge of image.
        RA_L1 = CentreRa - (2 * ra_unit)  # 2 degrees behind the target.
        RA_L2 = CentreRa - ra_unit  # 1 degrees behind the target.
        RA_L3 = CentreRa + ra_unit  # 1 degrees ahead the target.
        RA_L4 = CentreRa + (2 * ra_unit)  # 2 degrees ahead the target.
        AltL1, AzL1 = session.target.ra_dec_to_alt_az(
            RA_L1, CentreDec, asdegrees=True
        )  # Convert these location to Alt/Az positions.
        AltL2, AzL2 = session.target.ra_dec_to_alt_az(RA_L2, CentreDec, asdegrees=True)
        AltL3, AzL3 = session.target.ra_dec_to_alt_az(RA_L3, CentreDec, asdegrees=True)
        AltL4, AzL4 = session.target.ra_dec_to_alt_az(RA_L4, CentreDec, asdegrees=True)
        PlotAlt1, PlotAz1 = relative_alt_az(
            AltL1, AzL1, CentreAlt, CentreAz
        )  # Convert the alt/az positions to be relative to the center of the image.
        PlotAlt2, PlotAz2 = relative_alt_az(AltL2, AzL2, CentreAlt, CentreAz)
        PlotAlt3, PlotAz3 = relative_alt_az(AltL3, AzL3, CentreAlt, CentreAz)
        PlotAlt4, PlotAz4 = relative_alt_az(AltL4, AzL4, CentreAlt, CentreAz)
        XL1, YL1 = plot_relative_alt_az(
            PlotAlt1, PlotAz1, height, width
        )  # Convert the relative positions into pixel locations.
        XL2, YL2 = plot_relative_alt_az(PlotAlt2, PlotAz2, height, width)
        XL3, YL3 = plot_relative_alt_az(PlotAlt3, PlotAz3, height, width)
        XL4, YL4 = plot_relative_alt_az(PlotAlt4, PlotAz4, height, width)
        NewImageBuffer.DrawEdgeLine(
            (XL2, YL2), (XL1, YL1), edgecolor=pilomarimage.BGR("Black"), arrowpixels=20
        )  # The -ve line ends with an arrow to show direction.
        NewImageBuffer.DrawEdgeLine(
            (XL3, YL3), (XL4, YL4), edgecolor=pilomarimage.BGR("Black"), arrowpixels=20
        )  # The +ve line ends with an arrow to show direction.
        if XL4 > XL3:  # Add +ve and -ve labels at the ends of the lines.
            NewImageBuffer.AddEdgeText(
                "RA+",
                XL4 + 10,
                YL4,
                thickness=2,
                edgecolor=pilomarimage.BGR("Black"),
                vjust="c",
            )
            NewImageBuffer.AddEdgeText(
                "RA-",
                XL1 - 10,
                YL1,
                thickness=2,
                edgecolor=pilomarimage.BGR("Black"),
                vjust="c",
                hjust="r",
            )
        else:
            NewImageBuffer.AddEdgeText(
                "RA+",
                XL4 - 10,
                YL4,
                thickness=2,
                edgecolor=pilomarimage.BGR("Black"),
                vjust="c",
                hjust="r",
            )
            NewImageBuffer.AddEdgeText(
                "RA-",
                XL1 + 10,
                YL1,
                thickness=2,
                edgecolor=pilomarimage.BGR("Black"),
                vjust="c",
            )
        DEC_L1 = CentreDec - (2 * ra_unit)  # 2 degrees below the target.
        DEC_L2 = CentreDec - ra_unit  # 1 degrees below the target.
        DEC_L3 = CentreDec + ra_unit  # 1 degrees above the target.
        DEC_L4 = CentreDec + (2 * ra_unit)  # 2 degrees above the target.
        AltL1, AzL1 = session.target.ra_dec_to_alt_az(
            CentreRa, DEC_L1, asdegrees=True
        )  # Convert these location to Alt/Az positions.
        AltL2, AzL2 = session.target.ra_dec_to_alt_az(CentreRa, DEC_L2, asdegrees=True)
        AltL3, AzL3 = session.target.ra_dec_to_alt_az(CentreRa, DEC_L3, asdegrees=True)
        AltL4, AzL4 = session.target.ra_dec_to_alt_az(CentreRa, DEC_L4, asdegrees=True)
        PlotAlt1, PlotAz1 = relative_alt_az(
            AltL1, AzL1, CentreAlt, CentreAz
        )  # Convert the alt/az positions to be relative to the center of the image.
        PlotAlt2, PlotAz2 = relative_alt_az(AltL2, AzL2, CentreAlt, CentreAz)
        PlotAlt3, PlotAz3 = relative_alt_az(AltL3, AzL3, CentreAlt, CentreAz)
        PlotAlt4, PlotAz4 = relative_alt_az(AltL4, AzL4, CentreAlt, CentreAz)
        XL1, YL1 = plot_relative_alt_az(
            PlotAlt1, PlotAz1, height, width
        )  # Convert the relative positions into pixel locations.
        XL2, YL2 = plot_relative_alt_az(PlotAlt2, PlotAz2, height, width)
        XL3, YL3 = plot_relative_alt_az(PlotAlt3, PlotAz3, height, width)
        XL4, YL4 = plot_relative_alt_az(PlotAlt4, PlotAz4, height, width)
        NewImageBuffer.DrawEdgeLine(
            (XL2, YL2), (XL1, YL1), edgecolor=pilomarimage.BGR("Black"), arrowpixels=20
        )  # The -ve line ends with an arrow to show direction.
        NewImageBuffer.DrawEdgeLine(
            (XL3, YL3), (XL4, YL4), edgecolor=pilomarimage.BGR("Black"), arrowpixels=20
        )  # The +ve line ends with an arrow to show direction.
        if XL4 > XL3:  # Add +ve and -ve labels at the ends of the lines.
            NewImageBuffer.AddEdgeText(
                "Dec+",
                XL4 + 10,
                YL4,
                thickness=2,
                edgecolor=pilomarimage.BGR("Black"),
                vjust="c",
            )
            NewImageBuffer.AddEdgeText(
                "Dec-",
                XL1 - 10,
                YL1,
                thickness=2,
                edgecolor=pilomarimage.BGR("Black"),
                vjust="c",
                hjust="r",
            )
        else:
            NewImageBuffer.AddEdgeText(
                "Dec+",
                XL4 - 10,
                YL4,
                thickness=2,
                edgecolor=pilomarimage.BGR("Black"),
                vjust="c",
                hjust="r",
            )
            NewImageBuffer.AddEdgeText(
                "Dec-",
                XL1 + 10,
                YL1,
                thickness=2,
                edgecolor=pilomarimage.BGR("Black"),
                vjust="c",
            )

    if True:  # Draw arcs to show field rotation over differing timescales.
        # To do this, choose another point in the sky slightly offset from the target.
        # Then estimate how this point rotates around the target as the sky/telescope moves.
        cam_log.log("markup_preview: FieldRotation.", terminal=False)
        xpos = int(width / 2)
        ypos = int(height / 2)
        gap = 60
        NewImageBuffer.SetPenColor(pilomarimage.BGR("HotPink"))
        for i, span in enumerate(
            [3600, 1800, camera_in_use.exposure_seconds]
        ):  # List of exposure times, including the selected exposure time.
            rotation = session.target.rotation_arc(
                span=span
            )  # Calculate field rotation angle over the chosen timespan.
            cam_log.log(
                "markup_preview: Calculated rotation",
                span,
                rotation,
                DEGREE_SYMBOL,
                terminal=False,
            )
            if rotation > 0:
                textpos = xpos - 10  # To left of vertical axis.
                hjust = "r"  # Justify right.
            else:
                hjust = "l"  # Justify left.
                textpos = xpos + 10  # To right of vertical axis.
            cam_log.log(
                "markup_preview: Calculated rotation",
                span,
                rotation,
                DEGREE_SYMBOL,
                "label justification",
                hjust,
                terminal=False,
            )
            r = (i + 10) * gap  # How far down the 'y' axis do we draw this arc?
            # Put label left or right of the arc depending upon which way it is moving.
            if i == 0:  # Print header above first instance.
                NewImageBuffer.AddEdgeText(
                    "Field rotation",
                    textpos,
                    ypos + (9 * gap),
                    color=pilomarimage.BGR("HotPink"),
                    edgecolor=pilomarimage.BGR("Black"),
                    hjust=hjust,
                    bgcolor=pilomarimage.BGR("Black"),
                )  # Explain and demonstrate the field rotation that the telescope is currently experiencing.
            NewImageBuffer.AddEdgeText(
                human_readable_seconds(span) + " is " + str(round(rotation, 2)) + "deg",
                textpos,
                ypos + r,
                color=pilomarimage.BGR("HotPink"),
                edgecolor=pilomarimage.BGR("Black"),
                hjust=hjust,
                vjust="c",
                bgcolor=pilomarimage.BGR("Black"),
            )  # Show rotation value.
            if abs(rotation) > 180:  # Too big to be useful
                NewImageBuffer.AddEdgeText(
                    deg_3dp(rotation),
                    textpos,
                    ypos + r,
                    color=pilomarimage.BGR("HotPink"),
                    edgecolor=pilomarimage.BGR("Black"),
                    hjust=hjust,
                    bgcolor=pilomarimage.BGR("Black"),
                )  # Explain and demonstrate the field rotation that the telescope is currently experiencing.
            elif abs(rotation) > 0.1:  # Big enough for an arc to appear.
                NewImageBuffer.DrawEdgeEllipse(
                    xpos,
                    ypos,
                    r,
                    r,
                    90,
                    0,
                    rotation * -1,
                    thickness=3,
                    edgecolor=pilomarimage.BGR("Black"),
                )  # Draw arc representing the rotation.
            else:  # Too short for an arc to appear. Draw a dot instead.
                NewImageBuffer.DrawEdgeCircle(
                    xpos, ypos + r, 1, thickness=2, edgecolor=pilomarimage.BGR("Black")
                )  # Draw dot representing insignificant rotation.

    if True:  # Parameters.MarkupShowCrosshairs: # Target cross hairs
        cam_log.log("markup_preview: ShowCrosshairs", terminal=False)
        # Draw cross hairs. Gap in the centre so that target is still visible.
        NewImageBuffer.SetPenColor(pilomarimage.BGR("Yellow"))
        NewImageBuffer.DrawLine(
            (int(width / 2), 0), (int(width / 2), int(height / 2 - 20))
        )
        NewImageBuffer.DrawLine(
            (int(width / 2), height), (int(width / 2), int(height / 2 + 20))
        )
        NewImageBuffer.DrawLine(
            (0, int(height / 2)), (int(width / 2 - 20), int(height / 2))
        )
        NewImageBuffer.DrawLine(
            (int(width / 2) + 20, int(height / 2)), (width, int(height / 2))
        )

    if (
        True
    ):  # Parameters.MarkupShowDegreeScale: # Mark DEGREE scale. This is degrees movement of the camera, NOT degrees in the sky!
        cam_log.log("markup_preview: ShowDegreeScale", terminal=False)
        NewImageBuffer.SetPenColor(pilomarimage.BGR("Yellow"))
        # Calibration - Azimuth
        for i in range(-10, 11):
            xpos = int(width / 2) + (
                i * camera_in_use.pixels_per_fov_degree_width
            )  # 1 degree markers
            ypos = int(height / 2)
            text = str(i) + "deg"  # DEGREE_SYMBOL
            if i > 0:
                text = "+" + text
            NewImageBuffer.DrawLine((xpos, ypos - 100), (xpos, ypos))
            NewImageBuffer.AddText(text, xpos, ypos - 100, hjust="c", vjust="t")
        # Calibration - Altitude
        for i in range(-10, 11):
            xpos = int(width / 2)
            ypos = int(height / 2) + (
                i * camera_in_use.pixels_per_fov_degree_height
            )  # 1 degree markers
            NewImageBuffer.DrawLine((xpos - 100, ypos), (xpos, ypos))
            text = (
                str(i * -1) + "deg"
            )  # DEGREE_SYMBOL - Invert scale because image Y positions are inverted.
            if i < 0:
                text = "+" + text
            NewImageBuffer.AddText(text, xpos - 100, ypos, vjust="c", hjust="r")

    if True:  # Parameters.MarkupShowFullStepScale: # Mark FULL STEP scale.
        cam_log.log(
            "markup_preview: azpx/step",
            az_pixels_per_fullstep,
            "altpx/step",
            alt_pixels_per_fullstep,
            "HFOV",
            lens_in_use.fov_horizontal,
            "VFOV",
            lens_in_use.fov_vertical,
            "Wpx",
            width,
            "Hpx",
            height,
            terminal=False,
        )
        # Calibration - Azimuth
        NewImageBuffer.SetPenColor(pilomarimage.BGR("Cyan"))
        c = 0  # Counter used to stagger the text to reduce overlapping.
        MajorTickSteps = dynamic_scale(
            targetpix=200, pixelsperstep=az_pixels_per_fullstep
        )
        for i in range(
            int(-10 * MajorTickSteps), int(10 * MajorTickSteps + 1), MajorTickSteps
        ):  # Major tick marks only.
            c = 1 - c
            xpos = int((width / 2) + (i * az_pixels_per_fullstep))
            ypos = int(height / 2)
            NewImageBuffer.DrawLine((xpos, ypos), (xpos, ypos + 100), thickness=3)
            text = str(i) + "Steps"
            if i > 0:
                text = "+" + text
            NewImageBuffer.AddText(
                text, xpos, ypos + 110 + (c * 25), size=1.0, hjust="c", vjust="b"
            )  # Offset alternate markings to keep legible.
        # Calibration - Altitude
        MajorTickSteps = dynamic_scale(
            targetpix=200, pixelsperstep=alt_pixels_per_fullstep
        )
        for i in range(
            int(-10 * MajorTickSteps), int(10 * MajorTickSteps + 1), MajorTickSteps
        ):  # Major tick marks only.
            xpos = int(width / 2)
            ypos = int((height / 2) + (i * alt_pixels_per_fullstep))
            NewImageBuffer.DrawLine((xpos, ypos), (xpos + 100, ypos), thickness=3)
            text = str(i * -1) + "Steps"
            if i < 0:
                text = "+" + text
            NewImageBuffer.AddText(text, xpos + 110, ypos, vjust="c")
        # Mark precision circle on centre. Once you're inside this circle, there's little point in finetuning further on this scale.
        if az_pixels_per_fullstep > 5 or alt_pixels_per_fullstep > 5:
            # Only bother showing the precision circle IF it is large enough to be useful.
            # If the gearing is very fine, then there's no real purpose to showing the precision circle, it will be too small to see.
            xpos = int(width / 2)
            ypos = int(height / 2)
            NewImageBuffer.DrawCircle(
                xpos,
                ypos,
                int(az_pixels_per_fullstep),
                color=pilomarimage.BGR("Gold"),
                thickness=3,
            )
            NewImageBuffer.DrawCircle(
                xpos, ypos, int(az_pixels_per_fullstep), color=pilomarimage.BGR("Black")
            )

    if True:  # Draw angular scale for reference.
        ScaleList = [
            ["1deg", 1.0, 0.0, 0.0],
            ["30arcmin", 0.0, 30.0, 0.0],
            ["10arcmin", 0.0, 10.0, 0.0],
            ["1arcmin", 0.0, 1.0, 0.0],
            ["30arcsec", 0.0, 0.0, 30.0],
            ["10arcsec", 0.0, 0.0, 10.0],
        ]
        NewImageBuffer.SetPenColor(pilomarimage.BGR("White"))
        x = 200
        y = int(height / 2) + 200
        NewImageBuffer.AddEdgeText(
            "Angular scale", x, y, size=0.5, edgecolor=pilomarimage.BGR("Black")
        )
        for i, scale in enumerate(ScaleList):
            label = scale[0]
            d = (
                float(scale[1]) + (scale[2] / 60) + (scale[3] / (60**2))
            )  # Convert DMS into float degrees.
            p = int(d * camera_in_use.pixels_per_fov_degree_width)
            if p > width - 300:  # Line is too long to be useful.
                continue
            y += 20
            NewImageBuffer.AddEdgeText(
                label,
                x,
                y,
                size=0.5,
                hjust="r",
                vjust="c",
                edgecolor=pilomarimage.BGR("Black"),
            )
            NewImageBuffer.DrawLine((x + 10, y), (x + 10 + p, y), thickness=3)
            NewImageBuffer.DrawLine((x + 10, y - 10), (x + 10, y + 10), thickness=1)
            NewImageBuffer.DrawLine(
                (x + 10 + p, y - 10), (x + 10 + p, y + 10), thickness=1
            )

    if True:  # Parameters.MarkupShowMessier: # Mark neighbouring Messier objects ....
        NewImageBuffer.SetPenColor(pilomarimage.BGR("Green"))
        # Find that alt/az locations of all the objects.
        for TempStarName, TempStarParms in Messier_dictionary.items():  # Python3
            TempRAH = TempStarParms["ra"][0]  # Right Ascension HOURS
            TempRAM = TempStarParms["ra"][1]  # Right Ascension MINUTES
            TempRAS = TempStarParms["ra"][2]  # Right Ascension SECONDS
            TempStarRA = TempStarParms["radeg"]
            if TempStarRA < MinRADeg or TempStarRA > MaxRADeg:  # Outside drawing area.
                continue  # Skip to next object
            TempDED = TempStarParms["dec"][0]  # Declination DEGREES
            TempDEM = TempStarParms["dec"][1]  # Declination MINUTES
            TempDES = TempStarParms["dec"][2]  # Declination SECONDS
            TempStarDec = TempStarParms["decdeg"]
            if (
                TempStarDec < MinDecDeg or TempStarDec > MaxDecDeg
            ):  # Outside drawing area.
                continue  # Skip to next object
            TempStar = Star(
                ra_hours=(TempRAH, TempRAM, TempRAS),
                dec_degrees=(TempDED, TempDEM, TempDES),
            )  # Create star object from RADEC co-ordinates.
            TempStarType = TempStarParms["type"]
            TempStarWidth = int(
                (TempStarParms["widthdeg"] * camera_in_use.pixels_per_fov_degree_width)
                / 2
            )  # Width given in arcminutes.
            TempStarHeight = int(
                (
                    TempStarParms["heightdeg"]
                    * camera_in_use.pixels_per_fov_degree_height
                )
                / 2
            )
            temptarget = AstroTarget(
                TempStar,
                name=TempStarName,
                objecttype=TempStarType,
                constellation="",
                description="",
                magnitude=TempStarParms["magnitude"],
            )
            TempStarAz, TempStarAlt = temptarget.az_alt_degrees(time=t)
            if TempStarAz < 0:  # Below horizon, don't mark it up.
                continue  # Skip to next object.
            PlotStarAlt, PlotStarAz = relative_alt_az(
                TempStarAlt, TempStarAz, CentreAlt, CentreAz
            )
            TempStarX, TempStarY = plot_relative_alt_az(
                PlotStarAlt, PlotStarAz, height, width
            )
            TempTextX = (
                TempStarX + TempStarWidth + 5
            )  # Put Messier labels on the RIGHT of the object so they don't clash with NGC labels for the same thing.
            NewImageBuffer.DrawEllipse(
                TempStarX, TempStarY, int(TempStarWidth), int(TempStarHeight), 0, 0, 360
            )
            if params.markup_show_labels:
                text = az_alt_text(TempStarAz, TempStarAlt, "deg")
                NewImageBuffer.AddText(
                    text, TempTextX, TempStarY + lineheight, size=0.5
                )
                text = (
                    "RA:"
                    + TempStarParms["ralabel"]
                    + " Dec:"
                    + TempStarParms["declabel"]
                )
                NewImageBuffer.AddText(
                    text, TempTextX, NewImageBuffer.NextTextY, size=0.5
                )
                if TempStarName is not None:
                    NewImageBuffer.AddText(
                        TempStarName.upper(), TempTextX, TempStarY - 20, size=1
                    )

    if True:  # Mark neighbouring NGC items ...
        # Find the alt/az locations of all the objects.
        # NGC catalog is large, eliminate as much as possible first.
        cam_log.log(
            "markup_preview: NGCItems: CentreRa",
            CentreRa,
            DEGREE_SYMBOL,
            "CentreDec",
            CentreDec,
            DEGREE_SYMBOL,
            terminal=False,
        )
        cam_log.log(
            "markup_preview: NGCItems: Start:", len(NGC_DF), "records.", terminal=False
        )
        boolseries = NGC_DF["radeg"].between(
            MinRADeg, MaxRADeg, inclusive="both"
        )  # Create filter for items within RA range.
        tempdf = NGC_DF[boolseries]  # Apply filter.
        cam_log.log(
            "markup_preview: NGCItems: RA Filtered:",
            MinRADeg,
            DEGREE_SYMBOL,
            MaxRADeg,
            DEGREE_SYMBOL,
            ". Leaves",
            len(tempdf),
            "records.",
            terminal=False,
        )
        boolseries = tempdf["decdeg"].between(
            MinDecDeg, MaxDecDeg, inclusive="both"
        )  # Create filter for items with Dec range.
        tempdf = tempdf[boolseries]  # Apply filter.
        cam_log.log(
            "markup_preview: NGCItems: Dec Filtered:",
            MinDecDeg,
            DEGREE_SYMBOL,
            MaxDecDeg,
            DEGREE_SYMBOL,
            ". Leaves",
            len(tempdf),
            "records.",
            terminal=False,
        )
        NewImageBuffer.SetPenColor(pilomarimage.BGR("LightBlue"))
        for i in range(len(tempdf)):
            TempStarParms = tempdf.iloc[
                i
            ]  # Select each row in turn from the Pandas dataframe.
            TempStarName = TempStarParms["name"]
            try:  # Earlier versions of the data file may not have this column.
                TempStarName2 = TempStarParms["knownas"]
            except:
                TempStarName2 = ""  # Field not available in this data set.
            try:  # Earlier versions of the data file may not have this column.
                NGCType = TempStarParms["typelabel"]
            except:
                NGCType = TempStarParms["type"]
            TempStar = Star(
                ra_hours=(
                    TempStarParms["rah"],
                    TempStarParms["ram"],
                    TempStarParms["ras"],
                ),
                dec_degrees=(
                    TempStarParms["ded"],
                    TempStarParms["dem"],
                    TempStarParms["des"],
                ),
            )  # Create star object from RADEC co-ordinates.
            TempStarWidth = int(
                (TempStarParms["widthdeg"] * camera_in_use.pixels_per_fov_degree_width)
                / 2
            )  # Convert from arcseconds to degrees & radius.
            TempStarHeight = int(
                (
                    TempStarParms["heightdeg"]
                    * camera_in_use.pixels_per_fov_degree_height
                )
                / 2
            )
            if TempStarWidth < 1 and TempStarHeight < 1:
                continue  # Too small to display.
            temptarget = AstroTarget(
                TempStar,
                name=TempStarName,
                objecttype="ngc",
                constellation="",
                description="",
                magnitude=TempStarParms["magnitude"],
            )
            TempStarAz, TempStarAlt = temptarget.az_alt_degrees(time=t)
            if TempStarAz < 0:  # Below horizon, don't mark it up.
                continue  # Skip to next object.
            PlotStarAlt, PlotStarAz = relative_alt_az(
                TempStarAlt, TempStarAz, CentreAlt, CentreAz
            )
            TempStarX, TempStarY = plot_relative_alt_az(
                PlotStarAlt, PlotStarAz, height, width
            )
            # TempTextX = TempStarX - TempStarWidth - 5 # Put NGC labels on the LEFT of the object so they don't clash with any matching Messier label for the same thing.
            NewImageBuffer.DrawEllipse(
                TempStarX,
                TempStarY,
                int(TempStarWidth),
                int(TempStarHeight),
                angle=0,
                startAngle=0,
                endAngle=360,
            )
            cam_log.log(
                "markup_preview: NGCItems: Processing entry",
                i,
                TempStarName,
                TempStarName2,
                ";",
                TempStarWidth,
                "*",
                TempStarHeight,
                ";",
                TempStarX,
                ",",
                TempStarY,
                terminal=False,
            )
            if params.markup_show_labels:
                TempTextX = (
                    TempStarX - TempStarWidth - 5
                )  # Put NGC labels on the LEFT of the object so they don't clash with any matching Messier label for the same thing.
                text = az_alt_text(TempStarAz, TempStarAlt, "deg")
                NewImageBuffer.AddText(
                    text, TempTextX, TempStarY + lineheight, size=0.5, hjust="r"
                )
                text = (
                    "RA:"
                    + TempStarParms["ralabel"]
                    + " Dec:"
                    + TempStarParms["declabel"]
                )
                NewImageBuffer.AddText(
                    text, TempTextX, NewImageBuffer.NextTextY, size=0.5, hjust="r"
                )
                if NGCType is not None:  # Describe the object type.
                    NewImageBuffer.AddText(
                        NGCType.title(),
                        TempTextX,
                        NewImageBuffer.NextTextY,
                        size=0.5,
                        hjust="r",
                    )
                if TempStarName is not None:  # Name - ie NGCxxx
                    NewImageBuffer.AddText(
                        TempStarName.upper(),
                        TempTextX,
                        TempStarY - 30,
                        size=1,
                        hjust="r",
                    )
                if TempStarName2 is not None:  # Known as - ie Whirlpool Galaxy
                    NewImageBuffer.AddText(
                        TempStarName2.title(),
                        TempTextX,
                        NewImageBuffer.NextTextY,
                        size=1,
                        hjust="r",
                    )
        cam_log.log(
            "markup_preview: NGCItems: Plot NGC objects end. (",
            len(tempdf),
            "/",
            len(NGC_DF),
            "objects selected)",
            terminal=False,
        )

    hsat = HomeSite.at(t)
    if True:  # Parameters.MarkupShowStars: # Mark neighbouring stars.
        cam_log.log("markup_preview: ShowStars", terminal=False)
        NewImageBuffer.AvoidTextCollisions = (
            params.markup_avoid_collisions
        )  # Do we allow star labels to overlap?
        # Mark neighbouring stars on the picture too. This will help with alignment.
        # Select a subset of the Hipparcos catalog which is within 10Deg of the target (=centre of image)
        cam_log.log("markup_preview: SelectStars start", terminal=False)
        NeighbouringStars = local_stars.get(CentreRa, CentreDec)
        NeighbouringStarCount = len(NeighbouringStars)
        # inbounds_idx = LocalStars.ColumnIndex('inbounds') # Which dataframe column stores the 'inbounds' counter?
        cam_log.log(
            "markup_preview: NeighbouringStars contains",
            NeighbouringStarCount,
            "entries.",
            terminal=False,
        )
        NewImageBuffer.SetPenColor(pilomarimage.BGR("PaleGreen"))
        # Now convert this list of ra/dec locations into alt/az positions for plotting on the preview image.
        PlottedStarCount = (
            0  # How many stars have been plotted? We don't want to swamp the display.
        )
        for i in range(NeighbouringStarCount):
            if i % 400 == 0:
                cam_log.log(
                    "markup_preview: ShowStars. Processing star", i, terminal=False
                )
            TempStarRec = NeighbouringStars.iloc[
                i
            ]  # Select each row in turn from the Pandas dataframe, probably makes a COPY, not a pointer to the original row.
            TempStar = Star.from_dataframe(
                TempStarRec
            )  # Convert the Hipparcos entry into a Skyfield STAR object. *Q* Can we use TempStarRec here?
            TempStarAlt, TempStarAz, _ = (
                hsat.observe(TempStar).apparent().altaz()
            )  # Get the azimuth and altitude position of the star in the sky.
            # Calculate the location in the preview image.
            PlotStarAlt, PlotStarAz = relative_alt_az(
                TempStarAlt.degrees, TempStarAz.degrees, CentreAlt, CentreAz
            )
            TempStarX, TempStarY = plot_relative_alt_az(
                PlotStarAlt, PlotStarAz, height, width
            )
            if NewImageBuffer.OutOfBounds(TempStarX, TempStarY):
                continue  # This star is off the edge of the image, skip it.
            # We're going to plot this one.
            PlottedStarCount += 1
            TempStarWidth = int(TempStarRec["markupradius"])
            NewImageBuffer.DrawCircle(
                TempStarX, TempStarY, TempStarWidth, thickness=3
            )  # cyan # circle where the star is.
            labelx = TempStarX + TempStarWidth + 5  # X location of labels.
            if True:  # Parameters.MarkupShowNames:
                TempStarName = TempStarRec["starname"]
                try:
                    TempStarConstellation = TempStarRec[
                        "constellation"
                    ].title()  # Capitalise 1st letter of each word.
                except:
                    TempStarConstellation = ""
                if TempStarConstellation != "" and TempStarConstellation is not None:
                    TempStarName += " (" + TempStarConstellation + ")"
                NewImageBuffer.AddText(
                    TempStarRec["label"], labelx, TempStarY - 20
                )  # Hipparcos ID
                if len(TempStarName) > 0:  # Add star name.
                    NewImageBuffer.AddText(
                        TempStarName.title(),
                        labelx,
                        NewImageBuffer.NextTextY,
                        thickness=2,
                        size=1,
                    )
            if params.markup_show_labels:  # Show position labels. Alt/Az and Ra/Dec
                text = az_alt_text(TempStarAz.degrees, TempStarAlt.degrees, "deg")
                NewImageBuffer.AddText(text, labelx, NewImageBuffer.NextTextY, size=0.5)
                text = (
                    "RA:" + TempStarRec["ralabel"] + " Dec:" + TempStarRec["declabel"]
                )
                NewImageBuffer.AddText(text, labelx, NewImageBuffer.NextTextY, size=0.5)
            if (
                PlottedStarCount >= params.markup_star_label_limit
            ):  # We're plotted enough, don't swamp the image.
                cam_log.log(
                    "markup_preview: ShowStars: Plotted maximum",
                    PlottedStarCount,
                    "star labels.",
                    terminal=False,
                )
                break
        NewImageBuffer.AvoidTextCollisions = (
            False  # Turn off the label collision protection.
        )

    if (
        True
    ):  # Parameters.MarkupConstellations: # Mark constellation patterns... # Workaround for post skyfield 1.39. Fault not fully understood yet.
        cam_log.log(
            "markup_preview: ShowConstellations POST OCT.2023 version. Post Skyfield 1.39 etc.",
            terminal=False,
        )
        rad = 10  # 10 pixel gap between line and star.
        cclist = (
            {}
        )  # We place the name of the constellation in the middle of the visible stars. This list builds up where those locations are.
        NewImageBuffer.SetPenColor(pilomarimage.BGR("Red"))
        ConstellationsDf = ConstellationStars.get(CentreRa, CentreDec)
        cam_log.log(
            "markup_preview: ShowConstellations: Columns available:",
            list(ConstellationsDf.columns),
            terminal=False,
        )
        linkcount = 0
        successcount = 0
        for entryfrom, entryto, entryname in ConstellationLinks:
            linkcount += 1
            if (
                int(entryfrom) in ConstellationsDf.index
                and int(entryto) in ConstellationsDf.index
            ):
                cam_log.log(
                    "markup_preview: ShowConstellations: from",
                    int(entryfrom),
                    "to",
                    int(entryto),
                    terminal=False,
                )
                FromRec = ConstellationsDf.loc[
                    int(entryfrom)
                ]  # See how many records are returned. Expect 1: 15.10.2023
                try:
                    rah, ram, ras = angle_to_hms(FromRec["ra_degrees"])
                except Exception as e:
                    cam_log.log(
                        "AngleToHMS(",
                        FromRec["ra_degrees"],
                        ")=",
                        rah,
                        ram,
                        ras,
                        "failed. Skipping FromStar",
                        entryfrom,
                        terminal=False,
                    )
                    cam_log.log(
                        "AngleToHMS(",
                        FromRec["ra_degrees"],
                        ") Error:",
                        e,
                        terminal=False,
                    )
                    continue  # Don't process this star any further.
                try:
                    ded, dem, des = angle_to_dms(FromRec["dec_degrees"])
                except Exception as e:
                    cam_log.log(
                        "AngleToHMS(",
                        FromRec["dec_degrees"],
                        ")=",
                        ded,
                        dem,
                        des,
                        "failed. Skipping FromStar",
                        entryfrom,
                        terminal=False,
                    )
                    cam_log.log(
                        "AngleToHMS(",
                        FromRec["dec_degrees"],
                        ") Error:",
                        e,
                        terminal=False,
                    )
                    continue  # Don't process this star any further.
                try:
                    FromStar = Star(
                        ra_hours=(rah, ram, ras), dec_degrees=(ded, dem, des)
                    )
                except Exception as e:
                    cam_log.log(
                        "Skyfield Star construction of FromRec hip",
                        entryfrom,
                        "failed. Skipping.",
                        terminal=False,
                    )
                    cam_log.log(
                        "Star construction of", entryfrom, "Error:", e, terminal=False
                    )
                    continue  # Don't process this star any further.
                ToRec = ConstellationsDf.loc[
                    int(entryto)
                ]  # See how many records are returned. Expect 1: 15.10.2023
                try:
                    rah, ram, ras = angle_to_hms(ToRec["ra_degrees"])
                except Exception as e:
                    cam_log.log(
                        "AngleToHMS(",
                        ToRec["ra_degrees"],
                        ")=",
                        rah,
                        ram,
                        ras,
                        "failed. Skipping ToStar",
                        entryto,
                        terminal=False,
                    )
                    cam_log.log(
                        "AngleToHMS(",
                        ToRec["ra_degrees"],
                        ") Error:",
                        e,
                        terminal=False,
                    )
                    continue  # Don't process this star any further.
                try:
                    ded, dem, des = angle_to_dms(ToRec["dec_degrees"])
                except Exception as e:
                    cam_log.log(
                        "AngleToHMS(",
                        ToRec["dec_degrees"],
                        ")=",
                        ded,
                        dem,
                        des,
                        "failed. Skipping ToStar",
                        entryto,
                        terminal=False,
                    )
                    cam_log.log(
                        "AngleToHMS(",
                        ToRec["dec_degrees"],
                        ") Error:",
                        e,
                        terminal=False,
                    )
                    continue  # Don't process this star any further.
                try:
                    ToStar = Star(ra_hours=(rah, ram, ras), dec_degrees=(ded, dem, des))
                except Exception as e:
                    cam_log.log(
                        "Skyfield Star construction of ToRec hip",
                        entryto,
                        "failed. Skipping.",
                        terminal=False,
                    )
                    cam_log.log(
                        "Star construction of", entryto, "Error:", e, terminal=False
                    )
                    continue  # Don't process this star any further.
                successcount += 1
                FromAlt, FromAz, _ = (
                    hsat.observe(FromStar).apparent().altaz()
                )  # Get the azimuth and altitude position of the star in the sky.
                PlotFromAlt, PlotFromAz = relative_alt_az(
                    FromAlt.degrees, FromAz.degrees, CentreAlt, CentreAz
                )
                fromx, fromy = plot_relative_alt_az(
                    PlotFromAlt, PlotFromAz, height, width
                )
                ToAlt, ToAz, _ = (
                    hsat.observe(ToStar).apparent().altaz()
                )  # Get the azimuth and altitude position of the star in the sky.
                PlotToAlt, PlotToAz = relative_alt_az(
                    ToAlt.degrees, ToAz.degrees, CentreAlt, CentreAz
                )
                tox, toy = plot_relative_alt_az(PlotToAlt, PlotToAz, height, width)
                fromx, fromy, tox, toy = NewImageBuffer.TrimLine(
                    fromx, fromy, tox, toy, trimpixels=rad
                )  # Shorten the ends of the constellation line by a few pixels.
                deltax = tox - fromx  # Line size
                deltay = toy - fromy
                # Only draw the line between stars if they are sufficiently separated on the image. (DIV-BY-ZERO error if they are the same pixel).
                if abs(deltax) > (rad * 2) or abs(deltay) > (rad * 2):
                    hyp = math.sqrt(deltax**2 + deltay**2)
                    x1 = int(
                        fromx + (deltax * rad / hyp)
                    )  # End points of line 'rad' pixels away from actual stars.
                    x2 = int(tox - (deltax * rad / hyp))
                    y1 = int(fromy + (deltay * rad / hyp))
                    y2 = int(toy - (deltay * rad / hyp))
                    NewImageBuffer.DrawLine((x1, y1), (x2, y2))
                else:
                    cam_log.log(
                        "markup_preview: ShowConstellations: Too close to plot",
                        entryfrom,
                        "(",
                        fromx,
                        ",",
                        fromy,
                        " ) to",
                        entryto,
                        "(",
                        tox,
                        ",",
                        toy,
                        " ).",
                        terminal=False,
                    )
                # Add star locations to cclist to help place the constellation name sensibly.
                if NewImageBuffer.InBounds(fromx, fromy) or NewImageBuffer.InBounds(
                    tox, toy
                ):
                    ccentry = cclist.get(
                        entryname, {}
                    )  # Get current locations for this constellation name.
                    ccount = ccentry.get(
                        "count", 0
                    )  # Extract number of stars plotted so far for this constellation.
                    cctotx = ccentry.get(
                        "totalx", 0
                    )  # Extract total 'x' positions of all stars plotted for this constellation.
                    cctoty = ccentry.get(
                        "totaly", 0
                    )  # Extract total 'y' positions of all stars plotted for this constellation.
                    cctotx += fromx + tox  # Add this star pair.
                    cctoty += fromy + toy
                    ccount += 2  # We've added 2 stars to the list.
                    ccentry["count"] = ccount  # Update the count and totals.
                    ccentry["totalx"] = cctotx
                    ccentry["totaly"] = cctoty
                    cclist[entryname] = (
                        ccentry  # Store the entry back in the list of constellation names.
                    )
        cam_log.log(
            "markup_preview: Constellation links: Attempted:",
            linkcount,
            "Succeeded:",
            successcount,
            terminal=False,
        )
        # Now place constellation labels.
        for ccname, ccentry in cclist.items():
            x = ccentry["totalx"] / ccentry["count"]  # Average x
            y = ccentry["totaly"] / ccentry["count"]  # Average y
            x = max(x, 0)
            x = min(x, width)
            y = max(y, 0)
            y = min(y, height)
            hjust = "c"
            if x < width / 4:
                hjust = "l"
            elif x > 3 * width / 4:
                hjust = "r"
            if y < 20:
                y = 20
            elif y > height - 20:
                y = height - 20
            NewImageBuffer.AddText(ccname.title(), int(x), int(y), size=3, hjust=hjust)

    if True:  # Parameters.MarkupShowPlanets: # Mark neighbouring planets ....
        cam_log.log("markup_preview: ShowPlanets", terminal=False)
        NewImageBuffer.SetPenColor(pilomarimage.BGR("Gold"))
        # Find the alt/az locations of all the planets.
        for TempStarName in [
            "sun",
            "mercury barycenter",
            "venus barycenter",
            "moon",
            "mars barycenter",
            "jupiter barycenter",
            "saturn barycenter",
            "uranus barycenter",
            "neptune barycenter",
            "pluto barycenter",
        ]:
            TempStarDescription = TempStarName
            TempStar = planets[TempStarName]
            temptarget = AstroTarget(
                TempStar,
                name=TempStarName,
                objecttype="planet",
                description=TempStarDescription,
                magnitude=0.0,
            )
            TempStarAz, TempStarAlt = temptarget.az_alt_degrees(time=t)
            TempStarRA, TempStarDec = temptarget.ra_dec_degrees(time=t)
            PlotStarAlt, PlotStarAz = relative_alt_az(
                TempStarAlt, TempStarAz, CentreAlt, CentreAz
            )
            TempStarX, TempStarY = plot_relative_alt_az(
                PlotStarAlt, PlotStarAz, height, width
            )
            TempStarWidth = 40  # Planets are by default 40 pixel radius circles.
            if TempStarName == "moon":
                TempStarWidth = int(
                    convert_arcseconds_to_pixels((0.5286 / 2) * 3600)
                )  # Moon is approx 0.26 degrees angular radius.
            NewImageBuffer.DrawCircle(
                TempStarX, TempStarY, TempStarWidth, thickness=3
            )  # cyan # circle where the planet is.
            if params.markup_show_labels:
                text = az_alt_text(TempStarAz, TempStarAlt, "deg")
                NewImageBuffer.AddText(
                    text, TempStarX + TempStarWidth + 5, TempStarY + 40
                )
                text = ra_dec_text(TempStarRA, TempStarDec, "deg")
                # text = "RA:" + str(TempStarRA) + " Dec:" + str(TempStarDec)
                NewImageBuffer.AddText(
                    text, TempStarX + TempStarWidth + 5, NewImageBuffer.NextTextY
                )
            if TempStarName is not None:
                NewImageBuffer.AddText(
                    TempStarName.split()[0].title(),
                    TempStarX + TempStarWidth + 5,
                    TempStarY - 20,
                )

    if (
        False
    ):  # Parameters.MarkupShowRegistration: # Reference marks on preview image...
        cam_log.log("markup_preview: ShowRegistration", terminal=False)
        NewImageBuffer.SetPenColor(pilomarimage.BGR("Red"))
        NewImageBuffer.DrawLine((10, 10), (100, 10), thickness=3)  # Red
        NewImageBuffer.DrawLine((10, 10), (10, 100), thickness=3)  # Red
        text = "(10,10)"
        NewImageBuffer.AddText(text, 40, 60, color=pilomarimage.BGR("Red"))  # red

    if True:  # Parameters.MarkupShowDrift: # Mark last measured DRIFT indicator.
        cam_log.log(
            "markup_preview: ShowDrift:",
            drift_pixels_x,
            ",",
            drift_pixels_y,
            terminal=False,
        )
        if drift_pixels_x is not None and drift_pixels_y is not None:
            text = (
                "Drift: " + str(drift_pixels_x) + "," + str(drift_pixels_y) + " pixels"
            )
            NewImageBuffer.DrawEdgeLine(
                (int(width / 2), int(height / 2)),
                (
                    int(width / 2) + int(drift_pixels_x),
                    int(height / 2) + int(drift_pixels_y),
                ),
                color=pilomarimage.BGR("Red"),
                edgecolor=pilomarimage.BGR("Black"),
            )  # Black outline showing last measured drift.
            NewImageBuffer.DrawCircle(
                int(width / 2) + int(drift_pixels_x),
                int(height / 2) + int(drift_pixels_y),
                10,
                color=pilomarimage.BGR("Red"),
            )  # Black outline showing last measured drift.
            NewImageBuffer.AddEdgeText(
                text,
                int(width / 2) + int(drift_pixels_x) + 10,
                int(height / 2) + int(drift_pixels_y) + 10,
                color=pilomarimage.BGR("Red"),
                edgecolor=pilomarimage.BGR("Black"),
                thickness=2,
                edgethickness=2,
            )  # Red line
        else:
            NewImageBuffer.AddEdgeText(
                "NO DRIFT AVAILABLE",
                int(width / 2) + 150,
                int(height / 2) + 150,
                color=pilomarimage.BGR("Red"),
                edgecolor=pilomarimage.BGR("Black"),
                thickness=2,
                edgethickness=2,
            )  # Red line

    if True:  # Parameters.MarkupShowCurrentPosition: # Show current position.
        cam_log.log("markup_preview: CurrentPosition", terminal=False)
        cRa, cDec = (
            session.target.ra_dec_hours()
        )  # Calculations for target from observer's location. Returns HMS and Degree values.
        # Timestamp bottom center.
        xpos = int(width / 2)
        ypos = int(height - 70)
        text = str(camera_in_use.last_image_date_time)
        NewImageBuffer.AddText(
            text,
            xpos,
            ypos,
            size=2.0,
            color=pilomarimage.BGR("White"),
            bgcolor=pilomarimage.BGR("Black"),
            hjust="c",
        )
        # Filename in bottom left corner.
        xpos = int(10)
        ypos = int(height - 10)
        text = "File: " + filename
        NewImageBuffer.AddText(
            text,
            xpos,
            ypos,
            color=pilomarimage.BGR("White"),
            bgcolor=pilomarimage.BGR("Black"),
        )
        # Program ID in bottom right corner.
        xpos = int(width - 10)
        ypos = int(height - 10)
        NewImageBuffer.AddText(
            ProgramTitle + " " + VERSION,
            xpos,
            ypos,
            color=pilomarimage.BGR("White"),
            bgcolor=pilomarimage.BGR("Black"),
            hjust="r",
        )
        # Camera options in top left corner.
        xpos = int(width / 2)
        ypos = int(40)
        text = "Camera options: " + str(camera_in_use.last_light_command)
        NewImageBuffer.AddText(
            text,
            xpos,
            ypos,
            color=pilomarimage.BGR("Yellow"),
            bgcolor=pilomarimage.BGR("Black"),
            hjust="c",
        )
        # Key in top right corner.
        xpos = width - 50
        ypos = 50
        NewImageBuffer.AddText(
            "KEY",
            xpos,
            ypos,
            color=pilomarimage.BGR("White"),
            hjust="r",
            bgcolor=pilomarimage.BGR("Black"),
        )
        NewImageBuffer.AddText(
            "Hipparcos O",
            xpos,
            NewImageBuffer.NextTextY,
            color=pilomarimage.BGR("PaleGreen"),
            hjust="r",
            bgcolor=pilomarimage.BGR("Black"),
        )
        NewImageBuffer.AddText(
            "Messier O",
            xpos,
            NewImageBuffer.NextTextY,
            color=pilomarimage.BGR("Green"),
            hjust="r",
            bgcolor=pilomarimage.BGR("Black"),
        )
        NewImageBuffer.AddText(
            "NGC O",
            xpos,
            NewImageBuffer.NextTextY,
            color=pilomarimage.BGR("LightBlue"),
            hjust="r",
            bgcolor=pilomarimage.BGR("Black"),
        )
        NewImageBuffer.AddText(
            "Planet O",
            xpos,
            NewImageBuffer.NextTextY,
            color=pilomarimage.BGR("Gold"),
            hjust="r",
            bgcolor=pilomarimage.BGR("Black"),
        )
        NewImageBuffer.AddText(
            "Constellation -",
            xpos,
            NewImageBuffer.NextTextY,
            color=pilomarimage.BGR("Red"),
            hjust="r",
            bgcolor=pilomarimage.BGR("Black"),
        )
        # More detail in bottom right corner.
        xpos = int(width - 50)
        ypos = int(height - 100)
        NewImageBuffer.PrevTextY = ypos  # Initialize line pointer for a text block.
        for i in MotorControls:
            text = "Motor: " + i.MotorName + " "
            text += deg_3dp(i.CurrentAngle) + "deg, "  # DEGREE_SYMBOL
            text += (
                "position "
                + str(i.AngleToStep(i.CurrentAngle))
                + " of "
                + str(i.AxisStepsPerRev)
            )
            NewImageBuffer.AddText(
                text,
                xpos,
                NewImageBuffer.PrevTextY,
                color=pilomarimage.BGR("Green"),
                bgcolor=pilomarimage.BGR("Black"),
                hjust="r",
            )
        text = "Marking objects above magnitude " + str(
            round(params.target_min_magnitude, 1)
        )  # Object magnitude filter.
        NewImageBuffer.AddText(
            text,
            xpos,
            NewImageBuffer.PrevTextY,
            color=pilomarimage.BGR("Gold"),
            bgcolor=pilomarimage.BGR("Black"),
            hjust="r",
        )
        if session.target.magnitude is not None:  # Magnitude of the target.
            text = "Target magnitude " + str(round(session.target.magnitude, 1))
        else:
            text = "Target magnitude UNKNOWN"
        NewImageBuffer.AddText(
            text,
            xpos,
            NewImageBuffer.PrevTextY,
            color=pilomarimage.BGR("Gold"),
            bgcolor=pilomarimage.BGR("Black"),
            hjust="r",
        )
        # Astro location.
        if (
            session.target.object_type != "meteor"
        ):  # *Q* This doesn't work for meteor shower observations, so don't show it until fixed.
            text = az_alt_text(CentreAz, CentreAlt, "deg")
            NewImageBuffer.AddText(
                text,
                xpos,
                NewImageBuffer.PrevTextY,
                color=pilomarimage.BGR("HotPink"),
                bgcolor=pilomarimage.BGR("Black"),
                hjust="r",
            )
            text = "RA: " + str(cRa) + " Dec: " + str(cDec)
            NewImageBuffer.AddText(
                text,
                xpos,
                NewImageBuffer.PrevTextY,
                color=pilomarimage.BGR("HotPink"),
                bgcolor=pilomarimage.BGR("Black"),
                hjust="r",
            )
        # Lens characteristics
        text = (
            "FOV: "
            + deg_3dp(lens_in_use.fov_horizontal)
            + "deg * "
            + deg_3dp(lens_in_use.fov_vertical)
            + "deg"
        )  # DEGREE_SYMBOL
        NewImageBuffer.AddText(
            text,
            xpos,
            NewImageBuffer.PrevTextY,
            color=pilomarimage.BGR("Gold"),
            bgcolor=pilomarimage.BGR("Black"),
            hjust="r",
        )
        # Exposure details
        NewImageBuffer.AddText(
            "Exposure: " + str(camera_in_use.exposure_seconds) + " seconds.",
            xpos,
            NewImageBuffer.PrevTextY,
            color=pilomarimage.BGR("Gold"),
            bgcolor=pilomarimage.BGR("Black"),
            hjust="r",
        )
        # Photo capture time.
        NewImageBuffer.AddText(
            "Captured: " + str(camera_in_use.last_image_date_time),
            xpos,
            NewImageBuffer.PrevTextY,
            color=pilomarimage.BGR("Gold"),
            bgcolor=pilomarimage.BGR("Black"),
            hjust="r",
        )
        if (
            camera_in_use.capture_start > camera_in_use.capture_end
        ):  # *Q* Timestamp range is sometimes invalid. Needs investigating.
            cam_log.log(
                "markup_preview: Capture timestamps invalid:",
                str(camera_in_use.capture_start),
                "-",
                str(camera_in_use.capture_end),
                level="warning",
                terminal=False,
            )
        text = "ImageCaptureEnd: " + str(camera_in_use.capture_end)
        NewImageBuffer.AddText(
            text,
            xpos,
            NewImageBuffer.PrevTextY,
            color=pilomarimage.BGR("Cyan"),
            bgcolor=pilomarimage.BGR("Black"),
            hjust="r",
        )
        text = "Markup time: " + str(ts_to_datetime(t))
        NewImageBuffer.AddText(
            text,
            xpos,
            NewImageBuffer.PrevTextY,
            color=pilomarimage.BGR("Orange"),
            bgcolor=pilomarimage.BGR("Black"),
            hjust="r",
        )
        text = "Target: " + session.target.name  # Target
        NewImageBuffer.AddText(
            text,
            xpos,
            NewImageBuffer.PrevTextY,
            color=pilomarimage.BGR("White"),
            thickness=2,
            bgcolor=pilomarimage.BGR("Black"),
            hjust="r",
        )

    if True:  # Parameters.MarkupSaveDraft:
        cam_log.log("markup_preview: SaveDraft", filename, terminal=False)
        CameraWindow.print(
            now_hour_minute_sec() + " " + filename.split("/")[-1]
        )  # Show the preview filename that's being generated.
        NewImageBuffer.SaveFile(filename)
        camera_in_use.previewjpg = (
            filename  # Record the filename so that the web interface can access it.
        )

    cam_log.log(
        "markup_preview: Elapsed time ",
        str((now_utc() - RoutineStart).total_seconds()),
        terminal=False,
    )
    cam_log.log("markup_preview: End", terminal=False)
    return True


def create_target_image(
    color=False, MinMagnitude=None, astrotime=None, StarLimit=None, textlabel=None
):
    """Create a mockup target image based purely upon the expected view.
    color parameter dictates whether the return is GRAYSCALE or COLOR.
      Color images are generated when simulating a photograph (when the camera is disabled).
      Grayscale images are generated when creating a target star map for AstroAlign.
    By default it selects stars based upon Parameters.TargetMinMagnitude, however the calling routine can override this if required.
    color=True generates a colour image, star colours are estimated from the Hipparcos catalog data (B-V measure).
        This mode is used to simulate an observation photograph if there is no physical camera attached.
    applydistortion = The image can have estimated lens distortion applied to more closely match a real photograph.
    """
    cam_log.log(
        "create_target_image: Start. color",
        color,
        ", MinMagnitude",
        MinMagnitude,
        terminal=False,
    )
    if astrotime is not None:
        cam_log.log(
            "create_target_image: Start. Astrotime",
            ts_to_datetime(astrotime),
            terminal=False,
        )
    else:
        cam_log.log("create_target_image: Start. Astrotime", astrotime, terminal=False)
    RoutineStart = now_utc()  # Note the time that this routine starts.
    if (
        astrotime is None
    ):  # No specific time given, so we're live! Use current time and current camera position.
        t = (
            skyfield_now()
        )  # Current timestamp in 'astro' time. As close as possible to the time of the photograph itself. Could develop this further! # Offset supported.
        if (
            params.use_live_location
        ):  # Use the live target location rather than the last reported camera position for image processing.
            az_degree, alt_degree = session.target.az_alt_degrees(
                time=t
            )  # What is the alt/az location of the centre of the image?
            cam_log.log(
                "create_target_image: No astrotime received. Using current target position, at",
                ts_to_datetime(t),
                "alt",
                deg_3dp(alt_degree),
                "deg, az",
                deg_3dp(az_degree),
                "deg. at",
                ts_to_datetime(t),
                "for calculations",
                terminal=False,
            )
        else:  # Use the last reported camera position. Deprecated.
            alt_degree, az_degree = (
                last_reported_alt_az()
            )  # What is the alt/az location of the centre of the image?
            # ldt = last_reported_location_datetime() # Get the timestamp of the oldest position reading.
            cam_log.log(
                "create_target_image: No astrotime received. Using last reported camera position from",
                last_reported_location_datetime(),
                ", using",
                "alt",
                deg_3dp(alt_degree),
                "deg, az",
                round(az_degree),
                "deg. at",
                ts_to_datetime(t),
                "for calculations",
                terminal=False,
            )
    else:  # A specific time given, so calculate the view at that time.
        t = astrotime
        az_degree, alt_degree = session.target.az_alt_degrees(
            time=astrotime
        )  # Get expected camera position at specified time.
        cam_log.log(
            "create_target_image: Specific astrotime received. Using",
            ts_to_datetime(t),
            deg_3dp(alt_degree),
            "deg",
            deg_3dp(az_degree),
            "deg",
            terminal=False,
        )
    tgt_az_degree, tgt_alt_degree = session.target.az_alt_degrees(
        time=t
    )  # Get expected camera position at specified time.
    cam_log.log(
        "create_target_image: Latest Alt/Az",
        deg_3dp(alt_degree),
        "/",
        deg_3dp(az_degree),
        "deg",
        "; Target location Alt/Az",
        deg_3dp(tgt_alt_degree),
        "/",
        deg_3dp(tgt_az_degree),
        "deg",
        "; Latest vs Target Alt/Az",
        deg_3dp(alt_degree - tgt_alt_degree),
        "/",
        deg_3dp(az_degree - tgt_az_degree),
        "deg",
        terminal=False,
    )
    if abs(alt_degree - tgt_alt_degree) > 0.5 or abs(az_degree - tgt_az_degree) > 0.5:
        cam_log.log(
            "create_target_image: Latest vs Target locations differ too much: Alt/Az",
            round(alt_degree - tgt_alt_degree, 4),
            "/",
            round(az_degree - tgt_az_degree, 4),
            terminal=False,
        )
        DevWindow.print(
            now_hour_minute_sec()
            + " Latest v Target error alt/az "
            + str(round(alt_degree - tgt_alt_degree, 4))
            + "/"
            + str(round(az_degree - tgt_az_degree, 4))
        )
    NewTargetImage = pilomarimage(
        name="target_work", logger=cam_log
    )  # Create a new black canvas to draw upon.
    width = (
        sensor_in_use.pixel_width
    )  # Image dimension should match the live photos that will be compared against.
    height = sensor_in_use.pixel_height
    NewTargetImage.New(height, width, imagetype="bgr", datatype=np.uint8)
    if (
        MinMagnitude is None
    ):  # Calling procedure can override the minimum magnitude parameter.
        MinMagnitude = params.target_min_magnitude
    cam_log.log("create_target_image: MinMagnitude:", MinMagnitude, terminal=False)
    starlist = (
        []
    )  # Create star list. This will be used by astroalign.find_transform() in tracking.

    # Mark neighbouring stars on the picture too. This will help with alignment.
    CentreRa, CentreDec = (
        session.target.ra_dec_degrees()
    )  # Calculations for target from observer's location. Returns decimal degree values.
    # Find Hipparcos objects with specific ra/dec values (+/- 10degrees)
    MinRADeg = CentreRa - params.target_inclusion_radius
    MaxRADeg = CentreRa + params.target_inclusion_radius
    MinDecDeg = CentreDec - params.target_inclusion_radius
    MaxDecDeg = CentreDec + params.target_inclusion_radius
    cam_log.log(
        "create_target_image: Range RA=",
        MinRADeg,
        "<- (",
        CentreRa,
        ") ->",
        MaxRADeg,
        "deg.",
        terminal=False,
    )
    cam_log.log(
        "create_target_image: Range Dec=",
        MinDecDeg,
        "<- (",
        CentreDec,
        ") ->",
        MaxDecDeg,
        "deg.",
        terminal=False,
    )

    if color:  # Mark neighbouring Messier objects ....
        cam_log.log("create_target_image: ShowMessier", terminal=False)
        # Find that alt/az locations of all the objects.
        ItemCount = 0
        FullCount = 0
        for TempStarName, TempStarParms in Messier_dictionary.items():  # Python3
            FullCount += 1
            TempStarMagnitude = TempStarParms["magnitude"]
            if TempStarMagnitude > params.target_min_magnitude:  # Too dim to show.
                continue  # Skip to next object.
            TempStarRA = TempStarParms["radeg"]  # HMSToAngle(TempRAH,TempRAM,TempRAS)
            if TempStarRA < MinRADeg or TempStarRA > MaxRADeg:  # Outside drawing area.
                continue  # Skip to next object
            TempDED = TempStarParms["dec"][0]  # Declination DEGREES
            TempDEM = TempStarParms["dec"][1]  # Declination MINUTES
            TempDES = TempStarParms["dec"][2]  # Declination SECONDS
            TempStarDec = TempStarParms["decdeg"]  # DMSToAngle(TempDED,TempDEM,TempDES)
            if (
                TempStarDec < MinDecDeg or TempStarDec > MaxDecDeg
            ):  # Outside drawing area.
                continue  # Skip to next object
            TempStar = Star(
                ra_hours=(
                    TempStarParms["ra"][0],
                    TempStarParms["ra"][1],
                    TempStarParms["ra"][2],
                ),
                dec_degrees=(TempDED, TempDEM, TempDES),
            )  # Create star object from RADEC co-ordinates.
            TempStarType = TempStarParms["type"]
            if TempStarType in ["galaxy", "cluster", "milky way"]:
                TempStarColor = pilomarimage.BGR("MidnightBlue")
            else:
                TempStarColor = pilomarimage.BGR("HotPink")
            TempStarWidth = int(
                (TempStarParms["widthdeg"] * camera_in_use.pixels_per_fov_degree_width)
                / 2
            )  # Convert from degree diameter to pixel radius.
            TempStarHeight = int(
                (
                    TempStarParms["heightdeg"]
                    * camera_in_use.pixels_per_fov_degree_height
                )
                / 2
            )
            temptarget = AstroTarget(
                TempStar,
                name=TempStarName,
                objecttype=TempStarType,
                constellation="",
                description="",
                magnitude=TempStarMagnitude,
            )
            TempStarAz, TempStarAlt = temptarget.az_alt_degrees(time=t)
            PlotStarAlt, PlotStarAz = relative_alt_az(
                TempStarAlt, TempStarAz, alt_degree, az_degree
            )
            TempStarX, TempStarY = plot_relative_alt_az(
                PlotStarAlt, PlotStarAz, height, width
            )
            NewTargetImage.FillEllipse(
                TempStarX,
                TempStarY,
                TempStarWidth,
                TempStarHeight,
                angle=0,
                startAngle=0,
                endAngle=360,
                color=TempStarColor,
            )
            ItemCount += 1
        cam_log.log(
            "create_target_image: Plot Messier objects end. (",
            ItemCount,
            "/",
            FullCount,
            "objects selected)",
            terminal=False,
        )

    if color:  # Mark neighbouring NGC items ...
        # Find that alt/az locations of all the objects.
        # NGC catalog is large, eliminate as much as possible first.
        boolseries = NGC_DF["radeg"].between(
            MinRADeg, MaxRADeg, inclusive="both"
        )  # Create filter for items within RA range.
        tempdf = NGC_DF[boolseries]  # Apply filter.
        boolseries = tempdf["decdeg"].between(
            MinDecDeg, MaxDecDeg, inclusive="both"
        )  # Create filter for items with Dec range.
        tempdf = tempdf[boolseries]  # Apply filter.
        for i in range(len(tempdf)):
            TempStarParms = tempdf.iloc[
                i
            ]  # Select each row in turn from the Pandas dataframe.
            TempStar = Star(
                ra_hours=(
                    TempStarParms["rah"],
                    TempStarParms["ram"],
                    TempStarParms["ras"],
                ),
                dec_degrees=(
                    TempStarParms["ded"],
                    TempStarParms["dem"],
                    TempStarParms["des"],
                ),
            )  # Create star object from RADEC co-ordinates.
            TempStarWidth = int(
                (TempStarParms["widthdeg"] * camera_in_use.pixels_per_fov_degree_width)
                / 2
            )  # Convert from degree diameter to pixel radius.
            TempStarHeight = int(
                (
                    TempStarParms["heightdeg"]
                    * camera_in_use.pixels_per_fov_degree_height
                )
                / 2
            )
            temptarget = AstroTarget(
                TempStar,
                name=TempStarParms["name"],
                objecttype="ngc",
                constellation="",
                description="",
                magnitude=TempStarParms["magnitude"],
            )
            TempStarAz, TempStarAlt = temptarget.az_alt_degrees(time=t)
            PlotStarAlt, PlotStarAz = relative_alt_az(
                TempStarAlt, TempStarAz, alt_degree, az_degree
            )
            TempStarX, TempStarY = plot_relative_alt_az(
                PlotStarAlt, PlotStarAz, height, width
            )
            cam_log.log(
                "create_target_image: Plot NGC ",
                i,
                tempdf["name"],
                "at",
                TempStarX,
                TempStarY,
                "radius",
                TempStarWidth,
                TempStarHeight,
                terminal=False,
            )
            NewTargetImage.FillEllipse(
                TempStarX,
                TempStarY,
                TempStarWidth,
                TempStarHeight,
                angle=0,
                startAngle=0,
                endAngle=360,
                color=pilomarimage.BGR("DarkGreen"),
            )
        cam_log.log(
            "create_target_image: NGCItems: Plot NGC objects end. (",
            len(tempdf),
            "/",
            len(NGC_DF),
            "objects selected)",
            terminal=False,
        )

    # Decide on a cutoff for the number of stars to plot.
    # If not specified by calling routine, try to match the number of stars detected in the latest live image.
    # (When simulating images, the first tracking pass will have 0 stars in the LatestStarCount, because it doesn't exist until we create it here.)
    if StarLimit is None:
        StarLimit = max(DriftTracker.LatestImage.StarCount + 10, 50)
        cam_log.log(
            "create_target_image: LatestStarCount from last saved image is:",
            DriftTracker.LatestImage.StarCount,
            terminal=False,
        )
        cam_log.log(
            "create_target_image: LatestImage exists?",
            DriftTracker.LatestImage.ImageExists(),
            terminal=False,
        )
    cam_log.log("create_target_image: Setting StarLimit as:", StarLimit, terminal=False)
    TempStarRadius = int(
        params.tracking_star_radius
    )  # Default is that all stars are the same size in this image.

    if True:  # Parameters.TargetShowStars: # Mark neighbouring stars.
        # *Q* This can be very slow, taking 270 seconds in some tests. This hits the CPU hard especially when faking all the photographs!
        #     But when run alone consistently takes only 18 seconds. Hmmmmm.... A conflict comewhere?
        StarCount = 0  # How many stars have we plotted?
        NeighbouringStars = local_stars.get(CentreRa, CentreDec)
        cam_log.log(
            "create_target_image: NeighbouringStars contains",
            len(NeighbouringStars),
            "entries.",
            terminal=False,
        )
        TotalStars = len(NeighbouringStars)
        hsat = HomeSite.at(t)  # Calculate this once, it's reused for each star in turn.
        TempStarColor = pilomarimage.BGR(
            "White"
        )  # B&W tracking images are just simple white dots.

        for i in range(TotalStars):
            if i % 400 == 0:
                cam_log.log(
                    "create_target_image.ShowStars: Processing star", i, terminal=False
                )  # Monitor performance
                time.sleep(
                    0.1
                )  # Put a small pause in occassionally to let other processes get a chance!
            TempStarRec = NeighbouringStars.iloc[
                i
            ]  # Select each row in turn from the Pandas dataframe.
            TempStar = Star.from_dataframe(
                TempStarRec
            )  # Convert the Hipparcos entry into a Skyfield STAR object.
            TempStarAlt, TempStarAz, TempStarDistance = (
                hsat.observe(TempStar).apparent().altaz()
            )  # Get the azimuth and altitude position of the star in the sky.
            if not color and TempStarAlt.degrees < 0:  # Below horizon
                continue  # Don't plot it.
            PlotStarAlt, PlotStarAz = relative_alt_az(
                TempStarAlt.degrees, TempStarAz.degrees, alt_degree, az_degree
            )  # Calculate chart position relative to the centre of the chart.
            # Calculate the location in the preview image.
            TempStarX, TempStarY = plot_relative_alt_az(
                PlotStarAlt, PlotStarAz, height, width
            )
            if NewTargetImage.OutOfBounds(
                TempStarX, TempStarY
            ):  # The star is off the edge of the image, ignore it.
                continue  # The star is off the edge of the image, ignore it.
            TempStarMagnitude = TempStarRec[
                "magnitude"
            ]  # Note the brightness of the star.
            if TempStarMagnitude > MinMagnitude:  # Too dim
                continue  # The star is too dim, ignore it.
            if (
                color
            ):  # Colour images need star colour and represent the magnitude via the size of the star.
                TempStarRadius = int(TempStarRec["starradius"])
                TempStarColor = (
                    int(TempStarRec["color_b"]),
                    int(TempStarRec["color_g"]),
                    int(TempStarRec["color_r"]),
                )
            NewTargetImage.FillCircle(
                TempStarX, TempStarY, TempStarRadius, color=TempStarColor
            )
            starlist.append(
                [TempStarX, TempStarY]
            )  # *Q* Does latest drift calculation need Radius or Magnitude anymore?
            StarCount += 1  # Increment the count of stars plotted.
            if StarCount >= StarLimit:
                cam_log.log(
                    "create_target_image: DriftTracker star limit "
                    + str(StarLimit)
                    + " reached.",
                    terminal=False,
                )
                cam_log.log(
                    "create_target_image: DriftTracker star limit reached HIP",
                    TempStarRec.name,
                    ", magnitude",
                    TempStarRec["magnitude"],
                    terminal=False,
                )
                break
        cam_log.log(
            "create_target_image: Marked",
            StarCount,
            "of",
            StarLimit,
            "Stars,",
            TotalStars,
            "available.",
            terminal=False,
        )
        if StarCount < StarLimit:
            cam_log.log(
                "create_target_image: Exhausted NeighbouringStars cache after",
                StarCount,
                "stars.",
                terminal=False,
            )
    else:
        cam_log.log("create_target_image: No stars plotted.", terminal=False)

    if True:  # Parameters.TargetShowPlanets: # Mark neighbouring planets ....
        # Find the alt/az locations of all the planets.
        cam_log.log("create_target_image: Plot planets start.", terminal=False)
        PlanetRadii = [
            40,
            4,
            6,
            40,
            6,
            10,
            10,
            4,
            4,
            4,
        ]  # Radius to draw solar system objects. Must match list below.
        PlanetColors = [
            pilomarimage.BGR("Yellow"),
            pilomarimage.BGR("White"),
            pilomarimage.BGR("White"),
            pilomarimage.BGR("White"),
            pilomarimage.BGR("Red"),
            pilomarimage.BGR("Yellow"),
            pilomarimage.BGR("Gold"),
            pilomarimage.BGR("White"),
            pilomarimage.BGR("Blue"),
            pilomarimage.BGR("White"),
        ]  # Color to draw solar system objects. Must match list below.
        for i, TempStarName in enumerate(
            [
                "sun",
                "mercury barycenter",
                "venus barycenter",
                "moon",
                "mars barycenter",
                "jupiter barycenter",
                "saturn barycenter",
                "uranus barycenter",
                "neptune barycenter",
                "pluto barycenter",
            ]
        ):
            TempStarMagnitude = 0.0
            if TempStarMagnitude > MinMagnitude:  # Too dim to show.
                continue  # Skip to next planet.
            if color:  # Color images try to be vaguelly realistic.
                TempStarColor = PlanetColors[i]
                TempStarRadius = PlanetRadii[i]
            else:  # Grayscale images just need to show dots for items.
                TempStarColor = pilomarimage.BGR("White")
            TempStarDescription = TempStarName
            TempStar = planets[TempStarName]
            temptarget = AstroTarget(
                TempStar,
                name=TempStarName,
                objecttype="planet",
                description=TempStarDescription,
                magnitude=0.0,
            )
            TempStarAz, TempStarAlt = temptarget.az_alt_degrees(time=t)
            # Calculate the location of the star in the field of view!
            PlotStarAlt, PlotStarAz = relative_alt_az(
                TempStarAlt, TempStarAz, alt_degree, az_degree
            )  # Calculate chart position relative to the centre of the chart.
            # Calculate the location in the preview image.
            TempStarX, TempStarY = plot_relative_alt_az(
                PlotStarAlt, PlotStarAz, height, width
            )
            NewTargetImage.FillCircle(
                TempStarX, TempStarY, TempStarRadius, color=TempStarColor
            )
        cam_log.log("create_target_image: Plot planets end.", terminal=False)

    if textlabel is not None:  # We have a text string to include in the image too.
        NewTargetImage.AddText(
            textlabel, 10, 50, color=pilomarimage.BGR("White"), size=1.0, thickness=1
        )

    if color:  # Return a colour image.
        pass
    else:  # Return Grayscale image.
        NewTargetImage.ChangeType("grayscale")  # Convert BGR to grayscale.
    cam_log.log(
        "create_target_image: Elapsed time ",
        str((now_utc() - RoutineStart).total_seconds()),
        terminal=False,
    )
    cam_log.log("create_target_image: Complete.", terminal=False)
    return NewTargetImage.ImageBuffer, StarCount, starlist


camera_in_use.image_simulator = (
    create_target_image  # Tell astrocamera how to generate simulated images.
)
camera_in_use.relative_alt_az = relative_alt_az  # Point to utility functions.
camera_in_use.plot_relative_alt_az = plot_relative_alt_az  # Point to utility functions.


def auto_preview():
    """Take immediate automatic photograph and mark it up with the expected objects in view.
    This is normally used for calibration and testing."""
    main_log.log("auto_preview", terminal=True)
    FileRoot = FolderHandler.prep_file("preview", "preview_")
    camera_in_use.set_image_type("auto")
    # raspistill -o {&output} -ex off -t 10 -n -q 100 -md {&mode} -w {&width} -h {&height} -ag 16.0 -ss {&shutter}
    # libcamera-still --output {&output} --timeout 10 --nopreview --quality 100 --width {&width} --height {&height} --denoise off --analoggain 16.0 --shutter {&shutter}
    CameraCommand = params._camera_auto_command
    # CaptureSet will automatically set mode,width and height parameters if they are in the command line.
    main_log.log("auto_preview: Capturing image...", terminal=True)
    result = camera_in_use.capture_set(
        file_root=FileRoot, batch_size=1, camera_command=CameraCommand, terminal=False
    )
    main_log.log("auto_preview: Marking image...", terminal=True)
    markup_preview()
    main_log.log("Done.", terminal=True)
    return result


def manual_preview():
    """Force immediate image capture from the camera.
    This is used to help check camera focus or alignment without
    starting a full observation loop."""
    print(TextColor.yellow("manual_preview"))
    print("Capture PREVIEW images.")
    print("Lens cap should be OFF.")
    print("The camera will not track during preview functions.")
    print("Camera will use automatic exposure settings in PREVIEW mode.")
    inp = ""
    result = False
    while inp != "x":
        inp = input("<RETURN> to begin ('x' to quit): ").lower()  # Python3
        if inp == "x":
            print("quit")
            break
        result = auto_preview()
    return result


def image_count_session():
    """Count images in each folder for the current session.
    It counts the occurrences of whichever filetype the program is currently generating.
    - *.dng, or *.fits or *.jpg
    So it avoids double-counting images if multiple image types are being generated."""
    result = ""
    campaignkey = FolderHandler.get_path(
        "campaign"
    )  # Only interested in files within the campaign structure.
    imagetypes = ["jpg", "dng", "fits"]
    for key, value in FolderHandler.folder_list.items():  # Python3: Check each folder.
        vpath = value["path"]  # Get the path.
        if not value["exists"]:
            continue  # Folder hasn't been created yet.
        if vpath.startswith(campaignkey):
            filelist = []
            try:
                for file in os.listdir(vpath):  # List files in folder.
                    filename = file.split(".")[0]
                    filetype = file.split(".")[-1]
                    if filetype in imagetypes:  # It's an image file.
                        if not filename in filelist:
                            filelist.append(
                                filename
                            )  # list of unique filenames (minus filetype).
            except Exception as e:
                main_log.log(
                    "image_count_session: Failed with:", e, level="warning"
                )  # Allow graceful failure in case the folder nolonger exists.
            count = len(filelist)
            if count > 0:  # Only report the folder if there's something in it.
                result += (
                    key + "=" + str(count) + " "
                )  # Abbreviate image type and number of images.
    if result == "":
        result = "None"
    return result


def image_count_campaign():
    """Count images in each folder for the current campaign.
    It counts the occurrences of whichever filetype the program is currently generating.
    - *.dng, or *.fits or *.jpg
    So it avoids double-counting images if multiple image types are being generated."""
    # *Q* This solution slows down a lot for large file collections. Could be faster, but not used during an observation.
    result = ""
    selext = ".jpg"  # Default to jpg if no camera is enabled.
    if params.camera_enabled != True:
        selext = ".jpg"  # No camera, so only count the simulated jpgs.
    elif camera_in_use.fast_image_capture:
        selext = ".jpg"  # Fast image capture, only initial jpgs exist so far.
    elif camera_in_use.camera_save_jpg:
        selext = ".jpg"  # Looking for .jpg will detect more than .dng
    elif camera_in_use.camera_save_fits:
        select = ".fits"
    elif camera_in_use.camera_save_dng:
        selext = ".dng"
    else:
        selext = ".jpg"
    basedir = FolderHandler.get_path("campaign")
    main_log.log("image_count_campaign: basedir", basedir, terminal=False)
    searchpath = basedir + "/**/*" + selext
    main_log.log("image_count_campaign: searchpath", searchpath, terminal=False)
    FileCountList = {}
    for file in glob.glob(
        searchpath, recursive=True
    ):  # Recursive search through all the folders of the current campaign.
        trimmedfile = file.replace(basedir, "")  # Strip search path out.
        foldertype = trimmedfile.split("/")[-2].split("_")[
            0
        ]  # Last remaining item is filename, Penultimate folder is image type.
        FileCountList[foldertype] = (
            FileCountList.get(foldertype, 0) + 1
        )  # How many files of this type so far?
    # Convert the list of image types and counts into a summarised text string.
    for key, value in FileCountList.items():
        result += (
            key + "=" + str(value) + " "
        )  # Abbreviate image type and number of images.
    if result == "":
        result = "None"
    return result


def image_count():  # Could just be image_count_session() directly now.
    """Return count of images per type."""
    return (
        image_count_session()
    )  # Return values for the session, ignore other sessions in the same campaign.


def check_image_set():
    """Check that we have a full set of images.
    Call this before allowing a change of target, session parameters or ending a session.
    If the user selects YES, then we allow the target/session to change.
    If the user selects NO, then we keep the session alive with the current target and settings.
    If the folder has been deleted, then there are no images to worry about!"""
    imagelist = image_count()
    result = True  # We're happy that the image list is OK.
    if len(imagelist) > 0 and imagelist != "None":
        lines = [
            "Make sure you have captured the full set of images you need for this session.",
            "You will normally need a set of LIGHT, DARK, FLAT, DARK FLAT and BIAS images.",
            "Recommended minimum for stacking: LIGHT, DARK and BIAS sets.",
            "Images captured so far:",
            imagelist,
        ]
        TextColor.text_box(lines, fg=TextColor.YELLOW, bg=TextColor.BLACK)
        result = ask_yes_no("Is this session complete? [y/N]", default=False)
        print(" ")
    return result


def camera_handler(outboundqueue, inboundqueue):
    """This can run in a separate thread to take photos without distrubing tracking functions.
    Long exposures (>4seconds) really need the camera to move DURING the exposure.
    outboundqueue and inboundqueue are the communication queues that can be used to control this thread.
    """
    RunThread = True  # Set to False to terminate the handler. This will shutdown the thread entirely.
    batch_size = 1
    cam_log.log("camera_handler: Started")
    CameraWindow.print(now_hour_minute_sec() + " camera_handler started.")
    ready_to_observe = False  # When True the handler can start taking photographs.
    cam_log.log("camera_handler.initial: ready_to_observe = False", terminal=False)
    prev_ready_to_observe = False  # Detect when the ready_to_observe status changes.
    PhotoCount = 0  # Counter of completed photographs.
    camera_in_use.batch_count = 0  # Counter of completed photographs.
    az_drift_steps = 0
    alt_drift_steps = 0
    DriftX = None
    DriftY = None
    TimeAllocation = (
        {}
    )  # Measure how much time is spent on each task. Helps get scheduling and priorities right.
    AllocationTimer = Timer(600)  # Report time allocation figures every 10 minutes.
    LoopCounter = 0  # Count the number of loops.
    camera_in_use.current_task = None  # No task currently active.
    # Flush any outstanding commands in the command queue.
    FlushedCount = 0
    while (
        not inboundqueue.empty()
    ):  # There are some commands available from observation_run to the camera.
        # Get the incoming message.
        ReceivedMessage = inboundqueue.get()
        cam_log.log(
            "camerahandler: Communication flush: Ignoring:",
            ReceivedMessage,
            terminal=False,
        )
        FlushedCount += 1
    if FlushedCount > 0:
        CameraWindow.print("Flushed", FlushedCount, "old messages.")
    # Set observation specific parameters. These change based upon the target type etc.
    # - This sets camera_in_use.camera_tasks, the types of images to save, fast capture mode etc.
    camera_in_use.set_observation_parameters(
        session
    )  # Set observation specific parameters. These change based upon the target type etc.

    cam_log.log("camerahandler: Begin main loop.", terminal=False)
    while (
        RunThread
    ):  # This will run through all queued commands in sequence, then start polling periodically for new ones.
        if (
            not threading.main_thread().is_alive()
        ):  # Check if parent thread is still alive. Quit if it is nolonger there.
            cam_log.log(
                "camera_handler: Parent thread is nolonger alive. Stopping.",
                level="error",
            )
            RunThread = False
            time.sleep(5)
            break

        # Which task will we perform in this loop?
        LoopTask = camera_in_use.camera_tasks[0]
        camera_in_use.current_task = LoopTask
        LoopStartTimestamp = now_utc()  # How much time has been spent on this task?
        PrevTaskList = (
            camera_in_use.camera_tasks
        )  # This will be restored if the camera receives an override task from the main loop. So we don't miss anything.
        camera_in_use.camera_tasks = camera_in_use.camera_tasks[
            1:
        ]  # Shift the task list ready for the next loop.
        camera_in_use.camera_tasks.append(LoopTask)
        cam_log.log("camera_handler: Loop task:", LoopTask, terminal=False)

        # This will run through all queued commands in sequence before capturing images if allowed.
        # This is performed regardless of which task is being performed in this loop.
        while (
            not inboundqueue.empty()
        ):  # There are some commands available from observation_run to the camera.
            # Get the incoming message.
            ReceivedMessage = inboundqueue.get()
            camera_in_use.rx_count += 1
            cam_log.log(
                "camera_handler received command: " + str(ReceivedMessage),
                terminal=False,
            )
            CameraTxWindow.print(
                dictionary_to_string(ReceivedMessage)
            )  # Report communications from Main to Camera.
            if "Stop" in ReceivedMessage:  # Main routine has told camera to shutdown.
                RunThread = False
                ReplyMessage = {
                    "TimeStamp": now_utc(),
                    "Stop": "acknowledged",
                }  # Confirm back to main thread that STOP will be attempted.
                outboundqueue.put(ReplyMessage)
                camera_in_use.tx_count += 1
                CameraRxWindow.print(
                    dictionary_to_string(ReplyMessage)
                )  # Report communications from Camera to Main.
            if (
                "LoopTask" in ReceivedMessage
            ):  # Main routine has requested an immediate preview image or some other task override.
                # If multiple overrides are received in the same loop, only the latest one is actioned.
                LoopTask = ReceivedMessage[
                    "Task"
                ]  # Overwrite LoopTask to make it do whatever the main routine wants.
                camera_in_use.camera_tasks = PrevTaskList  # We have overridden the planned task sequence, restore the planned list to it's previous state so nothing is missed.
                DevWindow.print(
                    now_hour_minute_sec()
                    + ' LoopTask override "'
                    + LoopTask
                    + '" received.'
                )
                cam_log.log(
                    "camera_handler.inboundqueue: LoopTask overridden with",
                    LoopTask,
                    terminal=False,
                )
            if (
                "BatchSize" in ReceivedMessage
            ):  # Main routine is updating the batch size.
                batch_size = ReceivedMessage["BatchSize"]
            if (
                "ready_to_observe" in ReceivedMessage
            ):  # Main routine is updating the ready_to_observe status.
                ready_to_observe = ReceivedMessage["ready_to_observe"]
                cam_log.log(
                    "camera_handler.inboundqueue: ready_to_observe =",
                    ready_to_observe,
                    terminal=False,
                )
            if "Reset" in ReceivedMessage:  # Instruction to reset image buffers.
                camera_in_use.reset()  # Reset the image buffers.
                CameraWindow.print(now_hour_minute_sec() + " Reset image buffers.")
                cam_log.log(
                    "camera_handler.inboundqueue: reset received.", terminal=False
                )
            if (
                "PhotoCount" in ReceivedMessage
            ):  # Main routine is updating the current photo count.
                PhotoCount = ReceivedMessage["PhotoCount"]
                ReplyMessage = {
                    "TimeStamp": now_utc(),
                    "PhotoCountReset": True,
                }  # Acknowledge that the photo count has been reset.
                outboundqueue.put(ReplyMessage)
                camera_in_use.tx_count += 1
                CameraRxWindow.print(
                    dictionary_to_string(ReplyMessage)
                )  # Report communications from Camera to Main.

        if LoopTask == "image":  # Taking an actual photo.
            image_status_window.field_value(
                "CTASK", LoopTask, fg=TextColor.BLACK, bg=OSW_TEXT_GOOD
            )  # Tell the image status window what the camera is currently doing.
        elif LoopTask == "tracking":  # Taking a tracking photo.
            image_status_window.field_value(
                "CTASK", LoopTask, fg=TextColor.BLACK, bg=TextColor.CYAN
            )
        elif LoopTask == "preview":  # Generate preview image.
            image_status_window.field_value(
                "CTASK", LoopTask, fg=TextColor.BLACK, bg=TextColor.MAGENTA
            )
        else:  # Doing something else.
            image_status_window.field_value(
                "CTASK", LoopTask, fg=TextColor.BLACK, bg=OSW_TEXT_POOR
            )  # Tell the image status window what the camera is currently doing.

        # If the Microcontroller stops working or talking, we cannot be sure that ready_to_observe is still valid.
        # So after xx seconds of no microcontroller messages, reset ready_to_observe.
        if ready_to_observe and Mctl.RxAge() > Mctl.CommsTimeout:
            cam_log.log(
                "camera_handler: (cam_log) No recent messages from microcontroller (",
                Mctl.CommsTimeout,
                "s), assuming ready_to_observe is nolonger valid.",
                level="warning",
                terminal=False,
            )
            ready_to_observe = False
            cam_log.log(
                "camera_handler. Microcontroller comms timeout: ready_to_observe = False",
                terminal=False,
            )
            error_window.print(
                now_hour_minute_sec() + " Microcontroller comms timeout."
            )

        if (
            ready_to_observe != prev_ready_to_observe
        ):  # Note the change in status of ready_to_observe.
            CameraWindow.print(
                now_hour_minute_sec() + " ready_to_observe " + str(ready_to_observe)
            )
            prev_ready_to_observe = ready_to_observe
            cam_log.log(
                "camera_handler. Change of state: ready_to_observe from ",
                prev_ready_to_observe,
                "to",
                ready_to_observe,
                terminal=False,
            )

        if ready_to_observe:
            # Calculate drift.
            if (
                LoopTask == "tracking"
            ):  # Time to consider a tracking check, and it's enabled.
                if (
                    DriftTracker.TrackingAge() is None
                    or DriftTracker.TrackingAge() > DriftTracker.TrackingInterval
                ):
                    TrackingDue = True
                else:
                    TrackingDue = False
                if (
                    not params.use_tracking
                ):  # Tracking currently disabled. (User can dynamically change this switch during observation).
                    if TrackingDue:
                        DriftWindow.print(
                            now_hour_minute_sec() + " Drift tracking disabled."
                        )  # Warn the user.
                elif TrackingDue:
                    # First update the DriftTracker
                    obs_start = now_utc()
                    cam_log.log(
                        "camera_handler: Begin tracking image capture", terminal=False
                    )
                    DriftWindow.print(
                        now_hour_minute_sec() + " Begin tracking image capture."
                    )
                    if session.debug_mode:
                        print(
                            now_hour_minute_sec()
                            + " Begin "
                            + TextColor.cyan("tracking")
                            + " image capture."
                        )
                    try:
                        result = camera_in_use.take_tracking_photo(
                            batch_size, terminal=False
                        )
                    except Exception as e:
                        cam_log.log(
                            "camera_handler: camera_in_use.take_tracking_photo failed with:",
                            str(e),
                            level="error",
                        )
                        cam_log.report_exception(
                            e, comment="camera_handler: Call to TakeTrackingPhoto()"
                        )
                        result = False
                    cam_log.log(
                        "camera_handler: End tracking image capture", terminal=False
                    )
                    cam_log.log(
                        "camera_handler: Storing latest tracking image.", terminal=False
                    )
                    DriftTracker.SetLatestImage(
                        camera_in_use.image.ImageBuffer, obs_start
                    )  # OpenCV (numpy) array of the camera image it is saved in DriftTracker as Grayscale and reduced and enhanced.
                    cam_log.log(
                        "camera_handler: Consider storing target image...",
                        terminal=False,
                    )
                    cam_log.log(
                        "camera_handler: Begin create_target_image", terminal=False
                    )
                    if (
                        params.tracking_target_grayscale
                    ):  # Generate simplified tracking target.
                        TempCvBuffer, TempStarCount, TempStarList = create_target_image(
                            color=False,
                            MinMagnitude=params.target_min_magnitude,
                            StarLimit=2000,
                        )  # Create a completely calculated mock target image (grayscale). Used for image tracking.
                    else:  # Use more realistic tracking target.
                        TempCvBuffer, TempStarCount, TempStarList = create_target_image(
                            color=True,
                            MinMagnitude=params.target_min_magnitude,
                            StarLimit=2000,
                        )  # Create a completely calculated mock target image (grayscale). Used for image tracking.
                    cam_log.log(
                        "camera_handler: End create_target_image", terminal=False
                    )
                    cam_log.log(
                        "camera_handler: Stars",
                        TempStarCount,
                        ":",
                        TempStarList,
                        terminal=False,
                    )
                    cam_log.log(
                        "camera_handler: Calling SetTargetImage after create_target_image",
                        terminal=False,
                    )
                    DriftTracker.SetTargetImage(
                        TempCvBuffer,
                        starcount=TempStarCount,
                        starlist=TempStarList,
                        timestamp=obs_start,
                    )  # CvImage is an OpenCV (numpy) array of the camera image in grayscale.
                    cam_log.log(
                        "camera_handler: Completed SetTargetImage after create_target_image",
                        terminal=False,
                    )
                    cam_log.log(
                        "camera_handler: Begin drift calculation", terminal=False
                    )
                    DriftWindow.print(
                        now_hour_minute_sec()
                        + " Updating drift calculation for tracking."
                    )
                    az_drift_steps = 0  # No drift unless we safely calculate one.
                    alt_drift_steps = 0
                    if params.tracking_prediction:  # Project drift forward over time.
                        DriftX, DriftY, _ = DriftTracker.PredictedTransform(
                            now_utc()
                        )  # Predict the drift by using the measured drift between 2 images and extrapolating forward to now.
                    else:  # Use directly measured drift.
                        DriftX = DriftTracker.dx
                        DriftY = DriftTracker.dy
                    cam_log.log(
                        "camera_handler: DriftTracker PredictedTransform driftx",
                        str(DriftX),
                        "drifty",
                        str(DriftY),
                        terminal=False,
                    )
                    temp = len(DriftTracker.LatestStarMatchList)
                    if (
                        DriftX is not None and temp < params.tracking_match_threshold
                    ):  # At least 6 stars must have been matched.
                        cam_log.log(
                            "camera_handler: DriftTracker, low confidence.",
                            temp,
                            "star(s).",
                            terminal=False,
                        )
                        DriftWindow.print(
                            now_hour_minute_sec()
                            + " Low confidence. Matched "
                            + str(temp)
                            + " star(s)."
                        )
                        DriftX = None
                        DriftY = None
                    cam_log.log(
                        "camera_handler: DriftTracker trusted driftx",
                        str(DriftX),
                        "drifty",
                        str(DriftY),
                        terminal=False,
                    )
                    if DriftX is not None:
                        az_drift_steps = int(DriftX / az_pixels_per_fullstep)
                        alt_drift_steps = (
                            int(DriftY / alt_pixels_per_fullstep) * -1
                        )  # Invert result to convert from IMAGE Y direction to Motor Alt direction.
                        cam_log.log(
                            "camera_handler: Predicted drift: x="
                            + str(round(DriftX, 2))
                            + "("
                            + str(az_drift_steps)
                            + "steps), y="
                            + str(round(DriftY, 2))
                            + "("
                            + str(alt_drift_steps)
                            + "steps)",
                            terminal=False,
                        )
                    DriftWindow.print(
                        now_hour_minute_sec()
                        + " Drift result: "
                        + str(DriftX)
                        + ","
                        + str(DriftY)
                        + " px; "
                        + str(az_drift_steps)
                        + ","
                        + str(alt_drift_steps)
                        + " steps."
                    )
                    # Assign latest drift values back to the motors.
                    for (
                        i
                    ) in (
                        MotorControls
                    ):  # Run through all the motors selecting those that need tuning.
                        if i.MotorName == "azimuth":  # Azimuth motor.
                            if (
                                az_drift_steps is not None
                                and abs(az_drift_steps)
                                > params.minimum_drift_correction
                            ):  # Drift is large enough to do something.
                                DriftWindow.print(
                                    now_hour_minute_sec() + " Tuning " + i.MotorName
                                )
                                cam_log.log(
                                    now_hour_minute_sec() + " Tuning " + i.MotorName,
                                    terminal=False,
                                )
                                i.tune_position(az_drift_steps)
                            else:  # Drift is too small to worry about.
                                DriftWindow.print(
                                    now_hour_minute_sec()
                                    + " Not tuning "
                                    + i.MotorName
                                    + ", drift is too small."
                                )
                                cam_log.log(
                                    now_hour_minute_sec()
                                    + " Not tuning "
                                    + i.MotorName
                                    + ", drift is too small.",
                                    terminal=False,
                                )
                        elif i.MotorName == "altitude":  # Altitude motor.
                            if (
                                alt_drift_steps is not None
                                and abs(alt_drift_steps)
                                > params.minimum_drift_correction
                            ):  # Drift is large enough to do something.
                                DriftWindow.print(
                                    now_hour_minute_sec() + " Tuning " + i.MotorName
                                )
                                cam_log.log(
                                    now_hour_minute_sec() + " Tuning " + i.MotorName,
                                    terminal=False,
                                )
                                i.tune_position(alt_drift_steps)
                            else:  # Drift is too small to worry about.
                                DriftWindow.print(
                                    now_hour_minute_sec()
                                    + " Not tuning "
                                    + i.MotorName
                                    + ", drift is too small."
                                )
                                cam_log.log(
                                    now_hour_minute_sec()
                                    + " Not tuning "
                                    + i.MotorName
                                    + ", drift is too small.",
                                    terminal=False,
                                )
                    ReplyMessage = {
                        "TimeStamp": now_utc(),
                        "DriftX": DriftX,
                        "DriftY": DriftY,
                        "az_drift_steps": az_drift_steps,
                        "alt_drift_steps": alt_drift_steps,
                    }
                    outboundqueue.put(ReplyMessage)
                    camera_in_use.tx_count += 1
                    CameraRxWindow.print(
                        dictionary_to_string(ReplyMessage)
                    )  # Report communications from Camera to Main.
                    cam_log.log("camera_handler: End drift calculation", terminal=False)
            if (
                LoopTask == "image"
            ):  # Time to take an actual image. (If timelapse is active, only when it's due, otherwise every time.)
                if not camera_in_use.timelapse_due():  # Check timelapse mechanism.
                    cam_log.log(
                        "camera_handler: Image task. Timelapse is active but not due.",
                        terminal=False,
                    )
                else:  # Timelapse is inactive, or due.
                    cam_log.log(
                        "camera_handler: Image task. Timelapse is inactive or due.",
                        terminal=False,
                    )
                    # Now take the actual observation photo ('light' image).
                    obs_start = now_utc()
                    cam_log.log("camera_handler: Begin image capture", terminal=False)
                    if session.debug_mode:
                        print(
                            now_hour_minute_sec()
                            + " Begin "
                            + TextColor.green("image")
                            + " capture ("
                            + str(PhotoCount + 1)
                            + ") "
                            + str(camera_in_use.exposure_seconds)
                            + "s."
                        )
                    try:
                        result = camera_in_use.take_photo(batch_size, terminal=False)
                    except Exception as e:
                        cam_log.log(
                            "camera_handler: camera_in_use.take_photo failed.",
                            level="error",
                        )
                        cam_log.log(
                            "camera_handler: camera_in_use.take_photo raised:" + str(e),
                            level="error",
                        )
                        cam_log.report_exception(
                            e, comment="camera_handler: Call to TakePhoto()"
                        )
                        result = False
                    cam_log.log("camera_handler: End image capture", terminal=False)
                    obs_end = now_utc()
                    obs_time = obs_end - obs_start
                    obs_mult = obs_time.total_seconds() / camera_in_use.exposure_seconds
                    cam_log.log(
                        "camera_handler: Total capture time",
                        str(obs_time.total_seconds() * 1000) + "ms. (mult=",
                        obs_mult,
                        ")",
                        terminal=False,
                    )
                    if result:
                        PhotoCount += 1
                        camera_in_use.batch_count += 1
                        ReplyMessage = {
                            "TimeStamp": now_utc(),
                            "PhotoCount": PhotoCount,
                            "ObsStart": obs_start,
                            "ObsEnd": obs_end,
                            "ObsTime": obs_time,
                            "RunThread": True,
                        }
                        outboundqueue.put(
                            ReplyMessage
                        )  # Report communications from Camera to Main.
                        camera_in_use.tx_count += 1
                        CameraRxWindow.print(dictionary_to_string(ReplyMessage))
                        cam_log.log(
                            "Folder for image details:",
                            FolderHandler.get_path("session"),
                            terminal=False,
                        )
                        detailsfile = FolderHandler.prep_file(
                            "session", "imagedetails.txt"
                        )
                        tempra, tempdec = (
                            session.target.ra_dec_hours()
                        )  # Current RA and DEC of target.
                        tempaz, tempalt = (
                            session.target.az_alt_degrees()
                        )  # Current AZ and ALT of target.
                        if (
                            params.scan_for_meteors
                            and camera_in_use.image.ContainsMeteors()
                        ):  # Scan latest CvImage buffer for meteors or aircraft trails.
                            streaksdetected = True  # Found streaks in image.
                            CameraWindow.print(
                                now_hour_minute_sec()
                                + " Trail in image (Meteor/plane/satellite).",
                                fg=OSW_TEXT_POOR,
                                bg=OSW_TEXT_BG,
                            )  # Alert the operator that there's something spoiling the image.
                        else:
                            streaksdetected = False  # Didn't even check.
                        # Record a data file for the captured image (could be exif data?).
                        if not os.path.exists(
                            detailsfile
                        ):  # Create header line if it's a new file.
                            with open(detailsfile, "w") as f:
                                f.write(
                                    "Now"
                                    + "\t"
                                    + "PhotoCount"
                                    + "\t"
                                    + "Obs start"
                                    + "\t"
                                    + "Obs end"
                                    + "\t"
                                )
                                f.write("Obs time" + "\t" + "RA" + "\t" + "Dec" + "\t")
                                f.write(
                                    "Azimuth"
                                    + "\t"
                                    + "Altitude"
                                    + "\t"
                                    + "Streaks"
                                    + "\n"
                                )
                        with open(detailsfile, "a") as f:
                            f.write(
                                str(now_utc())
                                + "\t"
                                + str(PhotoCount)
                                + "\t"
                                + str(obs_start)
                                + "\t"
                                + str(obs_end)
                                + "\t"
                            )
                            f.write(
                                str(obs_time)
                                + "\t"
                                + str(tempra)
                                + "\t"
                                + str(tempdec)
                                + "\t"
                            )
                            f.write(
                                str(tempaz)
                                + "\t"
                                + str(tempalt)
                                + "\t"
                                + str(streaksdetected)
                                + "\n"
                            )
                    else:
                        cam_log.log(
                            "camera_handler: Image capture did not succeed. Stopping.",
                            level="error",
                        )
                        RunThread = False  # Something went wrong, quit!

            # Generate a labelled copy of the image periodically. For monitoring.
            if LoopTask == "preview":  # Time to consider making a preview markup.
                if (
                    PreviewTimer.due() and camera_in_use.image.ImageExists()
                ):  # Periodically prepare a new preview image. This is slow, so don't do it very frequently.
                    cam_log.log(
                        "camera_handler: Begin preview image markup", terminal=False
                    )
                    if session.debug_mode:
                        print(
                            now_hour_minute_sec()
                            + " Begin "
                            + TextColor.magenta("preview")
                            + " image generation."
                        )
                    # astrocamera.CaptureSet will have loaded the image into OpenCV compatible buffer. This is available to mark up with more information.
                    astrotimeend = datetime2_ts(camera_in_use.capture_end)
                    markup_preview(
                        drift_pixels_x=DriftTracker.dx,
                        drift_pixels_y=DriftTracker.dy,
                        astrotime=astrotimeend,
                    )  # Use last image buffer from camera_in_use.image to generate a marked up copy of the image on disc.
                    cam_log.log("camera_handler: End image markup", terminal=False)

            # Stop taking photos when the limit is reached. The main thread will also command the photos to stop, but it may be delayed.
            if PhotoCount >= params.batch_size:
                cam_log.log(
                    "camera_handler: Batch size reached.",
                    PhotoCount,
                    "images captured.",
                    terminal=False,
                )
                CameraWindow.print(
                    now_hour_minute_sec()
                    + " camera_handler: Batch size reached. "
                    + str(PhotoCount)
                    + " images captured."
                )
                ready_to_observe = False
                cam_log.log(
                    "camera_handler. BatchSize limit: ready_to_observe = False",
                    terminal=False,
                )
        else:  # ready_to_observe = False - No camera tasks performed.
            image_status_window.field_value(
                "CTASK", "WAITING", fg=TextColor.WHITE, bg=TextColor.RED
            )

        if RunThread and LoopTask == "pause":
            time.sleep(0.25)  # Small delay in each loop to relax things.

        # How much time has been spent on this task?
        LoopDuration = (now_utc() - LoopStartTimestamp).total_seconds()
        TimeAllocation[LoopTask] = LoopDuration + TimeAllocation.get(LoopTask, 0.0)
        LoopCounter += 1
        if LoopTask != "pause":  # Record CPU usage for the latest task.
            cam_log.log(
                "camera_handler: Loop completed",
                LoopTask,
                "in",
                round(LoopDuration, 2),
                "seconds",
                terminal=False,
            )
        if (
            AllocationTimer.due()
        ):  # Report how much time has been spent on each type of task.
            cam_log.log("camera_handler: Completed loop", LoopCounter, terminal=False)
            totaltime = 0
            for key, value in TimeAllocation.items():
                totaltime += value
            for key, value in TimeAllocation.items():
                if totaltime > 0:
                    timepc = int(100 * value / totaltime)  # Calculate % share.
                else:
                    timepc = 0
                cam_log.log(
                    "camera_handler: TimeAllocation:",
                    key,
                    value,
                    "seconds (",
                    timepc,
                    "%)",
                    terminal=False,
                )

    camera_in_use.current_task = None  # No task currently active.
    ReplyMessage = {"TimeStamp": now_utc(), "RunThread": False}
    outboundqueue.put(ReplyMessage)
    camera_in_use.tx_count += 1
    CameraRxWindow.print(
        dictionary_to_string(ReplyMessage)
    )  # Report communications from Camera to Main.
    CameraWindow.print(now_hour_minute_sec() + " camera_handler stopped.")
    cam_log.log("camera_handler: Finished.")


# Run the camera_handler as a separate thread.
# - This allows the camera to take lengthy exposures while the rest of the Observation routine continues.
CameraStatusQueue = (
    Queue()
)  # Use queue mechanism to send status information from capture thread to observation_run.
CameraControlQueue = (
    Queue()
)  # Use queue mechanism to CONTROL the capture thread from the observation_run.
CameraThread = None  # Pointer to camera thread.


def start_camera_thread():
    global CameraThread  # Must be global because it must persist after this function completes.
    if CameraThread is None or CameraThread.is_alive() != True:
        CameraThread = threading.Thread(
            target=camera_handler, args=(CameraStatusQueue, CameraControlQueue)
        )
        CameraThread.start()
        time.sleep(2)  # Wait a moment before returning.
    return True


def shutdown_camera():
    """Close the camerahandler thread."""
    global CameraThread
    global CameraStatusQueue
    global CameraControlQueue
    success = True  # Assume success unless we fail to shut down the handler correctly.
    print(
        "\n" + TextColor.yellow("Stopping camera_handler...")
    )  # force newline before printing text.
    if not camera_in_use.current_task in [None, "pause"]:
        print(
            'The camera is currently processing the "'
            + str(camera_in_use.current_task)
            + '" task.'
        )
    print(
        "Waiting for camera_handler to confirm it has completed (telescope may continue to move until this is finished) ..."
    )
    CameraControlQueue.put(
        {"Stop": True}
    )  # Post a shutdown message to the camera_handler
    session.camera_tx_count += 1  # We sent another message to the camera.
    # This waits for confirmation and warn to powercycle the RPi if the STOP command is unsuccessful after xxx seconds.
    # We'll give the camera_handler some time to shut down.
    # - Some tasks are quite slow, for example long exposures, or complex tracking operations.
    CameraShutdownTimer = Timer(max(200, camera_in_use.exposure_seconds * 4))
    while True:  # Loop until CameraShutdownTimer expires.
        if not CameraThread.is_alive():
            break  # Camera thread is completely stopped so OK to proceed.
        if not CameraStatusQueue.empty():
            StatusMessage = CameraStatusQueue.get()  # We have some feedback.
            session.camera_rx_count += 1  # We received another message from the camera.
        else:
            StatusMessage = {}  # Nothing from camera_handler.
        if "RunThread" in StatusMessage:  # RunThread status message received.
            if not StatusMessage["RunThread"]:  # camera_handler is shutting down.
                print("CameraThread stopping...")
                if CameraThread.is_alive():
                    CameraThread.join()  # Wait for it to complete.
                print(TextColor.yellow("CameraThread successfully stopped."))
                break  # OK to proceed.
        if CameraShutdownTimer.due():  # Timeout has expired, something's wrong.
            cam_log.log(
                "The camera_handler did not stop in a reasonable time.",
                terminal=False,
                level="error",
            )
            lines = [
                "Please POWER CYCLE the RPi to clear a potentially hung camera board.",
                "(Just restarting the program may not solve the problem.",
                " Just rebooting the RPi may not solve the problem either.)",
                "You may need to CTRL-C now to break out of the stuck camerahandler thread.",
                "The process stack has been recorded in the camera log file:",
                cam_log.filename,
            ]
            TextColor.text_box(lines, fg=TextColor.RED, bg=TextColor.BLACK)
            # Record the process stack to the log file just in case there's something useful there.
            lines = osCmd("ps -ef")
            cam_log.log("ps -ef\n", terminal=False)
            for line in lines:
                cam_log.log(line.strip() + "\n", terminal=False)
                success = False  # A terminal error occurred.
            break  # OK to proceed.
        else:
            temp = int(CameraShutdownTimer.remaining())  # How many seconds left?
            if temp < 60:
                print(
                    "Timeout in "
                    + TextColor.red(human_readable_seconds(temp))
                    + TextColor.cursorup()
                )
            elif temp < 120:
                print(
                    "Timeout in "
                    + TextColor.yellow(human_readable_seconds(temp))
                    + TextColor.cursorup()
                )
            else:
                print(
                    "Timeout in "
                    + TextColor.green(human_readable_seconds(temp))
                    + TextColor.cursorup()
                )
        time.sleep(0.5)  # Slight pause between loops.
    return success


start_camera_thread()  # Fire up the camera handler as a separate thread.


# Run the message handler as a separate thread.
# - This keeps traffic between RPi and Microcontroller running independently.
MessageThread = None  # Pointer to the message handler.


def start_message_thread():
    global MessageThread  # Must be global because it must persist after this function completes.
    session.terminate_mctl_handler = False  # Clear any existing shutdown flag.
    if MessageThread is None or MessageThread.is_alive() != True:
        MessageThread = threading.Thread(target=session.mctl_handler)
        MessageThread.start()
    return True


def shutdown_message():
    """Close the messagehandler thread."""
    global MessageThread
    success = True  # Assume success unless we fail to shut down the handler correctly.
    print(
        "\n" + TextColor.yellow("Stopping MessageHandler...")
    )  # force newline before printing text.
    print("Waiting for MessageHandler to confirm it has completed...")
    session.terminate_mctl_handler = (
        True  # Post a shutdown message to the MessageHandler
    )
    # This waits for confirmation and warn to powercycle the RPi if the STOP command is unsuccessful after xxx seconds.
    # We'll give the MessageHandler some time to shut down.
    # - Some tasks are quite slow, for example long exposures, or complex tracking operations.
    MessageShutdownTimer = Timer(200)
    while True:  # Loop until MessageShutdownTimer expires.
        if not MessageThread.is_alive():
            break  # Message thread is completely stopped so OK to proceed.
        if MessageShutdownTimer.due():  # Timeout has expired, something's wrong.
            main_log.log(
                "The MessageHandler did not stop in a reasonable time.",
                terminal=False,
                level="error",
            )
            success = False  # A terminal error occurred.
            break  # OK to proceed.
        else:
            temp = int(MessageShutdownTimer.remaining())  # How many seconds left?
            if temp < 60:
                print(
                    "Timeout in "
                    + TextColor.red(human_readable_seconds(temp))
                    + TextColor.cursorup()
                )
            elif temp < 120:
                print(
                    "Timeout in "
                    + TextColor.yellow(human_readable_seconds(temp))
                    + TextColor.cursorup()
                )
            else:
                print(
                    "Timeout in "
                    + TextColor.green(human_readable_seconds(temp))
                    + TextColor.cursorup()
                )
        time.sleep(0.5)  # Slight pause between loops.
    return success


start_message_thread()


def go_to_target(target_object):
    """Point camera at the target. But don't begin an observation.
    Observations can only start once the microcontroller has a trajectory available to follow.
    """
    print(TextColor.yellow("go_to_target: Pointing camera at target."))
    if (
        params.require_restart
    ):  # Warn that movements cannot be made until software is restarted.
        restart_required()
        return

    stop_motors()  # Clear anything that's still programmed for the motors.
    session.set_motor_control_mode(
        "direct"
    )  # We will directly control the movement of the microcontroller, no trajectory needs sending.

    # Prelocate the motors if case we need to handle gear backlash. It is good to go to a slightly lower azimuth position before starting the observation.
    if params.backlash_enabled:  # We're handling gear backlash.
        currentalt, currentaz = (
            last_reported_alt_az()
        )  # What is current position of the camera?
        az, alt = (
            session.target.az_alt_degrees()
        )  # What is the current position of the target?
        main_log.log(
            "go_to_target: Backlash prealignment: From ("
            + az_alt_text(currentaz, currentalt)
            + ") to ("
            + az_alt_text(az, alt)
            + ")"
        )
        # Prealignment for backlash effects.
        for i in MotorControls:  # Check every motor.
            if i.BacklashAngle != 0:  # Does the motor have backlash set?
                targetangle = i.CurrentAngle
                if (
                    i.MotorName == "azimuth"
                ):  # Compare target azimuth with current azimuth
                    if (
                        az < currentaz
                    ):  # We need to move to a lower azimuth position, so move even further to allow the mechanism to take-up any backlash when the gears change position.
                        targetangle = (
                            az - i.BacklashAngle
                        )  # Position the motor PAST the target so that the observation has to recover the situation, this will take up the slack in the gears.
                elif i.MotorName == "altitude":
                    if (
                        alt < currentalt
                    ):  # We need to move to a lower altitude position, so move even further to allow the mechanism to take-up any backlash when the gears change position.
                        targetangle = (
                            alt - i.BacklashAngle
                        )  # Position the motor PAST the target so that the observation has to recover the situation, this will take up the slack in the gears.
                if not i.CompareAngles(i.CurrentAngle, targetangle):
                    main_log.log(
                        "go_to_target: Pre alignment of "
                        + i.MotorName
                        + " motor to allow for gear backlash. Moving to "
                        + deg_3dp(targetangle, DEGREE_SYMBOL)
                    )
                    i.MonitorMove = True  # Display movement progress on the terminal.
                    temp = i.GoToAngle(
                        targetangle
                    )  # Move the motor PAST the target position, so that it will have to reverse to get on target. This will take up the slack in the gears.
                    i.MonitorMove = (
                        False  # Do not display movement progress on the terminal.
                    )
                    if not temp:  # Move failed.
                        main_log.log(
                            "go_to_target: GoToAngle() call failed. Pre alignment of "
                            + i.MotorName
                            + " failed.",
                            level="error",
                        )
                        return False  # Failed!
            else:
                main_log.log(
                    "go_to_target: No backlash adjustment required for " + i.MotorName
                )

    # GoTo the target.
    az, alt = (
        session.target.az_alt_degrees()
    )  # What is the current position of the target?
    currentalt, currentaz = (
        last_reported_alt_az()
    )  # What is the current position of the camera?
    main_log.log(
        "go_to_target: Alignment: From "
        + az_alt_text(currentaz, currentalt)
        + " to "
        + az_alt_text(az, alt)
    )
    for i in MotorControls:  # Check every motor.
        targetangle = i.CurrentAngle  # Default is the current position.
        if i.MotorName == "azimuth":  # Compare target azimuth with current azimuth
            targetangle = az  # Position the motor ON the target.
        elif i.MotorName == "altitude":
            targetangle = alt  # Position the motor ON the target.
        if not i.CompareAngles(
            i.CurrentAngle, targetangle
        ):  # There's a big enough position difference that it's worth moving the camera.
            main_log.log(
                "go_to_target: Target",
                i.MotorName,
                "from",
                deg_3dp(i.CurrentAngle, DEGREE_SYMBOL),
                "to",
                deg_3dp(targetangle, DEGREE_SYMBOL),
            )
            i.MonitorMove = True  # Display movement progress on the terminal.
            temp = i.GoToAngle(targetangle)  # Move the motor now.
            i.MonitorMove = False  # Do not display movement progress on the terminal.
            if not temp:  # Move failed.
                main_log.log(
                    "go_to_target: GoToAngle() call failed. Alignment of "
                    + i.MotorName
                    + " failed (From angle",
                    deg_3dp(i.CurrentAngle, DEGREE_SYMBOL),
                    "to",
                    deg_3dp(targetangle, DEGREE_SYMBOL),
                    ").",
                    level="error",
                )
                main_log.log(
                    "go_to_target: GoToAngle() call failed. Alignment of "
                    + i.MotorName
                    + " failed (From position",
                    i.AngleToStep(i.CurrentAngle),
                    "to",
                    i.AngleToStep(targetangle),
                    ").",
                    level="error",
                )
                return False  # Failed!
        else:
            main_log.log("go_to_target: Motor " + i.MotorName + " already on target.")
    stop_motors()  # Reset motor condition to prevent further movement.
    print(
        "NOTE: The camera is now positioned, but it is not tracking or photographing the target yet."
    )
    print("      (Pi-lomar must calculate a trajectory before photography can start.)")
    print(TextColor.yellow("Done."))
    return True


def stop_motors():
    """Send a fresh STOP command to the motorcontroller.
    This is called automatically at the end of an observation,
    it can also be sent manually from the Motor Controls menu."""
    Mctl.WriteFlush(
        send=False
    )  # Scrap all outstanding messages to the microcontroller.
    Mctl.write("stop")  # Tell the motors to immediately stop.
    Mctl.write("clear trajectory")  # Remove any existing trajectory from the motors.
    session.set_motor_control_mode("idle")  # We nolonger need to maintain a trajectory.


def restart_microcontroller():  # For menu
    global MctlThread
    global Mctl
    if MctlThread.is_alive() != True:
        main_log.log("ResetMctl: MctlThread is missing. Restarting...")
        Mctl = initiate_mctl()  # Restart the microcontroller thread.
        MctlThread = threading.Thread(
            target=start_mctl_comms, args=(), daemon=True
        )  # Run microcontroller communication independently, quit automatically.
        MctlThread.start()
    Mctl.Reset(planned=True)  # Restart the microcontroller manually.


def motor_status_off():
    """Turn motor status messages off.
    Feature to support 'fast' configuration of a complete trajectory for a motor."""
    main_log.log("MotorStatusOff: Turn off motor status messages.", terminal=False)
    print("Microcontroller will not send motor status messages back to the RPi.")
    Mctl.write(
        "sendstatus " + clean_datetime_string(str(now_utc())) + " n "
    )  # Turn off motor status responses.


def motor_status_on():
    """Turn motor status messages on.
    Feature to support 'fast' configuration of a complete trajectory for a motor."""
    main_log.log("MotorStatusOff: Turn on motor status messages.", terminal=False)
    print("Microcontroller will send motor status messages back to the RPi.")
    Mctl.write(
        "sendstatus " + clean_datetime_string(str(now_utc())) + " y "
    )  # Turn on motor status responses.


def microcontroller_leds_off():  # For menu
    params.mctl_led_status = False
    set_global_led_status()
    lines = [
        "Microcontroller LEDs are now off.",
        " ",
        "The RGB LED will remain off throughout operation.",
        " ",
        "This reduces the stray light within the",
        "observatory dome.",
    ]
    TextColor.text_box(lines, fg=TextColor.YELLOW, bg=TextColor.BLACK)


def microcontroller_leds_on():  # For menu
    params.mctl_led_status = True
    set_global_led_status()
    lines = [
        "Microcontroller LEDs are now on.",
        " ",
        "The RGB LED will be active throughout operation.",
        " ",
        "This increases the stray light within the",
        "observatory dome.",
    ]
    TextColor.text_box(lines, fg=TextColor.YELLOW, bg=TextColor.BLACK)


def tracking_on():
    """Turn drift tracking on."""
    main_log.log("Turning drift tracking on.", terminal=True)
    params.use_tracking = True


def tracking_off():
    """Turn drift tracking off."""
    main_log.log("Turning drift tracking off.", terminal=True)
    params.use_tracking = False


def observation_submenu(drifttracker=None):
    """Submenu of options that can be used DURING an observation."""
    TextColor.clearscreen()  # Clear the screen and force window refresh.

    if drifttracker is None:
        temp = None  # There is no drifttracker object to call.
    else:
        temp = drifttracker.Reset  # There is a drifttracker object to call.
    SubMenuOptions = {
        "program_status": {"label": "Status", "call": program_status, "break": True},
        "TuneAzimuth": {"label": "Tune azimuth", "call": tune_position_azimuth},
        "TuneAltitude": {
            "label": "Tune altitude",
            "call": tune_position_altitude,
            "break": True,
        },
        "MctlLedsOff": {
            "label": "Microcontroller LEDS off",
            "call": microcontroller_leds_off,
        },
        "MctlLedsOn": {
            "label": "Microcontroller LEDS on",
            "call": microcontroller_leds_on,
        },
        "restart_microcontroller": {
            "label": "Restart microcontroller",
            "call": restart_microcontroller,
            "break": True,
        },
        "tracking_on": {"label": "Tracking on", "call": tracking_on},
        "tracking_off": {"label": "Tracking off", "call": tracking_off},
        "ResetDriftTracking": {"label": "Reset drift tracking", "call": temp},
    }
    SubMenu = ProcedureMenu(
        SubMenuOptions,
        "Pilomar observation submenu",
        titlefg=MENU_TITLE_FG,
        titlebg=MENU_TITLE_BG,
    )

    # Run sub menu.
    SubMenu.prompt()


def update_storage_status():
    """Checks storage available.
    Updates displays.
    Returns TRUE if all OK.
    Returns FALSE if storage critically low."""
    # IF USB storage is being used, then check that capacity, otherwise check the SD card capacity.
    result = True  # All OK.
    fb = ImageStorageMonitor.FreeBytes()  # How much storage space do we have?
    sfb = human_readable_bytes(fb)  # Make it more readable.
    if fb > (1024**3):
        observation_status_window.field_value(
            "STORAGE", sfb, fg=OSW_TEXT_GOOD
        )  # Lots of space available.
    elif fb > (400 * (1024**2)):
        observation_status_window.field_value(
            "STORAGE", sfb, fg=OSW_TEXT_POOR
        )  # Space running low.
    elif fb > (150 * (1024**2)):
        observation_status_window.field_value(
            "STORAGE", sfb, fg=OSW_TEXT_BAD
        )  # Space running low.
    else:  # Dangerously low on space.
        observation_status_window.field_value("STORAGE", sfb, fg=OSW_TEXT_BAD)  # Red
        result = False  # Critically low on memory. Abort!
        main_log.log(
            "update_storage_status: Low storage space ("
            + str(fb)
            + " bytes) terminating the observation.",
            level="error",
        )
    # main_log.log("Storage available=" + HRBytes(fb),terminal=False)
    return result


def update_camera_status():
    if params.camera_enabled:  # Camera is enabled, report the selected exposure time.
        observation_status_window.field_value(
            "CEN", params.camera_enabled, fg=OSW_TEXT_GOOD
        )  # Green
        observation_status_window.field_value(
            "EXP", str(camera_in_use.exposure_seconds) + "s.", fg=OSW_TEXT_GOOD
        )  # Exposure duration.
    else:  # Camera is disabled, warn about this.
        observation_status_window.field_value(
            "CEN", params.camera_enabled, fg=OSW_TEXT_POOR
        )  # Red
        observation_status_window.field_value(
            "EXP", str(camera_in_use.exposure_seconds) + "s.", fg=OSW_TEXT_POOR
        )  # Red - Blank out Exposure duration.
    if (
        camera_in_use.timelapse_seconds is not None
        and camera_in_use.timelapse_seconds > 0.0
    ):
        observation_status_window.field_value(
            "TLAPSE",
            human_readable_seconds(camera_in_use.timelapse_timer.remaining()),
            fg=OSW_TEXT_GOOD,
        )  # Exposure duration.
    else:
        observation_status_window.field_value(
            "TLAPSE", "Off", fg=OSW_TEXT_GOOD
        )  # Exposure duration.
    if (
        camera_in_use.fast_image_capture
    ):  # Warn that shortcuts are being taken to get photos as quickly as possible. (Means delaying some processing until after the observation).
        observation_status_window.field_value(
            "FAST", "Fast", fg=OSW_TEXT_POOR
        )  # Fast Image Capture is active
    else:
        observation_status_window.field_value(
            "FAST", "Full", fg=OSW_TEXT_GOOD
        )  # Fast Image Capture is not active
    if sensor_in_use.on_chip_cleanup:
        observation_status_window.field_value(
            "OCC", "On", fg=OSW_TEXT_POOR
        )  # Red # Only applies to raspistill instances.
    else:
        observation_status_window.field_value(
            "OCC", "Off", fg=OSW_TEXT_GOOD
        )  # Green # Only applies to raspistill instances.
    return True


def update_camera_capture_status():
    if (
        camera_in_use.capture_start is not None
    ):  # Monitor the progress of the current photograph.
        if (
            camera_in_use.capture_end is None
            or camera_in_use.capture_end <= camera_in_use.capture_start
        ):
            # Latest image capture has started but not finished yet.
            image_status_window.field_value("CAMERASTATE", "Started", fg=OSW_TEXT_GOOD)
            image_status_window.field_value(
                "STATETIMES", str(camera_in_use.capture_start).split(".")[0]
            )
            image_age = (now_utc() - camera_in_use.capture_start).total_seconds()
            image_status_window.field_value(
                "STATEAGE", human_readable_seconds(image_age)
            )
        else:  # Last image capture is complete. Waiting for next one to start.
            image_status_window.field_value("CAMERASTATE", "Ended", fg=OSW_TEXT_GOOD)
            image_status_window.field_value(
                "STATETIMES", str(camera_in_use.capture_end).split(".")[0]
            )
            image_age = (now_utc() - camera_in_use.capture_end).total_seconds()
            image_status_window.field_value(
                "STATEAGE", human_readable_seconds(image_age)
            )
    else:  # No capture even started yet.
        image_status_window.field_value("CAMERASTATE", "Pending", fg=OSW_TEXT_POOR)
        image_status_window.field_value("STATETIMES", "")
        image_status_window.field_value("STATEAGE", "")
    return True


def generate_preview_movie(folder=None, filename=None):
    main_log.log("Generating animation of observation previews...", terminal=False)
    print(
        TextColor.yellow(
            "Generating animation of observation previews (if available)..."
        )
    )
    print("May take some time...")
    if folder is None:  # No folder named, default to current one.
        folder = FolderHandler.get_path("preview")
    sourcefilepattern = folder + "/preview_*.jpg"
    avifilename = FolderHandler.prep_file(
        "preview", "preview_" + clean_datetime_string(str(now_utc())) + ".mp4"
    )
    if filename is not None:  # Override target filename.
        avifilename = filename
    # *Q* GLOB facility may disappear from later versions of ffmpeg, this will need revising when that happens.
    cmd = (
        "ffmpeg -y -framerate 10 -pattern_type glob -i '"
        + sourcefilepattern
        + "' -vf scale='iw/2:ih/2' "
        + avifilename
    )
    osCmd(cmd)
    print(TextColor.yellow("Generated"), avifilename)
    main_log.log(
        "GeneratePreviewAvi: Completed animation of observation previews.",
        terminal=False,
    )
    return True


def generate_light_movie(folder=None, filename=None):
    main_log.log("Generating animation of observation light images...", terminal=False)
    print(TextColor.yellow("Generating animation of observation light images..."))
    print("May take some time...")
    if folder is None:  # No folder named, default to current one.
        folder = FolderHandler.get_path("light")
    sourcefilepattern = folder + "/light_*.jpg"
    avifilename = FolderHandler.prep_file(
        "light", "light_" + clean_datetime_string(str(now_utc())) + ".mp4"
    )
    if filename is not None:  # Override target filename.
        avifilename = filename
    # *Q* GLOB facility may disappear from later versions of ffmpeg, this will need revising when that happens.
    cmd = (
        "ffmpeg -y -framerate 10 -pattern_type glob -i '"
        + sourcefilepattern
        + "' -vf scale='iw/2:ih/2' "
        + avifilename
    )
    osCmd(cmd)
    print(TextColor.yellow("Generated"), avifilename)
    main_log.log(
        "GenerateLightAvi: Completed animation of observation light images.",
        terminal=False,
    )
    return True


def report_observation_errors():
    # If any errors were recorded during the session, summarise them here.
    # The display is very active during an observation, so it is useful to summarise errors clearly when the observation is complete.
    if len(main_log.error_list) > 0:  # Error messages were reported during the run.
        print(
            TextColor.yellow(
                "NOTE: main_log recorded the following errors DURING the observation :-"
            )
        )
        for ln in main_log.error_list:
            print("\t" + TextColor.orange(ln))
        main_log.error_list = []  # Empty the list. We've reported it now.
    if len(cam_log.error_list) > 0:  # Error messages were reported during the run.
        print(
            TextColor.yellow(
                "NOTE: cam_log recorded the following errors DURING the observation :-"
            )
        )
        for ln in cam_log.error_list:
            print("\t" + TextColor.orange(ln))
        cam_log.error_list = []  # Empty the list. We've reported it now.
    return True


def get_position_ages():
    """Return the age of the position measurements of each motor.
    Returns values in rounded whole seconds."""
    AzAge = AltAge = 0
    for i in MotorControls:
        if i.MotorName == "azimuth":
            AzAge = i.PositionAge()
        else:
            AltAge = i.PositionAge()
    return AzAge, AltAge


def incomplete_observation_check():
    """If the previous observation didn't complete,
    warn that camera positions may be incorrect
    and ask for permission to continue."""
    if os.path.exists(ObservationRunningFile):
        lines = [
            "The previous observation run did not complete properly.",
            "This may mean that the camera positions are out of date",
            "you may need to reset the camera altitude and azimuth.",
        ]
        TextColor.text_box(lines, fg=TextColor.WHITE, bg=TextColor.ORANGERED1)
        result = ask_yes_no("Continue with this observation? [y/N]", default=False)
    else:
        result = True
    return result


def flag_observation_start():
    """Create a flag to show that observation_run has started.
    This warns a following instance of the program in case this one fails
    and leaves a mess."""
    main_log.log("FlagObservationStart(): Begin", terminal=False)
    with open(ObservationRunningFile, "w") as f:
        f.write("observation_run started " + str(now_utc()) + " UTC\n")
    main_log.log("FlagObservationStart(): End", terminal=False)
    return True


def flag_observation_end():
    """Remove the flag for a running observation_run because it's now completed."""
    main_log.log("flag_observation_end(): Begin", terminal=False)
    session.set_motor_control_mode(
        "idle"
    )  # This will suppress further trajectory info being sent.
    # Session.end_observation() # Make sure that the observation is stopped! Even if the procedure crashed. This stops trajectories.
    # Send trajectory clear commands to the microcontroller.
    stop_motors()  # Tell the microcontroller to stop and drop any existing trajectory immediately.
    if os.path.exists(ObservationRunningFile):
        os.remove(ObservationRunningFile)
    main_log.log("flag_observation_end(): End", terminal=False)
    return True


def observation_run():
    """Perform an observation run. Take a set of photographs and keep the camera pointing at the target.
    This is the core of the program. This is the main loop that tracks a target and captures photos.
    It loops until
      the set number of photos are reached,
        or
      the target moves out of sight,
        or
      an irrecoverable situation is detected.
    It can be terminated by pressing 'x' on the keyboard.
    It could also be terminated by an input signal from a GPIO pin (ie a button) if enabled.
    This routine maintains its own display showing the status of the tracking and observation.
    DEBUGGING NOTE: Lots happen here, including co-ordination between multiple processing threads.
            The display refreshes constantly, so it is easy to lose error messages.
            If you want to capture error messages you can run the routine in debug mode.
            In debug mode the main display is disabled and ONLY error messages will appear on the terminal.
            Activate debug mode in the startup parameters json file.
              'Parameters.DebugMode' : true,
            It can also be done from the Miscellaneous Tools menu, or by pressing 'd' key during an observation.

    There are 4 threads operating at this point.
    - The main processing thread is this observation_run routine which has overall coordination and maintains the display/dashboard.
    - The Camera thread controls the camera activities.
    - The Mctl thread handles UART communication between the RPi and Microcontroller.
    - The Message thread deals with the actual messages received from the microcontroller and their responses.

    """
    main_log.log("observation_run: Beginning observation.", terminal=False)

    RunObservation = True  # We are OK to run the observation loop.
    observationresult = True  # Was observation completed successfully?

    # Mark that an observation has started. If the program fails during an observation we can warn that
    # camera position etc may be misaligned when it restarts.
    if not incomplete_observation_check():
        # There is an existing observation already running. Check this should proceed and warn that positions may be wrong.
        # The user chose to abandon this run.
        return False
    flag_observation_start()  # Mark that an observation run has started. Used this to warn if recovering from a failed run.

    # Don't start an observation if the target is not yet in range.
    if (
        not session.target.visible()
    ):  # The target isn't yet within the visibility range of the telescope.
        main_log.log(
            "observation_run: The target is not within the visibility range of the telescope.",
            terminal=False,
        )
        TextColor.text_box(
            ["The target is not visible to the telescope at the moment."],
            fg=TextColor.RED,
            bg=TextColor.BLACK,
        )
        observationresult = False
        RunObservation = False  # Not OK to run the observation loop.
        return observationresult  # Quit the run.

    # Setup campaign information.
    document_session()  # Create text file listing the details of this session.
    DriftTracker.Reset()  # Clear the drift tracking object for this new observation target.

    if params.use_tracking:
        DriftWindow.print(now_hour_minute_sec() + " Drift tracking is active.")
    else:
        DriftWindow.print(now_hour_minute_sec() + " Drift tracking is inactive.")
    main_log.error_list = (
        []
    )  # Clear out any old error summaries. We only want to report NEW instances.
    cam_log.error_list = (
        []
    )  # Clear out any old error summaries. We only want to report NEW instances.
    ready_to_observe = False  # We are not on-target yet.
    main_log.log("observation_run.initial: ready_to_observe = False", terminal=False)
    temp = (
        get_terminal_size()
    )  # Note the size of the window. If it changes, we'll clear the screen.
    TerminalCols = temp[0]  # Current screen columns.
    TerminalRows = temp[1]  # Current screen rows.
    temp = (
        ColorDisplay.global_window_limits()
    )  # How much screen space do all the windows required?
    if TerminalCols < temp[0] or TerminalRows < temp[1]:
        main_log.log(
            "observation_run: Terminal",
            TerminalCols,
            "*",
            TerminalRows,
            ", Windows",
            temp[0],
            "*",
            temp[1],
            terminal=False,
        )
        main_log.log(
            "observation_run: The terminal window is not big enough to display ALL available data. Stretch if possible.",
            terminal=False,
        )
    obsstart = now_utc()  # Note the start of the observation run.
    PhotoCount = 0  # How many photos have been taken? We can exit the loop when the limit is reached. If Camera is disabled, it will loop forever.
    SlowLoopCounter = 0  # Count how often we have slow processing loops, it can be the sign of storage problems.

    # Reset PhotoCount in the camera and wait for acknowledgement.
    # PhotoCount is maintained by the CameraThread, so we must communicate with it.
    start_camera_thread()  # Fire up the camera thread if it's not running.
    time.sleep(
        0.5
    )  # Pause briefly before sending the control message to the camera handler.
    ControlMessage = {
        "TimeStamp": now_utc(),
        "PhotoCount": 0,
    }  # *Q* Can be common attribute now rather than message queues.
    CameraControlQueue.put(ControlMessage)  # Tell the camera to reset the photo count.
    session.camera_tx_count += 1  # We sent another message to the camera.
    ControlMessage = {"Reset": True}  # Tell the camera to reset buffers.
    CameraControlQueue.put(ControlMessage)  # Tell the camera to reset the photo count.
    session.camera_tx_count += 1  # We sent another message to the camera.
    # Wait for acknowledgement
    main_log.log("observation_run: Resetting camera PhotoCount.", terminal=False)
    ack = False  # No acknowledgement from the camera yet.
    AckTimer = Timer(
        600
    )  # Set a timer for an acknowledgement. Camera is considered 'hung' or 'dead' after that.
    main_log.log(
        "observation_run: Reset camera photo count and wait for acknowledgement.",
        terminal=False,
    )
    while not ack:  # Loop until we receive acknowledgement.
        # Quit if the CameraThread has failed.
        if (
            not CameraThread.is_alive()
        ):  # If the camera thread is dead, then quit immediately.
            main_log.log("observation_run: CameraThread is not running!", level="error")
            print(
                "If the camera thread is dead you can try to restart it from the Camera Tools menu."
            )
            RunObservation = False  # We cannot perform the observation. We will have to return to the menu.
            observationresult = False  # Don't continue.
            return observationresult  # Return to the menu.
        if (
            not CameraStatusQueue.empty()
        ):  # The CameraThread has sent a message that needs processing.
            StatusMessage = (
                CameraStatusQueue.get()
            )  # Retrieve the first available message.
            session.camera_rx_count += 1  # We received another message.
            if (
                "PhotoCountReset" in StatusMessage
            ):  # Is it acknowledging that the PhotoCount has been reset?
                ack = True  # Acknowledged, OK to proceed.
                main_log.log("Reset camera PhotoCount acknowledged.", terminal=False)
            else:  # The message is for some other purpose, we ignore it for now.
                main_log.log(
                    "Reset camera PhotoCount ignored " + str(StatusMessage),
                    terminal=False,
                )
        # If the camera has not acknowledged in a reasonable time, assume something is wrong and quit.
        if AckTimer.due():  # Timeout on the acknowledgement.
            main_log.log(
                "Reset camera Photocount. Acknowledgement timed out. Camera considered unresponsive.",
                level="error",
            )
            lines = [
                "Camera is considered unresponsive.",
                "The camera thread is still alive.",
                "- The camera subsystem may have hung,",
                "  in which case you should power cycle the RPi to clear the problem.",
                "- The camera may have taken too long to initialize,",
                "  in which case please try again.",
                "- There may be an error from the camera handler,",
                "  in which case check the camera log file or re-run in debug mode.",
            ]
            TextColor.text_box(lines, fg=TextColor.RED, bg=TextColor.BLACK)
            observationresult = False  # Don't continue.
            RunObservation = False  # We cannot perform the observation. We will have to return to the menu.
            return observationresult  # Return to the menu.
        if not ack:
            time.sleep(0.5)  # Pause half a second before checking again.
            print(
                "Waiting for camera acknowledgement.",
                int(AckTimer.remaining()),
                "seconds left.",
                TextColor.cursorup(),
            )
    print(TextColor.clearforward())

    # Check that the UART communication with the motor microcontroller is alive.
    if not MctlThread.is_alive():  # UART comms thread has failed.
        main_log.log(
            "observation_run (startup): MctlThread is not running!", level="error"
        )
        observationresult = False  # Don't continue.
        RunObservation = False  # We cannot perform the observation. We will have to return to the menu.
        return observationresult  # Return to the menu.
    # Check that the message handler between the RPi and microcontroller is alive.
    if not MessageThread.is_alive():  # Message handler thread has failed.
        main_log.log(
            "observation_run (startup): MessageThread is not running!", level="error"
        )
        observationresult = False  # Don't continue.
        RunObservation = False  # We cannot perform the observation. We will have to return to the menu.
        return observationresult  # Return to the menu.

    # Set parameters used during the observation run.
    CameraAlt = None  # The current altitude of the camera (reported by the motor microcontroller). Unknown at first.
    CameraAz = None  # The current azimuth of the camera (reported by the motor microcontroller). Unknown at first.
    PrevAlt = None  # The previous altitude of the telescope. Uninitialised until the main loop has started.
    prev_ready_to_observe = False  # We are not ready to observe until the whole telescope is synchronised and on target.
    ObservationStartUTC = None  # The UTC timestamp when the image capture begins.
    LoopTimeList = []  # Show how quickly recent loops have completed.
    cumulativelooptime = 0  # Cumulative total of all the loop times.
    cumulativeloopcount = 0  # Count of all the loops executed.
    main_log.log("observation_run: Initializing motorcontroller...", terminal=False)
    main_log.log(
        "observation_run: Stopping any previous motor instructions.", terminal=False
    )
    if (
        params.observation_resets_mctl
    ):  # Do we just force a full reset of the microcontroller to clean it up each time an observation starts?
        main_log.log(
            "observation_run: Resetting microcontroller at start of observation (ObservationResetsMctl parameter)",
            terminal=False,
        )
        Mctl.Reset(
            planned=True
        )  # Perform a planned reset of the microcontroller to clear it ready for a new observation.
        time.sleep(2)  # Pause briefly before setting the microcontroller clock.
        Mctl.SetClock()  # Set the clock on the microcontroller.
    else:
        stop_motors()  # Clear any existing plan that the motors may have.
        Mctl.ReadFlush()  # Flush any unprocessed messages. If a large backlog exists it can delay the initial move and make it look like a motor/comms problem.
    if Mctl.BytesReceived < 10:
        time.sleep(3)  # Wait for microcontroller UART communication to get running.
    if Mctl.BytesReceived < 10:  # Not much sign of activity from the microcontroller!
        main_log.log(
            "observation_run: Microcontroller UART link does not appear to be communicating. Please check.",
            level="error",
            terminal=True,
        )
        print("1) Is microcontroller installed?")
        print("2) Is microcontroller connected via UART pins / GPIO header?")
        print("3) Is microcontroller software installed?")
        print(
            "4) Microcontroller connection via USB alone will not support UART communication."
        )
        observationresult = False  # Don't continue.
        RunObservation = False  # We cannot perform the observation. We will have to return to the menu.
        return observationresult  # Return to the menu.
    if params.initial_go_to:  # Does an observation run start with a GOTO?
        main_log.log(
            "observation_run: Performing initial GOTO performed before creating trajectory.",
            terminal=False,
        )
        az, alt = (
            session.target.az_alt_degrees()
        )  # Calculations for target from observer's location.
        temp = go_to_target(
            session.target
        )  # Go directly to the target before starting the trajectory mechanism.
        if not temp:
            main_log.log("observation_run: Initial GOTO failed.", level="error")
            temp = ask_yes_no("Do you want to continue anyway? [y/N]", False)
            if not temp:
                return  # Quit immediately.
    else:  # Let the telescope perform initial GOTO once the trajectory is available. Risks comms bottleneck.
        main_log.log(
            "observation_run: No initial GOTO performed before creating trajectory.",
            terminal=False,
        )
    if (
        session.target.is_fixed_point()
    ):  # Fixed point observations don't move the telescope, so no trajectory is needed.
        session.set_motor_control_mode(
            "direct"
        )  # We assume direct control of the telescope.
    else:
        session.set_motor_control_mode(
            "trajectory"
        )  # We need to pass trajectory information to the motorcontroller so that it can track the object itself.
    line = (
        "Start observation " + str(now_utc()).split(".")[0] + " UTC -----------------"
    )[
        :70
    ]  # Mark the start of a new observation in some of the status windows.
    MctlTxWindow.print(line)
    MctlRxWindow.print(line)
    CameraWindow.print(line)
    error_window.print(line)
    if not params.camera_enabled:
        CameraWindow.print("NOTE: Camera is disabled.")
    if camera_in_use.timelapse_timer is None:
        main_log.log("Timelapse inactive.", terminal=False)
    else:
        main_log.log(
            "Timelapse active (", camera_in_use.timelapse_seconds, "s)", terminal=True
        )
    if (
        camera_in_use.fast_image_capture
    ):  # We're taking shortcuts to get as many images as possible in a short time span.
        print(
            TextColor.yellow(
                "NOTE: FastImageCapture is active. Images will be captured as quickly as possible."
            )
        )
        print(
            TextColor.yellow(
                "Low priority image processing will not be done during the observation."
            )
        )
        print(
            TextColor.yellow(
                "If you want to extract raw (.dng) data you must do it separately after the observation."
            )
        )
    SessionWindow.clear(immediate=False)  # Clear old messages from the session window.
    DebugTimer = Timer(120)  # In debug mode, update summary status every 2 minutes.
    _ = ImageStorageMonitor.FreeBytes(force=True)  # Force disc space refresh.
    # After this point all messages to the terminal should respect WINDOW and DEBUG MODE selections, otherwise they get overwritten/corrupted.
    if session.debug_mode:
        # Do not clear the screen in debug mode. We don't want to lose error messages.
        print(
            TextColor.orange(
                "In DEBUG MODE. The dashboard display is suppressed so that any errors are more clear."
            )
        )  # In debug mode, nothing is displayed except error messages.
        print(
            TextColor.yellow(
                "In DEBUG MODE. Press 'x' to quit, 'd' toggle debug, 'm' submenu, 'r' refresh."
            )
        )  # In debug mode, nothing is displayed except error messages.
    else:
        # Not in debug mode. Specific window layout will be used to show information.
        # Any output from error messages or regular print() commands will be lost as the display frequently refreshes.
        TextColor.clearscreen()  # Clear the screen and force window refresh.
    if session.debug_mode:
        main_log.log("observation_run: (DebugMode) Starting main loop...")
    # keyboardcount = 0 # Count the iterations between keyboard scans.
    ColorDisplay.global_force_redraw()  # Force all window buffers to fully redraw initially.
    while RunObservation:  # Main loop of the observation.

        # main_log.log("observation_run: Loop starts",terminal=False)
        # Check for keyboard commands...
        # main_log.log("observation_run: Check for keyboard input...",terminal=False)
        # *Q* The following keyboard scan uses the curses library. It can cause the terminal display to blink sometimes. Not cured yet.
        if KeyboardTimer.due():  # It's time to scan the keyboard.
            keypress = Keyboard.check().lower()  # Non-blocking scan for keyboard input.
        else:
            keypress = ""  # Don't check keyboard this time round.
        if keypress != "":  # Some keyboard input detected.
            if ord(keypress) == 410:
                pass  # Ignore the 410 character, it is associated with screen resizing.
        if keypress == "x" or keypress == chr(27):  # Break with 'x' or 'esc' key.
            main_log.log(
                "Keyboard interrupt: Terminating.", level="warning", terminal=False
            )
            error_window.print(
                now_hour_minute_sec() + " Keyboard interrupt. Terminating observation."
            )
            observationresult = False  # Don't continue.
            RunObservation = (
                False  # This will quit the loop and shut down the motors and camera.
            )
        elif keypress == "m":  # Submenu.
            main_log.log("Keyboard interrupt: Submenu selected.", terminal=False)
            observation_submenu(
                drifttracker=DriftTracker
            )  # Pass the drifttracker object because the submenu can access its methods.
            TextColor.clearscreen()  # Clear screen afterwards.
        elif (
            keypress == "+"
        ):  # Exposure compensation. Increase exposure. (200% exposure time).
            main_log.log("Keyboard interrupt: Increase exposure time.", terminal=False)
            adjust_exposure_time(2.0)
        elif (
            keypress == "-"
        ):  # Exposure compensation. Decrease exposure. (50% exposure time).
            main_log.log("Keyboard interrupt: Decrease exposure time.", terminal=False)
            adjust_exposure_time(0.5)
        elif keypress == "t":  # Turn drift tracking on/off.
            main_log.log(
                "Keyboard interrupt: Toggle DriftTracking status.", terminal=False
            )
            params.use_tracking = not params.use_tracking  # Toggle the value.
            if params.use_tracking:
                DriftWindow.print(now_hour_minute_sec() + " Drift tracking ON.")
                main_log.log("Keyboard interrupt: Drift tracking ON.", terminal=False)
            else:
                DriftWindow.print(now_hour_minute_sec() + " Drift tracking OFF.")
                main_log.log("Keyboard interrupt: Drift tracking OFF.", terminal=False)
        elif keypress == "p":  # Trigger immediate PREVIEW image.
            main_log.log(
                "Keyboard interrupt: User requested immediate PREVIEW image.",
                terminal=False,
            )
            PreviewTimer.trigger()  # Mark the 'preview' timer as Due already.
            DevWindow.print(now_hour_minute_sec() + " Immediate PREVIEW requested.")
        elif keypress == "d":  # Toggle debug mode.
            main_log.log("Keyboard interrupt: Toggle debug mode.", terminal=False)
            params.debug_mode = not params.debug_mode  # Toggle the value.
            session.debug_mode = params.debug_mode  # Tell the session about it too!
            main_log.log(
                "Keyboard interrupt: DebugMode now",
                params.debug_mode,
                terminal=False,
            )
            TextColor.clearscreen()  # Clear screen afterwards.
            if session.debug_mode:
                print(TextColor.yellow("Debug mode ON."))
            else:
                print(TextColor.yellow("Debug mode OFF."))
        elif keypress == "r":  # Refresh screen.
            main_log.log("Keyboard interrupt: Refresh selected.", terminal=False)
            TextColor.clearscreen()  # Clear screen afterwards.
        # # Start fresh move/capture iteration.
        # If the window dimensions have changed, clear the screen and let it redraw automatically.
        if not session.debug_mode:
            temp = (
                get_terminal_size()
            )  # Note the size of the window. If it changes, we'll clear the screen.
            if (
                TerminalCols != temp[0] or TerminalRows != temp[1]
            ):  # Screen size has changed. Trigger refresh.
                TextColor.clearscreen()  # Clear screen afterwards.
                TerminalCols = temp[0]  # Note the new display dimensions.
                TerminalRows = temp[1]
        if not CameraThread.is_alive():  # If the CameraThread has died, quit.
            main_log.log(
                "observation_run: CameraThread (Camera handler) is not running!",
                level="error",
            )
            CameraWindow.print(now_hour_minute_sec() + " CameraThread is not running.")
            observationresult = False  # Don't continue.
            RunObservation = False  # Observation cannot continue.
        if not MessageThread.is_alive():  # If message handler thread has died, quit.
            main_log.log(
                "observation_run: (loop) MessageThread is not running!", level="error"
            )
            observationresult = False  # Don't continue.
            RunObservation = False  # Observation cannot continue.
        if (
            not MctlThread.is_alive()
        ):  # If the motor microcontroller communication thread has died, quit.
            main_log.log(
                "observation_run: (loop) MctlThread is not running!", level="error"
            )
            observationresult = False  # Don't continue.
            RunObservation = False  # Observation cannot continue.
        if (
            not CameraStatusQueue.empty()
        ):  # The CameraThread has sent messages that need to be processed.
            StatusMessage = (
                CameraStatusQueue.get()
            )  # Retrieve the first message in the queue.
            session.camera_rx_count += 1  # We received another message from the camera.
            # Extract any useful information from the received messages.
            if "PhotoCount" in StatusMessage:
                PhotoCount = StatusMessage[
                    "PhotoCount"
                ]  # Camera has updated the number of photographs taken during this run.
        # Calculate the current position of the target. This also updates the cached values, which remain valid for the duration of this loop.
        dtnow = now_utc()  # In datetime format.
        ra, dec = (
            session.target.ra_dec_degrees()
        )  # Target's position. Right Ascension and Declination.
        az, alt = session.target.az_alt_degrees(
            updatespeed=True
        )  # Target's position. Altitude and Azimuth from observer's location. Update angular velocity too.
        ObservationDuration = (
            dtnow - obsstart
        ).total_seconds()  # How long has this observation run been running for?
        observation_status_window.field_value(
            "TARGET", session.target.name, fg=OSW_TEXT_GOOD, bg=OSW_TEXT_BG
        )  # Update the target name.
        observation_status_window.field_value(
            "FOLDER",
            FolderHandler.get_path("session"),
            fg=OSW_TEXT_GOOD,
            bg=OSW_TEXT_BG,
        )  # Which folder is the observation data saved in.
        if ClockOffset is not None:  # The clock is not running in realtime.
            observation_status_window.field_value(
                "CLOCK",
                str(now_utc()).split("+")[0],
                fg=TextColor.WHITE,
                bg=TextColor.RED,
            )  # System clock in UTC.
        else:  # Clock IS running in realtime.
            observation_status_window.field_value(
                "CLOCK", str(now_utc()).split("+")[0], fg=OSW_TEXT_GOOD, bg=OSW_TEXT_BG
            )  # System clock in UTC.
        observation_status_window.field_value(
            "DURATION", human_readable_seconds(ObservationDuration), fg=OSW_TEXT_GOOD
        )  # How long has this observation been running.
        observation_status_window.field_value(
            "IMAGETYPES", camera_in_use.image_types(), fg=OSW_TEXT_GOOD, bg=OSW_TEXT_BG
        )  # What image types are being recorded?
        # Calculate storage available.
        if (
            not update_storage_status()
        ):  # Update storage space available, and decide if it's safe to continue.
            observationresult = False  # Don't continue.
            RunObservation = False  # Quit the observation run.
            main_log.log(
                "observation_run: Insufficient storage space terminating the observation.",
                level="error",
            )
        # Camera status.
        update_camera_status()  # Update the camera status.
        # Motor control mode.
        observation_status_window.field_value(
            "CMODE", session.motor_control_mode, fg=OSW_TEXT_GOOD
        )  # *Q* Is MotorControlMode needed anymore?
        # Target status
        if ready_to_observe:  # Camera is on target. Report the status.
            observation_status_window.field_value(
                "TSTATUS", "Acquired   ", fg=OSW_TEXT_GOOD
            )  # Green
            if (
                session.autonomous_control or session.motor_control_mode == "direct"
            ):  # We're on target AND there's a trajectory in place, or we've taken direct control of the motors.
                observation_status_window.field_value(
                    "TSDESC", "Ready for observation.    "
                )  # Green
            else:  # We're on target but the motor microcontroller does not have a full trajectory yet, we still need to wait before taking photographs.
                observation_status_window.field_value(
                    "TSDESC", "Waiting for trajectory.   "
                )  # Green
        else:  # The camera has not yet reached the target position.
            observation_status_window.field_value(
                "TSTATUS", "Acquiring  ", fg=OSW_TEXT_BAD
            )  # Red
            observation_status_window.field_value(
                "TSDESC", "Not ready for observation."
            )
        if not session.target.visible():
            fgc = fgd = OSW_TEXT_BAD  # Field colour if target is not visible. (Red)
        elif session.target.approaching_limit():
            fgc = fgd = (
                OSW_TEXT_POOR  # Field colour if target is approaching limits. (Yellow)
            )
        else:
            fgc = OSW_TEXT_GOOD  # Field colour if target is visible. (Green)
            fgd = OSW_TEXT_FG  # Field colour if target is visible. (Green)
        dh, dm, ds = angle_to_hms(
            ra
        )  # Convert target Right Ascension angle into hours, minutes, seconds.
        if (
            params.use_live_location
        ):  # Use the live target location rather than the last reported camera position for image processing.
            CameraAz, CameraAlt = (
                session.target.az_alt_degrees()
            )  # What is the alt/az location of the centre of the image?
            CameraLatestAlt, CameraLatestAz = (
                last_reported_alt_az()
            )  # What is the alt/az location of the centre of the image?
        else:  # Use the last reported camera position. Deprecated.
            CameraAlt, CameraAz = (
                last_reported_alt_az()
            )  # What is the alt/az location of the centre of the image?
            CameraLatestAlt = CameraAlt
            CameraLatestAz = CameraAz
        EstimatedAlt, EstimatedAz = (
            estimated_alt_az()
        )  # Where is the camera estimated to be pointing at given it's latest speed?
        observation_status_window.field_value(
            "CAMAZ",
            display_degree(CameraLatestAz, 15, symbol=DEGREE_SYMBOL),
            fg=fgc,
            bg=OSW_TEXT_BG,
        )  # Camera's last reported position.
        observation_status_window.field_value(
            "CAMALT",
            display_degree(CameraLatestAlt, 15, symbol=DEGREE_SYMBOL),
            fg=fgc,
            bg=OSW_TEXT_BG,
        )
        observation_status_window.field_value(
            "ESTAZ",
            display_degree(EstimatedAz, 15, symbol=DEGREE_SYMBOL),
            fg=fgd,
            bg=OSW_TEXT_BG,
        )  # Camera's estimated current position.
        observation_status_window.field_value(
            "ESTALT",
            display_degree(EstimatedAlt, 15, symbol=DEGREE_SYMBOL),
            fg=fgd,
            bg=OSW_TEXT_BG,
        )
        observation_status_window.field_value(
            "TARAZ",
            display_degree(az, 15, symbol=DEGREE_SYMBOL),
            fg=fgc,
            bg=OSW_TEXT_BG,
        )  # Current target position.
        observation_status_window.field_value(
            "TARALT",
            display_degree(alt, 15, symbol=DEGREE_SYMBOL),
            fg=fgc,
            bg=OSW_TEXT_BG,
        )
        observation_status_window.field_value(
            "COMP", compass_point(az), fg=fgc, bg=OSW_TEXT_BG
        )  # Azimuth as compass point.
        observation_status_window.field_value(
            "RA", display_hms(dh, dm, ds, 15), fg=OSW_TEXT_GOOD, bg=OSW_TEXT_BG
        )  # RA and DEC of target.
        observation_status_window.field_value(
            "DEC",
            display_degree(dec, 15, symbol=DEGREE_SYMBOL),
            fg=OSW_TEXT_GOOD,
            bg=OSW_TEXT_BG,
        )
        # main_log.log("observation_run: Target: Acquired=",ready_to_observe,", Alt=",alt,", Az=",az,", ra=",ra,", dec=",dec,", AltSpeed=",Session.target.alt_speed,", AzSpeed=",Session.target.az_speed,terminal=False)

        # If we're on target, then activate the camera (it runs in a separate thread until told to stop).
        if True:
            if (
                prev_ready_to_observe != ready_to_observe
            ):  # 'on target' status has changed.
                # It is always safe to turn OFF the camera.
                # But only turn the camera ON if the microcontroller reports that it has got AutonomousControl (ie a valid trajectory in place).
                if (
                    not ready_to_observe
                    or session.autonomous_control
                    or session.target.is_fixed_point()
                ):  # Only change status if turning OFF or if AutonomousControl is ready, or it's a fixed point.
                    ControlMessage = {
                        "TimeStamp": now_utc(),
                        "ready_to_observe": ready_to_observe,
                        "BatchSize": 1,
                    }
                    CameraControlQueue.put(
                        ControlMessage
                    )  # Keep sending the CameraEnabled status to the camera.
                    session.camera_tx_count += (
                        1  # We sent another message to the camera.
                    )
                    if session.debug_mode:
                        print(
                            now_hour_minute_sec()
                            + " ready_to_observe changed from "
                            + str(prev_ready_to_observe)
                            + " to "
                            + str(ready_to_observe)
                        )
                    main_log.log(
                        "observation_run. ready_to_observe change from",
                        prev_ready_to_observe,
                        "to",
                        ready_to_observe,
                        terminal=False,
                    )
                    prev_ready_to_observe = ready_to_observe
            if ready_to_observe:
                if ObservationStartUTC is None:
                    ObservationStartUTC = now_utc()  # Note when the observation starts.
                if (
                    camera_in_use.camera_fault()
                ):  # The camera isn't behaving itself. We may need to power cycle the RPi.
                    main_log.log(
                        "camera_in_use.camera_fault: You probably need to power cycle the RPi.",
                        level="error",
                    )
                    cam_log.log(
                        "camera_in_use.camera_fault: You probably need to power cycle the RPi.",
                        level="error",
                    )
                    observationresult = False  # Don't continue
                    RunObservation = False  # Terminate the observation.

        if PhotoCount >= params.batch_size:
            # We've taken the required number of photos as defined by BatchSize.
            # The camera_handler thread is probably already working on the next one, so you may get an extra freebie!
            main_log.log(
                "observation_run: BatchSize reached. Observation run complete."
            )
            RunObservation = False

        if (
            Mctl.DeviceFailure
        ):  # Communication with microcontroller has failed completely.
            main_log.log(
                "observation_run: Mctl.DeviceFailure reported. Stopping observation.",
                level="error",
            )
            observationresult = False  # Don't continue.
            RunObservation = False

        # Check that the target is within observation range of the motors and above the horizon.
        if alt < 0.0 and PrevAlt is not None:  # Target is below horizon!
            if (
                alt < PrevAlt or alt < 5.0
            ):  # The target has set and won't rise for a while!
                main_log.log(
                    "observation_run: Object below horizon. Stopping observation.",
                    level="warning",
                )
                observationresult = False  # Don't continue.
                RunObservation = False
        PrevAlt = alt
        for (
            i
        ) in (
            MotorControls
        ):  # Check also it is within range of the motor movement limits.
            if i.MotorName == "altitude":  # Check range of Altitude motor.
                # if alt < i.MinAngle or alt > i.MaxAngle: # Target is out of scope of the motors. *!*
                if (
                    alt < i.MinObservationAngle or alt > i.MaxAngle
                ):  # Target is out of scope of the motors. *!*
                    main_log.log(
                        "observation_run: The target is outside the altitude range of the telescope. Terminating observation.",
                        level="warning",
                    )
                    observationresult = False  # Don't continue.
                    RunObservation = False
            if i.MotorName == "azimuth":  # Check range of Azimuth motor.
                # if az < i.MinAngle or az > i.MaxAngle: # Target is out of scope of the motors. *!*
                if (
                    az < i.MinObservationAngle or az > i.MaxAngle
                ):  # Target is out of scope of the motors. *!*
                    main_log.log(
                        "observation_run: The target is outside the azimuth range of the telescope. Terminating observation.",
                        level="warning",
                    )
                    observationresult = False  # Don't continue.
                    RunObservation = False

        image_status_window.field_value("IMAGES", str(image_count()), fg=OSW_TEXT_GOOD)
        # Calculate total accumulated image time.
        AccumulatedTime = PhotoCount * camera_in_use.exposure_seconds
        if AccumulatedTime >= 1:  # Show in HH:MM:SS
            image_status_window.field_value(
                "ACCTIME", human_readable_seconds(AccumulatedTime), fg=OSW_TEXT_GOOD
            )
        else:  # Show in 0.00000s
            image_status_window.field_value(
                "ACCTIME", str(AccumulatedTime) + "s", fg=OSW_TEXT_GOOD
            )
        if True:
            pceta = ""  # Don't know the estimated completion time yet.
            if (
                PhotoCount > 0 and ObservationStartUTC is not None
            ):  # We can estimate when the batch of photographs will be completed.
                pcprogress = (
                    float(PhotoCount) / params.batch_size
                )  # Percentage of way through the image batch.
                if (
                    pcprogress > 0.0
                ):  # We've made some progress, so estimate the completion time.
                    pcelapsed = (
                        now_utc() - ObservationStartUTC
                    ).total_seconds()  # Elapsed time so far (seconds).
                    pcend = ObservationStartUTC + timedelta(
                        seconds=int(pcelapsed / pcprogress)
                    )  # Roughly when will the batch be completed?
                    pceta = str(pcend)[:16]  # YYYY.MM.DD HH:MM
            image_status_window.field_value(
                "RUN",
                str(PhotoCount) + " of " + str(params.batch_size),
                fg=OSW_TEXT_GOOD,
            )
            if PhotoCount >= params.batch_size:  # We've hit the target.
                image_status_window.field_color(
                    "RUN", fg=TextColor.BLACK, bg=TextColor.LIGHTGREEN
                )  # Highlight we've made it.
            image_status_window.field_value("ETA", pceta, fg=OSW_TEXT_GOOD)
        else:
            image_status_window.field_value(
                "RUN",
                str(PhotoCount) + " of " + str(params.batch_size) + "(dis.)",
                fg=TextColor.RED1,
            )  # Red
            image_status_window.field_value("ETA", "n/a", fg=OSW_TEXT_GOOD)
        if (
            StopButton is not None and StopButton.IsLow()
        ):  # Emergency stop pin on RPi has been grounded.
            print(TextColor.red("STOP BUTTON: Break observation"))
            error_window.print(now_hour_minute_sec() + " STOP BUTTON pressed.")
            observationresult = False  # Don't continue
            RunObservation = False  # Quit loop.
        UpdateCameraCaptureStatus()
        # Explain what is in the 'last captured image' buffer.
        if camera_in_use.image.ImageExists():  # openCV image buffer is loaded.
            if len(camera_in_use.image.ImageBuffer.shape) > 2:
                fmt = "color"  # Show whether COLOUR or GRAYSCALE image in the OpenCV buffer.
            else:
                fmt = "gray"
            image_status_window.field_value(
                "OCVIB",
                "loaded "
                + hms_from_stamp(camera_in_use.last_image_date_time)
                + " "
                + str(camera_in_use.image.ImageBuffer.shape[0]).rjust(4)
                + "*"
                + str(camera_in_use.image.ImageBuffer.shape[1]).rjust(4)
                + " "
                + fmt,
                fg=OSW_TEXT_GOOD,
            )
        else:
            image_status_window.field_value("OCVIB", "empty", fg=OSW_TEXT_POOR)
        # Explain the status of the TARGET tracking image.
        if DriftTracker.TargetImage.ImageExists():  # openCV image buffer is loaded.
            temp = (
                "matched "
                + str(len(DriftTracker.TargetStarMatchList))
                + " of "
                + str(DriftTracker.TargetImage.StarCount)
                + " stars"
            )
            if len(DriftTracker.TargetImage.ImageBuffer.shape) > 2:
                fmt = "color"  # Show whether COLOUR or GRAYSCALE image in the OpenCV buffer.
            else:
                fmt = "gray"
            temp = (
                str(DriftTracker.TargetImage.ImageBuffer.shape[0]).rjust(4)
                + "*"
                + str(DriftTracker.TargetImage.ImageBuffer.shape[1]).rjust(4)
                + " "
                + fmt
                + " "
                + temp
            )
            image_status_window.field_value(
                "DTI",
                "loaded " + hms_from_stamp(DriftTracker.TargetTimeStamp) + " " + temp,
                fg=OSW_TEXT_GOOD,
            )
        else:  # No drift target image available.
            image_status_window.field_value("DTI", "empty", fg=OSW_TEXT_POOR)
        # Explain the status of the LATEST tracking image.
        if DriftTracker.LatestImage.ImageExists():  # openCV image buffers are loaded.
            temp = (
                "matched "
                + str(len(DriftTracker.LatestStarMatchList))
                + " of "
                + str(DriftTracker.LatestImage.StarCount)
                + " stars"
            )
            if len(DriftTracker.LatestImage.ImageBuffer.shape) > 2:
                fmt = "color"  # Show whether COLOUR or GRAYSCALE image in the OpenCV buffer.
            else:
                fmt = "gray"
            temp = (
                str(DriftTracker.LatestImage.ImageBuffer.shape[0]).rjust(4)
                + "*"
                + str(DriftTracker.LatestImage.ImageBuffer.shape[1]).rjust(4)
                + " "
                + fmt
                + " "
                + temp
            )
            image_status_window.field_value(
                "DLI",
                "loaded " + hms_from_stamp(DriftTracker.LatestTimeStamp) + " " + temp,
                fg=OSW_TEXT_GOOD,
            )
        else:  # No current drift image available.
            image_status_window.field_value("DLI", "empty", fg=OSW_TEXT_POOR)
        ready_to_observe = True  # Work out if all the motors are on target!
        for i in MotorControls:  # Report tuning status of each motor in turn.
            if (
                session.target.is_fixed_point()
            ):  # Fixed point, doesn't need the motor to report 'OnTarget' - we decide in this program instead.
                pass  # Take no action here. Motor was already placed 'on target' when observation_run started. It doesn't move after that.
            elif not i.OnTarget:
                ready_to_observe = False  # This motor is not on target yet. So we're not ready to observe.
                main_log.log(
                    "observation_run.",
                    i.MotorName,
                    "Not on target: ready_to_observe = False",
                    terminal=False,
                )
            if i.LatestTuneTime is not None:  # This motor has been tuned.
                line = (
                    str(i.LatestTuneSteps)
                    + " steps at "
                    + str(i.LatestTuneTime).split("+")[0]
                    + " UTC"
                )
            else:  # This motor has not been tuned.
                line = "None"
            if i.MotorName == "azimuth":
                image_status_window.field_value("LAZT", line, fg=OSW_TEXT_GOOD)
            else:
                image_status_window.field_value("LALT", line, fg=OSW_TEXT_GOOD)

        if session.debug_mode:  # We're in debug mode, just summary status update.
            if DebugTimer.due():  # It's time to publish a summary status.
                print(
                    now_hour_minute_sec()
                    + " Target "
                    + TextColor.white(session.target.name)
                    + " "
                    + az_alt_text(az, alt)
                )
                print(
                    now_hour_minute_sec() + " Session images: " + image_count_session()
                )  # Count images in the current SESSION!
                for line in storage_strings():
                    print(now_hour_minute_sec() + line)
                print(
                    now_hour_minute_sec()
                    + " Session: "
                    + FolderHandler.get_path("session")
                )
                if (
                    ClockOffset is not None
                ):  # Warn that tracking clock is not running in realtime.
                    print(
                        TextColor.red(
                            now_hour_minute_sec() + " Tracking clock is offset to",
                            str(now_utc()).split(".")[0],
                        )
                    )
        else:  # Not in debug mode, update the color display.
            # Refresh status and debug windows.
            # These will draw if their allocated terminal space is available.
            observation_status_window.display(
                TerminalRows, TerminalCols
            )  # Refresh the actual display.
            image_status_window.display(TerminalRows, TerminalCols)
            instruction_window.display(
                TerminalRows, TerminalCols
            )  # Display session status.
            # - Column 2
            error_window.display(
                TerminalRows, TerminalCols
            )  # Display latest error messages.
            session.show_remote_status()  # Update status measures in the window buffers.
            SessionWindow.display(TerminalRows, TerminalCols)  # Display instructions.
            MctlRxWindow.display(
                TerminalRows, TerminalCols
            )  # Display Microcontroller UART RX traffic.
            MctlTxWindow.display(
                TerminalRows, TerminalCols
            )  # Display Microcontroller UART TX traffic.
            CameraWindow.display(TerminalRows, TerminalCols)  # Display camera status.
            # - Column 3
            DriftWindow.display(
                TerminalRows, TerminalCols
            )  # Display drift calculation log.
            CameraTxWindow.display(
                TerminalRows, TerminalCols
            )  # Display Camera command TX traffic.
            CameraRxWindow.display(
                TerminalRows, TerminalCols
            )  # Display Camera command RX traffic.
            DevWindow.display(
                TerminalRows, TerminalCols
            )  # Display developer events messages.

        # Calculate how long this loop took to execute.
        ltts = (now_utc() - dtnow).total_seconds()  # How long did the loop take?
        cumulativelooptime += ltts  # Total processing time of all loops.
        cumulativeloopcount += 1  # Number of loops.
        averagelooptime = cumulativelooptime / cumulativeloopcount  # Average loop time.
        # main_log.log("observation_run: Total LOOP time=" + str(round(ltts * 1000,3)) + "ms. Ave LOOP time=" + str(round(averagelooptime * 1000,3)) + "ms.",terminal=False)
        LoopTimeList.append(round(ltts, 1))  # Add to the list of recent loop times.
        if (
            ltts > 20
        ):  # Exceedingly long loop time. O/S is busy with something else! If frequent it can be a sign that the memory card is aging/fragmented/damaged. Time to reinstall.
            SlowLoopCounter += 1  # Increment the count of slow loops, if we get a lot, there's maybe a problem.
            if SlowLoopCounter % 10 == 0:
                DevWindow.print(
                    now_hour_minute_sec()
                    + " Detected "
                    + str(SlowLoopCounter)
                    + " slow loops."
                )
                # A lot of slow loops suggests that the O/S is getting distracted with other tasks.
                # It can be a sign that the memory card is aging and needs replacing.
        LoopTimeList = LoopTimeList[-10:]  # Limit list to last 10 entries.

        # End of main observation_run loop.

    # Observation is over at this point.
    print(
        TextColor.clearforward()
    )  # Clear the screen from the current location forward, makes the following messages easier to read.
    ready_to_observe = False
    if True:  # Tell the camera it is all over.
        ControlMessage = {"TimeStamp": now_utc(), "ready_to_observe": False}
        CameraControlQueue.put(
            ControlMessage
        )  # Keep sending the CameraEnabled status to the camera.
        session.camera_tx_count += 1  # We sent another message to the camera.
        shutdown_camera()  # Wait for the camera thread to terminate.
    # Tell the motors it is all over now that the camera is completed.
    stop_motors()  # Tell the motors to immediately stop.
    print(
        "\n" + TextColor.cursordown(10) + TextColor.clearforward()
    )  # Move cursor below the observation_run display and clear the rest of the screen to make way for the menu.
    if (
        params.generate_preview and not camera_in_use.fast_image_capture
    ):  # Preview images were requested, and could have been captured.
        if ask_yes_no(
            "Do you want to generate an AVI animation of the preview files? [y/N]",
            False,
        ):  # We can generate a small animation of the observation from the preview images.
            generate_preview_movie()
    if params.generate_keogram or session.target.object_type in [
        "aurora"
    ]:  # Generate Keogram at end of observation.
        main_log.log("Generating Keogram from observation images.", terminal=True)
        camera_in_use.build_keogram(altitude=alt, azimuth=az)

    report_observation_errors()

    TextColor.text_box(
        "The images are stored in " + FolderHandler.get_path("session"),
        fg=TextColor.YELLOW,
        bg=TextColor.BLACK,
    )
    if (
        camera_in_use.fast_image_capture and camera_in_use.camera_save_dng
    ):  # Only JPG files have been created so far.
        print(
            TextColor.yellow(
                "FastImageCapture is active. Only the raw JPG data files have been created so far."
            )
        )
        print(
            TextColor.yellow(
                "If you want to create separate DNG files, or pure JPG files you still need to process them."
            )
        )

    # End of observation...
    session.set_motor_control_mode("idle")  # The motors should now be idle.
    flag_observation_end()  # Mark that the observation run has completed successfully. This tells the next observationrun that all is OK. It's also called by the menu for safety.

    main_log.log("observation_run: end.", terminal=False)
    return observationresult


# -----------------------------------------------------------------------------------------------------


def add_angles(angle1, angle2):
    """Add 2 angles together.
    Angles can be decimal values, or skyfield angle objects."""
    if hasattr(angle1, "_degrees"):
        a1 = angle1._degrees
    elif hasattr(angle1, "degrees"):
        a1 = angle1.degrees
    else:
        a1 = angle1
    if hasattr(angle2, "_degrees"):
        a2 = angle2._degrees
    elif hasattr(angle2, "degrees"):
        a2 = angle2.degrees
    else:
        a2 = angle2
    result = a1 + a2
    return result


def disable_cleanup():  # For menu
    if check_image_set():  # Only allow a change if the current image set is acceptable.
        print("The Raspberry Pi HQ sensor performs some on-chip image cleanup.")
        print("On-chip cleanup may degrade the raw image data.")
        print("It is recommended to disable this feature for astrophotography.")
        if params.camera_driver == "raspistill":
            print(
                "- You may get warning messages displayed by this action, they are generally OK to ignore."
            )
            if ask_yes_no("Disable on-sensor cleanup? [y/N]", False):
                sensor_in_use.disable_cleanup()
                define_session_folders(
                    session.target.name, camera_in_use.exposure_seconds
                )  # This assigns folder names for all the image types.
                document_session()
                DriftTracker.Reset()
        else:
            print(
                "- With libcamera installations you should edit the --denoise parameter in the command templates."
            )
            print("  The '--denoise off' option will disable cleanup.")


# ------------------------------------------------------------------------------------------------


def enable_cleanup():  # For menu
    if check_image_set():  # Only allow a change if the current image set is acceptable.
        print(
            "The Raspberry Pi High Quality camera can perform some on-chip image cleanup."
        )
        print(
            "It is often disabled for astrophotography because it degrades the raw image data slightly."
        )
        print("It is recommended to enable this for regular photography.")
        if params.camera_driver == "raspistill":
            if ask_yes_no("Enable on-sensor cleanup? [y/N]", False):
                print(
                    "- You may get warning messages displayed by this action, they are generally OK to ignore."
                )
                sensor_in_use.enable_cleanup()
                define_session_folders(
                    session.target.name, camera_in_use.exposure_seconds
                )  # This assigns folder names for all the image types.
                document_session()
                DriftTracker.Reset()
        else:
            print(
                "- With libcamera installations you should edit the --denoise parameter in the command templates."
            )
            print("  Removing the '--denoise off' option will enable cleanup.")


def position_strings():
    """Return a string listing the current motor positions.
    For display purposes."""
    PS = " Camera:"
    for i in MotorControls:
        PS += (
            " "
            + i.MotorName
            + ": "
            + str(i.AngleToStep(i.CurrentAngle))
            + " ("
            + deg_3dp(i.CurrentAngle)
            + DEGREE_SYMBOL
            + ")"
        )
    PS = " " + PS.strip()
    return [PS]


def target_strings():
    """Returns a list of strings describing the current target."""
    # If star name is recognised in the starname dictionary, list the constellation too.
    result = []
    constellation = session.target.constellation
    if constellation is None:
        constellation = ""
    else:
        constellation = "(" + constellation + ") "
    type = session.target.object_type
    if type is None:
        type = ""
    else:
        type = "(" + type + ") "
    TS = " Target: " + session.target.name + " "
    TS += type
    TS += constellation
    result.append(TS)
    TS = " Mag: " + str(session.target.magnitude) + " "
    az, alt = session.target.az_alt_degrees()
    TS += az_alt_text(az, alt)
    if session.target.visible():
        TS += " (in range)"
    else:
        TS += " (out of range)"
    result.append(TS)
    return result


def sensor_strings():
    """Return a string showing the current sensor/image settings."""
    SS = (
        " Sensor: Mode "
        + str(sensor_in_use.mode)
        + ", Dimensions "
        + str(sensor_in_use.pixel_width)
        + "x"
        + str(sensor_in_use.pixel_height)
    )
    if sensor_in_use.on_chip_cleanup:
        SS += " OnChipCleanup ON."
    else:
        SS += " OnChipCleanup OFF."
    return [SS]


def exposure_strings():
    """Return a string listing the current exposure settings."""
    returnlist = []
    ES = " Exposure: " + str(camera_in_use.exposure_seconds) + "s"
    ES += ", Batch: " + str(params.batch_size)
    ES += ", Ctrl: " + str(params.control_batch_size)
    ES += ", Types: "
    if camera_in_use.camera_save_jpg:
        ES += "jpg "
    if camera_in_use.camera_save_dng:
        ES += "dng "
    if camera_in_use.camera_save_fits:
        ES += "fits "
    if not params.camera_enabled:
        ES += "(Disabled)"
    returnlist.append(ES)
    ES = ""
    if (
        camera_in_use.timelapse_seconds is not None
        and camera_in_use.timelapse_seconds > 0
    ):
        ES += " Timelapse: " + str(camera_in_use.timelapse_seconds) + "s. "
    if ES != "":
        returnlist.append(ES)
    return returnlist


def session_strings():
    """Return a string listing current session details."""
    SS = " Session: " + FolderHandler.get_path("session")
    return [SS]


def image_strings():
    """Return a string listing current session's images."""
    returnlist = []
    SS = (
        " Campaign images: " + image_count_campaign()
    )  # Count images in the CAMPAIGN! (Multiple sessions)
    returnlist.append(SS)
    SS = (
        " Session images: " + image_count_session()
    )  # Count images in the current SESSION!
    returnlist.append(SS)
    return returnlist


def storage_strings():
    """Return a string listing current storage space."""
    returnlist = []
    if params.use_usb_storage and usb_disc_monitor.drive_available:
        temp = int(usb_disc_monitor.free_mega_bytes())
        SS = " USB memory: Free storage: " + format(temp, ",") + "Mb."
        if temp < 1000:
            SS += " (<1 Gb left!)"
        elif temp < 500:
            SS += " (<500 Mb left! Critical!)"
        returnlist.append(SS)
    temp = int(sd_card_monitor.free_mega_bytes())
    SS = " SD card: Free storage: " + format(temp, ",") + "Mb."
    if temp < 1000:
        SS += " (<1 Gb left!)"
    elif temp < 500:
        SS += " (<500 Mb left! Critical!)"
    returnlist.append(SS)
    return returnlist


def program_start_strings():
    """Return a string listing when the program started."""
    delta = human_readable_seconds(
        (now_utc() - session.program_start_time).total_seconds()
    )
    PS = (
        " Program started: "
        + str(session.program_start_time).split(".")[0]
        + " UTC        ("
        + delta
        + ")"
    )
    return [PS]


def microcontroller_strings():
    """Return a string listing microcontroller status."""
    PS = (
        " Microcontroller: RPi>Mctl "
        + human_readable_bytes(Mctl.BytesSent)
        + ", Mctl>RPi "
        + human_readable_bytes(Mctl.BytesReceived)
        + "."
    )
    return [PS]


def document_session():
    """Create a brief description of the session and key parameters.
    Details are written to a disc file."""
    with open(FolderHandler.prep_file("session", "info.txt"), "w") as f:
        f.write("# " + ProgramTitle.upper() + " session settings:\n")
        f.write("Program started\t" + str(session.program_start_time) + "\n")
        f.write("Source code\t" + source_code() + "\n")
        f.write("Source version\t" + str(source_date()) + "\n")
        f.write("Session started\t" + str(now_utc()) + "\n")
        f.write("Session path\t" + FolderHandler.get_path("session") + "\n")
        f.write("Target\t" + session.target.name + "\n")
        f.write("SearchGroup\t" + session.target.search_group + "\n")
        f.write("SearchTerm\t" + session.target.search_term + "\n")
        f.write("Exposure time\t" + str(camera_in_use.exposure_seconds) + "seconds\n")
        f.write("Sensor mode\t" + str(sensor_in_use.mode) + "\n")
        f.write("Image width\t" + str(sensor_in_use.pixel_width) + "\n")
        f.write("Image height\t" + str(sensor_in_use.pixel_height) + "\n")
        f.write(
            "Maximum exposure time\t"
            + str(sensor_in_use.max_exposure_seconds)
            + "seconds\n"
        )
        f.write("Sensor type\t" + sensor_in_use.type + "\n")
        f.write(
            "Pixels per FOV degree width\t"
            + str(camera_in_use.pixels_per_fov_degree_width)
            + "\n"
        )
        f.write(
            "Pixels per FOV degree height\t"
            + str(camera_in_use.pixels_per_fov_degree_height)
            + "\n"
        )
        f.write("Infrared filter\t" + str(params.ir_filter) + "\n")
        f.write("Light pollution filter\t" + str(params.pollution_filter) + "\n")
        f.write(
            "Timelapse delay\t" + str(camera_in_use.timelapse_seconds) + "seconds\n"
        )
    # Append key values to 'recent target list'. This is useful if recovering from system failure, or resuming a previous observation at a later date.
    # When selecting a new target, this recent target list is offered as a short-cut to duplicate previous observations.
    if camera_in_use.timelapse_seconds == 0.0:
        CIU_TS = None  # Timelapse value 0.0  needs to be None! Set to None in the sessionentry.
    else:
        CIU_TS = camera_in_use.timelapse_seconds
    session_history.add(
        {
            "Name": session.target.name,
            "SearchGroup": session.target.search_group,
            "SearchTerm": session.target.search_term,
            "ExposureSeconds": camera_in_use.exposure_seconds,
            # 'SensorMode':sensor_in_use.mode,
            "LastObserved": str(now_utc()),
            "TimelapsePeriod": camera_in_use.timelapse_seconds,
        }
    )
    session_history.sort_by_age()  # Sort youngest first.
    session_history.save_as_json(
        HistoryJsonFile, limit=params.session_history_limit
    )  # Only save the xxx most recent targets.

    return


def summarise_observation_parameters():
    """Construct a string listing the observation parameters.
    Used to confirm that it's OK to start an observation."""
    result = ""
    result += (
        "Observation of "
        + session.target.name
        + " will capture "
        + str(int(params.batch_size))
        + " images of "
        + str(camera_in_use.exposure_seconds)
        + "s. ("
    )
    if camera_in_use.camera_save_jpg:
        result += "jpg "
    if camera_in_use.camera_save_dng:
        result += "dng "
    if camera_in_use.camera_save_fits:
        result += "fits "
    result = result.strip() + ")"
    return result


# Document the default session which has been defined by the startup questions.
# If the menu is used to change key parameters, a fresh session will be created at the same time.
# If you change multiple parameters, an empty set of folders will be needlessly created for each individual parameter change.
# *Q* Low priority, but this could be reworked to avoid creating those unused folder structures.
document_session()  # Write a summary document with key info into the session folder.


def flush_command_queue():  # For menu
    Mctl.WriteFlush(send=False)
    Mctl.ReadFlush()


def show_parameters():  # For menu
    params.show()


def edit_parameters():  # For menu
    # global Parameters
    params.save_attributes(params.param_filename)  # Save current values.
    osCmd(
        "cp "
        + params.param_filename
        + " "
        + params.param_filename.split(".")[0]
        + "_"
        + clean_datetime_string(utc_time_stamp())
        + ".bak"
    )  # Backup current values.
    os.system("nano " + params.param_filename)  # Edit
    params.load_parameters()  # Reload into memory - this prevents OLD values overwriting the new ones when you exit the program.
    params.require_restart = True  # Flag that the parameters are nolonger safe until the program is restarted.
    restart_required()  # Warn the user that the software now needs to be restarted.
    _ = input(TextColor.cyan("[ENTER] to continue"))


def edit_target_history():  # For menu
    osCmd(
        "cp "
        + HistoryJsonFile
        + " "
        + HistoryJsonFile.split(".")[0]
        + "_"
        + clean_datetime_string(utc_time_stamp())
        + ".bak"
    )  # Backup current values
    os.system("nano " + HistoryJsonFile)  # Edit


def debug_mode_off():  # For menu
    params.debug_mode = False  # Full dynamic display enabled.
    session.debug_mode = params.debug_mode
    main_log.log("observation_run debug mode disabled.")
    print(
        TextColor.yellow(
            "The full dashboard will be shown. This refreshes very quickly."
        )
    )
    print(
        TextColor.yellow(
            "This will make it difficult to see any error messages generated by the software."
        )
    )
    print(
        TextColor.yellow(
            "If you have problems that need to be investigated, please turn DebugMode back on."
        )
    )


def debug_mode_on():  # For menu
    params.debug_mode = True  # Dynamic display disabled. Error messages only shown.
    session.debug_mode = params.debug_mode
    main_log.log("observation_run debug mode activated.")
    print(
        TextColor.yellow(
            "The dashboard will not be shown, a simpler list of actions will appear instead."
        )
    )
    print(
        TextColor.yellow(
            "This will make it easier to see any error messages generated by the software."
        )
    )


def select_target():  # For menu
    if check_image_set():  # Only allow a change if the current image set is acceptable.
        session.target = target_selection()  # Returns a Target class.
        camera_in_use.set_observation_parameters(
            session
        )  # Set target specific parameters for the camera.
        define_session_folders(
            session.target.name, camera_in_use.exposure_seconds
        )  # This assigns folder names for all the image types.
        document_session()
        DriftTracker.Reset()
        program_status()  # Show current situation of the telescope and target.


def begin_observation():  # For menu
    if (
        params.require_restart
    ):  # Warn that movements cannot be made until software is restarted.
        restart_required()
        return
    print(TextColor.yellow(summarise_observation_parameters()))
    if ask_yes_no("OK to start observation? [y/N]", default=False):
        observation_run()


def menu_go_to_target():  # For menu
    go_to_target(session.target)


def set_timelapse_delay():  # For menu
    camera_in_use.set_timelapse(set_camera_timelapse(camera_in_use.timelapse_seconds))


def menu_set_batch_size():  # For menu
    params.batch_size = set_batch_size(params.batch_size)


def menu_set_control_batch_size():  # For menu
    params.control_batch_size = set_control_batch_size(params.control_batch_size)


def menu_dark_set():  # For menu
    start_camera_thread()
    camera_in_use.dark_set(batch_size=params.control_batch_size)
    shutdown_camera()


def menu_flat_set():  # For menu
    start_camera_thread()
    camera_in_use.flat_set(batch_size=params.control_batch_size)
    shutdown_camera()


def menu_bias_set():  # For menu
    start_camera_thread()
    camera_in_use.bias_set(batch_size=params.control_batch_size)
    shutdown_camera()


def menu_dark_flat_set():  # For menu
    start_camera_thread()
    camera_in_use.dark_flat_set(batch_size=params.control_batch_size)
    shutdown_camera()


def menu_manual_preview():  # For Menu
    start_camera_thread()
    manual_preview()  # *Q* should be within AstroCamera class eventually. Some work needed first though.
    shutdown_camera()


def menu_auto_photo():  # For menu
    if params.camera_enabled:
        start_camera_thread()
        camera_in_use.auto_photo()  # Take a series of completely automatic exposures (for focus testing etc in daylight).
        shutdown_camera()
    else:
        main_log.log(
            "MenuAutoPhoto: Camera is disabled. Cannot capture images.",
            level="warning",
            terminal=True,
        )


def process_image_files():  # For menu
    print(TextColor.yellow("Process image files:"))
    print("If you used FastImageCapture the image files have not been fully processed.")
    print("For example now RAW (.dng) extraction may have been done yet.")
    print("This option will run through all the image files captured so far")
    print("and make sure that each image is fully processed.")
    if ask_yes_no("Do you want to continue? [y/N]", False):
        camera_in_use.process_image_files()
    else:
        print("No further processing done.")


def menu_shutdown_message():
    print(TextColor.yellow("Shutdown message handler."))
    shutdown_message()


def menu_start_message():
    print(TextColor.yellow("Start message handler."))
    start_message_thread()


def communication_warnings():
    """Quick check that communication is up and running.
    Report to the terminal if not."""
    try:
        temp = int((now_utc() - Mctl.LastRxTime).total_seconds())
        if (
            temp >= params.mctl_comms_timeout
        ):  # Line has been open long enough to expect some traffic.
            print(
                TextColor.fgbgcolor(
                    TextColor.WHITE,
                    TextColor.ORANGERED1,
                    " WARNING: No data received from microcontroller for "
                    + str(temp)
                    + " seconds. ",
                )
            )
    except Exception as e:
        main_log.log(
            "communication_warnings(): Failed to calculate Rx age.",
            Mctl.LineOpenedTime,
            params.mctl_comms_timeout,
            terminal=False,
        )
        main_log.record_traceback(None)  # Record the stack at this point.
    try:
        if Mctl.BytesReceived <= 0 or Mctl.LinesReceived <= 0:
            print(
                TextColor.yellow(
                    "No data received from microcontroller since last startup."
                )
            )
    except Exception as e:
        main_log.log(
            "communication_warnings(): Failed to report Rx volume.",
            Mctl.BytesReceived,
            Mctl.LinesReceived,
            terminal=False,
        )
        main_log.record_traceback(None)  # Record the stack at this point.


def program_status():  # For menu
    """Show a status summary of the telescope and session.
    What's the target?
    What are the settings?
    What's the current position of the telescope?"""
    listlines = []
    temp = (
        " "
        + ProgramTitle.upper()
        + " "
        + VERSION
        + " "
        + (str(now_utc()).split(".")[0])
        + " UTC"
    )
    if session.debug_mode:  # In debug mode, warn the user.
        temp += " (DEBUG MODE)"
    listlines.extend([temp])
    listlines.extend(target_strings())
    listlines.extend([rise_set_string(session.target)])
    listlines.extend(session_strings())
    listlines.extend(position_strings())
    listlines.extend(exposure_strings())
    listlines.extend(image_strings())
    listlines.extend(sensor_strings())
    listlines.extend(storage_strings())
    listlines.extend(program_start_strings())
    listlines.extend(microcontroller_strings())
    temp = (
        " Observer's location: Latitude: "
        + deg_3dp(params._home_lat_val, DEGREE_SYMBOL)
        + " Longitude: "
        + deg_3dp(params._home_lon_val, DEGREE_SYMBOL)
    )
    listlines.extend([temp])
    TextColor.text_box(listlines, fg=MENU_SUBTITLE_FG, bg=MENU_SUBTITLE_BG)
    communication_warnings()  # Add some warnings if the communication doesn't look healthy.


def scan_for_meteors():  # For menu
    print(
        TextColor.yellow(
            "This will scan all available 'light' image files for potential meteor trails."
        )
    )
    print(TextColor.yellow("Press 'x' to quit"))
    camera_in_use.meteor_file_scan()  # Scan all available 'light' jpg files for potential meteor traces. Ignore the returned list of filenames.


def menu_satellite_passes():
    """Run the SatellitePasses method to list satellite passes in the next few days."""
    if not hasattr(session.target.handle, "find_events"):
        print(
            TextColor.red(
                "The current target (",
                session.target.name,
                ") does not support satellite pass calculations.",
            )
        )
        return
    else:
        session.target.satellite_passes(window=144)


def zip_comms_log():
    """Extract communication summary from the main log file and zip it."""
    main_log.log("ZipCommsLog", terminal=True)
    zipfile = main_log.package_search_result(
        "RPi received|RPi queueing|warning|error", ignorecase=True
    )
    main_log.log("ZipCommsLog: Generated", zipfile, terminal=True)


def zip_trajectory_log():
    main_log.log("ZipTrajectoryLog", terminal=True)
    zipfile = main_log.package_search_result(
        "RPi queueing.*): trajectory ", ignorecase=True
    )
    main_log.log("ZipTrajectoryLog: Generated", zipfile, terminal=True)


def zip_motor_status_log():
    main_log.log("ZipMotorStatusLog", terminal=True)
    zipfile = main_log.package_search_result(
        "RPi received: motor status", ignorecase=True
    )
    main_log.log("ZipMotorStatusLog: Generated", zipfile, terminal=True)


def monitor_comms_help():
    """Show the functions available in the MonitorComms utility."""
    print(TextColor.yellow("MonitorComms"))
    print("This will show communication traffic.")
    print("Press 'x' to return to the menu.")
    print("Press 'r' to reset microcontroller.")
    print("Press 'f' to flash LED Yellow.")
    print("Press 'c' to send manual commands.")
    print("Press '?' for this list.")


def monitor_comms():
    """For a period mirror microcontroller communication to the terminal."""
    monitor_comms_help()  # Show initial help.
    if (
        Mctl.PowerIsOn() or Mctl.PoweredByUsb
    ):  # Warn if the microcontroller is not powered.
        print(
            TextColor.green(
                "The microcontroller power is ON. Communication should be running."
            )
        )
    else:
        print(TextColor.red("The microcontroller is OFF. No communication expected."))
    Mctl.StartMonitor()  # Turn on replication to the terminal.
    while True:
        keypress = Keyboard.check().lower()
        if keypress == "x":
            break
        elif keypress == "r":  # Reset microcontroller.
            print(TextColor.yellow("Restarting microcontroller."))
            restart_microcontroller()  # Force the microcontroller to restart.
        elif keypress == "f":  # Flash RGB LED YELLOW for 1 second.
            print(TextColor.yellow("Sending YELLOW flash to microcontroller LED."))
            Mctl.write("set rgb " + clean_datetime_string(str(now_utc())) + " y y n 1")
        elif keypress == "c":  # Send manual commands to the microcontroller.
            Mctl.SendManualCommand()
            print("To send another command press 'c' again.")
        elif keypress == "?":  # Reprint the help list of commands.
            monitor_comms_help()
        time.sleep(0.5)
    Mctl.EndMonitor()  # Turn off replication to the terminal.


def show_motor_status():
    """Show the status of all the motors."""
    print(TextColor.yellow("Motor status"))

    print("  Backlash enabled:", params.backlash_enabled)
    print("   Fault sensitive:", params.fault_sensitive)
    print("Motor status delay:", params.motor_status_delay, "s")
    print(
        "  Restart required:", params.require_restart
    )  # Parameters have been changed, system needs restart.
    print(" ")
    for i in MotorControls:
        i.show_motor_status()


def tracking_status():
    """Show tracking parameters and results.
    This is to help tuning the tracking parameters.
    It is highly likely that every instance of the telescope will need
    different parameter settings to optimise the tracking depending upon
    the camera/lens in use and the quality of the sky visible.
    This shows the key parameters that affect the way tracking works to
    help you tune the values."""
    print(TextColor.yellow("Tracking status"))
    print("This shows tracking system parameters and any recent tracking results.")
    print("Use this information to finetune tracking performance.")
    print("")

    if params.use_tracking:
        print(
            TextColor.green("Tracking is currently enabled."),
            TextColor.blue("(UseTracking parameter)"),
        )
    else:
        print(
            TextColor.red("Tracking is currently disabled."),
            TextColor.blue("(UseTracking parameter)"),
        )
    print("")

    print(TextColor.white("Camera"))
    print(
        "      Image size:",
        camera_in_use.sensor.pixel_width,
        "w",
        "*",
        camera_in_use.sensor.pixel_height,
        "h",
        "pixels",
    )
    print(
        "            Lens:",
        camera_in_use.lens.length,
        "mm",
        "(35mm equiv:",
        camera_in_use.lens.equiv_length,
        "mm)",
    )
    print(
        "   Field of View:",
        "Horizontal",
        deg_3dp(camera_in_use.lens.fov_horizontal, DEGREE_SYMBOL),
        "Vertical",
        deg_3dp(camera_in_use.lens.fov_vertical, DEGREE_SYMBOL),
    )
    print("")

    print(TextColor.white("Target parameters (calculated image)"))
    if params.local_stars_magnitude < params.target_min_magnitude:
        bNote = TextColor.red(
            "Clipped to mag", params.local_stars_magnitude, "in Hipparcos selection."
        )
    else:
        bNote = ""
    print(
        "      Brightness: mag",
        params.target_min_magnitude,
        TextColor.blue("(TargetMinMagnitude parameter)"),
        bNote,
    )
    print(
        "                  mag",
        params.target_min_magnitude - 0.2,
        "would generate fewer stars.",
    )
    print(
        "                  mag",
        params.target_min_magnitude + 0.2,
        "would generate more stars.",
    )
    print(
        " Hipparcos limit: mag",
        params.local_stars_magnitude,
        TextColor.blue("(LocalStarsMagnitude parameter)"),
    )  # Cannot exceed this value without reloading LocalStars list.
    print("")

    print(TextColor.white("Latest parameters (captured image)"))
    print(
        "   Exposure time:",
        params.tracking_exposure_seconds,
        "s",
        TextColor.blue("(TrackingExposureSeconds parameter)"),
    )
    print(
        "                 ",
        round(params.tracking_exposure_seconds / 2, 1),
        "s would capture fewer stars.",
    )
    print(
        "                 ",
        round(params.tracking_exposure_seconds * 2, 1),
        "s would capture more stars.",
    )
    print("")

    # Results of latest drift calculation.
    print(TextColor.white("Drift calculation"))
    sm_fg = OSW_TEXT_GOOD
    ltemp = len(DriftTracker.TargetStarMatchList)
    if ltemp < 1:
        sm_fg = OSW_TEXT_BAD
    elif ltemp < 10:
        sm_fg = OSW_TEXT_POOR
    print("     Star matches:", TextColor.fgbgcolor(sm_fg, TextColor.BLACK, str(ltemp)))
    if DriftTracker.dx is not None:
        print(
            "  Drift dx,dy,rot:",
            round(DriftTracker.dx, 0),
            ",",
            round(DriftTracker.dy, 0),
            ",",
            deg_3dp(DriftTracker.rotation, DEGREE_SYMBOL),
        )
    else:
        print("  Drift dx,dy,rot: NOT CALCULATED YET.")
    print("")

    print(TextColor.white("Star generation/detection"))
    # Star detection.
    print(
        "  Enhance images:",
        params.latest_tracking_filter,
        TextColor.blue("(LatestTrackingFilter parameter)"),
    )

    # Processing of the TARGET image.
    print(
        "     Target image: Loaded",
        DriftTracker.TargetImage.ImageExists(),
        DriftTracker.TargetTimeStamp,
    )
    BadThreshold = 50
    PoorThreshold = 70
    DriftTracker.TargetImage.CalculateStarSpread()  # Calculate the spread of stars in the target image.
    hs = round(DriftTracker.TargetImage.HorizontalSpread, 0)
    vs = round(DriftTracker.TargetImage.VerticalSpread, 0)
    imgs = round(DriftTracker.TargetImage.AreaSpread, 0)
    hs_fg = vs_fg = imgs_fg = (
        OSW_TEXT_GOOD  # What color to show for GOOD star spread percentages?
    )
    if hs < BadThreshold:
        hs_fg = OSW_TEXT_BAD  # Horizontal star spread is BAD.
    elif hs < PoorThreshold:
        hs_fg = OSW_TEXT_POOR  # Horizontal star spread is POOR.
    if vs < BadThreshold:
        vs_fg = OSW_TEXT_BAD  # Vertical star spread is BAD.
    elif vs < PoorThreshold:
        vs_fg = OSW_TEXT_POOR  # Vertical star spread is POOR.
    if imgs < BadThreshold:
        imgs_fg = OSW_TEXT_BAD  # Area star spread is BAD.
    elif imgs < PoorThreshold:
        imgs_fg = OSW_TEXT_POOR  # Area star spread is POOR.
    print(
        "       Star count:",
        DriftTracker.TargetImage.StarCount,
        "Spread:",
        "Horiz",
        TextColor.fgbgcolor(hs_fg, TextColor.BLACK, str(hs)),
        "%, Vert",
        TextColor.fgbgcolor(vs_fg, TextColor.BLACK, str(vs)),
        "%, Area",
        TextColor.fgbgcolor(imgs_fg, TextColor.BLACK, str(imgs)),
        "%",
    )

    # Processing of the LATEST image.
    print(
        "     Latest image: Loaded",
        DriftTracker.LatestImage.ImageExists(),
        DriftTracker.LatestTimeStamp,
    )
    DriftTracker.LatestImage.CalculateStarSpread()  # Calculate the spread of stars in the target image.
    hs = round(DriftTracker.LatestImage.HorizontalSpread, 0)
    vs = round(DriftTracker.LatestImage.VerticalSpread, 0)
    imgs = round(DriftTracker.LatestImage.AreaSpread, 0)
    hs_fg = vs_fg = imgs_fg = (
        OSW_TEXT_GOOD  # What color to show for GOOD star spread percentages?
    )
    if hs < BadThreshold:
        hs_fg = OSW_TEXT_BAD  # Horizontal star spread is BAD.
    elif hs < PoorThreshold:
        hs_fg = OSW_TEXT_POOR  # Horizontal star spread is POOR.
    if vs < BadThreshold:
        vs_fg = OSW_TEXT_BAD  # Vertical star spread is BAD.
    elif vs < PoorThreshold:
        vs_fg = OSW_TEXT_POOR  # Vertical star spread is POOR.
    if imgs < BadThreshold:
        imgs_fg = OSW_TEXT_BAD  # Area star spread is BAD.
    elif imgs < PoorThreshold:
        imgs_fg = OSW_TEXT_POOR  # Area star spread is POOR.
    print(
        "       Star count:",
        DriftTracker.LatestImage.StarCount,
        "Spread:",
        "Horiz",
        TextColor.fgbgcolor(hs_fg, TextColor.BLACK, str(hs)),
        "%, Vert",
        TextColor.fgbgcolor(vs_fg, TextColor.BLACK, str(vs)),
        "%, Area",
        TextColor.fgbgcolor(imgs_fg, TextColor.BLACK, str(imgs)),
        "%",
    )


def microcontroller_status():
    """Display information about the microcontroller and communications."""
    print(TextColor.yellow("Microcontroller status"))

    print("Board type:", params.board_type)
    if session.valid_controller_version():
        print(
            "Microcontroller program version:",
            TextColor.green(session.controller_version),
            "(good)",
        )  # We like this version.
    else:
        print(
            "Microcontroller program version:",
            TextColor.red(session.controller_version),
            "(check)",
        )  # We don't trust this version.
    print(
        "Acceptable microcontroller versions:", ACCEPTABLECONTROLLERVERSIONS
    )  # What microcontroller versions are acceptable?
    print("  This program is compatible with these microcontroller software versions.")
    print(
        "Reset PIN:", Mctl.ResetBCM
    )  # Grounding this pin will RESET the remote device. (or turn it off if microcontroller power is controlled by it).
    print("  Controls RESET / Power via the GPIO connection.")
    print(
        "Received line queue:", len(Mctl.Lines)
    )  # Number of lines received but not yet processed.
    print("  Messages received from microcontroller but not yet processed.")
    print("Write chunk size:", Mctl.WriteChunkBytes, "bytes")
    print("  Data is sent to microcontroller is packets of this size.")
    print(
        "Write chunk gap:", Mctl.WriteChunkSeconds, "s"
    )  # Seconds between chunks written to microcontroller.
    print("  Seconds between each packet sent to the microcontroller.")
    print("Current receiving line:", Mctl.InputLine)
    print("Write queue length:", len(Mctl.WriteQueue))
    print("  Messages waiting to be transmitted to the microcontroller.")
    temp = str(Mctl.LinesReceived)
    if Mctl.LinesReceived < 1:
        temp = TextColor.red(temp)  # Highlight in RED that nothing received.
    print("Lines received:", temp)
    print("  Number of messages received since last reset.")
    print("Lines sent:", Mctl.LinesSent)
    print("  Number of messages sent since last reset.")
    temp = str(Mctl.BytesReceived)
    if Mctl.BytesReceived < 1:
        temp = TextColor.red(temp)  # Highlight in RED that nothing received.
    print("Bytes received:", temp)
    print("Bytes sent", Mctl.BytesSent)
    print(
        "Monitor communications:", Mctl.PrintComms
    )  # When TRUE communication log is copied to the terminal, otherwise it's only written to the log file.
    print("LEDs active:", Mctl.LedStatus)  # LEDS on by default.
    print("  LEDs can be disabled to reduce light pollution in the dome.")
    print("UART line opened:", str(Mctl.LineOpenedTime).split(".")[0], "UTC")
    print(
        "UART Last Tx:", str(Mctl.LastTxTime).split(".")[0], "UTC"
    )  # When was data last sent?
    temp = str(Mctl.LastRxTime).split(".")[0]
    if (
        Mctl.LastRxTime is None or Mctl.LastRxTime <= Mctl.LineOpenedTime
    ):  # Nothing received.
        temp = TextColor.red(temp)  # Highlight nothing received.
    print("UART Last Rx:", temp, "UTC")  # When was data last received?
    temp = str(Mctl.RxErrors)
    if Mctl.RxErrors > 10:
        temp = TextColor.red(temp)  # Lots of errors.
    elif Mctl.RxErrors > 0:
        temp = TextColor.yellow(temp)  # A few errors.
    print("UART Rx errors:", temp)
    print(
        "Comms timeout:", Mctl.CommsTimeout, "s"
    )  # Seconds. microcontroller is restarted if no data received after this period.
    temp = str(Mctl.ForcedRestarts)
    if Mctl.ForcedRestarts > 4:
        temp = TextColor.red(temp)
    elif Mctl.ForcedRestarts > 0:
        temp = TextColor.yellow(temp)
    print(
        "Forced restarts:", temp
    )  # How many restarts have been forced by this software?
    temp = str(Mctl.RemoteRestarts)
    if Mctl.RemoteRestarts > 4:
        temp = TextColor.red(temp)
    elif Mctl.RemoteRestarts > 0:
        temp = TextColor.yellow(temp)
    print(
        "Remote restarts:", temp
    )  # How many restarts have been registered by the remote device itself?
    temp = str(Mctl.ResetAttempts)
    if Mctl.ResetAttempts > 4:
        temp = TextColor.red(temp)
    elif Mctl.ResetAttempts > 0:
        temp = TextColor.yellow(temp)
    print(
        "Reset attempts:", temp
    )  # Increment for each sequential attempt to reset communication with the remote microcontroller board.
    print(
        "Powered by USB:", Mctl.PoweredByUsb
    )  # Don't allow GPIO power pin to be used.
    if Mctl.PoweredByUsb:
        print("  The Reset pin will not be enabled.")
        print("  The microcontroller is powered via the USB connection.")
    if Mctl.DeviceFailure:
        temp = TextColor.red(str(Mctl.DeviceFailure))
    else:
        temp = str(Mctl.DeviceFailure)
    print(
        "Device failure:", temp
    )  # Set to TRUE if device seems to be irrecoverably lost.
    if Mctl.DeviceFailure:
        print("  The microcontroller is considered irrecoverably lost.")
    print(
        "Write queue prohibit:", Mctl.WriteProhibited
    )  # OK to add to the write queue.
    print("  The program will not send data to the microcontroller.")
    if (
        session.mctl_exception_count != 0
    ):  # The microcontroller has handled some exceptions.
        print("Exceptions handled:", TextColor.yellow(session.mctl_exception_count))
        print("  The microcontroller has caught some runtime exceptions.")
    else:  # No exceptions have been caught by the microcontroller.
        print("Exceptions handled:", session.mctl_exception_count)
        print("  The microcontroller has not reported any runtime exceptions.")
    print(
        "Outbound message counter:", Mctl.SendId
    )  # Incremental counter, the message number being sent to the microcontroller.


def about_camera():
    """Display information about the camera."""
    print(TextColor.yellow("About Camera"))

    print(TextColor.white(" O/S"))
    print("  camera_driver:", params.camera_driver, "(", OS_name, ")")
    print("  CameraDetected:", TextColor.booltocolor(detect_camera()))

    print(TextColor.white(" camera_handler"))
    try:
        print(
            "  camera_handler running:", TextColor.booltocolor(CameraThread.is_alive())
        )
    except:
        print("  camera_handler running:", TextColor.red("False"), "(not found)")

    print(TextColor.white(" Sensor"))
    print("  Sensor width:", sensor_in_use.pixel_width, "px")
    print("  Sensor height:", sensor_in_use.pixel_height, "px")
    print("  Max exposure:", sensor_in_use.max_exposure_seconds, "s")
    print("    The longest exposure time supported by the camera.")
    print("  Min exposure:", sensor_in_use.min_exposure_seconds, "s")
    print("    The shortest exposure time supported by the camera.")
    print("  Sensor type:", sensor_in_use.type)
    print("    Defines characteristics of the camera.")
    print("  Sensor ID:", sensor_in_use.id)
    print("  Sensor mode:", sensor_in_use.mode)
    if (
        params.camera_driver == "raspistill"
    ):  # DisableCleanup / OnChipCleanup is handled differently between raspistill and libcamera.
        print(
            "  On chip cleanup:",
            sensor_in_use.on_chip_cleanup,
            TextColor.blue("(DisableCleanup parameter)"),
        )
    else:
        print(
            "  On chip cleanup:",
            sensor_in_use.on_chip_cleanup,
            TextColor.blue("(Libcamera command template parameter)"),
        )
    print("  Infrared filter:", params.ir_filter)  # Is Infrared filter fitted?
    print("    Information only.")

    print(TextColor.white(" Lens"))
    print("  Base focal length:", lens_in_use.base_length, "mm (before converters)")
    print(
        "  Focal length:",
        lens_in_use.length,
        "mm (including converters) ",
        TextColor.blue("(Param:", params.lens_length, "mm)"),
    )
    print("  35mm equivalent focal length:", lens_in_use.equiv_length, "mm")
    print(
        "  Horizontal Field of View:",
        lens_in_use.fov_horizontal,
        DEGREE_SYMBOL,
        TextColor.blue("(Param:", params.lens_horizontal_fov, DEGREE_SYMBOL, ")"),
    )
    print(
        "  Vertical Field of View:",
        lens_in_use.fov_vertical,
        DEGREE_SYMBOL,
        TextColor.blue("(Param:", params.lens_vertical_fov, DEGREE_SYMBOL, ")"),
    )

    print("  Field of View:", lens_in_use.fov, DEGREE_SYMBOL)
    print("  Aperture:", "f", lens_in_use.aperture)
    print("    Information only.")
    print(
        "  Pollution filter:", params.pollution_filter
    )  # Is light pollution filter fitted?
    print("    Information only.")

    print(TextColor.white(" Camera"))
    if params.camera_enabled:
        print("  Camera enabled:", TextColor.green(params.camera_enabled))
        print("    Live images will be captured by the camera.")
    else:
        print("  Camera enabled:", TextColor.red(params.camera_enabled))
        print("    Images will be simulated.")
    print("  Exposure time:", camera_in_use.exposure_seconds, "s")
    print("    Used for live image capture.")
    print("  Tracking exposure time:", camera_in_use.tracking_exposure_seconds, "s")
    print("    Used for drift tracking image capture.")
    print("  Timelapse delay:", camera_in_use.timelapse_seconds, "s")
    print("    When active this is the delay between each LIGHT image captured.")
    print("  Pixels per FoV degree width:", camera_in_use.pixels_per_fov_degree_width)
    print("  Pixels per FoV degree height:", camera_in_use.pixels_per_fov_degree_height)
    print("  Pixel FoV width:", round(camera_in_use.pixel_fov_width, 4), DEGREE_SYMBOL)
    print(
        "  Pixel FoV height:", round(camera_in_use.pixel_fov_height, 4), DEGREE_SYMBOL
    )

    print(TextColor.white(" Command templates"))
    print("        Light:", params._camera_light_command)
    print("         Dark:", params._camera_dark_command)
    print("  Bias/Offset:", params._camera_bias_command)
    print("         Flat:", params._camera_flat_command)
    print("    Dark flat:", params._camera_dark_flat_command)
    print("         Auto:", params._camera_auto_command)
    print("     Tracking:", params._camera_tracking_command)
    print("   Raw switch:", params._camera_raw_switch)

    print(TextColor.white(" Camera handler"))
    print("  Fast image capture parameter:", params.fast_image_capture)
    print("    Default for regular targets.")
    print("  Fast image capture current setting:", camera_in_use.fast_image_capture)
    print("    Setting for the current target.")
    print("  Image types:")
    print(
        "    jpg:",
        camera_in_use.camera_save_jpg,
        TextColor.blue("(Param:", params.camera_save_jpg, ")"),
    )
    print(
        "    dng:",
        camera_in_use.camera_save_dng,
        TextColor.blue("(Param:", params.camera_save_dng, ")"),
    )
    print(
        "    fits:",
        camera_in_use.camera_save_fits,
        TextColor.blue("(Param:", params.camera_save_fits, ")"),
    )


def about():
    """Display version information."""
    print(TextColor.yellow("About", ProgramTitle))
    # Print timestamp.
    main_log.log("Now:", now_utc(), "UTC", terminal=True)
    # Print O/S and hardware
    main_log.log("RPi model:", RPIMODEL)
    main_log.log("RPi model number:", RPiNum)
    main_log.log("RPi OS ID:", OS_id)
    main_log.log("RPi OS name:", OS_name)
    main_log.log("RPi OS type:", OS_type)
    main_log.log("RPi OS bits:", OS_bits)
    main_log.log("RPi processor:", OS_processor)
    main_log.log("RPi systemkey:", OS_systemkey)

    for line in osCmd("cat /sys/firmware/devicetree/base/model"):
        if len(line) > 0:
            main_log.log("Firmware:", line, terminal=True)
    for line in osCmd("cat /etc/os-release"):
        if len(line) > 0:
            main_log.log("OS release:", line, terminal=True)
    for line in osCmd("cat /proc/version"):
        if len(line) > 0:
            main_log.log("OS version:", line, terminal=True)
    for line in osCmd("cat /proc/cpuinfo"):
        if len(line) > 0:
            main_log.log("CPU info:", line, terminal=True)
    for line in osCmd("vcgencmd get_mem arm"):
        if len(line) > 0:
            main_log.log("CPU memory allocation:", line, terminal=True)
    for line in osCmd("vcgencmd get_mem gpu"):
        if len(line) > 0:
            main_log.log("GPU memory allocation:", line, terminal=True)
    for line in osCmd("uptime"):
        if len(line) > 0:
            main_log.log("Uptime:", line, terminal=True)
    # Print program ID
    main_log.log(
        "Program:", ProgramTitle, terminal=True
    )  # What program name is running?
    main_log.log(
        "Program version:", VERSION, terminal=True
    )  # Print RPi software version.
    main_log.log(
        "Project root:", ProjectRoot, terminal=True
    )  # What is the project root?
    if session.valid_controller_version():
        main_log.log(
            "Microcontroller program version:",
            TextColor.green(session.controller_version),
            "(good)",
            terminal=True,
        )  # We like this version.
    else:
        main_log.log(
            "Microcontroller program version:",
            TextColor.red(session.controller_version),
            "(check)",
            terminal=True,
        )  # We don't trust this version.
    main_log.log(
        "Acceptable microcontroller versions:",
        ACCEPTABLECONTROLLERVERSIONS,
        terminal=True,
    )  # What microcontroller versions are acceptable?
    main_log.log(
        "Python version:", sys.version_info, terminal=True
    )  # What version of Python is this?
    # Print any package versions available.
    main_log.log(
        "Skyfield version:", SkyfieldVersion, terminal=True
    )  # What version of Skyfield is in use?
    main_log.log(
        "Astroalign version:", astroalign.__version__, terminal=True
    )  # What version of Astroalign is in use?
    main_log.log(
        "Numpy version:", np.__version__, terminal=True
    )  # What version of Numpy is in use?
    main_log.log(
        "Pandas version:", pandas.__version__, terminal=True
    )  # What version of pandas is in use?
    main_log.log(
        "PiDNG version:", "Unknown", terminal=True
    )  # What version of piDNG is in use?


def choose_image_types():
    """User can decide which images types to record."""
    main_log.log("ChooseImageTypes:", terminal=False)
    main_log.log(
        "Currently: Driver=",
        params.camera_driver,
        ": jpg",
        params.camera_save_jpg,
        ": dng",
        params.camera_save_dng,
        ": fits",
        params.camera_save_fits,
        terminal=False,
    )
    option = None
    AllOptions = {
        "jpg": {
            "label": "JPG only",
            "value": "jpg",
            "SaveJpg": True,
            "SaveDng": False,
            "SaveFits": False,
            "oslist": ["buster"],
            "handlers": ["raspistill"],
        },
        "dng": {
            "label": "DNG only",
            "value": "dng",
            "SaveJpg": False,
            "SaveDng": True,
            "SaveFits": False,
            "oslist": ["buster"],
            "handlers": ["raspistill"],
        },
        "jpgdng": {
            "label": "JPG & DNG",
            "value": "jpgdng",
            "SaveJpg": True,
            "SaveDng": True,
            "SaveFits": False,
            "oslist": ["buster"],
            "handlers": ["raspistill"],
        },
        "jpg": {
            "label": "JPG only",
            "value": "jpg",
            "SaveJpg": True,
            "SaveDng": False,
            "SaveFits": False,
            "oslist": ["bookworm"],
            "handlers": ["libcamera"],
        },
        "dng": {
            "label": "DNG only",
            "value": "dng",
            "SaveJpg": False,
            "SaveDng": True,
            "SaveFits": False,
            "oslist": ["bookworm"],
            "handlers": ["libcamera"],
        },
        "jpgdng": {
            "label": "JPG & DNG",
            "value": "jpgdng",
            "SaveJpg": True,
            "SaveDng": True,
            "SaveFits": False,
            "oslist": ["bookworm"],
            "handlers": ["libcamera"],
        },
        "fits": {
            "label": "FITS only",
            "value": "fits",
            "SaveJpg": False,
            "SaveDng": False,
            "SaveFits": True,
            "oslist": ["bookworm"],
            "handlers": ["pilomarfits"],
        },
        "jpgfits": {
            "label": "JPG & FITS",
            "value": "jpgfits",
            "SaveJpg": True,
            "SaveDng": False,
            "SaveFits": True,
            "oslist": ["bookworm"],
            "handlers": ["pilomarfits"],
        },
    }
    FilteredOptions = {}
    for (
        key,
        value,
    ) in (
        AllOptions.items()
    ):  # Consider all available combinations of type, OS and driver.
        if OS_name in value["oslist"]:  # Offer those supported by this OS.
            FilteredOptions[key] = value
    main_log.log("ChooseImageTypes: Offering:", FilteredOptions, terminal=False)

    option_menu = OptionMenu(
        FilteredOptions,
        "Select combination",
        titlefg=MENU_TITLE_FG,
        titlebg=MENU_TITLE_BG,
    )
    option, found = (
        option_menu.prompt()
    )  # Ask the user to select an option from the menu.
    main_log.log("ChooseImageTypes: Chose:", option, found, terminal=False)

    if found:  # A choice was made.
        params.camera_save_jpg = AllOptions[option]["SaveJpg"]
        params.camera_save_dng = AllOptions[option]["SaveDng"]
        params.camera_save_fits = AllOptions[option]["SaveFits"]
        if (
            not params.camera_driver in AllOptions[option]["handlers"]
        ):  # Need to switch handler.
            newdriver = AllOptions[option]["handlers"][0]
            main_log.log(
                "ChooseImageTypes: Switching cameradriver from",
                params.camera_driver,
                "to",
                newdriver,
                terminal=True,
            )
            params.set_camera_driver(newdriver)
        camera_in_use.set_observation_parameters(session)  # Update camera settings.
    main_log.log(
        "Finally: Driver=",
        params.camera_driver,
        ": jpg",
        camera_in_use.camera_save_jpg,
        ": dng",
        camera_in_use.camera_save_dng,
        ": fits",
        camera_in_use.camera_save_fits,
        terminal=True,
    )

    return


def choose_capture_mode():
    """User can switch between FULL and FAST capture modes."""
    option = None
    ModeOptions = {
        "full": {
            "label": "Full capture and process images.",
            "value": "full",
            "fastmode": False,
        },
        "fast": {
            "label": "Fast capture, no image processing",
            "value": "fast",
            "fastmode": True,
        },
    }
    ModeMenu = OptionMenu(
        ModeOptions, "Select capture mode", titlefg=MENU_TITLE_FG, titlebg=MENU_TITLE_BG
    )

    option, found = ModeMenu.prompt()  # Ask the user to select an option from the menu.
    if found:  # A choice was made.
        params.fast_image_capture = ModeOptions[option]["fastmode"]
        main_log.log("ChooseCaptureMode: FastImageCapture:", params.fast_image_capture)
    return


def build_keogram():
    """Build a keogram from the current LIGHT folder."""
    print(TextColor.yellow("Build keogram from current light folder"))
    camera_in_use.build_keogram()


def gpio_status():
    """Display the status of any defined GPIO pins."""
    print(TextColor.yellow("GPIO status"))
    for pin in outputpin.OutputPins:
        print(pin.Status(), pin.Name)
    for pin in inputpin.InputPins:
        print(pin.Status(), pin.Name)


def config_microstepping(slewmicrosteps, observemicrosteps):
    """Given slew and observe microstep values, change motor config."""
    main_log.log(
        "config_microstepping: Slew",
        slewmicrosteps,
        "Observe",
        observemicrosteps,
        terminal=True,
    )
    if slewmicrosteps != 1:
        print(
            "When slewing the telescope for large moves (GOTO/HOME) the motors will use",
            slewmicrosteps,
            "microsteps",
        )
    else:
        print(
            "When slewing the telescope for large moves (GOTO/HOME) the motors will use FULL steps"
        )
    if observemicrosteps != 1:
        print(
            "When the telescope is observing the motors will use",
            observemicrosteps,
            "microsteps",
        )
    else:
        print("When the telescope is observing the motors will use FULL steps.")

    # Check we're homed.
    CameraAlt, CameraAz = (
        last_reported_alt_az()
    )  # What is the last reported alt/az location of the centre of the image?
    home_alt, home_az = home_alt_az()  # Home position for camera.
    if round(CameraAlt, 1) != round(home_alt, 1) or round(CameraAz, 1) != round(
        home_az, 1
    ):  # Camera is not at home position.
        main_log.log(
            "config_microstepping: The camera needs to be HOMED before changing microstepping.",
            terminal=True,
            level="warning",
        )
        return

    # Set parameters.
    if slewmicrosteps != observemicrosteps:
        params.slew_enabled = True  # Allow SLEW moves to be faster than OBSERVE moves.
    else:
        params.slew_enabled = (
            False  # SLEW and OBSERVE moves use the same microstepping values.
        )
    params.azimuth_microstep_ratio = (
        observemicrosteps  # 1 = Full steps, 2 = 1/2 steps, 4 = 1/4 steps, etc.
    )
    params.azimuth_slew_microstep_ratio = (
        slewmicrosteps  # 1 = Full steps, 2 = 1/2 steps, 4 = 1/4 steps, etc.
    )
    params.altitude_microstep_ratio = (
        observemicrosteps  # 1 = Full steps, 2 = 1/2 steps, 4 = 1/4 steps, etc.
    )
    params.altitude_slew_microstep_ratio = (
        slewmicrosteps  # 1 = Full steps, 2 = 1/2 steps, 4 = 1/4 steps, etc.
    )

    if slewmicrosteps == 1 or observemicrosteps == 1:
        if slewmicrosteps == 1:
            print("Slew moves will use FULL STEPS.")
        if observemicrosteps == 1:
            print("Observation moves will use FULL STEPS.")
        print("NOTE: FULL STEPS are fast, but noisy.")
        print(
            "      Increasing microstepping values slows the telescope down, but gives quieter and smoother motion."
        )

    # Flag restart required.
    params.require_restart = True  # Flag that the parameters are nolonger safe until the program is restarted.
    restart_required()  # Warn the user that the software now needs to be restarted.

    # Save parameters.
    print(TextColor.yellow("Saving parameters..."))
    params.save_attributes(
        params.param_filename
    )  # Write current operating parameters back to disc.
    print(TextColor.yellow("Done."))


def microstepping_1_1():
    print(TextColor.yellow("No microstepping"))
    config_microstepping(slewmicrosteps=1, observemicrosteps=1)


def microstepping_2_2():
    print(TextColor.yellow("Slew 1/2 microsteps, Observe 1/2 microsteps."))
    config_microstepping(slewmicrosteps=2, observemicrosteps=2)


def microstepping_4_4():
    print(TextColor.yellow("Slew 1/4 microsteps, Observe 1/4 microsteps."))
    config_microstepping(slewmicrosteps=4, observemicrosteps=4)


def microstepping_1_2():
    print(TextColor.yellow("Slew full steps, Observe 1/2 microsteps."))
    config_microstepping(slewmicrosteps=1, observemicrosteps=2)


def microstepping_1_4():
    print(TextColor.yellow("Slew full steps, Observe 1/4 microsteps."))
    config_microstepping(slewmicrosteps=1, observemicrosteps=4)


def microstepping_2_4():
    print(TextColor.yellow("Slew 1/2 microsteps, Observe 1/4 microsteps."))
    config_microstepping(slewmicrosteps=2, observemicrosteps=4)


def microstepping_4_8():
    print(TextColor.yellow("Slew 1/4 microsteps, Observe 1/8 microsteps."))
    config_microstepping(slewmicrosteps=4, observemicrosteps=8)


# Create menu structure.

StepMenuOptions = {
    "show_motor_status": {"label": "About motors", "call": show_motor_status},
    "microstepping_1_1": {"label": "No microstepping", "call": microstepping_1_1},
    "microstepping_2_2": {"label": "Slew 1/2, Observe 1/2", "call": microstepping_2_2},
    "microstepping_4_4": {"label": "Slew 1/4, Observe 1/4", "call": microstepping_4_4},
    "microstepping_1_2": {"label": "Slew full, Observe 1/2", "call": microstepping_1_2},
    "microstepping_1_4": {"label": "Slew full, Observe 1/4", "call": microstepping_1_4},
    "microstepping_2_4": {"label": "Slew 1/2, Observe 1/4", "call": microstepping_2_4},
    "microstepping_4_8": {"label": "Slew 1/4, Observe 1/8", "call": microstepping_4_8},
}
StepMenu = ProcedureMenu(
    StepMenuOptions,
    "Microstepping options",
    titlefg=MENU_TITLE_FG,
    titlebg=MENU_TITLE_BG,
)

MotorMenuOptions = {
    "show_motor_status": {"label": "About motors", "call": show_motor_status},
    "HomeAllMotors": {"label": "Home all motors", "call": home_position},
    "TuneAzimuth": {"label": "Tune azimuth position", "call": tune_position_azimuth},
    "TuneAltitude": {"label": "Tune altitude position", "call": tune_position_altitude},
    "AzimuthAngle": {"label": "Move azimuth to angle", "call": azimuth_angle},
    "AltitudeAngle": {"label": "Move altitude to angle", "call": altitude_angle},
    "ExerciseAzimuth": {
        "label": "Exercise azimuth motor",
        "call": exercise_motor_azimuth,
    },
    "ExerciseAltitude": {
        "label": "Exercise altitude motor",
        "call": exercise_motor_altitude,
    },
    "MicrosteppingOptions": {"label": "Microstepping options", "call": StepMenu},
    "ZipMotorStatusLog": {
        "label": "Zip motor status log",
        "call": zip_motor_status_log,
    },
    "StopAllMotors": {"label": "Stop all motors", "call": stop_motors},
}
MotorMenu = ProcedureMenu(
    MotorMenuOptions, "Motor tools menu", titlefg=MENU_TITLE_FG, titlebg=MENU_TITLE_BG
)


def lens16mm():
    """Set 16mm lens parameters."""
    main_log.log("Lens16mm: 16mm lens selected.", terminal=True)
    params.lens_length = 16.0
    params.lens_horizontal_fov = 21.8
    params.lens_vertical_fov = 16.4
    # Flag restart required. The camera objects need to be renewed.
    params.require_restart = True  # Flag that the parameters are nolonger safe until the program is restarted.
    restart_required()  # Warn the user that the software now needs to be restarted.


def lens50mm():
    """Set 50mm lens parameters."""
    main_log.log("Lens50mm: 50mm lens selected.", terminal=True)
    params.lens_length = 50.0
    params.lens_horizontal_fov = 7.0
    params.lens_vertical_fov = 5.2
    # Flag restart required. The camera objects need to be renewed.
    params.require_restart = True  # Flag that the parameters are nolonger safe until the program is restarted.
    restart_required()  # Warn the user that the software now needs to be restarted.


LensOptions = {
    "16mm": {"label": "16mm", "call": lens16mm},
    "50mm": {"label": "50mm", "call": lens50mm},
}

LensMenu = ProcedureMenu(
    LensOptions, "Lens options", titlefg=MENU_TITLE_FG, titlebg=MENU_TITLE_BG
)

CameraMenuOptions = {
    "AboutCamera": {"label": "About camera", "call": about_camera},
    "ChooseImageTypes": {"label": "Choose image types", "call": choose_image_types},
    "ChooseCaptureMode": {"label": "Choose capture mode", "call": choose_capture_mode},
    "start_camera_thread": {
        "label": "Start camera thread",
        "call": start_camera_thread,
    },
    "StopCameraThread": {"label": "Stop camera thread", "call": shutdown_camera},
    "SensorCleanupOff": {"label": "Sensor cleanup off", "call": disable_cleanup},
    "SensorCleanupOn": {"label": "Sensor cleanup on", "call": enable_cleanup},
    "AutoDetectCamera": {"label": "Auto detect camera", "call": auto_detect_camera},
    "ChooseLens": {"label": "Choose lens", "call": LensMenu},
    "CalibrateFov": {"label": "Calibrate FoV", "call": calibrate_fov_menu},
    "ProcessImageFiles": {"label": "Process image files", "call": process_image_files},
    "BuildKeogram": {"label": "Build keogram", "call": build_keogram},
    "EnableCamera": {"label": "Enable camera", "call": enable_camera},
    "DisableCamera": {"label": "Disable camera", "call": disable_camera},
}

CameraMenu = ProcedureMenu(
    CameraMenuOptions, "Camera tools menu", titlefg=MENU_TITLE_FG, titlebg=MENU_TITLE_BG
)

MctlMenuOptions = {
    "MicrocontrollerStatus": {
        "label": "About motorcontroller",
        "call": microcontroller_status,
    },
    "restart_microcontroller": {
        "label": "Restart microcontroller",
        "call": restart_microcontroller,
    },
    "StartMessage": {"label": "Start message handler", "call": menu_start_message},
    "shutdown_message": {
        "label": "Shutdown message handler",
        "call": menu_shutdown_message,
    },
    "FlushCommandQueue": {"label": "Flush command queue", "call": flush_command_queue},
    "ZipCommsLog": {"label": "Zip comms log", "call": zip_comms_log},
    "MonitorComms": {"label": "Monitor communication", "call": monitor_comms},
    "microcontroller_leds_on": {
        "label": "Microcontroller LEDs on",
        "call": microcontroller_leds_on,
    },
    "microcontroller_leds_off": {
        "label": "Microcontroller LEDs off",
        "call": microcontroller_leds_off,
    },
    "MicrocontrollerPowerOn": {
        "label": "Microcontroller GPIO power ON",
        "call": Mctl.PowerOn,
    },
    "MicrocontrollerPowerOff": {
        "label": "Microcontroller GPIO power OFF",
        "call": Mctl.PowerOff,
    },
}
MctlMenu = ProcedureMenu(
    MctlMenuOptions,
    "Microcontroller tools menu",
    titlefg=MENU_TITLE_FG,
    titlebg=MENU_TITLE_BG,
)

MiscMenuOptions = {
    "About": {"label": "About system", "call": about},
    "show_parameters": {"label": "Show parameters", "call": show_parameters},
    "edit_parameters": {"label": "Edit parameters", "call": edit_parameters},
    "tracking_status": {"label": "Tracking status", "call": tracking_status},
    "SetLocalTZ": {"label": "Set local timezone", "call": define_local_tz},
    "edit_target_history": {
        "label": "Edit target history",
        "call": edit_target_history,
    },
    "ShowFolderStructure": {
        "label": "Show folder structure",
        "call": FolderHandler.print_folder_list,
    },
    "DebugModeOn": {"label": "Debug mode on", "call": debug_mode_on},
    "DebugModeOff": {"label": "Debug mode off", "call": debug_mode_off},
    "ChooseColorScheme": {
        "label": "Choose color scheme",
        "call": params.choose_color_scheme,
    },
    "ChooseColor": {"label": "Choose individual color", "call": params.choose_color},
}
MiscMenu = ProcedureMenu(
    MiscMenuOptions,
    "Miscellaneous tools menu",
    titlefg=MENU_TITLE_FG,
    titlebg=MENU_TITLE_BG,
)

DevMenuOptions = {
    "SatellitePasses": {"label": "Satellite passes", "call": menu_satellite_passes},
    "LatestTrackingFilter": {
        "label": "Set Latest Tracking filter",
        "call": select_latest_filter,
    },
    "TestLatestFilter": {
        "label": "Test Latest Tracking filter",
        "call": test_latest_filter,
    },
    "RecheckDisc": {"label": "Check / remount storage", "call": recheck_disc},
    "ZipTrajectories": {"label": "Zip trajectory log", "call": zip_trajectory_log},
    "GpioStatus": {"label": "GPIO status", "call": gpio_status},
    "show_parameters": {"label": "Show parameters", "call": show_parameters},
    "edit_parameters": {"label": "Edit parameters", "call": edit_parameters},
}

DevMenu = ProcedureMenu(
    DevMenuOptions,
    "Development tools menu",
    titlefg=MENU_TITLE_FG,
    titlebg=MENU_TITLE_BG,
)

MainMenuOptions = {
    "SelectTarget": {"label": "Select target", "bold": True, "call": select_target},
    "BeginObservation": {
        "label": "Begin observation",
        "bold": True,
        "call": begin_observation,
        "postcall": flag_observation_end,
    },
    "program_status": {"label": "Status", "call": program_status},
    "GotoTarget": {"label": "GOTO target", "call": menu_go_to_target},
    "HomeAllMotors": {"label": "Home all motors", "call": home_position},
    "SetExposureTime": {"label": "Set exposure time", "call": menu_set_exposure_time},
    "SetLightBatchSize": {"label": "Set light batch size", "call": menu_set_batch_size},
    "set_control_batch_size": {
        "label": "Set control batch size",
        "call": menu_set_control_batch_size,
    },
    "TakeDarkFrameSet": {"label": "Take dark frame set", "call": menu_dark_set},
    "TakeFlatFrameSet": {"label": "Take flat frame set", "call": menu_flat_set},
    "TakeBiasFrameSet": {"label": "Take bias/offset frame set", "call": menu_bias_set},
    "TakeDarkFlatFrameSet": {
        "label": "Take dark flat frame set",
        "call": menu_dark_flat_set,
    },
    "TakePreviewFrames": {"label": "Take preview frames", "call": menu_manual_preview},
    "TakeAutoFrames": {"label": "Take auto frames", "call": menu_auto_photo},
    "SetTimelapseDelay": {"label": "Set timelapse delay", "call": set_timelapse_delay},
    "ScanForMeteors": {"label": "Scan images for meteors", "call": scan_for_meteors},
    "MotorMenu": {"label": "Motor tools", "call": MotorMenu},
    "MicrocontrollerMenu": {"label": "Microcontroller tools", "call": MctlMenu},
    "CameraMenu": {"label": "Camera tools", "call": CameraMenu},
    "MiscMenu": {"label": "Miscellaneous tools", "call": MiscMenu},
    "DevMenu": {"label": "Development tools", "call": DevMenu},
}

program_status()  # Show current situation of the telescope and target at startup.
MainMenu = ProcedureMenu(
    MainMenuOptions, "Pilomar main menu", titlefg=MENU_TITLE_FG, titlebg=MENU_TITLE_BG
)

# Run main menu.
while True:
    MainMenu.prompt()
    if ask_yes_no("Do you really want to shut down? [y/N]", default=False):
        break  # OK to quit.

# Cleanup.
main_log.log("MAIN: CLOSING", terminal=False)

flag_observation_end()  # Make sure that any observation is stopped. This prevents further trajectories being sent to the microcontroller.

# Offer to return camera to the HOME position.
CameraAlt, CameraAz = (
    last_reported_alt_az()
)  # What is the last reported alt/az location of the centre of the image?
home_alt, home_az = home_alt_az()  # Home position for camera.
if round(CameraAlt, 1) != round(home_alt, 1) or round(CameraAz, 1) != round(
    home_az, 1
):  # Camera is not at home position.
    print(
        TextColor.yellow(
            "The camera is currently at " + az_alt_text(CameraAz, CameraAlt)
        )
    )
    if params.require_restart:
        answer = (
            False  # Do not offer to move the motors if parameter file has been changed.
        )
    else:
        answer = ask_yes_no(
            "Would you like to home the camera before powering off? [y/N]", False
        )
    if answer:
        print("Returning camera to home position...")
        home_position()
        # Use the last reported camera position.
        CameraAlt, CameraAz = (
            last_reported_alt_az()
        )  # What is the alt/az location of the centre of the image?
        if round(CameraAlt, 1) != round(home_alt, 1) or round(CameraAz, 1) != round(
            home_az, 1
        ):  # Camera is not at home position.
            TextColor.text_box(
                [
                    "The camera did not successfully return to the home position.",
                    "The camera is left at " + az_alt_text(CameraAz, CameraAlt),
                ],
                fg=TextColor.WHITE,
                bg=TextColor.RED,
            )
        else:
            print(TextColor.yellow("Camera homed successfully."))
    else:
        TextColor.text_box(
            [
                "The camera will resume from its current position when restarted.",
                'To home the camera now, use the "home" option on the Camera Tools menu.',
            ]
        )
else:  # Camera is already at home position.
    print("Camera is currently in home position. No homing needed.")

# Store final position and total runtime of motors.
for i in MotorControls:
    i.StoreRecoveryAngle(
        force=True
    )  # Write the final position of each motor to disc. Force the write.

print(" ")
shutdown_camera()  # Terminate the camera_handler thread.
print(" ")
print(TextColor.yellow("Stopping microcontroller communication..."))
Mctl.Reset(
    planned=True
)  # For safety, reset the microcontroller. This prevents the stepper motors triggering due to out-of-date instructions.
main_log.log("Stopping microcontroller communication: send STOP...")
UartControlQueue.put("stop")  # Tell MctlThread to shut down.
if MctlThread.is_alive():
    main_log.log("Stopping microcontroller communication: wait for end...")
    MctlThread.join()  # Wait MctlThread to complete.
else:
    main_log.log("Stopping microcontroller communication: MctlThread already stopped.")
print(" ")
shutdown_message()  # Terminate the MessageHandler thread.
print(" ")
main_log.log("Powering off the microcontroller.", terminal=False)
Mctl.ResetPin.Off()  # Turn off the microcontroller power. Turn off regardless of GPIO/USB connectivity.
GPIOCleanup()  # Reset the GPIO state.
print(TextColor.yellow("Saving parameters..."))
params.save_attributes(
    params.param_filename
)  # Write current operating parameters back to disc.
print(TextColor.yellow("Done."))
print(
    TextColor.fgbgcolor(
        TextColor.BLACK, TextColor.GREEN, " PILOMAR COMPLETE. OK TO SHUTDOWN "
    )
)
main_log.log("MAIN: PROGRAM COMPLETE", terminal=False)
