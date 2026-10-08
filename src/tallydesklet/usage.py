"""Bounded calendar usage accounting and XDG state; independent of GTK."""
from dataclasses import dataclass
from datetime import date, timedelta
import json
import os
from pathlib import Path
import time

from .config import atomic_write, import_legacy_file


@dataclass(frozen=True)
class UsageTotals:
    daily: int | None
    weekly: int | None
    started_on: str | None = None
    notice: str | None = None


class UsageTracker:
    def __init__(self, today, days=None, started_on=None):
        self.days = dict(days or {})
        self.started_on = started_on or today.isoformat()
        self.previous = None  # Never restore counter baselines across app restarts.
        self.revision = 0
        self._advance(today)

    def _advance(self, today):
        first = (today - timedelta(days=6)).isoformat()
        last = today.isoformat()
        days = {key: value for key, value in self.days.items() if first <= key <= last}
        days.setdefault(last, 0)
        if days != self.days:
            self.days = days
            self.revision += 1

    def observe(self, now, today, interface, counters):
        self._advance(today)
        if interface is None or counters is None:
            self.previous = None
            return
        current = (now, interface, counters.bytes_recv, counters.bytes_sent)
        previous, self.previous = self.previous, current
        if previous is None or previous[1] != interface:
            return
        elapsed = now - previous[0]
        down, up = current[2] - previous[2], current[3] - previous[3]
        # Ambiguous resets, reconnects and resume gaps never add estimated traffic.
        if elapsed <= 0 or elapsed > 15 or down < 0 or up < 0:
            return
        if down + up:
            self.days[today.isoformat()] += down + up
            self.revision += 1

    def totals(self, today, notice=None):
        # Python weekdays start on Monday (0); our calendar week starts Sunday (6).
        sunday = (today - timedelta(days=(today.weekday() + 1) % 7)).isoformat()
        day = today.isoformat()
        return UsageTotals(self.days.get(day, 0),
                           sum(value for key, value in self.days.items() if sunday <= key <= day),
                           self.started_on, notice)

    def document(self):
        return {"schema_version": 1, "started_on": self.started_on, "days": self.days}


class UsageStore:
    def __init__(self, path=None):
        value = os.environ.get("XDG_STATE_HOME", "")
        home = Path(value) if value.startswith("/") else Path.home() / ".local/state"
        self.path = Path(path) if path else home / "tallydesklet/usage.json"
        self.legacy = None if path else home / "mint-meter/usage.json"
        self.notice = None

    def load(self, today):
        import_legacy_file(self.path, self.legacy)
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or raw.get("schema_version") != 1:
                raise ValueError("Invalid usage schema")
            started = raw["started_on"]
            if not isinstance(started, str) or date.fromisoformat(started).isoformat() != started:
                raise ValueError("Invalid start date")
            days = raw["days"]
            if not isinstance(days, dict) or len(days) > 7:
                raise ValueError("Invalid daily buckets")
            for day, total in days.items():
                if (date.fromisoformat(day).isoformat() != day or
                        type(total) is not int or total < 0):
                    raise ValueError("Invalid daily total")
            return UsageTracker(today, days, started)
        except FileNotFoundError:
            return UsageTracker(today)
        except (ValueError, UnicodeError, KeyError, TypeError):
            backup = self.path.with_name(f"usage.broken-{time.time_ns()}.json")
            self.path.rename(backup)
            self.notice = f"Invalid usage history preserved as {backup.name}; tracking restarted."
            return UsageTracker(today)

    def save(self, tracker):
        atomic_write(self.path, json.dumps(tracker.document(), indent=2, allow_nan=False) + "\n")
