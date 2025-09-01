"""
Comprehensive tests for the transformers utility.
"""

import pytest
import json
from typing import Any, Dict, List
from unittest.mock import patch, MagicMock

from web_fetch.utils.transformers import (
    DataTransformer,
    TransformationPipeline,
    TransformationStep,
    TransformationResult,
    TransformationError,
    JSONTransformer,
    XMLTransformer,
    HTMLTransformer,
    TextTransformer,
    transform_json,
    transform_xml,
    transform_html,
)


class TestTransformationResult:
    """Test transformation result model."""
    
    def test_result_creation(self):
        """Test transformation result creation."""
        original_data = {"name": "test", "value": 123}
        transformed_data = {"name": "TEST", "value": 123}
        
        result = TransformationResult(
            original_data=original_data,
            transformed_data=transformed_data,
            transformation_type="uppercase_name",
            success=True,
            metadata={"steps_applied": 1}
        )
        
        assert result.original_data == original_data
        assert result.transformed_data == transformed_data
        assert result.transformation_type == "uppercase_name"
        assert result.success is True
        assert result.metadata["steps_applied"] == 1
    
    def test_failed_result(self):
        """Test failed transformation result."""
        result = TransformationResult(
            original_data={"invalid": "data"},
            transformed_data=None,
            transformation_type="failed_transform",
            success=False,
            error="Transformation failed"
        )
        
        assert result.success is False
        assert result.error == "Transformation failed"
        assert result.transformed_data is None
    
    def test_result_serialization(self):
        """Test transformation result serialization."""
        result = TransformationResult(
            original_data={"test": "data"},
            transformed_data={"test": "DATA"},
            transformation_type="uppercase",
            success=True
        )
        
        data = result.to_dict()
        
        assert data["original_data"] == {"test": "data"}
        assert data["transformed_data"] == {"test": "DATA"}
        assert data["transformation_type"] == "uppercase"
        assert data["success"] is True


class TestTransformationStep:
    """Test transformation step functionality."""
    
    def test_step_creation(self):
        """Test transformation step creation."""
        def uppercase_transform(data: Dict[str, Any]) -> Dict[str, Any]:
            return {k: v.upper() if isinstance(v, str) else v for k, v in data.items()}
        
        step = TransformationStep(
            name="uppercase_strings",
            transform_func=uppercase_transform,
            description="Convert all string values to uppercase"
        )
        
        assert step.name == "uppercase_strings"
        assert step.description == "Convert all string values to uppercase"
        assert callable(step.transform_func)
    
    def test_step_execution(self):
        """Test transformation step execution."""
        def add_timestamp(data: Dict[str, Any]) -> Dict[str, Any]:
            data["timestamp"] = "2023-01-01T00:00:00Z"
            return data
        
        step = TransformationStep(
            name="add_timestamp",
            transform_func=add_timestamp
        )
        
        input_data = {"name": "test", "value": 123}
        result = step.execute(input_data)
        
        assert result["name"] == "test"
        assert result["value"] == 123
        assert result["timestamp"] == "2023-01-01T00:00:00Z"
    
    def test_conditional_step(self):
        """Test conditional transformation step."""
        def uppercase_name(data: Dict[str, Any]) -> Dict[str, Any]:
            data["name"] = data["name"].upper()
            return data
        
        def has_name_field(data: Dict[str, Any]) -> bool:
            return "name" in data and isinstance(data["name"], str)
        
        step = TransformationStep(
            name="uppercase_name",
            transform_func=uppercase_name,
            condition=has_name_field
        )
        
        # Should apply when condition is met
        data_with_name = {"name": "test", "value": 123}
        result = step.execute(data_with_name)
        assert result["name"] == "TEST"
        
        # Should not apply when condition is not met
        data_without_name = {"value": 123}
        result = step.execute(data_without_name)
        assert result == data_without_name  # Unchanged
    
    def test_step_error_handling(self):
        """Test transformation step error handling."""
        def failing_transform(data: Dict[str, Any]) -> Dict[str, Any]:
            raise ValueError("Transformation failed")
        
        step = TransformationStep(
            name="failing_step",
            transform_func=failing_transform
        )
        
        with pytest.raises(TransformationError):
            step.execute({"test": "data"})


