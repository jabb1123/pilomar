"""Fixed Point target for Pilomar.

A target object representing a fixed altitude/azimuth position
that doesn't move with the sky.

Copyright: GNU General Public License v3.0
"""

from pilomar.core.base import AttributeMaster


class FixedPoint(AttributeMaster):
    """A fixed altitude/azimuth target position.
    
    Unlike celestial objects, this represents a fixed point in the
    local sky that doesn't track with Earth's rotation.
    
    Attributes:
        name: Display name for this fixed point.
        altitude: Altitude in degrees (0-90).
        azimuth: Azimuth in degrees (0-360).
    """
    
    def __init__(self, name: str, alt: float, az: float):
        """Initialize fixed point target.
        
        Args:
            name: Name for this fixed point.
            alt: Altitude in degrees.
            az: Azimuth in degrees.
        """
        self.name = name
        self.altitude = alt
        self.azimuth = az
        
    # Legacy attribute aliases (PascalCase)
    @property
    def Name(self):
        return self.name
    
    @Name.setter
    def Name(self, value):
        self.name = value
        
    @property
    def Altitude(self):
        return self.altitude
    
    @Altitude.setter
    def Altitude(self, value):
        self.altitude = value
        
    @property
    def Azimuth(self):
        return self.azimuth
    
    @Azimuth.setter
    def Azimuth(self, value):
        self.azimuth = value


# Backward compatibility alias    
fixedpoint = FixedPoint
