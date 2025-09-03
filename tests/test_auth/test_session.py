"""
Comprehensive tests for the authentication session module.
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from web_fetch.auth.session import (
    SessionInfo,
    SessionManager,
    SessionStore,
)
from web_fetch.auth.config import SessionConfig
from web_fetch.auth.base import AuthResult, AuthType


class TestSessionInfo:
    """Test session information model."""

    def test_session_info_creation(self):
        """Test creating session info."""
        created_at = datetime.now()
        expires_at = created_at + timedelta(hours=1)
        
        session = SessionInfo(
            session_id="test-session-123",
            user_id="user-456",
            auth_type=AuthType.BEARER_TOKEN,
            created_at=created_at,
            expires_at=expires_at,
            metadata={"role": "admin"}
        )
        
        assert session.session_id == "test-session-123"
        assert session.user_id == "user-456"
        assert session.auth_type == AuthType.BEARER_TOKEN
        assert session.created_at == created_at
        assert session.expires_at == expires_at
        assert session.metadata == {"role": "admin"}

    def test_session_info_is_valid(self):
        """Test session validity checking."""
        now = datetime.now()
        
        # Valid session (expires in future)
        valid_session = SessionInfo(
            session_id="valid-session",
            user_id="user-123",
            auth_type=AuthType.API_KEY,
            created_at=now - timedelta(minutes=30),
            expires_at=now + timedelta(minutes=30)
        )
        assert valid_session.is_valid()

    def test_session_info_is_expired(self):
        """Test expired session detection."""
        now = datetime.now()
        
        # Expired session
        expired_session = SessionInfo(
            session_id="expired-session",
            user_id="user-123",
            auth_type=AuthType.API_KEY,
            created_at=now - timedelta(hours=2),
            expires_at=now - timedelta(hours=1)
        )
        assert not expired_session.is_valid()

    def test_session_info_time_until_expiry(self):
        """Test calculating time until expiry."""
        now = datetime.now()
        expires_at = now + timedelta(minutes=30)
        
        session = SessionInfo(
            session_id="test-session",
            user_id="user-123",
            auth_type=AuthType.API_KEY,
            created_at=now,
            expires_at=expires_at
        )
        
        time_left = session.time_until_expiry()
        assert time_left.total_seconds() > 1700  # Approximately 30 minutes
        assert time_left.total_seconds() < 1800

    def test_session_info_refresh_expiry(self):
        """Test refreshing session expiry."""
        now = datetime.now()
        original_expiry = now + timedelta(minutes=30)
        
        session = SessionInfo(
            session_id="test-session",
            user_id="user-123",
            auth_type=AuthType.API_KEY,
            created_at=now,
            expires_at=original_expiry
        )
        
        # Refresh with additional 1 hour
        session.refresh_expiry(timedelta(hours=1))
        
        assert session.expires_at > original_expiry
        time_diff = session.expires_at - original_expiry
        assert time_diff.total_seconds() >= 3600  # At least 1 hour


class TestSessionStore:
    """Test session store functionality."""

    def test_session_store_creation(self):
        """Test creating a session store."""
        store = SessionStore()
        assert store is not None
        assert len(store._sessions) == 0

    def test_store_and_retrieve_session(self):
        """Test storing and retrieving sessions."""
        store = SessionStore()
        
        session = SessionInfo(
            session_id="test-session",
            user_id="user-123",
            auth_type=AuthType.API_KEY,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=1)
        )
        
        # Store session
        store.store_session(session)
        
        # Retrieve session
        retrieved = store.get_session("test-session")
        assert retrieved is not None
        assert retrieved.session_id == "test-session"
        assert retrieved.user_id == "user-123"

    def test_retrieve_nonexistent_session(self):
        """Test retrieving non-existent session."""
        store = SessionStore()
        
        session = store.get_session("nonexistent-session")
        assert session is None

    def test_remove_session(self):
        """Test removing a session."""
        store = SessionStore()
        
        session = SessionInfo(
            session_id="test-session",
            user_id="user-123",
            auth_type=AuthType.API_KEY,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=1)
        )
        
        store.store_session(session)
        assert store.get_session("test-session") is not None
        
        store.remove_session("test-session")
        assert store.get_session("test-session") is None

    def test_list_sessions_for_user(self):
        """Test listing sessions for a specific user."""
        store = SessionStore()
        
        # Create sessions for different users
        session1 = SessionInfo(
            session_id="session-1",
            user_id="user-123",
            auth_type=AuthType.API_KEY,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=1)
        )
        
        session2 = SessionInfo(
            session_id="session-2",
            user_id="user-123",
            auth_type=AuthType.BEARER_TOKEN,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=1)
        )
        
        session3 = SessionInfo(
            session_id="session-3",
            user_id="user-456",
            auth_type=AuthType.API_KEY,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=1)
        )
        
        store.store_session(session1)
        store.store_session(session2)
        store.store_session(session3)
        
        # Get sessions for user-123
        user_sessions = store.get_sessions_for_user("user-123")
        assert len(user_sessions) == 2
        assert all(s.user_id == "user-123" for s in user_sessions)

    def test_cleanup_expired_sessions(self):
        """Test cleaning up expired sessions."""
        store = SessionStore()
        
        now = datetime.now()
        
        # Valid session
        valid_session = SessionInfo(
            session_id="valid-session",
            user_id="user-123",
            auth_type=AuthType.API_KEY,
            created_at=now,
            expires_at=now + timedelta(hours=1)
        )
        
        # Expired session
        expired_session = SessionInfo(
            session_id="expired-session",
            user_id="user-456",
            auth_type=AuthType.API_KEY,
            created_at=now - timedelta(hours=2),
            expires_at=now - timedelta(hours=1)
        )
        
        store.store_session(valid_session)
        store.store_session(expired_session)
        
        # Before cleanup
        assert len(store._sessions) == 2
        
        # Cleanup expired sessions
        removed_count = store.cleanup_expired_sessions()
        
        # After cleanup
        assert removed_count == 1
        assert len(store._sessions) == 1
        assert store.get_session("valid-session") is not None
        assert store.get_session("expired-session") is None


class TestSessionManager:
    """Test session manager functionality."""

    def test_session_manager_creation(self):
        """Test creating a session manager."""
        config = SessionConfig(
            session_timeout=timedelta(hours=1),
            cleanup_interval=timedelta(minutes=30),
            max_sessions_per_user=5
        )
        
        manager = SessionManager(config)
        assert manager.config == config
        assert manager.store is not None

    @pytest.mark.asyncio
    async def test_create_session(self):
        """Test creating a new session."""
        config = SessionConfig(session_timeout=timedelta(hours=1))
        manager = SessionManager(config)
        
        auth_result = AuthResult(
            success=True,
            auth_type=AuthType.API_KEY,
            user_id="user-123",
            metadata={"role": "admin"}
        )
        
        session = await manager.create_session(auth_result)
        
        assert session is not None
        assert session.user_id == "user-123"
        assert session.auth_type == AuthType.API_KEY
        assert session.metadata == {"role": "admin"}
        assert session.is_valid()

    @pytest.mark.asyncio
    async def test_get_session(self):
        """Test retrieving an existing session."""
        config = SessionConfig(session_timeout=timedelta(hours=1))
        manager = SessionManager(config)
        
        auth_result = AuthResult(
            success=True,
            auth_type=AuthType.API_KEY,
            user_id="user-123"
        )
        
        # Create session
        created_session = await manager.create_session(auth_result)
        
        # Retrieve session
        retrieved_session = await manager.get_session(created_session.session_id)
        
        assert retrieved_session is not None
        assert retrieved_session.session_id == created_session.session_id
        assert retrieved_session.user_id == "user-123"

    @pytest.mark.asyncio
    async def test_refresh_session(self):
        """Test refreshing a session."""
        config = SessionConfig(session_timeout=timedelta(hours=1))
        manager = SessionManager(config)
        
        auth_result = AuthResult(
            success=True,
            auth_type=AuthType.API_KEY,
            user_id="user-123"
        )
        
        # Create session
        session = await manager.create_session(auth_result)
        original_expiry = session.expires_at
        
        # Wait a bit to ensure time difference
        await asyncio.sleep(0.01)
        
        # Refresh session
        refreshed = await manager.refresh_session(session.session_id)
        
        assert refreshed is not None
        assert refreshed.expires_at > original_expiry

    @pytest.mark.asyncio
    async def test_invalidate_session(self):
        """Test invalidating a session."""
        config = SessionConfig(session_timeout=timedelta(hours=1))
        manager = SessionManager(config)
        
        auth_result = AuthResult(
            success=True,
            auth_type=AuthType.API_KEY,
            user_id="user-123"
        )
        
        # Create session
        session = await manager.create_session(auth_result)
        
        # Verify session exists
        assert await manager.get_session(session.session_id) is not None
        
        # Invalidate session
        await manager.invalidate_session(session.session_id)
        
        # Verify session is gone
        assert await manager.get_session(session.session_id) is None

    @pytest.mark.asyncio
    async def test_max_sessions_per_user_limit(self):
        """Test maximum sessions per user limit."""
        config = SessionConfig(
            session_timeout=timedelta(hours=1),
            max_sessions_per_user=2
        )
        manager = SessionManager(config)
        
        auth_result = AuthResult(
            success=True,
            auth_type=AuthType.API_KEY,
            user_id="user-123"
        )
        
        # Create maximum allowed sessions
        session1 = await manager.create_session(auth_result)
        session2 = await manager.create_session(auth_result)
        
        # Verify both sessions exist
        assert await manager.get_session(session1.session_id) is not None
        assert await manager.get_session(session2.session_id) is not None
        
        # Create third session (should remove oldest)
        session3 = await manager.create_session(auth_result)
        
        # First session should be removed, others should exist
        assert await manager.get_session(session1.session_id) is None
        assert await manager.get_session(session2.session_id) is not None
        assert await manager.get_session(session3.session_id) is not None

    @pytest.mark.asyncio
    async def test_automatic_cleanup(self):
        """Test automatic cleanup of expired sessions."""
        config = SessionConfig(
            session_timeout=timedelta(milliseconds=10),  # Very short for testing
            cleanup_interval=timedelta(milliseconds=20)
        )
        manager = SessionManager(config)
        
        auth_result = AuthResult(
            success=True,
            auth_type=AuthType.API_KEY,
            user_id="user-123"
        )
        
        # Create session
        session = await manager.create_session(auth_result)
        
        # Verify session exists
        assert await manager.get_session(session.session_id) is not None
        
        # Wait for session to expire
        await asyncio.sleep(0.05)
        
        # Trigger cleanup
        await manager._cleanup_expired_sessions()
        
        # Session should be gone
        assert await manager.get_session(session.session_id) is None
