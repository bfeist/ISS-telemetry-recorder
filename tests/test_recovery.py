import contextlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from connection_retry import record_forever
import healthcheck


class RecoveryTests(unittest.TestCase):
    def simulate(self, duration, status="CONNECTED:WS-STREAMING", fail_connect=False,
                 on_tick=None):
        now = [0]
        attempts = []
        listener = Mock(update_count=0)
        client = Mock()
        client.getStatus.return_value = status

        def connect():
            attempts.append(now[0])
            if fail_connect:
                raise OSError("server unavailable")

        def sleep(seconds):
            now[0] += seconds
            if on_tick:
                on_tick(now[0], listener, client)
            if now[0] >= duration:
                raise KeyboardInterrupt

        client.connect.side_effect = connect
        heartbeat = Mock()
        log = Mock()
        with patch("connection_retry.time.monotonic", side_effect=lambda: now[0]), \
             patch("connection_retry.time.sleep", side_effect=sleep):
            with self.assertRaises(KeyboardInterrupt):
                record_forever(client, listener, heartbeat, log)
        return attempts, heartbeat, log, client

    def test_silent_connected_stream_retries_for_days(self):
        attempts, heartbeat, _, _ = self.simulate(3 * 86400)
        self.assertGreater(len(attempts), 30)
        self.assertEqual(attempts[0], 60)
        self.assertEqual(attempts[-1] - attempts[-2], 300)
        self.assertLess(3 * 86400 - attempts[-1], 310)
        self.assertEqual(heartbeat.call_count, 3 * 8640)

    def test_startup_network_errors_never_exhaust_retries(self):
        attempts, _, log, _ = self.simulate(20000, "DISCONNECTED", True)
        self.assertEqual(attempts[:4], [0, 30, 90, 210])
        self.assertGreater(len(attempts), 30)
        self.assertTrue(any("server unavailable" in c.args[0] for c in log.call_args_list))

    def test_sdk_recovery_gets_time_before_forced_reconnect(self):
        attempts, _, _, _ = self.simulate(60, "DISCONNECTED:WILL-RETRY")
        self.assertEqual(attempts, [])

    def test_updates_reset_backoff_and_recording_continues(self):
        def tick(now, listener, client):
            if 1000 <= now <= 1200:
                listener.update_count += 1

        attempts, _, log, _ = self.simulate(1400, on_tick=tick)
        self.assertFalse(any(1000 <= t <= 1200 for t in attempts))
        self.assertEqual([t for t in attempts if t > 1200][:3], [1260, 1290, 1350])
        self.assertTrue(any("Telemetry resumed" in c.args[0] for c in log.call_args_list))

    def test_status_exception_does_not_end_recording(self):
        def tick(now, listener, client):
            client.getStatus.side_effect = OSError("temporary failure") if now < 100 else None

        attempts, _, log, _ = self.simulate(200, on_tick=tick)
        self.assertTrue(attempts)
        self.assertTrue(any("temporary failure" in c.args[0] for c in log.call_args_list))


class HealthcheckTests(unittest.TestCase):
    def test_missing_fresh_and_stale_heartbeat(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch.dict(os.environ, {"RAW_FOLDER": folder}), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(healthcheck.main(), 1)
            ready = Path(folder) / ".ready"
            ready.write_text("alive")
            self.assertEqual(healthcheck.main(), 0)
            os.utime(ready, (1, 1))
            self.assertEqual(healthcheck.main(), 1)


if __name__ == "__main__":
    unittest.main()
