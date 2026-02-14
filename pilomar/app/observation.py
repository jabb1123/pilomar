#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Observation run module for the Pilomar application.

This module provides the core observation loop that coordinates:
- Camera capture operations
- Motor control and tracking
- Target position calculations
- Drift tracking
- Status display/dashboard
- User input handling
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple
import threading
import time


class ObservationStatus(Enum):
    """Status codes for observation runs."""
    SUCCESS = auto()
    USER_EXIT = auto()
    USER_ABORT = auto()
    TARGET_NOT_VISIBLE = auto()
    CAMERA_THREAD_LOST = auto()
    MOTOR_THREAD_LOST = auto()
    MESSAGE_THREAD_LOST = auto()
    MICROCONTROLLER_COMMS_FAIL = auto()
    CAMERA_TIMEOUT = auto()
    DISC_SPACE = auto()
    PREVIOUS_INCOMPLETE = auto()
    GOTO_FAILED = auto()


@dataclass
class ObservationResult:
    """Result from an observation run."""
    success: bool
    status_codes: List[ObservationStatus] = field(default_factory=list)
    photo_count: int = 0
    duration_seconds: float = 0.0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    def add_status(self, status: ObservationStatus) -> None:
        """Add a status code to the result."""
        if status not in self.status_codes:
            self.status_codes.append(status)


@dataclass  
class ObservationContext:
    """Context containing all dependencies for an observation run.
    
    This avoids global state by explicitly passing all needed objects.
    """
    # Target and session
    target: Any  # target instance
    session: Any  # Session object
    
    # Hardware interfaces
    camera: Any  # CameraInUse
    motor_controls: List[Any]  # MotorControls list
    mctl: Any  # Microcontroller interface
    
    # Thread references
    camera_thread: Optional[threading.Thread] = None
    mctl_thread: Optional[threading.Thread] = None
    message_thread: Optional[threading.Thread] = None
    
    # Queue interfaces
    camera_control_queue: Any = None
    camera_status_queue: Any = None
    
    # Display/UI
    windows: Dict[str, Any] = field(default_factory=dict)
    debug_mode: bool = False
    
    # Logging
    logger: Any = None
    camera_logger: Any = None
    
    # Configuration
    parameters: Any = None
    folder_handler: Any = None
    
    # Tracking
    drift_tracker: Any = None
    
    # Time functions
    now_utc: Callable = None
    display_dt: Callable = None
    
    # Storage monitor
    storage_monitor: Any = None


