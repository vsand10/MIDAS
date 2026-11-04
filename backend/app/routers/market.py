# API routes for the Home screen: market overview, index chart and top movers (HOME-01)

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import get_current_user
from app.services import market_service
from app.services.alphavantage import DataUnavailableError

# Every route in this file requires a logged-in user
router = APIRouter(
    prefix="/api/market",
    tags=["market"],
    dependencies=[Depends(get_current_user)],
)

UNAVAILABLE = "Market data is unavailable right now"


@router.get("/overview")
def market_overview():
    """S&P 500, Nasdaq and Dow: value, change and percent change."""
    try:
        return {"indices": market_service.get_market_overview()}
    except DataUnavailableError as err:
        raise HTTPException(status_code=502, detail=UNAVAILABLE) from err


@router.get("/history")
def index_history(
    symbol: str,
    range_: Annotated[str, Query(alias="range")] = "1D",
):
    """Chart points for one index. range is 1D, 1W, 1M, 3M or 1Y."""
    if symbol not in market_service.INDEX_NAMES:
        raise HTTPException(status_code=400, detail="Unknown index")
    if range_ not in market_service.RANGE_SETTINGS:
        raise HTTPException(status_code=400, detail="Unknown range")
    try:
        return market_service.get_index_history(symbol, range_)
    except DataUnavailableError as err:
        raise HTTPException(status_code=502, detail=UNAVAILABLE) from err


@router.get("/movers")
def top_movers(limit: Annotated[int, Query(ge=1, le=10)] = 5):
    """Top gainers and losers today, as {"gainers": [...], "losers": [...]}."""
    try:
        return market_service.get_top_movers(limit)
    except DataUnavailableError as err:
        raise HTTPException(status_code=502, detail=UNAVAILABLE) from err
