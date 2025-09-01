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
from pydantic import AnyUrl

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
    """Web-Fetch Extended CLI - Advanced resource fetching and management."""
    ctx.ensure_object(dict)
    ctx.obj['config_file'] = config
    ctx.obj['verbose'] = verbose

    if verbose:
        click.echo("Verbose mode enabled")


@cli.group()
def test() -> None:
    """Test configurations and connections for extended resource types."""
    pass


@cli.group()
def fetch() -> None:
    """Fetch resources using extended resource types."""
    pass


@cli.group()
def cache() -> None:
    """Advanced cache management operations."""
    pass


@cli.group()
def monitor() -> None:
    """Monitoring and metrics for extended resources."""
    pass


@cli.group()
def config() -> None:
    """Configuration management and validation."""
    pass


# Test commands for extended resource types
@test.command()
@click.option('--url', '-u', required=True, help='RSS feed URL to test')
@click.option('--max-items', '-m', default=10, help='Maximum items to fetch')
@click.option('--include-content', is_flag=True, help='Include full content')
@click.pass_context
def rss(ctx: click.Context, url: str, max_items: int, include_content: bool) -> None:
    """Test RSS/Atom feed fetching with advanced options."""
    async def test_rss() -> None:
        from ..convenience import fetch_rss_feed

        config = ResourceConfig(enable_cache=False)
        rss_config = RSSConfig(
            max_items=max_items,
            include_content=include_content,
            validate_dates=True,
            follow_redirects=True
        )

        click.echo(f"Testing RSS feed: {url}")
        click.echo(f"Max items: {max_items}, Include content: {include_content}")

        try:
            result = await fetch_rss_feed(url, max_items=max_items, include_content=include_content, config=config)

            if result.is_success:
                feed_data = result.content
                click.echo(f"✓ Successfully fetched RSS feed")
                click.echo(f"  Title: {feed_data.get('title', 'N/A')}")
                click.echo(f"  Description: {feed_data.get('description', 'N/A')[:100]}...")
                click.echo(f"  Items: {len(feed_data.get('items', []))}")
                click.echo(f"  Language: {feed_data.get('language', 'N/A')}")
                click.echo(f"  Last updated: {feed_data.get('last_build_date', 'N/A')}")

                if ctx.obj['verbose'] and feed_data.get('items'):
                    click.echo("\nRecent items:")
                    for i, item in enumerate(feed_data['items'][:3]):
                        click.echo(f"  {i+1}. {item.get('title', 'No title')}")
                        click.echo(f"     Published: {item.get('pub_date', 'N/A')}")
                        click.echo(f"     Link: {item.get('link', 'N/A')}")
                        if include_content and item.get('content'):
                            content_preview = item['content'][:100] + "..." if len(item['content']) > 100 else item['content']
                            click.echo(f"     Content: {content_preview}")
            else:
                click.echo(f"✗ Failed to fetch RSS feed: {result.error}")
                sys.exit(1)

        except Exception as e:
            click.echo(f"✗ Error testing RSS feed: {e}")
            sys.exit(1)

    asyncio.run(test_rss())


