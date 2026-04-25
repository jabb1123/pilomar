"""Hardware interface modules for camera and GPIO."""

try:
    from .camera import AstroCamera, AstroLens, AstroSensor, CameraUtil
except ImportError:
    pass

try:
    from .gpio import InputPinGpio, InputPinGpiod, OutputPinGpio, OutputPinGpiod
except ImportError:
    pass

__all__ = [
    "AstroLens",
    "AstroSensor",
    "AstroCamera",
    "CameraUtil",
    "InputPinGpio",
    "OutputPinGpio",
    "InputPinGpiod",
    "OutputPinGpiod",
]
