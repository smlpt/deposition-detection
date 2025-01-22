#!/bin/bash

# Check if virtual environment exists
if [ ! -d "./venv/deposition-detection" ]; then
    echo "Creating virtual environment..."
    python3 -m venv ./venv/deposition-detection
    
    echo "Installing requirements..."
    echo "This might take a while"
    source ./venv/deposition-detection/bin/activate
    pip install -r requirements.txt
    echo "Requirements successfully installed."
else
    echo "Virtual environment already exists"
fi

echo "Launching server..."
# Activate virtual environment
source ./venv/deposition-detection/bin/activate
# Run the main script
python ./src/main.py