class TestJSONTransformer:
    """Test JSON transformer functionality."""
    
    @pytest.fixture
    def transformer(self):
        """Create JSON transformer."""
        return JSONTransformer()
    
    def test_extract_fields(self, transformer):
        """Test extracting specific fields from JSON."""
        data = {
            "user": {
                "name": "John Doe",
                "email": "john@example.com",
                "age": 30,
                "address": {
                    "city": "New York",
                    "country": "USA"
                }
            },
            "metadata": {
                "created": "2023-01-01",
                "version": "1.0"
            }
        }
        
        # Extract specific fields
        result = transformer.extract_fields(data, [
            "user.name",
            "user.email",
            "user.address.city",
            "metadata.version"
        ])
        
        expected = {
            "user.name": "John Doe",
            "user.email": "john@example.com",
            "user.address.city": "New York",
            "metadata.version": "1.0"
        }
        
        assert result == expected
    
    def test_flatten_json(self, transformer):
        """Test flattening nested JSON structure."""
        nested_data = {
            "user": {
                "name": "John",
                "details": {
                    "age": 30,
                    "location": {
                        "city": "NYC",
                        "country": "USA"
                    }
                }
            },
            "active": True
        }
        
        flattened = transformer.flatten(nested_data)
        
        expected = {
            "user.name": "John",
            "user.details.age": 30,
            "user.details.location.city": "NYC",
            "user.details.location.country": "USA",
            "active": True
        }
        
        assert flattened == expected
    
    def test_unflatten_json(self, transformer):
        """Test unflattening flat JSON structure."""
        flat_data = {
            "user.name": "John",
            "user.details.age": 30,
            "user.details.location.city": "NYC",
            "user.details.location.country": "USA",
            "active": True
        }
        
        unflattened = transformer.unflatten(flat_data)
        
        expected = {
            "user": {
                "name": "John",
                "details": {
                    "age": 30,
                    "location": {
                        "city": "NYC",
                        "country": "USA"
                    }
                }
            },
            "active": True
        }
        
        assert unflattened == expected
    
    def test_filter_fields(self, transformer):
        """Test filtering JSON fields."""
        data = {
            "public_field": "visible",
            "private_field": "hidden",
            "user": {
                "name": "John",
                "password": "secret",
                "email": "john@example.com"
            }
        }
        
        # Include only specific fields
        filtered = transformer.filter_fields(
            data,
            include=["public_field", "user.name", "user.email"]
        )
        
        expected = {
            "public_field": "visible",
            "user": {
                "name": "John",
                "email": "john@example.com"
            }
        }
        
        assert filtered == expected
    
    def test_exclude_fields(self, transformer):
        """Test excluding specific JSON fields."""
        data = {
            "name": "John",
            "email": "john@example.com",
            "password": "secret",
            "internal_id": "12345"
        }
        
        # Exclude sensitive fields
        filtered = transformer.filter_fields(
            data,
            exclude=["password", "internal_id"]
        )
        
        expected = {
            "name": "John",
            "email": "john@example.com"
        }
        
        assert filtered == expected
    
    def test_transform_values(self, transformer):
        """Test transforming JSON values."""
        data = {
            "name": "john doe",
            "email": "JOHN@EXAMPLE.COM",
            "age": "30",
            "tags": ["python", "web", "api"]
        }
        
        def transform_func(key: str, value: Any) -> Any:
            if key == "name":
                return value.title()
            elif key == "email":
                return value.lower()
            elif key == "age":
                return int(value)
            elif key == "tags" and isinstance(value, list):
                return [tag.upper() for tag in value]
            return value
        
        transformed = transformer.transform_values(data, transform_func)
        
        expected = {
            "name": "John Doe",
            "email": "john@example.com",
            "age": 30,
            "tags": ["PYTHON", "WEB", "API"]
        }
        
        assert transformed == expected


class TestXMLTransformer:
    """Test XML transformer functionality."""
    
    @pytest.fixture
    def transformer(self):
        """Create XML transformer."""
        return XMLTransformer()
    
    def test_xml_to_dict(self, transformer):
        """Test converting XML to dictionary."""
        xml_data = """
        <user>
            <name>John Doe</name>
            <email>john@example.com</email>
            <age>30</age>
            <address>
                <city>New York</city>
                <country>USA</country>
            </address>
        </user>
        """
        
        result = transformer.xml_to_dict(xml_data)
        
        assert result["user"]["name"] == "John Doe"
        assert result["user"]["email"] == "john@example.com"
        assert result["user"]["age"] == "30"
        assert result["user"]["address"]["city"] == "New York"
        assert result["user"]["address"]["country"] == "USA"
    
    def test_dict_to_xml(self, transformer):
        """Test converting dictionary to XML."""
        data = {
            "user": {
                "name": "John Doe",
                "email": "john@example.com",
                "age": 30,
                "address": {
                    "city": "New York",
                    "country": "USA"
                }
            }
        }
        
        xml_result = transformer.dict_to_xml(data)
        
        assert "<user>" in xml_result
        assert "<name>John Doe</name>" in xml_result
        assert "<email>john@example.com</email>" in xml_result
        assert "<age>30</age>" in xml_result
        assert "<city>New York</city>" in xml_result
        assert "<country>USA</country>" in xml_result
    
    def test_extract_xml_elements(self, transformer):
        """Test extracting specific XML elements."""
        xml_data = """
        <catalog>
            <book id="1">
                <title>Python Programming</title>
                <author>John Smith</author>
                <price>29.99</price>
            </book>
            <book id="2">
                <title>Web Development</title>
                <author>Jane Doe</author>
                <price>34.99</price>
            </book>
        </catalog>
        """
        
        # Extract all book titles
        titles = transformer.extract_elements(xml_data, "//book/title")
        assert len(titles) == 2
        assert "Python Programming" in titles
        assert "Web Development" in titles
        
        # Extract all authors
        authors = transformer.extract_elements(xml_data, "//book/author")
        assert len(authors) == 2
        assert "John Smith" in authors
        assert "Jane Doe" in authors
    
    def test_transform_xml_attributes(self, transformer):
        """Test transforming XML attributes."""
        xml_data = """
        <products>
            <product id="1" category="electronics">
                <name>Laptop</name>
                <price currency="USD">999.99</price>
            </product>
            <product id="2" category="books">
                <name>Python Guide</name>
                <price currency="USD">29.99</price>
            </product>
        </products>
        """
        
        # Transform to include attributes in the data
        result = transformer.xml_to_dict(xml_data, include_attributes=True)
        
        products = result["products"]["product"]
        assert products[0]["@id"] == "1"
        assert products[0]["@category"] == "electronics"
        assert products[0]["price"]["@currency"] == "USD"


