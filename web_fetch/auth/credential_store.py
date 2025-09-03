"""
Secure credential storage and management system.

This module provides secure storage, encryption, and management of authentication
credentials with support for multiple storage backends.
"""

from __future__ import annotations

import json
import os
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import logging
import hashlib
import base64

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .config import CredentialConfig, CredentialSource


logger = logging.getLogger(__name__)


class CredentialStoreError(Exception):
    """Base exception for credential store operations."""
    pass


class CredentialNotFoundError(CredentialStoreError):
    """Raised when a credential is not found."""
    pass


class CredentialEncryptionError(CredentialStoreError):
    """Raised when credential encryption/decryption fails."""
    pass


class CredentialStore(ABC):
    """Abstract base class for credential storage backends."""

    @abstractmethod
    async def store_credential(self, key: str, value: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Store a credential securely."""
        pass

    @abstractmethod
    async def retrieve_credential(self, key: str) -> Optional[str]:
        """Retrieve a credential."""
        pass

    @abstractmethod
    async def delete_credential(self, key: str) -> bool:
        """Delete a credential."""
        pass

    @abstractmethod
    async def list_credentials(self) -> List[str]:
        """List all stored credential keys."""
        pass

    @abstractmethod
    async def rotate_credential(self, key: str, new_value: str) -> None:
        """Rotate a credential to a new value."""
        pass


class EncryptedFileStore(CredentialStore):
    """File-based credential store with encryption."""

    def __init__(self, storage_path: Path, master_key: Optional[str] = None):
        """
        Initialize encrypted file store.

        Args:
            storage_path: Path to store encrypted credentials
            master_key: Master key for encryption (if None, will be derived from environment)
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Initialize encryption
        self._fernet = self._initialize_encryption(master_key)

        # Metadata file
        self.metadata_file = self.storage_path / "metadata.json"
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._load_metadata()

    def _initialize_encryption(self, master_key: Optional[str] = None) -> Fernet:
        """Initialize encryption with master key."""
        if master_key is None:
            # Try to get from environment
            master_key = os.getenv("WEBFETCH_MASTER_KEY")
            if not master_key:
                # Generate a key and warn user
                key = Fernet.generate_key()
                logger.warning(
                    "No master key provided. Generated new key. "
                    "Set WEBFETCH_MASTER_KEY environment variable to persist credentials across sessions."
                )
                return Fernet(key)

        # Derive key from master key using PBKDF2
        salt = b"webfetch_auth_salt"  # In production, use a random salt per installation
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_key.encode()))
        return Fernet(key)

    def _load_metadata(self) -> None:
        """Load metadata from file."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    self._metadata = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load credential metadata: {e}")
                self._metadata = {}

    def _save_metadata(self) -> None:
        """Save metadata to file."""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self._metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save credential metadata: {e}")

    def _get_credential_file(self, key: str) -> Path:
        """Get file path for a credential."""
        # Hash the key to avoid filesystem issues
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        return self.storage_path / f"{key_hash}.cred"

    async def store_credential(self, key: str, value: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Store a credential securely."""
        try:
            # Encrypt the credential
            encrypted_value = self._fernet.encrypt(value.encode())

            # Store to file
            credential_file = self._get_credential_file(key)
            with open(credential_file, 'wb') as f:
                f.write(encrypted_value)

            # Update metadata
            self._metadata[key] = {
                "created_at": time.time(),
                "updated_at": time.time(),
                "file_path": str(credential_file),
                **(metadata or {})
            }
            self._save_metadata()

            logger.debug(f"Stored credential: {key}")

        except Exception as e:
            raise CredentialStoreError(f"Failed to store credential '{key}': {e}")

    async def retrieve_credential(self, key: str) -> Optional[str]:
        """Retrieve a credential."""
        try:
            credential_file = self._get_credential_file(key)
            if not credential_file.exists():
                return None

            # Read and decrypt
            with open(credential_file, 'rb') as f:
                encrypted_value = f.read()

            decrypted_value = self._fernet.decrypt(encrypted_value)
            return decrypted_value.decode()

        except Exception as e:
            logger.error(f"Failed to retrieve credential '{key}': {e}")
            return None

    async def delete_credential(self, key: str) -> bool:
        """Delete a credential."""
        try:
            credential_file = self._get_credential_file(key)
            if credential_file.exists():
                credential_file.unlink()

            # Remove from metadata
            if key in self._metadata:
                del self._metadata[key]
                self._save_metadata()

            logger.debug(f"Deleted credential: {key}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete credential '{key}': {e}")
            return False

    async def list_credentials(self) -> List[str]:
        """List all stored credential keys."""
        return list(self._metadata.keys())

    async def rotate_credential(self, key: str, new_value: str) -> None:
        """Rotate a credential to a new value."""
        # Store old value as backup
        old_value = await self.retrieve_credential(key)
        if old_value:
            backup_key = f"{key}_backup_{int(time.time())}"
            await self.store_credential(backup_key, old_value, {"is_backup": True, "original_key": key})

        # Store new value
        await self.store_credential(key, new_value)

        # Update metadata
        if key in self._metadata:
            self._metadata[key]["rotated_at"] = time.time()
            self._save_metadata()


