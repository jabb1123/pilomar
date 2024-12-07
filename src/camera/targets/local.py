import os
import pandas
from skyfield.data import hipparcos  # Hipparcos star catalog.
from skyfield.api import load  # Skyfield data loader.
from utils.math_func import pandas_float
from utils.logfile import LogFile
from utils.math_func import angle_to_dms, angle_to_hms
from utils.params import AttributeMaster
from utils.text.textcolor import TextColor
from utils.time_funcs import now_utc
from utils.timer import ProgressTimer, Timer


def dim_channel(channel, ratio):
    """simple multiplier for single color channel."""
    channel = channel * ratio
    channel = max(channel, 0)  # Cannot be < 0
    channel = min(channel, 255)  # Cannot be > 255
    return int(channel)


def hip_color(bv):
    """Return b,g,r values for the color of any star given its B-V value from the hipparcos catalog."""
    bv = pandas_float(bv)  # Make sure it's a float, trap NaN values.
    try:
        if is_float(bv):  # Some entries are BLANK in Hipparcos data set.
            color_bv = float(bv)
            b, g, r = b_vto_bgr(color_bv)
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


class LocalStars(AttributeMaster):
    """Smart cache of neighbouring stars, to make rendering and markup of images faster.
    Creates a pandas dataframe of stars near the target.
    The dataframe is automatically updated if the target moves significantly.
    This also standardises and simplifies the selection logic so that all image generators
    will give similar results.

    Some notes on PANDAS! It can be complicated to understand what's going on under the hood.
    - Small changes to dataframe references can have unexpected impact upon performance.
      Pandas can be blisteringly fast, but making a small change can turn it into devastatingly slow.
    - It's easy to get lost in indexing in Pandas. There are multiple ways to find/reference items
      and the syntax is not always easy for a beginner.
    - It's easy to confuse .iloc[], .loc[], .at[] methods for example, and you can retrieve the wrong information by accident.
    - Updating Pandas dataframe rows/columns has been problematic at times for multiple reasons.
    - Most 'selections' of Pandas dataframe rows here will return 'copies' of the data rather than pointers to the original,
      so when updating back to the dataframe, be sure to select the same row in the source dataframe and update that!

    Using some ChatGPT style coding tools has sometimes been useful to break deadlocks when getting Pandas to behave as expected.
    The Pandas code here is unlikely to be perfect - I'm not an expert in it, it works, but can certainly be improved.

    Finding a specific HIP star row using     MyRow = self._df.loc[hip_num]
    Finding a specific row using index        MyRow = self._df.iloc[row_num]
    Finding a specific cell using             MyCell = self._df.loc[hip_num,'magnitude']
                          MyCell = self._df.iloc[row_num]['magnitude']
                          MyCell = self._df.iat[row_num,col_num]
    Find col_num for a specific column using localstars.ColumnIndex('magnitude')
    - This returns None if the column name is not known."""

    def __init__(self, ra, dec, radius, magnitude, maxstars=1000, logger=None):
        self.set_logger(
            logger
        )  # Inherited from attributemaster: Set up references to chosen logger (or disable if no logger defined).
        self.log(
            "localstars.__init__(",
            ra,
            dec,
            radius,
            magnitude,
            maxstars,
            "):",
            terminal=False,
        )
        self._df = None  # Pandas dataframe.
        hipparcos_cache_file = ProjectRoot + "/data/hipparcos.pkl"
        reload_data = False  # Set to True to force a reload of the Hipparcos data.
        if not reload_data and os.path.exists(
            hipparcos_cache_file
        ):  # A cache of the hipparcos data already exists, use it.
            hipparcos_df = pandas.read_pickle(hipparcos_cache_file)
            self.logger.log(
                "Hipparcos dataframe loaded",
                len(hipparcos_df),
                "stars from cache.",
                terminal=False,
            )
            self.logger.log(
                "Hipparcos dataframe contains",
                list(hipparcos_df.columns),
                "columns.",
                terminal=False,
            )
        else:
            hipparcos_url = (
                ProjectRoot + "/data/hip_main.dat.gz"
            )  # The skyfield example tries to pull this from the internet,
        # but the .gz. file doesn't always exist in the format expected so it is stored locally for now.
        # http://cdsarc.u-strasbg.fr/ftp/cats/aliases/H/Hipparcos/hip_main.dat
        # This was fixed by skyfield 1.31, it may break again if someone in u-strasbg re-zips the file.
        # hipparcos.URL contains the remote server copy of the file.
        if not os.path.exists(hipparcos_url):
            self.logger.log(
                "Hipparcos compressed catalog was not found locally (",
                hipparcos_url,
                "), will use Skyfield sources.",
                terminal=False,
            )
            # hipparcos_url = 'https://cdsarc.u-strasbg.fr/ftp/cats/I/239/hip_main.dat'
            hipparcos_url = (
                hipparcos.URL
            )  # The official source of the data file as provided by skyfield itself.
            self.logger.log(
                "Loading Hipparcos catalog dataframe from "
                + hipparcos_url
                + " (or local cache)...",
                terminal=False,
            )
            with load.open(
                hipparcos_url, reload=reload_data
            ) as f:  # Don't keep reloading it if it is already on disc.
                hipparcos_df: pandas.DataFrame = hipex_load_dataframe(f)
                self.logger.log(
                    "Hipparcos data:", list(hipparcos_df.columns), terminal=False
                )
                self.logger.log(
                    "Saving Hipparcos cache as", hipparcos_cache_file, terminal=True
                )
                hipparcos_df.to_pickle(hipparcos_cache_file)
        # The master dataframe that the cache is built from.
        self.master_df: pandas.DataFrame = hipparcos_df
        self.star_filter = []  # Integer list of HIP numbers to filter against.
        self.updated = None  # Timestamp when the cache was last updated.
        self.ra = ra  # Centre RIGHT ASCENSION in degrees.
        self.dec = dec  # Centre DECLINATION in degrees.
        self.radius = radius  # Selection radius in degrees.
        self._updateangle = (
            radius / 4
        )  # When centre has moved this far, it's time to update.
        self.magnitude = (
            magnitude  # Minimum magnitude to select. Ignore any stars dimmer than this.
        )
        self.maxstars = maxstars  # Maximum number of stars to select.
        self.update(ra, dec)  # Trigger update immediately to load the cache.

    def update(self, ra, dec):
        self.log("localstars.Update(", ra, dec, "): Begin", terminal=False)
        self._df = None  # Clear old cache.
        self.ra = ra  # Update RIGHT ASCENSION location.
        self.dec = dec  # Update DECLINATION location.
        self.min_ra_deg = self.ra - self.radius
        self.max_ra_deg = self.ra + self.radius
        self.min_dec_deg = self.dec - self.radius
        self.max_dec_deg = self.dec + self.radius
        # Select a subset of the Hipparcos catalog which is within TargetInclusionRadius of the target (=centre of image)
        self.log(
            "localstars.Update(): CoreSelection RA",
            self.min_ra_deg,
            "deg ...",
            self.max_ra_deg,
            "Dec",
            self.min_dec_deg,
            "...",
            self.max_dec_deg,
            terminal=False,
        )
        self._df = self.master_df.loc[
            (self.master_df["ra_degrees"] >= self.min_ra_deg)
            & (self.master_df["ra_degrees"] <= self.max_ra_deg)
            & (self.master_df["dec_degrees"] >= self.min_dec_deg)
            & (self.master_df["dec_degrees"] <= self.max_dec_deg)
            & (self.master_df["magnitude"] <= self.magnitude)
        ]
        self.log(
            "localstars.Update(): Starting with",
            len(self._df),
            "stars in the master list.",
            terminal=False,
        )
        if self.min_ra_deg < 0:  # -ve RA values need adjusting to 0-360 range.
            self.log(
                "localstars.Update(): -ve RA Selection RA",
                self.min_ra_deg + 360,
                "deg...",
                360,
                "Dec",
                self.min_dec_deg,
                "...",
                self.max_dec_deg,
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
                "localstars.Update(): Appending",
                len(df1),
                "stars to the master list. (<0rule)",
                terminal=False,
            )
            self._df = pandas.concat([self._df, df1])  # Add to original list.
        # If MaxRaDeg > 360 then subtract 360 and append result 0<x<=MaxRaDeg
        if (
            self.max_ra_deg > 360
        ):  # +ve RA values over 360 need adjusting to 0-360 range.
            self.log(
                "localstars.Update(): +ve RA Selection RA",
                0,
                "...",
                self.max_ra_deg - 360,
                "deg Dec",
                self.min_dec_deg,
                "...",
                self.max_dec_deg,
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
                "localstars.Update(): Appending",
                len(df2),
                "stars to the master list. (>360rule)",
                terminal=False,
            )
            self._df = pandas.concat([self._df, df2])  # Add to original list.
        self._df = self._df.sort_values(
            ["magnitude"], ascending=[True]
        )  # Sort the selected stars in ascending order of brightness. So we can match the brightest stars first.
        # If there's a StarFilter specified, apply it now.
        if len(self.star_filter) != 0:
            self.log("localstars.Update(): Applying filter.", terminal=False)
            self.filter()
            # self.log("localstars.Update(): Applied filter.",terminal=False)
        # Clip to maxstars.
        self.log("localstars.Update(): Clipping dataframe.", terminal=False)
        self._df = self._df[: self.maxstars]
        # self.log("localstars.Update(): Clipped dataframe.",terminal=False)
        self.updated = now_utc()  # Update timestamp.
        self.log(
            "localstars.Update(): Selected",
            len(self._df.index),
            "rows.",
            terminal=False,
        )
        self.log("localstars.Update(): Setting index.", terminal=False)
        self._df = self._df.set_index(
            "hip", drop=False
        )  # Make 'hip' the index of the DataFrame, but keep the 'hip' column for reference.
        # self.log("localstars.Update(): Set index.",terminal=False)
        self.column_names = list(
            self._df.columns
        )  # Get list of column names in sequence.
        self.log(
            "localstars.Update(): ColumnNames are", self.column_names, terminal=False
        )
        self.log("localstars.Update(): End", terminal=False)
        return True

    def column_index(self, name):
        """Return the column index for any given column name.
        This is the column index number used in Pandas dataframe.iloc[] references."""
        if not name in self.column_names:
            self.log(
                "localstars.ColumnIndex:",
                name,
                "is not in",
                self.column_names,
                level="error",
                terminal=True,
            )
            return None
        return self.column_names.index(name)

    def set_filter(self, filterlist):
        """Set the self.star_filter list."""
        self.star_filter = []
        for i in filterlist:  # Make sure all values in the list are integers.
            if not int(i) in self.star_filter:  # Ignore duplicates.
                self.star_filter.append(int(i))

    def filter(self):
        """Given a list of Hipparcos ID,s filter the dataframe.
        Only entries in the starlist are retained."""
        self._df = self._df[self._df.hip.isin(self.star_filter)]
        return True

    def get(self, ra, dec):
        self.log("localstars.Get(", ra, dec, "): Begin", terminal=False)
        if (
            abs(self.ra - ra) > self._updateangle
            or abs(self.dec - dec) > self._updateangle
        ):
            self.log(
                "localstars.Get(): Target location has moved enough to trigger a refresh.",
                terminal=False,
            )
            self._df = None  # Trigger refresh if target location has changed enough.
        if isinstance(self._df, type(None)):  # Need to update
            self.update(ra, dec)  # Perform the update.
        self.log("localstars.Get(): End", terminal=False)
        return self._df


