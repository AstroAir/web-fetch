# Content Parser Examples

This document provides comprehensive examples for using the various content parsers in the web-fetch library. Each parser is designed to handle specific content types and provides structured data extraction capabilities.

## Table of Contents

- [JSON Parser](#json-parser)
- [HTML Parser](#html-parser)
- [Text Parser](#text-parser)
- [CSV Parser](#csv-parser)
- [PDF Parser](#pdf-parser)
- [Image Parser](#image-parser)
- [Feed Parser](#feed-parser)
- [Raw Content Handling](#raw-content-handling)
- [Error Handling](#error-handling)
- [Performance Considerations](#performance-considerations)

## JSON Parser

### Basic JSON Parsing

```python
import asyncio
from web_fetch import fetch_url, ContentType

async def json_examples():
    # Standard JSON API response
    result = await fetch_url("https://jsonplaceholder.typicode.com/posts/1", ContentType.JSON)
    if result.is_success:
        print(f"Title: {result.content['title']}")
        print(f"User ID: {result.content['userId']}")
        print(f"Body: {result.content['body'][:100]}...")

    # JSON array handling
    result = await fetch_url("https://jsonplaceholder.typicode.com/users", ContentType.JSON)
    if result.is_success and isinstance(result.content, list):
        print(f"Number of users: {len(result.content)}")
        for user in result.content[:3]:  # First 3 users
            print(f"- {user['name']} ({user['email']})")

asyncio.run(json_examples())
```

### Complex JSON Structures

```python
async def complex_json_example():
    # Nested JSON with arrays and objects
    result = await fetch_url("https://httpbin.org/json", ContentType.JSON)
    if result.is_success:
        slideshow = result.content.get('slideshow', {})
        print(f"Slideshow: {slideshow.get('title')}")
        
        slides = slideshow.get('slides', [])
        for i, slide in enumerate(slides):
            print(f"Slide {i+1}: {slide.get('title')}")
            items = slide.get('items', [])
            for item in items:
                print(f"  - {item}")

asyncio.run(complex_json_example())
```

### JSON API Standards

```python
# The JSON parser automatically detects and handles various API standards:
# - JSON-LD (Linked Data)
# - HAL (Hypertext Application Language)
# - JSON API specification
# - OData JSON format
# - Collection+JSON

async def api_standards_example():
    # JSON-LD example (structured data)
    json_ld_data = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": "John Doe",
        "jobTitle": "Software Engineer"
    }
    
    # HAL example (hypermedia)
    hal_data = {
        "_links": {
            "self": {"href": "/users/123"},
            "orders": {"href": "/users/123/orders"}
        },
        "name": "John Doe",
        "email": "john@example.com"
    }
    
    print("JSON parser automatically detects and structures these formats")
```

## HTML Parser

### Basic HTML Parsing

```python
async def html_examples():
    # Basic HTML structure extraction
    result = await fetch_url("https://example.com", ContentType.HTML)
    if result.is_success:
        content = result.content
        print(f"Title: {content['title']}")
        print(f"Meta description: {content['meta']['description']}")
        print(f"Links found: {len(content['links'])}")
        print(f"Images found: {len(content['images'])}")
        
        # Show first few links
        for link in content['links'][:5]:
            print(f"Link: {link['text']} -> {link['href']}")

asyncio.run(html_examples())
```

### Advanced HTML Extraction

```python
async def advanced_html_example():
    result = await fetch_url("https://news.ycombinator.com", ContentType.HTML)
    if result.is_success:
        content = result.content
        
        # Extract headings hierarchy
        headings = content.get('headings', [])
        for heading in headings[:10]:
            level = heading['tag']
            text = heading['text'][:50]
            print(f"{level.upper()}: {text}...")
        
        # Extract structured data (if available)
        structured_data = content.get('structured_data', [])
        for data in structured_data:
            print(f"Schema: {data.get('@type', 'Unknown')}")
        
        # Extract forms
        forms = content.get('forms', [])
        for form in forms:
            print(f"Form: {form.get('action', 'No action')} ({form.get('method', 'GET')})")

asyncio.run(advanced_html_example())
```

### HTML Content Analysis

```python
async def html_analysis_example():
    result = await fetch_url("https://httpbin.org/html", ContentType.HTML)
    if result.is_success:
        content = result.content
        
        # Analyze content structure
        print("Content Analysis:")
        print(f"- Page has title: {'title' in content}")
        print(f"- Number of paragraphs: {len(content.get('paragraphs', []))}")
        print(f"- Has navigation: {len(content.get('nav', [])) > 0}")
        print(f"- External links: {sum(1 for link in content.get('links', []) if 'http' in link.get('href', ''))}")
        print(f"- Internal links: {sum(1 for link in content.get('links', []) if not link.get('href', '').startswith('http'))}")

asyncio.run(html_analysis_example())
```

## Text Parser

### Basic Text Processing

```python
async def text_examples():
    # Plain text content
    result = await fetch_url("https://httpbin.org/robots.txt", ContentType.TEXT)
    if result.is_success:
        lines = result.content.split('\n')
        print(f"Total lines: {len(lines)}")
        print(f"Non-empty lines: {len([l for l in lines if l.strip()])}")
        
        # Show content structure
        for i, line in enumerate(lines[:10]):
            if line.strip():
                print(f"{i+1}: {line.strip()}")

asyncio.run(text_examples())
```

### Text Content Analysis

```python
async def text_analysis_example():
    result = await fetch_url("https://httpbin.org/get", ContentType.TEXT)
    if result.is_success:
        text = result.content
        
        # Basic text statistics
        words = text.split()
        sentences = text.split('.')
        
        print("Text Analysis:")
        print(f"- Character count: {len(text)}")
        print(f"- Word count: {len(words)}")
        print(f"- Sentence count: {len(sentences)}")
        print(f"- Average word length: {sum(len(w) for w in words) / len(words):.1f}")
        
        # Find common patterns
        import re
        emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', text)
        
        print(f"- Email addresses found: {len(emails)}")
        print(f"- URLs found: {len(urls)}")

asyncio.run(text_analysis_example())
```

## CSV Parser

### Basic CSV Parsing

```python
# Note: For actual CSV files, you would typically fetch as TEXT and then parse
async def csv_example():
    # Simulate CSV data processing
    csv_content = """name,age,city
John Doe,30,New York
Jane Smith,25,Los Angeles
Bob Johnson,35,Chicago"""
    
    lines = csv_content.strip().split('\n')
    headers = lines[0].split(',')
    rows = [line.split(',') for line in lines[1:]]
    
    print(f"Headers: {headers}")
    print(f"Rows: {len(rows)}")
    
    # Convert to structured data
    data = []
    for row in rows:
        record = dict(zip(headers, row))
        data.append(record)
    
    for record in data:
        print(f"- {record['name']}: {record['age']} years old, lives in {record['city']}")

asyncio.run(csv_example())
```

### Advanced CSV Processing

```python
import csv
from io import StringIO

async def advanced_csv_example():
    # Fetch CSV-like data and process it
    result = await fetch_url("https://httpbin.org/get", ContentType.TEXT)
    if result.is_success:
        # For demonstration, create CSV from JSON response
        import json
        try:
            data = json.loads(result.content)
            
            # Convert to CSV format
            csv_output = StringIO()
            if isinstance(data, dict):
                writer = csv.DictWriter(csv_output, fieldnames=data.keys())
                writer.writeheader()
                writer.writerow(data)
                
                csv_content = csv_output.getvalue()
                print("Generated CSV:")
                print(csv_content)
        except:
            print("Could not convert to CSV format")

asyncio.run(advanced_csv_example())
```

## PDF Parser

### PDF Content Extraction

```python
# Note: PDF parsing requires additional libraries like PyPDF2 or pdfplumber
async def pdf_example():
    # For demonstration purposes - actual implementation would use PDF libraries
    print("PDF Parser Features:")
    print("- Text extraction from PDF documents")
    print("- Metadata extraction (title, author, creation date)")
    print("- Page-by-page processing")
    print("- Table extraction")
    print("- Image extraction from PDFs")
    
    # Example structure for PDF content
    pdf_content = {
        "text": "Extracted text content from PDF",
        "metadata": {
            "title": "Document Title",
            "author": "Document Author",
            "pages": 10,
            "creation_date": "2024-01-01"
        },
        "pages": [
            {"page_number": 1, "text": "Page 1 content"},
            {"page_number": 2, "text": "Page 2 content"}
        ]
    }
    
    print(f"Example PDF structure: {pdf_content}")

asyncio.run(pdf_example())
```

## Image Parser

### Image Metadata Extraction

```python
async def image_examples():
    # PNG image analysis
    result = await fetch_url("https://httpbin.org/image/png", ContentType.RAW)
    if result.is_success:
        content = result.content
        print(f"PNG Image size: {len(content)} bytes")
        
        # Check PNG signature
        png_signature = b'\x89PNG\r\n\x1a\n'
        if content.startswith(png_signature):
            print("✓ Valid PNG file")
            # In a real implementation, you would extract:
            # - Image dimensions
            # - Color depth
            # - Compression method
            # - Creation timestamp
    
    # JPEG image analysis
    result = await fetch_url("https://httpbin.org/image/jpeg", ContentType.RAW)
    if result.is_success:
        content = result.content
        print(f"JPEG Image size: {len(content)} bytes")
        
        # Check JPEG signature
        jpeg_signature = b'\xff\xd8\xff'
        if content.startswith(jpeg_signature):
            print("✓ Valid JPEG file")
            # In a real implementation, you would extract EXIF data:
            # - Camera make/model
            # - GPS coordinates
            # - Shooting parameters
            # - Timestamps

asyncio.run(image_examples())
```

## Feed Parser

### RSS/Atom Feed Processing

```python
async def feed_examples():
    # Note: For actual RSS/Atom feeds, you would use libraries like feedparser
    print("Feed Parser Features:")
    print("- RSS 2.0 feed parsing")
    print("- Atom 1.0 feed parsing")
    print("- Podcast feed support")
    print("- Feed validation")
    print("- Entry deduplication")
    
    # Example feed structure
    feed_structure = {
        "title": "Example Blog",
        "description": "A sample blog feed",
        "link": "https://example.com",
        "updated": "2024-01-01T12:00:00Z",
        "entries": [
            {
                "title": "First Post",
                "link": "https://example.com/post1",
                "published": "2024-01-01T10:00:00Z",
                "summary": "This is the first post"
            }
        ]
    }
    
    print(f"Example feed structure: {feed_structure}")

asyncio.run(feed_examples())
```

## Raw Content Handling

### Binary Data Processing

```python
async def raw_content_examples():
    # Handle binary data
    result = await fetch_url("https://httpbin.org/bytes/1024", ContentType.RAW)
    if result.is_success:
        content = result.content
        print(f"Binary data: {len(content)} bytes")
        print(f"First 20 bytes: {content[:20]}")
        print(f"Data type: {type(content)}")
        
        # Analyze binary content
        unique_bytes = set(content)
        print(f"Unique byte values: {len(unique_bytes)}")
        print(f"Entropy estimate: {len(unique_bytes) / 256:.2f}")

asyncio.run(raw_content_examples())
```

## Error Handling

### Parser Error Recovery

```python
async def error_handling_examples():
    # Handle invalid JSON gracefully
    try:
        result = await fetch_url("https://httpbin.org/html", ContentType.JSON)
        if not result.is_success:
            print(f"Expected JSON parsing error: {result.error}")
    except Exception as e:
        print(f"Caught parsing exception: {e}")
    
    # Handle empty content
    result = await fetch_url("https://httpbin.org/status/204", ContentType.TEXT)
    print(f"Empty content handling - Success: {result.is_success}")
    print(f"Content: {repr(result.content)}")
    
    # Handle large content
    result = await fetch_url("https://httpbin.org/bytes/10240", ContentType.TEXT)
    if result.is_success:
        print(f"Large content handled: {len(result.content)} chars")

asyncio.run(error_handling_examples())
```

## Performance Considerations

### Parser Performance Comparison

```python
import time

async def performance_examples():
    test_url = "https://httpbin.org/json"
    
    # Time different parsing approaches
    parsers = [
        (ContentType.RAW, "Raw (no parsing)"),
        (ContentType.TEXT, "Text parsing"),
        (ContentType.JSON, "JSON parsing"),
    ]
    
    for content_type, description in parsers:
        start_time = time.time()
        result = await fetch_url(test_url, content_type)
        end_time = time.time()
        
        if result.is_success:
            print(f"{description}: {end_time - start_time:.3f}s")
    
    print("\nPerformance Tips:")
    print("- Use RAW for binary data or when parsing isn't needed")
    print("- Use TEXT for simple text processing")
    print("- Use JSON only when you need structured data")
    print("- Use HTML for web page structure extraction")
    print("- Consider memory usage for large files")

asyncio.run(performance_examples())
```

## Best Practices

1. **Choose the Right Parser**: Select the content type that matches your data and processing needs
2. **Handle Errors Gracefully**: Always check `result.is_success` and handle parsing errors
3. **Validate Content**: Verify content structure before processing
4. **Consider Performance**: Use the most efficient parser for your use case
5. **Memory Management**: Be careful with large files - consider streaming for big content
6. **Content Type Detection**: Let the library auto-detect when possible
7. **Structured Data**: Prefer structured formats (JSON, HTML) over plain text when available
8. **Error Recovery**: Implement fallback strategies for parsing failures
