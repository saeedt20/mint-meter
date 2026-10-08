"""Metric collection in one worker thread; no GTK imports or UI-thread I/O."""
from dataclasses import dataclass
from datetime import date
import copy
import queue
import threading
import time

import psutil

from .network import Rate, RateSampler, choose_interface, route_candidates
from .usage import UsageStore, UsageTotals


def monotonic_time():
    # BOOTTIME is monotonic and includes suspend on Linux, so resume gaps reset.
    return time.clock_gettime(time.CLOCK_BOOTTIME) if hasattr(time, "CLOCK_BOOTTIME") else time.monotonic()


@dataclass(frozen=True)
class Capacity:
    used: int
    total: int
    available: int

    @property
    def fraction(self):
        return max(0, min(1, self.used / self.total)) if self.total else 0


def memory_capacity(memory):
    return Capacity(memory.total - memory.available, memory.total, memory.available)


def disk_capacity(path, provider=psutil.disk_usage):
    try:
        usage = provider(path)
        return Capacity(usage.used, usage.total, usage.free)
    except (OSError, ValueError):
        return None


@dataclass(frozen=True)
class Sample:
    time: float
    cpu: float | None
    ram: Capacity | None
    disk: Capacity | None
    network: Rate
    interfaces: tuple
    generation: int
    usage: UsageTotals


class Collector:
    def __init__(self, config):
        self.lock = threading.Lock()
        self.config = copy.deepcopy(config)
        self.generation = 0
        self.stop_event = threading.Event()
        self.wake = threading.Event()
        self.results = queue.Queue(maxsize=1)
        self.thread = threading.Thread(target=self._run, name="tallydesklet-sampler", daemon=True)

    def start(self):
        self.thread.start()

    def configure(self, config):
        with self.lock:
            self.config = copy.deepcopy(config)
            self.generation += 1
        self.wake.set()

    def stop(self):
        self.stop_event.set()
        self.wake.set()
        self.thread.join(timeout=2.5)

    def _run(self):
        store = UsageStore()
        try:
            usage = store.load(date.today())
        except OSError as error:
            usage = None
            store.notice = f"Usage history could not be read: {error}"
        self.usage_saved_revision = -1
        try:
            self._collect(store, usage)
        finally:
            if usage is not None and usage.revision != self.usage_saved_revision:
                self._save_usage(store, usage)

    def _save_usage(self, store, usage):
        try:
            store.save(usage)
            self.usage_saved_revision = usage.revision
            if store.notice and store.notice.startswith("Usage totals could not be saved:"):
                store.notice = None
        except OSError as error:
            store.notice = f"Usage totals could not be saved: {error}"

    def _collect(self, store, usage):
        rates = RateSampler()
        disk = None
        disk_at = routes_at = float("-inf")
        last_time = None
        generation = -1
        routes = None
        usage_saved_at = float("-inf")
        while not self.stop_event.is_set():
            self.wake.clear()
            with self.lock:
                config, current_generation = copy.deepcopy(self.config), self.generation
            now = monotonic_time()
            warm = last_time is None or now - last_time > 15
            if generation != current_generation:
                generation = current_generation
                disk_at = routes_at = float("-inf")
                rates = RateSampler()
            try:
                cpu = psutil.cpu_percent(interval=None)
                cpu = None if warm else max(0, min(100, cpu))
            except (OSError, psutil.Error):
                cpu = None
            try:
                ram = memory_capacity(psutil.virtual_memory())
            except (OSError, psutil.Error):
                ram = None
            if now - disk_at >= 10:
                disk = disk_capacity(config["disk"]["path"])
                disk_at = now
            try:
                stats = psutil.net_if_stats()
                if now - routes_at >= 5 or warm:
                    routes = route_candidates()
                    routes_at = now
                interface, status = choose_interface(routes, stats, config["network"]["interface"])
                # Match counter capture and its timestamp, after slow route inspection.
                counters = psutil.net_io_counters(pernic=True, nowrap=False)
                network_at = monotonic_time()
                selected_counters = counters.get(interface)
                rate = rates.sample(network_at, interface, selected_counters, status)
                interfaces = tuple(sorted(stats))
            except (OSError, psutil.Error):
                rate = rates.sample(now, None, None, "Unavailable")
                interfaces = ()
                interface, selected_counters = None, None
                network_at = monotonic_time()
            today = date.today()
            if usage is not None:
                usage.observe(network_at, today, interface, selected_counters)
                if network_at - usage_saved_at >= 60:
                    if usage.revision != self.usage_saved_revision:
                        self._save_usage(store, usage)
                    usage_saved_at = network_at
                totals = usage.totals(today, store.notice)
            else:
                totals = UsageTotals(None, None, notice=store.notice)
            sample = Sample(now, cpu, ram, disk, rate, interfaces, generation, totals)
            try:
                self.results.get_nowait()
            except queue.Empty:
                pass
            self.results.put_nowait(sample)
            last_time = now
            delay = max(.1, config["sampling"]["interval_seconds"] - (monotonic_time() - now))
            self.wake.wait(delay)
