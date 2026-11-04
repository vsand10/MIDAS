# Shared helpers for talking to Alpha Vantage: the request function, the error
# type, a small cache and the list of company names (used by NEWS-01 and HOME-01)

import csv
import io
import json
import os
import re
import threading
import time
from collections.abc import Callable
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://www.alphavantage.co/query"
TIMEOUT_SECONDS = 15

# Alpha Vantage answers HTTP 200 even for problems and puts the reason under one of these keys
MESSAGE_KEYS = ("Error Message", "Information", "Note")


class DataUnavailableError(Exception):
    """Raised when Alpha Vantage could not give us usable data."""


def entitlement() -> dict[str, str]:
    """{"entitlement": "realtime"} when ALPHA_VANTAGE_ENTITLEMENT is set, otherwise {}.

    Without it Alpha Vantage may answer with delayed or even a day-old data
    (top gainers and losers came back a day old). Needs a premium key, so it is
    opt-in: put ALPHA_VANTAGE_ENTITLEMENT=realtime in backend/.env.
    """
    value = (os.getenv("ALPHA_VANTAGE_ENTITLEMENT") or "").strip().lower()
    return {"entitlement": value} if value else {}


def _send(params: dict[str, str]) -> tuple[int, str]:
    """The only function that touches the network. Tests replace it.

    Errors are reported by type only, because the text of an httpx error can
    contain the full web address, and that address contains the API key.
    """
    try:
        res = httpx.get(BASE_URL, params=params, timeout=TIMEOUT_SECONDS)
    except httpx.HTTPError as err:
        raise DataUnavailableError(f"Alpha Vantage request failed ({type(err).__name__})") from None
    return res.status_code, res.text


def _request(function: str, params: dict[str, Any]) -> str:
    key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not key:
        raise DataUnavailableError("ALPHA_VANTAGE_API_KEY is not set")
    query = {k: str(v) for k, v in params.items()}
    status, text = _send({**query, "function": function, "apikey": key})
    if status != 200:
        raise DataUnavailableError(f"Alpha Vantage returned HTTP {status}")
    return text


def av_get(function: str, **params: Any) -> dict:
    """Calls one Alpha Vantage function and returns the JSON as a dictionary."""
    text = _request(function, params)
    try:
        data = json.loads(text)
    except ValueError:
        raise DataUnavailableError("Alpha Vantage sent something that is not JSON") from None
    if not isinstance(data, dict) or not data:
        raise DataUnavailableError("Alpha Vantage sent an empty answer")
    for message_key in MESSAGE_KEYS:
        if message_key in data:
            raise DataUnavailableError(f"Alpha Vantage: {str(data[message_key])[:200]}")
    return data


def av_get_csv(function: str, **params: Any) -> list[dict[str, str]]:
    """For the few functions (like LISTING_STATUS) that answer with CSV text."""
    text = _request(function, params)
    if text.lstrip().startswith("{"):  # a JSON error message instead of the CSV
        message_dict = _json_or_none(text) or {}
        for message_key in MESSAGE_KEYS:
            if message_key in message_dict:
                raise DataUnavailableError(f"Alpha Vantage: {str(message_dict[message_key])[:200]}")
        raise DataUnavailableError("Alpha Vantage sent JSON where CSV was expected")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise DataUnavailableError("Alpha Vantage sent an empty list")
    return rows


def _json_or_none(text: str) -> dict | None:
    try:
        value = json.loads(text)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def to_float(value: Any) -> float | None:
    """Alpha Vantage sends numbers as text ("752.15", "-0.47%", "None"). None if unusable."""
    if value is None:
        return None
    try:
        return float(str(value).strip().rstrip("%"))
    except ValueError:
        return None


def quote_price(quote: dict) -> float | None:
    """Latest price from one REALTIME_BULK_QUOTES record, or None if it has no usable price.

    "close" is the latest trade. Some stocks (thinly traded, or with no trade yet today)
    come back with it missing or 0, so fall back to the after-hours price and then to
    the previous close. A price of 0 is never returned.
    """
    for field in ("close", "extended_hours_quote", "previous_close"):
        value = to_float(quote.get(field))
        if value:
            return value
    return None


class TTLCache:
    """Remembers results for a while so repeated requests skip Alpha Vantage.

    If a refresh fails, the last good result is reused for up to
    `stale_seconds`, so a short outage doesn't break the screen.
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


# ---------------- Company names ----------------

LISTING_TTL_SECONDS = 24 * 3600
_listing_cache = TTLCache(max_items=2, stale_seconds=7 * 24 * 3600)

# Warrants, rights and units trade like stocks but are not what people look for
_NOT_A_STOCK = re.compile(r"\b(warrants?|rights?|units?)\b", re.IGNORECASE)


def company_names() -> dict[str, str]:
    """{"AAPL": "Apple Inc", ...} for every active listed stock (cached for a day)."""

    def load() -> dict[str, str]:
        rows = av_get_csv("LISTING_STATUS", state="active")
        return {
            r["symbol"]: r["name"]
            for r in rows
            if r.get("assetType") == "Stock"
            and r.get("symbol")
            and r.get("name")
            and not _NOT_A_STOCK.search(r["name"])
        }

    return _listing_cache.get_or_fetch("listing", LISTING_TTL_SECONDS, load)


def company_names_or_empty() -> dict[str, str]:
    """Same, but names are a nice-to-have: an outage gives {} instead of an error."""
    try:
        return company_names()
    except DataUnavailableError:
        return {}
