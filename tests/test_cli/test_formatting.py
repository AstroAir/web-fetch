"""
Comprehensive tests for the CLI formatting module.
"""

import pytest
import json
from datetime import datetime
from unittest.mock import patch, MagicMock

from web_fetch.cli.formatting import (
    format_output,
    format_json_output,
    format_table_output,
    format_text_output,
    format_xml_output,
    format_csv_output,
    format_batch_results,
    format_metrics,
    format_error,
    colorize_status_code,
    truncate_text,
    format_file_size,
    format_duration,
)
from web_fetch.models.http import FetchResult, BatchFetchResult
from web_fetch.models.base import ContentType
from web_fetch.batch.models import BatchResult, BatchStatus


class TestOutputFormatting:
    """Test output formatting functions."""

    def test_format_json_output(self):
        """Test JSON output formatting."""
        data = {"message": "success", "status": 200}
        result = format_json_output(data)
        
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["message"] == "success"
        assert parsed["status"] == 200

    def test_format_json_output_with_indent(self):
        """Test JSON output formatting with indentation."""
        data = {"nested": {"key": "value"}}
        result = format_json_output(data, indent=2)
        
        assert isinstance(result, str)
        assert "  " in result  # Should have indentation
        parsed = json.loads(result)
        assert parsed["nested"]["key"] == "value"

    def test_format_text_output_simple(self):
        """Test simple text output formatting."""
        text = "Hello, World!"
        result = format_text_output(text)
        
        assert result == "Hello, World!"

    def test_format_text_output_with_metadata(self):
        """Test text output formatting with metadata."""
        text = "Response content"
        metadata = {
            "status_code": 200,
            "content_type": "text/plain",
            "content_length": 16
        }
        
        result = format_text_output(text, metadata=metadata)
        
        assert "Response content" in result
        assert "200" in result
        assert "text/plain" in result

    def test_format_table_output(self):
        """Test table output formatting."""
        headers = ["URL", "Status", "Size"]
        rows = [
            ["https://example.com/1", "200", "1024"],
            ["https://example.com/2", "404", "512"],
            ["https://example.com/3", "200", "2048"]
        ]
        
        result = format_table_output(headers, rows)
        
        assert isinstance(result, str)
        assert "URL" in result
        assert "Status" in result
        assert "Size" in result
        assert "https://example.com/1" in result
        assert "200" in result

    def test_format_table_output_empty(self):
        """Test table output formatting with empty data."""
        headers = ["URL", "Status"]
        rows = []
        
        result = format_table_output(headers, rows)
        
        assert isinstance(result, str)
        assert "URL" in result
        assert "Status" in result

    def test_format_xml_output(self):
        """Test XML output formatting."""
        data = {
            "response": {
                "status": 200,
                "message": "success",
                "data": ["item1", "item2"]
            }
        }
        
        result = format_xml_output(data)
        
        assert isinstance(result, str)
        assert "<response>" in result
        assert "<status>200</status>" in result
        assert "<message>success</message>" in result

    def test_format_csv_output(self):
        """Test CSV output formatting."""
        headers = ["URL", "Status", "Size"]
        rows = [
            ["https://example.com/1", "200", "1024"],
            ["https://example.com/2", "404", "512"]
        ]
        
        result = format_csv_output(headers, rows)
        
        assert isinstance(result, str)
        lines = result.strip().split('\n')
        assert len(lines) == 3  # Header + 2 data rows
        assert "URL,Status,Size" in lines[0]
        assert "https://example.com/1,200,1024" in lines[1]

    def test_format_csv_output_with_quotes(self):
        """Test CSV output formatting with quoted fields."""
        headers = ["URL", "Content"]
        rows = [
            ["https://example.com", "Hello, World!"],
            ["https://test.com", "Data with \"quotes\""]
        ]
        
        result = format_csv_output(headers, rows)
        
        assert isinstance(result, str)
        assert '"Hello, World!"' in result
        assert '"""quotes"""' in result  # Escaped quotes


