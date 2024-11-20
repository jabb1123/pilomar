from datetime import timedelta
import os
import time
from camera.targets.target import AstroTarget
from circuitpython.code import BoolToString, StringToBool
from pilomar import text_to_int, verify_folder
from utils.math_func import deg_3dp
from utils.params import AttributeMaster, Parameters
from utils.statics import DEGREE_SYMBOL
from utils.text.human_readable import clean_datetime_string, human_readable_seconds
from utils.text.textcolor import TextColor
from utils.time_funcs import datetime2_ts, now_hour_minute_sec, utc_time_stamp, now_utc
from utils.timer import Timer


class MotorControl(AttributeMaster):
    """Representation of remote motor.
    The actual motor is controlled in the microcontroller software,
    this class contains an image of important parameters for
    the motor so that this program can direct it."""

    AllMotors = (
        []
    )  # A list of all sibling motors which is common to all instances of motorcontrol. So any single motor instance can refer to all the other motors if needed via motorcontrol.AllMotors.

    def __init__(
        self,
        name,
        gearratio,
        fullstepsperrev,
        microstepratio,
        minangle,
        maxangle,
        restangle,
        currentangle,
        backlashangle,
        orientation=1,
        limitangle=None,
        horizon=None,
        fasttime=0.001,
        slowtime=0.05,
        timedelta=0.003,
        driver="drv8825",
        slewmicrosteps=1,
        optimisemoves=False,
        logger=None,
        parameters: Parameters = None,
    ):
        """Create an instance of a stepper motor.
        Set up the physical configuration of the gears.
        Set up the electrical configuration of the stepper motor driver."""
        self.set_logger(
            logger
        )  # Inherited from attributemaster: Set up references to chosen logger (or disable if no logger defined).
        self.parameters: Parameters = (
            parameters  # Inherited from attributemaster: Set up references to chosen parameters (or disable if no parameters defined).
        )
        self.motor_name = name  # A unique name to identify the motor, should be the same as the motor's name in the microcontroller side too.
        self.driver = driver  # What driver board is being used?
        self.optimise_moves = optimisemoves  # Is the motor allowed to move freely across the 0/360 movement limit to track targets?
        self.gear_ratio = gearratio
        motorstepsperrev = (
            fullstepsperrev * microstepratio
        )  # Calculate motorstepsperrev to include microstep ratio.
        self.motor_steps_per_rev = motorstepsperrev  # FullStepsPerRev of the motor * any microstepping multiplier.
        self.microstep_ratio = microstepratio  # Just for documentation from this point onwards. Used for observation runs (Smoothest).
        self.slew_microsteps = slewmicrosteps  # When making fast SLEW moves, what microstepping do we use? Used for GOTO and HOME moves.
        self.slew_microsteps = min(
            self.slew_microsteps, self.microstep_ratio
        )  # Slew cannot use finer microstepping than the observation!
        if self.slew_microsteps != slewmicrosteps:
            self.log(
                "motorcontrol(",
                name,
                ") Slew microsteps (",
                slewmicrosteps,
                ") restricted to",
                self.microstep_ratio,
                level="warning",
                terminal=True,
            )
        self.slew_step_multiplier = int(
            round(self.microstep_ratio / self.slew_microsteps, 0)
        )
        self.log(
            "motorcontrol(",
            name,
            ") microstepping=",
            self.microstep_ratio,
            "(observation speed), slew steps=",
            self.slew_microsteps,
            "(goto speed), multiplier=",
            self.slew_step_multiplier,
            terminal=False,
        )
        modesignals = "nnn"  # Default full-step mode signals for the motor driver. (Used during observations).
        slewsignals = "nnn"  # Default full-step mode signals for the motor driver. (Used during large slew/GOTO moves).
        if driver in self.parameters.stepper_driver_data:  # Driver is recognised.
            modelist = self.parameters.stepper_driver_data[driver][
                "modelist"
            ]  # Pull the driver's modelist.
            # What are the mode signals for the selected microstepping ratio of the motor?
            if not str(microstepratio) in modelist:  # Keys are strings, not integers.
                self.log(
                    "motorcontrol(",
                    name,
                    ") observation microstepratio",
                    microstepratio,
                    "is not in",
                    driver,
                    "modelist.",
                    level="error",
                    terminal=True,
                )
                raise Exception(
                    "motorcontrol("
                    + str(name)
                    + ") observation microstepratio "
                    + str(microstepratio)
                    + " is not in "
                    + str(driver)
                    + "modelist."
                )
            # microstep ratio is recognised. Pull the modepin settings.
            modesignals = modelist[str(microstepratio)]["modesignals"]
            self.log(
                "motorcontrol(",
                name,
                ") observation microstep ratio",
                microstepratio,
                "for",
                driver,
                "uses mode settings",
                modesignals,
                terminal=False,
            )
            # What are the mode signals for the selected full step (slew) ratio of the motor?
            if (
                not str(self.slew_microsteps) in modelist
            ):  # Keys are strings, not integers.
                self.log(
                    "motorcontrol(",
                    name,
                    ") slew microstepratio",
                    self.slew_microsteps,
                    "is not in",
                    driver,
                    "modelist.",
                    level="error",
                    terminal=True,
                )
                raise Exception(
                    "motorcontrol(" + str(name) + ") slew microstepratio",
                    self.slew_microsteps,
                    "is not in " + str(driver) + "modelist.",
                )
            # microstep ratio is recognised. Pull the modepin settings.
            slewsignals = modelist[str(self.slew_microsteps)]["modesignals"]
            self.log(
                "motorcontrol(",
                name,
                ") slew microstep ratio",
                self.slew_microsteps,
                "for",
                driver,
                "uses mode settings",
                slewsignals,
                terminal=False,
            )
        else:  # Driver is not recognised.
            self.log(
                "motorcontrol(",
                name,
                ") steppermotor driver",
                driver,
                "is not recognised.",
                level="error",
                terminal=True,
            )
            raise Exception(
                "Steppermotor driver " + str(driver) + " is not recognised."
            )
        # What are the settings for the mode pins to the driver board? (Large SLEW, GOTO and HOME moves)
        self.slew_signals = slewsignals
        # What are the settings for the mode pins to the driver board? (Find movements during observations)
        self.mode_signals = modesignals
        # Can warn if position is within this angle of a limit.
        self.warning_angle = 10
        # If set the motor will not go below this angle when tracking a target.
        # Allows motor to move below the horizon for other reasons, but not track a target below the horizon.
        # If set to None, this has no effect.
        self.horizon = horizon
        self.min_angle = (
            minangle  # Physical minimum angle that this motor is allowed to go to.
        )
        self.min_observation_angle = (
            minangle  # Minimum angle that an observation is allowed to go to.
        )
        if self.horizon is not None:
            self.min_observation_angle = max(
                self.min_angle, self.horizon
            )  # How low can an observation be made?
        self.min_warning_angle = (
            self.min_observation_angle + self.warning_angle
        )  # Can warn if within xx degrees of minimum position.
        self.max_angle = maxangle
        self.max_warning_angle = (
            maxangle - self.warning_angle
        )  # Can warn if within xx degrees of maximum position.
        self.limit_angle = (
            limitangle  # The motor will reverse around a limit rather than crossing it.
        )
        self.orientation = orientation
        self.backlash_angle = backlashangle
        self.current_angle = (
            currentangle  # This will be updated by the microcontroller once running.
        )
        self.previous_angle = None  # Holds angle from previous status message.
        self.previous_mctl_timestamp = None  # Says when the previous angle was set.
        self.rest_angle = restangle
        self.motor_steps_per_axis_degree = self.motor_steps_per_rev / 360.0
        self.axis_steps_per_rev = self.motor_steps_per_rev * self.gear_ratio
        self.motor_configured = False
        self.fast_time = fasttime  # Fastest pulse to the motor STEP signal. (Full speed in large move.) # Was 0.0005
        self.slow_time = slowtime  # Slowest pulse to the motor STEP signal. (Initial speed at start of move.)
        self.time_delta = timedelta  # Acceleration rate for the motor STEP signal.
        self.trajectory_segment_size = 60  # Seconds.
        self.trajectory_valid = False  # Is the microcontroller trajectory valid?
        self.trajectory_entries = (
            0  # Number of trajectory entries stored on the microcontroller.
        )
        self.trajectory_valid_until = None  # The 'end time' of the trajectory as reported from the microcontroller.
        self.last_sent_trajectory_key = None  # Key to the last send trajectory data, we can repeat the transmission and save recalculating it sometimes.
        self.last_sent_trajectory_data = None  # Last trajectory data sent to the microcontroller. This can be re-transmitted to save time if the microcontroller asks again.
        self.on_target = False  # Is the motor currently on target?
        self.latest_tune_start = (
            None  # When did motor last START a TUNE move? (Images could be blurred)
        )
        self.latest_tune_time = None  # When did motor last COMPLETE a TUNE command? (Images could be blurred)
        self.latest_tune_steps = 0
        self.recovery_folder = ProjectRoot + "/data/" + self.motor_name + "_angle"
        self.recovery_file_name = (
            self.recovery_folder + "/" + utc_time_stamp() + ".log"
        )  # Used to record the position of the motor, this can then recover the situation in the event of any failures.
        verify_folder(
            self.recovery_folder
        )  # Make sure that the recovery folder exists.
        self.restore_angle()
        self.last_recovery_angle = (
            self.current_angle
        )  # This is used to detect when the motor has physically moved so we don't keep writing the same position repeatedly to the recovery file.
        self.log(
            "Motor "
            + self.motor_name
            + " recovered to "
            + str(round(self.current_angle, 5))
            + DEGREE_SYMBOL,
            terminal=False,
        )
        self.all_motors.append(
            self
        )  # Class attribute AllMotors points to ALL sibling motors. Can be used to check condition of any other motors too.
        self.status_mctl_timestamp = (
            None  # When did the Microcontroller send the latest status message?
        )
        self.status_local_timestamp = (
            None  # When did the RPi process the latest status message?
        )
        self.axis_speed = 0.0  # Currently calculated telescope speed (degrees/second).
        self.monitor_move = False  # Set to True to enable text updates as moves are performed. False to suppress. GoToAngle(), HomePosition(), SetMotorAngle respect this.
        self.restarted()  # Make sure that status flags are reset for a 'new' unconfigured motor.

    def __del__(self):
        """When deleted, remove this motor from the global list of all available motors."""
        self.all_motors.remove(
            self
        )  # Class attribute AllMotors points to ALL sibling motors. Remove this motor from the list when deleted.

    def show_motor_status(self):
        """Print general status of the motor."""
        print(TextColor.yellow("Motor:", self.motor_name))
        print("Driver:", self.driver)
        print(TextColor.white("Current status:"))
        print("- MotorConfigured:", self.motor_configured)
        print("  Microcontroller acknowledges receipt of configuration")
        print("- CurrentAngle:", deg_3dp(self.current_angle, DEGREE_SYMBOL))
        print("- Position:", self.angle_to_step(self.current_angle), "steps")
        if self.axis_speed is not None and self.axis_speed != 0:
            print(
                "- Latest AxisSpeed:",
                str(round(self.axis_speed, 4)) + DEGREE_SYMBOL + "/s",
            )
            print("  Last reported movement rate of the telescope")
        else:
            print("- Latest AxisSpeed:", self.axis_speed, DEGREE_SYMBOL + "/s")
            print("  Last reported movement rate of the telescope")
        print(TextColor.white("Gearing"))
        print("- GearRatio:", self.gear_ratio)
        print("- MotorStepsPerRev:", self.motor_steps_per_rev)
        print(
            "  Motor native full steps per rev:",
            round(self.motor_steps_per_rev / self.microstep_ratio, 0),
        )
        print("- MotorStepsPerAxisDegree:", round(self.motor_steps_per_axis_degree, 3))
        print("  Motor needs this many steps to move itself 1 degree")
        print("- AxisStepsPerRev:", self.axis_steps_per_rev)
        print("  Motor steps required to move telescope one full revolution")
        print(TextColor.white("Fine motor movements (during observations):"))
        print("- MicrostepRatio:", self.microstep_ratio)
        print("  Included in MotorStepsPerRev")
        print("- ModeSignals:", self.mode_signals)
        print("  Mode pin settings for driver during observations")
        print(TextColor.white("Large motor movements (GOTO and HOME):"))
        print("- Enabled:", self.parameters.slew_enabled)
        print("- SlewMicrosteps:", self.slew_microsteps)
        print("- SlewSignals:", self.slew_signals)
        print("  Mode pin settings for driver during large GOTO moves")
        print(TextColor.white("Configuration:"))
        print("- MinAngle:", deg_3dp(self.min_angle, DEGREE_SYMBOL))
        print("  Telescope will not move below this angle")
        print("- Horizon:", deg_3dp(self.horizon, DEGREE_SYMBOL))
        print(
            "- MinObservationAngle:", deg_3dp(self.min_observation_angle, DEGREE_SYMBOL)
        )
        print("  Observations not allowed below this angle")
        print("- MinWarningAngle:", deg_3dp(self.min_warning_angle, DEGREE_SYMBOL))
        print("  Warning when telescope gets this close to minimum observation angle")
        print("- MaxAngle:", deg_3dp(self.max_angle, DEGREE_SYMBOL))
        print("  Telescope will not move above this angle")
        print("- MaxWarningAngle:", deg_3dp(self.max_warning_angle, DEGREE_SYMBOL))
        print("  Warning when telescope gets this close to maximum angle")
        print("- OptimiseMoves:", self.optimise_moves)
        if self.optimise_moves:
            print(
                "  Trajectories can cross 0/360 limit if the movement is more efficient"
            )
        else:
            print("  Trajectories cannot cross cross 0/360 movement limits")
            print(
                "  Telescope will 'reverse' from a limit to track objects which cross it"
            )
        print("- Orientation:", self.orientation)
        print("  +1 / -1 flips rotation direction of motor")
        print("- BacklashEnabled:", self.parameters.backlash_enabled)
        print("  Allow extra motor movement when changing direction")
        print("- BacklashAngle:", deg_3dp(self.backlash_angle, DEGREE_SYMBOL))
        print("  Size of extra motor movement when changing direction")
        print("- RestAngle:", deg_3dp(self.rest_angle, DEGREE_SYMBOL))
        print("  Home/Parking position of the telescope")
        print("- FastTime:", self.fast_time, "s")
        print("  Approximate steps per second:", round((1 / (2 * self.fast_time)), 2))
        print(
            "  Approximate time for full revolution:",
            human_readable_seconds(self.axis_steps_per_rev * 2 * self.fast_time),
            "(",
            self.axis_steps_per_rev,
            "steps",
            ")",
        )
        print(
            "  Approximate time for telescope to move 10 degrees:",
            human_readable_seconds(self.axis_steps_per_rev * 2 * self.fast_time / 36),
            "(",
            int(self.axis_steps_per_rev / 36),
            "steps",
            ")",
        )
        print("- SlowTime:", self.slow_time, "s")
        print("  Approximate steps per second:", round((1 / (2 * self.slow_time)), 2))
        print("- TimeDelta:", self.time_delta, "s")
        print(TextColor.white("Trajectory:"))
        print("- TrajectorySegmentSize:", self.trajectory_segment_size, "s")
        print("- TrajectoryValid:", self.trajectory_valid)
        print("- TrajectoryEntries:", self.trajectory_entries)
        print("- TrajectoryValidUntil:", self.trajectory_valid_until, "UTC")
        print("- OnTarget:", self.on_target)
        print(TextColor.white("Tuning:"))
        print("- LatestTuneStart:", self.latest_tune_start, "UTC")
        print("- LatestTuneTime:", self.latest_tune_time, "UTC")
        print("- LatestTuneSteps:", self.latest_tune_steps)
        print("- RecoveryFileName:", self.recovery_file_name)
        print("")

    def restarted(self):
        """Call this if the microcontroller restarts.
        This resets some status flags so that we know the motor isn't fully configured yet.
        """
        self.motor_configured = False
        self.on_target = False  # Is the motor currently on target?
        self.trajectory_valid = False  # Is the microcontroller trajectory valid?
        self.trajectory_entries = (
            0  # Number of trajectory entries stored on the microcontroller.
        )
        self.trajectory_valid_until = None  # The 'end time' of the trajectory as reported from the microcontroller.
        self.last_sent_trajectory_key = None  # Key to the last send trajectory data, we can repeat the transmission and save recalculating it sometimes.
        self.last_sent_trajectory_data = None  # Last trajectory data sent to the microcontroller. This can be re-transmitted to save time if the microcontroller asks again.
        self.status_mctl_timestamp = (
            None  # When did the Microcontroller send the status message?
        )
        self.status_local_timestamp = (
            None  # When did the RPi process the status message?
        )
        self.previous_angle = None  # Holds angle from previous status message.
        self.previous_mctl_timestamp = None  # Says when the previous angle was set.

    def approaching_limit(self):
        """Return TRUE if motor is within warning limit of the end of movement."""
        if self.current_angle <= self.min_warning_angle:
            result = True
        elif self.current_angle >= self.max_warning_angle:
            result = True
        else:
            result = False
        return result

    def compare_angles(self, angle1, angle2, ptolerance=None, atolerance=None):
        """Compare two (float) angles, return TRUE if they are the same 'motor position'.
        ptolerance: defines a motor position tolerance. Number of motor steps that are considered a good enough match.
        atolerance: defines an angle tolerance. Angle within which the two values are considered a good enough match.
        If neither is specified, then angles are considered equal if they resolve to precisely the same motor position.
        """
        result = False
        if angle1 is not None and angle2 is not None:
            if (
                ptolerance is not None
                and abs(self.angle_to_step(angle1) - self.angle_to_step(angle2))
                <= ptolerance
            ):
                result = True  # Angles are same within STEP tolerance.
            if atolerance is not None and abs(angle1 - angle2) <= atolerance:
                result = True  # Angles are the same within ANGLE tolerange.
            if self.angle_to_step(angle1) == self.angle_to_step(angle2):
                result = True  # Angles equate to the same step position.
        return result

    def restore_angle(self):
        """This searches for the last recorded position of the motor and restores that state.
        The last recorded position is stored in a file in the self.recovery_folder."""
        filename = ""
        oldfiles = []  # List of recovery files, we'll delete the old ones.
        # Find all the position recovery files available. Read in time sequence due to filenaming.
        for file in os.listdir(self.recovery_folder):
            thisfile = self.recovery_folder + "/" + file
            if thisfile == self.recovery_file_name:
                continue  # Ignore the CURRENT file we're writing to.
            if file.endswith(".log"):
                if thisfile > filename:
                    filename = thisfile  # More recent image.
                oldfiles.append(thisfile)  # Maintain list of all files found.
        if len(filename) == 0:
            self.log(
                "No recovery log file found for "
                + self.motor_name
                + " motor. Assuming "
                + deg_3dp(self.rest_angle, DEGREE_SYMBOL)
            )
            return False
        angle = self.rest_angle  # Default to home position.
        with open(
            filename
        ) as file_in:  # Read all the positions in the file, could be smarter and go to the end of the file here.
            for (
                line
            ) in (
                file_in
            ):  # Lines will be on chronological sequence. We keep that latest valid entry as the last known position of the motor.
                line = line.strip()  # Trim unwanted characters from line.
                ls = line.split(";")  # Format is 'timestamp';'angle';'seconds'
                if len(ls) > 1:
                    angle = float(ls[1])  # 'timestamp';'angle';'seconds'
                else:
                    self.log(
                        "Bad recovery entry (" + line + "), angle ignored.",
                        level="warning",
                    )
        self.current_angle = angle
        self.log(
            self.motor_name,
            "motor restored to last known position",
            self.angle_to_step(self.current_angle),
            "(",
            deg_3dp(self.current_angle, DEGREE_SYMBOL),
            ")",
        )
        # Now remove any old recovery files that we don't need. Always keep last 2.
        if len(oldfiles) > 2:  # Only tidyup if more than 2 files available.
            oldfiles = sorted(oldfiles)[
                :-2
            ]  # Sort alphabetically. This is equivalent to chronological sequence. Ignore the last 2 files, we want to keep these.
            for thisfile in oldfiles:
                cmd = "rm " + thisfile
                os_cmd(cmd)
                self.log(
                    "Motor.RestoreAngle(",
                    self.motor_name,
                    ") removed old restore file",
                    thisfile,
                    terminal=False,
                )
        return True

    def tune_complete(self, line):
        """Process acknowledgement of a completed tuning command.
        Expects input like          tune complete azimuth yyyymmddhhmmss -342 yyyymmddhhmmss
                        0     1        2          3          4        5"""
        self.log(
            "Motor",
            self.motor_name,
            "received tune acknowledgement:",
            line,
            terminal=False,
        )
        lineitems = line.split(" ")  # Separate each element of the line.
        self.latest_tune_time = mctl_string_to_datetime(
            lineitems[3]
        )  # Element #3 is the timestamp of the last tune command completed.
        steps = text_to_int(lineitems[4])
        endtime = lineitems[3]  # When did the tune complete?
        if len(lineitems) > 5:  # When did the tune start?
            self.latest_tune_start = mctl_string_to_datetime(
                lineitems[5]
            )  # Start time known.
        else:
            self.latest_tune_start = self.latest_tune_time  # Start time not known.
        self.log("motorcontrol.TuneComplete: LatestTuneSteps:", steps, terminal=False)
        self.latest_tune_steps = text_to_int(
            steps
        )  # Element 4 is the number of steps that the tune command executed.

    def store_recovery_angle(self, force=False):
        """Records the latest position of the motor for recovery purposes.
        This is appended to self.recovery_file_name if the position has changed.
        This data is used to restore the state of the motor when the program next restarts.
        This is designed to retry if there is a file error, just in case there's an access conflict with any other reader/monitor.
        force=True: A value is stored even if the motor hasn't moved."""
        counter = 100  # Only try 100 times, then fail.
        # The motor has actually moved!
        if force or not self.compare_angles(
            self.current_angle, self.last_recovery_angle
        ):
            success = False
            while counter > 0:
                counter -= 1
                try:
                    with open(
                        self.recovery_file_name, "ab", 0
                    ) as f:  # Python3: Don't buffer. Note that the O/S may still have to flush buffers itself.
                        f.write(
                            (
                                utc_time_stamp() + ";" + str(self.current_angle) + "\n"
                            ).encode()
                        )  # Convert text to bytes.
                    self.last_recovery_angle = self.current_angle
                    success = True
                    break  # Success, so don't try again.
                except Exception as e:
                    self.log(
                        "steppermotor.StoreRecoveryAngle (",
                        self.motor_name,
                        ") to",
                        self.recovery_file_name,
                        ". File conflict",
                        str(e),
                        "waiting to retry.",
                        level="warning",
                    )
                    time.sleep(0.3)
            if not success:
                self.log(
                    "steppermotor.StoreRecoveryAngle (",
                    self.motor_name,
                    ") to",
                    self.recovery_file_name,
                    ". Failed to write data.",
                    level="error",
                )

    def go_to_angle(self, newangle):
        """Trigger 'goto angle' movement of the motor via the remote microcontroller.
        This version can accept status messages from all motors.
          goto 20210409090949 azimuth 180.0
            0       1          2      3"""
        self.log(
            "motorcontrol.GoToAngle(",
            self.motor_name,
            "): Begin move from ",
            deg_3dp(self.current_angle, DEGREE_SYMBOL),
            "to",
            deg_3dp(newangle, DEGREE_SYMBOL),
            "(",
            str(self.angle_to_step(newangle) - self.angle_to_step(self.current_angle)),
            "step difference)",
            terminal=False,
        )
        result = False  # Failed until proven otherwise.

        # Clip angles to min/max allowed. The motor won't pass beyond these points, so the routine will wait forever for it to complete.
        if newangle < self.min_angle:
            self.log(
                "motorcontrol.GoToAngle(",
                self.motor_name,
                "): move limited to minimum",
                deg_3dp(self.min_angle, DEGREE_SYMBOL),
                terminal=False,
            )
            newangle = self.min_angle
        if newangle > self.max_angle:
            self.log(
                "motorcontrol.GoToAngle(",
                self.motor_name,
                "): move limited to maximum",
                deg_3dp(self.max_angle, DEGREE_SYMBOL),
                terminal=False,
            )
            newangle = self.max_angle

        self.log(
            "motorcontrol.GoToAngle(",
            self.motor_name,
            "): Clear unprocessed messages received from microcontroller.",
            terminal=False,
        )
        Mctl.ReadFlush()  # Reset the input buffers. Scrap anything still waiting to be processed.

        # The following section 'repeats' in the event of the microcontroller resetting during a large move.
        # It repeats until the motor is finally at the target position.

        # Check that the motors are configured before proceeding.
        self.log(
            "motorcontrol.GoToAngle(",
            self.motor_name,
            "): Configure motor",
            terminal=False,
        )
        loopcounter = 0
        looplimit = 20
        # Keep trying until limit hit, or we are close enough to the target position.
        # - Allow a little tolerance for calculation rounding etc.
        # Position tolerance of 1 works best here.
        while not self.compare_angles(self.current_angle, newangle, ptolerance=1):
            loopcounter += 1
            if loopcounter > 1:
                self.log(
                    "motorcontrol.GoToAngle(",
                    self.motor_name,
                    "): Begin attempt",
                    loopcounter,
                    "of",
                    looplimit,
                    terminal=True,
                )
            else:
                self.log(
                    "motorcontrol.GoToAngle(",
                    self.motor_name,
                    "): Begin attempt",
                    loopcounter,
                    "of",
                    looplimit,
                    terminal=False,
                )
            # In each attempt, first check that the motor is configured.
            # This should happen automatically, but check in case of an unexpected remote reset.
            rt = Timer(
                60
            )  # Allow 60 seconds, if no response, reset the microcontroller.
            if self.motor_configured:
                self.log(
                    "motorcontrol.GoToAngle(",
                    self.motor_name,
                    "): Motor already configured.",
                    terminal=False,
                )
            else:
                self.log(
                    "motorcontrol.GoToAngle(",
                    self.motor_name,
                    "): Motor is not yet configured.",
                    terminal=False,
                )
            mcl = 0  # How many attempts to configure the motor?
            # Send configuration to the motor until it's acknowldeged. (May take a few seconds).
            while not self.motor_configured:
                mcl += 1  # Count how many times we've sent the configuration.
                if mcl > 15:  # Too many attempts.
                    self.log(
                        "motorcontrol.GoToAngle(",
                        self.motor_name,
                        "): Motor has failed to configure. Abandoning GOTO.",
                        level="error",
                    )
                    return False  # Report failure.
                self.send_config()  # Send the motor configuration regularly.
                if self.motor_configured:
                    self.log(
                        "motorcontrol.GoToAngle(",
                        self.motor_name,
                        "): CheckMotorConfig: Motor reports it is now configured.",
                        terminal=False,
                    )
                    break  # All motors configured. OK to proceed.
                time.sleep(5)  # Pause a moment.
                if rt.due():  # It's time to try resetting the microcontroller.
                    self.log(
                        "motorcontrol.GoToAngle(",
                        self.motor_name,
                        "): CheckMotorConfig: Motor config not acknowledged. Resetting microcontroller.",
                        terminal=True,
                    )
                    Mctl.Reset(planned=True)
                self.log(
                    "motorcontrol.GoToAngle(",
                    self.motor_name,
                    "): Not yet configured. Trying to configure again.",
                    terminal=False,
                )
            # Motor is now configured. Perform the actual move now.
            self.log(
                "motorcontrol.GoToAngle(",
                self.motor_name,
                "): Begin the move.",
                terminal=False,
            )
            # Generate the GOTO command.
            line = "goto "
            line += clean_datetime_string(now_utc()) + " "
            line += self.motor_name + " "
            line += str(newangle) + " "
            Mctl.Write(line)  # Send GO TO command.
            # Wait for movement to complete.
            prevangle = None  # Monitor changes in angle. If it doesn't change for a while, consider something went wrong.
            prevangletime = now_utc()
            # 3rd task is to wait for the motor to complete.
            if self.monitor_move:  # Display movement progress.
                print(
                    now_hour_minute_sec(),
                    self.motor_name,
                    TextColor.white(deg_3dp(self.current_angle, DEGREE_SYMBOL)),
                    TextColor.clearlineforward(),
                )
            while True:
                if prevangle != self.current_angle:  # The motor has moved.
                    prevangle = self.current_angle
                    prevangletime = now_utc()
                    if self.monitor_move:  # Display movement progress.
                        print(
                            TextColor.cursorup(),
                            now_hour_minute_sec(),
                            self.motor_name,
                            TextColor.white(deg_3dp(self.current_angle, DEGREE_SYMBOL)),
                            TextColor.clearlineforward(),
                        )
                if self.compare_angles(
                    self.current_angle, newangle, ptolerance=2
                ):  # Sometimes there's a mathematical disagreement between microcontroller and this software. So allow a small tolerance when comparing angles.
                    # Move complete.
                    self.log(
                        "motorcontrol.GoToAngle(",
                        self.motor_name,
                        "): CompareAngles considers position is within tolerance, move considered complete.",
                        terminal=False,
                    )
                    result = True  # Success.
                    break
                if (
                    now_utc() - prevangletime
                ).total_seconds() > 60:  # The angle hasn't changed for 60 seconds. Consider something's wrong.
                    # *Q* A common reason for the timeout is a large backlog of configuration messages being exchanged.
                    # - This can be caused by running the program as far as the main menu, but not starting an observation for a very long time.
                    self.log(
                        "motorcontrol.GoToAngle(",
                        self.motor_name,
                        "): Angle has not changed for over 60 seconds. Will retry.",
                        terminal=False,
                    )
                    break
                time.sleep(1)  # Don't poll too often.
            if loopcounter >= looplimit:
                self.log(
                    "motorcontrol.GoToAngle(",
                    self.motor_name,
                    "): After",
                    looplimit,
                    "attempts, motor move still not complete. Abandoning the move at",
                    self.current_angle,
                    DEGREE_SYMBOL,
                    ".",
                    level="error",
                )
                ErrorWindow.print(
                    now_hour_minute_sec()
                    + " "
                    + str(looplimit)
                    + " GOTO attemps failed."
                )
                break
        # *Q* If the motor is already within tolerance but not precisely in position, you can get a false alarm here.
        # This is typically when you're asking it to move a single motor step in isolation.
        # In practice this is because the motor won't be asked to move if it's already within tolerance.
        # - Workarounds:-
        #   Move both motors by 10Degrees in any direction, which will increase the positions beyond the tolerances to allow homing again.
        self.log(
            "motorcontrol.GoToAngle(",
            self.motor_name,
            "): Move completed: Got",
            deg_3dp(self.current_angle, DEGREE_SYMBOL),
            ", expected",
            deg_3dp(newangle, DEGREE_SYMBOL),
            terminal=False,
        )
        return result  # Did we succeed?

    def calculate_axis_speed(self):
        """Based upon last 2 valid status messages, what speed is the motor currently moving at?
        Degrees per second returned."""
        anglechange = 0.0
        timechange = 0.0
        self.axis_speed = 0.0  # No speed unless we know it!
        if self.current_angle is not None and self.previous_angle is not None:
            anglechange = self.current_angle - self.previous_angle
        if (
            self.status_mctl_timestamp is not None
            and self.previous_mctl_timestamp is not None
        ):
            timechange = (
                self.status_mctl_timestamp - self.previous_mctl_timestamp
            ).total_seconds()
        if timechange != 0.0:
            self.axis_speed = anglechange / timechange

    def estimate_current_angle(self):
        """Given current system clock and the latest status information from the motorcontroller,
        estimate the current angle of the motor."""
        if self.axis_speed is not None and self.status_mctl_timestamp is not None:
            timechange = (
                now_utc() - self.status_mctl_timestamp
            ).total_seconds()  # Seconds since last position sent.
            anglechange = (
                self.axis_speed * timechange
            )  # How many degrees has the telescope probably moved in this time?
            angle = (
                self.current_angle + anglechange
            ) % 360  # Where is the telescope likely to be now (0-360 degree range)
        else:
            angle = self.current_angle  # Just use latest static angle we know.
        return angle

    def position_age(self):
        """How old (seconds) is the position measurement?"""
        age = 0
        if self.status_mctl_timestamp is not None:
            age = round((now_utc() - self.status_mctl_timestamp).total_seconds(), 0)
        if age > 30:
            self.log(
                "motorcontrol.PositionAge(",
                self.motor_name,
                ") position",
                self.current_angle,
                "from",
                self.status_mctl_timestamp,
                "is stale (",
                age,
                "seconds).",
                terminal=False,
            )
        return age

    def receive_status(self, line):
        """Receive Status of a motor and store important parameters
          in this local motor image.

          This is usually called via CheckMotorStatus(line) which protects updates from unconfigured motors,
          and handles missing configurations automatically.
          This also protects from unconfigured status messages, but will not directly handle the consequences.

        Sample message:-
          motor status 20210409090939 azimuth n 20210409090939 0 48000 180.0 y y 3939 345
            0      1          2           3   4         5      6   7     8   9 10 11  12
        2: IntToTimeString(Clock.Now()) Current local timestamp.
        3: self.motor_name
        4: BoolToString(self.trajectory.Valid) TrajectoryValid
        5: self.trajectory.ValidUntilString()
        6: str(len(self.trajectory.TrajectoryList))
        7: str(self.current_position)
        8: str(self.current_angle)
        9: BoolToString(self.motor_configured) MotorConfigured
        10: BoolToString(self.on_target) Motor is on target.
        11: str(self.wait_time) Current speed of motor.
        12: str(VMot()) Current motor power supply voltage. - Feature withdrawn, now always '0'.
        13: Reason. Code explaining WHY the status message was sent.
        """
        lineitems = line.split(" ")
        configuredflag = StringToBool(lineitems[9])  # Is the motor configured?
        if configuredflag != self.motor_configured:
            self.log(
                "motorcontrol.ReceiveStatus(",
                self.motor_name,
                "): Configured flag set to ",
                configuredflag,
                terminal=False,
            )
        self.motor_configured = configuredflag  # Update the configured flag.
        if (
            self.motor_configured
        ):  # Only believe the angle once the motor is configured, otherwise it's just a default value and probably inaccurate.
            self.previous_angle = self.current_angle  # Store previous position.
            self.current_angle = float(lineitems[8])
            self.store_recovery_angle()  # Record the latest position of the motor for restart/recovery later.
            self.trajectory_valid = StringToBool(lineitems[4])
            self.trajectory_valid_until = mctl_string_to_datetime(lineitems[5])
            self.trajectory_entries = int(lineitems[6])
            self.on_target = StringToBool(lineitems[10])  # Is the motor on target?
        else:
            self.log(
                "motorcontrol.ReceiveStatus(",
                self.motor_name,
                "): Motor is not yet configured. Position and trajectory info ignored. Configuring now.",
                terminal=False,
            )
            self.send_config()  # Send motor configuration now.

        # Calculate the following attributes regardless of configuration status.
        self.previous_mctl_timestamp = (
            self.status_mctl_timestamp
        )  # Store previous timestamp
        self.status_mctl_timestamp = mctl_string_to_datetime(
            lineitems[2]
        )  # When did the Microcontroller send the status message?
        self.log(
            "motorcontrol.ReceiveStatus(",
            self.motor_name,
            "): StatusMctlTimestamp now",
            self.status_mctl_timestamp,
            "from",
            line,
            terminal=False,
        )
        self.status_local_timestamp = (
            now_utc()
        )  # When did the RPi process the status message?
        self.calculate_axis_speed()  # Check motor speed.

        return True

    def send_config(self):
        """Send configuration information from this motor image to the microcontroller
        where it will be loaded into the motor control there.

        configure motor 20231016085541 azimuth 130.492 0 360 0.0 -1 0.001 0.05 0.003 10 n  n 90.0 240 400  1 180.0 nnn 1 n nnn
          0       1         2           3       4    5  6   7  8   9     10    11  12 13 14 15   16 17  18 19    20 21 22 23

           2 = UTC timestamp when message sent.
           3 = Motor name.
           4 = Last reported (Current) angle.
           5 = Minimum allowed angle.
           6 = Maximum allowed angle.
           7 = Backlash angle.
           8 = Motor orientation.
           9 = FastTime.
          10 = SlowTime.
          11 = TimeDelta.
          12 = Delay between automatic status messages.
          13 = FaultSensitive (stop if fault signal from driver).
          14 = OptimiseMoves (allows unlimited full rotation).
          15 = LimitAngle (motor will not cross this angle) - under development.
          16 = Gear ratio.
          17 = Motor steps per revolution (1 revolution of motor).
          18 = Slew Steps (the number of 'microsteps' taken when making large moves).
          19 = Motor rest angle (when homed).
          20 = Microstepping mode signals (used when making observation).
          21 = SlewEnabled flag (Can motor make FULL STEP moves during large position changes). <- Experimental feature.
          22 = Slew stepping mode signals (used when making large position changes). <- Experimental feature.
        """
        self.log(
            "motorcontrol.SendConfig (" + self.motor_name + ") begin", terminal=False
        )
        line = "configure motor "  # Fields 0 & 1
        line += clean_datetime_string(now_utc()) + " "  # Field 2
        line += self.motor_name + " "  # Field 3
        line += (
            str(self.current_angle) + " "
        )  # Field 4: Remind the motor where it is according to its last report.
        line += (
            str(self.min_angle) + " "
        )  # Field 5: Send the minimum movement position. Will override the default on the microcontroller.
        line += (
            str(self.max_angle) + " "
        )  # Field 6: Send the maximum movement position. Will override the default on the microcontroller.
        line += (
            str(self.backlash_angle) + " "
        )  # Field 7: Send the backlash angle. Will override the default on the microcontroller.
        line += (
            str(self.orientation) + " "
        )  # Field 8: Send the orientation of the motor. Will override the default on the microcontroller.
        line += str(self.fast_time) + " "  # Field 9: Send the FAST motor pulse limit.
        line += str(self.slow_time) + " "  # Field 10: Send the SLOW motor pulse limit.
        line += (
            str(self.time_delta) + " "
        )  # Field 11: Send the motor pulse acceleration unit.
        line += (
            str(self.parameters.motor_status_delay) + " "
        )  # Field 12: Set timer delay for sending motor status back to the RPi.
        line += (
            BoolToString(self.parameters.fault_sensitive) + " "
        )  # Field 13: When 'y' the microcontroller will respect the DRV8825 fault pin to block movement.
        line += (
            BoolToString(self.optimise_moves) + " "
        )  # Field 14: When 'y' the microcontroller can take shortcuts for large moves.
        line += (
            str(self.limit_angle) + " "
        )  # Field 15: Movement limit, motor will reverse around rather than crossing this limit.
        line += str(self.gear_ratio) + " "  # Field 16: GearRatio.
        line += str(self.motor_steps_per_rev) + " "  # Field 17 MotorStepsPerRev
        line += (
            str(self.slew_step_multiplier) + " "
        )  # Field 18 SlewStepMultiplier (The number of microsteps taken when making large Slew moves).
        line += str(self.rest_angle) + " "  # Field 19 RestAngle
        line += (
            self.mode_signals + " "
        )  # Field 20 Steppermotor mode signals for microstepping.
        line += (
            BoolToString(self.parameters.slew_enabled) + " "
        )  # Field 21 SlewEnabled flat. (Can motor make FULL STEP moves during large position changes)
        line += (
            self.slew_signals + " "
        )  # Field 22 Steppermotor mode signals for full steps (Fast slew).
        Mctl.Write(line)
        self.log(
            "motorcontrol.SendConfig (" + self.motor_name + ") end", terminal=False
        )
        return True

    def step_to_angle(self, steps=0):
        """Convert a number of steps to a final angle (0-360) of movement."""
        # Change number of steps into an angle (will be decimal result)
        return steps * 360 / float(self.axis_steps_per_rev)

    def angle_to_step(self, deg=0.0):
        """Convert a final angle of movement to the nearest whole number of motor steps."""
        # Change angle into a number of steps (will be rounded integer result)
        return int(round(deg * float(self.axis_steps_per_rev) / 360, 0))

    def tune_position(self, delta):
        """Tune the motor position (motor steps). This corrects the position of the motor/telescope
        without registering a change in the direction it is currently pointing.
        Use this for drift adjustment or manual finetuning of the telescope position during setup or after problems.
        tune 20210410154530 azimuth -234
          0        1           2      3"""

        # This first makes sure that the motor is configured, it waits for that to be acknowledged before sending the tune command.
        # Check that the motors are configured before proceeding.
        self.log(
            "motorcontrol.TunePosition(",
            self.motor_name,
            ") by",
            delta,
            "steps.",
            terminal=False,
        )
        # There can be input queued from the microcontroller waiting to be handled.
        # - We should check in case the motor has lost its configuration before proceeding.
        self.log(
            "motorcontrol.TunePosition(",
            self.motor_name,
            "): CheckMotorConfig: Precheck motor is still configured.",
            terminal=False,
        )

        # Motor is now configured. Perform the actual move now.
        if self.motor_configured:  # Only allow tuning if the motor is configured.
            dtn = now_utc()
            line = (
                "tune "
                + clean_datetime_string(str(dtn))
                + " "
                + self.motor_name
                + " "
                + str(delta)
            )
            Mctl.Write(line)
            # This doesn't wait for feedback, it is up to the motorcontroller to deal with the message when it sees fit.
            # This program may send further tune messages if it still needs to change things.
        else:
            self.log(
                "motorcontroller.TunePosition(",
                self.motor_name,
                "): Motor is not yet configured. Tune command will not be sent.",
                level="error",
            )
        self.log(
            "motorcontrol.TunePosition(",
            self.motor_name,
            "):",
            delta,
            "step tune command sent to microcontroller.",
            terminal=False,
        )

    def extend_trajectory(self, targetobj: AstroTarget):
        """Generate next trajectory segment and send it.

        The trajectory is a series of short straight line movements chained together to create a path across the sky.
        Each segment is a simple straight line, it is short enough that it equates to a tiny part of the arc that is actually being followed.
        The segment is short enough that it is indistinguishable from the true curve when converted into motor positions.

        This generates a single segment. A single small straight line movement that the motors must follow.

        Works in 2 modes.
        - Dynamic and static:
          Static means each segment of the trajectory is the same length of time. Typically very short.
          Dynamic means that segments can vary in the time span to minimise the number of segments that need to be passed to the microcontroller.
            Dynamic extends the length of each straight line segment as far as possible while still remaining close to the trajectory arc through the sky.

        *Q*: Experiments suggest that trajectory can be very efficiently represented by angular accelerations rather than specific positions.
           But this needs more work yet. Both the encoding here, and the decoding in the microcontroller need to be developed.

        trajectory 20210409104504 azimuth 20210325223342 181.6003 20210325223442 181.7003 45000 47500
          0             1          2           3          4            5           6      7     8

          1 = UTC timestamp when record sent.
          2 = Motorname
          3 = Start UTC of segment.
          4 = Start angle of segment.
          5 = End UTC of segment.
          6 = End angle of segment.
          7 = Start motorposition of segment.
          8 = End motorposition of segment.
        """
        line = "trajectory "
        nowutc = now_utc()
        segmentsize = (
            self.trajectory_segment_size
        )  # How long does a trajectory segment last? (seconds)
        line += (
            clean_datetime_string(str(nowutc)) + " "
        )  # Timestamp must be current even if resending cached records.
        if (
            self.last_sent_trajectory_key == self.trajectory_valid_until
            and self.trajectory_valid_until > nowutc
        ):  # We have a future result cached already for this...
            self.log(
                "motorcontroller.ExtendTrajectory(",
                self.motor_name,
                "): Using cached trajectory calculation:",
                "'" + self.last_sent_trajectory_data + "'",
                terminal=False,
            )
            line += self.last_sent_trajectory_data
            Mctl.Write(line)
            return  # No need to process further.
        if (
            self.trajectory_valid_until is None
        ):  # Where does previously downloaded trajectory end? = Start of this chunk.
            startutc = nowutc
        else:
            startutc = self.trajectory_valid_until
        # We're not using a cached record, so continue constructing and calculating a new record.
        line += self.motor_name + " "
        if startutc < nowutc:  # Don't create OLD entries.
            startutc = nowutc
        # Calculate START angle for trajectory segment.
        az, alt = targetobj.az_alt_degrees(
            time=datetime2_ts(startutc)
        )  # Needs to be Skyfield time!
        line += clean_datetime_string(str(startutc)) + " "
        if self.motor_name == "altitude":
            startangle = alt
        else:
            startangle = az
        line += str(startangle) + " "
        if targetobj.is_fixed_point():  # Fixed points can have a larger segment size.
            endutc = startutc + timedelta(
                seconds=segmentsize * 2
            )  # But not too large because we need multiple segments queued up on the microcontroller, otherwise it may send an off target signal if the trajectory list expires.
        else:
            endutc = startutc + timedelta(seconds=segmentsize)
        # Calculate END angle for trajectory segment.
        az, alt = targetobj.az_alt_degrees(
            time=datetime2_ts(endutc)
        )  # Needs to be Skyfield time!
        if self.motor_name == "altitude":
            endangle = alt
        else:
            endangle = az
        gradient = (
            endangle - startangle
        ) / segmentsize  # What's the gradient of this trajectory segment We can try to extend its validity.
        # DynamicTrajectoryPeriods:
        # - If enabled: Each segment of the trajectory extends over a variable period of time.
        #               This is to maximise movement and minimise the number of trajectory segments required.
        #               There's a small loss of precision as a result. But should be too small to notice.
        # - If disabled: Each segment of the trajectory extends over a fixed period of time.
        #               This is slightly more precise, but has more segments to pass to the microcontroller.
        if (
            self.parameters.use_dynamic_trajectory_periods
            and not targetobj.is_fixed_point()
        ):  # Cannot solve dynamic trajectories for fixed points!
            # We have the 'fixed time period' trajectory extent already calculated.
            # Maximise the time period for this extent so that we don't need to pass as many segments to the microcontroller.
            max_iterations = 100  # Always quit once max_iterations hit.
            while max_iterations > 0:  # Time out if max iterations hit.
                max_iterations -= 1  # Reduce timeout.
                segmentsize += int(
                    self.trajectory_segment_size / 4
                )  # Increase the segment size.
                nextutc = startutc + timedelta(
                    seconds=segmentsize
                )  # Timestamp of the larger segment size.
                az, alt = targetobj.az_alt_degrees(
                    time=datetime2_ts(nextutc)
                )  # Needs to be Skyfield time!
                if self.motor_name == "altitude":
                    nextangle = alt
                else:
                    nextangle = az
                # if self.min_angle > nextangle or self.max_angle < nextangle: break # Cannot extend any further. *!*
                if self.min_observation_angle > nextangle or self.max_angle < nextangle:
                    break  # Cannot extend any further. *!*
                projectedangle = startangle + (
                    gradient * segmentsize
                )  # What would the position be with the original gradient?
                angledrift = abs(
                    nextangle - projectedangle
                )  # How much drift would there be from the minimum timeslot if we just used that original gradient?
                if (
                    angledrift <= 0.005
                ):  # We can extend the time period if we remain close enough to the gradient of the minimum segment size.
                    # *Q* This tolerance could be measured in terms of a pixel in the camera, that's possibly what counts.
                    endangle = nextangle
                    endutc = nextutc
                else:  # The extended period would drift too far. Don't try anything larger.
                    break
            if max_iterations <= 0:  # Iteration limit hit!
                self.log(
                    "motorcontroller.ExtendTrajectory(",
                    self.motor_name,
                    "): max_iterations hit. Segment artificially limited to",
                    endutc,
                    terminal=False,
                )
        line += clean_datetime_string(str(endutc)) + " "
        line += str(endangle) + " "
        startpos = int(self.angle_to_step(startangle))
        endpos = int(self.angle_to_step(endangle))
        line += str(startpos) + " "  # Add actual stepper position for START of segment.
        line += str(endpos) + " "  # Add actual stepper position for END of segment.
        self.log(
            "motorcontroller.ExtendTrajectory(",
            self.motor_name,
            ") Segment",
            (endutc - startutc).total_seconds(),
            "seconds,",
            startutc,
            round(startangle, 4),
            "deg -",
            endutc,
            round(endangle, 4),
            "deg,",
            startpos,
            "-",
            endpos,
            "steps",
            terminal=False,
        )
        # if endangle >= self.min_angle and endangle <= self.max_angle: # We're still within range. *!*
        if (
            endangle >= self.min_observation_angle and endangle <= self.max_angle
        ):  # We're still within range. *!*
            Mctl.Write(line)
            self.last_sent_trajectory_key = (
                self.trajectory_valid_until
            )  # Cache the trajectory calculation, if the same calculation is triggered, we can re-use the earlier copy for speed.
            self.last_sent_trajectory_data = line[
                26:
            ]  # Store the data sent (without the leading timestamp, a fresh timestamp will be used if resent).
            self.log(
                "motorcontroller.ExtendTrajectory(",
                self.motor_name,
                "): Cached trajectory calculation:",
                "'" + self.last_sent_trajectory_data + "'",
                terminal=False,
            )
        else:
            self.log(
                "motorcontroller.ExtendTrajectory("
                + self.motor_name
                + "): Trajectory is now complete.",
                terminal=False,
            )
