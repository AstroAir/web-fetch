"""
Enhanced HTTP methods support.

This module provides comprehensive support for all HTTP methods with
proper request/response handling and validation.
"""

import json
from contextlib import asynccontextmanager
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional, Union, Protocol
from urllib.parse import urlencode  # used by callers; keep imported

import aiohttp
from pydantic import BaseModel, Field

from ..exceptions import WebFetchError
from ..models import FetchRequest, FetchResult
from .session_manager import SessionManager, SessionConfig


class HTTPMethod(str, Enum):
    """Supported HTTP methods."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"
    PATCH = "PATCH"
    TRACE = "TRACE"
    CONNECT = "CONNECT"


class RequestBody(BaseModel):
    """Request body configuration."""

    data: Optional[Union[str, bytes, Dict[str, Any]]] = None
    json_data: Optional[Dict[str, Any]] = None
    form_data: Optional[Dict[str, Any]] = None
    files: Optional[Dict[str, Any]] = None
    content_type: Optional[str] = None
    encoding: str = "utf-8"


class _MethodHandlerProto(Protocol):
    async def __call__(
        self,
        session: aiohttp.ClientSession,
        url: str,
        headers: Optional[Dict[str, str]],
        body: Optional[RequestBody],
        params: Optional[Dict[str, Any]],
        **kwargs: Any,
    ) -> aiohttp.ClientResponse: ...

class HTTPMethodHandler:
    """Handler for different HTTP methods with enhanced session management."""

    def __init__(
        self,
        session_manager: Optional[SessionManager] = None,
        session_config: Optional[SessionConfig] = None
    ) -> None:
        """
        Initialize HTTP method handler.

        Args:
            session_manager: Optional session manager for reuse
            session_config: Optional session configuration
        """
        # 使用 Protocol 明确处理函数签名，避免变量类型别名在类型表达式中的限制
        self._method_handlers: Dict[HTTPMethod, _MethodHandlerProto] = {
            HTTPMethod.GET: self._handle_get,
            HTTPMethod.POST: self._handle_post,
            HTTPMethod.PUT: self._handle_put,
            HTTPMethod.DELETE: self._handle_delete,
            HTTPMethod.HEAD: self._handle_head,
            HTTPMethod.OPTIONS: self._handle_options,
            HTTPMethod.PATCH: self._handle_patch,
            HTTPMethod.TRACE: self._handle_trace,
        }

        self._session_manager = session_manager
        self._session_config = session_config
        self._owned_manager = session_manager is None

    async def _get_session_manager(self) -> SessionManager:
        """Get or create session manager."""
        if self._session_manager is None:
            self._session_manager = SessionManager(self._session_config)
        return self._session_manager

    @asynccontextmanager
    async def managed_request(
        self,
        method: HTTPMethod,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[RequestBody] = None,
        params: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[aiohttp.ClientResponse, None]:
        """
        Execute HTTP request with managed session lifecycle.

        Args:
            method: HTTP method
            url: Request URL
            headers: Request headers
            body: Request body
            params: URL parameters
            **kwargs: Additional arguments

        Yields:
            HTTP response

        Raises:
            WebFetchError: If method is not supported
        """
        if method not in self._method_handlers:
            raise WebFetchError(f"Unsupported HTTP method: {method}")

        session_manager = await self._get_session_manager()
        async with session_manager.get_session() as session:
            handler = self._method_handlers[method]
            response = await handler(session, url, headers, body, params, **kwargs)
            async with response:
                yield response

    async def execute_request(
        self,
        session: Optional[aiohttp.ClientSession],
        method: HTTPMethod,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[RequestBody] = None,
        params: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> aiohttp.ClientResponse:
        """
        Execute HTTP request with specified method.

        Args:
            session: Optional aiohttp session (will create managed one if None)
            method: HTTP method
            url: Request URL
            headers: Request headers
            body: Request body
            params: URL parameters
            **kwargs: Additional arguments

        Returns:
            HTTP response

        Raises:
            WebFetchError: If method is not supported
        """
        if method not in self._method_handlers:
            raise WebFetchError(f"Unsupported HTTP method: {method}")

        # Use managed session if none provided
        if session is None:
            session_manager = await self._get_session_manager()
            async with session_manager.get_session() as managed_session:
                handler = self._method_handlers[method]
                return await handler(managed_session, url, headers, body, params, **kwargs)
        else:
            handler = self._method_handlers[method]
            # 通过 Protocol 已经将返回类型限定为 aiohttp.ClientResponse
            return await handler(session, url, headers, body, params, **kwargs)

    async def close(self) -> None:
        """Close session manager if owned by this handler."""
        if self._owned_manager and self._session_manager:
            await self._session_manager.close()
            self._session_manager = None

    async def __aenter__(self) -> 'HTTPMethodHandler':
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    async def _handle_get(
        self,
        session: aiohttp.ClientSession,
        url: str,
        headers: Optional[Dict[str, str]],
        body: Optional[RequestBody],
        params: Optional[Dict[str, Any]],
        **kwargs: Any,
    ) -> aiohttp.ClientResponse:
        """Handle GET request."""
        return await session.get(url, headers=headers, params=params, **kwargs)

    async def _handle_post(
        self,
        session: aiohttp.ClientSession,
        url: str,
        headers: Optional[Dict[str, str]],
        body: Optional[RequestBody],
        params: Optional[Dict[str, Any]],
        **kwargs: Any,
    ) -> aiohttp.ClientResponse:
        """Handle POST request."""
        request_kwargs: Dict[str, Any] = self._prepare_request_body(body, headers)
        request_kwargs.update(kwargs)

        return await session.post(url, headers=headers, params=params, **request_kwargs)

    async def _handle_put(
        self,
        session: aiohttp.ClientSession,
        url: str,
        headers: Optional[Dict[str, str]],
        body: Optional[RequestBody],
        params: Optional[Dict[str, Any]],
        **kwargs: Any,
    ) -> aiohttp.ClientResponse:
        """Handle PUT request."""
        request_kwargs: Dict[str, Any] = self._prepare_request_body(body, headers)
        request_kwargs.update(kwargs)

        return await session.put(url, headers=headers, params=params, **request_kwargs)

    async def _handle_delete(
        self,
        session: aiohttp.ClientSession,
        url: str,
        headers: Optional[Dict[str, str]],
        body: Optional[RequestBody],
        params: Optional[Dict[str, Any]],
        **kwargs: Any,
    ) -> aiohttp.ClientResponse:
        """Handle DELETE request."""
        request_kwargs: Dict[str, Any] = {}
        if body:
            request_kwargs = self._prepare_request_body(body, headers)
        request_kwargs.update(kwargs)

        return await session.delete(
            url, headers=headers, params=params, **request_kwargs
        )

    async def _handle_head(
        self,
        session: aiohttp.ClientSession,
        url: str,
        headers: Optional[Dict[str, str]],
        body: Optional[RequestBody],
        params: Optional[Dict[str, Any]],
        **kwargs: Any,
    ) -> aiohttp.ClientResponse:
        """Handle HEAD request."""
        return await session.head(url, headers=headers, params=params, **kwargs)

    async def _handle_options(
        self,
        session: aiohttp.ClientSession,
        url: str,
        headers: Optional[Dict[str, str]],
        body: Optional[RequestBody],
        params: Optional[Dict[str, Any]],
        **kwargs: Any,
    ) -> aiohttp.ClientResponse:
        """Handle OPTIONS request."""
        return await session.options(url, headers=headers, params=params, **kwargs)

    async def _handle_patch(
        self,
        session: aiohttp.ClientSession,
        url: str,
        headers: Optional[Dict[str, str]],
        body: Optional[RequestBody],
        params: Optional[Dict[str, Any]],
        **kwargs: Any,
    ) -> aiohttp.ClientResponse:
        """Handle PATCH request."""
        request_kwargs: Dict[str, Any] = self._prepare_request_body(body, headers)
        request_kwargs.update(kwargs)

        return await session.patch(
            url, headers=headers, params=params, **request_kwargs
        )

    async def _handle_trace(
        self,
        session: aiohttp.ClientSession,
        url: str,
        headers: Optional[Dict[str, str]],
        body: Optional[RequestBody],
        params: Optional[Dict[str, Any]],
        **kwargs: Any,
    ) -> aiohttp.ClientResponse:
        """Handle TRACE request."""
        # aiohttp doesn't expose session.trace; use generic request
        request_kwargs: Dict[str, Any] = {}
        if body:
            request_kwargs = self._prepare_request_body(body, headers)
        request_kwargs.update(kwargs)
        return await session.request(
            "TRACE", url, headers=headers, params=params, **request_kwargs
        )

    def _prepare_request_body(
        self, body: Optional[RequestBody], headers: Optional[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Prepare request body for HTTP methods that support it.

        Args:
            body: Request body configuration
            headers: Request headers

        Returns:
            Dictionary with request body parameters
        """
        if not body:
            return {}

        request_kwargs: Dict[str, Any] = {}

        # Handle JSON data
        if body.json_data is not None:
            request_kwargs["json"] = body.json_data
            if headers and "content-type" not in (k.lower() for k in headers.keys()):
                headers["Content-Type"] = "application/json"

        # Handle form data
        elif body.form_data is not None:
            if body.files:
                # Multipart form data with files
                form_data = aiohttp.FormData()

                # Add form fields
                for key, value in body.form_data.items():
                    form_data.add_field(key, str(value))

                # Add files
                for key, file_info in body.files.items():
                    if isinstance(file_info, dict):
                        form_data.add_field(
                            key,
                            file_info["content"],
                            filename=file_info.get("filename"),
                            content_type=file_info.get("content_type"),
                        )
                    else:
                        form_data.add_field(key, file_info)

                request_kwargs["data"] = form_data  # FormData acceptable for aiohttp
            else:
                # URL-encoded form data
                request_kwargs["data"] = body.form_data
                if headers and "content-type" not in (
                    k.lower() for k in headers.keys()
                ):
                    headers["Content-Type"] = "application/x-www-form-urlencoded"

        # Handle raw data
        elif body.data is not None:
            if isinstance(body.data, dict):
                # Convert dict to JSON bytes
                request_kwargs["data"] = json.dumps(body.data).encode(body.encoding)
                if headers and "content-type" not in (
                    k.lower() for k in headers.keys()
                ):
                    headers["Content-Type"] = "application/json"
            elif isinstance(body.data, str):
                request_kwargs["data"] = body.data.encode(body.encoding)
            else:
                # bytes or other supported payloads
                request_kwargs["data"] = body.data

            # Set content type if specified
            if body.content_type and headers:
                headers["Content-Type"] = body.content_type

        return request_kwargs

    def get_supported_methods(self) -> List[HTTPMethod]:
        """
        Get list of supported HTTP methods.

        Returns:
            List of supported HTTP methods
        """
        return list(self._method_handlers.keys())

    def is_method_supported(self, method: HTTPMethod) -> bool:
        """
        Check if HTTP method is supported.

        Args:
            method: HTTP method to check

        Returns:
            True if method is supported
        """
        return method in self._method_handlers
