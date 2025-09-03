"""
Comprehensive tests for the enhanced authentication system.

This module tests all the new authentication features including
configuration, credential management, retry policies, and session management.
"""

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from web_fetch.auth.config import (
    AuthenticationConfig,
    CredentialConfig,
    CredentialSource,
    EnhancedAPIKeyConfig,
    RetryPolicy,
    SecurityConfig,
    SessionConfig,
)
from web_fetch.auth.credential_store import (
    CredentialManager,
    EncryptedFileStore,
    InMemoryStore,
)
from web_fetch.auth.enhanced_manager import EnhancedAuthManager
from web_fetch.auth.retry import (
    AuthErrorType,
    AuthenticationError,
    CircuitBreaker,
    RetryHandler,
    classify_error,
)
from web_fetch.auth.session import SessionInfo, SessionManager
from web_fetch.auth.base import AuthResult, AuthType, AuthLocation


class TestCredentialConfig:
    """Test credential configuration and resolution."""
    
    def test_direct_credential_config(self):
        """Test direct credential configuration."""
        config = CredentialConfig(
            source=CredentialSource.DIRECT,
            value="test-secret"
        )
        
        assert config.get_credential_value() == "test-secret"
    
    def test_environment_credential_config(self):
        """Test environment variable credential configuration."""
        os.environ["TEST_CREDENTIAL"] = "env-secret"
        
        config = CredentialConfig(
            source=CredentialSource.ENVIRONMENT,
            env_var="TEST_CREDENTIAL"
        )
        
        assert config.get_credential_value() == "env-secret"
        
        # Cleanup
        del os.environ["TEST_CREDENTIAL"]
    
    def test_file_credential_config(self):
        """Test file-based credential configuration."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("file-secret")
            temp_path = Path(f.name)
        
        try:
            config = CredentialConfig(
                source=CredentialSource.FILE,
                file_path=temp_path
            )
            
            assert config.get_credential_value() == "file-secret"
        finally:
            temp_path.unlink()
    
    def test_credential_validation(self):
        """Test credential configuration validation."""
        # Should raise error for direct source without value
        with pytest.raises(ValueError, match="Direct credential source requires 'value'"):
            CredentialConfig(source=CredentialSource.DIRECT)
        
        # Should raise error for environment source without env_var
        with pytest.raises(ValueError, match="Environment credential source requires 'env_var'"):
            CredentialConfig(source=CredentialSource.ENVIRONMENT)


class TestCredentialStore:
    """Test credential storage systems."""
    
    @pytest.mark.asyncio
    async def test_in_memory_store(self):
        """Test in-memory credential store."""
        store = InMemoryStore()
        
        # Store credential
        await store.store_credential("test-key", "test-value", {"type": "api_key"})
        
        # Retrieve credential
        value = await store.retrieve_credential("test-key")
        assert value == "test-value"
        
        # List credentials
        keys = await store.list_credentials()
        assert "test-key" in keys
        
        # Delete credential
        success = await store.delete_credential("test-key")
        assert success
        
        # Verify deletion
        value = await store.retrieve_credential("test-key")
        assert value is None
    
    @pytest.mark.asyncio
    async def test_encrypted_file_store(self):
        """Test encrypted file credential store."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = EncryptedFileStore(Path(temp_dir), master_key="test-master-key")
            
            # Store credential
            await store.store_credential("test-key", "test-value", {"type": "api_key"})
            
            # Retrieve credential
            value = await store.retrieve_credential("test-key")
            assert value == "test-value"
            
            # Verify file is encrypted (not readable as plain text)
            credential_files = list(Path(temp_dir).glob("*.cred"))
            assert len(credential_files) == 1
            
            with open(credential_files[0], 'rb') as f:
                encrypted_content = f.read()
                assert b"test-value" not in encrypted_content  # Should be encrypted
            
            # Test rotation
            await store.rotate_credential("test-key", "new-value")
            value = await store.retrieve_credential("test-key")
            assert value == "new-value"
    
    @pytest.mark.asyncio
    async def test_credential_manager(self):
        """Test credential manager functionality."""
        store = InMemoryStore()
        manager = CredentialManager(store)
        
        # Test direct credential resolution
        config = CredentialConfig(source=CredentialSource.DIRECT, value="direct-value")
        value = await manager.resolve_credential(config)
        assert value == "direct-value"
        
        # Test storing resolved credential
        success = await manager.store_resolved_credential("test-key", config)
        assert success
        
        # Test getting credential from store
        value = await manager.get_credential("test-key")
        assert value == "direct-value"


