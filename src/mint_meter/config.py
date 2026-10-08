"""Validated XDG preferences and atomic, private persistence."""
import copy
import json
import math
import os
from pathlib import Path
import re
import tempfile
import time

DEFAULTS = {
    "schema_version": 1,
    "appearance": {"theme": "dark", "background_opacity": .9, "scale": 1.0,
                   "accent_color": "#5FE3AF", "units": "decimal"},
    "sampling": {"interval_seconds": 1.0, "history_seconds": 60, "disk_interval_seconds": 10},
    "network": {"interface": "auto"}, "disk": {"path": "/"},
    "window": {"monitor": "primary", "anchor": "top-right", "margin": 24,
               "position": None, "locked": False, "always_on_top": False, "all_workspaces": True},
}


def config_home():
    value = os.environ.get("XDG_CONFIG_HOME", "")
    return Path(value) if value.startswith("/") else Path.home() / ".config"


def validate(raw):
    result = copy.deepcopy(DEFAULTS)
    if not isinstance(raw, dict):
        return result
    for group, defaults in DEFAULTS.items():
        if not isinstance(defaults, dict) or not isinstance(raw.get(group), dict):
            continue
        for key, default in defaults.items():
            value = raw[group].get(key, default)
            if type(value) is type(default):
                result[group][key] = value
            elif isinstance(default, float) and type(value) in (int, float):
                result[group][key] = float(value)
    a, s, w = result["appearance"], result["sampling"], result["window"]
    for key, low, high in (("background_opacity", .35, 1), ("scale", .75, 2)):
        a[key] = max(low, min(high, a[key])) if math.isfinite(a[key]) else DEFAULTS["appearance"][key]
    if a["theme"] not in ("dark", "light"):
        a["theme"] = "dark"
    if a["units"] not in ("decimal", "binary"):
        a["units"] = "decimal"
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", a["accent_color"]):
        a["accent_color"] = DEFAULTS["appearance"]["accent_color"]
    if s["interval_seconds"] not in (.5, 1, 2, 5):
        s["interval_seconds"] = 1.0
    s["history_seconds"], s["disk_interval_seconds"] = 60, 10
    w["margin"] = max(0, min(200, w["margin"]))
    w["anchor"] = "top-right"
    pos = raw.get("window", {}).get("position") if isinstance(raw.get("window"), dict) else None
    w["position"] = pos if (isinstance(pos, list) and len(pos) == 2 and
                                  all(type(v) is int and abs(v) < 100000 for v in pos)) else None
    if not result["disk"]["path"].startswith("/"):
        result["disk"]["path"] = "/"
    if not result["network"]["interface"] or len(result["network"]["interface"]) > 128:
        result["network"]["interface"] = "auto"
    return result


def atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".mint-meter-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


class ConfigStore:
    def __init__(self, path=None):
        self.path = Path(path) if path else config_home() / "mint-meter/config.json"
        self.notice = None

    def load(self):
        try:
            raw = json.loads(self.path.read_text())
            if not isinstance(raw, dict) or raw.get("schema_version", 1) != 1:
                raise ValueError("Unsupported configuration schema")
            return validate(raw)
        except FileNotFoundError:
            return validate({})
        except (ValueError, UnicodeError):
            backup = self.path.with_name(f"config.broken-{time.time_ns()}.json")
            self.path.rename(backup)
            self.notice = f"Invalid preferences preserved as {backup.name}; defaults loaded."
            return validate({})

    def save(self, config):
        atomic_write(self.path, json.dumps(validate(config), indent=2, allow_nan=False) + "\n")
