import json
import os
from typing import List
from session.entry import SessionEntry
from utils.logfile import LogFile
from utils.params import AttributeMaster


class SessionList(AttributeMaster):
    """A class that manages a list of observation sessions/targets.
    Use it to maintain things like :-
    - A list of past observations, so the user can repeat them.
    - A list of future observations, so an observation schedule can be followed."""

    def __init__(self, name, logger: LogFile = None):
        """Initialize an instance."""
        super().__init__()
        self.set_logger(logger)
        self.name = name
        # List of sessions.
        self.session_list: List[SessionEntry] = []

    def add(self, dictionary):
        """Create a new session entry.
        Optional dictionary will be used to load the entry."""
        # Calculate the signature of the entry.
        signature = SessionEntry.get_signature(dictionary)
        # Delete any earlier entry with the same set of attributes.
        # Don't allow duplicates, and don't merge conflicting details.
        self.delete(signature)
        self.session_list.append(SessionEntry(dictionary))

    def delete(self, signature):
        """Remove a session entry from the list."""
        newlist = []  # The list after cleaning.
        for se in self.session_list:  # Check each entry in turn.
            # Calculate its unique signature.
            temp = SessionEntry.get_signature(se._dictionary)
            if temp == signature:
                continue  # Don't add duplicates.
            newlist.append(se)
        self.session_list = newlist

    def sort_by_age(self):
        """Sort the list of session entries youngest first.
        This sorts self.session_list by the LastObserved attribute of each sessionentry.
        """
        # Sort dictionary by LastObserved value.
        for se in self.session_list:  # Make sure that the dates all exist!
            if se.last_observed is None:  # No date set.
                self.logger.log(
                    "sessionlist(",
                    self.name,
                    ").SortByAge:",
                    se.name,
                    "LastObserved is not set. Cannot sort the list.",
                    level="error",
                )
                return
        self.session_list = sorted(
            self.session_list, reverse=True, key=lambda x: (x.last_observed)
        )

    def sort_by_start_time(self):
        """Sort the list of session entries in the scheduled start.
        This sorts self.session_list by the ObservationStart attribute of each sessionentry.
        """
        # Sort dictionary by ObservationStart value.
        for se in self.session_list:  # Make sure that the dates all exist!
            if se.observation_start is None:  # No date set.
                self.logger.log(
                    "sessionlist(",
                    self.name,
                    ").SortByAge:",
                    se.name,
                    "ObservationStart is not set. Cannot sort the list.",
                    level="error",
                )
                return
        try:  # Only succeeds if all entries have a start time set.
            self.session_list = sorted(
                self.session_list, key=lambda x: (x.observation_start)
            )
        except Exception as e:
            self.logger.report_exception(
                e, comment="sessionlist.SortByStartTime. Unable to sort all values."
            )

    def load_from_json(self, filename):
        """Load the json file as a dictionary."""
        if os.path.exists(filename):  # File exists to load.
            with open(filename, "r") as f:
                dictionary: dict = json.load(f)
                # Now parse the json file and load the sessions up.
                for _, subdict in dictionary.items():
                    # Convert each item into a sessionentry instance.
                    # {'Name':'Moon-10','SearchTerm':'moon','SearchGroup':'solar',
                    # 'TargetType':'solar','ExposureSeconds':0.00000001, 'LastObserved':NowUTC()}
                    self.add(subdict)
        else:  # File doesn't exist.
            self.logger.log(
                "sessionlist.LoadFromJson:", filename, "does not exist.", terminal=False
            )

    def save_as_json(self, filename, limit=None):
        """Save the session list as a json file.
        Save it in an easily read/edited format.
        This saves 1 line per sessionentry.
        If limit is given, the export only writes that many entries."""
        with open(filename, "w") as f:
            f.write("{\n")
            for i, se in enumerate(self.session_list):
                if limit is not None and limit <= i:
                    break  # We've hit the export limit.
                se.build_dictionary()
                f.write(
                    '    "'
                    + str(i).rjust(4, "0")
                    + '" : '
                    + json.dumps(se._dictionary, default=str)
                )
                if i + 1 < len(self.session_list):
                    f.write(",")
                f.write("\n")
            f.write("}\n")
