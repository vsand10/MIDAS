# Stock detail feature (STOCK-01): quote, key stats, and price history for one stock.
# Self-contained on purpose: main.py only needs to mount `router`.
from app.stock_detail.router import router

__all__ = ["router"]