"""
This module provides a class to control a Nema 17 stepper motor
"""
from RpiMotorLib import RpiMotorLib
import RPi.GPIO as GPIO
from enum import Enum

from gpio import OutputPinGPIO

class MotorResolution(Enum):
  """
  The resolution of the motor
  """
  FULL_STEP = 'Full'
  HALF_STEP = 'Half'
  QUARTER_STEP = '1/4'
  EIGHTH_STEP = '1/8'
  SIXTEENTH_STEP = '1/16'
  THIRTYSECOND_STEP = '1/32'

class MotorDirection(Enum):
  """
  The direction of the motor
  """
  FORWARD = 1
  BACKWARD = 0

class MotorNema17:
  """
  A class to control a Nema 17 stepper motor
  
  :param motor_name: The name of the motor
  :type motor_name: str
  :param dir_pin: The direction pin of the motor
  :type dir_pin: int
  :param step_pin: The step pin of the motor
  :type step_pin: int
  :param enable_pin: The enable pin of the motor
  :type enable_pin: int
  :param m0_pin: The M0 pin of the motor
  :type m0_pin: int
  :param m1_pin: The M1 pin of the motor
  :type m1_pin: int
  :param m2_pin: The M2 pin of the motor
  :type m2_pin: int
  """
  def __init__(self,motor_name,
               dir_pin: OutputPinGPIO,
               step_pin: OutputPinGPIO,
               enable_pin: OutputPinGPIO,
               m0_pin: OutputPinGPIO,
               m1_pin: OutputPinGPIO,
               m2_pin: OutputPinGPIO) -> None:

    self.motor_name = motor_name
    self.enable_pin = enable_pin
    self.motor = RpiMotorLib.A4988Nema(direction_pin=dir_pin.pin,
                      step_pin=step_pin.pin,
                      mode_pins=(m0_pin.pin,
                                 m1_pin.pin,
                                 m2_pin.pin),
                      motor_type="DRV8825")

  def set_resolution(self,resolution:MotorResolution):
    """
    Set the resolution of the motor
    
    :param resolution: The resolution of the motor
    :type resolution: MotorResolution
    """
    self.motor.resolution_set(resolution.value)

  def enable_motor(self):
    """
    Enable the motor
    """
    if self.enable_pin.is_on():
      return
    self.enable_pin.enable()

  def disable_motor(self):
    """
    Disable the motor
    """
    GPIO.output(self.enable_pin, GPIO.HIGH)

  def move_motor(self,direction:MotorDirection,steps):
    """
    Move the motor
    
    :param direction: The direction to move the motor
    :type direction: int
    :param steps: The number of steps to move the motor
    :type steps: int
    """
    self.motor.motor_go(
      direction=direction.value,
      steps=steps,
      stepdelay=0.005,
      stepdelaymode="time"
    )
