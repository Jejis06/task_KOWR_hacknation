from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.knowledge import loader

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("")
async def collections() -> dict[str, Any]:
    return {name: loader.meta(name) for name in loader.COLLECTIONS}


@router.get("/{collection}")
async def list_items(collection: str) -> dict[str, Any]:
    try:
        return loader.load(collection)
    except KeyError as e:
        raise HTTPException(404, f"Nieznana kolekcja: {collection}") from e


@router.get("/{collection}/{item_id}")
async def get_item(collection: str, item_id: str) -> dict[str, Any]:
    if collection not in loader.COLLECTIONS:
        raise HTTPException(404, f"Nieznana kolekcja: {collection}")
    item = loader.get_item(collection, item_id)
    if item is None:
        raise HTTPException(404, f"Brak wpisu {item_id} w {collection}")
    return item
