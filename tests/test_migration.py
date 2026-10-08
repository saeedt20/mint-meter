"""Rename compatibility using isolated XDG directories and fixture state."""
from datetime import date
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tallydesklet import autostart
from tallydesklet.config import ConfigStore, DEFAULTS
from tallydesklet.usage import UsageStore


class RenameMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        env = patch.dict(os.environ, {"XDG_CONFIG_HOME": self.temp.name,
                                     "XDG_STATE_HOME": self.temp.name})
        env.start()
        self.addCleanup(env.stop)
        self.today = date(2026, 10, 8)

    def legacy(self, name, data):
        path = self.home / "mint-meter" / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(data)
        return path

    def test_preferences_import_once_without_changing_original(self):
        data = json.dumps({"appearance": {"theme": "light"},
                           "window": {"position": [50, 70], "locked": True}}).encode()
        original = self.legacy("config.json", data)
        store = ConfigStore()
        config = store.load()
        self.assertEqual(config["appearance"]["theme"], "light")
        self.assertEqual(config["window"]["position"], [50, 70])
        self.assertTrue(config["window"]["locked"])
        self.assertEqual(store.path.stat().st_mode & 0o777, 0o600)
        config["appearance"]["theme"] = "dark"
        store.save(config)
        self.assertEqual(ConfigStore().load()["appearance"]["theme"], "dark")
        self.assertEqual(original.read_bytes(), data)

    def test_usage_import_preserves_totals_and_restart_baseline(self):
        data = json.dumps({"schema_version": 1, "started_on": "2026-10-04",
                           "days": {"2026-10-07": 250, "2026-10-08": 100}}).encode()
        original = self.legacy("usage.json", data)
        store = UsageStore()
        tracker = store.load(self.today)
        self.assertEqual(tracker.totals(self.today).daily, 100)
        self.assertEqual(tracker.totals(self.today).weekly, 350)
        self.assertEqual(tracker.started_on, "2026-10-04")
        self.assertIsNone(tracker.previous)
        self.assertEqual(store.path.stat().st_mode & 0o777, 0o600)
        tracker.days[self.today.isoformat()] += 75
        store.save(tracker)
        self.assertEqual(UsageStore().load(self.today).totals(self.today).daily, 175)
        self.assertEqual(original.read_bytes(), data)

    def test_corrupt_legacy_files_preserved_in_both_locations(self):
        for name, store in (("config.json", ConfigStore()), ("usage.json", UsageStore())):
            original = self.legacy(name, b"\xff{bad json")
            result = store.load() if name == "config.json" else store.load(self.today)
            if name == "config.json":
                self.assertEqual(result, DEFAULTS)
            else:
                self.assertEqual(result.totals(self.today).daily, 0)
            self.assertIsNotNone(store.notice)
            backup = list(store.path.parent.glob(name.split('.')[0] + ".broken-*.json"))
            self.assertEqual(len(backup), 1)
            self.assertEqual(backup[0].read_bytes(), original.read_bytes())

    def test_failed_import_preserves_source_and_does_not_create_new_file(self):
        original = self.legacy("config.json", b'{"appearance":{"theme":"light"}}')
        before = original.read_bytes()
        store = ConfigStore()
        with patch("tallydesklet.config.os.replace", side_effect=OSError("fixture failure")):
            with self.assertRaises(OSError):
                store.load()
        self.assertFalse(store.path.exists())
        self.assertEqual(original.read_bytes(), before)
        self.assertEqual(list(store.path.parent.iterdir()), [])

    def test_explicit_paths_do_not_import_legacy_state(self):
        self.legacy("config.json", b'{"appearance":{"theme":"light"}}')
        self.legacy("usage.json", b'{bad json')
        config = ConfigStore(self.home / "isolated/config.json")
        usage = UsageStore(self.home / "isolated/usage.json")
        self.assertEqual(config.load(), DEFAULTS)
        self.assertEqual(usage.load(self.today).totals(self.today).daily, 0)
        self.assertFalse((self.home / "isolated").exists())

    def test_legacy_startup_choice_is_read_without_writes(self):
        legacy = self.home / "autostart/mint-meter.desktop"
        legacy.parent.mkdir()
        for hidden in ("false", "true"):
            data = f"[Desktop Entry]\nExec=/usr/bin/mint-meter\nHidden={hidden}\n"
            legacy.write_text(data)
            self.assertEqual(autostart.enabled(), hidden == "false")
            self.assertEqual(legacy.read_text(), data)
            self.assertFalse(autostart.entry_path().exists())
        autostart.entry_path().write_text("[Desktop Entry]\nExec=tallydesklet\nHidden=false\n")
        self.assertTrue(autostart.enabled())
        autostart.set_enabled(False)
        self.assertFalse(legacy.exists())
        self.assertFalse(autostart.entry_path().exists())

    def test_explicit_enable_replaces_legacy_entry_and_missing_launcher_keeps_it(self):
        legacy = self.home / "autostart/mint-meter.desktop"
        legacy.parent.mkdir()
        legacy.write_text("[Desktop Entry]\nExec=mint-meter\nHidden=false\n")
        executable = self.home / "tallydesklet"
        with self.assertRaises(ValueError):
            autostart.set_enabled(True, executable=executable)
        self.assertTrue(legacy.exists())
        self.assertFalse(autostart.entry_path().exists())
        executable.touch()
        autostart.set_enabled(True, executable=executable)
        self.assertTrue(autostart.enabled())
        self.assertFalse(legacy.exists())


if __name__ == "__main__":
    unittest.main()
