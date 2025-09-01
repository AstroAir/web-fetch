"""
Comprehensive tests for the JavaScript renderer utility.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from web_fetch.utils.js_renderer import (
    JSRenderer,
    JSRenderConfig,
    JSRenderResult,
    JSRenderError,
    BrowserEngine,
    RenderMode,
    WaitCondition,
)
from web_fetch.models.base import ContentType


class TestJSRenderConfig:
    """Test JavaScript render configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = JSRenderConfig()
        
        assert config.engine == BrowserEngine.CHROMIUM
        assert config.headless is True
        assert config.timeout == 30.0
        assert config.wait_for_load is True
        assert config.wait_condition == WaitCondition.LOAD
        assert config.viewport_width == 1920
        assert config.viewport_height == 1080
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = JSRenderConfig(
            engine=BrowserEngine.FIREFOX,
            headless=False,
            timeout=60.0,
            wait_for_load=False,
            wait_condition=WaitCondition.NETWORK_IDLE,
            viewport_width=1280,
            viewport_height=720,
            user_agent="Custom Agent/1.0"
        )
        
        assert config.engine == BrowserEngine.FIREFOX
        assert config.headless is False
        assert config.timeout == 60.0
        assert config.wait_for_load is False
        assert config.wait_condition == WaitCondition.NETWORK_IDLE
        assert config.viewport_width == 1280
        assert config.viewport_height == 720
        assert config.user_agent == "Custom Agent/1.0"
    
    def test_config_validation(self):
        """Test configuration validation."""
        # Invalid timeout
        with pytest.raises(ValueError, match="timeout must be positive"):
            JSRenderConfig(timeout=0)
        
        # Invalid viewport dimensions
        with pytest.raises(ValueError, match="viewport_width must be positive"):
            JSRenderConfig(viewport_width=0)
        
        with pytest.raises(ValueError, match="viewport_height must be positive"):
            JSRenderConfig(viewport_height=0)


class TestJSRenderResult:
    """Test JavaScript render result."""
    
    def test_result_creation(self):
        """Test render result creation."""
        result = JSRenderResult(
            url="https://example.com",
            html="<html><body>Rendered content</body></html>",
            status_code=200,
            render_time=2.5,
            screenshot_path="/tmp/screenshot.png"
        )
        
        assert result.url == "https://example.com"
        assert "Rendered content" in result.html
        assert result.status_code == 200
        assert result.render_time == 2.5
        assert result.screenshot_path == "/tmp/screenshot.png"
    
    def test_result_with_error(self):
        """Test render result with error."""
        result = JSRenderResult(
            url="https://error.example.com",
            html="",
            status_code=500,
            error="JavaScript execution failed"
        )
        
        assert result.url == "https://error.example.com"
        assert result.html == ""
        assert result.status_code == 500
        assert result.error == "JavaScript execution failed"
        assert result.success is False
    
    def test_result_success_property(self):
        """Test success property calculation."""
        # Successful result
        success_result = JSRenderResult(
            url="https://example.com",
            html="<html>content</html>",
            status_code=200
        )
        assert success_result.success is True
        
        # Failed result
        failed_result = JSRenderResult(
            url="https://example.com",
            html="",
            status_code=404,
            error="Page not found"
        )
        assert failed_result.success is False


