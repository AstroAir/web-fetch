"""
Extended Resource Types Examples

This module demonstrates usage of the new extended resource types:
- RSS/Atom feeds
- Authenticated APIs  
- Database connections
- Cloud storage operations
"""

import asyncio
import json
from pathlib import Path
from pydantic import AnyUrl

from web_fetch.convenience import (
    fetch_rss_feed, fetch_authenticated_api,
    execute_database_query, cloud_storage_operation
)
from web_fetch.models.extended_resources import (
    DatabaseConfig, DatabaseType, CloudStorageConfig, CloudStorageProvider
)
from web_fetch.models.resource import ResourceConfig, ResourceRequest, ResourceKind
from web_fetch.components.manager import ResourceManager


async def rss_feed_examples():
    """Examples of RSS/Atom feed parsing."""
    print("=== RSS/Atom Feed Examples ===")
    
    # Basic RSS feed parsing
    print("\n1. Basic RSS Feed Parsing")
    result = await fetch_rss_feed(
        "https://feeds.feedburner.com/oreilly/radar",
        max_items=5,
        include_content=True
    )
    
    if result.is_success:
        feed_data = result.content
        print(f"Feed: {feed_data['title']}")
        print(f"Description: {feed_data['description']}")
        print(f"Items: {len(feed_data['items'])}")
        
        for i, item in enumerate(feed_data['items'][:3], 1):
            print(f"  {i}. {item['title']}")
            print(f"     Link: {item['link']}")
            print(f"     Date: {item.get('pub_date', 'N/A')}")
    else:
        print(f"Error: {result.error}")
    
    # RSS feed with caching
    print("\n2. RSS Feed with Caching")
    config = ResourceConfig(
        enable_cache=True,
        cache_ttl_seconds=300  # 5 minutes
    )
    
    result = await fetch_rss_feed(
        "https://rss.cnn.com/rss/edition.rss",
        max_items=10,
        config=config
    )
    
    if result.is_success:
        print(f"Cached feed with {len(result.content['items'])} items")
        
        # Check metadata
        metadata = result.metadata
        if 'feed_metadata' in metadata:
            feed_meta = metadata['feed_metadata']
            print(f"Feed type: {feed_meta.get('feed_type', 'Unknown')}")
            print(f"Language: {feed_meta.get('language', 'Unknown')}")


async def authenticated_api_examples():
    """Examples of authenticated API access."""
    print("\n=== Authenticated API Examples ===")
    
    # API Key authentication example
    print("\n1. API Key Authentication")
    try:
        result = await fetch_authenticated_api(
            "https://api.github.com/user",
            auth_method="api_key",
            auth_config={
                "api_key": "your-github-token",  # Replace with actual token
                "key_name": "Authorization",
                "location": "header",
                "prefix": "token"
            },
            method="GET",
            headers={"Accept": "application/vnd.github.v3+json"}
        )
        
        if result.is_success:
            user_data = result.content
            print(f"GitHub user: {user_data.get('login', 'Unknown')}")
            print(f"Name: {user_data.get('name', 'N/A')}")
        else:
            print(f"API Error: {result.error}")
    except Exception as e:
        print(f"Authentication setup error: {e}")
    
    # OAuth 2.0 example (mock configuration)
    print("\n2. OAuth 2.0 Authentication (Example Configuration)")
    oauth_config = {
        "token_url": "https://api.example.com/oauth/token",
        "client_id": "your-client-id",
        "client_secret": "your-client-secret",
        "grant_type": "client_credentials",
        "scope": "read write"
    }
    
    print(f"OAuth config example: {json.dumps(oauth_config, indent=2)}")
    
    # Basic authentication example
    print("\n3. Basic Authentication (Example)")
    basic_config = {
        "username": "your-username",
        "password": "your-password"
    }
    
    print(f"Basic auth config: {json.dumps(basic_config, indent=2)}")


async def database_examples():
    """Examples of database operations."""
    print("\n=== Database Examples ===")
    
    # PostgreSQL example
    print("\n1. PostgreSQL Example")
    pg_config = DatabaseConfig(
        database_type=DatabaseType.POSTGRESQL,
        host="localhost",
        port=5432,
        database="testdb",
        username="testuser",
        password="testpass",
        min_connections=1,
        max_connections=5
    )
    
    print(f"PostgreSQL config: {pg_config.database_type.value}://{pg_config.host}:{pg_config.port}/{pg_config.database}")
    
    # Example query (would work with actual database)
    sample_query = "SELECT id, name, email FROM users WHERE active = $1 LIMIT $2"
    print(f"Sample query: {sample_query}")
    
    # MongoDB example
    print("\n2. MongoDB Example")
    mongo_config = DatabaseConfig(
        database_type=DatabaseType.MONGODB,
        host="localhost",
        port=27017,
        database="testdb",
        username="testuser",
        password="testpass",
        extra_params={
            "authSource": "admin",
            "ssl": False
        }
    )
    
    mongo_query = {
        "collection": "users",
        "operation": "find",
        "filter": {"status": "active"}
    }
    
    print(f"MongoDB config: {mongo_config.database_type.value}://{mongo_config.host}:{mongo_config.port}")
    print(f"Sample MongoDB query: {json.dumps(mongo_query, indent=2)}")
    
    # MySQL example
    print("\n3. MySQL Example")
    mysql_config = DatabaseConfig(
        database_type=DatabaseType.MYSQL,
        host="localhost",
        port=3306,
        database="testdb",
        username="testuser",
        password="testpass"
    )
    
    mysql_query = "SELECT COUNT(*) as total FROM products WHERE category = %s"
    print(f"MySQL config: {mysql_config.database_type.value}://{mysql_config.host}:{mysql_config.port}")
    print(f"Sample MySQL query: {mysql_query}")


