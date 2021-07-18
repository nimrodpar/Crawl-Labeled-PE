""" Simple pretty logger module. Avoids the mess that is the logging module. """

import inspect
import os

# Logging levels
import sys

WARNING = "WARNING"
INFO = "INFO"
DEBUG = "DEBUG"
CRITICAL = "CRITICAL"
ERROR = "ERROR"


# Color and formatting stuff
BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)
# The background is set with 40 plus the number of the color, and the foreground with 30

# These are the sequences need to get colored output
RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[1;%dm"
BOLD_SEQ = "\033[1m"

COLORS = {
    WARNING: YELLOW,
    INFO: GREEN,
    DEBUG: BLUE,
    CRITICAL: MAGENTA,
    ERROR: RED
}


def color_text(text, color):
    return COLOR_SEQ % (30 + color) + text + RESET_SEQ


def bold_text(text):
    return BOLD_SEQ + text + RESET_SEQ


def format_message(s, level_name):
    return "{:20} | {} | {}".format(color_text(level_name, COLORS[level_name]), bold_text("logger"), s)


logging_levels_ordinals = {DEBUG: 0, INFO: 1, WARNING: 2, ERROR: 3, CRITICAL: 4}
logging_level = WARNING


def log(s, level):
    if logging_levels_ordinals[level] < logging_levels_ordinals[logging_level]:
        return
    filename, line_number, _, _, _ = inspect.getframeinfo(inspect.currentframe().f_back.f_back)
    message = []
    for l in " ".join(map(str, s)).split("\n"):
        message.append(format_message(l, level))
    message[-1] += " {}".format(bold_text("({}:{})".format(os.path.basename(filename), line_number)))
    message = "\n".join(message)
    if logging_levels_ordinals[level] >= logging_levels_ordinals[WARNING]:
        print(message, file=sys.stderr)
    else:
        print(message)


def debug_mode():
    return logging_level == DEBUG


def verbose_mode():
    return logging_level <= INFO


def debug(*s):
    log(s, DEBUG)


def info(*s):
    log(s, INFO)


def warn(*s):
    log(s, WARNING)


def error(*s):
    log(s, ERROR)


def critical(*s):
    log(s, CRITICAL)