#!/usr/bin/env python3
"""Sky-tracking loop for the direct-GPIO stepper driver.

Wraps a :class:`~pilomar.control.direct_stepper.DualStepperDriver` and uses
Skyfield to compute the angular velocity of any sky target at the observer's
location, then converts that to motor step rates and feeds them to the driver
continuously.

This replaces the MCU-based trajectory system for mounts that drive motors
directly from the Pi GPIO (no external microcontroller).

Usage::

    import pigpio
    from pilomar.control.direct_stepper import DualStepperDriver
    from pilomar.control.direct_tracker import DirectSkyTracker

    pi = pigpio.pi()
    driver = DualStepperDriver(pi, ...)

    tracker = DirectSkyTracker(
        driver=driver,
        lat=41.728,
        lon=-71.504,
        elevation_m=10,
    )
    tracker.track_ra_dec(ra_hours=18.615, dec_degrees=38.784)
    # … observe …
    tracker.stop()
"""

import threading
import time
from collections.abc import Callable
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from skyfield.api import Star, load, wgs84

from pilomar.core.base import AttributeMaster

if TYPE_CHECKING:
    from pilomar.control.direct_stepper import DualStepperDriver


class DirectSkyTracker(AttributeMaster):
    """Continuously track a sky target by computing alt/az rates via Skyfield.

    The tracker runs a daemon thread that:

    1. Computes the current and near-future alt/az of the target.
    2. Derives the angular velocity (deg/sec) for each axis.
    3. Converts that to motor steps/sec using the driver's gear constants.
    4. Calls :meth:`~pilomar.control.direct_stepper.DualStepperDriver.set_rates`.

    Attributes:
        running: True while the tracking loop is active.
        target: Current Skyfield target object (``Star`` or planet body).
    """

    UPDATE_HZ: float = 5.0  # How often to recompute rates (per second)
    LOOKAHEAD_S: float = 0.5  # Seconds ahead used to estimate angular velocity

    def __init__(
        self,
        driver: "DualStepperDriver",
        lat: float,
        lon: float,
        elevation_m: float = 0.0,
        ephemeris: str = "de421.bsp",
        now_func: Callable | None = None,
        logger=None,
    ):
        """Initialise the sky tracker.

        Args:
            driver: The :class:`DualStepperDriver` to send rates to.
            lat: Observer latitude in decimal degrees (north positive).
            lon: Observer longitude in decimal degrees (east positive).
            elevation_m: Observer elevation above sea level in metres.
            ephemeris: Skyfield ephemeris file name (must be loadable).
            now_func: Optional UTC datetime callable (for testing / time offsets).
            logger: Optional ``LogFile`` instance.
        """
        super().__init__(now_func=now_func)
        self.set_logger(logger)

        self.driver = driver
        self.lat = lat
        self.lon = lon
        self.elevation_m = elevation_m

        self.ts = load.timescale()
        self.eph = load(ephemeris)
        self.observer = wgs84.latlon(lat, lon, elevation_m)

        self.target: Any | None = None
        self.running: bool = False
        self._thread: threading.Thread | None = None

        self.log(
            f"DirectSkyTracker: observer ({lat:.4f}, {lon:.4f}) elevation={elevation_m}m",
            terminal=False,
        )

    # ------------------------------------------------------------------
    # Target selection
    # ------------------------------------------------------------------

    def track_ra_dec(self, ra_hours: float, dec_degrees: float) -> None:
        """Track a fixed equatorial coordinate.

        Args:
            ra_hours: Right ascension in decimal hours (0–24).
            dec_degrees: Declination in decimal degrees (±90).
        """
        self.target = Star(ra_hours=ra_hours, dec_degrees=dec_degrees)
        self.log(
            f"DirectSkyTracker.track_ra_dec: RA={ra_hours:.4f}h Dec={dec_degrees:.4f}°",
            terminal=False,
        )
        self._start()

    def track_body(self, body_name: str) -> None:
        """Track a solar-system body by ephemeris name (e.g. ``'mars'``).

        Args:
            body_name: Skyfield body name as it appears in the loaded ephemeris.
        """
        self.target = self.eph[body_name]
        self.log(f"DirectSkyTracker.track_body: {body_name}", terminal=False)
        self._start()

    def start(self) -> None:
        """Start (or restart) the tracking loop for the current target.

        If a thread is already running it is stopped first so there is never
        more than one tracking thread active at a time.

        Raises:
            RuntimeError: If no target has been set.
        """
        if self.target is None:
            raise RuntimeError("DirectSkyTracker.start: no target set.")
        # Ensure any prior thread is fully stopped before spawning a new one.
        if self.running or (self._thread is not None and self._thread.is_alive()):
            self.stop()
        self._start()

    def stop(self) -> None:
        """Stop the tracking loop and zero the motor rates."""
        self.running = False
        if self._thread is not None:
            self._thread.join(timeout=3.0)
        self.driver.set_rates(0.0, 0.0)
        self.log("DirectSkyTracker: stopped", terminal=False)

    # ------------------------------------------------------------------
    # Current position query (used by SlewController)
    # ------------------------------------------------------------------

    def current_altaz(self) -> tuple[float, float]:
        """Return the target's current (altitude, azimuth) in degrees.

        Returns:
            ``(alt_degrees, az_degrees)`` tuple.
        """
        t = self.ts.now()
        return self._altaz(t)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _start(self) -> None:
        if not self.running:
            self.running = True
            self._thread = threading.Thread(target=self._loop, daemon=True, name="DirectSkyTracker")
            self._thread.start()

    def _loop(self) -> None:
        interval = 1.0 / self.UPDATE_HZ
        while self.running and self.target is not None:
            now = self.ts.now()
            future = self.ts.from_datetime(now.utc_datetime() + timedelta(seconds=self.LOOKAHEAD_S))

            alt1, az1 = self._altaz(now)
            alt2, az2 = self._altaz(future)

            if alt1 < 0.0:
                self.log(
                    "DirectSkyTracker: target below horizon, pausing",
                    terminal=True,
                )
                self.driver.set_rates(0.0, 0.0)
                time.sleep(1.0)
                continue

            # Angular velocity in degrees/sec
            alt_rate_deg = (alt2 - alt1) / self.LOOKAHEAD_S
            az_rate_deg = self._wrap_angle(az2 - az1) / self.LOOKAHEAD_S

            # Convert to motor steps/sec
            alt_steps = self._deg_per_sec_to_alt_steps(alt_rate_deg)
            az_steps = self._deg_per_sec_to_az_steps(az_rate_deg)

            self.driver.set_rates(
                az_steps_per_sec=az_steps,
                alt_steps_per_sec=alt_steps,
            )

            time.sleep(interval)

    def _altaz(self, t) -> tuple[float, float]:
        earth = self.eph["earth"]
        observer = earth + self.observer
        astrometric = observer.at(t).observe(self.target)
        alt, az, _ = astrometric.apparent().altaz()
        return alt.degrees, az.degrees

    @staticmethod
    def _wrap_angle(deg: float) -> float:
        """Fold an angle difference into ±180°."""
        return ((deg + 180.0) % 360.0) - 180.0

    def _deg_per_sec_to_alt_steps(self, deg_per_sec: float) -> float:
        return deg_per_sec * self.driver.alt_steps_per_rev / 360.0

    def _deg_per_sec_to_az_steps(self, deg_per_sec: float) -> float:
        return deg_per_sec * self.driver.az_steps_per_rev / 360.0
