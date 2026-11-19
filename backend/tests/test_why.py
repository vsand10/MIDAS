# Tests for WHY-01 (summary), SRC-01 (sources) and WHY-02 (key drivers)
# (no internet needed: Alpha Vantage and the AI service are replaced with fakes)

import json
from datetime import UTC, datetime, timedelta

import pytest

from app.services import gemini, market_service, news_service, why_service
from app.services.alphavantage import DataUnavailableError

from .test_market import quote


def article(title, hours_ago=2, summary="The company said so.", source="Reuters"):
    return {
        "id": title,
        "title": title,
        "source": source,
        "url": f"https://example.com/{title.replace(' ', '-')}",
        "publishedAt": (datetime.now(UTC) - timedelta(hours=hours_ago)).isoformat(),
        "summary": summary,
    }


def reply(summary="Shares rose after record earnings.", drivers=None, sources=(1,)):
    """What the AI sends back, as the JSON text."""
    return json.dumps({"summary": summary, "drivers": drivers or [], "sources": list(sources)})


def driver(title="Record earnings", description="Profit beat forecasts.", article_number=1):
    return {"title": title, "description": description, "article": article_number}


class FakeAI:
    """Stands in for the AI service and remembers what it was asked."""

    def __init__(
        self,
        answer=None,
        web_answer="INSUFFICIENT",
        web_sources=(),
        web_citations=(),
        web_answers=(),
    ):
        self.answer = answer if answer is not None else reply()
        # What Google Search finds when the news articles are not enough (grounded calls)
        self.web_answer = web_answer
        self.web_sources = list(web_sources)
        self.web_citations = list(web_citations)  # which source backs which words
        self.web_answers = list(web_answers)  # answers for the 1st, 2nd... web try, then web_answer
        self.calls = []

    def __call__(self, system, contents, *, grounded=True, json_output=False):
        prompt = contents[0]["parts"][0]["text"]
        self.calls.append(
            {"system": system, "prompt": prompt, "json_output": json_output, "grounded": grounded}
        )
        if grounded:
            reply_text = self.web_answers.pop(0) if self.web_answers else self.web_answer
            return {
                "reply": reply_text,
                "sources": self.web_sources,
                "citations": self.web_citations,
            }
        return {"reply": self.answer, "sources": []}


COMPARISON = {
    "indexes": [
        {"name": "S&P 500", "changePercent": 0.42},
        {"name": "Nasdaq", "changePercent": 0.9},
        {"name": "Dow Jones", "changePercent": -0.15},
    ],
    "sector": {"name": "Technology", "etf": "XLK", "changePercent": 1.2},
}


def setup(monkeypatch, *, articles, ai=None, price=110.0, previous=100.0, comparison=COMPARISON):
    ai = ai or FakeAI()
    monkeypatch.setattr(why_service, "market_comparison", lambda symbol: comparison)
    monkeypatch.setattr(why_service, "company_name", lambda symbol: "Apple Inc")
    monkeypatch.setattr(
        market_service, "_fetch_quotes", lambda symbols: [quote(s, price, previous) for s in symbols]
    )
    monkeypatch.setattr(news_service, "get_news", lambda symbol, limit=10: articles)
    monkeypatch.setattr(gemini, "generate", ai)
    return ai


FOUR = [article("Record earnings"), article("New chip launched"), article("Analyst upgrade"), article("Buyback")]


# ---------------- WHY-01 AC 1: the summary ----------------


def test_summary_explains_the_move(monkeypatch):
    ai = setup(monkeypatch, articles=[article("Record earnings beat forecasts")])
    result = why_service.get_why_it_moved("aapl")

    assert result["status"] == "ok"
    assert result["summary"] == "Shares rose after record earnings."
    assert result["changePercent"] == 10.0
    assert len(ai.calls) == 1
    assert ai.calls[0]["json_output"] is True
    assert ai.calls[0]["grounded"] is False  # the summary never uses web search


def test_summary_is_cut_to_three_sentences(monkeypatch):
    setup(
        monkeypatch,
        articles=[article("News")],
        ai=FakeAI(reply(summary="One. Two. Three. Four. Five.")),
    )
    assert why_service.get_why_it_moved("AAPL")["summary"] == "One. Two. Three."


def test_prompt_contains_the_move_and_the_news(monkeypatch):
    ai = setup(monkeypatch, articles=[article("Record earnings beat forecasts")])
    why_service.get_why_it_moved("AAPL")
    call = ai.calls[0]

    assert "up 10.00%" in call["prompt"]
    assert "Record earnings beat forecasts" in call["prompt"]
    assert "ONLY the headlines" in call["system"]  # no outside knowledge


def test_down_move_is_described_as_down(monkeypatch):
    ai = setup(monkeypatch, articles=[article("Recall announced")], price=95.0, previous=100.0)
    why_service.get_why_it_moved("AAPL")
    assert "down 5.00%" in ai.calls[0]["prompt"]


def test_old_articles_are_not_sent_to_the_ai(monkeypatch):
    ai = setup(
        monkeypatch,
        articles=[article("Fresh story", hours_ago=3), article("Ancient story", hours_ago=200)],
    )
    why_service.get_why_it_moved("AAPL")
    assert "Fresh story" in ai.calls[0]["prompt"]
    assert "Ancient story" not in ai.calls[0]["prompt"]


