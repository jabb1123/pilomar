#!/usr/bin/env python3
"""FITS file handling for astronomical image capture.

This module provides utilities for capturing raw sensor data and saving
it in FITS format, along with support for metadata, EXIF tags, and
various image processing operations.

Requires: astropy, picamera2, opencv-python, numpy
"""

# This software is published under the GNU General Public License v3.0.

__version__ = '0.2.1'

import json
import math
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
from astropy.io import fits
from picamera2 import Picamera2

from pilomar.core.time_utils import now_utc


def date_to_jd(input_datetime: datetime) -> float:
    """Convert a datetime to Julian Day.
    
    Based upon: https://gist.github.com/jiffyclub/1294443
    
    Algorithm from 'Practical Astronomy with your Calculator or Spreadsheet',
    4th ed., Duffet-Smith and Zwart, 2011.
    
    Args:
        input_datetime: Datetime object (can be timezone aware)
        
    Returns:
        Julian Day as float
        
    Example:
        >>> date_to_jd(datetime(1985, 2, 17, 6, 0, 0))
        2446113.75
    """
    year = input_datetime.year
    month = input_datetime.month
    day = input_datetime.day
    time_offset = (
        float(input_datetime.hour) + 
        float(input_datetime.minute / 60) + 
        float(input_datetime.second / 3600)
    ) / 24
    day = float(day) + time_offset
    
    if month == 1 or month == 2:
        yearp = year - 1
        monthp = month + 12
    else:
        yearp = year
        monthp = month
    
    # Check relation to October 15, 1582 (start of Gregorian calendar)
    if ((year < 1582) or
        (year == 1582 and month < 10) or
        (year == 1582 and month == 10 and day < 15)):
        # Before start of Gregorian calendar
        B = 0
    else:
        # After start of Gregorian calendar
        A = math.trunc(yearp / 100.)
        B = 2 - A + math.trunc(A / 4.)
        
    if yearp < 0:
        C = math.trunc((365.25 * yearp) - 0.75)
    else:
        C = math.trunc(365.25 * yearp)
        
    D = math.trunc(30.6001 * (monthp + 1))
    
    jd = B + C + D + day + 1720994.5
    return jd


def color_gain(
    array: np.ndarray,
    red: float = 1.0,
    green: float = 1.0,
    blue: float = 1.0
) -> np.ndarray:
    """Apply color channel gains to a BGR image array.
    
    Args:
        array: BGR image array
        red: Red channel gain multiplier
        green: Green channel gain multiplier
        blue: Blue channel gain multiplier
        
    Returns:
        Modified array with gains applied
    """
    array[:, :, 2] = array[:, :, 2] * red    # Red channel
    array[:, :, 1] = array[:, :, 1] * green  # Green channel
    array[:, :, 0] = array[:, :, 0] * blue   # Blue channel
    return array


def analog_gain(array: np.ndarray, gain: float = 1.0) -> np.ndarray:
    """Apply analog gain to all color channels.
    
    Args:
        array: Image array
        gain: Gain multiplier to apply to all channels
        
    Returns:
        Modified array with gain applied
    """
    array[:, :, :] = array[:, :, :] * gain
    return array


def histogram_array(input_array: np.ndarray, bins: int = 256) -> np.ndarray:
    """Calculate histogram of values in an array.
    
    Args:
        input_array: Array to analyze
        bins: Number of bins for histogram
        
    Returns:
        Histogram array
    """
    histogram, _ = np.histogram(input_array, bins=bins, range=(0, bins - 1))
    return histogram


def normalize_array(
    input_array: np.ndarray,
    min_out: float,
    max_out: float,
    min_in: Optional[float] = None,
    max_in: Optional[float] = None
) -> np.ndarray:
    """Normalize array values to a specified range.
    
    Args:
        input_array: Array to normalize
        min_out: Minimum value in output
        max_out: Maximum value in output
        min_in: Optional forced minimum input value
        max_in: Optional forced maximum input value
        
    Returns:
        Normalized array
    """
    input_array = input_array.astype(np.float32)
    c_min = np.min(input_array)
    c_max = np.max(input_array)

    if min_in is not None:
        c_min = min(c_min, min_in)
    if max_in is not None:
        c_max = max(c_max, max_in)

    c_span = c_max - c_min

    try:
        output_array = ((max_out - min_out) * (input_array - c_min) / c_span) + min_out
    except Exception:
        # Fallback: clip instead of normalize
        output_array = np.clip(input_array.astype(np.float32), 0, max_out)

    return output_array


