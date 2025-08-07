"""
Comprehensive tests for the parsers module.
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import BytesIO

from web_fetch.parsers import (
    PDFParser,
    ImageParser,
    FeedParser,
    CSVParser,
    JSONParser,
    MarkdownConverter,
    ContentAnalyzer,
    LinkExtractor,
    EnhancedContentParser,
)
from web_fetch.models.base import (
    PDFMetadata,
    ImageMetadata,
    FeedMetadata,
    CSVMetadata,
    ContentSummary,
    LinkInfo,
    ContentType,
)
from web_fetch.models.http import FetchResult
from web_fetch.exceptions import ContentError


class TestPDFParser:
    """Test PDF parser."""

    @pytest.mark.skipif(not hasattr(PDFParser, '_has_pypdf') or not PDFParser._has_pypdf,
                       reason="pypdf not available")
    def test_parse_pdf_content(self):
        """Test parsing PDF content."""
        parser = PDFParser()

        # Mock PDF content
        mock_pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj"

        with patch('pypdf.PdfReader') as mock_reader:
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Sample PDF text content"
            
            mock_pdf = MagicMock()
            mock_pdf.pages = [mock_page]
            mock_pdf.metadata = {
                '/Title': 'Test PDF',
                '/Author': 'Test Author',
                '/CreationDate': 'D:20230101120000'
            }
            mock_reader.return_value = mock_pdf
            
            text, metadata = parser.parse(mock_pdf_content)
            
            assert text == "Sample PDF text content"
            assert isinstance(metadata, PDFMetadata)
            assert metadata.title == "Test PDF"
            assert metadata.author == "Test Author"
            assert metadata.page_count == 1

    def test_parse_invalid_pdf(self):
        """Test parsing invalid PDF content."""
        parser = PDFParser()
        
        invalid_content = b"This is not a PDF file"
        
        with pytest.raises(ContentError):
            parser.parse(invalid_content)

    def test_parse_empty_pdf(self):
        """Test parsing empty PDF content."""
        parser = PDFParser()
        
        with pytest.raises(ContentError):
            parser.parse(b"")


class TestImageParser:
    """Test image parser."""

    @pytest.mark.skipif(not hasattr(ImageParser, '_has_pil') or not ImageParser._has_pil,
                       reason="PIL not available")
    def test_parse_image_metadata(self):
        """Test parsing image metadata."""
        parser = ImageParser()
        
        # Create a simple test image
        from PIL import Image
        
        # Create a small test image
        img = Image.new('RGB', (100, 50), color='red')
        
        # Save to bytes
        img_bytes = BytesIO()
        img.save(img_bytes, format='JPEG')
        img_content = img_bytes.getvalue()
        
        metadata = parser.parse(img_content)
        
        assert isinstance(metadata, ImageMetadata)
        assert metadata.width == 100
        assert metadata.height == 50
        assert metadata.format == "JPEG"
        assert metadata.mode == "RGB"

    def test_parse_invalid_image(self):
        """Test parsing invalid image content."""
        parser = ImageParser()
        
        invalid_content = b"This is not an image file"
        
        with pytest.raises(ContentError):
            parser.parse(invalid_content)

    def test_parse_image_with_exif(self):
        """Test parsing image with EXIF data."""
        parser = ImageParser()
        
        # Mock image with EXIF data
        with patch('PIL.Image.open') as mock_open:
            mock_img = MagicMock()
            mock_img.size = (1920, 1080)
            mock_img.format = "JPEG"
            mock_img.mode = "RGB"
            
            # Mock EXIF data
            mock_exif = {
                'Make': 'Test Camera',
                'Model': 'Test Model',
                'DateTime': '2023:01:01 12:00:00'
            }
            mock_img._getexif.return_value = {
                271: 'Test Camera',  # Make
                272: 'Test Model',   # Model
                306: '2023:01:01 12:00:00'  # DateTime
            }
            mock_open.return_value = mock_img
            
            metadata = parser.parse(b"fake_image_content")
            
            assert metadata.width == 1920
            assert metadata.height == 1080
            assert 'Make' in metadata.exif_data
            assert metadata.exif_data['Make'] == 'Test Camera'


class TestFeedParser:
    """Test feed parser."""

    @pytest.mark.skipif(not hasattr(FeedParser, '_has_feedparser') or not FeedParser._has_feedparser,
                       reason="feedparser not available")
    def test_parse_rss_feed(self):
        """Test parsing RSS feed."""
        parser = FeedParser()
        
        rss_content = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <description>A test RSS feed</description>
                <link>https://example.com</link>
                <item>
                    <title>Test Article 1</title>
                    <description>First test article</description>
                    <link>https://example.com/article1</link>
                    <pubDate>Mon, 01 Jan 2023 12:00:00 GMT</pubDate>
                </item>
                <item>
                    <title>Test Article 2</title>
                    <description>Second test article</description>
                    <link>https://example.com/article2</link>
                    <pubDate>Tue, 02 Jan 2023 12:00:00 GMT</pubDate>
                </item>
            </channel>
        </rss>"""
        
        with patch('feedparser.parse') as mock_parse:
            mock_feed = MagicMock()
            mock_feed.feed.title = "Test Feed"
            mock_feed.feed.description = "A test RSS feed"
            mock_feed.feed.link = "https://example.com"
            
            mock_entry1 = MagicMock()
            mock_entry1.title = "Test Article 1"
            mock_entry1.description = "First test article"
            mock_entry1.link = "https://example.com/article1"
            mock_entry1.published = "Mon, 01 Jan 2023 12:00:00 GMT"
            
            mock_entry2 = MagicMock()
            mock_entry2.title = "Test Article 2"
            mock_entry2.description = "Second test article"
            mock_entry2.link = "https://example.com/article2"
            mock_entry2.published = "Tue, 02 Jan 2023 12:00:00 GMT"
            
            mock_feed.entries = [mock_entry1, mock_entry2]
            mock_parse.return_value = mock_feed
            
            metadata = parser.parse(rss_content)
            
            assert isinstance(metadata, FeedMetadata)
            assert metadata.title == "Test Feed"
            assert metadata.description == "A test RSS feed"
            assert len(metadata.items) == 2
            assert metadata.items[0].title == "Test Article 1"

    def test_parse_invalid_feed(self):
        """Test parsing invalid feed content."""
        parser = FeedParser()
        
        invalid_content = "This is not a valid feed"
        
        with pytest.raises(ContentError):
            parser.parse(invalid_content)


