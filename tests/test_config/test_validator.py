"""
Comprehensive tests for the config validator module.
"""

import pytest
import tempfile
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from unittest.mock import patch, MagicMock

from web_fetch.config.validator import (
    ConfigValidator,
    ValidationRule,
    ValidationResult,
    ValidationError,
    RuleType,
    validate_url,
    validate_file_path,
    validate_directory_path,
    validate_port,
    validate_timeout,
    validate_positive_integer,
    validate_email,
    validate_json_schema,
)


class TestValidationRule:
    """Test validation rule model."""

    def test_validation_rule_creation(self):
        """Test creating validation rule."""
        rule = ValidationRule(
            field="timeout",
            rule_type=RuleType.RANGE,
            min_value=0.1,
            max_value=300.0,
            required=True,
            message="Timeout must be between 0.1 and 300 seconds"
        )
        
        assert rule.field == "timeout"
        assert rule.rule_type == RuleType.RANGE
        assert rule.min_value == 0.1
        assert rule.max_value == 300.0
        assert rule.required == True
        assert "Timeout must be" in rule.message

    def test_validation_rule_defaults(self):
        """Test validation rule defaults."""
        rule = ValidationRule(
            field="test_field",
            rule_type=RuleType.TYPE
        )
        
        assert rule.field == "test_field"
        assert rule.rule_type == RuleType.TYPE
        assert rule.required == False
        assert rule.message is None


class TestValidationResult:
    """Test validation result model."""

    def test_validation_result_success(self):
        """Test successful validation result."""
        result = ValidationResult(
            valid=True,
            field="timeout",
            value=30.0
        )
        
        assert result.valid == True
        assert result.field == "timeout"
        assert result.value == 30.0
        assert result.error is None

    def test_validation_result_failure(self):
        """Test failed validation result."""
        result = ValidationResult(
            valid=False,
            field="max_retries",
            value=-1,
            error="Value must be positive"
        )
        
        assert result.valid == False
        assert result.field == "max_retries"
        assert result.value == -1
        assert result.error == "Value must be positive"


class TestValidationError:
    """Test validation error."""

    def test_validation_error_creation(self):
        """Test creating validation error."""
        error = ValidationError(
            message="Validation failed",
            field="timeout",
            value=-1,
            rule_type=RuleType.RANGE
        )
        
        assert error.message == "Validation failed"
        assert error.field == "timeout"
        assert error.value == -1
        assert error.rule_type == RuleType.RANGE

    def test_validation_error_string_representation(self):
        """Test validation error string representation."""
        error = ValidationError(
            message="Invalid value",
            field="port",
            value=70000
        )
        
        error_str = str(error)
        assert "Invalid value" in error_str
        assert "port" in error_str


class TestRuleType:
    """Test rule type enumeration."""

    def test_rule_type_values(self):
        """Test rule type enumeration values."""
        assert RuleType.TYPE == "type"
        assert RuleType.RANGE == "range"
        assert RuleType.PATTERN == "pattern"
        assert RuleType.CUSTOM == "custom"
        assert RuleType.REQUIRED == "required"


