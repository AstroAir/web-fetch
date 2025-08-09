"""
Backward-compatibility shim for FTP connection module.

Some external code and legacy tests import `web_fetch.ftp_connection` directly.
The implementation has moved to `web_fetch.ftp.connection`. This module re-exports
key symbols and ensures patch targets like `web_fetch.ftp_connection.aioftp.Client`
continue to work.
"""
from __future__ import annotations

# Re-export the public API from the new location
from .ftp.connection import FTPConnectionPool as FTPConnectionPool  # noqa: F401

# Expose the aioftp module under this namespace so tests can patch it via
# `web_fetch.ftp_connection.aioftp.Client`
import aioftp as aioftp  # noqa: F401

__all__ = [
    "FTPConnectionPool",
    "aioftp",
]

