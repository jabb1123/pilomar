#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main entry point for the Pilomar application.

This module provides:
- Application initialization
- Main menu loop
- Graceful shutdown handling
"""

import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ApplicationContext:
    """Container for application-wide state and dependencies.
    
    This provides centralized access to all application components,
    replacing the previous global variable approach.
    """
    # Core configuration
    project_root: str = ""
    parameters: Any = None
    
    # Skyfield objects
    timescale: Any = None
    planets: Any = None
    skyfield_loader: Any = None
    
    # Session state
    session: Any = None
    target: Any = None
    
    # Hardware interfaces
    camera: Any = None
    lens: Any = None
    sensor: Any = None
    motor_controls: List[Any] = field(default_factory=list)
    mctl: Any = None  # Microcontroller
    
    # Threading
    camera_thread: Any = None
    mctl_thread: Any = None
    message_thread: Any = None
    
    # Queue interfaces
    camera_control_queue: Any = None
    camera_status_queue: Any = None
    uart_control_queue: Any = None
    
    # Logging
    main_log: Any = None
    camera_log: Any = None
    
    # Data catalogs
    hipparcos_df: Any = None
    ngc_df: Any = None
    comets_df: Any = None
    messier_dict: Dict = field(default_factory=dict)
    meteor_dict: Dict = field(default_factory=dict)
    star_names: Dict = field(default_factory=dict)
    constellation_links: List = field(default_factory=list)
    
    # Folder management
    folder_handler: Any = None
    
    # UI components
    textcolor: Any = None
    menus: Dict[str, Any] = field(default_factory=dict)
    windows: Dict[str, Any] = field(default_factory=dict)
    
    # Observation state
    observation_schedule: Any = None
    suggested_targets: Any = None
    drift_tracker: Any = None
    
    # Storage monitoring
    storage_monitor: Any = None


class Application:
    """Main Pilomar application controller.
    
    This class manages the application lifecycle including:
    - Initialization and configuration loading
    - Menu system setup
    - Main loop execution
    - Graceful shutdown
    """
    
    def __init__(self, project_root: str):
        """Initialize the application.
        
        Args:
            project_root: Path to the Pilomar project root directory
        """
        self.ctx = ApplicationContext(project_root=project_root)
        self._running = False
        self._initialized = False
    
    def _log(self, *args, level: str = 'info', terminal: bool = True):
        """Log a message."""
        if self.ctx.main_log:
            self.ctx.main_log.Log(*args, level=level, terminal=terminal)
        elif terminal:
            print(*args)
    
    def initialize(self) -> bool:
        """Initialize all application components.
        
        This performs the full initialization sequence:
        1. Load configuration/parameters
        2. Initialize Skyfield and ephemeris data
        3. Load astronomical catalogs
        4. Initialize hardware interfaces
        5. Set up UI components
        
        Returns:
            True if initialization successful, False otherwise
        """
        self._log("Initializing Pilomar...")
        
        try:
            # Basic initialization would go here
            # In practice, this would be populated with actual init code
            
            self._initialized = True
            self._log("Initialization complete")
            return True
            
        except Exception as e:
            self._log(f"Initialization failed: {e}", level='error')
            return False
    
    def run(self) -> int:
        """Run the main application loop.
        
        Returns:
            Exit code (0 for success, non-zero for error)
        """
        if not self._initialized:
            if not self.initialize():
                return 1
        
        self._running = True
        self._log("Starting main loop")
        
        try:
            # Main loop - in the original code this is:
            # while True:
            #     MainMenu.Prompt()
            #     if AskYesNo("Do you really want to shut down?"): break
            
            while self._running:
                # Display and handle main menu
                if 'main' in self.ctx.menus:
                    self.ctx.menus['main'].Prompt()
                else:
                    # Fallback if menus not set up
                    self._simple_menu_loop()
                
                # Check for exit condition
                if self._should_exit():
                    break
            
            return 0
            
        except KeyboardInterrupt:
            self._log("Interrupted by user", level='warning')
            return 130  # Standard exit code for Ctrl+C
        except Exception as e:
            self._log(f"Error in main loop: {e}", level='error')
            return 1
        finally:
            self.shutdown()
    
    def _simple_menu_loop(self) -> None:
        """Simple menu loop for when full UI not available."""
        print("\nPilomar - Simple Menu")
        print("=" * 40)
        print("1. Select target")
        print("2. Begin observation")
        print("3. Status")
        print("x. Exit")
        
        choice = input("Choice: ").lower().strip()
        
        if choice == 'x':
            self._running = False
    
    def _should_exit(self) -> bool:
        """Check if the user wants to exit.
        
        Returns:
            True if user confirms exit, False otherwise
        """
        try:
            response = input("Do you really want to shut down? [y/N] ").lower().strip()
            return response in ('y', 'yes')
        except (EOFError, KeyboardInterrupt):
            return True
    
    def shutdown(self) -> None:
        """Perform graceful shutdown.
        
        This ensures all resources are properly released:
        - Stop camera thread
        - Stop motor threads
        - Home motors (if requested)
        - Save parameters
        - Clean up GPIO
        """
        self._log("Shutting down...")
        self._running = False
        
        # Flag observation end
        # FlagObservationEnd()
        
        # Offer to home camera
        self._offer_home_camera()
        
        # Stop camera
        self._shutdown_camera()
        
        # Stop microcontroller
        self._shutdown_microcontroller()
        
        # Stop message handler
        self._shutdown_message_handler()
        
        # Save parameters
        self._save_parameters()
        
        # Cleanup GPIO
        self._cleanup_gpio()
        
        self._log("Shutdown complete")
    
    def _offer_home_camera(self) -> None:
        """Offer to return camera to home position."""
        # In full implementation, check current position vs home
        # and offer to move if not already home
        pass
    
    def _shutdown_camera(self) -> None:
        """Shutdown camera thread gracefully."""
        if self.ctx.camera_thread and self.ctx.camera_thread.is_alive():
            self._log("Stopping camera thread...")
            # Send shutdown signal and wait
            if self.ctx.camera_control_queue:
                self.ctx.camera_control_queue.put({'Shutdown': True})
            self.ctx.camera_thread.join(timeout=10)
    
    def _shutdown_microcontroller(self) -> None:
        """Shutdown microcontroller communication."""
        if self.ctx.mctl:
            self._log("Stopping microcontroller...")
            if hasattr(self.ctx.mctl, 'Reset'):
                self.ctx.mctl.Reset(planned=True)
        
        if self.ctx.uart_control_queue:
            self.ctx.uart_control_queue.put('stop')
        
        if self.ctx.mctl_thread and self.ctx.mctl_thread.is_alive():
            self.ctx.mctl_thread.join(timeout=10)
    
    def _shutdown_message_handler(self) -> None:
        """Shutdown message handler thread."""
        if self.ctx.message_thread and self.ctx.message_thread.is_alive():
            self._log("Stopping message handler...")
            self.ctx.message_thread.join(timeout=10)
    
    def _save_parameters(self) -> None:
        """Save current parameters to disk."""
        if self.ctx.parameters:
            self._log("Saving parameters...")
            if hasattr(self.ctx.parameters, 'SaveAttributes'):
                self.ctx.parameters.SaveAttributes(
                    getattr(self.ctx.parameters, 'ParamFileName', 'parameters.json')
                )
    
    def _cleanup_gpio(self) -> None:
        """Clean up GPIO state."""
        # GPIO cleanup would go here
        pass


def find_project_root() -> str:
    """Find the Pilomar project root directory.
    
    Searches up from current directory looking for markers like
    'pilomar.py', 'data/' directory, etc.
    
    Returns:
        Path to project root, or current directory if not found
    """
    # Check environment variable first
    if 'PILOMAR_ROOT' in os.environ:
        return os.environ['PILOMAR_ROOT']
    
    # Look for markers in current directory and parents
    markers = ['data', 'pilomar', 'parameters.json']
    current = os.getcwd()
    
    for _ in range(5):  # Don't search too far up
        for marker in markers:
            if os.path.exists(os.path.join(current, marker)):
                return current
        parent = os.path.dirname(current)
        if parent == current:  # Reached root
            break
        current = parent
    
    return os.getcwd()


def main(args: Optional[List[str]] = None) -> int:
    """Main entry point for Pilomar.
    
    Args:
        args: Command line arguments (uses sys.argv if None)
        
    Returns:
        Exit code
    """
    if args is None:
        args = sys.argv[1:]
    
    # Parse any command line arguments
    project_root = find_project_root()
    
    for i, arg in enumerate(args):
        if arg in ('--root', '-r') and i + 1 < len(args):
            project_root = args[i + 1]
        elif arg in ('--help', '-h'):
            print("Pilomar - Astronomical observation control")
            print()
            print("Usage: pilomar [options]")
            print()
            print("Options:")
            print("  -r, --root DIR    Set project root directory")
            print("  -h, --help        Show this help message")
            return 0
    
    # Create and run application
    app = Application(project_root)
    return app.run()


# Entry point
if __name__ == '__main__':
    sys.exit(main())
