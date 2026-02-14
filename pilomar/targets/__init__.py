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

from .fixed_point import FixedPoint, fixedpoint
from .quickstar import QuickStar, quickstar
from .local_stars import LocalStars, localstars
from .sky_context import SkyContext, TimeContext, HardwareContext
from .sky_context import skycontext, timecontext, hardwarecontext

# Target requires Skyfield - import conditionally
try:
    from .target import Target, target
    _TARGET_AVAILABLE = True
except ImportError:
    _TARGET_AVAILABLE = False
    Target = None
    target = None

# ImageTracker requires opencv and astroalign - import conditionally
try:
    from .image_tracker import ImageTracker, imagetracker
    _IMAGETRACKER_AVAILABLE = True
except ImportError:
    _IMAGETRACKER_AVAILABLE = False
    ImageTracker = None
    imagetracker = None

__all__ = [
    'Target',
    'target',
    'FixedPoint',
    'fixedpoint',
    'QuickStar',
    'quickstar',
    'LocalStars',
    'localstars',
    'ImageTracker',
    'imagetracker',
    'SkyContext',
    'TimeContext',
    'HardwareContext',
    'skycontext',
    'timecontext',
    'hardwarecontext',
]
