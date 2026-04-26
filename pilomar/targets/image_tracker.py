"""Image Tracker for Pilomar telescope system.

Uses OpenCV and AstroAlign packages to measure drift between
images for auto-correction and basic image tracking.

Copyright: GNU General Public License v3.0
"""

import math
from collections.abc import Callable
from datetime import datetime

import astroalign

from pilomar.core.base import AttributeMaster
from pilomar.core.time_utils import now_hms, now_utc_str


class ImageTracker(AttributeMaster):
    """Measures drift between images using OpenCV and AstroAlign.

    This class compares target images with latest camera captures to
    measure positional drift. Used for auto-correction of telescope
    position and basic image tracking.

    Attributes:
        tracking_interval: Seconds between tracking checks.
        prepared_images: Count of images processed.
        target_min_magnitude: Minimum star magnitude for target images.
        dx: Measured X drift in pixels.
        dy: Measured Y drift in pixels.
        zone_list: Search zones for large master maps.
    """

    def __init__(
        self,
        logger=None,
        image_class=None,
        folder_handler=None,
        camera_window=None,
        drift_window=None,
        dev_window=None,
        parameters=None,
        now_func: Callable | None = None,
        timestamp_func: Callable | None = None,
    ):
        """Initialize image tracker.

        Args:
            logger: LogFile instance for logging.
            image_class: PilomarImage class for image handling.
            folder_handler: FolderHandler for file paths.
            camera_window: Window for camera messages.
            drift_window: Window for drift messages.
            dev_window: Window for development messages.
            parameters: Parameters object with tracking settings.
            now_func: Function returning current UTC datetime.
            timestamp_func: Function returning timestamp string.
        """
        super().__init__(now_func=now_func)
        self.set_logger(logger)

        self._image_class = image_class
        self._folder_handler = folder_handler
        self._camera_window = camera_window
        self._drift_window = drift_window
        self._dev_window = dev_window
        self._parameters = parameters
        self._timestamp_func = now_utc_str if timestamp_func is None else timestamp_func

        # Get tracking parameters
        if parameters:
            self.tracking_interval = getattr(parameters, "TrackingInterval", 300)
            self.target_min_magnitude = getattr(parameters, "TargetMinMagnitude", 6.0)
        else:
            self.tracking_interval = 300
            self.target_min_magnitude = 6.0

        self.prepared_images = 0
        self.reset()

    def reset(self):
        """Reset image cache and related data."""
        self.log("ImageTracker.reset: Begin", terminal=False)

        # Reset Target Image
        if self._image_class:
            self.target_image = self._image_class(name="target", logger=self.logger)
        else:
            self.target_image = None
        self.target_timestamp = None
        self.target_star_match_list = []
        self.target_star_count = 0

        # Reset Master Image (Master target map)
        if self._image_class:
            self.master_image = self._image_class(name="master", logger=self.logger)
        else:
            self.master_image = None
        self.master_timestamp = None
        self.master_star_match_list = []
        self.master_star_count = 0

        # Reset Latest Image
        if self._image_class:
            self.latest_image = self._image_class(name="latest", logger=self.logger)
        else:
            self.latest_image = None
        self.latest_timestamp = None
        self.latest_star_match_list = []
        self.latest_star_count = 0

        # Drift measurements
        self.dx = None
        self.dy = None

        # Search zones
        self.zone_list = []

        self.log("ImageTracker.reset: End", terminal=False)

    def set_master_image(
        self,
        cv_image_buffer,
        starcount: int | None = None,
        starlist: list | None = None,
        timestamp=None,
        min_magnitude: float | None = None,
    ):
        """Register a new master target reference image.

        Args:
            cv_image_buffer: OpenCV image buffer.
            starcount: Pre-calculated star count (optional).
            starlist: Pre-calculated star list (optional).
            timestamp: Image timestamp (defaults to now).
            min_magnitude: Minimum star magnitude for selection.
        """
        self.log("ImageTracker.set_master_image: Begin", terminal=False)
        self.log(
            f"ImageTracker.set_master_image: Received buffer type {type(cv_image_buffer)}",
            terminal=False,
        )

        if cv_image_buffer is None:
            self.log(
                "ImageTracker.set_master_image: Received None buffer. Nothing set.",
                terminal=False,
            )
            return

        if timestamp is None:
            timestamp = self._now_func()
        self.master_timestamp = timestamp

        if self.master_image:
            self.master_image.load_buffer(cv_image_buffer)
            self.log(
                f"ImageTracker.set_master_image: Loaded image {self.master_image.get_dimensions()}",
                terminal=False,
            )
            self.master_image.change_type("grayscale")

            # Measure contrast
            contrast_m, contrast_s = self.master_image.measure_contrast()
            self.log(
                f"ImageTracker.set_master_image: Contrast {contrast_m}, {contrast_s}",
                terminal=False,
            )

        self.dx = None
        self.dy = None
        self.master_star_match_list = []

        if min_magnitude is not None:
            self.log(
                f"ImageTracker.set_master_image: Setting min_magnitude to {min_magnitude}",
                terminal=False,
            )
            self.target_min_magnitude = min_magnitude

        self.log("ImageTracker.set_master_image: Registered new target image", terminal=False)

        # Calculate stars if not provided
        if self.master_image:
            if starcount is None or starlist is None:
                self.log(
                    "ImageTracker.set_master_image: Calculating stars from image",
                    terminal=False,
                )
                self.master_image.count_stars()
            else:
                self.master_image.star_count = starcount
                self.master_image.star_list = starlist

            self.log(
                f"ImageTracker.set_master_image: Counted {self.master_image.star_count} stars",
                terminal=False,
            )

            # Save reference image
            if self._folder_handler:
                filename = self._folder_handler.prep_file(
                    "tracking", f"MasterTrackingImage_{self._timestamp_func()}.jpg"
                )
                if self._camera_window:
                    now_hms_val = now_hms()
                    self._camera_window.print(f"{now_hms_val} {filename.split('/')[-1]}")
                self.master_image.save_file(filename)

        # Calculate transformation
        self.log("ImageTracker.set_master_image: Calling search_master_image", terminal=False)
        result = self.search_master_image()
        self.log(
            f"ImageTracker.set_master_image: search_master_image returned {result}",
            terminal=False,
        )

    def set_target_image(self, cv_image_buffer, timestamp=None, zone: int = 0):
        """Register a new target reference image for a specific zone.

        Args:
            cv_image_buffer: OpenCV image buffer.
            timestamp: Image timestamp.
            zone: Zone number for multi-zone searches.
        """
        self.log(f"ImageTracker.set_target_image: Begin: Zone {zone}", terminal=False)

        if cv_image_buffer is None:
            self.log("ImageTracker.set_target_image: Received None buffer", terminal=False)
            return

        if timestamp is None:
            timestamp = self._now_func()
        self.target_timestamp = timestamp

        if self.target_image:
            self.target_image.load_buffer(cv_image_buffer)
            self.log(
                f"ImageTracker.set_target_image: Loaded {self.target_image.get_dimensions()}",
                terminal=False,
            )
            self.target_image.change_type("grayscale")

            # Count stars
            self.target_image.count_stars()
            self.log(
                f"ImageTracker.set_target_image: Counted {self.target_image.star_count} stars",
                terminal=False,
            )

            # Save for reference
            if self._folder_handler:
                filename = self._folder_handler.prep_file(
                    "tracking",
                    f"TargetTrackingImage_{str(zone).zfill(3)}_{self._timestamp_func()}.jpg",
                )
                if self._camera_window:
                    now_hms_val = now_hms()
                    self._camera_window.print(f"{now_hms_val} {filename.split('/')[-1]}")
                self.target_image.save_file(filename)

    def set_latest_image(self, cv_image_buffer, timestamp=None):
        """Register the latest camera image for drift calculation.

        Args:
            cv_image_buffer: OpenCV image buffer from camera.
            timestamp: Image capture timestamp.
        """
        self.log("ImageTracker.set_latest_image: Begin", terminal=False)

        if cv_image_buffer is None:
            self.log("ImageTracker.set_latest_image: Received None buffer", terminal=False)
            return

        if timestamp is None:
            timestamp = self._now_func()

        uts = self._timestamp_func()
        self.latest_timestamp = None  # Clear until prepared

        if self.latest_image:
            self.latest_image.load_buffer(cv_image_buffer)
            self.log(
                f"ImageTracker.set_latest_image: Loaded {self.latest_image.get_dimensions()}",
                terminal=False,
            )

            # Measure contrast
            contrast_m, contrast_s = self.latest_image.measure_contrast()
            self.log(
                f"ImageTracker.set_latest_image: Contrast {contrast_m}, {contrast_s}",
                terminal=False,
            )

            self.latest_image.change_type("grayscale")

            # Apply filter script if configured
            if self._parameters:
                filter_name = getattr(self._parameters, "LatestTrackingFilter", None)
                if filter_name:
                    if self.latest_image.run_filter_script(
                        scriptname=filter_name, window=self._dev_window
                    ):
                        self.log(
                            f"ImageTracker.set_latest_image: Filter {filter_name} success",
                            terminal=False,
                        )
                    else:
                        self.log(
                            f"ImageTracker.set_latest_image: Filter {filter_name} failed",
                            level="warning",
                        )

            self.latest_timestamp = timestamp
            self.latest_star_match_list = []

            # Count stars
            self.latest_image.count_stars()
            self.log(
                f"ImageTracker.set_latest_image: Counted {self.latest_image.star_count} stars",
                terminal=False,
            )

            # Save for reference
            if self._folder_handler:
                filename = self._folder_handler.prep_file(
                    "tracking", f"LatestTrackingImage_{uts}.jpg"
                )
                if self._camera_window:
                    now_hms_val = now_hms()
                    self._camera_window.print(f"{now_hms_val} {filename.split('/')[-1]}")
                self.latest_image.save_file(filename)

    def choose_search_sequence(self):
        """Calculate search zones for comparing images.

        If LatestImage and MasterImage are different sizes, creates a sequence
        of search zones starting at the center and moving outward.
        """
        self.log("ImageTracker.choose_search_sequence: Begin", terminal=False)
        self.zone_list = []

        if not self.master_image or not self.latest_image:
            self.log("ImageTracker.choose_search_sequence: Missing images", terminal=False)
            return

        master_width = self.master_image.get_width()
        master_height = self.master_image.get_height()
        latest_width = self.latest_image.get_width()
        latest_height = self.latest_image.get_height()

        master_center_x = master_width // 2
        master_center_y = master_height // 2

        # Get zone shift from parameters
        search_shift = 0.33
        if self._parameters:
            search_shift = getattr(self._parameters, "TrackingZoneShift", 0.33)

        x_shift = int(latest_width * search_shift)
        y_shift = int(latest_height * search_shift)

        self.log(
            f"ImageTracker.choose_search_sequence: Master {master_width}x{master_height}, "
            f"Latest {latest_width}x{latest_height}",
            terminal=False,
        )

        zone_center_x = master_center_x
        col_count = 0

        while col_count <= 10:  # Safety limit
            zone_center_y = master_center_y
            row_count = 0

            while row_count <= 10:  # Safety limit
                dist = math.sqrt(
                    (zone_center_x - master_center_x) ** 2 + (zone_center_y - master_center_y) ** 2
                )

                # Create mirror zones radiating from center
                mirror_list = [[zone_center_x, zone_center_y]]
                if row_count > 0:
                    mirror_list.append([zone_center_x, master_height - zone_center_y])
                if col_count > 0:
                    mirror_list.append([master_width - zone_center_x, zone_center_y])
                if row_count > 0 and col_count > 0:
                    mirror_list.append(
                        [master_width - zone_center_x, master_height - zone_center_y]
                    )

                for zone in mirror_list:
                    search_entry = [
                        dist,  # Distance to center
                        latest_width,  # Zone width
                        latest_height,  # Zone height
                        zone[0],  # Zone center X
                        zone[1],  # Zone center Y
                        zone[0] - master_center_x,  # X offset
                        zone[1] - master_center_y,  # Y offset
                        zone[0] - latest_width // 2,  # X start
                        zone[1] - latest_height // 2,  # Y start
                        "",  # Filename placeholder
                    ]
                    self.zone_list.append(search_entry)

                zone_center_y -= y_shift
                if zone_center_y - latest_height // 2 < 0:
                    break
                row_count += 1

            zone_center_x -= x_shift
            if zone_center_x - latest_width // 2 < 0:
                break
            col_count += 1

        self.zone_list = sorted(self.zone_list)

        # Assign filenames
        for i, entry in enumerate(self.zone_list):
            if self._folder_handler:
                entry[9] = self._folder_handler.prep_file(
                    "tracking",
                    f"ZoneTarget_{str(i).zfill(3)}_{self._timestamp_func()}.jpg",
                )

        self.log(
            "ImageTracker.choose_search_sequence: ",
            f"{len(self.zone_list)} zones",
            terminal=False,
        )

    def create_target_zone_buffer(self, zone: int):
        """Extract a zone buffer from the master map.

        Args:
            zone: Zone index to extract.

        Returns:
            OpenCV image buffer for the zone, or None on error.
        """
        self.log(f"ImageTracker.create_target_zone_buffer: Zone {zone}", terminal=False)

        if zone < 0 or zone >= len(self.zone_list):
            self.log(
                f"ImageTracker.create_target_zone_buffer: Invalid zone {zone}",
                level="error",
                terminal=True,
            )
            return None

        entry = self.zone_list[zone]
        zone_width = entry[1]
        zone_height = entry[2]
        x_start = entry[7]
        y_start = entry[8]

        # Extract zone from master
        if self.master_image and self.master_image.image_buffer is not None:
            image_buffer = self.master_image.image_buffer[
                y_start : y_start + zone_height, x_start : x_start + zone_width, ...
            ]
            self.log(
                "ImageTracker.create_target_zone_buffer: ",
                f"Created {image_buffer.shape}",
                terminal=False,
            )
            return image_buffer

        return None

    def search_master_image(self) -> bool:
        """Find transformation between target and latest images.

        Uses astroalign.find_transform to compare images and measure
        any positional shift.

        Returns:
            True if transformation found, False otherwise.
        """
        self.choose_search_sequence()
        num_zones = len(self.zone_list)
        self.log(
            f"ImageTracker.search_master_image: {num_zones} zones available",
            terminal=False,
        )

        result = False
        self.dx = None
        self.dy = None
        good_calculations = 0
        total_true_dx = 0
        total_true_dy = 0

        # Get match threshold from parameters
        target_matches = 3
        if self._parameters:
            target_matches = getattr(self._parameters, "TrackingZoneMatches", 3)

        for i, entry in enumerate(self.zone_list):
            drift_offset_x = entry[5]
            drift_offset_y = entry[6]

            zone_buffer = self.create_target_zone_buffer(zone=i)
            if zone_buffer is None:
                continue

            self.set_target_image(zone_buffer, timestamp=self.latest_timestamp, zone=i)

            try:
                if (
                    self.target_image
                    and self.latest_image
                    and self.target_image.image_buffer is not None
                    and self.latest_image.image_buffer is not None
                ):
                    transform, (lsl, tsl) = astroalign.find_transform(
                        source=self.latest_image.image_buffer,
                        target=self.target_image.image_buffer,
                    )

                    self.target_star_match_list = tsl
                    self.latest_star_match_list = lsl

                    self.log(
                        f"ImageTracker.search_master_image: Zone {i}: "
                        f"{len(tsl)} target stars, {len(lsl)} latest stars",
                        terminal=False,
                    )

                    dx = int(-1 * transform.translation[0])
                    true_dx = dx - drift_offset_x
                    dy = int(-1 * transform.translation[1])
                    true_dy = dy - drift_offset_y

                    good_calculations += 1
                    total_true_dx += true_dx
                    total_true_dy += true_dy

                    self.log(
                        f"ImageTracker.search_master_image: Zone {i}: "
                        f"dx={dx}, dy={dy}, true_dx={true_dx}, true_dy={true_dy}",
                        terminal=False,
                    )

                    self.save_tracking_analysis(zone=i)
                    result = True

            except Exception as e:  # pylint: disable=broad-except
                self.log(
                    f"ImageTracker.search_master_image: Zone {i}: Error: {e}",
                    terminal=False,
                )

            if good_calculations >= target_matches:
                self.log(
                    f"ImageTracker.search_master_image: {good_calculations} matches, stopping",
                    terminal=False,
                )
                break

        if good_calculations > 0:
            self.dx = int(round(total_true_dx / good_calculations, 0))
            self.dy = int(round(total_true_dy / good_calculations, 0))
        else:
            self.dx = self.dy = None

        if self._drift_window:
            now_hms = datetime.utcnow().strftime("%H:%M:%S")
            self._drift_window.print(f"{now_hms} Matched {good_calculations} zones.")

        self.log(
            f"ImageTracker.search_master_image: Average drift x={self.dx}, y={self.dy} "
            f"across {good_calculations} alignments",
            terminal=False,
        )

        return result

    def save_tracking_analysis(self, zone: int = 0):
        """Save visual analysis of tracking matches.

        Args:
            zone: Zone number being analyzed.
        """
        self.log("ImageTracker.save_tracking_analysis: Begin", terminal=False)
        # Full implementation would create annotated image showing matches
        # This is a placeholder for the complex visualization code
        self.log(f"ImageTracker.save_tracking_analysis: Zone {zone} (stub)", terminal=False)

    def valid_star_values(self, entry) -> bool:
        """Check if star entry has valid coordinate values.

        Args:
            entry: Star entry from match list.

        Returns:
            True if entry has valid float/int coordinates.
        """
        if len(entry) < 2:
            return False
        if isinstance(entry[0], (float, int)) and isinstance(entry[1], (float, int)):
            return True
        self.log(f"ImageTracker.valid_star_values: Invalid entry {entry}", terminal=True)
        return False
