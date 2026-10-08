"""One routed interface, monotonic counter deltas, no probe traffic."""
from dataclasses import dataclass
import json
import subprocess


def route_candidates(runner=subprocess.run):
    """Ask the kernel, without sending packets. IPv4 wins, then IPv6.

    Route-get honors policy routing and VPN split defaults, unlike simply
    reading the main table's default route. Addresses are lookup keys only.
    """
    candidates = []
    succeeded = False
    for family, address in (("-4", "1.1.1.1"), ("-6", "2606:4700:4700::1111")):
        try:
            proc = runner(["/usr/sbin/ip", "-j", family, "route", "get", address],
                          capture_output=True, text=True, timeout=1, check=False)
            if proc.returncode == 0:
                rows = json.loads(proc.stdout)
                succeeded = True
                candidates.extend(row["dev"] for row in rows if row.get("dev"))
            elif "unreachable" in proc.stderr.lower():
                succeeded = True
        except (OSError, ValueError, subprocess.TimeoutExpired):
            continue
    return list(dict.fromkeys(candidates)) if succeeded else None


def choose_interface(candidates, stats, override="auto"):
    if override != "auto":
        if override not in stats:
            return None, "Unavailable"
        return (override, "Ready") if stats[override].isup else (None, "Offline")
    if candidates is None:
        return None, "Unavailable"
    for name in candidates:
        if name != "lo" and name in stats and stats[name].isup:
            return name, "Ready"
    return None, "Offline"


@dataclass(frozen=True)
class Rate:
    interface: str | None
    down: float | None = None
    up: float | None = None
    status: str = "Warming up"


class RateSampler:
    def __init__(self):
        self.previous = None

    def sample(self, now, interface, counters, status="Offline"):
        if interface is None or counters is None:
            self.previous = None
            return Rate(interface, status=status if interface is None else "Unavailable")
        current = (now, interface, counters.bytes_recv, counters.bytes_sent)
        previous, self.previous = self.previous, current
        if previous is None or previous[1] != interface:
            return Rate(interface)
        elapsed = now - previous[0]
        down, up = current[2] - previous[2], current[3] - previous[3]
        if elapsed <= 0 or elapsed > 15 or down < 0 or up < 0:
            return Rate(interface)
        return Rate(interface, down / elapsed, up / elapsed, "Ready")
