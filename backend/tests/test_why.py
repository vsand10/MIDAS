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

    def __init__(self, answer=None):
        self.answer = answer if answer is not None else reply()
        self.calls = []

    def __call__(self, system, contents, *, grounded=True, json_output=False):
        prompt = contents[0]["parts"][0]["text"]
        self.calls.append(
            {"system": system, "prompt": prompt, "json_output": json_output, "grounded": grounded}
        )
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


def test_no_news_means_not_enough_information_and_no_ai_call(monkeypatch):
    ai = setup(monkeypatch, articles=[])
    result = why_service.get_why_it_moved("AAPL")

    assert result["status"] == "insufficient"
    assert result["message"] == "Not enough information to explain this move"
    assert result["summary"] is None
    assert ai.calls == []


def test_only_old_news_counts_as_no_news(monkeypatch):
    ai = setup(monkeypatch, articles=[article("Ancient story", hours_ago=200)])
    assert why_service.get_why_it_moved("AAPL")["status"] == "insufficient"
    assert ai.calls == []


def test_ai_saying_insufficient_shows_the_same_message(monkeypatch):
    setup(monkeypatch, articles=[article("Unrelated")], ai=FakeAI('{"insufficient": true}'))
    result = why_service.get_why_it_moved("AAPL")
    assert result["status"] == "insufficient"
    assert result["message"] == "Not enough information to explain this move"


def test_empty_summary_is_not_shown(monkeypatch):
    setup(monkeypatch, articles=[article("News")], ai=FakeAI(reply(summary="   ")))
    assert why_service.get_why_it_moved("AAPL")["status"] == "insufficient"


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
    assert result == {"reply": "Hello", "sources": [{"title": "A", "url": "https://example.com/a"}]}


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
