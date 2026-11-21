// Dane przykładowe zgodne z kontraktem – UI działa bez backendu (VITE_USE_MOCKS=true).
// WSZYSTKIE wartości są syntetyczne i oznaczone „MOCK” w provenance. Gdy blok A przejdzie na ✅,
// A podmienia tu mock prawdziwą (skróconą) próbką.
import type {
  AnalysisResult, BlockInfo, CropCalendarInfo, CropItem, DataBlock, DroughtHistory, HydrologyInfo, LandCoverInfo,
  LegalContextInfo, MonthlyClimate, ParcelRef, ProtectedAreasInfo, SeasonSummary, SoilInfo, TerrainInfo,
  VegetationInfo, WeatherForecast, WeatherHistory, YieldInfo,
} from "../api/types";
import type { Knowledge } from "../api/knowledge";

export const mockParcel: ParcelRef = {
  id: "302504_5.0024.7",
  teryt_unit: "302504_5",
  region_code: "0024",
  parcel_number: "7",
  voivodeship: "wielkopolskie",
  county: "powiat średzki",
  commune: "Środa Wielkopolska",
  region_name: "Słupia Wielka",
  geometry: {
    type: "Polygon",
    coordinates: [[[17.1955, 52.2185], [17.2045, 52.2188], [17.2042, 52.2222], [17.1958, 52.2219], [17.1955, 52.2185]]],
  },
  centroid: [17.19985, 52.22044],
  bbox: [17.1955, 52.2185, 17.2045, 52.2222],
  area_ha: 14.47,
};

export const mockBlocks: BlockInfo[] = [
  { key: "weather_history", title: "Opady i parowanie – 10 lat", category: "meteo", implemented: true },
  { key: "weather_forecast", title: "Prognoza pogody (16 dni)", category: "meteo", implemented: true },
  { key: "drought", title: "Susza – teraz i w historii", category: "meteo", implemented: false },
  { key: "soil", title: "Gleba", category: "soil", implemented: false },
  { key: "terrain", title: "Ukształtowanie terenu", category: "spatial", implemented: false },
  { key: "hydrology", title: "Wody powierzchniowe i podziemne", category: "hydro", implemented: false },
  { key: "vegetation", title: "Stan roślinności (satelita)", category: "satellite", implemented: false },
  { key: "land_cover", title: "Użytkowanie terenu", category: "spatial", implemented: false },
  { key: "yields", title: "Plony historyczne", category: "derived", implemented: false },
  { key: "protected_areas", title: "Obszary chronione", category: "spatial", implemented: false },
  { key: "crop_calendar", title: "Kalendarz uprawy i okres wegetacji", category: "knowledge", implemented: true },
  { key: "legal_context", title: "Pozwolenia, procedury i dofinansowania", category: "knowledge", implemented: true },
  { key: "analysis", title: "Ocena sytuacji wodnej i rekomendacje", category: "derived", implemented: true },
];

export const mockCrops: CropItem[] = [
  { id: "pszenica_ozima", name_pl: "Pszenica ozima", type: "ozima", sowing: "09-15..10-20", harvest: "07-20..08-20" },
  { id: "kukurydza_ziarno", name_pl: "Kukurydza na ziarno", type: "jara", sowing: "04-20..05-15", harvest: "09-25..11-15" },
  { id: "ziemniak", name_pl: "Ziemniak", type: "jara", sowing: "04-05..05-10", harvest: "08-15..10-10" },
  { id: "tuz", name_pl: "Łąki i pastwiska (TUZ)", type: "wieloletnia", sowing: null, harvest: "pokosy V–IX" },
];

// ── generator pogody (deterministyczny) ──
function rng(seed: number) {
  let s = seed;
  return () => ((s = (s * 1664525 + 1013904223) % 4294967296) / 4294967296);
}
const iso = (d: Date) => d.toISOString().slice(0, 10);

