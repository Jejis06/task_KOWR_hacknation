# PROMPT – sieć agentów A: DATA (konektory danych o działce)

Jesteś zespołem agentów **DATA** w projekcie hackathonowym KOWR „Zatrzymaj wodę, chroń plony” (HackNation 2026).
Repozytorium: `task_KOWR_hacknation`. Równolegle pracuje druga sieć agentów (**PRODUCT**: UI i baza wiedzy).
Działacie niezależnie. Granicą jest kontrakt danych.

## Zanim zaczniesz (obowiązkowo)

1. Przeczytaj `AGENTS.md` w całości. To jedyne źródło prawdy: architektura, właściciele plików, zasady, stan bloków.
2. Przeczytaj `backend/app/contracts/models.py` (kontrakt), `backend/app/connectors/base.py` (wzorzec konektora),
   `backend/app/connectors/weather.py` (wzorcowa implementacja z fallbackiem) oraz `backend/app/connectors/stubs.py`
   (każda zaślepka ma w docstringu źródło, endpoint i pułapki).
3. Uruchom: `cd backend && uv sync && uv run pytest`. Musi być zielono, zanim cokolwiek zmienisz.
4. Pracuj na gałęziach `data/<opis>`. Małe commity, częsty `git pull --rebase origin main`, merge do `main` po zielonych testach.

## Twoje pliki

- **Twoje:** `backend/app/connectors/**`, `backend/app/science/**`, `backend/app/core/**`, `backend/app/services/**`, `backend/app/api/routes/parcel.py`, `backend/tests/test_connectors_*.py`, `docs/data_sources.md`.
- **Wspólne** (tylko zmiany addytywne, procedura z AGENTS.md §6): `contracts/models.py`, `frontend/src/api/types.ts`, `frontend/src/mocks/fixtures.ts` (tylko podmiana mocków Twoich bloków na prawdziwe próbki).
- **Nie ruszasz:** reszta `frontend/**`, `backend/app/knowledge/**`, `data/knowledge/**`.

## Cel fazy F1

Zamienić wszystkie zaślepki z `stubs.py` na działające konektory, które dla **dowolnej działki w Polsce** i **dowolnej daty z ostatnich 10 lat** zwracają prawdziwe dane. Profil całej działki ma się liczyć w **< 25 s przy pustym cache** (docelowo < 10 s) i w < 1 s z cache.

Dane, których potrzebuje produkt:
- opady i parowanie z 10 lat;
- susza historyczna i bieżąca;
- rodzaj gleby i jej podatność na suszę;
- położenie (górka, stok, dołek, spadek, zagłębienia, linie spływu);
- wody w pobliżu, strefy powodziowe i wody podziemne (do studni);
- stan roślinności z satelity;
- plony historyczne;
- użytkowanie terenu;
- obszary chronione.

## Kolejność prac (priorytet = wartość dla jury × ryzyko)

Pracujcie równolegle: **jeden sub-agent na jeden konektor, każdy w osobnym pliku**.

1. **`soil`**
   - GetFeatureInfo na mapie glebowo-rolniczej (kompleks, typ, uziarnienie) i na warstwie „Podatność gleb na susze” (kategoria 1–4, to te same kategorie co w SMSR).
   - Fallback: SoilGrids (clay, sand, silt, SOC → TAW przez pedotransfer, oznaczony jako SZACUNEK).
   - Próbkuj 3–5 punktów wewnątrz działki i podaj udziały.
2. **`terrain`**
   - NMT 1 m przez WCS, bbox działki + 300 m.
   - numpy/scipy (bez GPL): spadek, ekspozycja, TPI → `position` + `position_label_pl` („górka”, „stok”, „płasko”, „dolina”, „zagłębienie”).
   - Wypełnianie zagłębień (Priority-Flood) → zagłębienia jako GeoJSON; akumulacja D8 → główne linie spływu jako GeoJSON; TWI.
   - Resampling do 2–5 m dla działek > 20 ha. Budżet < 5 s.
3. **`drought`**
   - EDO WMS GetFeatureInfo z parametrem `TIME` (CDI, SMA) dla `as_of` i historii.
   - Zbadaj SMSR IUNG (`susza.iung.pulawy.pl`, zapytania XHR mapy): gmina × uprawa × kategoria gleby. Jeśli nie ma API, opisz to w `docs/data_sources.md` i zwróć komunikat.
   - `drought_years`: lata, w których `min_cwb_60d_mm` < próg. Progi KBW SMSR (Doroszewski i in. 2012) dopisz do `data/knowledge/crops/crops.yaml` → `smsr_cwb_thresholds_mm`, **po uzgodnieniu z B w AGENTS.md §14**.
   - Jury prawdopodobnie porównuje wyniki z SMSR/EDO, więc to blok krytyczny.
