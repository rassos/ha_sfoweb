#!/bin/bash
# Convenience script to run the test with virtual environment

echo "Running SFO Enhanced Scraper Test..."
echo "==================================="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please run ./install_deps.sh first"
    exit 1
fi

# Activate virtual environment and run test
source venv/bin/activate
python test_scraper.py