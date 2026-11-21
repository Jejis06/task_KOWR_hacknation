"""Lokalna baza wiedzy (data/knowledge/**.yaml) – ładowana raz do pamięci.

Treści, które nie zmieniają się z dnia na dzień (prawo, procedury, dofinansowania, kalendarz upraw),
trzymamy lokalnie zamiast pobierać na żywo. Każdy wpis ma `status` (OK | DO_WERYFIKACJI | SZACUNEK)
i `sources` – patrz data/knowledge/README.md.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.config import settings

COLLECTIONS = {
    "crops": "crops/crops.yaml",
    "legal_pl": "legal_pl/prawo_wodne.yaml",
    "eu_law": "eu_law/eu_law.yaml",
    "procedures": "procedures/procedures.yaml",
    "funding": "funding/programs.yaml",
    "measures": "procedures/retention_measures.yaml",
    "cover_crops": "crops/cover_crops.yaml",
}


@lru_cache
def load(collection: str) -> dict[str, Any]:
    if collection not in COLLECTIONS:
        raise KeyError(collection)
    path: Path = settings.knowledge_dir / COLLECTIONS[collection]
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def items(collection: str) -> list[dict[str, Any]]:
    return load(collection).get("items", [])


def get_item(collection: str, item_id: str) -> dict[str, Any] | None:
    return next((x for x in items(collection) if x.get("id") == item_id), None)


def meta(collection: str) -> dict[str, Any]:
    return load(collection).get("meta", {})


@lru_cache
def documents() -> dict[str, dict[str, Any]]:
    """Dokumenty źródłowe (tytuł + adres) z data/knowledge/sources.yaml, po id."""
    path: Path = settings.knowledge_dir / "sources.yaml"
    with path.open(encoding="utf-8") as f:
        docs = (yaml.safe_load(f) or {}).get("documents") or []
    return {d["id"]: d for d in docs if isinstance(d, dict) and d.get("id")}


def public_source(ref: str) -> str | None:
    """Odwołanie ze źródeł w YAML → adres publiczny. Ścieżki lokalnych kopii (`data/knowledge/raw/<id>.txt`) zamieniamy
    na adres oryginału z sources.yaml; odwołań do plików bez publicznego odpowiednika nie pokazujemy użytkownikowi."""
    ref = str(ref).strip()
    if ref.startswith(("http://", "https://")):
        return ref
    stem = Path(ref.split()[0]).stem
    doc = documents().get(stem)
    return doc.get("url") if doc and doc.get("url") else None
