"""FastAPI – punkt wejścia. Uruchom: `cd backend && uv run uvicorn app.main:app --reload`."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, knowledge, parcel
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
app.include_router(health.router)
app.include_router(parcel.router)
app.include_router(knowledge.router)
