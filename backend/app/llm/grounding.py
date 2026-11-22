"""Kontekst dla LLM: fakty o działce (blok `analysis`, `legal_context`) + baza prawna i dotacje jako ponumerowane źródła.

Model widzi tylko te fakty i źródła [S1…Sn]; w odpowiedzi podaje numery źródeł i identyfikatory działań, a my zamieniamy je
na linki i plakietki formalności z reguł. Dzięki temu nie da się „wyhalucynować” przepisu, adresu ani kwalifikacji prawnej.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.contracts.models import AnalysisContext
from app.knowledge import loader
from app.services.profile import run_block

log = logging.getLogger(__name__)
MONTHS = ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"]
FORMALITY_PL = {"none": "bez formalności", "notification": "zgłoszenie wodnoprawne", "permit": "pozwolenie wodnoprawne",
                "depends": "zależy od wykonania"}


@dataclass
class Source:
    sid: str
    title: str
    url: str | None


@dataclass
class Grounding:
    ctx: AnalysisContext
    analysis: dict[str, Any] | None
    recs: list[dict[str, Any]]
    sources: list[Source] = field(default_factory=list)
    text: str = ""

    def source(self, sid: str) -> Source | None:
        return next((s for s in self.sources if s.sid == sid), None)

    def rec(self, measure_id: str) -> dict[str, Any] | None:
        return next((r for r in self.recs if r.get("measure_id") == measure_id), None)


def _dump(data: Any) -> dict[str, Any] | None:
    if data is None:
        return None
    return data if isinstance(data, dict) else data.model_dump(mode="json")


def _first_url(refs: list[str] | None) -> str | None:
    return next((u for u in (loader.public_source(x) for x in refs or []) if u), None)


async def build(ctx: AnalysisContext) -> Grounding:
    blk = await run_block("analysis", ctx)
    a = _dump(blk.data)
    g = Grounding(ctx=ctx, analysis=a, recs=list((a or {}).get("recommendations") or []))
    sources: list[Source] = []

    def add(title: str, url: str | None) -> str:
        sid = f"S{len(sources) + 1}"
        sources.append(Source(sid, title, url))
        return sid

    lines: list[str] = []
    p = ctx.parcel
    lines.append("## DZIAŁKA")
    lines.append(f"Identyfikator: {p.id}; gmina: {p.commune or '?'}; powiat: {p.county or '?'}; woj.: {p.voivodeship or '?'}; "
                 f"powierzchnia: {p.area_ha:.2f} ha; data analizy: {ctx.as_of.isoformat()}; uprawa: {ctx.crop or 'nie wybrano'}.")
    if p.approximate:
        lines.append("UWAGA: granice działki nieznane (GUGiK niedostępny) – analiza ~1 ha wokół punktu.")

    # źródła danych z bloku analysis (provenance)
    data_sids = [add(f"Dane: {pv.source_name}", pv.source_url) for pv in (blk.provenance or [])[:6]]

    if a and a.get("assessment"):
        s = a["assessment"]
        lines.append("\n## OCENA SYTUACJI WODNEJ (z reguł, nie zmieniaj)")
        lines.append(f"Teraz: {s.get('current_label_pl')}. {s.get('current_summary') or ''}")
        lines.append(f"10 lat: {s.get('historical_label_pl')}. {s.get('historical_summary') or ''}")
        if s.get("critical_months"):
            lines.append("Miesiące największego ryzyka: " + ", ".join(MONTHS[m - 1] for m in s["critical_months"]))
        lines.append(f"Pewność oceny: {s.get('confidence')}. Źródła danych: {', '.join(data_sids)}")
        for e in (s.get("evidence") or [])[:6]:
            lines.append(f"- dowód: {e.get('text')}")
        if s.get("field_check"):
            lines.append(f"Pogoda × rośliny: {s['field_check'].get('label_pl')} – {s['field_check'].get('text')}")
    else:
        lines.append("\n## OCENA: brak danych do oceny – nie formułuj zaleceń, powiedz to wprost.")

    if a:
        if a.get("causes"):
            lines.append("\n## PRZYCZYNY NIEDOBORU")
            for c in a["causes"]:
                lines.append(f"- {c.get('label_pl')} (~{c.get('share')}%): {c.get('explanation')}")
        if g.recs:
            lines.append("\n## DZIAŁANIA (measure_id → formalność z reguł; kolejność KOWR: retencja → agrotechnika → nawadnianie)")
            for r in g.recs:
                fund = "; ".join(f"{f.get('name')} [{f.get('call_label')}]" for f in r.get("funding") or [])
                fee = f"; opłata {r['fee_pln']:.2f} zł" if r.get("fee_pln") else ""
                lines.append(f"- {r['measure_id']}: {r.get('title')} | grupa: {r.get('group')} | formalność: "
                             f"{FORMALITY_PL.get(r.get('formality') or 'none')}{fee} | kiedy: {r.get('when') or '-'} | "
                             f"dlaczego: {r.get('why')} | warunki prawne: {r.get('formality_note') or '-'} | "
                             f"urząd: {r.get('office') or '-'} | pieniądze: {fund or 'brak'}")
        wb = a.get("water_balance") or {}
        if wb:
            lines.append("\n## BILANS WODY DZIAŁKI")
            lines.append(f"Niedobór w sezonie: {wb.get('season_deficit_mm')} mm ≈ {wb.get('season_deficit_m3')} m³; "
                         f"z ostatnich 60 dni: {wb.get('deficit_60d_m3')} m³.")
            if pond := wb.get("pond"):
                lines.append(f"Oczko: pojemność {pond.get('volume_m3')} m³, pow. {pond.get('area_m2')} m², koszt wykopu "
                             f"{pond.get('cost_pln_min')}–{pond.get('cost_pln_max')} zł (szacunek), zwrot z dotacji do "
                             f"{pond.get('subsidy_pln_max')} zł ({pond.get('subsidy_note')}).")
        if irr := a.get("irrigation"):
            lines.append(f"\n## NAWADNIANIE: {irr.get('recommended')} – {irr.get('summary')}")
        if a.get("limitations"):
            lines.append("\n## OGRANICZENIA ANALIZY")
            lines += [f"- {t}" for t in a["limitations"][:5]]

    # prognoza i kalendarz uprawy – do pytań „co i kiedy zrobić” (bloki z cache, liczone już dla raportu)
    try:
        fc = _dump((await run_block("weather_forecast", ctx)).data) or {}
        if fc.get("dates"):
            rain = sum(x or 0 for x in fc.get("precip_mm") or [])
            et0 = sum(x or 0 for x in fc.get("et0_mm") or [])
            lines.append(f"\n## PROGNOZA ({len(fc['dates'])} dni od {fc['dates'][0]}): opad {rain:.0f} mm, parowanie {et0:.0f} mm, "
                         f"bilans {rain - et0:+.0f} mm.")
    except Exception as e:  # noqa: BLE001 – prognoza jest dodatkiem, brak nie blokuje odpowiedzi
        log.info("LLM grounding: brak prognozy (%s)", e)
    try:
        cal = _dump((await run_block("crop_calendar", ctx)).data) or {}
        if cal.get("crop_name_pl"):
            lines.append(f"\n## UPRAWA: {cal['crop_name_pl']}; w sezonie: {'tak' if cal.get('in_season_on_as_of') else 'nie'}; "
                         f"faza: {cal.get('current_stage') or '-'}; okresy krytyczne: {', '.join(cal.get('critical_water_periods') or []) or '-'}; "
                         f"uwagi: {'; '.join(cal.get('warnings') or []) or '-'}")
    except Exception as e:  # noqa: BLE001
        log.info("LLM grounding: brak kalendarza uprawy (%s)", e)

    lines.append("\n## PRZEPISY (Prawo wodne i powiązane; cytuj numerem źródła)")
    for it in loader.items("legal_pl"):
        sid = add(f"{it.get('title')}" + (f" – {it['legal_basis']}" if it.get("legal_basis") else ""),
                  _first_url(it.get("sources")))
        extra = f" Uwaga: {it['open_question']} ({it.get('open_question_status')})" if it.get("open_question") else ""
        lines.append(f"[{sid}] {it.get('title')}: {it.get('rule')} Wymóg: {it.get('requirement')}. Status: {it.get('status')}.{extra}")

    lines.append("\n## PROCEDURY")
    for it in loader.items("procedures"):
        sid = add(it.get("title") or it["id"], _first_url(it.get("sources")) or it.get("form_url"))
        fees = it.get("fees") or {}
        fee = f" Opłata {ctx.as_of.year}: {fees.get(str(ctx.as_of.year)) or it.get('fee_pln')} zł." if fees or it.get("fee_pln") else ""
        steps = " → ".join(str(x) for x in (it.get("steps") or [])[:6])
        lines.append(f"[{sid}] {it.get('title')}: organ: {it.get('organ')}. Kiedy: {it.get('when') or '-'}. "
                     f"Jak: {it.get('how_to_submit') or '-'}.{fee} Kroki: {steps}")

    lines.append("\n## DOTACJE (status naboru z katalogu – nie obiecuj pieniędzy przy zamkniętym naborze)")
    kinds = loader.meta("funding").get("call_kinds") or {}
    for it in loader.items("funding"):
        sid = add(it.get("name") or it["id"], _first_url(it.get("sources")))
        lines.append(f"[{sid}] {it.get('name')} | dla rolnika: {'tak' if it.get('for_farmer') else 'nie (gminy/instytucje)'} | "
                     f"status: {kinds.get(it.get('call_kind') or 'unknown')} | nabór: {it.get('call') or '-'} | "
                     f"zakres: {it.get('scope') or '-'} | warunki: {it.get('conditions') or '-'}")

    g.sources, g.text = sources, "\n".join(lines)
    return g
