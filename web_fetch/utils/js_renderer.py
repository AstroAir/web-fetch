"""
JavaScript-rendered content support using Playwright.

This module provides functionality to render JavaScript-heavy pages and SPAs
using Playwright for dynamic content extraction with wait strategies and optimization.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional, List, Callable, Union
from urllib.parse import urlparse

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

from ..exceptions import WebFetchError

logger = logging.getLogger(__name__)


class BrowserType(Enum):
    """Supported browser types."""
    
    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"


class WaitStrategy(Enum):
    """Wait strategies for page loading."""
    
    LOAD = "load"                    # Wait for load event
    DOMCONTENTLOADED = "domcontentloaded"  # Wait for DOMContentLoaded
    NETWORKIDLE = "networkidle"      # Wait for network idle
    CUSTOM = "custom"                # Custom wait condition


@dataclass
class JSRenderConfig:
    """Configuration for JavaScript rendering."""
    
    browser_type: BrowserType = BrowserType.CHROMIUM
    headless: bool = True
    timeout: float = 30.0
    wait_strategy: WaitStrategy = WaitStrategy.NETWORKIDLE
    wait_for_selector: Optional[str] = None
    wait_for_function: Optional[str] = None
    viewport_width: int = 1920
    viewport_height: int = 1080
    user_agent: Optional[str] = None
    extra_headers: Dict[str, str] = None
    javascript_enabled: bool = True
    images_enabled: bool = False
    css_enabled: bool = True
    block_resources: List[str] = None  # Resource types to block
    stealth_mode: bool = True
    max_redirects: int = 10
    
    def __post_init__(self):
        if self.extra_headers is None:
            self.extra_headers = {}
        if self.block_resources is None:
            self.block_resources = ['image', 'media', 'font']  # Block by default for performance


class JavaScriptRenderer:
    """JavaScript content renderer using Playwright."""
    
    def __init__(self, config: Optional[JSRenderConfig] = None):
        """
        Initialize JavaScript renderer.
        
        Args:
            config: Rendering configuration
        """
        if not HAS_PLAYWRIGHT:
            raise ImportError("playwright is required for JavaScript rendering. Install with: pip install playwright")
        
        self.config = config or JSRenderConfig()
        self.playwright = None
        self.browser = None
        self.context = None
        self._session_count = 0
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def start(self):
        """Start the browser session."""
        if self.playwright is None:
            self.playwright = await async_playwright().start()
            
            # Launch browser
            browser_launcher = getattr(self.playwright, self.config.browser_type.value)
            
            launch_options = {
                'headless': self.config.headless,
                'args': self._get_browser_args()
            }
            
            self.browser = await browser_launcher.launch(**launch_options)
            
            # Create context
            context_options = {
                'viewport': {
                    'width': self.config.viewport_width,
                    'height': self.config.viewport_height
                },
                'user_agent': self.config.user_agent,
                'extra_http_headers': self.config.extra_headers,
                'java_script_enabled': self.config.javascript_enabled,
                'ignore_https_errors': True,
            }
            
            self.context = await self.browser.new_context(**context_options)
            
            # Set up resource blocking
            if self.config.block_resources:
                await self.context.route("**/*", self._handle_route)
            
            logger.info(f"Started {self.config.browser_type.value} browser session")
    
    async def close(self):
        """Close the browser session."""
        if self.context:
            await self.context.close()
            self.context = None
        
        if self.browser:
            await self.browser.close()
            self.browser = None
        
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
        
        logger.info("Closed browser session")
    
    async def render_page(self, url: str, **kwargs) -> Dict[str, Any]:
        """
        Render a JavaScript-heavy page and extract content.
        
        Args:
            url: URL to render
            **kwargs: Additional options to override config
            
        Returns:
            Dictionary with rendered content and metadata
            
        Raises:
            WebFetchError: If rendering fails
        """
        if not self.context:
            await self.start()
        
        page = None
        try:
            page = await self.context.new_page()
            self._session_count += 1
            
            # Apply any runtime configuration overrides
            timeout = kwargs.get('timeout', self.config.timeout) * 1000  # Convert to ms
            wait_strategy = kwargs.get('wait_strategy', self.config.wait_strategy)
            wait_for_selector = kwargs.get('wait_for_selector', self.config.wait_for_selector)
            wait_for_function = kwargs.get('wait_for_function', self.config.wait_for_function)
            
            # Navigate to page
            logger.debug(f"Navigating to {url}")
            
            # Set up wait condition
            wait_until = self._get_wait_until(wait_strategy)
            
            response = await page.goto(
                url,
                timeout=timeout,
                wait_until=wait_until
            )
            
            if not response:
                raise WebFetchError(f"Failed to load page: {url}")
            
            # Additional wait conditions
            if wait_for_selector:
                await page.wait_for_selector(wait_for_selector, timeout=timeout)
            
            if wait_for_function:
                await page.wait_for_function(wait_for_function, timeout=timeout)
            
            # Extract content and metadata
            result = await self._extract_page_data(page, response)
            result['url'] = url
            result['session_id'] = self._session_count
            
            logger.debug(f"Successfully rendered {url}")
            return result
            
        except PlaywrightTimeoutError as e:
            logger.error(f"Timeout rendering {url}: {e}")
            raise WebFetchError(f"Page rendering timeout: {e}")
        except Exception as e:
            logger.error(f"Failed to render {url}: {e}")
            raise WebFetchError(f"Page rendering failed: {e}")
        finally:
            if page:
                await page.close()
    
    async def _extract_page_data(self, page: Page, response) -> Dict[str, Any]:
        """Extract data from rendered page."""
        # Get page content
        html_content = await page.content()
        
        # Get page title
        title = await page.title()
        
        # Get page URL (may have changed due to redirects)
        final_url = page.url
        
        # Get response status
        status_code = response.status if response else 200
        
        # Get response headers
        headers = dict(response.headers) if response else {}
        
        # Extract text content
        text_content = await page.evaluate("""
            () => {
                // Remove script and style elements
                const scripts = document.querySelectorAll('script, style');
                scripts.forEach(el => el.remove());
                
                // Get text content
                return document.body ? document.body.innerText : '';
            }
        """)
        
        # Extract links
        links = await page.evaluate("""
            () => {
                const links = Array.from(document.querySelectorAll('a[href]'));
                return links.map(link => ({
                    text: link.textContent.trim(),
                    href: link.href,
                    title: link.title || null
                }));
            }
        """)
        
        # Extract images
        images = await page.evaluate("""
            () => {
                const images = Array.from(document.querySelectorAll('img[src]'));
                return images.map(img => ({
                    src: img.src,
                    alt: img.alt || null,
                    title: img.title || null,
                    width: img.naturalWidth || null,
                    height: img.naturalHeight || null
                }));
            }
        """)
        
        # Extract meta tags
        meta_tags = await page.evaluate("""
            () => {
                const metas = Array.from(document.querySelectorAll('meta'));
                const result = {};
                
                metas.forEach(meta => {
                    const name = meta.getAttribute('name') || meta.getAttribute('property');
                    const content = meta.getAttribute('content');
                    
                    if (name && content) {
                        result[name] = content;
                    }
                });
                
                return result;
            }
        """)
        
        # Get page metrics
        metrics = await page.evaluate("""
            () => {
                const perf = performance.getEntriesByType('navigation')[0];
                return {
                    loadTime: perf ? perf.loadEventEnd - perf.loadEventStart : null,
                    domContentLoadedTime: perf ? perf.domContentLoadedEventEnd - perf.domContentLoadedEventStart : null,
                    responseTime: perf ? perf.responseEnd - perf.responseStart : null
                };
            }
        """)
        
        return {
            'html_content': html_content,
            'text_content': text_content,
            'title': title,
            'final_url': final_url,
            'status_code': status_code,
            'headers': headers,
            'links': links,
            'images': images,
            'meta_tags': meta_tags,
            'metrics': metrics,
            'rendered_with_js': True
        }
    
    def _get_browser_args(self) -> List[str]:
        """Get browser launch arguments."""
        args = []
        
        if self.config.stealth_mode:
            args.extend([
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--disable-extensions',
                '--disable-plugins',
                '--disable-images' if not self.config.images_enabled else '',
            ])
        
        # Remove empty strings
        return [arg for arg in args if arg]
    
    def _get_wait_until(self, wait_strategy: WaitStrategy) -> str:
        """Convert wait strategy to Playwright wait_until parameter."""
        mapping = {
            WaitStrategy.LOAD: 'load',
            WaitStrategy.DOMCONTENTLOADED: 'domcontentloaded',
            WaitStrategy.NETWORKIDLE: 'networkidle',
        }
        return mapping.get(wait_strategy, 'networkidle')
    
    async def _handle_route(self, route):
        """Handle resource routing for blocking."""
        resource_type = route.request.resource_type
        
        if resource_type in self.config.block_resources:
            await route.abort()
        else:
            await route.continue_()
    
    async def screenshot(self, url: str, path: Optional[str] = None, **kwargs) -> bytes:
        """
        Take a screenshot of the rendered page.
        
        Args:
            url: URL to screenshot
            path: Optional file path to save screenshot
            **kwargs: Additional screenshot options
            
        Returns:
            Screenshot as bytes
        """
        if not self.context:
            await self.start()
        
        page = None
        try:
            page = await self.context.new_page()
            
            # Navigate to page
            await page.goto(url, timeout=self.config.timeout * 1000)
            
            # Take screenshot
            screenshot_options = {
                'path': path,
                'full_page': kwargs.get('full_page', True),
                'type': kwargs.get('type', 'png'),
            }
            
            screenshot_bytes = await page.screenshot(**screenshot_options)
            return screenshot_bytes
            
        finally:
            if page:
                await page.close()
    
    async def get_page_source(self, url: str, **kwargs) -> str:
        """
        Get the rendered HTML source of a page.
        
        Args:
            url: URL to get source for
            **kwargs: Additional rendering options
            
        Returns:
            Rendered HTML source
        """
        result = await self.render_page(url, **kwargs)
        return result.get('html_content', '')
    
    def is_available(self) -> bool:
        """Check if JavaScript rendering is available."""
        return HAS_PLAYWRIGHT
    
    async def install_browsers(self):
        """Install required browser binaries."""
        if not HAS_PLAYWRIGHT:
            raise ImportError("playwright is required for JavaScript rendering")
        
        import subprocess
        import sys
        
        try:
            # Install browsers
            result = subprocess.run([
                sys.executable, '-m', 'playwright', 'install', self.config.browser_type.value
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                raise WebFetchError(f"Failed to install browser: {result.stderr}")
            
            logger.info(f"Successfully installed {self.config.browser_type.value} browser")
            
        except Exception as e:
            raise WebFetchError(f"Browser installation failed: {e}")


# Convenience functions
async def render_js_page(url: str, config: Optional[JSRenderConfig] = None, **kwargs) -> Dict[str, Any]:
    """
    Convenience function to render a single JavaScript page.
    
    Args:
        url: URL to render
        config: Optional rendering configuration
        **kwargs: Additional rendering options
        
    Returns:
        Rendered page data
    """
    async with JavaScriptRenderer(config) as renderer:
        return await renderer.render_page(url, **kwargs)


async def get_js_page_source(url: str, config: Optional[JSRenderConfig] = None, **kwargs) -> str:
    """
    Convenience function to get rendered HTML source.
    
    Args:
        url: URL to get source for
        config: Optional rendering configuration
        **kwargs: Additional rendering options
        
    Returns:
        Rendered HTML source
    """
    async with JavaScriptRenderer(config) as renderer:
        return await renderer.get_page_source(url, **kwargs)
