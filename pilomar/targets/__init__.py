"""Target management for Pilomar telescope system.

This module provides classes for managing observation targets including:
- Target: Full observation target with Skyfield integration
- FixedPoint: Fixed altitude/azimuth targets
- QuickStar: Fast star position calculation
- LocalStars: Smart star cache for rendering
- ImageTracker: Drift measurement between images
- SkyContext/TimeContext/HardwareContext: Dependency injection helpers

Copyright: GNU General Public License v3.0
"""

from .fixed_point import FixedPoint
from .quickstar import QuickStar
from .local_stars import LocalStars
from .sky_context import SkyContext, TimeContext, HardwareContext

# Target requires Skyfield - import conditionally
try:
    from .target import Target

    _TARGET_AVAILABLE = True
except ImportError:
    _TARGET_AVAILABLE = False
    Target = None

# ImageTracker requires opencv and astroalign - import conditionally
try:
    from .image_tracker import ImageTracker

    _IMAGETRACKER_AVAILABLE = True
except ImportError:
    _IMAGETRACKER_AVAILABLE = False
    ImageTracker = None

__all__ = [
    "Target",
    "FixedPoint",
    "QuickStar",
    "LocalStars",
    "ImageTracker",
    "SkyContext",
    "TimeContext",
    "HardwareContext",
]
