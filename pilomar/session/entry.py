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
        'Name', 'LastObserved', 'SearchTerm', 'SearchGroup', 'TargetType',
        'RA', 'Dec', 'Alt', 'Az', 'ExposureSeconds', 'TimelapsePeriod',
        'ObservationStart', 'ObservationEnd', 'ObservationFrames',
        'RiseTime', 'PeakTime', 'SetTime', 'RiseAz', 'PeakAz', 'PeakAlt', 'SetAz',
        'Magnitude', 'DiameterDegrees', 'DiameterPixels'
    ]

    def __init__(self, dictionary=None):
        """Initialize a session entry.
        
        Args:
            dictionary: Optional dict to populate attributes from.
        """
        self._Dictionary = dictionary or {}
        self.extract_dictionary()
        self.reset()

    def reset(self):
        """Initialize/reset calculated attributes.
        
        These are calculation results not loaded/saved via dictionary.
        """
        pass

    def extract_dictionary(self, dictionary=None):
        """Import values from dictionary.
        
        Args:
            dictionary: Optional new dictionary to use.
        """
        if dictionary is not None:
            self._Dictionary = dictionary
        
        self.Name = self._get_param('Name', None)
        self.LastObserved = self._get_datetime('LastObserved', None)
        self.SearchTerm = self._get_param('SearchTerm', None)
        self.SearchGroup = self._get_param('SearchGroup', None)
        self.TargetType = self._get_param('TargetType', None)
        self.RA = self._get_param('RA', None)
        self._radeg = None  # Calculated RA in degrees
        self.Dec = self._get_param('Dec', None)
        self.Alt = self._get_param('Alt', None)
        self.Az = self._get_param('Az', None)
        self.ExposureSeconds = self._get_param('ExposureSeconds', None)
        self.TimelapsePeriod = self._get_param('TimelapseSeconds', None)
        self.ObservationStart = self._get_datetime('ObservationStart', None)
        self.ObservationEnd = self._get_datetime('ObservationEnd', None)
        self.ObservationDuration = self._get_param('ObservationDuration', None)
        self.ObservationFrames = self._get_param('ObservationFrames', None)
        
        # Values for suggested target lists
        self.RiseTime = self._get_datetime('RiseTime', None)
        self.PeakTime = self._get_datetime('PeakTime', None)
        self.SetTime = self._get_datetime('SetTime', None)
        self.RiseAz = self._get_param('RiseAz', None)
        self.PeakAz = self._get_param('PeakAz', None)
        self.PeakAlt = self._get_param('PeakAlt', None)
        self.SetAz = self._get_param('SetAz', None)
        self.Magnitude = self._get_param('Magnitude', None)
        self.DiameterDegrees = self._get_param('DiameterDegrees', None)
        self.DiameterPixels = self._get_param('DiameterPixels', None)

    def _get_param(self, name, default):
        """Get a value from the dictionary.
        
        Args:
            name: Parameter name.
            default: Default value if not found.
            
        Returns:
            The parameter value or default.
        """
        return self._Dictionary.get(name, default)

    def _get_datetime(self, name, default):
        """Get a datetime value from dictionary.
        
        Args:
            name: Parameter name.
            default: Default value if not found.
            
        Returns:
            The datetime value or default.
        """
        value = self._Dictionary.get(name, default)
        if isinstance(value, str):
            try:
                # Try ISO format first
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                try:
                    # Try common datetime format
                    return datetime.strptime(value, '%Y%m%d%H%M%S')
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
            'SearchTerm', 'TargetType', 'ExposureSeconds', 'TimelapsePeriod',
            'ObservationStart', 'ObservationEnd', 'ObservationDuration',
            'ObservationFrames'
        ]
        
        parts = []
        for field in field_list:
            value = dictionary.get(field)
            parts.append(str(value) if value is not None else '')
        
        return '/'.join(parts)

    def build_dictionary(self):
        """Save instance attributes to _Dictionary.
        
        Ignores None values and attributes starting with '_'.
        
        Returns:
            The built dictionary.
        """
        self._Dictionary = {}
        
        for attr in self.IMPORT_EXPORT_LIST:
            value = getattr(self, attr, None)
            if value is not None:
                self._Dictionary[attr] = value
        
        return self._Dictionary

    def simple_display(self):
        """Print simple display of the entry."""
        self.build_dictionary()
        
        for i, (key, value) in enumerate(self._Dictionary.items()):
            print(f"{i:3d} {key:>20} : {value}")


# Backward compatibility alias
sessionentry = SessionEntry