@test.command()
@click.option('--host', '-h', required=True, help='Database host')
@click.option('--port', '-p', default=5432, help='Database port')
@click.option('--database', '-d', required=True, help='Database name')
@click.option('--username', '-u', required=True, help='Database username')
@click.option('--password', required=True, prompt=True, hide_input=True, help='Database password')
@click.option('--type', 'db_type', type=click.Choice(['postgresql', 'mysql', 'mongodb']), default='postgresql', help='Database type')
@click.option('--query', '-q', help='Custom test query')
@click.option('--ssl', is_flag=True, help='Use SSL connection')
def database(host: str, port: int, database: str, username: str, password: str, db_type: str, query: Optional[str], ssl: bool) -> None:
    """Test database connection with advanced options."""
    async def test_database() -> None:
        from ..convenience import execute_database_query
        from pydantic import SecretStr

        # Map string to enum
        db_type_map = {
            'postgresql': DatabaseType.POSTGRESQL,
            'mysql': DatabaseType.MYSQL,
            'mongodb': DatabaseType.MONGODB
        }

        extra_params = {}
        if ssl:
            if db_type == 'postgresql':
                extra_params['ssl'] = 'require'
            elif db_type == 'mysql':
                extra_params['ssl_disabled'] = 'false'

        db_config = DatabaseConfig(
            database_type=db_type_map[db_type],
            host=host,
            port=port,
            database=database,
            username=username,
            password=SecretStr(password),
            connection_timeout=10.0,
            query_timeout=30.0,
            extra_params=extra_params
        )

        # Use custom query or default test query
        if query:
            test_query = DatabaseQuery(query=query, fetch_mode="all")
        else:
            if db_type == 'postgresql':
                test_query = DatabaseQuery(
                    query="SELECT version() as version, current_database() as database, current_user as user",
                    fetch_mode="one"
                )
            elif db_type == 'mysql':
                test_query = DatabaseQuery(
                    query="SELECT VERSION() as version, DATABASE() as database, USER() as user",
                    fetch_mode="one"
                )
            else:  # mongodb
                test_query = DatabaseQuery(
                    query='{"collection": "admin", "operation": "command", "command": {"buildInfo": 1}}',
                    fetch_mode="one"
                )

        click.echo(f"Testing {db_type} connection to {host}:{port}/{database}")
        click.echo(f"SSL: {'enabled' if ssl else 'disabled'}")

        try:
            result = await execute_database_query("", "", db_config)

            if result.is_success:
                click.echo("✓ Database connection successful")
                if result.content and result.content.get('data'):
                    click.echo("  Connection details:")
                    data = result.content['data']
                    if isinstance(data, dict):
                        for key, value in data.items():
                            click.echo(f"    {key}: {value}")
                    else:
                        click.echo(f"    Result: {data}")
                click.echo(f"  Query time: {result.response_time:.3f}s")
                click.echo(f"  Rows returned: {result.content.get('row_count', 0)}")
            else:
                click.echo(f"✗ Database connection failed: {result.error}")
                sys.exit(1)

        except Exception as e:
            click.echo(f"✗ Error testing database: {e}")
            sys.exit(1)

    asyncio.run(test_database())


@test.command()
@click.option('--provider', type=click.Choice(['s3', 'gcs', 'azure']), required=True, help='Cloud storage provider')
@click.option('--bucket', '-b', required=True, help='Bucket/container name')
@click.option('--access-key', required=True, help='Access key/account name')
@click.option('--secret-key', required=True, prompt=True, hide_input=True, help='Secret key/account key')
@click.option('--region', '-r', help='Region (for S3/GCS)')
@click.option('--prefix', '-p', help='Prefix to list objects')
def storage(provider: str, bucket: str, access_key: str, secret_key: str, region: Optional[str], prefix: Optional[str]) -> None:
    """Test cloud storage connection."""
    async def test_storage() -> None:
        from ..convenience import cloud_storage_operation
        from pydantic import SecretStr

        # Map provider to enum
        provider_map = {
            's3': CloudStorageProvider.AWS_S3,
            'gcs': CloudStorageProvider.GOOGLE_CLOUD,
            'azure': CloudStorageProvider.AZURE_BLOB
        }

        storage_config = CloudStorageConfig(
            provider=provider_map[provider],
            bucket_name=bucket,
            access_key=SecretStr(access_key),
            secret_key=SecretStr(secret_key),
            region=region or 'us-east-1'
        )

        operation = CloudStorageOperation(
            operation="list",
            prefix=prefix or ""
        )

        click.echo(f"Testing {provider} connection to bucket: {bucket}")
        if region:
            click.echo(f"Region: {region}")
        if prefix:
            click.echo(f"Prefix: {prefix}")

        try:
            result = await cloud_storage_operation("", "list", storage_config)

            if result.is_success:
                objects = result.content.get('objects', [])
                click.echo("✓ Cloud storage connection successful")
                click.echo(f"  Objects found: {len(objects)}")

                if objects:
                    total_size = sum(obj.get('size', 0) for obj in objects)
                    click.echo(f"  Total size: {total_size:,} bytes")

                    click.echo("  Recent objects:")
                    for i, obj in enumerate(objects[:5]):
                        size_mb = obj.get('size', 0) / (1024 * 1024)
                        click.echo(f"    {i+1}. {obj.get('key', 'N/A')} ({size_mb:.2f} MB)")
            else:
                click.echo(f"✗ Cloud storage connection failed: {result.error}")
                sys.exit(1)

        except Exception as e:
            click.echo(f"✗ Error testing cloud storage: {e}")
            sys.exit(1)

    asyncio.run(test_storage())


