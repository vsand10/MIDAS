# Gets market indices, index charts and top movers from Alpha Vantage (HOME-01)
#
# Alpha Vantage has no live value for the indices themselves:
#   - INDEX_DATA gives official daily closes, but only up to the previous trading day
#   - ETFs that track each index (SPY, ONEQ, DIA) have real-time quotes and intraday prices
# So the live level is estimated as: ETF price x (official index close / ETF close on the
# same day). The ratio is recalculated from the latest day both have, so it stays accurate.

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.services.alphavantage import (
    DataUnavailableError,
    TTLCache,
    av_get,
    company_names_or_empty,
    to_float,
)

MARKET_TZ = ZoneInfo("America/New_York")

# app symbol -> (name shown in the app, Alpha Vantage index symbol, ETF that tracks it)
INDEX_SOURCES = {
    "^GSPC": ("S&P 500", "SPX", "SPY"),
    "^IXIC": ("Nasdaq", "COMP", "ONEQ"),
    "^DJI": ("Dow", "DJI", "DIA"),
}
INDEX_NAMES = {symbol: source[0] for symbol, source in INDEX_SOURCES.items()}

# range -> how to build the chart. Matches the chart tabs in the app.
#   ("intraday", ETF interval, number of trading days to keep)
#   ("daily", number of calendar days to keep)
RANGE_SETTINGS = {
    "1D": ("intraday", "5min", 1),
    "1W": ("intraday", "30min", 5),
    "1M": ("daily", 30),
    "3M": ("daily", 91),
    "1Y": ("daily", 365),
}

# Alpha Vantage's gainers list is full of penny stocks (a few cents, a few shares traded).
# Only stocks that pass both checks are shown.
MIN_MOVER_PRICE = 5.0
MIN_MOVER_VOLUME = 500_000

# Used to top up the movers lists when Alpha Vantage's own lists are short or down
FALLBACK_STOCKS = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corp.",
    "NVDA": "NVIDIA Corp.",
    "AMZN": "Amazon.com Inc.",
    "GOOGL": "Alphabet Inc.",
    "META": "Meta Platforms Inc.",
    "TSLA": "Tesla Inc.",
    "AVGO": "Broadcom Inc.",
    "JPM": "JPMorgan Chase & Co.",
    "V": "Visa Inc.",
    "MA": "Mastercard Inc.",
    "UNH": "UnitedHealth Group",
    "LLY": "Eli Lilly and Co.",
    "JNJ": "Johnson & Johnson",
    "ABBV": "AbbVie Inc.",
    "MRK": "Merck & Co.",
    "XOM": "Exxon Mobil Corp.",
    "CVX": "Chevron Corp.",
    "WMT": "Walmart Inc.",
    "COST": "Costco Wholesale",
    "HD": "Home Depot",
    "PG": "Procter & Gamble",
    "KO": "Coca-Cola Co.",
    "PEP": "PepsiCo Inc.",
    "BAC": "Bank of America",
    "NFLX": "Netflix Inc.",
    "AMD": "Advanced Micro Devices",
    "CRM": "Salesforce Inc.",
    "ORCL": "Oracle Corp.",
    "DIS": "Walt Disney Co.",
}

OVERVIEW_TTL_SECONDS = 30
INTRADAY_TTL_SECONDS = 120
DAILY_TTL_SECONDS = 3600  # official daily data changes once a day
MOVERS_TTL_SECONDS = 120

_cache = TTLCache()


# ---------------- The only functions that talk to Alpha Vantage (tests replace these) ----------------


def _fetch_index_daily(index_symbol: str) -> list[dict]:
    """Official daily closes [{date, open, high, low, close}], newest first."""
    return av_get("INDEX_DATA", symbol=index_symbol, interval="daily").get("data", [])


def _fetch_etf_daily(etf: str) -> dict:
    """Daily ETF prices: {"2026-10-30": {"4. close": "755.72", ...}, ...}."""
    return av_get("TIME_SERIES_DAILY", symbol=etf).get("Time Series (Daily)", {})


def _fetch_etf_intraday(etf: str, interval: str) -> dict:
    """Intraday ETF prices: {"2026-11-02 15:55:00": {"4. close": "751.9", ...}, ...}."""
    data = av_get(
        "TIME_SERIES_INTRADAY",
        symbol=etf,
        interval=interval,
        entitlement="realtime",
        extended_hours="false",
    )
    return data.get(f"Time Series ({interval})", {})


def _fetch_quotes(symbols: list[str]) -> list[dict]:
    """Live quotes: [{symbol, close, previous_close, change, change_percent, ...}]."""
    return av_get("REALTIME_BULK_QUOTES", symbol=",".join(symbols)).get("data", [])


def _fetch_gainers_losers() -> dict:
    return av_get("TOP_GAINERS_LOSERS", entitlement="realtime")


