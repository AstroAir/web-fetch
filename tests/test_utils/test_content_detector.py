"""
Comprehensive tests for the content detector utility.
"""

import pytest
from unittest.mock import patch, MagicMock

from web_fetch.utils.content_detector import (
    ContentDetector,
    ContentTypeDetector,
    EncodingDetector,
    LanguageDetector,
    ContentMetadata,
    DetectionResult,
)
from web_fetch.models.base import ContentType


class TestContentTypeDetector:
    """Test content type detection functionality."""
    
    def test_detect_from_headers(self):
        """Test content type detection from HTTP headers."""
        detector = ContentTypeDetector()
        
        test_cases = [
            ({"content-type": "application/json"}, ContentType.JSON),
            ({"content-type": "text/html; charset=utf-8"}, ContentType.HTML),
            ({"Content-Type": "application/xml"}, ContentType.XML),
            ({"CONTENT-TYPE": "text/plain"}, ContentType.TEXT),
            ({"content-type": "image/jpeg"}, ContentType.BINARY),
            ({"content-type": "application/pdf"}, ContentType.BINARY),
        ]
        
        for headers, expected in test_cases:
            result = detector.detect_from_headers(headers)
            assert result == expected
    
    def test_detect_from_url(self):
        """Test content type detection from URL extensions."""
        detector = ContentTypeDetector()
        
        test_cases = [
            ("https://example.com/data.json", ContentType.JSON),
            ("https://example.com/page.html", ContentType.HTML),
            ("https://example.com/document.xml", ContentType.XML),
            ("https://example.com/file.txt", ContentType.TEXT),
            ("https://example.com/image.jpg", ContentType.BINARY),
            ("https://example.com/document.pdf", ContentType.BINARY),
            ("https://example.com/archive.zip", ContentType.BINARY),
            ("https://example.com/unknown", ContentType.TEXT),  # Default
        ]
        
        for url, expected in test_cases:
            result = detector.detect_from_url(url)
            assert result == expected
    
    def test_detect_from_content(self):
        """Test content type detection from content analysis."""
        detector = ContentTypeDetector()
        
        test_cases = [
            ('{"key": "value"}', ContentType.JSON),
            ('[{"item": 1}, {"item": 2}]', ContentType.JSON),
            ("<html><body>Test</body></html>", ContentType.HTML),
            ("<!DOCTYPE html><html></html>", ContentType.HTML),
            ('<?xml version="1.0"?><root></root>', ContentType.XML),
            ("<root><item>test</item></root>", ContentType.XML),
            ("Plain text content", ContentType.TEXT),
            (b'\x89PNG\r\n\x1a\n', ContentType.BINARY),  # PNG header
            (b'\xff\xd8\xff\xe0', ContentType.BINARY),   # JPEG header
        ]
        
        for content, expected in test_cases:
            result = detector.detect_from_content(content)
            assert result == expected
    
    def test_detect_priority(self):
        """Test detection priority (headers > content > url)."""
        detector = ContentTypeDetector()
        
        # Headers should take priority
        result = detector.detect(
            headers={"content-type": "application/json"},
            url="https://example.com/file.xml",
            content="<html>test</html>"
        )
        assert result == ContentType.JSON
        
        # Content should take priority over URL
        result = detector.detect(
            url="https://example.com/file.xml",
            content='{"json": "data"}'
        )
        assert result == ContentType.JSON
        
        # URL as fallback
        result = detector.detect(url="https://example.com/file.xml")
        assert result == ContentType.XML
    
    def test_detect_with_confidence(self):
        """Test detection with confidence scores."""
        detector = ContentTypeDetector()
        
        # High confidence detection
        result = detector.detect_with_confidence(
            headers={"content-type": "application/json"},
            content='{"valid": "json"}'
        )
        
        assert result.content_type == ContentType.JSON
        assert result.confidence > 0.8
        assert result.source == "headers"
        
        # Lower confidence detection
        result = detector.detect_with_confidence(
            content="maybe json but not sure"
        )
        
        assert result.content_type == ContentType.TEXT
        assert result.confidence < 0.8


