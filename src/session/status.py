# --------------------
# Observation session
# --------------------

import threading
import time
from camera.targets.target import AstroTarget
from circuitpython.code import StringToBool
from pilomar import (
    ACCEPTABLECONTROLLERVERSIONS,
    OSW_TEXT_BAD,
    OSW_TEXT_BG,
    OSW_TEXT_FG,
    OSW_TEXT_GOOD,
    OSW_TEXT_POOR,
    VERSION,
    get_position_ages,
    SessionWindow,
)
from utils.params import AttributeMaster, Parameters
from utils.statics import DEGREE_SYMBOL
from utils.text.human_readable import (
    clean_datetime_string,
    human_readable_bytes,
    human_readable_seconds,
)
from utils.time_funcs import hms_from_stamp, now_hour_minute_sec, now_utc
from utils.timer import Timer


class SessionStatus(AttributeMaster):
    """Class to hold current status of the observation.
    This can export all the status information to a file so that a remote process can also monitor the status.
    These are the variables that handle a single loop in the ObservationRun routine."""

    def __init__(self, logger=None):
        """Initialize status fields."""
        self._file_names = []
        self.set_logger(
            logger
        )  # Inherited from attributemaster: Set up references to chosen logger (or disable if no logger defined).
        self.program_start_time = now_utc()  # When the program starts.
        self.target: AstroTarget = (
            None  # No target yet. This gets set to a valid target object when the target is selected.
        )
        self.debug_mode = (
            Parameters.debug_mode
        )  # Initialize the debug mode flat for the entire session.
        self.autonomous_control = (
            False  # Is the Microcontroller controlling its own movements?
        )
        self.remote_control = (
            False  # Will the Microcontroller accept remote control (from here)?
        )
        self.clock_synchronised = (
            False  # Has the Microcontroller synchronised the clock?
        )
        self._observation_running = False  # Set to TRUE when observation is running. Resets if not confirmed regularly. Check via ObservationRunning() method.
        self.mctl_rx_errors = (
            0  # How many messages has the Microcontroller rejected? (Checksum errors)
        )
        self.mctl_rx_bytes = 0  # How many bytes has the Microcontroller received?
        self.mctl_tx_bytes = 0  # How many bytes has the Microcontroller sent?
        self.mctl_exception_count = (
            0  # How many exceptions has the Microcontroller handled?
        )
        self.trajectory_safety_flushes = 0  # How many times has the microcontroller flushed a valid trajectory because of a communication break?
        self.camera_tx_count = 0  # Number of messages SENT from RPi to Camera
        self.camera_rx_count = 0  # Number of messages RECEIVED by RPi from Camera
        self.mctl_life_seconds = (
            0  # How many seconds has the Microcontroller been running for?
        )
        self.mctl_write_drops = 0  # How many messages were dropped from send buffer on Microcontroller due to overflow?
        self.motor_control_mode = "idle"  # What mode are we in? 'idle'/'remote'/'trajectory'. This controls the responses to some automated status messages.
        # Define the different motor control modes. idle, direct, trajectory.
        self.mc_mdict = {
            "idle": {"description": "motors at rest.", "trajectory": False},
            "direct": {
                "description": "motor movement controlled directly from this software.",
                "trajectory": False,
            },
            "trajectory": {
                "description": "motor movement is autonomous following trajectory.",
                "trajectory": True,
            },
        }
        self.maintain_trajectory = None
        self.set_motor_control_mode(
            self.motor_control_mode
        )  # Updates self.maintain_trajectory
        self.terminate_mctl_handler = (
            False  # Set to TRUE to cause MctlHandler loop to terminate.
        )
        self.controller_version = "unknown"  # The microcontroller should report its software version number and store it here.
        self.time_diff = None  # Timedelta between remote clock and local clock (includes messaging delays).

    def reset(self):
        self.autonomous_control = False  # Is the Microcontroller controlling its own movements? eg Trajectories.
        self.remote_control = False  # Will the Microcontroller accept remote control (from here)? eg GoTo, Tune etc.
        self.clock_synchronised = (
            False  # Has the Microcontroller synchronised the clock?
        )
        self.mctl_rx_errors = (
            0  # How many messages has the Microcontroller rejected? (Checksum errors)
        )
        self.mctl_rx_bytes = 0  # How many bytes has the Microcontroller received?
        self.mctl_tx_bytes = 0  # How many bytes has the Microcontroller sent?
        self.mctl_exception_count = (
            0  # How many exceptions has the Microcontroller handled?
        )
        self.mctl_life_seconds = (
            0  # How many seconds has the Microcontroller been running for?
        )
        self.mctl_write_drops = 0  # How many messages were dropped from send buffer on Microcontroller due to overflow?
        self.motor_control_mode = "idle"  # What mode are we in? 'idle'/'remote'/'autonomous'. This controls the responses to some automated status messages.
        self.set_motor_control_mode(
            self.motor_control_mode
        )  # Updates self.maintain_trajectory

    def set_motor_control_mode(self, mode):
        """Change the control mode of the motors.
        Supported modes are listed in self.mc_mdict.
        - That defines how the session automatically responds to status messages received from the microcontroller.
        - If it's in trajectory mode then the system will automatically start feeding trajectory segments to the motor.
        - If it's not in trajectory mode, then the system will flush existing trajectory segments from the motor.
        Unrecognised modes fail-safe to 'idle'."""
        PMT = self.maintain_trajectory
        if mode in self.mc_mdict:
            self.log(
                "sessionstatus:SetMotorControlMode("
                + mode
                + ") from "
                + self.motor_control_mode
                + " to "
                + mode,
                terminal=False,
            )
            self.log(
                "sessionstatus:SetMotorControlMode("
                + mode
                + ") "
                + self.mc_mdict[mode]["description"],
                terminal=False,
            )
            self.motor_control_mode = mode
            self.maintain_trajectory = self.mc_mdict[mode]["trajectory"]
        else:
            self.log(
                "sessionstatus.SetMotorControlMode("
                + mode
                + ") is not recognised. Setting to idle.",
                level="error",
            )
            self.motor_control_mode = "idle"  # Turn off motors just in case.
            self.maintain_trajectory = self.mc_mdict["idle"][
                "trajectory"
            ]  # Turn off trajectory just in case.
        if (
            PMT and PMT != self.maintain_trajectory
        ):  # We've just stopped maintaining the trajectory. Clear out any existing entries.
            self.log(
                "sessionstatus.SetMotorControlMode(",
                mode,
                ") clearing trajectory from motors.",
                terminal=False,
            )
            Mctl.Write(
                "clear trajectory"
            )  # Send immediate instruction to wipe any existing trajectory from the motors.

    def check_motor_status(self, line):
        """Check the Microcontroller's status message.
        - If it reports that the motor is configured, update the motor status information from this message.
        - If it reports that the motor is NOT configured, then send the configuration immediately.
        If they are not, then send the configuration immediately.
        #  From Microcontroller to RPi
        #   motor status 20210409090939 azimuth n 20210409090939 0 48000 180.0 y
            0     1           2          3    4     5          6   7     8   9
        """
        lineitems = line.split(" ")  # Split out all the elements of the line.
        motorname = lineitems[3]  # Extract motor name.
        foundit = False
        for i in MotorControls:
            if i.MotorName == motorname:
                foundit = True
                i.ReceiveStatus(line)  # Update motor status information.
        self.check_trajectory(
            line, self.target
        )  # Check observation is active and keep trajectory up-to-date if needed.
        if not foundit:  # The motor name was not recognised.
            self.log(
                "sessionstatus.CheckMotorStatus did not recognise the motor name (",
                motorname,
                ")",
                level="error",
            )

    def check_session_status(self, line):
        """Check the Microcontroller's status message to see if the session is configured.
          If the time needs synchronising, do that immediately.
             session status 20210409090929 n n False 20 None None
              0      1           2       3 4   5   6   7     8
        2: IntToTimeString(Clock.Now()) + ' ' # Current local timestamp.
        3: BoolToString(Clock.ClockSynchronised) Do the RPi and Microcontroller clocks agree?
        4: BoolToString(self.autonomous_control) Can motors drive themselves? Fully configured and trajectory known.
        5: BoolToString(self.remote_control) Can motors be commanded remotely? Fully configured.
        6: str(utime.time() - RPi.StartTime) Alive seconds.
        7: Flush count
        8: Code indicating the reason the message was sent."""
        lineitems = line.split(" ")
        remotetime = MctlStringToDatetime(
            lineitems[2]
        )  # What does the remote system report as the time?
        self.time_diff = now_utc() - remotetime  # What's the time difference?
        self.clock_synchronised = StringToBool(lineitems[3])
        self.autonomous_control = StringToBool(lineitems[4])
        self.remote_control = StringToBool(lineitems[5])
        self.mctl_life_seconds = int(lineitems[6])
        if (
            len(lineitems) > 7
        ):  # How many times has the microcontroller flushed the trajectory because of comms problems?
            self.trajectory_safety_flushes = int(lineitems[7])
        else:
            self.trajectory_safety_flushes = 0
        # lineitems[8] contains reason codes, for documentation rather than function.
        if len(lineitems) > 9:  # Exception count is included in the message.
            self.mctl_exception_count = int(lineitems[9])
        if not self.clock_synchronised:  # Clock has not yet been synchronised.
            # Synchronise clocks.
            line = "set time " + clean_datetime_string(str(now_utc()))
            Mctl.Write(line)
        if self.clock_synchronised:
            temp = "Synchronised"
        else:
            temp = "Unsynchronised"

    def check_comms_stats(self, line):
        """Check the Microcontroller's comms status message for stats.
               comms status 20210409090929 0 0 538 0
              0      1           2       3 4  5  6
        2: IntToTimeString(Clock.Now()) + ' ' # Current local timestamp.
        3: str(RPi.MctlRxErrors) How many messages were rejected from RPi by Microcontroller.
        4: str(RPi.CharactersRead) How many bytes received from RPi by Microcontroller.
        5: str(RPi.CharactersWritten) How many bytes written by Microcontroller to RPi.
        6: str(RPi.WriteDrops) How many messages were dropped due to buffer overflow?"""
        lineitems = line.split(" ")
        self.mctl_rx_errors = int(lineitems[3])
        self.mctl_rx_bytes = int(lineitems[4])
        self.mctl_tx_bytes = int(lineitems[5])
        self.mctl_write_drops = int(lineitems[6])

    def check_trajectory(
        self, line, targetobj
    ):  # Needs reworking for actual Skyfield trajectory.
        """Check the Microcontroller's status message to see if the trajectory is known.
        If it is not known far enough into the future, extend it by a single 'TrajectoryPoint'
        when that one is confirmed back by the Microcontroller, we may add another...

        motor status 20210409090939 azimuth n 20210409090939 0 48000 180.0 y
        2: IntToTimeString(Clock.Now()) + ' ' # Current local timestamp.
        3: self.motor_name + ' '
        4: BoolToString(self.trajectory.Valid) + ' ' # TrajectoryValid
        5: self.trajectory.ValidUntilString() + ' '
        6: str(len(self.trajectory.TrajectoryList)) + ' '
        7: str(self.current_position) + ' '
        8: str(self.current_angle) + ' '
        9: BoolToString(self.motor_configured) + ' ' # MotorConfigured"""
        lineitems = line.split(" ")
        motorname = lineitems[3]
        # This should only send a trajectory update IF we're TRACKING something!
        if self.maintain_trajectory:
            foundit = False
            for i in MotorControls:
                if i.MotorName == motorname:
                    foundit = True
                    i.TrajectoryEntries = int(lineitems[6])
                    i.TrajectoryValid = StringToBool(lineitems[4])
                    i.TrajectoryValidUntil = MctlStringToDatetime(lineitems[5])
                    duration = i.TrajectoryValidUntil - now_utc()
                    # self.log('sessionstatus.CheckTrajectory: Examining', i.MotorName, ', Entries', i.TrajectoryEntries, ', ValidUntil', i.TrajectoryValidUntil, ', Valid',i.TrajectoryValid, ', duration',duration.total_seconds(), 's, Window', Parameters.trajectory_window, 's, ClkSync', self.clock_synchronised,terminal=False)
                    if (
                        duration.total_seconds() < Parameters.trajectory_window
                        and self.clock_synchronised
                    ):  # We need to add time to the trajectory plan.
                        self.log(
                            "sessionstatus.CheckTrajectory: Decided to extend.",
                            terminal=False,
                        )
                        i.ExtendTrajectory(targetobj)
                    # else: self.log('sessionstatus.CheckTrajectory: Decided not to extend. Valid for',duration.total_seconds(),"s, Minimum",Parameters.trajectory_window,"s",self.clock_synchronised,terminal=False)
            if not foundit:  # The motor name was not recognised.
                self.log(
                    "sessionstatus.CheckTrajectory did not recognise the motor name (",
                    motorname,
                    ")",
                    level="error",
                )
        else:
            self.log(
                "sessionstatus.CheckTrajectory: Not currently maintaining trajectories on microcontroller.",
                terminal=False,
            )

    def check_controller_started(self, line):
        Mctl.MctlRestarted()
        for i in MotorControls:
            i.Restarted()  # Need to mark that the motor is nolonger configured.
        self.log(
            "sessionstatus:CheckControllerStarted(): Microcontroller reports restart.",
            terminal=False,
        )
        ErrorWindow.print(now_hour_minute_sec() + " Microcontroller reports restart.")

    def check_goto_rejected(self, line):
        self.log(
            "sessionstatus:MctlHandler(): Microcontroller rejected goto command.",
            terminal=False,
        )
        ErrorWindow.print(
            now_hour_minute_sec() + " Microcontroller rejected goto command: " + line
        )

    def check_tune_complete(self, line):  # A tune command has been processed.
        """tune complete {name} {endtime} {delta} {starttime}
        0     1       2        3        4        5"""
        foundit = False
        lineitems = line.split(" ")
        motorname = lineitems[2]  # Which motor?
        for i in MotorControls:
            if i.MotorName == motorname:
                i.TuneComplete(line)
                foundit = True
        if not foundit:  # The motor name was not recognised.
            self.log(
                "sessionstatus.CheckTuneComplete did not recognise the motor name (",
                motorname,
                ")",
                level="error",
            )

    def unrecognised_message(self, line):
        self.log("sessionstatus:UnrecognisedMessage():", line, terminal=False)
        ErrorWindow.print(now_hour_minute_sec() + " Unrecognised message: " + line)

    def valid_controller_version(self):
        """Return TRUE if controller version is known and acceptable.
        This only succeeds if the microcontroller is communicating
        and has send the controller version number to the RPi already."""
        result = False  # Not acceptable unless proven.
        if self.controller_version != "unknown":
            try:
                compversion = self.controller_version[
                    : self.controller_version.rindex(".")
                ]  # Ignore patch level. Select "a.b" from "a.b.c" format version numbers.
                if compversion in ACCEPTABLECONTROLLERVERSIONS:
                    result = True  # Acceptable
            except Exception as e:
                self.log(
                    "sessionstatus.ValidControllerVersion(): Failed to check",
                    self.controller_version,
                    level="error",
                )
                self.log(
                    "sessionstatus.ValidControllerVersion(): Failed with",
                    str(e),
                    level="error",
                )
        return result

    def check_controller_version(self, line):
        """Handle controller version message.
        Message looks like this :-

          controller version 0.0.0

        pilomar has a list of acceptable versions (MAJOR.MINOR), it doesn't care about .MICRO version number.
        It reports to the log file if the controller is reporting an incompatible version.

        """
        self.log("sessionstatus:CheckControllerVersion(): " + line, terminal=False)
        lineitems = line.split(" ")
        result = False
        if len(lineitems) > 2:
            self.controller_version = lineitems[2]
            try:
                compversion = self.controller_version[
                    : self.controller_version.rindex(".")
                ]  # Ignore patch level. Select "a.b" from "a.b.c" format version numbers.
                if compversion in ACCEPTABLECONTROLLERVERSIONS:
                    result = True  # Version is good.
                else:
                    self.log(
                        "sessionstatus.CheckControllerVersion():",
                        self.controller_version,
                        "is not in",
                        ACCEPTABLECONTROLLERVERSIONS,
                        terminal=True,
                    )
                    ErrorWindow.print(
                        now_hour_minute_sec()
                        + " Controller version "
                        + compversion
                        + " is not in "
                        + str(ACCEPTABLECONTROLLERVERSIONS)
                    )
            except Exception as e:
                self.log(
                    "sessionstatus.CheckControllerVersion(): Failed to check",
                    self.controller_version,
                    level="error",
                )
                self.log(
                    "sessionstatus.CheckControllerVersion(): Failed with",
                    str(e),
                    level="error",
                )
        else:
            self.log(
                "sessionstatus.CheckControllerVersion(): Response is incomplete:",
                line,
                level="warning",
            )
        return result

    def mctl_handler(self):
        """Handles incoming messages from microcontroller queue,
        updates status information in various objects,
        performs automatic responses to standard conditions.

        This reads/writes to message queues. It analyses and processes messages from
        the microcontroller, it does not directly handle the UART transfer of data.
        To see the UART Channel handling look in microcontroller.CommsLoop method."""
        self.log("sessionstatus.MctlHandler(): Started.", terminal=True)
        heartbeat = Timer(
            30, skip=True
        )  # Send a heartbeat signal to the microcontroller every 30 seconds.
        Mctl.Write(
            "# rpi version " + VERSION
        )  # Tell the microcontroller what version of software is running. *Q* Remove '#' when microcontroller software updated. Aug.2023
        try:
            while True:  # Repeat until told to stop.
                if self.terminate_mctl_handler:
                    self.log(
                        "sessionstatus.MctlHandler(): Terminate signal received.",
                        terminal=False,
                    )
                    break
                if (
                    not threading.main_thread().is_alive()
                ):  # Check if parent is still alive. Quit if it is nolonger there.
                    self.log(
                        "sessionstatus.MctlHandler(): Main thread nolonger alive.",
                        terminal=False,
                    )
                    break
                if len(Mctl.Lines) > 0:  # Something to handle.
                    line = (
                        Mctl.Read()
                    )  # Pull next available message from microcontroller.
                    # Are all the same messages received, processed, logged or ignored in the same way?
                    if len(line) > 0:  # Data to process.
                        if line.startswith("session"):
                            self.check_session_status(
                                line
                            )  # Gather information about the microcontroller general health.
                        elif line.startswith("comms"):
                            self.check_comms_stats(
                                line
                            )  # Gather statistics about UART communication handling.
                        elif line.startswith("controller log"):
                            pass  # Just log messages from the microcontroller. No action needed.
                        elif line.startswith("log"):
                            pass  # Just log messages from the microcontroller. No action needed.
                        elif line.startswith("cleared trajectory"):
                            pass  # Just log these.
                        elif line.startswith("motor"):
                            self.check_motor_status(
                                line
                            )  # Check motor info from microcontroller, respond with missing config etc.
                        elif line.startswith("controller heartbeat"):
                            pass  # Just log these.
                        elif line.startswith("heartbeat"):
                            pass  # Just log these.
                        elif line.startswith("acknowledged"):
                            pass  # Just log these.
                        elif line.startswith("#"):
                            pass  # Comments from microcontroller, ignore them.
                        elif line.startswith("controller version"):
                            self.check_controller_version(
                                line
                            )  # Check that software is compatible across devices.
                        elif line.startswith("goto rejected"):
                            self.check_goto_rejected(
                                line
                            )  # A goto command was rejected.
                        elif line.startswith("tune complete"):
                            self.check_tune_complete(
                                line
                            )  # A tune command has been processed.
                        elif line.startswith("controller started"):
                            self.check_controller_started(
                                line
                            )  # Microcontroller reports a restart. Trigger chain of updates.
                        elif line.startswith("defined motors"):
                            pass  # Just log these.
                        else:
                            self.unrecognised_message(
                                line
                            )  # Unexpected or corrupted message.
                else:
                    time.sleep(
                        0.1
                    )  #  Nothing received this round, so pause to release the pressure on the CPU!
                # Send occassional heartbeat signal to keep line alive.
                if (
                    heartbeat.due()
                ):  # Microcontroller will panic and flush trajectories if comms goes silent for too long.
                    Mctl.Write("# heartbeat")  # Prove we're still alive.
                    self.log("sessionstatus.MctlHandler(): Heartbeat", terminal=False)
        except Exception as e:  # Message handler failed.
            self.log("sessionstatus.MctlHandler: Failed!", level="error")
            MainLog.ReportException(
                e, comment="MctlHandler failed."
            )  # Trap all the exception information in the main log file.
        self.terminate_mctl_handler = False  # Reset the termination flag.
        self.log("sessionstatus.MctlHandler(): End.", terminal=False)

    def time_diff_secs(self):
        # Convert self.time_diff into an absolute number of seconds.
        # self.time_diff format is "d, h:m:s" or "h:m:s"
        result = 0
        if self.time_diff is not None:
            result = round(self.time_diff.total_seconds(), 1)
        return result

    def show_remote_status(self):
        """Display status from Microcontroller"""
        # Microcontroller communications
        nowutc = now_utc()  # Store current time.
        SessionWindow.clear(immediate=False)
        SessionWindow.field_value("RQ", len(Mctl.Lines))  # Messages: Rx queued
        SessionWindow.field_value("RT", Mctl.LinesReceived)  # Messages: Rx total
        SessionWindow.field_value("TQ", len(Mctl.WriteQueue))  # Messages: Tx queued
        SessionWindow.field_value("TT", Mctl.LinesSent)  # Messages: Tx total
        SessionWindow.field_value("SR", Mctl.ResetAttempts)  # Reset attempts
        SessionWindow.range_field_color(
            "SR", lowlow=-100, low=-10, high=1, highhigh=100
        )  # Anything >= 1 is a POOR value.
        SessionWindow.field_value("DF", Mctl.DeviceFailure)  # Device failure flag
        if Mctl.DeviceFailure:
            SessionWindow.field_color("DF", fg=OSW_TEXT_BAD)
        else:
            SessionWindow.field_color("DF", fg=OSW_TEXT_GOOD)
        SessionWindow.field_value(
            "LR", str(Mctl.LastRxTime).split(".")[0].split(" ")[1]
        )  # Last message received.
        SessionWindow.field_value(
            "BX", human_readable_bytes(Mctl.BytesReceived)
        )  # RPi measure of bytes received.
        SessionWindow.field_value(
            "TX", human_readable_bytes(Mctl.BytesSent)
        )  # RPi measure of bytes sent.
        SessionWindow.field_value("RE", Mctl.RxErrors)  # RPi measure of receive errors.
        SessionWindow.range_field_color(
            "RE", lowlow=-100, low=-10, high=1, highhigh=100
        )  # Anything >= 1 is a POOR value.
        if self.mctl_life_seconds > 0:  # Microcontroller comms stats, including rate.
            rbps = int(self.mctl_rx_bytes / self.mctl_life_seconds)
            tbps = int(self.mctl_tx_bytes / self.mctl_life_seconds)
            SessionWindow.field_value(
                "MRX", human_readable_bytes(self.mctl_rx_bytes)
            )  # Microcontroller measure of bytes received.
            SessionWindow.field_value(
                "MRXR", human_readable_bytes(rbps) + "/s"
            )  # receive rate.
            SessionWindow.field_value(
                "MTX", human_readable_bytes(self.mctl_tx_bytes)
            )  # Microcontroller measure of bytes sent.
            SessionWindow.field_value(
                "MTXR", human_readable_bytes(tbps) + "/s"
            )  # send rate.
            SessionWindow.field_value(
                "TD", self.mctl_write_drops
            )  # Microcontroller transmit drop count.
        else:  # Microcontroller comms stats, excluding rate.
            SessionWindow.field_value(
                "MRX", human_readable_bytes(self.mctl_rx_bytes)
            )  # Microcontroller measure of bytes received.
            SessionWindow.field_value(
                "TRX", human_readable_bytes(self.mctl_tx_bytes)
            )  # Microcontroller measure of bytes sent.
        SessionWindow.field_value(
            "R2", self.mctl_rx_errors
        )  # Microcontroller receive errors.
        SessionWindow.range_field_color(
            "R2", lowlow=-100, low=-10, high=1, highhigh=100
        )  # Anything >= 1 is a POOR value.
        SessionWindow.field_value(
            "AC", self.autonomous_control
        )  # Flag to show microcontroller allows autonomous control.
        if self.autonomous_control:
            SessionWindow.field_color("AC", fg=OSW_TEXT_GOOD)
        else:
            SessionWindow.field_color("AC", fg=OSW_TEXT_POOR)
        SessionWindow.field_value(
            "RCL", self.remote_control
        )  # Flag to show microcontroller allows remote control.
        if self.remote_control:
            SessionWindow.field_color("RCL", fg=OSW_TEXT_GOOD)
        else:
            SessionWindow.field_color("RCL", fg=OSW_TEXT_BAD)
        SessionWindow.field_value(
            "CS", self.clock_synchronised
        )  # Flag to show that microcontroller flag is synchronised.
        if self.clock_synchronised:
            SessionWindow.field_color("CS", fg=OSW_TEXT_GOOD)
        else:
            SessionWindow.field_color("CS", fg=OSW_TEXT_BAD)
        SessionWindow.field_value(
            "FR", Mctl.ForcedRestarts
        )  # Count of FORCED restarts triggered by RPi.
        SessionWindow.range_field_color(
            "FR", lowlow=-100, low=-10, high=1, highhigh=100
        )  # Anything >= 1 is a POOR value.
        SessionWindow.field_value(
            "RR", Mctl.RemoteRestarts
        )  # Count of REMOTE restarts triggered by microcontroller.
        SessionWindow.range_field_color(
            "RR", lowlow=-100, low=-10, high=1, highhigh=100
        )  # Anything >= 1 is a POOR value.
        SessionWindow.field_value(
            "ALIVE", human_readable_seconds(self.mctl_life_seconds)
        )  # How long since last microcontroller restart.
        SessionWindow.field_value(
            "MTSF", self.trajectory_safety_flushes
        )  # How many times has the microcontroller flushed valid trajectorys due to comms problems?
        SessionWindow.field_value(
            "EXCEPT", self.mctl_exception_count
        )  # How many code exceptions have been reported by the microcontroller.
        if self.mctl_exception_count > 0:
            SessionWindow.field_color(
                "EXCEPT", fg=OSW_TEXT_POOR
            )  # The microcontroller has handled some exceptions in the code.
        else:
            SessionWindow.field_color(
                "EXCEPT", fg=OSW_TEXT_GOOD
            )  # The microcontroller has not encountered any code exceptions.
        if self.trajectory_safety_flushes > 0:
            SessionWindow.field_color("MTSF", fg=OSW_TEXT_BAD)
        else:
            SessionWindow.field_color("MTSF", fg=OSW_TEXT_GOOD)
        if (
            Mctl.PoweredByUsb
        ):  # There's a USB connection as well as a GPIO connection to the microcontroller. BEWARE!
            SessionWindow.field_value(
                "CMODE", "GPIO & USB!"
            )  # What type of connection/power is provided to the microcontroller?
            SessionWindow.field_color("CMODE", fg=OSW_TEXT_POOR)
        else:  # Just a GPIO connection to the microcontroller. RELAX!
            SessionWindow.field_value(
                "CMODE", "GPIO"
            )  # What type of connection/power is provided to the microcontroller?
            SessionWindow.field_color("CMODE", fg=OSW_TEXT_GOOD)
        # Mark the age of the last reported camera positions, warn if the data is getting stale.
        az_age, alt_age = get_position_ages()
        if az_age > 60:
            azafg = OSW_TEXT_BAD
        elif az_age > 20:
            azafg = OSW_TEXT_POOR
        else:
            azafg = OSW_TEXT_FG
        if alt_age > 60:
            altafg = OSW_TEXT_BAD
        elif alt_age > 20:
            altafg = OSW_TEXT_POOR
        else:
            altafg = OSW_TEXT_FG
        SessionWindow.field_value(
            "CAZA", "(" + str(az_age) + "s)", fg=azafg, bg=OSW_TEXT_BG
        )  # Age of camera reported position.
        SessionWindow.field_value(
            "CALTA", "(" + str(alt_age) + "s)", fg=altafg, bg=OSW_TEXT_BG
        )  # Age of camera reported position.
        SessionWindow.field_value(
            "CLKDIF", str(self.time_diff_secs()) + "s"
        )  # Time difference/delay between RPi and Microcontroller.
        for i in MotorControls:  # Report trajectory information for each motor.
            if i.MotorName == "azimuth":
                fnp = "Z"
            else:
                fnp = "L"
            SessionWindow.field_value(fnp + "C", i.MotorConfigured)
            if i.MotorConfigured:
                SessionWindow.field_color(fnp + "C", fg=OSW_TEXT_GOOD)
            else:
                SessionWindow.field_color(fnp + "C", fg=OSW_TEXT_POOR)
            SessionWindow.field_value(
                fnp + "A", "{:07.3f}".format(i.CurrentAngle) + DEGREE_SYMBOL
            )
            if Parameters.use_dynamic_trajectory_periods:
                SessionWindow.field_value(fnp + "MODE", "Dynamic trajectory")
            else:
                SessionWindow.field_value(fnp + "MODE", "Fixed trajectory")
            if i.AxisSpeed is None:
                SessionWindow.field_value(fnp + "DPS", "0.0" + DEGREE_SYMBOL)
            else:
                SessionWindow.field_value(
                    fnp + "DPS", str(i.AxisSpeed)[:6] + DEGREE_SYMBOL
                )
            SessionWindow.field_value(fnp + "D", i.TrajectoryEntries)
            if i.TrajectoryEntries > 0:
                SessionWindow.field_color(fnp + "D", fg=OSW_TEXT_GOOD)
            else:
                SessionWindow.field_color(fnp + "D", fg=OSW_TEXT_POOR)
            if self.motor_control_mode == "trajectory":
                SessionWindow.field_value(fnp + "T", i.OnTarget)
                if i.OnTarget:
                    SessionWindow.field_color(fnp + "T", fg=OSW_TEXT_GOOD)
                else:
                    SessionWindow.field_color(fnp + "T", fg=OSW_TEXT_POOR)
                if i.TrajectoryValidUntil is not None:
                    temphms = hms_from_stamp(
                        i.TrajectoryValidUntil, dateaware=True
                    )  # Show HH:MM:SS unless it's another day, then show DD HH:MM
                    tempsec = (
                        i.TrajectoryValidUntil - nowutc
                    ).total_seconds()  # How long does the trajectory last (seconds)?
                    if (
                        tempsec > Parameters.trajectory_window
                    ):  # Valid far enough into the future.
                        SessionWindow.field_value(
                            fnp + "U", temphms, fg=OSW_TEXT_GOOD, bg=OSW_TEXT_BG
                        )
                        temp = "(" + human_readable_seconds(tempsec) + ")"
                        SessionWindow.field_value(
                            fnp + "RM", temp, fg=OSW_TEXT_FG, bg=OSW_TEXT_BG
                        )
                    elif tempsec > 0:  # Running out soon, needs extending.
                        SessionWindow.field_value(
                            fnp + "U", temphms, fg=OSW_TEXT_POOR, bg=OSW_TEXT_BG
                        )
                        temp = "(" + human_readable_seconds(tempsec) + ")"
                        SessionWindow.field_value(
                            fnp + "RM", temp, fg=OSW_TEXT_POOR, bg=OSW_TEXT_BG
                        )
                    else:  # Already run out.
                        SessionWindow.field_value(
                            fnp + "U", temphms, fg=OSW_TEXT_BAD, bg=OSW_TEXT_BG
                        )
                        temp = "(" + human_readable_seconds(-1 * tempsec) + ")"
                        SessionWindow.field_value(
                            fnp + "RM", temp, fg=OSW_TEXT_BAD, bg=OSW_TEXT_BG
                        )
                else:  # No trajectory data yet.
                    temp = human_readable_seconds(0)
                    SessionWindow.field_value(
                        fnp + "U", temp, fg=OSW_TEXT_POOR, bg=OSW_TEXT_BG
                    )
                    SessionWindow.field_value(
                        fnp + "RM", "(" + temp + ")", fg=OSW_TEXT_POOR, bg=OSW_TEXT_BG
                    )
            else:  # Trajectories not used for this target. Don't show validity.
                SessionWindow.field_value(
                    fnp + "T", "Fixed", fg=OSW_TEXT_GOOD, bg=OSW_TEXT_BG
                )  # OnTarget does not apply for stationary targets.
                SessionWindow.field_value(
                    fnp + "U", "--:--:--", fg=OSW_TEXT_GOOD, bg=OSW_TEXT_BG
                )  # Trajectory not needed, so no expiry.
                SessionWindow.field_value(
                    fnp + "RM", "n/a", fg=OSW_TEXT_GOOD, bg=OSW_TEXT_BG
                )  # Trajectory not needed, so no expiry.
