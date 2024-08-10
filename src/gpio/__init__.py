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
  import RPi.GPIO as GPIO  # Handling IO signals. If available.
  from gpio_module import *
  GPIO_DRIVER = "GPIO"
except ModuleNotFoundError:
  pass

try:
  import gpio.gpiod as gpiod  # Handling IO signals. If available.
  from gpiod_module import *
  GPIO_DRIVER = "GPIOD"
except ModuleNotFoundError:
  print("No GPIO driver available.")


class GPIOPull(Enum):
  """
  The pull of the GPIO pin
  """
  PULLUP = 1
  PULLDOWN = 0
