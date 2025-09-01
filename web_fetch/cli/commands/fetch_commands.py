"""
Fetch commands for the extended CLI.

This module contains fetch command implementations extracted from extended.py
to improve modularity and maintainability. Each fetch command handles
data retrieval for different resource types.
"""

import asyncio
import csv
import io
import json
import sys
from pathlib import Path
from typing import Optional

import click


def create_fetch_commands(fetch_group):
    """Create and register fetch commands with the fetch group."""
    
    @fetch_group.command("rss")
    @click.argument('url')
    @click.option('--max-items', '-m', default=20, help='Maximum items to fetch')
    @click.option('--output', '-o', type=click.Path(), help='Output file path')
    @click.option('--format', 'output_format', type=click.Choice(['json', 'csv']), default='json', help='Output format')
    @click.option('--include-content', is_flag=True, help='Include full content')
    @click.pass_context
    def fetch_rss(ctx: click.Context, url: str, max_items: int, output: Optional[str], output_format: str, include_content: bool) -> None:
        """Fetch RSS feed with advanced options."""
        async def fetch_rss_resource() -> None:
            try:
                from ...convenience import fetch_rss_feed
                from ...models import ResourceConfig, RSSConfig
            except ImportError:
                click.echo("✗ RSS functionality not available")
                sys.exit(1)

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

    return fetch_group
