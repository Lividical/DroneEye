# log.py
import time
import threading
from dataclasses import dataclass, asdict

@dataclass
class CoordEntry:
    ts: str
    x: int
    y: int

class CoordLog:
    """
    Rolling log of (x,y) changes for a window (default 24h).
    - Ignores (-1,-1)
    - Logs only when coords change
    - Auto-resets every reset_seconds
    - Thread-safe
    """
    def __init__(self, reset_seconds: int = 86400, max_entries: int = 20000):
        self.reset_seconds = int(reset_seconds)
        self.max_entries = int(max_entries)

        self._lock = threading.Lock()
        self._window_start_epoch = time.time()
        self._entries: list[CoordEntry] = []
        self._last_xy: tuple[int, int] | None = None

    def _fmt_ts(self, t: float) -> str:
        # Uses system local time on the Pi
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))

    def _maybe_rollover(self, now: float) -> None:
        if (now - self._window_start_epoch) >= self.reset_seconds:
            self._window_start_epoch = now
            self._entries.clear()
            self._last_xy = None

    def update(self, x: int, y: int) -> bool:
        """
        Add an entry if valid and changed.
        Returns True if logged, False otherwise.
        """
        try:
            x = int(x)
            y = int(y)
        except Exception:
            return False

        if x == -1 or y == -1:
            return False

        now = time.time()
        with self._lock:
            self._maybe_rollover(now)

            if self._last_xy == (x, y):
                return False

            self._last_xy = (x, y)
            self._entries.append(CoordEntry(ts=self._fmt_ts(now), x=x, y=y))

            # clamp memory
            if len(self._entries) > self.max_entries:
                extra = len(self._entries) - self.max_entries
                if extra > 0:
                    del self._entries[:extra]

            return True

    def clear(self) -> None:
        now = time.time()
        with self._lock:
            self._window_start_epoch = now
            self._entries.clear()
            self._last_xy = None

    def get_window_start(self) -> str:
        with self._lock:
            return self._fmt_ts(self._window_start_epoch)

    def get_entries(self) -> list[dict]:
        with self._lock:
            return [asdict(e) for e in self._entries]