class TestBatchResultFormatting:
    """Test batch result formatting."""

    def test_format_batch_results_summary(self):
        """Test formatting batch results summary."""
        results = [
            FetchResult(
                url="https://example.com/1",
                status_code=200,
                headers={"content-length": "1024"},
                content="content1",
                content_type=ContentType.TEXT
            ),
            FetchResult(
                url="https://example.com/2",
                status_code=404,
                headers={},
                content="",
                content_type=ContentType.TEXT,
                error="Not found"
            )
        ]
        
        batch_result = BatchResult(
            batch_id="test-batch",
            results=results,
            status=BatchStatus.COMPLETED
        )
        
        formatted = format_batch_results(batch_result, format_type="summary")
        
        assert isinstance(formatted, str)
        assert "test-batch" in formatted
        assert "2" in formatted  # Total results
        assert "1" in formatted  # Success count
        assert "1" in formatted  # Failure count

    def test_format_batch_results_detailed(self):
        """Test formatting detailed batch results."""
        results = [
            FetchResult(
                url="https://example.com/1",
                status_code=200,
                headers={"content-type": "text/plain"},
                content="success",
                content_type=ContentType.TEXT
            )
        ]
        
        batch_result = BatchResult(
            batch_id="test-batch",
            results=results,
            status=BatchStatus.COMPLETED
        )
        
        formatted = format_batch_results(batch_result, format_type="detailed")
        
        assert isinstance(formatted, str)
        assert "https://example.com/1" in formatted
        assert "200" in formatted
        assert "success" in formatted

    def test_format_batch_results_json(self):
        """Test formatting batch results as JSON."""
        results = [
            FetchResult(
                url="https://example.com/1",
                status_code=200,
                headers={},
                content="content",
                content_type=ContentType.TEXT
            )
        ]
        
        batch_result = BatchResult(
            batch_id="test-batch",
            results=results,
            status=BatchStatus.COMPLETED
        )
        
        formatted = format_batch_results(batch_result, format_type="json")
        
        assert isinstance(formatted, str)
        parsed = json.loads(formatted)
        assert parsed["batch_id"] == "test-batch"
        assert parsed["status"] == "completed"
        assert len(parsed["results"]) == 1


class TestMetricsFormatting:
    """Test metrics formatting."""

    def test_format_metrics_basic(self):
        """Test basic metrics formatting."""
        metrics = {
            "requests_per_second": 10.5,
            "average_response_time": 1.234,
            "success_rate": 0.95,
            "total_requests": 100
        }
        
        formatted = format_metrics(metrics)
        
        assert isinstance(formatted, str)
        assert "10.5" in formatted
        assert "1.234" in formatted
        assert "95%" in formatted or "0.95" in formatted
        assert "100" in formatted

    def test_format_metrics_with_timestamp(self):
        """Test metrics formatting with timestamp."""
        metrics = {
            "requests_per_second": 5.0,
            "timestamp": datetime.now().isoformat()
        }
        
        formatted = format_metrics(metrics, include_timestamp=True)
        
        assert isinstance(formatted, str)
        assert "5.0" in formatted
        assert "timestamp" in formatted.lower() or "time" in formatted.lower()

    def test_format_metrics_table_format(self):
        """Test metrics formatting in table format."""
        metrics = {
            "requests_per_second": 8.2,
            "average_response_time": 0.856,
            "error_rate": 0.05
        }
        
        formatted = format_metrics(metrics, format_type="table")
        
        assert isinstance(formatted, str)
        assert "8.2" in formatted
        assert "0.856" in formatted


class TestErrorFormatting:
    """Test error formatting."""

    def test_format_error_simple(self):
        """Test simple error formatting."""
        error = Exception("Something went wrong")
        formatted = format_error(error)
        
        assert isinstance(formatted, str)
        assert "Something went wrong" in formatted
        assert "Error" in formatted

    def test_format_error_with_details(self):
        """Test error formatting with details."""
        error = Exception("Network error")
        formatted = format_error(error, include_traceback=True)
        
        assert isinstance(formatted, str)
        assert "Network error" in formatted

    def test_format_error_with_context(self):
        """Test error formatting with context."""
        error = Exception("Request failed")
        context = {
            "url": "https://example.com",
            "status_code": 500,
            "attempt": 3
        }
        
        formatted = format_error(error, context=context)
        
        assert isinstance(formatted, str)
        assert "Request failed" in formatted
        assert "https://example.com" in formatted
        assert "500" in formatted


