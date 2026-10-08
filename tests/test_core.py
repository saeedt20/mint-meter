import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace as NS
import tempfile
import unittest
from unittest.mock import patch

from tallydesklet import autostart
from tallydesklet.config import ConfigStore, DEFAULTS, validate
from tallydesklet.formatting import capacity, quantity
from tallydesklet.history import GraphScale, History
from tallydesklet.metrics import disk_capacity, memory_capacity
from tallydesklet.network import RateSampler, choose_interface, route_candidates
from tallydesklet.position import place


class CapacityTests(unittest.TestCase):
    def test_memory_uses_available(self):
        result = memory_capacity(NS(total=1000, available=600, used=700))
        self.assertEqual((result.used, result.total, result.available), (400, 1000, 600))
        self.assertEqual(result.fraction, .4)

    def test_disk_reserved_blocks(self):
        result = disk_capacity("/example", lambda path: NS(total=1000, used=500, free=400, percent=56))
        self.assertEqual(result.fraction, .5)
        self.assertEqual(result.available, 400)

    def test_missing_disk(self):
        def unavailable(path):
            raise FileNotFoundError(path)
        self.assertIsNone(disk_capacity("/missing", unavailable))


class FormattingTests(unittest.TestCase):
    def test_units(self):
        self.assertEqual(quantity(10**9), "1.0 GB")
        self.assertEqual(quantity(1024**3, True), "1.0 GiB")
        self.assertEqual(quantity(420000, rate=True), "420 KB/s")
        self.assertEqual(quantity(1024**2, True, True), "1.0 MiB/s")

    def test_boundaries(self):
        self.assertEqual(quantity(0, rate=True), "0 B/s")
        self.assertEqual(quantity(None), "—")
        self.assertEqual(quantity(10**18), "1000 PB")
        self.assertEqual(capacity(6200000000, 16000000000), "6.2 / 16.0 GB")


class NetworkTests(unittest.TestCase):
    def setUp(self):
        self.sampler = RateSampler()

    def sample(self, at, rx, tx=0, interface="eth0"):
        return self.sampler.sample(at, interface, NS(bytes_recv=rx, bytes_sent=tx))

    def test_warmup_and_elapsed(self):
        self.assertIsNone(self.sample(10, 100).down)
        rate = self.sample(12, 3100, 400)
        self.assertEqual((rate.down, rate.up), (1500, 200))
        self.assertEqual(self.sample(13, 3100, 400).down, 0)

    def test_counter_reset(self):
        self.sample(10, 200)
        self.assertIsNone(self.sample(11, 100).down)
        self.assertEqual(self.sample(12, 300).down, 200)

    def test_switch_and_resume(self):
        self.sample(1, 0)
        self.assertIsNone(self.sample(2, 10000, interface="tun0").down)
        self.assertIsNone(self.sample(50, 100000, interface="tun0").down)
        self.assertEqual(self.sample(51, 100100, interface="tun0").down, 100)

    def test_nonpositive_time(self):
        self.sample(10, 0)
        self.assertIsNone(self.sample(10, 100).down)
        self.assertIsNone(self.sample(9, 200).down)

    def test_disconnect_and_removal(self):
        self.sample(1, 0)
        self.assertEqual(self.sampler.sample(2, None, None).status, "Offline")
        self.assertIsNone(self.sample(3, 100000).down)
        self.assertEqual(self.sampler.sample(4, "eth0", None).status, "Unavailable")

    def test_routed_vpn_and_override(self):
        stats = {name: NS(isup=True) for name in ("lo", "eth0", "tun0", "wlan0")}
        self.assertEqual(choose_interface(["lo", "tun0", "eth0"], stats), ("tun0", "Ready"))
        self.assertEqual(choose_interface(["tun0"], stats, "eth0"), ("eth0", "Ready"))
        self.assertEqual(choose_interface([], stats), (None, "Offline"))
        self.assertEqual(choose_interface(None, stats), (None, "Unavailable"))
        self.assertEqual(choose_interface([], stats, "removed"), (None, "Unavailable"))
        stats["eth0"].isup = False
        self.assertEqual(choose_interface([], stats, "eth0"), (None, "Offline"))

    def test_routes_ipv4_ipv6_and_safe_arguments(self):
        calls = []
        def runner(args, **kwargs):
            calls.append(args)
            self.assertNotIn("shell", kwargs)
            return NS(returncode=0, stdout=json.dumps([{"dev": "tun0" if "-4" in args else "eth0"}]), stderr="")
        self.assertEqual(route_candidates(runner), ["tun0", "eth0"])
        self.assertEqual(len(calls), 2)

    def test_ipv6_only_and_unavailable(self):
        def runner(args, **kwargs):
            return NS(returncode=2, stderr="Network is unreachable") if "-4" in args else NS(returncode=0, stdout='[{"dev":"eth0"}]')
        self.assertEqual(route_candidates(runner), ["eth0"])
        def missing(*args, **kwargs):
            raise FileNotFoundError()
        self.assertIsNone(route_candidates(missing))


