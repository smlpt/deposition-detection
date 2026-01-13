#!/bin/bash

# Check if virtual environment exists
if [ ! -f "./venv/deposition-detection/bin/activate" ]; then
    echo "Creating virtual environment..."
    
    # Use python3.10 to specify version
    python3.10 -m venv ./venv/deposition-detection
    
    if [ $? -ne 0 ]; then
        echo "Failed to create virtual environment."
        echo "We are using Python 3.10 here for compatibility reasons. Make sure it is installed on your system!"
        exit 1
    fi
    
    echo "Installing requirements..."
    echo "This might take a while"
    source ./venv/deposition-detection/bin/activate
    pip install -r requirements.txt
    
    if [ $? -ne 0 ]; then
        echo "Failed to install requirements"
        exit 1
    fi
    
    echo "Requirements successfully installed."
else
    echo "Virtual environment already exists"
fi

echo "Launching server..."
# Activate virtual environment
source ./venv/deposition-detection/bin/activate

# Run the main script
python ./src/main.py