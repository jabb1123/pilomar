from utils.logfile import LogFile
from utils.params import AttributeMaster
from utils.time_funcs import dts_to_datetime


class SessionEntry(AttributeMaster):
    """A single entry in a list of observations.
    Used for recording past observations, and also to construct lists of future observation schedules.
    """

    def __init__(self, dictionary, logger: LogFile = None):
        """Initialize an instance."""
        super().__init__()
        self.set_logger(logger)
        self._dictionary = dictionary  # Populate the dictionary to load key attributes.
        self.extract_dictionary()  # Pull the attributes out of the dictionary.
        self.reset()  # Initialise other attributes.

    def reset(self):
        """Initialize/reset other attributes.
        These are calculation results and are not loaded/saved via the dictionary."""
        self.rise_time = None  # Earliest that target is visible.
        self.set_time = None  # Latest that target is visible.
        self.peak_time = None  # When is the target clearest?

    def extract_dictionary(self, dictionary=None):
        """Import values from the _Dictionary attribute.
        Dictionary can be given in the call, or can be already set.
        This is called in the __init__() phase and creates the basic attributes of the instance.
        """
        if dictionary is not None:
            # Update the dictionary attribute with the latest version.
            self._dictionary = dictionary
        # Attributes that can be saved/loaded via a dictionary.
        self.import_export_list = [
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
        self.name = self.get_parm_val("Name", None)
        # Needs converting from string to datetime with UTC tz.
        self.last_observed = self.get_datetime_val("LastObserved", None)
        self.search_term = self.get_parm_val("SearchTerm", None)
        self.search_group = self.get_parm_val("SearchGroup", None)
        self.target_type = self.get_parm_val("TargetType", None)
        self.ra = self.get_parm_val("RA", None)
        self.dec = self.get_parm_val("Dec", None)
        self.alt = self.get_parm_val("Alt", None)
        self.az = self.get_parm_val("Az", None)
        self.exposure_seconds = self.get_parm_val("ExposureSeconds", None)
        self.timelapse_period = self.get_parm_val("TimelapseSeconds", None)
        # self.SensorMode = self.GetParmVal("SensorMode",None)
        # Needs converting from string to datetime with UTC tz.
        self.observation_start = self.get_datetime_val("ObservationStart", None)
        # Needs converting from string to datetime with UTC tz.
        self.observation_end = self.get_datetime_val("ObservationEnd", None)
        self.observation_duration = self.get_parm_val("ObservationDuration", None)
        self.observation_frames = self.get_parm_val("ObservationFrames", None)

    @staticmethod
    def get_signature(dictionary):
        """Calculate a signature for the entry based upon critical attributes.
        This is so we can recognise duplicates."""
        signature = ""
        # Which attributes are used to identify an entry uniquely?
        # fieldlist = ['SearchTerm','TargetType','ExposureSeconds','TimelapsePeriod',
        # 'SensorMode','ObservationStart','ObservationEnd','ObservationDuration','ObservationFrames']
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
            if fieldvalue is not None:
                signature += str(fieldvalue)
        return signature

    def build_dictionary(self) -> dict:
        """Save the instance attributes which have values to the _Dictionary dictionary.
        - Will not save any values with None.
        It ignores any attributes starting with '_' character, and any references to methods.
        """
        self._dictionary = {}  # Start an empty dictionary.
        for attr, value in vars(self).items():
            if value is None:
                continue  # Don't save 'None' values.
            if attr in self.import_export_list:
                self._dictionary[attr] = value

    def get_parm_val(self, name, default, oldnames=None):
        """Get a value from a dictionary.

        name: The parameter name.
        default: The default parameter value if it is not in the dictionary yet.
        oldnames: optional list of previous parameter names, these are used to migrate values from old parameter names to new ones.

        If the value does not exist, create it with the default value."""
        result = default
        if isinstance(oldnames, list):  # Check for earlier parameter values.
            for oldname in oldnames:  # Check each name in turn.
                if (
                    oldname in self._dictionary
                ):  # oldname exists in the dictionary (can migrate from oldname to new name).
                    result = self._dictionary[
                        oldname
                    ]  # Retrieve the value from the oldname entry.
                    self.logger.log(
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
        result = self._dictionary.get(name, result)
        return result

    def get_datetime_val(self, name, default, oldnames=None):
        """Pull a string datetime and return the converted datetime value."""
        sval = self.get_parm_val(name, default, oldnames=oldnames)
        if not isinstance(
            sval, str
        ):  # Return None and datetime values without conversion.
            result = sval
        else:  # String values need converting.
            result = dts_to_datetime(sval)
        return result
