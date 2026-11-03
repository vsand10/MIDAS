# Shared test setup: a small app with the new routes and no real login or Alpha Vantage calls

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.deps import get_current_user
from app.routers import market, news
from app.services import alphavantage, market_service, news_service


@pytest.fixture(autouse=True)
def clear_caches():
    """Each test starts with empty caches so results never leak between tests."""
    market_service._cache.clear()
    news_service._cache.clear()
    alphavantage._listing_cache.clear()


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    """Safety net: a test that forgets to fake Alpha Vantage fails instead of calling it."""

    def refuse(params):
        raise AssertionError("A test tried to call Alpha Vantage for real")

    monkeypatch.setattr(alphavantage, "_send", refuse)
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "test-key")
    monkeypatch.delenv("ALPHA_VANTAGE_ENTITLEMENT", raising=False)


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(market.router)
    app.include_router(news.router)
    return app


@pytest.fixture
def client(app):
    """A logged-in test client (the login check is replaced with a fake user)."""
    app.dependency_overrides[get_current_user] = lambda: {"uid": "test-user"}
    return TestClient(app)


@pytest.fixture
def logged_out_client(app):
    return TestClient(app)
