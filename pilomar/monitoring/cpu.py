#!/usr/bin/python

# Pilomar's cpu monitor class.
# Also provides some measurements of RPi's voltage/current measurements.
# Also provides read access to settings from config.txt file.
# Also provides measurement of CPU temperature.

# This software is published under the GNU General Public License v3.0.
# Also respect any pre-existing terms of any components that this incorporates.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

from datetime import datetime

from pilomar.core.base import AttributeMaster
from pilomar.core.timer import Timer  # Pilomar's timer class.
from pilomar.utils.os_command import OsCommand  # Pilomar's OS Command execution.

try:
    from gpiozero import CPUTemperature

    GPIOZERO_AVAILABLE = True
except ImportError:
    CPUTemperature = None
    GPIOZERO_AVAILABLE = False


class CpuMonitor(AttributeMaster):  # 1 references.
    """Simple class to monitor the CPU load of the RPi.
    This periodically polls the CPU load and establishes some metrics."""

    def __init__(self, logger=None, name="", period=60):
        super().__init__()
        self.name = name  # Allow an instance name to be assigned.
        # CamLog # Handle to the class that handles logging and error tracing.
        self.set_logger(logger)
        self.os_command = OsCommand(logger=self.log)  # Create OS command executor.
        self.os_cmd = self.os_command.execute
        self.cpu_timer = Timer(period)  # Set timer for 60 seconds.
        self.measured_time = datetime.now()
        # Overall CPU load figures.
        self.cpu_used = 0  # Cpu used slots since system start
        self.cpu_idle = 0  # Cpu idle slots since system start
        self.cpu_busy = 0  # Percentage busy over Poll period.
        self.busy_history = []  # List of last 10 busy percentage figures.
        self.cpu_temp = 0  # Reported CPU temperature.
        self.curr_freq = None  # Current frequency
        # The previous frequency measure. Updated when checked by freq_changed() method.
        self.prev_freq = None
        self.min_freq = None  # Minimum frequency
        self.max_freq = None  # Maximum frequency
        # Is the CPU being throttled? 100 = 100% full speed, anything lower means it's idling a bit.
        self.clock_percent = None
        # Individual CORE load figures.
        self.core_list = [
            "cpu0",
            "cpu1",
            "cpu2",
            "cpu3",
        ]  # These are the cores to measure.
        self.core_used = [0] * len(
            self.core_list
        )  # Individual core used slots since system start.
        self.core_idle = [0] * len(
            self.core_list
        )  # Individual core idle slots since system start.
        self.core_busy = [0] * len(
            self.core_list
        )  # Individual core busy slots since system start.
        self.power_timestamp = datetime.now()
        self.power_data = {"timestamp": self.power_timestamp}
        self.throttle_timestamp = datetime.now()
        self.throttle_data = {
            "timestamp": self.throttle_timestamp
        }  # Clear out the readings.
        self.poll_all(force=True)  # Update the stats initially.

    def freq_changed(self):
        """Call this to see if the clock frequency has changed since you last checked."""
        result = False
        # We have a current measure.
        if self.curr_freq is not None:
            # Frequency changed.
            if self.prev_freq is not None and self.prev_freq != self.curr_freq:
                result = True
            # Save this clock frequency for the next comparison.
            self.prev_freq = self.curr_freq
        return result

    def is_throttled(self):
        """Return TRUE if CPU appears to be throttled."""
        result = False
        if (
            self.curr_freq is not None
            and self.max_freq is not None
            and self.curr_freq < self.max_freq
        ):
            result = True
        return result

    def min_speed(self):
        """Return TRUE if CPU appears to be running a minimum clock speed."""
        result = False
        if (
            self.curr_freq is not None
            and self.min_freq is not None
            and self.curr_freq <= self.min_freq
        ):
            result = True
        return result

    def full_speed(self):
        """Return TRUE if CPU appears to be running at full clock speed."""
        result = False
        if (
            self.curr_freq is not None
            and self.max_freq is not None
            and self.curr_freq >= self.max_freq
        ):
            result = True
        return result

    def log_cpu_info(self):
        """Record CPU information to the main log file."""
        c_cmd = "cat /proc/cpuinfo"
        listlines = self.os_cmd(c_cmd)
        for line in listlines:
            self.log(line, terminal=False)

    def measure_power(self):
        """Update the dictionary containing current and voltage measurements
            from the RPi. ONLY works on RPi5 currently.

            vcgencmd pmic_read_adc generates output like this...

             3V7_WL_SW_A current(0)=0.05855580A
               3V3_SYS_A current(1)=0.06148359A
               1V8_SYS_A current(2)=0.13272650A
              DDR_VDD2_A current(3)=0.13955800A
              DDR_VDDQ_A current(4)=0.00980400A
               1V1_SYS_A current(5)=0.19811380A
                0V8_SW_A current(6)=0.34157550A
              VDD_CORE_A current(7)=5.03652000A
               3V3_DAC_A current(17)=0.00006105A
               3V3_ADC_A current(18)=0.00054945A
               0V8_AON_A current(16)=0.00531135A
                  HDMI_A current(22)=0.02161170A
             3V7_WL_SW_V volt(8)=3.61069200V
               3V3_SYS_V volt(9)=3.29982600V
               1V8_SYS_V volt(10)=1.81684800V
              DDR_VDD2_V volt(11)=1.10109800V
              DDR_VDDQ_V volt(12)=0.60366240V
               1V1_SYS_V volt(13)=1.10292900V
                0V8_SW_V volt(14)=0.80292960V
              VDD_CORE_V volt(15)=0.89369880V
               3V3_DAC_V volt(20)=3.29944700V
               3V3_ADC_V volt(21)=3.30402600V
               0V8_AON_V volt(19)=0.79618980V
                  HDMI_V volt(23)=4.92450000V
                 EXT5V_V volt(24)=4.92450000V
                  BATT_V volt(25)=0.00341880V

        It sets self.power_data dictionary with values like...
            {'timestamp':....,
             'EXT5V':{'V':4.9245},
             '3V3_SYS':{'V':3.299826,'A':0.06148359},

        """
        self.power_timestamp = datetime.now()
        self.power_data["timestamp"] = self.power_timestamp
        c_cmd = "vcgencmd pmic_read_adc"
        lines = self.os_cmd(c_cmd)
        for rawline in lines:
            # print('measure_power: rawline',rawline)
            line = rawline.strip()
            lineitems = line.split(" ")
            if len(lineitems) == 2 and lineitems[1][-1] in ["A", "V"]:
                point = lineitems[0][:-2]
                unit = lineitems[0][-1]
                measure = float(lineitems[1].split("=")[1][:-1])
                # print('measure_power: point',point)
                # print('measure_power: unit',unit)
                # print('measure_power: measure',measure)
                entry = self.power_data.get(point, {})
                entry[unit] = measure
                # Store min/max too.
                minlab = "min_" + unit
                maxlab = "max_" + unit
                minval = min(measure, entry.get(minlab, 99999))
                maxval = max(measure, entry.get(maxlab, -99999))
                entry[minlab] = minval
                entry[maxlab] = maxval
                self.power_data[point] = entry

    def measure_throttle(self):
        """Update the dictionary containing the various throttle measurements for the CPU.
        vcgencmd get_throttled
        returns
        throttled=0x0

        Bit	        Hexadecimal value	        Meaning
        0           0x1                         Undervoltage detected
        1           0x2                         Arm frequency capped
        2           0x4                         Currently throttled
        3           0x8                         Soft temperature limit active
        16          0x10000                     Undervoltage has occurred
        17          0x20000                     Arm frequency capping has occurred
        18          0x40000                     Throttling has occurred
        19          0x80000                     Soft temperature limit has occurred

        """
        self.throttle_timestamp = datetime.now()
        self.throttle_data = {}  # Clear out the readings.
        self.throttle_data["timestamp"] = self.throttle_timestamp
        c_cmd = "vcgencmd get_throttled"
        lines = self.os_cmd(c_cmd)
        for line in lines:
            lineitems = line.strip().split("=")
            if len(lineitems) > 1:
                value = int(lineitems[1], 16)  # Convert from Hex to integer.
                # Undervoltage detected
                if value & 0x1:
                    self.throttle_data["UndervoltageDetected"] = True
                # Undervoltage not detected
                else:
                    self.throttle_data["UndervoltageDetected"] = False
                # ARMFrequencyCapped detected
                if value & 0x2:
                    self.throttle_data["ARMFrequencyCapped"] = True
                # ARMFrequencyCapped not detected
                else:
                    self.throttle_data["ARMFrequencyCapped"] = False
                # Currently throttled
                if value & 0x4:
                    self.throttle_data["CurrentlyThrottled"] = True
                # Not Currently throttled
                else:
                    self.throttle_data["CurrentlyThrottled"] = False
                # SoftTemperatureLimit active
                if value & 0x8:
                    self.throttle_data["SoftTemperatureLimitActive"] = True
                # SoftTemperatureLimit not active
                else:
                    self.throttle_data["SoftTemperatureLimitActive"] = False
                # Undervoltage occurred
                if value & 0x10000:
                    self.throttle_data["UndervoltageOccurred"] = True
                # Undervoltage not occurred
                else:
                    self.throttle_data["UndervoltageOccurred"] = False
                # ARMFrequencyCap occurred
                if value & 0x20000:
                    self.throttle_data["ARMFrequencyCapOccurred"] = True
                # ARMFrequencyCap has not occurred
                else:
                    self.throttle_data["ARMFrequencyCapOccurred"] = False
                # Throttling occurred
                if value & 0x40000:
                    self.throttle_data["ThrottlingOccurred"] = True
                # Throttling has not occurred
                else:
                    self.throttle_data["ThrottlingOccurred"] = False
                # SoftTemperatureLimit has occurred
                if value & 0x80000:
                    self.throttle_data["SoftTemperatureLimitOccurred"] = True
                # SoftTemperatureLimit has not occurred
                else:
                    self.throttle_data["SoftTemperatureLimitOccurred"] = False

    def display_throttle(self):
        """Basic display of cpu throttling measurements from the RPi."""
        print("Raspberry Pi throttling values")
        self.measure_throttle()
        for key, value in self.throttle_data.items():
            print(key, ":", value)

    def display_power(self):
        """Basic display of power measurements from the RPi."""
        print("Raspberry Pi power measurements:")
        # Generate dictionary of V and A measurements for various points in the RPi.
        self.measure_power()
        # Choose each measurement in turn.
        for key, entry in self.power_data.items():
            # Use measurement as the line label.
            line = key.rjust(20, " ") + ": "
            # If we have a dictionary, process each entry in turn.
            if isinstance(entry, dict):
                for k, v in entry.items():
                    line += k.rjust(5, " ") + ":" + str(v).ljust(14, " ")
            else:  # Not a dictionary so just report the value.
                line += str(entry)
            print(line)  # Print the resulting line.
        print("")
        print("Power configuration:")
        print(
            "usb_max_current_enable:",
            self.get_config_value("usb_max_current_enable", 0),
        )

    def get_config_value(self, name, default=None):
        """Retrieve configuration setting from config.txt
        Parameters ----------------------------------------------
        name = name as it appears in config.txt
        default = value to return if 'name' is not found.
        Output --------------------------------------------------
        Value as a string."""
        result = default
        c_cmd = "vcgencmd get_config " + name
        lines = self.os_cmd(c_cmd)
        for line in lines:
            # print('GetConfigValue:',line)
            lineitems = line.split("=")
            if len(lineitems) <= 1:
                continue  # Nothing there.
            result = lineitems[1].strip()
        return result

    def get_cpu_temp(self):
        """Return the CPU temperature."""
        if GPIOZERO_AVAILABLE and CPUTemperature is not None:
            cput = CPUTemperature()
            self.cpu_temp = cput.temperature
        else:
            self.cpu_temp = None
        return self.cpu_temp

    def log_cpu_temp(self):
        """Record CPU temperature in main log file."""
        self.log(
            "cpumonitor(",
            self.name,
            ").log_cpu_temp: Temperature",
            self.get_cpu_temp(),
            terminal=False,
        )

    def cmd_int(self, c_cmd, multiplier=1):
        """Execute command and return integer value."""
        result = None
        listlines = self.os_cmd(c_cmd)
        for line in listlines:
            self.log(line, terminal=False)
            try:
                result = int(line.strip()) * multiplier
            except Exception:  # pylint: disable=broad-except
                pass
        return result

    def cpu_frequency(self, force=False):
        """Return current, min and max CPU frequencies."""
        # Current frequency
        self.curr_freq = self.cmd_int(
            "cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq", multiplier=1000
        )
        # Minimum frequency
        if self.min_freq is None:
            # Minimum frequency
            self.min_freq = self.cmd_int(
                "cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq",
                multiplier=1000,
            )
        # Maximum frequency
        if self.max_freq is None:
            # Maximum frequency
            self.max_freq = self.cmd_int(
                "cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq",
                multiplier=1000,
            )
        try:
            if (
                self.curr_freq is not None
                and self.max_freq is not None
                and self.max_freq != 0
            ):
                self.clock_percent = int(round(100 * self.curr_freq / self.max_freq, 0))
            else:
                self.clock_percent = None  # Not measured yet.
        except Exception:  # pylint: disable=broad-except
            self.clock_percent = None  # Not measured yet.
        return True

    def poll_all(self, force=False):
        """Check if it is time to retrieve updated statistics from the entire CPU.
        Retrieves OVERALL load across all the cores and CPU.

        cpu  1550 30 2105 190212 711 0 32 0 0 0
        cpu0 354 8 622 47511 114 0 15 0 0 0
        cpu1 445 3 488 47498 234 0 5 0 0 0
        cpu2 354 5 528 47663 101 0 6 0 0 0
        cpu3 397 14 467 47539 261 0 6 0 0 0
        intr 131734 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1200 35002 0 2452 0 0 0 1 0 24246 0 0 0 0 0 889 0 0 6892 0 0 0 370 0 0 0 0 0 0 1482 27266 28957 0 0 0 0 0 0 2337 0 0 0 0 0 0 544 0 96
        ctxt 137336
        btime 1697994434
        processes 1335
        procs_running 1
        procs_blocked 0
        softirq 55555 3 5392 1 469 6425 0 10711 10714 0 21840

        """
        if force or self.cpu_timer.due():  # Time to update the CPU figures.
            statslist = self.os_cmd(
                "cat /proc/stat"
            )  # Check /proc/stat for specific core figures.

            # Update CPU figures.
            result = ""
            for (
                statsline
            ) in statslist:  # Find the statistics for this core in the result.
                if (
                    statsline.split()[0] == "cpu"
                ):  # 1st element will match the core name.
                    result = statsline
                    break
            if result == "":
                self.log(
                    "cpumonitor(",
                    self.name,
                    ").poll_all(): Didn't find stats for",
                    "cpu",
                    terminal=False,
                )
                return None  # No stats for the cpu, fail.
            # Break down the 1st line for analysis.
            # Using default split() makes it ignore duplicated spaces.
            elements = result.split()
            # We consider cols 1,2,3 as 'busy' activities.
            new_used = int(elements[1]) + int(elements[2]) + int(elements[3])
            # col 4 is an idle activity.
            new_idle = int(elements[4])
            # Change since the last poll
            diff_used = new_used - self.cpu_used
            # Change since the last poll
            diff_idle = new_idle - self.cpu_idle
            # Update stored figures.
            self.cpu_used = new_used
            self.cpu_idle = new_idle
            # Calculate % busy since last poll.
            self.cpu_busy = int(100 * diff_used / (diff_used + diff_idle))
            # Add to history list.
            self.busy_history.append(self.cpu_busy)
            # Only keep last 10 measures.
            self.busy_history = self.busy_history[-10:]

            # Update individual cores.
            for i, core in enumerate(self.core_list):
                result = ""
                # Find the statistics for this core in the result.
                for statsline in statslist:
                    # 1st element will match the core name.
                    if statsline.split()[0] == core:
                        result = statsline
                        break
                if result == "":
                    self.log(
                        f"cpumonitor({self.name}).poll_all(): Didn't find stats for {core}",
                        terminal=False,
                    )
                    continue  # No stats for this core, so ignore it.
                try:
                    # Break down the 1st line for analysis.
                    elements = result.split()
                    # We consider cols 1,2,3 as 'busy' activities.
                    new_used = int(elements[1]) + int(elements[2]) + int(elements[3])
                    # col 4 is an idle activity.
                    new_idle = int(elements[4])
                    # Change since the last poll
                    diff_used = new_used - self.core_used[i]
                    # Change since the last poll
                    diff_idle = new_idle - self.core_idle[i]
                    # Store current value for comparison with next round.
                    self.core_used[i] = new_used
                    self.core_idle[i] = new_idle
                    # Calculate % busy since last poll.
                    self.core_busy[i] = int(100 * diff_used / (diff_used + diff_idle))
                except Exception as e:  # pylint: disable=broad-except
                    # A log handler is defined.
                    if self.logger is not None:
                        self.log(
                            f"cpumonitor({self.name}).poll_all({core}) failed.",
                            terminal=False,
                        )
                        self.log(
                            f"cpumonitor({self.name}).poll_all({core}) Error: {str(e)}",
                            terminal=False,
                        )
                    else:  # No log handler available, print the error instead.
                        print(f"cpumonitor({self.name}).poll_all({core}) failed.")
                        print(
                            f"cpumonitor({self.name}).poll_all({core}) Error: {str(e)}"
                        )
            self.measured_time = datetime.now()
            self.log_cpu_temp()
            self.cpu_frequency()  # Update CPU clock speed attributes.
            _ = self.status_line()

    def status_line(self, label=True, sep=" ", force=False):
        """Return a status line for the CPU and all cores.
        label = True: Labels before each value.
                False: Just values.
        sep = Separator between each value."""
        self.poll_all(force=force)  # Check we have recent enough numbers.
        line = ""
        # Overall CPU load figures.
        if label:
            line += "Timestamp="
        line += str(self.measured_time) + sep
        if label:
            line += "CpuUsedSlots="
        line += str(self.cpu_used) + sep
        if label:
            line += "CpuIdleSlots="
        line += str(self.cpu_idle) + sep
        if label:
            line += "CpuBusyPc="
        line += str(self.cpu_busy) + "%" + sep
        if label:
            line += "CpuTemp="
        line += str(self.cpu_temp) + "C" + sep
        if label:
            line += "CurrFreq="
        line += str(self.curr_freq) + "Hz" + sep
        if label:
            line += "MinFreq="
        line += str(self.min_freq) + "Hz" + sep
        if label:
            line += "MaxFreq="
        line += str(self.max_freq) + "Hz" + sep
        if label:
            line += "ClockPc="
        line += str(self.clock_percent) + "%" + sep
        if label:
            line += "CpuBusyRange="
        temp = self.get_busy_range()
        if temp == "" or temp is None:
            temp = "calculating"
        line += str(temp) + sep
        if label:
            line += "is_throttled="
        line += str(self.is_throttled()) + sep
        if label:
            line += "min_speed="
        line += str(self.min_speed()) + sep
        if label:
            line += "full_speed="
        line += str(self.full_speed()) + sep
        # Individual CORE load figures.
        for i, c in enumerate(self.core_list):
            if label:
                line += c + "UsedSlots="
            line += str(self.core_used[i]) + sep
            if label:
                line += c + "IdleSlots="
            line += str(self.core_idle[i]) + sep
            if label:
                line += c + "BusyPc="
            line += str(self.core_busy[i]) + "%" + sep
        self.log(f"cpumonitor({self.name}).status_line: {line}", terminal=False)
        return line

    def percent_busy(self, force=False) -> int:
        """Return the recent CPU Busy % figure."""
        self.poll_all(force=force)  # Check we have recent enough numbers.
        return self.cpu_busy

    def percent_clock(self, force=False) -> int:
        """Return the recent clockspeed as percentage of clock range."""
        self.poll_all(force=force)  # Check we have recent enough numbers.
        return self.clock_percent

    def get_busy_range(self, force=False) -> str:
        """Return recent range of CPU busy percentages."""
        self.poll_all(force=force)
        result = ""
        if len(self.busy_history) > 5:
            min_busy = int(min(self.busy_history))
            max_busy = int(max(self.busy_history))
            result = f"({min_busy}% - {max_busy}%)"
        return result


if __name__ == "__main__":  # Fixes issue in notepad++ editor.
    pass
