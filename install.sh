#!/usr/bin/env bash
# Generated from design/utils_onboarding.md v1.0

set -e

echo "🦞 ClawBrain Installation & Auto-Setup"
echo "========================================"

# 1. OS & Architecture Detection
OS_TYPE=$(uname -s)
ARCH=$(uname -m)
echo "🔎 Detected OS: $OS_TYPE ($ARCH)"

# 2. Python Verification
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed. Please install Python 3.10+."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "🔎 Detected Python: $PYTHON_VERSION"

# 3. Virtual Environment Setup
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
else
    echo "✅ Virtual environment already exists."
fi

echo "🚀 Activating venv and installing dependencies..."
source venv/bin/activate

# Upgrade pip
pip install --quiet --upgrade pip

# Install dependencies
pip install --quiet -r requirements.txt

# 4. Environment Discovery (Setup Scout)
echo ""
PYTHONPATH=. python3 src/utils/setup_scout.py

# 5. Diagnostic Run
echo ""
PYTHONPATH=. python3 src/utils/doctor.py

echo ""
echo "✨ Installation complete!"
echo "----------------------------------------"
echo "To verify the installation:"
echo "  ./run_regression.sh"
echo ""
echo "To start the ClawBrain server:"
echo "  1. source venv/bin/activate"
echo "  2. python3 -m uvicorn src.main:app --host 0.0.0.0 --port 11435"
echo "----------------------------------------"
