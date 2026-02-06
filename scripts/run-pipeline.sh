#!/bin/bash
# ============================================
# Upbit Pipeline Launcher
# ============================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Load environment variables
if [ -f .env ]; then
    echo "Loading environment from .env"
    export $(grep -v '^#' .env | xargs)
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Python version: $PYTHON_VERSION"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies if needed
if [ ! -f "venv/.installed" ]; then
    echo "Installing dependencies..."
    pip install --upgrade pip
    pip install -e ".[dev,storage]"
    touch venv/.installed
fi

# Run the pipeline
echo "Starting Upbit Pipeline..."
echo "========================================="
python -m src.main "$@"
