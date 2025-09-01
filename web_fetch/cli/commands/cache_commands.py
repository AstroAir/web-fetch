"""
Cache management commands for the extended CLI.

This module contains cache command implementations extracted from extended.py
to improve modularity and maintainability. Each cache command handles
cache operations and management.
"""

import asyncio
import sys
from typing import Optional

import click


def create_cache_commands(cache_group):
    """Create and register cache commands with the cache group."""
    
    @cache_group.command()
    @click.option('--backend', type=click.Choice(['memory', 'redis']), default='memory', help='Cache backend')
    def stats(backend: str) -> None:
        """Show detailed cache statistics."""
        async def show_cache_stats() -> None:
            try:
                from ...models import CacheBackend
                from ...convenience import create_cached_resource_manager
            except ImportError:
                click.echo("✗ Cache functionality not available")
                sys.exit(1)

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

    @cache_group.command()
    @click.option('--tag', '-t', help='Invalidate by tag')
    @click.option('--host', '-h', help='Invalidate by host')
    @click.option('--kind', '-k', type=click.Choice(['http', 'rss', 'database', 'cloud_storage']), help='Invalidate by resource kind')
    @click.confirmation_option(prompt='Are you sure you want to invalidate cache entries?')
    def invalidate(tag: Optional[str], host: Optional[str], kind: Optional[str]) -> None:
        """Invalidate cache entries by tag, host, or kind."""
        async def invalidate_cache() -> None:
            try:
                from ...convenience import create_cached_resource_manager
            except ImportError:
                click.echo("✗ Cache functionality not available")
                sys.exit(1)

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

    @cache_group.command()
    @click.confirmation_option(prompt='Are you sure you want to clear all cache entries?')
    def clear() -> None:
        """Clear all cache entries."""
        async def clear_cache() -> None:
            try:
                from ...convenience import create_cached_resource_manager
            except ImportError:
                click.echo("✗ Cache functionality not available")
                sys.exit(1)

            manager = create_cached_resource_manager()

            try:
                count = await manager.clear_all()
                click.echo(f"✓ Cleared {count} cache entries")
                await manager.cleanup()

            except Exception as e:
                click.echo(f"✗ Error clearing cache: {e}")
                sys.exit(1)

        asyncio.run(clear_cache())

    return cache_group
