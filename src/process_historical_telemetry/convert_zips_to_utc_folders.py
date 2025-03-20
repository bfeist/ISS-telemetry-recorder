import datetime
import os
import zipfile
import glob
import shutil
import numba
import concurrent.futures
from collections import defaultdict
import platform
import psutil

# This script converts the zipped folders of historical telemetry provided by the ISSMimic team into UTC dated folders of txt files per field name
# The script also ensure time-based sorting, discards invalid timestamps, and deduplicates the data

telemetry_input_folder = "F:/tempF/ISS_Telemetry_Archive"
telemetry_output_folder = "F:/tempF/iss_telemetry_utc"
telemetry_working_folder = "F:/tempF/iss_working/current_telemetry_zip"
processed_zip_list = "F:/tempF/iss_working/processed_zips.txt"


# Helper function to get date-based directory path
def get_date_directory():
    # Create date-based directory structure using UTC date
    utc_now = datetime.datetime.utcnow()
    year = utc_now.strftime("%Y")
    month = utc_now.strftime("%m")
    day = utc_now.strftime("%d")

    # Create path: output_folder/year/month/day
    date_dir = os.path.join(telemetry_output_folder, year, month, day)
    os.makedirs(date_dir, exist_ok=True)

    return date_dir


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


def process_file(args):
    file, root, zip_year, zip_month, zip_day, decoded_timestamps_cache = args
    if file == "TIME_000001.txt":
        return None

    result_buffers = defaultdict(list)
    txt_path = os.path.join(root, file)

    try:
        with open(txt_path, "r") as infile:
            lines = infile.readlines()

        now = datetime.datetime.utcnow()
        zip_date = datetime.date(zip_year, zip_month, zip_day)
        one_day = datetime.timedelta(days=1)

        for line in lines:
            if not line.strip():
                continue
            try:
                ts_val = float(line.split()[0])
            except ValueError:
                continue

            if ts_val in decoded_timestamps_cache:
                dt = decoded_timestamps_cache[ts_val]
            else:
                timestamp_components = decode_timestamp(ts_val, zip_year)
                dt = timestamp_to_datetime(timestamp_components)

                # account for rollover between December and January
                if zip_month == 12 and dt.month == 1:
                    timestamp_components = decode_timestamp(ts_val, zip_year + 1)
                    dt = timestamp_to_datetime(timestamp_components)
                decoded_timestamps_cache[ts_val] = dt

            # Check dt against zip file's date (allowing one day difference for timezone shifts)
            if dt.date() not in (zip_date, zip_date + one_day, zip_date - one_day):
                continue

            if dt > now or dt.month not in range(1, 13) or dt.day not in range(1, 32):
                continue

            date_folder = os.path.join(
                telemetry_output_folder,
                dt.strftime("%Y"),
                dt.strftime("%m"),
                dt.strftime("%d"),
            )
            out_path = os.path.join(date_folder, file)
            result_buffers[out_path].append(line)

        return file, result_buffers
    except Exception as e:
        print(f"Error processing {file}: {e}")
        return None


def set_low_priority():
    """Set the current process to low priority (nice)"""
    current_process = psutil.Process(os.getpid())

    # Different priority settings based on platform
    if platform.system() == "Windows":
        # Windows: BELOW_NORMAL_PRIORITY_CLASS
        import ctypes

        ctypes.windll.kernel32.SetPriorityClass(
            ctypes.windll.kernel32.GetCurrentProcess(),
            0x00004000,  # BELOW_NORMAL_PRIORITY_CLASS
        )
    else:
        # Unix-like systems: nice value
        current_process.nice(10)  # Higher nice value = lower priority


def main():
    # Ensure working folder exists
    if not os.path.exists(telemetry_working_folder):
        os.makedirs(telemetry_working_folder, exist_ok=True)

    # Read list of processed zips
    processed_set = set()
    if os.path.exists(processed_zip_list):
        with open(processed_zip_list, "r") as f:
            processed_set = set(line.strip() for line in f if line.strip())

    # recursively find all zip files in the input folder using glob for nested structure
    zip_pattern = os.path.join(telemetry_input_folder, "**", "*.zip")
    zip_files = glob.glob(zip_pattern, recursive=True)

    for zip_file in zip_files:
        if zip_file in processed_set:
            print(f"Skipping processed zip: {zip_file}")
            continue
        # Print the zip being processed
        print(f"Processing zip: {zip_file}")

        # clear the working folder using shutil.rmtree
        if os.path.exists(telemetry_working_folder):
            shutil.rmtree(telemetry_working_folder)
        os.makedirs(telemetry_working_folder, exist_ok=True)

        # extract the zip file to the working folder
        with zipfile.ZipFile(zip_file, "r") as zip_ref:
            zip_ref.extractall(telemetry_working_folder)

        # get the year from the zip file name telemetry_2018-09-18_23_59.zip
        date = os.path.basename(zip_file).split("_")[1]
        zip_year = int(date.split("-")[0])
        zip_month = int(date.split("-")[1])
        zip_day = int(date.split("-")[2])

        # Initialize cache and current time once per zip file
        decoded_timestamps_cache = {}

        # Collect all files first
        files_to_process = []
        for root, dirs, files in os.walk(telemetry_working_folder):
            for file in files:
                if file.endswith(".txt") and file != "TIME_000001.txt":
                    files_to_process.append(
                        (
                            file,
                            root,
                            zip_year,
                            zip_month,
                            zip_day,
                            decoded_timestamps_cache,
                        )
                    )

        # Process files in parallel
        all_buffers = defaultdict(list)
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=16, initializer=set_low_priority
        ) as executor:
            for result in executor.map(process_file, files_to_process):
                if result:
                    file, result_buffers = result
                    # print(f"Completed processing: {file}")
                    for out_path, lines in result_buffers.items():
                        all_buffers[out_path].extend(lines)

        # Process all buffers
        buffer_count = len(all_buffers)
        for i, (out_path, lines) in enumerate(all_buffers.items(), 1):
            file = os.path.basename(out_path)
            print(
                f"Processing file: {file} [{i}/{buffer_count}] preparing...\033[K",
                end="\r",
                flush=True,
            )

            date_folder = os.path.dirname(out_path)
            os.makedirs(date_folder, exist_ok=True)

            # Load existing contents if file exists
            if os.path.exists(out_path):
                print(
                    f"Processing file: {file} [{i}/{buffer_count}] loading existing...\033[K",
                    end="\r",
                    flush=True,
                )
                with open(out_path, "r") as existing_file:
                    existing_lines = existing_file.readlines()
                lines.extend(existing_lines)

            # Efficient sorting and deduplication
            print(
                f"Processing file: {file} [{i}/{buffer_count}] sorting...\033[K",
                end="\r",
                flush=True,
            )
            lines.sort()

            print(
                f"Processing file: {file} [{i}/{buffer_count}] deduping...\033[K",
                end="\r",
                flush=True,
            )
            unique_lines = []
            seen = set()
            for line in lines:
                if line not in seen:
                    seen.add(line)
                    unique_lines.append(line)

            print(
                f"Processing file: {file} [{i}/{buffer_count}] writing...\033[K",
                end="\r",
                flush=True,
            )
            with open(out_path, "w") as out_file:
                out_file.writelines(unique_lines)

        # After processing, mark the zip as processed
        with open(processed_zip_list, "a") as f:
            f.write(zip_file + "\n")


if __name__ == "__main__":
    main()