def rotate_image(buffer: np.ndarray, angle: int) -> np.ndarray:
    """Rotate image by specified angle.
    
    Args:
        buffer: Image buffer to rotate
        angle: Rotation angle (0, 90, 180, 270 degrees clockwise)
        
    Returns:
        Rotated image buffer
    """
    if angle == 90:
        buffer = cv2.rotate(buffer, cv2.ROTATE_90_CLOCKWISE)
    elif angle == 180:
        buffer = cv2.rotate(buffer, cv2.ROTATE_180)
    elif angle == 270:
        buffer = cv2.rotate(buffer, cv2.ROTATE_90_COUNTERCLOCKWISE)
    elif angle == 0:
        pass  # No rotation
    return buffer


def arg_split(argline: str) -> List[str]:
    """Split argument line on spaces, preserving quoted strings.
    
    Handles both single and double quotes, and ignores comments after '#'.
    
    Args:
        argline: Command line argument string
        
    Returns:
        List of argument tokens
        
    Examples:
        >>> arg_split("--argname arg1 'arg 2' arg3")
        ['--argname', 'arg1', 'arg 2', 'arg3']
        >>> arg_split("--argname arg1 # comment")
        ['--argname', 'arg1']
    """
    argline = argline.strip('\n').strip()
    result = []
    in_quote = False
    quote_chars = ['"', "'"]
    current_arg = ''
    
    for c in argline:
        if c in quote_chars:
            in_quote = not in_quote
            if in_quote:
                quote_chars = [c]  # Only same quote can terminate
            continue
        if not in_quote and c == '#':
            break  # Comment starts
        if not in_quote and c == ' ':
            if current_arg:
                result.append(current_arg)
                current_arg = ''
                quote_chars = ['"', "'"]
        else:
            current_arg += c
    
    if current_arg:
        result.append(current_arg)
    
    return result


def parse_args(
    arg_list: List[str],
    arg_dict: Optional[Dict] = None
) -> Dict[str, Dict]:
    """Parse command line arguments into a dictionary.
    
    Args:
        arg_list: List of command line arguments
        arg_dict: Optional initial dictionary to update
        
    Returns:
        Dictionary mapping argument names to their values
        Format: {'--arg': {'all': 'val1,val2', 'list': ['val1', 'val2']}}
    """
    if arg_dict is None:
        arg_dict = {}
    
    current_arg = ''
    opt_list = []
    
    for raw_arg in arg_list:
        arg = raw_arg.strip().strip('\n')
        if len(arg) < 1:
            continue
        
        if arg.startswith('--'):
            if arg in arg_dict:
                continue  # Already exists, don't merge
            current_arg = arg
            arg_dict[arg] = {'all': '', 'list': []}
            opt_list = []
        else:
            if current_arg:
                opt_list.append(arg)
                arg_dict[current_arg]['list'] = opt_list
                cs = arg_dict[current_arg]['all']
                if cs:
                    cs += ','
                cs += arg.strip()
                while ',,' in cs:
                    cs = cs.replace(',,', ',')
                arg_dict[current_arg]['all'] = cs
    
    return arg_dict