class TestValidationFunctions:
    """Test individual validation functions."""

    def test_validate_url_valid(self):
        """Test validating valid URLs."""
        valid_urls = [
            "https://example.com",
            "http://localhost:8080",
            "https://api.example.com/v1/endpoint",
            "ftp://files.example.com/path"
        ]
        
        for url in valid_urls:
            result = validate_url(url)
            assert result.valid == True, f"URL {url} should be valid"

    def test_validate_url_invalid(self):
        """Test validating invalid URLs."""
        invalid_urls = [
            "not-a-url",
            "http://",
            "://example.com",
            "https://",
            ""
        ]
        
        for url in invalid_urls:
            result = validate_url(url)
            assert result.valid == False, f"URL {url} should be invalid"

    def test_validate_file_path_existing(self):
        """Test validating existing file paths."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(b"test content")
            tmp_file.flush()
            
            result = validate_file_path(tmp_file.name)
            assert result.valid == True
            
            # Clean up
            os.unlink(tmp_file.name)

    def test_validate_file_path_nonexistent(self):
        """Test validating non-existent file paths."""
        result = validate_file_path("/nonexistent/file.txt")
        assert result.valid == False
        assert "does not exist" in result.error

    def test_validate_directory_path_existing(self):
        """Test validating existing directory paths."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = validate_directory_path(tmp_dir)
            assert result.valid == True

    def test_validate_directory_path_nonexistent(self):
        """Test validating non-existent directory paths."""
        result = validate_directory_path("/nonexistent/directory")
        assert result.valid == False
        assert "does not exist" in result.error

    def test_validate_port_valid(self):
        """Test validating valid port numbers."""
        valid_ports = [80, 443, 8080, 3000, 65535]
        
        for port in valid_ports:
            result = validate_port(port)
            assert result.valid == True, f"Port {port} should be valid"

    def test_validate_port_invalid(self):
        """Test validating invalid port numbers."""
        invalid_ports = [0, -1, 65536, 100000]
        
        for port in invalid_ports:
            result = validate_port(port)
            assert result.valid == False, f"Port {port} should be invalid"

    def test_validate_timeout_valid(self):
        """Test validating valid timeout values."""
        valid_timeouts = [0.1, 1.0, 30.0, 300.0]
        
        for timeout in valid_timeouts:
            result = validate_timeout(timeout)
            assert result.valid == True, f"Timeout {timeout} should be valid"

    def test_validate_timeout_invalid(self):
        """Test validating invalid timeout values."""
        invalid_timeouts = [0, -1, -0.5]
        
        for timeout in invalid_timeouts:
            result = validate_timeout(timeout)
            assert result.valid == False, f"Timeout {timeout} should be invalid"

    def test_validate_positive_integer_valid(self):
        """Test validating valid positive integers."""
        valid_integers = [1, 5, 100, 1000]
        
        for integer in valid_integers:
            result = validate_positive_integer(integer)
            assert result.valid == True, f"Integer {integer} should be valid"

    def test_validate_positive_integer_invalid(self):
        """Test validating invalid positive integers."""
        invalid_integers = [0, -1, -100, 1.5, "not_an_integer"]
        
        for integer in invalid_integers:
            result = validate_positive_integer(integer)
            assert result.valid == False, f"Integer {integer} should be invalid"

    def test_validate_email_valid(self):
        """Test validating valid email addresses."""
        valid_emails = [
            "user@example.com",
            "test.email@domain.org",
            "admin+notifications@company.co.uk"
        ]
        
        for email in valid_emails:
            result = validate_email(email)
            assert result.valid == True, f"Email {email} should be valid"

    def test_validate_email_invalid(self):
        """Test validating invalid email addresses."""
        invalid_emails = [
            "not-an-email",
            "@example.com",
            "user@",
            "user@.com",
            ""
        ]
        
        for email in invalid_emails:
            result = validate_email(email)
            assert result.valid == False, f"Email {email} should be invalid"

    def test_validate_json_schema_valid(self):
        """Test validating data against JSON schema."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer", "minimum": 0}
            },
            "required": ["name"]
        }
        
        valid_data = {"name": "John", "age": 30}
        result = validate_json_schema(valid_data, schema)
        assert result.valid == True

    def test_validate_json_schema_invalid(self):
        """Test validating invalid data against JSON schema."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer", "minimum": 0}
            },
            "required": ["name"]
        }
        
        invalid_data = {"age": -5}  # Missing required name, invalid age
        result = validate_json_schema(invalid_data, schema)
        assert result.valid == False


