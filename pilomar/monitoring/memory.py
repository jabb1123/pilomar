#!/usr/bin/env python3

# Pilomar's memory monitor class.

# This software is published under the GNU General Public License v3.0.
# Also respect any pre-existing terms of any components that this incorporates.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import sys
import tracemalloc  # Memory allocation tracking.

from pilomar.core.base import AttributeMaster
from pilomar.core.timer import Timer  # Pilomar's timer class.
from pilomar.utils.os_command import OsCommand  # OS Command execution.


class MemoryMonitor(AttributeMaster):  # 1 references.
    """Simple class to monitor the memory load of the RPi."""

    def __init__(self, logger=None):
        super().__init__()
        self.set_logger(logger)
        self.os_command = OsCommand(logger=self.log)
        self.os_cmd = self.os_command.execute
        self.os_cmd_code = self.os_command.execute_code
        self.command = "free -m"
        self.timer = Timer(60)  # Set timer for 60 seconds.
        self.memory_total = 0
        self.memory_used = 0
        self.memory_free = 0
        self.used_history = []
        self.free_history = []
        self.poll(force=True)  # Kickstart the values.

    def start_trace(self):
        """Start tracking memory allocations."""
        tracemalloc.start()

    def read_trace(self):
        """Read current memory allocation statistics."""
        result = tracemalloc.get_traced_memory()
        if self.log is not None:
            self.log("memorymonitor.read_trace(). current/peak:", result, terminal=False)
        return result

    def snapshot_trace(self):
        """Take a snapshot of memory allocations."""
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics("lineno")
        if self.log is not None:
            for stat in top_stats:
                self.log("memorymonitor.snapshot_trace():", stat, terminal=False)
        return top_stats

    def stop_trace(self):
        """Stop memory allocation tracking."""
        tracemalloc.stop()

    def item_sizes(self):
        """Get sizes of global and local variables."""
        result = {}
        idx = 0
        # Globals
        # for name, size in sorted(((name, sys.getsizeof(value)) for name, value in list(globals().items())), key= lambda x: -x[1])[:10]:
        for name, size in sorted(
            ((name, sys.getsizeof(value)) for name, value in list(globals().items())),
            key=lambda x: -x[1],
        ):
            result[idx] = {"name": name, "size": size, "scope": "global"}
            idx += 1
            # print("{:>30}: {:>8}".format(name, sizeof_fmt(size)))
            if self.log is not None:
                self.log("memorymonitor.item_sizes():Globals:", name, size, terminal=False)
        ## Locals
        ##for name, size in sorted(((name, sys.getsizeof(value)) for name, value in list(locals().items())), key= lambda x: -x[1])[:10]:
        # for name, size in sorted(((name, sys.getsizeof(value)) for name, value in list(locals().items())), key= lambda x: -x[1]):
        #    result[idx] = {'name':name, 'size':size, 'scope':'global'}
        #    idx += 1
        #    #print("{:>30}: {:>8}".format(name, sizeof_fmt(size)))
        #    if self.log != None:
        #        self.log("memorymonitor.item_sizes():Locals:",name,size,terminal=False)
        return result

    def poll(self, force=False):
        """Decide if it is time to update the memory usage statistics.
        'Free' memory is based upon the 'available memory' figure rather than the 'free' column.
        This is because 'free' is missing memory allocated to the O/S cache.
        'available' shows something closer to the memory that the system COULD allocate to running programs.
        """
        #    $ free -m
        #                  total        used        free      shared  buff/cache   available
        #    Mem:           1815         175         216           1        1423        1548   <- This line is used.
        #    Swap:            99          33          66
        if force or self.timer.due():  # Time to update the CPU figures.
            lines = self.os_cmd(self.command)  # osCmd function dedicated to the MAIN thread.
            memoryfields = lines[1].split()  # This splits by blocks of whitespace.
            if len(memoryfields) > 2:
                # Total
                self.memory_total = int(memoryfields[1]) * 1000000
                # Used
                self.memory_used = int(memoryfields[2]) * 1000000
                # 'Available' (Because FREE column is misleading.)
                self.memory_free = int(memoryfields[6]) * 1000000
            self.used_history.append(self.memory_used)
            self.free_history.append(self.memory_free)
            # Last 10 entries only.
            self.used_history = self.used_history[-10:]
            # Last 10 entries only.
            self.free_history = self.free_history[-10:]

    def get_memory(self, force=False):
        """Return recent memory usage statistics."""
        self.poll(force=force)
        return self.memory_total, self.memory_used, self.memory_free

    def get_total(self, force=False) -> int:
        """Return recent total memory value."""
        self.poll(force=force)
        return self.memory_total

    def get_used(self, force=False) -> int:
        """Return recent used memory value."""
        self.poll(force=force)
        return self.memory_used

    def get_free(self, force=False) -> int:
        """Return recent free memory value."""
        self.poll(force=force)
        return self.memory_free

    def get_used_range(self, force=False) -> str:
        """Return recent range of memory full."""
        self.poll(force=force)
        result = ""
        if len(self.used_history) > 5:
            min_used = int(100 * min(self.used_history) / self.memory_total)
            max_used = int(100 * max(self.used_history) / self.memory_total)
            result = "(" + str(min_used) + "% - " + str(max_used) + "%" + ")"
        return result

    def get_free_range(self, force=False) -> str:
        """Return recent range of memory free."""
        self.poll(force=force)
        result = ""
        if len(self.free_history) > 5:
            min_free = int(100 * min(self.free_history) / self.memory_total)
            max_free = int(100 * max(self.free_history) / self.memory_total)
            result = "(" + str(min_free) + "% - " + str(max_free) + "%" + ")"
        return result
