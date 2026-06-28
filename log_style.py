import builtins
import os
import re
import sys
from datetime import datetime

_ORIGINAL_PRINT = builtins.print
_INSTALLED = False
_TAG_RE = re.compile(r"^\[([^\]]+)\]\s*(.*)$", re.DOTALL)

RESET = "\033[0m"
DIM = "\033[2m"
BOLD = "\033[1m"
COLORS = {
    "INFO": "\033[36m",
    "WARNING": "\033[33m",
    "ERROR": "\033[31m",
    "SUCCESS": "\033[32m",
    "EXIT": "\033[35m",
    "DEBUG": "\033[90m",
    "CHROME": "\033[34m",
    "9ROUTER": "\033[95m",
    "OAUTH": "\033[96m",
    "GOOGLE": "\033[34m",
    "AWS": "\033[33m",
    "DB": "\033[92m",
}

ALIASES = {
    "WARN": "WARNING",
    "ERROR": "ERROR",
    "SUCCESS": "SUCCESS",
    "INFO": "INFO",
    "EXIT": "EXIT",
    "DEBUG": "DEBUG",
}

BORDERS = {"=", "-"}


def _supports_color(stream):
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return hasattr(stream, "isatty") and stream.isatty()


def _color(text, code, enabled):
    if not enabled or not code:
        return text
    return f"{code}{text}{RESET}"


def _enable_windows_ansi():
    if os.name == "nt":
        os.system("")


def _render_line(line, color_enabled):
    if not line:
        return line

    stripped = line.strip()
    if stripped and set(stripped) <= BORDERS:
        return _color(stripped, DIM, color_enabled)

    if stripped == "RUN SUMMARY":
        return _color(f"{stripped:^72}", BOLD, color_enabled)

    if " : " in line and not line.startswith("["):
        key, value = line.split(" : ", 1)
        key_text = f"{key.rstrip():<32}"
        return f"{_color(key_text, DIM, color_enabled)} : {_color(value, BOLD, color_enabled)}"

    match = _TAG_RE.match(line)
    if not match:
        return line

    raw_tag, message = match.groups()
    tag = ALIASES.get(raw_tag.upper(), raw_tag.upper())
    timestamp = datetime.now().strftime("%H:%M:%S")
    color = COLORS.get(tag, "")
    label = _color(f"{tag:<8}", color, color_enabled)
    time_part = _color(timestamp, DIM, color_enabled)
    return f"{time_part}  {label} {message}"


def pretty_print(*args, **kwargs):
    stream = kwargs.get("file", sys.stdout)
    if stream not in (sys.stdout, sys.stderr):
        return _ORIGINAL_PRINT(*args, **kwargs)

    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    flush = kwargs.get("flush", False)
    color_enabled = _supports_color(stream)

    text = sep.join(str(arg) for arg in args)
    rendered = "\n".join(_render_line(line, color_enabled) for line in text.split("\n"))
    return _ORIGINAL_PRINT(rendered, end=end, file=stream, flush=flush)


def install_pretty_print():
    global _INSTALLED
    if _INSTALLED:
        return
    _enable_windows_ansi()
    builtins.print = pretty_print
    _INSTALLED = True