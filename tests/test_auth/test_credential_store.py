"""
Comprehensive tests for the credential store module.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import json

from web_fetch.auth.credential_store import (
    CredentialStore,
    InMemoryStore,
    EncryptedFileStore,
    CredentialManager,
    CredentialStoreError,
)
from web_fetch.auth.config import CredentialConfig, CredentialSource


class TestInMemoryStore:
    """Test in-memory credential store."""

    def test_store_creation(self):
        """Test creating an in-memory store."""
        store = InMemoryStore()
        assert store is not None
        assert len(store._credentials) == 0

    def test_store_and_retrieve_credential(self):
        """Test storing and retrieving credentials."""
        store = InMemoryStore()
        
        # Store a credential
        store.store("test-key", "test-value")
        
        # Retrieve the credential
        value = store.retrieve("test-key")
        assert value == "test-value"

    def test_retrieve_nonexistent_credential(self):
        """Test retrieving a non-existent credential."""
        store = InMemoryStore()
        
        with pytest.raises(CredentialStoreError):
            store.retrieve("nonexistent-key")

    def test_delete_credential(self):
        """Test deleting a credential."""
        store = InMemoryStore()
        
        # Store and then delete
        store.store("test-key", "test-value")
        store.delete("test-key")
        
        # Should raise error when trying to retrieve
        with pytest.raises(CredentialStoreError):
            store.retrieve("test-key")

    def test_list_credentials(self):
        """Test listing stored credentials."""
        store = InMemoryStore()
        
        # Store multiple credentials
        store.store("key1", "value1")
        store.store("key2", "value2")
        
        keys = store.list_keys()
        assert "key1" in keys
        assert "key2" in keys
        assert len(keys) == 2

    def test_exists_method(self):
        """Test checking if credential exists."""
        store = InMemoryStore()
        
        assert not store.exists("test-key")
        
        store.store("test-key", "test-value")
        assert store.exists("test-key")

    def test_clear_store(self):
        """Test clearing all credentials."""
        store = InMemoryStore()
        
        store.store("key1", "value1")
        store.store("key2", "value2")
        
        store.clear()
        assert len(store.list_keys()) == 0


class TestEncryptedFileStore:
    """Test encrypted file credential store."""

    def test_store_creation_with_temp_file(self):
        """Test creating an encrypted file store."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            store = EncryptedFileStore(tmp.name, "test-password")
            assert store is not None
            assert store.file_path == tmp.name
        
        # Clean up
        os.unlink(tmp.name)

    def test_store_and_retrieve_credential(self):
        """Test storing and retrieving credentials with encryption."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            store = EncryptedFileStore(tmp.name, "test-password")
            
            # Store a credential
            store.store("test-key", "test-value")
            
            # Retrieve the credential
            value = store.retrieve("test-key")
            assert value == "test-value"
        
        # Clean up
        os.unlink(tmp.name)

    def test_persistence_across_instances(self):
        """Test that credentials persist across store instances."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            # First instance
            store1 = EncryptedFileStore(tmp.name, "test-password")
            store1.store("test-key", "test-value")
            
            # Second instance
            store2 = EncryptedFileStore(tmp.name, "test-password")
            value = store2.retrieve("test-key")
            assert value == "test-value"
        
        # Clean up
        os.unlink(tmp.name)

    def test_wrong_password_fails(self):
        """Test that wrong password fails to decrypt."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            # Store with one password
            store1 = EncryptedFileStore(tmp.name, "correct-password")
            store1.store("test-key", "test-value")
            
            # Try to read with wrong password
            store2 = EncryptedFileStore(tmp.name, "wrong-password")
            with pytest.raises(CredentialStoreError):
                store2.retrieve("test-key")
        
        # Clean up
        os.unlink(tmp.name)

    def test_file_corruption_handling(self):
        """Test handling of corrupted credential files."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            # Write invalid data to file
            tmp.write(b"invalid encrypted data")
            tmp.flush()
            
            store = EncryptedFileStore(tmp.name, "test-password")
            with pytest.raises(CredentialStoreError):
                store.retrieve("any-key")
        
        # Clean up
        os.unlink(tmp.name)