class TestCSVParser:
    """Test CSV parser."""

    def test_parse_csv_content(self):
        """Test parsing CSV content."""
        parser = CSVParser()
        
        csv_content = """name,age,city
John,25,New York
Jane,30,Los Angeles
Bob,35,Chicago"""
        
        data, metadata = parser.parse(csv_content)
        
        assert isinstance(data, list)
        assert len(data) == 3
        assert data[0] == {"name": "John", "age": "25", "city": "New York"}
        
        assert isinstance(metadata, CSVMetadata)
        assert metadata.columns == ["name", "age", "city"]
        assert metadata.row_count == 3
        assert metadata.delimiter == ","

    def test_parse_csv_with_custom_delimiter(self):
        """Test parsing CSV with custom delimiter."""
        parser = CSVParser()
        
        csv_content = """name;age;city
John;25;New York
Jane;30;Los Angeles"""
        
        data, metadata = parser.parse(csv_content, delimiter=';')
        
        assert len(data) == 2
        assert data[0] == {"name": "John", "age": "25", "city": "New York"}
        assert metadata.delimiter == ";"

    def test_parse_csv_with_encoding_detection(self):
        """Test parsing CSV with encoding detection."""
        parser = CSVParser()
        
        # CSV content with special characters
        csv_content = "name,description\nJohn,Café owner\nJane,Naïve user"
        
        data, metadata = parser.parse(csv_content)
        
        assert len(data) == 2
        assert "Café" in data[0]["description"]

    @pytest.mark.skipif(not hasattr(CSVParser, '_has_pandas') or not CSVParser._has_pandas,
                       reason="pandas not available")
    def test_parse_csv_with_pandas(self):
        """Test parsing CSV using pandas."""
        parser = CSVParser()
        
        csv_content = """name,age,salary
John,25,50000.5
Jane,30,60000.0
Bob,35,70000.25"""
        
        with patch('pandas.read_csv') as mock_read_csv:
            import pandas as pd
            
            # Mock pandas DataFrame
            mock_df = pd.DataFrame({
                'name': ['John', 'Jane', 'Bob'],
                'age': [25, 30, 35],
                'salary': [50000.5, 60000.0, 70000.25]
            })
            mock_read_csv.return_value = mock_df
            
            data, metadata = parser.parse_with_pandas(csv_content)
            
            assert isinstance(data, list)
            assert len(data) == 3
            assert metadata.has_numeric_data is True


