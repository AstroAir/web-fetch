#!/usr/bin/env python3
"""
Simple test runner script for web-fetch project.
"""

import sys
import os
import subprocess
from pathlib import Path

def main():
    """Run tests and provide coverage report."""

    # Add the project root to Python path
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))

    print("Web-fetch Test Runner")
    print("=" * 50)

    # Check if pytest is available
    try:
        import pytest
        print(f"✓ Pytest version: {pytest.__version__}")
    except ImportError:
        print("✗ Pytest not found. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pytest", "pytest-asyncio", "pytest-cov"])
        import pytest
        print(f"✓ Pytest installed: {pytest.__version__}")

    # Check if required dependencies are available
    dependencies = [
        "aiohttp",
        "pydantic",
        "beautifulsoup4",
        "lxml"
    ]

    missing_deps = []
    for dep in dependencies:
        try:
            __import__(dep.replace("-", "_"))
            print(f"✓ {dep} available")
        except ImportError:
            missing_deps.append(dep)
            print(f"✗ {dep} missing")

    if missing_deps:
        print(f"\nInstalling missing dependencies: {', '.join(missing_deps)}")
        subprocess.run([sys.executable, "-m", "pip", "install"] + missing_deps)

    # Run tests
    print("\nRunning tests...")
    print("-" * 30)

    # Test discovery
    test_dirs = [
        "tests/test_auth",
        "tests/test_batch",
        "tests/test_cli",
        "tests/test_components",
        "tests/test_config",
        "tests/test_models",
        "tests/test_core",
        "tests/test_utils",
        "tests/test_parsers",
        "tests/test_http",
        "tests/test_ftp",
        "tests/test_graphql",
        "tests/test_websocket",
        "tests/test_monitoring",
        "tests/test_logging",
        "tests/test_managers",
        "tests/test_crawlers"
    ]

    total_tests = 0
    passed_tests = 0
    failed_tests = 0

    for test_dir in test_dirs:
        if os.path.exists(test_dir):
            print(f"\nTesting {test_dir}...")
            try:
                # Run pytest for this directory
                result = subprocess.run([
                    sys.executable, "-m", "pytest",
                    test_dir,
                    "-v",
                    "--tb=short",
                    "--no-header"
                ], capture_output=True, text=True, timeout=120)

                if result.returncode == 0:
                    print(f"✓ {test_dir} tests passed")
                    # Count tests from output
                    output_lines = result.stdout.split('\n')
                    for line in output_lines:
                        if "passed" in line and "failed" in line:
                            # Parse pytest summary line
                            parts = line.split()
                            for i, part in enumerate(parts):
                                if part == "passed":
                                    passed_tests += int(parts[i-1])
                                elif part == "failed":
                                    failed_tests += int(parts[i-1])
                else:
                    print(f"✗ {test_dir} tests failed")
                    print("Error output:")
                    print(result.stderr[:500])  # Show first 500 chars of error

            except subprocess.TimeoutExpired:
                print(f"⚠ {test_dir} tests timed out")
            except Exception as e:
                print(f"✗ Error running {test_dir} tests: {e}")
        else:
            print(f"⚠ {test_dir} not found")

    total_tests = passed_tests + failed_tests

    # Summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    print(f"Total tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")

    if failed_tests == 0 and total_tests > 0:
        print("🎉 All tests passed!")
        return 0
    elif total_tests == 0:
        print("⚠ No tests were run")
        return 1
    else:
        print(f"❌ {failed_tests} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
