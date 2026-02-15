#!/usr/bin/env python3
"""Session list management for Pilomar telescope control.

This module provides the SessionList class for managing lists of
observation sessions.
"""

from pilomar.core.base import AttributeMaster
from .entry import SessionEntry


class SessionList(AttributeMaster):
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
        super().__init__(now_func=now_func)
        self.set_logger(logger)
        self.name = name
        self.reset()

    def reset(self):
        """Reset the session list to empty state."""
        self.session_list = []
        self.sort_options = ["SearchTerm", "Az", "Alt", "Magnitude", "DiameterPixels"]
        self.sort_choice = 4  # Sort by size initially
        self.dirty_bit = False
        self.updated_timestamp = self._now_func()

    def age_minutes(self):
        """Return how many minutes old the data is.

        Returns:
            Age in minutes.
        """
        delta = self._now_func() - self.updated_timestamp
        return int(delta.total_seconds() / 60)

    def add(self, dictionary):
        """Create a new session entry.

        Args:
            dictionary: Dictionary to populate the entry.
        """
        signature = SessionEntry.get_signature(dictionary)
        self.delete(signature)  # Remove duplicates
        self.session_list.append(SessionEntry(dictionary))
        self.updated_timestamp = self._now_func()
        self.dirty_bit = True

    def delete(self, signature):
        """Remove a session entry by signature.

        Args:
            signature: The entry's signature to remove.
        """
        new_list = []
        for entry in self.session_list:
            entry_sig = SessionEntry.get_signature(entry._dictionary)
            if entry_sig != signature:
                new_list.append(entry)

        self.session_list = new_list
        self.updated_timestamp = self._now_func()
        self.dirty_bit = True

    def sort_by_age(self):
        """Sort the list by LastObserved (youngest first)."""
        for entry in self.session_list:
            if entry.LastObserved is None:
                self.log(
                    "SessionList(",
                    self.name,
                    ").sort_by_age:",
                    entry.Name,
                    "LastObserved is not set. Cannot sort.",
                    level="error",
                )
                return

        self.session_list = sorted(
            self.session_list, reverse=True, key=lambda x: x.LastObserved
        )

    def sort_by_start_time(self):
        """Sort the list by observation_start."""
        for entry in self.session_list:
            if entry.observation_start is None:
                self.log(
                    f"SessionList({self.name}).sort_by_start_time: {entry.Name} observation_start is not set. Cannot sort.",
                    level="error",
                )
                return

        try:
            self.session_list = sorted(
                self.session_list, key=lambda x: x.observation_start
            )
        except Exception:
            self.log("SessionList.sort_by_start_time: Unable to sort.", level="error")

    def sort_by_field(self, fieldname):
        """Sort the list by an arbitrary field.

        Args:
            fieldname: The field name to sort by.
        """
        for entry in self.session_list:
            if entry._get_param(fieldname, None) is None:
                self.log(
                    f"SessionList({self.name}).sort_by_field: {entry.Name} {fieldname} is not set. Cannot sort.",
                    level="error",
                )
                return

        try:
            self.session_list = sorted(
                self.session_list, key=lambda x: x._dictionary.get(fieldname)
            )
        except Exception:
            self.log("SessionList.sort_by_field: Unable to sort.", level="error")

    def next_sort_option(self, option=None):
        """Rotate through available sort options.

        Args:
            option: Specific option index, or None for next.
        """
        if option is None:
            self.sort_choice = (self.sort_choice + 1) % len(self.sort_options)
        else:
            self.sort_choice = option % len(self.sort_options)

        self.sort_by_field(self.sort_options[self.sort_choice])

    def display_suggestion_list(self):
        """Display list formatted for suggested targets."""
        print("")
        print(
            "id".rjust(4),
            "name".ljust(20)[:20],
            "az".rjust(8)[:8],
            "alt".rjust(9)[:9],
            "mag".rjust(9)[:9],
            "pixels".rjust(8)[:8],
            "rose".ljust(5)[:5],
            "set".ljust(5)[:5],
        )

        for i, entry in enumerate(self.session_list):
            # Build rise/set string
            rs = ""
            if entry.rise_time:
                rs += entry.rise_time.strftime("%H:%M") + " "
            else:
                rs += "--:-- "
            if entry.set_time:
                rs += entry.set_time.strftime("%H:%M") + " "
            else:
                rs += "--:-- "

            az = entry.az or 0
            alt = entry.alt or 0
            mag = entry.magnitude or 0
            dpix = entry.diameter_pixels or 0

            print(
                str(i).rjust(4),
                (entry.search_term or "").ljust(20)[:20],
                str(round(az, 1)).rjust(8)[:8] + "°",
                str(round(alt, 1)).rjust(8)[:8] + "°",
                str(round(float(mag), 1)).rjust(8)[:8],
                str(int(dpix)).rjust(8)[:8],
                rs,
            )

            if (i + 1) % 5 == 0:
                print("")

        print("(Sorted by", self.sort_options[self.sort_choice], ")")

    def display_schedule_list(self):
        """Display list formatted for observation schedules."""
        print("")
        print("Observation schedule:")
        print("")
        print(
            "id".rjust(4),
            "name".ljust(20)[:20],
            "frames".rjust(9)[:9],
            "secs".rjust(8)[:8],
            "group".ljust(8)[:8],
            "term".ljust(40)[:40],
        )

        for i, entry in enumerate(self.session_list):
            print(
                str(i).rjust(4),
                (entry.name or "").ljust(20)[:20],
                str(entry.observation_frames or "").rjust(9)[:9],
                str(entry.exposure_seconds or "").rjust(8)[:8],
                (entry.search_group or "").ljust(8)[:8],
                (entry.search_term or "").ljust(40)[:40],
            )

            if (i + 1) % 5 == 0:
                print("")

        print("")

    def __len__(self):
        """Return number of entries in the list."""
        return len(self.session_list)

    def __iter__(self):
        """Iterate over session entries."""
        return iter(self.session_list)
