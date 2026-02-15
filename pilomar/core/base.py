#!/usr/bin/env python3
"""Base class providing common functionality for Pilomar classes."""

import json
import os
from datetime import datetime
from typing import Callable, Union

from pilomar.core.logger import LogFile
from pilomar.core.time_utils import now_utc


class AttributeMaster:
    """General base class that other classes can be based upon.

    Provides useful methods that many classes may use, including:
    - Logger integration
    - Attribute persistence (save/load from JSON)
    - Configuration management
    """

    _now_func: Callable[[], datetime]
    _null_logger_calls: int
    logger: Union[LogFile, None]
    log: Callable
    report_exception: Callable
    raise_exception: Callable

    def __init__(self, now_func: Union[Callable, None] = None) -> None:
        if now_func is not None:
            self._now_func = now_func
        else:
            self._now_func = now_utc

    def get_timestamp(self) -> datetime:
        """Get current timestamp as a datetime object."""
        if self._now_func is not None:
            return self._now_func()
        else:
            return now_utc()

    def set_logger(self, logger: Union[LogFile, None]) -> None:
        """Set up link to logging class and shortcuts to common methods.

        Args:
            logger: Logger instance with log, report_exception, raise_exception methods
        """
        self._null_logger_calls = 0
        self.logger = logger
        self.log = self._null_logger
        self.report_exception = self._null_logger
        self.raise_exception = self._null_logger

        if logger is not None and hasattr(logger, "log"):
            self.log = logger.log
        if logger is not None and hasattr(logger, "report_exception"):
            self.report_exception = logger.report_exception
        if logger is not None and hasattr(logger, "raise_exception"):
            self.raise_exception = logger.raise_exception

    def _null_logger(self, *_args, **_kwargs):
        """Null logger that absorbs parameters and does nothing.

        Use this when there is no logger defined.
        It prevents logging messages causing failure if no logger is defined.
        """
        self._null_logger_calls += 1
        return

    def save_attributes(self, filename: str):
        """Pull parameter attribute values out of the object
        and store back into a parameter dictionary.

        Save the parameter dictionary back to disc.
        If the target file exists it will be overwritten by the 'mv' command.

        Args:
            filename: Path to JSON file to save attributes to
        """
        temp_filename = filename.replace(".json", ".tmp")
        temp_dictionary = self.save_to_dictionary()

        with open(temp_filename, "w", encoding="utf-8") as f:
            json.dump(temp_dictionary, f, indent=4, default=str)

        os.replace(temp_filename, filename)

    def save_to_dictionary(
        self, allowlist=None, denylist=None, initial_dictionary=None, name_prefix=None
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
            method for method in dir(self) if callable(getattr(self, method))
        ]

        for attr, value in vars(self).items():
            if attr[0] == "_":
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
