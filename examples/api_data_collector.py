#!/usr/bin/env python3
"""
Authenticated API Data Collector Example

This example demonstrates how to use the authenticated API component to collect
data from multiple APIs with different authentication methods.

Features demonstrated:
- OAuth 2.0 authentication
- API key authentication
- JWT token authentication
- Rate limiting and retry logic
- Data transformation and aggregation
- Error handling and logging
"""

import asyncio
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from web_fetch import fetch_authenticated_api
from web_fetch.models.extended_resources import AuthenticatedAPIConfig
from web_fetch.models.resource import ResourceConfig, ResourceRequest, ResourceKind
from pydantic import AnyUrl


class APIDataCollector:
    """Collect data from multiple authenticated APIs."""
    
    def __init__(self):
        """Initialize the data collector."""
        self.resource_config = ResourceConfig(
            enable_cache=True,
            cache_ttl_seconds=300  # 5 minutes
        )
        
        self.collected_data: List[Dict[str, Any]] = []
    
    async def collect_github_data(self, username: str) -> Dict[str, Any]:
        """
        Collect GitHub user data using OAuth 2.0.
        
        Args:
            username: GitHub username to fetch data for
            
        Returns:
            Dictionary with user data and repositories
        """
        # GitHub OAuth 2.0 configuration
        github_config = AuthenticatedAPIConfig(
            auth_method="oauth2",
            auth_config={
                "token_url": "https://github.com/login/oauth/access_token",
                "client_id": os.getenv("GITHUB_CLIENT_ID"),
                "client_secret": os.getenv("GITHUB_CLIENT_SECRET"),
                "grant_type": "client_credentials",
                "scope": "public_repo user:read"
            },
            retry_on_auth_failure=True,
            base_headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "API-Data-Collector/1.0"
            }
        )
        
        try:
            # Fetch user profile
            user_result = await fetch_authenticated_api(
                f"https://api.github.com/users/{username}",
                config=self.resource_config,
                api_config=github_config
            )
            
            if not user_result.is_success:
                return {
                    "source": "github",
                    "username": username,
                    "status": "error",
                    "error": user_result.error
                }
            
            user_data = user_result.content
            
            # Fetch user repositories
            repos_result = await fetch_authenticated_api(
                f"https://api.github.com/users/{username}/repos?sort=updated&per_page=10",
                config=self.resource_config,
                api_config=github_config
            )
            
            repos_data = repos_result.content if repos_result.is_success else []
            
            return {
                "source": "github",
                "username": username,
                "status": "success",
                "profile": {
                    "name": user_data.get("name"),
                    "bio": user_data.get("bio"),
                    "public_repos": user_data.get("public_repos"),
                    "followers": user_data.get("followers"),
                    "following": user_data.get("following"),
                    "created_at": user_data.get("created_at")
                },
                "recent_repos": [
                    {
                        "name": repo["name"],
                        "description": repo.get("description"),
                        "language": repo.get("language"),
                        "stars": repo["stargazers_count"],
                        "updated_at": repo["updated_at"]
                    }
                    for repo in repos_data[:5]
                ],
                "collected_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "source": "github",
                "username": username,
                "status": "error",
                "error": str(e)
            }
    
    async def collect_weather_data(self, city: str) -> Dict[str, Any]:
        """
        Collect weather data using API key authentication.
        
        Args:
            city: City name to get weather for
            
        Returns:
            Dictionary with weather data
        """
        # Weather API configuration (using API key)
        weather_config = AuthenticatedAPIConfig(
            auth_method="api_key",
            auth_config={
                "api_key": os.getenv("WEATHER_API_KEY", "demo-key"),
                "key_name": "appid",
                "location": "query"  # Add as query parameter
            },
            base_headers={
                "Accept": "application/json"
            }
        )
        
        try:
            result = await fetch_authenticated_api(
                f"https://api.openweathermap.org/data/2.5/weather?q={city}&units=metric",
                config=self.resource_config,
                api_config=weather_config
            )
            
            if not result.is_success:
                return {
                    "source": "weather",
                    "city": city,
                    "status": "error",
                    "error": result.error
                }
            
            weather_data = result.content
            
            return {
                "source": "weather",
                "city": city,
                "status": "success",
                "data": {
                    "temperature": weather_data["main"]["temp"],
                    "feels_like": weather_data["main"]["feels_like"],
                    "humidity": weather_data["main"]["humidity"],
                    "pressure": weather_data["main"]["pressure"],
                    "description": weather_data["weather"][0]["description"],
                    "wind_speed": weather_data.get("wind", {}).get("speed"),
                    "visibility": weather_data.get("visibility")
                },
                "collected_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "source": "weather",
                "city": city,
                "status": "error",
                "error": str(e)
            }
    
    async def collect_jwt_api_data(self, endpoint: str, jwt_token: str) -> Dict[str, Any]:
        """
        Collect data from JWT-authenticated API.
        
        Args:
            endpoint: API endpoint URL
            jwt_token: JWT token for authentication
            
        Returns:
            Dictionary with API response data
        """
        # JWT authentication configuration
        jwt_config = AuthenticatedAPIConfig(
            auth_method="jwt",
            auth_config={
                "token": jwt_token,
                "header_name": "Authorization",
                "prefix": "Bearer",
                "verify_signature": False,  # Skip signature verification for demo
                "verify_expiry": True
            },
            base_headers={
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
        )
        
        try:
            result = await fetch_authenticated_api(
                endpoint,
                config=self.resource_config,
                api_config=jwt_config
            )
            
            if not result.is_success:
                return {
                    "source": "jwt_api",
                    "endpoint": endpoint,
                    "status": "error",
                    "error": result.error
                }
            
            return {
                "source": "jwt_api",
                "endpoint": endpoint,
                "status": "success",
                "data": result.content,
                "collected_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "source": "jwt_api",
                "endpoint": endpoint,
                "status": "error",
                "error": str(e)
            }
    
    async def collect_all_data(self, targets: Dict[str, Any]) -> Dict[str, Any]:
        """
        Collect data from all configured sources.
        
        Args:
            targets: Dictionary with collection targets
            
        Returns:
            Collection summary
        """
        print("Starting data collection from multiple APIs...")
        
        tasks = []
        
        # GitHub data collection
        if "github_users" in targets:
            for username in targets["github_users"]:
                tasks.append(self.collect_github_data(username))
        
        # Weather data collection
        if "weather_cities" in targets:
            for city in targets["weather_cities"]:
                tasks.append(self.collect_weather_data(city))
        
        # JWT API data collection
        if "jwt_endpoints" in targets:
            jwt_token = targets.get("jwt_token")
            if jwt_token:
                for endpoint in targets["jwt_endpoints"]:
                    tasks.append(self.collect_jwt_api_data(endpoint, jwt_token))
        
        # Execute all collection tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        successful_collections = 0
        failed_collections = 0
        
        for result in results:
            if isinstance(result, Exception):
                failed_collections += 1
                print(f"Collection failed with exception: {result}")
            elif result.get("status") == "success":
                successful_collections += 1
                self.collected_data.append(result)
            else:
                failed_collections += 1
                print(f"Collection failed: {result.get('error', 'Unknown error')}")
        
        return {
            "total_tasks": len(tasks),
            "successful_collections": successful_collections,
            "failed_collections": failed_collections,
            "total_data_points": len(self.collected_data),
            "collected_at": datetime.utcnow().isoformat()
        }
    
    def export_data(self, filename: str) -> None:
        """Export collected data to JSON file."""
        output_path = Path(filename)
        
        export_data = {
            "metadata": {
                "exported_at": datetime.utcnow().isoformat(),
                "total_items": len(self.collected_data)
            },
            "data": self.collected_data
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(self.collected_data)} data points to {output_path}")
    
    def get_summary_by_source(self) -> Dict[str, int]:
        """Get summary of collected data by source."""
        source_counts = {}
        for item in self.collected_data:
            source = item.get("source", "unknown")
            source_counts[source] = source_counts.get(source, 0) + 1
        
        return source_counts


async def main():
    """Main example function."""
    # Configuration for data collection
    targets = {
        "github_users": ["octocat", "torvalds"],
        "weather_cities": ["London", "New York", "Tokyo"],
        "jwt_endpoints": [
            "https://httpbin.org/bearer",  # Demo endpoint
        ],
        "jwt_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiYWRtaW4iOnRydWV9.TJVA95OrM7E2cBab30RMHrHDcEfxjoYZgeFONFh7HgQ"  # Demo JWT
    }
    
    # Create collector
    collector = APIDataCollector()
    
    # Collect data
    summary = await collector.collect_all_data(targets)
    
    # Print summary
    print("\n" + "="*50)
    print("DATA COLLECTION SUMMARY")
    print("="*50)
    print(f"Total collection tasks: {summary['total_tasks']}")
    print(f"Successful collections: {summary['successful_collections']}")
    print(f"Failed collections: {summary['failed_collections']}")
    print(f"Total data points collected: {summary['total_data_points']}")
    
    # Source breakdown
    source_summary = collector.get_summary_by_source()
    print(f"\nData points by source:")
    for source, count in sorted(source_summary.items()):
        print(f"  {source}: {count}")
    
    # Export results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    collector.export_data(f"api_data_collection_{timestamp}.json")
    
    # Show sample data
    print(f"\nSample collected data:")
    for i, item in enumerate(collector.collected_data[:3]):
        print(f"{i+1}. Source: {item['source']}")
        print(f"   Status: {item['status']}")
        if item['status'] == 'success':
            if item['source'] == 'github':
                print(f"   User: {item['username']} ({item['profile']['name']})")
                print(f"   Repos: {item['profile']['public_repos']}")
            elif item['source'] == 'weather':
                print(f"   City: {item['city']}")
                print(f"   Temperature: {item['data']['temperature']}°C")
        print()


if __name__ == "__main__":
    # Note: Set environment variables for API keys:
    # export GITHUB_CLIENT_ID="your_github_client_id"
    # export GITHUB_CLIENT_SECRET="your_github_client_secret"
    # export WEATHER_API_KEY="your_openweathermap_api_key"

    print("API Data Collector Example")
    print("=" * 50)
    print("This example demonstrates authenticated API data collection.")
    print("Make sure to set the required environment variables for API keys.")
    print()

    asyncio.run(main())
