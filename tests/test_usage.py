from datetime import date, timedelta
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from mint_meter.config import DEFAULTS
from mint_meter.metrics import Collector
from mint_meter.usage import UsageStore, UsageTracker


THURSDAY = date(2026, 10, 8)


class UsageTests(unittest.TestCase):
    def observe(self, tracker, at, down, up=0, day=THURSDAY, interface="eth0"):
        tracker.observe(at, day, interface, NS(bytes_recv=down, bytes_sent=up))

    def test_combines_counter_deltas_and_idle(self):
        tracker = UsageTracker(THURSDAY)
        self.observe(tracker, 1, 100000, 20000)
        self.assertEqual(tracker.totals(THURSDAY).daily, 0)
        self.observe(tracker, 2, 103000, 21000)
        self.observe(tracker, 3, 103000, 21000)
        totals = tracker.totals(THURSDAY)
        self.assertEqual((totals.daily, totals.weekly), (4000, 4000))

    def test_midnight_and_sunday_reset(self):
        saturday = date(2026, 10, 10)
        sunday = saturday + timedelta(days=1)
        monday = sunday + timedelta(days=1)
        tracker = UsageTracker(saturday)
        self.observe(tracker, 1, 0, day=saturday)
        self.observe(tracker, 2, 100, day=saturday)
        self.observe(tracker, 3, 130, day=sunday)
        self.assertEqual((tracker.totals(sunday).daily, tracker.totals(sunday).weekly), (30, 30))
        self.observe(tracker, 4, 150, day=monday)
        self.assertEqual((tracker.totals(monday).daily, tracker.totals(monday).weekly), (20, 50))

    def test_offline_rollover_keeps_weekly_total(self):
        tracker = UsageTracker(THURSDAY)
        self.observe(tracker, 1, 0)
        self.observe(tracker, 2, 50)
        friday = THURSDAY + timedelta(days=1)
        tracker.observe(3, friday, None, None)
        self.assertEqual((tracker.totals(friday).daily, tracker.totals(friday).weekly), (0, 50))

    def test_switch_disconnect_and_counter_reset(self):
        tracker = UsageTracker(THURSDAY)
        self.observe(tracker, 1, 0)
        self.observe(tracker, 2, 100)
        self.observe(tracker, 3, 999999, interface="tun0")
        self.observe(tracker, 4, 1000009, interface="tun0")
        tracker.observe(5, THURSDAY, None, None)
        self.observe(tracker, 6, 9999999)
        self.observe(tracker, 7, 0)
        self.observe(tracker, 8, 20)
        self.assertEqual(tracker.totals(THURSDAY).daily, 130)

    def test_resume_and_nonpositive_intervals_never_add(self):
        tracker = UsageTracker(THURSDAY)
        for at, value in ((1, 0), (20, 1000000), (20, 2000000), (19, 3000000)):
            self.observe(tracker, at, value)
        self.observe(tracker, 20, 3000010)
        self.assertEqual(tracker.totals(THURSDAY).daily, 10)

    def test_retains_at_most_seven_daily_buckets(self):
        tracker = UsageTracker(THURSDAY)
        for offset in range(100):
            tracker.observe(offset, THURSDAY + timedelta(days=offset), None, None)
        self.assertEqual(len(tracker.days), 7)
        self.assertEqual(min(tracker.days), (THURSDAY + timedelta(days=93)).isoformat())


