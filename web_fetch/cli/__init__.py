"""
Web-Fetch CLI package.

This package provides command-line interfaces for the web-fetch library
with integrated enhanced formatting capabilities.
"""

from .main import main
from .extended import cli as extended_cli

__all__ = ["main", "extended_cli"]