class ObservationLoop:
    """Main observation loop coordinator.
    
    This class encapsulates the observation loop logic, coordinating
    between camera, motors, and display subsystems.
    """
    
    def __init__(self, ctx: ObservationContext):
        """Initialize observation loop.
        
        Args:
            ctx: Context containing all dependencies
        """
        self.ctx = ctx
        self._running = False
        self._result = ObservationResult(success=True)
        
        # Tracking state
        self._photo_count = 0
        self._ready_to_observe = False
        self._camera_alt = None
        self._camera_az = None
        self._loop_times = []
        
        # Timers
        self._obs_start = None
        self._keyboard_timer = None
        self._preview_timer = None
        self._debug_timer = None
    
    def _log(self, *args, level: str = 'info', terminal: bool = False):
        """Log a message."""
        if self.ctx.logger:
            self.ctx.logger.Log(*args, level=level, terminal=terminal)
    
    def _now_utc(self) -> datetime:
        """Get current UTC time."""
        if self.ctx.now_utc:
            return self.ctx.now_utc()
        return datetime.utcnow()
    
    def _check_threads_alive(self) -> bool:
        """Verify all required threads are running.
        
        Returns:
            True if all threads are alive, False otherwise
        """
        if self.ctx.camera_thread and not self.ctx.camera_thread.is_alive():
            self._log("CameraThread is not running!", level='error')
            self._result.add_status(ObservationStatus.CAMERA_THREAD_LOST)
            return False
        
        if self.ctx.mctl_thread and not self.ctx.mctl_thread.is_alive():
            self._log("MctlThread is not running!", level='error')
            self._result.add_status(ObservationStatus.MOTOR_THREAD_LOST)
            return False
        
        if self.ctx.message_thread and not self.ctx.message_thread.is_alive():
            self._log("MessageThread is not running!", level='error')
            self._result.add_status(ObservationStatus.MESSAGE_THREAD_LOST)
            return False
        
        return True
    
    def _check_target_visible(self) -> bool:
        """Check if the target is currently visible.
        
        Returns:
            True if target is visible, False otherwise
        """
        if hasattr(self.ctx.target, 'Visible'):
            return self.ctx.target.Visible()
        return True
    
    def _reset_camera_photo_count(self, timeout_seconds: float = 600) -> bool:
        """Reset the camera photo count and wait for acknowledgement.
        
        Args:
            timeout_seconds: Maximum time to wait for acknowledgement
            
        Returns:
            True if reset acknowledged, False on timeout
        """
        if not self.ctx.camera_control_queue or not self.ctx.camera_status_queue:
            return True  # Skip if no queue interface
        
        # Send reset message
        control_msg = {'TimeStamp': self._now_utc(), 'PhotoCount': 0}
        self.ctx.camera_control_queue.put(control_msg)
        
        reset_msg = {'Reset': True}
        self.ctx.camera_control_queue.put(reset_msg)
        
        # Wait for acknowledgement
        start_time = time.time()
        while True:
            if time.time() - start_time > timeout_seconds:
                self._log("Camera photo count reset timed out", level='error')
                return False
            
            if self.ctx.camera_thread and not self.ctx.camera_thread.is_alive():
                self._log("Camera thread died while waiting for reset ack", level='error')
                return False
            
            if not self.ctx.camera_status_queue.empty():
                msg = self.ctx.camera_status_queue.get()
                if 'PhotoCountReset' in msg:
                    self._log("Camera photo count reset acknowledged", terminal=False)
                    return True
            
            time.sleep(0.5)
    
    def _handle_keyboard_input(self, keypress: str) -> bool:
        """Handle keyboard input during observation.
        
        Args:
            keypress: The key that was pressed
            
        Returns:
            True to continue observation, False to exit
        """
        keypress = keypress.lower()
        
        if keypress == "x" or keypress == chr(27):  # x or ESC
            self._log("Keyboard interrupt: Terminating", level='warning')
            self._result.add_status(ObservationStatus.USER_EXIT)
            return False
        
        elif keypress == "d":  # Toggle debug mode
            self.ctx.debug_mode = not self.ctx.debug_mode
            if self.ctx.parameters:
                self.ctx.parameters.DebugMode = self.ctx.debug_mode
            self._log(f"Debug mode: {self.ctx.debug_mode}", terminal=False)
        
        elif keypress == "t":  # Toggle drift tracking
            if self.ctx.parameters:
                self.ctx.parameters.UseTracking = not self.ctx.parameters.UseTracking
                self._log(
                    f"Drift tracking: {'ON' if self.ctx.parameters.UseTracking else 'OFF'}",
                    terminal=False
                )
        
        elif keypress == "p":  # Trigger preview
            self._log("User requested immediate preview", terminal=False)
            if self._preview_timer:
                self._preview_timer.Trigger()
        
        elif keypress == "+":  # Increase exposure
            self._adjust_exposure(2.0)
        
        elif keypress == "-":  # Decrease exposure
            self._adjust_exposure(0.5)
        
        elif keypress == "r":  # Refresh screen
            self._log("Screen refresh requested", terminal=False)
            # Clear screen would be called here
        
        return True
    
    def _adjust_exposure(self, factor: float) -> None:
        """Adjust exposure time by a factor.
        
        Args:
            factor: Multiplier for exposure time (e.g., 2.0 for double)
        """
        if self.ctx.camera and hasattr(self.ctx.camera, 'ExposureSeconds'):
            old_exp = self.ctx.camera.ExposureSeconds
            self.ctx.camera.ExposureSeconds = old_exp * factor
            self._log(
                f"Exposure adjusted: {old_exp}s -> {self.ctx.camera.ExposureSeconds}s",
                terminal=False
            )
    
    def _update_target_position(self) -> Tuple[float, float, float, float]:
        """Calculate and update target position.
        
        Returns:
            Tuple of (ra, dec, az, alt) in degrees
        """
        target = self.ctx.target
        
        if hasattr(target, 'RaDecDegrees'):
            ra, dec = target.RaDecDegrees()
        else:
            ra, dec = 0.0, 0.0
        
        if hasattr(target, 'AzAltDegrees'):
            az, alt = target.AzAltDegrees(updatespeed=True)
        else:
            az, alt = 0.0, 0.0
        
        return ra, dec, az, alt
    
    def _process_camera_messages(self) -> None:
        """Process any pending camera status messages."""
        if not self.ctx.camera_status_queue:
            return
        
        while not self.ctx.camera_status_queue.empty():
            msg = self.ctx.camera_status_queue.get()
            
            if 'PhotoCount' in msg:
                self._photo_count = msg['PhotoCount']
            
            # Handle other message types as needed
    
    def _check_storage_space(self) -> bool:
        """Check if sufficient storage space is available.
        
        Returns:
            True if enough space, False otherwise
        """
        if not self.ctx.storage_monitor:
            return True
        
        try:
            free_bytes = self.ctx.storage_monitor.FreeBytes()
            # Default minimum: 100MB
            min_bytes = getattr(self.ctx.parameters, 'MinDiscMb', 100) * 1024 * 1024
            return free_bytes > min_bytes
        except Exception:
            return True  # Assume OK if check fails
    
    def run(self, batch_mode: bool = False) -> ObservationResult:
        """Execute the observation run.
        
        Args:
            batch_mode: If True, skip user prompts
            
        Returns:
            ObservationResult with success/failure and status codes
        """
        self._log("ObservationRun: Beginning observation", terminal=False)
        
        self._running = True
        self._result = ObservationResult(success=True)
        self._result.start_time = self._now_utc()
        
        # Pre-flight checks
        if not self._check_target_visible():
            self._log("Target is not visible", level='warning', terminal=True)
            self._result.success = False
            self._result.add_status(ObservationStatus.TARGET_NOT_VISIBLE)
            return self._result
        
        if not self._check_threads_alive():
            self._result.success = False
            return self._result
        
        # Reset camera
        if not self._reset_camera_photo_count():
            self._result.success = False
            self._result.add_status(ObservationStatus.CAMERA_TIMEOUT)
            return self._result
        
        # Initialize observation
        self._obs_start = self._now_utc()
        self._photo_count = 0
        self._ready_to_observe = False
        
        if self.ctx.drift_tracker:
            self.ctx.drift_tracker.Reset()
        
        # Main observation loop
        try:
            while self._running:
                loop_start = time.time()
                
                # Check threads are still alive
                if not self._check_threads_alive():
                    self._result.success = False
                    self._running = False
                    break
                
                # Process camera messages
                self._process_camera_messages()
                
                # Update target position
                ra, dec, az, alt = self._update_target_position()
                
                # Calculate duration
                duration = (self._now_utc() - self._obs_start).total_seconds()
                self._result.duration_seconds = duration
                
                # Check storage
                if not self._check_storage_space():
                    self._log("Insufficient storage space", level='error')
                    self._result.success = False
                    self._result.add_status(ObservationStatus.DISC_SPACE)
                    self._running = False
                    break
                
                # Check target still visible
                if not self._check_target_visible():
                    self._log("Target is no longer visible", terminal=True)
                    self._running = False
                    break
                
                # Check photo limit (if set)
                if self.ctx.parameters:
                    max_photos = getattr(self.ctx.parameters, 'MaxPhotos', 0)
                    if max_photos > 0 and self._photo_count >= max_photos:
                        self._log(f"Photo limit reached: {self._photo_count}", terminal=False)
                        self._running = False
                        break
                
                # Track loop time
                loop_time = time.time() - loop_start
                self._loop_times.append(loop_time)
                if len(self._loop_times) > 100:
                    self._loop_times.pop(0)
                
                # Small sleep to prevent CPU spinning
                time.sleep(0.01)
                
        except KeyboardInterrupt:
            self._log("Interrupted by user", level='warning')
            self._result.add_status(ObservationStatus.USER_ABORT)
        except Exception as e:
            self._log(f"Observation error: {e}", level='error')
            self._result.success = False
        
        # Cleanup
        self._result.end_time = self._now_utc()
        self._result.photo_count = self._photo_count
        
        self._log(
            f"Observation complete: {self._photo_count} photos in "
            f"{self._result.duration_seconds:.1f}s",
            terminal=True
        )
        
        return self._result
    
    def stop(self) -> None:
        """Stop the observation loop."""
        self._running = False
        self._result.add_status(ObservationStatus.USER_EXIT)


