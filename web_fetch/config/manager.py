"""
Configuration manager for web_fetch.

This module provides centralized configuration management with caching,
validation, and runtime updates.
"""

import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .loader import ConfigLoader
from .models import GlobalConfig, Environment
from .validator import ConfigValidator, ValidationError


logger = logging.getLogger(__name__)


class ConfigManager:
    """Centralized configuration manager."""
    
    _instance: Optional['ConfigManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> 'ConfigManager':
        """Singleton pattern implementation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        """Initialize configuration manager."""
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self._config: Optional[GlobalConfig] = None
        self._loader = ConfigLoader()
        self._validator = ConfigValidator()
        self._config_file: Optional[Path] = None
        self._lock = threading.RLock()
        
        # Configuration change callbacks
        self._change_callbacks: List[callable] = []
    
    def load_config(
        self,
        config_file: Optional[Union[str, Path]] = None,
        environment: Optional[Environment] = None,
        validate: bool = True,
        sanitize: bool = True
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
        with self._lock:
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
                        error_msg = "Configuration validation failed:\n" + "\n".join(errors)
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
        with self._lock:
            if self._config is None:
                # Try to load default configuration
                try:
                    return self.load_config()
                except Exception:
                    # Fall back to default configuration
                    self._config = GlobalConfig()
                    logger.warning("Using default configuration")
            
            return self._config
    
    def update_config(
        self,
        updates: Dict[str, Any],
        validate: bool = True,
        persist: bool = False
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
        with self._lock:
            if self._config is None:
                raise RuntimeError("No configuration loaded")
            
            # Create updated configuration
            config_dict = self._config.dict()
            config_dict = self._deep_update(config_dict, updates)
            
            try:
                new_config = GlobalConfig(**config_dict)
                
                # Validate if requested
                if validate:
                    is_valid, errors, warnings = self._validator.validate(new_config)
                    
                    if not is_valid:
                        error_msg = "Configuration update validation failed:\n" + "\n".join(errors)
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
        config_dict = config.dict()
        
        try:
            value = config_dict
            for key in path.split('.'):
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def set_setting(
        self,
        path: str,
        value: Any,
        validate: bool = True,
        persist: bool = False
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
        keys = path.split('.')
        updates = {}
        current = updates
        
        for key in keys[:-1]:
            current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
        
        # Apply update
        self.update_config(updates, validate, persist)
    
    def add_change_callback(self, callback: callable) -> None:
        """
        Add callback to be called when configuration changes.
        
        Args:
            callback: Function to call on configuration change
        """
        with self._lock:
            if callback not in self._change_callbacks:
                self._change_callbacks.append(callback)
    
    def remove_change_callback(self, callback: callable) -> None:
        """
        Remove configuration change callback.
        
        Args:
            callback: Function to remove from callbacks
        """
        with self._lock:
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
        with self._lock:
            self._config = GlobalConfig()
            self._notify_change_callbacks()
            logger.info("Configuration reset to defaults")
            return self._config
    
    def _deep_update(self, base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
        """Deep update dictionary."""
        result = base.copy()
        
        for key, value in updates.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_update(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _notify_change_callbacks(self) -> None:
        """Notify all change callbacks."""
        for callback in self._change_callbacks:
            try:
                callback(self._config)
            except Exception as e:
                logger.error(f"Error in configuration change callback: {e}")


# Global configuration manager instance
config_manager = ConfigManager()
