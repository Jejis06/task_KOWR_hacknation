"""Orkiestrator profilu działki: wszystkie bloki równolegle, w budżecie czasu.

Bloki z `depends_on` liczone są w 2. fali; zależności pobierają przez `run_block(key, ctx)`
(trafienie w cache z 1. fali – bloki ok/partial/no_data są cache'owane).
Frontend może też pobierać bloki pojedynczo (/api/parcel/block) i renderować progresywnie.
"""
from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

from app.config import settings
from app.connectors.registry import BLOCKS
from app.contracts.models import AnalysisContext, BlockStatus, DataBlock, ParcelProfile


async def run_block(key: str, ctx: AnalysisContext, use_cache: bool = True) -> DataBlock[Any]:
    return await BLOCKS[key].run(ctx, use_cache=use_cache)


async def build_profile(ctx: AnalysisContext, keys: list[str] | None = None,
                        use_cache: bool = True) -> ParcelProfile:
    t0 = time.perf_counter()
    keys = keys or list(BLOCKS)
    first = [k for k in keys if not getattr(BLOCKS[k], "depends_on", ())]
    second = [k for k in keys if k not in first]

    async def guarded(k: str) -> DataBlock[Any]:
        remaining = settings.total_budget_s - (time.perf_counter() - t0)
        try:
            return await asyncio.wait_for(run_block(k, ctx, use_cache), timeout=max(remaining, 1))
        except TimeoutError:
            c = BLOCKS[k]
            return DataBlock(key=k, title=c.title, status=BlockStatus.error,
                             messages=["Przekroczono całkowity budżet czasu analizy."])

    results = dict(zip(first, await asyncio.gather(*(guarded(k) for k in first))))
    if second:
        results.update(zip(second, await asyncio.gather(*(guarded(k) for k in second))))
    return ParcelProfile(context=ctx, blocks={k: results[k] for k in keys},
                         generated_at=datetime.now(UTC),
                         total_elapsed_ms=int((time.perf_counter() - t0) * 1000))
