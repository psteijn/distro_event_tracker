#!/bin/bash

# Check if Python is installed
if ! command -v python &> /dev/null; then
    echo "ERROR: Python is not installed or not in PATH"
    echo "Please install Python 3.7+ from https://python.org"
    read -p "Press Enter to exit..."
    exit 1
fi

echo "Python found:"
python --version

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    echo
    echo "Creating virtual environment..."
    python -m venv venv
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create virtual environment"
        read -p "Press Enter to exit..."
        exit 1
    fi
fi

# Activate virtual environment
echo
echo "Activating virtual environment..."
source venv/Scripts/activate

# Install/update dependencies
echo
echo "Installing dependencies..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies"
    read -p "Press Enter to exit..."
    exit 1
fi
