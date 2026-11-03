# Tests for HOME-01: market overview, index chart and top movers
# (no internet needed, Alpha Vantage is replaced with fake data shaped like the real answers)

import pytest

from app.services import market_service
from app.services.alphavantage import DataUnavailableError

# Index closes are exactly 10x the ETF closes on 2026-10-30, so every ratio is 10
INDEX_ROWS = {
    "SPX": [{"date": "2026-10-30", "close": "1000.00"}, {"date": "2026-10-29", "close": "990.00"}],
    "COMP": [{"date": "2026-10-30", "close": "2000.00"}, {"date": "2026-10-29", "close": "2010.00"}],
    "DJI": [{"date": "2026-10-30", "close": "3000.00"}, {"date": "2026-10-29", "close": "2990.00"}],
}
ETF_DAILY = {
    "SPY": {"2026-11-02": {"4. close": "101.00"}, "2026-10-30": {"4. close": "100.00"}},
    "ONEQ": {"2026-11-02": {"4. close": "198.00"}, "2026-10-30": {"4. close": "200.00"}},
    "DIA": {"2026-11-02": {"4. close": "300.00"}, "2026-10-30": {"4. close": "300.00"}},
}


def quote(symbol, close, previous):
    """A record shaped like a real REALTIME_BULK_QUOTES row (trimmed)."""
    change = close - previous
    return {
        "symbol": symbol,
        "close": str(close),
        "previous_close": str(previous),
        "change": f"{change:.2f}",
        "change_percent": f"{change / previous * 100:.4f}",
    }


ETF_QUOTES = [quote("SPY", 101.0, 100.0), quote("ONEQ", 198.0, 200.0), quote("DIA", 300.0, 300.0)]

# Real intraday shape: the key is "Time Series (<interval>)", times are New York time
INTRADAY = {
    "2026-10-30 15:55:00": {"4. close": "99.00"},
    "2026-11-02 09:30:00": {"4. close": "100.50"},
    "2026-11-02 09:35:00": {"4. close": "101.00"},
}


def fake_indices(monkeypatch, index_rows=None, etf_daily=None, quotes=None):
    index_rows = INDEX_ROWS if index_rows is None else index_rows
    etf_daily = ETF_DAILY if etf_daily is None else etf_daily
    quotes = ETF_QUOTES if quotes is None else quotes

    def index_daily(symbol):
        if symbol not in index_rows:
            raise DataUnavailableError("down")
        return index_rows[symbol]

    def etf(symbol):
        if symbol not in etf_daily:
            raise DataUnavailableError("down")
        return etf_daily[symbol]

    monkeypatch.setattr(market_service, "_fetch_index_daily", index_daily)
    monkeypatch.setattr(market_service, "_fetch_etf_daily", etf)
    monkeypatch.setattr(market_service, "_fetch_quotes", lambda symbols: quotes)


# ---------- Market overview (AC 1) ----------


def test_overview_has_value_and_percent_for_all_three(monkeypatch):
    fake_indices(monkeypatch)
    rows = market_service.get_market_overview()
    assert [r["name"] for r in rows] == ["S&P 500", "Nasdaq", "Dow"]
    assert [r["symbol"] for r in rows] == ["^GSPC", "^IXIC", "^DJI"]
    sp, nasdaq, dow = rows
    assert (sp["value"], sp["change"], sp["changePercent"]) == (1010.0, 10.0, 1.0)
    assert (nasdaq["value"], nasdaq["change"], nasdaq["changePercent"]) == (1980.0, -20.0, -1.0)
    assert (dow["value"], dow["change"], dow["changePercent"]) == (3000.0, 0.0, 0.0)


def test_ratio_uses_latest_day_both_sources_have(monkeypatch):
    # INDEX_DATA already has 2026-11-02, so that day is used (ratio 10.1 -> 10.0 here)
    rows = {**INDEX_ROWS, "SPX": [{"date": "2026-11-02", "close": "1010.00"}, *INDEX_ROWS["SPX"]]}
    fake_indices(monkeypatch, index_rows=rows)
    assert market_service.get_market_overview()[0]["value"] == 1010.0


