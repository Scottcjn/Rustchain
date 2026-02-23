#!/usr/bin/env python3
"""
Color logging utilities for RustChain miners.
Respects NO_COLOR environment variable.
"""

import os

# ANSI color codes
COLORS = {
    'reset': '\033[0m',
    'black': '\033[30m',
    'red': '\033[31m',
    'green': '\033[32m',
    'yellow': '\033[33m',
    'blue': '\033[34m',
    'magenta': '\033[35m',
    'cyan': '\033[36m',
    'white': '\033[37m',
    'gray': '\033[90m',
    'bright_red': '\033[91m',
    'bright_green': '\033[92m',
    'bright_yellow': '\033[93m',
    'bright_blue': '\033[94m',
    'bright_magenta': '\033[95m',
    'bright_cyan': '\033[96m',
    'bright_white': '\033[97m',
}

# Mapping of log levels to colors
LEVEL_COLORS = {
    'info': 'cyan',
    'warning': 'yellow',
    'error': 'red',
    'success': 'green',
    'debug': 'gray',
}

def should_color() -> bool:
    """Return True if colors should be used (NO_COLOR not set)."""
    return 'NO_COLOR' not in os.environ

def colorize(text: str, color_name: str) -> str:
    """
    Colorize text with the given color name.
    If colors are disabled, returns the original text.
    """
    if not should_color() or color_name not in COLORS:
        return text
    return f"{COLORS[color_name]}{text}{COLORS['reset']}"

def colorize_level(text: str, level: str) -> str:
    """
    Colorize text based on log level.
    Level must be one of: info, warning, error, success, debug.
    """
    color_name = LEVEL_COLORS.get(level)
    if color_name:
        return colorize(text, color_name)
    return text

# Convenience functions
def info(text: str) -> str:
    return colorize(text, 'cyan')

def warning(text: str) -> str:
    return colorize(text, 'yellow')

def error(text: str) -> str:
    return colorize(text, 'red')

def success(text: str) -> str:
    return colorize(text, 'green')

def debug(text: str) -> str:
    return colorize(text, 'gray')

# For backward compatibility, also provide a print-like function
def print_colored(text: str, level: str = None, **kwargs):
    """
    Print colored text. If level is provided, color based on level.
    Otherwise, print plain text (colored if color enabled).
    """
    if level:
        text = colorize_level(text, level)
    print(text, **kwargs)

if __name__ == '__main__':
    # Test the colors
    print("Testing colors (NO_COLOR = {}):".format(os.environ.get('NO_COLOR', 'not set')))
    print(info("info: cyan"))
    print(warning("warning: yellow"))
    print(error("error: red"))
    print(success("success: green"))
    print(debug("debug: gray"))
    print(colorize("custom magenta", "magenta"))