#!/usr/bin/env python3
"""
Comprehensive Integration Example

This example demonstrates how to integrate all extended resource types
(RSS feeds, authenticated APIs, databases, and cloud storage) in a
real-world data processing pipeline.

Use Case: News Aggregation and Analysis Pipeline
- Fetch news from RSS feeds
- Enrich with external API data
- Store in database
- Archive to cloud storage
- Generate analytics reports

Features demonstrated:
- Multi-resource type integration
- Data pipeline orchestration
- Error handling and recovery
- Performance monitoring
- Comprehensive logging
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path

from web_fetch import (
    fetch_rss_feed, fetch_authenticated_api, 
    fetch_database_query, fetch_cloud_storage
)
from web_fetch.models.extended_resources import (
    RSSConfig, AuthenticatedAPIConfig, DatabaseConfig, DatabaseQuery,
    CloudStorageConfig, CloudStorageOperation, DatabaseType, CloudStorageProvider
)
from web_fetch.models.resource import ResourceConfig
from pydantic import SecretStr


class NewsAggregationPipeline:
    """Comprehensive news aggregation and analysis pipeline."""
    
    def __init__(self):
        """Initialize the pipeline."""
        self.resource_config = ResourceConfig(
            enable_cache=True,
            cache_ttl_seconds=1800  # 30 minutes
        )
        
        self.pipeline_stats = {
            "feeds_processed": 0,
            "articles_collected": 0,
            "articles_enriched": 0,
            "articles_stored": 0,
            "files_archived": 0,
            "errors": []
        }
    
    def get_rss_config(self) -> RSSConfig:
        """Get RSS configuration."""
        return RSSConfig(
            max_items=50,
            include_content=True,
            validate_dates=True,
            follow_redirects=True,
            user_agent="NewsAggregator/1.0 (+https://example.com/contact)"
        )
    
    def get_sentiment_api_config(self) -> AuthenticatedAPIConfig:
        """Get sentiment analysis API configuration."""
        return AuthenticatedAPIConfig(
            auth_method="api_key",
            auth_config={
                "api_key": os.getenv("SENTIMENT_API_KEY", "demo-key"),
                "key_name": "X-API-Key",
                "location": "header"
            },
            base_headers={
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
        )
    
    def get_database_config(self) -> DatabaseConfig:
        """Get database configuration."""
        return DatabaseConfig(
            database_type=DatabaseType.POSTGRESQL,
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "news_db"),
            username=os.getenv("DB_USER", "postgres"),
            password=SecretStr(os.getenv("DB_PASSWORD", "password")),
            min_connections=2,
            max_connections=10,
            connection_timeout=30.0,
            query_timeout=60.0
        )
    
    def get_storage_config(self) -> CloudStorageConfig:
        """Get cloud storage configuration."""
        return CloudStorageConfig(
            provider=CloudStorageProvider.AWS_S3,
            bucket_name=os.getenv("S3_BUCKET", "news-archive"),
            access_key=SecretStr(os.getenv("AWS_ACCESS_KEY_ID", "access-key")),
            secret_key=SecretStr(os.getenv("AWS_SECRET_ACCESS_KEY", "secret-key")),
            region=os.getenv("AWS_REGION", "us-east-1")
        )
    
    async def fetch_news_feeds(self, feed_urls: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch articles from RSS feeds.
        
        Args:
            feed_urls: List of RSS feed URLs
            
        Returns:
            List of articles with metadata
        """
        print("Fetching news from RSS feeds...")
        
        rss_config = self.get_rss_config()
        articles = []
        
        # Fetch feeds concurrently
        tasks = [
            fetch_rss_feed(url, config=self.resource_config, rss_config=rss_config)
            for url in feed_urls
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            feed_url = feed_urls[i]
            
            if isinstance(result, Exception):
                self.pipeline_stats["errors"].append(f"Feed fetch failed: {feed_url} - {result}")
                continue
            
            if not result.is_success:
                self.pipeline_stats["errors"].append(f"Feed fetch failed: {feed_url} - {result.error}")
                continue
            
            self.pipeline_stats["feeds_processed"] += 1
            feed_data = result.content
            
            # Process articles from this feed
            for item in feed_data["items"]:
                article = {
                    "title": item.get("title", ""),
                    "description": item.get("description", ""),
                    "link": item.get("link", ""),
                    "pub_date": item.get("pub_date"),
                    "author": item.get("author"),
                    "categories": item.get("categories", []),
                    "source_feed": feed_url,
                    "source_title": feed_data.get("title", "Unknown"),
                    "collected_at": datetime.utcnow().isoformat(),
                    "sentiment_score": None,  # To be filled by enrichment
                    "sentiment_label": None
                }
                articles.append(article)
        
        self.pipeline_stats["articles_collected"] = len(articles)
        print(f"Collected {len(articles)} articles from {self.pipeline_stats['feeds_processed']} feeds")
        
        return articles
    
    async def enrich_with_sentiment(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Enrich articles with sentiment analysis.
        
        Args:
            articles: List of articles to enrich
            
        Returns:
            Enriched articles with sentiment data
        """
        print("Enriching articles with sentiment analysis...")
        
        api_config = self.get_sentiment_api_config()
        enriched_articles = []
        
        # Process articles in batches to avoid rate limits
        batch_size = 10
        for i in range(0, len(articles), batch_size):
            batch = articles[i:i + batch_size]
            
            # Create sentiment analysis tasks
            tasks = []
            for article in batch:
                # Use title + description for sentiment analysis
                text = f"{article['title']} {article['description']}"[:500]  # Limit text length
                
                # Mock sentiment API call (replace with real API)
                async def analyze_sentiment(text_content: str, article_data: Dict[str, Any]):
                    try:
                        # This would be a real API call in production
                        # result = await fetch_authenticated_api(
                        #     "https://api.sentiment-analyzer.com/analyze",
                        #     config=self.resource_config,
                        #     api_config=api_config,
                        #     method="POST",
                        #     json={"text": text_content}
                        # )
                        
                        # Mock sentiment analysis result
                        import random
                        sentiment_score = random.uniform(-1.0, 1.0)
                        sentiment_label = "positive" if sentiment_score > 0.1 else "negative" if sentiment_score < -0.1 else "neutral"
                        
                        article_data["sentiment_score"] = round(sentiment_score, 3)
                        article_data["sentiment_label"] = sentiment_label
                        article_data["enriched_at"] = datetime.utcnow().isoformat()
                        
                        return article_data
                        
                    except Exception as e:
                        self.pipeline_stats["errors"].append(f"Sentiment analysis failed: {e}")
                        return article_data
                
                tasks.append(analyze_sentiment(text, article.copy()))
            
            # Execute batch
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, Exception):
                    self.pipeline_stats["errors"].append(f"Enrichment failed: {result}")
                else:
                    enriched_articles.append(result)
                    if result.get("sentiment_score") is not None:
                        self.pipeline_stats["articles_enriched"] += 1
            
            # Rate limiting delay
            await asyncio.sleep(1)
        
        print(f"Enriched {self.pipeline_stats['articles_enriched']} articles with sentiment data")
        return enriched_articles
    
    async def store_in_database(self, articles: List[Dict[str, Any]]) -> bool:
        """
        Store articles in database.
        
        Args:
            articles: List of articles to store
            
        Returns:
            True if successful
        """
        print("Storing articles in database...")
        
        db_config = self.get_database_config()
        
        try:
            # Create table if not exists
            create_table_query = DatabaseQuery(
                query="""
                CREATE TABLE IF NOT EXISTS articles (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    link TEXT UNIQUE,
                    pub_date TIMESTAMP,
                    author TEXT,
                    categories TEXT[],
                    source_feed TEXT,
                    source_title TEXT,
                    sentiment_score FLOAT,
                    sentiment_label TEXT,
                    collected_at TIMESTAMP,
                    enriched_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                fetch_mode="none"
            )
            
            await fetch_database_query(db_config, create_table_query, config=self.resource_config)
            
            # Insert articles
            stored_count = 0
            for article in articles:
                insert_query = DatabaseQuery(
                    query="""
                    INSERT INTO articles (
                        title, description, link, pub_date, author, categories,
                        source_feed, source_title, sentiment_score, sentiment_label,
                        collected_at, enriched_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    ON CONFLICT (link) DO UPDATE SET
                        sentiment_score = EXCLUDED.sentiment_score,
                        sentiment_label = EXCLUDED.sentiment_label,
                        enriched_at = EXCLUDED.enriched_at
                    """,
                    parameters={
                        "$1": article["title"],
                        "$2": article["description"],
                        "$3": article["link"],
                        "$4": article.get("pub_date"),
                        "$5": article.get("author"),
                        "$6": article.get("categories", []),
                        "$7": article["source_feed"],
                        "$8": article["source_title"],
                        "$9": article.get("sentiment_score"),
                        "$10": article.get("sentiment_label"),
                        "$11": article["collected_at"],
                        "$12": article.get("enriched_at")
                    },
                    fetch_mode="none"
                )
                
                result = await fetch_database_query(db_config, insert_query, config=self.resource_config)
                if result.is_success:
                    stored_count += 1
                else:
                    self.pipeline_stats["errors"].append(f"Database insert failed: {result.error}")
            
            self.pipeline_stats["articles_stored"] = stored_count
            print(f"Stored {stored_count} articles in database")
            return True
            
        except Exception as e:
            self.pipeline_stats["errors"].append(f"Database operation failed: {e}")
            return False
    
    async def archive_to_cloud(self, articles: List[Dict[str, Any]]) -> bool:
        """
        Archive articles to cloud storage.
        
        Args:
            articles: List of articles to archive
            
        Returns:
            True if successful
        """
        print("Archiving articles to cloud storage...")
        
        storage_config = self.get_storage_config()
        
        try:
            # Create archive file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_data = {
                "metadata": {
                    "created_at": datetime.utcnow().isoformat(),
                    "article_count": len(articles),
                    "pipeline_stats": self.pipeline_stats
                },
                "articles": articles
            }
            
            # Save to temporary file
            temp_file = f"/tmp/news_archive_{timestamp}.json"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(archive_data, f, indent=2, ensure_ascii=False)
            
            # Upload to cloud storage
            operation = CloudStorageOperation(
                operation="put",
                key=f"archives/{timestamp}/news_articles.json",
                local_path=temp_file,
                metadata={
                    "content_type": "application/json",
                    "article_count": str(len(articles)),
                    "created_by": "news_aggregation_pipeline"
                }
            )
            
            result = await fetch_cloud_storage(storage_config, operation, config=self.resource_config)
            
            # Clean up temp file
            Path(temp_file).unlink()
            
            if result.is_success:
                self.pipeline_stats["files_archived"] = 1
                print(f"Archived {len(articles)} articles to cloud storage")
                return True
            else:
                self.pipeline_stats["errors"].append(f"Cloud archive failed: {result.error}")
                return False
                
        except Exception as e:
            self.pipeline_stats["errors"].append(f"Archive operation failed: {e}")
            return False
    
    async def run_pipeline(self, feed_urls: List[str]) -> Dict[str, Any]:
        """
        Run the complete news aggregation pipeline.
        
        Args:
            feed_urls: List of RSS feed URLs to process
            
        Returns:
            Pipeline execution summary
        """
        start_time = datetime.utcnow()
        print("Starting news aggregation pipeline...")
        print(f"Processing {len(feed_urls)} RSS feeds")
        
        try:
            # Step 1: Fetch news from RSS feeds
            articles = await self.fetch_news_feeds(feed_urls)
            
            if not articles:
                return {
                    "status": "completed",
                    "message": "No articles collected",
                    "stats": self.pipeline_stats,
                    "duration": (datetime.utcnow() - start_time).total_seconds()
                }
            
            # Step 2: Enrich with sentiment analysis
            enriched_articles = await self.enrich_with_sentiment(articles)
            
            # Step 3: Store in database
            db_success = await self.store_in_database(enriched_articles)
            
            # Step 4: Archive to cloud storage
            archive_success = await self.archive_to_cloud(enriched_articles)
            
            # Generate summary
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            return {
                "status": "completed",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "database_success": db_success,
                "archive_success": archive_success,
                "stats": self.pipeline_stats
            }
            
        except Exception as e:
            self.pipeline_stats["errors"].append(f"Pipeline failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "stats": self.pipeline_stats,
                "duration": (datetime.utcnow() - start_time).total_seconds()
            }


async def main():
    """Main example function."""
    # News feed URLs to process
    feed_urls = [
        "https://rss.cnn.com/rss/edition.rss",
        "https://feeds.bbci.co.uk/news/rss.xml",
        "https://feeds.feedburner.com/TechCrunch",
        "https://www.reddit.com/r/worldnews/.rss"
    ]
    
    # Create and run pipeline
    pipeline = NewsAggregationPipeline()
    summary = await pipeline.run_pipeline(feed_urls)
    
    # Print results
    print("\n" + "="*60)
    print("NEWS AGGREGATION PIPELINE SUMMARY")
    print("="*60)
    print(f"Status: {summary['status']}")
    print(f"Duration: {summary.get('duration_seconds', 0):.2f} seconds")
    
    if summary['status'] == 'completed':
        stats = summary['stats']
        print(f"Feeds processed: {stats['feeds_processed']}")
        print(f"Articles collected: {stats['articles_collected']}")
        print(f"Articles enriched: {stats['articles_enriched']}")
        print(f"Articles stored: {stats['articles_stored']}")
        print(f"Files archived: {stats['files_archived']}")
        print(f"Database success: {summary['database_success']}")
        print(f"Archive success: {summary['archive_success']}")
        
        if stats['errors']:
            print(f"\nErrors encountered: {len(stats['errors'])}")
            for error in stats['errors'][:5]:  # Show first 5 errors
                print(f"  - {error}")
    else:
        print(f"Pipeline failed: {summary.get('error', 'Unknown error')}")
    
    # Save detailed results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"pipeline_results_{timestamp}.json"
    
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"\nDetailed results saved to: {results_file}")


if __name__ == "__main__":
    print("Comprehensive Integration Example")
    print("=" * 60)
    print("This example demonstrates a complete news aggregation pipeline")
    print("integrating RSS feeds, APIs, database, and cloud storage.")
    print()
    print("Configure services via environment variables:")
    print("- Database: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD")
    print("- Cloud Storage: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, S3_BUCKET, AWS_REGION")
    print("- Sentiment API: SENTIMENT_API_KEY")
    print()
    
    asyncio.run(main())
