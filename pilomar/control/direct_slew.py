#!/usr/bin/env python3
"""Slew (goto) controller for the direct-GPIO stepper driver.

Handles fast, proportional moves to a target position while pausing sky
tracking, then resumes tracking once the slew is complete.

Usage::

    from pilomar.control.direct_slew import DirectSlewController

    slew = DirectSlewController(driver=driver, tracker=tracker)
    slew.slew_to_target()          # blocks until within tolerance
    slew.slew_to_altaz(45.0, 180.0)  # slew to explicit alt/az
"""

import time
from typing import TYPE_CHECKING, Optional

from pilomar.core.base import AttributeMaster

if TYPE_CHECKING:
    from pilomar.control.direct_stepper import DualStepperDriver
    from pilomar.control.direct_tracker import DirectSkyTracker


class DirectSlewController(AttributeMaster):
    """Proportional goto controller for a :class:`DualStepperDriver`.

    Performs a *stop-track → slew → resume-track* cycle.  Slew speed is
    capped at ``max_rate`` and scaled proportionally to the angular error so
    the mount decelerates naturally as it approaches the target (P-controller).

    Attributes:
        max_rate: Maximum slew speed in steps/sec (both axes).
        tolerance_deg: Angular tolerance in degrees considered "on target".
        gain: Proportional gain applied to step-error for velocity calculation.
    """

    max_rate: float = 3000.0
    tolerance_deg: float = 0.05
    gain: float = 0.8

    def __init__(
        self,
        driver: "DualStepperDriver",
        tracker: Optional["DirectSkyTracker"] = None,
        now_func=None,
        logger=None,
    ):
        """Initialise the slew controller.

        Args:
            driver: The :class:`DualStepperDriver` to command.
            tracker: Optional :class:`DirectSkyTracker` to pause/resume around
                the slew.  If ``None``, tracking state is not managed.
            now_func: Optional UTC datetime callable.
            logger: Optional ``LogFile`` instance.
        """
        super().__init__(now_func=now_func)
        self.set_logger(logger)
        self.driver = driver
        self.tracker = tracker

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def slew_to_target(self) -> None:
        """Slew to the tracker's current target position then resume tracking.

        Requires a tracker with an active target to have been set.

        Raises:
            RuntimeError: If no tracker or no active target is set.
        """
        if self.tracker is None or self.tracker.target is None:
            raise RuntimeError("DirectSlewController.slew_to_target: no tracker target set.")

        target_alt, target_az = self.tracker.current_altaz()
        self.slew_to_altaz(target_alt, target_az, resume_tracking=True)

    def slew_to_altaz(
        self,
        target_alt: float,
        target_az: float,
        resume_tracking: bool = False,
    ) -> None:
        """Slew both axes to an explicit alt/az position.

        Args:
            target_alt: Target altitude in degrees.
            target_az: Target azimuth in degrees.
            resume_tracking: If True, restart the tracker after the slew.
        """
        self.log(
            f"DirectSlewController: slewing to ALT={target_alt:.3f}° AZ={target_az:.3f}°",
            terminal=True,
        )

        # Pause tracking
        if self.tracker is not None:
            self.tracker.running = False

        self.driver.set_rates(0.0, 0.0)
        time.sleep(0.2)

        # P-controller loop
        while True:
            cur_alt = self.driver.alt_degrees()
            cur_az = self.driver.az_degrees()

            d_alt = target_alt - cur_alt
            d_az = self._wrap(target_az - cur_az)

            if abs(d_alt) < self.tolerance_deg and abs(d_az) < self.tolerance_deg:
                break

            alt_steps = self.driver.degrees_to_alt_steps(d_alt)
            az_steps = self.driver.degrees_to_az_steps(d_az)

            alt_rate = max(min(alt_steps * self.gain, self.max_rate), -self.max_rate)
            az_rate = max(min(az_steps * self.gain, self.max_rate), -self.max_rate)

            self.driver.set_rates(
                az_steps_per_sec=az_rate,
                alt_steps_per_sec=alt_rate,
            )

            time.sleep(0.05)

        self.driver.set_rates(0.0, 0.0)
        self.log("DirectSlewController: slew complete", terminal=True)

        # Resume tracking
        if resume_tracking and self.tracker is not None:
            self.tracker._start()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _wrap(deg: float) -> float:
        """Fold an angle difference into ±180°."""
        return ((deg + 180.0) % 360.0) - 180.0
