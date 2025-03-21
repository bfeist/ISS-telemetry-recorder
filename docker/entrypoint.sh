#!/bin/bash

echo "$(date -u): Starting ISS Telemetry Recorder"

# Use exec to replace the shell process with the Python process
# This ensures the Python process receives signals directly
exec python src/ISS-telemetry-recorder.py
