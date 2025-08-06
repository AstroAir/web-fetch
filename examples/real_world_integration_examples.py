#!/usr/bin/env python3
"""
Real-world integration examples for the web-fetch library.

This script demonstrates practical use cases including:
- API integration patterns
- Web scraping workflows
- Data pipeline integration
- Microservice communication
- Content aggregation systems
- Monitoring and health checks
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from web_fetch import (
    WebFetcher,
    FetchConfig,
    FetchRequest,
    ContentType,
    CacheConfig,
    RateLimitConfig,
    fetch_url,
    fetch_urls,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class APIResponse:
    """Structured API response."""
    success: bool
    data: Any
    status_code: int
    response_time: float
    cached: bool = False


async def example_rest_api_integration():
    """Demonstrate REST API integration patterns."""
    print("=== REST API Integration Examples ===\n")
    
    # Configure for API usage
    config = FetchConfig(
        total_timeout=30.0,
        max_retries=3,
        retry_delay=1.0,
        max_concurrent_requests=5
    )
    
    # Cache configuration for API responses
    cache_config = CacheConfig(
        ttl_seconds=300,  # 5 minutes
        max_size=100
    )
    
    async with WebFetcher(config) as fetcher:
        print("1. Basic API Operations:")
        
        # GET request
        print("   GET /posts/1")
        result = await fetcher.fetch_single(
            FetchRequest(
                url="https://jsonplaceholder.typicode.com/posts/1",
                content_type=ContentType.JSON
            )
        )
        
        if result.is_success:
            post = result.content
            print(f"   ✅ Retrieved post: {post.get('title', 'No title')[:50]}...")
        else:
            print(f"   ❌ Failed: {result.error}")
        
        # POST request
        print("\n   POST /posts")
        new_post = {
            "title": "My New Post",
            "body": "This is the content of my new post.",
            "userId": 1
        }
        
        result = await fetcher.fetch_single(
            FetchRequest(
                url="https://jsonplaceholder.typicode.com/posts",
                method="POST",
                content_type=ContentType.JSON,
                data=json.dumps(new_post),
                headers={"Content-Type": "application/json"}
            )
        )
        
        if result.is_success:
            created_post = result.content
            print(f"   ✅ Created post with ID: {created_post.get('id')}")
        else:
            print(f"   ❌ Failed: {result.error}")
        
        # PUT request
        print("\n   PUT /posts/1")
        updated_post = {
            "id": 1,
            "title": "Updated Post Title",
            "body": "Updated content.",
            "userId": 1
        }
        
        result = await fetcher.fetch_single(
            FetchRequest(
                url="https://jsonplaceholder.typicode.com/posts/1",
                method="PUT",
                content_type=ContentType.JSON,
                data=json.dumps(updated_post),
                headers={"Content-Type": "application/json"}
            )
        )
        
        if result.is_success:
            print(f"   ✅ Updated post: {result.content.get('title')}")
        else:
            print(f"   ❌ Failed: {result.error}")
        
        # DELETE request
        print("\n   DELETE /posts/1")
        result = await fetcher.fetch_single(
            FetchRequest(
                url="https://jsonplaceholder.typicode.com/posts/1",
                method="DELETE"
            )
        )
        
        if result.is_success:
            print(f"   ✅ Deleted post (status: {result.status_code})")
        else:
            print(f"   ❌ Failed: {result.error}")
    
    print()


async def example_web_scraping_workflow():
    """Demonstrate web scraping workflow patterns."""
    print("=== Web Scraping Workflow Examples ===\n")
    
    class WebScraper:
        """Example web scraper class."""
        
        def __init__(self):
            self.config = FetchConfig(
                total_timeout=20.0,
                max_retries=2,
                max_concurrent_requests=3,
                verify_ssl=True
            )
            self.rate_limit = RateLimitConfig(
                requests_per_second=2.0,  # Be respectful
                burst_size=5
            )
        
        async def scrape_news_headlines(self) -> List[Dict[str, str]]:
            """Scrape news headlines from a website."""
            print("   Scraping news headlines...")
            
            async with WebFetcher(self.config) as fetcher:
                # Fetch the main page
                result = await fetcher.fetch_single(
                    FetchRequest(
                        url="https://httpbin.org/html",  # Demo URL
                        content_type=ContentType.HTML
                    )
                )
                
                if not result.is_success:
                    print(f"   ❌ Failed to fetch page: {result.error}")
                    return []
                
                # Extract structured data
                page_data = result.content
                headlines = []
                
                # Simulate headline extraction
                if isinstance(page_data, dict):
                    links = page_data.get('links', [])
                    for i, link in enumerate(links[:5]):  # First 5 links
                        headlines.append({
                            'title': f"Headline {i+1}: {link.get('text', 'No title')}",
                            'url': link.get('href', ''),
                            'scraped_at': datetime.now().isoformat()
                        })
                
                print(f"   ✅ Scraped {len(headlines)} headlines")
                return headlines
        
        async def scrape_product_details(self, product_urls: List[str]) -> List[Dict]:
            """Scrape product details from multiple URLs."""
            print(f"   Scraping {len(product_urls)} product pages...")
            
            # Use batch processing for efficiency
            results = await fetch_urls(
                product_urls,
                ContentType.HTML,
                self.config
            )
            
            products = []
            for result in results.results:
                if result.is_success:
                    # Simulate product data extraction
                    product = {
                        'url': result.url,
                        'title': f"Product from {result.url}",
                        'price': f"${(hash(result.url) % 100) + 10}.99",  # Fake price
                        'availability': 'In Stock',
                        'scraped_at': datetime.now().isoformat()
                    }
                    products.append(product)
                else:
                    print(f"   ❌ Failed to scrape {result.url}: {result.error}")
            
            print(f"   ✅ Successfully scraped {len(products)} products")
            return products
    
    # Demonstrate scraping workflow
    scraper = WebScraper()
    
    print("1. News Headlines Scraping:")
    headlines = await scraper.scrape_news_headlines()
    for headline in headlines[:3]:  # Show first 3
        print(f"   - {headline['title'][:60]}...")
    
    print("\n2. Product Details Scraping:")
    product_urls = [
        "https://httpbin.org/html",
        "https://httpbin.org/json",
        "https://httpbin.org/xml"
    ]
    products = await scraper.scrape_product_details(product_urls)
    for product in products:
        print(f"   - {product['title']}: {product['price']}")
    
    print()


async def example_data_pipeline_integration():
    """Demonstrate data pipeline integration patterns."""
    print("=== Data Pipeline Integration Examples ===\n")
    
    class DataPipeline:
        """Example data pipeline processor."""
        
        def __init__(self):
            self.config = FetchConfig(
                total_timeout=60.0,
                max_retries=3,
                max_concurrent_requests=10
            )
            self.cache_config = CacheConfig(
                ttl_seconds=3600,  # 1 hour
                max_size=500
            )
        
        async def extract_data_sources(self) -> List[Dict]:
            """Extract data from multiple sources."""
            print("   Extracting data from sources...")
            
            data_sources = [
                {
                    'name': 'API Source 1',
                    'url': 'https://jsonplaceholder.typicode.com/posts',
                    'type': 'json'
                },
                {
                    'name': 'API Source 2',
                    'url': 'https://jsonplaceholder.typicode.com/users',
                    'type': 'json'
                },
                {
                    'name': 'Web Source',
                    'url': 'https://httpbin.org/html',
                    'type': 'html'
                }
            ]
            
            extracted_data = []
            
            async with WebFetcher(self.config) as fetcher:
                for source in data_sources:
                    try:
                        content_type = ContentType.JSON if source['type'] == 'json' else ContentType.HTML
                        
                        result = await fetcher.fetch_single(
                            FetchRequest(
                                url=source['url'],
                                content_type=content_type
                            )
                        )
                        
                        if result.is_success:
                            extracted_data.append({
                                'source': source['name'],
                                'data': result.content,
                                'extracted_at': datetime.now().isoformat(),
                                'size': len(str(result.content))
                            })
                            print(f"   ✅ Extracted from {source['name']}: {len(str(result.content))} chars")
                        else:
                            print(f"   ❌ Failed to extract from {source['name']}: {result.error}")
                    
                    except Exception as e:
                        print(f"   ❌ Error extracting from {source['name']}: {e}")
            
            return extracted_data
        
        async def transform_data(self, raw_data: List[Dict]) -> List[Dict]:
            """Transform extracted data."""
            print("   Transforming data...")
            
            transformed_data = []
            
            for item in raw_data:
                try:
                    # Simulate data transformation
                    transformed_item = {
                        'id': hash(item['source']) % 10000,
                        'source': item['source'],
                        'processed_at': datetime.now().isoformat(),
                        'record_count': len(item['data']) if isinstance(item['data'], list) else 1,
                        'data_size': item['size'],
                        'status': 'processed'
                    }
                    
                    transformed_data.append(transformed_item)
                    print(f"   ✅ Transformed {item['source']}")
                
                except Exception as e:
                    print(f"   ❌ Error transforming {item['source']}: {e}")
            
            return transformed_data
        
        async def load_data(self, transformed_data: List[Dict]) -> bool:
            """Load transformed data to destination."""
            print("   Loading data to destination...")
            
            # Simulate loading to a destination API
            destination_url = "https://httpbin.org/post"
            
            async with WebFetcher(self.config) as fetcher:
                try:
                    result = await fetcher.fetch_single(
                        FetchRequest(
                            url=destination_url,
                            method="POST",
                            content_type=ContentType.JSON,
                            data=json.dumps({
                                'pipeline_run': datetime.now().isoformat(),
                                'records': transformed_data,
                                'total_records': len(transformed_data)
                            }),
                            headers={"Content-Type": "application/json"}
                        )
                    )
                    
                    if result.is_success:
                        print(f"   ✅ Loaded {len(transformed_data)} records successfully")
                        return True
                    else:
                        print(f"   ❌ Failed to load data: {result.error}")
                        return False
                
                except Exception as e:
                    print(f"   ❌ Error loading data: {e}")
                    return False
        
        async def run_pipeline(self) -> bool:
            """Run the complete data pipeline."""
            print("Running data pipeline...")
            
            try:
                # Extract
                raw_data = await self.extract_data_sources()
                if not raw_data:
                    print("   ❌ No data extracted")
                    return False
                
                # Transform
                transformed_data = await self.transform_data(raw_data)
                if not transformed_data:
                    print("   ❌ No data transformed")
                    return False
                
                # Load
                success = await self.load_data(transformed_data)
                
                if success:
                    print("   ✅ Pipeline completed successfully")
                else:
                    print("   ❌ Pipeline failed at load stage")
                
                return success
            
            except Exception as e:
                print(f"   ❌ Pipeline failed: {e}")
                return False
    
    # Run the pipeline
    pipeline = DataPipeline()
    success = await pipeline.run_pipeline()
    print(f"Pipeline result: {'Success' if success else 'Failed'}")
    
    print()


async def example_microservice_communication():
    """Demonstrate microservice communication patterns."""
    print("=== Microservice Communication Examples ===\n")
    
    class ServiceClient:
        """Client for communicating with microservices."""
        
        def __init__(self, base_url: str, service_name: str):
            self.base_url = base_url.rstrip('/')
            self.service_name = service_name
            self.config = FetchConfig(
                total_timeout=15.0,
                max_retries=3,
                max_concurrent_requests=20
            )
        
        async def health_check(self) -> bool:
            """Check if the service is healthy."""
            try:
                async with WebFetcher(self.config) as fetcher:
                    result = await fetcher.fetch_single(
                        FetchRequest(
                            url=f"{self.base_url}/health",
                            content_type=ContentType.JSON
                        )
                    )
                    
                    return result.is_success and result.status_code == 200
            
            except Exception:
                return False
        
        async def get_user(self, user_id: int) -> Optional[Dict]:
            """Get user information."""
            async with WebFetcher(self.config) as fetcher:
                result = await fetcher.fetch_single(
                    FetchRequest(
                        url=f"{self.base_url}/users/{user_id}",
                        content_type=ContentType.JSON
                    )
                )
                
                if result.is_success:
                    return result.content
                else:
                    logger.error(f"Failed to get user {user_id}: {result.error}")
                    return None
        
        async def create_order(self, order_data: Dict) -> Optional[Dict]:
            """Create a new order."""
            async with WebFetcher(self.config) as fetcher:
                result = await fetcher.fetch_single(
                    FetchRequest(
                        url=f"{self.base_url}/orders",
                        method="POST",
                        content_type=ContentType.JSON,
                        data=json.dumps(order_data),
                        headers={"Content-Type": "application/json"}
                    )
                )
                
                if result.is_success:
                    return result.content
                else:
                    logger.error(f"Failed to create order: {result.error}")
                    return None
    
    # Simulate microservice communication
    print("1. Service Health Checks:")
    
    services = [
        ServiceClient("https://jsonplaceholder.typicode.com", "user-service"),
        ServiceClient("https://httpbin.org", "order-service"),
    ]
    
    for service in services:
        is_healthy = await service.health_check()
        status = "✅ Healthy" if is_healthy else "❌ Unhealthy"
        print(f"   {service.service_name}: {status}")
    
    print("\n2. Service Operations:")
    
    user_service = services[0]
    
    # Get user
    user = await user_service.get_user(1)
    if user:
        print(f"   ✅ Retrieved user: {user.get('name', 'Unknown')}")
    else:
        print("   ❌ Failed to retrieve user")
    
    # Create order (simulated)
    order_data = {
        "user_id": 1,
        "items": [{"product_id": 123, "quantity": 2}],
        "total": 29.99
    }
    
    # Use httpbin for POST simulation
    order_service = ServiceClient("https://httpbin.org", "order-service")
    order = await order_service.create_order(order_data)
    if order:
        print("   ✅ Created order successfully")
    else:
        print("   ❌ Failed to create order")
    
    print()


async def main():
    """Run all real-world integration examples."""
    print("Web Fetch Library - Real-World Integration Examples")
    print("=" * 70)
    print()
    
    try:
        await example_rest_api_integration()
        await example_web_scraping_workflow()
        await example_data_pipeline_integration()
        await example_microservice_communication()
        
        print("🎉 All real-world integration examples completed!")
        print("\nKey Integration Patterns Demonstrated:")
        print("- REST API CRUD operations")
        print("- Web scraping with rate limiting")
        print("- ETL data pipeline processing")
        print("- Microservice communication")
        print("- Health checks and monitoring")
        print("- Error handling and resilience")
        
    except Exception as e:
        print(f"❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
