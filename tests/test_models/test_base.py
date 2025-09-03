"""
Comprehensive tests for base models in web_fetch.models.base module.

Tests all dataclasses, enums, and base classes defined in the base module.
"""

import pytest
from datetime import datetime, timedelta
from dataclasses import FrozenInstanceError

from web_fetch.models.base import (
    ContentType,
    RetryStrategy,
    RequestHeaders,
    ProgressInfo,
    BaseConfig,
    BaseResult,
    PDFMetadata,
    ImageMetadata,
    FeedMetadata,
    FeedItem,
    CSVMetadata,
    LinkInfo,
    ContentSummary,
)


class TestContentType:
    """Test ContentType enumeration."""

    def test_all_content_types(self):
        """Test all content type values."""
        assert ContentType.RAW == "raw"
        assert ContentType.JSON == "json"
        assert ContentType.HTML == "html"
        assert ContentType.TEXT == "text"
        assert ContentType.PDF == "pdf"
        assert ContentType.IMAGE == "image"
        assert ContentType.RSS == "rss"
        assert ContentType.CSV == "csv"
        assert ContentType.MARKDOWN == "markdown"
        assert ContentType.XML == "xml"

    def test_content_type_string_behavior(self):
        """Test that ContentType behaves as string."""
        content_type = ContentType.JSON
        assert str(content_type) == "json"
        assert content_type == "json"
        assert content_type in ["json", "html", "text"]


class TestRetryStrategy:
    """Test RetryStrategy enumeration."""

    def test_all_retry_strategies(self):
        """Test all retry strategy values."""
        assert RetryStrategy.NONE == "none"
        assert RetryStrategy.LINEAR == "linear"
        assert RetryStrategy.EXPONENTIAL == "exponential"

    def test_retry_strategy_string_behavior(self):
        """Test that RetryStrategy behaves as string."""
        strategy = RetryStrategy.EXPONENTIAL
        assert str(strategy) == "exponential"
        assert strategy == "exponential"


class TestRequestHeaders:
    """Test RequestHeaders dataclass."""

    def test_default_headers(self):
        """Test default header values."""
        headers = RequestHeaders()
        assert "Mozilla/5.0" in headers.user_agent
        assert "Chrome" in headers.user_agent
        assert headers.accept == "*/*"
        assert headers.accept_language == "en-US,en;q=0.9"
        assert headers.accept_encoding == "gzip, deflate, br"
        assert headers.connection == "keep-alive"
        assert headers.custom_headers == {}

    def test_custom_headers(self):
        """Test custom headers."""
        custom = {"X-API-Key": "test-key", "Authorization": "Bearer token"}
        headers = RequestHeaders(custom_headers=custom)
        assert headers.custom_headers == custom

    def test_to_dict(self):
        """Test conversion to dictionary."""
        custom = {"X-Custom": "value"}
        headers = RequestHeaders(
            user_agent="Test Agent",
            accept="application/json",
            custom_headers=custom
        )

        header_dict = headers.to_dict()
        assert header_dict["User-Agent"] == "Test Agent"
        assert header_dict["Accept"] == "application/json"
        assert header_dict["X-Custom"] == "value"
        assert "Accept-Language" in header_dict
        assert "Accept-Encoding" in header_dict
        assert "Connection" in header_dict

    def test_immutable(self):
        """Test that RequestHeaders is immutable."""
        headers = RequestHeaders()
        with pytest.raises(FrozenInstanceError):
            headers.user_agent = "new-agent"

        with pytest.raises(FrozenInstanceError):
            headers.custom_headers["new"] = "value"

    def test_custom_headers_override(self):
        """Test that custom headers can override defaults."""
        custom = {"User-Agent": "Custom Agent", "Accept": "text/html"}
        headers = RequestHeaders(custom_headers=custom)

        header_dict = headers.to_dict()
        # Custom headers should override defaults
        assert header_dict["User-Agent"] == "Custom Agent"
        assert header_dict["Accept"] == "text/html"


