"""Pilomar Application Module.

This module contains the main application components for the Pilomar
telescope control system, including:

- PilomarApp: Main application class
- Data loaders for astronomical catalogs
- Target selection menus
- Observation control
- Preview image generation

Copyright: GNU General Public License v3.0
"""

from .constants import (
    VERSION,
    ACCEPTABLE_CONTROLLER_VERSIONS,
    DEGREE_SYMBOL,
    SYMBOLS,
)

from .data_loader import (
    CatalogPaths,
    CatalogData,
    CatalogLoader,
    load_dictionary,
    hms_to_degrees,
    dms_to_degrees,
    degrees_to_hms,
    degrees_to_dms,
)

from .target_chooser import (
    TargetSelectionContext,
    TargetChooser,
    create_target_chooser,
)

from .observation import (
    ObservationStatus,
    ObservationResult,
    ObservationContext,
    ObservationLoop,
    start_observation,
    go_to_target,
    document_session,
)

from .main import (
    ApplicationContext,
    Application,
    find_project_root,
    main,
)

__all__ = [
    # Constants
    "VERSION",
    "ACCEPTABLE_CONTROLLER_VERSIONS",
    "DEGREE_SYMBOL",
    "SYMBOLS",
    # Data loading
    "CatalogPaths",
    "CatalogData",
    "CatalogLoader",
    "load_dictionary",
    "hms_to_degrees",
    "dms_to_degrees",
    "degrees_to_hms",
    "degrees_to_dms",
    # Target chooser
    "TargetSelectionContext",
    "TargetChooser",
    "create_target_chooser",
    # Observation
    "ObservationStatus",
    "ObservationResult",
    "ObservationContext",
    "ObservationLoop",
    "start_observation",
    "go_to_target",
    "document_session",
    # Main application
    "ApplicationContext",
    "Application",
    "find_project_root",
    "main",
]
