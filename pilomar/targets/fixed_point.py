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
        altitude: altitude in degrees (0-90).
        azimuth: azimuth in degrees (0-360).
    """

    def __init__(self, name: str, alt: float, az: float):
        """Initialize fixed point target.

        Args:
            name: Name for this fixed point.
            alt: altitude in degrees.
            az: azimuth in degrees.
        """
        self.name = name
        self.altitude = alt
        self.azimuth = az