class TestProgressInfo:
    """Test ProgressInfo dataclass."""

    def test_default_values(self):
        """Test default progress info values."""
        progress = ProgressInfo()
        assert progress.bytes_downloaded == 0
        assert progress.total_bytes is None
        assert progress.chunk_count == 0
        assert progress.elapsed_time == 0.0
        assert progress.download_speed == 0.0
        assert progress.eta is None
        assert progress.percentage is None

    def test_is_complete_unknown_total(self):
        """Test completion check with unknown total."""
        progress = ProgressInfo(bytes_downloaded=1000)
        assert progress.is_complete is False

    def test_is_complete_known_total(self):
        """Test completion check with known total."""
        # Not complete
        progress = ProgressInfo(bytes_downloaded=500, total_bytes=1000)
        assert progress.is_complete is False

        # Complete
        progress = ProgressInfo(bytes_downloaded=1000, total_bytes=1000)
        assert progress.is_complete is True

        # Over complete (edge case)
        progress = ProgressInfo(bytes_downloaded=1200, total_bytes=1000)
        assert progress.is_complete is True

    def test_speed_human_bytes(self):
        """Test human-readable speed for bytes per second."""
        progress = ProgressInfo(download_speed=512.5)
        assert progress.speed_human == "512.5 B/s"

    def test_speed_human_kilobytes(self):
        """Test human-readable speed for kilobytes per second."""
        progress = ProgressInfo(download_speed=1536.0)  # 1.5 KB/s
        assert progress.speed_human == "1.5 KB/s"

        progress = ProgressInfo(download_speed=1024 * 500)  # 500 KB/s
        assert progress.speed_human == "500.0 KB/s"

    def test_speed_human_megabytes(self):
        """Test human-readable speed for megabytes per second."""
        progress = ProgressInfo(download_speed=1024 * 1024 * 2.5)  # 2.5 MB/s
        assert progress.speed_human == "2.5 MB/s"

        progress = ProgressInfo(download_speed=1024 * 1024 * 100)  # 100 MB/s
        assert progress.speed_human == "100.0 MB/s"


class TestBaseConfig:
    """Test BaseConfig base class."""

    def test_config_settings(self):
        """Test that BaseConfig has correct Pydantic settings."""
        config = BaseConfig()

        # Check that the model config is set correctly
        assert config.model_config.use_enum_values is True
        assert config.model_config.validate_assignment is True
        assert config.model_config.extra == "forbid"


class TestBaseResult:
    """Test BaseResult dataclass."""

    def test_default_values(self):
        """Test default result values."""
        result = BaseResult(url="https://example.com")
        assert result.url == "https://example.com"
        assert isinstance(result.timestamp, datetime)
        assert result.response_time == 0.0
        assert result.error is None
        assert result.retry_count == 0

    def test_custom_values(self):
        """Test custom result values."""
        timestamp = datetime.now()
        result = BaseResult(
            url="https://api.example.com",
            timestamp=timestamp,
            response_time=1.5,
            error="Connection timeout",
            retry_count=2
        )
        assert result.url == "https://api.example.com"
        assert result.timestamp == timestamp
        assert result.response_time == 1.5
        assert result.error == "Connection timeout"
        assert result.retry_count == 2


class TestPDFMetadata:
    """Test PDFMetadata dataclass."""

    def test_default_values(self):
        """Test default PDF metadata values."""
        metadata = PDFMetadata()
        assert metadata.title is None
        assert metadata.author is None
        assert metadata.subject is None
        assert metadata.creator is None
        assert metadata.producer is None
        assert metadata.creation_date is None
        assert metadata.modification_date is None
        assert metadata.page_count == 0
        assert metadata.encrypted is False
        assert metadata.text_length == 0
        assert metadata.language is None

    def test_custom_values(self):
        """Test custom PDF metadata values."""
        creation_date = datetime.now()
        modification_date = datetime.now() + timedelta(hours=1)

        metadata = PDFMetadata(
            title="Test Document",
            author="Test Author",
            subject="Test Subject",
            creator="Test Creator",
            producer="Test Producer",
            creation_date=creation_date,
            modification_date=modification_date,
            page_count=10,
            encrypted=True,
            text_length=5000,
            language="en"
        )

        assert metadata.title == "Test Document"
        assert metadata.author == "Test Author"
        assert metadata.subject == "Test Subject"
        assert metadata.creator == "Test Creator"
        assert metadata.producer == "Test Producer"
        assert metadata.creation_date == creation_date
        assert metadata.modification_date == modification_date
        assert metadata.page_count == 10
        assert metadata.encrypted is True
        assert metadata.text_length == 5000
        assert metadata.language == "en"


