# Tests for the shared Alpha Vantage helpers (no internet needed)

import json

import pytest

from app.services import alphavantage as av


def reply(monkeypatch, text, status=200):
    seen = {}

    def send(params):
        seen.update(params)
        return status, text

    monkeypatch.setattr(av, "_send", send)
    return seen


def test_av_get_sends_function_and_key_and_returns_json(monkeypatch):
    seen = reply(monkeypatch, '{"data": [1]}')
    assert av.av_get("INDEX_DATA", symbol="SPX") == {"data": [1]}
    assert seen == {
        "symbol": "SPX",
        "function": "INDEX_DATA",
        "apikey": "test-key",
    }


@pytest.mark.parametrize("key", ["Information", "Note", "Error Message"])
def test_alpha_vantage_problem_messages_become_errors(monkeypatch, key):
    reply(monkeypatch, json.dumps({key: "You have hit the limit"}))
    with pytest.raises(av.DataUnavailableError, match="limit"):
        av.av_get("NEWS_SENTIMENT")


def test_the_success_message_of_bulk_quotes_is_not_an_error(monkeypatch):
    reply(monkeypatch, '{"message": "success", "data": []}')
    assert av.av_get("REALTIME_BULK_QUOTES")["message"] == "success"


@pytest.mark.parametrize("text", ["{}", "not json", "[1, 2]"])
def test_empty_or_broken_answers_become_errors(monkeypatch, text):
    reply(monkeypatch, text)
    with pytest.raises(av.DataUnavailableError):
        av.av_get("TOP_GAINERS_LOSERS")


def test_bad_http_status_becomes_error(monkeypatch):
    reply(monkeypatch, "{}", status=500)
    with pytest.raises(av.DataUnavailableError, match="500"):
        av.av_get("TOP_GAINERS_LOSERS")


def test_missing_key_becomes_error(monkeypatch):
    monkeypatch.delenv("ALPHA_VANTAGE_API_KEY")
    with pytest.raises(av.DataUnavailableError, match="ALPHA_VANTAGE_API_KEY"):
        av.av_get("TOP_GAINERS_LOSERS")


def test_network_errors_never_expose_the_key(monkeypatch):
    import httpx

    def broken_get(url, params, timeout):
        raise httpx.ConnectError(f"failed for {url}?apikey={params['apikey']}")

    monkeypatch.undo()  # use the real _send for this test
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "secret-key-123")
    monkeypatch.setattr(httpx, "get", broken_get)
    with pytest.raises(av.DataUnavailableError) as err:
        av.av_get("TOP_GAINERS_LOSERS")
    assert "secret-key-123" not in str(err.value)
    assert err.value.__cause__ is None
    assert err.value.__suppress_context__


LISTING_CSV = (
    "symbol,name,exchange,assetType,ipoDate,delistingDate,status\n"
    "AAPL,Apple Inc,NASDAQ,Stock,1980-12-12,null,Active\n"
    "SPY,SPDR S&P 500 ETF Trust,NYSE ARCA,ETF,1993-01-22,null,Active\n"
    "HSCSW,HeartSciences Warrant,NASDAQ,Stock,2022-06-01,null,Active\n"
)


def test_csv_is_parsed(monkeypatch):
    reply(monkeypatch, LISTING_CSV)
    rows = av.av_get_csv("LISTING_STATUS", state="active")
    assert rows[0]["symbol"] == "AAPL"
    assert len(rows) == 3


def test_csv_function_reports_json_error_messages(monkeypatch):
    reply(monkeypatch, '{"Information": "premium endpoint"}')
    with pytest.raises(av.DataUnavailableError, match="premium"):
        av.av_get_csv("LISTING_STATUS")


def test_company_names_keeps_only_real_stocks_and_is_cached(monkeypatch):
    calls = []

    def send(params):
        calls.append(params)
        return 200, LISTING_CSV

    monkeypatch.setattr(av, "_send", send)
    assert av.company_names() == {"AAPL": "Apple Inc"}  # no ETF, no warrant
    av.company_names()
    assert len(calls) == 1


def test_company_names_or_empty_hides_outages(monkeypatch):
    reply(monkeypatch, "{}", status=503)
    assert av.company_names_or_empty() == {}


@pytest.mark.parametrize(
    ("value", "expected"),
    [("752.15", 752.15), ("-0.4724", -0.4724), ("188.5714%", 188.5714), ("None", None), (None, None)],
)
def test_to_float(value, expected):
    assert av.to_float(value) == expected


def test_entitlement_is_off_unless_configured(monkeypatch):
    assert av.entitlement() == {}
    monkeypatch.setenv("ALPHA_VANTAGE_ENTITLEMENT", " Realtime ")
    assert av.entitlement() == {"entitlement": "realtime"}