# ---------------- WHY-01 AC 2: not enough data ----------------


def test_no_news_and_no_web_result_means_not_enough_information(monkeypatch):
    ai = setup(monkeypatch, articles=[])
    result = why_service.get_why_it_moved("AAPL")

    assert result["status"] == "insufficient"
    assert result["message"] == "Not enough information to explain this move"
    assert result["summary"] is None
    assert [c["grounded"] for c in ai.calls] == [True, True]  # the web search, tried twice


def test_only_old_news_counts_as_no_news(monkeypatch):
    ai = setup(monkeypatch, articles=[article("Ancient story", hours_ago=200)])
    assert why_service.get_why_it_moved("AAPL")["status"] == "insufficient"
    assert [c["grounded"] for c in ai.calls] == [True, True]


def test_ai_saying_insufficient_shows_the_same_message(monkeypatch):
    setup(monkeypatch, articles=[article("Unrelated")], ai=FakeAI('{"insufficient": true}'))
    result = why_service.get_why_it_moved("AAPL")
    assert result["status"] == "insufficient"
    assert result["message"] == "Not enough information to explain this move"


def test_empty_summary_is_not_shown(monkeypatch):
    setup(monkeypatch, articles=[article("News")], ai=FakeAI(reply(summary="   ")))
    assert why_service.get_why_it_moved("AAPL")["status"] == "insufficient"


# ---------------- Web fallback: Google Search when the news is not enough ----------------

WEB_SOURCES = [
    {"title": "reuters.com", "url": "https://vertexaisearch.example/a"},
    {"title": "cnbc.com", "url": "https://vertexaisearch.example/b"},
]
WEB_SUMMARY = "Shares rose after the company raised its forecast."


def test_news_that_explains_the_move_never_uses_web_search(monkeypatch):
    ai = setup(monkeypatch, articles=[article("Record earnings")])
    result = why_service.get_why_it_moved("AAPL")

    assert result["origin"] == "articles"
    assert [c["grounded"] for c in ai.calls] == [False]


def test_no_news_falls_back_to_web_search(monkeypatch):
    ai = setup(
        monkeypatch,
        articles=[],
        ai=FakeAI(web_answer=WEB_SUMMARY, web_sources=WEB_SOURCES),
    )
    result = why_service.get_why_it_moved("AAPL")

    assert result["status"] == "ok"
    assert result["origin"] == "web"
    assert result["summary"] == WEB_SUMMARY
    assert result["comparison"] == COMPARISON
    assert result["drivers"] == []
    assert result["driversMessage"] == "No key drivers identified"
    assert ai.calls[0]["grounded"] is True
    assert ai.calls[0]["json_output"] is False  # Gemini cannot search and reply in JSON together


def test_web_sources_look_like_article_sources(monkeypatch):
    setup(monkeypatch, articles=[], ai=FakeAI(web_answer=WEB_SUMMARY, web_sources=WEB_SOURCES))
    sources = why_service.get_why_it_moved("AAPL")["sources"]

    assert sources == [
        {
            "title": "reuters.com",
            "source": "Web search",
            "url": "https://vertexaisearch.example/a",
            "publishedAt": None,
        },
        {
            "title": "cnbc.com",
            "source": "Web search",
            "url": "https://vertexaisearch.example/b",
            "publishedAt": None,
        },
    ]


def test_ai_saying_insufficient_about_the_news_tries_web_search(monkeypatch):
    ai = setup(
        monkeypatch,
        articles=[article("Unrelated")],
        ai=FakeAI('{"insufficient": true}', web_answer=WEB_SUMMARY, web_sources=WEB_SOURCES),
    )
    result = why_service.get_why_it_moved("AAPL")

    assert result["origin"] == "web"
    assert [c["grounded"] for c in ai.calls] == [False, True]


def test_web_search_that_finds_no_reason_is_not_enough_information(monkeypatch):
    setup(
        monkeypatch,
        articles=[],
        ai=FakeAI(web_answer="INSUFFICIENT.", web_sources=WEB_SOURCES),
    )
    assert why_service.get_why_it_moved("AAPL")["status"] == "insufficient"


def test_web_summary_without_sources_is_not_shown(monkeypatch):
    setup(monkeypatch, articles=[], ai=FakeAI(web_answer=WEB_SUMMARY, web_sources=[]))
    assert why_service.get_why_it_moved("AAPL")["status"] == "insufficient"


def test_web_summary_is_cut_to_three_sentences(monkeypatch):
    setup(
        monkeypatch,
        articles=[],
        ai=FakeAI(web_answer="One. Two. Three. Four.", web_sources=WEB_SOURCES),
    )
    assert why_service.get_why_it_moved("AAPL")["summary"] == "One. Two. Three."


def test_at_most_five_web_sources_are_listed(monkeypatch):
    many = [{"title": f"site{i}.com", "url": f"https://example.com/{i}"} for i in range(8)]
    setup(monkeypatch, articles=[], ai=FakeAI(web_answer=WEB_SUMMARY, web_sources=many))
    assert len(why_service.get_why_it_moved("AAPL")["sources"]) == 5


def test_a_failed_web_search_is_not_an_error(monkeypatch):
    class WebDown(FakeAI):
        def __call__(self, system, contents, *, grounded=True, json_output=False):
            if grounded:
                raise gemini.GeminiRateLimitedError("busy")
            return super().__call__(system, contents, grounded=grounded, json_output=json_output)

    setup(monkeypatch, articles=[], ai=WebDown())
    result = why_service.get_why_it_moved("AAPL")
    assert result["status"] == "insufficient"


