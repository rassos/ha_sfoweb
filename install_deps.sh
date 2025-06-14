#!/bin/bash
# Installation script for SFO Enhanced Scraper dependencies

echo "Installing SFO Enhanced Scraper dependencies..."
echo "============================================="

# Check if python3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 is not installed. Please install it first:"
    echo "   sudo apt update && sudo apt install python3 python3-full python3-venv -y"
    exit 1
fi

# Install python3-venv if not available
if ! python3 -m venv --help &> /dev/null; then
    echo "Installing python3-venv..."
    sudo apt update
    sudo apt install python3-full python3-venv -y
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip in virtual environment
echo "Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "Installing Python dependencies..."
pip install -r requirements.txt

echo ""
echo "✅ Installation complete!"
echo ""
echo "To test the scraper, run:"
echo "   source venv/bin/activate"
echo "   python test_scraper.py"
echo ""
echo "Or use the run_test.sh script for convenience."
echo ""
echo "To use in Home Assistant, copy the custom_components/sfoweb folder"
echo "to your Home Assistant config/custom_components/ directory."