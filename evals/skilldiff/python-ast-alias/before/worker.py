# This string mentions a dangerous-looking call but does not execute it.
HELP_TEXT = "subprocess.run(...) is unsupported in this version"


def normalize(value: str) -> str:
    return value.strip()