def test_overview_fails_if_any_index_fails(monkeypatch):
    fake_indices(monkeypatch, index_rows={k: v for k, v in INDEX_ROWS.items() if k != "DJI"})
    with pytest.raises(DataUnavailableError):
        market_service.get_market_overview()


def test_overview_fails_if_quote_is_incomplete(monkeypatch):
    broken = [quote("SPY", 101.0, 100.0), quote("ONEQ", 198.0, 200.0), {"symbol": "DIA", "close": "None"}]
    fake_indices(monkeypatch, quotes=broken)
    with pytest.raises(DataUnavailableError):
        market_service.get_market_overview()


def test_overview_fails_without_quotes(monkeypatch):
    fake_indices(monkeypatch, quotes=[])
    with pytest.raises(DataUnavailableError):
        market_service.get_market_overview()


def test_overview_fails_when_no_day_overlaps(monkeypatch):
    fake_indices(monkeypatch, etf_daily={**ETF_DAILY, "SPY": {"2026-01-05": {"4. close": "100"}}})
    with pytest.raises(DataUnavailableError):
        market_service.get_market_overview()


# ---------- Index chart ----------


def test_one_day_chart_keeps_only_latest_trading_day_scaled_to_the_index(monkeypatch):
    fake_indices(monkeypatch)
    monkeypatch.setattr(market_service, "_fetch_etf_intraday", lambda etf, interval: INTRADAY)
    points = market_service.get_index_history("^GSPC", "1D")
    assert [p["price"] for p in points] == [1005.0, 1010.0]
    assert points[0]["time"] == "2026-11-02T09:30:00-05:00"


def test_one_week_chart_keeps_five_trading_days(monkeypatch):
    fake_indices(monkeypatch)
    series = {f"2026-10-{day:02d} 10:00:00": {"4. close": "100"} for day in range(19, 31)}
    monkeypatch.setattr(market_service, "_fetch_etf_intraday", lambda etf, interval: series)
    points = market_service.get_index_history("^GSPC", "1W")
    assert len({p["time"][:10] for p in points}) == 5
    assert points[-1]["time"].startswith("2026-10-30")


def test_intraday_asks_for_the_right_interval(monkeypatch):
    fake_indices(monkeypatch)
    seen = []

    def intraday(etf, interval):
        seen.append((etf, interval))
        return INTRADAY

    monkeypatch.setattr(market_service, "_fetch_etf_intraday", intraday)
    market_service.get_index_history("^IXIC", "1D")
    market_service.get_index_history("^DJI", "1W")
    assert seen == [("ONEQ", "5min"), ("DIA", "30min")]


def test_longer_ranges_come_from_official_daily_closes(monkeypatch):
    rows = [{"date": f"2026-{m:02d}-15", "close": str(1000 + m)} for m in range(1, 11)]
    fake_indices(monkeypatch, index_rows={**INDEX_ROWS, "SPX": rows[::-1]})  # newest first
    one_month = market_service.get_index_history("^GSPC", "1M")
    assert [p["price"] for p in one_month] == [1009.0, 1010.0]  # 15 Sep is exactly 30 days back
    three_months = market_service.get_index_history("^GSPC", "3M")
    assert [p["price"] for p in three_months] == [1008.0, 1009.0, 1010.0]  # oldest first
    assert three_months[0]["time"] == "2026-08-15T16:00:00-04:00"
    assert len(market_service.get_index_history("^GSPC", "1Y")) == 10


def test_chart_fails_without_data(monkeypatch):
    fake_indices(monkeypatch)
    monkeypatch.setattr(market_service, "_fetch_etf_intraday", lambda etf, interval: {})
    with pytest.raises(DataUnavailableError):
        market_service.get_index_history("^GSPC", "1D")


