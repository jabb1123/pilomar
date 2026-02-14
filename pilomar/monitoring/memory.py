#!/usr/bin/python

# Pilomar's cpu monitor class.

# This software is published under the GNU General Public License v3.0.
# Also respect any pre-existing terms of any components that this incorporates.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

from pilomar.utils.os_command import OsCommand # OS Command execution.
from pilomar.core.timer import Timer # Pilomar's timer class.
import tracemalloc # Memory allocation tracking.
import sys

class MemoryMonitor(): # 1 references.
    """ Simple class to monitor the memory load of the RPi. """

    def __init__(self,logger=None):
        self.Log = logger # Define which logger to use.
        self.os_command = OsCommand(logger=logger)
        self.os_cmd = self.os_command.Execute
        self.os_cmdCode = self.os_command.ExecuteCode
        self.command = "free -m"
        self.timer = Timer(60) # Set timer for 60 seconds.
        self.memory_total = 0
        self.memory_used = 0
        self.memory_free = 0
        self.used_history = []
        self.free_history = []
        self.poll(force=True) # Kickstart the values.

    def start_trace(self):
        tracemalloc.start()

    def read_trace(self):
        result = tracemalloc.get_traced_memory()
        if self.Log != None: self.Log("memorymonitor.read_trace(). current/peak:",result,terminal=False)
        return result

    def snapshot_trace(self):
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('lineno')
        if self.Log != None: 
            for stat in top_stats:
                self.Log("memorymonitor.snapshot_trace():",stat,terminal=False)
        return top_stats
        
    def stop_trace(self):
        tracemalloc.stop()
    
    def item_sizes(self):
        result = {}
        idx = 0
        # Globals
        #for name, size in sorted(((name, sys.getsizeof(value)) for name, value in list(globals().items())), key= lambda x: -x[1])[:10]:
        for name, size in sorted(((name, sys.getsizeof(value)) for name, value in list(globals().items())), key= lambda x: -x[1]):
            result[idx] = {'name':name, 'size':size, 'scope':'global'}
            idx += 1
            #print("{:>30}: {:>8}".format(name, sizeof_fmt(size)))
            if self.Log != None:
                self.Log("memorymonitor.item_sizes():Globals:",name,size,terminal=False)
        ## Locals
        ##for name, size in sorted(((name, sys.getsizeof(value)) for name, value in list(locals().items())), key= lambda x: -x[1])[:10]:
        #for name, size in sorted(((name, sys.getsizeof(value)) for name, value in list(locals().items())), key= lambda x: -x[1]):
        #    result[idx] = {'name':name, 'size':size, 'scope':'global'}
        #    idx += 1
        #    #print("{:>30}: {:>8}".format(name, sizeof_fmt(size)))
        #    if self.Log != None:
        #        self.Log("memorymonitor.item_sizes():Locals:",name,size,terminal=False)
        return result

    def Poll(self,force = False):
        """ Decide if it is time to update the memory usage statistics. 
            'Free' memory is based upon the 'available memory' figure rather than the 'free' column.
            This is because 'free' is missing memory allocated to the O/S cache. 
            'available' shows something closer to the memory that the system COULD allocate to running programs. """
        #    $ free -m
        #                  total        used        free      shared  buff/cache   available
        #    Mem:           1815         175         216           1        1423        1548   <- This line is used.
        #    Swap:            99          33          66
        if force or self.timer.Due(): # Time to update the CPU figures.
            lines = self.os_cmd(self.command)  # osCmd function dedicated to the MAIN thread.
            memoryfields = lines[1].split() # This splits by blocks of whitespace.
            if len(memoryfields) > 2:
                self.memory_total = int(memoryfields[1]) * 1000000 # Total
                self.memory_used = int(memoryfields[2]) * 1000000 # Used
                self.memory_free = int(memoryfields[6]) * 1000000 # 'Available' (Because FREE column is misleading.)
            self.used_history.append(self.memory_used)
            self.free_history.append(self.memory_free)
            self.used_history = self.used_history[-10:] # Last 10 entries only.
            self.free_history = self.free_history[-10:] # Last 10 entries only.

    def GetMemory(self,force=False):
        """ Return recent memory usage statistics. """
        self.poll(force=force)
        return self.memory_total, self.memory_used, self.memory_free
        
    def GetTotal(self,force=False) -> int:
        """ Return recent total memory value. """
        self.poll(force=force)
        return self.memory_total

    def GetUsed(self,force=False) -> int:
        """ Return recent used memory value. """
        self.poll(force=force)
        return self.memory_used

    def GetFree(self,force=False) -> int:
        """ Return recent free memory value. """
        self.poll(force=force)
        return self.memory_free

    def GetUsedRange(self,force=False) -> str:
        """ Return recent range of memory full. """
        self.poll(force=force)
        result = ''
        if len(self.used_history) > 5:
            MinUsed = int(100 * min(self.used_history) / self.memory_total)
            MaxUsed = int(100 * max(self.used_history) / self.memory_total)
            result = '(' + str(MinUsed) + "% - " + str(MaxUsed) + "%" + ')'
        return result

    def GetFreeRange(self,force=False) -> str:
        """ Return recent range of memory free. """
        self.poll(force=force)
        result = ''
        if len(self.free_history) > 5:
            MinFree = int(100 * min(self.free_history) / self.memory_total)
            MaxFree = int(100 * max(self.free_history) / self.memory_total)
            result = '(' + str(MinFree) + "% - " + str(MaxFree) + "%" + ')'
        return result

