"""
CLI subcommands for the unified component system with rich formatting.

Provides a `components` subcommand that can invoke the unified ResourceManager
for any registered component type using a JSON options payload with beautiful
rich formatting for output and status indicators.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any, Dict

from ..components import ResourceManager
from ..models.resource import ResourceKind, ResourceRequest
from .formatting import Formatter, create_formatter


def add_components_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "components",
        help="🔧 Unified components interface (HTTP/FTP/GraphQL/WebSocket/etc.)",
        description="Unified resource management interface with rich formatting",
    )
    parser.add_argument("uri", help="Target resource URI")
    parser.add_argument(
        "--kind",
        required=True,
        choices=[k.value for k in ResourceKind],
        help="Resource kind (http, ftp, graphql, websocket, etc.)",
    )
    parser.add_argument(
        "--options",
        help="JSON string of type-specific options (e.g., method, query, variables)",
        default="{}",
    )
    parser.add_argument("--headers", help="JSON of headers", default="{}")
    parser.add_argument("--params", help="JSON of params", default="{}")
    parser.add_argument("--timeout", type=float, help="Timeout override seconds")
    parser.add_argument(
        "--format",
        choices=["json", "summary", "detailed"],
        default="summary",
        help="Output format (default: summary)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )

    parser.set_defaults(func=run_components_command)


async def run_components_command(args: argparse.Namespace) -> int:
    """Run the components command with rich formatting."""
    # Create formatter
    formatter = create_formatter(verbose=getattr(args, 'verbose', False))

    try:
        # Parse JSON arguments
        try:
            headers = json.loads(args.headers) if args.headers else None
            params = json.loads(args.params) if args.params else None
            options = json.loads(args.options) if args.options else {}
        except json.JSONDecodeError as e:
            formatter.print_error(f"Invalid JSON in arguments: {e}")
            return 1

        # Create resource request
        req = ResourceRequest(
            uri=args.uri,
            kind=ResourceKind(args.kind),
            headers=headers,
            params=params,
            options=options,
            timeout_seconds=args.timeout,
        )

        # Display request info if verbose
        if getattr(args, 'verbose', False):
            request_info = {
                "URI": args.uri,
                "Kind": args.kind,
                "Timeout": f"{args.timeout}s" if args.timeout else "Default",
                "Headers": len(headers) if headers else 0,
                "Params": len(params) if params else 0,
                "Options": len(options) if options else 0
            }
            formatter.print_key_value_pairs(request_info, title="Request Configuration")

        # Execute request with status indicator
        with formatter.create_status(f"Fetching {args.kind} resource: {args.uri}"):
            manager = ResourceManager()
            res = await manager.fetch(req)

        # Format and display results
        result_data = {
            "url": res.url,
            "status_code": res.status_code,
            "success": res.is_success,
            "content_type": res.content_type,
            "headers": res.headers,
            "metadata": res.metadata,
            "error": res.error,
        }

        if args.format == "json":
            formatter.print_json(result_data, f"Resource Response ({args.kind})")
        elif args.format == "detailed":
            formatter.print_url_result(args.uri, result_data, "detailed")
        else:  # summary
            formatter.print_url_result(args.uri, result_data, "summary")

        # Show success/failure status
        if res.is_success:
            formatter.print_success(f"Successfully fetched {args.kind} resource")
        else:
            formatter.print_error(f"Failed to fetch {args.kind} resource: {res.error}")

        return 0 if res.is_success else 1

    except Exception as e:
        formatter.print_error(f"Component operation failed: {e}")
        if getattr(args, 'verbose', False):
            import traceback
            formatter.console.print_exception()
        return 1

