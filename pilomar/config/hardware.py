#!/usr/bin/env python3
"""Hardware detection and configuration for Pilomar.

This module provides the Hardware class that detects and configures
hardware-specific settings for Raspberry Pi and PCB combinations.
"""

import sys
import os

from pilomar.core.base import AttributeMaster


class Hardware(AttributeMaster):
    """Class defining the hardware configuration.
    
    Detects Raspberry Pi model, operating system, PCB revision,
    and configures appropriate camera drivers.
    """
    
    # Operating systems that came with raspistill for camera support
    RASPISTILL_SYSTEMS = ['wheezy', 'jessie', 'stretch', 'buster']
    
    # Supported hardware/OS combinations
    SUPPORTED_SYSTEMS = [
        '3/buster/32',
        '4/buster/32', 
        '4/bookworm/64',
        'CM4/bookworm/64',
        '5/bookworm/64'
    ]

    def __init__(self, os_cmd, input_pin_factory=None, logger=None):
        """Create new instance of the hardware and initialize values.
        
        Args:
            os_cmd: Handle to oscommand.Execute method for running shell commands.
            input_pin_factory: Factory function for creating GPIO input pins.
            logger: Handle to a logfile instance.
        """
        self.set_logger(logger)
        self.os_cmd = os_cmd
        self._input_pin_factory = input_pin_factory
        
        # Initialize hardware detection
        self.set_program_title()
        self.set_rpi_model()
        self.set_os_version()
        self.native_camera_driver()
        
        # PCB identification (requires GPIO)
        self.pcb_mctl_family = "tiny"  # Default
        self.pcb_protect_usb = True  # Default
        self.pcb_revision = 0  # Default
        
        self.Log("Hardware.__init__(): RPi: Model:", self.rpi_model,
                 "Num:", self.rpi_num,
                 "OStype:", self.os_type,
                 "OSid:", self.os_version_id, 
                 "OSname:", self.os_version_name,
                 "OSbits:", self.os_bits,
                 "OSproc:", self.os_proc,
                 "SysKey:", self.os_systemkey, terminal=False)

    def identify_pcb(self, autodetect=True):
        """Check the GPIO pins that identify the PCB capabilities.
        
        There are currently 2 GPIO pins allocated for identifying the PCB capabilities.
        This allows up to 4 different PCBs to be detected.
        
        GPIO 22 (pin 13): LOW = Raspberry Pi PICO, HIGH = Pimoroni Tiny
        GPIO 27 (pin 15): LOW = Protected from USB conflicts, HIGH = Not protected
        
        Args:
            autodetect: When True, checks the jumper pins to identify the board.
                       When False, assumes an original (gen 0) board.
        """
        self.tiny_flag_pin = 22
        self.usb_protect_flag_pin = 27
        self.pcb_revision = 0
        
        if autodetect and self._input_pin_factory:
            self.Log("Hardware.identify_pcb(): Begin. TinyFlagPin",
                    self.tiny_flag_pin, "UsbProtectFlagPin", 
                    self.usb_protect_flag_pin, terminal=False)
            
            # Check microcontroller type
            tfp = self._input_pin_factory(self.tiny_flag_pin, "TinyFlag", pull='up')
            if tfp.IsHigh():
                self.pcb_mctl_family = "tiny"
            else:
                self.pcb_mctl_family = "pico"
            
            # Check USB protection
            upfp = self._input_pin_factory(self.usb_protect_flag_pin, "UsbProtectFlag", pull='up')
            if upfp.IsHigh():
                self.pcb_protect_usb = True
            else:
                self.pcb_protect_usb = False
            
            # Determine PCB revision
            if self.pcb_protect_usb and self.pcb_mctl_family == 'tiny':
                self.pcb_revision = 0  # Original PCB
            elif not self.pcb_protect_usb and self.pcb_mctl_family == 'pico':
                self.pcb_revision = 1  # 1st revision
            else:
                self.pcb_revision = 4  # Unknown
        else:
            self.Log("Hardware.identify_pcb(): Skipped (no GPIO or autodetect=False)", terminal=False)
            self.pcb_mctl_family = "tiny"
            self.pcb_protect_usb = True
            
        self.Log("Hardware.identify_pcb(): Family", self.pcb_mctl_family,
                "UsbProtect", self.pcb_protect_usb,
                "pcb revision", self.pcb_revision, terminal=False)

    def set_program_title(self):
        """Establish the program title from the source code name."""
        self.program_title = sys.argv[0].split('/')[-1].split('.')[0].lower()

    def set_rpi_model(self):
        """Establish the model of Raspberry Pi computer."""
        lines = self.os_cmd('cat /sys/firmware/devicetree/base/model')
        rpimodel = 'Raspberry Pi'
        for line in lines:
            if len(line) > 0:
                rpimodel = line
                
        rpimodel = rpimodel.replace('Raspberry Pi ', 'RPi ')
        rpimodel = rpimodel.replace('Compute Module ', 'CM')
        rpimodel = rpimodel.replace('Model ', '')
        rpimodel = rpimodel.replace('Rev ', '')
        
        # Remove non-printing characters
        temp = ''
        for char in rpimodel:
            if char >= ' ':
                temp += char
        self.rpi_model = temp
        
        rm_list = self.rpi_model.split(' ')
        if len(rm_list) > 1:
            self.rpi_num = rm_list[1]
        else:
            self.rpi_num = 'unknown'
            
        if len(rm_list) > 1:
            self.rpi_rev = rm_list[-1]
        else:
            self.rpi_rev = 'unknown'

    def set_os_version(self):
        """Establish the version of operating system.
        
        Sets:
            os_version_id: e.g., 12
            os_version_name: e.g., 'bookworm'
            os_type: e.g., 'debian'
            os_bits: e.g., 64
            os_proc: e.g., 'aarch64'
            os_systemkey: e.g., '4/bookworm/64'
        """
        self.os_version_id = None
        self.os_version_name = None
        self.os_type = None
        
        for line in self.os_cmd('cat /etc/os-release'):
            if len(line) > 0:
                elements = line.split('=')
                if elements[0] == 'VERSION_ID':
                    self.os_version_id = int(elements[1].replace('"', ''))
                elif elements[0] == 'VERSION_CODENAME':
                    self.os_version_name = elements[1]
                elif elements[0] == 'ID':
                    self.os_type = elements[1]
                    
        bits_result = self.os_cmd('getconf LONG_BIT')
        self.os_bits = int(bits_result[0]) if bits_result else 64
        
        proc_result = self.os_cmd('uname -m')
        self.os_proc = proc_result[0] if proc_result else 'unknown'
        
        self.os_systemkey = f"{self.rpi_num}/{self.os_version_name}/{self.os_bits}"

    def native_camera_driver(self):
        """Choose the native camera driver expected for this hardware/OS combination.
        
        Sets: self.camera_driver
        """
        if self.os_version_name in Hardware.RASPISTILL_SYSTEMS:
            self.camera_driver = 'raspistill'
        else:
            self.camera_driver = 'libcamera'
        self.Log(self.os_version_name, "O/S found, assuming camera driver is",
                self.camera_driver, terminal=False)

    def i2c_enabled(self):
        """Return True if i2c is enabled."""
        # This would need os_cmd_code function for return code check
        # For now, assume not enabled in non-RPi environments
        return False

    def spi_enabled(self):
        """Return True if SPI is enabled.
        
        Looks for specific SPI kernel modules being loaded.
        """
        lines = self.os_cmd('lsmod')
        for line in lines:
            for entry in ['spi_bcm2708', 'spi_bcm2835']:
                if entry in line:
                    self.Log("Hardware.spi_enabled(): Detected", entry,
                            "kernel module is loaded.", terminal=False)
                    return True
        return False

    def hardware_is_supported(self, allow_fail=True):
        """Return True if the hardware and OS combination is valid.
        
        Args:
            allow_fail: If True, raises exception when hardware is not supported.
                       If False, just returns False.
        
        Returns:
            True if hardware is supported, False otherwise.
            
        Raises:
            Exception: If hardware is not supported and allow_fail is True.
        """
        if self.os_systemkey in Hardware.SUPPORTED_SYSTEMS:
            self.Log(self.program_title, "OK to run under",
                    self.os_systemkey, terminal=False)
            self.system_supported = True
            return True
        else:
            self.Log(self.program_title, "is only designed to run under",
                    Hardware.SUPPORTED_SYSTEMS, level='error', terminal=True)
            self.Log(self.program_title, "is not designed to run under",
                    self.os_version_name, self.os_bits, "bit on",
                    self.rpi_model, "(", self.os_systemkey, ")",
                    level='error', terminal=True)
            self.system_supported = False
            if allow_fail:
                raise Exception(f"{self.program_title} is not designed to run "
                              f"under this combination of hardware and O/S.")
            return False


# Backward compatibility alias
hardware = Hardware
