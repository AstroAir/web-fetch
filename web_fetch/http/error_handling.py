"""
Security-focused error handling for web_fetch HTTP components.

This module provides secure error handling with information disclosure prevention,
safe logging, and security-aware error responses.
"""

import logging
import traceback
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field

from ..exceptions import WebFetchError


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(str, Enum):
    """Error categories for classification."""
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    NETWORK = "network"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    SERVER_ERROR = "server_error"
    CLIENT_ERROR = "client_error"
    SECURITY = "security"
    UNKNOWN = "unknown"


class SecureErrorConfig(BaseModel):
    """Configuration for secure error handling."""
    
    # Information disclosure settings
    expose_internal_errors: bool = Field(
        default=False,
        description="Whether to expose internal error details"
    )
    
    expose_stack_traces: bool = Field(
        default=False,
        description="Whether to include stack traces in responses"
    )
    
    expose_server_info: bool = Field(
        default=False,
        description="Whether to expose server information"
    )
    
    # Logging settings
    log_sensitive_data: bool = Field(
        default=False,
        description="Whether to log potentially sensitive data"
    )
    
    log_full_requests: bool = Field(
        default=False,
        description="Whether to log full request details"
    )
    
    max_log_length: int = Field(
        default=1000,
        ge=100,
        description="Maximum length of logged messages"
    )
    
    # Error response settings
    include_error_id: bool = Field(
        default=True,
        description="Whether to include error IDs in responses"
    )
    
    include_timestamp: bool = Field(
        default=True,
        description="Whether to include timestamps in error responses"
    )
    
    generic_error_message: str = Field(
        default="An error occurred while processing your request",
        description="Generic error message for security"
    )


class SecureError(BaseModel):
    """Secure error representation."""
    
    error_id: str = Field(description="Unique error identifier")
    category: ErrorCategory = Field(description="Error category")
    severity: ErrorSeverity = Field(description="Error severity")
    message: str = Field(description="Safe error message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Safe error details")
    timestamp: Optional[str] = Field(default=None, description="Error timestamp")
    
    # Internal fields (not exposed in responses)
    internal_message: Optional[str] = Field(default=None, description="Internal error message")
    stack_trace: Optional[str] = Field(default=None, description="Stack trace")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Error context")


