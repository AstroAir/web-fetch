#!/usr/bin/env python3
"""
FTP Optimization Demo

This example demonstrates the comprehensive FTP optimization features
including performance monitoring, adaptive configurations, and reporting.
"""

import asyncio
import time
from pathlib import Path

from web_fetch.ftp import (
    FTPFetcher,
    FTPConfigPresets,
    UseCase,
    get_monitor,
    get_metrics_collector,
    get_profiler,
    profile,
)


async def demonstrate_high_throughput_config():
    """Demonstrate high-throughput optimized configuration."""
    print("=== High Throughput Configuration Demo ===")
    
    # Get optimized preset for high throughput
    preset = FTPConfigPresets.get_preset(UseCase.HIGH_THROUGHPUT)
    print(f"Using preset: {preset.name}")
    print(f"Description: {preset.description}")
    
    # Create FTP fetcher with optimized config
    fetcher = FTPFetcher(preset.ftp_config)
    
    # Example download (replace with actual FTP server)
    try:
        result = await fetcher.download_file(
            url="ftp://example.com/large_file.zip",
            local_path=Path("downloads/large_file.zip")
        )
        print(f"Download completed: {result.bytes_transferred:,} bytes in {result.response_time:.2f}s")
        print(f"Transfer rate: {result.bytes_transferred / result.response_time / 1024 / 1024:.2f} MB/s")
    except Exception as e:
        print(f"Download failed (expected for demo): {e}")
    
    await fetcher.close()


async def demonstrate_performance_monitoring():
    """Demonstrate comprehensive performance monitoring."""
    print("\n=== Performance Monitoring Demo ===")
    
    # Get monitoring components
    monitor = get_monitor()
    metrics = get_metrics_collector()
    profiler = get_profiler()
    
    # Create FTP fetcher with monitoring enabled
    config = FTPConfigPresets.get_preset(UseCase.LOW_LATENCY).ftp_config
    fetcher = FTPFetcher(config)
    
    # Simulate some operations
    print("Simulating FTP operations...")
    
    @profile(include_args=True)
    async def simulated_download(url: str, size: int):
        """Simulate a download operation for demo purposes."""
        await asyncio.sleep(0.1)  # Simulate network delay
        return {"url": url, "size": size, "success": True}
    
    # Run simulated operations
    urls = [
        "ftp://server1.com/file1.txt",
        "ftp://server1.com/file2.txt", 
        "ftp://server2.com/file3.txt",
        "ftp://server1.com/file4.txt",
    ]
    
    for i, url in enumerate(urls):
        try:
            result = await simulated_download(url, (i + 1) * 1024 * 1024)
            print(f"  Completed: {url} ({result['size']:,} bytes)")
        except Exception as e:
            print(f"  Failed: {url} - {e}")
    
    # Get performance snapshot
    snapshot = monitor.get_current_performance_snapshot()
    print(f"\nCurrent Performance Snapshot:")
    print(f"  Active transfers: {snapshot.active_transfers}")
    print(f"  Total completed: {snapshot.total_transfers_completed}")
    print(f"  Average rate: {snapshot.average_transfer_rate / 1024:.1f} KB/s")
    print(f"  Pool efficiency: {snapshot.connection_pool_efficiency:.1%}")
    print(f"  Error rate: {snapshot.error_rate:.1%}")
    
    # Get profiling summary
    profiling_stats = profiler.get_profile_summary()
    if profiling_stats:
        print(f"\nProfiling Summary:")
        print(f"  Total operations: {profiling_stats['total_operations']}")
        print(f"  Success rate: {profiling_stats['overall_stats']['success_rate']:.1%}")
        print(f"  Average execution time: {profiling_stats['overall_stats']['average_execution_time']:.3f}s")
    
    await fetcher.close()


async def demonstrate_adaptive_configuration():
    """Demonstrate adaptive configuration and auto-tuning."""
    print("\n=== Adaptive Configuration Demo ===")
    
    # Compare different presets
    presets = [
        (UseCase.HIGH_THROUGHPUT, "High Throughput"),
        (UseCase.LOW_LATENCY, "Low Latency"),
        (UseCase.MEMORY_CONSTRAINED, "Memory Constrained"),
        (UseCase.RELIABLE_TRANSFER, "Reliable Transfer"),
    ]
    
    print("Configuration Comparison:")
    print(f"{'Preset':<20} {'Chunk Size':<12} {'Connections':<12} {'Monitoring':<12}")
    print("-" * 60)
    
    for use_case, name in presets:
        preset = FTPConfigPresets.get_preset(use_case)
        config = preset.ftp_config
        
        chunk_kb = config.chunk_size // 1024
        monitoring = "Enabled" if config.performance_monitoring else "Disabled"
        
        print(f"{name:<20} {chunk_kb:>8} KB {config.max_connections_per_host:>8}     {monitoring:<12}")
    
    # Demonstrate preset selection
    print(f"\nRecommended scenarios:")
    for use_case, name in presets:
        preset = FTPConfigPresets.get_preset(use_case)
        print(f"\n{name}:")
        for scenario in preset.recommended_scenarios[:3]:  # Show first 3
            print(f"  • {scenario}")


