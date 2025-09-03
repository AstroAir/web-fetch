"""
Utility functions for CLI operations.

This module contains utility functions extracted from main.py to improve
modularity and maintainability. Functions handle common CLI tasks like
header parsing and file loading.
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional


def parse_headers(header_strings: Optional[List[str]]) -> Dict[str, str]:
    """
    Parse header strings into a dictionary.

    Converts command-line header arguments in "key:value" format into
    a dictionary suitable for HTTP requests.

    Args:
        header_strings: List of header strings in "key:value" format,
                       or None if no headers provided

    Returns:
        Dictionary with header names as keys and values as strings.
        Empty dict if no valid headers provided.

    Note:
        Invalid header formats are logged to stderr but don't cause
        the function to fail. Only valid headers are included in result.

    Example:
        ```python
        headers = parse_headers(["Content-Type:application/json", "Authorization:Bearer token"])
        # Returns: {"Content-Type": "application/json", "Authorization": "Bearer token"}
        ```
    """
    headers = {}
    if header_strings:
        for header_string in header_strings:
            if ":" in header_string:
                key, value = header_string.split(":", 1)
                headers[key.strip()] = value.strip()
            else:
                print(f"Warning: Invalid header format: {header_string}", file=sys.stderr)
    return headers


def load_urls_from_file(file_path: Path) -> List[str]:
    """
    Load URLs from a text file.

    Reads URLs from a text file, one per line. Supports comments (lines
    starting with #) and automatically filters out empty lines.

    Args:
        file_path: Path to the text file containing URLs

    Returns:
        List of URL strings found in the file

    Raises:
        SystemExit: If file cannot be read or doesn't exist

    Note:
        - Empty lines are ignored
        - Lines starting with # are treated as comments and ignored
        - Leading/trailing whitespace is stripped from URLs

    Example file format:
        ```
        # API endpoints
        https://api.example.com/users
        https://api.example.com/posts

        # Static resources
        https://cdn.example.com/image.jpg
        ```
    """
    try:
        with open(file_path, "r") as f:
            urls = [
                line.strip() for line in f if line.strip() and not line.startswith("#")
            ]
        return urls
    except FileNotFoundError:
        print(f"✗ Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error reading file {file_path}: {e}", file=sys.stderr)
        sys.exit(1)
