# Źródła danych – szczegóły techniczne (właściciel: zespół DATA)

Skrót i stan: AGENTS.md §4. Tutaj: dokładne warstwy, parametry zapytań, formaty odpowiedzi, limity, pułapki.
Każdy konektor dopisuje sekcję w formacie:

## <key> – <źródło>
- Endpoint / warstwy:
- Przykładowe zapytanie:
- Format odpowiedzi:
- Limity / czas odpowiedzi:
- Licencja:
- Pułapki:

## weather_history – Open-Meteo Archive → NASA POWER
- Open-Meteo: `https://archive-api.open-meteo.com/v1/archive?latitude&longitude&start_date&end_date&daily=precipitation_sum,temperature_2m_max,temperature_2m_min,et0_fao_evapotranspiration&timezone=Europe/Warsaw`
- NASA POWER: `https://power.larc.nasa.gov/api/temporal/daily/point?parameters=PRECTOTCORR,T2M_MAX,T2M_MIN,RH2M,WS2M,ALLSKY_SFC_SW_DWN&community=AG&longitude&latitude&start=YYYYMMDD&end=YYYYMMDD&format=JSON`
  (Rs w MJ/m²/d dla community=AG; fill_value -999; ET0 liczone FAO-56 PM w `science/et0.py`).
- Limity: Open-Meteo 429 przy wspólnym IP (21.11.2026); POWER ~1,5 s dla 10 lat.
- Licencje: Open-Meteo CC BY 4.0 (API darmowe niekomercyjnie); NASA POWER – domena publiczna.
- Pułapki: reanaliza, nie pomiar; POWER siatka ~50 km; opóźnienie ostatnich dni.
- Walidacja opadu: najbliższa stacja synoptyczna IMGW (≤ 60 km), archiwum dobowe
  `https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/dobowe/synop/{rok}/{rok}_{kod3}_s.zip`
  (rok bieżący: `{rok}_{mm}_s.zip`, wszystkie stacje). CSV cp1250: kol. 13 = SMDB (opad), kol. 14 = status (8 = brak pomiaru,
  9 = brak zjawiska). Współrzędne stacji: `api/data/meteo` (kod 9-cyfrowy = NSP z CSV) → `data/imgw/synop_stations.json`
  (`scripts/build_imgw_stations.py`). Pułapka: >3 równoległe pobrania → serwer odpowiada po 10–35 s.
  Wynik 21.11.2026: NASA POWER zawyża opad IV–IX o 8–21% względem stacji (Poznań, Rzeszów, Zamość).

## soil – IUNG kategorie podatności gleb na suszę + Mapa glebowo-rolnicza → SoilGrids
- IUNG GeoServer WMS `https://sgeo.iung.pl/geoserver/wms`, warstwa `Susza:katgl_landuse2024` (raster; te same kategorie
  1–4 co w SMSR). GetFeatureInfo 1.3.0, `INFO_FORMAT=application/json` → `GRAY_INDEX`: 1–4 kategorie, 5 gleby organiczne,
  11 lasy, 12 wody, 13 zabudowa, 14 komunikacja/nieużytki, 19/99 niesklasyfikowane, 0/255 brak. Warstwę znaleziono w JS mapy
  SMSR (`susza.iung.pulawy.pl/static/js/mapkat.js`).
- Mapa glebowo-rolnicza (GUGiK/IUNG) ArcGIS WMS `https://mapy.geoportal.gov.pl/wss/service/pub/guest/MapaGlebowoRolnicza/MapServer/WMSServer`,
  warstwa `0` (KONTURY_GLEBOWE), `INFO_FORMAT=text/xml` (`<FIELDS KOMPLEKS_NR=… TYPPODTYP_NR=… PODLOZE1..5=…/>`).
- Próbkowanie: do 5 punktów wewnątrz działki (`core.geo.sample_points_2180`, odsunięcie 8 m od granicy), równolegle.
- Fallback / uzupełnienie: SoilGrids v2 `rest.isric.org/soilgrids/v2.0/properties/query` (clay/sand/silt/soc 0–100 cm) →
  TAW Saxton & Rawls (2006). Limit ISRIC ~5 zapytań/min – wołamy z timeoutem 5 s, błąd nie psuje bloku.
- `awc_mm` dla kategorii SMSR = środek przedziału WOD (Ślusarczyk 1979): I 110, II 150, III 186, IV 220 mm [SZACUNEK].
- Pułapki: WMS 1.3.0 + EPSG:2180 → BBOX = (N, E, N, E); mapa z lat 60.–80.; kody typów gleb wielo-literowe (Emt, Cd) –
  opis po najdłuższym znanym prefiksie. Czas: 4–9 s (MGR WMS najwolniejszy).

