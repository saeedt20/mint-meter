"""Time-based, bounded metric histories, independent of GTK."""
from collections import deque


class History:
    def __init__(self, seconds=60):
        self.seconds = seconds
        self.points = deque(maxlen=256)

    def append(self, now, value):
        self.points.append((now, value))
        self.evict(now)

    def evict(self, now):
        while self.points and self.points[0][0] < now - self.seconds:
            self.points.popleft()


class GraphScale:
    def __init__(self, floor=1000):
        self.floor = floor
        self.value = float(floor)

    def update(self, peak, elapsed):
        target = max(self.floor, peak * 1.15)
        # Rise immediately to avoid clipping; decay with a 10-second time constant.
        if target >= self.value:
            self.value = target
        else:
            self.value = max(target, self.value * 0.9 ** max(0, elapsed))
        return self.value
