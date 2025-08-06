#!/usr/bin/env python3
"""
FTP functionality examples for the web_fetch library.

This script demonstrates the key features of the FTP functionality including
single file downloads, batch downloads, directory listing, and streaming.
"""

import asyncio
from pathlib import Path

from web_fetch import (
    FTPAuthType,
    FTPConfig,
    FTPFetcher,
    FTPMode,
    FTPRequest,
    FTPBatchRequest,
    FTPVerificationMethod,
    ftp_download_file,
    ftp_list_directory,
    ftp_get_file_info,
    ftp_download_batch,
)


async def basic_ftp_examples():
    """Demonstrate basic FTP operations."""
    print("=== Basic FTP Examples ===\n")

    # Example 1: List directory contents
    print("1. Listing FTP directory contents:")
    try:
        # Note: Replace with a real FTP server for testing
        files = await ftp_list_directory("ftp://ftp.example.com/pub/")
        print(f"Found {len(files)} files:")
        for file_info in files[:5]:  # Show first 5 files
            print(f"  - {file_info.name} ({'dir' if file_info.is_directory else 'file'})")
            if file_info.size:
                print(f"    Size: {file_info.size} bytes")
    except Exception as e:
        print(f"Error listing directory: {e}")

    print()

    # Example 2: Get file information
    print("2. Getting file information:")
    try:
        file_info = await ftp_get_file_info("ftp://ftp.example.com/pub/readme.txt")
        print(f"File: {file_info.name}")
        print(f"Size: {file_info.size} bytes")
        print(f"Modified: {file_info.modified_time}")
        print(f"Is directory: {file_info.is_directory}")
    except Exception as e:
        print(f"Error getting file info: {e}")

    print()

    # Example 3: Simple file download
    print("3. Simple file download:")
    try:
        local_path = Path("downloads/readme.txt")
        result = await ftp_download_file(
            "ftp://ftp.example.com/pub/readme.txt",
            local_path
        )

        if result.is_success:
            print(f"Downloaded {result.bytes_transferred} bytes to {local_path}")
            print(f"Transfer rate: {result.transfer_rate_mbps:.2f} MB/s")
        else:
            print(f"Download failed: {result.error}")
    except Exception as e:
        print(f"Error downloading file: {e}")


async def advanced_ftp_examples():
    """Demonstrate advanced FTP features."""
    print("\n=== Advanced FTP Examples ===\n")

    # Custom configuration
    config = FTPConfig(
        mode=FTPMode.PASSIVE,
        auth_type=FTPAuthType.ANONYMOUS,
        max_concurrent_downloads=3,
        enable_parallel_downloads=True,
        verification_method=FTPVerificationMethod.SIZE,
        enable_resume=True,
        chunk_size=16384,  # 16KB chunks
        rate_limit_bytes_per_second=1024*1024,  # 1MB/s limit
    )

    # Example 1: Download with progress tracking
    print("1. Download with progress tracking:")

    def progress_callback(progress_info):
        if progress_info.progress_percentage:
            print(f"  Progress: {progress_info.progress_percentage:.1f}% "
                  f"({progress_info.bytes_transferred}/{progress_info.total_bytes} bytes) "
                  f"Rate: {progress_info.transfer_rate_mbps:.2f} MB/s")

    try:
        local_path = Path("downloads/large_file.zip")
        result = await ftp_download_file(
            "ftp://ftp.example.com/pub/large_file.zip",
            local_path,
            config=config,
            progress_callback=progress_callback
        )

        if result.is_success:
            print(f"Download completed: {result.bytes_transferred} bytes")
        else:
            print(f"Download failed: {result.error}")
    except Exception as e:
        print(f"Error: {e}")

    print()

    # Example 2: Batch downloads
    print("2. Batch downloads:")

    requests = [
        FTPRequest(url="ftp://ftp.example.com/pub/file1.txt", local_path=Path("downloads/file1.txt")),
        FTPRequest(url="ftp://ftp.example.com/pub/file2.txt", local_path=Path("downloads/file2.txt")),
        FTPRequest(url="ftp://ftp.example.com/pub/file3.txt", local_path=Path("downloads/file3.txt")),
    ]

    def batch_progress_callback(url, progress_info):
        filename = Path(url).name
        if progress_info.progress_percentage:
            print(f"  {filename}: {progress_info.progress_percentage:.1f}%")

    try:
        result = await ftp_download_batch(
            requests,
            config=config,
            parallel=True,
            progress_callback=batch_progress_callback
        )

        print(f"Batch download completed:")
        print(f"  Total files: {result.total_requests}")
        print(f"  Successful: {result.successful_requests}")
        print(f"  Failed: {result.failed_requests}")
        print(f"  Success rate: {result.success_rate:.1f}%")
        print(f"  Total bytes: {result.total_bytes_transferred}")
        print(f"  Average rate: {result.average_transfer_rate_mbps:.2f} MB/s")

    except Exception as e:
        print(f"Error: {e}")


async def streaming_example():
    """Demonstrate streaming downloads for large files."""
    print("\n=== Streaming Download Example ===\n")

    config = FTPConfig(
        chunk_size=32768,  # 32KB chunks for streaming
        max_file_size=100 * 1024 * 1024,  # 100MB max file size
        enable_resume=True,
    )

    async def streaming_progress(progress_info):
        if progress_info.progress_percentage:
            print(f"Streaming: {progress_info.progress_percentage:.1f}% "
                  f"Rate: {progress_info.transfer_rate_mbps:.2f} MB/s "
                  f"ETA: {progress_info.estimated_time_remaining:.0f}s"
                  if progress_info.estimated_time_remaining else "")

    try:
        async with FTPFetcher(config) as fetcher:
            local_path = Path("downloads/large_streaming_file.zip")
            result = await fetcher.stream_download(
                "ftp://ftp.example.com/pub/large_file.zip",
                local_path,
                streaming_progress
            )

            if result.is_success:
                print(f"Streaming download completed: {result.bytes_transferred} bytes")
                print(f"Transfer rate: {result.transfer_rate_mbps:.2f} MB/s")

                # Verify the download
                if result.file_info:
                    is_valid = await fetcher.verify_file(local_path, result.file_info)
                    print(f"File verification: {'PASSED' if is_valid else 'FAILED'}")
            else:
                print(f"Streaming download failed: {result.error}")

    except Exception as e:
        print(f"Error: {e}")


async def main():
    """Run all FTP examples."""
    print("FTP Functionality Examples")
    print("=" * 50)

    # Create downloads directory
    Path("downloads").mkdir(exist_ok=True)

    # Run examples
    await basic_ftp_examples()
    await advanced_ftp_examples()
    await streaming_example()

    print("\n" + "=" * 50)
    print("Examples completed!")
    print("\nNote: These examples use placeholder FTP URLs.")
    print("Replace with real FTP server URLs for actual testing.")


if __name__ == "__main__":
    asyncio.run(main())