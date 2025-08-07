"""
Configuration loader for web_fetch.

This module handles loading configuration from various sources including
environment variables, configuration files, and command-line arguments.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

try:
    import yaml

    HAS_YAML = True
except Exception:
    yaml = None
    HAS_YAML = False

from .models import Environment, GlobalConfig


class ConfigLoader:
    """Configuration loader with support for multiple sources."""

    def __init__(self) -> None:
        """Initialize configuration loader."""
        self.config_paths = [
            Path("web_fetch.yaml"),
            Path("web_fetch.yml"),
            Path("web_fetch.json"),
            Path("config/web_fetch.yaml"),
            Path("config/web_fetch.yml"),
            Path("config/web_fetch.json"),
            Path.home() / ".web_fetch" / "config.yaml",
            Path.home() / ".web_fetch" / "config.yml",
            Path.home() / ".web_fetch" / "config.json",
        ]

        # Environment variable prefix
        self.env_prefix = "WEB_FETCH_"

    def load_config(
        self,
        config_file: Optional[Union[str, Path]] = None,
        environment: Optional[Environment] = None,
    ) -> GlobalConfig:
        """
        Load configuration from all available sources.

        Args:
            config_file: Specific config file to load
            environment: Target environment

        Returns:
            GlobalConfig instance with merged configuration
        """
        # Start with default configuration
        config_data: Dict[str, Any] = {}

        # Load from file
        file_config = self._load_from_file(config_file)
        if file_config:
            config_data.update(file_config)

        # Load from environment variables
        env_config = self._load_from_environment()
        if env_config:
            config_data = self._deep_merge(config_data, env_config)

        # Apply environment-specific overrides
        if environment:
            config_data.setdefault("environment", {})["environment"] = environment.value

        # Create and return GlobalConfig
        return GlobalConfig(**config_data)

    def _load_from_file(
        self, config_file: Optional[Union[str, Path]] = None
    ) -> Optional[Dict[str, Any]]:
        """Load configuration from file."""
        if config_file:
            # Use specific file
            config_path = Path(config_file)
            if config_path.exists():
                return self._parse_config_file(config_path)
        else:
            # Search for config files
            for config_path in self.config_paths:
                if config_path.exists():
                    return self._parse_config_file(config_path)

        return None

    def _parse_config_file(self, config_path: Path) -> Dict[str, Any]:
        """Parse configuration file based on extension."""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                suffix = config_path.suffix.lower()
                if suffix in (".yaml", ".yml"):
                    if not HAS_YAML or yaml is None:
                        raise ValueError(
                            "PyYAML is required for YAML config files. Install with: pip install PyYAML"
                        )
                    return yaml.safe_load(f) or {}
                elif suffix == ".json":
                    return json.load(f) or {}
                else:
                    raise ValueError(
                        f"Unsupported config file format: {config_path.suffix}"
                    )
        except Exception as e:
            raise ValueError(f"Failed to parse config file {config_path}: {e}")

    def _load_from_environment(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        config: Dict[str, Any] = {}

        # Map environment variables to config structure
        env_mappings = {
            # Logging
            f"{self.env_prefix}LOG_LEVEL": ("logging", "level"),
            f"{self.env_prefix}LOG_FILE": ("logging", "file_path"),
            f"{self.env_prefix}LOG_FORMAT": ("logging", "format"),
            # Security
            f"{self.env_prefix}VERIFY_SSL": ("security", "verify_ssl"),
            f"{self.env_prefix}SSL_CERT_PATH": ("security", "ssl_cert_path"),
            f"{self.env_prefix}MAX_RESPONSE_SIZE": ("security", "max_response_size"),
            # Performance
            f"{self.env_prefix}MAX_CONNECTIONS": ("performance", "max_connections"),
            f"{self.env_prefix}CONNECTION_TIMEOUT": (
                "performance",
                "connection_timeout",
            ),
            f"{self.env_prefix}MAX_RETRIES": ("performance", "max_retries"),
            # Features
            f"{self.env_prefix}ENABLE_CACHING": ("features", "enable_caching"),
            f"{self.env_prefix}ENABLE_METRICS": ("features", "enable_metrics"),
            f"{self.env_prefix}ENABLE_HTTP2": ("features", "enable_http2"),
            # Environment
            f"{self.env_prefix}ENVIRONMENT": ("environment", "environment"),
            f"{self.env_prefix}DEBUG": ("environment", "debug"),
            f"{self.env_prefix}DATA_DIR": ("environment", "data_dir"),
            # Global
            f"{self.env_prefix}USER_AGENT": ("user_agent",),
        }

        for env_var, config_path in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                # Convert value to appropriate type
                converted_value = self._convert_env_value(value)

                # Set nested configuration value
                current = config
                for key in config_path[:-1]:
                    current = current.setdefault(key, {})
                current[config_path[-1]] = converted_value

        return config

    def _convert_env_value(self, value: str) -> Any:
        """Convert environment variable string to appropriate type."""
        # Boolean values
        lower = value.lower()
        if lower in ("true", "yes", "1", "on"):
            return True
        if lower in ("false", "no", "0", "off"):
            return False

        # Numeric values
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            pass

        # List values (comma-separated)
        if "," in value:
            return [item.strip() for item in value.split(",")]

        # String value
        return value

    def _deep_merge(
        self, base: Dict[str, Any], override: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result = base.copy()

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def save_config(self, config: GlobalConfig, config_file: Union[str, Path]) -> None:
        """Save configuration to file."""
        config_path = Path(config_file)
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dictionary (Pydantic v2)
        config_data = config.model_dump()

        # Save based on file extension
        with open(config_path, "w", encoding="utf-8") as f:
            suffix = config_path.suffix.lower()
            if suffix in (".yaml", ".yml"):
                if not HAS_YAML or yaml is None:
                    raise ValueError(
                        "PyYAML is required for YAML config files. Install with: pip install PyYAML"
                    )
                yaml.dump(config_data, f, default_flow_style=False, indent=2)
            elif suffix == ".json":
                json.dump(config_data, f, indent=2, default=str)
            else:
                raise ValueError(
                    f"Unsupported config file format: {config_path.suffix}"
                )
