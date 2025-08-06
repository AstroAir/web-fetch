"""
WebFetch MCP Server Implementation

This module implements the main MCP server using FastMCP framework that exposes
WebFetch functionality as tools for LLM consumption.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Union, Any, Literal
from urllib.parse import urlparse

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
    detect_content_type
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
        - validate_url: Validate and analyze URL structure
        - analyze_headers: Analyze HTTP response headers
        - detect_content_type: Detect content type from URL or headers

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

    return mcp


def main() -> None:
    """Main entry point for the MCP server."""
    mcp = create_mcp_server()

    if __name__ == "__main__":
        mcp.run()


if __name__ == "__main__":
    main()
