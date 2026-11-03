# Tests for NEWS-01: stock news (no internet needed, Alpha Vantage is replaced with fake data)

import pytest

from app.services import news_service
from app.services.alphavantage import DataUnavailableError


def item(title, published, relevance, url=None, source="Reuters", ticker="AAPL"):
    """A feed item shaped like a real NEWS_SENTIMENT article (trimmed)."""
    slug = title.lower().replace(" ", "-")
    return {
        "title": title,
        "url": url or f"https://example.com/{slug}",
        "time_published": published,
        "source": source,
        "summary": "Short summary.",
        "banner_image": "https://example.com/banner.jpg",
        "topics": [{"topic": "Technology", "relevance_score": "1.0"}, {"topic": "Earnings", "relevance_score": "0.5"}],
        "overall_sentiment_label": "Neutral",
        "overall_sentiment_score": "0.01",
        "ticker_sentiment": [
            {
                "ticker": ticker,
                "relevance_score": str(relevance),
                "ticker_sentiment_label": "Somewhat-Bullish",
                "ticker_sentiment_score": "0.21",
            }
        ],
    }


# Real articles from the AAPL feed on 2 Nov 2026 (trimmed), including the noisy ones
ZIPRECRUITER = item("ZipRecruiter adds ex-Copart CEO Jeffrey Liaw to its board", "20261102T210852", 0.645034)
FORM_4 = item("Form 4 T. Rowe Price U.S. Equity Research Fund For: 2 November", "20261102T193726", 0.627732)
HIDDEN_GOOGLE = item("Apple\u2019s Hidden Google Problem Could Cost It Billions", "20261102T192822", 0.300121)
WALL_ST = item("Should Apple (AAPL) Stock Worry About Ternus\u2019 First Call And Rising Chip Costs?", "20261102T180712", 1.0, source="Yahoo Finance Singapore")
MICRON = item("Micron Technology Inc Stock (MU) Moved Down by 3.07% on Nov 2", "20261102T171537", 0.611507)
OPTIONS = item("Are Options Traders Betting on a Big Move in Apple Stock?", "20261102T160915", 1.0, source="TradingView")


def fake_news(monkeypatch, items, name="Apple Inc"):
    monkeypatch.setattr(news_service, "_fetch_raw_news", lambda symbol: items)
    monkeypatch.setattr(news_service, "_company_name", lambda symbol: name)


def titles(articles):
    return [a["title"] for a in articles]


def test_article_is_normalized():
    assert news_service.normalize_article(WALL_ST, "AAPL") == {
        "id": WALL_ST["url"],
        "title": "Should Apple (AAPL) Stock Worry About Ternus\u2019 First Call And Rising Chip Costs?",
        "source": "Yahoo Finance Singapore",
        "url": WALL_ST["url"],
        "publishedAt": "2026-11-02T18:07:12+00:00",
        "summary": "Short summary.",
        "imageUrl": "https://example.com/banner.jpg",
        "sentiment": {"label": "Somewhat-Bullish", "score": 0.21},
        "relevance": 1.0,
        "topics": ["Technology", "Earnings"],
    }


def test_sentiment_falls_back_to_the_whole_article():
    raw = {**WALL_ST, "ticker_sentiment": [{"ticker": "AAPL", "relevance_score": "1.0"}]}
    article = news_service.normalize_article(raw, "AAPL")
    assert article["sentiment"] == {"label": "Neutral", "score": 0.01}


def test_no_sentiment_gives_none():
    raw = {k: v for k, v in WALL_ST.items() if k != "overall_sentiment_label"}
    raw["ticker_sentiment"] = []
    assert news_service.normalize_article(raw, "AAPL")["sentiment"] is None


def test_bad_image_link_is_dropped_but_article_is_kept():
    raw = {**WALL_ST, "banner_image": "javascript:alert(1)"}
    assert news_service.normalize_article(raw, "AAPL")["imageUrl"] is None


def test_items_missing_headline_link_or_time_are_dropped():
    for broken in ({**WALL_ST, "title": ""}, {**WALL_ST, "url": None}, {**WALL_ST, "time_published": "soon"}):
        assert news_service.normalize_article(broken, "AAPL") is None


def test_only_web_links_are_kept():
    assert news_service.normalize_article({**WALL_ST, "url": "javascript:alert(1)"}, "AAPL") is None


def test_missing_source_gets_a_label():
    assert news_service.normalize_article({**WALL_ST, "source": None}, "AAPL")["source"] == "Unknown source"


def test_noisy_articles_are_filtered_out(monkeypatch):
    fake_news(monkeypatch, [ZIPRECRUITER, FORM_4, HIDDEN_GOOGLE, WALL_ST, MICRON, OPTIONS])
    assert titles(news_service.get_news("AAPL")) == [
        "Apple\u2019s Hidden Google Problem Could Cost It Billions",
        "Should Apple (AAPL) Stock Worry About Ternus\u2019 First Call And Rising Chip Costs?",
        "Are Options Traders Betting on a Big Move in Apple Stock?",
    ]