class TestJSONParser:
    """Test JSON parser."""

    def test_parse_json_object(self):
        """Test parsing JSON object."""
        parser = JSONParser()
        
        json_content = '{"name": "John", "age": 25, "active": true}'
        
        data = parser.parse(json_content)
        
        assert isinstance(data, dict)
        assert data["name"] == "John"
        assert data["age"] == 25
        assert data["active"] is True

    def test_parse_json_array(self):
        """Test parsing JSON array."""
        parser = JSONParser()
        
        json_content = '[{"id": 1, "name": "John"}, {"id": 2, "name": "Jane"}]'
        
        data = parser.parse(json_content)
        
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["name"] == "John"
        assert data[1]["name"] == "Jane"

    def test_parse_nested_json(self):
        """Test parsing nested JSON."""
        parser = JSONParser()
        
        json_content = '''
        {
            "user": {
                "id": 123,
                "profile": {
                    "name": "John Doe",
                    "preferences": ["dark_mode", "notifications"]
                }
            },
            "metadata": {
                "created": "2023-01-01",
                "version": "1.0"
            }
        }
        '''
        
        data = parser.parse(json_content)
        
        assert data["user"]["id"] == 123
        assert data["user"]["profile"]["name"] == "John Doe"
        assert "dark_mode" in data["user"]["profile"]["preferences"]

    def test_parse_invalid_json(self):
        """Test parsing invalid JSON."""
        parser = JSONParser()
        
        invalid_json = '{"name": "John", "age": 25'  # Missing closing brace
        
        with pytest.raises(ContentError):
            parser.parse(invalid_json)

    def test_extract_json_paths(self):
        """Test extracting values using JSON paths."""
        parser = JSONParser()
        
        json_content = '''
        {
            "users": [
                {"name": "John", "age": 25},
                {"name": "Jane", "age": 30}
            ],
            "metadata": {"total": 2}
        }
        '''
        
        data = parser.parse(json_content)
        
        # Extract using simple paths
        names = parser.extract_path(data, "users[*].name")
        assert "John" in names
        assert "Jane" in names
        
        total = parser.extract_path(data, "metadata.total")
        assert total == 2


class TestMarkdownConverter:
    """Test markdown converter."""

    def test_html_to_markdown_basic(self):
        """Test basic HTML to markdown conversion."""
        converter = MarkdownConverter()
        
        html_content = """
        <h1>Main Title</h1>
        <p>This is a paragraph with <strong>bold text</strong> and <em>italic text</em>.</p>
        <ul>
            <li>First item</li>
            <li>Second item</li>
        </ul>
        """
        
        markdown = converter.html_to_markdown(html_content)
        
        assert "# Main Title" in markdown
        assert "**bold text**" in markdown or "__bold text__" in markdown
        assert "*italic text*" in markdown or "_italic text_" in markdown
        assert "- First item" in markdown or "* First item" in markdown

    def test_html_to_markdown_with_links(self):
        """Test HTML to markdown conversion with links."""
        converter = MarkdownConverter()
        
        html_content = '''
        <p>Visit <a href="https://example.com">our website</a> for more info.</p>
        <p>Check out <a href="https://github.com/user/repo">this repository</a>.</p>
        '''
        
        markdown = converter.html_to_markdown(html_content)
        
        assert "[our website](https://example.com)" in markdown
        assert "[this repository](https://github.com/user/repo)" in markdown

    def test_html_to_markdown_with_images(self):
        """Test HTML to markdown conversion with images."""
        converter = MarkdownConverter()
        
        html_content = '''
        <p>Here's an image:</p>
        <img src="https://example.com/image.jpg" alt="Test Image" title="A test image">
        '''
        
        markdown = converter.html_to_markdown(html_content)
        
        assert "![Test Image](https://example.com/image.jpg)" in markdown

    def test_html_to_markdown_preserve_structure(self):
        """Test that HTML structure is preserved in markdown."""
        converter = MarkdownConverter()
        
        html_content = """
        <article>
            <header>
                <h1>Article Title</h1>
                <p>By Author Name</p>
            </header>
            <section>
                <h2>Section 1</h2>
                <p>Section content here.</p>
            </section>
        </article>
        """
        
        markdown = converter.html_to_markdown(html_content)
        
        assert "# Article Title" in markdown
        assert "## Section 1" in markdown
        assert "By Author Name" in markdown


