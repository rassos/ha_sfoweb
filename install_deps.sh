#!/bin/bash
# Installation script for SFO Enhanced Scraper dependencies

echo "Installing SFO Enhanced Scraper dependencies..."
echo "============================================="

# Check if python3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 is not installed. Please install it first:"
    echo "   sudo apt update && sudo apt install python3 python3-pip -y"
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "Installing pip3..."
    sudo apt update
    sudo apt install python3-pip -y
fi

# Install requirements
echo "Installing Python dependencies..."
pip3 install --user -r requirements.txt

echo ""
echo "✅ Installation complete!"
echo ""
echo "To test the scraper, run:"
echo "   python3 test_scraper.py"
echo ""
echo "To use in Home Assistant, copy the custom_components/sfoweb folder"
echo "to your Home Assistant config/custom_components/ directory."