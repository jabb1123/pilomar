"""Local Stars cache for Pilomar.

Smart cache of neighboring stars for fast rendering and image markup.
Creates a pandas dataframe of stars near the target that automatically
updates when the target moves significantly.

Copyright: GNU General Public License v3.0
"""

from collections.abc import Callable

import pandas

from pilomar.core.base import AttributeMaster


class LocalStars(AttributeMaster):
    """Smart cache of neighboring stars for fast rendering.

    Creates and maintains a pandas dataframe of stars near a target
    location. The cache automatically refreshes when the target moves
    beyond a threshold distance.

    Attributes:
        ra: Center Right Ascension in degrees.
        dec: Center Declination in degrees.
        radius: Selection radius in degrees.
        magnitude: Minimum magnitude to select.
        maxstars: Maximum number of stars to cache.
        updated: Timestamp when cache was last updated.

    Notes on Pandas usage:
        - Small changes to dataframe references can dramatically impact performance.
        - .iloc[] uses integer position, .loc[] uses label-based indexing.
        - Selections typically return copies, not pointers to original data.
        - Use ColumnIndex() to get column positions for .iat[] access.
    """

    def __init__(
        self,
        ra: float,
        dec: float,
        radius: float,
        magnitude: float,
        master_df=None,
        maxstars: int = 1000,
        logger=None,
        now_func: Callable = None,
    ):
        """Initialize local stars cache.

        Args:
            ra: Center Right Ascension in degrees.
            dec: Center Declination in degrees.
            radius: Selection radius in degrees.
            magnitude: Minimum magnitude to select (dimmer stars excluded).
            master_df: Pandas dataframe with master star catalog (e.g., Hipparcos).
            maxstars: Maximum number of stars to keep in cache.
            logger: LogFile instance for logging.
            now_func: Function returning current UTC datetime.
        """
        super().__init__(now_func=now_func)
        self.set_logger(logger)
        self.log(
            f"LocalStars.__init__({ra}, {dec}, {radius}, {magnitude}, {maxstars}):",
            terminal=False,
        )

        self._df = None  # Pandas dataframe cache
        self.master_df = master_df  # Master catalog to select from
        self.star_filter = []  # List of HIP numbers to filter against
        self.updated = None  # Timestamp of last update
        self.ra = ra  # Center Right Ascension
        self.dec = dec  # Center Declination
        self.radius = radius  # Selection radius
        self._update_angle = radius / 4  # Refresh threshold
        self.magnitude = magnitude  # Magnitude limit
        self.maxstars = maxstars  # Max cached stars
        self.column_names = []  # Column names after update

        # Trigger initial update if we have data
        if master_df is not None:
            self.update(ra, dec)

    def update(self, ra: float, dec: float) -> bool:
        """Update the star cache for new position.

        Args:
            ra: New Right Ascension in degrees.
            dec: New Declination in degrees.

        Returns:
            True if update succeeded.
        """
        self.log(f"LocalStars.update({ra}, {dec}): Begin", terminal=False)

        if self.master_df is None:
            self.log("LocalStars.update: No master dataframe set", terminal=False)
            return False

        self._df = None  # Clear old cache
        self.ra = ra
        self.dec = dec

        self.min_ra_deg = self.ra - self.radius
        self.max_ra_deg = self.ra + self.radius
        self.min_dec_deg = self.dec - self.radius
        self.max_dec_deg = self.dec + self.radius

        # Select stars within radius and magnitude limit
        self.log(
            f"LocalStars.update: CoreSelection RA {self.min_ra_deg}° to {self.max_ra_deg}°, "
            f"Dec {self.min_dec_deg}° to {self.max_dec_deg}°",
            terminal=False,
        )

        self._df = self.master_df.loc[
            (self.master_df["ra_degrees"] >= self.min_ra_deg)
            & (self.master_df["ra_degrees"] <= self.max_ra_deg)
            & (self.master_df["dec_degrees"] >= self.min_dec_deg)
            & (self.master_df["dec_degrees"] <= self.max_dec_deg)
            & (self.master_df["magnitude"] <= self.magnitude)
        ]

        self.log(f"LocalStars.update: Starting with {len(self._df)} stars", terminal=False)

        # Handle RA wraparound at 0/360 boundary
        if self.min_ra_deg < 0:
            self.log(
                f"LocalStars.update: -ve RA Selection {self.min_ra_deg + 360}° to 360°",
                terminal=False,
            )
            df1 = self.master_df.loc[
                (self.master_df["ra_degrees"] >= self.min_ra_deg + 360)
                & (self.master_df["ra_degrees"] <= 360)
                & (self.master_df["dec_degrees"] >= self.min_dec_deg)
                & (self.master_df["dec_degrees"] <= self.max_dec_deg)
                & (self.master_df["magnitude"] <= self.magnitude)
            ]
            self.log(
                f"LocalStars.update: Appending {len(df1)} stars (<0 rule)",
                terminal=False,
            )
            self._df = pandas.concat([self._df, df1])

        if self.max_ra_deg > 360:
            self.log(
                f"LocalStars.update: +ve RA Selection 0° to {self.max_ra_deg - 360}°",
                terminal=False,
            )
            df2 = self.master_df.loc[
                (self.master_df["ra_degrees"] >= 0)
                & (self.master_df["ra_degrees"] <= self.max_ra_deg - 360)
                & (self.master_df["dec_degrees"] >= self.min_dec_deg)
                & (self.master_df["dec_degrees"] <= self.max_dec_deg)
                & (self.master_df["magnitude"] <= self.magnitude)
            ]
            self.log(
                f"LocalStars.update: Appending {len(df2)} stars (>360 rule)",
                terminal=False,
            )
            self._df = pandas.concat([self._df, df2])

        # Sort by brightness (ascending magnitude = brightest first)
        self._df = self._df.sort_values(["magnitude"], ascending=[True])

        # Apply star filter if specified
        if len(self.star_filter) != 0:
            self.log("LocalStars.update: Applying filter", terminal=False)
            self._apply_filter()

        # Clip to maxstars
        self.log("LocalStars.update: Clipping dataframe", terminal=False)
        self._df = self._df[: self.maxstars]

        self.updated = self._now_func()
        self.log(f"LocalStars.update: Selected {len(self._df.index)} rows", terminal=False)

        # Set index to HIP number but keep column
        self.log("LocalStars.update: Setting index", terminal=False)
        self._df = self._df.set_index("hip", drop=False)
        self.column_names = list(self._df.columns)
        self.log(f"LocalStars.update: ColumnNames are {self.column_names}", terminal=False)

        return True

    def column_index(self, name: str) -> int | None:
        """Get column index for a column name.

        This returns the column index used in Pandas .iloc[] references.

        Args:
            name: Column name to look up.

        Returns:
            Integer column index, or None if not found.
        """
        if name not in self.column_names:
            self.log(
                f"LocalStars.column_index: {name} not in {self.column_names}",
                level="error",
                terminal=True,
            )
            return None
        return self.column_names.index(name)

    def set_filter(self, filterlist: list[int]):
        """Set the star filter list.

        Only stars with HIP numbers in this list will be retained.

        Args:
            filterlist: List of HIP numbers to keep.
        """
        self.star_filter = []
        for i in filterlist:
            hip = int(i)
            if hip not in self.star_filter:
                self.star_filter.append(hip)

    def _apply_filter(self):
        """Apply the star filter to the dataframe."""
        self._df = self._df[self._df.hip.isin(self.star_filter)]
        return True

    def get(self, ra: float, dec: float):
        """Get star dataframe, updating if target has moved.

        Args:
            ra: Current target Right Ascension.
            dec: Current target Declination.

        Returns:
            Pandas dataframe of nearby stars.
        """
        self.log(f"LocalStars.get({ra}, {dec}): Begin", terminal=False)

        # Check if target has moved enough to trigger refresh
        if abs(self.ra - ra) > self._update_angle or abs(self.dec - dec) > self._update_angle:
            self.log("LocalStars.get: Target moved, triggering refresh", terminal=False)
            self._df = None

        if self._df is None:
            self.update(ra, dec)

        self.log("LocalStars.get: End", terminal=False)
        return self._df

    @property
    def dataframe(self):
        """Access the internal dataframe directly."""
        return self._df