def test_web_prompt_has_the_move_and_the_market_but_no_articles(monkeypatch):
    ai = setup(monkeypatch, articles=[], ai=FakeAI(web_answer=WEB_SUMMARY, web_sources=WEB_SOURCES))
    why_service.get_why_it_moved("AAPL")
    prompt = ai.calls[0]["prompt"]

    assert "Stock ticker: AAPL" in prompt
    assert "up 10.00%" in prompt
    assert "S&P 500: +0.42%" in prompt
    assert "<articles>" not in prompt


def test_web_system_prompt_says_how_to_give_up_and_what_not_to_use():
    assert '{"insufficient": true}' in why_service.WEB_SYSTEM_PROMPT
    assert "NOT a news source" in why_service.WEB_SYSTEM_PROMPT


def test_web_result_is_saved_too(monkeypatch):
    ai = setup(monkeypatch, articles=[], ai=FakeAI(web_answer=WEB_SUMMARY, web_sources=WEB_SOURCES))
    why_service.get_why_it_moved("AAPL")
    why_service.get_why_it_moved("AAPL")
    assert len(ai.calls) == 1


# ---------------- Key drivers from the web search ----------------


def web_reply(summary=WEB_SUMMARY, drivers=None):
    return json.dumps({"summary": summary, "drivers": drivers or []})


def web_driver(title="Raised forecast", description="The company raised its yearly forecast.", site=""):
    return {"title": title, "description": description, "site": site}


CITATIONS = [
    {"text": "The company raised its yearly forecast.", "urls": ["https://vertexaisearch.example/a"]},
    {"text": "A big customer signed a new deal.", "urls": ["https://vertexaisearch.example/b"]},
]
TWO_DRIVERS = [
    web_driver(),
    web_driver("New customer deal", "A big customer signed a new deal."),
]


def web_result(monkeypatch, *, answer, citations=CITATIONS, sources=WEB_SOURCES):
    setup(
        monkeypatch,
        articles=[],
        ai=FakeAI(web_answer=answer, web_sources=sources, web_citations=citations),
    )
    return why_service.get_why_it_moved("AAPL")


def test_web_search_is_tried_again_when_the_first_try_finds_nothing(monkeypatch):
    ai = setup(
        monkeypatch,
        articles=[],
        ai=FakeAI(
            web_answers=["INSUFFICIENT", WEB_SUMMARY],
            web_sources=WEB_SOURCES,
        ),
    )
    result = why_service.get_why_it_moved("AAPL")

    assert result["status"] == "ok"
    assert result["origin"] == "web"
    assert [c["grounded"] for c in ai.calls] == [True, True]


def test_a_try_with_a_summary_but_no_sources_is_also_repeated(monkeypatch):
    class NoSourcesFirst(FakeAI):
        def __call__(self, system, contents, *, grounded=True, json_output=False):
            out = super().__call__(system, contents, grounded=grounded, json_output=json_output)
            if grounded and len(self.calls) == 1:
                out["sources"] = []
            return out

    ai = setup(
        monkeypatch,
        articles=[],
        ai=NoSourcesFirst(web_answer=WEB_SUMMARY, web_sources=WEB_SOURCES),
    )
    assert why_service.get_why_it_moved("AAPL")["status"] == "ok"
    assert len(ai.calls) == 2


def test_a_gemini_error_is_not_tried_again(monkeypatch):
    setup(monkeypatch, articles=[])
    tries = []

    def broken(system, contents, *, grounded=True, json_output=False):
        tries.append(grounded)
        raise gemini.GeminiRateLimitedError("busy")

    monkeypatch.setattr(gemini, "generate", broken)
    assert why_service.get_why_it_moved("AAPL")["status"] == "insufficient"
    assert tries == [True]


def test_web_prompt_names_the_company_when_known(monkeypatch):
    ai = setup(monkeypatch, articles=[], ai=FakeAI(web_answer=WEB_SUMMARY, web_sources=WEB_SOURCES))
    why_service.get_why_it_moved("AAPL")
    assert "Company name: Apple Inc" in ai.calls[0]["prompt"]


def test_web_prompt_works_without_a_company_name():
    prompt = why_service.build_web_prompt("AAPL", 2.5)
    assert "Company name" not in prompt
    assert "Stock ticker: AAPL" in prompt


def test_web_prompt_accepts_sector_and_market_wide_reasons():
    assert "sector" in why_service.WEB_SYSTEM_PROMPT
    assert "whole market" in why_service.WEB_SYSTEM_PROMPT


def test_company_name_and_sector_come_from_one_lookup(monkeypatch):
    lookups = []

    def overview(function, **params):
        lookups.append(function)
        return {"Name": "Exxon Mobil Corp", "Sector": "Energy"}

    monkeypatch.setattr(why_service, "av_get", overview)
    assert why_service.company_name("XOM") == "Exxon Mobil Corp"
    assert why_service._company_sector("XOM") == "ENERGY"
    assert lookups == ["OVERVIEW"]


def test_company_name_is_none_when_alpha_vantage_is_down(monkeypatch):
    def down(function, **params):
        raise DataUnavailableError("down")

    monkeypatch.setattr(why_service, "av_get", down)
    assert why_service.company_name("XOM") is None


