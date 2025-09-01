"""
Monitoring commands for the extended CLI.

This module contains monitoring command implementations extracted from extended.py
to improve modularity and maintainability. Each monitor command handles
system monitoring and metrics collection.
"""

import sys

import click


def create_monitor_commands(monitor_group):
    """Create and register monitor commands with the monitor group."""
    
    @monitor_group.command()
    @click.option('--backend', type=click.Choice(['memory', 'console', 'prometheus']), default='memory', help='Metrics backend')
    def status(backend: str) -> None:
        """Show comprehensive monitoring status."""
        try:
            from ...monitoring import get_metrics_collector
        except ImportError:
            click.echo("✗ Monitoring functionality not available")
            sys.exit(1)

        try:
            collector = get_metrics_collector()
            stats = collector.get_summary()

            click.echo(f"Monitoring Status ({backend} backend):")
            click.echo(f"  Uptime: {stats.get('uptime_seconds', 0):.1f} seconds")
            click.echo(f"  Total requests: {stats.get('total_requests', 0)}")
            click.echo(f"  Total errors: {stats.get('total_errors', 0)}")
            click.echo(f"  Error rate: {stats.get('error_rate', 0):.1%}")
            click.echo(f"  Cache hits: {stats.get('cache_hits', 0)}")
            click.echo(f"  Cache misses: {stats.get('cache_misses', 0)}")
            click.echo(f"  Cache hit rate: {stats.get('cache_hit_rate', 0):.1%}")
            click.echo(f"  Requests per second: {stats.get('requests_per_second', 0):.2f}")
            click.echo(f"  Active warming tasks: {stats.get('active_warming_tasks', 0)}")

        except Exception as e:
            click.echo(f"✗ Error getting monitoring status: {e}")
            sys.exit(1)

    @monitor_group.command()
    def metrics() -> None:
        """Show detailed metrics information."""
        try:
            from ...monitoring import get_metrics_collector
        except ImportError:
            click.echo("✗ Monitoring functionality not available")
            sys.exit(1)

        try:
            collector = get_metrics_collector()
            metrics = collector.get_all_metrics()

            click.echo("Detailed Metrics:")
            for metric_name, metric_data in metrics.items():
                click.echo(f"  {metric_name}:")
                if isinstance(metric_data, dict):
                    for key, value in metric_data.items():
                        click.echo(f"    {key}: {value}")
                else:
                    click.echo(f"    Value: {metric_data}")

        except Exception as e:
            click.echo(f"✗ Error getting metrics: {e}")
            sys.exit(1)

    @monitor_group.command()
    def health() -> None:
        """Perform health check on all systems."""
        try:
            from ...monitoring import get_health_checker
        except ImportError:
            click.echo("✗ Health check functionality not available")
            sys.exit(1)

        try:
            health_checker = get_health_checker()
            health_status = health_checker.check_all()

            click.echo("System Health Check:")
            overall_healthy = True
            
            for component, status in health_status.items():
                status_icon = "✓" if status.get('healthy', False) else "✗"
                click.echo(f"  {status_icon} {component}: {status.get('message', 'Unknown')}")
                if not status.get('healthy', False):
                    overall_healthy = False

            if overall_healthy:
                click.echo("\n✓ All systems healthy")
            else:
                click.echo("\n✗ Some systems are unhealthy")
                sys.exit(1)

        except Exception as e:
            click.echo(f"✗ Error performing health check: {e}")
            sys.exit(1)

    return monitor_group
