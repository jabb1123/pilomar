
from utils.params import attributemaster

class FixedPoint(attributemaster):
  """A target object which is a fixed altitude and azimuth position.
  It doesn't move with the sky."""

  def __init__(self, name, alt, az):
    self.Name = name
    self.Altitude = alt
    self.Azimuth = az
