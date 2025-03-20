import datetime
import os
import zipfile
import shutil
import numba
from collections import defaultdict

# Path configuration
zip_file_path = "F:/tempF/telemetry_2024-01-01_allactually.zip"  # Update this path to your big zip file
telemetry_output_folder = "F:/tempF/iss_telemetry_utc"
telemetry_working_folder = "F:/tempF/iss_working/big_zip_extract"


@numba.jit(nopython=True)
def is_leap_year(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


@numba.jit
def decode_timestamp(timestamp, year):
    # Calculate day of year, hours, minutes, seconds
    day_of_year = int(timestamp // 24)
    remainder = timestamp - day_of_year * 24
    hours = int(remainder)
    remainder -= hours
    minutes = int(remainder * 60)
    seconds = (remainder * 60 - minutes) * 60

    # Check for rollover: if day_of_year exceeds max for current year, adjust the year and day_of_year
    max_day = 366 if is_leap_year(year) else 365
    if day_of_year > max_day:
        day_of_year -= max_day
        year += 1

    # Convert to Python datetime (can't use datetime directly in numba, so we return components)
    return year, day_of_year, hours, minutes, seconds


def timestamp_to_datetime(timestamp_components):
    year, day_of_year, hours, minutes, seconds = timestamp_components
    return datetime.datetime(year, 1, 1) + datetime.timedelta(
        days=day_of_year - 1, hours=hours, minutes=minutes, seconds=seconds
    )


def process_file(file_path, start_year=2024):
    """
    Process a single telemetry file, tracking year transitions
    """
    if os.path.basename(file_path) == "TIME_000001.txt":
        print(f"Skipping TIME_000001.txt file")
        return

    print(f"Processing file: {os.path.basename(file_path)}")

    # Dictionary to store lines by output path
    result_buffers = defaultdict(list)

    # Track the current year and previous day to detect year transitions
    current_year = start_year
    previous_day = None

    try:
        with open(file_path, "r") as infile:
            for line in infile:
                if not line.strip():
                    continue

                try:
                    parts = line.split()
                    ts_val = float(parts[0])
                except (ValueError, IndexError):
                    continue

                if ts_val <= 0:
                    continue

                # Decode timestamp
                timestamp_components = decode_timestamp(ts_val, current_year)
                year, day_of_year, hours, minutes, seconds = timestamp_components

                # Check for year transition (day 365/366 to day 1)
                if previous_day is not None:
                    if previous_day >= 365 and day_of_year == 1:
                        # Year transition detected, increment the year for subsequent timestamps
                        current_year += 1
                        print(
                            f"Year transition detected: {current_year-1} -> {current_year}"
                        )
                        # Recalculate with new year
                        timestamp_components = decode_timestamp(ts_val, current_year)
                        year, day_of_year, hours, minutes, seconds = (
                            timestamp_components
                        )

                previous_day = day_of_year

                # Convert to datetime
                dt = timestamp_to_datetime(timestamp_components)

                # Validate date
                now = datetime.datetime.utcnow()
                if (
                    dt > now
                    or dt.month not in range(1, 13)
                    or dt.day not in range(1, 32)
                ):
                    continue

                # Determine output path
                date_folder = os.path.join(
                    telemetry_output_folder,
                    dt.strftime("%Y"),
                    dt.strftime("%m"),
                    dt.strftime("%d"),
                )

                # if date isn't between 2024-01-01 and 2025-04-01, skip
                if dt < datetime.datetime(2024, 1, 1) or dt >= datetime.datetime(
                    2025, 4, 1
                ):
                    continue

                out_path = os.path.join(date_folder, os.path.basename(file_path))

                # Add to result buffer
                result_buffers[out_path].append(line)

        # Write all buffers to respective files
        for out_path, lines in result_buffers.items():
            date_folder = os.path.dirname(out_path)
            os.makedirs(date_folder, exist_ok=True)

            # Check if file exists and load existing content
            existing_lines = []
            if os.path.exists(out_path):
                with open(out_path, "r") as existing_file:
                    existing_lines = existing_file.readlines()

            # Combine lines
            all_lines = lines + existing_lines

            # Sort and deduplicate
            all_lines.sort()
            unique_lines = []
            seen = set()
            for line in all_lines:
                if line not in seen:
                    seen.add(line)
                    unique_lines.append(line)

            # Write to file
            with open(out_path, "w") as out_file:
                out_file.writelines(unique_lines)

            print(f"Wrote {len(unique_lines)} lines to {out_path}")

    except Exception as e:
        print(f"Error processing {file_path}: {e}")


def main():
    # Ensure working folder exists and is empty
    # if os.path.exists(telemetry_working_folder):
    #     shutil.rmtree(telemetry_working_folder)
    # os.makedirs(telemetry_working_folder, exist_ok=True)

    # print(f"Extracting {zip_file_path} to {telemetry_working_folder}")
    # with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
    #     zip_ref.extractall(telemetry_working_folder)

    # Process each txt file one at a time
    for root, dirs, files in os.walk(telemetry_working_folder):
        for file in files:
            if file.endswith(".txt"):
                file_path = os.path.join(root, file)
                process_file(file_path, start_year=2024)

    print("Processing complete")


if __name__ == "__main__":
    main()