def test_web_drivers_are_matched_to_sources_by_googles_citations(monkeypatch):
    result = web_result(monkeypatch, answer=web_reply(drivers=TWO_DRIVERS))

    assert [d["title"] for d in result["drivers"]] == ["Raised forecast", "New customer deal"]
    assert result["drivers"][0]["source"]["url"] == "https://vertexaisearch.example/a"
    assert result["drivers"][1]["source"]["url"] == "https://vertexaisearch.example/b"
    assert result["drivers"][0]["source"]["source"] == "Web search"
    assert result["driversMessage"] is None
    assert result["summary"] == WEB_SUMMARY


def test_web_drivers_are_matched_by_shared_words_when_googles_text_is_different(monkeypatch):
    # Like a real reply: Google cited one sentence of the summary, backed by two sources
    citations = [
        {
            "text": "The decline was driven by tumbling global crude oil prices, rising domestic "
            "fuel inventories, and post-ex-dividend selling pressure.",
            "urls": ["https://vertexaisearch.example/a", "https://vertexaisearch.example/b"],
        }
    ]
    drivers = [
        web_driver(
            "Crude oil and energy sell-off",
            "Global crude oil benchmarks tumbled and U.S. inventory builds weighed on energy.",
            site="reuters.com",  # not one of the real sources, so it cannot be used
        ),
        web_driver(
            "Post-ex-dividend selling pressure",
            "The stock faced income-focused distribution pressure after its ex-dividend date.",
            site="marketbeat.com",
        ),
    ]
    result = web_result(monkeypatch, answer=web_reply(drivers=drivers), citations=citations)

    assert [d["title"] for d in result["drivers"]] == [d["title"] for d in drivers]
    assert result["drivers"][0]["source"]["url"] == "https://vertexaisearch.example/a"


def test_web_driver_that_shares_too_few_words_with_a_citation_is_dropped(monkeypatch):
    citations = [{"text": "Crude oil prices tumbled worldwide.", "urls": ["https://vertexaisearch.example/a"]}]
    drivers = [
        web_driver("Crude weakness", "Crude oil prices tumbled."),
        web_driver("Tariff news", "A new tariff was announced on imports.", site="unknown.com"),
    ]
    result = web_result(monkeypatch, answer=web_reply(drivers=drivers), citations=citations)

    # Only one driver has a source, and one driver is not enough to show
    assert result["drivers"] == []


def test_the_exact_citation_beats_a_looser_match(monkeypatch):
    citations = [
        {"text": "Crude oil prices tumbled on rising global inventories.", "urls": ["https://vertexaisearch.example/a"]},
        {"text": "The company raised its yearly forecast.", "urls": ["https://vertexaisearch.example/b"]},
    ]
    drivers = [
        web_driver("Raised forecast", "The company raised its yearly forecast."),
        web_driver("Crude weakness", "Crude oil prices tumbled on rising global inventories."),
    ]
    result = web_result(monkeypatch, answer=web_reply(drivers=drivers), citations=citations)

    assert result["drivers"][0]["source"]["url"] == "https://vertexaisearch.example/b"
    assert result["drivers"][1]["source"]["url"] == "https://vertexaisearch.example/a"


def test_web_driver_without_a_citation_uses_the_site_the_ai_named(monkeypatch):
    drivers = [
        web_driver("Raised forecast", "Guidance went up.", site="www.reuters.com"),
        web_driver("New customer deal", "A deal was signed.", site="cnbc.com"),
    ]
    result = web_result(monkeypatch, answer=web_reply(drivers=drivers), citations=[])

    assert result["drivers"][0]["source"]["url"] == "https://vertexaisearch.example/a"
    assert result["drivers"][1]["source"]["url"] == "https://vertexaisearch.example/b"


def test_web_driver_with_no_source_is_dropped(monkeypatch):
    drivers = [*TWO_DRIVERS, web_driver("Unbacked", "Nobody reported this.", site="unknown.com")]
    result = web_result(monkeypatch, answer=web_reply(drivers=drivers))
    assert [d["title"] for d in result["drivers"]] == ["Raised forecast", "New customer deal"]


def test_one_web_driver_is_not_enough_to_show(monkeypatch):
    result = web_result(monkeypatch, answer=web_reply(drivers=TWO_DRIVERS[:1]))

    assert result["status"] == "ok"
    assert result["drivers"] == []
    assert result["driversMessage"] == "No key drivers identified"


def test_at_most_four_web_drivers_are_kept(monkeypatch):
    drivers = [web_driver(f"Event {i}", "The company raised its yearly forecast.") for i in range(6)]
    result = web_result(monkeypatch, answer=web_reply(drivers=drivers))
    assert len(result["drivers"]) == 4


def test_a_plain_text_web_reply_still_gives_a_summary_without_drivers(monkeypatch):
    result = web_result(monkeypatch, answer=WEB_SUMMARY)

    assert result["status"] == "ok"
    assert result["summary"] == WEB_SUMMARY
    assert result["drivers"] == []


def test_web_reply_saying_insufficient_in_json_is_not_enough_information(monkeypatch):
    result = web_result(monkeypatch, answer='{"insufficient": true}')
    assert result["status"] == "insufficient"