def hipex_load_dataframe(fobj, logger: LogFile = None):
    """Skyfield has a built in method to extract Hipparcos data and convert it into a Pandas dataframe.
    However it lacks some data fields that Pilomar uses.
    This is a replica of the Skyfield method, but it extracts the additional datafields that Pilomar uses.
    If the original Skyfield method ever changes, this version should also be reviewed.
    Original skyfield function is in :-
        /usr/local/lib/python3.7/dist-packages/skyfield/data/hipparcos.py

    This version of the routine is very slow, 3+ hours on Raspberry Pi 4B.
    - Likely that there are good Pandas improvements to make here. Needs more investigation.
    """
    # This extracts extra data columns from the hipparcos file.
    _COLUMN_NAMES = (
        "Catalog",
        "HIP",
        "Proxy",
        "RAhms",
        "DEdms",
        "Vmag",
        "VarFlag",
        "r_Vmag",
        "RAdeg",
        "DEdeg",
        "AstroRef",
        "Plx",
        "pmRA",
        "pmDE",
        "e_RAdeg",
        "e_DEdeg",
        "e_Plx",
        "e_pmRA",
        "e_pmDE",
        "DE:RA",
        "Plx:RA",
        "Plx:DE",
        "pmRA:RA",
        "pmRA:DE",
        "pmRA:Plx",
        "pmDE:RA",
        "pmDE:DE",
        "pmDE:Plx",
        "pmDE:pmRA",
        "F1",
        "F2",
        "---",
        "BTmag",
        "e_BTmag",
        "VTmag",
        "e_VTmag",
        "m_BTmag",
        "B-V",
        "e_B-V",
        "r_B-V",
        "V-I",
        "e_V-I",
        "r_V-I",
        "CombMag",
        "Hpmag",
        "e_Hpmag",
        "Hpscat",
        "o_Hpmag",
        "m_Hpmag",
        "Hpmax",
        "HPmin",
        "Period",
        "HvarType",
        "moreVar",
        "morePhoto",
        "CCDM",
        "n_CCDM",
        "Nsys",
        "Ncomp",
        "MultFlag",
        "Source",
        "Qual",
        "m_HIP",
        "theta",
        "rho",
        "e_rho",
        "dHp",
        "e_dHp",
        "Survey",
        "Chart",
        "Notes",
        "HD",
        "BD",
        "CoD",
        "CPD",
        "(V-I)red",
        "SpType",
        "r_SpType",
    )

    # Check the first 2 'magic' bytes at the start of the file, these will tell if the file is a gzip archive.
    # The pandas.read_csv method needs to know if it's compressed or not.
    fobj.seek(0)
    magic = fobj.read(2)
    compression = "gzip" if (magic == b"\x1f\x8b") else None
    fobj.seek(0)

    df = pandas.read_csv(
        fobj,
        sep="|",
        names=_COLUMN_NAMES,
        compression=compression,
        usecols=["HIP", "Vmag", "RAdeg", "DEdeg", "Plx", "pmRA", "pmDE", "B-V"],
        na_values=["     ", "       ", "        ", "            "],
    )

    df.columns = (
        "hip",
        "magnitude",
        "ra_degrees",
        "dec_degrees",
        "parallax_mas",
        "ra_mas_per_year",
        "dec_mas_per_year",
        "B-V",
    )

    df = df.assign(
        ra_hours=df["ra_degrees"] / 15.0,
        epoch_year=1991.25,
    )

    # Drop any rows with missing data.
    df = df.dropna(subset=["ra_degrees", "dec_degrees"])

    # Add some precalculated data to simplify things later.
    df["ralabel"] = ""  # Add a column for precalculated RA label for each star.
    df["declabel"] = ""  # Add a column for precalculated DEC label for each star.
    df["label"] = ""  # Full HIPnnnn label for display/labelling.
    df["starname"] = ""  # Add a column for the name of the star if known.
    df["constellation"] = ""  # Add a column for the name of the constellation if known.
    df["color_b"] = 255  # BLUE color of star.
    df["color_g"] = 255  # GREEN color of star.
    df["color_r"] = 255  # RED color of star.
    df["markupradius"] = 1  # Size of circle surrounding a star on the preview markup.
    df["starradius"] = 1  # Size of the DOT representing the star when making images.
    df["inbounds"] = (
        0  # Record how many times this star is within the bounds of the image. # Can be useful for finetuning the star list.
    )
    df["targetangle"] = (
        0.0  # Record how far away the star is from the target (angle). # Can be useful for finetuning the star list.
    )

    # Set proper names for stars if known.
    logger.log("hipex_load_dataframe: Setting proper names of stars :-", terminal=True)
    for key, StarDict in StarName_dictionary.items():
        hip = int(key)
        name = StarDict.get("name", None)
        constellation = StarDict.get("constellation", None)
        logger.log(
            "hipex_load_dataframe: Key",
            key,
            "Naming",
            hip,
            "as",
            name,
            "in",
            constellation,
            terminal=False,
        )
        if name is not None:
            df.loc[df.hip == hip, "starname"] = name  # Set proper name of star.
        if constellation is not None:
            df.loc[df.hip == hip, "constellation"] = (
                constellation  # Set constellation name.
            )

    logger.log(
        "hipex_load_dataframe: Set",
        len(pandas.unique(df["starname"])) - 1,
        "star names.",
        terminal=True,
    )
    logger.log(
        "hipex_load_dataframe: Set",
        len(pandas.unique(df["constellation"])) - 1,
        "constellation names.",
        terminal=True,
    )

    # Get list of unique B-V values.
    # Convert to b,g,r. Use Pandas efficiency to update all matching entries.
    # Create a catalog that can be used later to find these precalculated values.
    BVList = pandas.unique(df["B-V"])  # How many unique values of B-V are there?
    logger.log(
        "hipex_load_dataframe: Estimating",
        len(df),
        "star colors from",
        len(BVList),
        "unique B-V values...",
        terminal=True,
    )
    BVColors = {}
    for i, e in enumerate(
        BVList
    ):  # Convert each unique value only once, then assign to all matching entries in the dataframe.
        temp = pandas_float(e)
        if temp is not None:
            b, g, r = hip_color(temp)
        else:
            b = g = r = 255
        BVColors[e] = (b, g, r)

    # Pandas cells are referenced via indexes, calculate the indexes for each column here.
    ColumnNames = list(df.columns)
    col_ra_degrees = ColumnNames.index("ra_degrees")
    col_dec_degrees = ColumnNames.index("dec_degrees")
    col_ralabel = ColumnNames.index("ralabel")
    col_declabel = ColumnNames.index("declabel")
    col_markupradius = ColumnNames.index("markupradius")
    col_starradius = ColumnNames.index("starradius")
    col_label = ColumnNames.index("label")
    col_color_b = ColumnNames.index("color_b")
    col_color_g = ColumnNames.index("color_g")
    col_color_r = ColumnNames.index("color_r")
    total = len(df)  # How many rows to process?
    logger.log(
        "hipex_load_dataframe: Calculate extra fields directly in",
        total,
        "records.",
        terminal=True,
    )
    # Populate the ralabel and declabel columns, so we don't keep recalculating the values later in the program.
    updatetimer = Timer(10)  # Every few seconds update the progress.
    updatetimer.trigger()  # Force the timer to trigger immediately to show processing has begun.
    prgt = ProgressTimer("test", target=total)  # Report progress and ETA.
    print("")
    for i in range(total):  # Go through all the rows in the dataframe in sequence.
        dfrec = df.iloc[i]  # Point to each row in turn.
        temp = pandas_float(dfrec["hip"])  # Get hip number.
        if temp is not None:
            hip = int(temp)  # Extract hip number as integer.
        else:
            hip = 99999999  # Junk!
        # Create label for Right Ascension
        temp = pandas_float(dfrec["ra_degrees"])
        if temp is not None:
            h, m, s = angle_to_hms(temp)
            df.iat[i, col_ralabel] = (
                str(int(h)) + "h " + str(int(m)) + "' " + str(round(s, 1)) + '"'
            )
        else:
            logger.log(
                "hipex_load_dataframe: Unable to calculate ra_degrees for record",
                i,
                df.iat[i, col_ra_degrees],
                terminal=False,
            )
        # Create label for Declination
        temp = pandas_float(dfrec["dec_degrees"])
        if temp is not None:
            d, m, s = angle_to_dms(temp)
            df.iat[i, col_declabel] = (
                str(int(d)) + "deg " + str(int(m)) + "' " + str(round(s, 1)) + '"'
            )
        else:
            logger.log(
                "hipex_load_dataframe: Unable to calculate dec_degrees for record",
                i,
                df.iat[i, col_dec_degrees],
                terminal=False,
            )
        # Create label for the HIP id.
        df.iat[i, col_label] = "HIP" + str(
            hip
        )  # Full HIPnnnn label for display/labelling.
        temp = pandas_float(dfrec["magnitude"])
        if temp is not None:
            # How large a circle does PreviewImage draw around this star?
            df.iat[i, col_markupradius] = int(
                max(int(15 - temp) * 3, 1)
            )  # Calculate the radius of the star, brighter = bigger.
            # What size is the star dot when creating images?
            TempStarRadius, TempStarDimmer = magnitude2_radius(
                mag=temp, dimmest=10, brightest=-2, radius_max=20
            )
            df.iat[i, col_starradius] = int(TempStarRadius)
        else:
            TempStarDimmer = 1.0
        # Estimate the color of the star.
        b, g, r = BVColors[
            dfrec["B-V"]
        ]  # Look up the basic color from a dictionary of precalculated conversions.
        df.iat[i, col_color_b] = dim_channel(
            b, TempStarDimmer
        )  # Dim the star depending upon the magnitude.
        df.iat[i, col_color_g] = dim_channel(g, TempStarDimmer)
        df.iat[i, col_color_r] = dim_channel(r, TempStarDimmer)
        # Show progress...
        if updatetimer.due():
            prgt.update_count(
                i
            )  # How far have we got so far? prgt will then produce ETA and % complete for us.
            print(
                TextColor.cursorup() + now_utc(),
                TextColor.white(str(round(prgt.get_percent(), 1))),
                "%. Record",
                i,
                "of",
                total,
                "( HIP" + str(hip),
                "). ETA",
                str(prgt.get_eta()).split(".")[0],
                "UTC",
                TextColor.clearlineforward(),
            )
    return df