# Fetch commands for extended resources
@fetch.command("rss")
@click.argument('url')
@click.option('--max-items', '-m', default=20, help='Maximum items to fetch')
@click.option('--output', '-o', type=click.Path(), help='Output file path')
@click.option('--format', 'output_format', type=click.Choice(['json', 'csv']), default='json', help='Output format')
@click.option('--include-content', is_flag=True, help='Include full content')
@click.pass_context
def fetch_rss(ctx: click.Context, url: str, max_items: int, output: Optional[str], output_format: str, include_content: bool) -> None:
    """Fetch RSS feed with advanced options."""
    async def fetch_rss_resource() -> None:
        from ..convenience import fetch_rss_feed
        import csv

        config = ResourceConfig(enable_cache=True, cache_ttl_seconds=1800)
        rss_config = RSSConfig(
            max_items=max_items,
            include_content=include_content,
            validate_dates=True
        )

        click.echo(f"Fetching RSS feed: {url}")

        try:
            result = await fetch_rss_feed(url, max_items=max_items, include_content=include_content, config=config)

            if result.is_success:
                feed_data = result.content
                items = feed_data.get('items', [])

                click.echo(f"✓ Successfully fetched RSS feed")
                click.echo(f"  Title: {feed_data.get('title', 'N/A')}")
                click.echo(f"  Items: {len(items)}")

                # Prepare output
                if output_format == 'json':
                    output_data = {
                        "url": url,
                        "feed": feed_data,
                        "metadata": result.metadata,
                        "fetched_at": result.timestamp.isoformat()
                    }
                    output_text = json.dumps(output_data, indent=2, default=str)
                else:  # CSV
                    if items:
                        fieldnames = ['title', 'link', 'pub_date', 'description', 'author']
                        if include_content:
                            fieldnames.append('content')

                        import io
                        output_buffer = io.StringIO()
                        writer = csv.DictWriter(output_buffer, fieldnames=fieldnames)
                        writer.writeheader()

                        for item in items:
                            row = {field: item.get(field, '') for field in fieldnames}
                            writer.writerow(row)

                        output_text = output_buffer.getvalue()
                    else:
                        output_text = "No items found"

                # Save or display output
                if output:
                    Path(output).write_text(output_text)
                    click.echo(f"  Output saved to: {output}")
                else:
                    if ctx.obj['verbose']:
                        click.echo("\nRecent items:")
                        for i, item in enumerate(items[:5]):
                            click.echo(f"  {i+1}. {item.get('title', 'No title')}")
                            click.echo(f"     {item.get('link', 'No link')}")
            else:
                click.echo(f"✗ Failed to fetch RSS feed: {result.error}")
                sys.exit(1)

        except Exception as e:
            click.echo(f"✗ Error fetching RSS feed: {e}")
            sys.exit(1)

    asyncio.run(fetch_rss_resource())


