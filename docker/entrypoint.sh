#!/bin/bash

# Function to forward signals to the Python process
function handle_signal {
    echo "$(date -u): Received signal, forwarding to Python process"
    kill -TERM "$child" 2>/dev/null
}

# Set up signal handlers
trap handle_signal SIGINT SIGTERM

# Start the Python script in the background
echo "$(date -u): Starting ISS Telemetry Recorder"
python src/ISS-telemetry-recorder.py &

# Store the process ID
child=$!

# Wait for process to end
wait "$child"

# Get exit status
exit_code=$?
echo "$(date -u): ISS Telemetry Recorder exited with code $exit_code"

# Exit with the same code
exit $exit_code
