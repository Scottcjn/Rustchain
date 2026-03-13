#!/bin/bash

# RustChain Beacon Dashboard Installation Script
# Version: 1.1

set -e

echo "🔍 RustChain Beacon Dashboard v1.1 Installer"
echo "==========================================="
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1)
if [ "$PYTHON_VERSION" -lt 3 ]; then
    echo "❌ Python 3.8+ is required."
    exit 1
fi

echo "✅ Python $(python3 --version) detected"
echo ""

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements-beacon-dashboard.txt

# Create directories
echo "📁 Creating directories..."
mkdir -p config data logs

# Make dashboard executable
chmod +x beacon_dashboard_v1.1.py

echo ""
echo "✅ Installation complete!"
echo ""
echo "To start the dashboard:"
echo "  source venv/bin/activate"
echo "  python beacon_dashboard_v1.1.py"
echo ""
echo "Or use Docker:"
echo "  docker-compose -f docker-compose.beacon-dashboard.yml up -d"
echo ""
