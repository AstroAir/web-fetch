#!/usr/bin/env python3
"""
Extended Web-Fetch CLI Tool

Enhanced command-line interface for testing configurations, managing credentials,
and performing operations with the extended resource types (RSS, Database,
Cloud Storage, Authenticated APIs).

This complements the existing main.py CLI with extended functionality.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import click

# Import formatting utilities
try:
    from .formatting import Formatter, create_formatter, print_banner
    FORMATTING_AVAILABLE = True
except ImportError:
    FORMATTING_AVAILABLE = False
    # Create fallback formatter
    class Formatter:
        def __init__(self, verbose=False):
            self.verbose = verbose

        def print_success(self, message):
            click.echo(click.style(f"✓ {message}", fg='green'))

        def print_error(self, message):
            click.echo(click.style(f"✗ {message}", fg='red'))

        def print_warning(self, message):
            click.echo(click.style(f"⚠ {message}", fg='yellow'))

        def print_info(self, message):
            click.echo(click.style(f"ℹ {message}", fg='blue'))

        def print_json(self, data, title=None):
            if title:
                click.echo(f"\n{title}:")
                click.echo("-" * len(title))
            click.echo(json.dumps(data, indent=2, default=str))

        def print_key_value_pairs(self, data, title=None):
            if title:
                click.echo(f"\n{title}:")
                click.echo("=" * len(title))
            for key, value in data.items():
                formatted_key = key.replace("_", " ").title()
                if isinstance(value, (dict, list)):
                    formatted_value = json.dumps(value, indent=2)
                else:
                    formatted_value = str(value)
                click.echo(f"{formatted_key:<20}: {formatted_value}")

        def create_status(self, message):
            return self

        def __enter__(self):
            click.echo(f"⏳ {getattr(self, 'message', 'Processing...')}")
            return self

        def __exit__(self, *args):
            pass

    def create_formatter(verbose=False):
        return Formatter(verbose)

    def print_banner(title, version="1.0.0"):
        click.echo(f"🌐 {title} v{version}")
        click.echo("=" * 50)

try:
    from pydantic import AnyUrl
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    AnyUrl = str

from ..models.resource import ResourceRequest, ResourceKind, ResourceConfig
from ..models.extended_resources import (
    RSSConfig, AuthenticatedAPIConfig, DatabaseConfig, CloudStorageConfig,
    DatabaseQuery, CloudStorageOperation, DatabaseType, CloudStorageProvider
)
from ..managers.cached_resource_manager import create_cached_resource_manager
from ..cache import CacheBackend
from ..monitoring import MetricBackend, create_metrics_backend, configure_metrics


@click.group()
@click.version_option()
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.pass_context
def cli(ctx: click.Context, config: Optional[str], verbose: bool) -> None:
    """🌐 Web-Fetch Extended CLI - Advanced resource fetching and management."""
    ctx.ensure_object(dict)
    ctx.obj['config_file'] = config
    ctx.obj['verbose'] = verbose
    ctx.obj['formatter'] = create_formatter(verbose=verbose)

    if verbose:
        ctx.obj['formatter'].print_info("Verbose mode enabled")


@cli.group()
def test() -> None:
    """🔍 Test configurations and connections for extended resource types."""
    pass


@cli.group()
def fetch() -> None:
    """📥 Fetch resources using extended resource types."""
    pass


@cli.group()
def cache() -> None:
    """💾 Advanced cache management operations."""
    pass


@cli.group()
def monitor() -> None:
    """📊 Monitoring and metrics for extended resources."""
    pass


@cli.group()
def config() -> None:
    """⚙️ Configuration management and validation."""
    pass


# Import and register test commands
from .commands.test_commands import create_test_commands
create_test_commands(test)






# Import and register all command modules
from .commands.fetch_commands import create_fetch_commands
from .commands.cache_commands import create_cache_commands
from .commands.monitor_commands import create_monitor_commands
from .commands.config_commands import create_config_commands

create_fetch_commands(fetch)
create_cache_commands(cache)
create_monitor_commands(monitor)
create_config_commands(config)


if __name__ == '__main__':
    cli()
