"""
Comprehensive tests for the RSS component module.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from web_fetch.components.rss_component import (
    RSSComponent,
    RSSConfig,
    RSSError,
    RSSFeed,
    RSSItem,
    RSSParser,
)
from web_fetch.models.http import FetchRequest, FetchResult
from web_fetch.models.base import ContentType


class TestRSSConfig:
    """Test RSS configuration."""

    def test_rss_config_creation(self):
        """Test creating RSS configuration."""
        config = RSSConfig(
            feed_urls=["https://example.com/feed.xml"],
            update_interval=3600,
            max_items_per_feed=100,
            include_content=True,
            parse_dates=True
        )
        
        assert config.feed_urls == ["https://example.com/feed.xml"]
        assert config.update_interval == 3600
        assert config.max_items_per_feed == 100
        assert config.include_content == True
        assert config.parse_dates == True

    def test_rss_config_defaults(self):
        """Test RSS configuration defaults."""
        config = RSSConfig(feed_urls=["https://example.com/feed.xml"])
        
        assert config.update_interval == 3600  # 1 hour
        assert config.max_items_per_feed == 50
        assert config.include_content == True
        assert config.parse_dates == True

    def test_rss_config_validation(self):
        """Test RSS configuration validation."""
        # Empty feed URLs
        with pytest.raises(ValueError):
            RSSConfig(feed_urls=[])
        
        # Invalid update interval
        with pytest.raises(ValueError):
            RSSConfig(
                feed_urls=["https://example.com/feed.xml"],
                update_interval=-1
            )
        
        # Invalid max items
        with pytest.raises(ValueError):
            RSSConfig(
                feed_urls=["https://example.com/feed.xml"],
                max_items_per_feed=0
            )


class TestRSSItem:
    """Test RSS item model."""

    def test_rss_item_creation(self):
        """Test creating RSS item."""
        item = RSSItem(
            title="Test Article",
            link="https://example.com/article",
            description="Test description",
            pub_date=datetime.now(),
            guid="unique-id-123",
            author="Test Author",
            categories=["tech", "news"]
        )
        
        assert item.title == "Test Article"
        assert item.link == "https://example.com/article"
        assert item.description == "Test description"
        assert item.guid == "unique-id-123"
        assert item.author == "Test Author"
        assert item.categories == ["tech", "news"]

    def test_rss_item_minimal(self):
        """Test creating minimal RSS item."""
        item = RSSItem(
            title="Minimal Article",
            link="https://example.com/minimal"
        )
        
        assert item.title == "Minimal Article"
        assert item.link == "https://example.com/minimal"
        assert item.description is None
        assert item.pub_date is None

    def test_rss_item_string_representation(self):
        """Test RSS item string representation."""
        item = RSSItem(
            title="Test Article",
            link="https://example.com/article"
        )
        
        item_str = str(item)
        assert "Test Article" in item_str
        assert "https://example.com/article" in item_str


class TestRSSFeed:
    """Test RSS feed model."""

    def test_rss_feed_creation(self):
        """Test creating RSS feed."""
        items = [
            RSSItem(title="Article 1", link="https://example.com/1"),
            RSSItem(title="Article 2", link="https://example.com/2")
        ]
        
        feed = RSSFeed(
            title="Test Feed",
            link="https://example.com",
            description="Test RSS feed",
            items=items,
            last_updated=datetime.now()
        )
        
        assert feed.title == "Test Feed"
        assert feed.link == "https://example.com"
        assert feed.description == "Test RSS feed"
        assert len(feed.items) == 2
        assert feed.last_updated is not None

    def test_rss_feed_add_item(self):
        """Test adding item to RSS feed."""
        feed = RSSFeed(
            title="Test Feed",
            link="https://example.com",
            description="Test feed",
            items=[]
        )
        
        item = RSSItem(title="New Article", link="https://example.com/new")
        feed.add_item(item)
        
        assert len(feed.items) == 1
        assert feed.items[0] == item

    def test_rss_feed_get_recent_items(self):
        """Test getting recent items from feed."""
        now = datetime.now()
        old_date = now - timedelta(days=2)
        recent_date = now - timedelta(hours=1)
        
        items = [
            RSSItem(title="Old Article", link="https://example.com/old", pub_date=old_date),
            RSSItem(title="Recent Article", link="https://example.com/recent", pub_date=recent_date)
        ]
        
        feed = RSSFeed(
            title="Test Feed",
            link="https://example.com",
            description="Test feed",
            items=items
        )
        
        recent_items = feed.get_recent_items(hours=2)
        
        assert len(recent_items) == 1
        assert recent_items[0].title == "Recent Article"

    def test_rss_feed_filter_by_category(self):
        """Test filtering items by category."""
        items = [
            RSSItem(title="Tech Article", link="https://example.com/tech", categories=["tech"]),
            RSSItem(title="News Article", link="https://example.com/news", categories=["news"]),
            RSSItem(title="Mixed Article", link="https://example.com/mixed", categories=["tech", "news"])
        ]
        
        feed = RSSFeed(
            title="Test Feed",
            link="https://example.com",
            description="Test feed",
            items=items
        )
        
        tech_items = feed.filter_by_category("tech")
        
        assert len(tech_items) == 2
        assert all("tech" in item.categories for item in tech_items)


class TestRSSParser:
    """Test RSS parser functionality."""

    def test_rss_parser_creation(self):
        """Test creating RSS parser."""
        parser = RSSParser()
        assert parser is not None

    def test_parse_rss_xml(self):
        """Test parsing RSS XML."""
        rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <link>https://example.com</link>
                <description>Test RSS feed</description>
                <item>
                    <title>Test Article</title>
                    <link>https://example.com/article</link>
                    <description>Test description</description>
                    <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
                    <guid>test-guid-123</guid>
                </item>
            </channel>
        </rss>"""
        
        parser = RSSParser()
        feed = parser.parse_rss_xml(rss_xml)
        
        assert feed.title == "Test Feed"
        assert feed.link == "https://example.com"
        assert feed.description == "Test RSS feed"
        assert len(feed.items) == 1
        assert feed.items[0].title == "Test Article"

    def test_parse_atom_xml(self):
        """Test parsing Atom XML."""
        atom_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            <title>Test Atom Feed</title>
            <link href="https://example.com"/>
            <subtitle>Test Atom feed</subtitle>
            <entry>
                <title>Test Entry</title>
                <link href="https://example.com/entry"/>
                <summary>Test summary</summary>
                <published>2024-01-01T12:00:00Z</published>
                <id>test-entry-123</id>
            </entry>
        </feed>"""
        
        parser = RSSParser()
        feed = parser.parse_atom_xml(atom_xml)
        
        assert feed.title == "Test Atom Feed"
        assert feed.link == "https://example.com"
        assert feed.description == "Test Atom feed"
        assert len(feed.items) == 1
        assert feed.items[0].title == "Test Entry"

    def test_parse_invalid_xml(self):
        """Test parsing invalid XML."""
        invalid_xml = "<invalid>xml content</invalid>"
        
        parser = RSSParser()
        
        with pytest.raises(RSSError):
            parser.parse_rss_xml(invalid_xml)

    def test_parse_empty_xml(self):
        """Test parsing empty XML."""
        parser = RSSParser()
        
        with pytest.raises(RSSError):
            parser.parse_rss_xml("")


class TestRSSError:
    """Test RSS error handling."""

    def test_rss_error_creation(self):
        """Test creating RSS error."""
        error = RSSError(
            message="Feed parsing failed",
            feed_url="https://example.com/feed.xml",
            error_code="RSS_PARSE_ERROR",
            details={"line": 10, "column": 5}
        )
        
        assert error.message == "Feed parsing failed"
        assert error.feed_url == "https://example.com/feed.xml"
        assert error.error_code == "RSS_PARSE_ERROR"
        assert error.details["line"] == 10

    def test_rss_error_string_representation(self):
        """Test RSS error string representation."""
        error = RSSError(
            message="Network error",
            feed_url="https://example.com/feed.xml"
        )
        
        error_str = str(error)
        assert "Network error" in error_str
        assert "https://example.com/feed.xml" in error_str


class TestRSSComponent:
    """Test RSS component functionality."""

    def test_rss_component_creation(self):
        """Test creating RSS component."""
        config = RSSConfig(feed_urls=["https://example.com/feed.xml"])
        component = RSSComponent(config)
        
        assert component.config == config
        assert len(component.feeds) == 0

    @pytest.mark.asyncio
    async def test_rss_component_initialization(self):
        """Test RSS component initialization."""
        config = RSSConfig(feed_urls=["https://example.com/feed.xml"])
        component = RSSComponent(config)
        
        await component.initialize()
        
        assert component.status == "active"

    @pytest.mark.asyncio
    async def test_fetch_feed(self):
        """Test fetching RSS feed."""
        config = RSSConfig(feed_urls=["https://example.com/feed.xml"])
        component = RSSComponent(config)
        
        rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <link>https://example.com</link>
                <description>Test RSS feed</description>
                <item>
                    <title>Test Article</title>
                    <link>https://example.com/article</link>
                    <description>Test description</description>
                </item>
            </channel>
        </rss>"""
        
        mock_result = FetchResult(
            url="https://example.com/feed.xml",
            status_code=200,
            headers={"content-type": "application/rss+xml"},
            content=rss_xml,
            content_type=ContentType.XML
        )
        
        with patch('web_fetch.components.rss_component.fetch_url', return_value=mock_result):
            await component.initialize()
            
            feed = await component.fetch_feed("https://example.com/feed.xml")
            
            assert feed.title == "Test Feed"
            assert len(feed.items) == 1

    @pytest.mark.asyncio
    async def test_fetch_all_feeds(self):
        """Test fetching all configured feeds."""
        config = RSSConfig(feed_urls=[
            "https://example.com/feed1.xml",
            "https://example.com/feed2.xml"
        ])
        component = RSSComponent(config)
        
        rss_xml_1 = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Feed 1</title>
                <link>https://example.com</link>
                <description>First feed</description>
            </channel>
        </rss>"""
        
        rss_xml_2 = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Feed 2</title>
                <link>https://example.com</link>
                <description>Second feed</description>
            </channel>
        </rss>"""
        
        def mock_fetch(url, **kwargs):
            if "feed1" in url:
                return FetchResult(
                    url=url,
                    status_code=200,
                    headers={"content-type": "application/rss+xml"},
                    content=rss_xml_1,
                    content_type=ContentType.XML
                )
            else:
                return FetchResult(
                    url=url,
                    status_code=200,
                    headers={"content-type": "application/rss+xml"},
                    content=rss_xml_2,
                    content_type=ContentType.XML
                )
        
        with patch('web_fetch.components.rss_component.fetch_url', side_effect=mock_fetch):
            await component.initialize()
            
            feeds = await component.fetch_all_feeds()
            
            assert len(feeds) == 2
            assert feeds[0].title == "Feed 1"
            assert feeds[1].title == "Feed 2"

    @pytest.mark.asyncio
    async def test_get_recent_items(self):
        """Test getting recent items from all feeds."""
        config = RSSConfig(feed_urls=["https://example.com/feed.xml"])
        component = RSSComponent(config)
        
        now = datetime.now()
        recent_date = now - timedelta(minutes=30)
        
        rss_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <link>https://example.com</link>
                <description>Test RSS feed</description>
                <item>
                    <title>Recent Article</title>
                    <link>https://example.com/recent</link>
                    <description>Recent description</description>
                    <pubDate>{recent_date.strftime('%a, %d %b %Y %H:%M:%S GMT')}</pubDate>
                </item>
            </channel>
        </rss>"""
        
        mock_result = FetchResult(
            url="https://example.com/feed.xml",
            status_code=200,
            headers={"content-type": "application/rss+xml"},
            content=rss_xml,
            content_type=ContentType.XML
        )
        
        with patch('web_fetch.components.rss_component.fetch_url', return_value=mock_result):
            await component.initialize()
            await component.fetch_all_feeds()
            
            recent_items = await component.get_recent_items(hours=1)
            
            assert len(recent_items) == 1
            assert recent_items[0].title == "Recent Article"

    @pytest.mark.asyncio
    async def test_search_items(self):
        """Test searching items by keyword."""
        config = RSSConfig(feed_urls=["https://example.com/feed.xml"])
        component = RSSComponent(config)
        
        rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <link>https://example.com</link>
                <description>Test RSS feed</description>
                <item>
                    <title>Python Programming Tutorial</title>
                    <link>https://example.com/python</link>
                    <description>Learn Python programming</description>
                </item>
                <item>
                    <title>JavaScript Guide</title>
                    <link>https://example.com/javascript</link>
                    <description>JavaScript programming guide</description>
                </item>
            </channel>
        </rss>"""
        
        mock_result = FetchResult(
            url="https://example.com/feed.xml",
            status_code=200,
            headers={"content-type": "application/rss+xml"},
            content=rss_xml,
            content_type=ContentType.XML
        )
        
        with patch('web_fetch.components.rss_component.fetch_url', return_value=mock_result):
            await component.initialize()
            await component.fetch_all_feeds()
            
            python_items = await component.search_items("Python")
            
            assert len(python_items) == 1
            assert "Python" in python_items[0].title

    @pytest.mark.asyncio
    async def test_filter_by_category(self):
        """Test filtering items by category."""
        config = RSSConfig(feed_urls=["https://example.com/feed.xml"])
        component = RSSComponent(config)
        
        rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <link>https://example.com</link>
                <description>Test RSS feed</description>
                <item>
                    <title>Tech Article</title>
                    <link>https://example.com/tech</link>
                    <description>Technology news</description>
                    <category>technology</category>
                </item>
                <item>
                    <title>Sports Article</title>
                    <link>https://example.com/sports</link>
                    <description>Sports news</description>
                    <category>sports</category>
                </item>
            </channel>
        </rss>"""
        
        mock_result = FetchResult(
            url="https://example.com/feed.xml",
            status_code=200,
            headers={"content-type": "application/rss+xml"},
            content=rss_xml,
            content_type=ContentType.XML
        )
        
        with patch('web_fetch.components.rss_component.fetch_url', return_value=mock_result):
            await component.initialize()
            await component.fetch_all_feeds()
            
            tech_items = await component.filter_by_category("technology")
            
            assert len(tech_items) == 1
            assert "Tech" in tech_items[0].title

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling in RSS operations."""
        config = RSSConfig(feed_urls=["https://invalid.example.com/feed.xml"])
        component = RSSComponent(config)
        
        with patch('web_fetch.components.rss_component.fetch_url', side_effect=Exception("Network error")):
            await component.initialize()
            
            with pytest.raises(RSSError):
                await component.fetch_feed("https://invalid.example.com/feed.xml")

    @pytest.mark.asyncio
    async def test_component_metrics(self):
        """Test RSS component metrics."""
        config = RSSConfig(feed_urls=["https://example.com/feed.xml"])
        component = RSSComponent(config)
        
        rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <link>https://example.com</link>
                <description>Test RSS feed</description>
                <item>
                    <title>Test Article</title>
                    <link>https://example.com/article</link>
                </item>
            </channel>
        </rss>"""
        
        mock_result = FetchResult(
            url="https://example.com/feed.xml",
            status_code=200,
            headers={"content-type": "application/rss+xml"},
            content=rss_xml,
            content_type=ContentType.XML
        )
        
        with patch('web_fetch.components.rss_component.fetch_url', return_value=mock_result):
            await component.initialize()
            await component.fetch_all_feeds()
            
            metrics = component.get_metrics()
            
            assert metrics["feeds_processed"] >= 1
            assert metrics["items_parsed"] >= 1

    @pytest.mark.asyncio
    async def test_component_health_check(self):
        """Test RSS component health check."""
        config = RSSConfig(feed_urls=["https://example.com/feed.xml"])
        component = RSSComponent(config)
        
        await component.initialize()
        
        health = await component.health_check()
        
        assert health["status"] == "healthy"
        assert health["feeds_configured"] == 1