## terrain – NMT GUGiK (usługa wysokości) → numpy/scipy
- WCS `…/PZGIK/NMT/GRID1/WCS/DigitalTerrainModelFormatTIFF`: GetCapabilities/DescribeCoverage OK, **GetCoverage wisi > 60 s**
  (21.11.2026, wersje 1.0.0 i 2.0.1) → nieużywany.
- Używamy `https://services.gugik.gov.pl/nmt/?request=GetHByPointList` (POST `list="N E,N E,…"`, EPSG:2180).
  **Pułapka: usługa zwraca wysokości tylko dla ~1000 pierwszych punktów żądania** (reszta bez wartości) → paczki po 1000,
  równolegle; siatka ≤ 7000 punktów (krok 8–20 m) w bbox działki + 300 m; ~2,5 s.
- Obliczenia (`science/terrain.py`): spadek/ekspozycja (gradient), TPI (okno 300 m), Priority-Flood (Barnes 2014) →
  zagłębienia ≥ 0,2 m i ≥ 200 m² (GeoJSON z objętością), D8 + akumulacja → linie spływu ze zlewnią ≥ 1 ha, TWI.
  Klasyfikacja pozycji: progi TPI min(max(0,3 m; 0,5·SD); 1,5 m) i min(max(1 m; SD); 3 m).
- Licencja: PZGiK – bezpłatnie.

## drought – SMSR (tabele gmin) + KBW działki + EDO
- SMSR: brak API; tabele HTML `https://susza.iung.pulawy.pl/wykazy/{rok},{TERYT7}/` dla lat ≥ 2020 (2018 → 404).
  TERYT gminy z jednostki ewidencyjnej: `_4`/`_5` → `…3` (gmina miejsko-wiejska), `_8`/`_9` → `XXXX011`, inne bez zmian.
  Parsujemy: sekcje „Kategoria gleby I–IV” × wiersze gatunków × 14 okresów (`<th title="RRRR-MM-DD - RRRR-MM-DD">`),
  symbole `+` susza, `-` brak, `x` nie dotyczy, `#` uprawa niewskazana, `*` kategoria nie występuje; sekcja „Udział
  powierzchni zagrożonej suszą [%]”. Cache 30 dni (rok bieżący 12 h).
- KBW działki (`science/smsr.py`): Σ(P − ET0) w 14 okresach sześciodekadowych, progi z `data/knowledge/crops/smsr_thresholds.yaml`
  (generowane `scripts/build_smsr_thresholds.py` z `raw/smsr_progi_www.txt`, rozp. MRiRW 11.04.2019). Okres oceniany tylko,
  gdy kończy się ≤ as_of.
- EDO WMS `https://drought.emergency.copernicus.eu/api/wms` (warstwy `cdiad` – CDI v4.1, `smang` – anomalia wilgotności
  gleby; `TIME` co 10 dni: 1/11/21). **GetFeatureInfo nieobsługiwane** → GetMap 5×5 px w EPSG:4326, kolor środkowego
  piksela z palety: CDI (240,228,66) Watch, (230,159,0) Warning, (220,5,12) Alert, przezroczysty = brak suszy;
  SMA wg legendy (≤ −2 … ≥ 2).
- Licencje: SMSR – informacja publiczna IUNG-PIB; EDO – Copernicus EMS, z przypisaniem.

## hydrology – ISOK MZP, BDOT10k, PIG-PIB
- ISOK `https://wody.isok.gov.pl/wss/INSPIRE/INSPIRE_NZ_HY_MZPMRP_WMS`, warstwa `NZ.Fluvial` (atrybut `loo_ql_returnperiod`
  10/100/500). Styl domyślny = same obrysy, a GetFeatureInfo trwa 3–10 s (poligony po 200 tys. wierzchołków) →
  **GetMap z `SLD_BODY`** (wypełnienie: 500 niebieski, 100 zielony, 10 czerwony, rysowane w tej kolejności) w bbox działki,
  `FORMAT_OPTIONS=antialias:none`, piksele w granicach działki → scenariusz i udział (~0,4 s). Warstwa nie renderuje się
  przy bardzo małej skali (bbox > ~15 km).
- BDOT10k (kopia PIG-PIB) ArcGIS REST `https://cbdgmapa.pgi.gov.pl/arcgis/rest/services/mapa_topo/bdot_10k/MapServer/{30..34}/query`
  (30 woda powierzchniowa PTWP, 31 kanał, 32 rów melioracyjny, 33 ciek, 34 ciek okresowy) – envelope 1 km, `outSR=2180`,
  `maxAllowableOffset=2`; ~0,2 s. Nazw brak. MPHP i wszystkie usługi `wody.isok.gov.pl/gpservices` oraz
  `wss/INSPIRE/INSPIRE_AM*|HY*` → 401.
