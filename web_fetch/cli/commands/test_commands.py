"""
Test commands for the extended CLI.

This module contains test command implementations extracted from extended.py
to improve modularity and maintainability. Each test command validates
connectivity and functionality for different resource types.
"""

import asyncio
import sys
from typing import Optional

import click


def create_test_commands(test_group):
    """Create and register test commands with the test group."""
    
    @test_group.command()
    @click.option('--url', '-u', required=True, help='RSS feed URL to test')
    @click.option('--max-items', '-m', default=10, help='Maximum items to fetch')
    @click.option('--include-content', is_flag=True, help='Include full content')
    @click.pass_context
    def rss(ctx: click.Context, url: str, max_items: int, include_content: bool) -> None:
        """Test RSS/Atom feed fetching with advanced options."""
        async def test_rss() -> None:
            try:
                from ...convenience import fetch_rss_feed
                from ...models import ResourceConfig, RSSConfig
            except ImportError:
                click.echo("✗ RSS functionality not available")
                sys.exit(1)

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

    @test_group.command()
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
            try:
                from ...convenience import execute_database_query
                from ...models import DatabaseType, DatabaseConfig
                from pydantic import SecretStr
            except ImportError:
                click.echo("✗ Database functionality not available")
                sys.exit(1)

            # Map string to enum
            db_type_map = {
                'postgresql': DatabaseType.POSTGRESQL,
                'mysql': DatabaseType.MYSQL,
                'mongodb': DatabaseType.MONGODB
            }

            # Default test queries
            default_queries = {
                'postgresql': 'SELECT version();',
                'mysql': 'SELECT VERSION();',
                'mongodb': 'db.runCommand({buildInfo: 1})'
            }

            test_query = query or default_queries.get(db_type, 'SELECT 1;')

            config = DatabaseConfig(
                host=host,
                port=port,
                database=database,
                username=username,
                password=SecretStr(password),
                database_type=db_type_map[db_type],
                use_ssl=ssl,
                connection_timeout=30
            )

            click.echo(f"Testing {db_type} database connection:")
            click.echo(f"  Host: {host}:{port}")
            click.echo(f"  Database: {database}")
            click.echo(f"  Username: {username}")
            click.echo(f"  SSL: {'Yes' if ssl else 'No'}")
            click.echo(f"  Test query: {test_query}")

            try:
                result = await execute_database_query(config, test_query)

                if result.is_success:
                    click.echo(f"✓ Database connection successful")
                    click.echo(f"  Query executed successfully")
                    click.echo(f"  Rows returned: {len(result.content) if isinstance(result.content, list) else 'N/A'}")
                    click.echo(f"  Response time: {result.response_time:.2f}s")

                    if result.content and len(str(result.content)) < 500:
                        click.echo(f"  Result preview: {result.content}")
                else:
                    click.echo(f"✗ Database connection failed: {result.error}")
                    sys.exit(1)

            except Exception as e:
                click.echo(f"✗ Error testing database: {e}")
                sys.exit(1)

        asyncio.run(test_database())

    @test_group.command()
    @click.option('--provider', type=click.Choice(['s3', 'gcs', 'azure']), required=True, help='Cloud storage provider')
    @click.option('--bucket', '-b', required=True, help='Bucket/container name')
    @click.option('--access-key', required=True, help='Access key/account name')
    @click.option('--secret-key', required=True, prompt=True, hide_input=True, help='Secret key/account key')
    @click.option('--region', '-r', help='Region (for S3/GCS)')
    @click.option('--prefix', '-p', help='Prefix to list objects')
    def storage(provider: str, bucket: str, access_key: str, secret_key: str, region: Optional[str], prefix: Optional[str]) -> None:
        """Test cloud storage connection."""
        async def test_storage() -> None:
            try:
                from ...convenience import cloud_storage_operation
                from ...models import CloudStorageProvider, CloudStorageConfig, CloudStorageOperation
                from pydantic import SecretStr
            except ImportError:
                click.echo("✗ Cloud storage functionality not available")
                sys.exit(1)

            # Map provider to enum
            provider_map = {
                's3': CloudStorageProvider.S3,
                'gcs': CloudStorageProvider.GCS,
                'azure': CloudStorageProvider.AZURE
            }

            config = CloudStorageConfig(
                provider=provider_map[provider],
                bucket_name=bucket,
                access_key=access_key,
                secret_key=SecretStr(secret_key),
                region=region
            )

            click.echo(f"Testing {provider.upper()} cloud storage connection:")
            click.echo(f"  Provider: {provider.upper()}")
            click.echo(f"  Bucket: {bucket}")
            click.echo(f"  Region: {region or 'Default'}")
            click.echo(f"  Prefix: {prefix or 'None'}")

            try:
                # Test with list operation
                result = await cloud_storage_operation(
                    config,
                    CloudStorageOperation.LIST,
                    prefix=prefix,
                    max_keys=10
                )

                if result.is_success:
                    objects = result.content.get('objects', [])
                    click.echo(f"✓ Cloud storage connection successful")
                    click.echo(f"  Objects found: {len(objects)}")
                    click.echo(f"  Response time: {result.response_time:.2f}s")

                    if objects:
                        click.echo("  Recent objects:")
                        for obj in objects[:5]:
                            click.echo(f"    - {obj.get('key', 'N/A')} ({obj.get('size', 0)} bytes)")
                else:
                    click.echo(f"✗ Cloud storage connection failed: {result.error}")
                    sys.exit(1)

            except Exception as e:
                click.echo(f"✗ Error testing cloud storage: {e}")
                sys.exit(1)

        asyncio.run(test_storage())

    return test_group