class TestUtilityFormatting:
    """Test utility formatting functions."""

    def test_colorize_status_code_success(self):
        """Test colorizing successful status codes."""
        result = colorize_status_code(200)
        assert isinstance(result, str)
        assert "200" in result

    def test_colorize_status_code_client_error(self):
        """Test colorizing client error status codes."""
        result = colorize_status_code(404)
        assert isinstance(result, str)
        assert "404" in result

    def test_colorize_status_code_server_error(self):
        """Test colorizing server error status codes."""
        result = colorize_status_code(500)
        assert isinstance(result, str)
        assert "500" in result

    def test_truncate_text_short(self):
        """Test truncating short text."""
        text = "Short text"
        result = truncate_text(text, max_length=50)
        assert result == "Short text"

    def test_truncate_text_long(self):
        """Test truncating long text."""
        text = "This is a very long text that should be truncated"
        result = truncate_text(text, max_length=20)
        assert len(result) <= 23  # 20 + "..."
        assert result.endswith("...")

    def test_truncate_text_exact_length(self):
        """Test truncating text at exact length."""
        text = "Exactly twenty chars"
        result = truncate_text(text, max_length=20)
        assert result == text

    def test_format_file_size_bytes(self):
        """Test formatting file size in bytes."""
        result = format_file_size(512)
        assert "512" in result
        assert "B" in result

    def test_format_file_size_kilobytes(self):
        """Test formatting file size in kilobytes."""
        result = format_file_size(1536)  # 1.5 KB
        assert "1.5" in result
        assert "KB" in result

    def test_format_file_size_megabytes(self):
        """Test formatting file size in megabytes."""
        result = format_file_size(2097152)  # 2 MB
        assert "2.0" in result
        assert "MB" in result

    def test_format_file_size_gigabytes(self):
        """Test formatting file size in gigabytes."""
        result = format_file_size(3221225472)  # 3 GB
        assert "3.0" in result
        assert "GB" in result

    def test_format_duration_seconds(self):
        """Test formatting duration in seconds."""
        result = format_duration(45.5)
        assert "45.5" in result
        assert "s" in result

    def test_format_duration_minutes(self):
        """Test formatting duration in minutes."""
        result = format_duration(125.0)  # 2 minutes 5 seconds
        assert "2m" in result
        assert "5s" in result

    def test_format_duration_hours(self):
        """Test formatting duration in hours."""
        result = format_duration(7325.0)  # 2 hours 2 minutes 5 seconds
        assert "2h" in result
        assert "2m" in result
        assert "5s" in result

    def test_format_duration_zero(self):
        """Test formatting zero duration."""
        result = format_duration(0.0)
        assert "0" in result
        assert "s" in result


class TestFormatOutput:
    """Test main format_output function."""

    def test_format_output_auto_json(self):
        """Test auto-detecting JSON format."""
        data = {"key": "value"}
        result = format_output(data, format_type="auto")
        
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["key"] == "value"

    def test_format_output_auto_text(self):
        """Test auto-detecting text format."""
        data = "Plain text content"
        result = format_output(data, format_type="auto")
        
        assert result == "Plain text content"

    def test_format_output_forced_json(self):
        """Test forcing JSON format."""
        data = "Text content"
        result = format_output(data, format_type="json")
        
        assert isinstance(result, str)
        # Should be valid JSON even for text input
        parsed = json.loads(result)
        assert isinstance(parsed, str)

    def test_format_output_with_metadata(self):
        """Test format output with metadata."""
        data = "Content"
        metadata = {"status": 200, "type": "text/plain"}
        
        result = format_output(data, format_type="text", metadata=metadata)
        
        assert isinstance(result, str)
        assert "Content" in result

    def test_format_output_invalid_format(self):
        """Test format output with invalid format type."""
        data = "Content"
        
        with pytest.raises(ValueError):
            format_output(data, format_type="invalid_format")

    def test_format_output_fetch_result(self):
        """Test formatting FetchResult object."""
        fetch_result = FetchResult(
            url="https://example.com",
            status_code=200,
            headers={"content-type": "text/plain"},
            content="Hello, World!",
            content_type=ContentType.TEXT
        )
        
        result = format_output(fetch_result, format_type="json")
        
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["url"] == "https://example.com"
        assert parsed["status_code"] == 200
        assert parsed["content"] == "Hello, World!"
