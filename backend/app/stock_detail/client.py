# Everything that talks to Alpha Vantage for the stock detail feature, in the order it is used:
#   1. errors        what can go wrong, and the HTTP status each one maps to
#   2. clean data    the small objects the rest of the code works with
#   3. parsers       raw Alpha Vantage JSON -> clean data
#   4. the client    sends the request and spots error messages hidden in a 200 response
# Used by stock detail only. main.py makes its own Alpha Vantage calls (search, quotes, watchlist).
import logging
import math
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import httpx

# ---------------- 1. Errors ----------------
# Each one knows which HTTP status the MIDAS API should answer with.


class AlphaVantageError(Exception):
    status_code = 502
    detail = "Could not get stock data from Alpha Vantage"

    def __init__(self, detail: str | None = None):
        super().__init__(detail or self.detail)
        if detail:
            self.detail = detail


class SymbolNotFound(AlphaVantageError):
    # The page shows its "Stock not found" screen on a 404
    status_code = 404
    detail = "Stock not found"


class RateLimited(AlphaVantageError):
    status_code = 429
    detail = "Alpha Vantage rate limit reached, please try again in a moment"


class PlanLimited(AlphaVantageError):
    # Alpha Vantage answered 200 but said the API key's plan does not cover this data
    status_code = 502
    detail = "The Alpha Vantage plan does not include this data"


class NotConfigured(AlphaVantageError):
    status_code = 500
    detail = "Alpha Vantage API key is not configured"


class UpstreamError(AlphaVantageError):
    status_code = 502
    detail = "Could not connect to Alpha Vantage"


# ---------------- 2 & 3. Clean data and parsers ----------------

# U.S. markets run on New York time. Alpha Vantage sends intraday times without a
# timezone (New York time), and the page needs real timestamps to show local time.
MARKET_TZ = ZoneInfo("America/New_York")
MARKET_CLOSE = time(16, 0)


@dataclass(frozen=True)
class Quote:
    price: float
    change: float
    change_percent: float


@dataclass(frozen=True)
class Overview:
    name: str
    sector: str
    about: str
    market_cap: float | None
    pe_ratio: float | None
    eps: float | None
    week52_low: float | None
    week52_high: float | None
    dividend_yield: float | None  # percent


@dataclass(frozen=True)
class Bar:
    time: datetime  # UTC
    session: date  # trading day (New York date)
    close: float
    volume: float


def _num(value) -> float | None:
    """'12.5' -> 12.5, '-0.98%' -> -0.98, 'None' / '-' / '' / nan -> None."""
    if value is None:
        return None
    try:
        number = float(str(value).strip().rstrip("%"))
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _text(value) -> str:
    text = str(value).strip() if value is not None else ""
    return "" if text in ("None", "-") else text


def parse_quote(payload: dict) -> Quote:
    """GLOBAL_QUOTE. An empty quote means the symbol does not exist."""
    raw = payload.get("Global Quote") or {}
    price = _num(raw.get("05. price"))
    if price is None:
        raise SymbolNotFound()

    change = _num(raw.get("09. change"))
    change_percent = _num(raw.get("10. change percent"))
    previous_close = _num(raw.get("08. previous close"))
    if change is None:
        change = price - previous_close if previous_close is not None else 0.0
    if change_percent is None:
        change_percent = change / previous_close * 100 if previous_close else 0.0
    return Quote(price=price, change=change, change_percent=change_percent)


def parse_overview(payload: dict) -> Overview | None:
    """OVERVIEW. Returns None when Alpha Vantage has no company data for the symbol."""
    if not payload.get("Symbol"):
        return None

    # Alpha Vantage sends dividend yield as a fraction (0.0044), the page wants a percent
    dividend = _num(payload.get("DividendYield"))
    return Overview(
        name=_text(payload.get("Name")) or payload["Symbol"],
        sector=_text(payload.get("Sector")).title(),
        about=_text(payload.get("Description")),
        market_cap=_num(payload.get("MarketCapitalization")),
        pe_ratio=_num(payload.get("PERatio")),
        eps=_num(payload.get("EPS")),
        week52_low=_num(payload.get("52WeekLow")),
        week52_high=_num(payload.get("52WeekHigh")),
        dividend_yield=dividend * 100 if dividend else None,
    )


def parse_bars(payload: dict) -> list[Bar]:
    """Any TIME_SERIES_* response, oldest first.

    Intraday keys look like '2026-10-30 15:55:00'. Daily and weekly keys look like
    '2026-10-30'; those are placed at the 4 PM New York close so the date stays the
    same in every U.S. timezone.
    """
    series = next(
        (v for k, v in payload.items() if k != "Meta Data" and isinstance(v, dict)),
        {},
    )
    bars = []
    for stamp, row in series.items():
        close = _num(row.get("4. close"))
        if close is None:
            continue
        try:
            if len(stamp) > 10:
                local = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S")
            else:
                local = datetime.combine(date.fromisoformat(stamp), MARKET_CLOSE)
        except ValueError:
            continue
        local = local.replace(tzinfo=MARKET_TZ)
        bars.append(
            Bar(
                time=local.astimezone(UTC),
                session=local.date(),
                close=close,
                volume=_num(row.get("5. volume")) or 0.0,
            )
        )
    bars.sort(key=lambda bar: bar.time)
    return bars


# ---------------- 4. The client ----------------

logger = logging.getLogger(__name__)

BASE_URL = "https://www.alphavantage.co/query"

# Phrases Alpha Vantage uses when a key has made too many requests
RATE_LIMIT_HINTS = (
    "rate limit",
    "requests per",
    "call frequency",
    "per minute",
    "per day",
)


def check_payload(payload: dict) -> None:
    """Raise the right error if Alpha Vantage sent a message instead of data."""
    if "Error Message" in payload:
        # Sent for symbols that do not exist
        raise SymbolNotFound()

    message = payload.get("Note") or payload.get("Information")
    if not message:
        return

    lowered = str(message).lower()
    if "premium endpoint" in lowered:
        raise PlanLimited(f"The Alpha Vantage plan does not include this data: {message}")
    if any(hint in lowered for hint in RATE_LIMIT_HINTS):
        raise RateLimited()
    raise UpstreamError(f"Alpha Vantage said: {message}")


class AlphaVantageClient:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None, timeout: float = 10.0):
        self._transport = transport  # tests pass a fake transport here
        self._timeout = timeout

    async def request(self, function: str, **params) -> dict:
        # Read the key on every call: main.py loads .env after its imports run
        api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        if not api_key:
            raise NotConfigured()

        query = {"function": function, **params, "apikey": api_key}
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as http:
                response = await http.get(BASE_URL, params=query)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            # Log only the error type: the message can contain the URL, and the URL has the API key
            logger.warning("Alpha Vantage %s request failed: %s", function, type(exc).__name__)
            raise UpstreamError() from None

        if not isinstance(payload, dict):
            raise UpstreamError()
        check_payload(payload)
        return payload
