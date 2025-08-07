"""
Response transformation pipeline for the web_fetch library.

This module provides a flexible pipeline system for transforming and processing
HTTP responses, including data extraction, validation, and format conversion.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union
from urllib.parse import urljoin, urlparse

try:
    from bs4 import BeautifulSoup

    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

try:
    import jsonpath_ng

    HAS_JSONPATH = True
except ImportError:
    HAS_JSONPATH = False


@dataclass
class TransformationResult:
    """Result of a transformation operation."""

    data: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        """Check if transformation was successful."""
        return len(self.errors) == 0

    def add_error(self, error: str) -> None:
        """Add an error to the result."""
        self.errors.append(error)

    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to the result."""
        self.metadata[key] = value


class Transformer(ABC):
    """Base class for response transformers."""

    @abstractmethod
    async def transform(
        self, data: Any, context: Dict[str, Any]
    ) -> TransformationResult:
        """
        Transform the input data.

        Args:
            data: Input data to transform
            context: Context information (URL, headers, etc.)

        Returns:
            TransformationResult with transformed data
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Get the name of this transformer."""
        pass


class JSONPathExtractor(Transformer):
    """Extract data from JSON using JSONPath expressions."""

    def __init__(self, expressions: Dict[str, str], strict: bool = False):
        """
        Initialize JSONPath extractor.

        Args:
            expressions: Dict mapping field names to JSONPath expressions
            strict: If True, fail if any expression doesn't match
        """
        if not HAS_JSONPATH:
            raise ImportError("jsonpath-ng is required for JSONPathExtractor")

        self.expressions = expressions
        self.strict = strict
        self._compiled_expressions = {
            name: jsonpath_ng.parse(expr) for name, expr in expressions.items()
        }

    async def transform(
        self, data: Any, context: Dict[str, Any]
    ) -> TransformationResult:
        """Extract data using JSONPath expressions."""
        result = TransformationResult({})

        try:
            # Ensure data is parsed as JSON if it's a string
            if isinstance(data, str):
                data = json.loads(data)

            for field_name, compiled_expr in self._compiled_expressions.items():
                matches = compiled_expr.find(data)

                if matches:
                    # Extract values from matches
                    values = [match.value for match in matches]
                    result.data[field_name] = values[0] if len(values) == 1 else values
                elif self.strict:
                    result.add_error(
                        f"JSONPath expression '{self.expressions[field_name]}' found no matches"
                    )
                else:
                    result.data[field_name] = None

            result.add_metadata("extracted_fields", len(result.data))

        except json.JSONDecodeError as e:
            result.add_error(f"Invalid JSON data: {e}")
        except Exception as e:
            result.add_error(f"JSONPath extraction failed: {e}")

        return result

    @property
    def name(self) -> str:
        return "jsonpath_extractor"


class HTMLExtractor(Transformer):
    """Extract data from HTML using CSS selectors or XPath."""

    def __init__(
        self,
        selectors: Dict[str, str],
        selector_type: str = "css",
        extract_text: bool = True,
        base_url: Optional[str] = None,
    ):
        """
        Initialize HTML extractor.

        Args:
            selectors: Dict mapping field names to CSS selectors or XPath expressions
            selector_type: "css" or "xpath"
            extract_text: If True, extract text content; if False, extract HTML
            base_url: Base URL for resolving relative URLs
        """
        if not HAS_BS4:
            raise ImportError("beautifulsoup4 is required for HTMLExtractor")

        self.selectors = selectors
        self.selector_type = selector_type.lower()
        self.extract_text = extract_text
        self.base_url = base_url

        if self.selector_type not in ("css", "xpath"):
            raise ValueError("selector_type must be 'css' or 'xpath'")

    async def transform(
        self, data: Any, context: Dict[str, Any]
    ) -> TransformationResult:
        """Extract data from HTML."""
        result = TransformationResult({})

        try:
            # Parse HTML
            if isinstance(data, bytes):
                data = data.decode("utf-8", errors="ignore")

            soup = BeautifulSoup(data, "html.parser")

            # Use base_url from context if not provided
            base_url = self.base_url or context.get("url")

            for field_name, selector in self.selectors.items():
                try:
                    if self.selector_type == "css":
                        elements = soup.select(selector)
                    else:
                        # XPath support would require lxml
                        result.add_error(
                            f"XPath support not implemented for selector: {selector}"
                        )
                        continue

                    if elements:
                        if self.extract_text:
                            values = [elem.get_text(strip=True) for elem in elements]
                        else:
                            values = [str(elem) for elem in elements]

                        # Resolve relative URLs if extracting href or src attributes
                        if base_url and not self.extract_text:
                            values = self._resolve_urls(values, base_url)

                        result.data[field_name] = (
                            values[0] if len(values) == 1 else values
                        )
                    else:
                        result.data[field_name] = None

                except Exception as e:
                    result.add_error(f"Selector '{selector}' failed: {e}")

            result.add_metadata("extracted_fields", len(result.data))

        except Exception as e:
            result.add_error(f"HTML parsing failed: {e}")

        return result

    def _resolve_urls(self, values: List[str], base_url: str) -> List[str]:
        """Resolve relative URLs in extracted content."""
        resolved = []
        for value in values:
            # Simple URL resolution for href and src attributes
            if "href=" in value or "src=" in value:
                # This is a simplified approach - a full implementation would parse attributes properly
                resolved.append(value)  # For now, return as-is
            else:
                resolved.append(value)
        return resolved

    @property
    def name(self) -> str:
        return "html_extractor"


