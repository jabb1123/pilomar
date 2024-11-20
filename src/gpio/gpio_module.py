#!/usr/bin/python

# Raspberry Pi GPIO library.
# Presents an interface to the GPIO handlers on the Raspberry Pi SBCs.
# - Different classes can be built to handle different GPIO handlers,
#   but all should present the same interface to the calling programs.

# This software is published under the GNU General Public License v3.0.
# Also respect any pre-existing terms of any components that this incorporates.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

GPIO_DRIVER = None
try:
    import RPi.GPIO as GPIO  # Handling IO signals. If available.

    GPIO.setmode(GPIO.BCM)
except ModuleNotFoundError:
    pass


def cleanup_gpio():
    """Perform cleanup at end of session."""
    GPIO.cleanup()


class InputPinGPIO:
    """Wrapper for GPIO input pin.
    Allows different GPIO libraries to be implemented by hiding the actual implementation behind these methods.
    Pin can be declared as None in which case it's a non-functional device."""

    InputPins = []  # List of all defined input pins.
    __library__ = "RPi.GPIO"  # Which GPIO library does this support?
    __version__ = "0.0.0"  # What version of the library is this?

    def __init__(self, pinbcm, name=None, pull="up", enabled=True, invert=False):
        """Define a GPIO input pin.

        The purpose is to present a common interface to an I/O pin regardless of the underlying
        GPIO package being used. You can create alternative classes which interact with different
        packages and present the same interface to the program.

        pinbcm = the BCM pin number.
        name is an optional name for the pin.
        pull = GPIO.PUD_UP for pull up (default HIGH/ON),
             GPIO.PUD_DOWN for pull down. (default LOW/OFF)
        enabled = initial enabled(True)/disabled(False) state of the pin.
        invert = False: is_on returns TRUE for HIGH signal.
                is_off returns TRUE for a LOW signal.
             True:  is_on returns TRUE for LOW signal.
                is_off returns TRUE for a HIGH signal.

        if pinbcm is None then this is a fake input.
        it behaves as a GPIO input, but doesn't actually link to a GPIO port and always returns the PULL UP/DOWN value.
        """
        self.pin = pinbcm  # The BCM number of the pin.
        self.name = name  # A reference name of the pin.
        self.pull = pull.lower()  # Is this a PULL_UP or PULL_DOWN input.
        self.invert = invert  # is_on/is_off methods invert their value. is_high/is_low remain unchanged.
        if self.pin is not None:
            self.enabled = enabled
        else:
            self.enabled = False  # Dummy pins are always disabled.
        # Set the PULL UP / DOWN config for the input.
        if pull == "up":
            self.state = True  # Initial state HIGH.
        else:
            self.state = False  # Initial state LOW.
        # If it's a real pin, set it up through GPIO.
        if self.pin is not None:
            if self.pull == "up":
                GPIO.setup(
                    self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP
                )  # Will EARTH when triggered.
            else:
                GPIO.setup(
                    self.pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN
                )  # Will go HIGH when triggered.
        # Append to the global list of all input pins.
        InputPinGPIO.InputPins.append(self)  # Add to list of input pins.

    def refresh(self):
        """Get and store the current state of the pin.
        GPIO.input() returns 0 = Low, 1 = High.
        Convert to 0 = False, 1 = True
        DISABLED pins always return False (electrical LOW).
        If you want the logical state of the pin after this use is_on() and is_off() methods.
        If you want the physical state of the pin after this use is_high() and is_low() methods.
        """
        if self.enabled and GPIO.input(self.pin) != 0:
            self.state = True  # High
        else:
            self.state = False  # Low

    def is_high(self):
        """Return TRUE if input is HIGH.
        This is the true electrical state of the pin.
        It does NOT respect the self.invert flag, use is_on() for that."""
        self.refresh()  # Get current electrical state of the pin.
        return self.state  # Return True/False.

    def is_low(self):
        """Return TRUE if input is LOW.
        This is the true electrical state of the pin.
        It does NOT respect the self.invert flag, use is_off() for that."""
        self.refresh()  # Get current electrical state of the pin.
        return not self.state  # Return True/False.

    def is_on(self):
        """Return ON/OFF state of the input, respecting the 'invert' flag.
        If you want the true electrical state of the pin use self.is_high()"""
        result = self.is_high()
        if self.invert:
            result = not result
        return result  # Return True/False.

    def is_off(self):
        """Return ON/OFF state of the input, respecting the 'invert' flag.
        If you want the true electrical state of the pin use self.is_low()"""
        result = self.is_low()
        if self.invert:
            result = not result
        return result  # Return True/False.

    def enable(self):
        """Enable the pin and set the output accordingly.
        Can only enable real GPIO pins."""
        if self.pin is not None:
            self.enabled = True  # Can only enable if it's a real pin.
        self.refresh()  # Get current electrical state of the pin.

    def disable(self):
        """Disable the pin and set the state to LOW."""
        self.enabled = False
        self.refresh()  # Get current electrical state of the pin.

    def status(self):
        """Return a string describing the current status of the pin."""
        temp = (
            "GPIO: BCM:"
            + str(self.pin)
            + ", INPUT:"
            + " Ena:"
            + str(self.enabled).rjust(5)
            + " Inv:"
            + str(self.invert).rjust(5)
            + " is_on:"
            + str(self.is_on()).rjust(5)
            + " is_off:"
            + str(self.is_off()).rjust(5)
            + " is_high:"
            + str(self.is_high()).rjust(5)
            + " is_low:"
            + str(self.is_low()).rjust(5)
        )
        return temp