class TestImageMetadata:
    """Test ImageMetadata dataclass."""

    def test_default_values(self):
        """Test default image metadata values."""
        metadata = ImageMetadata()
        assert metadata.format is None
        assert metadata.mode is None
        assert metadata.width is None
        assert metadata.height is None
        assert metadata.file_size is None
        assert metadata.color_space is None
        assert metadata.has_transparency is False
        assert metadata.dpi is None
        assert metadata.exif_data == {}
        assert metadata.alt_text is None
        assert metadata.caption is None

    def test_custom_values(self):
        """Test custom image metadata values."""
        exif_data = {"Camera": "Canon", "ISO": 100}

        metadata = ImageMetadata(
            format="JPEG",
            mode="RGB",
            width=1920,
            height=1080,
            file_size=2048000,
            color_space="sRGB",
            has_transparency=True,
            dpi=(300, 300),
            exif_data=exif_data,
            alt_text="Test image",
            caption="A test image"
        )

        assert metadata.format == "JPEG"
        assert metadata.mode == "RGB"
        assert metadata.width == 1920
        assert metadata.height == 1080
        assert metadata.file_size == 2048000
        assert metadata.color_space == "sRGB"
        assert metadata.has_transparency is True
        assert metadata.dpi == (300, 300)
        assert metadata.exif_data == exif_data
        assert metadata.alt_text == "Test image"
        assert metadata.caption == "A test image"


class TestFeedMetadata:
    """Test FeedMetadata dataclass."""

    def test_default_values(self):
        """Test default feed metadata values."""
        metadata = FeedMetadata()
        assert metadata.title is None
        assert metadata.description is None
        assert metadata.link is None
        assert metadata.language is None
        assert metadata.copyright is None
        assert metadata.managing_editor is None
        assert metadata.web_master is None
        assert metadata.pub_date is None
        assert metadata.last_build_date is None
        assert metadata.category is None
        assert metadata.generator is None
        assert metadata.docs is None
        assert metadata.ttl is None
        assert metadata.image is None
        assert metadata.feed_type is None
        assert metadata.version is None
        assert metadata.item_count == 0

    def test_custom_values(self):
        """Test custom feed metadata values."""
        pub_date = datetime.now()
        last_build_date = datetime.now() + timedelta(hours=1)
        image = {"url": "https://example.com/image.png", "title": "Feed Image"}

        metadata = FeedMetadata(
            title="Test Feed",
            description="A test RSS feed",
            link="https://example.com",
            language="en-US",
            copyright="© 2024 Test",
            managing_editor="editor@example.com",
            web_master="webmaster@example.com",
            pub_date=pub_date,
            last_build_date=last_build_date,
            category="Technology",
            generator="Test Generator",
            docs="https://example.com/docs",
            ttl=60,
            image=image,
            feed_type="RSS",
            version="2.0",
            item_count=25
        )

        assert metadata.title == "Test Feed"
        assert metadata.description == "A test RSS feed"
        assert metadata.link == "https://example.com"
        assert metadata.language == "en-US"
        assert metadata.copyright == "© 2024 Test"
        assert metadata.managing_editor == "editor@example.com"
        assert metadata.web_master == "webmaster@example.com"
        assert metadata.pub_date == pub_date
        assert metadata.last_build_date == last_build_date
        assert metadata.category == "Technology"
        assert metadata.generator == "Test Generator"
        assert metadata.docs == "https://example.com/docs"
        assert metadata.ttl == 60
        assert metadata.image == image
        assert metadata.feed_type == "RSS"
        assert metadata.version == "2.0"
        assert metadata.item_count == 25


class TestFeedItem:
    """Test FeedItem dataclass."""

    def test_default_values(self):
        """Test default feed item values."""
        item = FeedItem()
        assert item.title is None
        assert item.description is None
        assert item.link is None
        assert item.author is None
        assert item.category is None
        assert item.comments is None
        assert item.enclosure is None
        assert item.guid is None
        assert item.pub_date is None
        assert item.source is None
        assert item.content is None
        assert item.summary is None
        assert item.tags == []

    def test_custom_values(self):
        """Test custom feed item values."""
        pub_date = datetime.now()
        enclosure = {"url": "https://example.com/audio.mp3", "type": "audio/mpeg", "length": "1024"}
        tags = ["tech", "programming", "python"]

        item = FeedItem(
            title="Test Article",
            description="A test article description",
            link="https://example.com/article",
            author="Test Author",
            category="Technology",
            comments="https://example.com/comments",
            enclosure=enclosure,
            guid="unique-id-123",
            pub_date=pub_date,
            source="Test Source",
            content="Full article content here",
            summary="Article summary",
            tags=tags
        )

        assert item.title == "Test Article"
        assert item.description == "A test article description"
        assert item.link == "https://example.com/article"
        assert item.author == "Test Author"
        assert item.category == "Technology"
        assert item.comments == "https://example.com/comments"
        assert item.enclosure == enclosure
        assert item.guid == "unique-id-123"
        assert item.pub_date == pub_date
        assert item.source == "Test Source"
        assert item.content == "Full article content here"
        assert item.summary == "Article summary"
        assert item.tags == tags


