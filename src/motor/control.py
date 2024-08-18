
from datetime import timedelta
import os
import time
from utils.params import attributemaster
from utils.text.textcolor import TextColor
from utils.timer import Timer


class motorcontrol(attributemaster):
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
  ):
    """Create an instance of a stepper motor.
    Set up the physical configuration of the gears.
    Set up the electrical configuration of the stepper motor driver."""
    self.SetLogger(
      logger
    )  # Inherited from attributemaster: Set up references to chosen logger (or disable if no logger defined).
    self.MotorName = name  # A unique name to identify the motor, should be the same as the motor's name in the microcontroller side too.
    self.Driver = driver  # What driver board is being used?
    self.OptimiseMoves = optimisemoves  # Is the motor allowed to move freely across the 0/360 movement limit to track targets?
    self.GearRatio = gearratio
    motorstepsperrev = (
      fullstepsperrev * microstepratio
    )  # Calculate motorstepsperrev to include microstep ratio.
    self.MotorStepsPerRev = motorstepsperrev  # FullStepsPerRev of the motor * any microstepping multiplier.
    self.MicrostepRatio = microstepratio  # Just for documentation from this point onwards. Used for observation runs (Smoothest).
    self.SlewMicrosteps = slewmicrosteps  # When making fast SLEW moves, what microstepping do we use? Used for GOTO and HOME moves.
    self.SlewMicrosteps = min(
      self.SlewMicrosteps, self.MicrostepRatio
    )  # Slew cannot use finer microstepping than the observation!
    if self.SlewMicrosteps != slewmicrosteps:
      self.Log(
        "motorcontrol(",
        name,
        ") Slew microsteps (",
        slewmicrosteps,
        ") restricted to",
        self.MicrostepRatio,
        level="warning",
        terminal=True,
      )
    self.SlewStepMultiplier = int(
      round(self.MicrostepRatio / self.SlewMicrosteps, 0)
    )
    self.Log(
      "motorcontrol(",
      name,
      ") microstepping=",
      self.MicrostepRatio,
      "(observation speed), slew steps=",
      self.SlewMicrosteps,
      "(goto speed), multiplier=",
      self.SlewStepMultiplier,
      terminal=False,
    )
    modesignals = "nnn"  # Default full-step mode signals for the motor driver. (Used during observations).
    slewsignals = "nnn"  # Default full-step mode signals for the motor driver. (Used during large slew/GOTO moves).
    if driver in Parameters.StepperDriverData:  # Driver is recognised.
      modelist = Parameters.StepperDriverData[driver][
        "modelist"
      ]  # Pull the driver's modelist.
      # What are the mode signals for the selected microstepping ratio of the motor?
      if not str(microstepratio) in modelist:  # Keys are strings, not integers.
        self.Log(
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
      self.Log(
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
        not str(self.SlewMicrosteps) in modelist
      ):  # Keys are strings, not integers.
        self.Log(
          "motorcontrol(",
          name,
          ") slew microstepratio",
          self.SlewMicrosteps,
          "is not in",
          driver,
          "modelist.",
          level="error",
          terminal=True,
        )
        raise Exception(
          "motorcontrol(" + str(name) + ") slew microstepratio",
          self.SlewMicrosteps,
          "is not in " + str(driver) + "modelist.",
        )
      # microstep ratio is recognised. Pull the modepin settings.
      slewsignals = modelist[str(self.SlewMicrosteps)]["modesignals"]
      self.Log(
        "motorcontrol(",
        name,
        ") slew microstep ratio",
        self.SlewMicrosteps,
        "for",
        driver,
        "uses mode settings",
        slewsignals,
        terminal=False,
      )
    else:  # Driver is not recognised.
      self.Log(
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
    self.SlewSignals = slewsignals  # What are the settings for the mode pins to the driver board? (Large SLEW, GOTO and HOME moves)
    self.ModeSignals = modesignals  # What are the settings for the mode pins to the driver board? (Find movements during observations)
    self.WarningAngle = 10  # Can warn if position is within this angle of a limit.
    self.Horizon = horizon  # If set the motor will not go below this angle when tracking a target. Allows motor to move below the horizon for other reasons, but not track a target below the horizon. If set to None, this has no effect.
    self.MinAngle = (
      minangle  # Physical minimum angle that this motor is allowed to go to.
    )
    self.MinObservationAngle = (
      minangle  # Minimum angle that an observation is allowed to go to.
    )
    if self.Horizon != None:
      self.MinObservationAngle = max(
        self.MinAngle, self.Horizon
      )  # How low can an observation be made?
    self.MinWarningAngle = (
      self.MinObservationAngle + self.WarningAngle
    )  # Can warn if within xx degrees of minimum position.
    self.MaxAngle = maxangle
    self.MaxWarningAngle = (
      maxangle - self.WarningAngle
    )  # Can warn if within xx degrees of maximum position.
    self.LimitAngle = (
      limitangle  # The motor will reverse around a limit rather than crossing it.
    )
    self.Orientation = orientation
    self.BacklashAngle = backlashangle
    self.CurrentAngle = (
      currentangle  # This will be updated by the microcontroller once running.
    )
    self.PreviousAngle = None  # Holds angle from previous status message.
    self.PreviousMctlTimestamp = None  # Says when the previous angle was set.
    self.RestAngle = restangle
    self.MotorStepsPerAxisDegree = self.MotorStepsPerRev / 360.0
    self.AxisStepsPerRev = self.MotorStepsPerRev * self.GearRatio
    self.MotorConfigured = False
    self.FastTime = fasttime  # Fastest pulse to the motor STEP signal. (Full speed in large move.) # Was 0.0005
    self.SlowTime = slowtime  # Slowest pulse to the motor STEP signal. (Initial speed at start of move.)
    self.TimeDelta = timedelta  # Acceleration rate for the motor STEP signal.
    self.TrajectorySegmentSize = 60  # Seconds.
    self.TrajectoryValid = False  # Is the microcontroller trajectory valid?
    self.TrajectoryEntries = (
      0  # Number of trajectory entries stored on the microcontroller.
    )
    self.TrajectoryValidUntil = None  # The 'end time' of the trajectory as reported from the microcontroller.
    self.LastSentTrajectoryKey = None  # Key to the last send trajectory data, we can repeat the transmission and save recalculating it sometimes.
    self.LastSentTrajectoryData = None  # Last trajectory data sent to the microcontroller. This can be re-transmitted to save time if the microcontroller asks again.
    self.OnTarget = False  # Is the motor currently on target?
    self.LatestTuneStart = (
      None  # When did motor last START a TUNE move? (Images could be blurred)
    )
    self.LatestTuneTime = None  # When did motor last COMPLETE a TUNE command? (Images could be blurred)
    self.LatestTuneSteps = 0
    self.RecoveryFolder = ProjectRoot + "/data/" + self.MotorName + "_angle"
    self.RecoveryFileName = (
      self.RecoveryFolder + "/" + UtcTimeStamp() + ".log"
    )  # Used to record the position of the motor, this can then recover the situation in the event of any failures.
    VerifyFolder(self.RecoveryFolder)  # Make sure that the recovery folder exists.
    self.RestoreAngle()
    self.LastRecoveryAngle = (
      self.CurrentAngle
    )  # This is used to detect when the motor has physically moved so we don't keep writing the same position repeatedly to the recovery file.
    self.Log(
      "Motor "
      + self.MotorName
      + " recovered to "
      + str(round(self.CurrentAngle, 5))
      + DegreeSymbol,
      terminal=False,
    )
    self.AllMotors.append(
      self
    )  # Class attribute AllMotors points to ALL sibling motors. Can be used to check condition of any other motors too.
    self.StatusMctlTimestamp = (
      None  # When did the Microcontroller send the latest status message?
    )
    self.StatusLocalTimestamp = (
      None  # When did the RPi process the latest status message?
    )
    self.AxisSpeed = 0.0  # Currently calculated telescope speed (degrees/second).
    self.MonitorMove = False  # Set to True to enable text updates as moves are performed. False to suppress. GoToAngle(), HomePosition(), SetMotorAngle respect this.
    self.Restarted()  # Make sure that status flags are reset for a 'new' unconfigured motor.

  def __del__(self):
    """When deleted, remove this motor from the global list of all available motors."""
    self.AllMotors.remove(
      self
    )  # Class attribute AllMotors points to ALL sibling motors. Remove this motor from the list when deleted.

  def ShowMotorStatus(self):
    """Print general status of the motor."""
    print(TextColor.yellow("Motor:", self.MotorName))
    print("Driver:", self.Driver)
    print(TextColor.white("Current status:"))
    print("- MotorConfigured:", self.MotorConfigured)
    print("  Microcontroller acknowledges receipt of configuration")
    print("- CurrentAngle:", Deg3dp(self.CurrentAngle, DegreeSymbol))
    print("- Position:", self.AngleToStep(self.CurrentAngle), "steps")
    if self.AxisSpeed != None and self.AxisSpeed != 0:
      print(
        "- Latest AxisSpeed:",
        str(round(self.AxisSpeed, 4)) + DegreeSymbol + "/s",
      )
      print("  Last reported movement rate of the telescope")
    else:
      print("- Latest AxisSpeed:", self.AxisSpeed, DegreeSymbol + "/s")
      print("  Last reported movement rate of the telescope")
    print(TextColor.white("Gearing"))
    print("- GearRatio:", self.GearRatio)
    print("- MotorStepsPerRev:", self.MotorStepsPerRev)
    print(
      "  Motor native full steps per rev:",
      round(self.MotorStepsPerRev / self.MicrostepRatio, 0),
    )
    print("- MotorStepsPerAxisDegree:", round(self.MotorStepsPerAxisDegree, 3))
    print("  Motor needs this many steps to move itself 1 degree")
    print("- AxisStepsPerRev:", self.AxisStepsPerRev)
    print("  Motor steps required to move telescope one full revolution")
    print(TextColor.white("Fine motor movements (during observations):"))
    print("- MicrostepRatio:", self.MicrostepRatio)
    print("  Included in MotorStepsPerRev")
    print("- ModeSignals:", self.ModeSignals)
    print("  Mode pin settings for driver during observations")
    print(TextColor.white("Large motor movements (GOTO and HOME):"))
    print("- Enabled:", Parameters.SlewEnabled)
    print("- SlewMicrosteps:", self.SlewMicrosteps)
    print("- SlewSignals:", self.SlewSignals)
    print("  Mode pin settings for driver during large GOTO moves")
    print(TextColor.white("Configuration:"))
    print("- MinAngle:", Deg3dp(self.MinAngle, DegreeSymbol))
    print("  Telescope will not move below this angle")
    print("- Horizon:", Deg3dp(self.Horizon, DegreeSymbol))
    print("- MinObservationAngle:", Deg3dp(self.MinObservationAngle, DegreeSymbol))
    print("  Observations not allowed below this angle")
    print("- MinWarningAngle:", Deg3dp(self.MinWarningAngle, DegreeSymbol))
    print("  Warning when telescope gets this close to minimum observation angle")
    print("- MaxAngle:", Deg3dp(self.MaxAngle, DegreeSymbol))
    print("  Telescope will not move above this angle")
    print("- MaxWarningAngle:", Deg3dp(self.MaxWarningAngle, DegreeSymbol))
    print("  Warning when telescope gets this close to maximum angle")
    print("- OptimiseMoves:", self.OptimiseMoves)
    if self.OptimiseMoves:
      print(
        "  Trajectories can cross 0/360 limit if the movement is more efficient"
      )
    else:
      print("  Trajectories cannot cross cross 0/360 movement limits")
      print(
        "  Telescope will 'reverse' from a limit to track objects which cross it"
      )
    print("- Orientation:", self.Orientation)
    print("  +1 / -1 flips rotation direction of motor")
    print("- BacklashEnabled:", Parameters.BacklashEnabled)
    print("  Allow extra motor movement when changing direction")
    print("- BacklashAngle:", Deg3dp(self.BacklashAngle, DegreeSymbol))
    print("  Size of extra motor movement when changing direction")
    print("- RestAngle:", Deg3dp(self.RestAngle, DegreeSymbol))
    print("  Home/Parking position of the telescope")
    print("- FastTime:", self.FastTime, "s")
    print("  Approximate steps per second:", round((1 / (2 * self.FastTime)), 2))
    print(
      "  Approximate time for full revolution:",
      HRSeconds(self.AxisStepsPerRev * 2 * self.FastTime),
      "(",
      self.AxisStepsPerRev,
      "steps",
      ")",
    )
    print(
      "  Approximate time for telescope to move 10 degrees:",
      HRSeconds(self.AxisStepsPerRev * 2 * self.FastTime / 36),
      "(",
      int(self.AxisStepsPerRev / 36),
      "steps",
      ")",
    )
    print("- SlowTime:", self.SlowTime, "s")
    print("  Approximate steps per second:", round((1 / (2 * self.SlowTime)), 2))
    print("- TimeDelta:", self.TimeDelta, "s")
    print(TextColor.white("Trajectory:"))
    print("- TrajectorySegmentSize:", self.TrajectorySegmentSize, "s")
    print("- TrajectoryValid:", self.TrajectoryValid)
    print("- TrajectoryEntries:", self.TrajectoryEntries)
    print("- TrajectoryValidUntil:", self.TrajectoryValidUntil, "UTC")
    print("- OnTarget:", self.OnTarget)
    print(TextColor.white("Tuning:"))
    print("- LatestTuneStart:", self.LatestTuneStart, "UTC")
    print("- LatestTuneTime:", self.LatestTuneTime, "UTC")
    print("- LatestTuneSteps:", self.LatestTuneSteps)
    print("- RecoveryFileName:", self.RecoveryFileName)
    print("")

  def Restarted(self):
    """Call this if the microcontroller restarts.
    This resets some status flags so that we know the motor isn't fully configured yet.
    """
    self.MotorConfigured = False
    self.OnTarget = False  # Is the motor currently on target?
    self.TrajectoryValid = False  # Is the microcontroller trajectory valid?
    self.TrajectoryEntries = (
      0  # Number of trajectory entries stored on the microcontroller.
    )
    self.TrajectoryValidUntil = None  # The 'end time' of the trajectory as reported from the microcontroller.
    self.LastSentTrajectoryKey = None  # Key to the last send trajectory data, we can repeat the transmission and save recalculating it sometimes.
    self.LastSentTrajectoryData = None  # Last trajectory data sent to the microcontroller. This can be re-transmitted to save time if the microcontroller asks again.
    self.StatusMctlTimestamp = (
      None  # When did the Microcontroller send the status message?
    )
    self.StatusLocalTimestamp = None  # When did the RPi process the status message?
    self.PreviousAngle = None  # Holds angle from previous status message.
    self.PreviousMctlTimestamp = None  # Says when the previous angle was set.

  def ApproachingLimit(self):
    """Return TRUE if motor is within warning limit of the end of movement."""
    if self.CurrentAngle <= self.MinWarningAngle:
      result = True
    elif self.CurrentAngle >= self.MaxWarningAngle:
      result = True
    else:
      result = False
    return result

  def CompareAngles(self, angle1, angle2, ptolerance=None, atolerance=None):
    """Compare two (float) angles, return TRUE if they are the same 'motor position'.
    ptolerance: defines a motor position tolerance. Number of motor steps that are considered a good enough match.
    atolerance: defines an angle tolerance. Angle within which the two values are considered a good enough match.
    If neither is specified, then angles are considered equal if they resolve to precisely the same motor position.
    """
    result = False
    if angle1 != None and angle2 != None:
      if (
        ptolerance != None
        and abs(self.AngleToStep(angle1) - self.AngleToStep(angle2))
        <= ptolerance
      ):
        result = True  # Angles are same within STEP tolerance.
      if atolerance != None and abs(angle1 - angle2) <= atolerance:
        result = True  # Angles are the same within ANGLE tolerange.
      if self.AngleToStep(angle1) == self.AngleToStep(angle2):
        result = True  # Angles equate to the same step position.
    return result

  def RestoreAngle(self):
    """This searches for the last recorded position of the motor and restores that state.
    The last recorded position is stored in a file in the self.RecoveryFolder."""
    filename = ""
    oldfiles = []  # List of recovery files, we'll delete the old ones.
    # Find all the position recovery files available. Read in time sequence due to filenaming.
    for file in os.listdir(self.RecoveryFolder):
      thisfile = self.RecoveryFolder + "/" + file
      if thisfile == self.RecoveryFileName:
        continue  # Ignore the CURRENT file we're writing to.
      if file.endswith(".log"):
        if thisfile > filename:
          filename = thisfile  # More recent image.
        oldfiles.append(thisfile)  # Maintain list of all files found.
    if len(filename) == 0:
      self.Log(
        "No recovery log file found for "
        + self.MotorName
        + " motor. Assuming "
        + Deg3dp(self.RestAngle, DegreeSymbol)
      )
      return False
    angle = self.RestAngle  # Default to home position.
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
          self.Log(
            "Bad recovery entry (" + line + "), angle ignored.",
            level="warning",
          )
    self.CurrentAngle = angle
    self.Log(
      self.MotorName,
      "motor restored to last known position",
      self.AngleToStep(self.CurrentAngle),
      "(",
      Deg3dp(self.CurrentAngle, DegreeSymbol),
      ")",
    )
    # Now remove any old recovery files that we don't need. Always keep last 2.
    if len(oldfiles) > 2:  # Only tidyup if more than 2 files available.
      oldfiles = sorted(oldfiles)[
        :-2
      ]  # Sort alphabetically. This is equivalent to chronological sequence. Ignore the last 2 files, we want to keep these.
      for thisfile in oldfiles:
        cmd = "rm " + thisfile
        osCmd(cmd)
        self.Log(
          "Motor.RestoreAngle(",
          self.MotorName,
          ") removed old restore file",
          thisfile,
          terminal=False,
        )
    return True

  def TuneComplete(self, line):
    """Process acknowledgement of a completed tuning command.
    Expects input like          tune complete azimuth yyyymmddhhmmss -342 yyyymmddhhmmss
                    0     1        2          3          4        5"""
    self.Log(
      "Motor",
      self.MotorName,
      "received tune acknowledgement:",
      line,
      terminal=False,
    )
    lineitems = line.split(" ")  # Separate each element of the line.
    self.LatestTuneTime = MctlStringToDatetime(
      lineitems[3]
    )  # Element #3 is the timestamp of the last tune command completed.
    steps = TextToInt(lineitems[4])
    endtime = lineitems[3]  # When did the tune complete?
    if len(lineitems) > 5:  # When did the tune start?
      self.LatestTuneStart = MctlStringToDatetime(
        lineitems[5]
      )  # Start time known.
    else:
      self.LatestTuneStart = self.LatestTuneTime  # Start time not known.
    self.Log("motorcontrol.TuneComplete: LatestTuneSteps:", steps, terminal=False)
    self.LatestTuneSteps = TextToInt(
      steps
    )  # Element 4 is the number of steps that the tune command executed.

  def StoreRecoveryAngle(self, force=False):
    """Records the latest position of the motor for recovery purposes.
    This is appended to self.RecoveryFileName if the position has changed.
    This data is used to restore the state of the motor when the program next restarts.
    This is designed to retry if there is a file error, just in case there's an access conflict with any other reader/monitor.
    force=True: A value is stored even if the motor hasn't moved."""
    counter = 100  # Only try 100 times, then fail.
    if (
      force
      or self.CompareAngles(self.CurrentAngle, self.LastRecoveryAngle) == False
    ):  # The motor has actually moved!
      success = False
      while counter > 0:
        counter -= 1
        try:
          with open(
            self.RecoveryFileName, "ab", 0
          ) as f:  # Python3: Don't buffer. Note that the O/S may still have to flush buffers itself.
            f.write(
              (
                UtcTimeStamp() + ";" + str(self.CurrentAngle) + "\n"
              ).encode()
            )  # Convert text to bytes.
          self.LastRecoveryAngle = self.CurrentAngle
          success = True
          break  # Success, so don't try again.
        except Exception as e:
          self.Log(
            "steppermotor.StoreRecoveryAngle (",
            self.MotorName,
            ") to",
            self.RecoveryFileName,
            ". File conflict",
            str(e),
            "waiting to retry.",
            level="warning",
          )
          time.sleep(0.3)
      if not success:
        self.Log(
          "steppermotor.StoreRecoveryAngle (",
          self.MotorName,
          ") to",
          self.RecoveryFileName,
          ". Failed to write data.",
          level="error",
        )

  def GoToAngle(self, newangle):
    """Trigger 'goto angle' movement of the motor via the remote microcontroller.
    This version can accept status messages from all motors.
      goto 20210409090949 azimuth 180.0
        0       1          2      3"""
    self.Log(
      "motorcontrol.GoToAngle(",
      self.MotorName,
      "): Begin move from ",
      Deg3dp(self.CurrentAngle, DegreeSymbol),
      "to",
      Deg3dp(newangle, DegreeSymbol),
      "(",
      str(self.AngleToStep(newangle) - self.AngleToStep(self.CurrentAngle)),
      "step difference)",
      terminal=False,
    )
    result = False  # Failed until proven otherwise.

    # Clip angles to min/max allowed. The motor won't pass beyond these points, so the routine will wait forever for it to complete.
    if newangle < self.MinAngle:
      self.Log(
        "motorcontrol.GoToAngle(",
        self.MotorName,
        "): move limited to minimum",
        Deg3dp(self.MinAngle, DegreeSymbol),
        terminal=False,
      )
      newangle = self.MinAngle
    if newangle > self.MaxAngle:
      self.Log(
        "motorcontrol.GoToAngle(",
        self.MotorName,
        "): move limited to maximum",
        Deg3dp(self.MaxAngle, DegreeSymbol),
        terminal=False,
      )
      newangle = self.MaxAngle

    self.Log(
      "motorcontrol.GoToAngle(",
      self.MotorName,
      "): Clear unprocessed messages received from microcontroller.",
      terminal=False,
    )
    Mctl.ReadFlush()  # Reset the input buffers. Scrap anything still waiting to be processed.

    # The following section 'repeats' in the event of the microcontroller resetting during a large move.
    # It repeats until the motor is finally at the target position.

    # Check that the motors are configured before proceeding.
    self.Log(
      "motorcontrol.GoToAngle(",
      self.MotorName,
      "): Configure motor",
      terminal=False,
    )
    loopcounter = 0
    looplimit = 20
    # Keep trying until limit hit, or we are close enough to the target position.
    # - Allow a little tolerance for calculation rounding etc.
    while (
      self.CompareAngles(self.CurrentAngle, newangle, ptolerance=1) == False
    ):  # Position tolerance of 1 works best here.
      loopcounter += 1
      if loopcounter > 1:
        self.Log(
          "motorcontrol.GoToAngle(",
          self.MotorName,
          "): Begin attempt",
          loopcounter,
          "of",
          looplimit,
          terminal=True,
        )
      else:
        self.Log(
          "motorcontrol.GoToAngle(",
          self.MotorName,
          "): Begin attempt",
          loopcounter,
          "of",
          looplimit,
          terminal=False,
        )
      # In each attempt, first check that the motor is configured. This should happen automatically, but check in case of an unexpected remote reset.
      rt = Timer(
        60
      )  # Allow 60 seconds, if no response, reset the microcontroller.
      if self.MotorConfigured:
        self.Log(
          "motorcontrol.GoToAngle(",
          self.MotorName,
          "): Motor already configured.",
          terminal=False,
        )
      else:
        self.Log(
          "motorcontrol.GoToAngle(",
          self.MotorName,
          "): Motor is not yet configured.",
          terminal=False,
        )
      mcl = 0  # How many attempts to configure the motor?
      while (
        self.MotorConfigured == False
      ):  # Send configuration to the motor until it's acknowldeged. (May take a few seconds).
        mcl += 1  # Count how many times we've sent the configuration.
        if mcl > 15:  # Too many attempts.
          self.Log(
            "motorcontrol.GoToAngle(",
            self.MotorName,
            "): Motor has failed to configure. Abandoning GOTO.",
            level="error",
          )
          return False  # Report failure.
        self.SendConfig()  # Send the motor configuration regularly.
        if self.MotorConfigured:
          self.Log(
            "motorcontrol.GoToAngle(",
            self.MotorName,
            "): CheckMotorConfig: Motor reports it is now configured.",
            terminal=False,
          )
          break  # All motors configured. OK to proceed.
        time.sleep(5)  # Pause a moment.
        if rt.due():  # It's time to try resetting the microcontroller.
          self.Log(
            "motorcontrol.GoToAngle(",
            self.MotorName,
            "): CheckMotorConfig: Motor config not acknowledged. Resetting microcontroller.",
            terminal=True,
          )
          Mctl.Reset(planned=True)
        self.Log(
          "motorcontrol.GoToAngle(",
          self.MotorName,
          "): Not yet configured. Trying to configure again.",
          terminal=False,
        )
      # Motor is now configured. Perform the actual move now.
      self.Log(
        "motorcontrol.GoToAngle(",
        self.MotorName,
        "): Begin the move.",
        terminal=False,
      )
      # Generate the GOTO command.
      line = "goto "
      line += CleanDatetimeString(NowUTC()) + " "
      line += self.MotorName + " "
      line += str(newangle) + " "
      Mctl.Write(line)  # Send GO TO command.
      # Wait for movement to complete.
      prevangle = None  # Monitor changes in angle. If it doesn't change for a while, consider something went wrong.
      prevangletime = NowUTC()
      # 3rd task is to wait for the motor to complete.
      if self.MonitorMove:  # Display movement progress.
        print(
          NowHMS(),
          self.MotorName,
          TextColor.white(Deg3dp(self.CurrentAngle, DegreeSymbol)),
          TextColor.clearlineforward(),
        )
      while True:
        if prevangle != self.CurrentAngle:  # The motor has moved.
          prevangle = self.CurrentAngle
          prevangletime = NowUTC()
          if self.MonitorMove:  # Display movement progress.
            print(
              TextColor.cursorup(),
              NowHMS(),
              self.MotorName,
              TextColor.white(Deg3dp(self.CurrentAngle, DegreeSymbol)),
              TextColor.clearlineforward(),
            )
        if self.CompareAngles(
          self.CurrentAngle, newangle, ptolerance=2
        ):  # Sometimes there's a mathematical disagreement between microcontroller and this software. So allow a small tolerance when comparing angles.
          # Move complete.
          self.Log(
            "motorcontrol.GoToAngle(",
            self.MotorName,
            "): CompareAngles considers position is within tolerance, move considered complete.",
            terminal=False,
          )
          result = True  # Success.
          break
        if (
          NowUTC() - prevangletime
        ).total_seconds() > 60:  # The angle hasn't changed for 60 seconds. Consider something's wrong.
          # *Q* A common reason for the timeout is a large backlog of configuration messages being exchanged.
          # - This can be caused by running the program as far as the main menu, but not starting an observation for a very long time.
          self.Log(
            "motorcontrol.GoToAngle(",
            self.MotorName,
            "): Angle has not changed for over 60 seconds. Will retry.",
            terminal=False,
          )
          break
        time.sleep(1)  # Don't poll too often.
      if loopcounter >= looplimit:
        self.Log(
          "motorcontrol.GoToAngle(",
          self.MotorName,
          "): After",
          looplimit,
          "attempts, motor move still not complete. Abandoning the move at",
          self.CurrentAngle,
          DegreeSymbol,
          ".",
          level="error",
        )
        ErrorWindow.print(
          NowHMS() + " " + str(looplimit) + " GOTO attemps failed."
        )
        break
    # *Q* If the motor is already within tolerance but not precisely in position, you can get a false alarm here.
    # This is typically when you're asking it to move a single motor step in isolation.
    # In practice this is because the motor won't be asked to move if it's already within tolerance.
    # - Workarounds:-
    #   Move both motors by 10Degrees in any direction, which will increase the positions beyond the tolerances to allow homing again.
    self.Log(
      "motorcontrol.GoToAngle(",
      self.MotorName,
      "): Move completed: Got",
      Deg3dp(self.CurrentAngle, DegreeSymbol),
      ", expected",
      Deg3dp(newangle, DegreeSymbol),
      terminal=False,
    )
    return result  # Did we succeed?

  def CalculateAxisSpeed(self):
    """Based upon last 2 valid status messages, what speed is the motor currently moving at?
    Degrees per second returned."""
    anglechange = 0.0
    timechange = 0.0
    self.AxisSpeed = 0.0  # No speed unless we know it!
    if self.CurrentAngle != None and self.PreviousAngle != None:
      anglechange = self.CurrentAngle - self.PreviousAngle
    if self.StatusMctlTimestamp != None and self.PreviousMctlTimestamp != None:
      timechange = (
        self.StatusMctlTimestamp - self.PreviousMctlTimestamp
      ).total_seconds()
    if timechange != 0.0:
      self.AxisSpeed = anglechange / timechange

  def EstimateCurrentAngle(self):
    """Given current system clock and the latest status information from the motorcontroller, estimate the current angle of the motor."""
    if self.AxisSpeed != None and self.StatusMctlTimestamp != None:
      timechange = (
        NowUTC() - self.StatusMctlTimestamp
      ).total_seconds()  # Seconds since last position sent.
      anglechange = (
        self.AxisSpeed * timechange
      )  # How many degrees has the telescope probably moved in this time?
      angle = (
        self.CurrentAngle + anglechange
      ) % 360  # Where is the telescope likely to be now (0-360 degree range)
    else:
      angle = self.CurrentAngle  # Just use latest static angle we know.
    return angle

  def PositionAge(self):
    """How old (seconds) is the position measurement?"""
    age = 0
    if self.StatusMctlTimestamp != None:
      age = round((NowUTC() - self.StatusMctlTimestamp).total_seconds(), 0)
    if age > 30:
      self.Log(
        "motorcontrol.PositionAge(",
        self.MotorName,
        ") position",
        self.CurrentAngle,
        "from",
        self.StatusMctlTimestamp,
        "is stale (",
        age,
        "seconds).",
        terminal=False,
      )
    return age

  def ReceiveStatus(self, line):
    """Receive Status of a motor and store important parameters
      in this local motor image.

      This is usually called via CheckMotorStatus(line) which protects updates from unconfigured motors, and handles missing configurations automatically.
      This also protects from unconfigured status messages, but will not directly handle the consequences.

    Sample message:-
      motor status 20210409090939 azimuth n 20210409090939 0 48000 180.0 y y 3939 345
        0      1          2           3   4         5      6   7     8   9 10 11  12
    2: IntToTimeString(Clock.Now()) Current local timestamp.
    3: self.MotorName
    4: BoolToString(self.Trajectory.Valid) TrajectoryValid
    5: self.Trajectory.ValidUntilString()
    6: str(len(self.Trajectory.TrajectoryList))
    7: str(self.CurrentPosition)
    8: str(self.CurrentAngle)
    9: BoolToString(self.MotorConfigured) MotorConfigured
    10: BoolToString(self.OnTarget) Motor is on target.
    11: str(self.WaitTime) Current speed of motor.
    12: str(VMot()) Current motor power supply voltage. - Feature withdrawn, now always '0'.
    13: Reason. Code explaining WHY the status message was sent.
    """
    lineitems = line.split(" ")
    configuredflag = StringToBool(lineitems[9])  # Is the motor configured?
    if configuredflag != self.MotorConfigured:
      self.Log(
        "motorcontrol.ReceiveStatus(",
        self.MotorName,
        "): Configured flag set to ",
        configuredflag,
        terminal=False,
      )
    self.MotorConfigured = configuredflag  # Update the configured flag.
    if (
      self.MotorConfigured
    ):  # Only believe the angle once the motor is configured, otherwise it's just a default value and probably inaccurate.
      self.PreviousAngle = self.CurrentAngle  # Store previous position.
      self.CurrentAngle = float(lineitems[8])
      self.StoreRecoveryAngle()  # Record the latest position of the motor for restart/recovery later.
      self.TrajectoryValid = StringToBool(lineitems[4])
      self.TrajectoryValidUntil = MctlStringToDatetime(lineitems[5])
      self.TrajectoryEntries = int(lineitems[6])
      self.OnTarget = StringToBool(lineitems[10])  # Is the motor on target?
    else:
      self.Log(
        "motorcontrol.ReceiveStatus(",
        self.MotorName,
        "): Motor is not yet configured. Position and trajectory info ignored. Configuring now.",
        terminal=False,
      )
      self.SendConfig()  # Send motor configuration now.

    # Calculate the following attributes regardless of configuration status.
    self.PreviousMctlTimestamp = (
      self.StatusMctlTimestamp
    )  # Store previous timestamp
    self.StatusMctlTimestamp = MctlStringToDatetime(
      lineitems[2]
    )  # When did the Microcontroller send the status message?
    self.Log(
      "motorcontrol.ReceiveStatus(",
      self.MotorName,
      "): StatusMctlTimestamp now",
      self.StatusMctlTimestamp,
      "from",
      line,
      terminal=False,
    )
    self.StatusLocalTimestamp = (
      NowUTC()
    )  # When did the RPi process the status message?
    _ = self.CalculateAxisSpeed()  # Check motor speed.

    return True

  def SendConfig(self):
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
    self.Log(
      "motorcontrol.SendConfig (" + self.MotorName + ") begin", terminal=False
    )
    line = "configure motor "  # Fields 0 & 1
    line += CleanDatetimeString(NowUTC()) + " "  # Field 2
    line += self.MotorName + " "  # Field 3
    line += (
      str(self.CurrentAngle) + " "
    )  # Field 4: Remind the motor where it is according to its last report.
    line += (
      str(self.MinAngle) + " "
    )  # Field 5: Send the minimum movement position. Will override the default on the microcontroller.
    line += (
      str(self.MaxAngle) + " "
    )  # Field 6: Send the maximum movement position. Will override the default on the microcontroller.
    line += (
      str(self.BacklashAngle) + " "
    )  # Field 7: Send the backlash angle. Will override the default on the microcontroller.
    line += (
      str(self.Orientation) + " "
    )  # Field 8: Send the orientation of the motor. Will override the default on the microcontroller.
    line += str(self.FastTime) + " "  # Field 9: Send the FAST motor pulse limit.
    line += str(self.SlowTime) + " "  # Field 10: Send the SLOW motor pulse limit.
    line += (
      str(self.TimeDelta) + " "
    )  # Field 11: Send the motor pulse acceleration unit.
    line += (
      str(Parameters.MotorStatusDelay) + " "
    )  # Field 12: Set timer delay for sending motor status back to the RPi.
    line += (
      BoolToString(Parameters.FaultSensitive) + " "
    )  # Field 13: When 'y' the microcontroller will respect the DRV8825 fault pin to block movement.
    line += (
      BoolToString(self.OptimiseMoves) + " "
    )  # Field 14: When 'y' the microcontroller can take shortcuts for large moves.
    line += (
      str(self.LimitAngle) + " "
    )  # Field 15: Movement limit, motor will reverse around rather than crossing this limit.
    line += str(self.GearRatio) + " "  # Field 16: GearRatio.
    line += str(self.MotorStepsPerRev) + " "  # Field 17 MotorStepsPerRev
    line += (
      str(self.SlewStepMultiplier) + " "
    )  # Field 18 SlewStepMultiplier (The number of microsteps taken when making large Slew moves).
    line += str(self.RestAngle) + " "  # Field 19 RestAngle
    line += (
      self.ModeSignals + " "
    )  # Field 20 Steppermotor mode signals for microstepping.
    line += (
      BoolToString(Parameters.SlewEnabled) + " "
    )  # Field 21 SlewEnabled flat. (Can motor make FULL STEP moves during large position changes)
    line += (
      self.SlewSignals + " "
    )  # Field 22 Steppermotor mode signals for full steps (Fast slew).
    Mctl.Write(line)
    self.Log("motorcontrol.SendConfig (" + self.MotorName + ") end", terminal=False)
    return True

  def StepToAngle(self, steps=0):
    """Convert a number of steps to a final angle (0-360) of movement."""
    # Change number of steps into an angle (will be decimal result)
    return steps * 360 / float(self.AxisStepsPerRev)

  def AngleToStep(self, deg=0.0):
    """Convert a final angle of movement to the nearest whole number of motor steps."""
    # Change angle into a number of steps (will be rounded integer result)
    return int(round(deg * float(self.AxisStepsPerRev) / 360, 0))

  def TunePosition(self, delta):
    """Tune the motor position (motor steps). This corrects the position of the motor/telescope
    without registering a change in the direction it is currently pointing.
    Use this for drift adjustment or manual finetuning of the telescope position during setup or after problems.
    tune 20210410154530 azimuth -234
      0        1           2      3"""

    # This first makes sure that the motor is configured, it waits for that to be acknowledged before sending the tune command.
    # Check that the motors are configured before proceeding.
    self.Log(
      "motorcontrol.TunePosition(",
      self.MotorName,
      ") by",
      delta,
      "steps.",
      terminal=False,
    )
    # There can be input queued from the microcontroller waiting to be handled.
    # - We should check in case the motor has lost its configuration before proceeding.
    self.Log(
      "motorcontrol.TunePosition(",
      self.MotorName,
      "): CheckMotorConfig: Precheck motor is still configured.",
      terminal=False,
    )

    # Motor is now configured. Perform the actual move now.
    if self.MotorConfigured:  # Only allow tuning if the motor is configured.
      dtn = NowUTC()
      line = (
        "tune "
        + CleanDatetimeString(str(dtn))
        + " "
        + self.MotorName
        + " "
        + str(delta)
      )
      Mctl.Write(line)
      # This doesn't wait for feedback, it is up to the motorcontroller to deal with the message when it sees fit.
      # This program may send further tune messages if it still needs to change things.
    else:
      self.Log(
        "motorcontroller.TunePosition(",
        self.MotorName,
        "): Motor is not yet configured. Tune command will not be sent.",
        level="error",
      )
    self.Log(
      "motorcontrol.TunePosition(",
      self.MotorName,
      "):",
      delta,
      "step tune command sent to microcontroller.",
      terminal=False,
    )

  def ExtendTrajectory(self, targetobj):
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
    nowutc = NowUTC()
    segmentsize = (
      self.TrajectorySegmentSize
    )  # How long does a trajectory segment last? (seconds)
    line += (
      CleanDatetimeString(str(nowutc)) + " "
    )  # Timestamp must be current even if resending cached records.
    if (
      self.LastSentTrajectoryKey == self.TrajectoryValidUntil
      and self.TrajectoryValidUntil > nowutc
    ):  # We have a future result cached already for this...
      self.Log(
        "motorcontroller.ExtendTrajectory(",
        self.MotorName,
        "): Using cached trajectory calculation:",
        "'" + self.LastSentTrajectoryData + "'",
        terminal=False,
      )
      line += self.LastSentTrajectoryData
      Mctl.Write(line)
      return  # No need to process further.
    if (
      self.TrajectoryValidUntil is None
    ):  # Where does previously downloaded trajectory end? = Start of this chunk.
      startutc = nowutc
    else:
      startutc = self.TrajectoryValidUntil
    # We're not using a cached record, so continue constructing and calculating a new record.
    line += self.MotorName + " "
    if startutc < nowutc:  # Don't create OLD entries.
      startutc = nowutc
    # Calculate START angle for trajectory segment.
    az, alt = targetobj.AzAltDegrees(
      time=Datetime2Ts(startutc)
    )  # Needs to be Skyfield time!
    line += CleanDatetimeString(str(startutc)) + " "
    if self.MotorName == "altitude":
      startangle = alt
    else:
      startangle = az
    line += str(startangle) + " "
    if targetobj.IsFixedPoint():  # Fixed points can have a larger segment size.
      endutc = startutc + timedelta(
        seconds=segmentsize * 2
      )  # But not too large because we need multiple segments queued up on the microcontroller, otherwise it may send an off target signal if the trajectory list expires.
    else:
      endutc = startutc + timedelta(seconds=segmentsize)
    # Calculate END angle for trajectory segment.
    az, alt = targetobj.AzAltDegrees(
      time=Datetime2Ts(endutc)
    )  # Needs to be Skyfield time!
    if self.MotorName == "altitude":
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
      Parameters.UseDynamicTrajectoryPeriods and targetobj.IsFixedPoint() == False
    ):  # Cannot solve dynamic trajectories for fixed points!
      # We have the 'fixed time period' trajectory extent already calculated.
      # Maximise the time period for this extent so that we don't need to pass as many segments to the microcontroller.
      MaxIterations = 100  # Always quit once MaxIterations hit.
      while MaxIterations > 0:  # Time out if max iterations hit.
        MaxIterations -= 1  # Reduce timeout.
        segmentsize += int(
          self.TrajectorySegmentSize / 4
        )  # Increase the segment size.
        nextutc = startutc + timedelta(
          seconds=segmentsize
        )  # Timestamp of the larger segment size.
        az, alt = targetobj.AzAltDegrees(
          time=Datetime2Ts(nextutc)
        )  # Needs to be Skyfield time!
        if self.MotorName == "altitude":
          nextangle = alt
        else:
          nextangle = az
        # if self.MinAngle > nextangle or self.MaxAngle < nextangle: break # Cannot extend any further. *!*
        if self.MinObservationAngle > nextangle or self.MaxAngle < nextangle:
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
      if MaxIterations <= 0:  # Iteration limit hit!
        self.Log(
          "motorcontroller.ExtendTrajectory(",
          self.MotorName,
          "): MaxIterations hit. Segment artificially limited to",
          endutc,
          terminal=False,
        )
    line += CleanDatetimeString(str(endutc)) + " "
    line += str(endangle) + " "
    startpos = int(self.AngleToStep(startangle))
    endpos = int(self.AngleToStep(endangle))
    line += str(startpos) + " "  # Add actual stepper position for START of segment.
    line += str(endpos) + " "  # Add actual stepper position for END of segment.
    self.Log(
      "motorcontroller.ExtendTrajectory(",
      self.MotorName,
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
    # if endangle >= self.MinAngle and endangle <= self.MaxAngle: # We're still within range. *!*
    if (
      endangle >= self.MinObservationAngle and endangle <= self.MaxAngle
    ):  # We're still within range. *!*
      Mctl.Write(line)
      self.LastSentTrajectoryKey = (
        self.TrajectoryValidUntil
      )  # Cache the trajectory calculation, if the same calculation is triggered, we can re-use the earlier copy for speed.
      self.LastSentTrajectoryData = line[
        26:
      ]  # Store the data sent (without the leading timestamp, a fresh timestamp will be used if resent).
      self.Log(
        "motorcontroller.ExtendTrajectory(",
        self.MotorName,
        "): Cached trajectory calculation:",
        "'" + self.LastSentTrajectoryData + "'",
        terminal=False,
      )
    else:
      self.Log(
        "motorcontroller.ExtendTrajectory("
        + self.MotorName
        + "): Trajectory is now complete.",
        terminal=False,
      )

