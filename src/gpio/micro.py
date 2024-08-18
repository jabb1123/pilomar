
import threading
import time
import serial
from queue import Queue
from utils.text.textcolor import TextColor
from utils.params import attributemaster
from utils.time_funcs import NowUTC

class microcontroller(attributemaster):
  """Class to manage the UART communication between the RPi and the motor microcontroller.
  This handles I/O and buffering of inbound/outbound messages over the UART lines.
  It also represents the entire motorcontroller PCB.

  Creating an instance of this object is not enough to initiate communication.
  - You must then call the 'initiate()' method to kick things off.

      mctl = microcontroller(port='/dev/serial0',resetpin=Parameters.MctlResetPin,boardtype=Parameters.BoardType) # Create communication with microcontroller over uart0 serial port.
      mctl.Log = MainLog.Log # Tell which Logging function to use for main logfile messages.
      mctl.Initiate() # Initiate communication.
  """

  def __init__(self, port="/dev/serial0", resetpin=4, boardtype=None, logger=None):
    """
    port = serial port to use for UART communication.
    resetpin = pin used to control reset or power for the microcontroller.
    boardtype = Identifier of specific motorcontroller board.
          Motorcontrol board behaviour may change depending upon the board type.
      None = Default
      "Ton-2023-12" = Raspberry Pi 4 HAT format with onboard 5V power source.
      "Matt-2023-12-06"  = Basic PCB board design published just after Instructables project published.
    """
    self.SetLogger(
      logger=logger
    )  # Inherited from attributemaster: Set up references to chosen logger (or disable if no logger defined).
    self.BoardType = boardtype  # Can be one of [None,'Ton-2023-12','Matt-2023-12-06'], or add your own.
    # if self.BoardType in ['Ton-2023-12']: self.SupportsMode0 = self.SupportsMode1 = self.SupportsMode2 = False # The microstepping modes are not supported.
    # else: self.SupportsMode0 = self.SupportsMode1 = self.SupportsMode2 = True # The microstepping modes are supported.

    # Now initiate communication with the microcontroller.
    self.uart = serial.Serial(port, 115200, timeout=0, exclusive=True)
    self.QueueToMctl = (
      Queue()
    )  # Use queue mechanism to send commands to the microcontroller communication thread.
    self.QueueFromMctl = (
      Queue()
    )  # Use queue mechanism to receive commands from the microcontroller communication thread.
    self.ResetBCM = resetpin  # Grounding this pin will RESET the remote device. (or turn it off if microcontroller power is controlled by it).
    self.ResetPin = outputpin(
      self.ResetBCM, "MctlReset"
    )  # Create GPIO pin if a pin is specified, else create dummy pin. All pins start OFF.
    self.Lines = []  # No lines received yet.
    self.WriteChunkBytes = 32  # Maximum number of characters to send in a batch.
    self.WriteChunkSeconds = (
      0.2  # Seconds between chunks written to microcontroller.
    )
    self.InputLine = ""  # This is the line currently being received. Completed lines are added to Lines list.
    self.WriteQueue = []  # No output to send yet.
    self.LinesReceived = (
      0  # total number of lines received from the microcontroller.
    )
    self.LinesSent = 0  # Total count of lines sent to the microcontroller.
    self.BytesReceived = 0  # Byte count from microcontroller.
    self.BytesSent = 0  # Byte count sent to the microcontroller.
    self.PrintComms = False  # When TRUE communication log is copied to the terminal, otherwise it's only written to the log file.
    self.LedStatus = True  # LEDS on by default.
    self.LineOpenedTime = NowUTC()  # When did the UART comms start?
    self.LastTxTime = NowUTC()  # When was data last sent?
    self.LastRxTime = NowUTC()  # When was data last received?
    self.RxErrors = 0  # How many receive errors have been detected.
    self.LastLineSent = None  # We get 'reflection' on the UART port if the remote device isn't ready. This helps us to detect that.
    self.CommsTimeout = (
      Parameters.MctlCommsTimeout
    )  # Seconds. microcontroller is restarted if no data received after this period.
    self.ForcedRestarts = 0  # How many restarts have been forced by this software?
    self.RemoteRestarts = (
      0  # How many restarts have been registered by the remote device itself?
    )
    self.ResetAttempts = 0  # Increment for each sequential attempt to reset communication with the remote microcontroller board.
    self.PoweredByUsb = False  # If the device is connected by USB, then power handling is different.
    # Power to Microcontroller comes through USB cable, DO NOT enable power via the GPIO!
    UsbList = (
      SDCardMonitor.ListUSBdevices()
    )  # List all the potential devices. If the CIRCUITPYTHON device is connected via USB, say so here!
    for dn, dl in UsbList:  # Check all connected USB devices.
      if dl in [
        "CIRCUITPY"
      ]:  # Circuit Python device has USB connection. We cannot power it by GPIO at the same time!
        self.PoweredByUsb = True  # Don't allow GPIO power pin to be used.
        print(
          "microcontroller.__init__(): Detected that the microcontroller",
          dl,
          "is potentially being powered over USB. (WARNING)",
        )
        lines = [
          "DETECTED A CONNECTED USB DEVICE LABELLED " + str(dl) + ".",
          "This looks like it's a microcontroller.",
          " ",
          "The microcontroller could receive conflicting voltages via the",
          "USB line and the GPIO header. These may damage the devices.",
          " ",
          "For safety, the 'enable' pin for microcontroller power will not be used.",
          "It will be permanently powered via the USB cable instead.",
          " ",
          "This means pi-lomar cannot power cycle the microcontroller if it needs to",
          "reset it. It also means that the microcontroller clock may get independently",
          "synchronised by the USB connection as well as by the pi-lomar software.",
          " ",
          "The software will continue to run, but there is a risk of unexpected behaviour.",
          " ",
          "Concurrent USB + GPIO connections to the microcontroller are recommended only",
          "during development or debugging with special care taken to protect the devices.",
        ]
        TextColor.text_box(
          lines, fg=TextColor.WHITE, bg=TextColor.ORANGERED1, justify="c"
        )
    if (
      self.PoweredByUsb == False
    ):  # If no USB power, we're powering it via a GPIO signal.
      # Never turn on second power source to the microcontroller if it's already got USB power.
      self.ResetPin.On()  # Turn the microcontroller ON if we're in charge of the power supply.
    self.DeviceFailure = (
      False  # Set to TRUE if device seems to be irrecoverably lost.
    )
    self.ErrorWindow = (
      None  # Link to a display window that can show error messages.
    )
    self.WriteProhibited = False  # OK to write again to the write queue.
    self.SendId = 0  # Incremental counter, the message number being sent to the microcontroller. The microcontroller will respond that this message number has been received.
    # Calling program needs to call microcontroller.Initiate() to get things going.

  def StartMonitor(self):
    """Start replicating communications to the terminal.
    The messages are still logged."""
    if self.Log != None:
      self.Log("microcontroller.StartMonitor()", terminal=False)
    self.PrintComms = True  # UART comms will be echoed to the terminal.

  def EndMonitor(self):
    """Stop replicating communications to the terminal.
    The messages are still logged."""
    if self.Log != None:
      self.Log("microcontroller.EndMonitor()", terminal=False)
    self.PrintComms = False  # UART comms will not be echoed to the terminal.

  def PowerOn(self):
    """Overrides all safeties, turns power GPIO power pin on for microcontroller."""
    if self.ResetBCM is None:
      self.Log(
        "microcontroller.PowerOn(): No Reset pin defined. Cannot turn microcontroller on via GPIO.",
        terminal=True,
      )
      return
    authority = AskYesNo(
      "No safety checks. Do you want to turn ON GPIO power for the microcontroller [y/N]?",
      False,
      fg=TextColor.BLACK,
      bg=TextColor.ORANGERED1,
    )
    if authority:
      self.Log(
        "microcontroller.PowerOn(): No safety checks. GPIO POWER PIN turned on for Microcontroller.",
        terminal=True,
      )
      # GPIO.output(self.ResetBCM, GPIO.HIGH)
      self.ResetPin.On()

  def PowerOff(self):
    """Overrides all safeties, turns power GPIO power pin off for microcontroller."""
    if self.ResetBCM is None:
      self.Log(
        "microcontroller.PowerOff(): No Reset pin defined. Cannot turn microcontroller off via GPIO.",
        terminal=True,
      )
      return
    authority = AskYesNo(
      "No safety checks. Do you want to turn OFF GPIO power for the microcontroller [y/N]?",
      False,
      fg=TextColor.BLACK,
      bg=TextColor.ORANGERED1,
    )
    if authority:
      self.Log(
        "microcontroller.PowerOff(): No safety checks. GPIO POWER PIN turned off for Microcontroller.",
        terminal=True,
      )
      self.Log(
        "microcontroller.PowerOff(): Note: If the messagehandler is still running, it will restart the microcontroller automatically.",
        terminal=True,
      )
      # GPIO.output(self.ResetBCM, GPIO.LOW)
      self.ResetPin.Off()

  def PowerIsOn(self):
    """Return TRUE if power is on, FALSE otherwise.
    This uses GPIO.input(self.ResetBCM) even though the pin is defined as an output,
    it still works and returns the state of the pin."""
    return self.ResetPin.State

  def SendManualCommand(self):
    """Prompt the user for a manual command to send to the microcontroller.
    There is no validation performed on this, if you get the syntax wrong you may crash the
    microcontroller. Use at your own risk."""
    print(TextColor.yellow("Manual command to microcontroller."))
    print("Enter your commands ('&now' will be replaced with current timestamp.)")
    print("There is no error checking on manual commands. Be careful.")
    command = input(TextColor.cyan("command ['x' to exit]: ")).strip()
    if command.lower() == "x":
      return True  # Quit.
    if command != "":  # There's something to send.
      command = command.replace(
        "&now", CleanDatetimeString(str(NowUTC()))
      )  # Substitude any reference to the current clock.
      self.Log("microcontroller.SendManualCommand():", command, terminal=True)
      self.Write(command)  # Sent.
    return True

  def Initiate(self):
    """Initiate communication."""
    self.Log(
      "microcontroller.__init__:",
      "baudrate=",
      self.uart.baudrate,
      "bytesize=",
      self.uart.bytesize,
      "parity=",
      self.uart.parity,
      "stopbits=",
      self.uart.stopbits,
      "timeout=",
      self.uart.timeout,
      "write_timeout=",
      self.uart.write_timeout,
      "inter_byte_timeout=",
      self.uart.inter_byte_timeout,
      "xonxoff=",
      self.uart.xonxoff,
      "rtscts=",
      self.uart.rtscts,
      "dsrdtr=",
      self.uart.dsrdtr,
      terminal=False,
    )
    self.Log(
      "New UART device. Triggering reset to initialize it...", terminal=False
    )
    self.Reset(
      planned=True
    )  # Make sure that the microcontroller is fresh and ready for new tasks.
    self.uart.reset_input_buffer()
    self.uart.reset_output_buffer()
    self.Log("New UART connection. Flushing...", terminal=False)
    # Send a comment line to flush any crud from the system.
    for i in range(2):
      self.Write("#" * 20)
    self.Write("rpi started")  # Tell microcontroller that the RPi has just started.
    self.SetClock()  # Set the time on the microcontroller.

  def ReportBoard(self):
    """Report the board type to the log file."""
    self.Log("microcontroller.ReportBoard:", self.BoardType, terminal=False)

  def SetClock(self):
    """Set the microcontroller clock."""
    line = "set time " + CleanDatetimeString(
      str(NowUTC())
    )  # Immediately send a time update to the microcontroller to synchronise the clocks ASAP.
    self.Write(line)
    self.Log("microcontroller.SetClock(): Setting time to", line, terminal=False)

  def CalculateChecksum(self, line):
    """Calculate a basic checksum for a line of text."""
    cs = ""
    a = 0
    if len(line) > 0:
      for i in range(len(line)):
        if i % 2 == 0:
          a += ord(line[i])
        else:
          a += ord(line[i]) * 3
    cs = str(hex(a % 65536))[2:]
    return cs

  def AddChecksum(self, line):
    """Add a checksum to a line of text ready for transmission."""
    return line + "|" + self.CalculateChecksum(line)

  def RemoveChecksum(self, line):
    """Strip off the trailing checksum from a received line of text."""
    i = line.rfind("|")
    if i >= 0:
      line = line[:i]
    return line

  def ValidateChecksum(self, line):
    """Validate a line of text that contains a checksum.
    Returns TRUE if the checksum is correct.
    Returns FALSE if the checksum is not correct."""
    result = False
    i = line.rfind("|")
    if i >= 0:
      cs = line[i + 1 :]
      line = line[:i]
      if cs == self.CalculateChecksum(line):
        result = True
    return result

  def Reset(self, planned=False):
    """Remote device needs resetting.
    Planned = False : Means that this was an unplanned reset, the microcontroller failed.
          Too many of these,and the program considers the microcontroller faulty.
    Planned = True : Means that this was a planned reset, eg end of an observation.
          This is just a convenient way to stop the motors and prepare for a
          fresh observation to be set up. It doesn't indicate any fault in the microcontroller.

    If a USB connection is detected to the microcontroller, then a reset can only be a soft reset
    where we request the software itself to restart itself.

    If there is no USB connection, then the power is controlled via a GPIO pin, so we can perform
    a hard reset by cycling the power or sending a 'low' signal to a reset pin if the microcontroller has one.
    (It's the same mechanism, but the result depends upon your chosen microcontroller and circuitry.
    """
    if (
      not planned
    ):  # If this is recovering from unplanned errors, then count the resets.
      if self.ResetAttempts > 10:  # Don't bother again.
        msg = (
          "After "
          + str(self.ResetAttempts)
          + " attempts, considering the microcontroller failed."
        )
        if self.ErrorWindow != None and hasattr(self.ErrorWindow, "Print"):
          self.ErrorWindow.Print(msg)
        print(TextColor.red(msg))
        self.DeviceFailure = True
        MainLog.RecordTraceback(None)  # Record the stack at this point.
        exit()  # Quit the program. (*Q* Other threads don't get stopped however!)
        return False
      else:
        self.ResetAttempts += 1  # Try again.
    # The behaviour will depend upon the circuitry supporting the chosen microcontroller.
    if (
      self.PoweredByUsb
    ):  # Powered by USB, so cannot power cycle it. Send a RESET command instead.
      MainLog.Log(
        "microcontroller.Reset(): Device is connected via USB, will not enable power via GPIO for safety.",
        terminal=False,
      )
      DevWindow.print(
        NowHMS()
        + " Microcontroller is powered by USB, performing software reset."
      )
      if self.PrintComms:
        print(TextColor.yellow("GPIO not in use. Software reset."))
      # Send software 'reset' command instead.
      self.Write("reset")
      # self.WriteFlush() # Make sure all commands are flushed through.
      # When initializing for the first time, the write process isn't running! This won't flush.
    else:  # Not USB power, so can power cycle the microcontroller to reset it.
      # GPIO pin is driven low for a second. This either triggers the microcontroller's
      # reset pin directly (eg Pico RP2040, Feather RP2040 etc),
      # or it can simply switch off the power to a microcontroller that lacks a reset pin (eg Tiny2040).
      DevWindow.print(
        NowHMS()
        + " Microcontroller is powered by GPIO, performing power reset."
      )
      # GPIO.output(self.ResetBCM, GPIO.LOW)
      if self.PrintComms:
        print(TextColor.yellow("GPIO pin", self.ResetBCM, "low."))
      self.ResetPin.Off()  # If it's a real pin, turn it off, else do nothing.
      time.sleep(1)  # Pause 1 second.
      if self.PrintComms:
        print(TextColor.yellow("GPIO pin", self.ResetBCM, "high."))
      self.ResetPin.On()  # If it's a real pin and enabled, turn it on, else do nothing.
      time.sleep(1)  # Pause 1 second.
    self.uart.reset_output_buffer()
    self.uart.reset_input_buffer()
    self.Lines = []  # No lines received yet.
    self.InputLine = (
      ""  # This holds the currently arriving line while it is being constructed.
    )
    self.WriteQueue = []  # No output to send yet.
    self.LineOpenedTime = NowUTC()
    self.LastTxTime = NowUTC()  # When was data last sent?
    self.LastRxTime = NowUTC()  # When was data last received?
    self.LastLineSent = None  # We get 'reflection' on the UART port if the remote device isn't ready. This needs ignoring.
    # Reset communication counters.
    self.LinesReceived = 0
    self.LinesSent = 0
    self.BytesReceived = 0
    self.BytesSent = 0
    self.RxErrors = 0
    self.ForcedRestarts += (
      1  # Record that we've chosen to forcefully restart the microcontroller.
    )
    self.WriteProhibited = False  # OK to write again to the write queue.
    ErrorWindow.print(NowHMS() + " Microcontroller reset ; planned " + str(planned))
    return True

  def RxAge(self):
    """How many seconds ago was the last message received?"""
    Rx = int((NowUTC() - self.LastRxTime).total_seconds())
    return Rx

  def ReadPoll(self):
    """Read all waiting characters into the input queue.
    This reads from the UART input queue and adds any received
    text into an internal buffer ready for the program to process.
    To pull a received message from the input queue use the Read() method instead!.
    """

    if not self.uart.is_open:
      MctlRxWindow.print("uart.ReadPoll: uart is not open!.")
      return  # Don't perform the poll.

    # Check for stalled communications.
    if self.RxAge() > self.CommsTimeout:
      self.Log(
        "uart.ReadPoll(): microcontroller has not transmitted for",
        self.RxAge(),
        "seconds. It will be restarted",
        level="error",
        terminal=False,
      )
      if self.Reset():  # Trigger reset and resync mechanism.
        self.Log(
          "uart.ReadPoll(): microcontroller reset complete.", terminal=False
        )
      else:
        self.Log(
          "uart.ReadPoll(): microcontroller reset failed.", level="error"
        )
        if self.DeviceFailure:
          self.Log(
            "uart.ReadPoll(): microcontroller considered permanently unavailable after "
            + str(self.ResetAttempts)
            + " restart attempts.",
            level="error",
            terminal=False,
          )
    while self.uart.in_waiting:  # Something in the read queue.
      try:  # Try to get the next available character.
        response = self.uart.read(1)  # Read single character.
        response = response.decode("utf-8")  # Decode the character.
        self.BytesReceived += 1  # Increment received count.
      except Exception as e:
        self.Log(
          "uart.Read: uart.read(1) failed. Ignored. " + str(e), terminal=False
        )
        response = ""  # Ignore unusable character.
      if response == "\n":  # End of line received.
        if (
          self.InputLine == self.LastLineSent
        ):  # We have reflection on the UART channel. Trouble!
          # This is a sign that the remote device isn't responding. UART seems to loop back in that case.
          print(
            TextColor.red(
              "uart.Read: Ignoring reflected line ("
              + str(self.InputLine)
              + ")"
            )
          )
          self.Log(
            "uart.Read: Ignoring reflected line ("
            + str(self.InputLine)
            + ")",
            terminal=False,
          )
        else:  # We have a valid line received from the correspondent.
          self.Lines.append(
            self.InputLine
          )  # Add received line to input queue.
          self.LastRxTime = (
            NowUTC()
          )  # Note when last receive activity occurred.
          self.ResetAttempts = (
            0  # We have activity, so clear the restart counter.
          )
          self.LinesReceived += 1  # Increment count of lines received.

          # If we are not currently running an observation, nothing is reading the queue, so flush anything too old.
          while len(self.Lines) > Parameters.UartRxQueueLimit:
            delline = self.Lines.pop(0)  # Kill the oldest lines first.

        self.InputLine = (
          ""  # Start a fresh input line next time anything is received.
        )
      else:
        self.InputLine += (
          response  # Add the character to the input line we are constructing.
        )

  def Read(self):
    """Return the next input line received (if there is one).
    Validate checksum and ignore anything which fails.
    This pulls the next input line from the received buffer.
    It does not poll the UART input line directly (See ReadPoll() method)."""
    result = ""
    while (
      len(result) == 0 and len(self.Lines) > 0
    ):  # No valid line to return yet, and still lines available in the receive buffer.
      result = self.Lines.pop(0).strip()
      if self.ValidateChecksum(result):  # Line is good, remove the checksum.
        cleanresult = self.RemoveChecksum(result)
      else:  # Line is bad. Don't clean it.
        cleanresult = result
      self.Log("RPi received: " + cleanresult, terminal=False)
      if self.PrintComms:
        print(TextColor.magenta("RPi received: " + cleanresult))

      MctlRxWindow.print(cleanresult)
      if self.ValidateChecksum(result):  # Line is good.
        result = cleanresult  # self.RemoveChecksum(result)
        if result == "pico started" or result == "controller started":
          self.RemoteRestarts += (
            1  # Record how many times the remote device reports a restart.
          )
          ErrorWindow.print(NowHMS() + " " + result)
        if "error" in result:
          print(TextColor.red("RPi received: ") + result)
          ErrorWindow.print(NowHMS() + " RPi received: " + result)
      else:  # Checksum failure.
        MctlRxWindow.print("RPi rejected checksum on: " + result)
        self.Log("RPi rejected checksum on: " + result, terminal=False)
        self.RxErrors += 1
        ErrorWindow.print(NowHMS() + " RPi rejected checksum on: " + result)
        result = ""
      # Some messages we can deal with immediately without passing back to the calling routines.
      if result.startswith("#"):
        result = ""  # Ignore comments.
    return result

  def WritePoll(self):
    """Write a chunk of data from the output buffer to the UART port.
    This takes lower priority than the READ from the UART port.
    It will only send 1 chunk every 0.2 seconds to give the receiving microcontroller
    time to read the data.
    To add lines to the output buffer use the Write() method."""
    if len(self.WriteQueue) == 0:
      return  # Nothing to send anyway.
    if self.uart.in_waiting:
      return  # Input waiting. Handle that first.
    if (
      self.LastTxTime != None
      and (NowUTC() - self.LastTxTime).total_seconds() < self.WriteChunkSeconds
    ):  # 0.2:
      return  # Must be 0.2 second gap between each transmitted packet.
    if not self.uart.is_open:
      MctlTxWindow.print("uart.WritePoll: uart is not open!.")
    if (
      len(self.WriteQueue[0]) < self.WriteChunkBytes
    ):  # Can write the entire line in one go.
      line = self.WriteQueue.pop(0)
      terminator = "\n"
    else:  # Need to send just a chunk of the line in this pass.
      line = self.WriteQueue[0][
        0 : self.WriteChunkBytes
      ]  # 1st 'chunksize' characters only.
      self.WriteQueue[0] = self.WriteQueue[0][
        self.WriteChunkBytes :
      ]  # Remove transmitted characters.
      terminator = ""
    self.LastLineSent = line  # Keep a note of what we sent, if we receive that back it is reflection indicating a problem.
    line += terminator
    self.LinesSent += 1
    self.BytesSent += len(line)
    self.uart.write(line.encode("utf-8"))  # Send data in UTF-8 format.
    self.LastTxTime = NowUTC()  # Note that time of the last data sent.

  def ReadFlush(self):
    """Clear the input buffer. Don't actually process them, because you may never reach the end if
    new messages are appearing. Just clear and reset the internal buffer of messages received.
    """
    self.Log(
      "microcontroller.ReadFlush: Drop",
      len(self.Lines),
      "unprocessed messages received from microcontroller...",
      terminal=False,
    )
    if len(self.Lines) > 0:
      for line in self.Lines:
        self.Log(
          "microcontroller.ReadFlush: Dropped line:", line, terminal=False
        )
      self.Lines = []  # Empty the queue.
    if len(self.InputLine) > 0:
      self.Log(
        "microcontroller.ReadFlush: Abandoned partly received input line (",
        self.InputLine,
        ")",
        terminal=False,
      )
      self.InputLine = (
        ""  # Scrap any line currently being received and constructed.
      )

  def WriteFlush(self, send=True):
    """Make sure the output buffer is completely flushed. Timeout after a limited number of attempts.
    This doesn't add anything to the output queue, it just makes sure that everything
    waiting to be sent is transmitted.
    if send parameter is false, the write queue is flushed without sending anything further.
    - Send = True: This routine will trigger WritePoll() directly. Assume that the main sending routine is stopped.
    - Send = False: This routine just flushes."""
    result = True
    if send:  # We should try to send outstanding messages.
      self.Log(
        "WriteFlush: Flushing microcontroller output queue (",
        len(self.WriteQueue),
        "pending messages will be sent)...",
        terminal=False,
      )
      self.Log(
        "WriteFlush: WriteProhibited:", self.WriteProhibited, terminal=False
      )
      TryCount = 0
      self.WriteProhibited = True  # Don't allow anything further to be added to the queue at the moment.
      while len(self.WriteQueue) > 0:
        TryCount += 1
        self.Log(
          "WriteFlush: Queue currently",
          len(self.WriteQueue),
          "entries",
          terminal=False,
        )
        self.Log(
          "WriteFlush: 1st in queue:", self.WriteQueue[0], terminal=False
        )
        self.WritePoll()  # Send next chunk of data from output buffer if allowed.
        time.sleep(
          0.1
        )  # Pause until the CommsLoop thread has cleared the buffer.
        if TryCount >= 500:
          self.Log(
            "WriteFlush: Flush timeout. Maximum loops.",
            len(self.WriteQueue),
            "Remaining messages will be dropped.",
            terminal=False,
          )
          result = False
          break
      self.WriteProhibited = False  # OK to write again to the write queue.
    else:
      self.Log(
        "WriteFlush: Flushing microcontroller output queue (",
        len(self.WriteQueue),
        "pending messages will be dropped)...",
        terminal=False,
      )
    self.WriteQueue = []  # Delete any remaining messages in the queue.
    return result

  def SetLedStatus(self, status=True):
    """Change status of Microcontroller LEDs.
    This will make the LEDS on the microcontroller itself go dark.
    This reduces light pollution within the telescope dome."""
    self.LedStatus = status
    if status:
      self.Write("leds on")
    else:
      self.Write("leds off")

  def MctlRestarted(self):
    """If microcontroller reports a restart, this routine resets the buffers and
    acknowledges the restart back to the microcontroller."""
    self.WriteFlush(
      send=False
    )  # Scrap the contents of the write buffer. We're starting again.
    self.Write(
      "# Hello controller"
    )  # Acknowledge to the microcontroller that we're restarting the conversation too.
    self.SetLedStatus(
      self.LedStatus
    )  # Turn on/off the status led on the microcontroller.

  def Write(self, line):
    """Add a new output message to the queue to be processed.
    It is not physically transmitted, it will wait in turn in the
    output queue until WritePoll() gets around to sending it.
    Nothing is added to the queue if self.WriteProhibited = True.
    To send text from the output queue to the Microcontroller over the UART line use the WritePoll() method.
    """
    if self.WriteProhibited:
      self.Log("microcontroller.Write: WriteProhibited: " + line)
    elif len(line) > 0:
      line = line.replace("\n", "")  # Was strip()
      self.SendId += 1  # Increment the message ID number.
      if line[-1:] != " ":
        line += " "  # Need a space separator between fields.
      line += (
        "[" + str(self.SendId) + "]"
      )  # Append sequential message ID. microcontroller will respond with this ID when it has received OK.
      MctlTxWindow.print(line)
      self.WriteQueue.append(
        self.AddChecksum(line)
      )  # Add to send queue with Checksum.
      self.Log(
        "RPi queueing (Q# " + str(len(self.WriteQueue)) + "): " + line,
        terminal=False,
      )
      if self.PrintComms:
        print(
          TextColor.green(
            "RPi queueing (Q# " + str(len(self.WriteQueue)) + "): " + line
          )
        )

  def CommsLoop(self, commandqueue):  # Runs as own thread.
    """This runs in its own thread, it just continually reads/writes
    to the microcontroller via the uart serial connection.
    It terminates when the main thread dies.
    You can send commands to this communication loop itself via the commandqueue queue.
    - Eg : 'stop' to shut down the loop completely."""
    self.Log("microcontroller.CommsLoop(): Start", terminal=False)

    prevloop = NowUTC()
    while True:  # Loop until explicitly told to break.
      # Warn if the loop is running slowly.
      tn = NowUTC()
      td = (tn - prevloop).total_seconds()
      if td > 1:
        self.Log(
          "microcontroller.CommsLoop(): Loop slow. Took",
          td,
          "seconds.",
          terminal=False,
        )
      prevloop = tn
      # Exchange messages with the microcontroller.
      self.WritePoll()  # Send next chunk of data from output buffer if allowed.
      self.ReadPoll()  # Read anything waiting in the input buffer.
      if (
        threading.main_thread().is_alive() == False
      ):  # Check if parent is still alive. Quit if it is nolonger there.
        self.Log(
          "microcontroller.CommsLoop(): Parent thread is nolonger alive. Stopping.",
          level="error",
        )
        break  # Parent thread died, so terminate this thread too.
      if (
        commandqueue.empty() == False
      ):  # This queue allows the main thread to send commands to the microcontroller comms controller itself.
        ReceivedMessage = commandqueue.get()
        if ReceivedMessage == "stop":
          self.Log(
            "microcontroller.CommsLoop(): Received 'stop' command.",
            terminal=False,
          )
          break  # Terminate this loop. Will require restart by main thread.
      time.sleep(0.01)  # Need a tiny pause otherwise this hogs the processor.
    self.WriteFlush(
      send=True
    )  # Flush any outbound comms to the microcontroller before closing.
    self.Log("microcontroller.CommsLoop(): End", terminal=False)