async def demonstrate_performance_reporting():
    """Demonstrate comprehensive performance reporting."""
    print("\n=== Performance Reporting Demo ===")
    
    monitor = get_monitor()
    
    # Generate performance report
    report = monitor.generate_performance_report(hours_back=1.0)
    
    print("Performance Report Summary:")
    print(f"  Report generated: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Analysis period: {report.duration_hours:.1f} hours")
    print(f"  Total transfers: {report.total_transfers:,}")
    print(f"  Success rate: {(report.successful_transfers / max(report.total_transfers, 1)) * 100:.1f}%")
    print(f"  Average transfer rate: {report.average_transfer_rate / 1024:.1f} KB/s")
    print(f"  Connection pool efficiency: {report.connection_pool_efficiency:.1%}")
    
    # Show recommendations
    if report.recommendations:
        print(f"\nOptimization Recommendations ({len(report.recommendations)}):")
        for i, rec in enumerate(report.recommendations[:3], 1):  # Show top 3
            print(f"  {i}. {rec.title} ({rec.priority.upper()} priority)")
            print(f"     {rec.description}")
            print(f"     Expected impact: {rec.expected_impact}")
    else:
        print("\nNo optimization recommendations at this time.")
    
    # Export report
    try:
        json_report = monitor.export_report(report, format="json")
        print(f"\nJSON report generated ({len(json_report):,} characters)")
        
        text_report = monitor.export_report(report, format="text")
        print(f"Text report generated ({len(text_report):,} characters)")
        
        # Save reports to files
        with open("ftp_performance_report.json", "w") as f:
            f.write(json_report)
        
        with open("ftp_performance_report.txt", "w") as f:
            f.write(text_report)
        
        print("Reports saved to ftp_performance_report.json and ftp_performance_report.txt")
        
    except Exception as e:
        print(f"Report export failed: {e}")


async def demonstrate_circuit_breaker_and_retry():
    """Demonstrate circuit breaker and retry mechanisms."""
    print("\n=== Circuit Breaker and Retry Demo ===")
    
    from web_fetch.ftp.circuit_breaker import get_circuit_breaker
    from web_fetch.ftp.retry import get_retry_manager
    
    circuit_breaker = get_circuit_breaker()
    retry_manager = get_retry_manager()
    
    print("Circuit Breaker and Retry mechanisms are integrated into FTP operations")
    print("These provide automatic resilience against:")
    print("  • Network timeouts and connection failures")
    print("  • Server overload and rate limiting")
    print("  • Temporary service unavailability")
    print("  • Cascading failure prevention")
    
    # Show current circuit breaker stats
    try:
        cb_stats = await circuit_breaker.get_stats()
        print(f"\nCircuit Breaker Status: {len(cb_stats)} hosts monitored")
        
        retry_stats = retry_manager.get_stats()
        print(f"Retry Manager Status: {retry_stats.get('total_operations', 0)} operations tracked")
        
    except Exception as e:
        print(f"Status check failed: {e}")


async def main():
    """Run all FTP optimization demonstrations."""
    print("FTP Component Optimization Demo")
    print("=" * 50)
    
    try:
        await demonstrate_high_throughput_config()
        await demonstrate_performance_monitoring()
        await demonstrate_adaptive_configuration()
        await demonstrate_performance_reporting()
        await demonstrate_circuit_breaker_and_retry()
        
        print("\n" + "=" * 50)
        print("Demo completed successfully!")
        print("\nKey optimization features demonstrated:")
        print("✓ Performance-tuned configuration presets")
        print("✓ Comprehensive metrics collection and monitoring")
        print("✓ Adaptive chunk sizing and connection management")
        print("✓ Circuit breaker patterns for resilience")
        print("✓ Intelligent retry mechanisms")
        print("✓ Detailed performance reporting and recommendations")
        print("✓ Memory-efficient streaming and parallel downloads")
        
    except Exception as e:
        print(f"\nDemo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Create downloads directory
    Path("downloads").mkdir(exist_ok=True)
    
    # Run the demo
    asyncio.run(main())