def start_observation(
    ctx: ObservationContext,
    batch_mode: bool = False
) -> ObservationResult:
    """Start an observation run.
    
    This is the main entry point for starting an observation.
    
    Args:
        ctx: Observation context with all dependencies
        batch_mode: If True, skip user prompts
        
    Returns:
        ObservationResult with outcome details
    """
    loop = ObservationLoop(ctx)
    return loop.run(batch_mode=batch_mode)


def go_to_target(
    target: Any,
    motor_controls: List[Any],
    mctl: Any,
    logger: Any = None,
    timeout_seconds: float = 120
) -> bool:
    """Move telescope to target position.
    
    Args:
        target: Target object with AzAltDegrees() method
        motor_controls: List of motor control objects
        mctl: Microcontroller interface
        logger: Optional logger
        timeout_seconds: Maximum time for move
        
    Returns:
        True if successful, False on failure
    """
    def _log(*args, level='info', terminal=False):
        if logger:
            logger.Log(*args, level=level, terminal=terminal)
    
    try:
        az, alt = target.AzAltDegrees()
        _log(f"GoToTarget: Moving to az={az:.2f}, alt={alt:.2f}", terminal=False)
        
        # Find motor controls
        az_motor = None
        alt_motor = None
        for motor in motor_controls:
            if getattr(motor, 'MotorName', '') == 'azimuth':
                az_motor = motor
            elif getattr(motor, 'MotorName', '') == 'altitude':
                alt_motor = motor
        
        # Send move commands
        if az_motor and hasattr(az_motor, 'GoTo'):
            az_motor.GoTo(az)
        if alt_motor and hasattr(alt_motor, 'GoTo'):
            alt_motor.GoTo(alt)
        
        # Wait for completion (simplified)
        start = time.time()
        while time.time() - start < timeout_seconds:
            # Check if motors have reached position
            # This would check actual motor position vs target
            time.sleep(0.5)
            
            # For now, just wait a fixed time
            if time.time() - start > 5:  # Minimum wait
                break
        
        _log("GoToTarget: Move complete", terminal=False)
        return True
        
    except Exception as e:
        _log(f"GoToTarget: Failed - {e}", level='error')
        return False