class TestJSRenderer:
    """Test JavaScript renderer functionality."""
    
    @pytest.fixture
    def config(self):
        """Create JS render configuration."""
        return JSRenderConfig(timeout=10.0, headless=True)
    
    @pytest.fixture
    def renderer(self, config):
        """Create JS renderer."""
        return JSRenderer(config)
    
    def test_renderer_initialization(self, renderer):
        """Test renderer initialization."""
        assert renderer.config.timeout == 10.0
        assert renderer.config.headless is True
        assert renderer._browser is None
        assert renderer._page is None
    
    @pytest.mark.asyncio
    async def test_render_basic_page(self, renderer):
        """Test rendering a basic page."""
        url = "https://example.com"
        expected_html = "<html><body><h1>Example</h1></body></html>"
        
        with patch('playwright.async_api.async_playwright') as mock_playwright:
            # Mock playwright components
            mock_browser = AsyncMock()
            mock_page = AsyncMock()
            mock_context = AsyncMock()
            
            mock_context.new_page.return_value = mock_page
            mock_browser.new_context.return_value = mock_context
            
            mock_chromium = AsyncMock()
            mock_chromium.launch.return_value = mock_browser
            
            mock_playwright_instance = AsyncMock()
            mock_playwright_instance.chromium = mock_chromium
            mock_playwright.return_value.__aenter__.return_value = mock_playwright_instance
            
            # Mock page responses
            mock_response = MagicMock()
            mock_response.status = 200
            mock_page.goto.return_value = mock_response
            mock_page.content.return_value = expected_html
            
            result = await renderer.render(url)
            
            assert isinstance(result, JSRenderResult)
            assert result.url == url
            assert result.html == expected_html
            assert result.status_code == 200
            assert result.success is True
    
    @pytest.mark.asyncio
    async def test_render_with_wait_condition(self, renderer):
        """Test rendering with specific wait condition."""
        renderer.config.wait_condition = WaitCondition.NETWORK_IDLE
        url = "https://spa.example.com"
        
        with patch('playwright.async_api.async_playwright') as mock_playwright:
            mock_browser = AsyncMock()
            mock_page = AsyncMock()
            mock_context = AsyncMock()
            
            mock_context.new_page.return_value = mock_page
            mock_browser.new_context.return_value = mock_context
            
            mock_chromium = AsyncMock()
            mock_chromium.launch.return_value = mock_browser
            
            mock_playwright_instance = AsyncMock()
            mock_playwright_instance.chromium = mock_chromium
            mock_playwright.return_value.__aenter__.return_value = mock_playwright_instance
            
            mock_response = MagicMock()
            mock_response.status = 200
            mock_page.goto.return_value = mock_response
            mock_page.content.return_value = "<html><body>SPA Content</body></html>"
            
            result = await renderer.render(url)
            
            # Verify network idle wait was used
            mock_page.goto.assert_called_once()
            call_args = mock_page.goto.call_args
            assert "wait_until" in call_args[1]
            assert call_args[1]["wait_until"] == "networkidle"
    
    @pytest.mark.asyncio
    async def test_render_with_custom_javascript(self, renderer):
        """Test rendering with custom JavaScript execution."""
        url = "https://example.com"
        custom_js = "document.body.style.backgroundColor = 'red';"
        
        with patch('playwright.async_api.async_playwright') as mock_playwright:
            mock_browser = AsyncMock()
            mock_page = AsyncMock()
            mock_context = AsyncMock()
            
            mock_context.new_page.return_value = mock_page
            mock_browser.new_context.return_value = mock_context
            
            mock_chromium = AsyncMock()
            mock_chromium.launch.return_value = mock_browser
            
            mock_playwright_instance = AsyncMock()
            mock_playwright_instance.chromium = mock_chromium
            mock_playwright.return_value.__aenter__.return_value = mock_playwright_instance
            
            mock_response = MagicMock()
            mock_response.status = 200
            mock_page.goto.return_value = mock_response
            mock_page.content.return_value = "<html><body style='background-color: red;'>Modified</body></html>"
            
            result = await renderer.render(url, execute_js=custom_js)
            
            # Verify custom JavaScript was executed
            mock_page.evaluate.assert_called_once_with(custom_js)
            assert result.success is True
    
    @pytest.mark.asyncio
    async def test_render_with_screenshot(self, renderer):
        """Test rendering with screenshot capture."""
        url = "https://example.com"
        screenshot_path = "/tmp/test_screenshot.png"
        
        with patch('playwright.async_api.async_playwright') as mock_playwright:
            mock_browser = AsyncMock()
            mock_page = AsyncMock()
            mock_context = AsyncMock()
            
            mock_context.new_page.return_value = mock_page
            mock_browser.new_context.return_value = mock_context
            
            mock_chromium = AsyncMock()
            mock_chromium.launch.return_value = mock_browser
            
            mock_playwright_instance = AsyncMock()
            mock_playwright_instance.chromium = mock_chromium
            mock_playwright.return_value.__aenter__.return_value = mock_playwright_instance
            
            mock_response = MagicMock()
            mock_response.status = 200
            mock_page.goto.return_value = mock_response
            mock_page.content.return_value = "<html><body>Content</body></html>"
            mock_page.screenshot.return_value = b"fake_screenshot_data"
            
            result = await renderer.render(url, screenshot_path=screenshot_path)
            
            # Verify screenshot was taken
            mock_page.screenshot.assert_called_once_with(path=screenshot_path)
            assert result.screenshot_path == screenshot_path
    
    @pytest.mark.asyncio
    async def test_render_timeout_error(self, renderer):
        """Test rendering timeout error."""
        renderer.config.timeout = 0.1  # Very short timeout
        url = "https://slow.example.com"
        
        with patch('playwright.async_api.async_playwright') as mock_playwright:
            mock_browser = AsyncMock()
            mock_page = AsyncMock()
            mock_context = AsyncMock()
            
            mock_context.new_page.return_value = mock_page
            mock_browser.new_context.return_value = mock_context
            
            mock_chromium = AsyncMock()
            mock_chromium.launch.return_value = mock_browser
            
            mock_playwright_instance = AsyncMock()
            mock_playwright_instance.chromium = mock_chromium
            mock_playwright.return_value.__aenter__.return_value = mock_playwright_instance
            
            # Mock slow page load
            async def slow_goto(*args, **kwargs):
                await asyncio.sleep(0.2)  # Longer than timeout
                return MagicMock(status=200)
            
            mock_page.goto.side_effect = slow_goto
            
            with pytest.raises(JSRenderError, match="Render timeout"):
                await renderer.render(url)
    
    @pytest.mark.asyncio
    async def test_render_navigation_error(self, renderer):
        """Test rendering navigation error."""
        url = "https://nonexistent.example.com"
        
        with patch('playwright.async_api.async_playwright') as mock_playwright:
            mock_browser = AsyncMock()
            mock_page = AsyncMock()
            mock_context = AsyncMock()
            
            mock_context.new_page.return_value = mock_page
            mock_browser.new_context.return_value = mock_context
            
            mock_chromium = AsyncMock()
            mock_chromium.launch.return_value = mock_browser
            
            mock_playwright_instance = AsyncMock()
            mock_playwright_instance.chromium = mock_chromium
            mock_playwright.return_value.__aenter__.return_value = mock_playwright_instance
            
            # Mock navigation failure
            mock_page.goto.side_effect = Exception("Navigation failed")
            
            with pytest.raises(JSRenderError, match="Navigation failed"):
                await renderer.render(url)
    
    @pytest.mark.asyncio
    async def test_render_multiple_pages(self, renderer):
        """Test rendering multiple pages."""
        urls = [
            "https://example1.com",
            "https://example2.com",
            "https://example3.com"
        ]
        
        with patch('playwright.async_api.async_playwright') as mock_playwright:
            mock_browser = AsyncMock()
            mock_page = AsyncMock()
            mock_context = AsyncMock()
            
            mock_context.new_page.return_value = mock_page
            mock_browser.new_context.return_value = mock_context
            
            mock_chromium = AsyncMock()
            mock_chromium.launch.return_value = mock_browser
            
            mock_playwright_instance = AsyncMock()
            mock_playwright_instance.chromium = mock_chromium
            mock_playwright.return_value.__aenter__.return_value = mock_playwright_instance
            
            def mock_goto(url, **kwargs):
                return MagicMock(status=200)
            
            def mock_content():
                # Return different content based on current URL
                current_url = mock_page.url
                return f"<html><body>Content for {current_url}</body></html>"
            
            mock_page.goto.side_effect = mock_goto
            mock_page.content.side_effect = mock_content
            
            results = await renderer.render_multiple(urls)
            
            assert len(results) == 3
            for result in results:
                assert result.success is True
                assert result.status_code == 200
    
    @pytest.mark.asyncio
    async def test_render_with_cookies(self, renderer):
        """Test rendering with custom cookies."""
        url = "https://example.com"
        cookies = [
            {"name": "session", "value": "abc123", "domain": "example.com"},
            {"name": "preference", "value": "dark", "domain": "example.com"}
        ]
        
        with patch('playwright.async_api.async_playwright') as mock_playwright:
            mock_browser = AsyncMock()
            mock_page = AsyncMock()
            mock_context = AsyncMock()
            
            mock_context.new_page.return_value = mock_page
            mock_browser.new_context.return_value = mock_context
            
            mock_chromium = AsyncMock()
            mock_chromium.launch.return_value = mock_browser
            
            mock_playwright_instance = AsyncMock()
            mock_playwright_instance.chromium = mock_chromium
            mock_playwright.return_value.__aenter__.return_value = mock_playwright_instance
            
            mock_response = MagicMock()
            mock_response.status = 200
            mock_page.goto.return_value = mock_response
            mock_page.content.return_value = "<html><body>Authenticated content</body></html>"
            
            result = await renderer.render(url, cookies=cookies)
            
            # Verify cookies were set
            mock_context.add_cookies.assert_called_once_with(cookies)
            assert result.success is True
    
    @pytest.mark.asyncio
    async def test_render_with_headers(self, renderer):
        """Test rendering with custom headers."""
        url = "https://api.example.com"
        headers = {
            "Authorization": "Bearer token123",
            "X-Custom-Header": "custom-value"
        }
        
        with patch('playwright.async_api.async_playwright') as mock_playwright:
            mock_browser = AsyncMock()
            mock_page = AsyncMock()
            mock_context = AsyncMock()
            
            mock_context.new_page.return_value = mock_page
            mock_browser.new_context.return_value = mock_context
            
            mock_chromium = AsyncMock()
            mock_chromium.launch.return_value = mock_browser
            
            mock_playwright_instance = AsyncMock()
            mock_playwright_instance.chromium = mock_chromium
            mock_playwright.return_value.__aenter__.return_value = mock_playwright_instance
            
            mock_response = MagicMock()
            mock_response.status = 200
            mock_page.goto.return_value = mock_response
            mock_page.content.return_value = "<html><body>API response</body></html>"
            
            result = await renderer.render(url, headers=headers)
            
            # Verify headers were set
            mock_page.set_extra_http_headers.assert_called_once_with(headers)
            assert result.success is True
    
    @pytest.mark.asyncio
    async def test_renderer_cleanup(self, renderer):
        """Test renderer cleanup."""
        with patch('playwright.async_api.async_playwright') as mock_playwright:
            mock_browser = AsyncMock()
            mock_playwright_instance = AsyncMock()
            mock_playwright_instance.chromium.launch.return_value = mock_browser
            mock_playwright.return_value.__aenter__.return_value = mock_playwright_instance
            
            # Initialize browser
            await renderer._initialize_browser()
            assert renderer._browser is not None
            
            # Cleanup should close browser
            await renderer.cleanup()
            mock_browser.close.assert_called_once()
            assert renderer._browser is None
    
    @pytest.mark.asyncio
    async def test_context_manager(self, renderer):
        """Test using renderer as context manager."""
        with patch('playwright.async_api.async_playwright') as mock_playwright:
            mock_browser = AsyncMock()
            mock_playwright_instance = AsyncMock()
            mock_playwright_instance.chromium.launch.return_value = mock_browser
            mock_playwright.return_value.__aenter__.return_value = mock_playwright_instance
            
            async with renderer:
                # Browser should be initialized
                assert renderer._browser is not None
            
            # Browser should be cleaned up automatically
            mock_browser.close.assert_called_once()
