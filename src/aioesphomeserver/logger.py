from __future__ import annotations

LOG_LEVEL_LETTERS = [
    "",    # NONE
    "E",   # ERROR
    "W",   # WARNING
    "I",   # INFO
    "C",   # CONFIG
    "D",   # DEBUG
    "V",   # VERBOSE
    "VV",  # VERY_VERBOSE
]

def format_log(level, tag, line_number, message):
    letter = LOG_LEVEL_LETTERS[level]

    return f"[{letter}][{tag}:{line_number}]: {message}"