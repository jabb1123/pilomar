#!/usr/bin/env python3
"""Direct-GPIO dual-axis stepper driver for Pilomar.

Replaces the UART microcontroller interface with a pigpio hardware-waveform
loop that drives both the altitude and azimuth stepper motors directly from
the Raspberry Pi GPIO pins.  Both axes are timed on the same 5 kHz grid so
they stay in sync automatically — no external MCU is required.

Usage::

    import pigpio
    from pilomar.control.direct_stepper import DualStepperDriver

    pi = pigpio.pi()
    driver = DualStepperDriver(
        pi,
        az_step_pin=21, az_dir_pin=20,
        alt_step_pin=6,  alt_dir_pin=5,
        az_steps_per_rev=384000,
        alt_steps_per_rev=384000,
        flip_az=True,
    )
    driver.set_rates(az_steps_per_sec=400.456, alt_steps_per_sec=100.114)
    # … later …
    driver.stop()
    pi.stop()
"""

import threading
import time

try:
    import pigpio

    _PIGPIO_AVAILABLE = True
except ImportError:
    _PIGPIO_AVAILABLE = False

from pilomar.core.base import AttributeMaster


class DualStepperDriver(AttributeMaster):
    """Drive two stepper axes directly via pigpio hardware waveforms.

    Both axes share a single waveform loop running at *TICK_US* microsecond
    resolution (default 200 µs → 5 kHz grid).  A new waveform chunk covering
    *CHUNK_TIME* seconds is built and sent every iteration so the timing is
    handled by the Pi's DMA engine — not the Python scheduler.

    Attributes:
        az_position_steps: Running azimuth step count (wraps at az_steps_per_rev).
        alt_position_steps: Running altitude step count (wraps at alt_steps_per_rev).
        az_rate: Current azimuth rate in steps/sec (positive = CW looking down).
        alt_rate: Current altitude rate in steps/sec (positive = up).
        running: True while the waveform loop is active.
    """

    # Timing constants
    TICK_US: int = 200  # microseconds per timing slot (5 kHz)
    CHUNK_TIME: float = 0.05  # seconds of waveform built per iteration

    def __init__(
        self,
        pi,
        az_step_pin: int,
        az_dir_pin: int,
        alt_step_pin: int,
        alt_dir_pin: int,
        az_steps_per_rev: int = 384000,
        alt_steps_per_rev: int = 384000,
        flip_az: bool = False,
        flip_alt: bool = False,
        home_pin: int | None = None,
        now_func=None,
        logger=None,
    ):
        """Initialise the dual stepper driver.

        Args:
            pi: Connected ``pigpio.pi`` instance.
            az_step_pin: BCM pin number for azimuth STEP signal.
            az_dir_pin: BCM pin number for azimuth DIR signal.
            alt_step_pin: BCM pin number for altitude STEP signal.
            alt_dir_pin: BCM pin number for altitude DIR signal.
            az_steps_per_rev: Full microstep count for one azimuth revolution.
            alt_steps_per_rev: Full microstep count for one altitude revolution.
            flip_az: Reverse azimuth direction logic.
            flip_alt: Reverse altitude direction logic.
            home_pin: Optional BCM pin for altitude home/limit switch (active LOW).
            now_func: Callable returning current UTC datetime (injected).
            logger: Optional ``LogFile`` instance.
        """
        super().__init__(now_func=now_func)
        self.set_logger(logger)

        if not _PIGPIO_AVAILABLE:
            raise ImportError(
                "pigpio is required for DualStepperDriver. Install it with: pip install pigpio"
            )

        self.pi = pi

        self.az_step_pin = az_step_pin
        self.az_dir_pin = az_dir_pin
        self.alt_step_pin = alt_step_pin
        self.alt_dir_pin = alt_dir_pin

        self.az_steps_per_rev = az_steps_per_rev
        self.alt_steps_per_rev = alt_steps_per_rev

        self.flip_az = flip_az
        self.flip_alt = flip_alt
        self.home_pin = home_pin

        # Position tracking
        self.az_position_steps: int = 0
        self.alt_position_steps: int = 0

        # Rate state (thread-safe via GIL on int/float assignment)
        self.az_rate: float = 0.0
        self.alt_rate: float = 0.0

        self._az_phase: float = 0.0
        self._alt_phase: float = 0.0

        # Configure GPIO outputs
        for pin in (az_step_pin, az_dir_pin, alt_step_pin, alt_dir_pin):
            pi.set_mode(pin, pigpio.OUTPUT)

        if home_pin is not None:
            pi.set_mode(home_pin, pigpio.INPUT)
            pi.set_pull_up_down(home_pin, pigpio.PUD_UP)

        self.running: bool = True
        self._thread = threading.Thread(target=self._waveform_loop, daemon=True)
        self._thread.start()
        self.log(
            f"DualStepperDriver: started "
            f"AZ(step={az_step_pin},dir={az_dir_pin}) "
            f"ALT(step={alt_step_pin},dir={alt_dir_pin})",
            terminal=False,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_rates(self, az_steps_per_sec: float, alt_steps_per_sec: float) -> None:
        """Set the continuous stepping rate for both axes.

        Args:
            az_steps_per_sec: Azimuth rate in steps/sec.  Positive = CW
                (looking down on mount).  Negative = CCW.
            alt_steps_per_sec: Altitude rate in steps/sec.  Positive = up.
                Negative = down.
        """
        self.az_rate = az_steps_per_sec
        self.alt_rate = alt_steps_per_sec

        az_dir_val = (1 if az_steps_per_sec >= 0 else 0) ^ self.flip_az
        alt_dir_val = (1 if alt_steps_per_sec >= 0 else 0) ^ self.flip_alt

        self.pi.write(self.az_dir_pin, az_dir_val)
        self.pi.write(self.alt_dir_pin, alt_dir_val)

    def stop(self) -> None:
        """Stop the waveform loop and release pigpio waveform resources."""
        self.running = False
        self._thread.join(timeout=2.0)
        self.pi.wave_clear()
        self.log("DualStepperDriver: stopped", terminal=False)

    # Position helpers

    def az_degrees(self) -> float:
        """Return current azimuth position in degrees."""
        return (self.az_position_steps / self.az_steps_per_rev) * 360.0

    def alt_degrees(self) -> float:
        """Return current altitude position in degrees."""
        return (self.alt_position_steps / self.alt_steps_per_rev) * 360.0

    def degrees_to_az_steps(self, degrees: float) -> int:
        """Convert an azimuth angle to a step count."""
        return int(degrees / 360.0 * self.az_steps_per_rev)

    def degrees_to_alt_steps(self, degrees: float) -> int:
        """Convert an altitude angle to a step count."""
        return int(degrees / 360.0 * self.alt_steps_per_rev)

    # Home / limit switch

    def home_pin_active(self) -> bool:
        """Return True if the altitude home switch is currently triggered.

        Returns False if no home pin was configured.
        """
        if self.home_pin is None:
            return False
        return self.pi.read(self.home_pin) == 0  # active LOW

    def home_altitude(self, approach_rate: float = 1000.0) -> None:
        """Drive the altitude axis down until the home switch fires.

        After homing, ``alt_position_steps`` is reset to 0 (representing the
        home / horizon position).

        Args:
            approach_rate: Speed in steps/sec for the final approach.
        """
        if self.home_pin is None:
            raise RuntimeError("No home_pin configured — cannot home altitude axis.")

        self.log("DualStepperDriver.home_altitude: starting", terminal=True)

        # If already triggered, back off first
        if self.home_pin_active():
            self.log(
                "DualStepperDriver.home_altitude: already triggered, backing off",
                terminal=True,
            )
            self.set_rates(0.0, approach_rate)
            while self.home_pin_active():
                time.sleep(0.01)
            self.set_rates(0.0, 0.0)
            time.sleep(0.3)

        # Drive towards home
        self.set_rates(0.0, -approach_rate)
        self._wait_for_home_switch()

        self.set_rates(0.0, 0.0)
        time.sleep(0.2)
        self.alt_position_steps = 0
        self.log("DualStepperDriver.home_altitude: complete, position zeroed", terminal=True)

    def _wait_for_home_switch(self, stable_ms: int = 50) -> None:
        """Block until the home switch has been continuously active for *stable_ms*."""
        start: float | None = None
        while True:
            if self.home_pin_active():
                if start is None:
                    start = time.time()
                elif (time.time() - start) * 1000 >= stable_ms:
                    return
            else:
                start = None
            time.sleep(0.005)

    # ------------------------------------------------------------------
    # Internal waveform loop (daemon thread)
    # ------------------------------------------------------------------

    def _waveform_loop(self) -> None:
        """Build and send pigpio hardware waveform chunks continuously.

        Each iteration covers CHUNK_TIME seconds of step pulses.  The DMA
        engine sends the waveform while Python prepares the next one, so
        there is no audible stutter between chunks.
        """
        ticks = int(self.CHUNK_TIME * 1e6 / self.TICK_US)

        while self.running:
            pulses = []

            az_rate = abs(self.az_rate)
            alt_rate = abs(self.alt_rate)

            az_inc = az_rate * self.TICK_US / 1e6
            alt_inc = alt_rate * self.TICK_US / 1e6

            az_step_mask = 1 << self.az_step_pin
            alt_step_mask = 1 << self.alt_step_pin

            for _ in range(ticks):
                on_mask = 0

                self._az_phase += az_inc
                self._alt_phase += alt_inc

                if self._az_phase >= 1.0:
                    on_mask |= az_step_mask
                    self._az_phase -= 1.0
                    self.az_position_steps += 1 if self.az_rate >= 0 else -1
                    self.az_position_steps %= self.az_steps_per_rev

                if self._alt_phase >= 1.0:
                    on_mask |= alt_step_mask
                    self._alt_phase -= 1.0
                    self.alt_position_steps += 1 if self.alt_rate >= 0 else -1
                    self.alt_position_steps %= self.alt_steps_per_rev

                if on_mask:
                    pulses.append(pigpio.pulse(on_mask, 0, self.TICK_US // 2))
                    pulses.append(pigpio.pulse(0, on_mask, self.TICK_US // 2))
                else:
                    pulses.append(pigpio.pulse(0, 0, self.TICK_US))

            if not pulses:
                # Both rates are zero — sleep rather than send an empty wave
                time.sleep(self.CHUNK_TIME)
                continue

            self.pi.wave_add_generic(pulses)
            wid = self.pi.wave_create()
            self.pi.wave_send_once(wid)

            while self.pi.wave_tx_busy():
                time.sleep(0.001)

            self.pi.wave_delete(wid)
