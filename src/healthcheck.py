#!/usr/bin/env python3
"""Check recorder liveness, not whether the upstream stream has data."""
import os
import sys
import time


def main():
    ready_file = os.path.join(os.environ.get("RAW_FOLDER", "/data"), ".ready")
    try:
        age = time.time() - os.path.getmtime(ready_file)
    except OSError as exc:
        print(f"Recorder heartbeat unavailable: {exc}")
        return 1
    # Allow small filesystem/clock rounding differences on fresh writes.
    if not -5 <= age < 120:
        print(f"Recorder heartbeat is stale ({age:.0f}s old)")
        return 1
    print(f"Recorder loop is alive (heartbeat {age:.0f}s old)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