class TestHTMLTransformer:
    """Test HTML transformer functionality."""
    
    @pytest.fixture
    def transformer(self):
        """Create HTML transformer."""
        return HTMLTransformer()
    
    def test_extract_text(self, transformer):
        """Test extracting text from HTML."""
        html_data = """
        <html>
            <body>
                <h1>Main Title</h1>
                <p>This is a paragraph with <strong>bold text</strong>.</p>
                <ul>
                    <li>Item 1</li>
                    <li>Item 2</li>
                </ul>
            </body>
        </html>
        """
        
        text = transformer.extract_text(html_data)
        
        assert "Main Title" in text
        assert "This is a paragraph with bold text." in text
        assert "Item 1" in text
        assert "Item 2" in text
        assert "<h1>" not in text  # HTML tags should be removed
    
    def test_extract_links(self, transformer):
        """Test extracting links from HTML."""
        html_data = """
        <html>
            <body>
                <a href="https://example.com">Example</a>
                <a href="/internal/page">Internal Link</a>
                <a href="mailto:contact@example.com">Contact</a>
            </body>
        </html>
        """
        
        links = transformer.extract_links(html_data)
        
        assert len(links) == 3
        assert {"url": "https://example.com", "text": "Example"} in links
        assert {"url": "/internal/page", "text": "Internal Link"} in links
        assert {"url": "mailto:contact@example.com", "text": "Contact"} in links
    
    def test_extract_images(self, transformer):
        """Test extracting images from HTML."""
        html_data = """
        <html>
            <body>
                <img src="image1.jpg" alt="First Image" width="100">
                <img src="https://example.com/image2.png" alt="Second Image">
                <img src="image3.gif">
            </body>
        </html>
        """
        
        images = transformer.extract_images(html_data)
        
        assert len(images) == 3
        assert {"src": "image1.jpg", "alt": "First Image", "width": "100"} in images
        assert {"src": "https://example.com/image2.png", "alt": "Second Image"} in images
        assert {"src": "image3.gif"} in images
    
    def test_extract_tables(self, transformer):
        """Test extracting tables from HTML."""
        html_data = """
        <html>
            <body>
                <table>
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Age</th>
                            <th>City</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>John</td>
                            <td>30</td>
                            <td>NYC</td>
                        </tr>
                        <tr>
                            <td>Jane</td>
                            <td>25</td>
                            <td>LA</td>
                        </tr>
                    </tbody>
                </table>
            </body>
        </html>
        """
        
        tables = transformer.extract_tables(html_data)
        
        assert len(tables) == 1
        table = tables[0]
        
        assert table["headers"] == ["Name", "Age", "City"]
        assert len(table["rows"]) == 2
        assert table["rows"][0] == ["John", "30", "NYC"]
        assert table["rows"][1] == ["Jane", "25", "LA"]


