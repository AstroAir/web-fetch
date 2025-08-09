"""
Configuration manager for web_fetch.

This module provides centralized configuration management with caching,
validation, and runtime updates.
"""

import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable

from .loader import ConfigLoader
from .models import Environment, GlobalConfig
from .validator import ConfigValidator, ValidationError

logger = logging.getLogger(__name__)


class ConfigManager:
    """Centralized configuration manager."""

    _instance: Optional["ConfigManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "ConfigManager":
        """Singleton pattern implementation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize configuration manager."""
        if hasattr(self, "_initialized"):
            return

        self._initialized = True
        self._config: Optional[GlobalConfig] = None
        self._loader = ConfigLoader()
        self._validator = ConfigValidator()
        self._config_file: Optional[Path] = None
        # Use an instance-level reentrant lock for internal synchronization
        self._instance_lock: threading.RLock = threading.RLock()

        # Configuration change callbacks
        self._change_callbacks: List[Callable[[Optional[GlobalConfig]], None]] = []

    def load_config(
        self,
        config_file: Optional[Union[str, Path]] = None,
        environment: Optional[Environment] = None,
        validate: bool = True,
        sanitize: bool = True,
    ) -> GlobalConfig:
        """
        Load configuration from all sources.

        Args:
            config_file: Specific config file to load
            environment: Target environment
            validate: Whether to validate configuration
            sanitize: Whether to sanitize configuration

        Returns:
            Loaded and validated configuration

        Raises:
            ValidationError: If configuration is invalid and validation is enabled
        """
        with self._instance_lock:
            try:
                # Load configuration
                config = self._loader.load_config(config_file, environment)

                # Validate if requested
                if validate:
                    is_valid, errors, warnings = self._validator.validate(config)

                    # Log warnings
                    for warning in warnings:
                        logger.warning(f"Configuration warning: {warning}")

                    # Raise error if invalid
                    if not is_valid:
                        error_msg = "Configuration validation failed:\n" + "\n".join(
                            errors
                        )
                        raise ValidationError(error_msg)

                # Sanitize if requested
                if sanitize:
                    config = self._validator.sanitize_config(config)

                # Store configuration
                self._config = config
                self._config_file = Path(config_file) if config_file else None

                # Notify callbacks
                self._notify_change_callbacks()

                logger.info("Configuration loaded successfully")
                return config

            except Exception as e:
                logger.error(f"Failed to load configuration: {e}")
                raise

    def get_config(self) -> GlobalConfig:
        """
        Get current configuration.

        Returns:
            Current configuration

        Raises:
            RuntimeError: If no configuration is loaded
        """
        with self._instance_lock:
            if self._config is None:
                # Try to load default configuration
                try:
                    return self.load_config()
                except Exception:
                    # Fall back to default configuration
                    self._config = GlobalConfig()
                    logger.warning("Using default configuration")

            return self._config

    def load_from_dict(self, config_dict: Dict[str, Any], validate: bool = True) -> GlobalConfig:
        """
        Load configuration from dictionary.

        Args:
            config_dict: Configuration dictionary
            validate: Whether to validate configuration

        Returns:
            Loaded configuration
        """
        with self._instance_lock:
            try:
                # Use the loader to handle transformations
                config = self._loader.load_from_dict(config_dict)

                if validate:
                    is_valid, errors, warnings = self._validator.validate(config)

                    for warning in warnings:
                        logger.warning(f"Configuration warning: {warning}")

                    if not is_valid:
                        error_msg = "Configuration validation failed:\n" + "\n".join(errors)
                        raise ValidationError(error_msg)

                self._config = config
                self._notify_change_callbacks()

                logger.info("Configuration loaded from dictionary")
                return config

            except Exception as e:
                logger.error(f"Failed to load configuration from dictionary: {e}")
                raise

    def update_config(
        self, updates: Dict[str, Any], validate: bool = True, persist: bool = False
    ) -> None:
        """
        Update configuration at runtime.

        Args:
            updates: Configuration updates as nested dictionary
            validate: Whether to validate updated configuration
            persist: Whether to persist changes to file

        Raises:
            ValidationError: If updated configuration is invalid
        """
        with self._instance_lock:
            if self._config is None:
                raise RuntimeError("No configuration loaded")

            # Create updated configuration
            config_dict = self._config.model_dump()
            config_dict = self._deep_update(config_dict, updates)

            # Transform the config dict to handle field name and value transformations
            transformed_dict = self._loader._transform_config_dict(config_dict)

            try:
                new_config = GlobalConfig(**transformed_dict)

                # Validate if requested
                if validate:
                    is_valid, errors, warnings = self._validator.validate(new_config)

                    if not is_valid:
                        error_msg = (
                            "Configuration update validation failed:\n"
                            + "\n".join(errors)
                        )
                        raise ValidationError(error_msg)

                    # Log warnings
                    for warning in warnings:
                        logger.warning(f"Configuration warning: {warning}")

                # Apply update
                self._config = new_config

                # Persist if requested
                if persist and self._config_file:
                    self._loader.save_config(new_config, self._config_file)

                # Notify callbacks
                self._notify_change_callbacks()

                logger.info("Configuration updated successfully")

            except Exception as e:
                logger.error(f"Failed to update configuration: {e}")
                raise

    def get_setting(self, path: str, default: Any = None) -> Any:
        """
        Get a specific configuration setting by path.

        Args:
            path: Dot-separated path to setting (e.g., 'logging.level')
            default: Default value if setting not found

        Returns:
            Configuration setting value
        """
        config = self.get_config()
        config_dict = config.model_dump()

        try:
            value = config_dict
            for key in path.split("."):
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def set_setting(
        self, path: str, value: Any, validate: bool = True, persist: bool = False
    ) -> None:
        """
        Set a specific configuration setting by path.

        Args:
            path: Dot-separated path to setting (e.g., 'logging.level')
            value: New value for setting
            validate: Whether to validate updated configuration
            persist: Whether to persist changes to file
        """
        # Build nested update dictionary
        keys = path.split(".")
        updates: Dict[str, Any] = {}
        current: Dict[str, Any] = updates

        for key in keys[:-1]:
            current[key] = {}
            current = current[key]

        current[keys[-1]] = value

        # Apply update
        self.update_config(updates, validate, persist)

    def get(self, path: str, default: Any = None) -> Any:
        """
        Get a configuration value by path.

        Args:
            path: Dot-separated path to setting (e.g., 'logging.level')
            default: Default value if path not found

        Returns:
            Configuration value or default
        """
        config = self.get_config()
        config_dict = config.model_dump()

        keys = path.split(".")
        current = config_dict

        try:
            for key in keys:
                current = current[key]
            return current
        except (KeyError, TypeError):
            return default

    def set(self, path: str, value: Any, validate: bool = True, persist: bool = False) -> None:
        """
        Set a configuration value by path.

        Args:
            path: Dot-separated path to setting (e.g., 'logging.level')
            value: New value for setting
            validate: Whether to validate updated configuration
            persist: Whether to persist changes to file
        """
        self.set_setting(path, value, validate, persist)

    def add_change_callback(self, callback: Callable[[Optional[GlobalConfig]], None]) -> None:
        """
        Add callback to be called when configuration changes.

        Args:
            callback: Function to call on configuration change
        """
        with self._instance_lock:
            if callback not in self._change_callbacks:
                self._change_callbacks.append(callback)

    def remove_change_callback(self, callback: Callable[[Optional[GlobalConfig]], None]) -> None:
        """
        Remove configuration change callback.

        Args:
            callback: Function to remove from callbacks
        """
        with self._instance_lock:
            if callback in self._change_callbacks:
                self._change_callbacks.remove(callback)

    def reload_config(self) -> GlobalConfig:
        """
        Reload configuration from file.

        Returns:
            Reloaded configuration
        """
        return self.load_config(self._config_file)

    def reset_to_defaults(self) -> GlobalConfig:
        """
        Reset configuration to defaults.

        Returns:
            Default configuration
        """
        with self._instance_lock:
            self._config = GlobalConfig()
            self._notify_change_callbacks()
            logger.info("Configuration reset to defaults")
            return self._config

    def _deep_update(
        self, base: Dict[str, Any], updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deep update dictionary."""
        result = base.copy()

        for key, value in updates.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._deep_update(result[key], value)
            else:
                result[key] = value

        return result

    def _notify_change_callbacks(self) -> None:
        """Notify all change callbacks."""
        # Work on a snapshot to avoid issues if callbacks mutate the list
        callbacks_snapshot = list(self._change_callbacks)
        for callback in callbacks_snapshot:
            try:
                callback(self._config)
            except Exception as e:
                logger.error(f"Error in configuration change callback: {e}")


# Global configuration manager instance
config_manager = ConfigManager()