class HistoryTests(unittest.TestCase):
    def test_interval_changes_and_eviction(self):
        h = History()
        for at in range(121):
            h.append(at / 2, at)
        self.assertEqual(len(h.points), 121)
        h.append(65, 2)
        self.assertEqual(h.points[0][0], 5)
        h.append(200, None)
        self.assertEqual(list(h.points), [(200, None)])

    def test_scale_floor_rise_and_decay(self):
        scale = GraphScale()
        self.assertEqual(scale.update(0, 1), 1000)
        high = scale.update(100000, 1)
        lower = scale.update(0, 1)
        self.assertGreater(lower, 1000)
        self.assertLess(lower, high)


class ConfigTests(unittest.TestCase):
    def test_bounds_and_types(self):
        config = validate({"appearance": {"scale": 99, "theme": "invalid", "background_opacity": float("nan"), "accent_color": "red"},
                           "sampling": {"interval_seconds": -1}, "window": {"locked": "false", "position": [-1920, 30]}})
        self.assertEqual(config["appearance"]["scale"], 2)
        self.assertEqual(config["appearance"]["theme"], "dark")
        self.assertEqual(config["appearance"]["background_opacity"], .9)
        self.assertEqual(config["sampling"]["interval_seconds"], 1)
        self.assertFalse(config["window"]["locked"])
        self.assertEqual(config["window"]["position"], [-1920, 30])
        self.assertIsNone(validate({"window": {"position": [True, 0]}})["window"]["position"])

    def test_independent_defaults(self):
        c = validate({})
        c["window"]["locked"] = True
        self.assertFalse(DEFAULTS["window"]["locked"])
        self.assertEqual(validate([]), DEFAULTS)

    def test_roundtrip_atomic_private_and_recovery(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "tallydesklet/config.json"
            store = ConfigStore(path)
            self.assertEqual(store.load(), DEFAULTS)
            config = copy.deepcopy(DEFAULTS)
            config["window"]["position"] = [-100, 25]
            store.save(config)
            self.assertEqual(store.load(), config)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            path.write_text("{bad data")
            self.assertEqual(store.load(), DEFAULTS)
            self.assertEqual(len(list(path.parent.glob("config.broken-*.json"))), 1)
            self.assertIsNotNone(store.notice)

    def test_atomic_failure_preserves_previous(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ConfigStore(Path(temp) / "config.json")
            store.save(DEFAULTS)
            before = store.path.read_bytes()
            with patch("tallydesklet.config.os.replace", side_effect=OSError("test failure")):
                with self.assertRaises(OSError):
                    store.save(DEFAULTS)
            self.assertEqual(store.path.read_bytes(), before)
            self.assertEqual(len(list(Path(temp).iterdir())), 1)


class PositionTests(unittest.TestCase):
    def test_default_workarea(self):
        self.assertEqual(place((0, 30, 1920, 1050), (320, 310)), (1576, 54))

    def test_negative_monitor(self):
        self.assertEqual(place((-1920, -200, 1920, 1080), (320, 310), [-2100, -300]), (-1920, -200))

    def test_removed_monitor_and_tiny_display(self):
        self.assertEqual(place((0, 0, 1920, 1080), (320, 310), [-1900, 20]), (0, 20))
        self.assertEqual(place((0, 0, 200, 200), (320, 310)), (0, 0))


class AutostartTests(unittest.TestCase):
    def test_opt_in_roundtrip_and_disabled_state(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"XDG_CONFIG_HOME": temp}):
            executable = Path(temp) / "tallydesklet"
            executable.touch()
            self.assertFalse(autostart.enabled())
            autostart.set_enabled(True, executable=executable)
            self.assertTrue(autostart.enabled())
            text = autostart.entry_path().read_text().replace("Hidden=false", "Hidden=true")
            autostart.entry_path().write_text(text)
            self.assertFalse(autostart.enabled())
            autostart.set_enabled(False)
            self.assertFalse(autostart.entry_path().exists())

    def test_missing_installed_executable(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                autostart.set_enabled(True, Path(temp) / "entry", Path(temp) / "missing")


if __name__ == "__main__":
    unittest.main()
