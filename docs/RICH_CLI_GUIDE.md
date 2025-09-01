# Web-Fetch Enhanced CLI Guide

This guide covers the enhanced CLI interfaces for web-fetch with integrated beautiful formatting, progress bars, and improved user experience.

## Overview

Web-fetch now provides enhanced CLI interfaces with integrated formatting:

1. **Main CLI** (`web_fetch.cli.main`) - Enhanced CLI with integrated rich formatting and fallbacks
2. **Extended CLI** (`web_fetch.cli.extended`) - Advanced resource types with enhanced formatting

## Installation

### Basic Installation
```bash
pip install web-fetch
```

### With Enhanced Formatting
```bash
pip install web-fetch rich>=13.0.0
```

### Development Installation
```bash
pip install -e .
pip install rich>=13.0.0
```

## Enhanced CLI Features

### Visual Enhancements
- 🎨 **Colored Output** - Success (green), errors (red), warnings (yellow), info (blue)
- 📊 **Progress Bars** - Visual progress for batch operations and downloads
- 📋 **Formatted Tables** - Beautiful tables for structured data display
- 🎯 **Status Indicators** - Spinners and status messages for operations
- 🖼️ **Panels and Layouts** - Organized information display
- 🌈 **Syntax Highlighting** - JSON, HTML, and code formatting

### Graceful Fallbacks
- Works even when rich library is not installed
- Automatically falls back to standard formatting
- No functionality loss when dependencies are missing

## Usage Examples

### Enhanced Main CLI

```bash
# Using entry point (if installed)
web-fetch https://httpbin.org/json

# Using module directly
python -m web_fetch.cli.main https://httpbin.org/json
```

#### Basic Operations
```bash
# Fetch with enhanced formatting
web-fetch https://httpbin.org/json --format summary --verbose

# Batch processing with progress bar
web-fetch --batch urls.txt --verbose

# Download with progress indicator
web-fetch https://example.com/file.zip --download ./downloads/ --progress

# Crawler operations with enhanced status
web-fetch --use-crawler --crawler-type firecrawl https://example.com
```

### Enhanced Extended CLI

```bash
# Using entry point
web-fetch-extended --help

# Using module directly
python -m web_fetch.cli.extended --help
```

#### Extended Operations
```bash
# Test RSS feed with enhanced formatting
web-fetch-extended test rss https://feeds.example.com/rss.xml

# Fetch RSS with enhanced progress
web-fetch-extended fetch rss https://feeds.example.com/rss.xml --max-items 50

# Database testing with enhanced panels
web-fetch-extended test database --host localhost --username user

# Cache management with enhanced tables
web-fetch-extended cache stats --backend redis
```

## Output Formats

### Summary Format (Default)
- Clean, concise output with status indicators
- Color-coded success/failure status
- Essential information only

### Detailed Format
- Comprehensive information display
- Formatted tables for headers and metadata
- Rich panels for organized sections

### JSON Format
- Syntax-highlighted JSON output
- Proper indentation and formatting
- Easy to read and parse

## Enhanced Formatting Components

### Status Messages
```
✓ Success message (green)
✗ Error message (red)
⚠ Warning message (yellow)
ℹ Info message (blue)
```

### Progress Indicators
- **Progress Bars** - For batch operations and downloads
- **Spinners** - For single operations and status updates
- **Task Tracking** - Multiple concurrent operations

### Data Display
- **Tables** - Structured data with headers and styling
- **Panels** - Grouped information with borders and titles
- **Key-Value Pairs** - Configuration and metadata display

## Configuration

### Environment Variables
```bash
# Enable/disable rich formatting
export WEBFETCH_RICH_ENABLED=true

# Set rich theme
export WEBFETCH_RICH_THEME=monokai

# Control progress display
export WEBFETCH_SHOW_PROGRESS=true
```

### Command Line Options
```bash
# Enable verbose output with rich formatting
--verbose

# Choose output format
--format [json|summary|detailed]

# Control progress display
--progress
```

## Troubleshooting

### Enhanced Formatting Not Available
If you see basic formatting instead of enhanced formatting:

```bash
# Install rich library
pip install rich>=13.0.0

# Verify installation
python -c "import rich; print(rich.__version__)"
```

### Fallback Mode
When rich is not available, the CLI automatically falls back to standard formatting:
- Basic colored output using ANSI codes
- Simple progress indicators
- Plain text tables

### Dependency Issues
If you encounter import errors:

```bash
# Reinstall with all dependencies
pip uninstall web-fetch
pip install -e .[all-features]

# Or install specific dependencies
pip install pydantic>=2.0.0 rich>=13.0.0
```

## Advanced Usage

### Custom Formatting
The enhanced CLI modules can be imported and used in your own scripts:

```python
from web_fetch.cli.formatting import Formatter, create_formatter

# Create formatter
formatter = create_formatter(verbose=True)

# Use formatting methods
formatter.print_success("Operation completed")
formatter.print_table(data, "Results")
formatter.print_json(response, "API Response")
```

### Integration with Scripts
```python
import asyncio
from web_fetch.cli.formatting import create_formatter

async def main():
    formatter = create_formatter()

    # Use enhanced formatting in your scripts
    formatter.print_info("Starting processing...")

    # Your processing logic here
    results = [{"url": "https://example.com", "status": "success"}]

    # Display results with enhanced formatting
    formatter.print_table(results, "Fetch Results")

asyncio.run(main())
```

## Best Practices

1. **Use Enhanced CLI for Interactive Work** - Better user experience with automatic fallbacks
2. **Enable Verbose Mode** - Get detailed progress information and enhanced formatting
3. **Choose Appropriate Format** - JSON for parsing, summary for reading
4. **Install Rich for Best Experience** - Enhanced formatting with rich library
5. **Fallback Mode Works** - CLI works even without rich library installed

## Support

For issues with enhanced CLI functionality:

1. Check rich library installation: `pip list | grep rich`
2. Test basic functionality: CLI works with fallback formatting
3. Enable verbose mode: `--verbose` for detailed output
4. Report issues with environment details and error messages