# Cache management commands
@cache.command()
@click.option('--backend', type=click.Choice(['memory', 'redis']), default='memory', help='Cache backend')
def stats(backend: str) -> None:
    """Show detailed cache statistics."""
    async def show_cache_stats() -> None:
        cache_backend = CacheBackend.MEMORY if backend == 'memory' else CacheBackend.REDIS

        try:
            manager = create_cached_resource_manager(
                cache_backend=cache_backend,
                cache_config={"redis_url": "redis://localhost:6379"} if backend == 'redis' else {}
            )

            stats = manager.get_cache_stats()

            click.echo(f"Cache Statistics ({backend} backend):")
            click.echo(f"  Hit rate: {stats.get('hit_rate', 0):.1%}")
            click.echo(f"  Total requests: {stats.get('total_requests', 0)}")
            click.echo(f"  Cache hits: {stats.get('hits', 0)}")
            click.echo(f"  Cache misses: {stats.get('misses', 0)}")
            click.echo(f"  Warming patterns: {stats.get('warming_patterns', 0)}")
            click.echo(f"  Warming enabled: {stats.get('warming_enabled', False)}")
            click.echo(f"  Invalidation enabled: {stats.get('invalidation_enabled', False)}")

            await manager.cleanup()

        except Exception as e:
            click.echo(f"✗ Error getting cache stats: {e}")
            sys.exit(1)

    asyncio.run(show_cache_stats())


@cache.command()
@click.option('--tag', '-t', help='Invalidate by tag')
@click.option('--host', '-h', help='Invalidate by host')
@click.option('--kind', '-k', type=click.Choice(['http', 'rss', 'database', 'cloud_storage']), help='Invalidate by resource kind')
@click.confirmation_option(prompt='Are you sure you want to invalidate cache entries?')
def invalidate(tag: Optional[str], host: Optional[str], kind: Optional[str]) -> None:
    """Invalidate cache entries by tag, host, or kind."""
    async def invalidate_cache() -> None:
        manager = create_cached_resource_manager()

        try:
            total_invalidated = 0

            if tag:
                count = await manager.invalidate_by_tag(tag)
                click.echo(f"Invalidated {count} entries by tag: {tag}")
                total_invalidated += count

            if host:
                count = await manager.invalidate_by_host(host)
                click.echo(f"Invalidated {count} entries by host: {host}")
                total_invalidated += count

            if kind:
                count = await manager.invalidate_by_kind(kind)
                click.echo(f"Invalidated {count} entries by kind: {kind}")
                total_invalidated += count

            if not any([tag, host, kind]):
                click.echo("No invalidation criteria specified")
                return

            click.echo(f"✓ Total entries invalidated: {total_invalidated}")

            await manager.cleanup()

        except Exception as e:
            click.echo(f"✗ Error invalidating cache: {e}")
            sys.exit(1)

    asyncio.run(invalidate_cache())


# Monitoring commands
@monitor.command()
@click.option('--backend', type=click.Choice(['memory', 'console', 'prometheus']), default='memory', help='Metrics backend')
def status(backend: str) -> None:
    """Show comprehensive monitoring status."""
    from ..monitoring import get_metrics_collector

    try:
        collector = get_metrics_collector()
        stats = collector.get_summary()

        click.echo(f"Monitoring Status ({backend} backend):")
        click.echo(f"  Uptime: {stats.get('uptime_seconds', 0):.1f} seconds")
        click.echo(f"  Total requests: {stats.get('total_requests', 0)}")
        click.echo(f"  Total errors: {stats.get('total_errors', 0)}")
        click.echo(f"  Error rate: {stats.get('error_rate', 0):.1%}")
        click.echo(f"  Cache hits: {stats.get('cache_hits', 0)}")
        click.echo(f"  Cache misses: {stats.get('cache_misses', 0)}")
        click.echo(f"  Cache hit rate: {stats.get('cache_hit_rate', 0):.1%}")
        click.echo(f"  Requests per second: {stats.get('requests_per_second', 0):.2f}")
        click.echo(f"  Active warming tasks: {stats.get('active_warming_tasks', 0)}")

    except Exception as e:
        click.echo(f"✗ Error getting monitoring status: {e}")
        sys.exit(1)


if __name__ == '__main__':
    cli()
