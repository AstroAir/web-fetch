"""
Configuration management for crawler APIs.

This module provides configuration classes and utilities for managing
API keys, settings, and preferences for different crawler services.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Optional, Any

from .base import CrawlerType, CrawlerConfig


@dataclass
class CrawlerAPIConfig:
    """Configuration for a specific crawler API."""
    
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout: float = 60.0
    max_retries: int = 3
    enabled: bool = True
    custom_settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CrawlerManagerConfig:
    """Configuration for the CrawlerManager."""
    
    # Primary crawler preference
    primary_crawler: CrawlerType = CrawlerType.FIRECRAWL
    
    # Fallback order
    fallback_crawlers: list[CrawlerType] = field(default_factory=lambda: [
        CrawlerType.SPIDER,
        CrawlerType.TAVILY,
        CrawlerType.ANYCRAWL
    ])
    
    # Individual crawler configurations
    spider_config: CrawlerAPIConfig = field(default_factory=CrawlerAPIConfig)
    firecrawl_config: CrawlerAPIConfig = field(default_factory=CrawlerAPIConfig)
    tavily_config: CrawlerAPIConfig = field(default_factory=CrawlerAPIConfig)
    anycrawl_config: CrawlerAPIConfig = field(default_factory=CrawlerAPIConfig)
    
    # Global settings
    enable_fallback: bool = True
    log_api_calls: bool = False
    cache_results: bool = False
    cache_ttl_seconds: int = 3600
    
    def get_crawler_config(self, crawler_type: CrawlerType) -> CrawlerAPIConfig:
        """Get configuration for a specific crawler type."""
        config_map: Dict[CrawlerType, CrawlerAPIConfig] = {
            CrawlerType.SPIDER: self.spider_config,
            CrawlerType.FIRECRAWL: self.firecrawl_config,
            CrawlerType.TAVILY: self.tavily_config,
            CrawlerType.ANYCRAWL: self.anycrawl_config,
        }
        return config_map.get(crawler_type, CrawlerAPIConfig())
    
    def set_crawler_config(self, crawler_type: CrawlerType, config: CrawlerAPIConfig) -> None:
        """Set configuration for a specific crawler type."""
        if crawler_type == CrawlerType.SPIDER:
            self.spider_config = config
        elif crawler_type == CrawlerType.FIRECRAWL:
            self.firecrawl_config = config
        elif crawler_type == CrawlerType.TAVILY:
            self.tavily_config = config
        elif crawler_type == CrawlerType.ANYCRAWL:
            self.anycrawl_config = config


class ConfigManager:
    """
    Configuration manager for crawler APIs.
    
    Handles loading configuration from environment variables, files,
    and provides a centralized way to manage API keys and settings.
    """
    
    # Environment variable names for API keys
    ENV_VARS: Dict[CrawlerType, str] = {
        CrawlerType.SPIDER: 'SPIDER_API_KEY',
        CrawlerType.FIRECRAWL: 'FIRECRAWL_API_KEY',
        CrawlerType.TAVILY: 'TAVILY_API_KEY',
        CrawlerType.ANYCRAWL: 'ANYCRAWL_API_KEY',
    }
    
    # Default base URLs
    DEFAULT_BASE_URLS: Dict[CrawlerType, str] = {
        CrawlerType.SPIDER: 'https://api.spider.cloud',
        CrawlerType.FIRECRAWL: 'https://api.firecrawl.dev',
        CrawlerType.TAVILY: 'https://api.tavily.com',
        CrawlerType.ANYCRAWL: 'http://localhost:3000',  # Self-hosted
    }
    
    def __init__(self) -> None:
        """Initialize the configuration manager."""
        self._config = CrawlerManagerConfig()
        self._load_from_environment()
    
    def _load_from_environment(self) -> None:
        """Load configuration from environment variables."""
        # Load API keys
        for crawler_type, env_var in self.ENV_VARS.items():
            api_key = os.getenv(env_var)
            if api_key:
                config = self._config.get_crawler_config(crawler_type)
                config.api_key = api_key
                config.enabled = True
        
        # Load base URLs
        for crawler_type, default_url in self.DEFAULT_BASE_URLS.items():
            env_var = f"{crawler_type.value.upper()}_BASE_URL"
            base_url = os.getenv(env_var, default_url)
            config = self._config.get_crawler_config(crawler_type)
            config.base_url = base_url
        
        # Load primary crawler preference
        primary_env = os.getenv('WEB_FETCH_PRIMARY_CRAWLER')
        if primary_env:
            try:
                self._config.primary_crawler = CrawlerType(primary_env.lower())
            except ValueError:
                pass  # Invalid crawler type, keep default
        
        # Load global settings
        self._config.enable_fallback = os.getenv('WEB_FETCH_ENABLE_FALLBACK', 'true').lower() == 'true'
        self._config.log_api_calls = os.getenv('WEB_FETCH_LOG_API_CALLS', 'false').lower() == 'false' and False or os.getenv('WEB_FETCH_LOG_API_CALLS', 'false').lower() == 'true'
        self._config.cache_results = os.getenv('WEB_FETCH_CACHE_RESULTS', 'false').lower() == 'true'
        
        try:
            self._config.cache_ttl_seconds = int(os.getenv('WEB_FETCH_CACHE_TTL', '3600'))
        except ValueError:
            pass  # Keep default
    
    def get_config(self) -> CrawlerManagerConfig:
        """Get the current configuration."""
        return self._config
    
    def set_api_key(self, crawler_type: CrawlerType, api_key: str) -> None:
        """Set API key for a specific crawler."""
        config = self._config.get_crawler_config(crawler_type)
        config.api_key = api_key
        config.enabled = True
    
    def get_api_key(self, crawler_type: CrawlerType) -> Optional[str]:
        """Get API key for a specific crawler."""
        config = self._config.get_crawler_config(crawler_type)
        return config.api_key
    
    def set_base_url(self, crawler_type: CrawlerType, base_url: str) -> None:
        """Set base URL for a specific crawler."""
        config = self._config.get_crawler_config(crawler_type)
        config.base_url = base_url
    
    def get_base_url(self, crawler_type: CrawlerType) -> Optional[str]:
        """Get base URL for a specific crawler."""
        config = self._config.get_crawler_config(crawler_type)
        return config.base_url
    
    def enable_crawler(self, crawler_type: CrawlerType, enabled: bool = True) -> None:
        """Enable or disable a specific crawler."""
        config = self._config.get_crawler_config(crawler_type)
        config.enabled = enabled
    
    def is_crawler_enabled(self, crawler_type: CrawlerType) -> bool:
        """Check if a crawler is enabled."""
        config = self._config.get_crawler_config(crawler_type)
        return config.enabled and config.api_key is not None
    
    def get_enabled_crawlers(self) -> list[CrawlerType]:
        """Get list of enabled crawlers."""
        enabled: list[CrawlerType] = []
        for crawler_type in CrawlerType:
            if self.is_crawler_enabled(crawler_type):
                enabled.append(crawler_type)
        return enabled
    
    def set_primary_crawler(self, crawler_type: CrawlerType) -> None:
        """Set the primary crawler."""
        self._config.primary_crawler = crawler_type
    
    def get_primary_crawler(self) -> CrawlerType:
        """Get the primary crawler."""
        return self._config.primary_crawler
    
    def set_fallback_order(self, crawlers: list[CrawlerType]) -> None:
        """Set the fallback crawler order."""
        self._config.fallback_crawlers = crawlers
    
    def get_fallback_order(self) -> list[CrawlerType]:
        """Get the fallback crawler order."""
        return self._config.fallback_crawlers
    
    def to_crawler_configs(self) -> Dict[CrawlerType, CrawlerConfig]:
        """Convert to CrawlerConfig objects for use with CrawlerManager."""
        configs: Dict[CrawlerType, CrawlerConfig] = {}
        
        for crawler_type in CrawlerType:
            api_config = self._config.get_crawler_config(crawler_type)
            
            if api_config.enabled and api_config.api_key:
                crawler_config = CrawlerConfig(
                    api_key=api_config.api_key,
                    timeout=api_config.timeout,
                    max_retries=api_config.max_retries,
                )
                
                # Add custom settings
                for key, value in api_config.custom_settings.items():
                    setattr(crawler_config, key, value)
                
                configs[crawler_type] = crawler_config
        
        return configs
    
    def get_status(self) -> Dict[str, Any]:
        """Get configuration status."""
        status: Dict[str, Any] = {
            'primary_crawler': self._config.primary_crawler.value,
            'fallback_crawlers': [c.value for c in self._config.fallback_crawlers],
            'enable_fallback': self._config.enable_fallback,
            'enabled_crawlers': [c.value for c in self.get_enabled_crawlers()],
            'crawler_status': {} 
        }
        
        crawler_status: Dict[str, Dict[str, Optional[str] | float | int | bool]] = {}
        for crawler_type in CrawlerType:
            config = self._config.get_crawler_config(crawler_type)
            crawler_status[crawler_type.value] = {
                'enabled': config.enabled,
                'has_api_key': config.api_key is not None,
                'base_url': config.base_url,
                'timeout': config.timeout,
                'max_retries': config.max_retries,
            }
        
        status['crawler_status'] = crawler_status
        return status


# Global configuration manager instance
config_manager = ConfigManager()
