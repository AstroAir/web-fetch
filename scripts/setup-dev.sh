#!/bin/bash
# Development environment setup script for web-fetch

set -e

echo "🚀 Setting up web-fetch development environment..."

# Check Python version
python_version=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
required_version="3.11"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python $required_version or higher is required. Found: $python_version"
    exit 1
fi

echo "✅ Python version check passed: $python_version"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install the package in development mode with all dependencies
echo "📚 Installing web-fetch with development dependencies..."
pip install -e ".[test,dev]"

# Install pre-commit hooks
echo "🪝 Setting up pre-commit hooks..."
pre-commit install

# Run initial checks
echo "🧪 Running initial checks..."
echo "  - Linting..."
flake8 web_fetch --count --select=E9,F63,F7,F82 --show-source --statistics

echo "  - Type checking..."
mypy web_fetch --ignore-missing-imports

echo "  - Running fast tests..."
pytest -m "not slow and not integration" --tb=short

echo ""
echo "🎉 Development environment setup complete!"
echo ""
echo "To get started:"
echo "  1. Activate the virtual environment: source venv/bin/activate"
echo "  2. Run tests: make test"
echo "  3. Run linting: make lint"
echo "  4. Format code: make format"
echo "  5. See all available commands: make help"
echo ""
echo "Happy coding! 🐍"
