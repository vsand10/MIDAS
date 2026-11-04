# API route for stock news (NEWS-01)

import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import get_current_user
from app.services import news_service
from app.services.alphavantage import DataUnavailableError

# Every route in this file requires a logged-in user
router = APIRouter(
    prefix="/api/stocks",
    tags=["news"],
    dependencies=[Depends(get_current_user)],
)

# Letters, digits and . - ^ = (for symbols like BRK-B), up to 15 characters
SYMBOL_PATTERN = re.compile(r"[A-Z0-9.\-^=]{1,15}")


@router.get("/{symbol}/news")
def stock_news(symbol: str, limit: Annotated[int, Query(ge=1, le=50)] = 10):
    """Recent articles for a stock, newest first. An empty list means no news."""
    clean = symbol.strip().upper()
    if not SYMBOL_PATTERN.fullmatch(clean):
        raise HTTPException(status_code=400, detail="Invalid stock symbol")
    try:
        return news_service.get_news(clean, limit)
    except DataUnavailableError as err:
        raise HTTPException(
            status_code=502, detail="News is unavailable right now"
        ) from err
