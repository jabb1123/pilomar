# ///////////////////////////////////////////////////////////////////////////////////
# Image processing (OpenCV)
# ///////////////////////////////////////////////////////////////////////////////////

import math

import numpy as np
from camera.image import pilomarimage
from utils.files.folder import FolderHandler
from utils.params import AttributeMaster, Parameters
from utils.time_funcs import now_hour_minute_sec, now_utc, utc_time_stamp


class ImageTracker(AttributeMaster):
    """ImageTracker uses OpenCV and AstroAlign packages to measure the drift of the
    stars between images. This may be useful for autocorrecting position or basic image tracking.
    """

    def __init__(self, logger=None, parameters: Parameters = None):
        self.set_logger(
            logger
        )  # Inherited from attributemaster: Set up references to chosen logger (or disable if no logger defined).
        self.parameters: Parameters = parameters

        self.target_image = pilomarimage(
            name="target", logger=CamLog
        )  # This will be the opencv image buffer.
        self.target_time_stamp = None  # UTC timestamp for image buffer.

        self.latest_image = pilomarimage(
            name="latest", logger=CamLog
        )  # This will be the opencv image buffer.
        self.latest_time_stamp = None  # UTC timestamp for the image buffer.

        self.tracking_interval = (
            parameters.tracking_interval
        )  # Check target tracking every nnn seconds.

        self.dx = None  # Measured delta-x between images.
        self.dy = None  # Measured delta-y between images.
        self.rotation = None  # Measured rotation between images.
        self.measureddelta = None  # Total seconds between reference images.

        self.prepared_images = 0  # Incrementing counter of images handled.
        self.target_star_match_list = (
            []
        )  # List of star locations in TargetImage (calculated by FindTransform method)
        self.latest_star_match_list = (
            []
        )  # List of star locations in LatestImage (calculated by FindTransform method)
        self.target_min_magnitude = (
            self.parameters.target_min_magnitude
        )  # The actual minimum star magnitude finally selected for the target image.

    def tracking_age(self):  # In pilomarimage
        """Return age of latest tracking image in seconds."""
        td = None
        if self.latest_time_stamp is not None:
            td = int((now_utc() - self.latest_time_stamp).total_seconds())
        return td

    def reset(self):
        """Reset image cache and related data."""
        self.log("ImageTracker.Reset: Begin", terminal=False)
        self.target_image.Clear()
        self.target_time_stamp = None
        self.target_star_match_list = []
        self.latest_image.Clear()
        self.latest_time_stamp = None
        self.latest_star_match_list = []
        self.latest_star_count = 0
        self.dx = None  # Measured delta-x between images.
        self.dy = None  # Measured delta-y between images.
        self.rotation = None  # Measured rotation between images.
        self.measureddelta = None  # Total seconds between reference images.
        self.log("ImageTracker.Reset: End", terminal=False)

    def set_target_image(
        self,
        cvimagebuffer,
        starcount=None,
        starlist=None,
        timestamp=None,
        min_magnitude=None,
    ):
        """This registers a new target reference image."""
        self.log("ImageTracker.SetTargetImage: Begin", terminal=False)
        self.log(
            "ImageTracker.SetTargetImage: Received image buffer type",
            str(type(cvimagebuffer)),
            terminal=False,
        )
        if isinstance(cvimagebuffer, type(None)):
            self.log(
                "ImageTracker.SetTargetImage: Received None type image buffer. Nothing set.",
                terminal=False,
            )
            return
        if (
            timestamp is None
        ):  # If we don't know the timestamp of the image, use the current clock.
            timestamp = now_utc()  # Assume current clock time.
        self.target_time_stamp = timestamp
        self.target_image.LoadBuffer(cvimagebuffer)
        self.target_image.ChangeType("grayscale")
        self.log(
            "ImageTracker.SetTargetImage: About to measure contrast.", terminal=False
        )
        contrast_m, contrast_s = (
            self.target_image.MeasureContrast()
        )  # Calculate contrast for latest image.
        self.log(
            "ImageTracker.SetTargetImage: Contrast measures",
            contrast_m,
            contrast_s,
            terminal=False,
        )
        self.log(
            "ImageTracker.SetTargetImage: Prepared image: type",
            str(type(self.target_image.ImageBuffer)),
            "shape",
            self.target_image.GetHeight(),
            "x",
            self.target_image.GetWidth(),
            "depth",
            self.target_image.GetDepth(),
            terminal=False,
        )
        self.dx = None
        self.dy = None
        self.rotation = None  # Measured rotation between images.
        self.measureddelta = None
        self.target_star_match_list = []
        if min_magnitude is not None:
            self.log(
                "ImageTracker.SetTargetImage: Setting min_magnitude to",
                min_magnitude,
                terminal=False,
            )
            self.target_min_magnitude = min_magnitude  # The actual minimum star magnitude finally selected for the target image.
        self.log(
            "ImageTracker.SetTargetImage: registered new target image", terminal=False
        )
        if (
            starcount is None or starlist is None
        ):  # StarCount or StarList not provided, calculate one from the image instead.
            self.log(
                "ImageTracker.SetTargetImage: Did not receive StarCount or StarList. Calculating them from image.",
                terminal=False,
            )
            _, _ = self.target_image.CountStars()
        else:  # StarCount and StarList already available, just use those.
            self.log(
                "ImageTracker.SetTargetImage: Received StarCount and StarList. Not recalculating them.",
                terminal=False,
            )
            self.target_image.StarCount = starcount
            self.target_image.StarList = starlist
        self.log(
            "ImageTracker.SetTargetImage: Counted",
            self.target_image.StarCount,
            "stars.",
            terminal=False,
        )
        # No need to clean up the image. It was generated to match the standardised image already.
        # Save target image for reference.
        filename = FolderHandler.PrepFile(
            "tracking", "TargetTrackingImage_" + UtcTimeStamp() + ".jpg"
        )
        self.parameters.camera_window.print(
            now_hour_minute_sec() + " " + filename.split("/")[-1]
        )  # Note the filename that's been generated.
        self.target_image.SaveFile(filename)
        # Calculate the transformation between TARGET and LATEST images.
        self.log(
            "ImageTracker.SetTargetImage: Calling FindTransform...", terminal=False
        )
        result = (
            self.find_transform_image()
        )  # Try to calculate transform from TARGET and LATEST images.
        self.log(
            "ImageTracker.SetTargetImage: FindTransform returned " + str(result),
            terminal=False,
        )

    def find_transform_image(self):
        """Use astroalign.find_transform to calculate transform between TARGET and LATEST images.
        The target image is generated by the program and represents the star layout we expect to photograph.
        The latest image is the one captured by the camera.
        Find Transform compares the two images and decides if they match.
        It measures any shift between the two images, this can be used to correct for drift in the telescope motion.
        """
        self.log("ImageTracker.FindTransformImage: Begin", terminal=False)
        result = False
        self.dx = None
        self.dy = None
        self.rotation = None  # Measured rotation between images.
        self.measureddelta = None
        if self.target_image.ImageMissing() or self.latest_image.ImageMissing():
            pass  # No images to compare. Skip this.
        else:  # Two images available to compare.
            try:  # The transform object is a numpy structure, if the transform calculation fails you can get weird problems that I couldn't always detect cleanly.
                # So for now ignore any errors at this stage, and assume that no transform could be calculated.
                # Sometimes it returned a NoneType that I couldn't test for (numpy array peculiarity), and sometimes it returned an empty array.
                self.log(
                    "ImageTracker.FindTransformImage: TargetImage: type",
                    str(type(self.target_image.ImageBuffer)),
                    "shape",
                    self.target_image.GetHeight(),
                    "x",
                    self.target_image.GetWidth(),
                    "depth",
                    self.target_image.GetDepth(),
                    "len[0]",
                    len(self.target_image.ImageBuffer[0]),
                    "(2 = (x,y), else image)",
                    "datatype",
                    str(self.target_image.ImageBuffer.dtype),
                    terminal=False,
                )
                self.log(
                    "ImageTracker.FindTransformImage: LatestImage: type",
                    str(type(self.latest_image.ImageBuffer)),
                    "shape",
                    self.latest_image.GetHeight(),
                    "x",
                    self.latest_image.GetWidth(),
                    "depth",
                    self.latest_image.GetDepth(),
                    "len[0]",
                    len(self.latest_image.ImageBuffer[0]),
                    "(2 = (x,y), else image)",
                    "datatype",
                    str(self.latest_image.ImageBuffer.dtype),
                    terminal=False,
                )
                self.log(
                    "ImageTracker.FindTransformImage: Calling astroalign.find_transform()...",
                    terminal=False,
                )
                # If find_transform fails, it reports that the input images are not supported, but this is a generic error for ANY failure at all.
                # Check the astroalign source code online and dig deeper... I've seen where _find_sources() fails due to 'sep' package versioning problems.
                transform, (LSL, TSL) = astroalign.find_transform(
                    source=self.latest_image.ImageBuffer,
                    target=self.target_image.ImageBuffer,
                )  # In Astroalign terms, this is source=LatestImage, target=TargetImage...
                self.target_star_match_list = TSL
                self.latest_star_match_list = LSL
                self.log(
                    "ImageTracker.FindTransformImage: Received "
                    + str(type(transform))
                    + " type in return.",
                    terminal=False,
                )
                self.log(
                    "ImageTracker.FindTransformImage: Identified "
                    + str(len(TSL))
                    + " suitable stars in target image.",
                    terminal=False,
                )
                self.log(
                    "ImageTracker.FindTransformImage: TargetStarMatchList "
                    + str(TSL)
                    + ".",
                    terminal=False,
                )
                if (
                    len(TSL) > 0 and len(LSL) > 0
                ):  # During development, look at the datatype.
                    self.log(
                        "ImageTracker.FindTransformImage: Example TSL 1st entry is:",
                        str(TSL[0]),
                        terminal=False,
                    )
                    self.log(
                        "ImageTracker.FindTransformImage: Example LSL 1st entry is:",
                        str(LSL[0]),
                        terminal=False,
                    )
                self.log(
                    "ImageTracker.FindTransformImage: Identified "
                    + str(len(LSL))
                    + " suitable stars in latest image.",
                    terminal=False,
                )
                self.log(
                    "ImageTracker.FindTransformImage: LatestStarMatchList "
                    + str(LSL)
                    + ".",
                    terminal=False,
                )
                self.dx = int(
                    -1 * transform.translation[0]
                )  # X-Difference scaled back up to compensate for any image scaling.
                self.dy = int(
                    -1 * transform.translation[1]
                )  # Y-Difference scaled back up to compensate for any image scaling.
                self.rotation = round(
                    math.degrees(transform.rotation), 3
                )  # How does the image need to be rotated? Convert radians into degrees.
                self.log(
                    "ImageTracker.FindTransformImage: Calculated transform: dx="
                    + str(self.dx),
                    "dy=" + str(self.dy),
                    terminal=False,
                )
                self.log(
                    "ImageTracker.FindTransformImage: Calculated rotation:",
                    self.rotation,
                    "degrees",
                    terminal=False,
                )  # How does the image need rotating?
                self.measureddelta = (
                    self.latest_time_stamp - self.target_time_stamp
                ).total_seconds()
                result = True
            except Exception as e:
                # The most likely explanation is that the lens cap is ON, or there are not enough stars visible in the observation.
                self.log(
                    "ImageTracker.FindTransformImage: Ignored error: " + str(e),
                    terminal=False,
                )  # Enable this line if you want to see what error is being ignored!
                self.log(
                    "ImageTracker.FindTransformImage: No transform matrix created. Too few stars, lens cap on, no transformation identified or fault in astroalign and dependencies?",
                    terminal=False,
                )
                self.parameters.drift_window.print(
                    now_hour_minute_sec() + " FindTransformImage unsuccessful."
                )
        try:
            self.save_tracking_analysis()  # Create an image showing the drift analysis in terms of the actual stars.
        except Exception as e:
            print(e)  # Trap all the exception information in the main log file.
            if self.log is not None:
                self.report__exception(
                    e,
                    level="error",
                    comment="SaveTrackingAnalysis call failed in FindTransform.",
                )

        return result  # True if successful, False if failed.

    def valid_star_values(self, entry):
        """Return if 'star' value is valid. Star is an entry from a StarMatchList.
        Used by SaveTrackingAnalysis() method."""
        result = False
        if len(entry) > 1:
            if isinstance(entry[0], float) and isinstance(entry[1], float):
                result = True
            if isinstance(entry[0], int) and isinstance(entry[1], int):
                result = True
        if not result:
            self.log(
                "imagetracker.ValidStarValues(",
                entry,
                ") type",
                type(entry),
                "was unacceptable.",
                terminal=True,
            )
        return result

    def mark_location(self, image, starx, stary, color, uppertext=None, lowertext=None):
        """Write the location text next to the star.
        image parameter should be a pilomarimage() instance.
        Places the text left/right depending upon it's location in the image.
        Write 'uppertext' value above centre of star.
        Write 'lowertext' value below centre of star."""
        starx = int(starx)
        stary = int(stary)
        if starx < (image.GetWidth() / 2):
            xloc = starx + 10
        else:
            xloc = starx - 120
        yloc = stary
        loctext = "(" + str(starx) + "," + str(stary) + ")"
        image.AddText(loctext, xloc, yloc, size=0.5, color=color)
        if uppertext is not None:  # There's additional info to print above the star.
            image.AddText(uppertext, starx - 10, yloc - 20, size=0.5, color=color)
        if lowertext is not None:  # There's additional info to print above the star.
            image.AddText(lowertext, starx - 10, yloc + 30, size=0.5, color=color)
        return True

    def save_tracking_analysis(self, latestlist=None, targetlist=None):
        """Combine LATEST, TARGET star lists and show which stars were matched up in FindTransform.
        This is a debug/development feature, but shows how the drift tracking is actually interpreting the images.
        If latestlist and targetlist are provided by the calling routine those are used for markup.
        Otherwise the existing values from the imagetracker instance are used."""
        self.log("ImageTracker.SaveTrackingAnalysis: Begin", terminal=False)
        if isinstance(latestlist, type(None)):
            latestlist = self.latest_image.StarList
        if isinstance(targetlist, type(None)):
            targetlist = self.target_image.StarList
        height = SensorInUse.PixelHeight
        width = SensorInUse.PixelWidth
        NewImageBuffer = pilomarimage(
            name="trackinganalysis", logger=CamLog
        )  # Color full frame blank image.
        NewImageBuffer.New(height, width, imagetype="bgr", datatype=np.uint8)
        NewImageBuffer.FillColor(pilomarimage.BGR("Black"))
        # Match lists must be the same length.
        if (
            type(self.latest_star_match_list) != type(None)
            and type(self.target_star_match_list) != type(None)
            and len(self.latest_star_match_list) == len(self.target_star_match_list)
        ):
            # Mark the matched stars first, and an arrow linking the TARGET and LATEST locations.
            for i, lstar in enumerate(self.latest_star_match_list):
                tstar = self.target_star_match_list[i]
                lx = int(lstar[0])  # Latest star X
                ly = int(lstar[1])  # Latest star Y
                tx = int(tstar[0])  # Target star X
                ty = int(tstar[1])  # Target star Y
                if self.valid_star_values(tstar):
                    NewImageBuffer.DrawCircle(
                        tx, ty, 15, pilomarimage.BGR("Green"), thickness=2
                    )  # Green circle around matched Target stars.
                else:
                    self.log(
                        "imagetracker.SaveTrackingAnalysis: TargetStarMatchList. tstar",
                        tstar,
                        "bad values.",
                        terminal=True,
                    )
                if self.valid_star_values(lstar):
                    NewImageBuffer.DrawCircle(
                        lx, ly, 15, pilomarimage.BGR("Red"), thickness=2
                    )  # Red circle around matched Latest stars.
                else:
                    self.log(
                        "imagetracker.SaveTrackingAnalysis: LatestStarMatchList. lstar",
                        lstar,
                        "bad values.",
                        terminal=True,
                    )
                if self.valid_star_values(tstar) and self.valid_star_values(lstar):
                    NewImageBuffer.DrawLine(
                        (lx, ly),
                        (tx, ty),
                        color=pilomarimage.BGR("White"),
                        arrowpixels=20,
                    )  # Green circle around matched Target stars.
                NewImageBuffer.DrawDumbbell(
                    (lx, ly),
                    (tx, ty),
                    20,
                    pilomarimage.BGR("Red"),
                    pilomarimage.BGR("Green"),
                    pilomarimage.BGR("Yellow"),
                    arrow=True,
                )
        else:  # Lists don't agree, so don't try to map them.
            self.log(
                "imagetracker.SaveTrackingAnalysis: Conflicting length of star lists: Target",
                type(self.target_star_match_list),
                len(self.target_star_match_list),
                "vs Latest",
                type(self.latest_star_match_list),
                len(self.latest_star_match_list),
                terminal=False,
            )
            self.parameters.drift_window.print(
                now_hour_minute_sec() + " drift analysis image not done."
            )  # Note analysis not done.
        # Superimpose all the TARGET stars. (Stars we expect to see)
        if self.target_image.StarList is not None:
            for i, star in enumerate(self.target_image.StarList):
                if self.valid_star_values(star):
                    starx = int(star[0])
                    stary = int(star[1])
                    magtext = "(" + str(starx) + "," + str(stary) + ")"
                    NewImageBuffer.DrawCircle(
                        starx, stary, 5, color=pilomarimage.BGR("Green")
                    )  # Green dot for Target stars.
                    self.mark_location(
                        NewImageBuffer,
                        starx,
                        stary,
                        pilomarimage.BGR("Green"),
                        "[" + str(i) + "]",
                        magtext,
                    )  # Mark location, brightness ranking (Brightest -> Dimmest) and magnitude if known.
                else:
                    self.log(
                        "imagetracker.SaveTrackingAnalysis: TargetImage.StarList. star",
                        star,
                        "bad values.",
                        terminal=True,
                    )
        # Superimpose all the LATEST stars. (Stars we actually see)
        if self.latest_image.StarList is not None:
            for i, star in enumerate(self.latest_image.StarList):
                if self.valid_star_values(star):
                    starx = int(star[0])
                    stary = int(star[1])
                    NewImageBuffer.DrawCircle(
                        starx, stary, 5, color=pilomarimage.BGR("Red")
                    )  # Red dot for Latest stars.
                    magtext = "(" + str(starx) + "," + str(stary) + ")"
                    self.mark_location(
                        NewImageBuffer,
                        starx,
                        stary,
                        pilomarimage.BGR("Red"),
                        "[" + str(i) + "]",
                        magtext,
                    )
                else:
                    self.log(
                        "imagetracker.SaveTrackingAnalysis: LatestImage.StarList. star",
                        star,
                        "bad values.",
                        terminal=True,
                    )
        # Add key.
        timestamp = str(now_utc()).split(".")[0] + " UTC"
        NewImageBuffer.AddText(
            "Tracking Analysis " + timestamp,
            1300,
            100,
            size=2,
            color=pilomarimage.BGR("White"),
            bgcolor=pilomarimage.BGR("Black"),
            thickness=2,
        )
        NewImageBuffer.AddText(
            str(self.target_image.StarCount) + " Target stars",
            100,
            100,
            size=1,
            color=pilomarimage.BGR("Green"),
            bgcolor=pilomarimage.BGR("Black"),
        )
        NewImageBuffer.AddText(
            str(self.latest_image.StarCount) + " Latest stars",
            100,
            140,
            size=1,
            color=pilomarimage.BGR("Red"),
            bgcolor=pilomarimage.BGR("Black"),
        )
        NewImageBuffer.AddText(
            str(len(self.latest_star_match_list)) + " Matches",
            100,
            180,
            size=1,
            color=pilomarimage.BGR("Yellow"),
            bgcolor=pilomarimage.BGR("Black"),
        )
        NewImageBuffer.AddText(
            "Predict drift: " + str(self.parameters.tracking_prediction),
            100,
            240,
            size=0.5,
            color=pilomarimage.BGR("Cyan"),
            bgcolor=pilomarimage.BGR("Black"),
        )
        NewImageBuffer.AddText(
            "Match threshold: "
            + str(self.parameters.tracking_match_threshold)
            + " stars.",
            100,
            260,
            size=0.5,
            color=pilomarimage.BGR("Cyan"),
            bgcolor=pilomarimage.BGR("Black"),
        )
        NewImageBuffer.AddText(
            "Min correction: "
            + str(self.parameters.minimum_drift_correction)
            + " steps.",
            100,
            280,
            size=0.5,
            color=pilomarimage.BGR("Cyan"),
            bgcolor=pilomarimage.BGR("Black"),
        )
        NewImageBuffer.AddText(
            "Tracking interval: " + str(self.parameters.tracking_interval) + " s.",
            100,
            300,
            size=0.5,
            color=pilomarimage.BGR("Cyan"),
            bgcolor=pilomarimage.BGR("Black"),
        )
        NewImageBuffer.AddText(
            "Star radius: " + str(self.parameters.tracking_star_radius) + " px.",
            100,
            340,
            size=0.5,
            color=pilomarimage.BGR("Cyan"),
            bgcolor=pilomarimage.BGR("Black"),
        )
        NewImageBuffer.AddText(
            "Exposure: " + str(self.parameters.tracking_exposure_seconds) + " s.",
            100,
            360,
            size=0.5,
            color=pilomarimage.BGR("Cyan"),
            bgcolor=pilomarimage.BGR("Black"),
        )
        NewImageBuffer.AddText(
            "Target time: " + str(DriftTracker.TargetTimeStamp) + " UTC",
            100,
            380,
            size=0.5,
            color=pilomarimage.BGR("Cyan"),
            bgcolor=pilomarimage.BGR("Black"),
        )
        NewImageBuffer.AddText(
            "Latest time: " + str(DriftTracker.LatestTimeStamp) + " UTC",
            100,
            400,
            size=0.5,
            color=pilomarimage.BGR("Cyan"),
            bgcolor=pilomarimage.BGR("Black"),
        )
        NewImageBuffer.AddText(
            "DX: " + str(DriftTracker.dx) + " px.",
            100,
            420,
            size=0.5,
            color=pilomarimage.BGR("Cyan"),
            bgcolor=pilomarimage.BGR("Black"),
        )
        NewImageBuffer.AddText(
            "DY: " + str(DriftTracker.dy) + " px.",
            100,
            440,
            size=0.5,
            color=pilomarimage.BGR("Cyan"),
            bgcolor=pilomarimage.BGR("Black"),
        )
        NewImageBuffer.AddText(
            "Rot: " + str(DriftTracker.rotation) + " deg.",
            100,
            460,
            size=0.5,
            color=pilomarimage.BGR("Cyan"),
            bgcolor=pilomarimage.BGR("Black"),
        )
        NewImageBuffer.AddText(
            "T.Min.Mag: " + str(DriftTracker.TargetMinMagnitude),
            100,
            480,
            size=0.5,
            color=pilomarimage.BGR("Cyan"),
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
        # Save the file.
        filename = FolderHandler.PrepFile(
            "tracking", "TrackingAnalysis_" + UtcTimeStamp() + ".jpg"
        )
        self.parameters.camera_window.print(
            now_hour_minute_sec() + " " + filename.split("/")[-1]
        )  # Note the filename that's been generated.
        self.parameters.drift_window.print(
            now_hour_minute_sec() + " Drift analysis image done."
        )  # Note analysis done.
        NewImageBuffer.SaveFile(filename)
        self.log("ImageTracker.SaveTrackingAnalysis: End", terminal=False)

    def set_latest_image(self, cvimagebuffer, timestamp=None):
        """This registers the latest image from the camera and performs the translation calculation.
        The imagetracker stores images in grayscale because we do some thresholding to enhance them.
        It does not return any measurements, but stores them in various attributes."""
        self.log("ImageTracker.SetLatestImage: Begin", terminal=False)
        self.log(
            "ImageTracker.SetLatestImage: Received image buffer type",
            str(type(cvimagebuffer)),
            terminal=False,
        )
        if isinstance(cvimagebuffer, type(None)):
            self.log(
                "ImageTracker.SetLatestImage: Received None type image buffer. Nothing set.",
                terminal=False,
            )
            return
        if timestamp is None:
            timestamp = now_utc()  # Assume current clock time.
        uts = utc_time_stamp()
        self.latest_time_stamp = None  # Clear the timestamp until we've completed preparing the image. This is accessed concurrently by the CameraHandler.
        self.log(
            "ImageTracker.SetLatestImage: About to measure contrast.", terminal=False
        )
        self.latest_image.LoadBuffer(
            cvimagebuffer
        )  # This makes a copy of the original image rather than just creating a pointer to it.
        contrast_m, contrast_s = (
            self.latest_image.MeasureContrast()
        )  # Calculate contrast for latest image.
        self.log(
            "ImageTracker.SetLatestImage: Contrast measures",
            contrast_m,
            contrast_s,
            terminal=False,
        )
        self.latest_image.ChangeType(
            "grayscale"
        )  # Always convert to grayscale at this point.
        if (
            self.parameters.latest_tracking_filter is not None
        ):  # A filter script is selected for latest tracking images, process that instead of the old hardcoded filter code.
            if self.latest_image.RunFilterScript(
                self.parameters.latest_tracking_filter
            ):  # If the script succeeds or fails.
                self.log(
                    "ImageTracker.SetLatestImage: LatestTrackingFilter(",
                    self.parameters.latest_tracking_filter,
                    ") success.",
                    terminal=False,
                )
            else:  # Failed.
                self.log(
                    "ImageTracker.SetLatestImage: LatestTrackingFilter(",
                    self.parameters.latest_tracking_filter,
                    ") failed.",
                    level="warning",
                )
        self.log(
            "ImageTracker.SetLatestImage: Prepared image:",
            "type",
            str(type(self.latest_image.ImageBuffer)),
            "shape",
            self.latest_image.GetHeight(),
            "x",
            self.latest_image.GetWidth(),
            "depth",
            self.latest_image.GetDepth(),
            terminal=False,
        )
        self.latest_time_stamp = (
            timestamp  # The image is now prepared, update the timestamp.
        )
        self.latest_star_match_list = (
            []
        )  # Clear the list of matched stars, this is set later when the find_transform call is made.
        self.log("ImageTracker.SetLatestImage: Registered latest image", terminal=False)
        _, _ = self.latest_image.CountStars()
        self.log(
            "ImageTracker.SetLatestImage: Counted",
            self.latest_image.StarCount,
            "stars.",
            terminal=False,
        )
        # Save target image for reference.
        filename = FolderHandler.PrepFile(
            "tracking", "LatestTrackingImage_" + uts + ".jpg"
        )
        self.parameters.camera_window.print(
            now_hour_minute_sec() + " " + filename.split("/")[-1]
        )  # Note the file that's being created.
        self.latest_image.SaveFile(filename)

    def predicted_transform(self, timestamp=None):
        """Estimate the image shift based upon the input images, projected forward in time.
        prediction is based upon timestamp received. If None, then prediction is based upon current timestamp.
        """
        if timestamp is None:
            timestamp = now_utc()  # Assume current clock.
        self.log(
            "ImageTracker.PredictedTransform(): dx",
            str(self.dx),
            "dy",
            str(self.dy),
            "measureddelta",
            str(self.measureddelta),
            terminal=False,
        )
        dx = None
        dy = None
        nowdelta = None
        if (
            self.dx is not None
            and self.dy is not None
            and self.measureddelta is not None
        ):
            if self.measureddelta > 0:
                nowdelta = (timestamp - self.target_time_stamp).total_seconds()
                dx = self.dx * nowdelta / self.measureddelta
                dy = self.dy * nowdelta / self.measureddelta
            else:
                dx = self.dx
                dy = self.dy
        return dx, dy, nowdelta
