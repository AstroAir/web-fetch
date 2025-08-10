"""
Tests for crawler API functionality.

This module contains comprehensive tests for the crawler API integration,
including unit tests for individual crawlers, integration tests for the
manager, and tests for fallback mechanisms.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from web_fetch.crawlers import (
    CrawlerType,
    CrawlerCapability,
    CrawlerConfig,
    CrawlerRequest,
    CrawlerResult,
    CrawlerError,
    CrawlerManager,
    configure_crawler,
    get_crawler_status,
)
from web_fetch.crawlers.convenience import (
    crawler_fetch_url,
    crawler_search_web,
    crawler_crawl_website,
)


class TestCrawlerBase:
    """Test base crawler functionality."""
    
    def test_crawler_config_creation(self):
        """Test CrawlerConfig creation and validation."""
        config = CrawlerConfig(
            api_key="test-key",
            timeout=30.0,
            max_retries=5,
            return_format="markdown",
            include_metadata=True
        )
        
        assert config.api_key == "test-key"
        assert config.timeout == 30.0
        assert config.max_retries == 5
        assert config.return_format == "markdown"
        assert config.include_metadata is True
    
    def test_crawler_request_creation(self):
        """Test CrawlerRequest creation and validation."""
        request = CrawlerRequest(
            url="https://example.com",
            operation=CrawlerCapability.SCRAPE,
            query="test query",
            max_results=10
        )
        
        assert str(request.url) == "https://example.com/"
        assert request.operation == CrawlerCapability.SCRAPE
        assert request.query == "test query"
        assert request.max_results == 10
    
    def test_crawler_result_creation(self):
        """Test CrawlerResult creation and methods."""
        result = CrawlerResult(
            url="https://example.com",
            crawler_type=CrawlerType.FIRECRAWL,
            operation=CrawlerCapability.SCRAPE,
            content="Test content",
            status_code=200,
            pages_crawled=1
        )
        
        assert result.url == "https://example.com"
        assert result.crawler_type == CrawlerType.FIRECRAWL
        assert result.is_success is True
        assert result.pages_crawled == 1
        
        # Test conversion to FetchResult
        fetch_result = result.to_fetch_result()
        assert fetch_result.url == "https://example.com"
        assert fetch_result.status_code == 200
        assert fetch_result.content == "Test content"
    
    def test_crawler_result_summary(self):
        """Test CrawlerResult summary generation."""
        result = CrawlerResult(
            url="https://example.com",
            crawler_type=CrawlerType.SPIDER,
            operation=CrawlerCapability.CRAWL,
            content="Test content",
            status_code=200,
            pages_crawled=5,
            total_cost=0.05
        )
        
        summary = result.get_summary()
        assert summary['url'] == "https://example.com"
        assert summary['crawler_type'] == "spider"
        assert summary['operation'] == "crawl"
        assert summary['pages_crawled'] == 5
        assert summary['total_cost'] == 0.05
        assert summary['success'] is True


class TestCrawlerManager:
    """Test CrawlerManager functionality."""
    
    @pytest.fixture
    def mock_crawler_configs(self):
        """Create mock crawler configurations."""
        return {
            CrawlerType.FIRECRAWL: CrawlerConfig(api_key="fc-test"),
            CrawlerType.SPIDER: CrawlerConfig(api_key="spider-test"),
            CrawlerType.TAVILY: CrawlerConfig(api_key="tvly-test"),
        }
    
    @pytest.fixture
    def crawler_manager(self, mock_crawler_configs):
        """Create a CrawlerManager instance for testing."""
        return CrawlerManager(
            primary_crawler=CrawlerType.FIRECRAWL,
            fallback_crawlers=[CrawlerType.SPIDER, CrawlerType.TAVILY],
            crawler_configs=mock_crawler_configs
        )
    
    def test_crawler_manager_initialization(self, crawler_manager):
        """Test CrawlerManager initialization."""
        assert crawler_manager.primary_crawler == CrawlerType.FIRECRAWL
        assert CrawlerType.SPIDER in crawler_manager.fallback_crawlers
        assert CrawlerType.TAVILY in crawler_manager.fallback_crawlers
    
    def test_get_available_crawlers(self, crawler_manager):
        """Test getting available crawlers."""
        # Mock the registry to simulate available crawlers
        with patch.object(crawler_manager, '_crawler_registry', {
            CrawlerType.FIRECRAWL: Mock,
            CrawlerType.SPIDER: Mock,
        }):
            available = crawler_manager.get_available_crawlers()
            assert CrawlerType.FIRECRAWL in available
            assert CrawlerType.SPIDER in available
    
    def test_find_capable_crawlers(self, crawler_manager):
        """Test finding crawlers with specific capabilities."""
        # Mock crawler instances
        mock_firecrawl = Mock()
        mock_firecrawl.supports_capability.return_value = True
        mock_spider = Mock()
        mock_spider.supports_capability.return_value = False
        
        with patch.object(crawler_manager, '_get_crawler_instance') as mock_get:
            mock_get.side_effect = lambda ct: mock_firecrawl if ct == CrawlerType.FIRECRAWL else mock_spider
            
            with patch.object(crawler_manager, 'get_available_crawlers', return_value=[CrawlerType.FIRECRAWL, CrawlerType.SPIDER]):
                capable = crawler_manager.find_capable_crawlers(CrawlerCapability.SEARCH)
                assert CrawlerType.FIRECRAWL in capable
                assert CrawlerType.SPIDER not in capable
    
    @pytest.mark.asyncio
    async def test_execute_request_success(self, crawler_manager):
        """Test successful request execution."""
        # Mock successful crawler
        mock_crawler = AsyncMock()
        mock_result = CrawlerResult(
            url="https://example.com",
            crawler_type=CrawlerType.FIRECRAWL,
            operation=CrawlerCapability.SCRAPE,
            content="Test content",
            status_code=200
        )
        mock_crawler.execute_request.return_value = mock_result
        
        request = CrawlerRequest(
            url="https://example.com",
            operation=CrawlerCapability.SCRAPE
        )
        
        with patch.object(crawler_manager, '_get_crawler_instance', return_value=mock_crawler):
            with patch.object(crawler_manager, '_get_crawler_order', return_value=[CrawlerType.FIRECRAWL]):
                result = await crawler_manager.execute_request(request)
                assert result.is_success
                assert result.content == "Test content"
    
    @pytest.mark.asyncio
    async def test_execute_request_fallback(self, crawler_manager):
        """Test request execution with fallback."""
        # Mock failing primary crawler and successful fallback
        mock_primary = AsyncMock()
        mock_primary.execute_request.side_effect = CrawlerError("Primary failed")
        
        mock_fallback = AsyncMock()
        mock_result = CrawlerResult(
            url="https://example.com",
            crawler_type=CrawlerType.SPIDER,
            operation=CrawlerCapability.SCRAPE,
            content="Fallback content",
            status_code=200
        )
        mock_fallback.execute_request.return_value = mock_result
        
        request = CrawlerRequest(
            url="https://example.com",
            operation=CrawlerCapability.SCRAPE
        )
        
        def mock_get_instance(crawler_type):
            if crawler_type == CrawlerType.FIRECRAWL:
                return mock_primary
            elif crawler_type == CrawlerType.SPIDER:
                return mock_fallback
            return Mock()
        
        with patch.object(crawler_manager, '_get_crawler_instance', side_effect=mock_get_instance):
            with patch.object(crawler_manager, '_get_crawler_order', return_value=[CrawlerType.FIRECRAWL, CrawlerType.SPIDER]):
                result = await crawler_manager.execute_request(request)
                assert result.is_success
                assert result.content == "Fallback content"
                assert result.crawler_type == CrawlerType.SPIDER
    
    @pytest.mark.asyncio
    async def test_execute_request_all_fail(self, crawler_manager):
        """Test request execution when all crawlers fail."""
        # Mock all crawlers failing
        mock_crawler = AsyncMock()
        mock_crawler.execute_request.side_effect = CrawlerError("All failed")
        
        request = CrawlerRequest(
            url="https://example.com",
            operation=CrawlerCapability.SCRAPE
        )
        
        with patch.object(crawler_manager, '_get_crawler_instance', return_value=mock_crawler):
            with patch.object(crawler_manager, '_get_crawler_order', return_value=[CrawlerType.FIRECRAWL]):
                with pytest.raises(CrawlerError, match="All crawlers failed"):
                    await crawler_manager.execute_request(request)
    
    @pytest.mark.asyncio
    async def test_convenience_methods(self, crawler_manager):
        """Test convenience methods."""
        mock_result = CrawlerResult(
            url="https://example.com",
            content="Test content",
            status_code=200
        )
        
        with patch.object(crawler_manager, 'execute_request', return_value=mock_result) as mock_execute:
            # Test scrape_url
            result = await crawler_manager.scrape_url("https://example.com")
            assert result.content == "Test content"
            mock_execute.assert_called_once()
            
            # Test crawl_website
            mock_execute.reset_mock()
            result = await crawler_manager.crawl_website("https://example.com", max_pages=10)
            assert result.content == "Test content"
            mock_execute.assert_called_once()
            
            # Test search_web
            mock_execute.reset_mock()
            result = await crawler_manager.search_web("test query")
            assert result.content == "Test content"
            mock_execute.assert_called_once()


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    @pytest.mark.asyncio
    async def test_crawler_fetch_url_with_crawler(self):
        """Test crawler_fetch_url with crawler enabled."""
        mock_result = CrawlerResult(
            url="https://example.com",
            content="Crawler content",
            status_code=200
        )
        
        with patch('web_fetch.crawlers.convenience.CrawlerManager') as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager.execute_request.return_value = mock_result
            mock_manager_class.return_value = mock_manager
            
            with patch('web_fetch.crawlers.convenience.config_manager') as mock_config:
                mock_config.to_crawler_configs.return_value = {}
                mock_config.get_primary_crawler.return_value = CrawlerType.FIRECRAWL
                mock_config.get_fallback_order.return_value = []
                
                result = await crawler_fetch_url("https://example.com", use_crawler=True)
                assert result.content == "Crawler content"
    
    @pytest.mark.asyncio
    async def test_crawler_fetch_url_fallback_to_http(self):
        """Test crawler_fetch_url falling back to HTTP."""
        with patch('web_fetch.convenience.fetch_url') as mock_fetch:
            mock_fetch.return_value = Mock(content="HTTP content")

            result = await crawler_fetch_url("https://example.com", use_crawler=False)
            mock_fetch.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_crawler_search_web(self):
        """Test crawler_search_web function."""
        mock_result = CrawlerResult(
            url="https://example.com",
            content="Search results",
            status_code=200,
            search_results=[{"title": "Test", "url": "https://test.com"}]
        )
        
        with patch('web_fetch.crawlers.convenience.CrawlerManager') as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager.execute_request.return_value = mock_result
            mock_manager_class.return_value = mock_manager
            
            with patch('web_fetch.crawlers.convenience.config_manager') as mock_config:
                mock_config.to_crawler_configs.return_value = {}
                mock_config.get_primary_crawler.return_value = CrawlerType.TAVILY
                mock_config.get_fallback_order.return_value = []
                
                result = await crawler_search_web("test query", max_results=5)
                assert result.content == "Search results"


class TestConfiguration:
    """Test configuration management."""
    
    def test_configure_crawler(self):
        """Test crawler configuration."""
        with patch('web_fetch.crawlers.convenience.config_manager') as mock_config:
            configure_crawler(
                CrawlerType.FIRECRAWL,
                api_key="test-key",
                enabled=True,
                custom_setting="value"
            )
            
            mock_config.set_api_key.assert_called_once_with(CrawlerType.FIRECRAWL, "test-key")
            mock_config.enable_crawler.assert_called_once_with(CrawlerType.FIRECRAWL, True)
    
    def test_get_crawler_status(self):
        """Test getting crawler status."""
        with patch('web_fetch.crawlers.convenience.config_manager') as mock_config:
            mock_config.get_status.return_value = {"test": "status"}
            
            status = get_crawler_status()
            assert status == {"test": "status"}
            mock_config.get_status.assert_called_once()


@pytest.mark.integration
class TestCrawlerIntegration:
    """Integration tests for crawler functionality."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_crawler_flow(self):
        """Test end-to-end crawler flow with mocked APIs."""
        # This would be an integration test that tests the full flow
        # from configuration to API call to result processing
        pass
    
    @pytest.mark.skipif(
        not any([
            pytest.importorskip("firecrawl", reason="Firecrawl not available"),
            pytest.importorskip("tavily", reason="Tavily not available"),
        ]),
        reason="No crawler SDKs available"
    )
    @pytest.mark.asyncio
    async def test_real_api_integration(self):
        """Test with real APIs (requires API keys)."""
        # This would test with real API calls if API keys are available
        # Should be run separately with proper API keys configured
        pass
