#!/usr/bin/env python3
import os
import sys
import time
import datetime
import glob
import subprocess


def get_log_timestamp():
    return datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def main():
    # Check if the .ready file exists and is recent
    ready_file = "/data/.ready"
    if os.path.exists(ready_file):
        mod_time = os.path.getmtime(ready_file)
        if time.time() - mod_time < 600:  # 10 minutes
            print(f"[{get_log_timestamp()}] Ready file is recent, process is alive")
            sys.exit(0)
        else:
            print(f"[{get_log_timestamp()}] Ready file is too old")
    else:
        print(f"[{get_log_timestamp()}] Ready file does not exist")

    # Check if the Python process is running
    try:
        result = subprocess.run(
            ["pgrep", "-f", "python.*ISS-telemetry-recorder.py"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(
                f"[{get_log_timestamp()}] Process is running: {result.stdout.strip()}"
            )
            # Create/update the ready file since the process is running
            with open(ready_file, "w") as f:
                f.write(f"Process running at {get_log_timestamp()}\n")
            sys.exit(0)
        else:
            print(f"[{get_log_timestamp()}] Process not found: {result.stderr.strip()}")
    except Exception as e:
        print(f"[{get_log_timestamp()}] Error checking process: {e}")

    # Check if the data directory exists
    data_dir = "/data/iss_telemetry"
    if not os.path.exists(data_dir):
        print(
            f"[{get_log_timestamp()}] ERROR: Data directory {data_dir} does not exist"
        )
        sys.exit(1)

    # Get current date in UTC
    utc_now = datetime.datetime.utcnow()
    year = utc_now.strftime("%Y")
    month = utc_now.strftime("%m")
    day = utc_now.strftime("%d")

    # Check if the current date directory exists
    date_dir = os.path.join(data_dir, year, month, day)
    if not os.path.exists(date_dir):
        print(
            f"[{get_log_timestamp()}] WARNING: Today's data directory {date_dir} does not exist"
        )
        # Not fatal - might be just starting up

    # Check if any data files were modified in the past 15 minutes
    recent_activity = False
    now = time.time()
    cutoff = now - (15 * 60)  # 15 minutes ago

    # Check for recent master.log updates (if it exists)
    master_log = os.path.join(date_dir, "master.log")
    if os.path.exists(master_log):
        if os.path.getmtime(master_log) > cutoff:
            recent_activity = True

    # If no recent activity in today's folder, check for any data files
    if not recent_activity:
        # Check if any telemetry files exist in the date directory
        data_files = glob.glob(os.path.join(date_dir, "*.txt"))
        if data_files:
            # Check if any were modified recently
            for file in data_files:
                if os.path.getmtime(file) > cutoff:
                    recent_activity = True
                    break

    if not recent_activity:
        print(f"[{get_log_timestamp()}] ERROR: No recent activity detected in the logs")
        sys.exit(1)

    print(f"[{get_log_timestamp()}] Healthcheck passed - recent activity detected")
    sys.exit(0)


if __name__ == "__main__":
    main()