class TestCredentialManager:
    """Test credential manager."""

    def test_manager_creation(self):
        """Test creating a credential manager."""
        store = InMemoryStore()
        manager = CredentialManager(store)
        assert manager is not None
        assert manager.store == store

    def test_resolve_direct_credential(self):
        """Test resolving direct credentials."""
        store = InMemoryStore()
        manager = CredentialManager(store)
        
        config = CredentialConfig(
            source=CredentialSource.DIRECT,
            value="direct-value"
        )
        
        value = manager.resolve_credential(config)
        assert value == "direct-value"

    def test_resolve_environment_credential(self):
        """Test resolving environment variable credentials."""
        store = InMemoryStore()
        manager = CredentialManager(store)
        
        with patch.dict(os.environ, {"TEST_VAR": "env-value"}):
            config = CredentialConfig(
                source=CredentialSource.ENVIRONMENT,
                key="TEST_VAR"
            )
            
            value = manager.resolve_credential(config)
            assert value == "env-value"

    def test_resolve_file_credential(self):
        """Test resolving file-based credentials."""
        store = InMemoryStore()
        manager = CredentialManager(store)
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
            tmp.write("file-content")
            tmp.flush()
            
            config = CredentialConfig(
                source=CredentialSource.FILE,
                path=tmp.name
            )
            
            value = manager.resolve_credential(config)
            assert value == "file-content"
        
        # Clean up
        os.unlink(tmp.name)

    def test_resolve_store_credential(self):
        """Test resolving store-based credentials."""
        store = InMemoryStore()
        store.store("stored-key", "stored-value")
        manager = CredentialManager(store)
        
        config = CredentialConfig(
            source=CredentialSource.STORE,
            key="stored-key"
        )
        
        value = manager.resolve_credential(config)
        assert value == "stored-value"

    def test_cache_credential(self):
        """Test credential caching."""
        store = InMemoryStore()
        manager = CredentialManager(store)
        
        config = CredentialConfig(
            source=CredentialSource.DIRECT,
            value="cached-value",
            cache_ttl=60
        )
        
        # First resolution should cache
        value1 = manager.resolve_credential(config)
        assert value1 == "cached-value"
        
        # Second resolution should use cache
        value2 = manager.resolve_credential(config)
        assert value2 == "cached-value"

    def test_missing_environment_variable(self):
        """Test handling missing environment variables."""
        store = InMemoryStore()
        manager = CredentialManager(store)
        
        config = CredentialConfig(
            source=CredentialSource.ENVIRONMENT,
            key="NONEXISTENT_VAR"
        )
        
        with pytest.raises(CredentialStoreError):
            manager.resolve_credential(config)

    def test_missing_file(self):
        """Test handling missing files."""
        store = InMemoryStore()
        manager = CredentialManager(store)
        
        config = CredentialConfig(
            source=CredentialSource.FILE,
            path="/nonexistent/file.txt"
        )
        
        with pytest.raises(CredentialStoreError):
            manager.resolve_credential(config)

    def test_invalid_credential_source(self):
        """Test handling invalid credential sources."""
        store = InMemoryStore()
        manager = CredentialManager(store)
        
        # Create config with invalid source
        config = CredentialConfig(source="invalid_source")
        
        with pytest.raises(CredentialStoreError):
            manager.resolve_credential(config)


class TestCredentialStoreIntegration:
    """Test integration scenarios for credential stores."""

    def test_manager_with_encrypted_store(self):
        """Test credential manager with encrypted file store."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            store = EncryptedFileStore(tmp.name, "test-password")
            manager = CredentialManager(store)
            
            # Store credential via manager
            store.store("api-key", "secret-key-value")
            
            # Resolve via manager
            config = CredentialConfig(
                source=CredentialSource.STORE,
                key="api-key"
            )
            
            value = manager.resolve_credential(config)
            assert value == "secret-key-value"
        
        # Clean up
        os.unlink(tmp.name)

    def test_multiple_credential_sources(self):
        """Test resolving credentials from multiple sources."""
        store = InMemoryStore()
        manager = CredentialManager(store)
        
        # Store in credential store
        store.store("store-key", "store-value")
        
        # Test different sources
        configs = [
            CredentialConfig(source=CredentialSource.DIRECT, value="direct"),
            CredentialConfig(source=CredentialSource.STORE, key="store-key"),
        ]
        
        values = [manager.resolve_credential(config) for config in configs]
        assert values == ["direct", "store-value"]
