# Stock detail API routes.
#   GET /api/stocks/{symbol}                 price, change, key stats, about
#   GET /api/stocks/{symbol}/history?range=  chart points for 1D / 1W / 1M / 3M / 1Y
# The response shapes below match the typedefs in frontend/src/services/stockservice.js
import re
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.deps import get_current_user
from app.stock_detail.client import AlphaVantageError, SymbolNotFound
from app.stock_detail.service import StockDetailService

# Login required: every call can spend Alpha Vantage requests on the shared key
router = APIRouter(
    prefix="/api/stocks",
    tags=["stock-detail"],
    dependencies=[Depends(get_current_user)],
)

_service = StockDetailService()

# Tickers like AAPL, BRK.B, RDS-A. Anything else cannot be a stock, so skip the upstream call.
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,9}$")

Range = Literal["1D", "1W", "1M", "3M", "1Y"]


# ---------------- Response shapes ----------------


class KeyStats(BaseModel):
    marketCap: float | None = None  # dollars
    peRatio: float | None = None
    week52Low: float | None = None
    week52High: float | None = None
    avgVolume: float | None = None  # shares per day (30 trading day average)
    eps: float | None = None  # dollars
    dividendYield: float | None = None  # percent, None if no dividend


class StockDetail(BaseModel):
    symbol: str
    name: str
    sector: str
    price: float
    change: float  # dollars, vs previous close
    changePercent: float  # percent, vs previous close
    stats: KeyStats
    about: str


class PricePoint(BaseModel):
    time: str  # ISO date string (UTC)
    price: float


# ---------------- Routes ----------------


def get_service() -> StockDetailService:
    return _service


def clean_symbol(symbol: str) -> str:
    cleaned = symbol.strip().upper()
    if not SYMBOL_PATTERN.match(cleaned):
        raise SymbolNotFound()
    return cleaned


@router.get("/{symbol}", response_model=StockDetail)
async def get_stock_detail(
    symbol: str,
    service: Annotated[StockDetailService, Depends(get_service)],
):
    try:
        return await service.detail(clean_symbol(symbol))
    except AlphaVantageError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from None


@router.get("/{symbol}/history", response_model=list[PricePoint])
async def get_stock_history(
    symbol: str,
    service: Annotated[StockDetailService, Depends(get_service)],
    range_: Annotated[Range, Query(alias="range")] = "1D",
):
    try:
        return await service.history(clean_symbol(symbol), range_)
    except AlphaVantageError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from None
