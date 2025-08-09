import pytest
from unittest.mock import AsyncMock, patch

from web_fetch.components.manager import ResourceManager
from web_fetch.models.resource import ResourceKind, ResourceRequest


@pytest.mark.asyncio
async def test_http_component_adapter_maps_result(monkeypatch):
    # Arrange: mock WebFetcher.fetch_single to avoid real HTTP
    from web_fetch.models.http import FetchResult
    from web_fetch.models.base import ContentType

    async def fake_fetch_single(_req):
        return FetchResult(
            url=str(_req.url),
            status_code=200,
            headers={"x-test": "1"},
            content={"ok": True},
            content_type=ContentType.JSON,
        )

    # Patch the class used by the adapter
    import web_fetch.components.http_component as http_comp
    monkeypatch.setattr(http_comp.WebFetcher, "fetch_single", AsyncMock(side_effect=fake_fetch_single))

    manager = ResourceManager()
    req = ResourceRequest(
        uri="https://example.com/api",
        kind=ResourceKind.HTTP,
        options={"method": "GET", "content_type": "json"},
    )

    # Act
    res = await manager.fetch(req)

    # Assert
    assert res.is_success
    assert res.status_code == 200
    assert res.headers.get("x-test") == "1"
    assert isinstance(res.content, dict) and res.content["ok"] is True


@pytest.mark.asyncio
async def test_graphql_component_adapter_maps_result(monkeypatch):
    # Arrange: mock GraphQLClient.execute to avoid real calls
    from web_fetch.graphql.models import GraphQLResult

    async def fake_execute(_op):
        return GraphQLResult(success=True, data={"x": 1}, errors=[])

    # Patch the class used by the adapter
    import web_fetch.components.graphql_component as gql_comp
    monkeypatch.setattr(gql_comp.GraphQLClient, "execute", AsyncMock(side_effect=fake_execute))

    manager = ResourceManager()
    req = ResourceRequest(
        uri="https://example.com/graphql",
        kind=ResourceKind.GRAPHQL,
        options={"query": "query { x }"},
    )

    # Act
    res = await manager.fetch(req)

    # Assert
    assert res.is_success
    assert res.status_code == 200
    assert res.content == {"x": 1}
    assert res.content_type == "application/json"

