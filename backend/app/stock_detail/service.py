# Gets stock detail data from Alpha Vantage, picks and assembles what the page needs,
# and caches the results. Returns plain dicts: router.py defines their exact shape.
import asyncio
import logging
from datetime import timedelta

from app.services.alphavantage import entitlement
from app.stock_detail.cache import TTLCache
from app.stock_detail.client import (
    AlphaVantageClient,
    AlphaVantageError,
    Bar,
    SymbolNotFound,
    parse_bars,
    parse_overview,
    parse_quote,
)

logger = logging.getLogger(__name__)

# How long each kind of data is reused, in seconds
QUOTE_TTL = 30
INTRADAY_TTL = 60
DAILY_TTL = 15 * 60
WEEKLY_TTL = 60 * 60
OVERVIEW_TTL = 6 * 60 * 60  # company facts barely change

# Chart range -> where its data comes from
INTRADAY_INTERVAL = {"1D": "5min", "1W": "60min"}


def _iso(moment) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def select_window(bars: list[Bar], range_: str) -> list[Bar]:
    """Keep only the bars that belong to a chart range, measured from the newest bar."""
    if not bars:
        return []
    latest = bars[-1].session

    if range_ == "1D":
        return [b for b in bars if b.session == latest]
    if range_ == "1W":
        last_five_days = sorted({b.session for b in bars})[-5:]
        return [b for b in bars if b.session in last_five_days]

    days = {"1M": 30, "3M": 91, "1Y": 365}[range_]
    cutoff = latest - timedelta(days=days)
    return [b for b in bars if b.session >= cutoff]


def average_volume(bars: list[Bar], days: int = 30) -> float | None:
    """Average shares traded per day over the newest `days` daily bars."""
    volumes = [b.volume for b in bars[-days:] if b.volume]
    return sum(volumes) / len(volumes) if volumes else None


class StockDetailService:
    def __init__(self, client: AlphaVantageClient | None = None, cache: TTLCache | None = None):
        self._client = client or AlphaVantageClient()
        self._cache = cache or TTLCache()

    # ---------------- Public ----------------

    async def detail(self, symbol: str) -> dict:
        quote, overview, daily = await asyncio.gather(
            self._quote(symbol),
            self._overview(symbol),
            self._daily(symbol),
            return_exceptions=True,
        )

        # The price is required. Company facts and volume are nice to have, so if
        # only those fail the page still opens (their fields are left empty).
        if isinstance(quote, BaseException):
            raise quote
        overview = self._optional(overview, "overview", symbol)
        daily = self._optional(daily, "daily volume", symbol)

        return {
            "symbol": symbol,
            "name": overview.name if overview else symbol,
            "sector": overview.sector if overview else "",
            "price": quote.price,
            "change": quote.change,
            "changePercent": quote.change_percent,
            "stats": {
                "marketCap": overview.market_cap if overview else None,
                "peRatio": overview.pe_ratio if overview else None,
                "week52Low": overview.week52_low if overview else None,
                "week52High": overview.week52_high if overview else None,
                "avgVolume": average_volume(daily) if daily else None,
                "eps": overview.eps if overview else None,
                "dividendYield": overview.dividend_yield if overview else None,
            },
            "about": overview.about if overview else "",
        }

    async def history(self, symbol: str, range_: str) -> list[dict]:
        if range_ in INTRADAY_INTERVAL:
            bars = await self._intraday(symbol, INTRADAY_INTERVAL[range_])
        elif range_ in ("1M", "3M"):
            bars = await self._daily(symbol)
        else:
            bars = await self._weekly(symbol)

        return [{"time": _iso(bar.time), "price": bar.close} for bar in select_window(bars, range_)]

    # ---------------- Cached Alpha Vantage calls ----------------

    def _quote(self, symbol):
        async def fetch():
            payload = await self._client.request("GLOBAL_QUOTE", symbol=symbol, **entitlement())
            return parse_quote(payload)

        return self._cache.get_or_fetch(("quote", symbol), QUOTE_TTL, fetch)

    def _overview(self, symbol):
        async def fetch():
            return parse_overview(await self._client.request("OVERVIEW", symbol=symbol))

        return self._cache.get_or_fetch(("overview", symbol), OVERVIEW_TTL, fetch)

    def _intraday(self, symbol, interval):
        async def fetch():
            payload = await self._client.request(
                "TIME_SERIES_INTRADAY",
                symbol=symbol,
                interval=interval,
                outputsize="full",
                extended_hours="false",  # chart regular trading hours only
                **entitlement(),
            )
            return parse_bars(payload)

        return self._cache.get_or_fetch(("intraday", symbol, interval), INTRADAY_TTL, fetch)

    def _daily(self, symbol):
        async def fetch():
            return parse_bars(await self._client.request("TIME_SERIES_DAILY", symbol=symbol))

        return self._cache.get_or_fetch(("daily", symbol), DAILY_TTL, fetch)

    def _weekly(self, symbol):
        async def fetch():
            return parse_bars(await self._client.request("TIME_SERIES_WEEKLY", symbol=symbol))

        return self._cache.get_or_fetch(("weekly", symbol), WEEKLY_TTL, fetch)

    # ---------------- Helpers ----------------

    @staticmethod
    def _optional(result, label, symbol):
        if not isinstance(result, BaseException):
            return result
        if isinstance(result, SymbolNotFound):
            return None
        if isinstance(result, AlphaVantageError):
            logger.warning("Stock detail for %s is missing %s: %s", symbol, label, result.detail)
            return None
        raise result  # a bug, not an Alpha Vantage problem: do not hide it
