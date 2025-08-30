"""
Logger utility with colored output for different message types.
Provides colored console output for better readability and debugging.
"""

import os
import sys
from datetime import datetime
from enum import Enum
from typing import Optional


class LogLevel(Enum):
    """Log level enumeration with color codes"""

    INFO = ("INFO", "")  # No color
    WARNING = ("WARNING", "\033[93m")  # Yellow
    ERROR = ("ERROR", "\033[91m")  # Red
    SUCCESS = ("SUCCESS", "\033[92m")  # Green


class Logger:
    """
    A simple logger class with colored output support.
    Automatically applies colors based on message type.
    """

    # ANSI color codes
    RESET = "\033[0m"
    BOLD = "\033[1m"

    def __init__(self, name: str = "TZ-Archiver", enable_colors: bool = True):
        """
        Initialize logger.

        Args:
            name: Logger name to display in messages
            enable_colors: Whether to enable colored output (disable for file logs)
        """
        self.name = name
        self.enable_colors = enable_colors and self._supports_color()

        # Enable ANSI colors on Windows
        if os.name == "nt" and enable_colors:
            self._enable_windows_ansi_colors()

    def _enable_windows_ansi_colors(self):
        """Enable ANSI color support on Windows"""
        try:
            import ctypes
            from ctypes import wintypes

            # Constants for Windows console
            STD_OUTPUT_HANDLE = -11
            STD_ERROR_HANDLE = -12
            ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004

            kernel32 = ctypes.windll.kernel32

            # Get handles for stdout and stderr
            hout = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
            herr = kernel32.GetStdHandle(STD_ERROR_HANDLE)

            # Get current console mode
            old_out_mode = wintypes.DWORD()
            old_err_mode = wintypes.DWORD()
            kernel32.GetConsoleMode(hout, ctypes.byref(old_out_mode))
            kernel32.GetConsoleMode(herr, ctypes.byref(old_err_mode))

            # Enable ANSI escape sequences
            new_out_mode = old_out_mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING
            new_err_mode = old_err_mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING

            kernel32.SetConsoleMode(hout, new_out_mode)
            kernel32.SetConsoleMode(herr, new_err_mode)

        except Exception:
            # If enabling ANSI fails, colors will just not work
            pass

    def _supports_color(self) -> bool:
        """Check if the terminal supports color output"""
        # Always try to enable colors on Windows
        if os.name == "nt":
            return True

        # Unix-like systems generally support colors
        return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

    def _format_message(
        self, level: LogLevel, message: str, timestamp: bool = True
    ) -> str:
        """Format message with timestamp, level, and colors"""
        # Get timestamp
        time_str = datetime.now().strftime("%H:%M:%S") if timestamp else ""

        # Get level info
        level_name, color_code = level.value

        # Format message parts
        parts = []

        if timestamp:
            if self.enable_colors:
                parts.append(f"\033[90m{time_str}\033[0m")  # Gray timestamp
            else:
                parts.append(time_str)

        # Add level with color (simplified)
        if self.enable_colors and color_code:
            level_part = f"{color_code}[{level_name}]\033[0m"
        else:
            level_part = f"[{level_name}]"

        parts.append(level_part)

        # Add logger name (simplified)
        parts.append(self.name)

        # Add message with color
        if self.enable_colors and color_code:
            message_part = f"{color_code}{message}\033[0m"
        else:
            message_part = message

        parts.append(message_part)

        return " ".join(parts)

    def _log(self, level: LogLevel, message: str, timestamp: bool = True):
        """Internal logging method"""
        formatted_message = self._format_message(level, message, timestamp)

        # Print to stderr for errors, stdout for everything else
        if level == LogLevel.ERROR:
            print(formatted_message, file=sys.stderr)
        else:
            print(formatted_message)

    def info(self, message: str, timestamp: bool = True):
        """Log an info message (no color)"""
        self._log(LogLevel.INFO, message, timestamp)

    def warning(self, message: str, timestamp: bool = True):
        """Log a warning message (yellow)"""
        self._log(LogLevel.WARNING, message, timestamp)

    def error(self, message: str, timestamp: bool = True):
        """Log an error message (red)"""
        self._log(LogLevel.ERROR, message, timestamp)

    def success(self, message: str, timestamp: bool = True):
        """Log a success message (green)"""
        self._log(LogLevel.SUCCESS, message, timestamp)

    def log(self, level: str, message: str, timestamp: bool = True):
        """
        Log a message with specified level.

        Args:
            level: "info", "warning", "error", or "success"
            message: Message to log
            timestamp: Whether to include timestamp
        """
        level_map = {
            "info": LogLevel.INFO,
            "warning": LogLevel.WARNING,
            "error": LogLevel.ERROR,
            "success": LogLevel.SUCCESS,
        }

        log_level = level_map.get(level.lower(), LogLevel.INFO)
        self._log(log_level, message, timestamp)


# Create a default logger instance
default_logger = Logger()


# Convenience functions for quick logging
def info(message: str, timestamp: bool = True):
    """Log an info message"""
    default_logger.info(message, timestamp)


def warning(message: str, timestamp: bool = True):
    """Log a warning message"""
    default_logger.warning(message, timestamp)


def error(message: str, timestamp: bool = True):
    """Log an error message"""
    default_logger.error(message, timestamp)


def success(message: str, timestamp: bool = True):
    """Log a success message"""
    default_logger.success(message, timestamp)


def log(level: str, message: str, timestamp: bool = True):
    """Log a message with specified level"""
    default_logger.log(level, message, timestamp)
