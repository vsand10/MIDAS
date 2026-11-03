# Small in-memory cache with an expiry time.
# Requests for the same key that arrive at the same moment share one fetch,
# so several people opening the same stock only cost one Alpha Vantage call.
import asyncio
import time
from collections.abc import Awaitable, Callable, Hashable
from typing import Any


class TTLCache:
    def __init__(self, max_items: int = 256):
        self._max_items = max_items
        self._data: dict[Hashable, tuple[float, Any]] = {}  # key -> (expires_at, value)
        self._inflight: dict[Hashable, asyncio.Task] = {}

    async def get_or_fetch(
        self,
        key: Hashable,
        ttl: float,
        fetch: Callable[[], Awaitable[Any]],
    ) -> Any:
        hit = self._data.get(key)
        if hit and hit[0] > time.monotonic():
            return hit[1]

        task = self._inflight.get(key)
        if task is None:
            task = asyncio.ensure_future(self._fetch_and_store(key, ttl, fetch))
            self._inflight[key] = task
        # shield: one caller giving up must not cancel the fetch the others wait on
        return await asyncio.shield(task)

    async def _fetch_and_store(self, key, ttl, fetch):
        try:
            value = await fetch()  # errors are not stored, so the next call retries
            self._store(key, ttl, value)
            return value
        finally:
            self._inflight.pop(key, None)

    def _store(self, key, ttl, value):
        now = time.monotonic()
        if len(self._data) >= self._max_items:
            # drop expired entries first, then the entries closest to expiring
            self._data = {k: v for k, v in self._data.items() if v[0] > now}
            while len(self._data) >= self._max_items:
                oldest = min(self._data, key=lambda k: self._data[k][0])
                del self._data[oldest]
        self._data[key] = (now + ttl, value)
