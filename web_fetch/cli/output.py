"""
Output formatting functions for CLI operations.

This module contains output formatting logic extracted from main.py to improve
modularity and maintainability. Functions handle different output formats
and result presentation.
"""

from typing import Any


def format_output(results: Any, format_type: str, verbose: bool = False) -> str:
    """Format results for output."""
    if format_type == "json":
        import json
        # Convert results to JSON-serializable format
        if hasattr(results, "results"):  # BatchFetchResult
            output = {
                "total_requests": results.total_requests,
                "successful_requests": results.successful_requests,
                "failed_requests": results.failed_requests,
                "success_rate": results.success_rate,
                "total_time": results.total_time,
                "results": [],
            }
            
            for result in results.results:
                result_dict = {
                    "url": result.url,
                    "status_code": result.status_code,
                    "success": result.is_success,
                    "content_type": result.content_type,
                    "headers": dict(result.headers) if result.headers else {},
                    "metadata": result.metadata,
                    "error": result.error,
                }
                if verbose or result.is_success:
                    result_dict["content"] = result.content
                output["results"].append(result_dict)
            
            return json.dumps(output, indent=2, default=str)
        else:
            # Single result
            result_dict = {
                "url": results.url,
                "status_code": results.status_code,
                "success": results.is_success,
                "content_type": results.content_type,
                "headers": dict(results.headers) if results.headers else {},
                "metadata": results.metadata,
                "error": results.error,
            }
            if verbose or results.is_success:
                result_dict["content"] = results.content
            return json.dumps(result_dict, indent=2, default=str)

    elif format_type == "summary":
        if hasattr(results, "results"):  # BatchFetchResult
            output_lines = []
            output_lines.append(f"Batch Results Summary:")
            output_lines.append(f"  Total requests: {results.total_requests}")
            output_lines.append(f"  Successful: {results.successful_requests}")
            output_lines.append(f"  Failed: {results.failed_requests}")
            output_lines.append(f"  Success rate: {results.success_rate:.1f}%")
            output_lines.append(f"  Total time: {results.total_time:.2f}s")
            output_lines.append("")
            
            if verbose:
                output_lines.append("Individual Results:")
                for i, result in enumerate(results.results, 1):
                    status = "✓" if result.is_success else "✗"
                    output_lines.append(f"  {i}. {status} {result.url}")
                    if result.status_code:
                        output_lines.append(f"     Status: {result.status_code}")
                    if result.content_type:
                        output_lines.append(f"     Type: {result.content_type}")
                    if result.error:
                        output_lines.append(f"     Error: {result.error}")
                    output_lines.append("")
            
            return "\n".join(output_lines)
        else:
            # Single result
            status = "✓" if results.is_success else "✗"
            output_lines = [
                f"Result: {status} {results.url}",
                f"Status Code: {results.status_code}",
                f"Content Type: {results.content_type}",
            ]
            if results.error:
                output_lines.append(f"Error: {results.error}")
            if verbose and results.metadata:
                output_lines.append(f"Metadata: {results.metadata}")
            return "\n".join(output_lines)

    elif format_type == "detailed":
        # Similar to summary but with more details
        return (
            format_output(results, "summary", verbose)
            + "\n\nContent preview:\n"
            + str(results.content)[:500]
            + "..."
        )

    else:
        # Default to summary format
        return format_output(results, "summary", verbose)
