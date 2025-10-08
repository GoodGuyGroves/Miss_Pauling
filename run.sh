#!/usr/bin/env bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the application directory
cd "$SCRIPT_DIR"

# Activate the virtual environment
source .venv/bin/activate

# Install/update dependencies
pip install -r requirements.txt

# Run the FastAPI application
exec uvicorn main:app --host 0.0.0.0 --port 8000