# ---------------- Helpers ----------------


def _round(value: float | None) -> float | None:
    return None if value is None else round(float(value), 2)


def _quote_by_symbol(symbols: list[str]) -> dict[str, dict]:
    quotes = {q.get("symbol"): q for q in _fetch_quotes(symbols) if isinstance(q, dict)}
    if not quotes:
        raise DataUnavailableError("No quotes returned")
    return quotes


def _cached_index_daily(index_symbol: str) -> list[dict]:
    """INDEX_DATA is large (about 1.3 MB), so it is cached for an hour."""
    return _cache.get_or_fetch(
        f"index-daily:{index_symbol}",
        DAILY_TTL_SECONDS,
        lambda: _fetch_index_daily(index_symbol),
    )


def _cached_etf_daily(etf: str) -> dict:
    return _cache.get_or_fetch(f"etf-daily:{etf}", DAILY_TTL_SECONDS, lambda: _fetch_etf_daily(etf))


def _index_ratio(symbol: str) -> float:
    """official index close / ETF close, on the latest day that both have a close."""
    _, index_symbol, etf = INDEX_SOURCES[symbol]
    index_closes = {
        row.get("date"): to_float(row.get("close"))
        for row in _cached_index_daily(index_symbol)
        if isinstance(row, dict)
    }
    etf_days = _cached_etf_daily(etf)
    for day in sorted(index_closes, reverse=True):  # ISO dates sort correctly as text
        index_close = index_closes[day]
        etf_close = to_float((etf_days.get(day) or {}).get("4. close"))
        if index_close and etf_close:
            return index_close / etf_close
    raise DataUnavailableError(f"No overlapping days for {symbol}")


# ---------------- Market overview ----------------


def get_market_overview() -> list[dict]:
    """S&P 500, Nasdaq and Dow with value and change. All three or an error."""

    def load() -> list[dict]:
        etfs = [source[2] for source in INDEX_SOURCES.values()]
        with ThreadPoolExecutor(max_workers=len(INDEX_SOURCES) + 1) as pool:
            quotes_future = pool.submit(_quote_by_symbol, etfs)
            ratio_futures = {s: pool.submit(_index_ratio, s) for s in INDEX_SOURCES}
            quotes = quotes_future.result()  # each result() re-raises the first failure
            ratios = {s: f.result() for s, f in ratio_futures.items()}

        rows = []
        for symbol, (name, _, etf) in INDEX_SOURCES.items():
            quote = quotes.get(etf) or {}
            price = to_float(quote.get("close"))
            previous = to_float(quote.get("previous_close"))
            if not price or not previous:
                raise DataUnavailableError(f"Incomplete quote for {etf}")
            ratio = ratios[symbol]
            rows.append(
                {
                    "symbol": symbol,
                    "name": name,
                    "value": _round(price * ratio),
                    "change": _round((price - previous) * ratio),
                    "changePercent": _round((price / previous - 1) * 100),
                }
            )
        return rows

    return _cache.get_or_fetch("overview", OVERVIEW_TTL_SECONDS, load)


# ---------------- Index chart ----------------


def _market_time(text: str) -> datetime:
    """"2026-11-02 15:55:00" (New York time) -> a time that knows its time zone."""
    return datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=MARKET_TZ)


def intraday_points(series: dict, ratio: float, days: int) -> list[dict]:
    """Chart points from an Alpha Vantage intraday series, scaled by `ratio`.

    Keeps only the latest `days` trading days (this also works on weekends).
    Shared with the Stock Detail chart (ratio 1).
    """
    points = []
    for stamp in sorted(series):
        close = to_float((series[stamp] or {}).get("4. close"))
        if close:
            points.append((stamp, close * ratio))
    if not points:
        raise DataUnavailableError("No intraday data returned")
    keep = sorted({stamp[:10] for stamp, _ in points})[-days:]
    return [
        {"time": _market_time(stamp).isoformat(), "price": _round(price)}
        for stamp, price in points
        if stamp[:10] in keep
    ]


def daily_points(closes: list[tuple[str, float | None]], calendar_days: int) -> list[dict]:
    """Chart points from (date, close) pairs, keeping the last `calendar_days` days.

    A day is shown at its 4 pm market close. Shared with the Stock Detail chart.
    """
    rows = sorted((d, c) for d, c in closes if d and c)
    if not rows:
        raise DataUnavailableError("No daily data returned")
    newest = datetime.strptime(rows[-1][0], "%Y-%m-%d")
    cutoff = (newest - timedelta(days=calendar_days)).strftime("%Y-%m-%d")
    return [
        {"time": _market_time(f"{day} 16:00:00").isoformat(), "price": _round(close)}
        for day, close in rows
        if day >= cutoff
    ]


