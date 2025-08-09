"""
CLI subcommands for the unified component system.

Provides a `components` subcommand that can invoke the unified ResourceManager
for any registered component type using a JSON options payload.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any, Dict

from ..components import ResourceManager
from ..models.resource import ResourceKind, ResourceRequest


def add_components_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "components",
        help="Unified components interface (HTTP/FTP/GraphQL/WebSocket/etc.)",
    )
    parser.add_argument("uri", help="Target resource URI")
    parser.add_argument(
        "--kind",
        required=True,
        choices=[k.value for k in ResourceKind],
        help="Resource kind",
    )
    parser.add_argument(
        "--options",
        help="JSON string of type-specific options (e.g., method, query, variables)",
        default="{}",
    )
    parser.add_argument("--headers", help="JSON of headers", default="{}")
    parser.add_argument("--params", help="JSON of params", default="{}")
    parser.add_argument("--timeout", type=float, help="Timeout override seconds")

    parser.set_defaults(func=run_components_command)


async def run_components_command(args: argparse.Namespace) -> int:
    manager = ResourceManager()
    req = ResourceRequest(
        uri=args.uri,
        kind=ResourceKind(args.kind),
        headers=json.loads(args.headers) if args.headers else None,
        params=json.loads(args.params) if args.params else None,
        options=json.loads(args.options) if args.options else {},
        timeout_seconds=args.timeout,
    )
    res = await manager.fetch(req)
    print(
        json.dumps(
            {
                "url": res.url,
                "status_code": res.status_code,
                "success": res.is_success,
                "content_type": res.content_type,
                "headers": res.headers,
                "metadata": res.metadata,
                "error": res.error,
            },
            indent=2,
            default=str,
        )
    )
    return 0 if res.is_success else 1

