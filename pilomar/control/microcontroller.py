#!/usr/bin/env python3
"""Microcontroller communication for Pilomar telescope.

This module provides the Microcontroller class for managing UART
communication with the motor microcontroller.
"""

import os
import threading
import time
from queue import Queue

from pilomar.core.base import AttributeMaster


class Microcontroller(AttributeMaster):
    """Manage UART communication between RPi and motor microcontroller.

    Handles I/O and buffering of inbound/outbound messages over UART.
    Also represents the entire motorcontroller PCB.
    """

    def __init__(
        self,
        port="/dev/serial0",
        reset_pin=4,
        board_type=None,
        comms_timeout=120,
        rx_queue_limit=50,
        output_pin_factory=None,
        now_func=None,
        logger=None,
    ):
        """Initialize microcontroller communication.

        Args:
            port: Serial port device path.
            reset_pin: GPIO pin for reset/power control.
            board_type: Specific board type identifier.
            comms_timeout: Seconds before resetting on no communication.
            rx_queue_limit: Maximum messages in receive queue.
            output_pin_factory: Factory for creating GPIO output pins.
            now_func: Function returning current UTC datetime.
            logger: Optional logger instance.
        """
        super().__init__(now_func=now_func)
        self.set_logger(logger)
        self._output_pin_factory = output_pin_factory

        self.board_type = board_type
        self.port = port
        self.comms_timeout = comms_timeout
        self.rx_queue_limit = rx_queue_limit

        # Initialize serial if available
        self.uart = None
        self._init_serial()

        # Communication queues
        self.queue_to_mctl = Queue()
        self.queue_from_mctl = Queue()

        # Reset pin control
        self.reset_bcm = reset_pin
        self.reset_pin = None
        if output_pin_factory:
            self.reset_pin = output_pin_factory(reset_pin, "MctlReset")

        # Receive buffer
        self.lines = []
        self.input_line = ""

        # Transmit buffer
        self.write_queue = []
        self.write_chunk_bytes = 32
        self.write_chunk_seconds = 0.2

        # Statistics
        self.lines_received = 0
        self.lines_sent = 0
        self.bytes_received = 0
        self.bytes_sent = 0
        self.rx_errors = 0

        # State tracking
        self.print_comms = False
        self.led_status = True
        self.line_opened_time = self._now_func()
        self.last_tx_time = self._now_func()
        self.last_rx_time = self._now_func()
        self.last_line_sent = None

        # Restart tracking
        self.forced_restarts = 0
        self.remote_restarts = 0
        self.reset_attempts = 0

        # Power handling
        self.powered_by_usb = False
        self.device_failure = False
        self.write_prohibited = False

        # Message tracking
        self.send_id = 0

        # Microcontroller reported values
        self.reported_reset_reason = "UNKNOWN"
        self.reported_clockspeed = 0
        self.reported_voltage = 0
        self.reported_mem_alloc = 0
        self.reported_mem_free = 0
        self.reported_temperature = 0.0
        self.reported_features = []

    def _init_serial(self):
        """Initialize serial communication."""
        try:
            import serial  # pylint: disable=import-outside-toplevel

            if os.path.exists(self.port):
                self.uart = serial.Serial(self.port, 115200, timeout=0, exclusive=True)
                self.log("Microcontroller: Serial port opened:", self.port, terminal=False)
            else:
                self.log(
                    "Microcontroller: Serial port not found:",
                    self.port,
                    level="warning",
                )
        except ImportError:
            self.log("Microcontroller: pyserial not available", level="warning")
        except Exception as e:  # pylint: disable=broad-except
            self.log("Microcontroller: Serial init failed:", str(e), level="error")

    def initiate(self):
        """Initiate communication with microcontroller."""
        if not self.uart:
            self.log("Microcontroller.initiate: No serial connection", level="error")
            return

        self.log("Microcontroller: Initiating communication...", terminal=False)
        self.reset(planned=True)
        self.uart.reset_input_buffer()
        self.uart.reset_output_buffer()

        # Flush with comments
        for _ in range(2):
            self.write("#" * 20)

        self.write("rpi started")
        self.set_clock()

    def set_clock(self):
        """Set the microcontroller clock."""
        timestamp = self._clean_datetime_string(str(self._now_func()))
        line = "set time " + timestamp
        self.write(line)
        self.log("Microcontroller.set_clock: Setting time to", line, terminal=False)

    def _clean_datetime_string(self, line):
        """Clean a datetime string for transmission.

        Args:
            line: The datetime string.

        Returns:
            Cleaned string with only digits.
        """
        result = ""
        for char in line:
            if char.isdigit():
                result += char
        return result[:14]  # YYYYMMDDHHmmss

    def calculate_checksum(self, line):
        """Calculate checksum for a line of text.

        Args:
            line: The text line.

        Returns:
            Checksum string.
        """
        a = 0
        for i, char in enumerate(line):
            if i % 2 == 0:
                a += ord(char)
            else:
                a += ord(char) * 3
        return hex(a % 65536)[2:]

    def add_checksum(self, line):
        """Add checksum to line for transmission.

        Args:
            line: The text line.

        Returns:
            Line with appended checksum.
        """
        return line + "|" + self.calculate_checksum(line)

    def remove_checksum(self, line):
        """Remove checksum from received line.

        Args:
            line: The received line.

        Returns:
            Line without checksum.
        """
        i = line.rfind("|")
        if i >= 0:
            return line[:i]
        return line

    def validate_checksum(self, line):
        """Validate a line's checksum.

        Args:
            line: The line with checksum.

        Returns:
            True if checksum is valid.
        """
        i = line.rfind("|")
        if i >= 0:
            cs = line[i + 1 :]
            text = line[:i]
            return cs == self.calculate_checksum(text)
        return False

    def reset(self, planned=False):
        """Reset the microcontroller.

        Args:
            planned: True if this is a planned reset.

        Returns:
            True if reset successful.
        """
        if not planned:
            self.reset_attempts += 1
            if self.reset_attempts > 10:
                self.log(
                    "Microcontroller: After",
                    self.reset_attempts,
                    "attempts, considering device failed.",
                    level="error",
                )
                self.device_failure = True
                return False

        if self.reset_pin:
            self.log("Microcontroller.reset: Cycling power pin", terminal=False)
            self.reset_pin.Off()
            time.sleep(1)
            self.reset_pin.On()
            time.sleep(1)
        else:
            # Software reset
            self.write("reset")

        # Reset buffers
        if self.uart:
            self.uart.reset_output_buffer()
            self.uart.reset_input_buffer()

        self.lines = []
        self.input_line = ""
        self.write_queue = []
        self.line_opened_time = self._now_func()
        self.last_tx_time = self._now_func()
        self.last_rx_time = self._now_func()
        self.last_line_sent = None

        # Reset counters
        self.lines_received = 0
        self.lines_sent = 0
        self.bytes_received = 0
        self.bytes_sent = 0
        self.rx_errors = 0
        self.forced_restarts += 1
        self.write_prohibited = False

        return True

    def rx_age(self):
        """Get seconds since last received message.

        Returns:
            Seconds since last receive.
        """
        return int((self._now_func() - self.last_rx_time).total_seconds())

    def read_poll(self):
        """Read waiting characters into input queue."""
        if not self.uart or not self.uart.is_open:
            return

        # Check for stalled communications
        if self.rx_age() > self.comms_timeout:
            self.log(
                "Microcontroller: No data for",
                self.rx_age(),
                "seconds. Resetting.",
                level="error",
            )
            self.reset()
            return

        while self.uart.in_waiting:
            try:
                response = self.uart.read(1).decode("utf-8")
                self.bytes_received += 1
            except Exception as e:  # pylint: disable=broad-except
                self.log("Microcontroller.read_poll: Read failed:", str(e), terminal=False)
                response = ""

            if response == "\n":
                if self.input_line != self.last_line_sent:
                    self.lines.append(self.input_line)
                    self.last_rx_time = self._now_func()
                    self.reset_attempts = 0
                    self.lines_received += 1

                    # Limit queue size
                    while len(self.lines) > self.rx_queue_limit:
                        self.lines.pop(0)

                self.input_line = ""
            else:
                self.input_line += response

    def read(self):
        """Return next validated input line.

        Returns:
            The next line, or empty string.
        """
        result = ""
        while not result and self.lines:
            result = self.lines.pop(0).strip()

            if self.validate_checksum(result):
                result = self.remove_checksum(result)
                self.log("RPi received:", result, terminal=False)

                if result in ["pico started", "controller started"]:
                    self.remote_restarts += 1
            else:
                self.log("RPi rejected checksum:", result, terminal=False)
                self.rx_errors += 1
                result = ""

            # Ignore comments
            if result.startswith("#"):
                result = ""

        return result

    def write_poll(self):
        """Write chunk of data from output buffer."""
        if not self.write_queue:
            return

        if self.uart and self.uart.in_waiting:
            return  # Handle input first

        if (self._now_func() - self.last_tx_time).total_seconds() < self.write_chunk_seconds:
            return  # Wait between transmissions

        if not self.uart or not self.uart.is_open:
            return

        if len(self.write_queue[0]) < self.write_chunk_bytes:
            line = self.write_queue.pop(0)
            terminator = "\n"
        else:
            line = self.write_queue[0][: self.write_chunk_bytes]
            self.write_queue[0] = self.write_queue[0][self.write_chunk_bytes :]
            terminator = ""

        self.last_line_sent = line
        line += terminator
        self.lines_sent += 1
        self.bytes_sent += len(line)

        self.uart.write(line.encode("utf-8"))
        self.last_tx_time = self._now_func()

    def write(self, line):
        """Add message to output queue.

        Args:
            line: The message to send.
        """
        if self.write_prohibited:
            self.log("Microcontroller.write: WriteProhibited:", line)
            return

        if not line:
            return

        line = line.replace("\n", "")
        self.send_id += 1

        if line[-1:] != " ":
            line += " "
        line += f"[{self.send_id}]"

        self.write_queue.append(self.add_checksum(line))
        self.log("RPi queueing (Q#", len(self.write_queue), "):", line, terminal=False)

    def write_flush(self, send=True):
        """Flush output buffer.

        Args:
            send: If True, send remaining messages.

        Returns:
            True if flush completed.
        """
        if send:
            self.log(
                "Microcontroller.write_flush:",
                len(self.write_queue),
                "messages to send",
                terminal=False,
            )
            self.write_prohibited = True

            try_count = 0
            while self.write_queue:
                try_count += 1
                self.write_poll()
                time.sleep(0.1)

                if try_count >= 500:
                    self.log("Microcontroller.write_flush: Timeout", level="warning")
                    break

            self.write_prohibited = False
        else:
            self.log(
                "Microcontroller.write_flush: Dropping",
                len(self.write_queue),
                "messages",
                terminal=False,
            )

        self.write_queue = []
        return True

    def set_led_status(self, status=True):
        """Set microcontroller LED status.

        Args:
            status: True to enable LEDs.
        """
        self.led_status = status
        self.write("leds on" if status else "leds off")

    def comms_loop(self, command_queue):
        """Main communication loop (runs in separate thread).

        Args:
            command_queue: Queue for receiving commands (e.g., 'stop').
        """
        self.log("Microcontroller.comms_loop: Start", terminal=False)

        while True:
            self.write_poll()
            self.read_poll()

            if not threading.main_thread().is_alive():
                self.log("Microcontroller.comms_loop: Parent died, stopping", level="error")
                break

            if not command_queue.empty():
                msg = command_queue.get()
                if msg == "stop":
                    self.log("Microcontroller.comms_loop: Received stop", terminal=False)
                    break

            time.sleep(0.01)

        self.write_flush(send=True)
        self.log("Microcontroller.comms_loop: End", terminal=False)
