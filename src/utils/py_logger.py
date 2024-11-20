import logging


class PyLogger(object):

    _base_log_name = None

    def __init__(
        self, log_base=None, log_ext=None, to_console=False, to_file=False, level="INFO"
    ):

        if log_base is not None:
            PyLogger._base_log_name = log_base
        if PyLogger._base_log_name is None:
            raise ValueError(
                "There is no value for log basename yet. Please provide a value for log_base."
            )
        if log_ext is None:
            self.log = logging.getLogger(PyLogger._base_log_name)
        else:
            self.log = logging.getLogger(f"{self._base_log_name}.{log_ext}")

        self.log.setLevel(logging.getLevelName(level))

        if to_console:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.getLevelName(level))
            self.log.addHandler(console_handler)

        if to_file:
            file_handler = logging.FileHandler(f"{self._base_log_name}.log")
            file_handler.setLevel(logging.getLevelName(level))
            self.log.addHandler(file_handler)

        self.log_file = f"{log_base}.{log_ext}"

    def info(self, message):
        with open(self.log_file, "a") as f:
            f.write(f"INFO: {message}\n")


class ColoredFormatter(logging.Formatter):
    # Define color codes for different log levels
    COLORS = {
        "DEBUG": "\033[92m",  # Green for DEBUG
        "INFO": "\033[0m",  # Default (no color) for INFO
        "WARNING": "\033[93m",  # Yellow for WARNING
        "ERROR": "\033[91m",  # Red for ERROR
        "CRITICAL": "\033[95m",  # Magenta for CRITICAL
    }
    RESET = "\033[0m"

    def format(self, record):
        # Get the original log message
        log_msg = super().format(record)
        # Apply color based on the log level
        color = self.COLORS.get(record.levelname, self.RESET)
        return f"{color}{log_msg}{self.RESET}"
