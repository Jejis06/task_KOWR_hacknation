"""FastAPI – punkt wejścia. Uruchom: `cd backend && uv run uvicorn app.main:app --reload`."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from datetime import date, timedelta

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, knowledge, parcel, tiles
from app.config import settings
from app.core.http import close_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await close_client()


app = FastAPI(title="Zatrzymaj wodę – API danych o działce", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET"],
                   allow_headers=["*"])


@app.middleware("http")
async def cache_headers(request: Request, call_next):
    """Cache w przeglądarce dla odpowiedzi GET API: powtórne otwarcie tej samej działki/daty nie pyta serwera.
    Dane historyczne (data analizy > 7 dni temu) są niezmienne → 7 dni; bieżące → 1 h; działki i wiedza → 1 dzień."""
    response = await call_next(request)
    path = request.url.path
    if request.method != "GET" or response.status_code != 200 or "cache-control" in response.headers:
        return response
    if path.startswith("/api/parcel/block/"):
        d = request.query_params.get("date")
        try:
            old = d is not None and date.fromisoformat(d) < date.today() - timedelta(days=7)
        except ValueError:
            old = False
        response.headers["Cache-Control"] = f"public, max-age={7 * 24 * 3600 if old else 3600}"
    elif path.startswith(("/api/parcel/resolve", "/api/knowledge", "/api/parcel/blocks")):
        response.headers["Cache-Control"] = "public, max-age=86400"
    return response


app.include_router(health.router)
app.include_router(parcel.router)
app.include_router(knowledge.router)
app.include_router(tiles.router)
