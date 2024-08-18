
import pandas
from utils.params import attributemaster
from utils.time_funcs import NowUTC

class localstars(attributemaster):
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
    self.SetLogger(
      logger
    )  # Inherited from attributemaster: Set up references to chosen logger (or disable if no logger defined).
    self.Log(
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
    self.MasterDf = (
      HipparcosDf  # The master dataframe that the cache is built from.
    )
    self.StarFilter = []  # Integer list of HIP numbers to filter against.
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
    self.Update(ra, dec)  # Trigger update immediately to load the cache.

  def Update(self, ra, dec):
    self.Log("localstars.Update(", ra, dec, "): Begin", terminal=False)
    self._df = None  # Clear old cache.
    self.ra = ra  # Update RIGHT ASCENSION location.
    self.dec = dec  # Update DECLINATION location.
    self.MinRADeg = self.ra - self.radius
    self.MaxRADeg = self.ra + self.radius
    self.MinDecDeg = self.dec - self.radius
    self.MaxDecDeg = self.dec + self.radius
    # Select a subset of the Hipparcos catalog which is within TargetInclusionRadius of the target (=centre of image)
    self.Log(
      "localstars.Update(): CoreSelection RA",
      self.MinRADeg,
      "deg ...",
      self.MaxRADeg,
      "Dec",
      self.MinDecDeg,
      "...",
      self.MaxDecDeg,
      terminal=False,
    )
    self._df = self.MasterDf.loc[
      (self.MasterDf["ra_degrees"] >= self.MinRADeg)
      & (self.MasterDf["ra_degrees"] <= self.MaxRADeg)
      & (self.MasterDf["dec_degrees"] >= self.MinDecDeg)
      & (self.MasterDf["dec_degrees"] <= self.MaxDecDeg)
      & (self.MasterDf["magnitude"] <= self.magnitude)
    ]
    self.Log(
      "localstars.Update(): Starting with",
      len(self._df),
      "stars in the master list.",
      terminal=False,
    )
    if self.MinRADeg < 0:  # -ve RA values need adjusting to 0-360 range.
      self.Log(
        "localstars.Update(): -ve RA Selection RA",
        self.MinRADeg + 360,
        "deg...",
        360,
        "Dec",
        self.MinDecDeg,
        "...",
        self.MaxDecDeg,
        terminal=False,
      )
      df1 = self.MasterDf.loc[
        (self.MasterDf["ra_degrees"] >= self.MinRADeg + 360)
        & (self.MasterDf["ra_degrees"] <= 360)
        & (self.MasterDf["dec_degrees"] >= self.MinDecDeg)
        & (self.MasterDf["dec_degrees"] <= self.MaxDecDeg)
        & (self.MasterDf["magnitude"] <= self.magnitude)
      ]
      self.Log(
        "localstars.Update(): Appending",
        len(df1),
        "stars to the master list. (<0rule)",
        terminal=False,
      )
      self._df = pandas.concat([self._df, df1])  # Add to original list.
    # If MaxRaDeg > 360 then subtract 360 and append result 0<x<=MaxRaDeg
    if self.MaxRADeg > 360:  # +ve RA values over 360 need adjusting to 0-360 range.
      self.Log(
        "localstars.Update(): +ve RA Selection RA",
        0,
        "...",
        self.MaxRADeg - 360,
        "deg Dec",
        self.MinDecDeg,
        "...",
        self.MaxDecDeg,
        terminal=False,
      )
      df2 = self.MasterDf.loc[
        (self.MasterDf["ra_degrees"] >= 0)
        & (self.MasterDf["ra_degrees"] <= self.MaxRADeg - 360)
        & (self.MasterDf["dec_degrees"] >= self.MinDecDeg)
        & (self.MasterDf["dec_degrees"] <= self.MaxDecDeg)
        & (self.MasterDf["magnitude"] <= self.magnitude)
      ]
      self.Log(
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
    if len(self.StarFilter) != 0:
      self.Log("localstars.Update(): Applying filter.", terminal=False)
      self.Filter()
      # self.Log("localstars.Update(): Applied filter.",terminal=False)
    # Clip to maxstars.
    self.Log("localstars.Update(): Clipping dataframe.", terminal=False)
    self._df = self._df[: self.maxstars]
    # self.Log("localstars.Update(): Clipped dataframe.",terminal=False)
    self.update = NowUTC()  # Update timestamp.
    self.Log(
      "localstars.Update(): Selected",
      len(self._df.index),
      "rows.",
      terminal=False,
    )
    self.Log("localstars.Update(): Setting index.", terminal=False)
    self._df = self._df.set_index(
      "hip", drop=False
    )  # Make 'hip' the index of the DataFrame, but keep the 'hip' column for reference.
    # self.Log("localstars.Update(): Set index.",terminal=False)
    self.ColumnNames = list(
      self._df.columns
    )  # Get list of column names in sequence.
    self.Log(
      "localstars.Update(): ColumnNames are", self.ColumnNames, terminal=False
    )
    self.Log("localstars.Update(): End", terminal=False)
    return True

  def ColumnIndex(self, name):
    """Return the column index for any given column name.
    This is the column index number used in Pandas dataframe.iloc[] references."""
    if not name in self.ColumnNames:
      self.Log(
        "localstars.ColumnIndex:",
        name,
        "is not in",
        self.ColumnNames,
        level="error",
        terminal=True,
      )
      return None
    return self.ColumnNames.index(name)

  def SetFilter(self, filterlist):
    """Set the self.StarFilter list."""
    self.StarFilter = []
    for i in filterlist:  # Make sure all values in the list are integers.
      if not int(i) in self.StarFilter:  # Ignore duplicates.
        self.StarFilter.append(int(i))

  def Filter(self):
    """Given a list of Hipparcos ID,s filter the dataframe.
    Only entries in the starlist are retained."""
    self._df = self._df[self._df.hip.isin(self.StarFilter)]
    return True

  def Get(self, ra, dec):
    self.Log("localstars.Get(", ra, dec, "): Begin", terminal=False)
    if (
      abs(self.ra - ra) > self._updateangle
      or abs(self.dec - dec) > self._updateangle
    ):
      self.Log(
        "localstars.Get(): Target location has moved enough to trigger a refresh.",
        terminal=False,
      )
      self._df = None  # Trigger refresh if target location has changed enough.
    if type(self._df) == type(None):  # Need to update
      self.Update(ra, dec)  # Perform the update.
    self.Log("localstars.Get(): End", terminal=False)
    return self._df

