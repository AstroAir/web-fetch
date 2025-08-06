---
name: Bug report
about: Create a report to help us improve
title: '[BUG] '
labels: bug
assignees: ''

---

**Describe the bug**
A clear and concise description of what the bug is.

**To Reproduce**
Steps to reproduce the behavior:
1. Code example or configuration used
2. URL or endpoint being accessed (if safe to share)
3. Expected behavior vs actual behavior

**Code Example**
```python
# Minimal code example that reproduces the issue
import asyncio
from web_fetch import fetch_url, ContentType

async def main():
    result = await fetch_url("https://example.com", ContentType.JSON)
    print(result)

asyncio.run(main())
```

**Error Message**
```
Paste the full error message and stack trace here
```

**Environment (please complete the following information):**
- OS: [e.g. Ubuntu 22.04, Windows 11, macOS 13]
- Python version: [e.g. 3.11.5]
- Web Fetch version: [e.g. 0.1.0]
- AIOHTTP version: [e.g. 3.9.0]

**Additional context**
Add any other context about the problem here:
- Network conditions
- Target server behavior
- Configuration used
- Frequency of the issue

**Possible Solution**
If you have ideas about what might be causing the issue or how to fix it, please share them here.