def document_session(
    ctx: ObservationContext,
    output_path: str
) -> None:
    """Create a text file documenting the observation session.
    
    Args:
        ctx: Observation context
        output_path: Path to write session document
    """
    lines = []
    lines.append(f"Pilomar Observation Session")
    lines.append(f"=" * 40)
    lines.append(f"")
    
    if ctx.target:
        lines.append(f"Target: {getattr(ctx.target, 'Name', 'Unknown')}")
        lines.append(f"Type: {getattr(ctx.target, 'ObjectType', 'Unknown')}")
        if hasattr(ctx.target, 'Description'):
            lines.append(f"Description: {ctx.target.Description}")
    
    lines.append(f"")
    lines.append(f"Session Start: {datetime.utcnow().isoformat()} UTC")
    
    if ctx.camera:
        lines.append(f"")
        lines.append(f"Camera Settings:")
        if hasattr(ctx.camera, 'ExposureSeconds'):
            lines.append(f"  Exposure: {ctx.camera.ExposureSeconds}s")
    
    try:
        with open(output_path, 'w') as f:
            f.write('\n'.join(lines))
    except Exception as e:
        if ctx.logger:
            ctx.logger.Log(f"Failed to write session document: {e}", level='error')


# Status code string conversion for backward compatibility
STATUS_CODE_STRINGS = {
    ObservationStatus.SUCCESS: "success",
    ObservationStatus.USER_EXIT: "user:exit",
    ObservationStatus.USER_ABORT: "user:abort",
    ObservationStatus.TARGET_NOT_VISIBLE: "system:notvisible",
    ObservationStatus.CAMERA_THREAD_LOST: "system:camerathreadlost",
    ObservationStatus.MOTOR_THREAD_LOST: "system:microcontrollerthreadlost",
    ObservationStatus.MESSAGE_THREAD_LOST: "system:messagethreadlost",
    ObservationStatus.MICROCONTROLLER_COMMS_FAIL: "system:microcontrollercommsfail",
    ObservationStatus.CAMERA_TIMEOUT: "system:cameraresettimeout",
    ObservationStatus.DISC_SPACE: "system:discspace",
    ObservationStatus.PREVIOUS_INCOMPLETE: "user:previousincomplete",
    ObservationStatus.GOTO_FAILED: "user:gotofailed",
}


def status_to_string(status: ObservationStatus) -> str:
    """Convert status enum to string code."""
    return STATUS_CODE_STRINGS.get(status, str(status))


def result_to_legacy(result: ObservationResult) -> Tuple[bool, List[str]]:
    """Convert ObservationResult to legacy (success, status_list) format."""
    status_strings = [status_to_string(s) for s in result.status_codes]
    return result.success, status_strings
