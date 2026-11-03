# Tests for the Home API routes: responses, errors and login protection

from app.services import market_service
from app.services.alphavantage import DataUnavailableError

from .test_market import INTRADAY, fake_indices, fake_movers, gl


def alpha_vantage_works(monkeypatch):
    fake_indices(monkeypatch)
    monkeypatch.setattr(market_service, "_fetch_etf_intraday", lambda etf, interval: INTRADAY)


def alpha_vantage_down(monkeypatch):
    def broken(*args, **kwargs):
        raise DataUnavailableError("down")

    for name in (
        "_fetch_index_daily",
        "_fetch_etf_daily",
        "_fetch_etf_intraday",
        "_fetch_quotes",
        "_fetch_gainers_losers",
    ):
        monkeypatch.setattr(market_service, name, broken)


def test_overview_route(client, monkeypatch):
    alpha_vantage_works(monkeypatch)
    res = client.get("/api/market/overview")
    assert res.status_code == 200
    indices = res.json()["indices"]
    assert [i["name"] for i in indices] == ["S&P 500", "Nasdaq", "Dow"]
    assert indices[0]["value"] == 1010.0
    assert indices[0]["changePercent"] == 1.0


def test_overview_route_error_message(client, monkeypatch):
    alpha_vantage_down(monkeypatch)
    res = client.get("/api/market/overview")
    assert res.status_code == 502
    assert res.json()["detail"] == "Market data is unavailable right now"


def test_history_route(client, monkeypatch):
    alpha_vantage_works(monkeypatch)
    res = client.get("/api/market/history", params={"symbol": "^GSPC", "range": "1D"})
    assert res.status_code == 200
    assert [p["price"] for p in res.json()] == [1005.0, 1010.0]


def test_history_route_error_message(client, monkeypatch):
    alpha_vantage_down(monkeypatch)
    res = client.get("/api/market/history", params={"symbol": "^GSPC", "range": "1M"})
    assert res.status_code == 502


def test_history_route_rejects_unknown_index_and_range(client):
    assert client.get("/api/market/history", params={"symbol": "AAPL"}).status_code == 400
    bad_range = {"symbol": "^GSPC", "range": "5Y"}
    assert client.get("/api/market/history", params=bad_range).status_code == 400


def test_movers_route(client, monkeypatch):
    fake_movers(
        monkeypatch,
        gainers=[gl("AAA", 10, 4.0)],
        losers=[gl("CCC", 30, -4.0)],
    )
    res = client.get("/api/market/movers", params={"limit": 1})
    assert res.status_code == 200
    body = res.json()
    assert body["gainers"][0]["changePercent"] == 4.0
    assert body["losers"][0]["changePercent"] == -4.0


def test_movers_route_error_message(client, monkeypatch):
    alpha_vantage_down(monkeypatch)
    res = client.get("/api/market/movers")
    assert res.status_code == 502
    assert res.json()["detail"] == "Market data is unavailable right now"


def test_movers_limit_is_validated(client):
    assert client.get("/api/market/movers", params={"limit": 0}).status_code == 422
    assert client.get("/api/market/movers", params={"limit": 99}).status_code == 422


def test_all_market_routes_require_login(logged_out_client):
    for path in ("/api/market/overview", "/api/market/movers", "/api/market/history?symbol=^GSPC"):
        assert logged_out_client.get(path).status_code == 401