- PIG-PIB `…/hydrogeologia/cbdh_otwory/MapServer/0/query` (otwory: głębokość, rok, typ, przeznaczenie – bez zwierciadła
  i wydajności), `gzwp/identify`, `jcwpd/identify` (warstwa 2 = cykl 2022–2027: kod UE, region wodny, dorzecze),
  `podtopienia/identify`. MHP (`/arcgis/rest/services/mhp`) → „Token Required”.
- Zarząd: region wodny (JCWPd) → RZGW (tabela w kodzie, DO_WERYFIKACJI); Zarząd Zlewni/Nadzór Wodny – brak publicznej usługi.

## protected_areas – GDOŚ WFS
- `https://sdi.gdos.gov.pl/wfs` (GeoServer, WFS 1.1.0, `OUTPUTFORMAT=application/json`, `PROPERTYNAME=nazwa[,kod]` – bez
  geometrii). 10 warstw: ObszarySpecjalnejOchrony, SpecjalneObszaryOchrony, ParkiNarodowe, Rezerwaty, ParkiKrajobrazowe,
  ObszaryChronionegoKrajobrazu, ZespolyPrzyrodniczoKrajobrazowe, UzytkiEkologiczne, PomnikiPrzyrodyPowierzchniowe, ramsar.
- `CQL_FILTER=INTERSECTS(geom,POLYGON(...))` i `DWITHIN(geom,POLYGON(...),1000,meters)`. **Pułapka: współrzędne EPSG:2180
  w CQL w kolejności (N E)**; WFS 2.0 z wieloma typami naraz → 502. ~0,3 s.

## vegetation – Sentinel-2 L2A przez Microsoft Planetary Computer
- Earth Search STAC działa, ale odczyt COG z `sentinel-cogs.s3.us-west-2` na łączu hackathonu ~21 KB/s (kafel 1,5 MB = 70 s);
  dodatkowo rasterio 1.5.2 / GDAL 3.12.2 nie dekoduje kafli tych COG (`TIFFReadEncodedTile() failed`; 1.4.3 działa).
- Używamy PC: STAC `https://planetarycomputer.microsoft.com/api/stac/v1/search` + Data API
  `POST /api/data/v1/item/statistics?collection=sentinel-2-l2a&item=…&asset_as_band=true&expression=…` z GeoJSON działki →
  statystyki liczone na serwerze (~0,5 s/scenę, bez klucza). Wyrażenia: `((SCL==4)|(SCL==5))*1.0;…*(B08-B04)/(B08+B04-2000)`
  (offset BOA 1000 dla baseline ≥ 04.00, `s2:processing_baseline`); NDVI = Σ/Σclear.
- Seria: ≤ 1 scena/miesiąc IV–X (min. zachmurzenie wg STAC, potem ≥ 70% czystych pikseli), latest ≥ 60% czystych w 60 dniach.
  Cache sceny 365 dni; budżet serii 10 s, reszta dokańcza się w tle. ~5–6 s z pustym cache.

## land_cover – ESA WorldCover + BDOT10k
- PC Data API `item/statistics?collection=esa-worldcover&assets=map&categorical=true` (item v200 2021 z STAC) → histogram klas
  (10 drzewa, 20 zarośla, 30 trawy, 40 grunty orne, 50 zabudowa, 60 bez roślinności, 80 wody, 90 mokradła…).
- BDOT10k (PIG) warstwy 28–30, 44–53: przecięcie poligonów z działką; kopia niekompletna (np. brak warstwy 49 dla
  pow. średzkiego) → używamy tylko gdy pokrywa ≥ 80% działki.

## yields – GUS BDL (usunięte z aplikacji 22.11.2026)
> GUS BDL ma plony tylko dla województw i Polski, nie dla działki – blok usunięty; notatka zostaje jako materiał na przyszłość.

- `https://bdl.stat.gov.pl/api/v1/data/by-variable/{id}?unit-level=2|0&year=…` – plony z 1 ha „ogółem” (dt/ha):
  4332 pszenica, 4338 żyto, 4344 jęczmień, 4350 owies, 4356 pszenżyto, 4314 zboża ogółem, 4368 ziemniaki, 4374 buraki cukrowe,
  4380 rzepak i rzepik, 4386 łąki trwałe, 47752 kukurydza na ziarno, 47749 kukurydza na zielonkę, 47769 soja,
  47740 strączkowe. **Tylko województwa (level 2) i Polska** – powiatów w BDL brak. Bez klucza (limit zapytań).
- Proxy działki: szczytowe NDVI IV–IX / mediana lat (z bloku `vegetation`).
