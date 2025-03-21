import datetime
import os
import time
import sys
import signal
import traceback
import threading
from lightstreamer.client import LightstreamerClient, Subscription, SubscriptionListener

from lightstreamer.client import (
    ClientListener,
)

from dotenv import load_dotenv

# Force stdout to be line-buffered for more reliable console output
(
    sys.stdout.reconfigure(line_buffering=True)
    if hasattr(sys.stdout, "reconfigure")
    else None
)

# Load environment variables - check for Docker environment first
if os.path.exists("/.dockerenv"):
    print(
        f"[{datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}] Running in Docker container"
    )
    # In Docker, environment variables should be already set
    RAW_FOLDER = os.environ.get("RAW_FOLDER", "/data")
else:
    # For local development, use .env file
    load_dotenv(dotenv_path=".env")
    RAW_FOLDER = os.getenv("RAW_FOLDER")

output_folder = os.path.join(RAW_FOLDER, "iss_telemetry")


# Add watchdog timer for detecting script inactivity
class Watchdog:
    def __init__(self, timeout=300):  # 5 minutes timeout by default
        self.timeout = timeout
        self.last_activity = time.time()
        self.running = True
        self.thread = threading.Thread(target=self._monitor)
        self.thread.daemon = True

    def start(self):
        print(
            f"[{get_log_timestamp()}] Starting watchdog timer (timeout: {self.timeout}s)"
        )
        self.thread.start()

    def pet(self):
        """Reset the watchdog timer by recording activity"""
        self.last_activity = time.time()

    def stop(self):
        self.running = False

    def _monitor(self):
        while self.running:
            if time.time() - self.last_activity > self.timeout:
                print(
                    f"[{get_log_timestamp()}] WARNING: No activity detected for {self.timeout} seconds!"
                )
                print(
                    f"[{get_log_timestamp()}] Script may be frozen - consider restarting it"
                )

                # Log to master log as well
                try:
                    date_dir = get_date_directory()
                    master_log = os.path.join(date_dir, "master.log")
                    with open(master_log, "a") as f:
                        f.write(
                            f"{get_log_timestamp()} - WARNING: Watchdog detected no activity for {self.timeout} seconds!\n"
                        )
                except Exception as e:
                    print(
                        f"[{get_log_timestamp()}] ERROR: Could not write to master log: {e}"
                    )

                # Reset timer to prevent flooding logs with the same message
                self.last_activity = time.time()

            time.sleep(60)  # Check every minute


# Create logs directory if it doesn't exist
def ensure_logs_directory():
    # In Docker, we'll store logs under the data volume
    if os.path.exists("/.dockerenv"):
        logs_dir = os.path.join(RAW_FOLDER, "logs")
    else:
        logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    return logs_dir


# Create output directory if it doesn't exist
def ensure_output_directory():
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    return output_folder


# Timestamp for log messages
def get_log_timestamp():
    return datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


# Helper function to get date-based directory path
def get_date_directory():
    # Create date-based directory structure using UTC date
    utc_now = datetime.datetime.utcnow()
    year = utc_now.strftime("%Y")
    month = utc_now.strftime("%m")
    day = utc_now.strftime("%d")

    # Create path: output_folder/year/month/day
    date_dir = os.path.join(output_folder, year, month, day)
    os.makedirs(date_dir, exist_ok=True)

    return date_dir


# Connection status listener to monitor and debug connection issues
class ConnectionStatusListener(ClientListener):
    def __init__(self, logs_dir):
        self.logs_dir = logs_dir
        # Will set the connection_log path dynamically in log_event
        self.connection_log = None
        # Initialize with a temporary log until we set up the dated directory
        temp_log = os.path.join(logs_dir, "temp_connection.log")
        with open(temp_log, "a") as f:  # Changed from 'w' to 'a'
            f.write(f"Connection log started at {get_log_timestamp()}\n")
            f.write("=" * 60 + "\n\n")

    def log_event(self, event_type, message):
        log_msg = f"{get_log_timestamp()} - {event_type}: {message}"
        print(f"[CONNECTION] {log_msg}")

        # Get date directory and create connection log path
        date_dir = get_date_directory()
        self.connection_log = os.path.join(date_dir, "connection.log")

        # Append to the connection log
        with open(self.connection_log, "a") as f:
            f.write(f"{log_msg}\n")

    def onStatusChange(self, status):
        self.log_event("Status", status)
        # Pet the watchdog when status changes
        if hasattr(sys, "watchdog"):
            sys.watchdog.pet()

    def onServerError(self, error_code, error_message):
        self.log_event("ERROR", f"Code {error_code}: {error_message}")

    def onPropertyChange(self, property_name):
        self.log_event("Property Change", property_name)


