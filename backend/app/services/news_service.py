# Gets recent news articles for a stock from Yahoo Finance

from datetime import UTC, datetime
from typing import Any

import yfinance as yf

from app.services.yfinance_utils import call_yfinance, TTLCache

NEWS_TTL_SECONDS = 600 # 10 minute news interval

_cache = TTLCache()

def _fetch_raw_news(symbol: str, count: int) -> list[dict]:
    """The only function that talks to Yahoo, tests replace this funct
    Uses Yahoo's search route for news. yf.Ticker(symbol).get_news() came back
    empty when tested, while this one returned articles.
    """
    return yf.Search(symbol, news_count=count).news


def _parse_time(value: Any) -> datetime | None:
    """Parses a timestamp value into a datetime object, returning None if invalid.
       Accepts an ISO string ("2025-03-01T12:00:00Z") or epoch seconds.
    """
    if isinstance(value, int | float) and not isinstance(value, bool):
        return datetime.fromtimestamp(value, tz=UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None

def _link(value: Any) -> str | None:
    """Pulls a web address out of {"url": "..."} or a plain string.

    Only http(s) links are kept, so a bad feed can never hand the app a
    javascript: link.
    """
    url = value.get("url") if isinstance(value, dict) else value
    if isinstance(url, str) and url.startswith(("https://", "http://")):
        return url
    return None

def normalize_article(raw: dict) -> dict | None:
    """Turns one yfinance news item into {id, title, source, url, publishedAt}.

    Yahoo has used two layouts: a newer one with everything under "content",
    and an older flat one. Both are handled. Items missing a headline, a link
    or a time are dropped, since the screen needs all three.
    """
    content = raw.get("content") if isinstance(raw.get("content"), dict) else raw

    title = str(content.get("title") or "").strip()
    url = (
        _link(content.get("canonicalUrl"))
        or _link(content.get("clickThroughUrl"))
        or _link(content.get("link"))
    )
    published = _parse_time(
        content.get("pubDate")
        or content.get("displayTime")
        or content.get("providerPublishTime")
    )
    if not (title and url and published):
        return None

    provider = content.get("provider")
    source = provider.get("displayName") if isinstance(provider, dict) else None
    source = source or content.get("publisher") or "Unknown source"

    return {
        "id": str(raw.get("id") or raw.get("uuid") or content.get("id") or url),
        "title": title,
        "source": str(source),
        "url": url,
        # Always UTC, so sorting the text also sorts by time
        "publishedAt": published.astimezone(UTC).isoformat(),
    }

def build_articles(raw_items: list[dict] | None, limit: int) -> list[dict]:
    """Cleans the raw list: valid items only, no duplicates, newest first."""
    seen: set[str] = set()
    articles = []
    for raw in raw_items or []:
        if not isinstance(raw, dict):
            continue
        article = normalize_article(raw)
        if article and article["url"] not in seen:
            seen.add(article["url"])
            articles.append(article)
    articles.sort(key=lambda a: a["publishedAt"], reverse=True)
    return articles[:limit]


def get_news(symbol: str, limit: int = 10) -> list[dict]:
    """Newest-first articles for a stock. An empty list means "no news"."""
    symbol = symbol.upper()

    def load() -> list[dict]:
        raw = call_yfinance(_fetch_raw_news, symbol, max(limit, 10))
        return build_articles(raw, limit)

    return _cache.get_or_fetch(f"{symbol}:{limit}", NEWS_TTL_SECONDS, load)
