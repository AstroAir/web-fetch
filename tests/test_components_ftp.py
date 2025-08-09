import pytest
from unittest.mock import AsyncMock

from web_fetch.components.manager import ResourceManager
from web_fetch.models.resource import ResourceKind, ResourceRequest


@pytest.mark.asyncio
async def test_ftp_component_adapter_list(monkeypatch):
    # Arrange: mock FTPFetcher.fetch_single
    from web_fetch.ftp.models import FTPResult, FTPFileInfo
    import web_fetch.components.ftp_component as ftp_comp

    async def fake_fetch_single(_req):
        from datetime import datetime
        return FTPResult(
            url=_req.url,
            operation=_req.operation,
            status_code=200,
            local_path=None,
            bytes_transferred=0,
            total_bytes=None,
            response_time=0.01,
            timestamp=datetime.utcnow(),
            error=None,
            file_info=None,
            files_list=[FTPFileInfo(name="a.txt", path="/", size=10, modified_time=None, is_directory=False)],
        )

    monkeypatch.setattr(ftp_comp.FTPFetcher, "fetch_single", AsyncMock(side_effect=fake_fetch_single))

    manager = ResourceManager()
    req = ResourceRequest(
        uri="ftp://example.com/pub/",
        kind=ResourceKind.FTP,
        options={"operation": "list"},
    )

    # Act
    res = await manager.fetch(req)

    # Assert
    assert res.is_success
    assert res.metadata.get("files_list")

