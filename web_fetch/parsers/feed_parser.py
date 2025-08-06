"""
RSS/Atom feed parsing and metadata extraction.

This module provides functionality to parse RSS and Atom feeds, extracting
feed metadata, items, and structured content using feedparser.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, Dict, Any, Tuple, List
from urllib.parse import urljoin

try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False

from ..models.base import FeedMetadata, FeedItem
from ..exceptions import ContentError

logger = logging.getLogger(__name__)


class FeedParser:
    """Parser for RSS/Atom feeds."""
    
    def __init__(self):
        """Initialize feed parser."""
        if not HAS_FEEDPARSER:
            raise ImportError("feedparser is required for feed parsing. Install with: pip install feedparser")
    
    def parse(
        self, 
        content: bytes, 
        url: Optional[str] = None
    ) -> Tuple[Dict[str, Any], FeedMetadata, List[FeedItem]]:
        """
        Parse feed content and extract metadata and items.
        
        Args:
            content: Feed content as bytes
            url: Optional URL for context in error messages
            
        Returns:
            Tuple of (feed_data_dict, feed_metadata, feed_items_list)
            
        Raises:
            ContentError: If feed parsing fails
        """
        try:
            # Parse feed content
            text_content = content.decode('utf-8', errors='replace')
            parsed_feed = feedparser.parse(text_content)
            
            # Check for parsing errors
            if parsed_feed.bozo and parsed_feed.bozo_exception:
                logger.warning(f"Feed parsing warning for {url}: {parsed_feed.bozo_exception}")
            
            # Extract feed metadata
            feed_metadata = self._extract_feed_metadata(parsed_feed, url)
            
            # Extract feed items
            feed_items = self._extract_feed_items(parsed_feed, url)
            feed_metadata.item_count = len(feed_items)
            
            # Create feed data dictionary
            feed_data = {
                'title': feed_metadata.title,
                'description': feed_metadata.description,
                'link': feed_metadata.link,
                'language': feed_metadata.language,
                'feed_type': feed_metadata.feed_type,
                'version': feed_metadata.version,
                'item_count': feed_metadata.item_count,
                'last_updated': feed_metadata.last_build_date.isoformat() if feed_metadata.last_build_date else None,
                'items': [self._item_to_dict(item) for item in feed_items[:10]]  # Include first 10 items
            }
            
            return feed_data, feed_metadata, feed_items
            
        except UnicodeDecodeError as e:
            logger.error(f"Failed to decode feed content from {url}: {e}")
            raise ContentError(f"Feed content encoding error: {e}")
        except Exception as e:
            logger.error(f"Failed to parse feed from {url}: {e}")
            raise ContentError(f"Feed parsing error: {e}")
    
    def _extract_feed_metadata(self, parsed_feed, url: Optional[str]) -> FeedMetadata:
        """Extract metadata from parsed feed."""
        metadata = FeedMetadata()
        
        feed_info = parsed_feed.feed
        
        # Basic feed information
        metadata.title = getattr(feed_info, 'title', None)
        metadata.description = getattr(feed_info, 'description', None) or getattr(feed_info, 'subtitle', None)
        metadata.link = getattr(feed_info, 'link', None)
        metadata.language = getattr(feed_info, 'language', None)
        
        # Feed management information
        metadata.copyright = getattr(feed_info, 'rights', None)
        metadata.managing_editor = getattr(feed_info, 'managingEditor', None) or getattr(feed_info, 'author', None)
        metadata.web_master = getattr(feed_info, 'webMaster', None)
        metadata.generator = getattr(feed_info, 'generator', None)
        metadata.docs = getattr(feed_info, 'docs', None)
        
        # Dates
        if hasattr(feed_info, 'published_parsed') and feed_info.published_parsed:
            metadata.pub_date = datetime(*feed_info.published_parsed[:6])
        elif hasattr(feed_info, 'updated_parsed') and feed_info.updated_parsed:
            metadata.pub_date = datetime(*feed_info.updated_parsed[:6])
        
        if hasattr(feed_info, 'updated_parsed') and feed_info.updated_parsed:
            metadata.last_build_date = datetime(*feed_info.updated_parsed[:6])
        
        # TTL (Time To Live)
        if hasattr(feed_info, 'ttl'):
            try:
                metadata.ttl = int(feed_info.ttl)
            except (ValueError, TypeError):
                pass
        
        # Category
        if hasattr(feed_info, 'tags') and feed_info.tags:
            metadata.category = feed_info.tags[0].get('term', None)
        
        # Image information
        if hasattr(feed_info, 'image') and feed_info.image:
            metadata.image = {
                'url': getattr(feed_info.image, 'href', None) or getattr(feed_info.image, 'url', None),
                'title': getattr(feed_info.image, 'title', None),
                'link': getattr(feed_info.image, 'link', None),
                'width': getattr(feed_info.image, 'width', None),
                'height': getattr(feed_info.image, 'height', None),
            }
        
        # Feed type and version
        metadata.feed_type = parsed_feed.version.split()[0] if parsed_feed.version else 'Unknown'
        metadata.version = parsed_feed.version
        
        return metadata
    
    def _extract_feed_items(self, parsed_feed, url: Optional[str]) -> List[FeedItem]:
        """Extract items from parsed feed."""
        items = []
        
        for entry in parsed_feed.entries:
            item = FeedItem()
            
            # Basic item information
            item.title = getattr(entry, 'title', None)
            item.description = getattr(entry, 'description', None) or getattr(entry, 'summary', None)
            item.link = getattr(entry, 'link', None)
            item.guid = getattr(entry, 'id', None) or getattr(entry, 'guid', None)
            
            # Author information
            if hasattr(entry, 'author'):
                item.author = entry.author
            elif hasattr(entry, 'author_detail') and entry.author_detail:
                item.author = entry.author_detail.get('name', None)
            
            # Content
            if hasattr(entry, 'content') and entry.content:
                # Get the first content entry
                content_entry = entry.content[0]
                item.content = content_entry.get('value', None)
            elif hasattr(entry, 'summary'):
                item.content = entry.summary
            
            item.summary = getattr(entry, 'summary', None)
            
            # Publication date
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                item.pub_date = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                item.pub_date = datetime(*entry.updated_parsed[:6])
            
            # Tags/Categories
            if hasattr(entry, 'tags') and entry.tags:
                item.tags = [tag.get('term', '') for tag in entry.tags if tag.get('term')]
                if item.tags:
                    item.category = item.tags[0]  # Use first tag as primary category
            
            # Comments
            item.comments = getattr(entry, 'comments', None)
            
            # Enclosure (for podcasts, etc.)
            if hasattr(entry, 'enclosures') and entry.enclosures:
                enclosure = entry.enclosures[0]
                item.enclosure = {
                    'url': getattr(enclosure, 'href', None),
                    'type': getattr(enclosure, 'type', None),
                    'length': getattr(enclosure, 'length', None),
                }
            
            # Source
            if hasattr(entry, 'source') and entry.source:
                item.source = entry.source.get('href', None)
            
            items.append(item)
        
        return items
    
    def _item_to_dict(self, item: FeedItem) -> Dict[str, Any]:
        """Convert FeedItem to dictionary for JSON serialization."""
        return {
            'title': item.title,
            'description': item.description,
            'link': item.link,
            'author': item.author,
            'category': item.category,
            'pub_date': item.pub_date.isoformat() if item.pub_date else None,
            'guid': item.guid,
            'tags': item.tags,
            'summary': item.summary,
            'has_content': bool(item.content),
            'has_enclosure': bool(item.enclosure),
        }
    
    def get_feed_info(self, content: bytes) -> Dict[str, Any]:
        """
        Get basic feed information without full parsing.
        
        Args:
            content: Feed content as bytes
            
        Returns:
            Dictionary with basic feed information
            
        Raises:
            ContentError: If feed parsing fails
        """
        try:
            text_content = content.decode('utf-8', errors='replace')
            parsed_feed = feedparser.parse(text_content)
            
            feed_info = parsed_feed.feed
            
            return {
                'title': getattr(feed_info, 'title', None),
                'description': getattr(feed_info, 'description', None),
                'link': getattr(feed_info, 'link', None),
                'feed_type': parsed_feed.version.split()[0] if parsed_feed.version else 'Unknown',
                'version': parsed_feed.version,
                'item_count': len(parsed_feed.entries),
                'language': getattr(feed_info, 'language', None),
            }
            
        except Exception as e:
            raise ContentError(f"Failed to get feed info: {e}")
    
    def is_valid_feed(self, content: bytes) -> bool:
        """
        Check if content is a valid feed.
        
        Args:
            content: Content to check as bytes
            
        Returns:
            True if content is a valid feed, False otherwise
        """
        try:
            text_content = content.decode('utf-8', errors='replace')
            parsed_feed = feedparser.parse(text_content)
            
            # Check if we have a valid feed structure
            return (
                hasattr(parsed_feed, 'feed') and 
                (hasattr(parsed_feed.feed, 'title') or hasattr(parsed_feed.feed, 'description')) and
                len(parsed_feed.entries) > 0
            )
        except Exception:
            return False