def test_high_relevance_is_kept_even_without_the_name(monkeypatch):
    sneaky = item("iPhone sales beat forecasts", "20261102T100000", 0.95)
    fake_news(monkeypatch, [sneaky])
    assert len(news_service.get_news("AAPL")) == 1


def test_name_mention_needs_a_minimum_relevance(monkeypatch):
    barely = item("Apple is mentioned in passing here", "20261102T100000", 0.05)
    fake_news(monkeypatch, [barely])
    assert news_service.get_news("AAPL") == []


def test_word_must_match_whole_word(monkeypatch):
    fake_news(monkeypatch, [item("Pineapple prices rise", "20261102T100000", 0.5)])
    assert news_service.get_news("AAPL") == []


def test_ticker_in_headline_counts_when_name_is_unknown(monkeypatch):
    fake_news(monkeypatch, [item("AAPL options volume jumps", "20261102T100000", 0.5)], name=None)
    assert len(news_service.get_news("AAPL")) == 1


def test_articles_about_other_tickers_are_not_relevant(monkeypatch):
    other = item("Apple rumors", "20261102T100000", 0.99, ticker="MSFT")
    fake_news(monkeypatch, [other])
    assert news_service.get_news("AAPL") == []


def test_articles_are_newest_first_without_duplicates(monkeypatch):
    first = item("Apple story one", "20261102T090000", 1.0)
    second = item("Apple story two", "20261102T150000", 1.0)
    third = item("Apple story three", "20261102T120000", 1.0)
    fake_news(monkeypatch, [first, second, third, second])
    assert titles(news_service.get_news("AAPL")) == [
        "Apple story two",
        "Apple story three",
        "Apple story one",
    ]


def test_limit_is_applied(monkeypatch):
    fake_news(monkeypatch, [item(f"Apple story {n}", f"20261102T{n:02d}0000", 1.0) for n in range(1, 8)])
    assert len(news_service.get_news("AAPL", limit=3)) == 3


def test_no_news_gives_empty_list(monkeypatch):
    fake_news(monkeypatch, [])
    assert news_service.get_news("AAPL") == []


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Apple Inc", ["apple"]),
        ("Meta Platforms Inc - Class A Common Stock", ["meta platforms", "meta"]),
        ("Bank of America Corp", ["bank of america"]),
        (None, []),
    ],
)
def test_name_keywords(name, expected):
    assert news_service._name_keywords(name) == expected


def test_route_returns_articles_for_logged_in_user(client, monkeypatch):
    fake_news(monkeypatch, [WALL_ST])
    res = client.get("/api/stocks/aapl/news")
    assert res.status_code == 200
    assert res.json()[0]["source"] == "Yahoo Finance Singapore"


def test_route_returns_empty_list_when_no_news(client, monkeypatch):
    fake_news(monkeypatch, [])
    res = client.get("/api/stocks/AAPL/news")
    assert res.status_code == 200
    assert res.json() == []


def test_route_reports_502_when_alpha_vantage_fails(client, monkeypatch):
    def broken(symbol):
        raise DataUnavailableError("down")

    monkeypatch.setattr(news_service, "_fetch_raw_news", broken)
    res = client.get("/api/stocks/AAPL/news")
    assert res.status_code == 502
    assert res.json()["detail"] == "News is unavailable right now"


def test_route_rejects_bad_symbol(client):
    assert client.get("/api/stocks/AA PL$/news").status_code == 400


def test_route_requires_login(logged_out_client):
    assert logged_out_client.get("/api/stocks/AAPL/news").status_code == 401


def test_missing_company_list_does_not_break_news(monkeypatch):
    monkeypatch.setattr(news_service, "_fetch_raw_news", lambda symbol: [WALL_ST, ZIPRECRUITER])

    def listing_down():
        raise DataUnavailableError("listing down")

    monkeypatch.setattr(news_service, "company_names", listing_down)
    assert titles(news_service.get_news("AAPL")) == [titles([WALL_ST])[0]]


def test_cache_reuses_result_and_survives_short_outage(monkeypatch):
    calls = {"n": 0}

    def flaky(symbol):
        calls["n"] += 1
        if calls["n"] > 1:
            raise DataUnavailableError("down")
        return [WALL_ST]

    monkeypatch.setattr(news_service, "_fetch_raw_news", flaky)
    monkeypatch.setattr(news_service, "_company_name", lambda symbol: "Apple Inc")
    first = news_service.get_news("AAPL")
    assert news_service.get_news("AAPL") == first
    assert calls["n"] == 1  # second call came from the cache

    # Force the cache entry to look old: the next call tries again, fails, reuses it
    key, (stamp, value) = next(iter(news_service._cache._items.items()))
    news_service._cache._items[key] = (stamp - news_service.NEWS_TTL_SECONDS - 1, value)
    assert news_service.get_news("AAPL") == first
    assert calls["n"] == 2


def test_error_raised_when_alpha_vantage_fails_and_nothing_cached(monkeypatch):
    def broken(symbol):
        raise DataUnavailableError("down")

    monkeypatch.setattr(news_service, "_fetch_raw_news", broken)
    with pytest.raises(DataUnavailableError):
        news_service.get_news("AAPL")