def test_web_driver_sources_are_listed_first_and_always_kept(monkeypatch):
    many = [{"title": f"site{i}.com", "url": f"https://example.com/{i}"} for i in range(7)]
    citations = [{"text": "The company raised its yearly forecast.", "urls": ["https://example.com/6"]}]
    drivers = [
        web_driver(),
        web_driver("Second", "Another event.", site="site5.com"),
    ]
    result = web_result(
        monkeypatch, answer=web_reply(drivers=drivers), citations=citations, sources=many
    )

    urls = [s["url"] for s in result["sources"]]
    assert len(urls) == 5
    assert urls[:2] == ["https://example.com/6", "https://example.com/5"]


def test_web_drivers_are_sent_to_the_screen(client, monkeypatch):
    setup(
        monkeypatch,
        articles=[],
        ai=FakeAI(
            web_answer=web_reply(drivers=TWO_DRIVERS),
            web_sources=WEB_SOURCES,
            web_citations=CITATIONS,
        ),
    )
    body = client.get("/api/stocks/AAPL/why-moved").json()
    assert body["origin"] == "web"
    assert len(body["drivers"]) == 2
    assert body["drivers"][0]["source"]["url"].startswith("https://")


def age_saved_result(symbol, seconds):
    """Makes the saved result look `seconds` older."""
    key = f"why:{symbol}"
    stamp, value = why_service._cache._items[key]
    why_service._cache._items[key] = (stamp - seconds, value)


def test_not_enough_information_is_only_kept_for_five_minutes(monkeypatch):
    ai = setup(monkeypatch, articles=[])
    why_service.get_why_it_moved("AAPL")
    first_calls = len(ai.calls)

    age_saved_result("AAPL", why_service.MISS_TTL_SECONDS - 10)
    why_service.get_why_it_moved("AAPL")
    assert len(ai.calls) == first_calls  # still saved

    age_saved_result("AAPL", 20)
    why_service.get_why_it_moved("AAPL")
    assert len(ai.calls) > first_calls  # expired, searched again


def test_a_good_answer_is_still_kept_for_thirty_minutes(monkeypatch):
    ai = setup(monkeypatch, articles=[article("Record earnings")])
    why_service.get_why_it_moved("AAPL")

    age_saved_result("AAPL", why_service.WHY_TTL_SECONDS - 10)
    why_service.get_why_it_moved("AAPL")
    assert len(ai.calls) == 1

    age_saved_result("AAPL", 20)
    why_service.get_why_it_moved("AAPL")
    assert len(ai.calls) == 2


# ---------------- WHY-01 AC 3: caching ----------------


def test_second_request_uses_the_saved_result(monkeypatch):
    ai = setup(monkeypatch, articles=[article("Record earnings")])
    first = why_service.get_why_it_moved("AAPL")
    second = why_service.get_why_it_moved("aapl")

    assert second == first
    assert len(ai.calls) == 1  # no second AI request


def test_different_stocks_are_cached_separately(monkeypatch):
    ai = setup(monkeypatch, articles=[article("News")])
    why_service.get_why_it_moved("AAPL")
    why_service.get_why_it_moved("MSFT")
    assert len(ai.calls) == 2


def test_failed_ai_call_is_not_saved(monkeypatch):
    ai = setup(monkeypatch, articles=[article("News")])

    def broken(system, contents, *, grounded=True, json_output=False):
        raise gemini.GeminiRateLimitedError("busy")

    monkeypatch.setattr(gemini, "generate", broken)
    with pytest.raises(DataUnavailableError):
        why_service.get_why_it_moved("AAPL")

    monkeypatch.setattr(gemini, "generate", ai)  # the AI is back
    assert why_service.get_why_it_moved("AAPL")["status"] == "ok"


def test_no_price_data_is_unavailable(monkeypatch):
    setup(monkeypatch, articles=[article("News")])
    monkeypatch.setattr(market_service, "_fetch_quotes", lambda symbols: [])
    with pytest.raises(DataUnavailableError):
        why_service.get_why_it_moved("AAPL")


# ---------------- SRC-01: sources ----------------


def test_each_source_has_publisher_title_date_and_link(monkeypatch):
    articles = [article("Record earnings", source="Reuters")]
    setup(monkeypatch, articles=articles)
    [source] = why_service.get_why_it_moved("AAPL")["sources"]

    assert source["source"] == "Reuters"
    assert source["title"] == "Record earnings"
    assert source["url"] == "https://example.com/Record-earnings"
    assert source["publishedAt"] == articles[0]["publishedAt"]


def test_several_sources_are_listed_in_the_order_cited(monkeypatch):
    setup(monkeypatch, articles=FOUR, ai=FakeAI(reply(sources=[3, 1, 2])))
    titles = [s["title"] for s in why_service.get_why_it_moved("AAPL")["sources"]]
    assert titles == ["Analyst upgrade", "Record earnings", "New chip launched"]


def test_only_cited_articles_are_listed_as_sources(monkeypatch):
    setup(monkeypatch, articles=FOUR, ai=FakeAI(reply(sources=[4])))
    titles = [s["title"] for s in why_service.get_why_it_moved("AAPL")["sources"]]
    assert titles == ["Buyback"]  # not just the newest three


def test_repeated_and_invalid_citations_are_ignored(monkeypatch):
    setup(monkeypatch, articles=FOUR, ai=FakeAI(reply(sources=[2, 2, 99, 0, "1", True, None])))
    titles = [s["title"] for s in why_service.get_why_it_moved("AAPL")["sources"]]
    assert titles == ["New chip launched"]


