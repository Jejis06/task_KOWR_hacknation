"""AgroLegal – wstępnie wypełnione zgłoszenie wodnoprawne (wzór gov.pl, art. 422 Prawa wodnego).

Zwraca stronę HTML gotową do druku / zapisu jako PDF (druk przeglądarki – zero zależności po stronie serwera).
Wypełniamy wyłącznie dane o działce i inwestycji; dane osobowe (imię, nazwisko, adres) zostają puste do wpisania
ręcznie – zgodnie z wymogiem zadania KOWR (minimalizacja danych osobowych) i niczego nie zapisujemy.
Obsługiwany wariant: pkt 9 wzoru – staw ≤ 5000 m² i ≤ 3 m, zasilany opadowo/gruntowo (art. 394 ust. 1 pkt 9).
"""
from __future__ import annotations

from datetime import date
from html import escape
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from shapely.geometry import Point

from app.api.routes.parcel import _resolve, _validate_date
from app.contracts.models import AnalysisContext
from app.core.geo import to_2180
from app.knowledge import loader
from app.services.profile import run_block

router = APIRouter(prefix="/api/forms", tags=["forms"])

POND_MAX_M2, POND_MAX_DEPTH_M = 5000, 3.0


def _fmt(v: float | None, unit: str = "", dec: int = 0) -> str:
    if v is None:
        return "……"
    s = f"{v:,.{dec}f}".replace(",", " ").replace(".", ",")
    return f"{s} {unit}".strip()


def _line(label: str, value: str | None = None, hint: str | None = None) -> str:
    v = escape(value) if value else "&nbsp;"
    h = f'<div class="hint">{escape(hint)}</div>' if hint else ""
    cls = "val" if value else "val empty"
    return f'<div class="row"><div class="lbl">{escape(label)}</div><div class="{cls}">{v}</div>{h}</div>'


