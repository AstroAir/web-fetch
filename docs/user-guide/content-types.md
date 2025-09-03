# Content Types

WebFetch supports multiple content types for automatic parsing and processing of HTTP responses. This guide explains each content type and when to use them.

## Overview

WebFetch provides four main content types:

- **`ContentType.TEXT`** - Plain text content
- **`ContentType.JSON`** - JSON data structures  
- **`ContentType.HTML`** - HTML with structured data extraction
- **`ContentType.RAW`** - Raw binary data

## ContentType.TEXT

Parse response as UTF-8 text content.

### When to Use

- Plain text files
- CSV data
- Log files
- Configuration files
- Any text-based content

### Example

```python
import asyncio
from web_fetch import fetch_url, ContentType

async def fetch_text():
    result = await fetch_url("https://httpbin.org/robots.txt", ContentType.TEXT)
    if result.is_success:
        print(f"Content type: {type(result.content)}")  # <class 'str'>
        print(f"Content: {result.content}")

asyncio.run(fetch_text())
```

### Return Value

- **Type**: `str`
- **Encoding**: Automatically detected (UTF-8, Latin-1, etc.)
- **Processing**: Minimal - just decoding bytes to string

## ContentType.JSON

Parse response as JSON data structures.

### When to Use

- REST APIs
- JSON configuration files
- Data exchange formats
- Any valid JSON content

### Example

```python
import asyncio
from web_fetch import fetch_url, ContentType

async def fetch_json():
    result = await fetch_url("https://httpbin.org/json", ContentType.JSON)
    if result.is_success:
        print(f"Content type: {type(result.content)}")  # <class 'dict'>
        print(f"Title: {result.content['slideshow']['title']}")

asyncio.run(fetch_json())
```

### Return Value

- **Type**: `dict`, `list`, `str`, `int`, `float`, `bool`, or `None`
- **Processing**: Full JSON parsing with error handling
- **Validation**: Validates JSON syntax

### Error Handling

```python
import asyncio
from web_fetch import fetch_url, ContentType, ContentError

async def safe_json_fetch():
    try:
        result = await fetch_url("https://httpbin.org/html", ContentType.JSON)
        if not result.is_success:
            print(f"JSON parsing failed: {result.error}")
    except ContentError as e:
        print(f"Content error: {e}")

asyncio.run(safe_json_fetch())
```

## ContentType.HTML

Parse HTML and extract structured data.

### When to Use

- Web pages
- HTML documents
- Web scraping
- Content extraction

### Example

```python
import asyncio
from web_fetch import fetch_url, ContentType

async def fetch_html():
    result = await fetch_url("https://example.com", ContentType.HTML)
    if result.is_success:
        html_data = result.content
        print(f"Content type: {type(html_data)}")  # <class 'dict'>
        print(f"Title: {html_data['title']}")
        print(f"Links found: {len(html_data['links'])}")
        print(f"Images found: {len(html_data['images'])}")

asyncio.run(fetch_html())
```

### Return Value Structure

The HTML content type returns a structured dictionary:

```python
{
    "title": "Page Title",
    "text": "Extracted text content",
    "links": [
        {
            "text": "Link text",
            "href": "https://example.com/link",
            "title": "Link title (if present)"
        }
    ],
    "images": [
        {
            "src": "https://example.com/image.jpg",
            "alt": "Image alt text",
            "title": "Image title (if present)"
        }
    ],
    "meta": {
        "description": "Page description",
        "keywords": "page, keywords",
        "author": "Page author"
    },
    "headings": {
        "h1": ["Main heading"],
        "h2": ["Subheading 1", "Subheading 2"],
        "h3": ["Sub-subheading"]
    }
}
```

### Advanced HTML Processing

```python
import asyncio
from web_fetch import fetch_url, ContentType

async def detailed_html_analysis():
    result = await fetch_url("https://example.com", ContentType.HTML)
    if result.is_success:
        html_data = result.content
        
        # Analyze links
        external_links = [
            link for link in html_data['links'] 
            if link['href'].startswith('http')
        ]
        
        # Check for specific meta tags
        description = html_data['meta'].get('description', 'No description')
        
        # Count headings
        total_headings = sum(len(headings) for headings in html_data['headings'].values())
        
        print(f"External links: {len(external_links)}")
        print(f"Description: {description}")
        print(f"Total headings: {total_headings}")

asyncio.run(detailed_html_analysis())
```

## ContentType.RAW

Return raw binary data without processing.

### When to Use

- Binary files (images, videos, archives)
- File downloads
- Custom processing requirements
- When you need the original bytes

### Example

```python
import asyncio
from web_fetch import fetch_url, ContentType

async def fetch_raw():
    result = await fetch_url("https://httpbin.org/bytes/1024", ContentType.RAW)
    if result.is_success:
        data = result.content
        print(f"Content type: {type(data)}")  # <class 'bytes'>
        print(f"Size: {len(data)} bytes")
        print(f"First 20 bytes: {data[:20]}")

asyncio.run(fetch_raw())
```

### Return Value

- **Type**: `bytes`
- **Processing**: None - raw response body
- **Use Cases**: File downloads, binary data, custom processing

### File Download Example

```python
import asyncio
from pathlib import Path
from web_fetch import fetch_url, ContentType

async def download_file():
    result = await fetch_url("https://httpbin.org/image/png", ContentType.RAW)
    if result.is_success:
        # Save to file
        output_path = Path("downloads/image.png")
        output_path.parent.mkdir(exist_ok=True)
        output_path.write_bytes(result.content)
        print(f"Downloaded {len(result.content)} bytes to {output_path}")

asyncio.run(download_file())
```

## Content Type Detection

WebFetch can automatically detect content types based on response headers:

```python
import asyncio
from web_fetch import fetch_url, ContentType

async def auto_detect():
    # Let WebFetch choose based on Content-Type header
    result = await fetch_url("https://httpbin.org/json")  # No content_type specified
    
    # WebFetch will automatically use JSON parsing for application/json responses
    if result.is_success:
        print(f"Auto-detected content: {type(result.content)}")

asyncio.run(auto_detect())
```

## Best Practices

### Choose the Right Content Type

1. **Use `TEXT`** for simple text processing
2. **Use `JSON`** for APIs and structured data
3. **Use `HTML`** for web scraping and content extraction
4. **Use `RAW`** for binary files and custom processing

### Error Handling

Always check for success and handle content errors:

```python
import asyncio
from web_fetch import fetch_url, ContentType, ContentError

async def robust_fetch():
    try:
        result = await fetch_url("https://api.example.com/data", ContentType.JSON)
        
        if result.is_success:
            # Process successful result
            data = result.content
            print(f"Received data: {data}")
        else:
            # Handle HTTP errors
            print(f"HTTP error {result.status_code}: {result.error}")
            
    except ContentError as e:
        # Handle content parsing errors
        print(f"Content parsing failed: {e}")
    except Exception as e:
        # Handle other errors
        print(f"Unexpected error: {e}")

asyncio.run(robust_fetch())
```

### Performance Considerations

- **JSON parsing** has overhead - use `TEXT` if you don't need structured data
- **HTML parsing** is the most expensive - only use when you need structured extraction
- **RAW** is fastest - no processing overhead
- **TEXT** is lightweight - good for simple text content

## Next Steps

- **[Error Handling](error-handling.md)** - Comprehensive error handling strategies
- **[Caching](caching.md)** - Caching responses for better performance
- **[Advanced Examples](../examples/advanced.md)** - Complex usage patterns
