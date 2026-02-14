#!/usr/bin/env python3
"""Base class providing common functionality for Pilomar classes."""

# This software is published under the GNU General Public License v3.0.
# Also respect any pre-existing terms of any components that this incorporates.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# THIS SOFTWARE CAN CONTROL ELECTRICAL AND MECHANICAL DEVICES.
# THERE IS THEREFORE A RISK OF INJURY FROM INCORRECT ASSEMBLY, OPERATION OR FAILURE OF COMPONENTS.
# IT IS YOUR RESPONSIBILITY TO ENSURE THE SAFETY OF THE DEVICES YOU CHOOSE TO CONTROL WITH THIS SOFTWARE.

import os
import json


class AttributeMaster:
    """General base class that other classes can be based upon.
    
    Provides useful methods that many classes may use, including:
    - Logger integration
    - Attribute persistence (save/load from JSON)
    - Configuration management
    """

    def set_logger(self, logger):
        """Set up link to logging class and shortcuts to common methods.
        
        Args:
            logger: Logger instance with Log, ReportException, RaiseException methods
        """
        self._null_logger_calls = 0
        self.logger = logger
        self.log = self._null_logger
        self.report_exception = self._null_logger
        self.raise_exception = self._null_logger
        
        if hasattr(logger, 'Log'):
            self.log = logger.Log
        if hasattr(logger, 'ReportException'):
            self.report_exception = logger.ReportException
        if hasattr(logger, 'RaiseException'):
            self.raise_exception = logger.RaiseException

    def _null_logger(self, *args, **kwargs):
        """Null logger that absorbs parameters and does nothing.
        
        Use this when there is no logger defined.
        It prevents logging messages causing failure if no logger is defined.
        """
        self._null_logger_calls += 1
        return

    def save_attributes(self, filename: str):
        """Pull parameter attribute values out of the object and store back into a parameter dictionary.
        
        Save the parameter dictionary back to disc.
        If the target file exists it will be overwritten by the 'mv' command.
        
        Args:
            filename: Path to JSON file to save attributes to
        """
        temp_filename = filename.replace(".json", ".tmp")
        temp_dictionary = self.save_to_dictionary()
        
        with open(temp_filename, 'w') as f:
            json.dump(temp_dictionary, f, indent=4, default=str)
        
        os.replace(temp_filename, filename)

    def save_to_dictionary(
        self,
        allowlist=None,
        denylist=None,
        initial_dictionary=None,
        name_prefix=None
    ) -> dict:
        """Adds the ability to save attributes of the object to a dictionary.
        
        It ignores any attributes starting with '_' character.
        
        Args:
            allowlist: If specified, lists the field names that should be saved.
                      If missing, all fields are saved.
            denylist: If specified, lists field names that will NOT be saved,
                     all others are.
            initial_dictionary: Provides initial values that this method will append to.
            name_prefix: Provides an optional prefix to all the field names.
            
        Returns:
            Dictionary containing the object's attributes
        """
        if initial_dictionary is None:
            conf_dict = {}
        else:
            conf_dict = initial_dictionary.copy()
            
        method_list = [
            method for method in dir(self) 
            if callable(getattr(self, method))
        ]
        
        for attr, value in vars(self).items():
            if attr[0] == '_':
                continue
            if attr in method_list:
                continue
            if denylist is not None and attr in denylist:
                continue
            if allowlist is None or attr in allowlist:
                if name_prefix is not None:
                    attr = name_prefix + attr
                conf_dict[attr] = value
                
        return conf_dict
