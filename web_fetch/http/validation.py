"""
Comprehensive input validation utilities for web_fetch HTTP components.

This module provides robust input validation, parameter sanitization,
and data validation across all HTTP operations.
"""

import json
import re
from typing import Any, Dict, List, Optional, Union
from urllib.parse import parse_qs, quote, unquote, urlparse

from pydantic import BaseModel, Field, validator

from ..exceptions import WebFetchError


class ValidationConfig(BaseModel):
    """Configuration for input validation."""
    
    # String validation
    max_string_length: int = Field(
        default=10000,
        ge=1,
        description="Maximum allowed string length"
    )
    
    # URL validation
    max_url_length: int = Field(
        default=2048,
        ge=1,
        description="Maximum allowed URL length"
    )
    
    allowed_url_schemes: set[str] = Field(
        default={'http', 'https'},
        description="Allowed URL schemes"
    )
    
    # Parameter validation
    max_param_count: int = Field(
        default=100,
        ge=1,
        description="Maximum number of parameters"
    )
    
    max_param_name_length: int = Field(
        default=256,
        ge=1,
        description="Maximum parameter name length"
    )
    
    max_param_value_length: int = Field(
        default=4096,
        ge=1,
        description="Maximum parameter value length"
    )
    
    # JSON validation
    max_json_depth: int = Field(
        default=10,
        ge=1,
        description="Maximum JSON nesting depth"
    )
    
    max_json_size: int = Field(
        default=1024 * 1024,  # 1MB
        ge=1,
        description="Maximum JSON size in bytes"
    )
    
    # File validation
    max_filename_length: int = Field(
        default=255,
        ge=1,
        description="Maximum filename length"
    )
    
    allowed_file_extensions: Optional[set[str]] = Field(
        default=None,
        description="Allowed file extensions (if set)"
    )
    
    blocked_file_extensions: set[str] = Field(
        default={'.exe', '.bat', '.cmd', '.com', '.scr', '.pif'},
        description="Blocked file extensions"
    )


