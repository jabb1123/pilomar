def bool_to_string(value: bool):
    if value:
        return "y"
    else:
        return "n"


def string_to_bool(value: str, default: bool = False):
    if value.lower() == "y" or value.lower() == "true":
        return True
    elif value.lower() == "n" or value.lower() == "false":
        return False
    else:
        return default
