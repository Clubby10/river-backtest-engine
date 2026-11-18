"""Expose the backtest engine through FastAPI endpoints."""

from fastapi import FastAPI

app = FastAPI(title="River Backtest API")

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}