function weather(asOf: string): WeatherHistory {
  const r = rng(42);
  const end = new Date(`${asOf}T12:00:00Z`);
  const start = new Date(end);
  start.setUTCFullYear(end.getUTCFullYear() - 10);
  const dates: string[] = [], p: number[] = [], tx: number[] = [], tn: number[] = [], e: number[] = [];
  for (let d = new Date(start); d <= end; d.setUTCDate(d.getUTCDate() + 1)) {
    const doy = (d.getTime() - Date.UTC(d.getUTCFullYear(), 0, 0)) / 864e5;
    const season = Math.sin(((doy - 100) / 365) * 2 * Math.PI);
    const dry = d.getUTCFullYear() % 3 === 0 ? 0.6 : 1; // co trzeci rok suchszy
    dates.push(iso(d));
    p.push(r() < 0.42 ? Math.round(r() * r() * 14 * dry * (1 + 0.4 * season) * 10) / 10 : 0);
    tx.push(Math.round((13 + 12 * season + r() * 4) * 10) / 10);
    tn.push(Math.round((4 + 9 * season + r() * 3) * 10) / 10);
    e.push(Math.max(0.2, Math.round((2 + 2.2 * season + r() * 0.6) * 10) / 10));
  }
  const monthly: MonthlyClimate[] = Array.from({ length: 12 }, (_, m) => {
    const idx = dates.map((d, i) => [d, i] as const).filter(([d]) => Number(d.slice(5, 7)) === m + 1).map(([, i]) => i);
    const years = new Set(idx.map((i) => dates[i].slice(0, 4))).size || 1;
    const ps = idx.reduce((a, i) => a + p[i], 0) / years;
    const es = idx.reduce((a, i) => a + e[i], 0) / years;
    return { month: m + 1, precip_mean_mm: Math.round(ps), et0_mean_mm: Math.round(es), cwb_mean_mm: Math.round(ps - es) };
  });
  const seasons: SeasonSummary[] = [];
  for (let y = start.getUTCFullYear(); y <= end.getUTCFullYear(); y++) {
    const idx = dates.map((d, i) => [d, i] as const).filter(([d]) => d.startsWith(String(y)) && +d.slice(5, 7) >= 4 && +d.slice(5, 7) <= 9).map(([, i]) => i);
    if (idx.length < 150) continue;
    const ps = idx.reduce((a, i) => a + p[i], 0), es = idx.reduce((a, i) => a + e[i], 0);
    let run = 0, best = 0;
    idx.forEach((i) => { run = p[i] < 1 ? run + 1 : 0; best = Math.max(best, run); });
    seasons.push({ year: y, precip_apr_sep_mm: Math.round(ps), et0_apr_sep_mm: Math.round(es), cwb_apr_sep_mm: Math.round(ps - es),
      longest_dry_spell_days: best, min_cwb_60d_mm: Math.round((ps - es) / 2.2) });
  }
  const last = (n: number, arr: number[]) => arr.slice(-n).reduce((a, b) => a + b, 0);
  return {
    provider: "MOCK (dane syntetyczne)", grid_resolution_note: "MOCK – siatka ok. 9 km (ERA5-Land)", start: iso(start), end: asOf,
    daily: { dates, precip_mm: p, tmax_c: tx, tmin_c: tn, et0_mm: e },
    monthly_climatology: monthly, seasons,
    last_30d_precip_mm: Math.round(last(30, p)), last_30d_precip_normal_mm: 38,
    cwb_60d_mm: Math.round(last(60, p) - last(60, e)), cwb_60d_normal_mm: -25,
  };
}

const now = () => new Date().toISOString();
const MOCK_PROV = (name: string, dataAsOf?: string) => [{
  source_name: `MOCK – ${name}`, retrieved_at: now(), mode: "local_snapshot" as const, snapshot_date: "2026-11-21",
  data_as_of: dataAsOf ?? null, licence: "dane syntetyczne do testów UI",
}];