@router.get("/zgloszenie", response_class=HTMLResponse)
async def zgloszenie(id: str | None = None, lon: float | None = None, lat: float | None = None,
                     date_: date | None = Query(None, alias="date"), crop: str | None = None) -> HTMLResponse:
    as_of = _validate_date(date_)
    parcel = await _resolve(id, lon, lat)
    ctx = AnalysisContext(parcel=parcel, as_of=as_of, crop=crop)
    blk = await run_block("analysis", ctx)
    data: Any = blk.data
    if data is not None and not isinstance(data, dict):
        data = data.model_dump(mode="json")
    wb = (data or {}).get("water_balance") or {}
    pond = wb.get("pond") or {}
    if pond.get("needs_permit"):
        raise HTTPException(422, "Zagłębienie na tej działce przekracza 5000 m² – potrzebne jest pozwolenie "
                                 "wodnoprawne, a nie zgłoszenie. Zaplanuj mniejsze oczko albo przygotuj wniosek o pozwolenie.")

    proc = loader.get_item("procedures", "zgloszenie_wodnoprawne") or {}
    fee = (proc.get("fees") or {}).get(str(as_of.year)) or proc.get("fee_pln")
    lon_c, lat_c = parcel.centroid
    p92 = to_2180(Point(lon_c, lat_c))
    area = pond.get("area_m2")
    plan_area = min(area, POND_MAX_M2) if area else None   # analiza już przycina oczko do progu zgłoszenia
    vol = pond.get("volume_m3")

    loc = [
        f"Województwo: {parcel.voivodeship or '……'}; powiat: {parcel.county or '……'}; gmina: {parcel.commune or '……'}",
        f"Obręb: {parcel.region_name or '……'} ({parcel.region_code or '……'}); numer działki: {parcel.parcel_number or '……'}",
        f"Identyfikator działki: {parcel.id}",
        f"Współrzędne środka działki: {lat_c:.6f}° N, {lon_c:.6f}° E (WGS84); "
        f"X = {p92.y:,.1f}, Y = {p92.x:,.1f} (PL-1992)".replace(",", " "),
        f"Powierzchnia działki: {_fmt(parcel.area_ha, 'ha', 2)}",
    ]
    desc = (f"Wykonanie stawu ziemnego (oczka wodnego) w naturalnym zagłębieniu terenu, o powierzchni lustra wody do "
            f"{_fmt(plan_area, 'm²')} i głębokości nieprzekraczającej {_fmt(POND_MAX_DEPTH_M, 'm', 1)} od naturalnej "
            f"powierzchni terenu, o pojemności ok. {_fmt(vol, 'm³')}. Staw napełniany wyłącznie wodami opadowymi, "
            "roztopowymi lub gruntowymi (nie w ramach usług wodnych), bez połączenia z ciekiem. Zasięg oddziaływania "
            "nie wykracza poza granice działki. Skarpy o nachyleniu bezpiecznym (np. 1:2 – 1:3), urobek rozplantowany "
            "na działce. Roboty sprzętem mechanicznym (koparka), bez umocnień betonowych.")
    if pond.get("capped"):
        desc += (f" Staw zajmie najniższą część naturalnego zagłębienia o powierzchni ok. {_fmt(pond.get('depression_area_m2'), 'm²')}"
                 " – powierzchnia lustra wody nie przekroczy 5000 m².")
    if parcel.approximate:
        loc.insert(0, "UWAGA: usługa działek GUGiK była niedostępna – uzupełnij obręb i numer działki ręcznie.")

    ok_box, no_box = "☒", "☐"
    options = [
        (1, "Wykonanie pomostu o szerokości do 3 m i długości do 25 m"),
        (6, "Prowadzenie robót w wodach oraz innych robót, które mogą zmienić stan wód podziemnych"),
        (9, ("Wykonanie stawów napełnianych wyłącznie wodami opadowymi, roztopowymi lub gruntowymi, o powierzchni do "
            "5000 m² i głębokości do 3 m, o zasięgu oddziaływania w granicach własnego terenu")),
        (10, "Przebudowa rowu – przepust lub inny przekrój zamknięty do 10 m"),
    ]
    opts = "".join(f'<div class="opt">{ok_box if n == 9 else no_box} {n}. {escape(t)}</div>' for n, t in options)
    steps = "".join(f"<li>{escape(s)}</li>" for s in (proc.get("steps") or []))
    today = date.today().strftime("%d.%m.%Y")

    html = f"""<!doctype html><html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Zgłoszenie wodnoprawne – {escape(parcel.id)}</title>
<style>
 body {{ font: 15px/1.45 system-ui, -apple-system, Segoe UI, Roboto, sans-serif; color: #111; background: #f4f6f3; margin: 0; }}
 .page {{ max-width: 820px; margin: 16px auto; background: #fff; padding: 28px 32px; border-radius: 8px; box-shadow: 0 1px 4px #0002; }}
 h1 {{ font-size: 22px; margin: 0 0 4px; }} h2 {{ font-size: 16px; margin: 22px 0 8px; border-bottom: 2px solid #2d6a4f; padding-bottom: 3px; }}
 .banner {{ background: #fff6dd; border: 1px solid #e6c46a; padding: 10px 12px; border-radius: 6px; font-size: 13px; }}
 .toolbar {{ position: sticky; top: 0; background: #2d6a4f; color: #fff; padding: 10px 16px; display: flex; gap: 12px; align-items: center; justify-content: center; }}
 .toolbar button {{ font-size: 17px; font-weight: 700; padding: 10px 22px; border-radius: 8px; border: 0; background: #fff; color: #2d6a4f; cursor: pointer; }}
 .row {{ margin: 6px 0 10px; }} .lbl {{ font-size: 12px; color: #444; font-weight: 600; text-transform: uppercase; letter-spacing: .02em; }}
 .val {{ border-bottom: 1px solid #999; min-height: 24px; padding: 2px 0; white-space: pre-wrap; }}
 .val.empty {{ min-height: 28px; }} .hint {{ font-size: 12px; color: #666; }}
 .opt {{ margin: 4px 0; font-size: 14px; }} ul, ol {{ padding-left: 20px; }} li {{ margin: 3px 0; }}
 .meta {{ font-size: 12px; color: #555; }} .org {{ text-align: right; }}
 .sig {{ display: flex; justify-content: space-between; margin-top: 36px; font-size: 12px; }} .sig div {{ border-top: 1px solid #999; padding-top: 4px; width: 40%; text-align: center; }}
 .pb {{ page-break-before: always; }}
 @media print {{ body {{ background: #fff; }} .toolbar, .noprint {{ display: none; }} .page {{ box-shadow: none; margin: 0; max-width: none; padding: 0 6mm; }} }}
</style></head><body>
<div class="toolbar noprint"><span>Wstępnie wypełnione przez AgroLegal</span>
<button onclick="window.print()">🖨 Drukuj / zapisz jako PDF</button></div>
<div class="page">
 <div class="banner noprint">Sprawdź każde pole przed złożeniem. <b>Dane osobowe wpisz ręcznie</b> – AgroLegal ich nie zbiera.
 Informacja orientacyjna, nie porada prawna. Ostateczna kwalifikacja należy do Wód Polskich.</div>
 <div class="org"><div class="lbl">Organ, do którego kierujesz zgłoszenie</div>
 <div>Kierownik Nadzoru Wodnego właściwego dla gminy <b>{escape(parcel.commune or '……')}</b><br>Państwowe Gospodarstwo Wodne Wody Polskie</div>
 <div class="hint">Adres nadzoru wodnego znajdziesz na wody.gov.pl → Kontakt (wyszukaj po nazwie gminy).</div></div>
 <h1>Zgłoszenie wodnoprawne</h1>
 <div class="meta">na podstawie art. 422 ustawy z dnia 20 lipca 2017 r. – Prawo wodne (t.j. Dz.U. 2026 poz. 1335 ze zm.)</div>

 <h2>2. Zgłaszający (wypełnij ręcznie, WIELKIMI LITERAMI)</h2>
 {_line("Imię i nazwisko / nazwa")}
 {_line("Adres zamieszkania (miejscowość, ulica, nr, kod pocztowy, poczta)")}
 {_line("Telefon / e-mail (nieobowiązkowe)")}

 <h2>4. Treść zgłoszenia</h2>
 <div class="lbl">4.1. Czynność, roboty lub urządzenie wodne wymagające zgłoszenia</div>{opts}
 {_line("4.1.1. Cel", "Retencja wód opadowych i roztopowych na potrzeby gospodarstwa rolnego – ograniczenie skutków suszy "
        "i spowolnienie odpływu wody z pola.")}
 {_line("4.2. Stan prawny nieruchomości", None, "Np. „własność zgłaszającego, księga wieczysta nr ……”. Staw tylko na "
        "własnym gruncie (lub z pisemną zgodą właścicieli gruntów w zasięgu oddziaływania).")}
 {_line("4.3. Opis robót i podstawowe parametry", desc)}
 {_line("4.4. Lokalizacja (dane ewidencyjne i współrzędne)", chr(10).join(loc))}
 {_line("4.5. Planowany termin rozpoczęcia robót (DD-MM-RRRR)", None, "Co najmniej 30 dni po złożeniu – tyle organ ma "
        "na ewentualny sprzeciw.")}

 <h2>5. Podstawa prawna</h2>
 <p>Art. 422 w związku z art. 394 ust. 1 pkt 9 ustawy z dnia 20 lipca 2017 r. – Prawo wodne.</p>

 <h2>6. Załączniki</h2>
 <ol>
  <li>Mapa sytuacyjno-wysokościowa z państwowego zasobu geodezyjnego i kartograficznego z naniesionym schematem stawu
   i zasięgiem oddziaływania (układ wysokościowy PL-EVRF2007-NH) – zamówisz w starostwie albo przez geoportal.gov.pl.</li>
  <li>Szkic lub rysunek stawu (wymiary, głębokość, skarpy).</li>
  <li>Dowód wniesienia opłaty za zgłoszenie: <b>{_fmt(fee, 'zł', 2)}</b> (stawka {as_of.year}) na rachunek Wód Polskich.</li>
  <li>Pisemna zgoda właścicieli sąsiednich gruntów – tylko jeśli oddziaływanie stawu wykracza poza Twoją działkę.</li>
  <li>Pełnomocnictwo z opłatą skarbową 17 zł – tylko jeśli działa pełnomocnik.</li>
 </ol>
 <div class="sig"><div>miejscowość, data</div><div>podpis zgłaszającego</div></div>

 <div class="pb"></div>
 <h2>Jak złożyć – krok po kroku</h2>
 <ol>{steps}</ol>
 <p><b>Sposób złożenia:</b> {escape(proc.get("how_to_submit") or "osobiście lub listownie")}</p>
 <p><b>Ważne:</b> szczelne oczko do 50 m² nie wymaga zgłoszenia. Staw większy niż 5000 m², głębszy niż 3 m albo
 zasilany z rowu lub cieku wymaga <b>pozwolenia wodnoprawnego</b>. Kilka stawów na jednej działce się sumuje.
 Staw głębszy niż 3 m może wymagać decyzji środowiskowej (wójt/burmistrz).</p>
 <p class="meta">Wygenerowano {today} przez AgroLegal z danych: GUGiK ULDK (działka), GUGiK NMT (zagłębienie terenu),
 wzór zgłoszenia gov.pl, opłaty M.P. 2025 poz. 717 / M.P. 2026 poz. 430. Wymiary stawu to szacunek z modelu terenu –
 zweryfikuj w terenie.</p>
</div></body></html>"""
    return HTMLResponse(html)