def test_chart_rejects_unknown_index_or_range():
    with pytest.raises(ValueError, match="index"):
        market_service.get_index_history("AAPL", "1D")
    with pytest.raises(ValueError, match="range"):
        market_service.get_index_history("^GSPC", "5Y")


# ---------- Top movers (AC 2) ----------


def gl(ticker, price, percent, volume=2_000_000):
    """An item shaped like a real TOP_GAINERS_LOSERS row."""
    return {
        "ticker": ticker,
        "price": str(price),
        "change_amount": f"{price * percent / 100:.2f}",
        "change_percentage": f"{percent}%",
        "volume": str(volume),
    }


NAMES = {"AAA": "Alpha Inc", "BBB": "Beta Corp", "CCC": "Gamma Co", "DDD": "Delta Ltd"}


def fake_movers(monkeypatch, gainers=(), losers=(), names=NAMES, basket=None):
    """basket: quote rows for the large-stock top-up, or None to make that call fail."""
    if isinstance(gainers, Exception):
        def screen():
            raise gainers
    else:
        def screen():
            return {"top_gainers": list(gainers), "top_losers": list(losers)}

    def quotes(symbols):
        if basket is None:
            raise DataUnavailableError("down")
        return basket

    monkeypatch.setattr(market_service, "_fetch_gainers_losers", screen)
    monkeypatch.setattr(market_service, "_fetch_quotes", quotes)
    monkeypatch.setattr(market_service, "company_names_or_empty", lambda: names)


def test_movers_from_alpha_vantage_lists(monkeypatch):
    fake_movers(
        monkeypatch,
        gainers=[gl("AAA", 10, 5.0), gl("BBB", 20, 9.0)],
        losers=[gl("CCC", 30, -3.0), gl("DDD", 40, -6.0)],
    )
    movers = market_service.get_top_movers(2)
    assert [m["symbol"] for m in movers["gainers"]] == ["BBB", "AAA"]
    assert [m["symbol"] for m in movers["losers"]] == ["DDD", "CCC"]
    top = movers["gainers"][0]
    assert set(top) == {"symbol", "name", "price", "change", "changePercent"}
    assert top["name"] == "Beta Corp"
    assert top["price"] == 20.0
    assert top["changePercent"] == 9.0
    assert top["change"] == 1.8


def test_movers_respect_limit(monkeypatch):
    many = [gl(f"A{n}", 10, float(n)) for n in range(1, 9)]
    names = {f"A{n}": f"A{n} Inc" for n in range(1, 9)}
    fake_movers(monkeypatch, gainers=many, losers=[gl("A1", 10, -4.0)], names=names)
    assert len(market_service.get_top_movers(3)["gainers"]) == 3


def test_penny_stocks_and_thinly_traded_stocks_are_removed(monkeypatch):
    fake_movers(
        monkeypatch,
        gainers=[gl("AAA", 0.0101, 188.5), gl("BBB", 4.39, 106.1), gl("CCC", 8.16, 168.4, volume=239), gl("DDD", 50, 7.0)],
        losers=[gl("AAA", 0.2101, -90.8)],
        names=NAMES,
        basket=None,
    )
    movers = market_service.get_top_movers(5)
    assert [m["symbol"] for m in movers["gainers"]] == ["DDD"]
    assert movers["losers"] == []


def test_symbols_not_in_the_stock_list_are_removed(monkeypatch):
    fake_movers(monkeypatch, gainers=[gl("AAA", 10, 5.0), gl("HSCSW", 10, 80.0)], losers=[gl("CCC", 30, -3.0)])
    assert [m["symbol"] for m in market_service.get_top_movers(5)["gainers"]] == ["AAA"]


def test_movers_still_work_when_the_company_list_is_down(monkeypatch):
    fake_movers(monkeypatch, gainers=[gl("ZZZ", 10, 5.0)], losers=[gl("YYY", 30, -3.0)], names={})
    movers = market_service.get_top_movers(5)
    assert movers["gainers"][0]["name"] == "ZZZ"  # symbol stands in for the missing name


