# Main FastAPI file for starting the MIDAS backend and connecting API routes
import os

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from google.cloud import firestore
from pydantic import BaseModel

from app.deps import get_current_user, init_firebase

load_dotenv()
init_firebase()

# Firestore connection for watchlist data
db = firestore.Client(
    project=os.getenv("FIREBASE_PROJECT_ID")
)

# Create the main FastAPI application for MIDAS
app = FastAPI(title="MIDAS API")

# Default route that shows a message when MIDAS API is opened
@app.get("/")
def home():
    return {"message": "MIDAS API is running"}

# Health check route to test if backend can respond
@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok"}

# Protected route to confirm a Firebase token is accepted
@app.get("/api/me")
def me(user: dict = Depends(get_current_user)):
    return {"uid": user["uid"], "email": user.get("email")}


# Search for stocks using Alpha Vantage
@app.get("/api/stocks/search")
async def search_stocks(q: str, sector: str = "All"):

    # Remove extra spaces from the user's search text
    query = q.strip()

    # Return an empty list if the search is blank
    if not query:
        return []

    # Get the Alpha Vantage API key from the .env file
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")

    # Show an error if the API key is missing
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="Alpha Vantage API key is not configured",
        )

    # Parameters for Alpha Vantage Symbol Search
    search_params = {
        "function": "SYMBOL_SEARCH",
        "keywords": query,
        "apikey": api_key,
    }

    try:
        # Connect to Alpha Vantage
        async with httpx.AsyncClient(timeout=10.0) as client:

            # Search for stocks by ticker or company name
            response = await client.get(
                "https://www.alphavantage.co/query",
                params=search_params,
            )

            # Raise an error if Alpha Vantage does not respond successfully
            response.raise_for_status()

            # Convert the API response from JSON into Python data
            data = response.json()

            # Get matching stocks
            matches = data.get("bestMatches", [])

            # Store the final search results
            results = []

            # Check the first 8 search results
            for stock in matches[:8]:

                symbol = stock.get("1. symbol")
                name = stock.get("2. name")
                region = stock.get("4. region", "")

                # Skip results that are not U.S. listings
                if region != "United States":
                    continue
                # Skip a result if it does not have a stock symbol
                if not symbol:
                    continue

                stock_sector = ""

                # Only check company sector when the user selects
                # Tech, Energy, Finance, or Health
                if sector != "All":

                    # Parameters for Alpha Vantage Company Overview
                    overview_params = {
                        "function": "OVERVIEW",
                        "symbol": symbol,
                        "apikey": api_key,
                    }

                    # Get company information
                    overview_response = await client.get(
                        "https://www.alphavantage.co/query",
                        params=overview_params,
                    )

                    overview_response.raise_for_status()

                    # Convert company information from JSON
                    overview = overview_response.json()

                    # Get the company's sector
                    stock_sector = overview.get("Sector", "")

                    # Match Alpha Vantage sector names
                    # with the sector buttons used by MIDAS
                    sector_map = {
                        "Tech": [
                            "TECHNOLOGY",
                        ],
                        "Energy": [
                            "ENERGY",
                            "ENERGY & TRANSPORTATION",
                        ],
                        "Finance": [
                            "FINANCE",
                            "FINANCIAL SERVICES",
                        ],
                        "Health": [
                            "HEALTHCARE",
                            "HEALTH CARE",
                            "LIFE SCIENCES",
                        ],
                    }

                    # Get the Alpha Vantage sectors allowed
                    # for the selected MIDAS sector
                    allowed_sectors = sector_map.get(sector, [])

                    # Skip the stock if it does not match
                    # the selected sector
                    if stock_sector.upper() not in allowed_sectors:
                        continue

                # Convert the Alpha Vantage result
                # into the format used by MIDAS
                results.append(
                    {
                        "symbol": symbol,
                        "name": name,
                        "sector": stock_sector,
                        "price": None,
                        "change": None,
                        "changePercent": None,
                    }
                )

            # Return the matching stocks to the React frontend
            return results

    # Show an error if Alpha Vantage cannot be reached
    except httpx.HTTPError:
        raise HTTPException(
            status_code=502,
            detail="Could not connect to Alpha Vantage",
        )



