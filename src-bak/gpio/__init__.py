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
    import gpiod as gpio_driver  # Handling IO signals. If available.
    import gpiod_module
    from gpiod_module import InputPinGPIO
    from gpiod_module import OutputPinGPIO
    from gpiod_module import cleanup_gpio

    GPIO_DRIVER = "GPIOD"
except ModuleNotFoundError:
    print("No GPIO driver available.")

try:
    import RPi.GPIO as gpio_driver  # Handling IO signals. If available.
    import gpio_module
    from gpio_module import InputPinGPIO
    from gpio_module import OutputPinGPIO
    from gpio_module import cleanup_gpio

    GPIO_DRIVER = "GPIO"
except ModuleNotFoundError:
    pass


class GPIOPull(Enum):
    """
    The pull of the GPIO pin
    """

    PULLUP = 1
    PULLDOWN = 0
