#!/usr/bin/env python3
"""
Cloud Storage Manager Example

This example demonstrates how to use the cloud storage component to manage
files across different cloud storage providers (AWS S3, Google Cloud Storage, Azure Blob).

Features demonstrated:
- Multi-provider cloud storage operations
- File upload, download, and listing
- Batch operations
- Metadata management
- Cross-provider synchronization
"""

import asyncio
import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from web_fetch import fetch_cloud_storage
from web_fetch.models.extended_resources import (
    CloudStorageConfig, CloudStorageOperation, CloudStorageProvider
)
from web_fetch.models.resource import ResourceConfig
from pydantic import SecretStr


class CloudStorageManager:
    """Manage files across multiple cloud storage providers."""
    
    def __init__(self):
        """Initialize the storage manager."""
        self.resource_config = ResourceConfig(
            enable_cache=True,
            cache_ttl_seconds=300  # 5 minutes
        )
        
        self.operations_log: List[Dict[str, Any]] = []
    
    def get_s3_config(self) -> CloudStorageConfig:
        """Get AWS S3 configuration."""
        return CloudStorageConfig(
            provider=CloudStorageProvider.AWS_S3,
            bucket_name=os.getenv("AWS_S3_BUCKET", "my-s3-bucket"),
            access_key=SecretStr(os.getenv("AWS_ACCESS_KEY_ID", "access-key")),
            secret_key=SecretStr(os.getenv("AWS_SECRET_ACCESS_KEY", "secret-key")),
            region=os.getenv("AWS_REGION", "us-east-1"),
            multipart_threshold=16 * 1024 * 1024,  # 16MB
            max_concurrency=10,
            retry_attempts=3,
            extra_config={
                "signature_version": "s3v4",
                "use_ssl": True,
                "verify": True
            }
        )
    
    def get_gcs_config(self) -> CloudStorageConfig:
        """Get Google Cloud Storage configuration."""
        return CloudStorageConfig(
            provider=CloudStorageProvider.GOOGLE_CLOUD,
            bucket_name=os.getenv("GCS_BUCKET", "my-gcs-bucket"),
            region=os.getenv("GCS_REGION", "us-central1"),
            multipart_threshold=32 * 1024 * 1024,  # 32MB
            max_concurrency=8,
            retry_attempts=3,
            extra_config={
                "credentials_path": os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
                "project_id": os.getenv("GCP_PROJECT_ID")
            }
        )
    
    def get_azure_config(self) -> CloudStorageConfig:
        """Get Azure Blob Storage configuration."""
        return CloudStorageConfig(
            provider=CloudStorageProvider.AZURE_BLOB,
            bucket_name=os.getenv("AZURE_CONTAINER", "my-container"),
            access_key=SecretStr(os.getenv("AZURE_ACCOUNT_NAME", "account-name")),
            secret_key=SecretStr(os.getenv("AZURE_ACCOUNT_KEY", "account-key")),
            multipart_threshold=64 * 1024 * 1024,  # 64MB
            max_concurrency=6,
            retry_attempts=3
        )
    
    async def list_files(self, storage_config: CloudStorageConfig, prefix: str = "") -> Dict[str, Any]:
        """
        List files in cloud storage.
        
        Args:
            storage_config: Storage configuration
            prefix: Prefix to filter files
            
        Returns:
            List operation results
        """
        operation = CloudStorageOperation(
            operation="list",
            prefix=prefix
        )
        
        try:
            result = await fetch_cloud_storage(
                storage_config,
                operation,
                config=self.resource_config
            )
            
            if not result.is_success:
                return {
                    "provider": storage_config.provider.value,
                    "operation": "list",
                    "status": "error",
                    "error": result.error
                }
            
            files = result.content.get("objects", [])
            
            return {
                "provider": storage_config.provider.value,
                "operation": "list",
                "status": "success",
                "prefix": prefix,
                "file_count": len(files),
                "files": files,
                "total_size": sum(f.get("size", 0) for f in files),
                "listed_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "provider": storage_config.provider.value,
                "operation": "list",
                "status": "error",
                "error": str(e)
            }
    
    async def upload_file(self, storage_config: CloudStorageConfig, 
                         local_path: str, remote_key: str, 
                         metadata: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Upload file to cloud storage.
        
        Args:
            storage_config: Storage configuration
            local_path: Local file path
            remote_key: Remote object key
            metadata: Optional metadata
            
        Returns:
            Upload operation results
        """
        operation = CloudStorageOperation(
            operation="put",
            key=remote_key,
            local_path=local_path,
            metadata=metadata or {}
        )
        
        try:
            # Check if local file exists
            if not Path(local_path).exists():
                return {
                    "provider": storage_config.provider.value,
                    "operation": "upload",
                    "status": "error",
                    "error": f"Local file not found: {local_path}"
                }
            
            file_size = Path(local_path).stat().st_size
            
            result = await fetch_cloud_storage(
                storage_config,
                operation,
                config=self.resource_config
            )
            
            if not result.is_success:
                return {
                    "provider": storage_config.provider.value,
                    "operation": "upload",
                    "status": "error",
                    "error": result.error
                }
            
            return {
                "provider": storage_config.provider.value,
                "operation": "upload",
                "status": "success",
                "local_path": local_path,
                "remote_key": remote_key,
                "file_size": file_size,
                "metadata": metadata,
                "uploaded_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "provider": storage_config.provider.value,
                "operation": "upload",
                "status": "error",
                "error": str(e)
            }
    
    async def download_file(self, storage_config: CloudStorageConfig,
                           remote_key: str, local_path: str) -> Dict[str, Any]:
        """
        Download file from cloud storage.
        
        Args:
            storage_config: Storage configuration
            remote_key: Remote object key
            local_path: Local file path to save to
            
        Returns:
            Download operation results
        """
        operation = CloudStorageOperation(
            operation="get",
            key=remote_key,
            local_path=local_path
        )
        
        try:
            result = await fetch_cloud_storage(
                storage_config,
                operation,
                config=self.resource_config
            )
            
            if not result.is_success:
                return {
                    "provider": storage_config.provider.value,
                    "operation": "download",
                    "status": "error",
                    "error": result.error
                }
            
            # Save content to local file
            content = result.content.get("content", b"")
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(local_path, "wb") as f:
                f.write(content)
            
            return {
                "provider": storage_config.provider.value,
                "operation": "download",
                "status": "success",
                "remote_key": remote_key,
                "local_path": local_path,
                "file_size": len(content),
                "downloaded_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "provider": storage_config.provider.value,
                "operation": "download",
                "status": "error",
                "error": str(e)
            }
    
    async def sync_between_providers(self, source_config: CloudStorageConfig,
                                   target_config: CloudStorageConfig,
                                   prefix: str = "") -> Dict[str, Any]:
        """
        Synchronize files between two cloud storage providers.
        
        Args:
            source_config: Source storage configuration
            target_config: Target storage configuration
            prefix: Prefix to filter files for sync
            
        Returns:
            Synchronization results
        """
        print(f"Syncing from {source_config.provider.value} to {target_config.provider.value}...")
        
        # List files in source
        source_files = await self.list_files(source_config, prefix)
        
        if source_files["status"] != "success":
            return {
                "operation": "sync",
                "status": "error",
                "error": f"Failed to list source files: {source_files['error']}"
            }
        
        # List files in target
        target_files = await self.list_files(target_config, prefix)
        target_keys = set()
        
        if target_files["status"] == "success":
            target_keys = {f["key"] for f in target_files["files"]}
        
        # Sync files
        sync_tasks = []
        files_to_sync = []
        
        for file_info in source_files["files"]:
            file_key = file_info["key"]
            
            # Skip if file already exists in target
            if file_key in target_keys:
                continue
            
            files_to_sync.append(file_key)
            
            # Download from source and upload to target
            temp_path = f"/tmp/{Path(file_key).name}"
            
            # Create sync task
            async def sync_file(key: str, temp: str):
                # Download from source
                download_result = await self.download_file(source_config, key, temp)
                if download_result["status"] != "success":
                    return download_result
                
                # Upload to target
                upload_result = await self.upload_file(target_config, temp, key)
                
                # Clean up temp file
                try:
                    Path(temp).unlink()
                except:
                    pass
                
                return upload_result
            
            sync_tasks.append(sync_file(file_key, temp_path))
        
        # Execute sync tasks
        if sync_tasks:
            sync_results = await asyncio.gather(*sync_tasks, return_exceptions=True)
            
            successful_syncs = 0
            failed_syncs = 0
            
            for result in sync_results:
                if isinstance(result, Exception):
                    failed_syncs += 1
                elif result.get("status") == "success":
                    successful_syncs += 1
                else:
                    failed_syncs += 1
        else:
            successful_syncs = 0
            failed_syncs = 0
        
        return {
            "operation": "sync",
            "status": "success",
            "source_provider": source_config.provider.value,
            "target_provider": target_config.provider.value,
            "total_source_files": len(source_files["files"]),
            "files_to_sync": len(files_to_sync),
            "successful_syncs": successful_syncs,
            "failed_syncs": failed_syncs,
            "synced_at": datetime.utcnow().isoformat()
        }
    
    async def manage_storage(self, providers: List[str], operations: List[str]) -> Dict[str, Any]:
        """
        Perform storage management operations across providers.
        
        Args:
            providers: List of storage providers to use
            operations: List of operations to perform
            
        Returns:
            Management summary
        """
        print("Starting cloud storage management...")
        
        configs = {}
        if "s3" in providers:
            configs["s3"] = self.get_s3_config()
        if "gcs" in providers:
            configs["gcs"] = self.get_gcs_config()
        if "azure" in providers:
            configs["azure"] = self.get_azure_config()
        
        tasks = []
        
        # List operations
        if "list" in operations:
            for provider, config in configs.items():
                tasks.append(self.list_files(config, "documents/"))
        
        # Upload operations (demo files)
        if "upload" in operations:
            # Create demo files
            demo_files = ["demo1.txt", "demo2.txt"]
            for filename in demo_files:
                demo_path = Path(f"/tmp/{filename}")
                demo_path.write_text(f"Demo content for {filename}\nCreated at: {datetime.now()}")
                
                for provider, config in configs.items():
                    tasks.append(self.upload_file(
                        config, 
                        str(demo_path), 
                        f"documents/{filename}",
                        {"created_by": "cloud_storage_manager", "demo": "true"}
                    ))
        
        # Execute all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        successful_operations = 0
        failed_operations = 0
        
        for result in results:
            if isinstance(result, Exception):
                failed_operations += 1
                print(f"Operation failed with exception: {result}")
            elif result.get("status") == "success":
                successful_operations += 1
                self.operations_log.append(result)
            else:
                failed_operations += 1
                print(f"Operation failed: {result.get('error', 'Unknown error')}")
        
        return {
            "total_operations": len(tasks),
            "successful_operations": successful_operations,
            "failed_operations": failed_operations,
            "providers_used": len(configs),
            "managed_at": datetime.utcnow().isoformat()
        }
    
    def export_log(self, filename: str) -> None:
        """Export operations log to JSON file."""
        output_path = Path(filename)
        
        export_data = {
            "metadata": {
                "exported_at": datetime.utcnow().isoformat(),
                "total_operations": len(self.operations_log)
            },
            "operations": self.operations_log
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(self.operations_log)} operations to {output_path}")


async def main():
    """Main example function."""
    # Storage providers to use (comment out unavailable ones)
    providers = [
        "s3",
        # "gcs",
        # "azure"
    ]
    
    # Operations to perform
    operations = [
        "list",
        "upload"
    ]
    
    # Create storage manager
    manager = CloudStorageManager()
    
    # Perform storage management
    summary = await manager.manage_storage(providers, operations)
    
    # Print summary
    print("\n" + "="*50)
    print("CLOUD STORAGE MANAGEMENT SUMMARY")
    print("="*50)
    print(f"Total operations: {summary['total_operations']}")
    print(f"Successful operations: {summary['successful_operations']}")
    print(f"Failed operations: {summary['failed_operations']}")
    print(f"Providers used: {summary['providers_used']}")
    
    # Show operations log
    if manager.operations_log:
        print(f"\nRecent operations:")
        for op in manager.operations_log[-5:]:  # Show last 5
            print(f"- {op['operation']} on {op['provider']}: {op['status']}")
    
    # Export log
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    manager.export_log(f"storage_operations_{timestamp}.json")


if __name__ == "__main__":
    print("Cloud Storage Manager Example")
    print("=" * 50)
    print("This example demonstrates multi-provider cloud storage management.")
    print("Configure storage credentials via environment variables:")
    print("- AWS: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_BUCKET, AWS_REGION")
    print("- GCS: GOOGLE_APPLICATION_CREDENTIALS, GCP_PROJECT_ID, GCS_BUCKET, GCS_REGION")
    print("- Azure: AZURE_ACCOUNT_NAME, AZURE_ACCOUNT_KEY, AZURE_CONTAINER")
    print()
    
    asyncio.run(main())