# Listener for telemetry items: writes each update to a file named after the item.
class TelemetryListener(SubscriptionListener):
    def __init__(self, logs_dir):
        self.logs_dir = logs_dir
        self.output_dir = ensure_output_directory()

        # Add counter for updates
        self.update_count = 0
        self.last_update_time = datetime.datetime.now()
        self.last_status_print = datetime.datetime.now()
        # Print status every 60 seconds
        self.status_interval = datetime.timedelta(seconds=60)
        # Keep track of items updated since last status print
        self.items_since_last_print = set()
        # New: Dictionary to store the last written (timestamp, value) per item to avoid duplicates
        self.last_written = {}

    def onSubscription(self, subscription):
        message = f"Subscribed to telemetry items: {subscription.getItemNames()}"
        print(f"[{get_log_timestamp()}] {message}")

    def onUnsubscription(self, subscription):
        message = f"Unsubscribed from telemetry items: {subscription.getItemNames()}"
        print(f"[{get_log_timestamp()}] {message}")

    def onItemUpdate(self, update):
        try:
            item_name = update.getItemName()
            timestamp = update.getValue("TimeStamp")
            value = update.getValue("Value")

            # Skip duplicate updates (for items except TIME_000001)
            if item_name != "TIME_000001":
                last = self.last_written.get(item_name)
                if last == (timestamp, value):
                    return  # duplicate detected, skip writing
                self.last_written[item_name] = (timestamp, value)

            # Update counter, time and item set
            self.update_count += 1
            self.last_update_time = datetime.datetime.now()
            self.items_since_last_print.add(item_name)

            # Pet the watchdog to indicate activity
            if hasattr(sys, "watchdog"):
                sys.watchdog.pet()

            # Only print periodic status updates to console
            current_time = datetime.datetime.now()
            if current_time - self.last_status_print >= self.status_interval:
                unique_items = len(self.items_since_last_print)
                status_message = (
                    f"Still recording: {self.update_count} total updates received "
                    f"({unique_items} unique items updated in the last minute)"
                )
                print(f"[{get_log_timestamp()}] {status_message}")
                sys.stdout.flush()  # Ensure output is displayed immediately

                # Also write to master log
                try:
                    date_dir = get_date_directory()
                    master_log = os.path.join(date_dir, "master.log")
                    with open(master_log, "a") as f:
                        f.write(f"{get_log_timestamp()} - {status_message}\n")
                except Exception as e:
                    print(
                        f"[{get_log_timestamp()}] ERROR: Could not write to master log: {e}"
                    )
                    sys.stdout.flush()

                self.last_status_print = current_time
                self.items_since_last_print = set()

            # Skip writing TIME_000001 data to disk as it's redundant (timestamped timestamps)
            # and is already processed by the TimeListener class
            if item_name == "TIME_000001":
                return

            # Get date directory
            date_dir = get_date_directory()

            # Append the update to a file in the date-based directory
            item_file = os.path.join(date_dir, f"{item_name}.txt")
            with open(item_file, "a") as f:
                f.write(f"{timestamp} {value}\n")
        except Exception as e:
            exc_info = traceback.format_exc()
            error_msg = f"Error in onItemUpdate: {str(e)}\n{exc_info}"
            print(f"[{get_log_timestamp()}] ERROR: {error_msg}")
            sys.stdout.flush()

            try:
                date_dir = get_date_directory()
                error_log = os.path.join(date_dir, "error.log")
                with open(error_log, "a") as f:
                    f.write(f"{get_log_timestamp()} - {error_msg}\n")
            except:
                pass  # At this point we can't do much if even error logging fails

    def onEndOfSnapshot(self, item_name, item_pos):
        message = f"End of snapshot for {item_name} at position {item_pos}"
        print(f"[{get_log_timestamp()}] {message}")
        sys.stdout.flush()  # Ensure output is displayed

    def onItemError(
        self, exception, subscription_error_code, subscription_error_message
    ):
        message = f"Item error: {subscription_error_code} - {subscription_error_message}. Exception: {exception}"
        print(f"[{get_log_timestamp()}] ERROR: {message}")
        sys.stdout.flush()  # Ensure output is displayed

        # Log to error file
        try:
            date_dir = get_date_directory()
            error_log = os.path.join(date_dir, "error.log")
            with open(error_log, "a") as f:
                f.write(f"{get_log_timestamp()} - {message}\n")
        except Exception as e:
            print(f"[{get_log_timestamp()}] ERROR: Could not write to error log: {e}")
            sys.stdout.flush()


