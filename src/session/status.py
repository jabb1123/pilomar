

# --------------------
# Observation session
# --------------------

from pilomar import SessionWindow
from utils.params import AttributeMaster
from utils.text.human_readable import HRSeconds
from utils.time_funcs import HmsFromStamp


class sessionstatus(AttributeMaster):
  """Class to hold current status of the observation.
  This can export all the status information to a file so that a remote process can also monitor the status.
  These are the variables that handle a single loop in the ObservationRun routine."""

  def __init__(self, logger=None):
    """Initialize status fields."""
    self._FileNames = []
    self.set_logger(
      logger
    )  # Inherited from attributemaster: Set up references to chosen logger (or disable if no logger defined).
    self.ProgramStartTime = NowUTC()  # When the program starts.
    self.Target = None  # No target yet. This gets set to a valid target object when the target is selected.
    self.DebugMode = (
      Parameters.DebugMode
    )  # Initialize the debug mode flat for the entire session.
    self.AutonomousControl = (
      False  # Is the Microcontroller controlling its own movements?
    )
    self.RemoteControl = (
      False  # Will the Microcontroller accept remote control (from here)?
    )
    self.ClockSynchronised = (
      False  # Has the Microcontroller synchronised the clock?
    )
    self._ObservationRunning = False  # Set to TRUE when observation is running. Resets if not confirmed regularly. Check via ObservationRunning() method.
    self.MctlRxErrors = (
      0  # How many messages has the Microcontroller rejected? (Checksum errors)
    )
    self.MctlRxBytes = 0  # How many bytes has the Microcontroller received?
    self.MctlTxBytes = 0  # How many bytes has the Microcontroller sent?
    self.MctlExceptionCount = (
      0  # How many exceptions has the Microcontroller handled?
    )
    self.TrajectorySafetyFlushes = 0  # How many times has the microcontroller flushed a valid trajectory because of a communication break?
    self.CameraTxCount = 0  # Number of messages SENT from RPi to Camera
    self.CameraRxCount = 0  # Number of messages RECEIVED by RPi from Camera
    self.MctlLifeSeconds = (
      0  # How many seconds has the Microcontroller been running for?
    )
    self.MctlWriteDrops = 0  # How many messages were dropped from send buffer on Microcontroller due to overflow?
    self.MotorControlMode = "idle"  # What mode are we in? 'idle'/'remote'/'trajectory'. This controls the responses to some automated status messages.
    # Define the different motor control modes. idle, direct, trajectory.
    self.MCMdict = {
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
    self.MaintainTrajectory = None
    self.SetMotorControlMode(
      self.MotorControlMode
    )  # Updates self.MaintainTrajectory
    self.TerminateMctlHandler = (
      False  # Set to TRUE to cause MctlHandler loop to terminate.
    )
    self.ControllerVersion = "unknown"  # The microcontroller should report its software version number and store it here.
    self.TimeDiff = None  # Timedelta between remote clock and local clock (includes messaging delays).

  def Reset(self):
    self.AutonomousControl = False  # Is the Microcontroller controlling its own movements? eg Trajectories.
    self.RemoteControl = False  # Will the Microcontroller accept remote control (from here)? eg GoTo, Tune etc.
    self.ClockSynchronised = (
      False  # Has the Microcontroller synchronised the clock?
    )
    self.MctlRxErrors = (
      0  # How many messages has the Microcontroller rejected? (Checksum errors)
    )
    self.MctlRxBytes = 0  # How many bytes has the Microcontroller received?
    self.MctlTxBytes = 0  # How many bytes has the Microcontroller sent?
    self.MctlExceptionCount = (
      0  # How many exceptions has the Microcontroller handled?
    )
    self.MctlLifeSeconds = (
      0  # How many seconds has the Microcontroller been running for?
    )
    self.MctlWriteDrops = 0  # How many messages were dropped from send buffer on Microcontroller due to overflow?
    self.MotorControlMode = "idle"  # What mode are we in? 'idle'/'remote'/'autonomous'. This controls the responses to some automated status messages.
    self.SetMotorControlMode(
      self.MotorControlMode
    )  # Updates self.MaintainTrajectory

  def SetMotorControlMode(self, mode):
    """Change the control mode of the motors.
    Supported modes are listed in self.MCMdict.
    - That defines how the session automatically responds to status messages received from the microcontroller.
    - If it's in trajectory mode then the system will automatically start feeding trajectory segments to the motor.
    - If it's not in trajectory mode, then the system will flush existing trajectory segments from the motor.
    Unrecognised modes fail-safe to 'idle'."""
    PMT = self.MaintainTrajectory
    if mode in self.MCMdict:
      self.log(
        "sessionstatus:SetMotorControlMode("
        + mode
        + ") from "
        + self.MotorControlMode
        + " to "
        + mode,
        terminal=False,
      )
      self.log(
        "sessionstatus:SetMotorControlMode("
        + mode
        + ") "
        + self.MCMdict[mode]["description"],
        terminal=False,
      )
      self.MotorControlMode = mode
      self.MaintainTrajectory = self.MCMdict[mode]["trajectory"]
    else:
      self.log(
        "sessionstatus.SetMotorControlMode("
        + mode
        + ") is not recognised. Setting to idle.",
        level="error",
      )
      self.MotorControlMode = "idle"  # Turn off motors just in case.
      self.MaintainTrajectory = self.MCMdict["idle"][
        "trajectory"
      ]  # Turn off trajectory just in case.
    if (
      PMT and PMT != self.MaintainTrajectory
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

  def CheckMotorStatus(self, line):
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
    self.CheckTrajectory(
      line, self.Target
    )  # Check observation is active and keep trajectory up-to-date if needed.
    if not foundit:  # The motor name was not recognised.
      self.log(
        "sessionstatus.CheckMotorStatus did not recognise the motor name (",
        motorname,
        ")",
        level="error",
      )

  def CheckSessionStatus(self, line):
    """Check the Microcontroller's status message to see if the session is configured.
      If the time needs synchronising, do that immediately.
         session status 20210409090929 n n False 20 None None
          0      1           2       3 4   5   6   7     8
    2: IntToTimeString(Clock.Now()) + ' ' # Current local timestamp.
    3: BoolToString(Clock.ClockSynchronised) Do the RPi and Microcontroller clocks agree?
    4: BoolToString(self.AutonomousControl) Can motors drive themselves? Fully configured and trajectory known.
    5: BoolToString(self.RemoteControl) Can motors be commanded remotely? Fully configured.
    6: str(utime.time() - RPi.StartTime) Alive seconds.
    7: Flush count
    8: Code indicating the reason the message was sent."""
    lineitems = line.split(" ")
    remotetime = MctlStringToDatetime(
      lineitems[2]
    )  # What does the remote system report as the time?
    self.TimeDiff = NowUTC() - remotetime  # What's the time difference?
    self.ClockSynchronised = StringToBool(lineitems[3])
    self.AutonomousControl = StringToBool(lineitems[4])
    self.RemoteControl = StringToBool(lineitems[5])
    self.MctlLifeSeconds = int(lineitems[6])
    if (
      len(lineitems) > 7
    ):  # How many times has the microcontroller flushed the trajectory because of comms problems?
      self.TrajectorySafetyFlushes = int(lineitems[7])
    else:
      self.TrajectorySafetyFlushes = 0
    # lineitems[8] contains reason codes, for documentation rather than function.
    if len(lineitems) > 9:  # Exception count is included in the message.
      self.MctlExceptionCount = int(lineitems[9])
    if self.ClockSynchronised == False:  # Clock has not yet been synchronised.
      # Synchronise clocks.
      line = "set time " + CleanDatetimeString(str(NowUTC()))
      Mctl.Write(line)
    if self.ClockSynchronised:
      temp = "Synchronised"
    else:
      temp = "Unsynchronised"

  def CheckCommsStats(self, line):
    """Check the Microcontroller's comms status message for stats.
           comms status 20210409090929 0 0 538 0
          0      1           2       3 4  5  6
    2: IntToTimeString(Clock.Now()) + ' ' # Current local timestamp.
    3: str(RPi.MctlRxErrors) How many messages were rejected from RPi by Microcontroller.
    4: str(RPi.CharactersRead) How many bytes received from RPi by Microcontroller.
    5: str(RPi.CharactersWritten) How many bytes written by Microcontroller to RPi.
    6: str(RPi.WriteDrops) How many messages were dropped due to buffer overflow?"""
    lineitems = line.split(" ")
    self.MctlRxErrors = int(lineitems[3])
    self.MctlRxBytes = int(lineitems[4])
    self.MctlTxBytes = int(lineitems[5])
    self.MctlWriteDrops = int(lineitems[6])

  def CheckTrajectory(
    self, line, targetobj
  ):  # Needs reworking for actual Skyfield trajectory.
    """Check the Microcontroller's status message to see if the trajectory is known.
    If it is not known far enough into the future, extend it by a single 'TrajectoryPoint'
    when that one is confirmed back by the Microcontroller, we may add another...

    motor status 20210409090939 azimuth n 20210409090939 0 48000 180.0 y
    2: IntToTimeString(Clock.Now()) + ' ' # Current local timestamp.
    3: self.MotorName + ' '
    4: BoolToString(self.Trajectory.Valid) + ' ' # TrajectoryValid
    5: self.Trajectory.ValidUntilString() + ' '
    6: str(len(self.Trajectory.TrajectoryList)) + ' '
    7: str(self.CurrentPosition) + ' '
    8: str(self.CurrentAngle) + ' '
    9: BoolToString(self.MotorConfigured) + ' ' # MotorConfigured"""
    lineitems = line.split(" ")
    motorname = lineitems[3]
    # This should only send a trajectory update IF we're TRACKING something!
    if self.MaintainTrajectory:
      foundit = False
      for i in MotorControls:
        if i.MotorName == motorname:
          foundit = True
          i.TrajectoryEntries = int(lineitems[6])
          i.TrajectoryValid = StringToBool(lineitems[4])
          i.TrajectoryValidUntil = MctlStringToDatetime(lineitems[5])
          duration = i.TrajectoryValidUntil - NowUTC()
          # self.Log('sessionstatus.CheckTrajectory: Examining', i.MotorName, ', Entries', i.TrajectoryEntries, ', ValidUntil', i.TrajectoryValidUntil, ', Valid',i.TrajectoryValid, ', duration',duration.total_seconds(), 's, Window', Parameters.TrajectoryWindow, 's, ClkSync', self.ClockSynchronised,terminal=False)
          if (
            duration.total_seconds() < Parameters.TrajectoryWindow
            and self.ClockSynchronised
          ):  # We need to add time to the trajectory plan.
            self.log(
              "sessionstatus.CheckTrajectory: Decided to extend.",
              terminal=False,
            )
            i.ExtendTrajectory(targetobj)
          # else: self.Log('sessionstatus.CheckTrajectory: Decided not to extend. Valid for',duration.total_seconds(),"s, Minimum",Parameters.TrajectoryWindow,"s",self.ClockSynchronised,terminal=False)
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

  def CheckControllerStarted(self, line):
    Mctl.MctlRestarted()
    for i in MotorControls:
      i.Restarted()  # Need to mark that the motor is nolonger configured.
    self.log(
      "sessionstatus:CheckControllerStarted(): Microcontroller reports restart.",
      terminal=False,
    )
    ErrorWindow.print(NowHMS() + " Microcontroller reports restart.")

  def CheckGotoRejected(self, line):
    self.log(
      "sessionstatus:MctlHandler(): Microcontroller rejected goto command.",
      terminal=False,
    )
    ErrorWindow.print(NowHMS() + " Microcontroller rejected goto command: " + line)

  def CheckTuneComplete(self, line):  # A tune command has been processed.
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

  def UnrecognisedMessage(self, line):
    self.log("sessionstatus:UnrecognisedMessage():", line, terminal=False)
    ErrorWindow.print(NowHMS() + " Unrecognised message: " + line)

  def ValidControllerVersion(self):
    """Return TRUE if controller version is known and acceptable.
    This only succeeds if the microcontroller is communicating
    and has send the controller version number to the RPi already."""
    result = False  # Not acceptable unless proven.
    if self.ControllerVersion != "unknown":
      try:
        compversion = self.ControllerVersion[
          : self.ControllerVersion.rindex(".")
        ]  # Ignore patch level. Select "a.b" from "a.b.c" format version numbers.
        if compversion in ACCEPTABLECONTROLLERVERSIONS:
          result = True  # Acceptable
      except Exception as e:
        self.log(
          "sessionstatus.ValidControllerVersion(): Failed to check",
          self.ControllerVersion,
          level="error",
        )
        self.log(
          "sessionstatus.ValidControllerVersion(): Failed with",
          str(e),
          level="error",
        )
    return result

  def CheckControllerVersion(self, line):
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
      self.ControllerVersion = lineitems[2]
      try:
        compversion = self.ControllerVersion[
          : self.ControllerVersion.rindex(".")
        ]  # Ignore patch level. Select "a.b" from "a.b.c" format version numbers.
        if compversion in ACCEPTABLECONTROLLERVERSIONS:
          result = True  # Version is good.
        else:
          self.log(
            "sessionstatus.CheckControllerVersion():",
            self.ControllerVersion,
            "is not in",
            ACCEPTABLECONTROLLERVERSIONS,
            terminal=True,
          )
          ErrorWindow.print(
            NowHMS()
            + " Controller version "
            + compversion
            + " is not in "
            + str(ACCEPTABLECONTROLLERVERSIONS)
          )
      except Exception as e:
        self.log(
          "sessionstatus.CheckControllerVersion(): Failed to check",
          self.ControllerVersion,
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

  def MctlHandler(self):
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
        if self.TerminateMctlHandler:
          self.log(
            "sessionstatus.MctlHandler(): Terminate signal received.",
            terminal=False,
          )
          break
        if (
          threading.main_thread().is_alive() == False
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
              self.CheckSessionStatus(
                line
              )  # Gather information about the microcontroller general health.
            elif line.startswith("comms"):
              self.CheckCommsStats(
                line
              )  # Gather statistics about UART communication handling.
            elif line.startswith("controller log"):
              pass  # Just log messages from the microcontroller. No action needed.
            elif line.startswith("log"):
              pass  # Just log messages from the microcontroller. No action needed.
            elif line.startswith("cleared trajectory"):
              pass  # Just log these.
            elif line.startswith("motor"):
              self.CheckMotorStatus(
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
              self.CheckControllerVersion(
                line
              )  # Check that software is compatible across devices.
            elif line.startswith("goto rejected"):
              self.CheckGotoRejected(line)  # A goto command was rejected.
            elif line.startswith("tune complete"):
              self.CheckTuneComplete(
                line
              )  # A tune command has been processed.
            elif line.startswith("controller started"):
              self.CheckControllerStarted(
                line
              )  # Microcontroller reports a restart. Trigger chain of updates.
            elif line.startswith("defined motors"):
              pass  # Just log these.
            else:
              self.UnrecognisedMessage(
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
    self.TerminateMctlHandler = False  # Reset the termination flag.
    self.log("sessionstatus.MctlHandler(): End.", terminal=False)

  def TimeDiffSecs(self):
    # Convert self.TimeDiff into an absolute number of seconds.
    # self.TimeDiff format is "d, h:m:s" or "h:m:s"
    result = 0
    if self.TimeDiff != None:
      result = round(self.TimeDiff.total_seconds(), 1)
    return result

  def ShowRemoteStatus(self):
    """Display status from Microcontroller"""
    # Microcontroller communications
    nowutc = NowUTC()  # Store current time.
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
      "BX", HRBytes(Mctl.BytesReceived)
    )  # RPi measure of bytes received.
    SessionWindow.field_value(
      "TX", HRBytes(Mctl.BytesSent)
    )  # RPi measure of bytes sent.
    SessionWindow.field_value("RE", Mctl.RxErrors)  # RPi measure of receive errors.
    SessionWindow.range_field_color(
      "RE", lowlow=-100, low=-10, high=1, highhigh=100
    )  # Anything >= 1 is a POOR value.
    if self.MctlLifeSeconds > 0:  # Microcontroller comms stats, including rate.
      rbps = int(self.MctlRxBytes / self.MctlLifeSeconds)
      tbps = int(self.MctlTxBytes / self.MctlLifeSeconds)
      SessionWindow.field_value(
        "MRX", HRBytes(self.MctlRxBytes)
      )  # Microcontroller measure of bytes received.
      SessionWindow.field_value("MRXR", HRBytes(rbps) + "/s")  # receive rate.
      SessionWindow.field_value(
        "MTX", HRBytes(self.MctlTxBytes)
      )  # Microcontroller measure of bytes sent.
      SessionWindow.field_value("MTXR", HRBytes(tbps) + "/s")  # send rate.
      SessionWindow.field_value(
        "TD", self.MctlWriteDrops
      )  # Microcontroller transmit drop count.
    else:  # Microcontroller comms stats, excluding rate.
      SessionWindow.field_value(
        "MRX", HRBytes(self.MctlRxBytes)
      )  # Microcontroller measure of bytes received.
      SessionWindow.field_value(
        "TRX", HRBytes(self.MctlTxBytes)
      )  # Microcontroller measure of bytes sent.
    SessionWindow.field_value(
      "R2", self.MctlRxErrors
    )  # Microcontroller receive errors.
    SessionWindow.range_field_color(
      "R2", lowlow=-100, low=-10, high=1, highhigh=100
    )  # Anything >= 1 is a POOR value.
    SessionWindow.field_value(
      "AC", self.AutonomousControl
    )  # Flag to show microcontroller allows autonomous control.
    if self.AutonomousControl:
      SessionWindow.field_color("AC", fg=OSW_TEXT_GOOD)
    else:
      SessionWindow.field_color("AC", fg=OSW_TEXT_POOR)
    SessionWindow.field_value(
      "RCL", self.RemoteControl
    )  # Flag to show microcontroller allows remote control.
    if self.RemoteControl:
      SessionWindow.field_color("RCL", fg=OSW_TEXT_GOOD)
    else:
      SessionWindow.field_color("RCL", fg=OSW_TEXT_BAD)
    SessionWindow.field_value(
      "CS", self.ClockSynchronised
    )  # Flag to show that microcontroller flag is synchronised.
    if self.ClockSynchronised:
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
      "ALIVE", HRSeconds(self.MctlLifeSeconds)
    )  # How long since last microcontroller restart.
    SessionWindow.field_value(
      "MTSF", self.TrajectorySafetyFlushes
    )  # How many times has the microcontroller flushed valid trajectorys due to comms problems?
    SessionWindow.field_value(
      "EXCEPT", self.MctlExceptionCount
    )  # How many code exceptions have been reported by the microcontroller.
    if self.MctlExceptionCount > 0:
      SessionWindow.field_color(
        "EXCEPT", fg=OSW_TEXT_POOR
      )  # The microcontroller has handled some exceptions in the code.
    else:
      SessionWindow.field_color(
        "EXCEPT", fg=OSW_TEXT_GOOD
      )  # The microcontroller has not encountered any code exceptions.
    if self.TrajectorySafetyFlushes > 0:
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
    AzAge, AltAge = GetPositionAges()
    if AzAge > 60:
      azafg = OSW_TEXT_BAD
    elif AzAge > 20:
      azafg = OSW_TEXT_POOR
    else:
      azafg = OSW_TEXT_FG
    if AltAge > 60:
      altafg = OSW_TEXT_BAD
    elif AltAge > 20:
      altafg = OSW_TEXT_POOR
    else:
      altafg = OSW_TEXT_FG
    SessionWindow.field_value(
      "CAZA", "(" + str(AzAge) + "s)", fg=azafg, bg=OSW_TEXT_BG
    )  # Age of camera reported position.
    SessionWindow.field_value(
      "CALTA", "(" + str(AltAge) + "s)", fg=altafg, bg=OSW_TEXT_BG
    )  # Age of camera reported position.
    SessionWindow.field_value(
      "CLKDIF", str(self.TimeDiffSecs()) + "s"
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
        fnp + "A", "{:07.3f}".format(i.CurrentAngle) + DegreeSymbol
      )
      if Parameters.UseDynamicTrajectoryPeriods:
        SessionWindow.field_value(fnp + "MODE", "Dynamic trajectory")
      else:
        SessionWindow.field_value(fnp + "MODE", "Fixed trajectory")
      if i.AxisSpeed is None:
        SessionWindow.field_value(fnp + "DPS", "0.0" + DegreeSymbol)
      else:
        SessionWindow.field_value(
          fnp + "DPS", str(i.AxisSpeed)[:6] + DegreeSymbol
        )
      SessionWindow.field_value(fnp + "D", i.TrajectoryEntries)
      if i.TrajectoryEntries > 0:
        SessionWindow.field_color(fnp + "D", fg=OSW_TEXT_GOOD)
      else:
        SessionWindow.field_color(fnp + "D", fg=OSW_TEXT_POOR)
      if self.MotorControlMode == "trajectory":
        SessionWindow.field_value(fnp + "T", i.OnTarget)
        if i.OnTarget:
          SessionWindow.field_color(fnp + "T", fg=OSW_TEXT_GOOD)
        else:
          SessionWindow.field_color(fnp + "T", fg=OSW_TEXT_POOR)
        if i.TrajectoryValidUntil != None:
          temphms = HmsFromStamp(
            i.TrajectoryValidUntil, dateaware=True
          )  # Show HH:MM:SS unless it's another day, then show DD HH:MM
          tempsec = (
            i.TrajectoryValidUntil - nowutc
          ).total_seconds()  # How long does the trajectory last (seconds)?
          if (
            tempsec > Parameters.TrajectoryWindow
          ):  # Valid far enough into the future.
            SessionWindow.field_value(
              fnp + "U", temphms, fg=OSW_TEXT_GOOD, bg=OSW_TEXT_BG
            )
            temp = "(" + HRSeconds(tempsec) + ")"
            SessionWindow.field_value(
              fnp + "RM", temp, fg=OSW_TEXT_FG, bg=OSW_TEXT_BG
            )
          elif tempsec > 0:  # Running out soon, needs extending.
            SessionWindow.field_value(
              fnp + "U", temphms, fg=OSW_TEXT_POOR, bg=OSW_TEXT_BG
            )
            temp = "(" + HRSeconds(tempsec) + ")"
            SessionWindow.field_value(
              fnp + "RM", temp, fg=OSW_TEXT_POOR, bg=OSW_TEXT_BG
            )
          else:  # Already run out.
            SessionWindow.field_value(
              fnp + "U", temphms, fg=OSW_TEXT_BAD, bg=OSW_TEXT_BG
            )
            temp = "(" + HRSeconds(-1 * tempsec) + ")"
            SessionWindow.field_value(
              fnp + "RM", temp, fg=OSW_TEXT_BAD, bg=OSW_TEXT_BG
            )
        else:  # No trajectory data yet.
          temp = HRSeconds(0)
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

