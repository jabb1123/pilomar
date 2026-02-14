#!/usr/bin/env python3
"""Microcontroller communication for Pilomar telescope.

This module provides the Microcontroller class for managing UART
communication with the motor microcontroller.
"""

import os
import time
import threading
from datetime import datetime
from queue import Queue

from pilomar.core.base import AttributeMaster


class Microcontroller(AttributeMaster):
    """Manage UART communication between RPi and motor microcontroller.
    
    Handles I/O and buffering of inbound/outbound messages over UART.
    Also represents the entire motorcontroller PCB.
    """

    def __init__(
        self,
        port='/dev/serial0',
        reset_pin=4,
        board_type=None,
        comms_timeout=120,
        rx_queue_limit=50,
        output_pin_factory=None,
        now_func=None,
        logger=None
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
        self.set_logger(logger)
        self._now_func = now_func or (lambda: datetime.utcnow())
        self._output_pin_factory = output_pin_factory
        
        self.BoardType = board_type
        self.Port = port
        self.CommsTimeout = comms_timeout
        self.RxQueueLimit = rx_queue_limit
        
        # Initialize serial if available
        self.uart = None
        self._init_serial()
        
        # Communication queues
        self.QueueToMctl = Queue()
        self.QueueFromMctl = Queue()
        
        # Reset pin control
        self.ResetBCM = reset_pin
        self.ResetPin = None
        if output_pin_factory:
            self.ResetPin = output_pin_factory(reset_pin, "MctlReset")
        
        # Receive buffer
        self.Lines = []
        self.InputLine = ''
        
        # Transmit buffer
        self.WriteQueue = []
        self.WriteChunkBytes = 32
        self.WriteChunkSeconds = 0.2
        
        # Statistics
        self.LinesReceived = 0
        self.LinesSent = 0
        self.BytesReceived = 0
        self.BytesSent = 0
        self.RxErrors = 0
        
        # State tracking
        self.PrintComms = False
        self.LedStatus = True
        self.LineOpenedTime = self._now_func()
        self.LastTxTime = self._now_func()
        self.LastRxTime = self._now_func()
        self.LastLineSent = None
        
        # Restart tracking
        self.ForcedRestarts = 0
        self.RemoteRestarts = 0
        self.ResetAttempts = 0
        
        # Power handling
        self.PoweredByUsb = False
        self.DeviceFailure = False
        self.WriteProhibited = False
        
        # Message tracking
        self.SendId = 0
        
        # Microcontroller reported values
        self.ReportedResetReason = 'UNKNOWN'
        self.ReportedClockspeed = 0
        self.ReportedVoltage = 0
        self.ReportedMemAlloc = 0
        self.ReportedMemFree = 0
        self.ReportedTemperature = 0.0
        self.ReportedFeatures = []

    def _init_serial(self):
        """Initialize serial communication."""
        try:
            import serial
            if os.path.exists(self.Port):
                self.uart = serial.Serial(
                    self.Port, 115200, timeout=0, exclusive=True
                )
                self.Log("Microcontroller: Serial port opened:", self.Port,
                        terminal=False)
            else:
                self.Log("Microcontroller: Serial port not found:", self.Port,
                        level='warning')
        except ImportError:
            self.Log("Microcontroller: pyserial not available", level='warning')
        except Exception as e:
            self.Log("Microcontroller: Serial init failed:", str(e), level='error')

    def initiate(self):
        """Initiate communication with microcontroller."""
        if not self.uart:
            self.Log("Microcontroller.initiate: No serial connection", level='error')
            return
        
        self.Log('Microcontroller: Initiating communication...', terminal=False)
        self.reset(planned=True)
        self.uart.reset_input_buffer()
        self.uart.reset_output_buffer()
        
        # Flush with comments
        for _ in range(2):
            self.write('#' * 20)
        
        self.write('rpi started')
        self.set_clock()

    def set_clock(self):
        """Set the microcontroller clock."""
        timestamp = self._clean_datetime_string(str(self._now_func()))
        line = 'set time ' + timestamp
        self.write(line)
        self.Log("Microcontroller.set_clock: Setting time to", line, terminal=False)

    def _clean_datetime_string(self, line):
        """Clean a datetime string for transmission.
        
        Args:
            line: The datetime string.
            
        Returns:
            Cleaned string with only digits.
        """
        result = ''
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
        return line + '|' + self.calculate_checksum(line)

    def remove_checksum(self, line):
        """Remove checksum from received line.
        
        Args:
            line: The received line.
            
        Returns:
            Line without checksum.
        """
        i = line.rfind('|')
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
        i = line.rfind('|')
        if i >= 0:
            cs = line[i + 1:]
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
            self.ResetAttempts += 1
            if self.ResetAttempts > 10:
                self.Log('Microcontroller: After', self.ResetAttempts,
                        'attempts, considering device failed.', level='error')
                self.DeviceFailure = True
                return False
        
        if self.ResetPin:
            self.Log("Microcontroller.reset: Cycling power pin", terminal=False)
            self.ResetPin.Off()
            time.sleep(1)
            self.ResetPin.On()
            time.sleep(1)
        else:
            # Software reset
            self.write('reset')
        
        # Reset buffers
        if self.uart:
            self.uart.reset_output_buffer()
            self.uart.reset_input_buffer()
        
        self.Lines = []
        self.InputLine = ''
        self.WriteQueue = []
        self.LineOpenedTime = self._now_func()
        self.LastTxTime = self._now_func()
        self.LastRxTime = self._now_func()
        self.LastLineSent = None
        
        # Reset counters
        self.LinesReceived = 0
        self.LinesSent = 0
        self.BytesReceived = 0
        self.BytesSent = 0
        self.RxErrors = 0
        self.ForcedRestarts += 1
        self.WriteProhibited = False
        
        return True

    def rx_age(self):
        """Get seconds since last received message.
        
        Returns:
            Seconds since last receive.
        """
        return int((self._now_func() - self.LastRxTime).total_seconds())

    def read_poll(self):
        """Read waiting characters into input queue."""
        if not self.uart or not self.uart.is_open:
            return
        
        # Check for stalled communications
        if self.rx_age() > self.CommsTimeout:
            self.Log('Microcontroller: No data for', self.rx_age(),
                    'seconds. Resetting.', level='error')
            self.reset()
            return
        
        while self.uart.in_waiting:
            try:
                response = self.uart.read(1).decode('utf-8')
                self.BytesReceived += 1
            except Exception as e:
                self.Log('Microcontroller.read_poll: Read failed:', str(e),
                        terminal=False)
                response = ''
            
            if response == '\n':
                if self.InputLine != self.LastLineSent:
                    self.Lines.append(self.InputLine)
                    self.LastRxTime = self._now_func()
                    self.ResetAttempts = 0
                    self.LinesReceived += 1
                    
                    # Limit queue size
                    while len(self.Lines) > self.RxQueueLimit:
                        self.Lines.pop(0)
                
                self.InputLine = ''
            else:
                self.InputLine += response

    def read(self):
        """Return next validated input line.
        
        Returns:
            The next line, or empty string.
        """
        result = ''
        while not result and self.Lines:
            result = self.Lines.pop(0).strip()
            
            if self.validate_checksum(result):
                result = self.remove_checksum(result)
                self.Log('RPi received:', result, terminal=False)
                
                if result in ['pico started', 'controller started']:
                    self.RemoteRestarts += 1
            else:
                self.Log('RPi rejected checksum:', result, terminal=False)
                self.RxErrors += 1
                result = ''
            
            # Ignore comments
            if result.startswith('#'):
                result = ''
        
        return result

    def write_poll(self):
        """Write chunk of data from output buffer."""
        if not self.WriteQueue:
            return
        
        if self.uart and self.uart.in_waiting:
            return  # Handle input first
        
        if (self._now_func() - self.LastTxTime).total_seconds() < self.WriteChunkSeconds:
            return  # Wait between transmissions
        
        if not self.uart or not self.uart.is_open:
            return
        
        if len(self.WriteQueue[0]) < self.WriteChunkBytes:
            line = self.WriteQueue.pop(0)
            terminator = '\n'
        else:
            line = self.WriteQueue[0][:self.WriteChunkBytes]
            self.WriteQueue[0] = self.WriteQueue[0][self.WriteChunkBytes:]
            terminator = ''
        
        self.LastLineSent = line
        line += terminator
        self.LinesSent += 1
        self.BytesSent += len(line)
        
        self.uart.write(line.encode('utf-8'))
        self.LastTxTime = self._now_func()

    def write(self, line):
        """Add message to output queue.
        
        Args:
            line: The message to send.
        """
        if self.WriteProhibited:
            self.Log('Microcontroller.write: WriteProhibited:', line)
            return
        
        if not line:
            return
        
        line = line.replace('\n', '')
        self.SendId += 1
        
        if line[-1:] != ' ':
            line += ' '
        line += f'[{self.SendId}]'
        
        self.WriteQueue.append(self.add_checksum(line))
        self.Log('RPi queueing (Q#', len(self.WriteQueue), '):', line, terminal=False)

    def write_flush(self, send=True):
        """Flush output buffer.
        
        Args:
            send: If True, send remaining messages.
            
        Returns:
            True if flush completed.
        """
        if send:
            self.Log('Microcontroller.write_flush:', len(self.WriteQueue),
                    'messages to send', terminal=False)
            self.WriteProhibited = True
            
            try_count = 0
            while self.WriteQueue:
                try_count += 1
                self.write_poll()
                time.sleep(0.1)
                
                if try_count >= 500:
                    self.Log('Microcontroller.write_flush: Timeout', level='warning')
                    break
            
            self.WriteProhibited = False
        else:
            self.Log('Microcontroller.write_flush: Dropping',
                    len(self.WriteQueue), 'messages', terminal=False)
        
        self.WriteQueue = []
        return True

    def set_led_status(self, status=True):
        """Set microcontroller LED status.
        
        Args:
            status: True to enable LEDs.
        """
        self.LedStatus = status
        self.write('leds on' if status else 'leds off')

    def comms_loop(self, command_queue):
        """Main communication loop (runs in separate thread).
        
        Args:
            command_queue: Queue for receiving commands (e.g., 'stop').
        """
        self.Log('Microcontroller.comms_loop: Start', terminal=False)
        
        while True:
            self.write_poll()
            self.read_poll()
            
            if not threading.main_thread().is_alive():
                self.Log("Microcontroller.comms_loop: Parent died, stopping",
                        level='error')
                break
            
            if not command_queue.empty():
                msg = command_queue.get()
                if msg == "stop":
                    self.Log("Microcontroller.comms_loop: Received stop",
                            terminal=False)
                    break
            
            time.sleep(0.01)
        
        self.write_flush(send=True)
        self.Log('Microcontroller.comms_loop: End', terminal=False)


# Backward compatibility alias  
microcontroller = Microcontroller
