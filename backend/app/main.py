# Main FastAPI file for starting the MIDAS backend and connecting API routes

from dotenv import load_dotenv
from fastapi import FastAPI, Depends
from app.deps import init_firebase, get_current_user

load_dotenv()
init_firebase()

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