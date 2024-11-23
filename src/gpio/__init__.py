"""
This module is used to handle GPIO signals. It is used to read and write to GPIO pins. 

To use this module easily, the following code is recommended:

```python
from gpio import *
```

This will import the correct GPIO driver for the system. If no GPIO driver is available,
the module will not be imported.
"""

from enum import Enum

GPIO_DRIVER = None

try:
    import RPi.GPIO as gpio_driver  # Handling IO signals. If available.
    import gpio_module

    InputPinGPIO = gpio_module.InputPinGPIO
    OutputPinGPIO = gpio_module.OutputPinGPIO
    cleanup_gpio = gpio_module.cleanup_gpio

    GPIO_DRIVER = "GPIO"
except ModuleNotFoundError:
    pass

try:
    import gpiod as gpio_driver  # Handling IO signals. If available.
    import gpiod_module

    InputPinGPIO = gpiod_module.InputPinGPIO
    OutputPinGPIO = gpiod_module.OutputPinGPIO
    cleanup_gpio = gpiod_module.cleanup_gpio

    GPIO_DRIVER = "GPIOD"
except ModuleNotFoundError:
    print("No GPIO driver available.")


class GPIOPull(Enum):
    """
    The pull of the GPIO pin
    """

    PULLUP = 1
    PULLDOWN = 0