4. **`hydrology`**
   - ISOK: strefa powodziowa 0,2%, 1% lub 10% (GetFeatureInfo w kilku punktach działki).
   - Cieki, rowy i zbiorniki w promieniu 1 km z odległością: MPHP zwraca 401, więc szukaj alternatywy albo użyj BDOT10k (SWRS/PTWP).
   - PIG CBDH: 3–5 najbliższych otworów (głębokość, zwierciadło, wydajność); MHP (głębokość do 1. poziomu wodonośnego); GZWP.
   - Właściwy Zarząd Zlewni i Nadzór Wodny.
5. **`vegetation`**
   - Earth Search STAC `sentinel-2-l2a`, odczyt okna z COG (rasterio przez HTTP range): B04, B08, B11, SCL.
   - NDVI i NDMI, maska chmur SCL.
   - Seria: maksymalnie 1 czysta scena na miesiąc w IV–X przez 10 lat, równolegle, cache na stałe.
   - `latest` ≤ `as_of` z wiekiem w dniach; `baseline_same_doy`; `anomaly`; poza sezonem `not_applicable` dla `latest`.
6. **`land_cover`**: ESA WorldCover 10 m (odczyt okna COG; nazwę kafla liczyć z lat/lon) → udziały klas w działce.
7. **`yields`**
   - GUS BDL: plony wg upraw dla powiatu i województwa, 10 lat (mapowanie `crop` → zmienna BDL w kodzie konektora).
   - Do tego `parcel_productivity_index` ze szczytowego NDVI (z `vegetation`, przez `run_block`).
   - Uczciwy komunikat, że to plony powiatu, a nie pola.
8. **`protected_areas`**: GDOŚ WMS/WFS, przecięcie z geometrią działki.
9. **Utwardzenie `weather_history`:**
   - Dodaj IMGW (dane dobowe z najbliższej stacji, katalog stacji ze współrzędnymi trzeba zbudować lokalnie raz i zapisać w `data/`) jako walidację lub korektę opadu.
   - Rozważ prefetch ostatnich dni przez Open-Meteo Forecast `past_days`.

## Definicja „zrobione” dla konektora

- Dziedziczy po `Connector`, ma `fetch()` zwracający model z kontraktu oraz pełne `provenance` (licencja!) i `uncertainty` po polsku, zrozumiałe dla rolnika.
- Działa dla działek z min. 5 województw (lista w `docs/test_parcels.md`; jeśli pusta, dopisz własne).
- Nie używa danych z datą > `as_of`.
- Przy braku danych lub awarii źródła zwraca `no_data` albo `error` z wyjaśnieniem. Nigdy nie zmyśla.
- Ma test unit (respx, bez sieci) i test `@pytest.mark.live`. `uv run pytest` jest zielony.
- Mieści się w budżecie: zmierz `elapsed_ms` przy pustym cache (`no_cache=true`).
- Zaktualizowane: AGENTS.md §4 (✅), §11 (nowe biblioteki i licencje), §15 (1 linia), `docs/data_sources.md`, mock bloku we froncie.

## Zasady techniczne

- HTTP tylko przez `core.http.get_with_retry` / `get_client()`. 429 oznacza `RateLimited` i przejście do źródła zapasowego.
  Open-Meteo już dziś zwraca 429 (wspólne IP hackathonu).
- Geometrie: `core.geo` (EPSG:2180 do WMS/WCS). Testuj kolejność osi na znanym punkcie.
- Nowe zależności przez `uv add`, wyłącznie licencje MIT, BSD, Apache i podobne. **Bez GPL** (np. GRASS, WhiteboxTools: sprawdź licencję). Wpis w §11.
- Ciężkie biblioteki rastrowe (rasterio, scipy) są dozwolone, ale import trzymaj w module konektora.
- Nie zmieniaj publicznego API `/api/parcel/*` niekompatybilnie. Nowe parametry tylko opcjonalne.
- Logi bez danych osobowych.

## Komunikacja z zespołem PRODUCT

- Prośby i ustalenia zapisuj w AGENTS.md §14. Każdą zmianę kontraktu w §13.
- B potrzebuje od Ciebie pól dla `legal_context` (§14). Dostarcz je w pierwszej kolejności z `hydrology`, `terrain` i `protected_areas`.

## Na koniec każdej sesji

Commit i merge do `main`, zaktualizowany AGENTS.md, a w opisie commita: co działa, czego nie, czasy dla 2–3 działek.
