"""Bazowa klasa konektora danych.

Konektor = jedno źródło / jeden blok danych o działce. Wzorzec:

    class MyConnector(Connector):
        key = "my_block"; title = "Mój blok"; category = "hydro"
        live_ttl_s = 6 * 3600
        async def fetch(self, ctx: AnalysisContext) -> DataBlock: ...

`run()` (NIE nadpisywać) zapewnia: cache, timeout, zamianę wyjątków na blok `error`, pomiar czasu.
`fetch()` NIGDY nie zwraca zmyślonych danych – przy braku danych zwraca status `no_data`
z wyjaśnieniem w `messages`/`uncertainty`.
"""
from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any, ClassVar, Literal

from app.config import settings
from app.contracts.models import AnalysisContext, BlockStatus, DataBlock, Provenance
from app.core.cache import cache_get, cache_set, make_key, ttl_for

log = logging.getLogger(__name__)

Category = Literal["meteo", "satellite", "soil", "hydro", "spatial", "knowledge", "derived"]


def query_url(url: str, params: dict | None = None) -> str:
    """Pełny URL zapytania GET (tak jak wysyła go httpx) – do `Provenance.query_url`."""
    import httpx
    return str(httpx.URL(url, params={k: str(v) for k, v in (params or {}).items()}))


def now_utc() -> datetime:
    return datetime.now(UTC)


# podbij, gdy zmienia się format/treść provenance we wszystkich konektorach (unieważnia cały cache)
PROV_VERSION = 2


class Connector(ABC):
    key: ClassVar[str]
    title: ClassVar[str]
    category: ClassVar[Category]
    implemented: ClassVar[bool] = True
    timeout_s: ClassVar[float] = settings.default_connector_timeout_s
    live_ttl_s: ClassVar[int] = 3 * 3600
    cache_version: ClassVar[int] = 1           # podbij, gdy zmienia się format danych
    uses_crop: ClassVar[bool] = False          # czy wynik zależy od uprawy (klucz cache)

    @abstractmethod
    async def fetch(self, ctx: AnalysisContext) -> DataBlock[Any]:
        ...

    # ── helpers dla podklas ──
    def block(self, status: BlockStatus, data: Any = None, **kw: Any) -> DataBlock[Any]:
        return DataBlock(key=self.key, title=self.title, status=status, data=data, **kw)

    def prov(self, source_name: str, **kw: Any) -> Provenance:
        return Provenance(source_name=source_name, retrieved_at=now_utc(), **kw)

    def _cache_key(self, ctx: AnalysisContext) -> str:
        return make_key(self.key, v=self.cache_version, pv=PROV_VERSION, parcel=ctx.parcel.id, as_of=ctx.as_of.isoformat(),
                        crop=ctx.crop if self.uses_crop else None)

    async def run(self, ctx: AnalysisContext, use_cache: bool = True) -> DataBlock[Any]:
        t0 = time.perf_counter()
        key = self._cache_key(ctx)
        if use_cache and (hit := cache_get(key)) is not None:
            blk = DataBlock[Any].model_validate(hit)
            for p in blk.provenance:
                if p.mode == "live":
                    p.mode = "cached"
            blk.elapsed_ms = int((time.perf_counter() - t0) * 1000)
            return blk
        try:
            blk = await asyncio.wait_for(self.fetch(ctx), timeout=self.timeout_s)
        except TimeoutError:
            blk = self.block(BlockStatus.error, messages=[f"Przekroczono limit czasu {self.timeout_s:.0f} s."],
                             uncertainty=["Źródło danych nie odpowiedziało na czas – blok pominięty w analizie."])
        except NotImplementedError:
            blk = self.block(BlockStatus.not_implemented, messages=["Konektor jeszcze nie zaimplementowany."])
        except Exception as e:
            log.exception("connector %s failed", self.key)
            blk = self.block(BlockStatus.error, messages=[f"{type(e).__name__}: {e}"],
                             uncertainty=["Błąd pobierania danych – blok pominięty w analizie."])
        blk.elapsed_ms = int((time.perf_counter() - t0) * 1000)
        if blk.status in (BlockStatus.ok, BlockStatus.partial, BlockStatus.no_data, BlockStatus.not_applicable):
            cache_set(key, blk.model_dump(mode="json"), ttl_for(ctx.as_of, self.live_ttl_s))
        return blk
