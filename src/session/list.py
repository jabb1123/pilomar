import json
import os
from session.entry import SessionEntry
from utils.params import AttributeMaster


class SessionList(AttributeMaster):
  """A class that manages a list of observation sessions/targets.
  Use it to maintain things like :-
  - A list of past observations, so the user can repeat them.
  - A list of future observations, so an observation schedule can be followed."""

  def __init__(self, name):
    """Initialize an instance."""
    self.name = name
    self.session_list = []  # List of sessions.

  def Add(self, dictionary):
    """Create a new session entry.
    Optional dictionary will be used to load the entry."""
    signature = SessionEntry.get_signature(
      dictionary
    )  # Calculate the signature of the entry.
    self.Delete(
      signature
    )  # Delete any earlier entry with the same set of attributes. Don't allow duplicates, and don't merge conflicting details.
    self.session_list.append(SessionEntry(dictionary))

  def Delete(self, signature):
    """Remove a session entry from the list."""
    newlist = []  # The list after cleaning.
    for se in self.session_list:  # Check each entry in turn.
      temp = SessionEntry.get_signature(
        se._Dictionary
      )  # Calculate its unique signature.
      if temp == signature:
        continue  # Don't add duplicates.
      newlist.append(se)
    self.session_list = newlist

  def SortByAge(self):
    """Sort the list of session entries youngest first.
    This sorts self.SessionList by the LastObserved attribute of each sessionentry.
    """
    # Sort dictionary by LastObserved value.
    for se in self.session_list:  # Make sure that the dates all exist!
      if se.LastObserved == None:  # No date set.
        MainLog.Log(
          "sessionlist(",
          self.name,
          ").SortByAge:",
          se.Name,
          "LastObserved is not set. Cannot sort the list.",
          level="error",
        )
        return
    self.session_list = sorted(
      self.session_list, reverse=True, key=lambda x: (x.LastObserved)
    )

  def SortByStartTime(self):
    """Sort the list of session entries in the scheduled start.
    This sorts self.SessionList by the ObservationStart attribute of each sessionentry.
    """
    # Sort dictionary by ObservationStart value.
    for se in self.session_list:  # Make sure that the dates all exist!
      if se.ObservationStart == None:  # No date set.
        MainLog.Log(
          "sessionlist(",
          self.name,
          ").SortByAge:",
          se.Name,
          "ObservationStart is not set. Cannot sort the list.",
          level="error",
        )
        return
    try:  # Only succeeds if all entries have a start time set.
      self.session_list = sorted(
        self.session_list, key=lambda x: (x.ObservationStart)
      )
    except Exception as e:
      MainLog.ReportException(
        e, comment="sessionlist.SortByStartTime. Unable to sort all values."
      )

  def LoadFromJson(self, filename):
    """Load the json file as a dictionary."""
    if os.path.exists(filename):  # File exists to load.
      with open(filename, "r") as f:
        dictionary = json.load(f)
        for (
          name,
          subdict,
        ) in (
          dictionary.items()
        ):  # Now parse the json file and load the sessions up.
          self.Add(
            subdict
          )  # Convert each item into a sessionentry instance. {'Name':'Moon-10','SearchTerm':'moon','SearchGroup':'solar','TargetType':'solar','ExposureSeconds':0.00000001, 'LastObserved':NowUTC()}
    else:  # File doesn't exist.
      MainLog.Log(
        "sessionlist.LoadFromJson:", filename, "does not exist.", terminal=False
      )

  def SaveAsJson(self, filename, limit=None):
    """Save the session list as a json file.
    Save it in an easily read/edited format.
    This saves 1 line per sessionentry.
    If limit is given, the export only writes that many entries."""
    with open(filename, "w") as f:
      f.write("{\n")
      for i, se in enumerate(self.session_list):
        if limit != None and limit <= i:
          break  # We've hit the export limit.
        se.BuildDictionary()
        f.write(
          '    "'
          + str(i).rjust(4, "0")
          + '" : '
          + json.dumps(se._Dictionary, default=str)
        )
        if i + 1 < len(self.session_list):
          f.write(",")
        f.write("\n")
      f.write("}\n")