# Get realtime quotes for multiple stocks using Alpha Vantage
@app.get("/api/stocks/quotes")
async def get_stock_quotes(symbols: str):
    # Get the Alpha Vantage API key from the .env file
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="Alpha Vantage API key is not configured",
        )

    # Remove extra spaces and empty symbols
    symbol_list = [
        symbol.strip().upper()
        for symbol in symbols.split(",")
        if symbol.strip()
    ]

    if not symbol_list:
        return []

    params = {
        "function": "REALTIME_BULK_QUOTES",
        "symbol": ",".join(symbol_list),
        "apikey": api_key,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://www.alphavantage.co/query",
                params=params,
            )

        response.raise_for_status()
        data = response.json()

        quotes = data.get("data", [])

        return [
            {
                "symbol": quote.get("symbol"),
                "price": float(quote.get("close", 0)),
                "change": float(quote.get("change", 0)),
                "changePercent": float(
                    quote.get("change_percent", 0)
                ),
            }
            for quote in quotes
        ]

    except httpx.HTTPError:
        raise HTTPException(
            status_code=502,
            detail="Could not get stock quotes from Alpha Vantage",
        )    

# ---------------- Watchlist ----------------
# Watchlist
@app.get("/api/watchlist")
def get_watchlist(user: dict = Depends(get_current_user)):
    uid = user["uid"]

    watchlist_ref = (
        db.collection("users")
        .document(uid)
        .collection("watchlist")
    )

    docs = watchlist_ref.stream()

    return [
    {
        "symbol": doc.id,
        "name": doc.to_dict().get("name", doc.id),
        "sector": doc.to_dict().get("sector", ""),
    }
    for doc in docs
]

class WatchlistRequest(BaseModel):
    symbol: str

# Add a stock to the current user's watchlist
@app.post("/api/watchlist")
def add_to_watchlist(
    request: WatchlistRequest,
    user: dict = Depends(get_current_user),
):
    uid = user["uid"]
    symbol = request.symbol.strip().upper()

    if not symbol:
        raise HTTPException(status_code=400, detail="Stock symbol is required")

    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")

    # Find the company name
    name = symbol

    try:
        response = httpx.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "SYMBOL_SEARCH",
                "keywords": symbol,
                "apikey": api_key,
            },
            timeout=10.0,
        )

        data = response.json()

        for match in data.get("bestMatches", []):
            if match.get("1. symbol", "").upper() == symbol:
                name = match.get("2. name", symbol)
                break

    except httpx.HTTPError:
        pass

    # Find the company's sector
    sector = ""

    try:
        response = httpx.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "OVERVIEW",
                "symbol": symbol,
                "apikey": api_key,
            },
            timeout=10.0,
        )

        overview = response.json()
        sector = overview.get("Sector", "")

    except httpx.HTTPError:
        pass

    user_ref = db.collection("users").document(uid)

    user_ref.set(
        {
            "email": user.get("email"),
        },
        merge=True,
    )

    watchlist_ref = user_ref.collection("watchlist").document(symbol)

    watchlist_ref.set(
        {
            "symbol": symbol,
            "name": name,
            "sector": sector,
            "addedAt": firestore.SERVER_TIMESTAMP,
        }
    )

    return {
        "symbol": symbol,
        "name": name,
        "sector": sector,
        "added": True,
    }


    # Use the stock symbol as the document ID.
    # This naturally prevents duplicate stocks.
    watchlist_ref = user_ref.collection("watchlist").document(symbol)

    watchlist_ref.set(
        {
            "symbol": symbol,
            "addedAt": firestore.SERVER_TIMESTAMP,
        }
    )

    return {
        "symbol": symbol,
        "added": True,
    }

# Remove a stock from the current user's watchlist
@app.delete("/api/watchlist/{symbol}")
def remove_from_watchlist(
    symbol: str,
    user: dict = Depends(get_current_user),
):
    uid = user["uid"]
    sym = symbol.strip().upper()

    watchlist_ref = (
        db.collection("users")
        .document(uid)
        .collection("watchlist")
        .document(sym)
    )

    watchlist_ref.delete()

    return {
        "symbol": sym,
        "removed": True,
    }