# Listener for time updates: computes a difference and writes a status line to AOS.log.
class TimeListener(SubscriptionListener):
    def __init__(self, timestamp_now, logs_dir):
        self.timestamp_now = timestamp_now
        self.logs_dir = logs_dir
        self.output_dir = ensure_output_directory()
        # Will set the aos_file path dynamically in onItemUpdate
        self.aos_file = None
        self.current_date_dir = None

        # Store previous state to avoid repeated writes
        self.last_aosnum = None
        self.last_write_time = datetime.datetime.now()
        self.write_interval = datetime.timedelta(
            minutes=5
        )  # Only force write every 5 minutes

        # Replace detailed logging with simple metrics
        self.update_count = 0
        self.last_status_print = datetime.datetime.now()
        self.status_interval = datetime.timedelta(seconds=60)  # Report once per minute
        self.items_since_last_print = set()

        # Add status tracking for AOS changes
        self.current_status = None

    def onItemUpdate(self, update):
        try:
            # Pet the watchdog to indicate activity
            if hasattr(sys, "watchdog"):
                sys.watchdog.pet()

            # Rest of the existing onItemUpdate method
            status = update.getValue("Status.Class")
            aos_timestamp_str = update.getValue("TimeStamp")

            # Get date directory
            date_dir = get_date_directory()

            # Update the AOS file path if the date changed or not set yet
            if self.current_date_dir != date_dir:
                self.aos_file = os.path.join(date_dir, "AOS.log")
                self.current_date_dir = date_dir

            try:
                aos_timestamp = float(aos_timestamp_str)
            except ValueError:
                message = f"Invalid TimeStamp received: {aos_timestamp_str}"
                print(f"[{get_log_timestamp()}] {message}")
                with open(self.aos_file, "a") as f:
                    f.write(f"{get_log_timestamp()} - {message}\n")
                return

            difference = self.timestamp_now - aos_timestamp

            # Determine status but don't log it immediately
            if status == "24":
                if difference > 0.00153680542553047:
                    message = "Stale Signal!"
                    aosnum = 2
                else:
                    message = "Signal Acquired!"
                    aosnum = 1
            else:
                message = "Signal Lost!"
                aosnum = 0

            # Log AOS changes to console when they happen
            if aosnum != self.current_status:
                print(
                    f"[{get_log_timestamp()}] AOS Change: {message} (Status={status}, Diff={difference:.6f})"
                )
                self.current_status = aosnum

            # Update counter and track item
            self.update_count += 1
            self.items_since_last_print.add("TIME_000001")

            # Only print periodic status updates to console
            current_time = datetime.datetime.now()
            if current_time - self.last_status_print >= self.status_interval:
                # print(
                #     f"[{get_log_timestamp()}] Time updates: {self.update_count} updates received in the last minute"
                # )
                self.update_count = 0
                self.last_status_print = current_time
                self.items_since_last_print = set()

            # Only write to AOS file if status changed or if we haven't written in a while
            if (aosnum != self.last_aosnum) or (
                current_time - self.last_write_time > self.write_interval
            ):
                # Append the AOS status update to AOS.log
                with open(self.aos_file, "a") as f:
                    f.write(f"AOS {aos_timestamp_str} {aosnum}\n")
                self.last_aosnum = aosnum
                self.last_write_time = current_time
        except Exception as e:
            exc_info = traceback.format_exc()
            error_msg = f"Error in TimeListener.onItemUpdate: {str(e)}\n{exc_info}"
            print(f"[{get_log_timestamp()}] ERROR: {error_msg}")
            sys.stdout.flush()

            try:
                date_dir = get_date_directory()
                error_log = os.path.join(date_dir, "error.log")
                with open(error_log, "a") as f:
                    f.write(f"{get_log_timestamp()} - {error_msg}\n")
            except:
                pass


# Compute a "timestamp now" similar to the JavaScript version.
def compute_timestamp_now():
    now = datetime.datetime.utcnow()
    day_of_year = now.timetuple().tm_yday
    hours = now.hour
    minutes = now.minute
    seconds = now.second
    timestamp_now = day_of_year * 24 + hours + minutes / 60 + seconds / 3600
    print(f"[{get_log_timestamp()}] Computed timestamp now: {timestamp_now}")
    return timestamp_now