class TestRetrySystem:
    """Test retry and error handling system."""
    
    def test_error_classification(self):
        """Test error classification."""
        # Test timeout error
        timeout_error = classify_error(asyncio.TimeoutError("Timeout"), None)
        assert timeout_error.error_type == AuthErrorType.TIMEOUT
        assert timeout_error.is_retryable
        
        # Test 401 status code
        http_error = classify_error(Exception("Unauthorized"), 401)
        assert http_error.error_type == AuthErrorType.INVALID_CREDENTIALS
        assert not http_error.is_retryable
        
        # Test 429 status code
        rate_limit_error = classify_error(Exception("Rate limited"), 429)
        assert rate_limit_error.error_type == AuthErrorType.RATE_LIMITED
        assert rate_limit_error.is_retryable
        assert rate_limit_error.retry_after == 60.0
    
    @pytest.mark.asyncio
    async def test_circuit_breaker(self):
        """Test circuit breaker functionality."""
        circuit_breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        
        # Function that always fails
        async def failing_function():
            raise AuthenticationError("Test failure", AuthErrorType.SERVER_ERROR)
        
        # First failure
        with pytest.raises(AuthenticationError):
            await circuit_breaker.call(failing_function)
        
        # Second failure - should open circuit
        with pytest.raises(AuthenticationError):
            await circuit_breaker.call(failing_function)
        
        # Circuit should be open now
        assert circuit_breaker.state.value == "open"
        
        # Should reject calls while open
        with pytest.raises(AuthenticationError, match="Circuit breaker is OPEN"):
            await circuit_breaker.call(failing_function)
        
        # Wait for recovery timeout
        await asyncio.sleep(0.2)
        
        # Should transition to half-open and allow one call
        with pytest.raises(AuthenticationError):
            await circuit_breaker.call(failing_function)
    
    @pytest.mark.asyncio
    async def test_retry_handler(self):
        """Test retry handler functionality."""
        policy = RetryPolicy(max_attempts=3, initial_delay=0.01, max_delay=0.1)
        retry_handler = RetryHandler(policy)
        
        call_count = 0
        
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise AuthenticationError("Temporary failure", AuthErrorType.NETWORK_ERROR)
            return "success"
        
        # Should succeed on third attempt
        result = await retry_handler.execute_with_retry(flaky_function, operation_name="test")
        assert result == "success"
        assert call_count == 3


class TestSessionManagement:
    """Test session management system."""
    
    @pytest.mark.asyncio
    async def test_session_creation_and_retrieval(self):
        """Test session creation and retrieval."""
        config = SessionConfig(session_timeout=3600.0, max_sessions=5)
        session_manager = SessionManager(config)
        
        # Create session
        auth_result = AuthResult(success=True, headers={"Authorization": "Bearer token"})
        session_info = await session_manager.create_session("api_key", auth_result, {"user": "test"})
        
        assert session_info.auth_method == "api_key"
        assert session_info.metadata["user"] == "test"
        assert session_info.auth_result == auth_result
        assert not session_info.is_expired
        
        # Retrieve session
        retrieved_session = await session_manager.get_session(session_info.session_id)
        assert retrieved_session is not None
        assert retrieved_session.session_id == session_info.session_id
        
        # List sessions
        sessions = await session_manager.list_sessions("api_key")
        assert len(sessions) == 1
        assert sessions[0].session_id == session_info.session_id
    
    @pytest.mark.asyncio
    async def test_session_expiration(self):
        """Test session expiration handling."""
        config = SessionConfig(session_timeout=0.1, max_sessions=5)  # 0.1 second timeout
        session_manager = SessionManager(config)
        
        # Create session
        auth_result = AuthResult(success=True)
        session_info = await session_manager.create_session("api_key", auth_result)
        
        # Wait for expiration
        await asyncio.sleep(0.2)
        
        # Session should be expired and not retrievable
        retrieved_session = await session_manager.get_session(session_info.session_id)
        assert retrieved_session is None
    
    @pytest.mark.asyncio
    async def test_session_limits(self):
        """Test session limit enforcement."""
        config = SessionConfig(session_timeout=3600.0, max_sessions=2)
        session_manager = SessionManager(config)
        
        auth_result = AuthResult(success=True)
        
        # Create maximum number of sessions
        session1 = await session_manager.create_session("api_key", auth_result)
        session2 = await session_manager.create_session("api_key", auth_result)
        
        # Creating third session should remove oldest
        session3 = await session_manager.create_session("api_key", auth_result)
        
        # First session should be removed
        retrieved_session1 = await session_manager.get_session(session1.session_id)
        assert retrieved_session1 is None
        
        # Other sessions should still exist
        retrieved_session2 = await session_manager.get_session(session2.session_id)
        retrieved_session3 = await session_manager.get_session(session3.session_id)
        assert retrieved_session2 is not None
        assert retrieved_session3 is not None


