from datetime import datetime
import threading
import time
import serial
from queue import Queue
from utils.files.disk import DiskMonitor
from utils.logfile import LogFile
from utils.text.display import ask_yes_no
from utils.text.human_readable import clean_datetime_string
from utils.text.textcolor import TextColor
from utils.params import AttributeMaster, Parameters
from utils.time_funcs import now_hour_minute_sec, now_utc

import gpio

if gpio.GPIO_DRIVER == "GPIO":  # Original GPIO handlers needed for IO.
    # Select the GPIO specific drivers for IO functions.
    outputpin = gpio.OutputPinGPIO
elif gpio.GPIO_DRIVER == "GPIOD":  # Bookworm GPIOD handlers needed for IO.
    # Select the GPIOD specific drivers for IO functions.
    outputpin = gpio.OutputPinGPIO
else:
    pass
    # raise ImportError(
    #     "Could not identify a suitable GPIO driver for this installation."
    # )


class Microcontroller(AttributeMaster):
    """Class to manage the UART communication between the RPi and the motor microcontroller.
    This handles I/O and buffering of inbound/outbound messages over the UART lines.
    It also represents the entire motorcontroller PCB.

    Creating an instance of this object is not enough to initiate communication.
    - You must then call the 'initiate()' method to kick things off.

        mctl = microcontroller(port='/dev/serial0',resetpin=Parameters.MctlResetPin,boardtype=Parameters.BoardType) # Create communication with microcontroller over uart0 serial port.
        mctl.Log = self.logger.Log # Tell which Logging function to use for main logfile messages.
        mctl.Initiate() # Initiate communication.
    """

    def __init__(
        self,
        port="/dev/serial0",
        resetpin=4,
        boardtype=None,
        logger: LogFile = None,
        parameters: Parameters = None,
        sd_card_monitor: DiskMonitor = None,
    ):
        """
        port = serial port to use for UART communication.
        resetpin = pin used to control reset or power for the microcontroller.
        boardtype = Identifier of specific motorcontroller board.
              Motorcontrol board behaviour may change depending upon the board type.
          None = Default
          "Ton-2023-12" = Raspberry Pi 4 HAT format with onboard 5V power source.
          "Matt-2023-12-06"  = Basic PCB board design published just after Instructables project published.
        """
        # Inherited from attributemaster: Set up references to chosen logger (or disable if no logger defined).
        self.set_logger(logger=logger)
        self.board_type = boardtype  # Can be one of [None,'Ton-2023-12','Matt-2023-12-06'], or add your own.
        # if self.board_type in ['Ton-2023-12']: self.supports_mode0 = self.supports_mode1 = self.supports_mode2 = False # The microstepping modes are not supported.
        # else: self.supports_mode0 = self.supports_mode1 = self.supports_mode2 = True # The microstepping modes are supported.

        self.sd_card_monitor: DiskMonitor = sd_card_monitor
        # Now initiate communication with the microcontroller.
        self.uart = serial.Serial(port, 115200, timeout=0, exclusive=True)
        # Use queue mechanism to send commands to the microcontroller communication thread.
        self.queue_to_mctl = Queue()
        # Use queue mechanism to receive commands from the microcontroller communication thread.
        self.queue_from_mctl = Queue()
        # Grounding this pin will RESET the remote device. (or turn it off if microcontroller power is controlled by it).
        self.reset_bcm = resetpin
        # Create GPIO pin if a pin is specified, else create dummy pin. All pins start OFF.
        self.reset_pin = outputpin(self.reset_bcm, "MctlReset")
        # No lines received yet.
        self.lines = []
        # Maximum number of characters to send in a batch.
        self.write_chunk_bytes = 32
        # Seconds between chunks written to microcontroller.
        self.write_chunk_seconds = 0.2
        # This is the line currently being received. Completed lines are added to Lines list.
        self.input_line = ""
        # No output to send yet.
        self.write_queue = []
        # total number of lines received from the microcontroller.
        self.lines_received = 0
        # Total count of lines sent to the microcontroller.
        self.lines_sent = 0
        # Byte count from microcontroller.
        self.bytes_received = 0
        # Byte count sent to the microcontroller.
        self.bytes_sent = 0
        # When TRUE communication log is copied to the terminal, otherwise it's only written to the log file.
        self.print_comms = False
        # LEDS on by default.
        self.led_status = True
        # When did the UART comms start?
        self.line_opened_time = now_utc()
        # When was data last sent?
        self.last_tx_time = now_utc()
        # When was data last received?
        self.last_rx_time = now_utc()
        # How many receive errors have been detected.
        self.rx_errors = 0
        # We get 'reflection' on the UART port if the remote device isn't ready. This helps us to detect that.
        self.last_line_sent = None
        # Seconds. microcontroller is restarted if no data received after this period.
        self.comms_timeout = parameters.mctl_comms_timeout
        # How many restarts have been forced by this software?
        self.forced_restarts = 0
        # How many restarts have been registered by the remote device itself?
        self.remote_restarts = 0
        # Increment for each sequential attempt to reset communication with the remote microcontroller board.
        self.reset_attempts = 0
        # If the device is connected by USB, then power handling is different.
        self.powered_by_usb = False
        self.parameters = parameters
        # Power to Microcontroller comes through USB cable, DO NOT enable power via the GPIO!
        # List all the potential devices. If the CIRCUITPYTHON device is connected via USB, say so here!
        usb_list = self.sd_card_monitor.list_us_bdevices()
        # Check all connected USB devices.
        for dn, dl in usb_list:
            # Circuit Python device has USB connection. We cannot power it by GPIO at the same time!
            if dl in ["CIRCUITPY"]:
                # Don't allow GPIO power pin to be used.
                self.powered_by_usb = True
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
        # If no USB power, we're powering it via a GPIO signal.
        if not self.powered_by_usb:
            # Never turn on second power source to the microcontroller if it's already got USB power.
            # Turn the microcontroller ON if we're in charge of the power supply.
            self.reset_pin.on()
        # Set to TRUE if device seems to be irrecoverably lost.
        self.device_failure = False
        # Link to a display window that can show error messages.
        # OK to write again to the write queue.
        self.write_prohibited = False
        # Incremental counter, the message number being sent to the microcontroller.
        # The microcontroller will respond that this message number has been received.
        self.send_id = 0
        # Calling program needs to call microcontroller.Initiate() to get things going.

    def start_monitor(self):
        """Start replicating communications to the terminal.
        The messages are still logged."""
        if self.log is not None:
            self.log("microcontroller.StartMonitor()", terminal=False)
        # UART comms will be echoed to the terminal.
        self.print_comms = True

    def end_monitor(self):
        """Stop replicating communications to the terminal.
        The messages are still logged."""
        if self.log is not None:
            self.log("microcontroller.EndMonitor()", terminal=False)
        # UART comms will not be echoed to the terminal.
        self.print_comms = False

    def power_on(self):
        """Overrides all safeties, turns power GPIO power pin on for microcontroller."""
        if self.reset_bcm is None:
            self.log(
                "microcontroller.PowerOn(): No Reset pin defined. Cannot turn microcontroller on via GPIO.",
                terminal=True,
            )
            return
        authority = ask_yes_no(
            "No safety checks. Do you want to turn ON GPIO power for the microcontroller [y/N]?",
            False,
            fg=TextColor.BLACK,
            bg=TextColor.ORANGERED1,
        )
        if authority:
            self.log(
                "microcontroller.PowerOn(): No safety checks. GPIO POWER PIN turned on for Microcontroller.",
                terminal=True,
            )
            # GPIO.output(self.reset_bcm, GPIO.HIGH)
            self.reset_pin.On()

    def power_off(self):
        """Overrides all safeties, turns power GPIO power pin off for microcontroller."""
        if self.reset_bcm is None:
            self.log(
                "microcontroller.PowerOff(): No Reset pin defined. Cannot turn microcontroller off via GPIO.",
                terminal=True,
            )
            return
        authority = ask_yes_no(
            "No safety checks. Do you want to turn OFF GPIO power for the microcontroller [y/N]?",
            False,
            fg=TextColor.BLACK,
            bg=TextColor.ORANGERED1,
        )
        if authority:
            self.log(
                "microcontroller.PowerOff(): No safety checks. GPIO POWER PIN turned off for Microcontroller.",
                terminal=True,
            )
            self.log(
                "microcontroller.PowerOff(): Note: If the messagehandler is still running, it will restart the microcontroller automatically.",
                terminal=True,
            )
            # GPIO.output(self.reset_bcm, GPIO.LOW)
            self.reset_pin.Off()

    def power_is_on(self):
        """Return TRUE if power is on, FALSE otherwise.
        This uses GPIO.input(self.reset_bcm) even though the pin is defined as an output,
        it still works and returns the state of the pin."""
        return self.reset_pin.State

    def send_manual_command(self):
        """Prompt the user for a manual command to send to the microcontroller.
        There is no validation performed on this, if you get the syntax wrong you may crash the
        microcontroller. Use at your own risk."""
        print(TextColor.yellow("Manual command to microcontroller."))
        print("Enter your commands ('&now' will be replaced with current timestamp.)")
        print("There is no error checking on manual commands. Be careful.")
        command = input(TextColor.cyan("command ['x' to exit]: ")).strip()
        if command.lower() == "x":
            # Quit.
            return True
        # There's something to send.
        if command != "":
            # Substitude any reference to the current clock.
            command = command.replace("&now", clean_datetime_string(str(now_utc())))
            self.log("microcontroller.SendManualCommand():", command, terminal=True)
            # Sent.
            self.write(command)
        return True

    def initiate(self):
        """Initiate communication."""
        self.log(
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
        self.log(
            "New UART device. Triggering reset to initialize it...", terminal=False
        )
        # Make sure that the microcontroller is fresh and ready for new tasks.
        self.reset(planned=True)
        self.uart.reset_input_buffer()
        self.uart.reset_output_buffer()
        self.log("New UART connection. Flushing...", terminal=False)
        # Send a comment line to flush any crud from the system.
        for i in range(2):
            self.write("#" * 20)
        # Tell microcontroller that the RPi has just started.
        self.write("rpi started")
        # Set the time on the microcontroller.
        self.set_clock()

    def report_board(self):
        """Report the board type to the log file."""
        self.log("microcontroller.ReportBoard:", self.board_type, terminal=False)

    def set_clock(self):
        """Set the microcontroller clock."""
        # Immediately send a time update to the microcontroller to synchronise the clocks ASAP.
        line = "set time " + clean_datetime_string(str(now_utc()))
        self.write(line)
        self.log("microcontroller.SetClock(): Setting time to", line, terminal=False)

    def calculate_checksum(self, line):
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

    def add_checksum(self, line):
        """Add a checksum to a line of text ready for transmission."""
        return line + "|" + self.calculate_checksum(line)

    def remove_checksum(self, line):
        """Strip off the trailing checksum from a received line of text."""
        i = line.rfind("|")
        if i >= 0:
            line = line[:i]
        return line

    def validate_checksum(self, line):
        """Validate a line of text that contains a checksum.
        Returns TRUE if the checksum is correct.
        Returns FALSE if the checksum is not correct."""
        result = False
        i = line.rfind("|")
        if i >= 0:
            cs = line[i + 1 :]
            line = line[:i]
            if cs == self.calculate_checksum(line):
                result = True
        return result

    def reset(self, planned=False):
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
        # If this is recovering from unplanned errors, then count the resets.
        if not planned:
            if self.reset_attempts > 10:  # Don't bother again.
                msg = (
                    "After "
                    + str(self.reset_attempts)
                    + " attempts, considering the microcontroller failed."
                )
                if self.parameters.error_window is not None and hasattr(
                    self.parameters.error_window, "Print"
                ):
                    self.parameters.error_window.Print(msg)
                print(TextColor.red(msg))
                self.device_failure = True
                self.logger.record_traceback(None)  # Record the stack at this point.
                exit()  # Quit the program. (*Q* Other threads don't get stopped however!)
                return False
            else:
                self.reset_attempts += 1  # Try again.
        # The behaviour will depend upon the circuitry supporting the chosen microcontroller.
        # Powered by USB, so cannot power cycle it. Send a RESET command instead.
        if self.powered_by_usb:
            self.logger.log(
                "microcontroller.Reset(): Device is connected via USB, will not enable power via GPIO for safety.",
                terminal=False,
            )
            self.parameters.dev_window.print(
                now_hour_minute_sec()
                + " Microcontroller is powered by USB, performing software reset."
            )
            if self.print_comms:
                print(TextColor.yellow("GPIO not in use. Software reset."))
            # Send software 'reset' command instead.
            self.write("reset")
            # self.write_flush() # Make sure all commands are flushed through.
            # When initializing for the first time, the write process isn't running! This won't flush.
        else:  # Not USB power, so can power cycle the microcontroller to reset it.
            # GPIO pin is driven low for a second. This either triggers the microcontroller's
            # reset pin directly (eg Pico RP2040, Feather RP2040 etc),
            # or it can simply switch off the power to a microcontroller that lacks a reset pin (eg Tiny2040).
            self.parameters.dev_window.print(
                now_hour_minute_sec()
                + " Microcontroller is powered by GPIO, performing power reset."
            )
            # GPIO.output(self.reset_bcm, GPIO.LOW)
            if self.print_comms:
                print(TextColor.yellow("GPIO pin", self.reset_bcm, "low."))
            self.reset_pin.Off()  # If it's a real pin, turn it off, else do nothing.
            time.sleep(1)  # Pause 1 second.
            if self.print_comms:
                print(TextColor.yellow("GPIO pin", self.reset_bcm, "high."))
            self.reset_pin.On()  # If it's a real pin and enabled, turn it on, else do nothing.
            time.sleep(1)  # Pause 1 second.
        self.uart.reset_output_buffer()
        self.uart.reset_input_buffer()
        self.lines = []  # No lines received yet.
        self.input_line = (
            ""  # This holds the currently arriving line while it is being constructed.
        )
        self.write_queue = []  # No output to send yet.
        self.line_opened_time = now_utc()
        self.last_tx_time = now_utc()  # When was data last sent?
        self.last_rx_time = now_utc()  # When was data last received?
        self.last_line_sent = None  # We get 'reflection' on the UART port if the remote device isn't ready. This needs ignoring.
        # Reset communication counters.
        self.lines_received = 0
        self.lines_sent = 0
        self.bytes_received = 0
        self.bytes_sent = 0
        self.rx_errors = 0
        self.forced_restarts += (
            1  # Record that we've chosen to forcefully restart the microcontroller.
        )
        self.write_prohibited = False  # OK to write again to the write queue.
        self.parameters.error_window.print(
            now_hour_minute_sec() + " Microcontroller reset ; planned " + str(planned)
        )
        return True

    def rx_age(self):
        """How many seconds ago was the last message received?"""
        Rx = int((now_utc() - self.last_rx_time).total_seconds())
        return Rx

    def read_poll(self):
        """Read all waiting characters into the input queue.
        This reads from the UART input queue and adds any received
        text into an internal buffer ready for the program to process.
        To pull a received message from the input queue use the Read() method instead!.
        """

        if not self.uart.is_open:
            MctlRxWindow.print("uart.ReadPoll: uart is not open!.")
            return  # Don't perform the poll.

        # Check for stalled communications.
        if self.rx_age() > self.comms_timeout:
            self.log(
                "uart.ReadPoll(): microcontroller has not transmitted for",
                self.rx_age(),
                "seconds. It will be restarted",
                level="error",
                terminal=False,
            )
            if self.reset():  # Trigger reset and resync mechanism.
                self.log(
                    "uart.ReadPoll(): microcontroller reset complete.", terminal=False
                )
            else:
                self.log(
                    "uart.ReadPoll(): microcontroller reset failed.", level="error"
                )
                if self.device_failure:
                    self.log(
                        "uart.ReadPoll(): microcontroller considered permanently unavailable after "
                        + str(self.reset_attempts)
                        + " restart attempts.",
                        level="error",
                        terminal=False,
                    )
        while self.uart.in_waiting:  # Something in the read queue.
            try:  # Try to get the next available character.
                response = self.uart.read(1)  # Read single character.
                response = response.decode("utf-8")  # Decode the character.
                self.bytes_received += 1  # Increment received count.
            except Exception as e:
                self.log(
                    "uart.Read: uart.read(1) failed. Ignored. " + str(e), terminal=False
                )
                response = ""  # Ignore unusable character.
            if response == "\n":  # End of line received.
                # We have reflection on the UART channel. Trouble!
                if self.input_line == self.last_line_sent:
                    # This is a sign that the remote device isn't responding. UART seems to loop back in that case.
                    print(
                        TextColor.red(
                            "uart.Read: Ignoring reflected line ("
                            + str(self.input_line)
                            + ")"
                        )
                    )
                    self.log(
                        "uart.Read: Ignoring reflected line ("
                        + str(self.input_line)
                        + ")",
                        terminal=False,
                    )
                else:  # We have a valid line received from the correspondent.
                    # Add received line to input queue.
                    self.lines.append(self.input_line)
                    # Note when last receive activity occurred.
                    self.last_rx_time = now_utc()
                    # We have activity, so clear the restart counter.
                    self.reset_attempts = 0
                    self.lines_received += 1  # Increment count of lines received.

                    # If we are not currently running an observation, nothing is reading the queue, so flush anything too old.
                    while len(self.lines) > self.parameters.uart_rx_queue_limit:
                        delline = self.lines.pop(0)  # Kill the oldest lines first.
                # Start a fresh input line next time anything is received.
                self.input_line = ""
            else:
                # Add the character to the input line we are constructing.
                self.input_line += response

    def read(self):
        """Return the next input line received (if there is one).
        Validate checksum and ignore anything which fails.
        This pulls the next input line from the received buffer.
        It does not poll the UART input line directly (See ReadPoll() method)."""
        result = ""
        # No valid line to return yet, and still lines available in the receive buffer.
        while len(result) == 0 and len(self.lines) > 0:
            result = self.lines.pop(0).strip()
            if self.validate_checksum(result):  # Line is good, remove the checksum.
                cleanresult = self.remove_checksum(result)
            else:  # Line is bad. Don't clean it.
                cleanresult = result
            self.log("RPi received: " + cleanresult, terminal=False)
            if self.print_comms:
                print(TextColor.magenta("RPi received: " + cleanresult))

            MctlRxWindow.print(cleanresult)
            if self.validate_checksum(result):  # Line is good.
                result = cleanresult  # self.remove_checksum(result)
                if result == "pico started" or result == "controller started":
                    # Record how many times the remote device reports a restart.
                    self.remote_restarts += 1
                    self.parameters.error_window.print(
                        now_hour_minute_sec() + " " + result
                    )
                if "error" in result:
                    print(TextColor.red("RPi received: ") + result)
                    self.parameters.error_window.print(
                        now_hour_minute_sec() + " RPi received: " + result
                    )
            else:  # Checksum failure.
                MctlRxWindow.print("RPi rejected checksum on: " + result)
                self.log("RPi rejected checksum on: " + result, terminal=False)
                self.rx_errors += 1
                self.parameters.error_window.print(
                    now_hour_minute_sec() + " RPi rejected checksum on: " + result
                )
                result = ""
            # Some messages we can deal with immediately without passing back to the calling routines.
            if result.startswith("#"):
                result = ""  # Ignore comments.
        return result

    def write_poll(self):
        """Write a chunk of data from the output buffer to the UART port.
        This takes lower priority than the READ from the UART port.
        It will only send 1 chunk every 0.2 seconds to give the receiving microcontroller
        time to read the data.
        To add lines to the output buffer use the Write() method."""
        if len(self.write_queue) == 0:
            # Nothing to send anyway.
            return
        if self.uart.in_waiting:
            # Input waiting. Handle that first.
            return
        # 0.2:
        if (
            self.last_tx_time is not None
            and (now_utc() - self.last_tx_time).total_seconds()
            < self.write_chunk_seconds
        ):
            return  # Must be 0.2 second gap between each transmitted packet.
        if not self.uart.is_open:
            MctlTxWindow.print("uart.WritePoll: uart is not open!.")
        # Can write the entire line in one go.
        if len(self.write_queue[0]) < self.write_chunk_bytes:
            line = self.write_queue.pop(0)
            terminator = "\n"
        # Need to send just a chunk of the line in this pass.
        else:
            # 1st 'chunksize' characters only.
            line = self.write_queue[0][0 : self.write_chunk_bytes]
            # Remove transmitted characters.
            self.write_queue[0] = self.write_queue[0][self.write_chunk_bytes :]
            terminator = ""
        self.last_line_sent = line  # Keep a note of what we sent, if we receive that back it is reflection indicating a problem.
        line += terminator
        self.lines_sent += 1
        self.bytes_sent += len(line)
        self.uart.write(line.encode("utf-8"))  # Send data in UTF-8 format.
        self.last_tx_time = now_utc()  # Note that time of the last data sent.

    def read_flush(self):
        """Clear the input buffer. Don't actually process them, because you may never reach the end if
        new messages are appearing. Just clear and reset the internal buffer of messages received.
        """
        self.log(
            "microcontroller.ReadFlush: Drop",
            len(self.lines),
            "unprocessed messages received from microcontroller...",
            terminal=False,
        )
        if len(self.lines) > 0:
            for line in self.lines:
                self.log(
                    "microcontroller.ReadFlush: Dropped line:", line, terminal=False
                )
            # Empty the queue.
            self.lines = []
        if len(self.input_line) > 0:
            self.log(
                "microcontroller.ReadFlush: Abandoned partly received input line (",
                self.input_line,
                ")",
                terminal=False,
            )
            # Scrap any line currently being received and constructed.
            self.input_line = ""

    def write_flush(self, send=True):
        """Make sure the output buffer is completely flushed. Timeout after a limited number of attempts.
        This doesn't add anything to the output queue, it just makes sure that everything
        waiting to be sent is transmitted.
        if send parameter is false, the write queue is flushed without sending anything further.
        - Send = True: This routine will trigger WritePoll() directly. Assume that the main sending routine is stopped.
        - Send = False: This routine just flushes."""
        result = True
        # We should try to send outstanding messages.
        if send:
            self.log(
                "WriteFlush: Flushing microcontroller output queue (",
                len(self.write_queue),
                "pending messages will be sent)...",
                terminal=False,
            )
            self.log(
                "WriteFlush: WriteProhibited:", self.write_prohibited, terminal=False
            )
            try_count = 0
            # Don't allow anything further to be added to the queue at the moment.
            self.write_prohibited = True
            while len(self.write_queue) > 0:
                try_count += 1
                self.log(
                    "WriteFlush: Queue currently",
                    len(self.write_queue),
                    "entries",
                    terminal=False,
                )
                self.log(
                    "WriteFlush: 1st in queue:", self.write_queue[0], terminal=False
                )
                # Send next chunk of data from output buffer if allowed.
                self.write_poll()
                # Pause until the CommsLoop thread has cleared the buffer.
                time.sleep(0.1)
                if try_count >= 500:
                    self.log(
                        "WriteFlush: Flush timeout. Maximum loops.",
                        len(self.write_queue),
                        "Remaining messages will be dropped.",
                        terminal=False,
                    )
                    result = False
                    break
            # OK to write again to the write queue.
            self.write_prohibited = False
        else:
            self.log(
                "WriteFlush: Flushing microcontroller output queue (",
                len(self.write_queue),
                "pending messages will be dropped)...",
                terminal=False,
            )
        # Delete any remaining messages in the queue.
        self.write_queue = []
        return result

    def set_led_status(self, status=True):
        """Change status of Microcontroller LEDs.
        This will make the LEDS on the microcontroller itself go dark.
        This reduces light pollution within the telescope dome."""
        self.led_status = status
        if status:
            self.write("leds on")
        else:
            self.write("leds off")

    def mctl_restarted(self):
        """If microcontroller reports a restart, this routine resets the buffers and
        acknowledges the restart back to the microcontroller."""
        # Scrap the contents of the write buffer. We're starting again.
        self.write_flush(send=False)
        # Acknowledge to the microcontroller that we're restarting the conversation too.
        self.write("# Hello controller")
        # Turn on/off the status led on the microcontroller.
        self.set_led_status(self.led_status)

    def write(self, line):
        """Add a new output message to the queue to be processed.
        It is not physically transmitted, it will wait in turn in the
        output queue until WritePoll() gets around to sending it.
        Nothing is added to the queue if self.write_prohibited = True.
        To send text from the output queue to the Microcontroller over the UART line use the WritePoll() method.
        """
        if self.write_prohibited:
            self.log("microcontroller.Write: WriteProhibited: " + line)
        elif len(line) > 0:
            # Was strip()
            line = line.replace("\n", "")
            # Increment the message ID number.
            self.send_id += 1
            if line[-1:] != " ":
                # Need a space separator between fields.
                line += " "
            # Append sequential message ID. microcontroller will respond with this ID when it has received OK.
            line += "[" + str(self.send_id) + "]"
            MctlTxWindow.print(line)
            self.write_queue.append(
                self.add_checksum(line)
            )  # Add to send queue with Checksum.
            self.log(
                "RPi queueing (Q# " + str(len(self.write_queue)) + "): " + line,
                terminal=False,
            )
            if self.print_comms:
                print(
                    TextColor.green(
                        "RPi queueing (Q# " + str(len(self.write_queue)) + "): " + line
                    )
                )

    def mtcl_string_to_datetime(self, string):
        """Convert a microcontroller string to a datetime object."""
        return datetime.strptime(string, "%Y-%m-%d %H:%M:%S")

    def comms_loop(self, command_queue: Queue):  # Runs as own thread.
        """This runs in its own thread, it just continually reads/writes
        to the microcontroller via the uart serial connection.
        It terminates when the main thread dies.
        You can send commands to this communication loop itself via the command_queue queue.
        - Eg : 'stop' to shut down the loop completely."""
        self.log("microcontroller.CommsLoop(): Start", terminal=False)

        prevloop = now_utc()
        # Loop until explicitly told to break.
        while True:
            # Warn if the loop is running slowly.
            tn = now_utc()
            td = (tn - prevloop).total_seconds()
            if td > 1:
                self.log(
                    "microcontroller.CommsLoop(): Loop slow. Took",
                    td,
                    "seconds.",
                    terminal=False,
                )
            prevloop = tn
            # Exchange messages with the microcontroller.
            # Send next chunk of data from output buffer if allowed.
            self.write_poll()
            # Read anything waiting in the input buffer.
            self.read_poll()
            # Check if parent is still alive. Quit if it is nolonger there.
            if not threading.main_thread().is_alive():
                self.log(
                    "microcontroller.CommsLoop(): Parent thread is nolonger alive. Stopping.",
                    level="error",
                )
                break  # Parent thread died, so terminate this thread too.
            # This queue allows the main thread to send commands to the microcontroller comms controller itself.
            if not command_queue.empty():
                received_message = command_queue.get()
                if received_message == "stop":
                    self.log(
                        "microcontroller.CommsLoop(): Received 'stop' command.",
                        terminal=False,
                    )
                    break  # Terminate this loop. Will require restart by main thread.
            time.sleep(0.01)  # Need a tiny pause otherwise this hogs the processor.
        # Flush any outbound comms to the microcontroller before closing.
        self.write_flush(send=True)
        self.log("microcontroller.CommsLoop(): End", terminal=False)

    def start_mctl_comms(self, control_queue: Queue):
        """This runs the microcontroller communications in a separate thread.
        This should keep communication flowing even if the main thread
        is busy with other tasks.
        (Python does not have truly concurrent threads, so it may still pause sometimes.)
        This does not generate or process messages in either direction, it ONLY handles the
        transfer of queued messages between the RPi and Microcontroller via the UART channel.

        To see where the messages are analysed and processed you need to view the Session.mctl_handler method.
        """
        # Communication between the MctlComms thread and the main thread is through the UartControlQueue.
        self.comms_loop(control_queue)
