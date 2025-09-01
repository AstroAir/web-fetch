"""
Comprehensive tests for the validation utility.
"""

import pytest
from typing import Dict, List, Any, Optional
from unittest.mock import patch

from web_fetch.utils.validation import (
    Validator,
    ValidationRule,
    ValidationResult,
    ValidationError,
    ValidationSeverity,
    URLValidator,
    HeaderValidator,
    DataValidator,
    SchemaValidator,
    validate_url,
    validate_headers,
    validate_json_schema,
)


class TestValidationResult:
    """Test validation result model."""
    
    def test_result_creation(self):
        """Test validation result creation."""
        result = ValidationResult(
            is_valid=True,
            field="url",
            message="Valid URL format",
            severity=ValidationSeverity.INFO
        )
        
        assert result.is_valid is True
        assert result.field == "url"
        assert result.message == "Valid URL format"
        assert result.severity == ValidationSeverity.INFO
    
    def test_error_result(self):
        """Test validation error result."""
        result = ValidationResult(
            is_valid=False,
            field="email",
            message="Invalid email format",
            severity=ValidationSeverity.ERROR,
            error_code="INVALID_EMAIL"
        )
        
        assert result.is_valid is False
        assert result.field == "email"
        assert result.message == "Invalid email format"
        assert result.severity == ValidationSeverity.ERROR
        assert result.error_code == "INVALID_EMAIL"
    
    def test_result_serialization(self):
        """Test validation result serialization."""
        result = ValidationResult(
            is_valid=False,
            field="password",
            message="Password too short",
            severity=ValidationSeverity.WARNING
        )
        
        data = result.to_dict()
        
        assert data["is_valid"] is False
        assert data["field"] == "password"
        assert data["message"] == "Password too short"
        assert data["severity"] == "WARNING"


class TestValidationRule:
    """Test validation rule functionality."""
    
    def test_rule_creation(self):
        """Test validation rule creation."""
        def length_validator(value: str) -> bool:
            return len(value) >= 8
        
        rule = ValidationRule(
            name="min_length",
            validator=length_validator,
            message="Value must be at least 8 characters",
            severity=ValidationSeverity.ERROR
        )
        
        assert rule.name == "min_length"
        assert rule.validator("password123") is True
        assert rule.validator("short") is False
        assert rule.message == "Value must be at least 8 characters"
        assert rule.severity == ValidationSeverity.ERROR
    
    def test_rule_validation(self):
        """Test rule validation execution."""
        def email_validator(value: str) -> bool:
            return "@" in value and "." in value
        
        rule = ValidationRule(
            name="email_format",
            validator=email_validator,
            message="Invalid email format"
        )
        
        # Valid email
        result = rule.validate("user@example.com", "email")
        assert result.is_valid is True
        assert result.field == "email"
        
        # Invalid email
        result = rule.validate("invalid-email", "email")
        assert result.is_valid is False
        assert result.message == "Invalid email format"
    
    def test_conditional_rule(self):
        """Test conditional validation rule."""
        def password_strength_validator(value: str) -> bool:
            return any(c.isupper() for c in value) and any(c.isdigit() for c in value)
        
        def password_condition(data: Dict[str, Any]) -> bool:
            return data.get("require_strong_password", False)
        
        rule = ValidationRule(
            name="password_strength",
            validator=password_strength_validator,
            message="Password must contain uppercase letter and digit",
            condition=password_condition
        )
        
        # Rule should not apply when condition is false
        data = {"password": "weakpass", "require_strong_password": False}
        result = rule.validate("weakpass", "password", data)
        assert result.is_valid is True  # Rule skipped
        
        # Rule should apply when condition is true
        data = {"password": "weakpass", "require_strong_password": True}
        result = rule.validate("weakpass", "password", data)
        assert result.is_valid is False  # Rule applied and failed


