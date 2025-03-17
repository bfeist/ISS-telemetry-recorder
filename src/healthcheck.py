#!/usr/bin/env python3
import os
import sys
import time
import datetime
import glob


def get_log_timestamp():
    return datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def main():
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
