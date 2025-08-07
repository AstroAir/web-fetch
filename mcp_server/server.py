"""
WebFetch MCP Server Implementation

This module implements the main MCP server using FastMCP framework that exposes
WebFetch functionality as tools for LLM consumption.
"""

import asyncio
import logging
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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
                handler: ResumableDownloadHandler = ResumableDownloadHandler(config)
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

    return mcp


def main() -> None:
    """Main entry point for the MCP server."""
    mcp = create_mcp_server()

    if __name__ == "__main__":
        mcp.run()


if __name__ == "__main__":
    main()