class TestEnhancedAuthManager:
    """Test enhanced authentication manager."""
    
    @pytest.mark.asyncio
    async def test_manager_initialization(self):
        """Test manager initialization from configuration."""
        # Create test configuration
        config = AuthenticationConfig(
            default_method="api_key",
            methods={
                "api_key": EnhancedAPIKeyConfig(
                    name="test_api_key",
                    api_key=CredentialConfig(source=CredentialSource.DIRECT, value="test-key"),
                    key_name="X-API-Key",
                    location=AuthLocation.HEADER
                )
            }
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = EnhancedAuthManager(config=config, storage_path=Path(temp_dir))
            
            # Test authentication
            result = await manager.authenticate("api_key")
            assert result.success
            assert result.headers["X-API-Key"] == "test-key"
            
            # Test session creation
            sessions = await manager.get_session_info("api_key")
            assert len(sessions) == 1
            
            await manager.shutdown()
    
    @pytest.mark.asyncio
    async def test_manager_from_config_file(self):
        """Test manager creation from configuration file."""
        config_data = {
            "default_method": "api_key",
            "methods": {
                "api_key": {
                    "auth_type": "api_key",
                    "name": "test_api_key",
                    "api_key": {
                        "source": "direct",
                        "value": "test-key"
                    },
                    "key_name": "X-API-Key",
                    "location": "header"
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = Path(f.name)
        
        try:
            manager = EnhancedAuthManager.from_config_file(config_path)
            
            # Test authentication
            result = await manager.authenticate("api_key")
            assert result.success
            assert result.headers["X-API-Key"] == "test-key"
            
            await manager.shutdown()
        finally:
            config_path.unlink()
    
    @pytest.mark.asyncio
    async def test_manager_health_status(self):
        """Test manager health status reporting."""
        config = AuthenticationConfig(
            methods={
                "api_key": EnhancedAPIKeyConfig(
                    name="test_api_key",
                    api_key=CredentialConfig(source=CredentialSource.DIRECT, value="test-key")
                )
            }
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = EnhancedAuthManager(config=config, storage_path=Path(temp_dir))
            
            # Get health status
            status = await manager.get_health_status()
            
            assert status["overall_healthy"] is True
            assert "api_key" in status["methods"]
            assert status["methods"]["api_key"]["circuit_breaker_state"] == "closed"
            assert status["methods"]["api_key"]["healthy"] is True
            
            await manager.shutdown()
    
    @pytest.mark.asyncio
    async def test_manager_retry_functionality(self):
        """Test manager retry functionality with mocked failures."""
        config = AuthenticationConfig(
            methods={
                "api_key": EnhancedAPIKeyConfig(
                    name="test_api_key",
                    api_key=CredentialConfig(source=CredentialSource.DIRECT, value="test-key"),
                    retry_policy=RetryPolicy(max_attempts=3, initial_delay=0.01)
                )
            }
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = EnhancedAuthManager(config=config, storage_path=Path(temp_dir))
            
            # Mock the auth method to fail twice then succeed
            auth_method = manager._auth_methods["api_key"]
            original_authenticate = auth_method.authenticate
            call_count = 0
            
            async def mock_authenticate(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    raise Exception("Temporary failure")
                return await original_authenticate(*args, **kwargs)
            
            auth_method.authenticate = mock_authenticate
            
            # Should succeed after retries
            result = await manager.authenticate("api_key")
            assert result.success
            assert call_count == 3
            
            await manager.shutdown()
