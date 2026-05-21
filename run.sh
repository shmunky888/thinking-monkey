#!/bin/bash
# Move to the script's directory
cd "$(dirname "$0")"

# Execute the pose matcher using the correct virtual environment python
./venv/bin/python main.py
