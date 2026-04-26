#!/usr/bin/env python3
"""Session entry class for Pilomar observation tracking.

This module provides the SessionEntry class for recording individual
observation sessions.
"""

from datetime import datetime


class SessionEntry:
    """A single entry in a list of observations.

    Used for recording past observations and constructing lists
    of future observation schedules.
    """

    # Attributes that can be saved/loaded via dictionary
    IMPORT_EXPORT_LIST = [
        "name",
        "last_observed",
        "search_term",
        "search_group",
        "target_type",
        "ra",
        "dec",
        "alt",
        "az",
        "exposure_seconds",
        "timelapse_period",
        "observation_start",
        "observation_end",
        "observation_frames",
        "rise_time",
        "peak_time",
        "set_time",
        "rise_az",
        "peak_az",
        "peak_alt",
        "set_az",
        "magnitude",
        "diameter_degrees",
        "diameter_pixels",
    ]

    def __init__(self, dictionary=None):
        """Initialize a session entry.

        Args:
            dictionary: Optional dict to populate attributes from.
        """
        self._dictionary = dictionary or {}
        self.extract_dictionary()
        self.reset()

    def reset(self):
        """Initialize/reset calculated attributes.

        These are calculation results not loaded/saved via dictionary.
        """
        return

    def extract_dictionary(self, dictionary=None):
        """Import values from dictionary.

        Args:
            dictionary: Optional new dictionary to use.
        """
        if dictionary is not None:
            self._dictionary = dictionary

        self.name = self._get_param("name", None)
        self.last_observed = self._get_datetime("last_observed", None)
        self.search_term = self._get_param("search_term", None)
        self.search_group = self._get_param("search_group", None)
        self.target_type = self._get_param("target_type", None)
        self.ra = self._get_param("ra", None)
        self._radeg = None  # Calculated ra in degrees
        self.dec = self._get_param("dec", None)
        self.alt = self._get_param("alt", None)
        self.az = self._get_param("az", None)
        self.exposure_seconds = self._get_param("exposure_seconds", None)
        self.timelapse_period = self._get_param("timelapse_period", None)
        self.observation_start = self._get_datetime("observation_start", None)
        self.observation_end = self._get_datetime("observation_end", None)
        self.observation_duration = self._get_param("observation_duration", None)
        self.observation_frames = self._get_param("observation_frames", None)

        # Values for suggested target lists
        self.rise_time = self._get_datetime("rise_time", None)
        self.peak_time = self._get_datetime("peak_time", None)
        self.set_time = self._get_datetime("set_time", None)
        self.rise_az = self._get_param("rise_az", None)
        self.peak_az = self._get_param("peak_az", None)
        self.peak_alt = self._get_param("peak_alt", None)
        self.set_az = self._get_param("set_az", None)
        self.magnitude = self._get_param("magnitude", None)
        self.diameter_degrees = self._get_param("diameter_degrees", None)
        self.diameter_pixels = self._get_param("diameter_pixels", None)

    def _get_param(self, name, default):
        """Get a value from the dictionary.

        Args:
            name: Parameter name.
            default: Default value if not found.

        Returns:
            The parameter value or default.
        """
        return self._dictionary.get(name, default)

    def _get_datetime(self, name, default):
        """Get a datetime value from dictionary.

        Args:
            name: Parameter name.
            default: Default value if not found.

        Returns:
            The datetime value or default.
        """
        value = self._dictionary.get(name, default)
        if isinstance(value, str):
            try:
                # Try ISO format first
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                try:
                    # Try common datetime format
                    return datetime.strptime(value, "%Y%m%d%H%M%S")
                except ValueError:
                    return default
        return value

    @staticmethod
    def get_signature(dictionary):
        """Calculate a signature for the entry based on critical attributes.

        This identifies duplicates.

        Args:
            dictionary: The entry's dictionary.

        Returns:
            A signature string.
        """
        field_list = [
            "search_term",
            "target_type",
            "exposure_seconds",
            "timelapse_period",
            "observation_start",
            "observation_end",
            "observation_duration",
            "observation_frames",
        ]

        parts = []
        for field in field_list:
            value = dictionary.get(field)
            parts.append(str(value) if value is not None else "")

        return "/".join(parts)

    def build_dictionary(self):
        """Save instance attributes to _dictionary.

        Ignores None values and attributes starting with '_'.

        Returns:
            The built dictionary.
        """
        self._dictionary = {}

        for attr in self.IMPORT_EXPORT_LIST:
            value = getattr(self, attr, None)
            if value is not None:
                self._dictionary[attr] = value

        return self._dictionary

    def simple_display(self):
        """Print simple display of the entry."""
        self.build_dictionary()

        for i, (key, value) in enumerate(self._dictionary.items()):
            print(f"{i:3d} {key:>20} : {value}")
