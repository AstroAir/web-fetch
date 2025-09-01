"""
Cloud storage resource component.

This component handles cloud storage operations for AWS S3, Google Cloud Storage,
and Azure Blob Storage with authentication, file operations, and metadata extraction.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from ..models.extended_resources import CloudStorageConfig, CloudStorageOperation, CloudStorageProvider
from ..models.resource import ResourceConfig, ResourceKind, ResourceRequest, ResourceResult
from .base import ResourceComponent, component_registry

logger = logging.getLogger(__name__)

# Optional cloud storage SDK imports
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

try:
    from google.cloud import storage as gcs
    from google.auth.exceptions import DefaultCredentialsError
    HAS_GCS = True
except ImportError:
    HAS_GCS = False

try:
    from azure.storage.blob import BlobServiceClient
    from azure.core.exceptions import AzureError
    HAS_AZURE = True
except ImportError:
    HAS_AZURE = False


class CloudStorageComponent(ResourceComponent):
    """Resource component for cloud storage operations."""

    kind = ResourceKind.CLOUD_STORAGE

    def __init__(
        self,
        config: Optional[ResourceConfig] = None,
        storage_config: Optional[CloudStorageConfig] = None
    ):
        super().__init__(config)
        self.storage_config = storage_config or CloudStorageConfig(
            provider=CloudStorageProvider.AWS_S3,
            bucket_name="test-bucket"
        )
        self._client: Any = None

    async def _get_s3_client(self) -> Any:
        """Get or create AWS S3 client."""
        if not HAS_BOTO3:
            raise ImportError("boto3 is required for AWS S3 operations")

        if self._client is None:
            session_kwargs = {}

            if self.storage_config.access_key and self.storage_config.secret_key:
                session_kwargs.update({
                    'aws_access_key_id': self.storage_config.access_key.get_secret_value(),
                    'aws_secret_access_key': self.storage_config.secret_key.get_secret_value(),
                })

                if self.storage_config.token:
                    session_kwargs['aws_session_token'] = self.storage_config.token.get_secret_value()

            if self.storage_config.region:
                session_kwargs['region_name'] = self.storage_config.region

            session = boto3.Session(**session_kwargs)

            client_kwargs = {}
            if self.storage_config.endpoint_url:
                client_kwargs['endpoint_url'] = self.storage_config.endpoint_url

            self._client = session.client('s3', **client_kwargs)

        return self._client

    async def _get_gcs_client(self) -> Any:
        """Get or create Google Cloud Storage client."""
        if not HAS_GCS:
            raise ImportError("google-cloud-storage is required for GCS operations")

        if self._client is None:
            # GCS typically uses service account credentials or default credentials
            self._client = gcs.Client()

        return self._client

    async def _get_azure_client(self) -> Any:
        """Get or create Azure Blob Storage client."""
        if not HAS_AZURE:
            raise ImportError("azure-storage-blob is required for Azure operations")

        if self._client is None:
            if self.storage_config.access_key:
                # Use account key authentication
                account_url = f"https://{self.storage_config.access_key.get_secret_value()}.blob.core.windows.net"
                self._client = BlobServiceClient(
                    account_url=account_url,
                    credential=self.storage_config.secret_key.get_secret_value() if self.storage_config.secret_key else None
                )
            else:
                raise ValueError("Azure Blob Storage requires access_key (account name) and secret_key (account key)")

        return self._client

    async def _execute_s3_operation(self, operation: CloudStorageOperation) -> Dict[str, Any]:
        """Execute AWS S3 operation."""
        client = await self._get_s3_client()
        bucket = self.storage_config.bucket_name

        try:
            if operation.operation == "get":
                response = client.get_object(Bucket=bucket, Key=operation.key)
                content = response['Body'].read()
                return {
                    "operation": "get",
                    "key": operation.key,
                    "content": content,
                    "content_type": response.get('ContentType'),
                    "size": response.get('ContentLength'),
                    "last_modified": response.get('LastModified').isoformat() if response.get('LastModified') else None,
                    "metadata": response.get('Metadata', {}),
                }

            elif operation.operation == "list":
                prefix = operation.prefix or ""
                response = client.list_objects_v2(Bucket=bucket, Prefix=prefix)
                objects = []
                for obj in response.get('Contents', []):
                    objects.append({
                        "key": obj['Key'],
                        "size": obj['Size'],
                        "last_modified": obj['LastModified'].isoformat(),
                        "etag": obj['ETag'],
                    })
                return {
                    "operation": "list",
                    "prefix": prefix,
                    "objects": objects,
                    "count": len(objects),
                }

            elif operation.operation == "put":
                extra_args: Dict[str, Any] = {}
                if operation.content_type:
                    extra_args['ContentType'] = operation.content_type
                if operation.metadata:
                    extra_args['Metadata'] = dict(operation.metadata)

                if operation.local_path:
                    client.upload_file(operation.local_path, bucket, operation.key, ExtraArgs=extra_args)
                    return {
                        "operation": "put",
                        "key": operation.key,
                        "source": operation.local_path,
                        "success": True,
                    }
                else:
                    raise ValueError("local_path required for S3 put operation")

            elif operation.operation == "delete":
                client.delete_object(Bucket=bucket, Key=operation.key)
                return {
                    "operation": "delete",
                    "key": operation.key,
                    "success": True,
                }

            else:
                raise ValueError(f"Unsupported S3 operation: {operation.operation}")

        except ClientError as e:
            raise Exception(f"S3 operation failed: {e}")

    async def _execute_gcs_operation(self, operation: CloudStorageOperation) -> Dict[str, Any]:
        """Execute Google Cloud Storage operation."""
        client = await self._get_gcs_client()
        bucket = client.bucket(self.storage_config.bucket_name)

        try:
            if operation.operation == "get":
                blob = bucket.blob(operation.key)
                content = blob.download_as_bytes()
                return {
                    "operation": "get",
                    "key": operation.key,
                    "content": content,
                    "content_type": blob.content_type,
                    "size": blob.size,
                    "last_modified": blob.time_created.isoformat() if blob.time_created else None,
                    "metadata": blob.metadata or {},
                }

            elif operation.operation == "list":
                prefix = operation.prefix or ""
                blobs = bucket.list_blobs(prefix=prefix)
                objects = []
                for blob in blobs:
                    objects.append({
                        "key": blob.name,
                        "size": blob.size,
                        "last_modified": blob.time_created.isoformat() if blob.time_created else None,
                        "etag": blob.etag,
                    })
                return {
                    "operation": "list",
                    "prefix": prefix,
                    "objects": objects,
                    "count": len(objects),
                }

            elif operation.operation == "put":
                blob = bucket.blob(operation.key)
                if operation.content_type:
                    blob.content_type = operation.content_type
                if operation.metadata:
                    blob.metadata = operation.metadata

                if operation.local_path:
                    blob.upload_from_filename(operation.local_path)
                    return {
                        "operation": "put",
                        "key": operation.key,
                        "source": operation.local_path,
                        "success": True,
                    }
                else:
                    raise ValueError("local_path required for GCS put operation")

            elif operation.operation == "delete":
                blob = bucket.blob(operation.key)
                blob.delete()
                return {
                    "operation": "delete",
                    "key": operation.key,
                    "success": True,
                }

            else:
                raise ValueError(f"Unsupported GCS operation: {operation.operation}")

        except Exception as e:
            raise Exception(f"GCS operation failed: {e}")

    async def _execute_azure_operation(self, operation: CloudStorageOperation) -> Dict[str, Any]:
        """Execute Azure Blob Storage operation."""
        client = await self._get_azure_client()
        container = self.storage_config.bucket_name

        try:
            if operation.operation == "get":
                blob_client = client.get_blob_client(container=container, blob=operation.key)
                blob_data = blob_client.download_blob()
                content = blob_data.readall()
                properties = blob_client.get_blob_properties()

                return {
                    "operation": "get",
                    "key": operation.key,
                    "content": content,
                    "content_type": properties.content_settings.content_type,
                    "size": properties.size,
                    "last_modified": properties.last_modified.isoformat() if properties.last_modified else None,
                    "metadata": properties.metadata or {},
                }

            elif operation.operation == "list":
                prefix = operation.prefix or ""
                container_client = client.get_container_client(container)
                blobs = container_client.list_blobs(name_starts_with=prefix)
                objects = []
                for blob in blobs:
                    objects.append({
                        "key": blob.name,
                        "size": blob.size,
                        "last_modified": blob.last_modified.isoformat() if blob.last_modified else None,
                        "etag": blob.etag,
                    })
                return {
                    "operation": "list",
                    "prefix": prefix,
                    "objects": objects,
                    "count": len(objects),
                }

            elif operation.operation == "put":
                blob_client = client.get_blob_client(container=container, blob=operation.key)

                if operation.local_path:
                    with open(operation.local_path, 'rb') as data:
                        blob_client.upload_blob(
                            data,
                            content_type=operation.content_type,
                            metadata=operation.metadata,
                            overwrite=True
                        )
                    return {
                        "operation": "put",
                        "key": operation.key,
                        "source": operation.local_path,
                        "success": True,
                    }
                else:
                    raise ValueError("local_path required for Azure put operation")

            elif operation.operation == "delete":
                blob_client = client.get_blob_client(container=container, blob=operation.key)
                blob_client.delete_blob()
                return {
                    "operation": "delete",
                    "key": operation.key,
                    "success": True,
                }

            else:
                raise ValueError(f"Unsupported Azure operation: {operation.operation}")

        except AzureError as e:
            raise Exception(f"Azure operation failed: {e}")

    async def fetch(self, request: ResourceRequest) -> ResourceResult:
        """
        Execute cloud storage operation.

        Args:
            request: Resource request with storage operation

        Returns:
            ResourceResult with operation results
        """
        try:
            # Parse operation from request options
            operation_data = request.options.get("operation")
            if not operation_data:
                return ResourceResult(
                    url=str(request.uri),
                    error="Cloud storage operation not specified in request options"
                )

            # Create operation configuration
            if isinstance(operation_data, dict):
                operation = CloudStorageOperation(**operation_data)
            else:
                return ResourceResult(
                    url=str(request.uri),
                    error="Invalid operation format"
                )

            # Execute operation based on provider
            if self.storage_config.provider == CloudStorageProvider.AWS_S3:
                result_data = await self._execute_s3_operation(operation)
            elif self.storage_config.provider == CloudStorageProvider.GOOGLE_CLOUD:
                result_data = await self._execute_gcs_operation(operation)
            elif self.storage_config.provider == CloudStorageProvider.AZURE_BLOB:
                result_data = await self._execute_azure_operation(operation)
            else:
                return ResourceResult(  # type: ignore[unreachable]
                    url=str(request.uri),
                    error=f"Unsupported cloud storage provider: {self.storage_config.provider}"
                )

            # Create result
            result = ResourceResult(
                url=str(request.uri),
                status_code=200,
                content=result_data,
                content_type="application/json"
            )

            # Add cloud storage metadata
            provider_name = self.storage_config.provider.value if hasattr(self.storage_config.provider, 'value') else str(self.storage_config.provider)
            result.metadata = {
                "cloud_storage": {
                    "provider": provider_name,
                    "bucket": self.storage_config.bucket_name,
                    "operation": operation.operation,
                    "region": self.storage_config.region,
                }
            }

            return result

        except Exception as e:
            logger.error(f"Cloud storage operation failed: {e}")
            return ResourceResult(
                url=str(request.uri),
                error=f"Cloud storage error: {str(e)}"
            )

    def cache_key(self, request: ResourceRequest) -> Optional[str]:
        """Generate cache key for cloud storage operation."""
        if not self.config or not self.config.enable_cache:
            return None

        operation_data = request.options.get("operation", {})
        if isinstance(operation_data, dict):
            # Only cache read operations
            if operation_data.get("operation") in ["get", "list"]:
                key_parts = [
                    "cloud_storage",
                    self.storage_config.provider.value if hasattr(self.storage_config.provider, 'value') else str(self.storage_config.provider),
                    self.storage_config.bucket_name,
                    str(sorted(operation_data.items())),
                ]
                return ":".join(key_parts)

        return None


# Register component in the global registry
component_registry.register(ResourceKind.CLOUD_STORAGE, lambda config=None: CloudStorageComponent(config))

__all__ = ["CloudStorageComponent"]