class RegexExtractor(Transformer):
    """Extract data using regular expressions."""

    def __init__(self, patterns: Dict[str, str], flags: int = 0):
        """
        Initialize regex extractor.

        Args:
            patterns: Dict mapping field names to regex patterns
            flags: Regex flags (e.g., re.IGNORECASE)
        """
        self.patterns = patterns
        self.flags = flags
        self._compiled_patterns = {
            name: re.compile(pattern, flags) for name, pattern in patterns.items()
        }

    async def transform(
        self, data: Any, context: Dict[str, Any]
    ) -> TransformationResult:
        """Extract data using regex patterns."""
        result = TransformationResult({})

        try:
            # Convert data to string if needed
            if isinstance(data, bytes):
                data = data.decode("utf-8", errors="ignore")
            elif not isinstance(data, str):
                data = str(data)

            for field_name, compiled_pattern in self._compiled_patterns.items():
                matches = compiled_pattern.findall(data)

                if matches:
                    result.data[field_name] = (
                        matches[0] if len(matches) == 1 else matches
                    )
                else:
                    result.data[field_name] = None

            result.add_metadata("extracted_fields", len(result.data))

        except Exception as e:
            result.add_error(f"Regex extraction failed: {e}")

        return result

    @property
    def name(self) -> str:
        return "regex_extractor"


class DataValidator(Transformer):
    """Validate extracted data against schemas or rules."""

    def __init__(
        self,
        validators: Dict[str, Callable[[Any], bool]],
        error_messages: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize data validator.

        Args:
            validators: Dict mapping field names to validation functions
            error_messages: Custom error messages for validation failures
        """
        self.validators = validators
        self.error_messages = error_messages or {}

    async def transform(
        self, data: Any, context: Dict[str, Any]
    ) -> TransformationResult:
        """Validate data fields."""
        result = TransformationResult(data)

        if not isinstance(data, dict):
            result.add_error("Data must be a dictionary for validation")
            return result

        valid_fields = 0

        for field_name, validator in self.validators.items():
            if field_name in data:
                try:
                    if validator(data[field_name]):
                        valid_fields += 1
                    else:
                        error_msg = self.error_messages.get(
                            field_name, f"Validation failed for field '{field_name}'"
                        )
                        result.add_error(error_msg)
                except Exception as e:
                    result.add_error(f"Validation error for field '{field_name}': {e}")

        result.add_metadata("validated_fields", valid_fields)
        result.add_metadata("total_validators", len(self.validators))

        return result

    @property
    def name(self) -> str:
        return "data_validator"


class TransformationPipeline:
    """Pipeline for chaining multiple transformers."""

    def __init__(self, transformers: List[Transformer]):
        """
        Initialize transformation pipeline.

        Args:
            transformers: List of transformers to apply in order
        """
        self.transformers = transformers

    async def transform(
        self, data: Any, context: Optional[Dict[str, Any]] = None
    ) -> TransformationResult:
        """
        Apply all transformers in the pipeline.

        Args:
            data: Input data to transform
            context: Context information

        Returns:
            Final transformation result
        """
        context = context or {}
        current_data = data
        all_errors = []
        all_metadata = {}

        for transformer in self.transformers:
            try:
                result = await transformer.transform(current_data, context)

                if result.is_success:
                    current_data = result.data
                else:
                    all_errors.extend(result.errors)

                # Merge metadata
                all_metadata[transformer.name] = result.metadata

            except Exception as e:
                all_errors.append(f"Transformer '{transformer.name}' failed: {e}")

        final_result = TransformationResult(current_data)
        final_result.errors = all_errors
        final_result.metadata = all_metadata

        return final_result

    def add_transformer(self, transformer: Transformer) -> None:
        """Add a transformer to the end of the pipeline."""
        self.transformers.append(transformer)

    def insert_transformer(self, index: int, transformer: Transformer) -> None:
        """Insert a transformer at a specific position in the pipeline."""
        self.transformers.insert(index, transformer)


__all__ = [
    "Transformer",
    "TransformationResult",
    "TransformationPipeline",
    "JSONPathExtractor",
    "HTMLExtractor",
    "RegexExtractor",
    "DataValidator",
]
