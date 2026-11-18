# API route for the "Why it moved" summary on Stock Detail (WHY-01)

import re

from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_current_user
from app.services import why_service
from app.services.alphavantage import DataUnavailableError

# Every route in this file requires a logged-in user
router = APIRouter(
    prefix="/api/stocks",
    tags=["why-it-moved"],
    dependencies=[Depends(get_current_user)],
)

SYMBOL_PATTERN = re.compile(r"[A-Z0-9.\-^=]{1,15}")


@router.get("/{symbol}/why-moved")
def why_it_moved(symbol: str):
    """A short AI summary of why the stock moved today, or a "not enough information" answer."""
    clean = symbol.strip().upper()
    if not SYMBOL_PATTERN.fullmatch(clean):
        raise HTTPException(status_code=400, detail="Invalid stock symbol")
    try:
        return why_service.get_why_it_moved(clean)
    except DataUnavailableError as err:
        raise HTTPException(
            status_code=502, detail="The explanation is unavailable right now"
        ) from err