async def cloud_storage_examples():
    """Examples of cloud storage operations."""
    print("\n=== Cloud Storage Examples ===")
    
    # AWS S3 example
    print("\n1. AWS S3 Example")
    s3_config = CloudStorageConfig(
        provider=CloudStorageProvider.AWS_S3,
        bucket_name="my-test-bucket",
        access_key="AKIAIOSFODNN7EXAMPLE",  # Example key
        secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",  # Example key
        region="us-east-1"
    )
    
    print(f"S3 bucket: {s3_config.bucket_name} in {s3_config.region}")
    
    # List operation example
    print("List operation example:")
    list_operation = {
        "operation": "list",
        "prefix": "documents/"
    }
    print(f"  {json.dumps(list_operation, indent=2)}")
    
    # Upload operation example
    print("Upload operation example:")
    upload_operation = {
        "operation": "put",
        "key": "uploads/document.pdf",
        "local_path": "./local-file.pdf",
        "content_type": "application/pdf",
        "metadata": {"author": "John Doe", "version": "1.0"}
    }
    print(f"  {json.dumps(upload_operation, indent=2)}")
    
    # Google Cloud Storage example
    print("\n2. Google Cloud Storage Example")
    gcs_config = CloudStorageConfig(
        provider=CloudStorageProvider.GOOGLE_CLOUD,
        bucket_name="my-gcs-bucket",
        extra_config={
            "credentials_path": "/path/to/service-account.json"
        }
    )
    
    print(f"GCS bucket: {gcs_config.bucket_name}")
    print(f"Provider: {gcs_config.provider.value}")
    
    # Azure Blob Storage example
    print("\n3. Azure Blob Storage Example")
    azure_config = CloudStorageConfig(
        provider=CloudStorageProvider.AZURE_BLOB,
        bucket_name="my-container",
        access_key="mystorageaccount",
        secret_key="storage-account-key"
    )
    
    print(f"Azure container: {azure_config.bucket_name}")
    print(f"Storage account: {azure_config.access_key}")


async def unified_manager_examples():
    """Examples using the unified ResourceManager."""
    print("\n=== Unified Resource Manager Examples ===")
    
    manager = ResourceManager()
    
    # List available components
    print("\n1. Available Components")
    components = manager.list_components()
    for kind, component_class in components.items():
        print(f"  {kind}: {component_class}")
    
    # Create components
    print("\n2. Component Creation")
    try:
        rss_component = manager.get_component(ResourceKind.RSS)
        print(f"RSS component: {type(rss_component).__name__}")
        
        api_component = manager.get_component(ResourceKind.API_AUTH)
        print(f"API component: {type(api_component).__name__}")
        
        db_component = manager.get_component(ResourceKind.DATABASE)
        print(f"Database component: {type(db_component).__name__}")
        
        storage_component = manager.get_component(ResourceKind.CLOUD_STORAGE)
        print(f"Storage component: {type(storage_component).__name__}")
    except Exception as e:
        print(f"Component creation error: {e}")
    
    # Unified request example
    print("\n3. Unified Request Example")
    rss_request = ResourceRequest(
        uri=AnyUrl("https://feeds.feedburner.com/oreilly/radar"),
        kind=ResourceKind.RSS,
        options={"max_items": 5}
    )
    
    print(f"RSS request: {rss_request.kind.value} -> {rss_request.uri}")
    
    # Note: Actual fetch would require valid feed URL
    # result = await manager.fetch(rss_request)


async def error_handling_examples():
    """Examples of error handling patterns."""
    print("\n=== Error Handling Examples ===")
    
    # Invalid RSS feed
    print("\n1. Invalid RSS Feed")
    result = await fetch_rss_feed("https://httpbin.org/status/404")
    
    if not result.is_success:
        print(f"Error: {result.error}")
        print(f"Status code: {result.status_code}")
    
    # Invalid API endpoint
    print("\n2. Invalid API Endpoint")
    try:
        result = await fetch_authenticated_api(
            "https://httpbin.org/status/401",
            auth_method="api_key",
            auth_config={
                "api_key": "invalid-key",
                "key_name": "X-API-Key",
                "location": "header"
            }
        )
        
        if not result.is_success:
            print(f"API Error: {result.error}")
            print(f"Status code: {result.status_code}")
            
            # Check authentication metadata
            if 'authentication' in result.metadata:
                auth_meta = result.metadata['authentication']
                print(f"Auth method: {auth_meta.get('method')}")
                print(f"Authenticated: {auth_meta.get('authenticated')}")
    except Exception as e:
        print(f"Authentication error: {e}")


async def main():
    """Run all examples."""
    print("Extended Resource Types Examples")
    print("=" * 50)
    
    await rss_feed_examples()
    await authenticated_api_examples()
    await database_examples()
    await cloud_storage_examples()
    await unified_manager_examples()
    await error_handling_examples()
    
    print("\n" + "=" * 50)
    print("Examples completed!")


if __name__ == "__main__":
    asyncio.run(main())