class TestURLValidator:
    """Test URL validation functionality."""
    
    @pytest.fixture
    def validator(self):
        """Create URL validator."""
        return URLValidator()
    
    def test_valid_urls(self, validator):
        """Test validation of valid URLs."""
        valid_urls = [
            "https://example.com",
            "http://localhost:8080",
            "https://sub.domain.com/path?query=value",
            "ftp://files.example.com/file.txt",
            "https://example.com:443/secure/path",
            "http://192.168.1.1:3000/api"
        ]
        
        for url in valid_urls:
            result = validator.validate_url(url)
            assert result.is_valid is True, f"URL should be valid: {url}"
    
    def test_invalid_urls(self, validator):
        """Test validation of invalid URLs."""
        invalid_urls = [
            "not-a-url",
            "javascript:alert('xss')",
            "file:///etc/passwd",
            "https://",
            "",
            "http://",
            "ftp://",
            "https://example..com",  # Double dot
            "http://example.com:99999",  # Invalid port
        ]
        
        for url in invalid_urls:
            result = validator.validate_url(url)
            assert result.is_valid is False, f"URL should be invalid: {url}"
    
    def test_url_scheme_validation(self, validator):
        """Test URL scheme validation."""
        # Allow only specific schemes
        validator.allowed_schemes = ["https", "http"]
        
        result = validator.validate_url("https://example.com")
        assert result.is_valid is True
        
        result = validator.validate_url("ftp://files.example.com")
        assert result.is_valid is False
        assert "scheme not allowed" in result.message.lower()
    
    def test_url_domain_validation(self, validator):
        """Test URL domain validation."""
        # Block specific domains
        validator.blocked_domains = ["malicious.com", "spam.net"]
        
        result = validator.validate_url("https://example.com")
        assert result.is_valid is True
        
        result = validator.validate_url("https://malicious.com/path")
        assert result.is_valid is False
        assert "domain not allowed" in result.message.lower()
    
    def test_url_length_validation(self, validator):
        """Test URL length validation."""
        validator.max_length = 50
        
        short_url = "https://example.com"
        result = validator.validate_url(short_url)
        assert result.is_valid is True
        
        long_url = "https://example.com/" + "a" * 100
        result = validator.validate_url(long_url)
        assert result.is_valid is False
        assert "too long" in result.message.lower()


class TestHeaderValidator:
    """Test HTTP header validation functionality."""
    
    @pytest.fixture
    def validator(self):
        """Create header validator."""
        return HeaderValidator()
    
    def test_valid_headers(self, validator):
        """Test validation of valid headers."""
        valid_headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer token123",
            "User-Agent": "MyApp/1.0",
            "Accept": "application/json, text/plain",
            "X-Custom-Header": "custom-value"
        }
        
        result = validator.validate_headers(valid_headers)
        assert result.is_valid is True
    
    def test_invalid_header_names(self, validator):
        """Test validation of invalid header names."""
        invalid_headers = {
            "": "empty-name",  # Empty header name
            "Invalid Header": "space-in-name",  # Space in name
            "Invalid\nHeader": "newline-in-name",  # Newline in name
            "Invalid\x00Header": "null-in-name",  # Null byte in name
        }
        
        for name, value in invalid_headers.items():
            headers = {name: value}
            result = validator.validate_headers(headers)
            assert result.is_valid is False
    
    def test_invalid_header_values(self, validator):
        """Test validation of invalid header values."""
        invalid_headers = {
            "Valid-Name": "invalid\nvalue",  # Newline in value
            "Another-Valid": "invalid\rvalue",  # Carriage return in value
            "Third-Valid": "invalid\x00value",  # Null byte in value
        }
        
        for name, value in invalid_headers.items():
            headers = {name: value}
            result = validator.validate_headers(headers)
            assert result.is_valid is False
    
    def test_required_headers(self, validator):
        """Test validation of required headers."""
        validator.required_headers = ["Content-Type", "Authorization"]
        
        # Missing required headers
        headers = {"User-Agent": "MyApp/1.0"}
        result = validator.validate_headers(headers)
        assert result.is_valid is False
        assert "required header" in result.message.lower()
        
        # All required headers present
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer token",
            "User-Agent": "MyApp/1.0"
        }
        result = validator.validate_headers(headers)
        assert result.is_valid is True
    
    def test_forbidden_headers(self, validator):
        """Test validation of forbidden headers."""
        validator.forbidden_headers = ["X-Forbidden", "Dangerous-Header"]
        
        # Contains forbidden header
        headers = {
            "Content-Type": "application/json",
            "X-Forbidden": "should-not-be-here"
        }
        result = validator.validate_headers(headers)
        assert result.is_valid is False
        assert "forbidden header" in result.message.lower()
        
        # No forbidden headers
        headers = {"Content-Type": "application/json"}
        result = validator.validate_headers(headers)
        assert result.is_valid is True


