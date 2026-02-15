#!/usr/bin/env python3
"""Keogram builder for creating time-lapse image strips."""

# This software is published under the GNU General Public License v3.0.


import cv2
import numpy as np

from pilomar.imaging.image import PilomarImage


class PilomarKeogram:
    """Simple keogram builder.

    A keogram is a time-compressed image created by extracting vertical strips
    from a series of images and combining them horizontally.

    Usage:
        keo = PilomarKeogram('my_keogram', width=1920, height=1080)
        keo.extract(image1)
        keo.extract(image2)
        keo.extract(image3)
        keo.build_image_buffer()
        # Now manipulate keo.keogram as needed
        keo.save_file('keogram.jpg')
    """

    def __init__(self, name: str, width: int, height: int):
        """Initialize a keogram builder.

        Args:
            name: A name for this instance
            width: Width of target output image
            height: Height of target output image
        """
        self.name = name
        self.width = width
        self.height = height
        self.keogram_pixels = None  # List of sampled data
        self.sample_count = 0  # Number of sample strips captured
        self.keogram = PilomarImage(name="keogram", logger=None)

    def extract(self, image_handler: "PilomarImage") -> None:
        """Extract data for a keogram from an image.

        Extracts a vertical band from the image, finds the brightest pixel
        in each row, and appends these pixels to the accumulated data.

        Args:
            image_handler: A PilomarImage instance containing the source image
        """
        source_width = image_handler.get_width()
        source_height = image_handler.get_height()

        # Take middle 10% of image
        band = int(source_width * 0.10)
        work_buf = image_handler.image_buffer.copy()

        x_start = int((source_width - band) / 2)
        x_end = int((source_width + band) / 2)
        work_buf = work_buf[:, x_start:x_end, :]  # Extract sample band

        gray_image = cv2.cvtColor(work_buf, cv2.COLOR_BGR2GRAY)
        n_width = work_buf.shape[1]

        column = []  # Column of pixel data to extract
        for r in range(source_height):
            max_brightness = 0
            max_pixel = [0, 0, 0]

            for c in range(n_width):
                brightness = gray_image[r][c]
                if brightness > max_brightness:
                    max_brightness = brightness
                    max_pixel = work_buf[r, c, :]

            column.append([[max_pixel[0], max_pixel[1], max_pixel[2]]])

        if self.keogram_pixels is None:
            self.keogram_pixels = np.array(column).astype(np.uint8)
        else:
            self.keogram_pixels = np.append(self.keogram_pixels, column, axis=1)

        self.sample_count += 1

    def build_image_buffer(self) -> None:
        """Build the final keogram image from accumulated data.

        Resizes the collected pixel data to the target dimensions and
        loads it into the keogram image buffer.
        """
        write_buffer = cv2.resize(
            self.keogram_pixels.astype(np.uint8),
            (self.width, self.height),
            interpolation=cv2.INTER_AREA,
        )
        self.keogram.load_buffer(write_buffer)

    def save_file(self, filename: str) -> None:
        """Export and save the keogram as a file.

        Args:
            filename: Path to save the keogram image
        """
        self.keogram.save_file(filename)
