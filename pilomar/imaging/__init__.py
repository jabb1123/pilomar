#!/usr/bin/env python3
"""Imaging module for Pilomar astronomical image processing.

This module provides classes for image manipulation, processing, and
visualization of astronomical images.

Classes:
    PilomarImage: Main image processing class
    PilomarKeogram: Keogram (time-lapse strip) builder
    FitsCapture: FITS format image capture
    DataSet: Data set for graphing
    DataPoint: Single data point for graphing
    FdObject: Force-directed graph object
    FdEdge: Force-directed graph edge

Functions:
    date_to_jd: Convert datetime to Julian Day
    normalize_array: Normalize array values to range
    color_gain: Apply color channel gains
    analog_gain: Apply analog gain to image
"""

from .data_types import DataSet, DataPoint, FdObject, FdEdge
from .image import PilomarImage
from .keogram import PilomarKeogram

# FITS support (requires astropy and picamera2)
from .fits import (
    FitsCapture,
    date_to_jd,
    normalize_array,
    color_gain,
    analog_gain,
    rotate_image,
)

__all__ = [
    "PilomarImage",
    "PilomarKeogram",
    "DataSet",
    "DataPoint",
    "FdObject",
    "FdEdge",
    # FITS (when available)
    "FitsCapture",
    "date_to_jd",
    "normalize_array",
    "color_gain",
    "analog_gain",
    "rotate_image",
]