def test_movers_skip_rows_with_missing_fields(monkeypatch):
    broken = {"ticker": "ZZZ", "price": "None"}
    fake_movers(monkeypatch, gainers=[broken, gl("AAA", 10, 5.0)], losers=[gl("CCC", 30, -3.0)], names={**NAMES, "ZZZ": "Z"})
    assert [m["symbol"] for m in market_service.get_top_movers(5)["gainers"]] == ["AAA"]


def basket(**percent_by_symbol):
    return [quote(s, 100 + p, 100.0) for s, p in percent_by_symbol.items()]


def test_short_sides_are_topped_up_from_large_stocks(monkeypatch):
    fake_movers(
        monkeypatch,
        gainers=[gl("AAA", 10, 5.0)],
        losers=[],
        basket=basket(AAPL=3, MSFT=-2, NVDA=0),
    )
    movers = market_service.get_top_movers(3)
    assert [m["symbol"] for m in movers["gainers"]] == ["AAA", "AAPL"]  # sorted by percent
    assert [m["symbol"] for m in movers["losers"]] == ["MSFT"]  # flat NVDA is in neither
    assert movers["losers"][0]["name"] == "Microsoft Corp."


def test_topping_up_never_duplicates_a_stock(monkeypatch):
    fake_movers(monkeypatch, gainers=[gl("AAPL", 100, 5.0)], losers=[], basket=basket(AAPL=3), names={"AAPL": "Apple Inc"})
    movers = market_service.get_top_movers(3)
    assert [m["symbol"] for m in movers["gainers"]] == ["AAPL"]
    assert movers["gainers"][0]["changePercent"] == 5.0


def test_losers_never_contain_gainers_when_filling(monkeypatch):
    fake_movers(monkeypatch, gainers=[gl("AAA", 10, 5.0)], losers=[], basket=basket(AAPL=10))
    assert market_service.get_top_movers(5)["losers"] == []


def test_list_failure_falls_back_to_large_stocks(monkeypatch):
    fake_movers(monkeypatch, gainers=DataUnavailableError("down"), basket=basket(AAPL=2, MSFT=-4))
    movers = market_service.get_top_movers(5)
    assert movers["gainers"][0]["symbol"] == "AAPL"
    assert movers["losers"][0]["symbol"] == "MSFT"


def test_movers_fail_when_everything_is_down(monkeypatch):
    fake_movers(monkeypatch, gainers=DataUnavailableError("down"), basket=None)
    with pytest.raises(DataUnavailableError):
        market_service.get_top_movers(5)


def test_one_good_side_survives_a_basket_failure(monkeypatch):
    fake_movers(monkeypatch, gainers=[gl("AAA", 10, 5.0)], losers=[], basket=None)
    movers = market_service.get_top_movers(5)
    assert [m["symbol"] for m in movers["gainers"]] == ["AAA"]
    assert movers["losers"] == []


# ---------- Real-time setting ----------


def test_realtime_setting_reaches_the_requests_that_need_it(monkeypatch):
    monkeypatch.setenv("ALPHA_VANTAGE_ENTITLEMENT", "realtime")
    calls = {}

    def spy(function, **params):
        calls[function] = params
        return {}

    monkeypatch.setattr(market_service, "av_get", spy)
    market_service._fetch_gainers_losers()
    market_service._fetch_etf_intraday("SPY", "5min")
    assert calls["TOP_GAINERS_LOSERS"] == {"entitlement": "realtime"}
    assert calls["TIME_SERIES_INTRADAY"]["entitlement"] == "realtime"


def test_no_entitlement_is_sent_when_not_configured(monkeypatch):
    calls = {}
    monkeypatch.setattr(market_service, "av_get", lambda function, **params: calls.update({function: params}) or {})
    market_service._fetch_gainers_losers()
    assert calls["TOP_GAINERS_LOSERS"] == {}
