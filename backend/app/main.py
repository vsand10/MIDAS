# Main FastAPI file for starting the MIDAS backend and connecting API routes

from fastapi import FastAPI

# Create the main FastAPI application for MIDAS
app = FastAPI(title="MIDAS API")

# Default route that shows a message when MIDAS API is opened
@app.get("/")
def home():
    return {"message": "MIDAS API is running"}

# Health check route to test if backend can respond
@app.get("/health")
def health():
    return {"status": "ok"}