function forecast(asOf: string): WeatherForecast {
  const r = rng(7);
  const dates = Array.from({ length: 16 }, (_, i) => { const d = new Date(`${asOf}T12:00:00Z`); d.setUTCDate(d.getUTCDate() + i); return iso(d); });
  return { provider: "MOCK", dates, precip_mm: dates.map(() => (r() < 0.4 ? Math.round(r() * 9 * 10) / 10 : 0)),
    et0_mm: dates.map(() => Math.round((0.6 + r()) * 10) / 10), tmax_c: dates.map(() => Math.round(6 + r() * 6)), tmin_c: dates.map(() => Math.round(-1 + r() * 4)) };
}

const PAYLOADS: Record<string, (asOf: string) => unknown> = {
  weather_history: weather,
  weather_forecast: forecast,
  drought: (): DroughtHistory => ({
    current: [{ source: "SMSR IUNG", date: "2026-09-30", value: -112, class_label: "zagrożenie suszą (kukurydza, kat. II)", level: "commune" },
              { source: "EDO CDI", date: "2026-11-11", value: "ostrzeżenie", class_label: "ostrzeżenie", level: "pixel" }],
    history: [{ source: "SMSR IUNG", date: "2019-07-31", value: "susza", class_label: "susza", level: "commune" },
              { source: "SMSR IUNG", date: "2023-06-30", value: "susza", class_label: "susza", level: "commune" }],
    drought_years: [2018, 2019, 2022, 2023, 2026],
  }),
  soil: (): SoilInfo => ({ agri_complex: "2 – pszenny dobry", soil_type: "gleby płowe", texture_class: "glina lekka (gleba średnia)",
    drought_susceptibility: "III", bonitation_classes: ["RII", "RIIIa", "RIVa"], clay_pct: 14, sand_pct: 58, silt_pct: 28,
    soc_g_kg: 11, awc_mm: 165, source_used: "MOCK mapa glebowo-rolnicza" }),
  terrain: (): TerrainInfo => ({ elevation_mean_m: 98.4, elevation_min_m: 95.1, elevation_max_m: 102.7, slope_mean_deg: 1.4,
    slope_max_deg: 4.8, aspect_dominant: "SW", position: "flat", position_label_pl: "płasko", tpi_m: -0.6, twi_mean: 7.9,
    dem_resolution_m: 1,
    depressions_geojson: { type: "FeatureCollection", features: [{ type: "Feature", properties: { area_m2: 2400, depth_m: 0.6 },
      geometry: { type: "Polygon", coordinates: [[[17.2010, 52.2192], [17.2030, 52.2193], [17.2029, 52.2203], [17.2011, 52.2202], [17.2010, 52.2192]]] } }] },
    flow_lines_geojson: { type: "FeatureCollection", features: [{ type: "Feature", properties: {},
      geometry: { type: "LineString", coordinates: [[17.1965, 52.2215], [17.1990, 52.2205], [17.2020, 52.2198], [17.2050, 52.2190]] } }] } }),
  hydrology: (): HydrologyInfo => ({
    nearest_water: [{ kind: "ditch", name: "rów melioracyjny R-7", distance_m: 140 }, { kind: "stream", name: "Moskawa", distance_m: 2300 },
      { kind: "lake", name: "Jezioro Raczyńskie", distance_m: 6200 }],
    in_flood_zone: null, flood_zone_checked: true, catchment_name: "Moskawa", jcwp_code: "RW60001718589",
    groundwater_depth_m: "2–5 m", gzwp: null, nearest_boreholes: [{ depth_m: 42, water_table_m: 6.5, yield_m3_h: 18, distance_m: 1800 }],
    water_management_board: "Nadzór Wodny w Środzie Wlkp. (ZZ Poznań)" }),
  vegetation: (asOf: string): VegetationInfo => {
    const r = rng(3);
    const series = Array.from({ length: 48 }, (_, i) => { const d = new Date(`${asOf}T12:00:00Z`); d.setUTCDate(d.getUTCDate() - (47 - i) * 15);
      const doy = (d.getTime() - Date.UTC(d.getUTCFullYear(), 0, 0)) / 864e5;
      return { date: iso(d), ndvi: Math.round((0.35 + 0.4 * Math.max(0, Math.sin(((doy - 80) / 365) * 2 * Math.PI)) + r() * 0.05) * 100) / 100, cloud_pct: Math.round(r() * 20) }; });
    return { latest: series[series.length - 1], latest_age_days: 6, series, baseline_same_doy: 0.41, anomaly: -0.04, in_growing_season: false };
  },
  land_cover: (): LandCoverInfo => ({ classes: { "grunty orne": 92.5, "trawy/łąki": 4.1, "drzewa": 3.4 }, agricultural_share_pct: 96.6, source_used: "MOCK ESA WorldCover 2021" }),
  yields: (): YieldInfo => ({ official: [2019, 2020, 2021, 2022, 2023, 2024, 2025].map((y, i) => ({ year: y, crop: "kukurydza na ziarno",
    yield_t_ha: [7.1, 8.4, 8.9, 6.2, 7.0, 7.8, 8.1][i], level: "powiat" as const, unit_name: "powiat średzki" })),
    parcel_productivity_index: [], note: "Plony GUS to średnia dla powiatu – nie dla Twojego pola." }),
  protected_areas: (): ProtectedAreasInfo => ({ hits: [], checked_layers: ["Natura 2000 OSO", "Natura 2000 SOO", "rezerwaty", "parki narodowe", "parki krajobrazowe", "OChK"] }),
  crop_calendar: (asOf: string): CropCalendarInfo => ({ crop: "kukurydza_ziarno", crop_name_pl: "Kukurydza na ziarno", in_season_on_as_of: false,
    current_stage: "przed siewem", sowing_ok_now: false, critical_water_periods: ["wiechowanie i kwitnienie (VII) – najbardziej krytyczne", "nalewanie ziarna (VIII)"],
    stages: [{ name: "siew i wschody", start: "2027-04-20", end: "2027-04-30", kc: null }, { name: "faza początkowa", start: "2027-05-01", end: "2027-05-30", kc: 0.3 },
      { name: "rozwój roślin", start: "2027-05-31", end: "2027-07-09", kc: 0.75 }, { name: "pełnia wzrostu", start: "2027-07-10", end: "2027-08-28", kc: 1.2 },
      { name: "dojrzewanie", start: "2027-08-29", end: "2027-09-27", kc: 0.35 }, { name: "zbiór", start: "2027-09-25", end: "2027-11-15", kc: null }],
    warnings: [`MOCK (${asOf}): siew w tym roku już niemożliwy (Kukurydza na ziarno: termin 20.04–15.05, przy glebie ≥8 °C, wegetacja 130–160 dni).`],
    suggested_crops_now: [] }),
  legal_context: (asOf: string): LegalContextInfo => ({
    disclaimer: "Informacja orientacyjna, nie porada prawna.", funding_ids: ["fgr_plus", "arimr_i1011", "arimr_i104"],
    facts_checked: { "wody i strefy powodziowe": "sprawdzono", "obszary chronione": "sprawdzono", "ukształtowanie terenu": "sprawdzono" },
    hints: [
      { topic: "staw", title: "Staw lub zbiornik retencyjny (do 5000 m², do 3 m)", requirement: "zgłoszenie wodnoprawne", group: "notification",
        why: "MOCK: staw do 5000 m² i 3 m, zasilany opadami – zgłoszenie wodnoprawne (30 dni na sprzeciw).", procedure_id: "zgloszenie_wodnoprawne", legal_ids: ["staw_zgloszenie", "staw_pozwolenie", "ograniczenia_lokalizacji"],
        status: "OK", sources: ["https://www.gov.pl/wody-polskie/zgloszenie-wodnoprawne"], fee_pln: Number(asOf.slice(0, 4)) >= 2027 ? 137.09 : 132.33,
        fee_year: Number(asOf.slice(0, 4)) >= 2027 ? 2027 : 2026, facts_used: ["poza mapowanymi strefami zagrożenia powodziowego (ISOK)"], unchecked: [] },
      { topic: "rów", title: "Zastawka – zatrzymanie wody w istniejącym rowie", requirement: "brak (zatrzymanie wody)", group: "none",
        why: "MOCK: zatrzymanie wody w istniejącym rowie – bez zgłoszenia.", legal_ids: ["row_zatrzymanie", "row_przebudowa"], status: "OK", sources: [], facts_used: ["najbliższy rów: R-7, ok. 140 m od działki"] },
      { topic: "nawadnianie", title: "Nawadnianie upraw wodą ze studni", requirement: "pozwolenie wodnoprawne", group: "permit",
        why: "MOCK: nawadnianie to szczególne korzystanie z wód.", procedure_id: "pozwolenie_wodnoprawne", legal_ids: ["nawadnianie_pozwolenie"], status: "OK", sources: [], fee_pln: 330.07, fee_year: 2026 },
      { topic: "istniejący zbiornik", title: "Pobór wody z istniejącego stawu, zbiornika lub rowu", requirement: "zależy od ilości wody i celu",
        group: "depends", why: "MOCK: do 5 m³/d – zwykłe korzystanie; nawadnianie – pozwolenie.", status: "DO_WERYFIKACJI", sources: [] },
    ] }),
  analysis: (asOf: string): AnalysisResult => ({
    assessment: {
      current_level: "moderate", current_label_pl: "umiarkowany niedobór wody",
      current_summary: `MOCK: na ${asOf} w glebie jest mniej wody niż zwykle o tej porze – ostatnie 60 dni były suchsze od normy, ale trwa spoczynek zimowy, więc rośliny nie cierpią teraz z powodu suszy.`,
      historical_level: "high", historical_label_pl: "wysoka podatność na suszę",
      historical_summary: "MOCK: w ostatnich 10 latach susza rolnicza wystąpiła tu w 5 sezonach; największe ryzyko niedoboru wody jest od maja do lipca.",
      drought_years: [2018, 2019, 2022, 2023, 2026], critical_months: [5, 6, 7], confidence: "medium",
      evidence: [
        { text: "KBW 60 dni: −44 mm (norma −25 mm)", block: "weather_history" },
        { text: "susza w 5 z 11 sezonów (SMSR gmina + KBW działki)", block: "drought" },
        { text: "najsuchszy sezon IV–IX: 2022, KBW −521 mm", block: "weather_history" },
        { text: "gleba kat. III (średnio podatna), zapas wody ok. 165 mm", block: "soil" },
      ],
    },
    causes: [
      { key: "opady_deficyt", label_pl: "Za mało opadów przy dużym parowaniu", share: 0.55,
        explanation: "W sezonie wegetacyjnym parowanie wyraźnie przewyższa opady (Wielkopolska – jeden z najsuchszych regionów).",
        evidence: [{ text: "średni KBW IV–IX z 10 lat: −380 mm", block: "weather_history" }, { text: "najdłuższy okres bez deszczu w 2022: 17 dni", block: "weather_history" }] },
      { key: "gleba_niska_retencja", label_pl: "Gleba trzyma średnio dużo wody", share: 0.25,
        explanation: "Glina lekka z niską zawartością próchnicy – zapas wody wystarcza na ok. 2–3 tygodnie bez deszczu w lipcu.",
        evidence: [{ text: "węgiel organiczny 11 g/kg", block: "soil" }, { text: "zapas wody dostępnej ok. 165 mm/1 m", block: "soil" }] },
      { key: "odplyw_powierzchniowy", label_pl: "Woda szybko odpływa rowem", share: 0.2,
        explanation: "Linia spływu przecina działkę i kończy się w rowie melioracyjnym – woda z roztopów i ulew odpływa poza gospodarstwo.",
        evidence: [{ text: "linia spływu przez działkę, rów R-7 w odległości 140 m", block: "hydrology" }, { text: "1 zagłębienie bezodpływowe ok. 2400 m²", block: "terrain" }] },
    ],
    recommendations: [
      { measure_id: "zastawka_row", group: "retencja_krajobrazowa", priority: 1, title: "Zastawka na rowie R-7",
        why: "Rów melioracyjny 140 m od działki odprowadza wodę z roztopów. Piętrzenie wiosną zatrzyma wodę w okolicy i podniesie poziom wód gruntowych.",
        addresses: ["odplyw_powierzchniowy", "opady_deficyt"], when: "przed roztopami (II–III)", legal_ids: ["row_zatrzymanie", "row_przebudowa"], funding_ids: [],
        evidence: [{ text: "rów R-7: 140 m", block: "hydrology" }] },
      { measure_id: "oczko_zbiornik", group: "retencja_krajobrazowa", priority: 2, title: "Oczko wodne w zagłębieniu terenu",
        why: "W południowo-wschodniej części działki jest naturalne zagłębienie (ok. 2400 m², 0,6 m), w którym zbiera się woda – mało kopania, poza strefą powodziową.",
        addresses: ["odplyw_powierzchniowy"], when: "poza sezonem (X–III), po zgłoszeniu wodnoprawnym", legal_ids: ["staw_zgloszenie", "ograniczenia_lokalizacji"], funding_ids: ["arimr_i104"],
        where_geojson: { type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [[[17.2010, 52.2192], [17.2030, 52.2193], [17.2029, 52.2203], [17.2011, 52.2202], [17.2010, 52.2192]]] } },
        evidence: [{ text: "zagłębienie 2400 m², głębokość 0,6 m", block: "terrain" }, { text: "poza strefą zagrożenia powodziowego", block: "hydrology" }] },
      { measure_id: "miedzyplony", group: "agrotechnika", priority: 1, title: "Międzyplon po zbiorze",
        why: "Okrywa gleby po żniwach ogranicza parowanie i zwiększa próchnicę – przy 11 g/kg węgla organicznego każdy wzrost poprawia zapas wody.",
        addresses: ["gleba_niska_retencja"], when: "VII–VIII, zaraz po zbiorze", legal_ids: [], funding_ids: [], evidence: [{ text: "węgiel organiczny 11 g/kg", block: "soil" }] },
      { measure_id: "resztki_mulcz", group: "agrotechnika", priority: 2, title: "Zostaw resztki pożniwne (mulcz)",
        why: "Mulcz na powierzchni zmniejsza straty wody z wierzchniej warstwy gleby w okresie najczęstszych susz (V–VII).",
        addresses: ["gleba_niska_retencja"], when: "po zbiorze", legal_ids: [], funding_ids: [], evidence: [{ text: "ryzyko największe V–VII", block: "drought" }] },
    ],
    irrigation: { recommended: "no", horizon_days: 16, deficit_mm: -8.8, dose_mm: null, timing: null,
      summary: "MOCK: nawadnianie teraz nie ma sensu – uprawa w spoczynku zimowym, a prognoza daje więcej opadu niż parowania.",
      evidence: [{ text: "prognoza 16 dni: opad 25 mm, parowanie 17 mm", block: "weather_forecast" }] },
    limitations: ["MOCK: opady z reanalizy (siatka ok. 9 km) – lokalne burze mogą się różnić.", "Brak danych o drenowaniu działki (brak otwartej mapy drenaży w Polsce).",
      "Ocena gleby z mapy glebowo-rolniczej z lat 70–80."],
    method: ["Bilans wodny FAO-56 (ET₀ Penman-Monteith, Kc uprawy).", "Progi KBW SMSR (rozp. MRiRW z 11.04.2019) dla grupy upraw i kategorii gleby.",
      "Katalog działań NWRM (KE 2014/2015) i zasada „zatrzymaj wodę tam, gdzie spadła”."],
    missing_blocks: [],
  }),
};

