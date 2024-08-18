
from utils.params import attributemaster

class sessionentry(attributemaster):
  """A single entry in a list of observations.
  Used for recording past observations, and also to construct lists of future observation schedules.
  """

  def __init__(self, dictionary):
    self._Dictionary = dictionary  # Populate the dictionary to load key attributes.
    self.ExtractDictionary()  # Pull the attributes out of the dictionary.
    self.Reset()  # Initialise other attributes.

  def Reset(self):
    """Initialize/reset other attributes.
    These are calculation results and are not loaded/saved via the dictionary."""
    self.RiseTime = None  # Earliest that target is visible.
    self.SetTime = None  # Latest that target is visible.
    self.PeakTime = None  # When is the target clearest?

  def ExtractDictionary(self, dictionary=None):
    """Import values from the _Dictionary attribute.
    Dictionary can be given in the call, or can be already set.
    This is called in the __init__() phase and creates the basic attributes of the instance.
    """
    if dictionary != None:
      self._Dictionary = (
        dictionary  # Update the dictionary attribute with the latest version.
      )
    # Attributes that can be saved/loaded via a dictionary.
    self.ImportExportList = [
      "Name",
      "LastObserved",
      "SearchTerm",
      "SearchGroup",
      "TargetType",
      "RA",
      "Dec",
      "Alt",
      "Az",
      "ExposureSeconds",
      "TimelapsePeriod",  # 'SensorMode',
      "ObservationStart",
      "ObservationEnd",
      "ObservationFrames",
    ]
    self.Name = self.GetParmVal("Name", None)
    self.LastObserved = self.GetDatetimeVal(
      "LastObserved", None
    )  # Needs converting from string to datetime with UTC tz.
    self.SearchTerm = self.GetParmVal("SearchTerm", None)
    self.SearchGroup = self.GetParmVal("SearchGroup", None)
    self.TargetType = self.GetParmVal("TargetType", None)
    self.RA = self.GetParmVal("RA", None)
    self.Dec = self.GetParmVal("Dec", None)
    self.Alt = self.GetParmVal("Alt", None)
    self.Az = self.GetParmVal("Az", None)
    self.ExposureSeconds = self.GetParmVal("ExposureSeconds", None)
    self.TimelapsePeriod = self.GetParmVal("TimelapseSeconds", None)
    # self.SensorMode = self.GetParmVal("SensorMode",None)
    self.ObservationStart = self.GetDatetimeVal(
      "ObservationStart", None
    )  # Needs converting from string to datetime with UTC tz.
    self.ObservationEnd = self.GetDatetimeVal(
      "ObservationEnd", None
    )  # Needs converting from string to datetime with UTC tz.
    self.ObservationDuration = self.GetParmVal("ObservationDuration", None)
    self.ObservationFrames = self.GetParmVal("ObservationFrames", None)

  @staticmethod
  def GetSignature(dictionary):
    """Calculate a signature for the entry based upon critical attributes.
    This is so we can recognise duplicates."""
    signature = ""
    # Which attributes are used to identify an entry uniquely?
    # fieldlist = ['SearchTerm','TargetType','ExposureSeconds','TimelapsePeriod','SensorMode','ObservationStart','ObservationEnd','ObservationDuration','ObservationFrames']
    fieldlist = [
      "SearchTerm",
      "TargetType",
      "ExposureSeconds",
      "TimelapsePeriod",
      "ObservationStart",
      "ObservationEnd",
      "ObservationDuration",
      "ObservationFrames",
    ]
    for i, fieldname in enumerate(fieldlist):
      fieldvalue = dictionary.get(fieldname, None)
      if i > 0:
        signature += "/"
      if fieldvalue != None:
        signature += str(fieldvalue)
    return signature

  def BuildDictionary(self) -> dict:
    """Save the instance attributes which have values to the _Dictionary dictionary.
    - Will not save any values with None.
    It ignores any attributes starting with '_' character, and any references to methods.
    """
    self._Dictionary = {}  # Start an empty dictionary.
    for attr, value in vars(self).items():
      if value == None:
        continue  # Don't save 'None' values.
      if attr in self.ImportExportList:
        self._Dictionary[attr] = value

  def GetParmVal(self, name, default, oldnames=None):
    """Get a value from a dictionary.

    name: The parameter name.
    default: The default parameter value if it is not in the dictionary yet.
    oldnames: optional list of previous parameter names, these are used to migrate values from old parameter names to new ones.

    If the value does not exist, create it with the default value."""
    result = default
    if type(oldnames) == list:  # Check for earlier parameter values.
      for oldname in oldnames:  # Check each name in turn.
        if (
          oldname in self._Dictionary
        ):  # oldname exists in the dictionary (can migrate from oldname to new name).
          result = self._Dictionary[
            oldname
          ]  # Retrieve the value from the oldname entry.
          MainLog.Log(
            "sessionentry.GetParmVal(",
            name,
            ") migrating from",
            oldname,
            "with value",
            result,
            terminal=False,
          )
          break  # Look no further.
    # Now get/initialise the current parameter name.
    result = self._Dictionary.get(name, result)
    return result

  def GetDatetimeVal(self, name, default, oldnames=None):
    """Pull a string datetime and return the converted datetime value."""
    sval = self.GetParmVal(name, default, oldnames=oldnames)
    if type(sval) != str:  # Return None and datetime values without conversion.
      result = sval
    else:  # String values need converting.
      result = DTSToDatetime(sval)
    return result
