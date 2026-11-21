from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.connectors.registry import BLOCKS
from app.connectors.uldk import ParcelNotFound, resolve_by_id, resolve_by_xy
from app.contracts.models import AnalysisContext, BlockInfo, DataBlock, ParcelProfile, ParcelRef
from app.services.profile import build_profile, run_block

router = APIRouter(prefix="/api/parcel", tags=["parcel"])


def _validate_date(as_of: date | None) -> date:
    today = date.today()
    d = as_of or today
    if d > today:
        raise HTTPException(422, "Data analizy nie może być z przyszłości.")
    if d.year < today.year - settings.history_years:
        raise HTTPException(422, f"Data analizy musi mieścić się w ostatnich {settings.history_years} latach.")
    return d


async def _resolve(id: str | None, lon: float | None, lat: float | None) -> ParcelRef:
    try:
        if id:
            return await resolve_by_id(id)
        if lon is not None and lat is not None:
            return await resolve_by_xy(lon, lat)
    except ParcelNotFound as e:
        raise HTTPException(404, f"Nie znaleziono działki: {e}") from e
    raise HTTPException(422, "Podaj identyfikator działki (id) albo współrzędne (lon, lat).")


@router.get("/resolve", response_model=ParcelRef)
async def resolve(id: str | None = None, lon: float | None = None, lat: float | None = None) -> ParcelRef:
    """Identyfikator działki (np. 146505_8.0116.5) lub „obręb numer”, albo punkt z mapy."""
    return await _resolve(id, lon, lat)


@router.get("/blocks", response_model=list[BlockInfo])
async def list_blocks() -> list[BlockInfo]:
    return [BlockInfo(key=c.key, title=c.title, category=c.category, implemented=c.implemented)
            for c in BLOCKS.values()]


@router.get("/profile", response_model=ParcelProfile)
async def profile(id: str | None = None, lon: float | None = None, lat: float | None = None,
                  date_: date | None = Query(None, alias="date"), crop: str | None = None,
                  blocks: str | None = Query(None, description="lista kluczy po przecinku"),
                  no_cache: bool = False) -> ParcelProfile:
    ctx = AnalysisContext(parcel=await _resolve(id, lon, lat), as_of=_validate_date(date_), crop=crop)
    keys = [k for k in blocks.split(",") if k in BLOCKS] if blocks else None
    return await build_profile(ctx, keys, use_cache=not no_cache)


@router.get("/block/{key}", response_model=DataBlock[Any])
async def block(key: str, id: str | None = None, lon: float | None = None, lat: float | None = None,
                date_: date | None = Query(None, alias="date"), crop: str | None = None,
                no_cache: bool = False) -> DataBlock[Any]:
    """Pojedynczy blok – frontend odpytuje wszystkie równolegle i renderuje progresywnie."""
    if key not in BLOCKS:
        raise HTTPException(404, f"Nieznany blok: {key}")
    ctx = AnalysisContext(parcel=await _resolve(id, lon, lat), as_of=_validate_date(date_), crop=crop)
    return await run_block(key, ctx, use_cache=not no_cache)