def check_network_connectivity(host="push.lightstreamer.com"):
    """Check if we can connect to the specified host"""
    import socket
    import ssl

    try:
        # First try standard connection
        print(f"[{get_log_timestamp()}] Testing connection to {host}...")
        socket.create_connection((host, 443), timeout=5)
        return True
    except OSError as e:
        print(f"[{get_log_timestamp()}] Standard connection failed: {e}")
        try:
            # Try SSL connection
            print(f"[{get_log_timestamp()}] Trying SSL connection to {host}...")
            context = ssl.create_default_context()
            with socket.create_connection((host, 443), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    print(
                        f"[{get_log_timestamp()}] SSL connection successful to {host}"
                    )
                    return True
        except Exception as e:
            print(f"[{get_log_timestamp()}] SSL connection failed: {e}")
            return False
    sys.stdout.flush()  # Ensure output is displayed


# Add signal handler for graceful shutdown
# Enhanced for Docker environment
def signal_handler(sig, frame):
    print(
        f"\n[{get_log_timestamp()}] Received signal {sig}, shutting down gracefully..."
    )
    sys.stdout.flush()

    # Get current date directory for final log entry
    try:
        date_dir = get_date_directory()
        master_log = os.path.join(date_dir, "master.log")
        with open(master_log, "a") as f:
            f.write(f"{get_log_timestamp()} - Recording stopped by signal {sig}.\n")
            f.write("This may be due to container shutdown or restart.\n")
    except Exception as e:
        print(f"[{get_log_timestamp()}] Error writing shutdown log: {e}")

    # Stop the watchdog if it's running
    if hasattr(sys, "watchdog"):
        sys.watchdog.stop()

    # Clean exit
    print(f"[{get_log_timestamp()}] Exiting with status 0.")
    sys.stdout.flush()
    os._exit(
        0
    )  # Use os._exit instead of sys.exit to ensure immediate exit without threading issues


def main():
    # Register signal handlers - important for Docker container operation
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Print Docker-specific information if running in container
    if os.path.exists("/.dockerenv"):
        print(f"[{get_log_timestamp()}] Running in Docker container")
        print(f"[{get_log_timestamp()}] RAW_FOLDER set to: {RAW_FOLDER}")
        print(f"[{get_log_timestamp()}] Process ID: {os.getpid()}")

        # Create a .ready file for the healthcheck script
        try:
            with open(os.path.join(RAW_FOLDER, ".ready"), "w") as f:
                f.write(f"Process started at {get_log_timestamp()}\n")
                f.write(f"PID: {os.getpid()}\n")
        except Exception as e:
            print(f"[{get_log_timestamp()}] Warning: Could not create ready file: {e}")

    # Start the watchdog timer - longer timeout in Docker to handle container operations
    timeout = (
        600 if os.path.exists("/.dockerenv") else 300
    )  # 10 minutes in Docker, 5 otherwise
    sys.watchdog = Watchdog(timeout=timeout)
    sys.watchdog.start()

    # Set up logs directory
    logs_dir = ensure_logs_directory()
    print(f"[{get_log_timestamp()}] Logging to directory: {os.path.abspath(logs_dir)}")
    print(
        f"[{get_log_timestamp()}] Telemetry data will be saved to: {os.path.abspath(output_folder)}"
    )
    sys.stdout.flush()

    # Get date directory for master log
    date_dir = get_date_directory()

    # Create a master log file in the dated directory - append if exists
    master_log = os.path.join(date_dir, "master.log")
    if os.path.exists(master_log):
        with open(master_log, "a") as f:
            f.write(
                f"\nISS Telemetry Recording Session restarted at {get_log_timestamp()}\n"
            )
            f.write("-" * 60 + "\n\n")
    else:
        with open(master_log, "w") as f:
            f.write(
                f"ISS Telemetry Recording Session started at {get_log_timestamp()}\n"
            )
            f.write("=" * 60 + "\n\n")

    # Check network connectivity first - try both server domains
    print(f"[{get_log_timestamp()}] Checking network connectivity...")
    sys.stdout.flush()

    server_url = "https://push.lightstreamer.com"

    # In Docker, we want to retry network connectivity checks
    max_network_retries = 12  # Retry for 12 * 10 seconds = 2 minutes
    network_retry_count = 0

    while network_retry_count < max_network_retries:
        if check_network_connectivity("push.lightstreamer.com"):
            print(f"[{get_log_timestamp()}] Using server: {server_url}")
            break
        else:
            network_retry_count += 1
            if network_retry_count < max_network_retries:
                print(
                    f"[{get_log_timestamp()}] Network connection failed. Retrying in 10 seconds... ({network_retry_count}/{max_network_retries})"
                )
                time.sleep(10)
            else:
                error_msg = "Cannot connect to Lightstreamer server after multiple attempts. Will continue and hope for network recovery."
                print(f"[{get_log_timestamp()}] WARNING: {error_msg}")
                sys.stdout.flush()
                with open(os.path.join(date_dir, "master.log"), "a") as f:
                    f.write(f"{get_log_timestamp()} - WARNING: {error_msg}\n")
                # In Docker, we don't exit - the container will restart and we'll try again
                if not os.path.exists("/.dockerenv"):
                    sys.exit(1)

    print(f"[{get_log_timestamp()}] Network connectivity confirmed.")
    sys.stdout.flush()

    # Create a simpler client matching the working JavaScript version
    client = LightstreamerClient("https://push.lightstreamer.com", "ISSLIVE")

    # Add connection status listener
    connection_listener = ConnectionStatusListener(logs_dir)
    client.addListener(connection_listener)

    # Configure connection options - keep only what's necessary
    client.connectionOptions.setSlowingEnabled(False)
    client.connectionOptions.setKeepaliveInterval(30000)
    client.connectionOptions.setRequestedMaxBandwidth("unlimited")
    client.connectionOptions.setRetryDelay(5000)

    print(
        f"[{get_log_timestamp()}] Connection options set: SlowingEnabled=False, KeepaliveInterval=30000ms, RetryDelay=5000ms"
    )
    sys.stdout.flush()

    # Define the list of telemetry items
    # fmt: off
    items = ["AIRLOCK000001", "AIRLOCK000002", "AIRLOCK000003", "AIRLOCK000004", "AIRLOCK000005", "AIRLOCK000006", "AIRLOCK000007", "AIRLOCK000008", "AIRLOCK000009", "AIRLOCK000010", "AIRLOCK000011", "AIRLOCK000012", "AIRLOCK000013", "AIRLOCK000014", "AIRLOCK000015", "AIRLOCK000016", "AIRLOCK000017", "AIRLOCK000018", "AIRLOCK000019", "AIRLOCK000020", "AIRLOCK000021", "AIRLOCK000022", "AIRLOCK000023", "AIRLOCK000024", "AIRLOCK000025", "AIRLOCK000026", "AIRLOCK000027", "AIRLOCK000028", "AIRLOCK000029", "AIRLOCK000030", "AIRLOCK000031", "AIRLOCK000032", "AIRLOCK000033", "AIRLOCK000034", "AIRLOCK000035", "AIRLOCK000036", "AIRLOCK000037", "AIRLOCK000038", "AIRLOCK000039", "AIRLOCK000040", "AIRLOCK000041", "AIRLOCK000042", "AIRLOCK000043", "AIRLOCK000044", "AIRLOCK000045", "AIRLOCK000046", "AIRLOCK000047", "AIRLOCK000048", "AIRLOCK000049", "AIRLOCK000050", "AIRLOCK000051", "AIRLOCK000052", "AIRLOCK000053", "AIRLOCK000054", "AIRLOCK000055", "AIRLOCK000056", "AIRLOCK000057", "NODE2000001", "NODE2000002", "NODE2000003", "NODE2000006", "NODE2000007", "NODE3000001", "NODE3000002", "NODE3000003", "NODE3000004", "NODE3000005", "NODE3000006", "NODE3000007", "NODE3000008", "NODE3000009", "NODE3000010", "NODE3000011", "NODE3000012", "NODE3000013", "NODE3000017", "NODE3000018", "NODE3000019", "USLAB000053", "USLAB000054", "USLAB000055", "USLAB000056", "USLAB000057", "USLAB000058", "USLAB000059", "USLAB000060", "USLAB000061", "USLAB000062", "USLAB000063", "USLAB000064", "USLAB000065", "AIRLOCK000058", "NODE1000001", "NODE1000002", "NODE2000004", "NODE2000005", "NODE3000014", "NODE3000015", "NODE3000016", "NODE3000020", "P1000006", "P1000008", "P1000009", "P3000001", "P3000002", "P4000003", "P4000006", "P6000003", "P6000006", "S0000010", "S0000011", "S0000012", "S0000013", "S1000006", "S1000007", "S1000008", "S3000001", "S3000002", "S4000003", "S4000006", "S6000003", "S6000006", "USLAB000066", "USLAB000067", "USLAB000068", "USLAB000069", "USLAB000070", "USLAB000071", "USLAB000072", "USLAB000073", "USLAB000074", "USLAB000075", "USLAB000076", "USLAB000077", "USLAB000078", "USLAB000079", "USLAB000080", "P1000001", "P1000002", "P1000003", "P4000001", "P4000002", "P4000004", "P4000005", "P4000007", "P4000008", "P6000001", "P6000002", "P6000004", "P6000005", "P6000007", "P6000008", "S1000001", "S1000002", "S1000003", "S4000001", "S4000002", "S4000004", "S4000005", "S4000007", "S4000008", "S6000001", "S6000002", "S6000004", "S6000005", "S6000007", "S6000008", "P1000004", "P1000005", "P1000007", "S1000004", "S1000009", "USLAB000088", "USLAB000089", "USLAB000090", "USLAB000091", "USLAB000092", "USLAB000093", "USLAB000094", "USLAB000095", "USLAB000096", "USLAB000097", "USLAB000098", "USLAB000099", "USLAB000100", "USLAB000101", "Z1000013", "Z1000014", "Z1000015", "S0000001", "S0000002", "S0000003", "S0000004", "S0000005", "S0000006", "S0000007", "S0000008", "S0000009", "USLAB000081", "RUSSEG000001", "RUSSEG000002", "RUSSEG000003", "RUSSEG000004", "RUSSEG000005", "RUSSEG000006", "RUSSEG000007", "RUSSEG000008", "RUSSEG000009", "RUSSEG000010", "RUSSEG000011", "RUSSEG000012", "RUSSEG000013", "RUSSEG000014", "RUSSEG000015", "RUSSEG000016", "RUSSEG000017", "RUSSEG000018", "RUSSEG000019", "RUSSEG000020", "RUSSEG000021", "RUSSEG000022", "RUSSEG000023", "RUSSEG000024", "S1000005", "USLAB000001", "USLAB000002", "USLAB000003", "USLAB000004", "USLAB000005", "USLAB000006", "USLAB000007", "USLAB000008", "USLAB000009", "USLAB000011", "USLAB000013", "USLAB000014", "USLAB000015", "USLAB000016", "USLAB000017", "USLAB000018", "USLAB000019", "USLAB000020", "USLAB000021", "USLAB000022", "USLAB000023", "USLAB000024", "USLAB000025", "USLAB000026", "USLAB000027", "USLAB000028", "USLAB000029", "USLAB000030", "USLAB000031", "USLAB000038", "USLAB000039", "USLAB000040", "USLAB000041", "USLAB000042", "USLAB000043", "USLAB000044", "USLAB000045", "USLAB000046", "USLAB000047", "USLAB000048", "USLAB000049", "USLAB000050", "USLAB000051", "USLAB000052", "Z1000001", "Z1000002", "Z1000003", "Z1000004", "Z1000005", "Z1000006", "Z1000007", "Z1000008", "Z1000009", "Z1000010", "Z1000011", "Z1000012", "USLAB000010", "USLAB000012", "RUSSEG000025", "USLAB000032", "USLAB000033", "USLAB000034", "USLAB000035", "USLAB000036", "USLAB000037", "USLAB000082", "USLAB000083", "USLAB000084", "USLAB000085", "USLAB000087", "USLAB000086", "USLAB000102", "TIME_000001", "TIME_000002", "CSAMT000001", "CSAMT000002", "CSASSRMS001", "CSASSRMS002", "CSASSRMS003", "CSASSRMS004", "CSASSRMS005", "CSASSRMS006", "CSASSRMS007", "CSASSRMS008", "CSASSRMS009", "CSASSRMS010", "CSASSRMS011", "CSASPDM0001", "CSASPDM0002", "CSASPDM0003", "CSASPDM0004", "CSASPDM0005", "CSASPDM0006", "CSASPDM0007", "CSASPDM0008", "CSASPDM0009", "CSASPDM0010", "CSASPDM0011", "CSASPDM0012", "CSASPDM0013", "CSASPDM0014", "CSASPDM0015", "CSASPDM0016", "CSASPDM0017", "CSASPDM0018", "CSASPDM0019", "CSASPDM0020", "CSASPDM0021", "CSASPDM0022", "CSAMBS00001", "CSAMBS00002", "CSAMBA00003", "CSAMBA00004"]
    # fmt: on

    # Create a telemetry listener with the logs directory
    telemetry_listener = TelemetryListener(logs_dir)

    # Test items
    test_items = [
        "CSASSRMS004",  # SR
        "CSASSRMS005",  # SY
        "CSASSRMS006",  # SP
        "CSASSRMS007",  # EP
        "CSASSRMS008",  # WP
        "CSASSRMS009",  # WY
        "CSASSRMS010",  # WR
    ]

    # Function to create a fresh test subscription
    def create_test_subscription():
        sub = Subscription(
            "MERGE",
            test_items,
            ["TimeStamp", "Value"],
        )
        sub.addListener(telemetry_listener)
        return sub

    # Function to create a fresh time subscription
    def create_time_subscription(timestamp_now):
        sub = Subscription(
            "MERGE",
            ["TIME_000001"],
            ["TimeStamp", "Value", "Status.Class", "Status.Indicator"],
        )
        sub.addListener(TimeListener(timestamp_now, logs_dir))
        return sub

    # Function to create a fresh telemetry subscription for all items
    def create_telemetry_subscription():
        sub = Subscription(
            mode="MERGE",
            items=items,
            fields=["TimeStamp", "Value"],
        )
        sub.addListener(telemetry_listener)
        return sub

    # Create initial subscriptions
    test_subscription = create_test_subscription()
    timestamp_now = compute_timestamp_now()
    time_subscription = create_time_subscription(timestamp_now)
    telemetry_subscription = None  # Will create later if needed

    # Connect first, then subscribe (like in working JS)
    print(f"[{get_log_timestamp()}] Connecting to Lightstreamer server...")
    sys.stdout.flush()
    client.connect()

    # Wait a bit for connection
    time.sleep(3)

    print(f"[{get_log_timestamp()}] Subscribing to test items...")
    sys.stdout.flush()
    client.subscribe(test_subscription)
    print(f"[{get_log_timestamp()}] Subscribing to TIME_000001...")
    sys.stdout.flush()
    client.subscribe(time_subscription)

    # Keep the script running with improved reconnection logic
    try:
        no_data_count = 0
        last_count = 0
        # Increase max_reconnect_attempts for Docker environment to be more resilient
        max_reconnect_attempts = 30 if os.path.exists("/.dockerenv") else 10
        reconnect_attempts = 0
        health_check_interval = 0

        # Only subscribe to all items if we start receiving data from test items
        full_subscription_done = False

        while True:
            # Pet the watchdog to show the main loop is still running
            if hasattr(sys, "watchdog"):
                sys.watchdog.pet()

            time.sleep(10)  # Check every 10 seconds

            # Increment health check interval counter
            health_check_interval += 1

            # Every 30 iterations (5 minutes), update .ready file if running in Docker
            if health_check_interval >= 30:
                health_check_interval = 0
                if os.path.exists("/.dockerenv"):
                    try:
                        ready_file = os.path.join(RAW_FOLDER, ".ready")
                        with open(ready_file, "a") as f:
                            f.write(f"Still alive at {get_log_timestamp()}\n")
                    except Exception as e:
                        print(
                            f"[{get_log_timestamp()}] Warning: Could not update ready file: {e}"
                        )

            # Log client status periodically for debugging
            status = client.getStatus()
            # print(f"[{get_log_timestamp()}] Client status: {status}")

            # Check connection status explicitly - reconnect if not CONNECTED
            if not status.startswith("CONNECTED"):
                print(
                    f"[{get_log_timestamp()}] Not connected (status: {status}). Attempting to reconnect..."
                )
                sys.stdout.flush()
                try:
                    client.connect()
                except Exception as e:
                    print(f"[{get_log_timestamp()}] Error during reconnect: {str(e)}")
                    sys.stdout.flush()
                time.sleep(3)  # Give it time to connect
                continue

            # Check if we're getting updates
            if telemetry_listener.update_count > 0 and not full_subscription_done:
                print(
                    f"[{get_log_timestamp()}] Test subscription successful! Subscribing to all items..."
                )
                sys.stdout.flush()

                # Now create and subscribe to the full item set
                try:
                    telemetry_subscription = create_telemetry_subscription()
                    client.subscribe(telemetry_subscription)
                    full_subscription_done = True
                    print(f"[{get_log_timestamp()}] Subscribed to all telemetry items.")
                    sys.stdout.flush()
                except Exception as e:
                    print(
                        f"[{get_log_timestamp()}] Error subscribing to all items: {str(e)}"
                    )
                    sys.stdout.flush()

            # Update where we write to the master log, getting the current date-based directory
            date_dir = get_date_directory()
            master_log = os.path.join(date_dir, "master.log")

            if telemetry_listener.update_count == last_count:
                no_data_count += 1
                if no_data_count >= 6:  # No data for 60 seconds
                    print(
                        f"[{get_log_timestamp()}] WARNING: No updates received in the last 60 seconds."
                    )
                    sys.stdout.flush()

                    if no_data_count == 6 or no_data_count % 18 == 0:
                        if reconnect_attempts < max_reconnect_attempts:
                            reconnect_attempts += 1
                            print(
                                f"[{get_log_timestamp()}] Attempting to reconnect... (Attempt {reconnect_attempts}/{max_reconnect_attempts})"
                            )
                            sys.stdout.flush()

                            try:
                                # Simplified reconnection process matching JS better
                                client.disconnect()
                                time.sleep(3)
                                client.connect()
                                time.sleep(5)  # Give more time to establish connection

                                # Create fresh subscription objects for reconnection
                                print(
                                    f"[{get_log_timestamp()}] Creating fresh subscriptions..."
                                )
                                sys.stdout.flush()
                                test_subscription = create_test_subscription()
                                timestamp_now = (
                                    compute_timestamp_now()
                                )  # Recalculate timestamp
                                time_subscription = create_time_subscription(
                                    timestamp_now
                                )

                                # Resubscribe to test items first
                                print(
                                    f"[{get_log_timestamp()}] Resubscribing to test items..."
                                )
                                sys.stdout.flush()
                                client.subscribe(test_subscription)
                                time.sleep(1)
                                client.subscribe(time_subscription)

                                # Reset full subscription flag to resubscribe to all items once test items work
                                full_subscription_done = False
                            except Exception as e:
                                print(
                                    f"[{get_log_timestamp()}] Error during reconnection: {str(e)}"
                                )
                                sys.stdout.flush()
                        else:
                            print(
                                f"[{get_log_timestamp()}] Max reconnection attempts reached."
                            )
                            sys.stdout.flush()
                            with open(master_log, "a") as f:
                                f.write(
                                    f"{get_log_timestamp()} - Max reconnection attempts reached.\n"
                                )

                            if os.path.exists("/.dockerenv"):
                                print(
                                    f"[{get_log_timestamp()}] In Docker container - exiting with error code to trigger container restart"
                                )
                                sys.exit(
                                    1
                                )  # Exit with error so Docker will restart the container
                            else:
                                print(
                                    f"[{get_log_timestamp()}] Please restart the script manually."
                                )
                                break
            else:
                # We got data, reset the counters
                no_data_count = 0
                reconnect_attempts = 0
                last_count = telemetry_listener.update_count

    except KeyboardInterrupt:
        print(f"[{get_log_timestamp()}] Recording stopped by user.")
        sys.stdout.flush()

        # Get current date directory for final log entry
        date_dir = get_date_directory()
        master_log = os.path.join(date_dir, "master.log")

        with open(master_log, "a") as f:
            f.write(f"{get_log_timestamp()} - Recording stopped by user.\n")
            f.write(f"Total updates received: {telemetry_listener.update_count}\n")
        print(f"All logs saved to: {os.path.abspath(date_dir)}")

        # Proper cleanup
        client.disconnect()

    except Exception as e:
        exc_info = traceback.format_exc()
        error_msg = f"Unhandled exception in main loop: {str(e)}\n{exc_info}"
        print(f"[{get_log_timestamp()}] CRITICAL ERROR: {error_msg}")
        sys.stdout.flush()

        # Get current date directory for error log
        try:
            date_dir = get_date_directory()
            error_log = os.path.join(date_dir, "error.log")
            with open(error_log, "a") as f:
                f.write(f"{get_log_timestamp()} - CRITICAL ERROR: {error_msg}\n")

            master_log = os.path.join(date_dir, "master.log")
            with open(master_log, "a") as f:
                f.write(
                    f"{get_log_timestamp()} - Script crashed with error: {str(e)}\n"
                )

            # In Docker, exit with error code to trigger container restart
            if os.path.exists("/.dockerenv"):
                print(
                    f"[{get_log_timestamp()}] Exiting with error code to trigger container restart"
                )
                sys.exit(1)
        except:
            pass  # At this point we can't do much if even error logging fails

    finally:
        # Always try to disconnect client and clean up
        try:
            print(f"[{get_log_timestamp()}] Cleaning up resources...")
            sys.stdout.flush()
            if "client" in locals() and client:
                client.disconnect()

            if hasattr(sys, "watchdog"):
                sys.watchdog.stop()

            # In finally block, remove ready file if exiting
            if os.path.exists("/.dockerenv"):
                ready_file = os.path.join(RAW_FOLDER, ".ready")
                if os.path.exists(ready_file):
                    try:
                        os.remove(ready_file)
                        print(f"[{get_log_timestamp()}] Removed ready file")
                    except Exception as e:
                        print(
                            f"[{get_log_timestamp()}] Failed to remove ready file: {e}"
                        )
        except Exception as e:
            print(f"[{get_log_timestamp()}] Error in cleanup: {e}")
            pass


if __name__ == "__main__":
    main()
