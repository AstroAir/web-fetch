"""
FTP resource verification and integrity checking.

This module provides comprehensive file verification, integrity checks,
and validation for FTP downloads with multiple verification methods.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiofiles

from ..exceptions import FTPVerificationError
from .models import (
    FTPConfig,
    FTPFileInfo,
    FTPVerificationMethod,
    FTPVerificationResult,
)


class FTPVerificationManager:
    """
    Manager for FTP file verification and integrity checking.
    """

    def __init__(self, config: FTPConfig):
        """Initialize the verification manager."""
        self.config = config

    async def verify_file(
        self,
        local_path: Path,
        file_info: FTPFileInfo,
        expected_checksums: Optional[Dict[str, str]] = None,
    ) -> FTPVerificationResult:
        """
        Verify a downloaded file using the configured verification method.

        Args:
            local_path: Path to the downloaded file
            file_info: Information about the original file
            expected_checksums: Optional dictionary of expected checksums

        Returns:
            FTPVerificationResult with verification details
        """
        if self.config.verification_method == FTPVerificationMethod.NONE:
            return FTPVerificationResult(
                method=FTPVerificationMethod.NONE,
                expected_value=None,
                actual_value=None,
                is_valid=True,
                error=None,
            )

        if not local_path.exists():
            return FTPVerificationResult(
                method=self.config.verification_method,
                expected_value=None,
                actual_value=None,
                is_valid=False,
                error="Local file does not exist",
            )

        try:
            if self.config.verification_method == FTPVerificationMethod.SIZE:
                return await self._verify_size(local_path, file_info)

            elif self.config.verification_method == FTPVerificationMethod.MD5:
                return await self._verify_checksum(
                    local_path,
                    "md5",
                    expected_checksums.get("md5") if expected_checksums else None,
                )

            elif self.config.verification_method == FTPVerificationMethod.SHA256:
                return await self._verify_checksum(
                    local_path,
                    "sha256",
                    expected_checksums.get("sha256") if expected_checksums else None,
                )

            else:
                return FTPVerificationResult(
                    method=self.config.verification_method,
                    expected_value=None,
                    actual_value=None,
                    is_valid=False,
                    error=f"Unsupported verification method: {self.config.verification_method}",
                )

        except Exception as e:
            return FTPVerificationResult(
                method=self.config.verification_method,
                expected_value=None,
                actual_value=None,
                is_valid=False,
                error=f"Verification failed: {str(e)}",
            )

    async def _verify_size(
        self, local_path: Path, file_info: FTPFileInfo
    ) -> FTPVerificationResult:
        """
        Verify file size matches expected size.

        Args:
            local_path: Path to the downloaded file
            file_info: Information about the original file

        Returns:
            FTPVerificationResult with size verification details
        """
        try:
            actual_size = local_path.stat().st_size
            expected_size = file_info.size

            if expected_size is None:
                return FTPVerificationResult(
                    method=FTPVerificationMethod.SIZE,
                    expected_value=None,
                    actual_value=str(actual_size),
                    is_valid=True,
                    error="No expected size available, verification skipped",
                )

            is_valid = actual_size == expected_size
            error = (
                None
                if is_valid
                else f"Size mismatch: expected {expected_size}, got {actual_size}"
            )

            return FTPVerificationResult(
                method=FTPVerificationMethod.SIZE,
                expected_value=str(expected_size),
                actual_value=str(actual_size),
                is_valid=is_valid,
                error=error,
            )

        except Exception as e:
            return FTPVerificationResult(
                method=FTPVerificationMethod.SIZE,
                expected_value=None,
                actual_value=None,
                is_valid=False,
                error=f"Size verification failed: {str(e)}",
            )

    async def _verify_checksum(
        self, local_path: Path, algorithm: str, expected_checksum: Optional[str] = None
    ) -> FTPVerificationResult:
        """
        Verify file checksum using specified algorithm.

        Args:
            local_path: Path to the downloaded file
            algorithm: Hash algorithm to use (md5, sha256)
            expected_checksum: Expected checksum value

        Returns:
            FTPVerificationResult with checksum verification details
        """
        try:
            # Calculate file checksum
            if algorithm.lower() == "md5":
                hash_func = hashlib.md5()
                method = FTPVerificationMethod.MD5
            elif algorithm.lower() == "sha256":
                hash_func = hashlib.sha256()
                method = FTPVerificationMethod.SHA256
            else:
                return FTPVerificationResult(
                    method=self.config.verification_method,
                    expected_value=expected_checksum,
                    actual_value=None,
                    is_valid=False,
                    error=f"Unsupported hash algorithm: {algorithm}",
                )

            # Read file and calculate hash
            async with aiofiles.open(local_path, "rb") as f:
                while chunk := await f.read(self.config.chunk_size):
                    hash_func.update(chunk)

            actual_checksum = hash_func.hexdigest().lower()

            if expected_checksum is None:
                return FTPVerificationResult(
                    method=method,
                    expected_value=None,
                    actual_value=actual_checksum,
                    is_valid=True,
                    error=f"Checksum calculated but no expected value provided: {actual_checksum}",
                )

            expected_checksum = expected_checksum.lower()
            is_valid = actual_checksum == expected_checksum
            error = (
                None
                if is_valid
                else f"Checksum mismatch: expected {expected_checksum}, got {actual_checksum}"
            )

            return FTPVerificationResult(
                method=method,
                expected_value=expected_checksum,
                actual_value=actual_checksum,
                is_valid=is_valid,
                error=error,
            )

        except Exception as e:
            return FTPVerificationResult(
                method=self.config.verification_method,
                expected_value=expected_checksum,
                actual_value=None,
                is_valid=False,
                error=f"Checksum verification failed: {str(e)}",
            )

    async def verify_batch_files(
        self,
        file_paths: List[Tuple[Path, FTPFileInfo]],
        expected_checksums: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> List[FTPVerificationResult]:
        """
        Verify multiple files in batch.

        Args:
            file_paths: List of tuples containing (local_path, file_info)
            expected_checksums: Optional dictionary mapping file paths to checksums

        Returns:
            List of FTPVerificationResult objects
        """
        results = []

        for local_path, file_info in file_paths:
            file_checksums = None
            if expected_checksums:
                file_checksums = expected_checksums.get(str(local_path))

            result = await self.verify_file(local_path, file_info, file_checksums)
            results.append(result)

        return results

    def get_verification_summary(
        self, results: List[FTPVerificationResult]
    ) -> Dict[str, Any]:
        """
        Generate a summary of verification results.

        Args:
            results: List of verification results

        Returns:
            Dictionary containing verification summary
        """
        total_files = len(results)
        valid_files = sum(1 for r in results if r.is_valid)
        invalid_files = total_files - valid_files

        errors = [r.error for r in results if r.error and not r.is_valid]

        return {
            "total_files": total_files,
            "valid_files": valid_files,
            "invalid_files": invalid_files,
            "success_rate": (
                (valid_files / total_files * 100) if total_files > 0 else 0.0
            ),
            "verification_method": self.config.verification_method.value,
            "errors": errors,
            "details": [
                {
                    "method": r.method.value,
                    "expected": r.expected_value,
                    "actual": r.actual_value,
                    "valid": r.is_valid,
                    "error": r.error,
                }
                for r in results
            ],
        }

    @staticmethod
    async def calculate_file_checksum(
        file_path: Path, algorithm: str = "sha256"
    ) -> str:
        """
        Calculate checksum for a file.

        Args:
            file_path: Path to the file
            algorithm: Hash algorithm to use (md5, sha256)

        Returns:
            Hexadecimal checksum string
        """
        if algorithm.lower() == "md5":
            hash_func = hashlib.md5()
        elif algorithm.lower() == "sha256":
            hash_func = hashlib.sha256()
        else:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}")

        async with aiofiles.open(file_path, "rb") as f:
            while chunk := await f.read(8192):
                hash_func.update(chunk)

        return hash_func.hexdigest().lower()

    @staticmethod
    def validate_checksum_format(checksum: str, algorithm: str) -> bool:
        """
        Validate checksum format for given algorithm.

        Args:
            checksum: Checksum string to validate
            algorithm: Hash algorithm (md5, sha256)

        Returns:
            True if format is valid, False otherwise
        """
        if not checksum or not isinstance(checksum, str):
            return False

        # Remove any whitespace and convert to lowercase
        checksum = checksum.strip().lower()

        if algorithm.lower() == "md5":
            # MD5 should be 32 hex characters
            return len(checksum) == 32 and all(
                c in "0123456789abcdef" for c in checksum
            )
        elif algorithm.lower() == "sha256":
            # SHA256 should be 64 hex characters
            return len(checksum) == 64 and all(
                c in "0123456789abcdef" for c in checksum
            )

        return False
