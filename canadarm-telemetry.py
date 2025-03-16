import datetime
import os
import time
from lightstreamer.client import LightstreamerClient, Subscription, SubscriptionListener


def get_timestamp():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class TelemetryListener(SubscriptionListener):
    def __init__(self):
        self.update_count = 0

    def onSubscription(self):
        print(f"[{get_timestamp()}] Subscribed to telemetry")

    def onItemUpdate(self, update):
        self.update_count += 1
        item_name = update.getItemName()
        value = update.getValue("Value")
        timestamp = update.getValue("TimeStamp")
        print(f"[{get_timestamp()}] Update #{self.update_count}: {item_name} = {value}")


def main():
    print(f"[{get_timestamp()}] Starting Canadarm telemetry recorder")

    # Create client - exactly matching the JavaScript version
    client = LightstreamerClient("https://push.lightstreamer.com", "ISSLIVE")

    # Create listener
    listener = TelemetryListener()

    # Create subscription for Canadarm data (SSRMS)
    arm_items = [
        "CSASSRMS001",  # -1  SACS Operating Base eg: "LEE B"
        "CSASSRMS002",  # Base Location eg: "MBS PDGF 3"
        "CSASSRMS003",  # -4  SSRMS LEE Stop Condition ; -5 SSRMS LEE Run Speed ; -6 SSRMS LEE Hot
        "CSASSRMS004",  # SR
        "CSASSRMS005",  # SY
        "CSASSRMS006",  # SP
        "CSASSRMS007",  # EP
        "CSASSRMS008",  # WP
        "CSASSRMS009",  # WY
        "CSASSRMS010",  # WR
        "CSASSRMS011",  # SSRMS Tip LEE Payload Status eg "Captured"
    ]

    sub = Subscription("MERGE", arm_items, ["TimeStamp", "Value"])
    sub.addListener(listener)

    # Time subscription
    time_sub = Subscription(
        "MERGE",
        ["TIME_000001"],
        ["TimeStamp", "Value", "Status.Class", "Status.Indicator"],
    )
    time_sub.addListener(listener)

    # Connect
    print(f"[{get_timestamp()}] Connecting to Lightstreamer server")
    client.connect()

    time.sleep(2)

    # Subscribe
    print(f"[{get_timestamp()}] Subscribing to Canadarm data")
    client.subscribe(sub)
    client.subscribe(time_sub)

    try:
        # Keep script running and report status
        while True:
            print(
                f"[{get_timestamp()}] Status: {client.getStatus()}, Updates: {listener.update_count}"
            )
            time.sleep(10)
    except KeyboardInterrupt:
        print(f"[{get_timestamp()}] Recording stopped by user")
        client.disconnect()


if __name__ == "__main__":
    main()