class TestEncodingDetector:
    """Test encoding detection functionality."""
    
    def test_detect_from_headers(self):
        """Test encoding detection from HTTP headers."""
        detector = EncodingDetector()
        
        test_cases = [
            ({"content-type": "text/html; charset=utf-8"}, "utf-8"),
            ({"content-type": "application/json; charset=iso-8859-1"}, "iso-8859-1"),
            ({"Content-Type": "text/plain; charset=windows-1252"}, "windows-1252"),
            ({"content-type": "text/html"}, None),  # No charset specified
        ]
        
        for headers, expected in test_cases:
            result = detector.detect_from_headers(headers)
            assert result == expected
    
    def test_detect_from_content(self):
        """Test encoding detection from content analysis."""
        detector = EncodingDetector()
        
        # UTF-8 content
        utf8_content = "Hello, 世界! 🌍".encode('utf-8')
        result = detector.detect_from_content(utf8_content)
        assert result in ["utf-8", "UTF-8"]
        
        # ASCII content
        ascii_content = b"Hello, World!"
        result = detector.detect_from_content(ascii_content)
        assert result in ["ascii", "ASCII", "utf-8", "UTF-8"]
    
    def test_detect_from_bom(self):
        """Test encoding detection from Byte Order Mark."""
        detector = EncodingDetector()
        
        # UTF-8 BOM
        utf8_bom_content = b'\xef\xbb\xbfHello, World!'
        result = detector.detect_from_bom(utf8_bom_content)
        assert result == "utf-8-sig"
        
        # UTF-16 LE BOM
        utf16_le_content = b'\xff\xfeH\x00e\x00l\x00l\x00o\x00'
        result = detector.detect_from_bom(utf16_le_content)
        assert result == "utf-16-le"
        
        # No BOM
        no_bom_content = b'Hello, World!'
        result = detector.detect_from_bom(no_bom_content)
        assert result is None
    
    @patch('chardet.detect')
    def test_detect_with_chardet(self, mock_chardet):
        """Test encoding detection using chardet library."""
        detector = EncodingDetector()
        
        # Mock chardet response
        mock_chardet.return_value = {
            'encoding': 'utf-8',
            'confidence': 0.99
        }
        
        content = b"Some binary content"
        result = detector.detect_from_content(content)
        
        assert result == "utf-8"
        mock_chardet.assert_called_once_with(content)
    
    def test_detect_priority(self):
        """Test encoding detection priority."""
        detector = EncodingDetector()
        
        # Headers should take priority
        result = detector.detect(
            headers={"content-type": "text/html; charset=iso-8859-1"},
            content=b'\xef\xbb\xbfHello'  # UTF-8 BOM
        )
        assert result == "iso-8859-1"
        
        # BOM should take priority over content analysis
        result = detector.detect(content=b'\xef\xbb\xbfHello')
        assert result == "utf-8-sig"


class TestLanguageDetector:
    """Test language detection functionality."""
    
    def test_detect_from_headers(self):
        """Test language detection from HTTP headers."""
        detector = LanguageDetector()
        
        test_cases = [
            ({"content-language": "en"}, "en"),
            ({"Content-Language": "en-US"}, "en-US"),
            ({"content-language": "fr, en"}, "fr"),  # First language
            ({}, None),  # No language header
        ]
        
        for headers, expected in test_cases:
            result = detector.detect_from_headers(headers)
            assert result == expected
    
    def test_detect_from_html(self):
        """Test language detection from HTML lang attribute."""
        detector = LanguageDetector()
        
        test_cases = [
            ('<html lang="en">', "en"),
            ('<html lang="fr-FR">', "fr-FR"),
            ('<HTML LANG="de">', "de"),  # Case insensitive
            ('<html>', None),  # No lang attribute
            ('Not HTML content', None),  # Not HTML
        ]
        
        for content, expected in test_cases:
            result = detector.detect_from_html(content)
            assert result == expected
    
    @patch('langdetect.detect')
    def test_detect_from_content(self, mock_langdetect):
        """Test language detection from content analysis."""
        detector = LanguageDetector()
        
        # Mock langdetect response
        mock_langdetect.return_value = "en"
        
        content = "This is English text content."
        result = detector.detect_from_content(content)
        
        assert result == "en"
        mock_langdetect.assert_called_once_with(content)
    
    @patch('langdetect.detect')
    def test_detect_from_content_error_handling(self, mock_langdetect):
        """Test error handling in content language detection."""
        detector = LanguageDetector()
        
        # Mock langdetect to raise exception
        mock_langdetect.side_effect = Exception("Detection failed")
        
        content = "Short text"
        result = detector.detect_from_content(content)
        
        assert result is None  # Should handle errors gracefully