# ---------------------------------------------------------------------------------------------------------------


class OutputPinGPIO:
    """Define a GPIO output pin.

      The purpose is to present a common interface to an I/O pin regardless of the underlying
      GPIO package being used. You can create alternative classes which interact with different
      packages and present the same interface to the program.


    Allows different GPIO libraries to be implemented by hiding the actual implementation behind these methods.
    PIN can be declared as None, in which case it's a non-functional device."""

    OutputPins = []  # List of all defined output pins.
    __library__ = "RPi.GPIO"  # Which GPIO library does this support?
    __version__ = "0.0.0"  # What version of the library is this?

    def __init__(self, pinbcm, name=None, enabled=True, state=False, invert=False):
        """Create a new pin.
        pinbcm is the BCM number of the GPIO pin.
        name is an optional name for the pin.
        enabled = initial enabled/disabled condition of the pin.
        state = initial on(True)/off(False) condition of the pin.
        invert = Switch HIGH/LOW electrical states for the on/off status."""
        self.pin = pinbcm  # The BCM pin number.
        self.name = name  # Reference name for the pin.
        self.state = state  # It's logical on/off state.
        self.invert = invert  # Flips electrical state to be opposite of logical state. LOW=ON, HIGH=OFF.
        # Only real pins can be enabled.
        if self.pin is not None:
            self.enabled = enabled
        else:
            self.enabled = False  # If no real pin, force it to 'disabled'.
        # Only real pins are connected to a GPIO pin.
        if self.pin is not None:
            GPIO.setup(self.pin, GPIO.OUT)
        OutputPinGPIO.OutputPins.append(self)  # Add to list of output pins.
        self.refresh()

    def on(self):
        """Turn on (HIGH) the output pin."""
        self.state = True
        self.refresh()  # Set electrical state of the pin.

    def off(self):
        """Turn off (LOW) the output pin."""
        self.state = False
        self.refresh()  # Set the electrical state of the pin.

    def is_on(self):
        """Return ON/OFF state of the input, respecting the 'invert' flag.
        If you want the true electrical state of the pin use self.is_high()"""
        result = self.is_high()  # Get the current electrical state of the pin.
        if self.invert:
            result = not result  # Consider the Invert flag.
        return result  # REturn True/False for logical state of the pin.

    def is_off(self):
        """Return ON/OFF state of the input, respecting the 'invert' flag.
        If you want the true electrical state of the pin use self.is_low()"""
        result = self.is_low()  # Get the current electrical state of the pin.
        if self.invert:
            result = not result  # Consider the Invert flag.
        return result  # Return True/False for the logical state of the pin.

    def is_high(self):
        """Return TRUE if the pin is HIGH.
        The true electrical state of the pin.
        Does not respect self.invert flag.
        To respect self.invert, use is_on()/is_off()"""
        if GPIO.input(self.pin) != 0:
            result = True  # The true electrical state of the pin.
        else:
            result = False
        return result

    def is_low(self):
        """Return TRUE if the pin is LOW.
        The true electrical state of the pin.
        Does not respect self.invert flag.
        To respect self.invert, use is_on()/is_off()"""
        if GPIO.input(self.pin) != 0:
            result = False  # The true electrical state of the pin.
        else:
            result = True
        return result

    def refresh(self):
        """Set the electrical state of the output pin to match the status and its enabled condition."""
        if self.pin is not None:  # It's a real pin.
            if self.enabled:
                temp = self.state  # Logical state.
                if self.invert:
                    temp = not temp  # Convert to electrical state.
                if temp:
                    GPIO.output(self.pin, GPIO.HIGH)  # Enabled and HIGH.
                else:
                    GPIO.output(self.pin, GPIO.LOW)  # Enabled and LOW.
            else:
                GPIO.output(self.pin, GPIO.LOW)  # Disabled pin should default to LOW.

    def enable(self):
        """Enable the pin, this allows the output to be set HIGH.
        Can only enable REAL pins."""
        if self.pin is not None:
            self.enabled = True  # Only ENABLE if it's a real pin.
        self.refresh()  # Set the current electrical state of the pin.

    def disable(self):
        """Disable the pin, this prevents the output being set HIGH, it is forced LOW."""
        self.enabled = False
        self.refresh()  # Set the current electrical state of the pin.

    def status(self):
        """Return a string describing the current status of the pin."""
        temp = (
            "GPIO: BCM:"
            + str(self.pin)
            + ", OUTPUT:"
            + " Ena:"
            + str(self.enabled).rjust(5)
            + " Inv:"
            + str(self.invert).rjust(5)
            + " is_on:"
            + str(self.is_on()).rjust(5)
            + " is_off:"
            + str(self.is_off()).rjust(5)
            + " is_high:"
            + str(self.is_high()).rjust(5)
            + " is_low:"
            + str(self.is_low()).rjust(5)
        )
        return temp