class TestDataValidator:
    """Test data validation functionality."""
    
    @pytest.fixture
    def validator(self):
        """Create data validator."""
        return DataValidator()
    
    def test_validate_json_data(self, validator):
        """Test JSON data validation."""
        # Valid JSON
        valid_json = '{"name": "test", "value": 123}'
        result = validator.validate_json(valid_json)
        assert result.is_valid is True
        
        # Invalid JSON
        invalid_json = '{"name": "test", "value":}'
        result = validator.validate_json(invalid_json)
        assert result.is_valid is False
        assert "invalid json" in result.message.lower()
    
    def test_validate_xml_data(self, validator):
        """Test XML data validation."""
        # Valid XML
        valid_xml = '<?xml version="1.0"?><root><item>test</item></root>'
        result = validator.validate_xml(valid_xml)
        assert result.is_valid is True
        
        # Invalid XML
        invalid_xml = '<root><item>test</root>'  # Missing closing tag
        result = validator.validate_xml(invalid_xml)
        assert result.is_valid is False
        assert "invalid xml" in result.message.lower()
    
    def test_validate_email(self, validator):
        """Test email validation."""
        # Valid emails
        valid_emails = [
            "user@example.com",
            "test.email@domain.co.uk",
            "user+tag@example.org",
            "123@numbers.com"
        ]
        
        for email in valid_emails:
            result = validator.validate_email(email)
            assert result.is_valid is True, f"Email should be valid: {email}"
        
        # Invalid emails
        invalid_emails = [
            "not-an-email",
            "@example.com",
            "user@",
            "user@.com",
            "user..double@example.com",
            "user@example..com"
        ]
        
        for email in invalid_emails:
            result = validator.validate_email(email)
            assert result.is_valid is False, f"Email should be invalid: {email}"
    
    def test_validate_phone_number(self, validator):
        """Test phone number validation."""
        # Valid phone numbers
        valid_phones = [
            "+1-555-123-4567",
            "(555) 123-4567",
            "555.123.4567",
            "5551234567",
            "+44 20 7946 0958"
        ]
        
        for phone in valid_phones:
            result = validator.validate_phone(phone)
            assert result.is_valid is True, f"Phone should be valid: {phone}"
        
        # Invalid phone numbers
        invalid_phones = [
            "123",  # Too short
            "abc-def-ghij",  # Letters
            "555-123-456789",  # Too long
            ""  # Empty
        ]
        
        for phone in invalid_phones:
            result = validator.validate_phone(phone)
            assert result.is_valid is False, f"Phone should be invalid: {phone}"


