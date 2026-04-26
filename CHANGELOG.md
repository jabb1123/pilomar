# Changelog

All notable changes to the Pilomar project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-02-14

### Added
- Complete application refactoring with modular architecture
- New `pilomar/app/` module with clean separation of concerns:
  - `main.py` - Application entry point and main menu loop
  - `target_chooser.py` - Target selection for all catalog types
  - `observation.py` - Observation session management
  - `data_loader.py` - Catalog loading with caching
- New `pilomar/config/` module:
  - `parameters.py` - Configuration management with JSON persistence
  - `base.py` - AttributeMaster base class for logging
- New `pilomar/ui/` module:
  - `menu.py` - Menu system with ListChooser for interactive selection
  - `text_color.py` - Terminal color formatting
- Simplified main menu with "Advanced Tools" submenu for less common operations
- Camera Tools menu with comprehensive options:
  - Exposure and batch size settings
  - Dark, flat, bias, and dark flat frame capture
  - Preview and auto capture modes
  - Timelapse delay configuration
  - Meteor scanning
- Motor Tools menu for telescope positioning
- Microcontroller Tools menu for GPIO and LED control
- Tracking Tools menu for drift tracking configuration
- Observation Schedule menu for session planning
- Settings menu with location setup, color scheme, and debug mode
- First-time setup wizard for observer location (lat/lon)
- Automatic catalog loading from Skyfield (Hipparcos, comets from MPC)
- Interactive list chooser for all catalog selections

### Changed
- Restructured codebase from monolithic `pilomar.py` to modular package
- Parameters now load via `importlib.util` to avoid circular imports
- All menus now use consistent navigation ('b' to go back, 'x' to exit)
- Catalog data loaded lazily with proper error handling

### Fixed
- Parameters file now properly created on first run
- Location coordinates parsed correctly in multiple formats (decimal or "51.477 N")
- ListChooser now works with both `prompt()` and `Prompt()` method names

## [0.9.0] - 2025-05-03

### Fixed
- Issue #102: False alarm for SPI being enabled
- Issue #100: Dimension mismatch during tracking operation

### Changed
- Updated pilomarfits.py with improvements

## [0.8.0] - 2025-04-20

### Added
- Default data files for catalogs
- PCG entries added to NGC catalog
- Updated documentation

### Changed
- Reorganized data directory structure

## [0.7.0] - 2025-02-04

### Added
- Brief installation instructions in README
- Installation summary documentation

## [0.6.0] - 2024-11-29

### Added
- Simple guide to motor controller wiring

## [0.5.0] - 2024-09-21

### Fixed
- Issue #91: Tiny2040 corrupted file - re-uploaded code.py
- Issue #89: Corrected Parameters._CameraAutoCommand reference
- Issue #88: Added missing AskYesNo function definition

## [0.4.0] - 2024-09-11

### Added
- GPIOD support for both gpiochip0 and gpiochip4 (Bookworm compatibility)
- Support for Pimoroni Tiny2350 with CircuitPython 9.2
- Support for Raspberry Pi Compute Module 4
- ADC0 pin unassigned by default for flexibility

### Changed
- Extract board model when dealing with compute modules
- Improved serial connection detection for microcontroller

## [0.3.0] - 2024-07-10

### Added
- ChooseLens option added to Camera Tools menu
- FITS export support with astropy package
- IC (Index Catalog) items added to NGC catalog
- Bookworm 64-bit support
- O/S specific build scripts

### Changed
- Metadata capture no longer needs separate exposure
- Documentation updated with example observation

### Fixed
- Issue #64: pidngconvert in new Bookworm build fails
- Issue #53: CalculateStarSpread() bright skies handling

## [0.2.0] - 2024-01-31

### Added
- OptimiseMoves parameter for efficient telescope movement
- Checksum validation improvements
- Updated draft manual with example observations

### Changed
- January 2024 code revisions and testing
- Improved move optimization logic

## [0.1.0] - 2024-01-11

### Added
- Initial public release
- Python3 control software for Raspberry Pi
- CircuitPython firmware for Pimoroni Tiny2040 microcontroller
- Stepper motor control for Alt-Az mount
- Camera integration with Raspberry Pi camera modules
- Support for multiple astronomical catalogs:
  - Messier objects
  - NGC/IC objects
  - Hipparcos star catalog
  - Comets (via Minor Planet Center)
  - Meteor showers
  - Satellites (via CelesTrak)
- Target tracking with drift correction
- Image capture in JPG, DNG, and FITS formats
- Dark, flat, and bias frame calibration
- 3D printable observatory enclosure design (via Instructables)

---

## Links

- [Instructables Build Guide](https://www.instructables.com/Pi-lomar-3D-Printed-Working-Miniature-Observatory-/)
- [GitHub Wiki](https://github.com/Short-bus/pilomar/wiki)
- [Issue Tracker](https://github.com/Short-bus/pilomar/issues)
