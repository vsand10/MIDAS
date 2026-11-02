# Helpers for talking to Yahoo Finance through yfinance

import threading 
import time 
from collections.abc import Callable
from typing import Any

class DataUnavailableError(Exception):
    """Raised when data is not available from Yahoo Finance."""

def call_yfinance(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Run yfinance call and turn failures into DataUnavailableError.
        yfinance is unofficial and can fail in many ways, so we catch all exceptions and raise DataUnavailableError.
    """
    try:
        return fn(*args, **kwargs)
    except Exception as err:
        raise DataUnavailableError(str(err)) from err


class TTLCache:
    """A simple TTL (Time-To-Live) cache so repeated requests skip Yahoo
        If refresh fails, last good result is used for up to 'stale_seconds'
    """
    def __init__(self, max_items: int = 256, stale_seconds: float = 3600) -> None:
        self._items: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()
        self._max_items = max_items
        self._stale_seconds = stale_seconds

    def get_or_fetch(self, key: str, ttl_seconds: float, fetch: Callable[[], Any]) -> Any:
        with self._lock:
            hit = self._items.get(key)
        if hit and time.monotonic() - hit[0] < ttl_seconds:
            return hit[1]

        try: 
            value = fetch()
        except DataUnavailableError:
            if hit and time.monotonic() - hit[0] < ttl_seconds + self._stale_seconds:
                return hit[1]
            raise

        with self._lock:
            if key not in self._items and len(self._items) >= self._max_items:
                oldest = min(self._items, key=lambda k: self._items[k][0])
                del self._items[oldest]
            self._items[key] = (time.monotonic(), value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
