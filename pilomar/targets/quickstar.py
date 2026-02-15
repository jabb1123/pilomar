"""Quick Star position calculation for Pilomar.

A fast-calculating star position cache for rendering charts quickly.
Not as precise as Skyfield in the long-term, but accurate enough
for the duration of an observation session.

Copyright: GNU General Public License v3.0
"""

from pilomar.core.base import AttributeMaster
from pilomar.celestial.trig import (
    alt_az_to_xyz,
    xyz_to_alt_az,
    rotate_xyz_on_x_axis,
    rotate_xyz_on_z_axis,
)


class QuickStar(AttributeMaster):
    """Fast-calculating star position for chart rendering.

    This class caches star positions and rotates them with Earth's rotation
    to provide fast approximate positions without expensive Skyfield calculations.

    Attributes:
        base_x: Cached X coordinate in rotated space.
        base_y: Cached Y coordinate in rotated space.
        base_z: Cached Z coordinate in rotated space.
        base_time: Timestamp when position was cached.
    """

    def __init__(self, alt: float, az: float, timestamp, home_latitude: float):
        """Initialize QuickStar with known position.

        Args:
            alt: Known altitude (degrees) at timestamp.
            az: Known azimuth (degrees) at timestamp.
            timestamp: datetime timestamp when alt/az were known.
            home_latitude: Observer's latitude in degrees.
        """
        self.home_latitude = home_latitude
        self.base_x, self.base_y, self.base_z = self._calculate_base_xyz(alt, az)
        self.base_time = timestamp

    def _calculate_base_xyz(self, alt: float, az: float) -> tuple:
        """Calculate cacheable x,y,z position from alt/az coordinates.

        Converts current alt/az to xyz with observer's latitude removed.
        The resulting position can be rotated with time and shifted back
        to observer's latitude for fast cached positions.

        Args:
            alt: Altitude in degrees.
            az: Azimuth in degrees.

        Returns:
            Tuple of (x, y, z) coordinates in rotated space.
        """
        # Convert current alt/az to xyz position in space
        x, y, z = alt_az_to_xyz(alt, az)
        # Remove observer's latitude so positions rotate around zenith
        x, y, z = rotate_xyz_on_x_axis(x, y, z, 90 - self.home_latitude)
        return x, y, z

    def alt_az(self, timestamp) -> tuple:
        """Get apparent alt/az for observer at given timestamp.

        Rotates cached position with time and returns apparent alt/az
        from observer's position.

        Args:
            timestamp: datetime timestamp for position calculation.

        Returns:
            Tuple of (altitude, azimuth) in degrees.
        """
        elapsed_seconds = (timestamp - self.base_time).total_seconds()
        # Use sidereal period of Earth's rotation (just under 24 hours)
        time_angle = 360 * elapsed_seconds / 86164.0905

        # Rotate cached location by angle representing elapsed time
        x, y, z = rotate_xyz_on_z_axis(
            self.base_x, self.base_y, self.base_z, time_angle
        )

        # Add observer's latitude back
        x, y, z = rotate_xyz_on_x_axis(x, y, z, self.home_latitude - 90)

        # Convert to alt/az pair
        alt, az = xyz_to_alt_az(x, y, z)
        return alt, az
