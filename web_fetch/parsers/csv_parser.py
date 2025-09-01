"""
CSV parsing and structured data handling.

This module provides functionality to parse CSV data into structured formats
with automatic delimiter detection, encoding handling, and data type inference.
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import chardet

try:
    import pandas as pd

    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

from ..exceptions import ContentError
from ..models.base import CSVMetadata

logger = logging.getLogger(__name__)


class CSVParser:
    """Parser for CSV data with automatic detection and structured output."""

    def __init__(self, use_pandas: bool = True):
        """
        Initialize CSV parser.

        Args:
            use_pandas: Whether to use pandas for parsing (provides better type inference)
        """
        self.use_pandas = use_pandas and HAS_PANDAS
        if use_pandas and not HAS_PANDAS:
            logger.warning("pandas not available, falling back to built-in csv module")

    def parse(
        self, content: bytes, url: Optional[str] = None
    ) -> Tuple[Dict[str, Any], CSVMetadata]:
        """
        Parse CSV content and extract structured data and metadata.

        Args:
            content: CSV content as bytes
            url: Optional URL for context in error messages

        Returns:
            Tuple of (structured_data_dict, csv_metadata)

        Raises:
            ContentError: If CSV parsing fails
        """
        try:
            # Detect encoding
            encoding = self._detect_encoding(content)

            # Decode content
            text_content = content.decode(encoding, errors="replace")

            # Detect CSV dialect (delimiter, quote char, etc.)
            dialect = self._detect_dialect(text_content)

            # Parse CSV data
            if self.use_pandas:
                data, metadata = self._parse_with_pandas(
                    text_content, dialect, encoding
                )
            else:
                data, metadata = self._parse_with_csv(text_content, dialect, encoding)

            metadata.file_size = len(content)

            return data, metadata

        except Exception as e:
            logger.error(f"Failed to parse CSV from {url}: {e}")
            raise ContentError(f"CSV parsing error: {e}")

    def _detect_encoding(self, content: bytes) -> str:
        """Detect the encoding of CSV content."""
        try:
            # Use chardet to detect encoding
            result = chardet.detect(content)
            encoding = result.get("encoding", "utf-8")
            confidence = result.get("confidence", 0)

            # If confidence is low, try common encodings
            if confidence < 0.7:
                for enc in ["utf-8", "latin1", "cp1252", "iso-8859-1"]:
                    try:
                        content.decode(enc)
                        return enc
                    except UnicodeDecodeError:
                        continue

            return encoding or "utf-8"

        except Exception:
            return "utf-8"

    def _detect_dialect(self, text_content: str) -> csv.Dialect:
        """Detect CSV dialect (delimiter, quote character, etc.)."""
        try:
            # Use csv.Sniffer to detect dialect
            sniffer = csv.Sniffer()

            # Sample first few lines for detection
            sample = "\n".join(text_content.split("\n")[:10])

            dialect = sniffer.sniff(sample, delimiters=",;\t|")

            # Verify the dialect makes sense
            if not hasattr(dialect, "delimiter") or dialect.delimiter not in ",;\t|":
                # Fallback to comma
                dialect.delimiter = ","

            return dialect  # type: ignore

        except Exception:
            # Create a default dialect
            class DefaultDialect(csv.excel):
                delimiter = ","
                quotechar = '"'
                doublequote = True
                skipinitialspace = False
                lineterminator = "\n"
                quoting = csv.QUOTE_MINIMAL

            return DefaultDialect()

    def _parse_with_pandas(
        self, text_content: str, dialect: csv.Dialect, encoding: str
    ) -> Tuple[Dict[str, Any], CSVMetadata]:
        """Parse CSV using pandas for better type inference."""
        try:
            # Create StringIO object
            csv_io = io.StringIO(text_content)

            # Read CSV with pandas
            df = pd.read_csv(
                csv_io,
                delimiter=dialect.delimiter,
                quotechar=dialect.quotechar,
                encoding=encoding,
                low_memory=False,
                na_values=["", "NULL", "null", "None", "N/A", "n/a"],
                keep_default_na=True,
            )

            # Create metadata
            metadata = CSVMetadata()
            metadata.delimiter = dialect.delimiter
            metadata.quotechar = dialect.quotechar or '"'
            metadata.encoding = encoding
            metadata.has_header = True  # pandas assumes header by default
            metadata.row_count = len(df)
            metadata.column_count = len(df.columns)
            metadata.column_names = df.columns.tolist()

            # Infer column types
            metadata.column_types = {}
            for col in df.columns:
                dtype = str(df[col].dtype)
                if dtype.startswith("int"):
                    metadata.column_types[col] = "integer"
                elif dtype.startswith("float"):
                    metadata.column_types[col] = "float"
                elif dtype.startswith("bool"):
                    metadata.column_types[col] = "boolean"
                elif dtype.startswith("datetime"):
                    metadata.column_types[col] = "datetime"
                else:
                    metadata.column_types[col] = "string"

            # Count null values
            metadata.null_values = df.isnull().sum().to_dict()

            # Convert to structured data
            structured_data = {
                "columns": metadata.column_names,
                "data": df.to_dict("records"),
                "summary": {
                    "total_rows": metadata.row_count,
                    "total_columns": metadata.column_count,
                    "column_types": metadata.column_types,
                    "null_counts": metadata.null_values,
                    "memory_usage": df.memory_usage(deep=True).sum(),
                },
                "sample_data": df.head(5).to_dict("records") if len(df) > 0 else [],
            }

            return structured_data, metadata

        except Exception as e:
            logger.error(f"Pandas CSV parsing failed: {e}")
            # Fallback to built-in csv module
            return self._parse_with_csv(text_content, dialect, encoding)

    def _parse_with_csv(
        self, text_content: str, dialect: csv.Dialect, encoding: str
    ) -> Tuple[Dict[str, Any], CSVMetadata]:
        """Parse CSV using built-in csv module."""
        csv_io = io.StringIO(text_content)
        reader = csv.reader(csv_io, dialect=dialect)

        rows = list(reader)

        if not rows:
            raise ContentError("CSV file is empty")

        # Determine if first row is header
        has_header = self._detect_header(rows)

        # Extract headers and data
        if has_header:
            headers = rows[0]
            data_rows = rows[1:]
        else:
            headers = [f"Column_{i+1}" for i in range(len(rows[0]))]
            data_rows = rows

        # Create metadata
        metadata = CSVMetadata()
        metadata.delimiter = dialect.delimiter
        metadata.quotechar = dialect.quotechar or '"'
        metadata.encoding = encoding
        metadata.has_header = has_header
        metadata.row_count = len(data_rows)
        metadata.column_count = len(headers)
        metadata.column_names = headers

        # Basic type inference
        metadata.column_types = self._infer_column_types(data_rows, headers)

        # Count null/empty values
        metadata.null_values = {}
        for i, col in enumerate(headers):
            null_count = sum(
                1 for row in data_rows if i >= len(row) or not row[i].strip()
            )
            metadata.null_values[col] = null_count

        # Convert to structured data
        structured_data = {
            "columns": headers,
            "data": [dict(zip(headers, row)) for row in data_rows],
            "summary": {
                "total_rows": metadata.row_count,
                "total_columns": metadata.column_count,
                "column_types": metadata.column_types,
                "null_counts": metadata.null_values,
            },
            "sample_data": [dict(zip(headers, row)) for row in data_rows[:5]],
        }

        return structured_data, metadata

    def _detect_header(self, rows: List[List[str]]) -> bool:
        """Detect if the first row contains headers."""
        if len(rows) < 2:
            return True  # Assume header if only one row

        first_row = rows[0]
        second_row = rows[1]

        # Check if first row has different characteristics than second row
        # Headers are usually strings, data might be numbers
        header_score = 0

        for i, (first_val, second_val) in enumerate(zip(first_row, second_row)):
            # Check if first value is non-numeric and second is numeric
            try:
                float(second_val)
                if not self._is_numeric(first_val):
                    header_score += 1
            except ValueError:
                pass

            # Check for common header patterns
            if any(
                word in first_val.lower()
                for word in ["id", "name", "date", "time", "count", "value"]
            ):
                header_score += 1

        return header_score > len(first_row) * 0.3

    def _is_numeric(self, value: str) -> bool:
        """Check if a string value is numeric."""
        try:
            float(value)
            return True
        except ValueError:
            return False

    def _infer_column_types(
        self, data_rows: List[List[str]], headers: List[str]
    ) -> Dict[str, str]:
        """Infer column types from data."""
        column_types = {}

        for i, header in enumerate(headers):
            # Sample values from this column
            sample_values = []
            for row in data_rows[:100]:  # Sample first 100 rows
                if i < len(row) and row[i].strip():
                    sample_values.append(row[i].strip())

            if not sample_values:
                column_types[header] = "string"
                continue

            # Check if all values are integers
            if all(self._is_integer(val) for val in sample_values):
                column_types[header] = "integer"
            # Check if all values are floats
            elif all(self._is_numeric(val) for val in sample_values):
                column_types[header] = "float"
            # Check if all values are booleans
            elif all(
                val.lower() in ["true", "false", "1", "0", "yes", "no"]
                for val in sample_values
            ):
                column_types[header] = "boolean"
            else:
                column_types[header] = "string"

        return column_types

    def _is_integer(self, value: str) -> bool:
        """Check if a string value is an integer."""
        try:
            int(value)
            return True
        except ValueError:
            return False

    def get_csv_info(self, content: bytes) -> Dict[str, Any]:
        """
        Get basic CSV information without full parsing.

        Args:
            content: CSV content as bytes

        Returns:
            Dictionary with basic CSV information

        Raises:
            ContentError: If CSV reading fails
        """
        try:
            encoding = self._detect_encoding(content)
            text_content = content.decode(encoding, errors="replace")

            # Count lines
            lines = text_content.split("\n")
            non_empty_lines = [line for line in lines if line.strip()]

            # Detect dialect
            dialect = self._detect_dialect(text_content)

            # Parse first few rows to get column count
            csv_io = io.StringIO(text_content)
            reader = csv.reader(csv_io, dialect=dialect)
            first_row = next(reader, [])

            return {
                "encoding": encoding,
                "delimiter": dialect.delimiter,
                "estimated_rows": len(non_empty_lines),
                "estimated_columns": len(first_row),
                "file_size": len(content),
                "has_header": (
                    self._detect_header([first_row, next(reader, [])])
                    if first_row
                    else False
                ),
            }

        except Exception as e:
            raise ContentError(f"Failed to get CSV info: {e}")

    def is_valid_csv(self, content: bytes) -> bool:
        """
        Check if content is valid CSV.

        Args:
            content: Content to check as bytes

        Returns:
            True if content is valid CSV, False otherwise
        """
        try:
            encoding = self._detect_encoding(content)
            text_content = content.decode(encoding, errors="replace")

            csv_io = io.StringIO(text_content)
            reader = csv.reader(csv_io)

            # Try to read first few rows
            rows_read = 0
            for row in reader:
                rows_read += 1
                if rows_read >= 3:  # If we can read 3 rows, it's probably valid
                    break

            return rows_read > 0

        except Exception:
            return False