class TestSchemaValidator:
    """Test schema validation functionality."""
    
    @pytest.fixture
    def validator(self):
        """Create schema validator."""
        return SchemaValidator()
    
    def test_json_schema_validation(self, validator):
        """Test JSON schema validation."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer", "minimum": 0},
                "email": {"type": "string", "format": "email"}
            },
            "required": ["name", "age"]
        }
        
        # Valid data
        valid_data = {
            "name": "John Doe",
            "age": 30,
            "email": "john@example.com"
        }
        result = validator.validate_json_schema(valid_data, schema)
        assert result.is_valid is True
        
        # Invalid data (missing required field)
        invalid_data = {
            "name": "John Doe"
            # Missing required 'age' field
        }
        result = validator.validate_json_schema(invalid_data, schema)
        assert result.is_valid is False
        assert "required" in result.message.lower()
        
        # Invalid data (wrong type)
        invalid_data = {
            "name": "John Doe",
            "age": "thirty"  # Should be integer
        }
        result = validator.validate_json_schema(invalid_data, schema)
        assert result.is_valid is False
        assert "type" in result.message.lower()
    
    def test_custom_format_validation(self, validator):
        """Test custom format validation."""
        def validate_custom_id(value: str) -> bool:
            return value.startswith("ID_") and len(value) == 8
        
        validator.add_format_validator("custom_id", validate_custom_id)
        
        schema = {
            "type": "object",
            "properties": {
                "id": {"type": "string", "format": "custom_id"}
            }
        }
        
        # Valid custom ID
        valid_data = {"id": "ID_12345"}
        result = validator.validate_json_schema(valid_data, schema)
        assert result.is_valid is True
        
        # Invalid custom ID
        invalid_data = {"id": "INVALID_ID"}
        result = validator.validate_json_schema(invalid_data, schema)
        assert result.is_valid is False


class TestValidator:
    """Test main validator functionality."""
    
    @pytest.fixture
    def validator(self):
        """Create main validator."""
        return Validator()
    
    def test_add_validation_rules(self, validator):
        """Test adding validation rules."""
        def min_length_validator(value: str) -> bool:
            return len(value) >= 5
        
        rule = ValidationRule(
            name="min_length",
            validator=min_length_validator,
            message="Value must be at least 5 characters"
        )
        
        validator.add_rule("password", rule)
        
        assert "password" in validator._rules
        assert len(validator._rules["password"]) == 1
        assert validator._rules["password"][0] == rule
    
    def test_validate_field(self, validator):
        """Test field validation."""
        def email_validator(value: str) -> bool:
            return "@" in value and "." in value
        
        rule = ValidationRule(
            name="email_format",
            validator=email_validator,
            message="Invalid email format"
        )
        
        validator.add_rule("email", rule)
        
        # Valid email
        results = validator.validate_field("email", "user@example.com")
        assert len(results) == 1
        assert results[0].is_valid is True
        
        # Invalid email
        results = validator.validate_field("email", "invalid-email")
        assert len(results) == 1
        assert results[0].is_valid is False
    
    def test_validate_data(self, validator):
        """Test data validation with multiple fields."""
        # Add rules for different fields
        def email_validator(value: str) -> bool:
            return "@" in value and "." in value
        
        def age_validator(value: int) -> bool:
            return 0 <= value <= 150
        
        email_rule = ValidationRule("email_format", email_validator, "Invalid email")
        age_rule = ValidationRule("age_range", age_validator, "Age must be 0-150")
        
        validator.add_rule("email", email_rule)
        validator.add_rule("age", age_rule)
        
        # Valid data
        data = {"email": "user@example.com", "age": 25}
        results = validator.validate_data(data)
        
        assert len(results) == 2
        assert all(result.is_valid for result in results)
        
        # Invalid data
        data = {"email": "invalid-email", "age": 200}
        results = validator.validate_data(data)
        
        assert len(results) == 2
        assert all(not result.is_valid for result in results)
    
    def test_validation_summary(self, validator):
        """Test validation summary generation."""
        def always_fail(value: Any) -> bool:
            return False
        
        rule = ValidationRule("always_fail", always_fail, "Always fails")
        validator.add_rule("test_field", rule)
        
        data = {"test_field": "any_value"}
        results = validator.validate_data(data)
        summary = validator.get_validation_summary(results)
        
        assert summary["total_validations"] == 1
        assert summary["passed"] == 0
        assert summary["failed"] == 1
        assert len(summary["errors"]) == 1
        assert summary["errors"][0]["field"] == "test_field"


class TestValidationUtilityFunctions:
    """Test utility validation functions."""
    
    def test_validate_url_function(self):
        """Test standalone URL validation function."""
        # Valid URL
        result = validate_url("https://example.com")
        assert result is True
        
        # Invalid URL
        result = validate_url("not-a-url")
        assert result is False
    
    def test_validate_headers_function(self):
        """Test standalone headers validation function."""
        # Valid headers
        headers = {"Content-Type": "application/json"}
        result = validate_headers(headers)
        assert result is True
        
        # Invalid headers
        headers = {"": "empty-name"}
        result = validate_headers(headers)
        assert result is False
    
    def test_validate_json_schema_function(self):
        """Test standalone JSON schema validation function."""
        schema = {"type": "string"}
        
        # Valid data
        result = validate_json_schema("test string", schema)
        assert result is True
        
        # Invalid data
        result = validate_json_schema(123, schema)
        assert result is False
