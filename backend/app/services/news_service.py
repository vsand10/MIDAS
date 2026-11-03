# Gets recent news articles for a stock from Alpha Vantage NEWS_SENTIMENT (NEWS-01)

import re
from datetime import UTC, datetime

from app.services.alphavantage import (
    DataUnavailableError,
    TTLCache,
    av_get,
    company_names,
    to_float,
)

NEWS_TTL_SECONDS = 600  # news does not change second to second

# Alpha Vantage gives every article a 0 to 1 "relevance" for each ticker it lists.
# Real data showed scores of 0.6 for articles that never mention the company
# (a ZipRecruiter board change, an unrelated fund filing), so a score alone is
# not enough. An article is kept when either:
#   - its score is very high, or
#   - its score is at least MIN_MENTION_RELEVANCE and the headline names the company
HIGH_RELEVANCE = 0.9
MIN_MENTION_RELEVANCE = 0.2

# Words dropped from a company name before looking for it in a headline
NAME_SUFFIXES = {
    "inc", "corp", "corporation", "co", "company", "ltd", "limited", "plc", "holdings",
    "group", "class", "common", "stock", "ordinary", "shares", "adr", "the", "a", "b", "c",
}  # fmt: skip
# First words too common to search for on their own ("Bank of America" is not "bank")
GENERIC_FIRST_WORDS = {"bank", "first", "united", "american", "general", "global", "national", "home", "new"}

_cache = TTLCache()


def _fetch_raw_news(symbol: str) -> list[dict]:
    """The only line that talks to Alpha Vantage. Tests replace this function.

    The feed always holds up to 50 articles whatever the limit, so we ask for
    all of them, filter, and cut to the limit ourselves.
    """
    data = av_get("NEWS_SENTIMENT", tickers=symbol, sort="LATEST", limit=50)
    feed = data.get("feed")
    return feed if isinstance(feed, list) else []


def _company_name(symbol: str) -> str | None:
    """Company name for headline matching. A missing name only makes filtering stricter."""
    try:
        return company_names().get(symbol)
    except DataUnavailableError:
        return None


def _name_keywords(name: str | None) -> list[str]:
    """Lower-case phrases that identify the company in a headline."""
    if not name:
        return []
    words = [w for w in re.findall(r"[a-z0-9&]+", name.lower()) if w not in NAME_SUFFIXES]
    if not words:
        return []
    keywords = [" ".join(words)]
    if len(words) > 1 and len(words[0]) >= 4 and words[0] not in GENERIC_FIRST_WORDS:
        keywords.append(words[0])
    return keywords


def _mentions(title: str, symbol: str, keywords: list[str]) -> bool:
    """True if the headline contains the company name or (for 3+ letter tickers) the ticker."""
    lowered = title.lower()
    for keyword in keywords:
        if re.search(rf"\b{re.escape(keyword)}\b", lowered):
            return True
    return len(symbol) >= 3 and re.search(rf"\b{re.escape(symbol)}\b", title) is not None


def _ticker_entry(raw: dict, symbol: str) -> dict:
    """Alpha Vantage's scores for this ticker in this article ({} if it is not listed)."""
    for entry in raw.get("ticker_sentiment") or []:
        if isinstance(entry, dict) and entry.get("ticker") == symbol:
            return entry
    return {}


def _relevance(raw: dict, symbol: str) -> float:
    """The article's relevance score for this ticker (0 if the ticker is not listed)."""
    return to_float(_ticker_entry(raw, symbol).get("relevance_score")) or 0.0


def is_relevant(raw: dict, symbol: str, keywords: list[str]) -> bool:
    score = _relevance(raw, symbol)
    if score >= HIGH_RELEVANCE:
        return True
    return score >= MIN_MENTION_RELEVANCE and _mentions(str(raw.get("title") or ""), symbol, keywords)


def _parse_time(value: object) -> datetime | None:
    """Alpha Vantage times look like "20261102T180712" and are UTC."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        return None


def _sentiment(raw: dict, symbol: str) -> dict | None:
    """{"label": "Somewhat-Bullish", "score": 0.21} for this ticker, else for the whole article."""
    entry = _ticker_entry(raw, symbol)
    label = entry.get("ticker_sentiment_label") or raw.get("overall_sentiment_label")
    score = to_float(entry.get("ticker_sentiment_score"))
    if score is None:
        score = to_float(raw.get("overall_sentiment_score"))
    if not label:
        return None
    return {"label": str(label), "score": score}


def normalize_article(raw: dict, symbol: str) -> dict | None:
    """Turns one feed item into the article the News screens show.

    Items missing a headline, a web link or a time are dropped, since the
    screens need all three. Only http(s) links and images are kept, so a bad
    feed can never hand the app a javascript: link.
    """
    title = str(raw.get("title") or "").strip()
    url = raw.get("url")
    published = _parse_time(raw.get("time_published"))
    if not (title and published and _is_web_link(url)):
        return None
    image = raw.get("banner_image")
    topics = [t.get("topic") for t in raw.get("topics") or [] if isinstance(t, dict) and t.get("topic")]
    return {
        "id": url,
        "title": title,
        "source": str(raw.get("source") or "Unknown source"),
        "url": url,
        # Always UTC, so sorting the text also sorts by time
        "publishedAt": published.isoformat(),
        "summary": str(raw.get("summary") or "").strip(),
        "imageUrl": image if _is_web_link(image) else None,
        "sentiment": _sentiment(raw, symbol),
        "relevance": _relevance(raw, symbol),
        "topics": [str(t) for t in topics[:3]],
    }


def _is_web_link(value: object) -> bool:
    return isinstance(value, str) and value.startswith(("https://", "http://"))


def build_articles(
    raw_items: list[dict] | None, symbol: str, keywords: list[str], limit: int
) -> list[dict]:
    """Relevant, valid articles only, no duplicates, newest first."""
    seen: set[str] = set()
    articles = []
    for raw in raw_items or []:
        if not isinstance(raw, dict) or not is_relevant(raw, symbol, keywords):
            continue
        article = normalize_article(raw, symbol)
        if article and article["url"] not in seen:
            seen.add(article["url"])
            articles.append(article)
    articles.sort(key=lambda a: a["publishedAt"], reverse=True)
    return articles[:limit]


def get_news(symbol: str, limit: int = 10) -> list[dict]:
    """Newest-first articles for a stock. An empty list means "no news"."""
    symbol = symbol.upper()

    def load() -> list[dict]:
        raw = _fetch_raw_news(symbol)
        keywords = _name_keywords(_company_name(symbol))
        return build_articles(raw, symbol, keywords, limit)

    return _cache.get_or_fetch(f"{symbol}:{limit}", NEWS_TTL_SECONDS, load)
