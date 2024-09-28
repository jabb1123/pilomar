class WarningFlags:

    def __init__(
        self,
    ):
        self.warningFlags = {}

    def FirstWarningFlag(self, flagname):
        """Given a flag name, return True if this is the first time it's been triggered.
        This is used to prevent warning messages repeating when a condition is triggered.
        Using this mechanism we know that the warning is already issued, so don't repeat it.
        """
        res = self.warningFlags.get(flagname, False)
        if not res:
            self.warningFlags[flagname] = True  # 1st occurrence, so flag it as such.
        return res

    def ResetWarningFlag(self, flagname):
        """Given a flag name, reset it to False.
        This is used to prevent warning messages repeating when a condition is triggered.
        Using this mechanism we know that the warning is already issued, so don't repeat it.
        """
        self.warningFlags[flagname] = False
