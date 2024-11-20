"""    
WarningFlags class is used to prevent warning messages repeating when a condition is triggered.
"""


class WarningFlags:
    """WarningFlags class is used to prevent warning messages repeating when a condition is triggered."""

    def __init__(
        self,
    ):
        self.warning_flags = {}

    def first_warning_flag(self, flagname):
        """Given a flag name, return True if this is the first time it's been triggered.
        This is used to prevent warning messages repeating when a condition is triggered.
        Using this mechanism we know that the warning is already issued, so don't repeat it.
        """
        res = self.warning_flags.get(flagname, False)
        if not res:
            self.warning_flags[flagname] = True  # 1st occurrence, so flag it as such.
        return res

    def reset_warning_flag(self, flagname):
        """Given a flag name, reset it to False.
        This is used to prevent warning messages repeating when a condition is triggered.
        Using this mechanism we know that the warning is already issued, so don't repeat it.
        """
        self.warning_flags[flagname] = False