class TestCSVMetadata:
    """Test CSVMetadata dataclass."""

    def test_default_values(self):
        """Test default CSV metadata values."""
        metadata = CSVMetadata()
        assert metadata.delimiter == ","
        assert metadata.quotechar == '"'
        assert metadata.encoding == "utf-8"
        assert metadata.has_header is True
        assert metadata.row_count == 0
        assert metadata.column_count == 0
        assert metadata.column_names == []
        assert metadata.column_types == {}
        assert metadata.null_values == {}
        assert metadata.file_size is None

    def test_custom_values(self):
        """Test custom CSV metadata values."""
        column_names = ["id", "name", "email", "age"]
        column_types = {"id": "int", "name": "str", "email": "str", "age": "int"}
        null_values = {"name": 2, "email": 1}

        metadata = CSVMetadata(
            delimiter=";",
            quotechar="'",
            encoding="utf-16",
            has_header=False,
            row_count=1000,
            column_count=4,
            column_names=column_names,
            column_types=column_types,
            null_values=null_values,
            file_size=2048
        )

        assert metadata.delimiter == ";"
        assert metadata.quotechar == "'"
        assert metadata.encoding == "utf-16"
        assert metadata.has_header is False
        assert metadata.row_count == 1000
        assert metadata.column_count == 4
        assert metadata.column_names == column_names
        assert metadata.column_types == column_types
        assert metadata.null_values == null_values
        assert metadata.file_size == 2048


class TestLinkInfo:
    """Test LinkInfo dataclass."""

    def test_default_values(self):
        """Test default link info values."""
        link = LinkInfo(url="https://example.com")
        assert link.url == "https://example.com"
        assert link.text is None
        assert link.title is None
        assert link.rel is None
        assert link.type is None
        assert link.is_external is False
        assert link.is_valid is True
        assert link.status_code is None
        assert link.content_type is None

    def test_custom_values(self):
        """Test custom link info values."""
        link = LinkInfo(
            url="https://external.com/page",
            text="External Link",
            title="Link to external site",
            rel="nofollow",
            type="text/html",
            is_external=True,
            is_valid=False,
            status_code=404,
            content_type="text/html"
        )

        assert link.url == "https://external.com/page"
        assert link.text == "External Link"
        assert link.title == "Link to external site"
        assert link.rel == "nofollow"
        assert link.type == "text/html"
        assert link.is_external is True
        assert link.is_valid is False
        assert link.status_code == 404
        assert link.content_type == "text/html"


class TestContentSummary:
    """Test ContentSummary dataclass."""

    def test_default_values(self):
        """Test default content summary values."""
        summary = ContentSummary()
        assert summary.word_count == 0
        assert summary.sentence_count == 0
        assert summary.paragraph_count == 0
        assert summary.reading_time_minutes == 0.0
        assert summary.key_phrases == []
        assert summary.summary_text is None
        assert summary.language is None
        assert summary.readability_score is None

    def test_custom_values(self):
        """Test custom content summary values."""
        key_phrases = ["machine learning", "artificial intelligence", "data science"]

        summary = ContentSummary(
            word_count=1500,
            sentence_count=75,
            paragraph_count=12,
            reading_time_minutes=6.0,
            key_phrases=key_phrases,
            summary_text="This article discusses machine learning concepts.",
            language="en",
            readability_score=8.5
        )

        assert summary.word_count == 1500
        assert summary.sentence_count == 75
        assert summary.paragraph_count == 12
        assert summary.reading_time_minutes == 6.0
        assert summary.key_phrases == key_phrases
        assert summary.summary_text == "This article discusses machine learning concepts."
        assert summary.language == "en"
        assert summary.readability_score == 8.5
