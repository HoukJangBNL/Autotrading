#!/bin/bash

# Setup script for Schwab Automated Trading System

set -e

echo "🚀 Setting up Schwab Automated Trading System..."

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_VERSION="3.10"

if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)"; then
    echo "❌ Python 3.10+ is required. Current version: $PYTHON_VERSION"
    exit 1
fi

echo "✅ Python version: $PYTHON_VERSION"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
else
    echo "📦 Virtual environment already exists"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements-dev.txt

# Create necessary directories
echo "📁 Creating project directories..."
mkdir -p logs data config

# Copy environment file
if [ ! -f ".env" ]; then
    echo "⚙️  Creating .env file..."
    cp .env.example .env
    echo "⚠️  Please update .env with your Schwab API credentials"
else
    echo "⚙️  .env file already exists"
fi

# Initialize database
echo "🗄️  Initializing database..."
alembic upgrade head

# Install pre-commit hooks
echo "🪝 Installing pre-commit hooks..."
pre-commit install

# Run initial tests
echo "🧪 Running tests..."
pytest tests/ -v

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Update .env with your Schwab API credentials"
echo "2. Run 'source venv/bin/activate' to activate the virtual environment"
echo "3. Run 'python -m src.main' to start the trading system"
echo "4. Run 'docker-compose up' to start with Docker"