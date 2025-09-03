"""
Advanced session management for authentication.

This module provides comprehensive session handling with persistence,
cleanup, and multi-session support for authentication operations.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import logging

from .config import SessionConfig
from .base import AuthResult


logger = logging.getLogger(__name__)


@dataclass
class SessionInfo:
    """Information about an authentication session."""
    
    session_id: str
    auth_method: str
    created_at: float
    last_accessed: float
    expires_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    auth_result: Optional[AuthResult] = None
    
    @property
    def is_expired(self) -> bool:
        """Check if session has expired."""
        if self.expires_at is None:
            return False
        return time.time() >= self.expires_at
    
    @property
    def is_active(self) -> bool:
        """Check if session is active (not expired)."""
        return not self.is_expired
    
    def touch(self) -> None:
        """Update last accessed time."""
        self.last_accessed = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session info to dictionary."""
        return {
            "session_id": self.session_id,
            "auth_method": self.auth_method,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "expires_at": self.expires_at,
            "metadata": self.metadata,
            "auth_result": self.auth_result.model_dump() if self.auth_result else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionInfo":
        """Create session info from dictionary."""
        auth_result = None
        if data.get("auth_result"):
            auth_result = AuthResult(**data["auth_result"])
        
        return cls(
            session_id=data["session_id"],
            auth_method=data["auth_method"],
            created_at=data["created_at"],
            last_accessed=data["last_accessed"],
            expires_at=data.get("expires_at"),
            metadata=data.get("metadata", {}),
            auth_result=auth_result
        )


class SessionStore:
    """Storage backend for session persistence."""
    
    def __init__(self, storage_path: Optional[Path] = None):
        """
        Initialize session store.
        
        Args:
            storage_path: Path for session storage (None for in-memory only)
        """
        self.storage_path = storage_path
        self._sessions: Dict[str, SessionInfo] = {}
        
        if self.storage_path:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            self._load_sessions()
    
    def _get_session_file(self, session_id: str) -> Path:
        """Get file path for a session."""
        if not self.storage_path:
            raise ValueError("No storage path configured")
        return self.storage_path / f"{session_id}.json"
    
    def _load_sessions(self) -> None:
        """Load sessions from storage."""
        if not self.storage_path or not self.storage_path.exists():
            return
        
        for session_file in self.storage_path.glob("*.json"):
            try:
                with open(session_file, 'r') as f:
                    session_data = json.load(f)
                
                session_info = SessionInfo.from_dict(session_data)
                
                # Skip expired sessions during load
                if not session_info.is_expired:
                    self._sessions[session_info.session_id] = session_info
                else:
                    # Clean up expired session file
                    session_file.unlink(missing_ok=True)
                    
            except Exception as e:
                logger.error(f"Failed to load session from {session_file}: {e}")
    
    async def store_session(self, session_info: SessionInfo) -> None:
        """Store a session."""
        self._sessions[session_info.session_id] = session_info
        
        if self.storage_path:
            try:
                session_file = self._get_session_file(session_info.session_id)
                with open(session_file, 'w') as f:
                    json.dump(session_info.to_dict(), f, indent=2)
            except Exception as e:
                logger.error(f"Failed to persist session {session_info.session_id}: {e}")
    
    async def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """Get a session by ID."""
        session_info = self._sessions.get(session_id)
        if session_info and session_info.is_expired:
            # Clean up expired session
            await self.remove_session(session_id)
            return None
        return session_info
    
    async def remove_session(self, session_id: str) -> bool:
        """Remove a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            
            if self.storage_path:
                try:
                    session_file = self._get_session_file(session_id)
                    session_file.unlink(missing_ok=True)
                except Exception as e:
                    logger.error(f"Failed to remove session file {session_id}: {e}")
            
            return True
        return False
    
    async def list_sessions(self, auth_method: Optional[str] = None) -> List[SessionInfo]:
        """List all active sessions, optionally filtered by auth method."""
        sessions = []
        for session_info in list(self._sessions.values()):
            if session_info.is_expired:
                # Clean up expired session
                await self.remove_session(session_info.session_id)
                continue
            
            if auth_method is None or session_info.auth_method == auth_method:
                sessions.append(session_info)
        
        return sessions
    
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions and return count of removed sessions."""
        expired_sessions = []
        for session_id, session_info in self._sessions.items():
            if session_info.is_expired:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            await self.remove_session(session_id)
        
        logger.debug(f"Cleaned up {len(expired_sessions)} expired sessions")
        return len(expired_sessions)


class SessionManager:
    """High-level session management interface."""
    
    def __init__(self, config: SessionConfig):
        """
        Initialize session manager.
        
        Args:
            config: Session configuration
        """
        self.config = config
        self.store = SessionStore(config.storage_path if config.enable_persistence else None)
        self._cleanup_task: Optional[asyncio.Task] = None
        self._active_sessions: Set[str] = set()
        
        # Start cleanup task if persistence is enabled
        if config.enable_persistence:
            self._start_cleanup_task()
    
    def _start_cleanup_task(self) -> None:
        """Start the session cleanup background task."""
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(self.config.cleanup_interval)
                    await self.store.cleanup_expired_sessions()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in session cleanup task: {e}")
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
    
    async def create_session(
        self,
        auth_method: str,
        auth_result: AuthResult,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SessionInfo:
        """
        Create a new authentication session.
        
        Args:
            auth_method: Authentication method name
            auth_result: Authentication result
            metadata: Optional session metadata
            
        Returns:
            Created session info
            
        Raises:
            ValueError: If maximum sessions exceeded
        """
        # Check session limits
        active_sessions = await self.store.list_sessions(auth_method)
        if len(active_sessions) >= self.config.max_sessions:
            # Remove oldest session
            oldest_session = min(active_sessions, key=lambda s: s.last_accessed)
            await self.remove_session(oldest_session.session_id)
            logger.info(f"Removed oldest session {oldest_session.session_id} due to limit")
        
        # Create new session
        session_id = str(uuid.uuid4())
        current_time = time.time()
        expires_at = current_time + self.config.session_timeout if self.config.session_timeout > 0 else None
        
        session_info = SessionInfo(
            session_id=session_id,
            auth_method=auth_method,
            created_at=current_time,
            last_accessed=current_time,
            expires_at=expires_at,
            metadata=metadata or {},
            auth_result=auth_result
        )
        
        await self.store.store_session(session_info)
        self._active_sessions.add(session_id)
        
        logger.debug(f"Created session {session_id} for {auth_method}")
        return session_info
    
    async def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """
        Get a session by ID and update last accessed time.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session info or None if not found/expired
        """
        session_info = await self.store.get_session(session_id)
        if session_info:
            session_info.touch()
            await self.store.store_session(session_info)
        return session_info
    
    async def remove_session(self, session_id: str) -> bool:
        """
        Remove a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            True if session was removed, False if not found
        """
        success = await self.store.remove_session(session_id)
        if success:
            self._active_sessions.discard(session_id)
            logger.debug(f"Removed session {session_id}")
        return success
    
    async def list_sessions(self, auth_method: Optional[str] = None) -> List[SessionInfo]:
        """
        List all active sessions.
        
        Args:
            auth_method: Optional filter by authentication method
            
        Returns:
            List of active sessions
        """
        return await self.store.list_sessions(auth_method)
    
    async def refresh_session(self, session_id: str) -> Optional[SessionInfo]:
        """
        Refresh a session's expiration time.
        
        Args:
            session_id: Session ID
            
        Returns:
            Updated session info or None if not found
        """
        session_info = await self.store.get_session(session_id)
        if session_info:
            current_time = time.time()
            session_info.last_accessed = current_time
            if self.config.session_timeout > 0:
                session_info.expires_at = current_time + self.config.session_timeout
            
            await self.store.store_session(session_info)
            logger.debug(f"Refreshed session {session_id}")
        
        return session_info
    
    async def cleanup_sessions(self, auth_method: Optional[str] = None) -> int:
        """
        Clean up expired sessions.
        
        Args:
            auth_method: Optional filter by authentication method
            
        Returns:
            Number of sessions cleaned up
        """
        if auth_method:
            # Clean up sessions for specific auth method
            sessions = await self.store.list_sessions(auth_method)
            expired_count = 0
            for session in sessions:
                if session.is_expired:
                    await self.remove_session(session.session_id)
                    expired_count += 1
            return expired_count
        else:
            # Clean up all expired sessions
            return await self.store.cleanup_expired_sessions()
    
    async def shutdown(self) -> None:
        """Shutdown the session manager and cleanup resources."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Final cleanup
        await self.store.cleanup_expired_sessions()
        logger.info("Session manager shutdown complete")
    
    def __del__(self):
        """Cleanup on deletion."""
        if self._cleanup_task and not self._cleanup_task.done():
            logger.warning("SessionManager deleted without proper shutdown")