class InMemoryStore(CredentialStore):
    """In-memory credential store (for testing/development)."""

    def __init__(self):
        """Initialize in-memory store."""
        self._credentials: Dict[str, str] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}

    async def store_credential(self, key: str, value: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Store a credential in memory."""
        self._credentials[key] = value
        self._metadata[key] = {
            "created_at": time.time(),
            "updated_at": time.time(),
            **(metadata or {})
        }

    async def retrieve_credential(self, key: str) -> Optional[str]:
        """Retrieve a credential from memory."""
        return self._credentials.get(key)

    async def delete_credential(self, key: str) -> bool:
        """Delete a credential from memory."""
        if key in self._credentials:
            del self._credentials[key]
            if key in self._metadata:
                del self._metadata[key]
            return True
        return False

    async def list_credentials(self) -> List[str]:
        """List all stored credential keys."""
        return list(self._credentials.keys())

    async def rotate_credential(self, key: str, new_value: str) -> None:
        """Rotate a credential to a new value."""
        await self.store_credential(key, new_value)


class CredentialManager:
    """High-level credential management interface."""

    def __init__(self, store: CredentialStore):
        """
        Initialize credential manager.

        Args:
            store: Credential store backend
        """
        self.store = store

    async def resolve_credential(self, config: CredentialConfig) -> Optional[str]:
        """
        Resolve a credential value based on its configuration.

        Args:
            config: Credential configuration

        Returns:
            Resolved credential value or None if not found
        """
        try:
            if config.source == CredentialSource.DIRECT:
                return config.get_credential_value()
            elif config.source == CredentialSource.ENVIRONMENT:
                return config.get_credential_value()
            elif config.source == CredentialSource.FILE:
                return config.get_credential_value()
            elif config.source == CredentialSource.KEYRING:
                return config.get_credential_value()
            elif config.source == CredentialSource.VAULT:
                # For vault, we might store the retrieved value in our store for caching
                vault_key = f"vault:{config.vault_path}"
                cached_value = await self.store.retrieve_credential(vault_key)
                if cached_value:
                    return cached_value

                # In a real implementation, retrieve from vault and cache
                raise NotImplementedError("Vault integration not yet implemented")

            return None

        except Exception as e:
            logger.error(f"Failed to resolve credential: {e}")
            return None

    async def store_resolved_credential(self, key: str, config: CredentialConfig) -> bool:
        """
        Store a resolved credential in the secure store.

        Args:
            key: Storage key for the credential
            config: Credential configuration

        Returns:
            True if stored successfully, False otherwise
        """
        try:
            value = await self.resolve_credential(config)
            if value:
                await self.store.store_credential(key, value, {
                    "source": config.source.value,
                    "config_hash": hashlib.sha256(str(config).encode()).hexdigest()
                })
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to store resolved credential '{key}': {e}")
            return False

    async def get_credential(self, key: str, config: Optional[CredentialConfig] = None) -> Optional[str]:
        """
        Get a credential, resolving from config if not in store.

        Args:
            key: Credential key
            config: Optional credential configuration for resolution

        Returns:
            Credential value or None if not found
        """
        # Try to get from store first
        value = await self.store.retrieve_credential(key)
        if value:
            return value

        # If not in store and config provided, resolve and store
        if config:
            value = await self.resolve_credential(config)
            if value:
                await self.store.store_credential(key, value)
            return value

        return None
