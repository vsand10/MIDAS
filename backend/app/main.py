from fastapi import FastAPI

app = FastAPI(title="MIDAS API")


@app.get("/")
def home():
    return {"message": "MIDAS API is running"}


@app.get("/health")
def health():
    return {"status": "ok"}