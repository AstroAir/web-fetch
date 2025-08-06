# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive GitHub project organization with essential files
- MIT License
- Contributing guidelines with development workflow
- GitHub Actions CI/CD workflows for testing and releases
- Issue and PR templates
- Comprehensive .gitignore for Python projects

### Changed
- Reorganized codebase structure for better maintainability
- Moved FTP functionality to dedicated `web_fetch/ftp/` module
- Consolidated CLI into `web_fetch/cli/` module
- Removed redundant files and directories (`legacy/`, `protocols/`, duplicate model files)
- Moved utility scripts to examples directory

### Removed
- Redundant `fetcher_original.py` file
- Duplicate `models.py` and `utils.py` files in root
- Legacy compatibility module
- Protocols directory (consolidated into main structure)

## [0.1.0] - 2024-01-01

### Added
- Initial release of web-fetch library
- Modern async web scraping/fetching utility with AIOHTTP
- Support for multiple content types (JSON, HTML, text, raw bytes)
- Streaming capabilities for large files
- FTP support with async operations
- Comprehensive error handling and retry logic
- Rate limiting and caching functionality
- Command-line interface
- Enhanced features with circuit breakers and metrics
- Comprehensive test suite
- Documentation and examples

### Features
- **HTTP/HTTPS Support**
  - Async/await syntax for concurrent requests
  - Session management with connection pooling
  - Timeout configuration and retry logic
  - Content parsing (JSON, HTML, text, raw)
  - Streaming downloads with progress tracking

- **FTP Support**
  - Async FTP client with connection pooling
  - File upload/download with progress tracking
  - Batch operations and parallel transfers
  - File verification and integrity checking

- **Advanced Features**
  - Circuit breakers for fault tolerance
  - Request deduplication
  - Response transformation pipelines
  - Metrics collection and monitoring
  - Caching with TTL and LRU eviction
  - Rate limiting with token bucket algorithm

- **Developer Experience**
  - Type hints throughout the codebase
  - Comprehensive error hierarchy
  - Detailed logging and debugging support
  - Extensive test coverage
  - CLI for quick operations
  - Rich documentation and examples
