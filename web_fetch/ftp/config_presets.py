"""
Performance-tuned configuration presets for different FTP use cases.

This module provides optimized configuration presets for various scenarios
including high-throughput, low-latency, and memory-constrained environments.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

from .models import FTPConfig, FTPTransferMode, FTPVerificationMethod
from .circuit_breaker import CircuitBreakerConfig
from .retry import RetryConfig, RetryStrategy


class UseCase(Enum):
    """Different use cases for FTP operations."""
    HIGH_THROUGHPUT = "high_throughput"
    LOW_LATENCY = "low_latency"
    MEMORY_CONSTRAINED = "memory_constrained"
    RELIABLE_TRANSFER = "reliable_transfer"
    BULK_DOWNLOAD = "bulk_download"
    REAL_TIME = "real_time"
    MOBILE_NETWORK = "mobile_network"
    SATELLITE_LINK = "satellite_link"


@dataclass
class OptimizedPreset:
    """Complete optimized configuration preset."""
    
    name: str
    description: str
    ftp_config: FTPConfig
    circuit_breaker_config: Optional[CircuitBreakerConfig] = None
    retry_config: Optional[RetryConfig] = None
    recommended_scenarios: list[str] = None


class FTPConfigPresets:
    """
    Factory for creating performance-tuned FTP configuration presets.
    
    Provides optimized configurations for different use cases and network conditions.
    """
    
    @staticmethod
    def high_throughput() -> OptimizedPreset:
        """
        Configuration optimized for maximum throughput.
        
        Best for: Large file transfers on high-bandwidth connections
        Trade-offs: Higher memory usage, more aggressive connection pooling
        """
        ftp_config = FTPConfig(
            # Connection settings - aggressive for throughput
            connection_timeout=60.0,
            data_timeout=600.0,
            keepalive_interval=30.0,
            
            # Performance settings - optimized for speed
            max_concurrent_downloads=10,
            max_connections_per_host=8,
            enable_parallel_downloads=True,
            
            # Advanced performance tuning
            adaptive_chunk_size=True,
            connection_health_check=True,
            adaptive_cleanup_interval=True,
            performance_monitoring=True,
            
            # File handling - large chunks for throughput
            chunk_size=1024 * 1024,  # 1MB chunks
            buffer_size=2 * 1024 * 1024,  # 2MB buffer
            min_chunk_size=256 * 1024,  # 256KB min
            max_chunk_size=4 * 1024 * 1024,  # 4MB max
            
            # Verification - size only for speed
            verification_method=FTPVerificationMethod.SIZE,
            enable_resume=True,
            
            # Transfer mode
            transfer_mode=FTPTransferMode.BINARY,
        )
        
        circuit_breaker_config = CircuitBreakerConfig(
            failure_threshold=8,
            recovery_timeout=30.0,
            success_threshold=5,
            timeout=120.0,
        )
        
        retry_config = RetryConfig(
            max_attempts=5,
            base_delay=0.5,
            max_delay=30.0,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            progressive_timeout=True,
            base_timeout=60.0,
            max_timeout=300.0,
        )
        
        return OptimizedPreset(
            name="High Throughput",
            description="Optimized for maximum transfer speed on high-bandwidth connections",
            ftp_config=ftp_config,
            circuit_breaker_config=circuit_breaker_config,
            retry_config=retry_config,
            recommended_scenarios=[
                "Data center to data center transfers",
                "Bulk file synchronization",
                "High-bandwidth dedicated connections",
                "Large media file transfers"
            ]
        )
    
    @staticmethod
    def low_latency() -> OptimizedPreset:
        """
        Configuration optimized for low latency and quick response.
        
        Best for: Interactive applications, small file transfers
        Trade-offs: May sacrifice some throughput for responsiveness
        """
        ftp_config = FTPConfig(
            # Connection settings - quick timeouts
            connection_timeout=15.0,
            data_timeout=60.0,
            keepalive_interval=15.0,
            
            # Performance settings - moderate concurrency
            max_concurrent_downloads=5,
            max_connections_per_host=4,
            enable_parallel_downloads=True,
            
            # Advanced performance tuning
            adaptive_chunk_size=True,
            connection_health_check=True,
            adaptive_cleanup_interval=True,
            performance_monitoring=True,
            
            # File handling - smaller chunks for responsiveness
            chunk_size=64 * 1024,  # 64KB chunks
            buffer_size=256 * 1024,  # 256KB buffer
            min_chunk_size=16 * 1024,  # 16KB min
            max_chunk_size=512 * 1024,  # 512KB max
            
            # Verification - size only for speed
            verification_method=FTPVerificationMethod.SIZE,
            enable_resume=True,
            
            # Transfer mode
            transfer_mode=FTPTransferMode.BINARY,
        )
        
        circuit_breaker_config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=15.0,
            success_threshold=2,
            timeout=30.0,
        )
        
        retry_config = RetryConfig(
            max_attempts=3,
            base_delay=0.2,
            max_delay=5.0,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            progressive_timeout=False,
            base_timeout=15.0,
        )
        
        return OptimizedPreset(
            name="Low Latency",
            description="Optimized for quick response times and interactive use",
            ftp_config=ftp_config,
            circuit_breaker_config=circuit_breaker_config,
            retry_config=retry_config,
            recommended_scenarios=[
                "Interactive file browsers",
                "Real-time applications",
                "Small file transfers",
                "API-driven file operations"
            ]
        )
    
    @staticmethod
    def memory_constrained() -> OptimizedPreset:
        """
        Configuration optimized for minimal memory usage.
        
        Best for: Resource-constrained environments, embedded systems
        Trade-offs: Lower throughput and concurrency for memory efficiency
        """
        ftp_config = FTPConfig(
            # Connection settings - conservative
            connection_timeout=30.0,
            data_timeout=300.0,
            keepalive_interval=60.0,
            
            # Performance settings - minimal concurrency
            max_concurrent_downloads=2,
            max_connections_per_host=2,
            enable_parallel_downloads=False,
            
            # Advanced performance tuning
            adaptive_chunk_size=False,  # Fixed size to avoid overhead
            connection_health_check=False,  # Reduce overhead
            adaptive_cleanup_interval=False,
            performance_monitoring=False,  # Reduce memory overhead
            
            # File handling - small chunks for memory efficiency
            chunk_size=16 * 1024,  # 16KB chunks
            buffer_size=32 * 1024,  # 32KB buffer
            min_chunk_size=8 * 1024,  # 8KB min
            max_chunk_size=64 * 1024,  # 64KB max
            
            # Verification - none to save memory
            verification_method=FTPVerificationMethod.NONE,
            enable_resume=True,
            
            # Transfer mode
            transfer_mode=FTPTransferMode.BINARY,
        )
        
        circuit_breaker_config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=60.0,
            success_threshold=2,
            timeout=60.0,
        )
        
        retry_config = RetryConfig(
            max_attempts=2,
            base_delay=1.0,
            max_delay=10.0,
            strategy=RetryStrategy.FIXED_DELAY,
            progressive_timeout=False,
            base_timeout=30.0,
        )
        
        return OptimizedPreset(
            name="Memory Constrained",
            description="Optimized for minimal memory usage in resource-constrained environments",
            ftp_config=ftp_config,
            circuit_breaker_config=circuit_breaker_config,
            retry_config=retry_config,
            recommended_scenarios=[
                "Embedded systems",
                "IoT devices",
                "Containers with memory limits",
                "Shared hosting environments"
            ]
        )
    
    @staticmethod
    def reliable_transfer() -> OptimizedPreset:
        """
        Configuration optimized for maximum reliability and data integrity.
        
        Best for: Critical data transfers, compliance requirements
        Trade-offs: Slower transfers due to extensive verification and retry logic
        """
        ftp_config = FTPConfig(
            # Connection settings - generous timeouts
            connection_timeout=120.0,
            data_timeout=1800.0,  # 30 minutes
            keepalive_interval=60.0,
            
            # Performance settings - moderate concurrency
            max_concurrent_downloads=3,
            max_connections_per_host=3,
            enable_parallel_downloads=True,
            
            # Advanced performance tuning
            adaptive_chunk_size=True,
            connection_health_check=True,
            adaptive_cleanup_interval=True,
            performance_monitoring=True,
            
            # File handling - moderate chunks with verification
            chunk_size=256 * 1024,  # 256KB chunks
            buffer_size=512 * 1024,  # 512KB buffer
            min_chunk_size=64 * 1024,  # 64KB min
            max_chunk_size=1024 * 1024,  # 1MB max
            
            # Verification - full hash verification
            verification_method=FTPVerificationMethod.SHA256,
            enable_resume=True,
            
            # Transfer mode
            transfer_mode=FTPTransferMode.BINARY,
            
            # Retry settings - aggressive retries
            max_retries=10,
            retry_delay=5.0,
            retry_backoff_factor=1.5,
        )
        
        circuit_breaker_config = CircuitBreakerConfig(
            failure_threshold=10,
            recovery_timeout=120.0,
            success_threshold=5,
            timeout=300.0,
            count_authentication_errors=False,
            count_not_found_errors=False,
        )
        
        retry_config = RetryConfig(
            max_attempts=10,
            base_delay=2.0,
            max_delay=120.0,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            progressive_timeout=True,
            base_timeout=120.0,
            max_timeout=600.0,
        )
        
        return OptimizedPreset(
            name="Reliable Transfer",
            description="Optimized for maximum reliability and data integrity",
            ftp_config=ftp_config,
            circuit_breaker_config=circuit_breaker_config,
            retry_config=retry_config,
            recommended_scenarios=[
                "Financial data transfers",
                "Medical records",
                "Legal document exchange",
                "Backup operations",
                "Compliance-critical transfers"
            ]
        )
    
    @staticmethod
    def get_preset(use_case: UseCase) -> OptimizedPreset:
        """Get a preset configuration for a specific use case."""
        preset_map = {
            UseCase.HIGH_THROUGHPUT: FTPConfigPresets.high_throughput,
            UseCase.LOW_LATENCY: FTPConfigPresets.low_latency,
            UseCase.MEMORY_CONSTRAINED: FTPConfigPresets.memory_constrained,
            UseCase.RELIABLE_TRANSFER: FTPConfigPresets.reliable_transfer,
            UseCase.BULK_DOWNLOAD: FTPConfigPresets.high_throughput,  # Alias
            UseCase.REAL_TIME: FTPConfigPresets.low_latency,  # Alias
            UseCase.MOBILE_NETWORK: FTPConfigPresets.memory_constrained,  # Conservative for mobile
            UseCase.SATELLITE_LINK: FTPConfigPresets.reliable_transfer,  # High latency, need reliability
        }
        
        preset_func = preset_map.get(use_case)
        if preset_func:
            return preset_func()
        else:
            # Default to balanced configuration
            return FTPConfigPresets.low_latency()
    
    @staticmethod
    def list_presets() -> Dict[str, str]:
        """List all available presets with descriptions."""
        return {
            "high_throughput": "Maximum transfer speed on high-bandwidth connections",
            "low_latency": "Quick response times and interactive use",
            "memory_constrained": "Minimal memory usage for resource-constrained environments",
            "reliable_transfer": "Maximum reliability and data integrity",
        }
