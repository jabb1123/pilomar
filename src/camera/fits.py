#!/usr/bin/python

# This software is published under the GNU General Public License v3.0.
# Also respect any pre-existing terms of any components that this incorporates.

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

# -------------------------------------------------------------------------------------------------------------------
# This script is intended to create a simple 'libcamera-still' type of interface to the Picamera2 library.
# - The difference is that this can save raw sensor data as .fits format files instead of .dng files.
# - It does not replicate all the functions of libcamera-still or libcamera-jpg, only those needed for the pilomar project.
#
# Usage:
#   Instead of the command :
#        libcamera-still --output {&output} --timeout 10 --nopreview --quality 100 --width {&width} --height {&height} --denoise off --analoggain 16.0 --shutter {&shutter}
#   You can call this with :
#        python3 pilomarfits.py --output {&output} --width {&width} --height (&height} --denoise off --awbgains 1.0,1.0 --shutter {&shutter} --metadata --tuning-file imx477_noir.json
#
#   It outputs 3 files.
#      {&output} as .jpg             - Contains an unprocessed color jpeg image.
#      {&output} as .fits            - Contains raw bayer data in fits format.
#      {&output} as .json            - Contains a json dictionary of metadata associated with the image, camera and call.
#
# Supported parameters are :
#   --output        Output filename. Use the .jpg filename.
#   --width         Image width. Use the sensor maximum width.
#   --height        Image height. Use the sensor maximum height.
#   --denoise       'off' to remove on-chip image cleaning.
#   --awbgains      red,blue gains for color image.
#   --shutter       Exposure time in microseconds.
#   --metadata      When specified the .json file of metadata is saved.
#   --raw           Will save .fits file.
#   --tuning-file   imx477.json (default if not specified)
#                   imx477_noir.json (recommended if infrared cutoff filter has been removed)
#   Any other parameters will be ignored (many are not needed for just dumping raw bayer data from the sensor).
#
# Dependencies :
#   You must have astropy installed on your raspberry pi. It provides the 'fits' libraries needed.
#        sudo apt install python3-astropy
# -------------------------------------------------------------------------------------------------------------------

VERSION = "0.1.0"

import os

from utils.time_funcs import now_utc

os.environ["LIBCAMERA_LOG_LEVELS"] = "3"  # Report errors only.
import json
import sys
import time

import cv2
import numpy as np
from astropy.io import fits
from picamera2 import Picamera2, libcamera

StartupTime = now_utc()  # When did program start?


def color_gain(array, red=1.0, green=1.0, blue=1.0):
    """Given a BGR image array, boost just the RED, GREEN and BLUE channels by different factors."""
    array[:, :, 2] = array[:, :, 2] * red  # red channel
    array[:, :, 1] = array[:, :, 1] * green  # green channel
    array[:, :, 0] = array[:, :, 0] * blue  # blue channel
    return array


# Set up the camera.
config = picam2.create_still_configuration(
    raw={"format": sensor_format, "size": (width, height)}
)
picam2.configure(config)
picam2.set_controls(ControlsToApply)
picam2.start()
# Allow the camera time to start up and accept config and control settings. It takes time!
time.sleep(2)  # Wait for control propogation.
# Extract bayer data from the sensor.
CaptureStartTime = now_utc()  # When did capture begin?
CameraRequest = picam2.capture_request()
rawarray12 = CameraRequest.make_array("raw")
RequestMetadata = CameraRequest.get_metadata()
CaptureEndTime = now_utc()  # When did capture complete?
data32 = rawarray12.view(np.uint16).astype(
    np.float32
)  # Unpack from 12bit to 16bit. Result is left shifted 4 bits.
CameraRequest.release()  # Release the camera buffers, otherwise we may run out of memory.
data32 = data32 / (2**4)  # Scale back down to 12 bit.

# Create FITS image file.
RawSaveStartTime = now_utc()  # When did FITS file generation start?
if "--raw" in ArgumentDict:
    hdulist = fits.HDUList()
    hdulist.append(
        fits.ImageHDU(data=cv2.flip(data32, 0), name="SCI")
    )  # Flip vertically.
    hdulist.writeto(fitsfilename, overwrite=True)  # Save fits.
RawSaveEndTime = now_utc()  # When did FITS file generation finish?

# Now convert to colour. Debayer the matrix.
BayerStartTime = now_utc()  # When did debayer start?
bayer = data32.clip(0, (2**16 - 1)).astype(np.uint16)
colour = cv2.cvtColor(bayer, cv2.COLOR_BAYER_BGGR2BGR)  # Demosaic.
if redgain != 1.0 or bluegain != 1.0:
    colour = color_gain(
        colour, red=redgain, blue=bluegain
    )  # Boost channels to get more realistic colours.
colour = colour.clip(0, (2**16 - 1)) / (2**4)  # Convert from 12bit values to 8 bit.
BayerEndTime = now_utc()  # When did debayer end?

# Always save the .jpg file.
JpgStartTime = now_utc()  # When did jpg save start?
cv2.imwrite(jpgfilename, colour, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
JpgEndTime = now_utc()  # When did jpg save end?

# Finally write metadata if needed.
MetaStartTime = now_utc()  # When did metadata save start?
if "--metadata" in ArgumentDict:  # Extract and save metadata.
    metadata = RequestMetadata
    metadata["program"] = sys.argv[0]  # Program name.
    metadata["pilomarfits_version"] = VERSION
    metadata["pilomar_set_controls"] = ControlsToApply
    metadata["pilomar_runtime_args"] = ArgumentDict
    metadata["pilomar_control_dict"] = ControlDict
    metadata["jpgfilename"] = jpgfilename
    metadata["fitsfilename"] = fitsfilename
    metadata["jsonfilename"] = jsonfilename
    metadata["StartupTime"] = StartupTime  # When did program start?
    metadata["CaptureDuration"] = (
        CaptureEndTime - CaptureStartTime
    ).total_seconds()  # How long did capture take?
    metadata["RawSaveDuration"] = (
        RawSaveEndTime - RawSaveStartTime
    ).total_seconds()  # How long did FITS file generation take?
    metadata["BayerDuration"] = (
        BayerEndTime - BayerStartTime
    ).total_seconds()  # How long did debayer take?
    metadata["JpgDuration"] = (
        JpgEndTime - JpgStartTime
    ).total_seconds()  # How long did jpg save take?
    temp = now_utc()
    metadata["ProcessDuration"] = (
        temp - StartupTime
    ).total_seconds()  # How long did the entire process take up to here?
    metadata["CompletionTime"] = temp  # When did generation end?
    with open(jsonfilename, "w", encoding="UTF-8") as f:  # Dump as json to disc.
        json.dump(
            metadata, f, indent=4, default=str
        )  # Save the updated dictionary back to disc.

exit()