class TestTextTransformer:
    """Test text transformer functionality."""
    
    @pytest.fixture
    def transformer(self):
        """Create text transformer."""
        return TextTransformer()
    
    def test_clean_text(self, transformer):
        """Test cleaning text content."""
        dirty_text = "  This is   a test\n\nwith   extra   spaces\t\tand\nnewlines.  "
        
        cleaned = transformer.clean_text(dirty_text)
        
        assert cleaned == "This is a test with extra spaces and newlines."
    
    def test_extract_emails(self, transformer):
        """Test extracting email addresses from text."""
        text = """
        Contact us at support@example.com or sales@company.org.
        You can also reach john.doe@domain.co.uk for technical issues.
        Invalid emails like @invalid.com or user@ should be ignored.
        """
        
        emails = transformer.extract_emails(text)
        
        assert len(emails) == 3
        assert "support@example.com" in emails
        assert "sales@company.org" in emails
        assert "john.doe@domain.co.uk" in emails
    
    def test_extract_urls(self, transformer):
        """Test extracting URLs from text."""
        text = """
        Visit our website at https://example.com or check out
        http://blog.example.com/post for more information.
        FTP files are available at ftp://files.example.com/downloads.
        """
        
        urls = transformer.extract_urls(text)
        
        assert len(urls) == 3
        assert "https://example.com" in urls
        assert "http://blog.example.com/post" in urls
        assert "ftp://files.example.com/downloads" in urls
    
    def test_extract_phone_numbers(self, transformer):
        """Test extracting phone numbers from text."""
        text = """
        Call us at (555) 123-4567 or +1-800-555-0199.
        International: +44 20 7946 0958
        Simple format: 555.123.4567
        """
        
        phones = transformer.extract_phone_numbers(text)
        
        assert len(phones) >= 3  # May extract more depending on regex
        assert "(555) 123-4567" in phones
        assert "+1-800-555-0199" in phones
        assert "+44 20 7946 0958" in phones
    
    def test_tokenize_text(self, transformer):
        """Test text tokenization."""
        text = "This is a sample text for tokenization testing."
        
        tokens = transformer.tokenize(text)
        
        expected_tokens = ["This", "is", "a", "sample", "text", "for", "tokenization", "testing"]
        assert tokens == expected_tokens
    
    def test_remove_stopwords(self, transformer):
        """Test removing stopwords from text."""
        text = "This is a sample text with common stopwords that should be removed."
        
        filtered = transformer.remove_stopwords(text)
        
        # Should remove common stopwords like "is", "a", "with", "that", "be"
        assert "sample" in filtered
        assert "text" in filtered
        assert "common" in filtered
        assert "stopwords" in filtered
        assert "removed" in filtered
        # Stopwords should be removed
        assert " is " not in filtered
        assert " a " not in filtered


class TestTransformationPipeline:
    """Test transformation pipeline functionality."""
    
    @pytest.fixture
    def pipeline(self):
        """Create transformation pipeline."""
        return TransformationPipeline()
    
    def test_add_transformation_steps(self, pipeline):
        """Test adding transformation steps to pipeline."""
        def step1(data):
            data["step1_applied"] = True
            return data
        
        def step2(data):
            data["step2_applied"] = True
            return data
        
        pipeline.add_step("step1", step1)
        pipeline.add_step("step2", step2)
        
        assert len(pipeline.steps) == 2
        assert pipeline.steps[0].name == "step1"
        assert pipeline.steps[1].name == "step2"
    
    def test_execute_pipeline(self, pipeline):
        """Test executing transformation pipeline."""
        def uppercase_name(data):
            if "name" in data:
                data["name"] = data["name"].upper()
            return data
        
        def add_processed_flag(data):
            data["processed"] = True
            return data
        
        pipeline.add_step("uppercase", uppercase_name)
        pipeline.add_step("add_flag", add_processed_flag)
        
        input_data = {"name": "john doe", "age": 30}
        result = pipeline.execute(input_data)
        
        assert result.success is True
        assert result.transformed_data["name"] == "JOHN DOE"
        assert result.transformed_data["age"] == 30
        assert result.transformed_data["processed"] is True
    
    def test_pipeline_error_handling(self, pipeline):
        """Test pipeline error handling."""
        def working_step(data):
            data["working"] = True
            return data
        
        def failing_step(data):
            raise ValueError("Step failed")
        
        pipeline.add_step("working", working_step)
        pipeline.add_step("failing", failing_step)
        
        input_data = {"test": "data"}
        result = pipeline.execute(input_data)
        
        assert result.success is False
        assert "Step failed" in result.error
    
    def test_conditional_pipeline_steps(self, pipeline):
        """Test conditional pipeline steps."""
        def add_admin_flag(data):
            data["is_admin"] = True
            return data
        
        def is_admin_user(data):
            return data.get("role") == "admin"
        
        step = TransformationStep(
            name="admin_flag",
            transform_func=add_admin_flag,
            condition=is_admin_user
        )
        
        pipeline.add_step_object(step)
        
        # Should apply for admin user
        admin_data = {"name": "Admin User", "role": "admin"}
        result = pipeline.execute(admin_data)
        assert result.transformed_data["is_admin"] is True
        
        # Should not apply for regular user
        user_data = {"name": "Regular User", "role": "user"}
        result = pipeline.execute(user_data)
        assert "is_admin" not in result.transformed_data
