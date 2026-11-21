// LUSTRO kontraktu backend/app/contracts/models.py – zmiany tylko addytywne, synchronicznie z backendem.
// (Opcjonalnie: generuj z OpenAPI `npx openapi-typescript http://127.0.0.1:8000/openapi.json`.)

export type BlockStatus = "ok" | "partial" | "no_data" | "not_applicable" | "error" | "not_implemented";

export type BlockKey =
  | "weather_history" | "weather_forecast" | "drought" | "soil" | "terrain" | "hydrology"
  | "vegetation" | "land_cover" | "yields" | "protected_areas" | "crop_calendar" | "legal_context" | "analysis";

export interface Provenance {
  source_name: string;
  source_url?: string | null;
  licence?: string | null;
  retrieved_at: string;
  mode: "live" | "cached" | "local_snapshot";
  snapshot_date?: string | null;
  data_as_of?: string | null;
  notes?: string | null;
}

export interface DataBlock<T = unknown> {
  key: BlockKey | string;
  title: string;
  status: BlockStatus;
  data: T | null;
  provenance: Provenance[];
  uncertainty: string[];
  messages: string[];
  elapsed_ms?: number | null;
}

export interface GeoJSONGeometry { type: string; coordinates: unknown }

export interface ParcelRef {
  id: string;
  teryt_unit?: string | null;
  region_code?: string | null;
  parcel_number?: string | null;
  voivodeship?: string | null;
  county?: string | null;
  commune?: string | null;
  region_name?: string | null;
  geometry: GeoJSONGeometry;
  centroid: [number, number];
  bbox: [number, number, number, number];
  area_ha: number;
}

export interface BlockInfo {
  key: BlockKey;
  title: string;
  category: "meteo" | "satellite" | "soil" | "hydro" | "spatial" | "knowledge" | "derived";
  implemented: boolean;
}

// ── payloady (podzbiór najczęściej używanych pól; pełne w models.py) ──
export interface DailySeries {
  dates: string[]; precip_mm: (number | null)[]; tmax_c: (number | null)[];
  tmin_c: (number | null)[]; et0_mm: (number | null)[];
}
export interface MonthlyClimate { month: number; precip_mean_mm: number | null; et0_mean_mm: number | null; cwb_mean_mm: number | null }
export interface SeasonSummary {
  year: number; precip_apr_sep_mm: number | null; et0_apr_sep_mm: number | null; cwb_apr_sep_mm: number | null;
  longest_dry_spell_days: number | null; min_cwb_60d_mm: number | null;
}
export interface WeatherHistory {
  provider: string; grid_resolution_note: string; start: string; end: string; daily: DailySeries;
  monthly_climatology: MonthlyClimate[]; seasons: SeasonSummary[];
  last_30d_precip_mm: number | null; last_30d_precip_normal_mm: number | null;
  cwb_60d_mm: number | null; cwb_60d_normal_mm: number | null;
  station_check?: { station: string; station_code: string; distance_km: number; season_bias_pct: number | null;
    station_last_30d_precip_mm: number | null; mean_abs_season_diff_mm: number | null;
    seasons_apr_sep: { year: number; reanalysis_mm: number; station_mm: number }[] } | null;
}

export interface CropItem {
  id: string; name_pl: string; type: string; sowing: string | null; harvest: string | null;
  drought_sensitivity?: string; critical?: string[];
}

