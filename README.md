# pi-lomar

RaspberryPi based miniature observatory.
A Python3 project to control a small camera and telephoto lens housed in a miniature 3D printed observatory enclosure.
This combines multiple open modules to handle object location, tracking and image capture.

This uses Python3 on the Raspberry Pi and CircuitPython on a connected Pimoroni Tiny2040 microcontroller.

The physical telescope, mechanism and dome is buildable from the [Instructables page](https://www.instructables.com/Pi-lomar-3D-Printed-Working-Miniature-Observatory-/)

The [wiki for pi-lomar](https://github.com/Short-bus/pilomar/wiki)

-----------------------------------------------------

The Skyfield API is described [here](https://rhodesmill.org/skyfield/api.html)

## Configuration

This version expects the following hardware:

- RaspberryPi microcomputer (V3 or V4) 2GB or greater.
- Raspbian BUSTER 32BIT or BOOKWORM 64BIT operating system.
- Pimoroni Tiny2040 8MB as a microcontroller of the motors
- Nema 17 stepper motors (0.9degree per full step).
- DRV8825 stepper motor driver chips.
- Raspberry Pi High Quality Camera Sensor V1.0
- Raspberry Pi 16mm 'telephoto' lens.
- - You can use other lenses, the program will generally try to adapt to
the lens length defined in the parameter file, do not exceed 50mm.

Recommended exposures.

- Full Moon = 1e-6 seconds
- M31 Andromeda Galaxy = 10.0 seconds = Magnitude 3.44
- M27 Dumbbell Nebula = 20.0 seconds = Magnitude 7.50
Fastest possible exposure is 1e-6 seconds.

-----------------------------------------------------

### OS Support

This version runs on only certain Raspberry Pi configurations.

#### Working combinations

- RASPBERRY PI 3B + BUSTER 32Bit
- RASPBERRY PI 4B + BUSTER 32Bit
- RASPBERRY PI 4B + BOOKWORM 64Bit <------------ RECOMMENDED

#### Unsupported combinations

- RASPBERRY PI
- RASPBERRY PI 2
- RASPBERRY PI 3B + BULLSEYE
- RASPBERRY PI 4B + BULLSEYE
- RASPBERRY PI 5B (Not ready yet)

-----------------------------------------------------

BEWARE! This program uses THREADS. It has to handle UI, MOVEMENT, COMMUNICATIONS and PHOTOGRAPHY in parallel.
Thread 1 (MAIN Process) handles:

- User interface, astro calculations, observation control.

Thread 2 handles:

- Image capture, image preparation, preview generation, tracking image processing, motor position tuning.

Thread 3 handles:

- UART communication flow between RPi and microcontroller, including trajectory calculation and updates.

-----------------------------------------------------

## KNOWN ISSUES

*Q* On rare occasions, the camera process can hang completely, it does
not complete image capture, requiring a power cycle of the RPi.
    The cause is not known, but the camera board stops responding for a very long time.
    I have read online that power problems to the camera can cause this.
    This is detected and reported, but this does not recover the situation programmatically.
    Problem is more rare in builds from 2023 onwards.
*Q* Some microcontrollers sometimes randomly reset. The software is relatively reset
tolerant and recovers automatically, but the cause of the resets is not yet identified.
    Resets are reported, and generally only cause brief delays while the system recovers.
    Resets are more common with RPi Pico 2040 and Adafruit Feather 2040.
    Resets do not occur with Pimoroni Tiny2040 8MB.
*Q* During observations the keyboard scanning routine can the display to blink sometimes over telnet connections.
    If you are sensitive to flashing images you can slow down the keyboard scanning
so that the image is more stable, but it will react to keyboard input more slowly.

Version
0.1.1    29.11.2023 Removed out of date references to MotorRunningSeconds.
                    Stopped eternal looping if recoveryfile write had continuous failure.
                    MarkupPreview now tolerates older format ngc.json datafile.
0.1.2    29.11.2023 Remaining references to onboard LEDs removed as they
are not required in the running system, and simplify the PCB build.
         11.12.2023 ProjectRoot is respected across the program, there were some
hardcoded /home/pi directory names still in the code. (GitHub Issue #35)
         11.12.2023 Min/MaxAltitudeAngle initialisation was wrong. (GitHub Issue #38)
         18.12.2023 Version validation only considers first 2 elements.
                    SetMotorAngle() now states current motor angle.
0.2.0    13.01.2024 GoToAngle, GoToTarget show progress during large moves.
         31.01.2024 2024-01-issues items addressed.
0.3.0    12.03.2024 2024-03-issues items addressed.
1.0.0    20.04.2024 Refactored code.
                    Preparations for RPi5 support.
1.1.0    07.05.2024 Bookworm/64bit can now generate .fits image files.

## Versioning

MAJOR.MINOR.MICRO

- MAJOR = Breaking change. Not fully compatible with previous versions. Usually requires RPI and MICROCONTROLLER updates together.
- MINOR = New features but backwards compatible. Usually allows RPI or MICROCONTROLLER to be updated independently.
- MICRO = Development/bugfix releases.

## Licensing Information

This software is published under the [GNU General Public License v3.0](LICENSE).
Also respect any pre-existing terms of any components that this incorporates.

- SKYFIELD is issued and used under the "MIT License" terms.
- HIPPARCOS data is used under Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International License.
- JPL data for planet positions will have its own licence.
- NGC (New General Catalog) is gathered from multiple sources including the Saguaro Astronomy Club Database version 8.1
- The MESSIER catalog is gathered from multiple sources.
- The MeteorShower list is based upon the Wikipedia list (2021).
- Space station data comes from the celestrak.org website (using NORAD public data).
- The Comet list comes from the Minor Planet Center.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
THIS SOFTWARE CAN CONTROL ELECTRICAL AND MECHANICAL DEVICES.
THERE IS THEREFORE A RISK OF INJURY FROM INCORRECT ASSEMBLY, OPERATION OR FAILURE OF COMPONENTS.
IT IS YOUR RESPONSIBILITY TO ENSURE THE SAFETY OF THE DEVICES YOU CHOOSE TO CONTROL WITH THIS SOFTWARE.