class TestContentAnalyzer:
    """Test content analyzer."""

    def test_analyze_text_content(self):
        """Test analyzing text content."""
        analyzer = ContentAnalyzer()
        
        text_content = """
        This is a sample article about web scraping and data analysis.
        Web scraping is the process of extracting data from websites.
        It involves making HTTP requests and parsing HTML content.
        Data analysis helps us understand patterns in the extracted data.
        """
        
        summary = analyzer.analyze(text_content)
        
        assert isinstance(summary, ContentSummary)
        assert summary.word_count > 0
        assert summary.character_count > 0
        assert len(summary.keywords) > 0
        assert "web" in [kw.lower() for kw in summary.keywords]

    @pytest.mark.skipif(not hasattr(ContentAnalyzer, '_has_nltk') or not ContentAnalyzer._has_nltk,
                       reason="NLTK not available")
    def test_analyze_with_nltk(self):
        """Test content analysis with NLTK."""
        analyzer = ContentAnalyzer()
        
        text_content = """
        Natural language processing is a fascinating field of study.
        It combines linguistics, computer science, and artificial intelligence.
        NLP techniques are used in many applications today.
        """
        
        with patch('nltk.tokenize.sent_tokenize') as mock_sent_tokenize:
            with patch('nltk.tokenize.word_tokenize') as mock_word_tokenize:
                mock_sent_tokenize.return_value = [
                    "Natural language processing is a fascinating field of study.",
                    "It combines linguistics, computer science, and artificial intelligence.",
                    "NLP techniques are used in many applications today."
                ]
                mock_word_tokenize.return_value = [
                    "Natural", "language", "processing", "is", "a", "fascinating",
                    "field", "of", "study", "It", "combines", "linguistics"
                ]
                
                summary = analyzer.analyze_with_nltk(text_content)
                
                assert summary.sentence_count == 3
                assert "natural" in [kw.lower() for kw in summary.keywords]

    def test_extract_keywords(self):
        """Test keyword extraction."""
        analyzer = ContentAnalyzer()
        
        text_content = """
        Machine learning algorithms are powerful tools for data analysis.
        These algorithms can learn patterns from data automatically.
        Popular machine learning techniques include neural networks and decision trees.
        """
        
        keywords = analyzer.extract_keywords(text_content, max_keywords=5)
        
        assert len(keywords) <= 5
        assert any("machine" in kw.lower() for kw in keywords)
        assert any("learning" in kw.lower() for kw in keywords)


class TestEnhancedContentParser:
    """Test enhanced content parser."""

    def test_parse_html_content(self):
        """Test parsing HTML content."""
        parser = EnhancedContentParser()
        
        fetch_result = FetchResult(
            url="https://example.com",
            content="<html><body><h1>Test Page</h1><p>Content here</p></body></html>",
            status_code=200,
            headers={"content-type": "text/html"},
            content_type="text/html"
        )
        
        parsed_content = parser.parse(fetch_result, ContentType.HTML)
        
        assert "Test Page" in parsed_content
        assert "Content here" in parsed_content

    def test_parse_json_content(self):
        """Test parsing JSON content."""
        parser = EnhancedContentParser()
        
        json_data = {"message": "Hello", "status": "success", "data": [1, 2, 3]}
        
        fetch_result = FetchResult(
            url="https://api.example.com/data",
            content=json.dumps(json_data),
            status_code=200,
            headers={"content-type": "application/json"},
            content_type="application/json"
        )
        
        parsed_content = parser.parse(fetch_result, ContentType.JSON)
        
        assert isinstance(parsed_content, dict)
        assert parsed_content["message"] == "Hello"
        assert parsed_content["data"] == [1, 2, 3]

    def test_auto_detect_content_type(self):
        """Test automatic content type detection."""
        parser = EnhancedContentParser()
        
        # HTML content
        html_result = FetchResult(
            url="https://example.com",
            content="<html><head><title>Test</title></head><body>Content</body></html>",
            status_code=200,
            headers={"content-type": "text/html"},
            content_type="text/html"
        )
        
        detected_type = parser.detect_content_type(html_result)
        assert detected_type == ContentType.HTML
        
        # JSON content
        json_result = FetchResult(
            url="https://api.example.com",
            content='{"key": "value"}',
            status_code=200,
            headers={"content-type": "application/json"},
            content_type="application/json"
        )
        
        detected_type = parser.detect_content_type(json_result)
        assert detected_type == ContentType.JSON