// ── payloady bloków zespołu DATA (A) – jedna definicja na interfejs (scalone A+B 2026-11-21) ──
export type TerrainPosition = "hilltop" | "upper_slope" | "mid_slope" | "flat" | "valley" | "depression";
export type WaterKind = "river" | "stream" | "ditch" | "lake" | "pond" | "reservoir" | "spring" | "other";
export interface SoilInfo {
  agri_complex: string | null; soil_type: string | null; texture_class: string | null;
  drought_susceptibility: string | null; bonitation_classes: string[];
  clay_pct: number | null; sand_pct: number | null; silt_pct: number | null; soc_g_kg: number | null;
  awc_mm: number | null; source_used: string | null;
  drought_category?: number | null;                       // SMSR 1–4
  drought_category_shares_pct?: Record<string, number>;
  agri_complex_code?: string | null;
  agri_complex_shares_pct?: Record<string, number>;
  texture_profile?: string[];
  samples?: Record<string, unknown>[];
}
export interface TerrainInfo {
  elevation_mean_m: number | null; elevation_min_m: number | null; elevation_max_m: number | null;
  slope_mean_deg: number | null; slope_max_deg: number | null; aspect_dominant: string | null;
  position: TerrainPosition | null;
  position_label_pl: string | null; tpi_m: number | null; twi_mean: number | null;
  // FeatureCollection (EPSG:4326); properties: zagłębienia {area_m2, max_depth_m, volume_m3, touches_parcel},
  // linie spływu {length_m, catchment_ha, crosses_parcel}
  depressions_geojson: GeoJSON.FeatureCollection | null; flow_lines_geojson: GeoJSON.FeatureCollection | null;
  dem_resolution_m: number | null;
}
export interface WaterFeature {
  kind: WaterKind;
  name: string | null; distance_m: number; geometry?: GeoJSONGeometry | null;
}
export interface HydrologyInfo {
  nearest_water: WaterFeature[];
  in_flood_zone: "0.2%" | "1%" | "10%" | null; flood_zone_checked: boolean;
  catchment_name: string | null; jcwp_code: string | null; groundwater_depth_m: string | null;
  gzwp: string | null; nearest_boreholes: Record<string, unknown>[]; water_management_board: string | null;
  in_flood_hazard_area?: boolean | null; in_groundwater_flood_area?: boolean | null; jcwpd_code?: string | null;
}
export interface ProtectedAreaHit { kind: string; name: string | null; code: string | null; distance_m?: number | null }
export interface ProtectedAreasInfo { hits: ProtectedAreaHit[]; checked_layers: string[]; nearby?: ProtectedAreaHit[] }
export interface WeatherForecast {
  provider: string; dates: string[]; precip_mm: (number | null)[]; et0_mm: (number | null)[];
  tmax_c: (number | null)[]; tmin_c: (number | null)[];
}
export interface DroughtIndex {
  source: string; date: string | null; value: number | string | null; class_label?: string | null;
  level?: "commune" | "pixel" | "parcel" | null;
}
export interface DroughtHistory {
  current: DroughtIndex[]; history: DroughtIndex[]; drought_years: number[];
  drought_years_smsr?: number[]; drought_years_computed?: number[]; crop_group?: string | null;
  soil_category?: number | null; commune_teryt?: string | null; commune_name?: string | null;
  periods?: { year: number; period: number; start: string; end: string; drought: boolean; source: "smsr" | "computed";
              kbw_mm?: number; threshold_mm?: number; commune_area_share_pct?: number | null }[];
}
export interface VegetationObs { date: string; ndvi: number | null; ndmi?: number | null; cloud_pct?: number | null; scene_id?: string | null }
export interface VegetationInfo {
  latest: VegetationObs | null; latest_age_days: number | null; series: VegetationObs[];
  baseline_same_doy: number | null; anomaly: number | null; in_growing_season: boolean | null;
}
export interface LandCoverInfo {
  classes: Record<string, number>; agricultural_share_pct: number | null; source_used: string | null;
  cropland_share_pct?: number | null; bdot_classes?: Record<string, number>;
}
export interface YieldRecord { year: number; crop: string; yield_t_ha: number | null; level: "powiat" | "voivodeship" | "country" | "parcel_proxy"; unit_name?: string | null }
export interface YieldInfo { official: YieldRecord[]; parcel_productivity_index: { year: number; peak_ndvi: number; rel_index: number }[]; note: string | null }
export interface CropStage { name: string; start: string; end: string; kc?: number | null }
export interface CropCalendarInfo {
  crop: string; crop_name_pl: string; in_season_on_as_of: boolean; current_stage?: string | null;
  stages: CropStage[]; critical_water_periods: string[]; sowing_ok_now?: boolean | null;
  warnings: string[]; suggested_crops_now: string[];
}
export type KnowledgeStatus = "OK" | "DO_WERYFIKACJI" | "SZACUNEK";
export interface LegalHint {
  topic: string; requirement: string; why: string; procedure_id?: string | null;
  status: KnowledgeStatus; sources: string[];
  // addytywnie 2026-11-21 (B)
  title?: string | null; group?: "none" | "notification" | "permit" | "depends" | null;
  legal_ids?: string[]; fee_pln?: number | null; fee_year?: number | null;
  facts_used?: string[]; unchecked?: string[]; caution?: string | null;
}
export interface LegalContextInfo {
  hints: LegalHint[]; funding_ids: string[];
  disclaimer?: string | null; facts_checked?: Record<string, string>;
}

// ── wyniki analizy F2 – blok `analysis` (propozycja B, 2026-11-21; lustro models.py) ──
export type RiskLevel = "none" | "low" | "moderate" | "high" | "very_high";
export interface Evidence { text: string; block?: string | null }
export interface WaterAssessment {
  current_level?: RiskLevel | null; current_label_pl?: string | null; current_summary?: string | null;
  historical_level?: RiskLevel | null; historical_label_pl?: string | null; historical_summary?: string | null;
  drought_years: number[]; critical_months: number[]; confidence?: "low" | "medium" | "high" | null; evidence: Evidence[];
}
export interface Cause { key: string; label_pl: string; share?: number | null; explanation?: string | null; evidence: Evidence[] }
export interface Recommendation {
  measure_id: string; group: "retencja_krajobrazowa" | "agrotechnika" | "nawadnianie"; title: string; why: string;
  priority: number; addresses: string[]; when?: string | null; where_geojson?: GeoJSON.FeatureCollection | GeoJSON.Feature | null;
  legal_ids: string[]; funding_ids: string[]; evidence: Evidence[];
}
export interface IrrigationAdvice {
  recommended?: "no" | "monitor" | "yes" | null; summary?: string | null; deficit_mm?: number | null; dose_mm?: number | null;
  horizon_days?: number | null; timing?: string | null; evidence: Evidence[];
}
export interface AnalysisResult {
  assessment?: WaterAssessment | null; causes: Cause[]; recommendations: Recommendation[]; irrigation?: IrrigationAdvice | null;
  limitations: string[]; method: string[]; missing_blocks: string[];
}
