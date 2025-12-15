#!/bin/bash
# Script to run Home Assistant for development testing

cd "$(dirname "$0")/.."

# Activate virtual environment
source venv/bin/activate

# Run Home Assistant with our config directory
echo "🏠 Starting Home Assistant..."
echo "📍 Config directory: $(pwd)/config"
echo "🔗 Access at: http://localhost:8123"
echo ""
echo "Press Ctrl+C to stop"
echo ""

hass -c config