def test_a_summary_with_no_sources_is_not_shown(monkeypatch):
    setup(monkeypatch, articles=FOUR, ai=FakeAI(reply(sources=[])))
    result = why_service.get_why_it_moved("AAPL")
    assert result["status"] == "insufficient"
    assert result["summary"] is None
    assert result["message"] == "Not enough information to explain this move"


def test_a_summary_citing_only_invalid_sources_is_not_shown(monkeypatch):
    setup(monkeypatch, articles=FOUR, ai=FakeAI(reply(sources=[42])))
    assert why_service.get_why_it_moved("AAPL")["status"] == "insufficient"


# ---------------- WHY-02: key drivers ----------------


def test_two_to_four_drivers_with_title_description_and_article(monkeypatch):
    drivers = [
        driver("Record earnings", "Profit beat forecasts.", 1),
        driver("New chip launched", "A faster chip was announced.", 2),
    ]
    setup(monkeypatch, articles=FOUR, ai=FakeAI(reply(drivers=drivers, sources=[1, 2])))
    result = why_service.get_why_it_moved("AAPL")

    assert [d["title"] for d in result["drivers"]] == ["Record earnings", "New chip launched"]
    first = result["drivers"][0]
    assert first["description"] == "Profit beat forecasts."
    assert first["source"]["url"] == "https://example.com/Record-earnings"
    assert first["source"]["title"] == "Record earnings"
    assert "article" not in first  # the internal number is not sent to the browser
    assert result["driversMessage"] is None


def test_at_most_four_drivers_are_kept(monkeypatch):
    drivers = [driver(f"Driver {i}", "Something happened.", (i % 4) + 1) for i in range(6)]
    setup(monkeypatch, articles=FOUR, ai=FakeAI(reply(drivers=drivers)))
    assert len(why_service.get_why_it_moved("AAPL")["drivers"]) == 4


def test_one_driver_is_not_enough_to_show(monkeypatch):
    setup(monkeypatch, articles=FOUR, ai=FakeAI(reply(drivers=[driver()])))
    result = why_service.get_why_it_moved("AAPL")

    assert result["status"] == "ok"  # the summary still shows
    assert result["drivers"] == []
    assert result["driversMessage"] == "No key drivers identified"


def test_no_drivers_gives_the_no_drivers_message(monkeypatch):
    setup(monkeypatch, articles=FOUR, ai=FakeAI(reply(drivers=[])))
    result = why_service.get_why_it_moved("AAPL")
    assert result["drivers"] == []
    assert result["driversMessage"] == "No key drivers identified"


def test_drivers_pointing_at_missing_articles_are_dropped(monkeypatch):
    drivers = [driver("Good one", "Real event.", 1), driver("Made up", "No such article.", 9)]
    setup(monkeypatch, articles=FOUR, ai=FakeAI(reply(drivers=drivers)))
    result = why_service.get_why_it_moved("AAPL")
    assert result["drivers"] == []  # only one valid driver is left, so none are shown


def test_drivers_missing_a_title_or_description_are_dropped(monkeypatch):
    drivers = [
        driver("", "No title.", 1),
        driver("No description", "", 2),
        driver("Fine", "Has everything.", 3),
        driver("Also fine", "Has everything too.", 4),
    ]
    setup(monkeypatch, articles=FOUR, ai=FakeAI(reply(drivers=drivers)))
    titles = [d["title"] for d in why_service.get_why_it_moved("AAPL")["drivers"]]
    assert titles == ["Fine", "Also fine"]


def test_drivers_with_wrong_types_do_not_crash(monkeypatch):
    answer = json.dumps({"summary": "Up.", "drivers": "none", "sources": [1]})
    setup(monkeypatch, articles=FOUR, ai=FakeAI(answer))
    assert why_service.get_why_it_moved("AAPL")["driversMessage"] == "No key drivers identified"


def test_a_drivers_article_is_also_listed_as_a_source(monkeypatch):
    drivers = [driver("A", "First.", 3), driver("B", "Second.", 4)]
    setup(monkeypatch, articles=FOUR, ai=FakeAI(reply(drivers=drivers, sources=[1])))
    titles = [s["title"] for s in why_service.get_why_it_moved("AAPL")["sources"]]
    assert titles == ["Record earnings", "Analyst upgrade", "Buyback"]


def test_long_driver_text_is_shortened(monkeypatch):
    drivers = [driver("T" * 300, "D" * 600, 1), driver("Second", "Fine.", 2)]
    setup(monkeypatch, articles=FOUR, ai=FakeAI(reply(drivers=drivers)))
    first = why_service.get_why_it_moved("AAPL")["drivers"][0]
    assert len(first["title"]) == why_service.TITLE_CHARS
    assert len(first["description"]) == why_service.DESCRIPTION_CHARS


def test_drivers_are_made_for_several_stocks(monkeypatch):
    drivers = [driver("A", "First.", 1), driver("B", "Second.", 2)]
    setup(monkeypatch, articles=FOUR, ai=FakeAI(reply(drivers=drivers)))
    for symbol in ("AAPL", "MSFT", "NVDA"):
        assert len(why_service.get_why_it_moved(symbol)["drivers"]) == 2


