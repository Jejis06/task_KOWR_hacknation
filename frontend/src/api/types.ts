// LUSTRO kontraktu backend/app/contracts/models.py – zmiany tylko addytywne, synchronicznie z backendem.
// (Opcjonalnie: generuj z OpenAPI `npx openapi-typescript http://127.0.0.1:8000/openapi.json`.)

export type BlockStatus = "ok" | "partial" | "no_data" | "not_applicable" | "error" | "not_implemented";

export type BlockKey =
  | "weather_history" | "weather_forecast" | "drought" | "soil" | "terrain" | "hydrology"
  | "vegetation" | "land_cover" | "yields" | "protected_areas" | "crop_calendar" | "legal_context";

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
}

export interface CropItem {
  id: string; name_pl: string; type: string; sowing: string | null; harvest: string | null;
  drought_sensitivity?: string; critical?: string[];
}

// ── payloady bloków zespołu DATA (A) – dodawane addytywnie ──
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
