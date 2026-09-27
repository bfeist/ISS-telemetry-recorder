"""Keep a subscribed Lightstreamer client alive through prolonged outages."""

import time


def record_forever(client, listener, heartbeat, log, poll_interval=10,
                   inactivity_timeout=60, max_retry_delay=300):
    """Retry forever, including startup failures and connected-but-silent feeds.

    Lightstreamer retains active subscriptions across disconnect/connect calls.
    Let its normal network recovery run between our bounded retry attempts.
    KeyboardInterrupt and process shutdown signals are deliberately not caught.
    """
    last_count = listener.update_count
    last_update = time.monotonic()
    next_retry = last_update
    retry_delay = 30
    attempts = 0

    while True:
        try:
            heartbeat()
            now = time.monotonic()
            count = listener.update_count
            if count != last_count:
                if attempts:
                    log("Telemetry resumed; retry delay reset.")
                last_count = count
                last_update = now
                attempts = 0
                retry_delay = 30
                next_retry = now

            status = client.getStatus()
            silent = now - last_update >= inactivity_timeout
            if now >= next_retry and (status == "DISCONNECTED" or silent):
                attempts += 1
                # Set the deadline before SDK calls so exceptions also back off.
                next_retry = now + retry_delay
                log(f"No telemetry / status {status}. Reconnecting "
                    f"(attempt {attempts}; retry delay {retry_delay}s; no retry limit).")
                retry_delay = min(retry_delay * 2, max_retry_delay)
                client.disconnect()
                client.connect()
        except Exception as exc:
            log(f"Recorder recovery error: {exc}. Will keep retrying.")
        time.sleep(poll_interval)
