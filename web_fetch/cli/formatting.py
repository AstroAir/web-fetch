#!/usr/bin/env python3
"""
Formatting utilities for web-fetch CLI tools.

This module provides shared formatting functions and components
used across CLI modules with rich formatting when available and
graceful fallbacks when not available.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Rich imports with fallbacks
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        SpinnerColumn,
        TaskID,
        TextColumn,
        TimeElapsedColumn,
        TimeRemainingColumn,
    )
    from rich.status import Status
    from rich.syntax import Syntax
    from rich.table import Table
    from rich.text import Text
    from rich.tree import Tree
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    # Fallback classes for when rich is not available
    class Console:
        def print(self, *args, style=None, **kwargs):
            print(*args)
    
    class Panel:
        def __init__(self, content, title=None, **kwargs):
            self.content = str(content)
            self.title = title
    
    class Table:
        def __init__(self, title=None, **kwargs):
            self.title = title
            self.columns = []
            self.rows = []
        
        def add_column(self, name, **kwargs):
            self.columns.append(name)
        
        def add_row(self, *values):
            self.rows.append(values)
    
    class Progress:
        def __init__(self, *args, **kwargs):
            pass
        
        def __enter__(self):
            return self
        
        def __exit__(self, *args):
            pass
        
        def add_task(self, description, total=None):
            print(f"Starting: {description}")
            return 0
        
        def advance(self, task_id):
            pass
    
    class Status:
        def __init__(self, message, **kwargs):
            self.message = message
        
        def __enter__(self):
            print(f"⏳ {self.message}")
            return self
        
        def __exit__(self, *args):
            pass


# Global console instance
console = Console()


class Formatter:
    """Formatting utilities for CLI output with rich support and fallbacks."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.console = console
        self.rich_available = RICH_AVAILABLE
    
    def print_header(self, title: str, subtitle: Optional[str] = None) -> None:
        """Print a formatted header with title and optional subtitle."""
        if self.rich_available:
            text = Text(title, style="bold blue")
            if subtitle:
                text.append(f"\n{subtitle}", style="dim")
            
            panel = Panel(
                text,
                border_style="blue",
                padding=(1, 2),
            )
            self.console.print(panel)
        else:
            print(f"\n🌐 {title}")
            if subtitle:
                print(f"   {subtitle}")
            print("=" * 50)
    
    def print_success(self, message: str) -> None:
        """Print a success message with green checkmark."""
        if self.rich_available:
            self.console.print(f"✓ {message}", style="bold green")
        else:
            print(f"✓ {message}")
    
    def print_error(self, message: str) -> None:
        """Print an error message with red X."""
        if self.rich_available:
            self.console.print(f"✗ {message}", style="bold red")
        else:
            print(f"✗ {message}")
    
    def print_warning(self, message: str) -> None:
        """Print a warning message with yellow exclamation."""
        if self.rich_available:
            self.console.print(f"⚠ {message}", style="bold yellow")
        else:
            print(f"⚠ {message}")
    
    def print_info(self, message: str) -> None:
        """Print an info message with blue info icon."""
        if self.rich_available:
            self.console.print(f"ℹ {message}", style="bold blue")
        else:
            print(f"ℹ {message}")
    
    def print_json(self, data: Any, title: Optional[str] = None) -> None:
        """Print JSON data with syntax highlighting."""
        json_str = json.dumps(data, indent=2, default=str)
        
        if self.rich_available:
            syntax = Syntax(json_str, "json", theme="monokai", line_numbers=True)
            
            if title:
                panel = Panel(syntax, title=title, border_style="cyan")
                self.console.print(panel)
            else:
                self.console.print(syntax)
        else:
            if title:
                print(f"\n{title}:")
                print("-" * len(title))
            print(json_str)
    
    def print_table(self, data: List[Dict[str, Any]], title: Optional[str] = None) -> None:
        """Print tabular data in a rich table."""
        if not data:
            self.print_warning("No data to display")
            return
        
        if self.rich_available:
            table = Table(title=title, show_header=True, header_style="bold magenta")
            
            # Add columns based on first row keys
            for key in data[0].keys():
                table.add_column(key.replace("_", " ").title(), style="cyan")
            
            # Add rows
            for row in data:
                table.add_row(*[str(value) for value in row.values()])
            
            self.console.print(table)
        else:
            if title:
                print(f"\n{title}:")
                print("=" * len(title))
            
            # Print headers
            headers = [key.replace("_", " ").title() for key in data[0].keys()]
            print(" | ".join(f"{h:<15}" for h in headers))
            print("-" * (len(headers) * 17))
            
            # Print rows
            for row in data:
                values = [str(value)[:15] for value in row.values()]
                print(" | ".join(f"{v:<15}" for v in values))
    
    def print_key_value_pairs(self, data: Dict[str, Any], title: Optional[str] = None) -> None:
        """Print key-value pairs in a formatted table."""
        if self.rich_available:
            table = Table(title=title, show_header=True, header_style="bold magenta")
            table.add_column("Property", style="cyan", no_wrap=True)
            table.add_column("Value", style="white")
            
            for key, value in data.items():
                # Format key
                formatted_key = key.replace("_", " ").title()
                
                # Format value
                if isinstance(value, (dict, list)):
                    formatted_value = json.dumps(value, indent=2)
                else:
                    formatted_value = str(value)
                
                table.add_row(formatted_key, formatted_value)
            
            self.console.print(table)
        else:
            if title:
                print(f"\n{title}:")
                print("=" * len(title))
            
            for key, value in data.items():
                formatted_key = key.replace("_", " ").title()
                if isinstance(value, (dict, list)):
                    formatted_value = json.dumps(value, indent=2)
                else:
                    formatted_value = str(value)
                print(f"{formatted_key:<20}: {formatted_value}")
    
    def create_progress_bar(self, description: str = "Processing") -> Progress:
        """Create a rich progress bar for operations."""
        if self.rich_available:
            return Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                TextColumn("•"),
                TimeElapsedColumn(),
                TextColumn("•"),
                TimeRemainingColumn(),
                console=self.console,
            )
        else:
            return Progress()
    
    def create_status(self, message: str) -> Status:
        """Create a rich status spinner."""
        return Status(message, console=self.console, spinner="dots")
    
    def print_url_result(self, url: str, result: Dict[str, Any], format_type: str = "summary") -> None:
        """Print URL fetch result in specified format."""
        if format_type == "json":
            self.print_json(result, f"Result for {url}")
        elif format_type == "detailed":
            self._print_detailed_result(url, result)
        else:  # summary
            self._print_summary_result(url, result)
    
    def _print_summary_result(self, url: str, result: Dict[str, Any]) -> None:
        """Print a summary of the URL fetch result."""
        status_code = result.get("status_code", "Unknown")
        content_type = result.get("content_type", "Unknown")
        success = result.get("success", False)
        
        # Status styling
        if success:
            status_style = "bold green"
            status_icon = "✓"
        else:
            status_style = "bold red"
            status_icon = "✗"
        
        if self.rich_available:
            # Create summary table
            table = Table(show_header=False, box=None, padding=(0, 1))
            table.add_column("Property", style="cyan", no_wrap=True)
            table.add_column("Value")
            
            table.add_row("URL", url)
            table.add_row("Status", f"{status_icon} {status_code}", style=status_style)
            table.add_row("Content Type", content_type)
            
            if "content_length" in result:
                table.add_row("Content Length", str(result["content_length"]))
            
            if "response_time" in result:
                table.add_row("Response Time", f"{result['response_time']:.2f}s")
            
            self.console.print(table)
            self.console.print()  # Add spacing
        else:
            print(f"URL: {url}")
            print(f"Status: {status_icon} {status_code}")
            print(f"Content Type: {content_type}")
            if "content_length" in result:
                print(f"Content Length: {result['content_length']}")
            if "response_time" in result:
                print(f"Response Time: {result['response_time']:.2f}s")
            print()
    
    def _print_detailed_result(self, url: str, result: Dict[str, Any]) -> None:
        """Print detailed URL fetch result."""
        # Main result panel
        self.print_key_value_pairs(
            {
                "url": result.get("url", url),
                "status_code": result.get("status_code", "Unknown"),
                "success": result.get("success", False),
                "content_type": result.get("content_type", "Unknown"),
                "content_length": result.get("content_length", "Unknown"),
                "response_time": f"{result.get('response_time', 0):.2f}s",
            },
            title="Request Details"
        )
        
        # Headers
        if "headers" in result and result["headers"]:
            self.print_key_value_pairs(result["headers"], title="Response Headers")
        
        # Metadata
        if "metadata" in result and result["metadata"]:
            self.print_json(result["metadata"], title="Metadata")
        
        # Error details
        if "error" in result and result["error"]:
            self.print_error(f"Error: {result['error']}")


def create_formatter(verbose: bool = False) -> Formatter:
    """Create a Formatter instance."""
    return Formatter(verbose=verbose)


def print_banner(title: str, version: str = "1.0.0") -> None:
    """Print application banner."""
    if RICH_AVAILABLE:
        banner_text = Text()
        banner_text.append("🌐 ", style="bold blue")
        banner_text.append(title, style="bold white")
        banner_text.append(f" v{version}", style="dim white")
        
        panel = Panel(
            banner_text,
            border_style="blue",
            padding=(1, 2),
        )
        console.print(panel)
    else:
        print(f"🌐 {title} v{version}")
        print("=" * 50)


def print_help_footer() -> None:
    """Print help footer with additional information."""
    if RICH_AVAILABLE:
        footer_text = Text()
        footer_text.append("💡 Tip: ", style="bold yellow")
        footer_text.append("Use ", style="dim")
        footer_text.append("--verbose", style="bold cyan")
        footer_text.append(" for detailed output and ", style="dim")
        footer_text.append("--help", style="bold cyan")
        footer_text.append(" for command-specific help", style="dim")
        
        console.print(footer_text)
        console.print()
    else:
        print("💡 Tip: Use --verbose for detailed output and --help for command-specific help")
        print()