# ---------------- Index and sector comparison ----------------


def test_prompt_includes_index_and_sector_moves(monkeypatch):
    ai = setup(monkeypatch, articles=[article("News")])
    why_service.get_why_it_moved("AAPL")
    prompt = ai.calls[0]["prompt"]

    assert "<market>" in prompt
    assert "S&P 500: +0.42%" in prompt
    assert "Dow Jones: -0.15%" in prompt
    assert "Technology sector (XLK): +1.20%" in prompt
    assert prompt.index("</market>") < prompt.index("<articles>")  # kept apart from the news


def test_system_prompt_says_market_figures_are_not_a_source():
    assert "NOT a news source" in why_service.SYSTEM_PROMPT


def test_comparison_is_returned_for_the_screen(monkeypatch):
    setup(monkeypatch, articles=[article("News")])
    assert why_service.get_why_it_moved("AAPL")["comparison"] == COMPARISON


def test_no_comparison_when_there_is_not_enough_information(monkeypatch):
    setup(monkeypatch, articles=[])
    assert why_service.get_why_it_moved("AAPL")["comparison"] is None


def test_summary_is_made_without_any_comparison_data(monkeypatch):
    empty = {"indexes": [], "sector": None}
    ai = setup(monkeypatch, articles=[article("News")], comparison=empty)
    result = why_service.get_why_it_moved("AAPL")

    assert result["status"] == "ok"
    assert "<market>" not in ai.calls[0]["prompt"]


def fake_market_data(monkeypatch, *, sector="TECHNOLOGY", etf_percent=1.234):
    """Fakes the three Alpha Vantage lookups market_comparison makes."""
    overview = [
        {"name": "S&P 500", "changePercent": 0.42, "value": 5000},
        {"name": "Nasdaq", "changePercent": 0.9, "value": 16000},
    ]
    monkeypatch.setattr(why_service, "get_market_overview", lambda: overview)
    monkeypatch.setattr(why_service, "av_get", lambda function, **params: {"Sector": sector})
    seen = []

    def percent(symbol):
        seen.append(symbol)
        return etf_percent

    monkeypatch.setattr(why_service, "_percent_change", percent)
    return seen


def test_comparison_finds_the_index_and_sector_moves(monkeypatch):
    seen = fake_market_data(monkeypatch)
    result = why_service.market_comparison("NVDA")

    assert [i["name"] for i in result["indexes"]] == ["S&P 500", "Nasdaq"]
    assert result["sector"] == {"name": "Technology", "etf": "XLK", "changePercent": 1.23}
    assert seen == ["XLK"]


@pytest.mark.parametrize(
    ("alpha_vantage_sector", "etf"),
    [
        ("FINANCE", "XLF"),
        ("LIFE SCIENCES", "XLV"),
        ("HEALTHCARE", "XLV"),
        ("ENERGY", "XLE"),
        ("REAL ESTATE", "XLRE"),
    ],
)
def test_sector_names_map_to_the_right_etf(monkeypatch, alpha_vantage_sector, etf):
    fake_market_data(monkeypatch, sector=alpha_vantage_sector)
    assert why_service.market_comparison("XYZ")["sector"]["etf"] == etf


def test_unknown_sector_is_left_out(monkeypatch):
    seen = fake_market_data(monkeypatch, sector="TRADE & SERVICES")
    result = why_service.market_comparison("XYZ")
    assert result["sector"] is None
    assert result["indexes"]  # the indexes still show
    assert seen == []


def test_sector_lookup_failure_leaves_the_indexes(monkeypatch):
    fake_market_data(monkeypatch)

    def fails(function, **params):
        raise DataUnavailableError("no overview")

    monkeypatch.setattr(why_service, "av_get", fails)
    result = why_service.market_comparison("XYZ")
    assert result["sector"] is None
    assert len(result["indexes"]) == 2


def test_index_failure_leaves_the_sector(monkeypatch):
    fake_market_data(monkeypatch)

    def fails():
        raise DataUnavailableError("no indexes")

    monkeypatch.setattr(why_service, "get_market_overview", fails)
    result = why_service.market_comparison("NVDA")
    assert result["indexes"] == []
    assert result["sector"]["etf"] == "XLK"


def test_sector_move_is_shared_between_stocks(monkeypatch):
    seen = fake_market_data(monkeypatch)
    why_service.market_comparison("NVDA")
    why_service.market_comparison("MSFT")
    assert seen == ["XLK"]  # one quote for both stocks


# ---------------- Reading the AI's reply ----------------


def test_reply_wrapped_in_code_fences_is_accepted(monkeypatch):
    fenced = "```json\n" + reply() + "\n```"
    setup(monkeypatch, articles=[article("News")], ai=FakeAI(fenced))
    assert why_service.get_why_it_moved("AAPL")["status"] == "ok"


@pytest.mark.parametrize("bad", ["Shares rose today.", "[1, 2]", "", "{broken"])
def test_a_reply_that_is_not_a_json_object_is_an_ai_failure(monkeypatch, bad):
    setup(monkeypatch, articles=[article("News")], ai=FakeAI(bad))
    with pytest.raises(DataUnavailableError):
        why_service.get_why_it_moved("AAPL")


