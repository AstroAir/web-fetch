"""
Comprehensive tests for the cloud storage component module.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, Optional
import tempfile
import os

from web_fetch.components.cloud_storage_component import (
    CloudStorageComponent,
    CloudStorageConfig,
    CloudStorageProvider,
    CloudStorageError,
    S3Config,
    GCSConfig,
    AzureConfig,
)
from web_fetch.models.http import FetchRequest, FetchResult
from web_fetch.models.base import ContentType


class TestCloudStorageConfig:
    """Test cloud storage configuration."""

    def test_s3_config_creation(self):
        """Test creating S3 configuration."""
        config = S3Config(
            provider=CloudStorageProvider.AWS_S3,
            bucket_name="test-bucket",
            access_key_id="test-access-key",
            secret_access_key="test-secret-key",
            region="us-east-1"
        )
        
        assert config.provider == CloudStorageProvider.AWS_S3
        assert config.bucket_name == "test-bucket"
        assert config.access_key_id == "test-access-key"
        assert config.secret_access_key == "test-secret-key"
        assert config.region == "us-east-1"

    def test_gcs_config_creation(self):
        """Test creating Google Cloud Storage configuration."""
        config = GCSConfig(
            provider=CloudStorageProvider.GOOGLE_CLOUD,
            bucket_name="test-gcs-bucket",
            project_id="test-project",
            credentials_path="/path/to/credentials.json"
        )
        
        assert config.provider == CloudStorageProvider.GOOGLE_CLOUD
        assert config.bucket_name == "test-gcs-bucket"
        assert config.project_id == "test-project"
        assert config.credentials_path == "/path/to/credentials.json"

    def test_azure_config_creation(self):
        """Test creating Azure Blob Storage configuration."""
        config = AzureConfig(
            provider=CloudStorageProvider.AZURE_BLOB,
            container_name="test-container",
            account_name="testaccount",
            account_key="test-account-key"
        )
        
        assert config.provider == CloudStorageProvider.AZURE_BLOB
        assert config.container_name == "test-container"
        assert config.account_name == "testaccount"
        assert config.account_key == "test-account-key"

    def test_cloud_storage_config_validation(self):
        """Test cloud storage configuration validation."""
        # Missing bucket name for S3
        with pytest.raises(ValueError):
            S3Config(
                provider=CloudStorageProvider.AWS_S3,
                bucket_name="",
                access_key_id="key",
                secret_access_key="secret"
            )
        
        # Missing credentials for GCS
        with pytest.raises(ValueError):
            GCSConfig(
                provider=CloudStorageProvider.GOOGLE_CLOUD,
                bucket_name="bucket",
                project_id="project",
                credentials_path=""
            )


class TestCloudStorageProvider:
    """Test cloud storage provider enumeration."""

    def test_provider_values(self):
        """Test provider enumeration values."""
        assert CloudStorageProvider.AWS_S3 == "aws_s3"
        assert CloudStorageProvider.GOOGLE_CLOUD == "google_cloud"
        assert CloudStorageProvider.AZURE_BLOB == "azure_blob"
        assert CloudStorageProvider.MINIO == "minio"

    def test_provider_capabilities(self):
        """Test provider capabilities."""
        # All providers should support basic operations
        providers = [
            CloudStorageProvider.AWS_S3,
            CloudStorageProvider.GOOGLE_CLOUD,
            CloudStorageProvider.AZURE_BLOB,
            CloudStorageProvider.MINIO
        ]
        
        assert len(providers) == 4


class TestCloudStorageError:
    """Test cloud storage error handling."""

    def test_cloud_storage_error_creation(self):
        """Test creating cloud storage error."""
        error = CloudStorageError(
            message="Upload failed",
            provider=CloudStorageProvider.AWS_S3,
            operation="upload",
            details={"bucket": "test-bucket", "key": "test-key"}
        )
        
        assert error.message == "Upload failed"
        assert error.provider == CloudStorageProvider.AWS_S3
        assert error.operation == "upload"
        assert error.details["bucket"] == "test-bucket"

    def test_cloud_storage_error_string_representation(self):
        """Test cloud storage error string representation."""
        error = CloudStorageError(
            message="Download failed",
            provider=CloudStorageProvider.GOOGLE_CLOUD,
            operation="download"
        )
        
        error_str = str(error)
        assert "Download failed" in error_str
        assert "google_cloud" in error_str
        assert "download" in error_str


class TestCloudStorageComponent:
    """Test cloud storage component functionality."""

    def test_cloud_storage_component_creation(self):
        """Test creating cloud storage component."""
        config = S3Config(
            provider=CloudStorageProvider.AWS_S3,
            bucket_name="test-bucket",
            access_key_id="test-key",
            secret_access_key="test-secret"
        )
        
        component = CloudStorageComponent(config)
        
        assert component.config == config
        assert component.provider == CloudStorageProvider.AWS_S3

    @pytest.mark.asyncio
    async def test_s3_component_initialization(self):
        """Test S3 component initialization."""
        config = S3Config(
            provider=CloudStorageProvider.AWS_S3,
            bucket_name="test-bucket",
            access_key_id="test-key",
            secret_access_key="test-secret"
        )
        
        component = CloudStorageComponent(config)
        
        with patch('boto3.client') as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.return_value = mock_client
            
            await component.initialize()
            
            assert component.status == "active"
            mock_boto3.assert_called_once()

    @pytest.mark.asyncio
    async def test_gcs_component_initialization(self):
        """Test Google Cloud Storage component initialization."""
        config = GCSConfig(
            provider=CloudStorageProvider.GOOGLE_CLOUD,
            bucket_name="test-bucket",
            project_id="test-project",
            credentials_path="/path/to/creds.json"
        )
        
        component = CloudStorageComponent(config)
        
        with patch('google.cloud.storage.Client') as mock_gcs:
            mock_client = MagicMock()
            mock_gcs.return_value = mock_client
            
            await component.initialize()
            
            assert component.status == "active"
            mock_gcs.assert_called_once()

    @pytest.mark.asyncio
    async def test_azure_component_initialization(self):
        """Test Azure Blob Storage component initialization."""
        config = AzureConfig(
            provider=CloudStorageProvider.AZURE_BLOB,
            container_name="test-container",
            account_name="testaccount",
            account_key="test-key"
        )
        
        component = CloudStorageComponent(config)
        
        with patch('azure.storage.blob.BlobServiceClient') as mock_azure:
            mock_client = MagicMock()
            mock_azure.return_value = mock_client
            
            await component.initialize()
            
            assert component.status == "active"
            mock_azure.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_file_s3(self):
        """Test uploading file to S3."""
        config = S3Config(
            provider=CloudStorageProvider.AWS_S3,
            bucket_name="test-bucket",
            access_key_id="test-key",
            secret_access_key="test-secret"
        )
        
        component = CloudStorageComponent(config)
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write("Test content")
            tmp_file.flush()
            
            with patch('boto3.client') as mock_boto3:
                mock_client = MagicMock()
                mock_boto3.return_value = mock_client
                
                await component.initialize()
                
                result = await component.upload_file(
                    local_path=tmp_file.name,
                    remote_key="test/file.txt"
                )
                
                assert result["success"] == True
                assert result["remote_key"] == "test/file.txt"
                mock_client.upload_file.assert_called_once()
            
            # Clean up
            os.unlink(tmp_file.name)

    @pytest.mark.asyncio
    async def test_download_file_s3(self):
        """Test downloading file from S3."""
        config = S3Config(
            provider=CloudStorageProvider.AWS_S3,
            bucket_name="test-bucket",
            access_key_id="test-key",
            secret_access_key="test-secret"
        )
        
        component = CloudStorageComponent(config)
        
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            with patch('boto3.client') as mock_boto3:
                mock_client = MagicMock()
                mock_boto3.return_value = mock_client
                
                await component.initialize()
                
                result = await component.download_file(
                    remote_key="test/file.txt",
                    local_path=tmp_file.name
                )
                
                assert result["success"] == True
                assert result["local_path"] == tmp_file.name
                mock_client.download_file.assert_called_once()
            
            # Clean up
            os.unlink(tmp_file.name)

    @pytest.mark.asyncio
    async def test_upload_content_s3(self):
        """Test uploading content directly to S3."""
        config = S3Config(
            provider=CloudStorageProvider.AWS_S3,
            bucket_name="test-bucket",
            access_key_id="test-key",
            secret_access_key="test-secret"
        )
        
        component = CloudStorageComponent(config)
        
        with patch('boto3.client') as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.return_value = mock_client
            
            await component.initialize()
            
            content = "Test content for upload"
            result = await component.upload_content(
                content=content,
                remote_key="test/content.txt",
                content_type="text/plain"
            )
            
            assert result["success"] == True
            assert result["remote_key"] == "test/content.txt"
            mock_client.put_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_content_s3(self):
        """Test downloading content directly from S3."""
        config = S3Config(
            provider=CloudStorageProvider.AWS_S3,
            bucket_name="test-bucket",
            access_key_id="test-key",
            secret_access_key="test-secret"
        )
        
        component = CloudStorageComponent(config)
        
        with patch('boto3.client') as mock_boto3:
            mock_client = MagicMock()
            mock_response = {
                'Body': MagicMock()
            }
            mock_response['Body'].read.return_value = b"Downloaded content"
            mock_client.get_object.return_value = mock_response
            mock_boto3.return_value = mock_client
            
            await component.initialize()
            
            result = await component.download_content(remote_key="test/content.txt")
            
            assert result["success"] == True
            assert result["content"] == "Downloaded content"
            mock_client.get_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_objects_s3(self):
        """Test listing objects in S3."""
        config = S3Config(
            provider=CloudStorageProvider.AWS_S3,
            bucket_name="test-bucket",
            access_key_id="test-key",
            secret_access_key="test-secret"
        )
        
        component = CloudStorageComponent(config)
        
        with patch('boto3.client') as mock_boto3:
            mock_client = MagicMock()
            mock_response = {
                'Contents': [
                    {'Key': 'file1.txt', 'Size': 100},
                    {'Key': 'file2.txt', 'Size': 200}
                ]
            }
            mock_client.list_objects_v2.return_value = mock_response
            mock_boto3.return_value = mock_client
            
            await component.initialize()
            
            result = await component.list_objects(prefix="test/")
            
            assert result["success"] == True
            assert len(result["objects"]) == 2
            assert result["objects"][0]["key"] == "file1.txt"
            mock_client.list_objects_v2.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_object_s3(self):
        """Test deleting object from S3."""
        config = S3Config(
            provider=CloudStorageProvider.AWS_S3,
            bucket_name="test-bucket",
            access_key_id="test-key",
            secret_access_key="test-secret"
        )
        
        component = CloudStorageComponent(config)
        
        with patch('boto3.client') as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.return_value = mock_client
            
            await component.initialize()
            
            result = await component.delete_object(remote_key="test/file.txt")
            
            assert result["success"] == True
            assert result["remote_key"] == "test/file.txt"
            mock_client.delete_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_object_exists_s3(self):
        """Test checking if object exists in S3."""
        config = S3Config(
            provider=CloudStorageProvider.AWS_S3,
            bucket_name="test-bucket",
            access_key_id="test-key",
            secret_access_key="test-secret"
        )
        
        component = CloudStorageComponent(config)
        
        with patch('boto3.client') as mock_boto3:
            mock_client = MagicMock()
            mock_client.head_object.return_value = {"ContentLength": 100}
            mock_boto3.return_value = mock_client
            
            await component.initialize()
            
            exists = await component.object_exists(remote_key="test/file.txt")
            
            assert exists == True
            mock_client.head_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_object_not_exists_s3(self):
        """Test checking if object doesn't exist in S3."""
        config = S3Config(
            provider=CloudStorageProvider.AWS_S3,
            bucket_name="test-bucket",
            access_key_id="test-key",
            secret_access_key="test-secret"
        )
        
        component = CloudStorageComponent(config)
        
        with patch('boto3.client') as mock_boto3:
            mock_client = MagicMock()
            mock_client.head_object.side_effect = Exception("Not found")
            mock_boto3.return_value = mock_client
            
            await component.initialize()
            
            exists = await component.object_exists(remote_key="test/nonexistent.txt")
            
            assert exists == False

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling in cloud storage operations."""
        config = S3Config(
            provider=CloudStorageProvider.AWS_S3,
            bucket_name="test-bucket",
            access_key_id="test-key",
            secret_access_key="test-secret"
        )
        
        component = CloudStorageComponent(config)
        
        with patch('boto3.client') as mock_boto3:
            mock_client = MagicMock()
            mock_client.upload_file.side_effect = Exception("Upload failed")
            mock_boto3.return_value = mock_client
            
            await component.initialize()
            
            with pytest.raises(CloudStorageError):
                await component.upload_file(
                    local_path="/nonexistent/file.txt",
                    remote_key="test/file.txt"
                )

    @pytest.mark.asyncio
    async def test_component_metrics(self):
        """Test cloud storage component metrics."""
        config = S3Config(
            provider=CloudStorageProvider.AWS_S3,
            bucket_name="test-bucket",
            access_key_id="test-key",
            secret_access_key="test-secret"
        )
        
        component = CloudStorageComponent(config)
        
        with patch('boto3.client') as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.return_value = mock_client
            
            await component.initialize()
            
            # Perform some operations
            await component.upload_content("content", "test1.txt")
            await component.upload_content("content", "test2.txt")
            
            metrics = component.get_metrics()
            
            assert metrics["operations_performed"] >= 2
            assert metrics["uploads_successful"] >= 2

    @pytest.mark.asyncio
    async def test_component_health_check(self):
        """Test cloud storage component health check."""
        config = S3Config(
            provider=CloudStorageProvider.AWS_S3,
            bucket_name="test-bucket",
            access_key_id="test-key",
            secret_access_key="test-secret"
        )
        
        component = CloudStorageComponent(config)
        
        with patch('boto3.client') as mock_boto3:
            mock_client = MagicMock()
            mock_client.head_bucket.return_value = {}
            mock_boto3.return_value = mock_client
            
            await component.initialize()
            
            health = await component.health_check()
            
            assert health["status"] == "healthy"
            assert health["provider"] == "aws_s3"
            assert health["bucket_accessible"] == True