class SecurityErrorHandler:
    """Security-focused error handler."""
    
    def __init__(self, config: Optional[SecureErrorConfig] = None):
        """
        Initialize security error handler.
        
        Args:
            config: Error handling configuration
        """
        self.config = config or SecureErrorConfig()
        self.logger = logging.getLogger(__name__)
        
        # Sensitive data patterns to redact
        self._sensitive_patterns = [
            r'password["\']?\s*[:=]\s*["\']?([^"\']+)',
            r'token["\']?\s*[:=]\s*["\']?([^"\']+)',
            r'key["\']?\s*[:=]\s*["\']?([^"\']+)',
            r'secret["\']?\s*[:=]\s*["\']?([^"\']+)',
            r'authorization["\']?\s*[:=]\s*["\']?([^"\']+)',
            r'cookie["\']?\s*[:=]\s*["\']?([^"\']+)',
        ]
        
        # Compile patterns for efficiency
        import re
        self._compiled_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self._sensitive_patterns
        ]
    
    def handle_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        category: Optional[ErrorCategory] = None,
        severity: Optional[ErrorSeverity] = None
    ) -> SecureError:
        """
        Handle an error securely.
        
        Args:
            error: Exception to handle
            context: Additional context information
            category: Error category
            severity: Error severity
            
        Returns:
            SecureError object
        """
        error_id = str(uuid4())
        
        # Determine category and severity
        if category is None:
            category = self._categorize_error(error)
        
        if severity is None:
            severity = self._determine_severity(error, category)
        
        # Create secure error
        secure_error = SecureError(
            error_id=error_id,
            category=category,
            severity=severity,
            message=self._get_safe_message(error, category),
            internal_message=str(error),
            context=context
        )
        
        # Add timestamp if configured
        if self.config.include_timestamp:
            from datetime import datetime
            secure_error.timestamp = datetime.utcnow().isoformat()
        
        # Add stack trace if configured
        if self.config.expose_stack_traces:
            secure_error.stack_trace = traceback.format_exc()
        
        # Add safe details if configured
        if self.config.expose_internal_errors:
            secure_error.details = self._get_safe_details(error, context)
        
        # Log the error
        self._log_error(secure_error, error)
        
        return secure_error
    
    def _categorize_error(self, error: Exception) -> ErrorCategory:
        """Categorize error based on type and message."""
        error_type = type(error).__name__.lower()
        error_message = str(error).lower()
        
        # Network-related errors
        if any(keyword in error_type for keyword in ['connection', 'network', 'socket']):
            return ErrorCategory.NETWORK
        
        # Timeout errors
        if 'timeout' in error_type or 'timeout' in error_message:
            return ErrorCategory.TIMEOUT
        
        # Authentication/Authorization
        if any(keyword in error_message for keyword in ['unauthorized', 'forbidden', 'auth']):
            if 'unauthorized' in error_message:
                return ErrorCategory.AUTHENTICATION
            else:
                return ErrorCategory.AUTHORIZATION
        
        # Validation errors
        if any(keyword in error_type for keyword in ['validation', 'value', 'type']):
            return ErrorCategory.VALIDATION
        
        # Rate limiting
        if 'rate' in error_message and 'limit' in error_message:
            return ErrorCategory.RATE_LIMIT
        
        # Security-related
        if any(keyword in error_message for keyword in ['security', 'blocked', 'suspicious']):
            return ErrorCategory.SECURITY
        
        # HTTP status-based categorization
        if hasattr(error, 'status') or hasattr(error, 'status_code'):
            status = getattr(error, 'status', None) or getattr(error, 'status_code', None)
            if status:
                if 400 <= status < 500:
                    return ErrorCategory.CLIENT_ERROR
                elif 500 <= status < 600:
                    return ErrorCategory.SERVER_ERROR
        
        return ErrorCategory.UNKNOWN
    
    def _determine_severity(self, error: Exception, category: ErrorCategory) -> ErrorSeverity:
        """Determine error severity."""
        # Critical errors
        if category in [ErrorCategory.SECURITY, ErrorCategory.AUTHENTICATION]:
            return ErrorSeverity.CRITICAL
        
        # High severity errors
        if category in [ErrorCategory.AUTHORIZATION, ErrorCategory.SERVER_ERROR]:
            return ErrorSeverity.HIGH
        
        # Medium severity errors
        if category in [ErrorCategory.NETWORK, ErrorCategory.TIMEOUT, ErrorCategory.RATE_LIMIT]:
            return ErrorSeverity.MEDIUM
        
        # Low severity errors
        return ErrorSeverity.LOW
    
    def _get_safe_message(self, error: Exception, category: ErrorCategory) -> str:
        """Get safe error message for public consumption."""
        if not self.config.expose_internal_errors:
            # Return generic message for security
            return self.config.generic_error_message
        
        # Category-specific safe messages
        safe_messages = {
            ErrorCategory.VALIDATION: "Invalid input provided",
            ErrorCategory.AUTHENTICATION: "Authentication required",
            ErrorCategory.AUTHORIZATION: "Access denied",
            ErrorCategory.NETWORK: "Network connection failed",
            ErrorCategory.TIMEOUT: "Request timed out",
            ErrorCategory.RATE_LIMIT: "Rate limit exceeded",
            ErrorCategory.SERVER_ERROR: "Internal server error",
            ErrorCategory.CLIENT_ERROR: "Invalid request",
            ErrorCategory.SECURITY: "Security policy violation",
        }
        
        return safe_messages.get(category, self.config.generic_error_message)
    
    def _get_safe_details(self, error: Exception, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Get safe error details."""
        details = {}
        
        # Add error type if configured
        if self.config.expose_internal_errors:
            details['error_type'] = type(error).__name__
        
        # Add safe context information
        if context:
            safe_context: Dict[str, str] = {}
            for key, value in context.items():
                # Skip sensitive keys
                if any(sensitive in key.lower() for sensitive in ['password', 'token', 'key', 'secret']):
                    continue

                # Redact sensitive values
                safe_value = self._redact_sensitive_data(str(value))
                safe_context[key] = safe_value
            
            if safe_context:
                details.update(safe_context)
        
        return details
    
    def _redact_sensitive_data(self, text: str) -> str:
        """Redact sensitive data from text."""
        if not self.config.log_sensitive_data:
            for pattern in self._compiled_patterns:
                text = pattern.sub(lambda m: m.group(0).replace(m.group(1), '*' * len(m.group(1))), text)
        
        return text
    
    def _log_error(self, secure_error: SecureError, original_error: Exception) -> None:
        """Log error securely."""
        # Prepare log message
        log_message = f"Error {secure_error.error_id}: {secure_error.category.value} - {secure_error.internal_message}"
        
        # Truncate if too long
        if len(log_message) > self.config.max_log_length:
            log_message = log_message[:self.config.max_log_length] + "..."
        
        # Redact sensitive data
        log_message = self._redact_sensitive_data(log_message)
        
        # Log based on severity
        if secure_error.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(log_message, extra={'error_id': secure_error.error_id})
        elif secure_error.severity == ErrorSeverity.HIGH:
            self.logger.error(log_message, extra={'error_id': secure_error.error_id})
        elif secure_error.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(log_message, extra={'error_id': secure_error.error_id})
        else:
            self.logger.info(log_message, extra={'error_id': secure_error.error_id})
        
        # Log stack trace separately if configured
        if self.config.expose_stack_traces and secure_error.stack_trace:
            stack_trace = self._redact_sensitive_data(secure_error.stack_trace)
            self.logger.debug(f"Stack trace for {secure_error.error_id}: {stack_trace}")
    
    def to_response_dict(self, secure_error: SecureError) -> Dict[str, Any]:
        """Convert secure error to response dictionary."""
        response = {
            'error': True,
            'message': secure_error.message,
            'category': secure_error.category.value,
        }
        
        if self.config.include_error_id:
            response['error_id'] = secure_error.error_id
        
        if self.config.include_timestamp and secure_error.timestamp:
            response['timestamp'] = secure_error.timestamp
        
        if secure_error.details:
            response['details'] = secure_error.details
        
        return response


# Global error handler instance
_global_error_handler: Optional[SecurityErrorHandler] = None


def get_global_error_handler(config: Optional[SecureErrorConfig] = None) -> SecurityErrorHandler:
    """Get or create global error handler."""
    global _global_error_handler
    
    if _global_error_handler is None:
        _global_error_handler = SecurityErrorHandler(config)
    
    return _global_error_handler


def handle_http_error(
    error: Exception,
    context: Optional[Dict[str, Any]] = None,
    config: Optional[SecureErrorConfig] = None
) -> Dict[str, Any]:
    """
    Handle HTTP error and return safe response.
    
    Args:
        error: Exception to handle
        context: Additional context
        config: Error handling configuration
        
    Returns:
        Safe error response dictionary
    """
    handler = get_global_error_handler(config)
    secure_error = handler.handle_error(error, context)
    return handler.to_response_dict(secure_error)
