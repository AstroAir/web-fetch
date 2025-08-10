"""
Tests for specific crawler implementations.

This module tests the individual crawler implementations like FireCrawl,
Spider, Tavily, and AnyCrawl.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime

from web_fetch.crawlers.base import CrawlerCapability, CrawlerRequest, CrawlerType, CrawlerError
from web_fetch.crawlers.firecrawl_crawler import FirecrawlCrawler
from web_fetch.crawlers.spider_crawler import SpiderCrawler
from web_fetch.crawlers.tavily_crawler import TavilyCrawler
from web_fetch.crawlers.anycrawl_crawler import AnyCrawlCrawler
from web_fetch.crawlers.config import CrawlerConfig


class TestFirecrawlCrawler:
    """Test the Firecrawl crawler implementation."""

    @pytest.fixture
    def firecrawl_config(self):
        """Create a FireCrawl config for testing."""
        return CrawlerConfig(
            api_key="test_api_key",
            timeout=30.0,
            max_retries=3
        )

    @pytest.fixture
    def firecrawl_crawler(self, firecrawl_config):
        """Create a FireCrawl crawler for testing."""
        return FirecrawlCrawler(firecrawl_config)

    def test_firecrawl_crawler_creation(self, firecrawl_crawler):
        """Test creating a FireCrawl crawler."""
        assert firecrawl_crawler.crawler_type == CrawlerType.FIRECRAWL
        assert firecrawl_crawler.config.api_key == "test_api_key"

    def test_firecrawl_capabilities(self, firecrawl_crawler):
        """Test FireCrawl supported capabilities."""
        capabilities = firecrawl_crawler.get_capabilities()
        
        assert CrawlerCapability.SCRAPE in capabilities
        assert CrawlerCapability.CRAWL in capabilities
        assert CrawlerCapability.SEARCH in capabilities
        assert CrawlerCapability.EXTRACT in capabilities

    def test_firecrawl_supports_capability(self, firecrawl_crawler):
        """Test checking if FireCrawl supports capabilities."""
        assert firecrawl_crawler.supports_capability(CrawlerCapability.SCRAPE)
        assert firecrawl_crawler.supports_capability(CrawlerCapability.CRAWL)
        assert not firecrawl_crawler.supports_capability(CrawlerCapability.SCREENSHOT)

    @pytest.mark.asyncio
    async def test_firecrawl_scrape_request(self, firecrawl_crawler):
        """Test FireCrawl scrape request preparation."""
        request = CrawlerRequest(
            url="https://example.com",
            operation=CrawlerCapability.SCRAPE
        )
        
        # Test that the crawler can handle the request
        assert firecrawl_crawler.supports_capability(request.operation)

    @pytest.mark.asyncio
    async def test_firecrawl_session_creation(self, firecrawl_crawler):
        """Test FireCrawl session creation."""
        # Mock aiohttp.ClientSession
        with patch('aiohttp.ClientSession') as mock_session:
            session = await firecrawl_crawler._get_session()
            
            # Should create session if none exists
            mock_session.assert_called_once()


class TestSpiderCrawler:
    """Test the Spider crawler implementation."""

    @pytest.fixture
    def spider_config(self):
        """Create a Spider config for testing."""
        return CrawlerConfig(
            api_key="test_spider_key",
            timeout=45.0,
            enable_javascript=True
        )

    @pytest.fixture
    def spider_crawler(self, spider_config):
        """Create a Spider crawler for testing."""
        return SpiderCrawler(spider_config)

    def test_spider_crawler_creation(self, spider_crawler):
        """Test creating a Spider crawler."""
        assert spider_crawler.crawler_type == CrawlerType.SPIDER
        assert spider_crawler.config.api_key == "test_spider_key"

    def test_spider_capabilities(self, spider_crawler):
        """Test Spider supported capabilities."""
        capabilities = spider_crawler.get_capabilities()
        
        assert CrawlerCapability.SCRAPE in capabilities
        assert CrawlerCapability.CRAWL in capabilities
        assert CrawlerCapability.SEARCH in capabilities
        assert CrawlerCapability.SCREENSHOT in capabilities

    def test_spider_request_preparation(self, spider_crawler):
        """Test Spider request payload preparation."""
        request = CrawlerRequest(
            url="https://example.com",
            operation=CrawlerCapability.SCRAPE
        )
        
        payload = spider_crawler._prepare_spider_request(request)
        
        assert payload["url"] == "https://example.com"
        assert "return_format" in payload
        assert "metadata" in payload

    def test_spider_javascript_config(self, spider_crawler):
        """Test Spider JavaScript configuration."""
        request = CrawlerRequest(
            url="https://example.com",
            operation=CrawlerCapability.SCRAPE
        )
        
        payload = spider_crawler._prepare_spider_request(request)
        
        # Should use chrome request type when JavaScript is enabled
        assert payload["request"] == "chrome"


class TestTavilyCrawler:
    """Test the Tavily crawler implementation."""

    @pytest.fixture
    def tavily_config(self):
        """Create a Tavily config for testing."""
        return CrawlerConfig(
            api_key="test_tavily_key",
            timeout=30.0
        )

    @pytest.fixture
    def tavily_crawler(self, tavily_config):
        """Create a Tavily crawler for testing."""
        return TavilyCrawler(tavily_config)

    def test_tavily_crawler_creation(self, tavily_crawler):
        """Test creating a Tavily crawler."""
        assert tavily_crawler.crawler_type == CrawlerType.TAVILY
        assert tavily_crawler.config.api_key == "test_tavily_key"

    def test_tavily_capabilities(self, tavily_crawler):
        """Test Tavily supported capabilities."""
        capabilities = tavily_crawler.get_capabilities()
        
        # Tavily is primarily a search engine
        assert CrawlerCapability.SEARCH in capabilities

    def test_tavily_search_only(self, tavily_crawler):
        """Test that Tavily only supports search operations."""
        assert tavily_crawler.supports_capability(CrawlerCapability.SEARCH)
        assert not tavily_crawler.supports_capability(CrawlerCapability.SCRAPE)
        assert not tavily_crawler.supports_capability(CrawlerCapability.CRAWL)


class TestAnyCrawlCrawler:
    """Test the AnyCrawl crawler implementation."""

    @pytest.fixture
    def anycrawl_config(self):
        """Create an AnyCrawl config for testing."""
        return CrawlerConfig(
            api_key="test_anycrawl_key",
            timeout=60.0,
            include_metadata=True
        )

    @pytest.fixture
    def anycrawl_crawler(self, anycrawl_config):
        """Create an AnyCrawl crawler for testing."""
        return AnyCrawlCrawler(anycrawl_config)

    def test_anycrawl_crawler_creation(self, anycrawl_crawler):
        """Test creating an AnyCrawl crawler."""
        assert anycrawl_crawler.crawler_type == CrawlerType.ANYCRAWL
        assert anycrawl_crawler.config.api_key == "test_anycrawl_key"

    def test_anycrawl_capabilities(self, anycrawl_crawler):
        """Test AnyCrawl supported capabilities."""
        capabilities = anycrawl_crawler.get_capabilities()
        
        assert CrawlerCapability.SCRAPE in capabilities
        assert CrawlerCapability.CRAWL in capabilities
        assert CrawlerCapability.SEARCH in capabilities
        assert CrawlerCapability.EXTRACT in capabilities

    def test_anycrawl_request_preparation(self, anycrawl_crawler):
        """Test AnyCrawl request payload preparation."""
        request = CrawlerRequest(
            url="https://example.com",
            operation=CrawlerCapability.SCRAPE
        )
        
        payload = anycrawl_crawler._prepare_anycrawl_request(request)
        
        assert payload["url"] == "https://example.com"
        assert payload["include_metadata"] is True
        assert "format" in payload


class TestCrawlerErrorHandling:
    """Test error handling across crawler implementations."""

    @pytest.fixture
    def basic_config(self):
        """Create a basic config for testing."""
        return CrawlerConfig(api_key="test_key")

    def test_missing_api_key_error(self):
        """Test error when API key is missing."""
        config = CrawlerConfig()  # No API key
        
        # Different crawlers may handle missing API keys differently
        # Some might allow it for testing, others might require it
        crawler = FireCrawlCrawler(config)
        assert crawler.config.api_key is None

    @pytest.mark.asyncio
    async def test_unsupported_operation_error(self, basic_config):
        """Test error when requesting unsupported operation."""
        crawler = TavilyCrawler(basic_config)
        
        # Tavily doesn't support scraping
        request = CrawlerRequest(
            url="https://example.com",
            operation=CrawlerCapability.SCRAPE
        )
        
        with pytest.raises(CrawlerError, match="does not support"):
            await crawler.execute_request(request)

    @pytest.mark.asyncio
    async def test_network_error_handling(self, basic_config):
        """Test handling of network errors."""
        crawler = FireCrawlCrawler(basic_config)
        
        request = CrawlerRequest(
            url="https://example.com",
            operation=CrawlerCapability.SCRAPE
        )
        
        # Mock network error
        with patch.object(crawler, '_get_session') as mock_session:
            mock_session.side_effect = Exception("Network error")
            
            with pytest.raises(Exception):
                await crawler.scrape(request)


class TestCrawlerConfiguration:
    """Test crawler configuration options."""

    def test_crawler_config_defaults(self):
        """Test default crawler configuration values."""
        config = CrawlerConfig()
        
        assert config.timeout == 60.0
        assert config.max_retries == 3
        assert config.retry_delay == 1.0

    def test_crawler_config_custom_values(self):
        """Test custom crawler configuration values."""
        config = CrawlerConfig(
            api_key="custom_key",
            timeout=120.0,
            max_retries=5,
            enable_javascript=True,
            include_metadata=True
        )
        
        assert config.api_key == "custom_key"
        assert config.timeout == 120.0
        assert config.max_retries == 5
        assert config.enable_javascript is True
        assert config.include_metadata is True

    def test_crawler_config_validation(self):
        """Test crawler configuration validation."""
        # Test invalid timeout
        with pytest.raises(ValueError):
            CrawlerConfig(timeout=-1.0)
        
        # Test invalid max_retries
        with pytest.raises(ValueError):
            CrawlerConfig(max_retries=-1)