class TestConfigValidator:
    """Test config validator functionality."""

    def test_config_validator_creation(self):
        """Test creating config validator."""
        validator = ConfigValidator()
        assert validator is not None
        assert len(validator.rules) == 0

    def test_add_validation_rule(self):
        """Test adding validation rule."""
        validator = ConfigValidator()
        
        rule = ValidationRule(
            field="timeout",
            rule_type=RuleType.RANGE,
            min_value=0.1,
            max_value=300.0
        )
        
        validator.add_rule(rule)
        
        assert len(validator.rules) == 1
        assert validator.rules[0] == rule

    def test_validate_config_success(self):
        """Test successful config validation."""
        validator = ConfigValidator()
        
        # Add timeout validation rule
        timeout_rule = ValidationRule(
            field="timeout",
            rule_type=RuleType.RANGE,
            min_value=0.1,
            max_value=300.0
        )
        validator.add_rule(timeout_rule)
        
        # Add retries validation rule
        retries_rule = ValidationRule(
            field="max_retries",
            rule_type=RuleType.RANGE,
            min_value=0,
            max_value=10
        )
        validator.add_rule(retries_rule)
        
        config = {
            "timeout": 30.0,
            "max_retries": 3
        }
        
        results = validator.validate(config)
        
        assert len(results) == 2
        assert all(result.valid for result in results)

    def test_validate_config_failure(self):
        """Test failed config validation."""
        validator = ConfigValidator()
        
        # Add timeout validation rule
        timeout_rule = ValidationRule(
            field="timeout",
            rule_type=RuleType.RANGE,
            min_value=0.1,
            max_value=300.0
        )
        validator.add_rule(timeout_rule)
        
        config = {
            "timeout": -1.0  # Invalid timeout
        }
        
        results = validator.validate(config)
        
        assert len(results) == 1
        assert not results[0].valid
        assert "range" in results[0].error.lower()

    def test_validate_required_field_missing(self):
        """Test validation with missing required field."""
        validator = ConfigValidator()
        
        # Add required field rule
        required_rule = ValidationRule(
            field="api_key",
            rule_type=RuleType.REQUIRED,
            required=True
        )
        validator.add_rule(required_rule)
        
        config = {}  # Missing api_key
        
        results = validator.validate(config)
        
        assert len(results) == 1
        assert not results[0].valid
        assert "required" in results[0].error.lower()

    def test_validate_type_checking(self):
        """Test type validation."""
        validator = ConfigValidator()
        
        # Add type validation rule
        type_rule = ValidationRule(
            field="max_retries",
            rule_type=RuleType.TYPE,
            expected_type=int
        )
        validator.add_rule(type_rule)
        
        config = {
            "max_retries": "not_an_integer"  # Wrong type
        }
        
        results = validator.validate(config)
        
        assert len(results) == 1
        assert not results[0].valid
        assert "type" in results[0].error.lower()

    def test_validate_pattern_matching(self):
        """Test pattern validation."""
        validator = ConfigValidator()
        
        # Add pattern validation rule
        pattern_rule = ValidationRule(
            field="user_agent",
            rule_type=RuleType.PATTERN,
            pattern=r"^[\w\-\.]+/\d+\.\d+$"  # name/version format
        )
        validator.add_rule(pattern_rule)
        
        # Valid user agent
        config_valid = {
            "user_agent": "web-fetch/1.0"
        }
        
        results = validator.validate(config_valid)
        assert len(results) == 1
        assert results[0].valid
        
        # Invalid user agent
        config_invalid = {
            "user_agent": "invalid user agent format"
        }
        
        results = validator.validate(config_invalid)
        assert len(results) == 1
        assert not results[0].valid

    def test_validate_custom_function(self):
        """Test custom validation function."""
        validator = ConfigValidator()
        
        def validate_even_number(value):
            """Custom validator for even numbers."""
            if not isinstance(value, int):
                return ValidationResult(
                    valid=False,
                    field="custom_field",
                    value=value,
                    error="Value must be an integer"
                )
            
            if value % 2 != 0:
                return ValidationResult(
                    valid=False,
                    field="custom_field",
                    value=value,
                    error="Value must be even"
                )
            
            return ValidationResult(
                valid=True,
                field="custom_field",
                value=value
            )
        
        # Add custom validation rule
        custom_rule = ValidationRule(
            field="even_number",
            rule_type=RuleType.CUSTOM,
            custom_validator=validate_even_number
        )
        validator.add_rule(custom_rule)
        
        # Valid even number
        config_valid = {"even_number": 4}
        results = validator.validate(config_valid)
        assert len(results) == 1
        assert results[0].valid
        
        # Invalid odd number
        config_invalid = {"even_number": 3}
        results = validator.validate(config_invalid)
        assert len(results) == 1
        assert not results[0].valid

    def test_validate_multiple_rules_same_field(self):
        """Test multiple validation rules for the same field."""
        validator = ConfigValidator()
        
        # Add type rule
        type_rule = ValidationRule(
            field="port",
            rule_type=RuleType.TYPE,
            expected_type=int
        )
        validator.add_rule(type_rule)
        
        # Add range rule
        range_rule = ValidationRule(
            field="port",
            rule_type=RuleType.RANGE,
            min_value=1,
            max_value=65535
        )
        validator.add_rule(range_rule)
        
        config = {"port": 8080}
        
        results = validator.validate(config)
        
        assert len(results) == 2
        assert all(result.valid for result in results)

    def test_validate_nested_config(self):
        """Test validating nested configuration."""
        validator = ConfigValidator()
        
        # Add rule for nested field
        nested_rule = ValidationRule(
            field="database.port",
            rule_type=RuleType.RANGE,
            min_value=1,
            max_value=65535
        )
        validator.add_rule(nested_rule)
        
        config = {
            "database": {
                "port": 5432
            }
        }
        
        results = validator.validate(config)
        
        assert len(results) == 1
        assert results[0].valid

    def test_get_validation_summary(self):
        """Test getting validation summary."""
        validator = ConfigValidator()
        
        # Add some rules
        timeout_rule = ValidationRule(
            field="timeout",
            rule_type=RuleType.RANGE,
            min_value=0.1,
            max_value=300.0
        )
        validator.add_rule(timeout_rule)
        
        config = {"timeout": -1.0}  # Invalid
        
        results = validator.validate(config)
        summary = validator.get_validation_summary(results)
        
        assert summary["total_validations"] == 1
        assert summary["successful_validations"] == 0
        assert summary["failed_validations"] == 1
        assert len(summary["errors"]) == 1

    def test_validate_with_warnings(self):
        """Test validation with warnings."""
        validator = ConfigValidator()
        
        # Add rule that generates warnings
        warning_rule = ValidationRule(
            field="timeout",
            rule_type=RuleType.RANGE,
            min_value=0.1,
            max_value=300.0,
            warning_threshold=60.0  # Warn if timeout > 60
        )
        validator.add_rule(warning_rule)
        
        config = {"timeout": 120.0}  # Valid but should generate warning
        
        results = validator.validate(config)
        
        assert len(results) == 1
        assert results[0].valid
        assert results[0].warning is not None

    def test_validate_config_schema(self):
        """Test validating entire config against schema."""
        validator = ConfigValidator()
        
        schema = {
            "type": "object",
            "properties": {
                "timeout": {"type": "number", "minimum": 0.1},
                "max_retries": {"type": "integer", "minimum": 0}
            },
            "required": ["timeout"]
        }
        
        validator.set_schema(schema)
        
        # Valid config
        config_valid = {"timeout": 30.0, "max_retries": 3}
        results = validator.validate_schema(config_valid)
        assert results.valid
        
        # Invalid config
        config_invalid = {"max_retries": 3}  # Missing required timeout
        results = validator.validate_schema(config_invalid)
        assert not results.valid