class UsageStoreTests(unittest.TestCase):
    def test_xdg_path_atomic_private_restart_and_closed_traffic(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"XDG_STATE_HOME": temp}):
            store = UsageStore()
            self.assertEqual(store.path, Path(temp) / "mint-meter/usage.json")
            tracker = store.load(THURSDAY)
            tracker.observe(1, THURSDAY, "eth0", NS(bytes_recv=100, bytes_sent=0))
            tracker.observe(2, THURSDAY, "eth0", NS(bytes_recv=150, bytes_sent=10))
            store.save(tracker)
            self.assertEqual(store.path.stat().st_mode & 0o777, 0o600)
            restored = store.load(THURSDAY)
            restored.observe(3, THURSDAY, "eth0", NS(bytes_recv=999999, bytes_sent=0))
            self.assertEqual(restored.totals(THURSDAY).daily, 60)
            restored.observe(4, THURSDAY, "eth0", NS(bytes_recv=1000099, bytes_sent=0))
            self.assertEqual(restored.totals(THURSDAY).daily, 160)

    def test_corrupt_history_preserved_and_tracking_restarted(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "usage.json"
            for invalid in ('{broken', '{"schema_version":1,"started_on":"2026-10-08","days":{"2026-10-08":-10}}'):
                path.write_text(invalid)
                store = UsageStore(path)
                self.assertEqual(store.load(THURSDAY).totals(THURSDAY).daily, 0)
                self.assertTrue(store.notice)
            self.assertEqual(len(list(Path(temp).glob("usage.broken-*.json"))), 2)

    def test_atomic_failure_preserves_saved_totals(self):
        with tempfile.TemporaryDirectory() as temp:
            store = UsageStore(Path(temp) / "usage.json")
            tracker = store.load(THURSDAY)
            store.save(tracker)
            before = store.path.read_bytes()
            with patch("mint_meter.config.os.replace", side_effect=OSError("failed save")):
                with self.assertRaises(OSError):
                    store.save(tracker)
            self.assertEqual(store.path.read_bytes(), before)


class CollectorUsageTests(unittest.TestCase):
    def collect(self, store, clock, stop_after, routes):
        collector = Collector(DEFAULTS)
        samples = []

        def wait(delay):
            samples.append(collector.results.get_nowait())
            if len(samples) == stop_after:
                collector.stop_event.set()
            else:
                clock[0] = [2., 3.][len(samples)-1]

        collector.wake.wait = wait
        with patch("mint_meter.metrics.UsageStore", return_value=store), \
             patch("mint_meter.metrics.monotonic_time", side_effect=lambda: clock[0]), \
             patch("mint_meter.metrics.psutil.cpu_percent", return_value=10), \
             patch("mint_meter.metrics.psutil.virtual_memory", return_value=NS(total=1000, available=500)), \
             patch("mint_meter.metrics.disk_capacity", return_value=None), \
             patch("mint_meter.metrics.psutil.net_if_stats", return_value={"eth0": NS(isup=True)}), \
             patch("mint_meter.metrics.psutil.net_io_counters", side_effect=lambda **kw: {
                 "eth0": NS(bytes_recv=int(clock[0]*1000), bytes_sent=0)}), \
             patch("mint_meter.metrics.route_candidates", side_effect=routes):
            collector._run()
        return samples

    def test_route_delay_rates_and_shutdown_usage_flush(self):
        clock = [0.]

        def routes():
            clock[0] += 1
            return ["eth0"]

        with tempfile.TemporaryDirectory() as temp:
            store = UsageStore(Path(temp) / "usage.json")
            with patch.object(store, "save", wraps=store.save) as save:
                samples = self.collect(store, clock, 3, routes)
            self.assertEqual(save.call_count, 2)  # Initial checkpoint and final flush, not each sample.
            self.assertEqual([s.network.down for s in samples], [None, 1000, 1000])
            self.assertEqual(samples[-1].usage.daily, 2000)
            self.assertEqual(sum(json.loads(store.path.read_text())["days"].values()), 2000)

    def test_unreadable_history_is_unavailable_and_not_overwritten(self):
        store = NS(load=lambda day: (_ for _ in ()).throw(PermissionError("unreadable")), notice=None)
        samples = self.collect(store, [0.], 1, lambda: ["eth0"])
        self.assertIsNone(samples[0].usage.daily)
        self.assertIn("could not be read", samples[0].usage.notice)
        self.assertEqual(samples[0].network.status, "Warming up")

    def test_save_failure_keeps_live_totals_and_reports_notice(self):
        with tempfile.TemporaryDirectory() as temp:
            store = UsageStore(Path(temp) / "usage.json")
            with patch.object(store, "save", side_effect=OSError("disk full")):
                samples = self.collect(store, [0.], 3, lambda: ["eth0"])
            self.assertEqual(samples[-1].usage.daily, 3000)
            self.assertIn("could not be saved", samples[-1].usage.notice)


if __name__ == "__main__":
    unittest.main()
