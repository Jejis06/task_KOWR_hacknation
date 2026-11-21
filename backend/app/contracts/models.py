"""KONTRAKT DANYCH – wspólny dla backendu (zespół DATA) i frontendu (zespół PRODUCT).

ZASADY ZMIAN (patrz AGENTS.md §6):
- tylko zmiany ADDYTYWNE (nowe pola opcjonalne / nowe modele), bez zmiany nazw i typów istniejących pól;
- każda zmiana → aktualizacja `frontend/src/api/types.ts` + wpis w AGENTS.md „Dziennik zmian kontraktu”.

Każdy blok danych to `DataBlock` z jawnym statusem, pochodzeniem (provenance) i niepewnością,
bo KOWR wymaga: „Brak danych jest komunikowany wprost, bez pozornej precyzji” oraz podania dat i źródeł.
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ───────────────────────────── wspólne ─────────────────────────────
class BlockStatus(str, Enum):
    ok = "ok"                          # dane kompletne
    partial = "partial"                # część danych (np. brak ostatnich dni, chmury)
    no_data = "no_data"                # źródło odpowiedziało, ale nie ma danych dla tej lokalizacji/daty
    not_applicable = "not_applicable"  # nie dotyczy (np. NDVI poza sezonem wegetacji)
    error = "error"                    # błąd / timeout źródła
    not_implemented = "not_implemented"


class Provenance(BaseModel):
    source_name: str                   # np. "GUGiK ULDK"
    source_url: str | None = None
    licence: str | None = None         # np. "CC BY 4.0", "dane publiczne PZGiK – bezpłatnie"
    retrieved_at: datetime             # kiedy pobrano (UTC)
    mode: Literal["live", "cached", "local_snapshot"] = "live"
    snapshot_date: date | None = None  # dla local_snapshot: data pobrania pliku
    data_as_of: date | None = None     # najnowsza data, której dotyczą dane (np. ostatni dzień opadu)
    notes: str | None = None
    # ── dodane 2026-11-21 (koordynator, addytywnie) ──
    # source_url = strona źródła, która NA PEWNO się otwiera (opis zbioru / przeglądarka mapowa);
    # query_url = dokładne zapytanie, którym pobraliśmy dane dla tej działki (otwiera surowe dane), jeśli to prosty GET
    query_url: str | None = None


class DataBlock(BaseModel, Generic[T]):
    key: str                           # = Connector.key (np. "weather_history")
    title: str                         # nazwa dla rolnika, po polsku
    status: BlockStatus
    data: T | None = None
    provenance: list[Provenance] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)  # ograniczenia i niepewność – prostym językiem
    messages: list[str] = Field(default_factory=list)     # komunikaty techniczne / ostrzeżenia
    elapsed_ms: int | None = None


class GeoJSONGeometry(BaseModel):
    type: str
    coordinates: Any


# ───────────────────────────── działka ─────────────────────────────
class ParcelRef(BaseModel):
    id: str                            # pełny identyfikator działki, np. "146505_8.0116.5"
    teryt_unit: str | None = None      # jednostka ewidencyjna, np. "146505_8"
    region_code: str | None = None     # obręb, np. "0116"
    parcel_number: str | None = None   # numer działki, np. "5" lub "123/4"
    voivodeship: str | None = None
    county: str | None = None
    commune: str | None = None
    region_name: str | None = None     # nazwa obrębu
    geometry: GeoJSONGeometry          # EPSG:4326
    centroid: tuple[float, float]      # (lon, lat)
    bbox: tuple[float, float, float, float]  # (minlon, minlat, maxlon, maxlat)
    area_ha: float


class AnalysisContext(BaseModel):
    parcel: ParcelRef
    as_of: date                        # data analizy (jury: dziś lub dowolna data z ostatnich 10 lat)
    crop: str | None = None            # klucz z data/knowledge/crops/crops.yaml


# ───────────────────────── payloady bloków ─────────────────────────
class DailySeries(BaseModel):
    dates: list[date]
    precip_mm: list[float | None]
    tmax_c: list[float | None]
    tmin_c: list[float | None]
    et0_mm: list[float | None]         # ewapotranspiracja wskaźnikowa FAO-56


class MonthlyClimate(BaseModel):
    month: int                         # 1..12
    precip_mean_mm: float | None
    et0_mean_mm: float | None
    cwb_mean_mm: float | None          # klimatyczny bilans wodny P - ET0


class SeasonSummary(BaseModel):
    year: int
    precip_apr_sep_mm: float | None
    et0_apr_sep_mm: float | None
    cwb_apr_sep_mm: float | None
    longest_dry_spell_days: int | None  # najdłuższy ciąg dni z opadem < 1 mm w IV–IX
    min_cwb_60d_mm: float | None        # najniższy 60-dniowy KBW w sezonie (proxy metody SMSR)


class WeatherHistory(BaseModel):
    provider: str                      # "open-meteo-era5" | "nasa-power"
    grid_resolution_note: str
    start: date
    end: date
    daily: DailySeries
    monthly_climatology: list[MonthlyClimate]
    seasons: list[SeasonSummary]
    last_30d_precip_mm: float | None = None
    last_30d_precip_normal_mm: float | None = None
    cwb_60d_mm: float | None = None    # KBW z 60 dni do as_of
    cwb_60d_normal_mm: float | None = None
    # ── dodane 2026-11-21 (A, addytywnie) ──
    # walidacja opadu najbliższą stacją synoptyczną IMGW: {station, distance_km, season_bias_pct,
    # station_last_30d_precip_mm, mean_abs_season_diff_mm, seasons_apr_sep: [{year, reanalysis_mm, station_mm}]}
    station_check: dict | None = None
    # sezony IV–IX po dacie analizy (do dziś) – TYLKO do porównania w UI, analiza ich nie używa (koordynator, 2026-11-21)
    seasons_after_as_of: list[SeasonSummary] = Field(default_factory=list)
    # średni wiatr na 2 m i min. wilgotność w VI–VIII (10 lat) – do korekty Kc mid, FAO-56 równ. 62
    kc_climate: dict | None = None


class WeatherForecast(BaseModel):
    provider: str
    dates: list[date]
    precip_mm: list[float | None]
    et0_mm: list[float | None]
    tmax_c: list[float | None]
    tmin_c: list[float | None]


class DroughtIndex(BaseModel):
    source: str                        # "SMSR IUNG" | "EDO CDI" | "EDO SMA" | "computed"
    date: date | None
    value: float | str | None
    class_label: str | None = None     # np. "susza", "ostrzeżenie", "brak"
    level: Literal["commune", "pixel", "parcel"] | None = None


class DroughtHistory(BaseModel):
    current: list[DroughtIndex]
    history: list[DroughtIndex]        # historyczne epizody (10 lat)
    drought_years: list[int] = Field(default_factory=list)  # lata z suszą w sezonie
    # ── dodane 2026-11-21 (A, addytywnie) ──
    drought_years_smsr: list[int] = Field(default_factory=list)      # wg oficjalnych tabel SMSR dla gminy (2020+)
    drought_years_computed: list[int] = Field(default_factory=list)  # wg KBW policzonego dla działki (10 lat)
    crop_group: str | None = None          # grupa upraw SMSR, np. "zboża ozime"
    soil_category: int | None = None       # kategoria gleby SMSR 1–4 użyta do progów
    commune_teryt: str | None = None       # TERYT gminy (7 cyfr) użyty w SMSR
    commune_name: str | None = None
    periods: list[dict] = Field(default_factory=list)  # [{year, period 1–14, start, end, drought, source, kbw_mm?, threshold_mm?, commune_area_share_pct?}]


class SoilInfo(BaseModel):
    agri_complex: str | None = None    # kompleks przydatności rolniczej (IUNG)
    soil_type: str | None = None       # typ gleby
    texture_class: str | None = None   # uziarnienie / kategoria agronomiczna
    drought_susceptibility: str | None = None  # kategoria podatności na suszę (IUNG / SMSR 1–4)
    bonitation_classes: list[str] = Field(default_factory=list)  # klasy bonitacyjne z EGiB
    clay_pct: float | None = None
    sand_pct: float | None = None
    silt_pct: float | None = None
    soc_g_kg: float | None = None      # węgiel organiczny
    awc_mm: float | None = None        # zapas wody dostępnej (TAW) dla 1 m profilu – szacunek
    source_used: str | None = None
    # ── dodane 2026-11-21 (A, addytywnie) ──
    drought_category: int | None = None                 # kategoria podatności na suszę SMSR 1–4 (dominująca)
    drought_category_shares_pct: dict[str, float] = Field(default_factory=dict)  # "1".."4","organiczne",…
    agri_complex_code: str | None = None                # kod kompleksu, np. "4", "2z"
    agri_complex_shares_pct: dict[str, float] = Field(default_factory=dict)
    texture_profile: list[str] = Field(default_factory=list)  # gatunki gleby od wierzchu w głąb (np. pgm/gl)
    samples: list[dict] = Field(default_factory=list)    # wyniki z punktów próbkowania (lon, lat, kategoria…)


class TerrainInfo(BaseModel):
    elevation_mean_m: float | None = None
    elevation_min_m: float | None = None
    elevation_max_m: float | None = None
    slope_mean_deg: float | None = None
    slope_max_deg: float | None = None
    aspect_dominant: str | None = None          # N/NE/E/...
    position: Literal["hilltop", "upper_slope", "mid_slope", "flat", "valley", "depression"] | None = None
    position_label_pl: str | None = None        # „górka”, „stok”, „płasko”, „dolina”, „zagłębienie (dołek)”
    tpi_m: float | None = None                  # Topographic Position Index
    twi_mean: float | None = None               # Topographic Wetness Index
    depressions_geojson: dict | None = None     # zagłębienia bezodpływowe (FeatureCollection)
    flow_lines_geojson: dict | None = None      # główne linie spływu
    dem_resolution_m: float | None = None
    # ── 2026-11-21 (koordynator) ── odcinki granicy działki, przez które spływ (D8) wypływa z pola
    # FeatureCollection LineString (EPSG:4326), properties {catchment_ha, length_m}; zagłębienia mają też {catchment_ha}
    runoff_exits_geojson: dict | None = None


class WaterFeature(BaseModel):
    kind: Literal["river", "stream", "ditch", "lake", "pond", "reservoir", "spring", "other"]
    name: str | None = None
    distance_m: float
    geometry: GeoJSONGeometry | None = None


class HydrologyInfo(BaseModel):
    nearest_water: list[WaterFeature] = Field(default_factory=list)
    in_flood_zone: Literal["0.2%", "1%", "10%"] | None = None
    flood_zone_checked: bool = False
    catchment_name: str | None = None           # zlewnia / JCWP
    jcwp_code: str | None = None
    groundwater_depth_m: str | None = None      # głębokość do pierwszego poziomu wodonośnego (MHP)
    gzwp: str | None = None                     # Główny Zbiornik Wód Podziemnych
    nearest_boreholes: list[dict] = Field(default_factory=list)  # CBDH: głębokość, zwierciadło, wydajność
    water_management_board: str | None = None   # właściwy Zarząd Zlewni / Nadzór Wodny Wód Polskich
    # ── dodane 2026-11-21 (A, addytywnie) ──
    in_flood_hazard_area: bool | None = None    # jakakolwiek część działki w obszarze MZP (nawet gdy scenariusz nieznany)
    in_groundwater_flood_area: bool | None = None  # obszar zagrożony podtopieniami (PIG-PIB)
    jcwpd_code: str | None = None               # Jednolita Część Wód Podziemnych (kod UE)


class VegetationObs(BaseModel):
    date: date
    ndvi: float | None
    ndmi: float | None = None
    cloud_pct: float | None = None
    scene_id: str | None = None


class VegetationInfo(BaseModel):
    latest: VegetationObs | None = None
    latest_age_days: int | None = None
    series: list[VegetationObs] = Field(default_factory=list)   # 10 lat, przefiltrowane chmury
    baseline_same_doy: float | None = None      # typowe NDVI dla tego dnia roku (10 lat)
    anomaly: float | None = None                # latest - baseline
    in_growing_season: bool | None = None
    # ── 2026-11-21 (koordynator) ── NDMI (wilgotność liści, B08/B11) liczony w tej samej serii co NDVI
    ndmi_baseline_same_doy: float | None = None
    ndmi_anomaly: float | None = None


class YieldRecord(BaseModel):
    year: int
    crop: str
    yield_t_ha: float | None
    level: Literal["powiat", "voivodeship", "country", "parcel_proxy"]
    unit_name: str | None = None


class YieldInfo(BaseModel):
    official: list[YieldRecord] = Field(default_factory=list)      # GUS BDL (powiat/województwo)
    parcel_productivity_index: list[dict] = Field(default_factory=list)  # [{year, peak_ndvi, rel_index}]
    note: str | None = None


class LandCoverInfo(BaseModel):
    classes: dict[str, float] = Field(default_factory=dict)  # klasa -> udział % działki
    agricultural_share_pct: float | None = None
    source_used: str | None = None
    # ── dodane 2026-11-21 (A, addytywnie) ──
    cropland_share_pct: float | None = None   # tylko grunty orne (WorldCover klasa 40)
    bdot_classes: dict[str, float] = Field(default_factory=dict)  # BDOT10k: klasa -> udział % działki


class ProtectedAreaHit(BaseModel):
    kind: str                          # "Natura 2000 OSO", "Natura 2000 SOO", "rezerwat", "park narodowy", "OChK"...
    name: str | None = None
    code: str | None = None
    distance_m: float | None = None    # dodane 2026-11-21 (A): 0 = działka w obszarze; None = „w promieniu 1 km”


class ProtectedAreasInfo(BaseModel):
    hits: list[ProtectedAreaHit] = Field(default_factory=list)
    checked_layers: list[str] = Field(default_factory=list)
    nearby: list[ProtectedAreaHit] = Field(default_factory=list)  # dodane 2026-11-21 (A): w promieniu 1 km


class CropStage(BaseModel):
    name: str
    start: date
    end: date
    kc: float | None = None


class CropCalendarInfo(BaseModel):
    crop: str
    crop_name_pl: str
    in_season_on_as_of: bool
    current_stage: str | None = None
    stages: list[CropStage] = Field(default_factory=list)
    critical_water_periods: list[str] = Field(default_factory=list)
    sowing_ok_now: bool | None = None
    warnings: list[str] = Field(default_factory=list)   # np. „za późno na siew kukurydzy”
    suggested_crops_now: list[str] = Field(default_factory=list)


class LegalHint(BaseModel):
    topic: str                         # "staw", "studnia", "nawadnianie", "rów", ...
    requirement: str                   # "zgłoszenie wodnoprawne" | "pozwolenie wodnoprawne" | "brak" ...
    why: str                           # uzasadnienie z faktami o działce
    procedure_id: str | None = None    # → data/knowledge/procedures/*.yaml
    status: Literal["OK", "DO_WERYFIKACJI", "SZACUNEK"] = "OK"
    sources: list[str] = Field(default_factory=list)
    # ↓ addytywnie 2026-11-21 (B): grupowanie kart w UI i fakty o działce
    title: str | None = None           # nazwa dla rolnika, np. „Staw lub zbiornik do 5000 m²”
    group: Literal["none", "notification", "permit", "depends"] | None = None  # bez formalności / zgłoszenie / pozwolenie / zależy
    legal_ids: list[str] = Field(default_factory=list)   # → data/knowledge/legal_pl/prawo_wodne.yaml
    fee_pln: float | None = None       # opłata administracyjna dla roku daty analizy
    fee_year: int | None = None
    facts_used: list[str] = Field(default_factory=list)  # fakty o działce wykorzystane w regule
    unchecked: list[str] = Field(default_factory=list)   # czego nie udało się sprawdzić (blok bez danych)
    caution: str | None = None         # ostrzeżenie (np. strefa powodziowa, Natura 2000)


class LegalContextInfo(BaseModel):
    hints: list[LegalHint] = Field(default_factory=list)
    funding_ids: list[str] = Field(default_factory=list)  # → data/knowledge/funding/programs.yaml
    # ↓ addytywnie 2026-11-21 (B)
    disclaimer: str | None = None
    facts_checked: dict[str, str] = Field(default_factory=dict)  # blok → status (ok / brak danych / niezaimplementowany)



# ─────────────── wyniki analizy (F2) – blok `analysis` ───────────────
# Dodane 2026-11-21 (B, addytywnie) jako PROPOZYCJA dla A: kształt, który renderuje widok raportu.
# Kolejność KOWR: ocena sytuacji wodnej → przyczyny → retencja → agrotechnika → (opcjonalnie) nawadnianie.
# Każde stwierdzenie ma `evidence` = konkretne liczby z bloków danych (z jednostką i datą) – bez tego UI go nie pokaże.
RiskLevel = Literal["none", "low", "moderate", "high", "very_high"]


class Evidence(BaseModel):
    text: str                          # „KBW 60 dni: −112 mm (norma −25 mm) do 20.11.2026”
    block: str | None = None           # klucz bloku źródłowego, np. "weather_history"


class WaterAssessment(BaseModel):
    current_level: RiskLevel | None = None      # bieżący niedobór wody na dzień analizy
    current_label_pl: str | None = None         # „wysoki niedobór wody”
    current_summary: str | None = None          # 1–2 zdania dla rolnika
    historical_level: RiskLevel | None = None   # wieloletnia podatność działki na niedobory (10 lat)
    historical_label_pl: str | None = None
    historical_summary: str | None = None
    drought_years: list[int] = Field(default_factory=list)
    critical_months: list[int] = Field(default_factory=list)   # 1..12 – kiedy ryzyko największe
    confidence: Literal["low", "medium", "high"] | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    # KBW (pogoda, ~10 km) × NDMI (pomiar z pola, 20 m): {kbw: dry|normal, ndmi: low|normal, case, label_pl, text}
    field_check: dict | None = None


class Cause(BaseModel):
    key: str                           # cause_keys z retention_measures.yaml: opady_deficyt | gleba_niska_retencja | odplyw_powierzchniowy | uprawa_wrazliwa
    label_pl: str
    share: float | None = None         # udział 0..1 (szacunek)
    explanation: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)


class Recommendation(BaseModel):
    measure_id: str                    # → data/knowledge/procedures/retention_measures.yaml
    group: Literal["retencja_krajobrazowa", "agrotechnika", "nawadnianie"]
    title: str
    why: str                           # uzasadnienie z danych tej działki
    priority: int = 1                  # 1 = najpierw
    addresses: list[str] = Field(default_factory=list)   # klucze przyczyn
    when: str | None = None            # termin wykonania, np. „VII–VIII po zbiorze”
    where_geojson: dict | None = None  # gdzie na działce (np. zagłębienie) – EPSG:4326
    legal_ids: list[str] = Field(default_factory=list)   # → legal_pl; UI dobiera kartę z legal_context
    funding_ids: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


class IrrigationAdvice(BaseModel):
    recommended: Literal["no", "monitor", "yes"] | None = None
    summary: str | None = None
    deficit_mm: float | None = None    # ETc − opad efektywny w horyzoncie prognozy
    dose_mm: float | None = None
    horizon_days: int | None = None
    timing: str | None = None          # „w ciągu 3 dni, rano lub wieczorem”
    evidence: list[Evidence] = Field(default_factory=list)
    # ── 2026-11-21 (koordynator) ── dobowy bilans wody w strefie korzeni FAO-56 (rozdz. 8, równ. 80–90)
    depletion_mm: float | None = None  # Dr na dzień analizy
    taw_mm: float | None = None        # całkowita woda dostępna w strefie korzeni (równ. 82)
    raw_mm: float | None = None        # woda łatwo dostępna = p·TAW (równ. 83)
    ks: float | None = None            # współczynnik stresu wodnego (równ. 84)
    days_to_stress: int | None = None  # za ile dni Dr przekroczy RAW (z prognozy)
    stress_date: str | None = None
    season_et_ratio: float | None = None   # ETc adj / ETc od początku sezonu
    yield_loss_pct: float | None = None    # 1 − Ya/Ym = Ky (1 − ETa/ETc) (równ. 90, Ky z tab. 24)
    soil_water: list[dict] = Field(default_factory=list)  # [{date, dr_mm, raw_mm, taw_mm, forecast}] do wykresu


class AnalysisResult(BaseModel):
    assessment: WaterAssessment | None = None
    causes: list[Cause] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    irrigation: IrrigationAdvice | None = None
    limitations: list[str] = Field(default_factory=list)   # czynniki nieuwzględnione, dokładność danych
    method: list[str] = Field(default_factory=list)        # krótki opis metody (FAO-56, progi SMSR…)
    missing_blocks: list[str] = Field(default_factory=list)  # bloki bez danych, pominięte w analizie
    # bilans ilościowy działki: deficyt [mm → m³] vs pojemność i zlewnia zagłębienia (koordynator, 2026-11-21)
    water_balance: dict | None = None

# ───────────────────────────── odpowiedzi API ─────────────────────────────
class ParcelProfile(BaseModel):
    context: AnalysisContext
    blocks: dict[str, DataBlock[Any]]
    generated_at: datetime
    total_elapsed_ms: int


class BlockInfo(BaseModel):
    key: str
    title: str
    category: Literal["meteo", "satellite", "soil", "hydro", "spatial", "knowledge", "derived"]
    implemented: bool
