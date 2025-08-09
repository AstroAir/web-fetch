"""
FTP resource component adapter bridging existing FTPFetcher to the unified API.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Optional

from ..ftp.fetcher import FTPFetcher
from ..ftp.models import FTPRequest
from ..models.resource import ResourceConfig, ResourceKind, ResourceRequest, ResourceResult
from .base import ResourceComponent, component_registry


class FTPResourceComponent(ResourceComponent):
    kind = ResourceKind.FTP

    def __init__(self, config: Optional[ResourceConfig] = None):
        super().__init__(config)

    async def fetch(self, request: ResourceRequest) -> ResourceResult:
        # Expect operation in options: "download" | "list" | "info"
        operation = str(request.options.get("operation", "info"))

        # For download: require local_path in options
        ftp_req = FTPRequest(
            url=str(request.uri),
            operation=operation,
            local_path=request.options.get("local_path"),
        )

        async with FTPFetcher() as ftp:
            ftp_result = await ftp.fetch_single(ftp_req)

        # Map FTPResult -> ResourceResult
        metadata: Dict[str, Any] = {}
        if getattr(ftp_result, "file_info", None) is not None and ftp_result.file_info is not None:
            metadata["file_info"] = asdict(ftp_result.file_info)
        if getattr(ftp_result, "files_list", None):
            metadata["files_list"] = [asdict(fi) for fi in (ftp_result.files_list or [])]

        return ResourceResult(
            url=str(request.uri),
            status_code=ftp_result.status_code,
            headers={},
            content=None,
            content_type=None,
            metadata=metadata,
            response_time=getattr(ftp_result, "response_time", 0.0),
            error=ftp_result.error,
        )


# Register component in the global registry
component_registry.register(ResourceKind.FTP, lambda config=None: FTPResourceComponent(config))

__all__ = ["FTPResourceComponent"]

