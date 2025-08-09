# Security Best Practices - Extended Resource Types

This document provides comprehensive security guidelines for using extended resource types safely and securely.

## Table of Contents

- [General Security Principles](#general-security-principles)
- [Credential Management](#credential-management)
- [Authentication Security](#authentication-security)
- [Database Security](#database-security)
- [Cloud Storage Security](#cloud-storage-security)
- [Network Security](#network-security)
- [Logging and Monitoring](#logging-and-monitoring)
- [Security Checklist](#security-checklist)

## General Security Principles

### Principle of Least Privilege

Always grant the minimum permissions necessary for your application to function.

```python
# Good: Specific permissions
s3_policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject"
            ],
            "Resource": "arn:aws:s3:::my-specific-bucket/*"
        }
    ]
}

# Bad: Overly broad permissions
bad_policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": "s3:*",
            "Resource": "*"
        }
    ]
}
```

### Defense in Depth

Implement multiple layers of security controls.

```python
# Multiple security layers
security_config = {
    "encryption": {
        "in_transit": True,      # TLS/SSL
        "at_rest": True,         # Database/storage encryption
        "key_rotation": True     # Regular key rotation
    },
    "authentication": {
        "multi_factor": True,    # MFA where possible
        "token_expiry": 3600,    # Short-lived tokens
        "refresh_tokens": True   # Token refresh mechanism
    },
    "network": {
        "vpc_isolation": True,   # Network isolation
        "firewall_rules": True,  # Restrictive firewall
        "ip_whitelisting": True  # IP restrictions
    }
}
```

### Secure by Default

Configure components with secure defaults.

```python
# Secure default configuration
secure_config = ResourceConfig(
    enable_cache=True,
    cache_ttl_seconds=300,      # Short cache TTL
    max_retries=3,              # Limited retries
    timeout_seconds=30,         # Reasonable timeout
    verify_ssl=True,            # Always verify SSL
    follow_redirects=False      # Disable redirects by default
)
```

## Credential Management

### Environment Variables

Store sensitive credentials in environment variables, never in code.

```python
import os
from pydantic import SecretStr

# Good: Environment variables
db_config = DatabaseConfig(
    database_type=DatabaseType.POSTGRESQL,
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", "5432")),
    database=os.getenv("DB_NAME"),
    username=os.getenv("DB_USER"),
    password=SecretStr(os.getenv("DB_PASSWORD"))
)

# Bad: Hardcoded credentials
bad_config = DatabaseConfig(
    database_type=DatabaseType.POSTGRESQL,
    host="db.example.com",
    port=5432,
    database="production",
    username="admin",
    password=SecretStr("password123")  # Never do this!
)
```

### Secrets Management

Use dedicated secrets management services for production environments.

```python
import boto3
from botocore.exceptions import ClientError

class SecretsManager:
    def __init__(self, region_name="us-east-1"):
        self.client = boto3.client('secretsmanager', region_name=region_name)
    
    def get_secret(self, secret_name):
        try:
            response = self.client.get_secret_value(SecretId=secret_name)
            return response['SecretString']
        except ClientError as e:
            raise Exception(f"Failed to retrieve secret {secret_name}: {e}")

# Usage with secrets manager
secrets = SecretsManager()
db_password = secrets.get_secret("production/database/password")

db_config = DatabaseConfig(
    database_type=DatabaseType.POSTGRESQL,
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", "5432")),
    database=os.getenv("DB_NAME"),
    username=os.getenv("DB_USER"),
    password=SecretStr(db_password)
)
```

### Credential Rotation

Implement regular credential rotation.

```python
import asyncio
from datetime import datetime, timedelta

class CredentialRotator:
    def __init__(self, rotation_interval_hours=24):
        self.rotation_interval = timedelta(hours=rotation_interval_hours)
        self.last_rotation = datetime.now()
        self.current_credentials = None
    
    async def get_credentials(self):
        if self._should_rotate():
            await self._rotate_credentials()
        return self.current_credentials
    
    def _should_rotate(self):
        return datetime.now() - self.last_rotation > self.rotation_interval
    
    async def _rotate_credentials(self):
        # Implement credential rotation logic
        # This could involve calling an API to generate new credentials
        pass

# Usage
rotator = CredentialRotator(rotation_interval_hours=12)
credentials = await rotator.get_credentials()
```

### SecretStr Usage

Always use `SecretStr` for sensitive data to prevent accidental logging.

```python
from pydantic import SecretStr
import logging

# Good: SecretStr prevents accidental exposure
api_config = AuthenticatedAPIConfig(
    auth_method="api_key",
    auth_config={
        "api_key": SecretStr("sensitive-api-key"),  # Won't be logged
        "key_name": "X-API-Key",
        "location": "header"
    }
)

# Logging won't expose the secret
logging.info(f"API config: {api_config}")  # api_key will show as '**********'

# Access secret value only when needed
api_key_value = api_config.auth_config["api_key"].get_secret_value()
```

## Authentication Security

### OAuth 2.0 Security

Implement OAuth 2.0 securely with proper validation.

```python
import jwt
import time
from datetime import datetime, timedelta

class SecureOAuthConfig:
    def __init__(self, client_id, client_secret, token_url):
        self.client_id = client_id
        self.client_secret = SecretStr(client_secret)
        self.token_url = token_url
        self.token_cache = {}
    
    def validate_token(self, token):
        try:
            # Decode without verification to check expiry
            decoded = jwt.decode(token, options={"verify_signature": False})
            exp = decoded.get('exp')
            
            if exp and exp < time.time():
                return False, "Token expired"
            
            # Additional validation
            if decoded.get('iss') != self.expected_issuer:
                return False, "Invalid issuer"
            
            if decoded.get('aud') != self.client_id:
                return False, "Invalid audience"
            
            return True, "Valid"
        except jwt.InvalidTokenError as e:
            return False, f"Invalid token: {e}"
    
    async def get_secure_token(self):
        # Implement secure token acquisition with validation
        pass

# Secure OAuth configuration
oauth_config = AuthenticatedAPIConfig(
    auth_method="oauth2",
    auth_config={
        "token_url": "https://secure-auth.example.com/oauth/token",
        "client_id": os.getenv("OAUTH_CLIENT_ID"),
        "client_secret": os.getenv("OAUTH_CLIENT_SECRET"),
        "grant_type": "client_credentials",
        "scope": "read write",
        "audience": "https://api.example.com",
        "validate_ssl": True,
        "timeout": 30
    },
    retry_on_auth_failure=True,
    refresh_token_threshold=300,  # Refresh 5 minutes before expiry
    base_headers={
        "User-Agent": "SecureApp/1.0",
        "Accept": "application/json"
    }
)
```

### API Key Security

Secure API key management and usage.

```python
import hashlib
import hmac
import time

class SecureAPIKeyManager:
    def __init__(self, api_key, signing_secret=None):
        self.api_key = SecretStr(api_key)
        self.signing_secret = SecretStr(signing_secret) if signing_secret else None
    
    def generate_signature(self, payload, timestamp=None):
        """Generate HMAC signature for request validation."""
        if not self.signing_secret:
            return None
        
        timestamp = timestamp or str(int(time.time()))
        message = f"{timestamp}.{payload}"
        
        signature = hmac.new(
            self.signing_secret.get_secret_value().encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return f"t={timestamp},v1={signature}"
    
    def validate_signature(self, payload, signature_header, tolerance=300):
        """Validate incoming webhook signature."""
        if not self.signing_secret:
            return False
        
        try:
            elements = dict(item.split('=') for item in signature_header.split(','))
            timestamp = int(elements['t'])
            signature = elements['v1']
            
            # Check timestamp tolerance
            if abs(time.time() - timestamp) > tolerance:
                return False
            
            # Verify signature
            expected_signature = hmac.new(
                self.signing_secret.get_secret_value().encode(),
                f"{timestamp}.{payload}".encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
        except (KeyError, ValueError):
            return False

# Secure API key configuration
api_key_manager = SecureAPIKeyManager(
    api_key=os.getenv("API_KEY"),
    signing_secret=os.getenv("API_SIGNING_SECRET")
)

api_config = AuthenticatedAPIConfig(
    auth_method="api_key",
    auth_config={
        "api_key": api_key_manager.api_key.get_secret_value(),
        "key_name": "X-API-Key",
        "location": "header",
        "validate_signature": True
    },
    base_headers={
        "User-Agent": "SecureApp/1.0",
        "X-Request-ID": lambda: str(uuid.uuid4())  # Unique request ID
    }
)
```

### JWT Security

Implement secure JWT handling with proper validation.

```python
import jwt
from cryptography.hazmat.primitives import serialization

class SecureJWTHandler:
    def __init__(self, private_key_path=None, public_key_path=None, algorithm="RS256"):
        self.algorithm = algorithm
        self.private_key = None
        self.public_key = None
        
        if private_key_path:
            with open(private_key_path, 'rb') as f:
                self.private_key = serialization.load_pem_private_key(
                    f.read(), password=None
                )
        
        if public_key_path:
            with open(public_key_path, 'rb') as f:
                self.public_key = serialization.load_pem_public_key(f.read())
    
    def create_token(self, payload, expires_in=3600):
        """Create a secure JWT token."""
        if not self.private_key:
            raise ValueError("Private key required for token creation")
        
        now = datetime.utcnow()
        payload.update({
            'iat': now,
            'exp': now + timedelta(seconds=expires_in),
            'nbf': now,
            'jti': str(uuid.uuid4())  # Unique token ID
        })
        
        return jwt.encode(payload, self.private_key, algorithm=self.algorithm)
    
    def validate_token(self, token):
        """Validate JWT token with comprehensive checks."""
        try:
            if not self.public_key:
                raise ValueError("Public key required for token validation")
            
            decoded = jwt.decode(
                token,
                self.public_key,
                algorithms=[self.algorithm],
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iat": True,
                    "require": ["exp", "iat", "nbf", "jti"]
                }
            )
            
            return True, decoded
        except jwt.ExpiredSignatureError:
            return False, "Token expired"
        except jwt.InvalidTokenError as e:
            return False, f"Invalid token: {e}"

# Secure JWT configuration
jwt_handler = SecureJWTHandler(
    private_key_path="/secure/path/to/private_key.pem",
    public_key_path="/secure/path/to/public_key.pem"
)

jwt_config = AuthenticatedAPIConfig(
    auth_method="jwt",
    auth_config={
        "token": jwt_handler.create_token({"sub": "user123", "scope": "read"}),
        "header_name": "Authorization",
        "prefix": "Bearer",
        "verify_signature": True,
        "verify_expiry": True,
        "algorithm": "RS256"
    }
)
```

## Database Security

### Connection Security

Always use encrypted connections and proper authentication.

```python
# Secure PostgreSQL configuration
secure_pg_config = DatabaseConfig(
    database_type=DatabaseType.POSTGRESQL,
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", "5432")),
    database=os.getenv("DB_NAME"),
    username=os.getenv("DB_USER"),
    password=SecretStr(os.getenv("DB_PASSWORD")),
    ssl_mode="require",  # Force SSL
    extra_params={
        "sslcert": "/secure/path/to/client-cert.pem",
        "sslkey": "/secure/path/to/client-key.pem",
        "sslrootcert": "/secure/path/to/ca-cert.pem",
        "sslmode": "verify-full",  # Verify certificate and hostname
        "application_name": "secure-web-fetch",
        "connect_timeout": 10,
        "command_timeout": 30
    }
)
```

### SQL Injection Prevention

Always use parameterized queries to prevent SQL injection.

```python
# Good: Parameterized queries
safe_query = DatabaseQuery(
    query="SELECT * FROM users WHERE email = $1 AND status = $2",
    parameters={"$1": user_email, "$2": "active"},
    fetch_mode="all"
)

# Input validation and sanitization
import re
from typing import Optional

def validate_email(email: str) -> Optional[str]:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if re.match(pattern, email):
        return email
    return None

def sanitize_table_name(table_name: str) -> str:
    """Sanitize table name to prevent injection."""
    # Only allow alphanumeric characters and underscores
    if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
        return table_name
    raise ValueError(f"Invalid table name: {table_name}")
```

## Cloud Storage Security

### Encryption and Access Control

Always use encryption and proper access control policies.

```python
# AWS S3 with encryption
secure_s3_config = CloudStorageConfig(
    provider=CloudStorageProvider.AWS_S3,
    bucket_name=os.getenv("S3_BUCKET_NAME"),
    access_key=SecretStr(os.getenv("AWS_ACCESS_KEY_ID")),
    secret_key=SecretStr(os.getenv("AWS_SECRET_ACCESS_KEY")),
    region=os.getenv("AWS_REGION", "us-east-1"),
    extra_config={
        "use_ssl": True,  # Encryption in transit
        "verify": True,   # Verify SSL certificates
        "server_side_encryption": "aws:kms",  # Encryption at rest
        "sse_kms_key_id": os.getenv("KMS_KEY_ID"),
        "bucket_key_enabled": True,
        "signature_version": "s3v4",
        "addressing_style": "virtual"
    }
)
```

## Network Security

### TLS/SSL Configuration

Always use secure TLS configurations.

```python
import ssl

# Secure SSL context
def create_secure_ssl_context():
    context = ssl.create_default_context()
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.maximum_version = ssl.TLSVersion.TLSv1_3

    # Disable weak ciphers
    context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')

    return context

# Use secure context in HTTP configuration
http_config = FetchConfig(
    verify_ssl=True,
    ssl_context=create_secure_ssl_context(),
    timeout_seconds=30,
    max_retries=3
)
```

## Logging and Monitoring

### Security Logging

Implement comprehensive security logging without exposing sensitive data.

```python
import logging
from datetime import datetime

class SecurityLogger:
    def __init__(self):
        self.logger = logging.getLogger('web_fetch.security')
        self.logger.setLevel(logging.INFO)

        # Create secure formatter that masks sensitive data
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def log_auth_attempt(self, method, success, user_id=None, ip_address=None):
        """Log authentication attempts."""
        self.logger.info(
            f"Auth attempt: method={method}, success={success}, "
            f"user={user_id or 'unknown'}, ip={ip_address or 'unknown'}"
        )

    def log_data_access(self, resource_type, operation, user_id=None):
        """Log data access events."""
        self.logger.info(
            f"Data access: type={resource_type}, operation={operation}, "
            f"user={user_id or 'unknown'}, timestamp={datetime.utcnow().isoformat()}"
        )

    def log_security_event(self, event_type, details, severity="INFO"):
        """Log security events."""
        log_method = getattr(self.logger, severity.lower())
        log_method(f"Security event: {event_type} - {details}")

# Usage
security_logger = SecurityLogger()

class SecureResourceComponent(ResourceComponent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.security_logger = SecurityLogger()

    async def fetch(self, request):
        # Log access attempt
        self.security_logger.log_data_access(
            resource_type=self.kind.value,
            operation="fetch",
            user_id=getattr(request, 'user_id', None)
        )

        result = await super().fetch(request)

        # Log result (without sensitive data)
        if result.is_success:
            self.security_logger.log_security_event(
                "data_access_success",
                f"Resource {self.kind.value} accessed successfully"
            )
        else:
            self.security_logger.log_security_event(
                "data_access_failure",
                f"Resource {self.kind.value} access failed: {result.error}",
                severity="WARNING"
            )

        return result
```

## Security Checklist

### Pre-Production Checklist

- [ ] **Credentials Management**
  - [ ] All credentials stored in environment variables or secrets manager
  - [ ] No hardcoded credentials in code
  - [ ] SecretStr used for all sensitive data
  - [ ] Credential rotation implemented

- [ ] **Authentication Security**
  - [ ] Strong authentication methods implemented
  - [ ] Token expiration and refresh configured
  - [ ] Multi-factor authentication where possible
  - [ ] Signature validation for webhooks

- [ ] **Database Security**
  - [ ] SSL/TLS encryption enabled
  - [ ] Parameterized queries used exclusively
  - [ ] Database user permissions minimized
  - [ ] Connection pooling configured securely

- [ ] **Cloud Storage Security**
  - [ ] Encryption at rest and in transit enabled
  - [ ] IAM policies follow least privilege principle
  - [ ] Bucket policies restrict access appropriately
  - [ ] Access logging enabled

- [ ] **Network Security**
  - [ ] TLS 1.2+ enforced
  - [ ] Certificate validation enabled
  - [ ] IP whitelisting implemented where appropriate
  - [ ] Firewall rules configured

- [ ] **Monitoring and Logging**
  - [ ] Security events logged
  - [ ] Sensitive data masked in logs
  - [ ] Log monitoring and alerting configured
  - [ ] Audit trails maintained

### Regular Security Maintenance

- [ ] **Monthly Tasks**
  - [ ] Review access logs for anomalies
  - [ ] Update dependencies and security patches
  - [ ] Rotate credentials and certificates
  - [ ] Review and update security policies

- [ ] **Quarterly Tasks**
  - [ ] Security audit and penetration testing
  - [ ] Review and update IAM policies
  - [ ] Disaster recovery testing
  - [ ] Security training for development team

- [ ] **Annual Tasks**
  - [ ] Comprehensive security assessment
  - [ ] Update security documentation
  - [ ] Review and update incident response procedures
  - [ ] Compliance audit (if applicable)
