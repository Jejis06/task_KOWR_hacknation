"""Plony historyczne → YieldInfo.

UWAGA: publicznych plonów per pole w Polsce NIE MA, a GUS BDL publikuje plony z 1 ha (dt/ha) tylko dla
województw i kraju (zmienne P1423 „Produkcja roślinna”, P2138 „Inne wybrane uprawy rolnicze”; poziom
powiatów – brak, sprawdzone 21.11.2026). Dlatego:
1) GUS BDL API `https://bdl.stat.gov.pl/api/v1/data/by-variable/{id}` – województwo działki + Polska, 10 lat.
2) Proxy dla działki: szczytowe NDVI w sezonie z bloku `vegetation` → indeks względny (rok / mediana lat).
"""
from __future__ import annotations

import asyncio
import statistics
from collections import defaultdict
from typing import Any, ClassVar

from app.connectors.base import Connector
from app.contracts.models import (
    AnalysisContext,
    BlockStatus,
    DataBlock,
    VegetationInfo,
    YieldInfo,
    YieldRecord,
)
from app.core.http import RateLimited, get_with_retry

BDL = "https://bdl.stat.gov.pl/api/v1/data/by-variable/{var}"
LIC = "GUS – Bank Danych Lokalnych, otwarte dane (ponowne wykorzystanie z podaniem źródła)"
# uprawa (crops.yaml) → (zmienna BDL „plony z 1 ha, ogółem”, nazwa GUS)
CROP_VAR: dict[str, tuple[int, str]] = {
    "pszenica_ozima": (4332, "pszenica"), "pszenica_jara": (4332, "pszenica"), "zyto_ozime": (4338, "żyto"),
    "jeczmien_jary": (4344, "jęczmień"), "owies": (4350, "owies"), "pszenzyto": (4356, "pszenżyto"),
    "kukurydza_ziarno": (47752, "kukurydza na ziarno"), "kukurydza_kiszonka": (47749, "kukurydza na zielonkę"),
    "rzepak_ozimy": (4380, "rzepak i rzepik"), "ziemniak": (4368, "ziemniaki"),
    "burak_cukrowy": (4374, "buraki cukrowe"), "soja": (47769, "soja"), "groch": (47740, "rośliny strączkowe"),
    "tuz": (4386, "łąki trwałe (siano)"),
}
DEFAULT_VAR = (4314, "zboża ogółem")


async def bdl_series(var: int, level: int, years: list[int]) -> list[dict]:
    params: list[tuple[str, Any]] = [("unit-level", level), ("format", "json"), ("page-size", 100)]
    params += [("year", y) for y in years]
    r = await get_with_retry(BDL.format(var=var), params=params, timeout_s=10)  # type: ignore[arg-type]
    return r.json().get("results", [])


def peak_ndvi_index(veg: VegetationInfo) -> list[dict]:
    peaks: dict[int, float] = defaultdict(float)
    for o in veg.series + ([veg.latest] if veg.latest else []):
        if o and o.ndvi is not None and 4 <= o.date.month <= 9:
            peaks[o.date.year] = max(peaks[o.date.year], o.ndvi)
    if len(peaks) < 3:
        return []
    med = statistics.median(peaks.values())
    return [{"year": y, "peak_ndvi": round(v, 3), "rel_index": round(v / med, 2)} for y, v in sorted(peaks.items())]


class YieldsConnector(Connector):
    key = "yields"
    title = "Plony historyczne"
    category = "derived"
    live_ttl_s = 30 * 24 * 3600
    timeout_s = 20
    uses_crop = True
    cache_version = 2
    depends_on: ClassVar[tuple[str, ...]] = ("vegetation",)

    async def fetch(self, ctx: AnalysisContext) -> DataBlock[Any]:
        from app.services.profile import run_block

        var, gus_name = CROP_VAR.get(ctx.crop or "", DEFAULT_VAR)
        msgs: list[str] = []
        if ctx.crop and ctx.crop not in CROP_VAR:
            msgs.append(f"GUS nie publikuje plonów dla uprawy „{ctx.crop}” – pokazujemy „{gus_name}”.")
        elif not ctx.crop:
            msgs.append(f"Nie wybrano uprawy – pokazujemy plony „{gus_name}”.")
        # dane GUS za rok N publikowane są w kolejnym roku → bez podglądania przyszłości: lata < rok analizy
        years = list(range(ctx.as_of.year - 10, ctx.as_of.year))
        voiv, country, veg = await asyncio.gather(bdl_series(var, 2, years), bdl_series(var, 0, years),
                                                  run_block("vegetation", ctx), return_exceptions=True)
        info = YieldInfo()
        provs = []
        wanted = (ctx.parcel.voivodeship or "").upper()
        for res, level in ((voiv, "voivodeship"), (country, "country")):
            if isinstance(res, RateLimited):
                msgs.append("GUS BDL: limit zapytań (429).")
                continue
            if isinstance(res, Exception):
                msgs.append(f"GUS BDL niedostępny ({type(res).__name__}).")
                continue
            for unit in res:
                if level == "voivodeship" and unit.get("name", "").upper() != wanted:
                    continue
                for v in unit.get("values", []):
                    if v.get("val") is None:
                        continue
                    info.official.append(YieldRecord(year=int(v["year"]), crop=gus_name,
                                                     yield_t_ha=round(float(v["val"]) / 10, 2), level=level,
                                                     unit_name=unit.get("name", "").capitalize()))
        if info.official:
            provs.append(self.prov("GUS – Bank Danych Lokalnych (plony z 1 ha, ogółem)",
                                   source_url=BDL.format(var=var), licence=LIC,
                                   data_as_of=None, notes=f"zmienna {var}: {gus_name}; dt/ha → t/ha"))
        info.official.sort(key=lambda r: (r.level, r.year))
        if not isinstance(veg, Exception) and veg.data:
            vi = veg.data if isinstance(veg.data, VegetationInfo) else VegetationInfo.model_validate(veg.data)
            info.parcel_productivity_index = peak_ndvi_index(vi)
            if info.parcel_productivity_index:
                provs.append(self.prov("Indeks produktywności działki ze szczytowego NDVI (Sentinel-2)",
                                       licence="obliczenia własne na danych Copernicus Sentinel",
                                       notes="szczytowe NDVI IV–IX danego roku / mediana z lat"))
        info.note = ("Plony urzędowe GUS dotyczą całego województwa (i Polski), a nie Twojego pola – GUS nie "
                     "publikuje plonów dla powiatów ani działek. Indeks z NDVI pokazuje, czy dany rok był na tej "
                     "działce lepszy (>1) czy gorszy (<1) od typowego, ale nie przelicza się wprost na tony.")
        unc = [info.note, "Szczytowe NDVI zależy od uprawy w danym roku (płodozmian!) – porównuj lata z tą samą uprawą.",
               f"Dane GUS za rok {ctx.as_of.year} nie są jeszcze dostępne na dzień analizy."]
        if not provs:
            return self.block(BlockStatus.error, messages=msgs, uncertainty=["Brak danych o plonach."])
        status = BlockStatus.ok if info.official and info.parcel_productivity_index else BlockStatus.partial
        return self.block(status, info, provenance=provs, uncertainty=unc, messages=msgs)
