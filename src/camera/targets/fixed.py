
from utils.params import AttributeMaster

class FixedPoint(AttributeMaster):
  """A target object which is a fixed altitude and azimuth position.
  It doesn't move with the sky."""

  def __init__(self, name, alt, az):
    self.name = name
    self.altitude = alt
    self.azimuth = az
