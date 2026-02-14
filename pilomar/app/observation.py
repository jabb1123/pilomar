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
    
    def _stop_motors(self) -> None:
        """Send stop command to motors and clear trajectories."""
        if self.ctx.mctl:
            if hasattr(self.ctx.mctl, 'WriteFlush'):
                self.ctx.mctl.WriteFlush(send=False)
            if hasattr(self.ctx.mctl, 'Write'):
                self.ctx.mctl.Write('stop')
                self.ctx.mctl.Write('clear trajectory')
        self._log("Motors stopped", terminal=False)
    
    def _goto_target(self) -> bool:
        """Move telescope directly to target position.
        
        Returns:
            True if successful, False on failure
        """
        if not self.ctx.target or not self.ctx.motor_controls:
            return True  # Skip if no hardware
        
        try:
            az, alt = self.ctx.target.AzAltDegrees()
            self._log(f"GoToTarget: Moving to az={az:.2f}, alt={alt:.2f}", terminal=True)
            
            for motor in self.ctx.motor_controls:
                motor_name = getattr(motor, 'MotorName', getattr(motor, 'motor_name', ''))
                target_angle = az if motor_name == 'azimuth' else alt
                
                if hasattr(motor, 'GoToAngle'):
                    motor.MonitorMove = True
                    result = motor.GoToAngle(target_angle)
                    motor.MonitorMove = False
                    if not result:
                        self._log(f"GoToTarget: {motor_name} move failed", level='error')
                        return False
            
            self._stop_motors()
            self._log("GoToTarget: Move complete", terminal=True)
            return True
            
        except Exception as e:
            self._log(f"GoToTarget failed: {e}", level='error')
            return False
    
    def _extend_trajectories(self) -> None:
        """Calculate and send trajectory extensions for all motors."""
        if not self.ctx.motor_controls or not self.ctx.target:
            return
        
        for motor in self.ctx.motor_controls:
            if hasattr(motor, 'ExtendTrajectory'):
                try:
                    motor.ExtendTrajectory(self.ctx.target)
                except Exception as e:
                    self._log(f"Trajectory extension failed: {e}", level='error')
    
    def _check_target_in_range(self, az: float, alt: float) -> bool:
        """Check if target position is within motor limits.
        
        Args:
            az: Target azimuth in degrees
            alt: Target altitude in degrees
            
        Returns:
            True if in range, False otherwise
        """
        if not self.ctx.motor_controls:
            return True
        
        for motor in self.ctx.motor_controls:
            motor_name = getattr(motor, 'MotorName', getattr(motor, 'motor_name', ''))
            min_angle = getattr(motor, 'MinObservationAngle', getattr(motor, 'MinAngle', 0))
            max_angle = getattr(motor, 'MaxAngle', 360)
            
            if motor_name == 'altitude':
                if alt < min_angle or alt > max_angle:
                    self._log(f"Target altitude {alt:.1f} outside range [{min_angle}, {max_angle}]", 
                              level='warning', terminal=True)
                    return False
            elif motor_name == 'azimuth':
                if az < min_angle or az > max_angle:
                    self._log(f"Target azimuth {az:.1f} outside range [{min_angle}, {max_angle}]",
                              level='warning', terminal=True)
                    return False
        
        return True
    
    def _update_camera_ready_status(self, ready: bool) -> None:
        """Update camera about observation readiness.
        
        Args:
            ready: Whether telescope is on target and ready
        """
        if not self.ctx.camera_control_queue:
            return
        
        control_msg = {
            'TimeStamp': self._now_utc(),
            'ReadyToObserve': ready,
            'BatchSize': getattr(self.ctx.parameters, 'BatchSize', 1) if self.ctx.parameters else 1
        }
        self.ctx.camera_control_queue.put(control_msg)
        self._log(f"Camera ReadyToObserve: {ready}", terminal=False)
    
    def _is_on_target(self, az: float, alt: float) -> bool:
        """Check if camera is pointing at target position.
        
        Args:
            az: Target azimuth
            alt: Target altitude
            
        Returns:
            True if on target within tolerance
        """
        if not self.ctx.motor_controls:
            return True  # Assume on target if no motors
        
        tolerance = 0.5  # degrees
        
        for motor in self.ctx.motor_controls:
            motor_name = getattr(motor, 'MotorName', getattr(motor, 'motor_name', ''))
            current_angle = getattr(motor, 'CurrentAngle', None)
            
            if current_angle is not None:
                target_angle = az if motor_name == 'azimuth' else alt
                if abs(current_angle - target_angle) > tolerance:
                    return False
        
        return True
    
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
        
        # Initial GOTO to center target
        if not self._goto_target():
            self._log("Failed to move to target", level='error')
            self._result.success = False
            self._result.add_status(ObservationStatus.MOTOR_FAULT)
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
                
                # Check target still in motor range
                if not self._check_target_in_range(az, alt):
                    self._log("Target has moved out of motor range", terminal=True)
                    self._result.add_status(ObservationStatus.MOTOR_RANGE)
                    self._running = False
                    break
                
                # Extend motor trajectories to track target
                self._extend_trajectories()
                
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
                    self._result.add_status(ObservationStatus.TARGET_NOT_VISIBLE)
                    self._running = False
                    break
                
                # Update ReadyToObserve state based on pointing
                is_on_target = self._is_on_target(az, alt)
                if is_on_target != self._ready_to_observe:
                    self._ready_to_observe = is_on_target
                    self._update_camera_ready_status(is_on_target)
                
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
        self._stop_motors()
        self._update_camera_ready_status(False)
        
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
    timeout_seconds: float = 120,
    position_tolerance: float = 0.5
) -> bool:
    """Move telescope to target position.
    
    Args:
        target: Target object with AzAltDegrees() method
        motor_controls: List of motor control objects
        mctl: Microcontroller interface
        logger: Optional logger
        timeout_seconds: Maximum time for move
        position_tolerance: Degrees tolerance for position matching
        
    Returns:
        True if successful, False on failure
    """
    def _log(*args, level='info', terminal=False):
        if logger:
            logger.Log(*args, level=level, terminal=terminal)
    
    def _compare_angles(current: float, target_angle: float, tolerance: float) -> bool:
        """Check if angles match within tolerance."""
        if current is None:
            return False
        diff = abs(current - target_angle)
        # Handle wraparound at 360 degrees
        if diff > 180:
            diff = 360 - diff
        return diff <= tolerance
    
    try:
        az, alt = target.AzAltDegrees()
        _log(f"GoToTarget: Moving to az={az:.2f}, alt={alt:.2f}", terminal=False)
        
        # Find motor controls
        az_motor = None
        alt_motor = None
        for motor in motor_controls:
            name = getattr(motor, 'MotorName', getattr(motor, 'motor_name', ''))
            if name == 'azimuth':
                az_motor = motor
            elif name == 'altitude':
                alt_motor = motor
        
        # Use GoToAngle if available (preferred - handles retries internally)
        # Otherwise fall back to simpler GoTo command
        moves_started = False
        
        if az_motor:
            if hasattr(az_motor, 'GoToAngle'):
                az_motor.MonitorMove = True
                result = az_motor.GoToAngle(az)
                az_motor.MonitorMove = False
                if not result:
                    _log("GoToTarget: Azimuth move failed", level='warning')
                moves_started = True
            elif hasattr(az_motor, 'GoTo'):
                az_motor.GoTo(az)
                moves_started = True
        
        if alt_motor:
            if hasattr(alt_motor, 'GoToAngle'):
                alt_motor.MonitorMove = True
                result = alt_motor.GoToAngle(alt)
                alt_motor.MonitorMove = False
                if not result:
                    _log("GoToTarget: Altitude move failed", level='warning')
                moves_started = True
            elif hasattr(alt_motor, 'GoTo'):
                alt_motor.GoTo(alt)
                moves_started = True
        
        if not moves_started:
            _log("GoToTarget: No motor controls available", level='warning')
            return True  # No motors = success (nothing to move)
        
        # Wait for motors to reach position with actual monitoring
        start = time.time()
        last_change_time = start
        last_positions = {}
        
        while time.time() - start < timeout_seconds:
            # Check all motor positions
            all_in_position = True
            
            for motor in motor_controls:
                name = getattr(motor, 'MotorName', getattr(motor, 'motor_name', ''))
                current = getattr(motor, 'CurrentAngle', None)
                target_angle = az if name == 'azimuth' else alt
                
                if not _compare_angles(current, target_angle, position_tolerance):
                    all_in_position = False
                
                # Track if position has changed (motor is still moving)
                if name in last_positions and current != last_positions[name]:
                    last_change_time = time.time()
                last_positions[name] = current
            
            if all_in_position:
                _log("GoToTarget: All motors in position", terminal=False)
                break
            
            # If no position change for 60 seconds, consider it stalled
            if time.time() - last_change_time > 60:
                _log("GoToTarget: Motors not responding for 60s, aborting", level='warning')
                return False
            
            time.sleep(0.5)
        
        # Final position check
        positions_ok = True
        for motor in motor_controls:
            name = getattr(motor, 'MotorName', getattr(motor, 'motor_name', ''))
            current = getattr(motor, 'CurrentAngle', None)
            target_angle = az if name == 'azimuth' else alt
            
            if not _compare_angles(current, target_angle, position_tolerance * 2):
                _log(f"GoToTarget: {name} not in position: {current} vs {target_angle}", 
                     level='warning')
                positions_ok = False
        
        if positions_ok:
            _log("GoToTarget: Move complete", terminal=False)
        return positions_ok
        
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