def _index_intraday(symbol: str, interval: str, days: int) -> list[dict]:
    _, _, etf = INDEX_SOURCES[symbol]
    series = _cache.get_or_fetch(
        f"intraday:{etf}:{interval}",
        INTRADAY_TTL_SECONDS,
        lambda: _fetch_etf_intraday(etf, interval),
    )
    return intraday_points(series, _index_ratio(symbol), days)


def _index_daily(symbol: str, calendar_days: int) -> list[dict]:
    rows = _cached_index_daily(INDEX_SOURCES[symbol][1])
    closes = [(r.get("date"), to_float(r.get("close"))) for r in rows if isinstance(r, dict)]
    return daily_points(closes, calendar_days)


def get_index_history(symbol: str, range_: str) -> list[dict]:
    """Chart points [{time, price}] oldest to newest for one of the three indices."""
    if symbol not in INDEX_SOURCES:
        raise ValueError(f"Unknown index {symbol}")
    if range_ not in RANGE_SETTINGS:
        raise ValueError(f"Unknown range {range_}")
    kind, *settings = RANGE_SETTINGS[range_]

    def load() -> list[dict]:
        if kind == "intraday":
            return _index_intraday(symbol, *settings)
        return _index_daily(symbol, *settings)

    return _cache.get_or_fetch(f"history:{symbol}:{range_}", INTRADAY_TTL_SECONDS, load)


# ---------------- Top movers ----------------


def _mover_row(item: dict, names: dict[str, str]) -> dict | None:
    """One TOP_GAINERS_LOSERS item -> a row, or None for penny stocks and odd tickers."""
    symbol = item.get("ticker")
    price = to_float(item.get("price"))
    percent = to_float(item.get("change_percentage"))
    if not symbol or price is None or percent is None:
        return None
    if price < MIN_MOVER_PRICE or (to_float(item.get("volume")) or 0) < MIN_MOVER_VOLUME:
        return None
    # When the company list is available, only real listed stocks are shown
    # (no warrants, rights or ETFs, which also use odd tickers)
    if names and symbol not in names:
        return None
    return {
        "symbol": symbol,
        "name": names.get(symbol, symbol),
        "price": _round(price),
        "change": _round(to_float(item.get("change_amount"))),
        "changePercent": _round(percent),
    }


def _screened_rows() -> tuple[list[dict], list[dict]]:
    """Filtered gainers and losers from Alpha Vantage; two empty lists if it is down."""
    try:
        data = _fetch_gainers_losers()
    except DataUnavailableError:
        return [], []
    names = company_names_or_empty()

    def rows(key: str) -> list[dict]:
        items = data.get(key) or []
        return [row for row in (_mover_row(i, names) for i in items if isinstance(i, dict)) if row]

    return rows("top_gainers"), rows("top_losers")


def _basket_rows() -> list[dict]:
    """Daily change for the large stocks, from one bulk quote call."""
    quotes = _quote_by_symbol(list(FALLBACK_STOCKS))
    rows = []
    for symbol, name in FALLBACK_STOCKS.items():
        quote = quotes.get(symbol) or {}
        price = to_float(quote.get("close"))
        percent = to_float(quote.get("change_percent"))
        if price is None or percent is None:
            continue  # this one stock had no data; skip it
        rows.append(
            {
                "symbol": symbol,
                "name": name,
                "price": _round(price),
                "change": _round(to_float(quote.get("change"))),
                "changePercent": _round(percent),
            }
        )
    return rows


def get_top_movers(limit: int = 5) -> dict:
    """{"gainers": [...], "losers": [...]} with symbol, name, price, change, changePercent.

    Uses Alpha Vantage's gainers/losers lists with penny stocks removed. If that
    leaves fewer than `limit` on a side (or the list is down), the side is topped
    up from a basket of large stocks. Raises DataUnavailableError only if there is
    nothing at all to show.
    """

    def load() -> dict:
        gainers, losers = _screened_rows()

        if len(gainers) < limit or len(losers) < limit:
            try:
                basket = _basket_rows()
            except DataUnavailableError:
                basket = []  # keep whatever we already have
            taken = {r["symbol"] for r in gainers + losers}
            fresh = [r for r in basket if r["symbol"] not in taken]
            gainers += [r for r in fresh if r["changePercent"] > 0]
            losers += [r for r in fresh if r["changePercent"] < 0]

        gainers.sort(key=lambda r: r["changePercent"], reverse=True)
        losers.sort(key=lambda r: r["changePercent"])
        if not gainers and not losers:
            raise DataUnavailableError("No movers data")
        return {"gainers": gainers[:limit], "losers": losers[:limit]}

    return _cache.get_or_fetch(f"movers:{limit}", MOVERS_TTL_SECONDS, load)
