import json
import argparse
import pytest
from unittest.mock import patch

from web_fetch.cli.components import add_components_subparser


def build_parser():
    parser = argparse.ArgumentParser()
    subs = parser.add_subparsers(dest="command")
    add_components_subparser(subs)
    return parser


@pytest.mark.asyncio
async def test_cli_components_invokes_resource_manager(monkeypatch):
    # Arrange: stub manager.fetch to return a simple ResourceResult-like object
    class FakeResult:
        def __init__(self):
            self.url = "https://example.com"
            self.status_code = 200
            self.headers = {"X": "Y"}
            self.content = {"ok": True}
            self.content_type = "application/json"
            self.metadata = {"note": "ok"}
            self.error = None

        @property
        def is_success(self):
            return True

    async def fake_fetch(self, req):
        return FakeResult()

    with patch("web_fetch.components.manager.ResourceManager.fetch", new=fake_fetch):
        parser = build_parser()
        args = parser.parse_args(
            [
                "components",
                "https://example.com",
                "--kind",
                "http",
                "--options",
                "{}",
            ]
        )

        # Act: call the async command directly
        from web_fetch.cli.components import run_components_command

        exit_code = await run_components_command(args)

        # Assert
        assert exit_code == 0