export function mockBlock(key: string, q?: { date?: string }): DataBlock {
  const info = mockBlocks.find((b) => b.key === key);
  const asOf = q?.date ?? new Date().toISOString().slice(0, 10);
  const make = PAYLOADS[key];
  if (!make) {
    return { key, title: info?.title ?? key, status: "not_implemented", data: null, provenance: [], uncertainty: [], messages: ["Tryb mock"], elapsed_ms: 1 };
  }
  const notApplicable = key === "vegetation" && [11, 12, 1, 2, 3].includes(Number(asOf.slice(5, 7)));
  return {
    key, title: info?.title ?? key, status: notApplicable ? "not_applicable" : key === "legal_context" ? "ok" : "ok",
    data: make(asOf), provenance: MOCK_PROV(info?.title ?? key, asOf),
    uncertainty: ["Dane przykładowe (tryb mock) – nie opisują prawdziwej działki."].concat(
      notApplicable ? ["Poza sezonem wegetacji NDVI nie opisuje stanu upraw – pokazujemy ostatni sezon."] : []),
    messages: [], elapsed_ms: 120,
  };
}

export const mockKnowledge: Knowledge = {
  loaded: true,
  disclaimer: "Informacja orientacyjna, nie porada prawna. Ostateczna kwalifikacja: właściwy Nadzór Wodny / Zarząd Zlewni Wód Polskich oraz starostwo.",
  procedures: {
    zgloszenie_wodnoprawne: { id: "zgloszenie_wodnoprawne", title: "Zgłoszenie wodnoprawne", organ: "Kierownik Nadzoru Wodnego (Wody Polskie)",
      when: "Przed rozpoczęciem robót.", steps: ["Ustal właściwy Nadzór Wodny.", "Przygotuj opis, mapę i szkice.", "Wnieś opłatę i złóż zgłoszenie.", "Czekaj 30 dni na ewentualny sprzeciw."],
      fees: { "2026": 132.33, "2027": 137.09 }, typical_duration: "1–2 miesiące", typical_duration_status: "SZACUNEK", status: "OK",
      form_url: "https://www.gov.pl/attachment/31cc9cc2-6318-499a-adf9-040346fdf193", form_title: "Wzór zgłoszenia wodnoprawnego (gov.pl)",
      sources: ["https://www.gov.pl/wody-polskie/zgloszenie-wodnoprawne"] },
    pozwolenie_wodnoprawne: { id: "pozwolenie_wodnoprawne", title: "Pozwolenie wodnoprawne", organ: "Dyrektor Zarządu Zlewni albo RZGW",
      steps: [], attachments: ["operat wodnoprawny", "opis działalności", "dowód opłaty"], fees: { "2026": 330.07, "2027": 341.95 },
      typical_duration: "od kilku miesięcy do ponad roku", typical_duration_status: "SZACUNEK", status: "OK",
      form_url: "https://www.gov.pl/attachment/9b10c34a-922b-4911-b728-910736f466c9", form_title: "Wzór wniosku o pozwolenie wodnoprawne (gov.pl)",
      sources: ["https://www.gov.pl/wody-polskie/pozwolenie-wodnoprawne"] },
  },
  funding: {
    fgr_plus: { id: "fgr_plus", name: "Kredyt z gwarancją FGR Plus (BGK)", scope: "Gwarancja do 80% kredytu", call: "nabór ciągły", status: "OK", for_farmer: true },
    arimr_i1011: { id: "arimr_i1011", name: "ARiMR I.10.1.1", scope: "45–65% kosztów", call: "nabory okresowe", status: "DO_WERYFIKACJI", for_farmer: true },
    arimr_i104: { id: "arimr_i104", name: "ARiMR I.10.4 – ochrona środowiska i klimatu", scope: "zbiorniki na wodę opadową; do 65%", call: "do weryfikacji", status: "DO_WERYFIKACJI", for_farmer: true },
  },
  legal: {},
  eu: [{ id: "rdw", short: "Ramowa Dyrektywa Wodna", act: "Dyrektywa 2000/60/WE", celex: "32000L0060", farmer_impact: "Pobór >5 m³/d i nawadnianie wymagają zgody.", status: "OK" }],
  eurlexPattern: "https://eur-lex.europa.eu/legal-content/PL/TXT/?uri=CELEX:{celex}",
};
