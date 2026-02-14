#!/usr/bin/env python3
"""Session list management for Pilomar telescope control.

This module provides the SessionList class for managing lists of
observation sessions.
"""

from datetime import datetime
from .entry import SessionEntry


class SessionList:
    """A class that manages a list of observation sessions/targets.
    
    Use for:
    - List of past observations (for repeating)
    - List of suggested targets for current location/time
    - List of future observations (observation schedule)
    """

    def __init__(self, name, now_func=None, logger=None):
        """Initialize a session list.
        
        Args:
            name: Name for this list.
            now_func: Function returning current UTC datetime.
            logger: Optional logger for messages.
        """
        self.Name = name
        self._now_func = now_func or (lambda: datetime.utcnow())
        self._logger = logger
        self.reset()

    def reset(self):
        """Reset the session list to empty state."""
        self.SessionList = []
        self.SortOptions = ['SearchTerm', 'Az', 'Alt', 'Magnitude', 'DiameterPixels']
        self.SortChoice = 4  # Sort by size initially
        self.DirtyBit = False
        self.UpdatedTimestamp = self._now_func()

    def Log(self, *args, **kwargs):
        """Log a message if logger is available."""
        if self._logger and hasattr(self._logger, 'Log'):
            self._logger.Log(*args, **kwargs)

    def age_minutes(self):
        """Return how many minutes old the data is.
        
        Returns:
            Age in minutes.
        """
        delta = self._now_func() - self.UpdatedTimestamp
        return int(delta.total_seconds() / 60)

    def add(self, dictionary):
        """Create a new session entry.
        
        Args:
            dictionary: Dictionary to populate the entry.
        """
        signature = SessionEntry.get_signature(dictionary)
        self.delete(signature)  # Remove duplicates
        self.SessionList.append(SessionEntry(dictionary))
        self.UpdatedTimestamp = self._now_func()
        self.DirtyBit = True

    def delete(self, signature):
        """Remove a session entry by signature.
        
        Args:
            signature: The entry's signature to remove.
        """
        new_list = []
        for entry in self.SessionList:
            entry_sig = SessionEntry.get_signature(entry._Dictionary)
            if entry_sig != signature:
                new_list.append(entry)
        
        self.SessionList = new_list
        self.UpdatedTimestamp = self._now_func()
        self.DirtyBit = True

    def sort_by_age(self):
        """Sort the list by LastObserved (youngest first)."""
        for entry in self.SessionList:
            if entry.LastObserved is None:
                self.Log("SessionList(", self.Name, ").sort_by_age:",
                        entry.Name, "LastObserved is not set. Cannot sort.",
                        level='error')
                return
        
        self.SessionList = sorted(
            self.SessionList,
            reverse=True,
            key=lambda x: x.LastObserved
        )

    def sort_by_start_time(self):
        """Sort the list by ObservationStart."""
        for entry in self.SessionList:
            if entry.ObservationStart is None:
                self.Log("SessionList(", self.Name, ").sort_by_start_time:",
                        entry.Name, "ObservationStart is not set. Cannot sort.",
                        level='error')
                return
        
        try:
            self.SessionList = sorted(
                self.SessionList,
                key=lambda x: x.ObservationStart
            )
        except Exception as e:
            self.Log("SessionList.sort_by_start_time: Unable to sort.",
                    level='error')

    def sort_by_field(self, fieldname):
        """Sort the list by an arbitrary field.
        
        Args:
            fieldname: The field name to sort by.
        """
        for entry in self.SessionList:
            if entry._get_param(fieldname, None) is None:
                self.Log("SessionList(", self.Name, ").sort_by_field:",
                        entry.Name, fieldname, "is not set. Cannot sort.",
                        level='error')
                return
        
        try:
            self.SessionList = sorted(
                self.SessionList,
                key=lambda x: x._Dictionary.get(fieldname)
            )
        except Exception as e:
            self.Log("SessionList.sort_by_field: Unable to sort.", level='error')

    def next_sort_option(self, option=None):
        """Rotate through available sort options.
        
        Args:
            option: Specific option index, or None for next.
        """
        if option is None:
            self.SortChoice = (self.SortChoice + 1) % len(self.SortOptions)
        else:
            self.SortChoice = option % len(self.SortOptions)
        
        self.sort_by_field(self.SortOptions[self.SortChoice])

    def display_suggestion_list(self):
        """Display list formatted for suggested targets."""
        print("")
        print("id".rjust(4), "name".ljust(20)[:20], "az".rjust(8)[:8],
              "alt".rjust(9)[:9], "mag".rjust(9)[:9], "pixels".rjust(8)[:8],
              "rose".ljust(5)[:5], "set".ljust(5)[:5])
        
        for i, entry in enumerate(self.SessionList):
            # Build rise/set string
            rs = ""
            if entry.RiseTime:
                rs += entry.RiseTime.strftime('%H:%M') + " "
            else:
                rs += "--:-- "
            if entry.SetTime:
                rs += entry.SetTime.strftime('%H:%M') + " "
            else:
                rs += "--:-- "
            
            az = entry.Az or 0
            alt = entry.Alt or 0
            mag = entry.Magnitude or 0
            dpix = entry.DiameterPixels or 0
            
            print(str(i).rjust(4),
                  (entry.SearchTerm or "").ljust(20)[:20],
                  str(round(az, 1)).rjust(8)[:8] + "°",
                  str(round(alt, 1)).rjust(8)[:8] + "°",
                  str(round(float(mag), 1)).rjust(8)[:8],
                  str(int(dpix)).rjust(8)[:8],
                  rs)
            
            if (i + 1) % 5 == 0:
                print("")
        
        print("(Sorted by", self.SortOptions[self.SortChoice], ")")

    def display_schedule_list(self):
        """Display list formatted for observation schedules."""
        print("")
        print("Observation schedule:")
        print("")
        print("id".rjust(4), "name".ljust(20)[:20], "frames".rjust(9)[:9],
              "secs".rjust(8)[:8], "group".ljust(8)[:8], "term".ljust(40)[:40])
        
        for i, entry in enumerate(self.SessionList):
            print(str(i).rjust(4),
                  (entry.Name or "").ljust(20)[:20],
                  str(entry.ObservationFrames or "").rjust(9)[:9],
                  str(entry.ExposureSeconds or "").rjust(8)[:8],
                  (entry.SearchGroup or "").ljust(8)[:8],
                  (entry.SearchTerm or "").ljust(40)[:40])
            
            if (i + 1) % 5 == 0:
                print("")
        
        print("")

    def __len__(self):
        """Return number of entries in the list."""
        return len(self.SessionList)

    def __iter__(self):
        """Iterate over session entries."""
        return iter(self.SessionList)


# Backward compatibility alias
sessionlist = SessionList