class TestContentDetector:
    """Test main content detector functionality."""
    
    @pytest.fixture
    def detector(self):
        """Create content detector instance."""
        return ContentDetector()
    
    def test_analyze_comprehensive(self, detector):
        """Test comprehensive content analysis."""
        headers = {
            "content-type": "text/html; charset=utf-8",
            "content-language": "en-US"
        }
        content = '<html lang="en"><body><h1>Hello, World!</h1></body></html>'
        url = "https://example.com/page.html"
        
        result = detector.analyze(headers=headers, content=content, url=url)
        
        assert isinstance(result, ContentMetadata)
        assert result.content_type == ContentType.HTML
        assert result.encoding == "utf-8"
        assert result.language == "en-US"
        assert result.size == len(content)
        assert result.url == url
    
    def test_analyze_binary_content(self, detector):
        """Test analysis of binary content."""
        headers = {"content-type": "image/jpeg"}
        content = b'\xff\xd8\xff\xe0\x00\x10JFIF'  # JPEG header
        
        result = detector.analyze(headers=headers, content=content)
        
        assert result.content_type == ContentType.BINARY
        assert result.encoding is None  # Binary content has no encoding
        assert result.size == len(content)
        assert result.is_binary is True
    
    def test_analyze_json_content(self, detector):
        """Test analysis of JSON content."""
        headers = {"content-type": "application/json; charset=utf-8"}
        content = '{"message": "Hello, World!", "count": 42}'
        
        result = detector.analyze(headers=headers, content=content)
        
        assert result.content_type == ContentType.JSON
        assert result.encoding == "utf-8"
        assert result.is_structured is True
        assert result.is_text is True
    
    def test_analyze_with_detection_options(self, detector):
        """Test analysis with custom detection options."""
        content = "This is plain text content."
        
        # Disable language detection
        result = detector.analyze(
            content=content,
            detect_language=False
        )
        
        assert result.language is None
        
        # Enable detailed analysis
        result = detector.analyze(
            content=content,
            detailed_analysis=True
        )
        
        assert hasattr(result, 'word_count')
        assert hasattr(result, 'line_count')
    
    def test_get_content_summary(self, detector):
        """Test content summary generation."""
        content = "This is a test document with multiple sentences. It contains various information."
        
        summary = detector.get_content_summary(content, max_length=50)
        
        assert len(summary) <= 50
        assert isinstance(summary, str)
        assert len(summary) > 0
    
    def test_is_content_type(self, detector):
        """Test content type checking utilities."""
        # Test JSON detection
        json_content = '{"key": "value"}'
        assert detector.is_json(json_content) is True
        assert detector.is_html(json_content) is False
        
        # Test HTML detection
        html_content = '<html><body>Test</body></html>'
        assert detector.is_html(html_content) is True
        assert detector.is_json(html_content) is False
        
        # Test XML detection
        xml_content = '<?xml version="1.0"?><root></root>'
        assert detector.is_xml(xml_content) is True
        assert detector.is_html(xml_content) is False


class TestDetectionResult:
    """Test detection result model."""
    
    def test_detection_result_creation(self):
        """Test detection result creation."""
        result = DetectionResult(
            content_type=ContentType.JSON,
            confidence=0.95,
            source="headers"
        )
        
        assert result.content_type == ContentType.JSON
        assert result.confidence == 0.95
        assert result.source == "headers"
    
    def test_detection_result_comparison(self):
        """Test detection result comparison."""
        result1 = DetectionResult(ContentType.JSON, 0.9, "headers")
        result2 = DetectionResult(ContentType.JSON, 0.8, "content")
        result3 = DetectionResult(ContentType.HTML, 0.9, "headers")
        
        # Same content type, higher confidence should be better
        assert result1 > result2
        
        # Different content types
        assert result1 != result3


class TestContentMetadata:
    """Test content metadata model."""
    
    def test_content_metadata_creation(self):
        """Test content metadata creation."""
        metadata = ContentMetadata(
            content_type=ContentType.HTML,
            encoding="utf-8",
            language="en",
            size=1024,
            url="https://example.com"
        )
        
        assert metadata.content_type == ContentType.HTML
        assert metadata.encoding == "utf-8"
        assert metadata.language == "en"
        assert metadata.size == 1024
        assert metadata.url == "https://example.com"
    
    def test_content_metadata_properties(self):
        """Test content metadata computed properties."""
        # Text content
        text_metadata = ContentMetadata(content_type=ContentType.HTML)
        assert text_metadata.is_text is True
        assert text_metadata.is_binary is False
        assert text_metadata.is_structured is True
        
        # Binary content
        binary_metadata = ContentMetadata(content_type=ContentType.BINARY)
        assert binary_metadata.is_text is False
        assert binary_metadata.is_binary is True
        assert binary_metadata.is_structured is False
    
    def test_content_metadata_serialization(self):
        """Test content metadata serialization."""
        metadata = ContentMetadata(
            content_type=ContentType.JSON,
            encoding="utf-8",
            size=512
        )
        
        data = metadata.to_dict()
        
        assert data["content_type"] == "JSON"
        assert data["encoding"] == "utf-8"
        assert data["size"] == 512
        assert "is_text" in data
        assert "is_binary" in data
