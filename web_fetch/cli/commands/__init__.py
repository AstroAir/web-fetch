"""
CLI commands package for web_fetch.

This package contains modular command implementations for the extended CLI.
Each command group is organized into separate modules for better maintainability.
"""

from .test_commands import create_test_commands
from .fetch_commands import create_fetch_commands
from .cache_commands import create_cache_commands
from .monitor_commands import create_monitor_commands
from .config_commands import create_config_commands

__all__ = [
    'create_test_commands',
    'create_fetch_commands',
    'create_cache_commands',
    'create_monitor_commands',
    'create_config_commands'
]
