"""
Configuration commands for the extended CLI.

This module contains configuration command implementations extracted from extended.py
to improve modularity and maintainability. Each config command handles
configuration management and validation.
"""

import json
import sys
from pathlib import Path
from typing import Optional

import click


def create_config_commands(config_group):
    """Create and register config commands with the config group."""
    
    @config_group.command()
    @click.option('--config-file', '-c', type=click.Path(exists=True), help='Configuration file to validate')
    def validate(config_file: Optional[str]) -> None:
        """Validate configuration file."""
        try:
            from ...models import WebFetchConfig
        except ImportError:
            click.echo("✗ Configuration functionality not available")
            sys.exit(1)

        if not config_file:
            # Look for default config files
            default_paths = [
                Path.cwd() / "web_fetch_config.json",
                Path.cwd() / "web_fetch_config.yaml",
                Path.home() / ".web_fetch" / "config.json",
                Path.home() / ".web_fetch" / "config.yaml"
            ]
            
            config_file = None
            for path in default_paths:
                if path.exists():
                    config_file = str(path)
                    break
            
            if not config_file:
                click.echo("✗ No configuration file found. Use --config-file to specify one.")
                sys.exit(1)

        try:
            config_path = Path(config_file)
            
            if config_path.suffix.lower() == '.json':
                with open(config_path, 'r') as f:
                    config_data = json.load(f)
            elif config_path.suffix.lower() in ['.yaml', '.yml']:
                try:
                    import yaml
                    with open(config_path, 'r') as f:
                        config_data = yaml.safe_load(f)
                except ImportError:
                    click.echo("✗ YAML support not available. Install PyYAML to use YAML config files.")
                    sys.exit(1)
            else:
                click.echo("✗ Unsupported config file format. Use .json or .yaml/.yml")
                sys.exit(1)

            # Validate configuration
            config = WebFetchConfig(**config_data)
            
            click.echo(f"✓ Configuration file '{config_file}' is valid")
            click.echo(f"  Timeout: {config.timeout}s")
            click.echo(f"  Max concurrent: {config.max_concurrent}")
            click.echo(f"  Max retries: {config.max_retries}")
            click.echo(f"  Cache enabled: {config.enable_cache}")
            if config.enable_cache:
                click.echo(f"  Cache TTL: {config.cache_ttl}s")

        except Exception as e:
            click.echo(f"✗ Configuration validation failed: {e}")
            sys.exit(1)

    @config_group.command()
    @click.option('--format', 'output_format', type=click.Choice(['json', 'yaml']), default='json', help='Output format')
    def show(output_format: str) -> None:
        """Show current configuration."""
        try:
            from ...models import WebFetchConfig
        except ImportError:
            click.echo("✗ Configuration functionality not available")
            sys.exit(1)

        try:
            # Get default configuration
            config = WebFetchConfig()
            config_dict = config.dict()

            if output_format == 'json':
                click.echo(json.dumps(config_dict, indent=2, default=str))
            else:  # yaml
                try:
                    import yaml
                    click.echo(yaml.dump(config_dict, default_flow_style=False))
                except ImportError:
                    click.echo("✗ YAML support not available. Install PyYAML to use YAML output.")
                    sys.exit(1)

        except Exception as e:
            click.echo(f"✗ Error showing configuration: {e}")
            sys.exit(1)

    @config_group.command()
    @click.argument('key')
    @click.argument('value')
    @click.option('--config-file', '-c', type=click.Path(), help='Configuration file to update')
    def set(key: str, value: str, config_file: Optional[str]) -> None:
        """Set configuration value."""
        try:
            from ...models import WebFetchConfig
        except ImportError:
            click.echo("✗ Configuration functionality not available")
            sys.exit(1)

        if not config_file:
            config_file = str(Path.cwd() / "web_fetch_config.json")

        try:
            config_path = Path(config_file)
            
            # Load existing config or create new one
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config_data = json.load(f)
            else:
                config_data = {}

            # Convert value to appropriate type
            if value.lower() in ['true', 'false']:
                value = value.lower() == 'true'
            elif value.isdigit():
                value = int(value)
            elif '.' in value and value.replace('.', '').isdigit():
                value = float(value)

            # Set the value
            config_data[key] = value

            # Validate the updated configuration
            config = WebFetchConfig(**config_data)

            # Save the configuration
            with open(config_path, 'w') as f:
                json.dump(config_data, f, indent=2, default=str)

            click.echo(f"✓ Set {key} = {value} in {config_file}")

        except Exception as e:
            click.echo(f"✗ Error setting configuration: {e}")
            sys.exit(1)

    return config_group
