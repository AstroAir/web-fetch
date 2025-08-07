"""
WebFetch MCP Server Implementation

This module implements the main MCP server using FastMCP framework that exposes
WebFetch functionality as tools for LLM consumption.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Union, Any, Literal, Callable

from fastmcp import FastMCP, Context
from pydantic import BaseModel, Field, HttpUrl
from typing_extensions import Annotated

# Import WebFetch functionality
from web_fetch import (
    fetch_url,
    fetch_urls,
    enhanced_fetch_url,
    enhanced_fetch_urls,
    FetchConfig,
    FetchRequest,
    FetchResult,
    ContentType,
    RetryStrategy,
    WebFetchError,
    is_valid_url,
    normalize_url,
    analyze_url,
    analyze_headers,
    detect_content_type,
    # New imports for enhanced features
    BatchManager,
    BatchRequest,
    BatchConfig,
    BatchPriority,
    HTTPMethodHandler,
    HTTPMethod,
    FileUploadHandler,
    DownloadHandler,
    ResumableDownloadHandler,
    PaginationHandler,
    PaginationStrategy,
    HeaderManager,
    CookieManager,
    config_manager,
    GlobalConfig,
)

# Import advanced utilities
from web_fetch.utils import (
    CircuitBreakerConfig,
    EnhancedCacheConfig,
    CacheBackend,
    TransformationPipeline,
    JSRenderConfig
)

# Import WebSocket functionality
from web_fetch.websocket import (
    WebSocketClient,
    WebSocketConfig,
    WebSocketManager,
    WebSocketConnectionState,
    WebSocketMessage,
    WebSocketMessageType,
    WebSocketResult,
    WebSocketError
)

# Import GraphQL functionality
from web_fetch.graphql import (
    GraphQLClient,
    GraphQLConfig,
    GraphQLQuery,
    GraphQLMutation,
    GraphQLSubscription,
    GraphQLResult,
    GraphQLSchema,
    GraphQLError,
    QueryBuilder,
    MutationBuilder,
    SubscriptionBuilder,
    GraphQLValidator
)

# Import Authentication functionality
from web_fetch.auth import (
    AuthManager,
    AuthMethod,
    AuthResult,
    APIKeyAuth,
    APIKeyConfig,
    OAuth2Auth,
    OAuth2Config,
    JWTAuth,
    JWTConfig,
    BasicAuth,
    BasicAuthConfig,
    BearerTokenAuth,
    BearerTokenConfig,
    CustomAuth,
    CustomAuthConfig
)

# Import Content Processing functionality
from web_fetch.parsers import (
    EnhancedContentParser,
    PDFParser,
    ImageParser,
    FeedParser,
    CSVParser,
    JSONParser,
    MarkdownConverter,
    ContentAnalyzer,
    LinkExtractor
)
from web_fetch.utils.transformers import (
    TransformationPipeline,
    JSONPathExtractor,
    HTMLExtractor,
    RegexExtractor
)

# Import Monitoring and Metrics functionality
from web_fetch.utils.metrics import (
    MetricsCollector,
    RequestMetrics,
    AggregatedMetrics,
    record_request_metrics,
    get_metrics_summary,
    get_recent_performance
)

# Import FTP functionality
from web_fetch.ftp import (
    FTPFetcher,
    FTPConfig,
    FTPRequest,
    FTPResult,
    FTPBatchRequest,
    FTPBatchResult,
    FTPFileInfo,
    FTPProgressInfo,
    FTPAuthType,
    FTPMode,
    FTPTransferMode,
    ftp_download_file,
    ftp_download_batch,
    ftp_list_directory,
    ftp_get_file_info
)

# Import Crawler functionality
from web_fetch.crawlers import (
    CrawlerManager,
    CrawlerType,
    CrawlerCapability,
    CrawlerConfig,
    CrawlerRequest,
    CrawlerResult,
    crawler_fetch_url,
    crawler_fetch_urls,
    crawler_search_web,
    crawler_crawl_website,
    crawler_extract_content,
    configure_crawler,
    set_primary_crawler,
    set_fallback_order,
    get_crawler_status
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global WebSocket manager
_websocket_manager: Optional[WebSocketManager] = None

# Global GraphQL clients
_graphql_clients: Dict[str, GraphQLClient] = {}

# Global authentication manager
_auth_manager: Optional[AuthManager] = None

# Global performance optimization components
_connection_pool: Optional[aiohttp.ClientSession] = None
_cache_manager: Optional[EnhancedCache] = None
_rate_limiter: Optional[Dict[str, float]] = None


def create_mcp_server() -> FastMCP:
    """
    Create and configure the WebFetch MCP server.

    Returns:
        FastMCP: Configured MCP server instance
    """
    mcp = FastMCP(
        name="WebFetch",
        instructions="""
        This server provides comprehensive web fetching capabilities for retrieving content from URLs.

        Available tools:
        - web_fetch: Fetch content from a single URL with various parsing options
        - web_fetch_batch: Fetch content from multiple URLs concurrently
        - web_fetch_enhanced: Advanced fetching with caching, circuit breakers, and more features
        - batch_fetch_advanced: Advanced batch processing with priority queues and scheduling
        - upload_file: Upload files to web endpoints with progress tracking
        - download_file: Download files with resume capability and integrity verification
        - paginate_api: Handle API pagination automatically
        - manage_headers: Advanced header management with presets and rules
        - manage_cookies: Cookie management with persistence and security
        - validate_url: Validate and analyze URL structure
        - analyze_headers: Analyze HTTP response headers
        - detect_content_type: Detect content type from URL or headers
        - configure_system: Configure global system settings

        The server supports various content types (TEXT, JSON, HTML, RAW) and provides
        comprehensive error handling, retry logic, and performance optimizations.
        """,
        include_fastmcp_meta=True
    )

    @mcp.tool(
        name="web_fetch",
        description="Fetch content from a single URL with configurable parsing and timeout options",
        tags={"web", "fetch", "http"}
    )
    async def web_fetch_tool(
        url: Annotated[str, Field(description="The URL to fetch content from")],
        content_type: Annotated[
            Literal["TEXT", "JSON", "HTML", "RAW"],
            Field(description="How to parse the response content")
        ] = "TEXT",
        timeout: Annotated[
            float,
            Field(description="Request timeout in seconds", ge=1.0, le=300.0)
        ] = 30.0,
        max_retries: Annotated[
            int,
            Field(description="Maximum number of retry attempts", ge=0, le=10)
        ] = 3,
        follow_redirects: Annotated[
            bool,
            Field(description="Whether to follow HTTP redirects")
        ] = True,
        verify_ssl: Annotated[
            bool,
            Field(description="Whether to verify SSL certificates")
        ] = True,
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Fetch content from a single URL with comprehensive options.

        This tool provides a simple interface to fetch web content with various
        parsing options and configuration settings.
        """
        try:
            # Log the request
            if ctx:
                await ctx.info(f"Fetching URL: {url}")

            # Validate URL
            if not is_valid_url(url):
                raise ValueError(f"Invalid URL format: {url}")

            # Normalize URL
            normalized_url = normalize_url(url)

            # Convert content_type string to enum
            content_type_enum = ContentType[content_type]

            # Create fetch configuration
            config = FetchConfig(
                total_timeout=timeout,
                max_retries=max_retries,
                follow_redirects=follow_redirects,
                verify_ssl=verify_ssl
            )

            # Perform the fetch
            result = await fetch_url(
                url=normalized_url,
                content_type=content_type_enum,
                config=config
            )

            # Log success
            if ctx:
                await ctx.info(f"Successfully fetched {url} - Status: {result.status_code}")

            # Return structured result
            return {
                "success": result.is_success,
                "status_code": result.status_code,
                "url": str(result.url),
                "content": result.content,
                "headers": dict(result.headers),
                "content_type": result.content_type.value,
                "response_time": result.response_time,
                "error": result.error,
                "final_url": str(result.url),
                "metadata": {
                    "pdf_metadata": result.pdf_metadata.__dict__ if result.pdf_metadata else None,
                    "image_metadata": result.image_metadata.__dict__ if result.image_metadata else None,
                    "feed_metadata": result.feed_metadata.__dict__ if result.feed_metadata else None,
                    "csv_metadata": result.csv_metadata.__dict__ if result.csv_metadata else None,
                    "content_summary": result.content_summary.__dict__ if result.content_summary else None,
                    "links": [link.__dict__ for link in result.links] if result.links else [],
                    "feed_items": [item.__dict__ for item in result.feed_items] if result.feed_items else []
                }
            }

        except WebFetchError as e:
            error_msg = f"WebFetch error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "url": url,
                "status_code": 0
            }
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "url": url,
                "status_code": 0
            }

    @mcp.tool(
        name="web_fetch_batch",
        description="Fetch content from multiple URLs concurrently with shared configuration",
        tags={"web", "fetch", "batch", "concurrent"}
    )
    async def web_fetch_batch_tool(
        urls: Annotated[
            List[str],
            Field(description="List of URLs to fetch concurrently", min_length=1, max_length=20)
        ],
        content_type: Annotated[
            Literal["TEXT", "JSON", "HTML", "RAW"],
            Field(description="How to parse the response content for all URLs")
        ] = "TEXT",
        timeout: Annotated[
            float,
            Field(description="Request timeout in seconds for each URL", ge=1.0, le=300.0)
        ] = 30.0,
        max_retries: Annotated[
            int,
            Field(description="Maximum number of retry attempts per URL", ge=0, le=10)
        ] = 3,
        max_concurrent: Annotated[
            int,
            Field(description="Maximum number of concurrent requests", ge=1, le=20)
        ] = 5,
        follow_redirects: Annotated[
            bool,
            Field(description="Whether to follow HTTP redirects")
        ] = True,
        verify_ssl: Annotated[
            bool,
            Field(description="Whether to verify SSL certificates")
        ] = True,
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Fetch content from multiple URLs concurrently.

        This tool allows fetching multiple URLs in parallel with shared configuration,
        providing efficient batch processing capabilities.
        """
        try:
            # Log the batch request
            if ctx:
                await ctx.info(f"Starting batch fetch for {len(urls)} URLs")
                await ctx.report_progress(0, len(urls))

            # Validate all URLs first
            invalid_urls = []
            valid_urls = []

            for url in urls:
                if is_valid_url(url):
                    valid_urls.append(normalize_url(url))
                else:
                    invalid_urls.append(url)

            if invalid_urls:
                error_msg = f"Invalid URLs found: {invalid_urls}"
                if ctx:
                    await ctx.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "invalid_urls": invalid_urls,
                    "results": []
                }

            # Convert content_type string to enum
            content_type_enum = ContentType[content_type]

            # Create fetch configuration
            config = FetchConfig(
                total_timeout=timeout,
                max_retries=max_retries,
                max_concurrent_requests=max_concurrent,
                follow_redirects=follow_redirects,
                verify_ssl=verify_ssl
            )

            # Perform batch fetch
            batch_result = await fetch_urls(
                urls=valid_urls,
                content_type=content_type_enum,
                config=config
            )

            # Process results
            results = []
            successful_count = 0

            for i, result in enumerate(batch_result.results):
                if result.is_success:
                    successful_count += 1

                # Convert result to dictionary
                result_dict = {
                    "success": result.is_success,
                    "status_code": result.status_code,
                    "url": str(result.url),
                    "content": result.content,
                    "headers": dict(result.headers),
                    "content_type": result.content_type.value,
                    "response_time": result.response_time,
                    "error": result.error,
                    "final_url": str(result.url),
                    "metadata": {
                        "pdf_metadata": result.pdf_metadata.__dict__ if result.pdf_metadata else None,
                        "image_metadata": result.image_metadata.__dict__ if result.image_metadata else None,
                        "feed_metadata": result.feed_metadata.__dict__ if result.feed_metadata else None,
                        "csv_metadata": result.csv_metadata.__dict__ if result.csv_metadata else None,
                        "content_summary": result.content_summary.__dict__ if result.content_summary else None,
                        "links": [link.__dict__ for link in result.links] if result.links else [],
                        "feed_items": [item.__dict__ for item in result.feed_items] if result.feed_items else []
                    }
                }
                results.append(result_dict)

                # Update progress
                if ctx:
                    await ctx.report_progress(i + 1, len(urls))

            # Log completion
            if ctx:
                await ctx.info(f"Batch fetch completed: {successful_count}/{len(urls)} successful")

            return {
                "success": True,
                "total_requests": batch_result.total_requests,
                "successful_requests": batch_result.successful_requests,
                "failed_requests": batch_result.failed_requests,
                "total_time": batch_result.total_time,
                "results": results,
                "summary": {
                    "success_rate": successful_count / len(urls) if urls else 0,
                    "average_response_time": sum(r.response_time for r in batch_result.results if r.response_time) / len(batch_result.results) if batch_result.results else 0
                }
            }

        except WebFetchError as e:
            error_msg = f"WebFetch batch error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "results": []
            }
        except Exception as e:
            error_msg = f"Unexpected batch error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "results": []
            }

    @mcp.tool(
        name="web_fetch_enhanced",
        description="Advanced web fetching with caching, circuit breakers, deduplication, and more features",
        tags={"web", "fetch", "enhanced", "advanced"}
    )
    async def web_fetch_enhanced_tool(
        url: Annotated[str, Field(description="The URL to fetch content from")],
        method: Annotated[
            Literal["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"],
            Field(description="HTTP method to use")
        ] = "GET",
        headers: Annotated[
            Optional[Dict[str, str]],
            Field(description="Custom HTTP headers to send with the request")
        ] = None,
        data: Annotated[
            Optional[Union[str, Dict[str, Any]]],
            Field(description="Request body data (for POST/PUT requests)")
        ] = None,
        params: Annotated[
            Optional[Dict[str, str]],
            Field(description="URL query parameters")
        ] = None,
        content_type: Annotated[
            Literal["TEXT", "JSON", "HTML", "RAW"],
            Field(description="How to parse the response content")
        ] = "TEXT",
        timeout: Annotated[
            float,
            Field(description="Request timeout in seconds", ge=1.0, le=300.0)
        ] = 30.0,
        max_retries: Annotated[
            int,
            Field(description="Maximum number of retry attempts", ge=0, le=10)
        ] = 3,
        follow_redirects: Annotated[
            bool,
            Field(description="Whether to follow HTTP redirects")
        ] = True,
        verify_ssl: Annotated[
            bool,
            Field(description="Whether to verify SSL certificates")
        ] = True,
        enable_caching: Annotated[
            bool,
            Field(description="Enable response caching")
        ] = False,
        cache_ttl: Annotated[
            int,
            Field(description="Cache TTL in seconds", ge=60, le=3600)
        ] = 300,
        enable_circuit_breaker: Annotated[
            bool,
            Field(description="Enable circuit breaker for fault tolerance")
        ] = False,
        enable_deduplication: Annotated[
            bool,
            Field(description="Enable request deduplication")
        ] = True,
        enable_metrics: Annotated[
            bool,
            Field(description="Enable metrics collection")
        ] = True,
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Advanced web fetching with comprehensive features.

        This tool provides access to all advanced WebFetch features including
        caching, circuit breakers, request deduplication, metrics collection,
        and custom HTTP methods with full request customization.
        """
        try:
            # Log the enhanced request
            if ctx:
                await ctx.info(f"Enhanced fetch for URL: {url} (method: {method})")

            # Validate URL
            if not is_valid_url(url):
                raise ValueError(f"Invalid URL format: {url}")

            # Normalize URL
            normalized_url = normalize_url(url)

            # Convert content_type string to enum
            content_type_enum = ContentType[content_type]

            # Create fetch configuration
            config = FetchConfig(
                total_timeout=timeout,
                max_retries=max_retries,
                follow_redirects=follow_redirects,
                verify_ssl=verify_ssl
            )

            # Create circuit breaker config if enabled
            circuit_breaker_config = None
            if enable_circuit_breaker:
                circuit_breaker_config = CircuitBreakerConfig(
                    failure_threshold=5,
                    recovery_timeout=60.0,
                    success_threshold=3,
                    timeout=timeout,
                    failure_exceptions=(WebFetchError,),
                    failure_status_codes={500, 502, 503, 504}
                )

            # Create cache config if enabled
            cache_config = None
            if enable_caching:
                cache_config = EnhancedCacheConfig(
                    backend=CacheBackend.MEMORY,
                    default_ttl=float(cache_ttl),
                    max_size=1000
                )

            # Perform the enhanced fetch
            result = await enhanced_fetch_url(
                url=normalized_url,
                method=method,
                headers=headers,
                data=data,
                params=params,
                content_type=content_type_enum,
                config=config,
                circuit_breaker_config=circuit_breaker_config,
                enable_deduplication=enable_deduplication,
                enable_metrics=enable_metrics,
                cache_config=cache_config
            )

            # Log success
            if ctx:
                await ctx.info(f"Enhanced fetch successful for {url} - Status: {result.status_code}")

            # Return structured result with enhanced metadata
            return {
                "success": result.is_success,
                "status_code": result.status_code,
                "url": str(result.url),
                "content": result.content,
                "headers": dict(result.headers),
                "content_type": result.content_type.value,
                "response_time": result.response_time,
                "error": result.error,
                "final_url": str(result.url),
                "request_info": {
                    "method": method,
                    "headers_sent": headers,
                    "data_sent": data,
                    "params_sent": params
                },
                "features_used": {
                    "caching": enable_caching,
                    "circuit_breaker": enable_circuit_breaker,
                    "deduplication": enable_deduplication,
                    "metrics": enable_metrics
                },
                "metadata": {
                    "pdf_metadata": result.pdf_metadata.__dict__ if result.pdf_metadata else None,
                    "image_metadata": result.image_metadata.__dict__ if result.image_metadata else None,
                    "feed_metadata": result.feed_metadata.__dict__ if result.feed_metadata else None,
                    "csv_metadata": result.csv_metadata.__dict__ if result.csv_metadata else None,
                    "content_summary": result.content_summary.__dict__ if result.content_summary else None,
                    "links": [link.__dict__ for link in result.links] if result.links else [],
                    "feed_items": [item.__dict__ for item in result.feed_items] if result.feed_items else []
                }
            }

        except WebFetchError as e:
            error_msg = f"Enhanced WebFetch error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "url": url,
                "status_code": 0,
                "request_info": {
                    "method": method,
                    "headers_sent": headers,
                    "data_sent": data,
                    "params_sent": params
                }
            }
        except Exception as e:
            error_msg = f"Unexpected enhanced fetch error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "url": url,
                "status_code": 0,
                "request_info": {
                    "method": method,
                    "headers_sent": headers,
                    "data_sent": data,
                    "params_sent": params
                }
            }

    @mcp.tool(
        name="validate_url",
        description="Validate and analyze URL structure and properties",
        tags={"url", "validation", "analysis"}
    )
    async def validate_url_tool(
        url: Annotated[str, Field(description="The URL to validate and analyze")],
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Validate a URL and provide detailed analysis of its structure.

        This tool validates URL format and provides comprehensive analysis
        including scheme, domain, path components, and other URL properties.
        """
        try:
            if ctx:
                await ctx.info(f"Validating URL: {url}")

            # Basic validation
            is_valid = is_valid_url(url)

            if not is_valid:
                return {
                    "valid": False,
                    "url": url,
                    "error": "Invalid URL format",
                    "analysis": None
                }

            # Normalize URL
            normalized_url = normalize_url(url)

            # Analyze URL structure
            analysis = analyze_url(url)

            return {
                "valid": True,
                "url": url,
                "normalized_url": normalized_url,
                "analysis": {
                    "scheme": analysis.scheme,
                    "domain": analysis.domain,
                    "port": analysis.port,
                    "path": analysis.path,
                    "fragment": analysis.fragment,
                    "is_secure": analysis.is_secure,
                    "is_local": analysis.is_local,
                    "query_params": analysis.query_params,
                    "issues": analysis.issues
                }
            }

        except Exception as e:
            error_msg = f"URL validation error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "valid": False,
                "url": url,
                "error": error_msg,
                "analysis": None
            }

    @mcp.tool(
        name="analyze_headers",
        description="Analyze HTTP response headers for insights and metadata",
        tags={"http", "headers", "analysis"}
    )
    async def analyze_headers_tool(
        headers: Annotated[
            Dict[str, str],
            Field(description="HTTP headers to analyze (key-value pairs)")
        ],
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Analyze HTTP headers to extract useful information and insights.

        This tool analyzes HTTP response headers to provide insights about
        server technology, caching policies, security headers, and more.
        """
        try:
            if ctx:
                await ctx.info("Analyzing HTTP headers")

            # Analyze headers
            analysis = analyze_headers(headers)

            return {
                "success": True,
                "analysis": {
                    "server_info": {
                        "server": analysis.server
                    },
                    "content_info": {
                        "content_type": analysis.content_type,
                        "content_length": analysis.content_length,
                        "content_encoding": analysis.content_encoding
                    },
                    "caching": {
                        "cache_control": analysis.cache_control,
                        "expires": analysis.expires,
                        "etag": analysis.etag,
                        "last_modified": analysis.last_modified,
                        "is_cacheable": analysis.is_cacheable
                    },
                    "security": {
                        "security_headers": analysis.security_headers
                    },
                    "custom_headers": analysis.custom_headers
                },
                "raw_headers": headers
            }

        except Exception as e:
            error_msg = f"Header analysis error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "raw_headers": headers
            }

    @mcp.tool(
        name="detect_content_type",
        description="Detect content type from URL, headers, or content",
        tags={"content", "detection", "mime"}
    )
    async def detect_content_type_tool(
        url: Annotated[
            Optional[str],
            Field(description="URL to analyze for content type hints")
        ] = None,
        headers: Annotated[
            Optional[Dict[str, str]],
            Field(description="HTTP headers containing content-type information")
        ] = None,
        content_sample: Annotated[
            Optional[str],
            Field(description="Sample of content to analyze")
        ] = None,
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Detect content type using various methods and sources.

        This tool attempts to detect content type from URL patterns,
        HTTP headers, and content analysis to provide accurate MIME type
        identification and content classification.
        """
        try:
            if ctx:
                await ctx.info("Detecting content type")

            if not any([headers, content_sample]):
                return {
                    "success": False,
                    "error": "At least one of headers or content_sample must be provided"
                }

            # Prepare parameters for detection
            headers_dict = headers or {}
            content_bytes = content_sample.encode() if content_sample else b''

            # Detect content type
            detected_type = detect_content_type(headers_dict, content_bytes)

            return {
                "success": True,
                "detected_type": detected_type,
                "analysis": {
                    "from_url": url is not None,
                    "from_headers": headers is not None,
                    "from_content": content_sample is not None,
                    "confidence": "high" if detected_type != "application/octet-stream" else "low"
                },
                "inputs": {
                    "url": url,
                    "headers": headers,
                    "content_sample_length": len(content_sample) if content_sample else 0
                }
            }

        except Exception as e:
            error_msg = f"Content type detection error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "inputs": {
                    "url": url,
                    "headers": headers,
                    "content_sample_length": len(content_sample) if content_sample else 0
                }
            }

    @mcp.tool(
        name="batch_fetch_advanced",
        description="Advanced batch processing with priority queues, scheduling, and progress tracking",
        tags={"batch", "advanced", "priority", "scheduling"}
    )
    async def batch_fetch_advanced_tool(
        requests: Annotated[
            List[Dict[str, Any]],
            Field(description="List of request configurations with URLs and options", min_length=1, max_length=100)
        ],
        priority: Annotated[
            Literal["LOW", "NORMAL", "HIGH", "URGENT"],
            Field(description="Batch priority level")
        ] = "NORMAL",
        max_concurrent: Annotated[
            int,
            Field(description="Maximum concurrent requests", ge=1, le=50)
        ] = 10,
        timeout: Annotated[
            float,
            Field(description="Total batch timeout in seconds", ge=1.0, le=3600.0)
        ] = 300.0,
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Process multiple requests with advanced batch management.

        This tool provides sophisticated batch processing with priority queues,
        intelligent scheduling, and comprehensive progress tracking.
        """
        try:
            if ctx:
                await ctx.info(f"Starting advanced batch processing for {len(requests)} requests")

            # Create batch configuration
            batch_config = BatchConfig(
                max_concurrent_requests_per_batch=max_concurrent,
                batch_timeout=timeout,
                enable_metrics=True,
                enable_progress_tracking=True
            )

            # Create batch manager
            batch_manager = BatchManager(batch_config)
            await batch_manager.start()

            try:
                # Convert requests to FetchRequest objects
                fetch_requests = []
                for i, req in enumerate(requests):
                    if isinstance(req, dict) and 'url' in req:
                        # Convert string URL to HttpUrl
                        url_str = req['url']
                        if not is_valid_url(url_str):
                            raise ValueError(f"Invalid URL at index {i}: {url_str}")
                        
                        # Create HttpUrl object
                        http_url = HttpUrl(url_str)
                        
                        fetch_req = FetchRequest(
                            url=http_url,
                            method=req.get('method', 'GET'),
                            headers=req.get('headers'),
                            params=req.get('params')
                        )
                        fetch_requests.append(fetch_req)
                    else:
                        raise ValueError(f"Invalid request format at index {i}")

                # Create batch request
                batch_request = BatchRequest(
                    requests=fetch_requests,
                    priority=BatchPriority[priority],
                    max_concurrent=max_concurrent,
                    timeout=timeout
                )

                # Submit batch
                batch_id = await batch_manager.submit_batch(batch_request)

                # Wait for completion with progress updates
                while True:
                    status = await batch_manager.get_batch_status(batch_id)
                    if status and status.value in ['completed', 'failed', 'cancelled']:
                        break

                    # Report progress
                    progress = await batch_manager.get_batch_progress(batch_id)
                    if progress and ctx:
                        await ctx.report_progress(
                            progress.completed_requests + progress.failed_requests,
                            progress.total_requests
                        )

                    await asyncio.sleep(0.5)

                # Get final result
                result = await batch_manager.get_batch_result(batch_id)

                if result:
                    return {
                        "success": True,
                        "batch_id": batch_id,
                        "status": result.status.value,
                        "total_requests": result.total_requests,
                        "successful_requests": result.successful_requests,
                        "failed_requests": result.failed_requests,
                        "success_rate": result.success_rate,
                        "total_time": result.total_time,
                        "average_response_time": result.average_response_time,
                        "results": [
                            {
                                "url": str(r.url),
                                "status_code": r.status_code,
                                "success": r.is_success,
                                "content": r.content if r.is_success else None,
                                "error": r.error if not r.is_success else None
                            }
                            for r in result.results
                        ]
                    }
                else:
                    return {
                        "success": False,
                        "error": "Failed to get batch result",
                        "batch_id": batch_id
                    }

            finally:
                await batch_manager.stop()

        except Exception as e:
            error_msg = f"Advanced batch processing error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "requests_count": len(requests)
            }

    @mcp.tool(
        name="download_file",
        description="Download files with resume capability, progress tracking, and integrity verification",
        tags={"download", "file", "resume", "integrity"}
    )
    async def download_file_tool(
        url: Annotated[str, Field(description="URL of the file to download")],
        output_path: Annotated[str, Field(description="Local path where to save the file")],
        resume: Annotated[
            bool,
            Field(description="Whether to resume partial downloads")
        ] = True,
        verify_checksum: Annotated[
            bool,
            Field(description="Whether to verify file integrity")
        ] = False,
        expected_checksum: Annotated[
            Optional[str],
            Field(description="Expected file checksum for verification")
        ] = None,
        max_file_size: Annotated[
            Optional[int],
            Field(description="Maximum file size in bytes")
        ] = None,
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Download a file with advanced features.

        This tool provides robust file downloading with resume capability,
        progress tracking, and integrity verification.
        """
        try:
            if ctx:
                await ctx.info(f"Starting download: {url} -> {output_path}")

            # Create download configuration
            from web_fetch.http.download import DownloadConfig

            config = DownloadConfig(
                verify_checksum=verify_checksum,
                expected_checksum=expected_checksum,
                max_file_size=max_file_size,
                overwrite_existing=True
            )

            # Choose handler based on resume capability
            if resume:
                handler = ResumableDownloadHandler(config)
                download_method = handler.download_file_resumable
            else:
                handler = DownloadHandler(config)
                download_method = handler.download_file

            # Progress callback with proper type annotation
            def progress_callback(progress: Any) -> None:
                if ctx:
                    asyncio.create_task(ctx.report_progress(
                        progress.bytes_downloaded,
                        progress.total_bytes or progress.bytes_downloaded
                    ))

            # Perform download
            import aiohttp
            async with aiohttp.ClientSession() as session:
                result = await download_method(
                    session=session,
                    url=url,
                    output_path=output_path,
                    progress_callback=progress_callback
                )

            return {
                "success": result.success,
                "file_path": str(result.file_path),
                "bytes_downloaded": result.bytes_downloaded,
                "total_bytes": result.total_bytes,
                "download_time": result.download_time,
                "average_speed": result.average_speed,
                "speed_human": result.speed_human,
                "checksum": result.checksum,
                "error": result.error
            }

        except Exception as e:
            error_msg = f"Download error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "url": url,
                "output_path": output_path
            }

    @mcp.tool(
        name="paginate_api",
        description="Automatically handle API pagination to fetch all pages of data",
        tags={"pagination", "api", "automatic"}
    )
    async def paginate_api_tool(
        base_url: Annotated[str, Field(description="Base API URL")],
        strategy: Annotated[
            Literal["offset_limit", "page_size", "cursor", "link_header"],
            Field(description="Pagination strategy to use")
        ] = "page_size",
        max_pages: Annotated[
            int,
            Field(description="Maximum pages to fetch", ge=1, le=100)
        ] = 10,
        page_size: Annotated[
            int,
            Field(description="Items per page", ge=1, le=1000)
        ] = 20,
        headers: Annotated[
            Optional[Dict[str, str]],
            Field(description="HTTP headers to include")
        ] = None,
        params: Annotated[
            Optional[Dict[str, str]],
            Field(description="Base query parameters")
        ] = None,
        data_field: Annotated[
            str,
            Field(description="Field name containing the data array")
        ] = "data",
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Automatically handle API pagination.

        This tool intelligently handles different pagination strategies
        to fetch all available data from paginated APIs.
        """
        try:
            if ctx:
                await ctx.info(f"Starting pagination for: {base_url}")

            from web_fetch.http.pagination import PaginationConfig, PaginationStrategy as PagStrategy
            from web_fetch.src.core_fetcher import WebFetcher

            # Create pagination configuration
            config = PaginationConfig(
                strategy=PagStrategy[strategy.upper()],
                max_pages=max_pages,
                page_size=page_size,
                data_field=data_field
            )

            # Create pagination handler
            handler = PaginationHandler(config)

            # Convert string URL to HttpUrl
            if not is_valid_url(base_url):
                raise ValueError(f"Invalid base URL: {base_url}")
            
            http_url = HttpUrl(base_url)

            # Create base request
            base_request = FetchRequest(
                url=http_url,
                headers=headers,
                params=params
            )

            # Fetch all pages
            async with WebFetcher() as fetcher:
                result = await handler.fetch_all_pages(fetcher, base_request)

            return {
                "success": True,
                "total_items": len(result.data),
                "total_pages": result.total_pages,
                "has_more": result.has_more,
                "data": result.data,
                "pagination_info": {
                    "strategy": strategy,
                    "pages_fetched": result.total_pages,
                    "items_per_page": page_size,
                    "total_requests": len(result.responses)
                },
                "responses": [
                    {
                        "url": str(r.url),
                        "status_code": r.status_code,
                        "success": r.is_success
                    }
                    for r in result.responses
                ]
            }

        except Exception as e:
            error_msg = f"Pagination error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "base_url": base_url,
                "strategy": strategy
            }

    @mcp.tool(
        name="configure_system",
        description="Configure global system settings for web fetching",
        tags={"configuration", "settings", "global"}
    )
    async def configure_system_tool(
        logging_level: Annotated[
            Optional[Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]],
            Field(description="Set logging level")
        ] = None,
        max_connections: Annotated[
            Optional[int],
            Field(description="Maximum total connections", ge=1, le=1000)
        ] = None,
        connection_timeout: Annotated[
            Optional[float],
            Field(description="Connection timeout in seconds", ge=1.0, le=300.0)
        ] = None,
        enable_caching: Annotated[
            Optional[bool],
            Field(description="Enable response caching")
        ] = None,
        enable_metrics: Annotated[
            Optional[bool],
            Field(description="Enable metrics collection")
        ] = None,
        user_agent: Annotated[
            Optional[str],
            Field(description="Default User-Agent header")
        ] = None,
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Configure global system settings.

        This tool allows configuration of global settings that affect
        all web fetching operations.
        """
        try:
            if ctx:
                await ctx.info("Updating system configuration")

            # Get current configuration
            current_config = config_manager.get_config()

            # Prepare updates with proper typing
            updates: Dict[str, Any] = {}

            if logging_level:
                updates['logging'] = {'level': logging_level}

            if max_connections:
                performance_config = updates.setdefault('performance', {})
                performance_config['max_connections'] = max_connections

            if connection_timeout:
                performance_config = updates.setdefault('performance', {})
                performance_config['connection_timeout'] = connection_timeout

            if enable_caching is not None:
                features_config = updates.setdefault('features', {})
                features_config['enable_caching'] = enable_caching

            if enable_metrics is not None:
                features_config = updates.setdefault('features', {})
                features_config['enable_metrics'] = enable_metrics

            if user_agent:
                updates['user_agent'] = user_agent

            # Apply updates if any
            if updates:
                config_manager.update_config(updates, validate=True, persist=False)

                # Get updated configuration
                updated_config = config_manager.get_config()

                return {
                    "success": True,
                    "message": "Configuration updated successfully",
                    "updates_applied": updates,
                    "current_config": {
                        "logging_level": updated_config.logging.level.value,
                        "max_connections": updated_config.performance.max_connections,
                        "connection_timeout": updated_config.performance.connection_timeout,
                        "enable_caching": updated_config.features.enable_caching,
                        "enable_metrics": updated_config.features.enable_metrics,
                        "user_agent": updated_config.user_agent
                    }
                }
            else:
                # No updates, return current configuration
                return {
                    "success": True,
                    "message": "No updates specified, returning current configuration",
                    "current_config": {
                        "logging_level": current_config.logging.level.value,
                        "max_connections": current_config.performance.max_connections,
                        "connection_timeout": current_config.performance.connection_timeout,
                        "enable_caching": current_config.features.enable_caching,
                        "enable_metrics": current_config.features.enable_metrics,
                        "user_agent": current_config.user_agent
                    }
                }

        except Exception as e:
            error_msg = f"Configuration error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }

    @mcp.tool(
        name="upload_file",
        description="Upload files to web endpoints with progress tracking and multipart support",
        tags={"upload", "file", "multipart", "progress"}
    )
    async def upload_file_tool(
        url: Annotated[str, Field(description="URL endpoint to upload the file to")],
        file_path: Annotated[str, Field(description="Local path to the file to upload")],
        field_name: Annotated[
            str,
            Field(description="Form field name for the file")
        ] = "file",
        additional_fields: Annotated[
            Optional[Dict[str, str]],
            Field(description="Additional form fields to include")
        ] = None,
        headers: Annotated[
            Optional[Dict[str, str]],
            Field(description="Custom HTTP headers")
        ] = None,
        timeout: Annotated[
            float,
            Field(description="Upload timeout in seconds", ge=1.0, le=3600.0)
        ] = 300.0,
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Upload a file to a web endpoint with progress tracking.

        This tool provides file upload capabilities with multipart form data,
        progress tracking, and comprehensive error handling.
        """
        try:
            if ctx:
                await ctx.info(f"Starting file upload: {file_path} -> {url}")

            # Validate URL
            if not is_valid_url(url):
                raise ValueError(f"Invalid URL format: {url}")

            # Check if file exists
            import os
            if not os.path.exists(file_path):
                raise ValueError(f"File not found: {file_path}")

            # Get file size for progress tracking
            file_size = os.path.getsize(file_path)

            # Create upload handler
            upload_handler = FileUploadHandler()

            # Progress callback
            def progress_callback(progress: Any) -> None:
                if ctx:
                    asyncio.create_task(ctx.report_progress(
                        progress.bytes_uploaded,
                        progress.total_bytes or file_size
                    ))

            # Perform upload
            import aiohttp
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                result = await upload_handler.upload_file(
                    session=session,
                    url=url,
                    file_path=file_path,
                    field_name=field_name,
                    additional_fields=additional_fields or {},
                    headers=headers or {},
                    progress_callback=progress_callback
                )

            return {
                "success": result.success,
                "status_code": result.status_code,
                "response_headers": dict(result.response_headers) if result.response_headers else {},
                "response_content": result.response_content,
                "bytes_uploaded": result.bytes_uploaded,
                "upload_time": result.upload_time,
                "average_speed": result.average_speed,
                "speed_human": result.speed_human,
                "error": result.error
            }

        except Exception as e:
            error_msg = f"Upload error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "url": url,
                "file_path": file_path
            }

    @mcp.tool(
        name="manage_headers",
        description="Advanced header management with presets, rules, and validation",
        tags={"headers", "management", "presets", "validation"}
    )
    async def manage_headers_tool(
        action: Annotated[
            Literal["create_preset", "apply_preset", "validate_headers", "analyze_headers"],
            Field(description="Action to perform")
        ],
        preset_name: Annotated[
            Optional[str],
            Field(description="Name of the header preset")
        ] = None,
        headers: Annotated[
            Optional[Dict[str, str]],
            Field(description="Headers to work with")
        ] = None,
        preset_config: Annotated[
            Optional[Dict[str, Any]],
            Field(description="Configuration for creating presets")
        ] = None,
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Manage HTTP headers with advanced features.

        This tool provides comprehensive header management including presets,
        validation, and analysis capabilities.
        """
        try:
            if ctx:
                await ctx.info(f"Header management action: {action}")

            # Create header manager
            header_manager = HeaderManager()

            if action == "create_preset":
                if not preset_name or not headers:
                    raise ValueError("preset_name and headers are required for create_preset")

                # Create header preset
                preset = header_manager.create_preset(
                    name=preset_name,
                    headers=headers,
                    description=preset_config.get("description", "") if preset_config else ""
                )

                return {
                    "success": True,
                    "action": action,
                    "preset_name": preset_name,
                    "preset": {
                        "name": preset.name,
                        "headers": preset.headers,
                        "description": preset.description,
                        "created_at": preset.created_at.isoformat()
                    }
                }

            elif action == "apply_preset":
                if not preset_name:
                    raise ValueError("preset_name is required for apply_preset")

                # Apply header preset
                applied_headers = header_manager.apply_preset(preset_name, headers or {})

                return {
                    "success": True,
                    "action": action,
                    "preset_name": preset_name,
                    "applied_headers": applied_headers,
                    "original_headers": headers or {}
                }

            elif action == "validate_headers":
                if not headers:
                    raise ValueError("headers are required for validate_headers")

                # Validate headers
                validation_result = header_manager.validate_headers(headers)

                return {
                    "success": True,
                    "action": action,
                    "validation": {
                        "is_valid": validation_result.is_valid,
                        "errors": validation_result.errors,
                        "warnings": validation_result.warnings,
                        "suggestions": validation_result.suggestions
                    },
                    "headers": headers
                }

            elif action == "analyze_headers":
                if not headers:
                    raise ValueError("headers are required for analyze_headers")

                # Analyze headers
                analysis = analyze_headers(headers)

                return {
                    "success": True,
                    "action": action,
                    "analysis": {
                        "server_info": {
                            "server": analysis.server
                        },
                        "content_info": {
                            "content_type": analysis.content_type,
                            "content_length": analysis.content_length,
                            "content_encoding": analysis.content_encoding
                        },
                        "caching": {
                            "cache_control": analysis.cache_control,
                            "expires": analysis.expires,
                            "etag": analysis.etag,
                            "last_modified": analysis.last_modified,
                            "is_cacheable": analysis.is_cacheable
                        },
                        "security": {
                            "security_headers": analysis.security_headers
                        },
                        "custom_headers": analysis.custom_headers
                    },
                    "headers": headers
                }

            else:
                raise ValueError(f"Unknown action: {action}")

        except Exception as e:
            error_msg = f"Header management error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "action": action
            }

    @mcp.tool(
        name="manage_cookies",
        description="Cookie management with persistence, security, and session handling",
        tags={"cookies", "session", "security", "persistence"}
    )
    async def manage_cookies_tool(
        action: Annotated[
            Literal["create_jar", "add_cookie", "get_cookies", "clear_cookies", "save_jar", "load_jar"],
            Field(description="Action to perform")
        ],
        jar_name: Annotated[
            Optional[str],
            Field(description="Name of the cookie jar")
        ] = None,
        cookie_data: Annotated[
            Optional[Dict[str, Any]],
            Field(description="Cookie data for add_cookie action")
        ] = None,
        domain: Annotated[
            Optional[str],
            Field(description="Domain for cookie operations")
        ] = None,
        file_path: Annotated[
            Optional[str],
            Field(description="File path for save_jar/load_jar actions")
        ] = None,
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Manage HTTP cookies with advanced features.

        This tool provides comprehensive cookie management including jar creation,
        persistence, security validation, and session handling.
        """
        try:
            if ctx:
                await ctx.info(f"Cookie management action: {action}")

            # Create cookie manager
            cookie_manager = CookieManager()

            if action == "create_jar":
                if not jar_name:
                    raise ValueError("jar_name is required for create_jar")

                # Create cookie jar
                jar = cookie_manager.create_jar(jar_name)

                return {
                    "success": True,
                    "action": action,
                    "jar_name": jar_name,
                    "jar_id": jar.jar_id,
                    "created_at": jar.created_at.isoformat()
                }

            elif action == "add_cookie":
                if not jar_name or not cookie_data:
                    raise ValueError("jar_name and cookie_data are required for add_cookie")

                # Add cookie to jar
                cookie = cookie_manager.add_cookie(
                    jar_name=jar_name,
                    name=cookie_data["name"],
                    value=cookie_data["value"],
                    domain=cookie_data.get("domain", domain),
                    path=cookie_data.get("path", "/"),
                    secure=cookie_data.get("secure", False),
                    http_only=cookie_data.get("http_only", False),
                    expires=cookie_data.get("expires")
                )

                return {
                    "success": True,
                    "action": action,
                    "jar_name": jar_name,
                    "cookie": {
                        "name": cookie.name,
                        "value": cookie.value,
                        "domain": cookie.domain,
                        "path": cookie.path,
                        "secure": cookie.secure,
                        "http_only": cookie.http_only,
                        "expires": cookie.expires.isoformat() if cookie.expires else None
                    }
                }

            elif action == "get_cookies":
                if not jar_name:
                    raise ValueError("jar_name is required for get_cookies")

                # Get cookies from jar
                cookies = cookie_manager.get_cookies(jar_name, domain)

                return {
                    "success": True,
                    "action": action,
                    "jar_name": jar_name,
                    "domain": domain,
                    "cookies": [
                        {
                            "name": cookie.name,
                            "value": cookie.value,
                            "domain": cookie.domain,
                            "path": cookie.path,
                            "secure": cookie.secure,
                            "http_only": cookie.http_only,
                            "expires": cookie.expires.isoformat() if cookie.expires else None
                        }
                        for cookie in cookies
                    ]
                }

            elif action == "clear_cookies":
                if not jar_name:
                    raise ValueError("jar_name is required for clear_cookies")

                # Clear cookies from jar
                cleared_count = cookie_manager.clear_cookies(jar_name, domain)

                return {
                    "success": True,
                    "action": action,
                    "jar_name": jar_name,
                    "domain": domain,
                    "cleared_count": cleared_count
                }

            elif action == "save_jar":
                if not jar_name or not file_path:
                    raise ValueError("jar_name and file_path are required for save_jar")

                # Save cookie jar to file
                cookie_manager.save_jar(jar_name, file_path)

                return {
                    "success": True,
                    "action": action,
                    "jar_name": jar_name,
                    "file_path": file_path
                }

            elif action == "load_jar":
                if not jar_name or not file_path:
                    raise ValueError("jar_name and file_path are required for load_jar")

                # Load cookie jar from file
                jar = cookie_manager.load_jar(jar_name, file_path)

                return {
                    "success": True,
                    "action": action,
                    "jar_name": jar_name,
                    "file_path": file_path,
                    "jar_id": jar.jar_id,
                    "loaded_at": jar.created_at.isoformat()
                }

            else:
                raise ValueError(f"Unknown action: {action}")

        except Exception as e:
            error_msg = f"Cookie management error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "action": action
            }

    @mcp.tool(
        name="websocket_connect",
        description="Establish WebSocket connection for real-time communication",
        tags={"websocket", "realtime", "connection", "streaming"}
    )
    async def websocket_connect_tool(
        url: Annotated[str, Field(description="WebSocket URL (ws:// or wss://)")],
        connection_id: Annotated[
            str,
            Field(description="Unique identifier for this connection")
        ],
        subprotocols: Annotated[
            Optional[List[str]],
            Field(description="WebSocket subprotocols to request")
        ] = None,
        headers: Annotated[
            Optional[Dict[str, str]],
            Field(description="Additional headers for WebSocket handshake")
        ] = None,
        auto_reconnect: Annotated[
            bool,
            Field(description="Enable automatic reconnection on connection loss")
        ] = True,
        ping_interval: Annotated[
            float,
            Field(description="Ping interval in seconds", ge=1.0, le=300.0)
        ] = 30.0,
        max_message_size: Annotated[
            int,
            Field(description="Maximum message size in bytes", ge=1024, le=10485760)
        ] = 1048576,
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Establish a WebSocket connection for real-time communication.

        This tool creates a WebSocket connection with comprehensive configuration
        options including automatic reconnection, ping/pong handling, and message queuing.
        """
        try:
            if ctx:
                await ctx.info(f"Establishing WebSocket connection: {connection_id} -> {url}")

            # Validate URL
            if not url.startswith(('ws://', 'wss://')):
                raise ValueError("URL must start with ws:// or wss://")

            # Create WebSocket configuration
            config = WebSocketConfig(
                url=HttpUrl(url),
                subprotocols=subprotocols or [],
                headers=headers or {},
                auto_reconnect=auto_reconnect,
                ping_interval=ping_interval,
                max_message_size=max_message_size,
                enable_ping=True,
                enable_compression=True
            )

            # Create WebSocket manager if not exists
            global _websocket_manager
            if _websocket_manager is None:
                _websocket_manager = WebSocketManager()

            manager = _websocket_manager

            # Add connection
            result = await manager.add_connection(connection_id, config)

            return {
                "success": result.success,
                "connection_id": connection_id,
                "url": url,
                "connection_state": result.connection_state.value,
                "connection_time": result.connection_time,
                "error": result.error,
                "config": {
                    "auto_reconnect": auto_reconnect,
                    "ping_interval": ping_interval,
                    "max_message_size": max_message_size,
                    "subprotocols": subprotocols or [],
                    "headers": headers or {}
                }
            }

        except Exception as e:
            error_msg = f"WebSocket connection error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "connection_id": connection_id,
                "url": url
            }

    @mcp.tool(
        name="websocket_send",
        description="Send messages through WebSocket connection",
        tags={"websocket", "send", "message", "realtime"}
    )
    async def websocket_send_tool(
        connection_id: Annotated[
            str,
            Field(description="Connection identifier")
        ],
        message: Annotated[
            str,
            Field(description="Message to send")
        ],
        message_type: Annotated[
            Literal["text", "binary"],
            Field(description="Type of message to send")
        ] = "text",
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Send a message through an established WebSocket connection.

        This tool sends text or binary messages through a WebSocket connection
        with delivery confirmation and error handling.
        """
        try:
            if ctx:
                await ctx.info(f"Sending WebSocket message to {connection_id}")

            # Get manager
            global _websocket_manager
            if _websocket_manager is None:
                raise ValueError("No WebSocket manager found. Connect first using websocket_connect.")

            manager = _websocket_manager

            # Send message based on type
            if message_type == "text":
                success = await manager.send_text(connection_id, message)
            elif message_type == "binary":
                # Convert string to bytes for binary message
                message_bytes = message.encode('utf-8')
                success = await manager.send_binary(connection_id, message_bytes)
            else:
                raise ValueError(f"Unsupported message type: {message_type}")

            return {
                "success": success,
                "connection_id": connection_id,
                "message_type": message_type,
                "message_size": len(message.encode('utf-8')),
                "timestamp": time.time()
            }

        except Exception as e:
            error_msg = f"WebSocket send error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "connection_id": connection_id
            }

    @mcp.tool(
        name="websocket_receive",
        description="Receive messages from WebSocket connection",
        tags={"websocket", "receive", "message", "realtime"}
    )
    async def websocket_receive_tool(
        connection_id: Annotated[
            str,
            Field(description="Connection identifier")
        ],
        timeout: Annotated[
            float,
            Field(description="Receive timeout in seconds", ge=0.1, le=60.0)
        ] = 5.0,
        max_messages: Annotated[
            int,
            Field(description="Maximum number of messages to receive", ge=1, le=100)
        ] = 10,
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Receive messages from a WebSocket connection.

        This tool receives messages from an established WebSocket connection
        with configurable timeout and message limits.
        """
        try:
            if ctx:
                await ctx.info(f"Receiving WebSocket messages from {connection_id}")

            # Get manager
            global _websocket_manager
            if _websocket_manager is None:
                raise ValueError("No WebSocket manager found. Connect first using websocket_connect.")

            manager = _websocket_manager

            # Receive messages
            messages = await manager.receive_messages(connection_id, timeout, max_messages)

            return {
                "success": True,
                "connection_id": connection_id,
                "message_count": len(messages),
                "messages": [
                    {
                        "type": msg.type.value,
                        "data": msg.data,
                        "timestamp": msg.timestamp,
                        "size": msg.size
                    }
                    for msg in messages
                ],
                "timeout": timeout,
                "max_messages": max_messages
            }

        except Exception as e:
            error_msg = f"WebSocket receive error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "connection_id": connection_id
            }

    @mcp.tool(
        name="websocket_disconnect",
        description="Disconnect WebSocket connection",
        tags={"websocket", "disconnect", "cleanup"}
    )
    async def websocket_disconnect_tool(
        connection_id: Annotated[
            str,
            Field(description="Connection identifier")
        ],
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Disconnect a WebSocket connection.

        This tool cleanly disconnects a WebSocket connection and removes it
        from the connection manager.
        """
        try:
            if ctx:
                await ctx.info(f"Disconnecting WebSocket connection: {connection_id}")

            # Get manager
            global _websocket_manager
            if _websocket_manager is None:
                raise ValueError("No WebSocket manager found.")

            manager = _websocket_manager

            # Remove connection
            result = await manager.remove_connection(connection_id)

            return {
                "success": result.success,
                "connection_id": connection_id,
                "connection_state": result.connection_state.value,
                "error": result.error
            }

        except Exception as e:
            error_msg = f"WebSocket disconnect error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "connection_id": connection_id
            }

    @mcp.tool(
        name="websocket_status",
        description="Get status of WebSocket connections",
        tags={"websocket", "status", "monitoring"}
    )
    async def websocket_status_tool(
        connection_id: Annotated[
            Optional[str],
            Field(description="Specific connection ID to check (optional)")
        ] = None,
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Get status information for WebSocket connections.

        This tool provides status information for all connections or a specific
        connection, including connection state, message counts, and health metrics.
        """
        try:
            if ctx:
                await ctx.info("Getting WebSocket connection status")

            # Get manager
            global _websocket_manager
            if _websocket_manager is None:
                return {
                    "success": True,
                    "total_connections": 0,
                    "connections": {},
                    "message": "No WebSocket manager initialized"
                }

            manager = _websocket_manager

            # Get status for specific connection or all connections
            if connection_id:
                status = await manager.get_connection_status(connection_id)
                if status:
                    return {
                        "success": True,
                        "connection_id": connection_id,
                        "status": {
                            "state": status.connection_state.value,
                            "messages_sent": status.total_messages_sent,
                            "messages_received": status.total_messages_received,
                            "bytes_sent": status.total_bytes_sent,
                            "bytes_received": status.total_bytes_received,
                            "connection_time": status.connection_time
                        }
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Connection '{connection_id}' not found"
                    }
            else:
                # Get status for all connections
                all_status = await manager.get_all_status()
                return {
                    "success": True,
                    "total_connections": len(all_status),
                    "connections": {
                        conn_id: {
                            "state": status.connection_state.value,
                            "messages_sent": status.total_messages_sent,
                            "messages_received": status.total_messages_received,
                            "bytes_sent": status.total_bytes_sent,
                            "bytes_received": status.total_bytes_received,
                            "connection_time": status.connection_time
                        }
                        for conn_id, status in all_status.items()
                    }
                }

        except Exception as e:
            error_msg = f"WebSocket status error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }

    @mcp.tool(
        name="graphql_query",
        description="Execute GraphQL queries with schema validation and caching",
        tags={"graphql", "query", "api", "schema"}
    )
    async def graphql_query_tool(
        endpoint: Annotated[str, Field(description="GraphQL endpoint URL")],
        query: Annotated[str, Field(description="GraphQL query string")],
        variables: Annotated[
            Optional[Dict[str, Any]],
            Field(description="Query variables")
        ] = None,
        operation_name: Annotated[
            Optional[str],
            Field(description="Operation name for the query")
        ] = None,
        headers: Annotated[
            Optional[Dict[str, str]],
            Field(description="Additional HTTP headers")
        ] = None,
        timeout: Annotated[
            float,
            Field(description="Request timeout in seconds", ge=1.0, le=300.0)
        ] = 30.0,
        use_cache: Annotated[
            bool,
            Field(description="Enable response caching")
        ] = True,
        validate_query: Annotated[
            bool,
            Field(description="Validate query against schema")
        ] = True,
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Execute a GraphQL query with comprehensive features.

        This tool provides GraphQL query execution with schema validation,
        response caching, and error handling.
        """
        try:
            if ctx:
                await ctx.info(f"Executing GraphQL query: {endpoint}")

            # Validate endpoint URL
            if not is_valid_url(endpoint):
                raise ValueError(f"Invalid endpoint URL: {endpoint}")

            # Get or create GraphQL client
            global _graphql_clients
            client_key = f"{endpoint}_{timeout}_{validate_query}"

            if client_key not in _graphql_clients:
                config = GraphQLConfig(
                    endpoint=HttpUrl(endpoint),
                    timeout=timeout,
                    validate_queries=validate_query,
                    enable_response_caching=use_cache,
                    headers=headers or {}
                )
                _graphql_clients[client_key] = GraphQLClient(config)

            client = _graphql_clients[client_key]

            # Create GraphQL query
            gql_query = GraphQLQuery(
                query=query,
                variables=variables or {},
                operation_name=operation_name
            )

            # Execute query
            result = await client.execute(gql_query, use_cache=use_cache)

            return {
                "success": result.success,
                "data": result.data,
                "errors": [
                    {
                        "message": error.get("message", str(error)) if isinstance(error, dict) else str(error),
                        "locations": error.get("locations", []) if isinstance(error, dict) else [],
                        "path": error.get("path", []) if isinstance(error, dict) else [],
                        "extensions": error.get("extensions", {}) if isinstance(error, dict) else {}
                    }
                    for error in (result.errors or [])
                ],
                "extensions": result.extensions or {},
                "query_info": {
                    "operation_name": operation_name,
                    "variables": variables or {},
                    "cached": getattr(result, 'from_cache', False)
                },
                "performance": {
                    "execution_time": getattr(result, 'execution_time', 0.0),
                    "response_size": len(str(result.data)) if result.data else 0
                }
            }

        except GraphQLError as e:
            error_msg = f"GraphQL error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "error_type": "GraphQLError",
                "endpoint": endpoint
            }
        except Exception as e:
            error_msg = f"GraphQL query error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "error_type": "UnexpectedError",
                "endpoint": endpoint
            }

    @mcp.tool(
        name="graphql_mutation",
        description="Execute GraphQL mutations for data modification",
        tags={"graphql", "mutation", "api", "modify"}
    )
    async def graphql_mutation_tool(
        endpoint: Annotated[str, Field(description="GraphQL endpoint URL")],
        mutation: Annotated[str, Field(description="GraphQL mutation string")],
        variables: Annotated[
            Optional[Dict[str, Any]],
            Field(description="Mutation variables")
        ] = None,
        operation_name: Annotated[
            Optional[str],
            Field(description="Operation name for the mutation")
        ] = None,
        headers: Annotated[
            Optional[Dict[str, str]],
            Field(description="Additional HTTP headers")
        ] = None,
        timeout: Annotated[
            float,
            Field(description="Request timeout in seconds", ge=1.0, le=300.0)
        ] = 30.0,
        validate_query: Annotated[
            bool,
            Field(description="Validate mutation against schema")
        ] = True,
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Execute a GraphQL mutation for data modification.

        This tool provides GraphQL mutation execution with schema validation
        and comprehensive error handling.
        """
        try:
            if ctx:
                await ctx.info(f"Executing GraphQL mutation: {endpoint}")

            # Validate endpoint URL
            if not is_valid_url(endpoint):
                raise ValueError(f"Invalid endpoint URL: {endpoint}")

            # Get or create GraphQL client
            global _graphql_clients
            client_key = f"{endpoint}_{timeout}_{validate_query}"

            if client_key not in _graphql_clients:
                config = GraphQLConfig(
                    endpoint=HttpUrl(endpoint),
                    timeout=timeout,
                    validate_queries=validate_query,
                    enable_response_caching=False,  # Don't cache mutations
                    headers=headers or {}
                )
                _graphql_clients[client_key] = GraphQLClient(config)

            client = _graphql_clients[client_key]

            # Create GraphQL mutation
            gql_mutation = GraphQLMutation(
                query=mutation,
                variables=variables or {},
                operation_name=operation_name
            )

            # Execute mutation
            result = await client.execute(gql_mutation, use_cache=False)

            return {
                "success": result.success,
                "data": result.data,
                "errors": [
                    {
                        "message": error.get("message", str(error)) if isinstance(error, dict) else str(error),
                        "locations": error.get("locations", []) if isinstance(error, dict) else [],
                        "path": error.get("path", []) if isinstance(error, dict) else [],
                        "extensions": error.get("extensions", {}) if isinstance(error, dict) else {}
                    }
                    for error in (result.errors or [])
                ],
                "extensions": result.extensions or {},
                "mutation_info": {
                    "operation_name": operation_name,
                    "variables": variables or {}
                },
                "performance": {
                    "execution_time": getattr(result, 'execution_time', 0.0),
                    "response_size": len(str(result.data)) if result.data else 0
                }
            }

        except GraphQLError as e:
            error_msg = f"GraphQL mutation error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "error_type": "GraphQLError",
                "endpoint": endpoint
            }
        except Exception as e:
            error_msg = f"GraphQL mutation error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "error_type": "UnexpectedError",
                "endpoint": endpoint
            }

    @mcp.tool(
        name="graphql_introspect",
        description="Introspect GraphQL schema to discover available types, queries, and mutations",
        tags={"graphql", "introspection", "schema", "discovery"}
    )
    async def graphql_introspect_tool(
        endpoint: Annotated[str, Field(description="GraphQL endpoint URL")],
        headers: Annotated[
            Optional[Dict[str, str]],
            Field(description="Additional HTTP headers")
        ] = None,
        timeout: Annotated[
            float,
            Field(description="Request timeout in seconds", ge=1.0, le=300.0)
        ] = 30.0,
        force_refresh: Annotated[
            bool,
            Field(description="Force schema refresh even if cached")
        ] = False,
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Introspect GraphQL schema to discover available operations.

        This tool performs GraphQL schema introspection to discover available
        types, queries, mutations, and subscriptions.
        """
        try:
            if ctx:
                await ctx.info(f"Introspecting GraphQL schema: {endpoint}")

            # Validate endpoint URL
            if not is_valid_url(endpoint):
                raise ValueError(f"Invalid endpoint URL: {endpoint}")

            # Get or create GraphQL client
            global _graphql_clients
            client_key = f"{endpoint}_{timeout}_introspect"

            if client_key not in _graphql_clients:
                config = GraphQLConfig(
                    endpoint=HttpUrl(endpoint),
                    timeout=timeout,
                    introspection_enabled=True,
                    headers=headers or {}
                )
                _graphql_clients[client_key] = GraphQLClient(config)

            client = _graphql_clients[client_key]

            # Perform schema introspection
            schema = await client.introspect_schema(force_refresh=force_refresh)

            return {
                "success": True,
                "endpoint": endpoint,
                "schema": {
                    "types": [
                        {
                            "name": type_info.get("name"),
                            "kind": type_info.get("kind"),
                            "description": type_info.get("description"),
                            "fields": [
                                {
                                    "name": field.get("name"),
                                    "type": field.get("type", {}).get("name"),
                                    "description": field.get("description")
                                }
                                for field in type_info.get("fields", [])
                            ] if type_info.get("fields") else []
                        }
                        for type_info in schema.types
                    ],
                    "queries": [
                        {
                            "name": query.get("name"),
                            "description": query.get("description"),
                            "type": query.get("type", {}).get("name")
                        }
                        for query in schema.queries
                    ],
                    "mutations": [
                        {
                            "name": mutation.get("name"),
                            "description": mutation.get("description"),
                            "type": mutation.get("type", {}).get("name")
                        }
                        for mutation in schema.mutations
                    ],
                    "subscriptions": [
                        {
                            "name": subscription.get("name"),
                            "description": subscription.get("description"),
                            "type": subscription.get("type", {}).get("name")
                        }
                        for subscription in schema.subscriptions
                    ],
                    "directives": [
                        {
                            "name": directive.get("name"),
                            "description": directive.get("description"),
                            "locations": directive.get("locations", [])
                        }
                        for directive in schema.directives
                    ]
                },
                "stats": {
                    "total_types": len(schema.types),
                    "total_queries": len(schema.queries),
                    "total_mutations": len(schema.mutations),
                    "total_subscriptions": len(schema.subscriptions),
                    "total_directives": len(schema.directives)
                }
            }

        except GraphQLError as e:
            error_msg = f"GraphQL introspection error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "error_type": "GraphQLError",
                "endpoint": endpoint
            }
        except Exception as e:
            error_msg = f"GraphQL introspection error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "error_type": "UnexpectedError",
                "endpoint": endpoint
            }

    @mcp.tool(
        name="auth_configure",
        description="Configure authentication methods for API access",
        tags={"auth", "configuration", "api", "security"}
    )
    async def auth_configure_tool(
        auth_type: Annotated[
            Literal["api_key", "oauth2", "jwt", "basic", "bearer"],
            Field(description="Type of authentication to configure")
        ],
        auth_name: Annotated[
            str,
            Field(description="Unique name for this authentication configuration")
        ],
        config: Annotated[
            Dict[str, Any],
            Field(description="Authentication configuration parameters")
        ],
        set_as_default: Annotated[
            bool,
            Field(description="Set this as the default authentication method")
        ] = False,
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Configure authentication methods for API access.

        This tool allows configuration of various authentication methods
        including API keys, OAuth2, JWT, Basic auth, and Bearer tokens.
        """
        try:
            if ctx:
                await ctx.info(f"Configuring {auth_type} authentication: {auth_name}")

            # Initialize auth manager if needed
            global _auth_manager
            if _auth_manager is None:
                _auth_manager = AuthManager()

            # Create authentication method based on type
            if auth_type == "api_key":
                auth_config = APIKeyConfig(**config)
                auth_method = APIKeyAuth(auth_config)
            elif auth_type == "oauth2":
                auth_config = OAuth2Config(**config)
                auth_method = OAuth2Auth(auth_config)
            elif auth_type == "jwt":
                auth_config = JWTConfig(**config)
                auth_method = JWTAuth(auth_config)
            elif auth_type == "basic":
                auth_config = BasicAuthConfig(**config)
                auth_method = BasicAuth(auth_config)
            elif auth_type == "bearer":
                auth_config = BearerTokenConfig(**config)
                auth_method = BearerTokenAuth(auth_config)
            else:
                raise ValueError(f"Unsupported authentication type: {auth_type}")

            # Add authentication method
            _auth_manager.add_auth_method(auth_name, auth_method)

            # Set as default if requested
            if set_as_default:
                _auth_manager.set_default_method(auth_name)

            return {
                "success": True,
                "auth_name": auth_name,
                "auth_type": auth_type,
                "is_default": set_as_default,
                "config_summary": {
                    key: "***" if "secret" in key.lower() or "password" in key.lower() or "token" in key.lower()
                    else value
                    for key, value in config.items()
                }
            }

        except Exception as e:
            error_msg = f"Authentication configuration error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "auth_name": auth_name,
                "auth_type": auth_type
            }

    @mcp.tool(
        name="auth_authenticate",
        description="Perform authentication and get credentials",
        tags={"auth", "authenticate", "credentials", "token"}
    )
    async def auth_authenticate_tool(
        auth_name: Annotated[
            Optional[str],
            Field(description="Name of authentication method (uses default if not specified)")
        ] = None,
        auth_params: Annotated[
            Optional[Dict[str, Any]],
            Field(description="Additional authentication parameters")
        ] = None,
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Perform authentication and retrieve credentials.

        This tool executes the authentication process for a configured
        authentication method and returns the resulting credentials.
        """
        try:
            if ctx:
                await ctx.info(f"Performing authentication: {auth_name or 'default'}")

            # Get auth manager
            global _auth_manager
            if _auth_manager is None:
                raise ValueError("No authentication manager configured. Configure authentication first.")

            # Perform authentication
            result = await _auth_manager.authenticate(auth_name, **(auth_params or {}))

            return {
                "success": result.success,
                "auth_name": auth_name or "default",
                "headers": result.headers or {},
                "params": result.params or {},
                "body_data": result.body_data or {},
                "expires_at": result.expires_at.isoformat() if result.expires_at else None,
                "error": result.error,
                "metadata": {
                    "has_headers": bool(result.headers),
                    "has_params": bool(result.params),
                    "has_body_data": bool(result.body_data),
                    "is_expired": result.is_expired
                }
            }

        except Exception as e:
            error_msg = f"Authentication error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "auth_name": auth_name or "default"
            }

    @mcp.tool(
        name="auth_refresh",
        description="Refresh authentication credentials",
        tags={"auth", "refresh", "token", "renewal"}
    )
    async def auth_refresh_tool(
        auth_name: Annotated[
            Optional[str],
            Field(description="Name of authentication method (uses default if not specified)")
        ] = None,
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Refresh authentication credentials.

        This tool refreshes expired or expiring authentication credentials
        for methods that support token refresh (OAuth2, JWT).
        """
        try:
            if ctx:
                await ctx.info(f"Refreshing authentication: {auth_name or 'default'}")

            # Get auth manager
            global _auth_manager
            if _auth_manager is None:
                raise ValueError("No authentication manager configured.")

            # Get authentication method
            auth_method = _auth_manager.get_auth_method(auth_name)
            if not auth_method:
                raise ValueError(f"Authentication method '{auth_name}' not found")

            # Perform refresh
            result = await auth_method.refresh()

            return {
                "success": result.success,
                "auth_name": auth_name or "default",
                "headers": result.headers or {},
                "params": result.params or {},
                "body_data": result.body_data or {},
                "expires_at": result.expires_at.isoformat() if result.expires_at else None,
                "error": result.error,
                "metadata": {
                    "has_headers": bool(result.headers),
                    "has_params": bool(result.params),
                    "has_body_data": bool(result.body_data),
                    "is_expired": result.is_expired
                }
            }

        except Exception as e:
            error_msg = f"Authentication refresh error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "auth_name": auth_name or "default"
            }

    @mcp.tool(
        name="content_parse",
        description="Parse and extract structured data from various content types",
        tags={"content", "parse", "extract", "transform"}
    )
    async def content_parse_tool(
        content: Annotated[str, Field(description="Content to parse")],
        content_type: Annotated[
            Literal["json", "html", "text", "csv", "xml", "markdown"],
            Field(description="Type of content to parse")
        ],
        url: Annotated[
            Optional[str],
            Field(description="Source URL for context (optional)")
        ] = None,
        headers: Annotated[
            Optional[Dict[str, str]],
            Field(description="HTTP headers for additional context")
        ] = None,
        extract_links: Annotated[
            bool,
            Field(description="Extract links from HTML content")
        ] = True,
        analyze_content: Annotated[
            bool,
            Field(description="Perform content analysis and summarization")
        ] = True,
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Parse and extract structured data from various content types.

        This tool provides comprehensive content parsing capabilities for
        different formats including JSON, HTML, CSV, XML, and more.
        """
        try:
            if ctx:
                await ctx.info(f"Parsing {content_type} content")

            # Create enhanced content parser
            parser = EnhancedContentParser()

            # Convert content to bytes
            content_bytes = content.encode('utf-8')

            # Map content type to ContentType enum
            content_type_map = {
                "json": ContentType.JSON,
                "html": ContentType.HTML,
                "text": ContentType.TEXT,
                "csv": ContentType.CSV,
                "xml": ContentType.XML,
                "markdown": ContentType.MARKDOWN
            }

            if content_type not in content_type_map:
                raise ValueError(f"Unsupported content type: {content_type}")

            # Parse content
            parsed_content, result = await parser.parse_content(
                content_bytes=content_bytes,
                requested_type=content_type_map[content_type],
                url=url,
                headers=headers or {}
            )

            # Extract additional metadata
            metadata = {}

            if result.pdf_metadata:
                metadata["pdf"] = result.pdf_metadata.__dict__
            if result.image_metadata:
                metadata["image"] = result.image_metadata.__dict__
            if result.feed_metadata:
                metadata["feed"] = result.feed_metadata.__dict__
            if result.csv_metadata:
                metadata["csv"] = result.csv_metadata.__dict__
            if result.content_summary:
                metadata["summary"] = result.content_summary.__dict__

            # Extract links if requested and content is HTML
            links = []
            if extract_links and content_type == "html" and result.links:
                links = [link.__dict__ for link in result.links]

            return {
                "success": True,
                "content_type": content_type,
                "parsed_content": parsed_content,
                "metadata": metadata,
                "links": links,
                "feed_items": [item.__dict__ for item in result.feed_items] if result.feed_items else [],
                "analysis": {
                    "content_length": len(content),
                    "parsed_successfully": True,
                    "has_metadata": bool(metadata),
                    "links_found": len(links),
                    "feed_items_found": len(result.feed_items) if result.feed_items else 0
                }
            }

        except Exception as e:
            error_msg = f"Content parsing error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "content_type": content_type,
                "content_length": len(content)
            }

    @mcp.tool(
        name="content_transform",
        description="Transform content using extraction pipelines and data transformers",
        tags={"content", "transform", "extract", "pipeline"}
    )
    async def content_transform_tool(
        content: Annotated[str, Field(description="Content to transform")],
        transformations: Annotated[
            List[Dict[str, Any]],
            Field(description="List of transformation configurations")
        ],
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Transform content using extraction pipelines and data transformers.

        This tool applies a series of transformations to content including
        JSONPath extraction, HTML parsing, regex matching, and data validation.
        """
        try:
            if ctx:
                await ctx.info(f"Applying {len(transformations)} transformations")

            # Create transformation pipeline
            pipeline = TransformationPipeline()

            # Add transformers based on configuration
            for i, transform_config in enumerate(transformations):
                transform_type = transform_config.get("type")

                if transform_type == "jsonpath":
                    expressions = transform_config.get("expressions", {})
                    strict = transform_config.get("strict", False)
                    transformer = JSONPathExtractor(expressions, strict)

                elif transform_type == "html":
                    selectors = transform_config.get("selectors", {})
                    extract_text = transform_config.get("extract_text", True)
                    base_url = transform_config.get("base_url")
                    transformer = HTMLExtractor(selectors, extract_text=extract_text, base_url=base_url)

                elif transform_type == "regex":
                    patterns = transform_config.get("patterns", {})
                    flags = transform_config.get("flags", 0)
                    transformer = RegexExtractor(patterns, flags)

                else:
                    raise ValueError(f"Unsupported transformation type: {transform_type}")

                pipeline.add_transformer(transformer)

            # Apply transformations
            result = await pipeline.transform(content, {})

            return {
                "success": True,
                "transformed_data": result.data,
                "errors": result.errors,
                "metadata": result.metadata,
                "transformations_applied": len(transformations),
                "analysis": {
                    "has_errors": bool(result.errors),
                    "fields_extracted": len(result.data),
                    "metadata_items": len(result.metadata)
                }
            }

        except Exception as e:
            error_msg = f"Content transformation error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "transformations_count": len(transformations)
            }

    @mcp.tool(
        name="metrics_summary",
        description="Get comprehensive system metrics and performance summary",
        tags={"metrics", "monitoring", "performance", "health"}
    )
    async def metrics_summary_tool(
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive system metrics and performance summary.

        This tool provides detailed metrics about system performance including
        success rates, response times, error summaries, and health indicators.
        """
        try:
            if ctx:
                await ctx.info("Retrieving system metrics summary")

            # Get comprehensive metrics summary
            summary = get_metrics_summary()

            return {
                "success": True,
                "metrics": summary,
                "timestamp": time.time(),
                "health_status": "healthy" if summary.get("recent_success_rate", 0) > 90 else "degraded"
            }

        except Exception as e:
            error_msg = f"Metrics summary error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }

    @mcp.tool(
        name="metrics_recent",
        description="Get recent performance metrics for monitoring current system health",
        tags={"metrics", "monitoring", "recent", "performance"}
    )
    async def metrics_recent_tool(
        minutes: Annotated[
            int,
            Field(description="Number of minutes to look back", ge=1, le=60)
        ] = 5,
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Get recent performance metrics for monitoring current system health.

        This tool provides recent performance data useful for real-time monitoring
        and alerting on system health issues.
        """
        try:
            if ctx:
                await ctx.info(f"Retrieving metrics for last {minutes} minutes")

            # Get recent performance metrics
            recent_metrics = get_recent_performance()

            return {
                "success": True,
                "time_window_minutes": minutes,
                "metrics": {
                    "total_requests": recent_metrics.total_requests,
                    "successful_requests": recent_metrics.successful_requests,
                    "failed_requests": recent_metrics.failed_requests,
                    "success_rate": recent_metrics.success_rate,
                    "average_response_time": recent_metrics.average_response_time,
                    "min_response_time": recent_metrics.min_response_time,
                    "max_response_time": recent_metrics.max_response_time,
                    "total_response_size": recent_metrics.total_response_size,
                    "error_counts": recent_metrics.error_counts,
                    "status_code_counts": recent_metrics.status_code_counts,
                    "method_counts": recent_metrics.method_counts,
                    "host_counts": recent_metrics.host_counts
                },
                "timestamp": time.time(),
                "health_indicators": {
                    "is_healthy": recent_metrics.success_rate > 90,
                    "response_time_acceptable": recent_metrics.average_response_time < 5.0,
                    "error_rate_low": recent_metrics.failed_requests < recent_metrics.total_requests * 0.1
                }
            }

        except Exception as e:
            error_msg = f"Recent metrics error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "time_window_minutes": minutes
            }

    @mcp.tool(
        name="metrics_record",
        description="Record custom metrics for monitoring and analytics",
        tags={"metrics", "record", "custom", "tracking"}
    )
    async def metrics_record_tool(
        url: Annotated[str, Field(description="URL for the request")],
        method: Annotated[str, Field(description="HTTP method")],
        status_code: Annotated[int, Field(description="HTTP status code")],
        response_time: Annotated[float, Field(description="Response time in seconds")],
        response_size: Annotated[
            int,
            Field(description="Response size in bytes")
        ] = 0,
        error: Annotated[
            Optional[str],
            Field(description="Error message if request failed")
        ] = None,
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Record custom metrics for monitoring and analytics.

        This tool allows manual recording of request metrics for custom
        monitoring scenarios and analytics tracking.
        """
        try:
            if ctx:
                await ctx.info(f"Recording metrics for {method} {url}")

            # Record the metrics
            record_request_metrics(
                url=url,
                method=method,
                status_code=status_code,
                response_time=response_time,
                response_size=response_size,
                error=error
            )

            return {
                "success": True,
                "recorded_metrics": {
                    "url": url,
                    "method": method,
                    "status_code": status_code,
                    "response_time": response_time,
                    "response_size": response_size,
                    "error": error,
                    "timestamp": time.time()
                }
            }

        except Exception as e:
            error_msg = f"Metrics recording error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "url": url,
                "method": method
            }

    @mcp.tool(
        name="ftp_list_directory",
        description="List files and directories in an FTP directory",
        tags={"ftp", "directory", "list", "files"}
    )
    async def ftp_list_directory_tool(
        url: Annotated[str, Field(description="FTP URL of the directory to list")],
        username: Annotated[
            Optional[str],
            Field(description="FTP username (optional for anonymous)")
        ] = None,
        password: Annotated[
            Optional[str],
            Field(description="FTP password")
        ] = None,
        timeout: Annotated[
            float,
            Field(description="Connection timeout in seconds", ge=1.0, le=300.0)
        ] = 30.0,
        use_ssl: Annotated[
            bool,
            Field(description="Use FTPS (FTP over SSL)")
        ] = False,
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        List files and directories in an FTP directory.

        This tool provides FTP directory listing capabilities with support
        for both anonymous and authenticated access.
        """
        try:
            if ctx:
                await ctx.info(f"Listing FTP directory: {url}")

            # Validate FTP URL
            if not url.startswith(('ftp://', 'ftps://')):
                raise ValueError("URL must start with ftp:// or ftps://")

            # Create FTP configuration
            auth_type = FTPAuthType.ANONYMOUS if not username else FTPAuthType.USER_PASS
            config = FTPConfig(
                auth_type=auth_type,
                username=username,
                password=password,
                connection_timeout=timeout
            )

            # List directory
            files = await ftp_list_directory(url, config)

            return {
                "success": True,
                "url": url,
                "file_count": len(files),
                "files": [
                    {
                        "name": file_info.name,
                        "path": file_info.path,
                        "size": file_info.size,
                        "modified_time": file_info.modified_time.isoformat() if file_info.modified_time else None,
                        "is_directory": file_info.is_directory,
                        "permissions": file_info.permissions
                    }
                    for file_info in files
                ]
            }

        except Exception as e:
            error_msg = f"FTP directory listing error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "url": url
            }

    @mcp.tool(
        name="ftp_download_file",
        description="Download a file from FTP server with progress tracking",
        tags={"ftp", "download", "file", "transfer"}
    )
    async def ftp_download_file_tool(
        url: Annotated[str, Field(description="FTP URL of the file to download")],
        local_path: Annotated[str, Field(description="Local path to save the file")],
        username: Annotated[
            Optional[str],
            Field(description="FTP username (optional for anonymous)")
        ] = None,
        password: Annotated[
            Optional[str],
            Field(description="FTP password")
        ] = None,
        timeout: Annotated[
            float,
            Field(description="Connection timeout in seconds", ge=1.0, le=300.0)
        ] = 30.0,
        use_ssl: Annotated[
            bool,
            Field(description="Use FTPS (FTP over SSL)")
        ] = False,
        resume: Annotated[
            bool,
            Field(description="Resume partial download if file exists")
        ] = False,
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Download a file from FTP server with progress tracking.

        This tool provides FTP file download capabilities with support for
        resumable downloads and progress monitoring.
        """
        try:
            if ctx:
                await ctx.info(f"Downloading FTP file: {url} -> {local_path}")

            # Validate FTP URL
            if not url.startswith(('ftp://', 'ftps://')):
                raise ValueError("URL must start with ftp:// or ftps://")

            # Create FTP configuration
            auth_type = FTPAuthType.ANONYMOUS if not username else FTPAuthType.USER_PASS
            config = FTPConfig(
                auth_type=auth_type,
                username=username,
                password=password,
                connection_timeout=timeout
            )

            # Progress callback
            def progress_callback(progress: FTPProgressInfo) -> None:
                if ctx:
                    asyncio.create_task(ctx.report_progress(
                        progress.bytes_transferred,
                        progress.total_bytes or 0
                    ))

            # Download file
            from pathlib import Path
            result = await ftp_download_file(
                url=url,
                local_path=Path(local_path),
                config=config,
                progress_callback=progress_callback
            )

            return {
                "success": result.is_success,
                "url": url,
                "local_path": local_path,
                "bytes_transferred": result.bytes_transferred,
                "total_bytes": result.total_bytes,
                "response_time": result.response_time,
                "transfer_rate_mbps": result.transfer_rate_mbps,
                "error": result.error
            }

        except Exception as e:
            error_msg = f"FTP download error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "url": url,
                "local_path": local_path
            }

    @mcp.tool(
        name="crawler_scrape",
        description="Scrape web content using advanced crawler APIs with fallback support",
        tags={"crawler", "scrape", "content", "extraction"}
    )
    async def crawler_scrape_tool(
        url: Annotated[str, Field(description="URL to scrape")],
        crawler_type: Annotated[
            Optional[Literal["firecrawl", "spider", "tavily", "anycrawl"]],
            Field(description="Preferred crawler type (auto-select if not specified)")
        ] = None,
        content_format: Annotated[
            Literal["markdown", "html", "text"],
            Field(description="Desired content format")
        ] = "markdown",
        include_links: Annotated[
            bool,
            Field(description="Extract and include links from the page")
        ] = True,
        include_images: Annotated[
            bool,
            Field(description="Extract and include image URLs")
        ] = True,
        wait_for_js: Annotated[
            bool,
            Field(description="Wait for JavaScript to render (if supported)")
        ] = False,
        timeout: Annotated[
            float,
            Field(description="Request timeout in seconds", ge=1.0, le=300.0)
        ] = 30.0,
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Scrape web content using advanced crawler APIs with automatic fallback.

        This tool provides intelligent web scraping using multiple crawler services
        with automatic fallback and content format conversion.
        """
        try:
            if ctx:
                await ctx.info(f"Scraping URL with crawler: {url}")

            # Validate URL
            if not is_valid_url(url):
                raise ValueError(f"Invalid URL format: {url}")

            # Map crawler type
            crawler_type_map = {
                "firecrawl": CrawlerType.FIRECRAWL,
                "spider": CrawlerType.SPIDER,
                "tavily": CrawlerType.TAVILY,
                "anycrawl": CrawlerType.ANYCRAWL
            }

            # Create crawler request
            request = CrawlerRequest(
                url=HttpUrl(url),
                operation=CrawlerCapability.SCRAPE,
                content_type=ContentType.MARKDOWN if content_format == "markdown" else ContentType.HTML,
                include_links=include_links,
                include_images=include_images,
                wait_for_js=wait_for_js,
                timeout=timeout
            )

            # Use crawler API
            result = await crawler_fetch_url(
                url=url,
                use_crawler=True,
                crawler_type=crawler_type_map.get(crawler_type) if crawler_type else None,
                operation=CrawlerCapability.SCRAPE,
                content_type=ContentType.MARKDOWN if content_format == "markdown" else ContentType.HTML
            )

            return {
                "success": result.success,
                "url": url,
                "content": result.content,
                "content_type": result.content_type.value,
                "links": [link.__dict__ for link in result.links] if result.links else [],
                "images": result.images or [],
                "metadata": {
                    "title": result.title,
                    "description": result.description,
                    "status_code": result.status_code,
                    "response_time": result.response_time,
                    "content_length": len(result.content) if result.content else 0,
                    "crawler_used": getattr(result, 'crawler_type', 'unknown'),
                    "pages_crawled": getattr(result, 'pages_crawled', 1)
                },
                "error": result.error
            }

        except Exception as e:
            error_msg = f"Crawler scraping error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "url": url
            }

    @mcp.tool(
        name="crawler_search",
        description="Search the web using AI-powered crawler APIs",
        tags={"crawler", "search", "ai", "web"}
    )
    async def crawler_search_tool(
        query: Annotated[str, Field(description="Search query")],
        max_results: Annotated[
            int,
            Field(description="Maximum number of results to return", ge=1, le=20)
        ] = 5,
        include_answer: Annotated[
            bool,
            Field(description="Include AI-generated answer summary")
        ] = True,
        include_images: Annotated[
            bool,
            Field(description="Include relevant images in results")
        ] = False,
        search_depth: Annotated[
            Literal["basic", "advanced"],
            Field(description="Search depth and quality")
        ] = "basic",
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Search the web using AI-powered crawler APIs.

        This tool provides intelligent web search capabilities using advanced
        crawler services that can understand context and provide AI-generated summaries.
        """
        try:
            if ctx:
                await ctx.info(f"Searching web with query: {query}")

            # Use crawler search API
            result = await crawler_search_web(
                query=query,
                max_results=max_results,
                include_answer=include_answer,
                include_images=include_images,
                search_depth=search_depth
            )

            return {
                "success": result.success,
                "query": query,
                "answer": getattr(result, 'answer', None),
                "results": [
                    {
                        "title": search_result.get("title", ""),
                        "url": search_result.get("url", ""),
                        "content": search_result.get("content", ""),
                        "score": search_result.get("score", 0.0)
                    }
                    for search_result in (getattr(result, 'search_results', []) or [])
                ],
                "images": getattr(result, 'images', []) or [],
                "metadata": {
                    "total_results": len(getattr(result, 'search_results', []) or []),
                    "response_time": result.response_time,
                    "crawler_used": getattr(result, 'crawler_type', 'unknown'),
                    "has_answer": bool(getattr(result, 'answer', None))
                },
                "error": result.error
            }

        except Exception as e:
            error_msg = f"Crawler search error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "query": query
            }

    @mcp.tool(
        name="performance_optimize",
        description="Optimize system performance with caching, connection pooling, and resource management",
        tags={"performance", "optimization", "cache", "pool"}
    )
    async def performance_optimize_tool(
        action: Annotated[
            Literal["enable_cache", "configure_pool", "optimize_memory", "tune_concurrency"],
            Field(description="Performance optimization action")
        ],
        config: Annotated[
            Optional[Dict[str, Any]],
            Field(description="Configuration parameters for the optimization")
        ] = None,
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Optimize system performance with various strategies.

        This tool provides comprehensive performance optimization including
        caching, connection pooling, memory management, and concurrency tuning.
        """
        try:
            if ctx:
                await ctx.info(f"Applying performance optimization: {action}")

            global _cache_manager, _connection_pool, _rate_limiter

            if action == "enable_cache":
                # Configure enhanced caching
                cache_config = EnhancedCacheConfig(
                    backend=CacheBackend.MEMORY,
                    max_size=config.get("max_size", 1000) if config else 1000,
                    default_ttl=config.get("ttl", 3600) if config else 3600,
                    enable_compression=config.get("enable_compression", True) if config else True
                )

                _cache_manager = EnhancedCache(cache_config)

                return {
                    "success": True,
                    "action": action,
                    "cache_config": {
                        "backend": cache_config.backend.value,
                        "max_size": cache_config.max_size,
                        "default_ttl": cache_config.default_ttl,
                        "compression_enabled": cache_config.enable_compression
                    }
                }

            elif action == "configure_pool":
                # Configure connection pooling
                pool_config = config or {}

                connector = aiohttp.TCPConnector(
                    limit=pool_config.get("max_connections", 100),
                    limit_per_host=pool_config.get("max_per_host", 30),
                    ttl_dns_cache=pool_config.get("dns_cache_ttl", 300),
                    use_dns_cache=True,
                    keepalive_timeout=pool_config.get("keepalive_timeout", 30),
                    enable_cleanup_closed=True
                )

                timeout = aiohttp.ClientTimeout(
                    total=pool_config.get("total_timeout", 60),
                    connect=pool_config.get("connect_timeout", 10)
                )

                if _connection_pool:
                    await _connection_pool.close()

                _connection_pool = aiohttp.ClientSession(
                    connector=connector,
                    timeout=timeout
                )

                return {
                    "success": True,
                    "action": action,
                    "pool_config": {
                        "max_connections": pool_config.get("max_connections", 100),
                        "max_per_host": pool_config.get("max_per_host", 30),
                        "dns_cache_ttl": pool_config.get("dns_cache_ttl", 300),
                        "keepalive_timeout": pool_config.get("keepalive_timeout", 30)
                    }
                }

            elif action == "optimize_memory":
                # Memory optimization
                import gc

                # Force garbage collection
                collected = gc.collect()

                # Get memory statistics
                try:
                    import psutil
                    process = psutil.Process()
                    memory_info = process.memory_info()
                    memory_percent = process.memory_percent()
                except ImportError:
                    memory_info = None
                    memory_percent = None

                result = {
                    "success": True,
                    "action": action,
                    "memory_stats": {
                        "objects_collected": collected
                    }
                }

                if memory_info:
                    result["memory_stats"].update({
                        "memory_rss": memory_info.rss,
                        "memory_vms": memory_info.vms,
                        "memory_percent": memory_percent
                    })

                return result

            elif action == "tune_concurrency":
                # Concurrency tuning
                concurrency_config = config or {}

                # Initialize rate limiter if not exists
                if _rate_limiter is None:
                    _rate_limiter = {}

                max_concurrent = concurrency_config.get("max_concurrent", 50)
                rate_limit = concurrency_config.get("rate_limit", 10.0)  # requests per second

                return {
                    "success": True,
                    "action": action,
                    "concurrency_config": {
                        "max_concurrent": max_concurrent,
                        "rate_limit": rate_limit,
                        "adaptive_enabled": concurrency_config.get("adaptive", True)
                    }
                }

            else:
                raise ValueError(f"Unknown optimization action: {action}")

        except Exception as e:
            error_msg = f"Performance optimization error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "action": action
            }

    @mcp.tool(
        name="performance_monitor",
        description="Monitor system performance and resource usage",
        tags={"performance", "monitoring", "resources", "health"}
    )
    async def performance_monitor_tool(
        metric_type: Annotated[
            Literal["system", "cache", "connections", "memory"],
            Field(description="Type of performance metrics to retrieve")
        ] = "system",
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """
        Monitor system performance and resource usage.

        This tool provides detailed performance monitoring including system
        resources, cache performance, connection statistics, and memory usage.
        """
        try:
            if ctx:
                await ctx.info(f"Monitoring performance metrics: {metric_type}")

            if metric_type == "system":
                # System performance metrics
                try:
                    import psutil

                    cpu_percent = psutil.cpu_percent(interval=1)
                    memory = psutil.virtual_memory()
                    disk = psutil.disk_usage('/')

                    return {
                        "success": True,
                        "metric_type": metric_type,
                        "system_metrics": {
                            "cpu_percent": cpu_percent,
                            "memory_total": memory.total,
                            "memory_available": memory.available,
                            "memory_percent": memory.percent,
                            "disk_total": disk.total,
                            "disk_free": disk.free,
                            "disk_percent": (disk.used / disk.total) * 100
                        }
                    }
                except ImportError:
                    return {
                        "success": False,
                        "error": "psutil not available for system metrics",
                        "metric_type": metric_type
                    }

            elif metric_type == "cache":
                # Cache performance metrics
                global _cache_manager

                if _cache_manager:
                    stats = _cache_manager.get_stats()
                    return {
                        "success": True,
                        "metric_type": metric_type,
                        "cache_metrics": {
                            "hits": stats.get("hits", 0),
                            "misses": stats.get("misses", 0),
                            "sets": stats.get("sets", 0),
                            "hit_rate": stats.get("hits", 0) / max(stats.get("hits", 0) + stats.get("misses", 0), 1) * 100,
                            "size": stats.get("size", 0)
                        }
                    }
                else:
                    return {
                        "success": True,
                        "metric_type": metric_type,
                        "cache_metrics": {
                            "status": "not_configured",
                            "message": "Cache manager not initialized"
                        }
                    }

            elif metric_type == "connections":
                # Connection pool metrics
                global _connection_pool

                if _connection_pool and hasattr(_connection_pool, '_connector'):
                    connector = _connection_pool._connector
                    return {
                        "success": True,
                        "metric_type": metric_type,
                        "connection_metrics": {
                            "total_connections": getattr(connector, '_total_connections', 0),
                            "available_connections": getattr(connector, '_available_connections', 0),
                            "acquired_connections": getattr(connector, '_acquired_connections', 0),
                            "limit": getattr(connector, '_limit', 0),
                            "limit_per_host": getattr(connector, '_limit_per_host', 0)
                        }
                    }
                else:
                    return {
                        "success": True,
                        "metric_type": metric_type,
                        "connection_metrics": {
                            "status": "not_configured",
                            "message": "Connection pool not initialized"
                        }
                    }

            elif metric_type == "memory":
                # Memory usage metrics
                import gc
                import sys

                gc_stats = gc.get_stats()

                return {
                    "success": True,
                    "metric_type": metric_type,
                    "memory_metrics": {
                        "gc_collections": [stat['collections'] for stat in gc_stats],
                        "gc_collected": [stat['collected'] for stat in gc_stats],
                        "gc_uncollectable": [stat['uncollectable'] for stat in gc_stats],
                        "total_objects": len(gc.get_objects())
                    }
                }

            else:
                raise ValueError(f"Unknown metric type: {metric_type}")

        except Exception as e:
            error_msg = f"Performance monitoring error: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "metric_type": metric_type
            }

    return mcp


def main() -> None:
    """Main entry point for the MCP server."""
    mcp = create_mcp_server()

    if __name__ == "__main__":
        mcp.run()


if __name__ == "__main__":
    main()