@pytest.mark.parametrize(
    "error",
    [
        gemini.GeminiError("x"),
        gemini.GeminiNotConfiguredError("x"),
        gemini.GeminiRateLimitedError("x"),
        gemini.GeminiBlockedError("x"),
    ],
)
def test_every_gemini_problem_becomes_data_unavailable(monkeypatch, error):
    setup(monkeypatch, articles=[article("News")])

    def broken(system, contents, *, grounded=True, json_output=False):
        raise error

    monkeypatch.setattr(gemini, "generate", broken)
    with pytest.raises(DataUnavailableError):
        why_service.get_why_it_moved("AAPL")


# ---------------- The shared Gemini client ----------------


class FakeResponse:
    def __init__(self, text, status=200):
        self.status_code = status
        self._body = {"candidates": [{"content": {"parts": [{"text": text}]}}]}

    def json(self):
        return self._body


def sent_payload(monkeypatch, **options):
    sent = {}

    def fake_post(url, headers, payload):
        sent.update(payload=payload, headers=headers)
        return FakeResponse("{}")

    monkeypatch.setattr(gemini, "_post", fake_post)
    gemini.generate("system", [{"role": "user", "parts": [{"text": "hi"}]}], **options)
    return sent


def test_gemini_json_output_asks_for_json(monkeypatch):
    sent = sent_payload(monkeypatch, grounded=False, json_output=True)
    assert sent["payload"]["generationConfig"]["responseMimeType"] == "application/json"
    assert sent["headers"] == {"x-goog-api-key": "test-ai-key"}  # the key is never in the URL


def test_gemini_ungrounded_calls_do_not_use_web_search(monkeypatch):
    sent = sent_payload(monkeypatch, grounded=False)
    assert "tools" not in sent["payload"]


def test_gemini_chat_calls_still_use_web_search_by_default(monkeypatch):
    sent = sent_payload(monkeypatch)
    assert sent["payload"]["tools"] == [{"google_search": {}}]
    assert "responseMimeType" not in sent["payload"]["generationConfig"]


def test_gemini_returns_reply_and_sources(monkeypatch):
    body = {
        "candidates": [
            {
                "content": {"parts": [{"text": "Hello"}]},
                "groundingMetadata": {
                    "groundingChunks": [{"web": {"uri": "https://example.com/a", "title": "A"}}]
                },
            }
        ]
    }

    class Response(FakeResponse):
        def json(self):
            return body

    monkeypatch.setattr(gemini, "_post", lambda url, headers, payload: Response("x"))
    result = gemini.generate("system", [{"role": "user", "parts": [{"text": "hi"}]}])
    assert result == {
        "reply": "Hello",
        "sources": [{"title": "A", "url": "https://example.com/a"}],
        "citations": [],
    }


def test_gemini_citations_use_googles_own_source_numbers(monkeypatch):
    # The first two chunks are the same page, so sources lists three, but the numbering
    # Google used for the citations still counts every chunk
    body = {
        "candidates": [
            {
                "content": {"parts": [{"text": "Hello"}]},
                "groundingMetadata": {
                    "groundingChunks": [
                        {"web": {"uri": "https://example.com/a", "title": "a.com"}},
                        {"web": {"uri": "https://example.com/a", "title": "a.com"}},
                        {"web": {"uri": "https://example.com/b", "title": "b.com"}},
                    ],
                    "groundingSupports": [
                        {"segment": {"text": "Profit beat forecasts."}, "groundingChunkIndices": [2]},
                        {"segment": {"text": ""}, "groundingChunkIndices": [0]},
                        {"segment": {"text": "Bad index."}, "groundingChunkIndices": [9]},
                    ],
                },
            }
        ]
    }

    class Response(FakeResponse):
        def json(self):
            return body

    monkeypatch.setattr(gemini, "_post", lambda url, headers, payload: Response("x"))
    result = gemini.generate("system", [{"role": "user", "parts": [{"text": "hi"}]}])
    assert result["citations"] == [{"text": "Profit beat forecasts.", "urls": ["https://example.com/b"]}]


# ---------------- The route ----------------


def test_route_returns_summary_drivers_and_sources(client, monkeypatch):
    drivers = [driver("A", "First.", 1), driver("B", "Second.", 2)]
    setup(monkeypatch, articles=FOUR, ai=FakeAI(reply(drivers=drivers, sources=[1, 2])))
    res = client.get("/api/stocks/AAPL/why-moved")

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert len(body["drivers"]) == 2
    assert len(body["sources"]) == 2


def test_route_returns_not_enough_information(client, monkeypatch):
    setup(monkeypatch, articles=[])
    body = client.get("/api/stocks/AAPL/why-moved").json()
    assert body["message"] == "Not enough information to explain this move"
    assert body["drivers"] == []
    assert body["sources"] == []


def test_route_error_message(client, monkeypatch):
    setup(monkeypatch, articles=[article("News")])

    def broken(system, contents, *, grounded=True, json_output=False):
        raise gemini.GeminiRateLimitedError("busy")

    monkeypatch.setattr(gemini, "generate", broken)
    res = client.get("/api/stocks/AAPL/why-moved")
    assert res.status_code == 502
    assert res.json()["detail"] == "The explanation is unavailable right now"


def test_route_rejects_bad_symbols(client):
    assert client.get("/api/stocks/<script>/why-moved").status_code in (400, 404)


def test_route_requires_login(logged_out_client):
    assert logged_out_client.get("/api/stocks/AAPL/why-moved").status_code == 401