class FitsCapture:
    """FITS image capture handler for Raspberry Pi cameras.
    
    This class wraps the Picamera2 library to capture raw sensor data
    and save it in FITS format with proper header metadata.
    
    Attributes:
        logger: Optional logger instance for recording operations
        verbose: Whether to print log messages to terminal
        debug: Whether to enable debug analysis
    """

    # Control parameter definitions
    CONTROL_DICT = {
        '--shutter': {
            'attribute': 'ExposureTime',
            'default': 5000,
            'type': int
        },
        '--gain': {
            'attribute': 'AnalogueGain',
            'default': 1.0,
            'type': float
        },
        '--analoggain': {
            'attribute': 'AnalogueGain',
            'default': 1.0,
            'type': float
        },
    }

    def __init__(
        self,
        logger: Any = None,
        verbose: bool = False,
        debug: bool = False
    ):
        """Initialize FITS capture handler.
        
        Args:
            logger: Optional logger with .log() method
            verbose: Show log messages on terminal
            debug: Enable extra analysis during processing
        """
        self.logger = logger
        self.verbose = verbose
        self.debug = debug
        self.camera = None
        self.camera_model = "IMX477"
        self.processing_data = {}

        if PICAMERA2_AVAILABLE:
            self._detect_camera()

    def _detect_camera(self) -> None:
        """Detect attached camera model."""
        try:
            global_info = Picamera2.global_camera_info()
            for cam in global_info:
                self.camera_model = cam.get('Model', 'IMX477').upper()
        except Exception:
            pass

    def log(self, *args, **kwargs) -> None:
        """Log a message if logger is available."""
        if self.logger:
            terminal = kwargs.pop('terminal', self.verbose)
            self.logger.log(*args, terminal=terminal, **kwargs)

    def build_controls(
        self,
        arguments: Dict[str, Dict],
        shutter_specified: bool = False
    ) -> Dict[str, Any]:
        """Build camera control settings from arguments.
        
        Args:
            arguments: Parsed argument dictionary
            shutter_specified: Whether shutter speed was explicitly set
            
        Returns:
            Dictionary of camera controls to apply
        """
        controls = {}

        for arg_name, element_dict in arguments.items():
            if arg_name in self.CONTROL_DICT:
                ctrl_entry = self.CONTROL_DICT[arg_name]
                value = ctrl_entry['default']
                dtype = ctrl_entry['type']

                if 'list' in element_dict and element_dict['list']:
                    option = element_dict['list'][0]
                    if dtype == float:
                        value = float(option)
                    elif dtype == int:
                        value = int(float(option))
                    else:
                        value = option

                controls[ctrl_entry['attribute']] = value

        # Noise reduction off
        controls['NoiseReductionMode'] = 0

        if not shutter_specified:
            controls['AeEnable'] = True
        else:
            controls['HdrMode'] = 0
            controls['AeEnable'] = False
            controls['AwbEnable'] = False
            if 'ColourGains' not in controls:
                controls['ColourGains'] = (1.0, 1.0)
            if 'AnalogueGain' not in controls:
                controls['AnalogueGain'] = 1.0

        return controls

    def capture(
        self,
        output_filename: str,
        width: int = 4056,
        height: int = 3040,
        shutter: Optional[int] = None,
        analog_gain: float = 1.0,
        red_gain: float = 1.0,
        blue_gain: float = 1.0,
        quality: int = 100,
        tuning_file: str = "imx477.json",
        image_type: str = 'LIGHT',
        rotation: int = 0,
        save_fits: bool = True,
        save_numpy: bool = False,
        save_metadata: bool = False,
        fits_tags: Optional[Dict] = None,
        exif_tags: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Capture an image and save in various formats.
        
        Args:
            output_filename: Base output filename (extension replaced as needed)
            width: Image width in pixels
            height: Image height in pixels
            shutter: Exposure time in microseconds (None for auto)
            analog_gain: Analog gain multiplier
            red_gain: Red channel gain
            blue_gain: Blue channel gain
            quality: JPEG quality (1-100)
            tuning_file: Camera tuning file name
            image_type: Type of image (LIGHT, DARK, BIAS, etc.)
            rotation: Rotation angle (0, 90, 180, 270)
            save_fits: Save FITS file
            save_numpy: Save numpy array file
            save_metadata: Save JSON metadata file
            fits_tags: Additional FITS header tags
            exif_tags: Additional EXIF tags for JPEG
            
        Returns:
            Dictionary of capture metadata and timing information
        """
        if not PICAMERA2_AVAILABLE:
            raise RuntimeError("Picamera2 not available")
        if save_fits and not ASTROPY_AVAILABLE:
            raise RuntimeError("Astropy not available for FITS output")

        startup_time = now_utc()

        # Prepare filenames
        jpg_filename = output_filename.replace('.fits', '.jpg')
        fits_filename = jpg_filename.replace('.jpg', '.fits')
        numpy_filename = jpg_filename.replace('.jpg', '.npy')
        json_filename = jpg_filename.replace('.jpg', '.json')

        # Build controls
        controls = {
            'NoiseReductionMode': 0,
            'HdrMode': 0,
            'AeEnable': shutter is None,
        }
        if shutter is not None:
            controls['ExposureTime'] = shutter
            controls['AwbEnable'] = False
            controls['ColourGains'] = (1.0, 1.0)
            controls['AnalogueGain'] = analog_gain

        # Initialize camera
        tuning = Picamera2.load_tuning_file(tuning_file)
        self.camera = Picamera2(tuning=tuning)
        properties = self.camera.camera_properties

        config = self.camera.create_still_configuration(
            raw={'format': 'SBGGR12', 'size': (width, height)}
        )
        self.camera.configure(config)
        self.camera.set_controls(controls)
        self.camera.start()

        time.sleep(2)  # Allow camera to stabilize

        # Capture
        capture_start = now_utc()
        request = self.camera.capture_request()
        raw_array = request.make_array('raw')
        metadata = request.get_metadata()
        capture_end = now_utc()
        capture_midpoint = capture_start + (capture_end - capture_start) / 2
        request.release()

        # Unpack 12-bit data from 8-bit stream
        raw_12bit = raw_array.view(np.uint16).astype(np.uint16)
        data_32 = raw_12bit.astype(np.float32) / (2 ** 4)

        # Save FITS
        fits_save_start = now_utc()
        if save_fits:
            self._save_fits(
                fits_filename, data_32, metadata, controls,
                image_type, analog_gain, red_gain, blue_gain,
                capture_start, capture_midpoint, fits_tags
            )
        fits_save_end = now_utc()

        # Debayer to color
        bayer_start = now_utc()
        bayer = data_32.astype(np.uint16)
        color = cv2.cvtColor(bayer, cv2.COLOR_BAYER_BGGR2BGR)
        color = color[:, :-8, :]  # Remove dead columns

        # Apply gains
        if red_gain != 1.0 or blue_gain != 1.0:
            color = color_gain(color, red=red_gain, blue=blue_gain)
        if analog_gain != 1.0:
            color = analog_gain(color, gain=analog_gain)
        bayer_end = now_utc()

        # Save numpy
        numpy_start = now_utc()
        if save_numpy:
            np.save(numpy_filename, color.astype(np.uint16))
        numpy_end = now_utc()

        # Normalize to 8-bit for JPEG
        color = color.clip(0, 4095)
        color = np.rint(normalize_array(color, 0, 255, min_in=0))

        # Rotate if needed
        if rotation:
            color = rotate_image(color, rotation % 360)

        # Save JPEG
        jpg_start = now_utc()
        cv2.imwrite(jpg_filename, color, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        jpg_end = now_utc()

        # Add EXIF tags if provided
        exif_start = now_utc()
        if exif_tags:
            try:
                from .image import PilomarImage
                pim = PilomarImage(name='camera', logger=self.logger)
                pim.add_exif_tags(jpg_filename, exif_tags)
            except ImportError:
                pass
        exif_end = now_utc()

        # Build result metadata
        result = {
            'startup_time': startup_time,
            'capture_start': capture_start,
            'capture_end': capture_end,
            'capture_midpoint': capture_midpoint,
            'capture_duration': (capture_end - capture_start).total_seconds(),
            'fits_save_duration': (fits_save_end - fits_save_start).total_seconds(),
            'bayer_duration': (bayer_end - bayer_start).total_seconds(),
            'numpy_duration': (numpy_end - numpy_start).total_seconds(),
            'jpg_duration': (jpg_end - jpg_start).total_seconds(),
            'exif_duration': (exif_end - exif_start).total_seconds(),
            'jpg_filename': jpg_filename,
            'fits_filename': fits_filename if save_fits else None,
            'numpy_filename': numpy_filename if save_numpy else None,
            'camera_metadata': metadata,
            'camera_properties': properties,
        }

        # Save metadata
        if save_metadata:
            result['json_filename'] = json_filename
            with open(json_filename, 'w') as f:
                json.dump(result, f, indent=4, default=str)

        return result

    def _save_fits(
        self,
        filename: str,
        data: np.ndarray,
        metadata: Dict,
        controls: Dict,
        image_type: str,
        analog_gain: float,
        red_gain: float,
        blue_gain: float,
        capture_start: datetime,
        capture_midpoint: datetime,
        extra_tags: Optional[Dict] = None
    ) -> None:
        """Save data as FITS file with header tags.
        
        Args:
            filename: Output FITS filename
            data: Image data array
            metadata: Camera capture metadata
            controls: Applied camera controls
            image_type: Image type string
            analog_gain: Applied analog gain
            red_gain: Applied red gain
            blue_gain: Applied blue gain
            capture_start: Capture start time
            capture_midpoint: Capture midpoint time
            extra_tags: Additional header tags
        """
        tags = {}

        # Exposure time
        exp_time = controls.get('ExposureTime')
        if exp_time is None:
            exp_time = metadata.get('ExposureTime')
        if exp_time is not None:
            exp_time_sec = float(exp_time) / 1.0e6
            tags['EXPTIME'] = {'value': exp_time_sec, 'comment': 'Exposure time (s)'}
            tags['EXPOSURE'] = {'value': exp_time_sec, 'comment': 'Exposure time (s)'}

        tags['XBINNING'] = {'value': 1.0, 'comment': 'No X binning'}
        tags['YBINNING'] = {'value': 1.0, 'comment': 'No Y binning'}
        tags['ROWORDER'] = {'value': 'TOP-DOWN', 'comment': 'Image row order'}
        tags['BAYERPAT'] = {'value': 'RGGB', 'comment': 'Bayer pattern'}

        sensor_temp = metadata.get('SensorTemperature')
        if sensor_temp is not None:
            tags['CCD-TEMP'] = {'value': sensor_temp, 'comment': 'Sensor temperature (C)'}

        tags['IMAGETYP'] = {'value': image_type, 'comment': 'Image type'}
        tags['XPIXSZ'] = {'value': 3.76, 'comment': 'X pixel size (um)'}
        tags['YPIXSZ'] = {'value': 3.76, 'comment': 'Y pixel size (um)'}
        tags['GAIN'] = {'value': analog_gain, 'comment': 'Analog gain'}
        tags['RGAIN'] = {'value': red_gain, 'comment': 'Red gain'}
        tags['BGAIN'] = {'value': blue_gain, 'comment': 'Blue gain'}
        tags['INSTRUME'] = {'value': self.camera_model, 'comment': 'Camera model'}
        tags['TIMESYS'] = {'value': 'UTC', 'comment': 'Time system'}
        tags['SWCREATE'] = {'value': f'PILOMARFITS {__version__}', 'comment': 'Creation software'}
        tags['JD'] = {'value': date_to_jd(capture_start), 'comment': 'Julian date'}
        tags['DATE-OBS'] = {'value': capture_start.isoformat(), 'comment': 'Start of exposure'}
        tags['MIDPOINT'] = {'value': capture_midpoint.isoformat(), 'comment': 'Midpoint of exposure'}

        # Merge extra tags
        if extra_tags:
            tags.update(extra_tags)

        # Write FITS file
        hdu_list = fits.HDUList()
        hdu_list.append(fits.ImageHDU(data=cv2.flip(data, 0), name='SCI'))

        header = hdu_list[0].header
        for key, details in tags.items():
            header.append((key, details['value'], details['comment']), end=True)

        hdu_list.writeto(filename, overwrite=True)

    def close(self) -> None:
        """Close camera connection."""
        if self.camera:
            self.camera.close()
            self.camera = None


def main():
    """Command-line interface for FITS capture."""
    os.environ["LIBCAMERA_LOG_LEVELS"] = "3"  # Errors only
    
    args = parse_args(sys.argv[1:])
    
    verbose = '--verbose' in args
    debug = '--debug' in args
    
    # Get parameters
    output = args.get('--output', {'all': 'output.jpg'})['all']
    width = int(args.get('--width', {'list': ['4056']})['list'][0])
    height = int(args.get('--height', {'list': ['3040']})['list'][0])
    
    shutter = None
    if '--shutter' in args:
        shutter = int(args['--shutter']['list'][0])
    
    analog_gain = 1.0
    if '--gain' in args:
        analog_gain = float(args['--gain']['all'])
    if '--analoggain' in args:
        analog_gain = float(args['--analoggain']['all'])
    
    red_gain, blue_gain = 1.0, 1.0
    if '--awbgains' in args:
        gains = args['--awbgains']['all'].split(',')
        red_gain = float(gains[0])
        blue_gain = float(gains[1])
    
    tuning = args.get('--tuning-file', {'list': ['imx477.json']})['list'][0]
    image_type = args.get('--image-type', {'list': ['LIGHT']})['list'][0].upper()
    rotation = int(args.get('--rotate', {'all': '0'})['all']) if '--rotate' in args else 0
    
    capture = FitsCapture(verbose=verbose, debug=debug)
    
    try:
        result = capture.capture(
            output_filename=output,
            width=width,
            height=height,
            shutter=shutter,
            analog_gain=analog_gain,
            red_gain=red_gain,
            blue_gain=blue_gain,
            tuning_file=tuning,
            image_type=image_type,
            rotation=rotation,
            save_fits='--raw' in args,
            save_numpy='--numpy-file' in args,
            save_metadata='--metadata' in args,
        )
        
        if verbose:
            print(f"Capture complete: {result['jpg_filename']}")
            print(f"  Duration: {result['capture_duration']:.3f}s")
    finally:
        capture.close()


if __name__ == '__main__':
    main()