class InputValidator:
    """Comprehensive input validator for HTTP components."""
    
    def __init__(self, config: Optional[ValidationConfig] = None):
        """
        Initialize input validator.
        
        Args:
            config: Validation configuration
        """
        self.config = config or ValidationConfig()
        
        # Compile regex patterns for efficiency
        self._sql_injection_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)",
            r"(\b(OR|AND)\s+\d+\s*=\s*\d+)",
            r"(\b(OR|AND)\s+['\"]?\w+['\"]?\s*=\s*['\"]?\w+['\"]?)",
            r"(--|#|/\*|\*/)",
            r"(\bxp_\w+|\bsp_\w+)",
        ]
        
        self._xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"vbscript:",
            r"onload\s*=",
            r"onerror\s*=",
            r"onclick\s*=",
            r"<iframe[^>]*>",
            r"<object[^>]*>",
            r"<embed[^>]*>",
        ]
        
        self._path_traversal_patterns = [
            r"\.\./",
            r"\.\.\\",
            r"%2e%2e%2f",
            r"%2e%2e%5c",
            r"\.\.%2f",
            r"\.\.%5c",
        ]
        
        # Compile all patterns
        self._compiled_sql_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self._sql_injection_patterns
        ]
        self._compiled_xss_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self._xss_patterns
        ]
        self._compiled_path_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self._path_traversal_patterns
        ]
    
    def validate_string(self, value: str, field_name: str = "field") -> str:
        """
        Validate and sanitize string input.
        
        Args:
            value: String to validate
            field_name: Name of the field for error messages
            
        Returns:
            Validated string
            
        Raises:
            WebFetchError: If validation fails
        """
        if not isinstance(value, str):
            raise WebFetchError(f"{field_name} must be a string")
        
        # Check length
        if len(value) > self.config.max_string_length:
            raise WebFetchError(
                f"{field_name} exceeds maximum length of {self.config.max_string_length}"
            )
        
        # Check for null bytes
        if '\x00' in value:
            raise WebFetchError(f"{field_name} contains null bytes")
        
        # Check for control characters (except common whitespace)
        if re.search(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', value):
            raise WebFetchError(f"{field_name} contains invalid control characters")
        
        return value
    
    def validate_url(self, url: str) -> str:
        """
        Validate URL input.
        
        Args:
            url: URL to validate
            
        Returns:
            Validated URL
            
        Raises:
            WebFetchError: If validation fails
        """
        if not isinstance(url, str):
            raise WebFetchError("URL must be a string")
        
        url = url.strip()
        
        # Check length
        if len(url) > self.config.max_url_length:
            raise WebFetchError(f"URL exceeds maximum length of {self.config.max_url_length}")
        
        # Parse URL
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise WebFetchError(f"Invalid URL format: {e}")
        
        # Validate scheme
        if parsed.scheme.lower() not in self.config.allowed_url_schemes:
            raise WebFetchError(
                f"Invalid URL scheme: {parsed.scheme}. "
                f"Allowed: {', '.join(self.config.allowed_url_schemes)}"
            )
        
        # Check for suspicious patterns
        self._check_injection_patterns(url, "URL")
        
        return url
    
    def validate_parameters(self, params: Dict[str, Any]) -> Dict[str, str]:
        """
        Validate and sanitize URL parameters.
        
        Args:
            params: Parameters to validate
            
        Returns:
            Validated parameters
            
        Raises:
            WebFetchError: If validation fails
        """
        if not isinstance(params, dict):
            raise WebFetchError("Parameters must be a dictionary")
        
        # Check parameter count
        if len(params) > self.config.max_param_count:
            raise WebFetchError(f"Too many parameters: {len(params)} > {self.config.max_param_count}")
        
        validated_params = {}
        
        for name, value in params.items():
            # Validate parameter name
            if not isinstance(name, str):
                raise WebFetchError("Parameter names must be strings")
            
            if len(name) > self.config.max_param_name_length:
                raise WebFetchError(
                    f"Parameter name '{name}' exceeds maximum length of {self.config.max_param_name_length}"
                )
            
            # Validate parameter value
            str_value = str(value)
            if len(str_value) > self.config.max_param_value_length:
                raise WebFetchError(
                    f"Parameter value for '{name}' exceeds maximum length of {self.config.max_param_value_length}"
                )
            
            # Check for injection patterns
            self._check_injection_patterns(name, f"parameter name '{name}'")
            self._check_injection_patterns(str_value, f"parameter value for '{name}'")
            
            validated_params[name] = str_value
        
        return validated_params
    
    def validate_json(self, data: Union[str, Dict[Any, Any], List[Any]]) -> Union[Dict[Any, Any], List[Any]]:
        """
        Validate JSON data.
        
        Args:
            data: JSON data to validate
            
        Returns:
            Validated JSON data
            
        Raises:
            WebFetchError: If validation fails
        """
        # Parse JSON if string
        if isinstance(data, str):
            # Check size
            if len(data.encode('utf-8')) > self.config.max_json_size:
                raise WebFetchError(f"JSON data exceeds maximum size of {self.config.max_json_size} bytes")

            try:
                parsed_data = json.loads(data)
            except json.JSONDecodeError as e:
                raise WebFetchError(f"Invalid JSON: {e}")
        else:
            parsed_data = data

        # Check nesting depth
        self._check_json_depth(parsed_data, 0)

        # Check for injection patterns in string values
        self._validate_json_content(parsed_data)

        return cast(Union[Dict[Any, Any], List[Any]], parsed_data)
    
    def validate_filename(self, filename: str) -> str:
        """
        Validate filename for uploads.
        
        Args:
            filename: Filename to validate
            
        Returns:
            Validated filename
            
        Raises:
            WebFetchError: If validation fails
        """
        if not isinstance(filename, str):
            raise WebFetchError("Filename must be a string")
        
        filename = filename.strip()
        
        # Check length
        if len(filename) > self.config.max_filename_length:
            raise WebFetchError(f"Filename exceeds maximum length of {self.config.max_filename_length}")
        
        # Check for path traversal
        for pattern in self._compiled_path_patterns:
            if pattern.search(filename):
                raise WebFetchError("Filename contains path traversal patterns")
        
        # Check for invalid characters
        if re.search(r'[<>:"|?*\x00-\x1f]', filename):
            raise WebFetchError("Filename contains invalid characters")
        
        # Check file extension
        if '.' in filename:
            extension = '.' + filename.split('.')[-1].lower()
            
            if extension in self.config.blocked_file_extensions:
                raise WebFetchError(f"File extension '{extension}' is not allowed")
            
            if (self.config.allowed_file_extensions and 
                extension not in self.config.allowed_file_extensions):
                raise WebFetchError(f"File extension '{extension}' is not in allowlist")
        
        return filename
    
    def _check_injection_patterns(self, value: str, field_name: str) -> None:
        """Check for injection attack patterns."""
        # SQL injection
        for pattern in self._compiled_sql_patterns:
            if pattern.search(value):
                raise WebFetchError(f"Potential SQL injection detected in {field_name}")
        
        # XSS
        for pattern in self._compiled_xss_patterns:
            if pattern.search(value):
                raise WebFetchError(f"Potential XSS attack detected in {field_name}")
        
        # Path traversal
        for pattern in self._compiled_path_patterns:
            if pattern.search(value):
                raise WebFetchError(f"Path traversal attempt detected in {field_name}")
    
    def _check_json_depth(self, data: Any, current_depth: int) -> None:
        """Check JSON nesting depth."""
        if current_depth > self.config.max_json_depth:
            raise WebFetchError(f"JSON nesting depth exceeds maximum of {self.config.max_json_depth}")
        
        if isinstance(data, dict):
            for value in data.values():
                self._check_json_depth(value, current_depth + 1)
        elif isinstance(data, list):
            for item in data:
                self._check_json_depth(item, current_depth + 1)
    
    def _validate_json_content(self, data: Any) -> None:
        """Validate JSON content for injection patterns."""
        if isinstance(data, str):
            self._check_injection_patterns(data, "JSON string value")
        elif isinstance(data, dict):
            for key, value in data.items():
                if isinstance(key, str):
                    self._check_injection_patterns(key, "JSON key")
                self._validate_json_content(value)
        elif isinstance(data, list):
            for item in data:
                self._validate_json_content(item)


# Global validator instance
_global_validator: Optional[InputValidator] = None


def get_global_validator(config: Optional[ValidationConfig] = None) -> InputValidator:
    """Get or create global input validator."""
    global _global_validator
    
    if _global_validator is None:
        _global_validator = InputValidator(config)
    
    return _global_validator
