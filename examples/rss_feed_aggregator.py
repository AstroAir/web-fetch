#!/usr/bin/env python3
"""
RSS Feed Aggregator Example

This example demonstrates how to use the RSS component to aggregate feeds from
multiple sources, process the content, and store the results.

Features demonstrated:
- Multiple RSS feed processing
- Content filtering and deduplication
- Error handling and retry logic
- Caching for performance
- Data export to different formats
"""

import asyncio
import json
import csv
from datetime import datetime, timedelta
from typing import List, Dict, Any, Set
from pathlib import Path

from web_fetch import fetch_rss_feed
from web_fetch.models.extended_resources import RSSConfig
from web_fetch.models.resource import ResourceConfig


class RSSFeedAggregator:
    """RSS feed aggregator with deduplication and filtering."""
    
    def __init__(self, cache_ttl: int = 1800):
        """
        Initialize the aggregator.
        
        Args:
            cache_ttl: Cache time-to-live in seconds (default: 30 minutes)
        """
        self.resource_config = ResourceConfig(
            enable_cache=True,
            cache_ttl_seconds=cache_ttl
        )
        
        self.rss_config = RSSConfig(
            max_items=100,
            include_content=True,
            validate_dates=True,
            follow_redirects=True,
            user_agent="RSS-Aggregator/1.0 (+https://example.com/contact)"
        )
        
        self.seen_urls: Set[str] = set()
        self.aggregated_items: List[Dict[str, Any]] = []
    
    async def add_feed(self, feed_url: str, category: str = "general") -> Dict[str, Any]:
        """
        Add a feed to the aggregation.
        
        Args:
            feed_url: URL of the RSS/Atom feed
            category: Category to assign to items from this feed
            
        Returns:
            Dictionary with feed processing results
        """
        print(f"Processing feed: {feed_url}")
        
        try:
            result = await fetch_rss_feed(
                feed_url,
                config=self.resource_config,
                rss_config=self.rss_config
            )
            
            if not result.is_success:
                return {
                    "feed_url": feed_url,
                    "status": "error",
                    "error": result.error,
                    "items_added": 0
                }
            
            feed_data = result.content
            items_added = 0
            
            # Process each item
            for item in feed_data['items']:
                if self._should_include_item(item):
                    # Add category and source information
                    enhanced_item = {
                        **item,
                        "category": category,
                        "source_feed": feed_url,
                        "source_title": feed_data.get('title', 'Unknown'),
                        "processed_at": datetime.utcnow().isoformat()
                    }
                    
                    self.aggregated_items.append(enhanced_item)
                    self.seen_urls.add(item['link'])
                    items_added += 1
            
            return {
                "feed_url": feed_url,
                "status": "success",
                "feed_title": feed_data.get('title'),
                "total_items": len(feed_data['items']),
                "items_added": items_added,
                "items_skipped": len(feed_data['items']) - items_added
            }
            
        except Exception as e:
            return {
                "feed_url": feed_url,
                "status": "error",
                "error": str(e),
                "items_added": 0
            }
    
    def _should_include_item(self, item: Dict[str, Any]) -> bool:
        """
        Determine if an item should be included in the aggregation.
        
        Args:
            item: RSS item dictionary
            
        Returns:
            True if item should be included
        """
        # Skip items without links
        if not item.get('link'):
            return False
        
        # Skip duplicates
        if item['link'] in self.seen_urls:
            return False
        
        # Skip items older than 7 days
        if item.get('pub_date'):
            try:
                pub_date = datetime.fromisoformat(item['pub_date'].replace('Z', '+00:00'))
                if pub_date < datetime.now().replace(tzinfo=pub_date.tzinfo) - timedelta(days=7):
                    return False
            except (ValueError, TypeError):
                pass  # Include items with unparseable dates
        
        # Add more filtering logic as needed
        return True
    
    async def aggregate_feeds(self, feeds: Dict[str, str]) -> Dict[str, Any]:
        """
        Aggregate multiple RSS feeds.
        
        Args:
            feeds: Dictionary mapping feed URLs to categories
            
        Returns:
            Aggregation summary
        """
        print(f"Starting aggregation of {len(feeds)} feeds...")
        
        # Process feeds concurrently
        tasks = [
            self.add_feed(feed_url, category)
            for feed_url, category in feeds.items()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Summarize results
        successful_feeds = 0
        failed_feeds = 0
        total_items = 0
        
        for result in results:
            if isinstance(result, Exception):
                failed_feeds += 1
                print(f"Feed processing failed: {result}")
            elif result['status'] == 'success':
                successful_feeds += 1
                total_items += result['items_added']
            else:
                failed_feeds += 1
                print(f"Feed failed: {result['feed_url']} - {result['error']}")
        
        # Sort items by publication date (newest first)
        self.aggregated_items.sort(
            key=lambda x: x.get('pub_date', ''),
            reverse=True
        )
        
        return {
            "total_feeds": len(feeds),
            "successful_feeds": successful_feeds,
            "failed_feeds": failed_feeds,
            "total_items": total_items,
            "unique_items": len(self.aggregated_items),
            "processed_at": datetime.utcnow().isoformat()
        }
    
    def export_to_json(self, filename: str) -> None:
        """Export aggregated items to JSON file."""
        output_path = Path(filename)
        
        export_data = {
            "metadata": {
                "exported_at": datetime.utcnow().isoformat(),
                "total_items": len(self.aggregated_items)
            },
            "items": self.aggregated_items
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(self.aggregated_items)} items to {output_path}")
    
    def export_to_csv(self, filename: str) -> None:
        """Export aggregated items to CSV file."""
        if not self.aggregated_items:
            print("No items to export")
            return
        
        output_path = Path(filename)
        
        # Get all unique keys from items
        fieldnames = set()
        for item in self.aggregated_items:
            fieldnames.update(item.keys())
        
        fieldnames = sorted(fieldnames)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.aggregated_items)
        
        print(f"Exported {len(self.aggregated_items)} items to {output_path}")
    
    def get_category_summary(self) -> Dict[str, int]:
        """Get summary of items by category."""
        category_counts = {}
        for item in self.aggregated_items:
            category = item.get('category', 'unknown')
            category_counts[category] = category_counts.get(category, 0) + 1
        
        return category_counts


