# Error Code Reference

This document provides a comprehensive reference for all error codes and messages used in the web-fetch library's extended resource types.

## Table of Contents

- [General Error Patterns](#general-error-patterns)
- [RSS/Atom Feed Errors](#rssatom-feed-errors)
- [Authenticated API Errors](#authenticated-api-errors)
- [Database Errors](#database-errors)
- [Cloud Storage Errors](#cloud-storage-errors)
- [HTTP Status Code Mapping](#http-status-code-mapping)
- [Troubleshooting Guide](#troubleshooting-guide)

## General Error Patterns

All error messages in web-fetch follow consistent patterns for easy identification and handling:

### Error Message Format

```
{Component} {Operation} error: {Specific Error Description}
```

Examples:

- `RSS feed fetch error: Invalid XML content`
- `Database query error: Connection failed`
- `Cloud storage error: Invalid credentials`

### Error Categories

1. **Network Errors**: Connection, timeout, DNS resolution issues
2. **Authentication Errors**: Invalid credentials, expired tokens, permission denied
3. **Validation Errors**: Invalid input, malformed data, constraint violations
4. **Configuration Errors**: Missing required settings, invalid configuration values
5. **Service Errors**: External service failures, rate limiting, service unavailable

## RSS/Atom Feed Errors

### Feed Parsing Errors

| Error Message | Description | Cause | Solution |
|---------------|-------------|-------|----------|
| `RSS feed fetch error: Invalid XML content` | Feed content is not valid XML | Malformed XML, non-XML response | Verify feed URL returns valid XML |
| `RSS feed fetch error: Network timeout` | Request timed out | Slow server, network issues | Increase timeout, check network |
| `RSS feed fetch error: HTTP {status_code}` | HTTP error response | Server error, invalid URL | Check URL, server status |
| `Feed missing required title or description` | Feed lacks essential metadata | Incomplete feed structure | Contact feed provider |
| `Feed items must be a list` | Invalid feed item structure | Malformed feed data | Verify feed format |

### Feed Validation Errors

| Error Message | Description | Cause | Solution |
|---------------|-------------|-------|----------|
| `Invalid feed content structure` | Feed data is not a dictionary | Parsing failure, invalid response | Check feed URL and format |
| `Feed validation failed: {details}` | General validation error | Various validation issues | Check error details for specifics |

### Example Error Handling

```python
from web_fetch import fetch_rss_feed

result = await fetch_rss_feed("https://example.com/feed.xml")

if not result.is_success:
    error = result.error
    
    if "Invalid XML content" in error:
        print("Feed contains malformed XML")
    elif "Network timeout" in error:
        print("Feed server is slow or unreachable")
    elif "HTTP" in error:
        print(f"Server returned error: {error}")
    else:
        print(f"Unknown feed error: {error}")
```

## Authenticated API Errors

### Authentication Errors

| Error Message | Description | Cause | Solution |
|---------------|-------------|-------|----------|
| `Authentication failed: Invalid credentials` | Credentials are incorrect | Wrong API key, client ID/secret | Verify credentials |
| `Authentication failed: Token expired` | Access token has expired | Token lifetime exceeded | Refresh token or re-authenticate |
| `Authentication failed: Invalid token format` | Token format is incorrect | Malformed JWT, invalid encoding | Check token generation |
| `OAuth token request failed: {details}` | OAuth token acquisition failed | Invalid OAuth configuration | Verify OAuth settings |
| `API key authentication failed: {details}` | API key authentication failed | Invalid key or configuration | Check API key settings |

### API Request Errors

| Error Message | Description | Cause | Solution |
|---------------|-------------|-------|----------|
| `Authenticated API fetch error: {details}` | General API request failure | Various API issues | Check error details |
| `API validation failed: {details}` | Response validation failed | Invalid response format | Check API response structure |
| `Rate limit exceeded` | Too many requests | API rate limiting | Implement backoff, reduce frequency |

### Example Error Handling

```python
from web_fetch import fetch_authenticated_api

result = await fetch_authenticated_api(url, config=auth_config)

if not result.is_success:
    error = result.error
    
    if "Invalid credentials" in error:
        print("Check your API credentials")
    elif "Token expired" in error:
        print("Token needs refresh")
    elif "Rate limit" in error:
        print("Slow down API requests")
    else:
        print(f"API error: {error}")
        
    # Check authentication metadata
    auth_metadata = result.metadata.get('authentication', {})
    if not auth_metadata.get('authenticated', False):
        print("Authentication failed")
```

## Database Errors

### Connection Errors

| Error Message | Description | Cause | Solution |
|---------------|-------------|-------|----------|
| `Database query error: Connection failed` | Cannot connect to database | Network, credentials, server down | Check connection parameters |
| `Database query error: Authentication failed` | Database login failed | Wrong username/password | Verify database credentials |
| `Database query error: Database not found` | Target database doesn't exist | Wrong database name | Check database name |
| `Database query error: Connection timeout` | Connection attempt timed out | Slow network, server overload | Increase timeout, check network |

### Query Errors

| Error Message | Description | Cause | Solution |
|---------------|-------------|-------|----------|
| `Database query error: Invalid query syntax` | SQL syntax error | Malformed SQL query | Fix SQL syntax |
| `Database query error: Table not found` | Referenced table doesn't exist | Wrong table name, missing table | Verify table exists |
| `Database query error: Permission denied` | Insufficient database permissions | User lacks required permissions | Grant necessary permissions |
| `Database query error: Query timeout` | Query execution timed out | Complex query, large dataset | Optimize query, increase timeout |

### MongoDB-Specific Errors

| Error Message | Description | Cause | Solution |
|---------------|-------------|-------|----------|
| `MongoDB query must be valid JSON` | Query is not valid JSON | Malformed query structure | Fix JSON format |
| `Database query error: Collection not found` | MongoDB collection doesn't exist | Wrong collection name | Verify collection name |
| `Database query error: Invalid operation` | Unsupported MongoDB operation | Wrong operation type | Use supported operations |

### Example Error Handling

```python
from web_fetch import fetch_database_query

result = await fetch_database_query(db_config, query)

if not result.is_success:
    error = result.error
    
    if "Connection failed" in error:
        print("Cannot connect to database")
    elif "Authentication failed" in error:
        print("Database login failed")
    elif "Invalid query syntax" in error:
        print("SQL syntax error")
    elif "Permission denied" in error:
        print("Insufficient database permissions")
    else:
        print(f"Database error: {error}")
```

## Cloud Storage Errors

### Authentication Errors

| Error Message | Description | Cause | Solution |
|---------------|-------------|-------|----------|
| `Cloud storage error: Invalid credentials` | Storage credentials are wrong | Wrong access key/secret | Verify credentials |
| `Cloud storage error: Access denied` | Insufficient permissions | Limited IAM permissions | Grant required permissions |
| `Cloud storage error: Token expired` | Temporary credentials expired | Session token expired | Refresh credentials |

### Storage Operation Errors

| Error Message | Description | Cause | Solution |
|---------------|-------------|-------|----------|
| `Cloud storage error: Bucket not found` | Storage bucket doesn't exist | Wrong bucket name, deleted bucket | Verify bucket name |
| `Cloud storage error: Object not found` | Requested object doesn't exist | Wrong object key, deleted object | Check object key |
| `Cloud storage error: Permission denied` | Insufficient object permissions | Limited access to object | Grant object permissions |
| `Cloud storage error: Storage quota exceeded` | Storage limit reached | Account storage limit | Increase quota or clean up |

### Provider-Specific Errors

#### AWS S3 Errors

| Error Message | Description | Cause | Solution |
|---------------|-------------|-------|----------|
| `Cloud storage error: NoSuchBucket` | S3 bucket doesn't exist | Wrong bucket name | Verify bucket name |
| `Cloud storage error: InvalidAccessKeyId` | AWS access key is invalid | Wrong access key | Check AWS credentials |
| `Cloud storage error: SignatureDoesNotMatch` | AWS signature mismatch | Wrong secret key, clock skew | Verify secret key, sync time |

#### Google Cloud Storage Errors

| Error Message | Description | Cause | Solution |
|---------------|-------------|-------|----------|
| `Cloud storage error: 403 Forbidden` | GCS access denied | Insufficient permissions | Check IAM permissions |
| `Cloud storage error: 404 Not Found` | GCS bucket/object not found | Wrong name or deleted | Verify names |

#### Azure Blob Storage Errors

| Error Message | Description | Cause | Solution |
|---------------|-------------|-------|----------|
| `Cloud storage error: AuthenticationFailed` | Azure auth failed | Wrong account key | Verify account credentials |
| `Cloud storage error: ContainerNotFound` | Container doesn't exist | Wrong container name | Check container name |

### Example Error Handling

```python
from web_fetch import fetch_cloud_storage

result = await fetch_cloud_storage(storage_config, operation)

if not result.is_success:
    error = result.error
    
    if "Invalid credentials" in error:
        print("Check storage credentials")
    elif "Bucket not found" in error:
        print("Verify bucket name")
    elif "Permission denied" in error:
        print("Insufficient storage permissions")
    elif "NoSuchBucket" in error:
        print("AWS S3 bucket doesn't exist")
    else:
        print(f"Storage error: {error}")
```

## HTTP Status Code Mapping

Extended resource types map internal errors to appropriate HTTP status codes:

| Status Code | Description | Common Causes |
|-------------|-------------|---------------|
| 200 | Success | Operation completed successfully |
| 400 | Bad Request | Invalid input, malformed data |
| 401 | Unauthorized | Authentication failed, invalid credentials |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource doesn't exist |
| 408 | Request Timeout | Operation timed out |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Unexpected error, service failure |
| 502 | Bad Gateway | External service error |
| 503 | Service Unavailable | Service temporarily unavailable |

## Troubleshooting Guide

### Quick Diagnosis

1. **Check error message pattern** to identify component and operation
2. **Look for specific error details** in the message
3. **Check metadata** for additional context
4. **Verify configuration** for the failing component
5. **Test connectivity** to external services

### Common Solutions

#### Network Issues

- Increase timeout values
- Check firewall settings
- Verify DNS resolution
- Test with curl/ping

#### Authentication Issues

- Verify credentials are correct
- Check token expiration
- Ensure proper permissions
- Test with provider's CLI tools

#### Configuration Issues

- Validate all required fields
- Check data types (SecretStr for passwords)
- Verify URLs and endpoints
- Test with minimal configuration

### Getting Help

When reporting issues, include:

1. Complete error message
2. Component configuration (without secrets)
3. Request details
4. Metadata from the result
5. Steps to reproduce

Example bug report:

```python
# Error occurred
result = await fetch_rss_feed("https://example.com/feed.xml")
print(f"Error: {result.error}")
print(f"Status: {result.status_code}")
print(f"Metadata: {result.metadata}")

# Configuration used (remove secrets)
config = RSSConfig(
    max_items=50,
    include_content=True,
    validate_dates=True
)
```