async def main():
    """Main example function."""
    # Define feeds to aggregate
    feeds = {
        "https://feeds.feedburner.com/oreilly/radar": "tech",
        "https://rss.cnn.com/rss/edition.rss": "news",
        "https://feeds.bbci.co.uk/news/rss.xml": "news",
        "https://feeds.feedburner.com/TechCrunch": "tech",
        "https://www.reddit.com/r/programming/.rss": "programming"
    }
    
    # Create aggregator
    aggregator = RSSFeedAggregator(cache_ttl=3600)  # 1 hour cache
    
    # Aggregate feeds
    summary = await aggregator.aggregate_feeds(feeds)
    
    # Print summary
    print("\n" + "="*50)
    print("AGGREGATION SUMMARY")
    print("="*50)
    print(f"Total feeds processed: {summary['total_feeds']}")
    print(f"Successful feeds: {summary['successful_feeds']}")
    print(f"Failed feeds: {summary['failed_feeds']}")
    print(f"Total items collected: {summary['total_items']}")
    print(f"Unique items after deduplication: {summary['unique_items']}")
    
    # Category breakdown
    category_summary = aggregator.get_category_summary()
    print(f"\nItems by category:")
    for category, count in sorted(category_summary.items()):
        print(f"  {category}: {count}")
    
    # Export results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    aggregator.export_to_json(f"aggregated_feeds_{timestamp}.json")
    aggregator.export_to_csv(f"aggregated_feeds_{timestamp}.csv")
    
    # Show recent items
    print(f"\nMost recent items:")
    for i, item in enumerate(aggregator.aggregated_items[:5]):
        print(f"{i+1}. [{item['category']}] {item['title']}")
        print(f"   Source: {item['source_title']}")
        print(f"   Published: {item.get('pub_date', 'Unknown')}")
        print(f"   URL: {item['link']}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
