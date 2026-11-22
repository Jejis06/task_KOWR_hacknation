/**
 * Kontrakt API frontendu. Prawdziwe bloki z FastAPI (`/api/...`) przechodzą przez `adapt()` (api/adapt.ts), który
 * tłumaczy je na format prezentacji (summary / metrics / series / rows); surowe dane zostają w `data.raw`.
 * VITE_USE_MOCKS=true → dane demonstracyjne z api/mocks.ts (bez backendu).
 */
import { adapt } from "./adapt";

export const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === "true";
export const DEMO_ID = "302504_5.0019.52/16";

export type Polygon = { type: "Polygon"; coordinates: number[][][] };
export type ParcelRef = {
  id: string;
  region_name: string;
  commune: string;
  county: string;
  voivodeship: string;
  parcel_number: string;
  geometry: Polygon | { type: string; coordinates: unknown };
  centroid: [number, number];
  bbox: [number, number, number, number];
  area_ha: number;
};
export type Provenance = {
  source_name: string;
  source_url: string | null;
  query_url?: string | null;
  licence: string | null;
  retrieved_at: string;
  mode: "live" | "cached" | "local_snapshot";
  data_as_of: string | null;
  snapshot_date?: string | null;
  notes: string | null;
};
export type Evidence = { text: string; block: string | null };
export type FieldCheck = {
  kbw: "dry" | "normal";
  ndmi: "low" | "normal";
  kbw_anomaly_mm: number;
  ndmi_anomaly: number;
  case: "confirmed" | "field_holds" | "local_problem" | "no_signal";
  label_pl: string;
  text: string;
};
export type Assessment = {
  current_level: "none" | "low" | "moderate" | "high" | "very_high";
  current_label_pl: string;
  current_summary: string;
  historical_level: string;
  historical_label_pl: string;
  historical_summary: string;
  drought_years: number[];
  critical_months: number[];
  confidence: string;
  evidence: Evidence[];
  field_check?: FieldCheck | null;
};
export type SowingOption = { name: string; when: string; why: string; source_title: string | null; source_url: string | null };
export type Recommendation = {
  measure_id: string;
  group: "retencja_krajobrazowa" | "agrotechnika" | "nawadnianie";
  title: string;
  why: string;
  priority: number;
  when: string | null;
  where_geojson: GeoJSON.GeoJsonObject | null;
  legal_ids: string[];
  funding_ids: string[];
  evidence: Evidence[];
  /** międzyplon / mulcz: co i kiedy zrobić (2026-11-21, B) */
  sowing?: SowingOption[];
  funding?: { name: string; url: string | null }[];
};
export type SoilWaterDay = { date: string; dr_mm: number; raw_mm: number; taw_mm: number; forecast: boolean };
export type Irrigation = {
  recommended: "no" | "monitor" | "yes" | null;
  summary: string | null;
  deficit_mm: number | null;
  dose_mm: number | null;
  horizon_days: number | null;
  timing: string | null;
  evidence: Evidence[];
  depletion_mm?: number | null;
  taw_mm?: number | null;
  raw_mm?: number | null;
  ks?: number | null;
  days_to_stress?: number | null;
  stress_date?: string | null;
  season_et_ratio?: number | null;
  yield_loss_pct?: number | null;
  soil_water?: SoilWaterDay[];
};
export type WaterBalance = {
  area_ha: number;
  deficit_60d_mm: number | null;
  deficit_60d_m3: number | null;
  season_deficit_mm: number | null;
  season_deficit_m3: number | null;
  worst_season_deficit_mm: number | null;
  worst_season_deficit_m3: number | null;
  depression_volume_m3?: number;
  depression_area_m2?: number;
  depression_catchment_ha?: number | null;
  winter_surplus_mm?: number;
  depression_inflow_m3?: number | null;
  depression_fill_pct?: number | null;
  coverage_season_pct?: number | null;
};
export type SeriesRow = {
  label: string;
  rain: number;
  normal: number;
  evaporation: number;
  value: number;
  value2?: number | null;
};
export type Row = { label: string; value: string; detail: string; dry?: boolean; mapId?: string };
export type DataPayload = {
  summary?: string;
  metrics?: { label: string; value: string; term?: string }[];
  series?: SeriesRow[];
  rows?: Row[];
  balance_mm?: number | null;
  normal_mm?: number | null;
  assessment?: Assessment;
  causes?: { key: string; label_pl: string; share: number; explanation: string; evidence: Evidence[] }[];
  recommendations?: Recommendation[];
  irrigation?: Irrigation;
  water_balance?: WaterBalance | null;
  limitations?: string[];
  method?: string[];
  /** surowe dane bloku z backendu (kontrakt backend/app/contracts/models.py) */
  raw?: any; // eslint-disable-line @typescript-eslint/no-explicit-any
};
export type BlockStatus = "ok" | "partial" | "no_data" | "not_applicable" | "error" | "not_implemented";
export type DataBlock = {
  key: string;
  title: string;
  status: BlockStatus;
  data: DataPayload;
  provenance: Provenance[];
  uncertainty: string[];
  messages: string[];
  elapsed_ms: number | null;
};
export type GeocodeResult = { label: string; lon: number; lat: number; has_house_number: boolean; source: string };
export type Crop = { id: string; name_pl: string; type: string; sowing: string | null; harvest: string | null };

/** Bloki pokazywane w UI (kolejność kart). Tytuły po stronie frontu – krótsze niż w backendzie. */
export const blockDefinitions = [
  ["weather_history", "Opady i pogoda", "Pogoda"],
  ["weather_forecast", "Prognoza na 16 dni", "Pogoda"],
  ["drought", "Susza rolnicza", "Woda"],
  ["soil", "Gleba", "Pole"],
  ["terrain", "Ukształtowanie terenu", "Pole"],
  ["hydrology", "Woda w okolicy", "Woda"],
  ["vegetation", "Kondycja roślin", "Pole"],
  ["land_cover", "Pokrycie terenu", "Pole"],
  ["protected_areas", "Ochrona przyrody", "Otoczenie"],
  ["crop_calendar", "Kalendarz uprawy", "Uprawa"],
  ["legal_context", "Formalności i wsparcie", "Formalności"],
  ["analysis", "Ocena i zalecenia", "Ocena"],
].map(([key, title, category]) => ({ key: key ?? "", title: title ?? "", category: category ?? "", implemented: true }));
export const blockTitle = (key: string) => blockDefinitions.find((b) => b.key === key)?.title ?? key;

export function dateBounds(today = new Date()): { min: string; max: string } {
  const max = today.toISOString().slice(0, 10);
  const minDate = new Date(`${max}T12:00:00Z`);
  minDate.setUTCFullYear(minDate.getUTCFullYear() - 10);
  return { min: minDate.toISOString().slice(0, 10), max };
}
export function validDate(value: string, today = new Date()) {
  const { min, max } = dateBounds(today);
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(value)) && value >= min && value <= max;
}
export function canShowAdvice(block?: DataBlock) {
  return Boolean(block?.data.assessment && (block.status === "ok" || block.status === "partial"));
}
export function doseToVolume(mm: number) {
  return mm * 10;
}

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, signal ? { signal } : {});
  if (!response.ok) {
    let detail = "";
    try {
      detail = ((await response.json()) as { detail?: string }).detail ?? "";
    } catch {
      /* brak treści */
    }
    throw new Error(detail || `Nie udało się pobrać danych (${response.status}). Spróbuj ponownie.`);
  }
  return response.json() as Promise<T>;
}
function wait(ms: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const t = setTimeout(resolve, ms);
    const abort = () => {
      clearTimeout(t);
      reject(new DOMException("Przerwano", "AbortError"));
    };
    if (signal?.aborted) {
      abort();
      return;
    }
    signal?.addEventListener("abort", abort, { once: true });
  });
}

export const api = {
  async resolve(input: { id?: string; lon?: number; lat?: number }, signal?: AbortSignal): Promise<ParcelRef> {
    if (!USE_MOCKS)
      return request(
        `/api/parcel/resolve?${new URLSearchParams(
          Object.entries(input).filter(([, v]) => v !== undefined && v !== "").map(([k, v]) => [k, String(v)]),
        )}`,
        signal,
      );
    const { parcel } = await import("./mocks");
    await wait(180, signal);
    if (input.id && input.id.trim() !== DEMO_ID)
      throw new Error(`W wersji demonstracyjnej dostępna jest działka ${DEMO_ID}. Wybierz ją na mapie lub użyj przykładu.`);
    return { ...parcel };
  },
  async geocode(q: string, signal?: AbortSignal): Promise<GeocodeResult> {
    if (!USE_MOCKS) return request(`/api/geocode?${new URLSearchParams({ q })}`, signal);
    const { parcel } = await import("./mocks");
    await wait(150, signal);
    return { label: q, lon: parcel.centroid[0], lat: parcel.centroid[1], has_house_number: false, source: "dane demonstracyjne" };
  },
  async inArea(ring: [number, number][], signal?: AbortSignal): Promise<{ parcels: ParcelRef[]; total: number }> {
    if (!USE_MOCKS) {
      const r = await fetch("/api/parcel/in-area", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ring }), signal });
      if (!r.ok) {
        let detail = "";
        try { detail = ((await r.json()) as { detail?: string }).detail ?? ""; } catch { /* brak treści */ }
        throw new Error(detail || "Nie udało się pobrać działek z obszaru.");
      }
      const parcels = (await r.json()) as ParcelRef[];
      return { parcels, total: Number(r.headers.get("X-Total-Count") ?? parcels.length) };
    }
    const { parcel } = await import("./mocks");
    await wait(300, signal);
    return { parcels: [{ ...parcel }], total: 1 };
  },
  async blocks(signal?: AbortSignal) {
    if (!USE_MOCKS) {
      const server = await request<{ key: string; implemented: boolean }[]>("/api/parcel/blocks", signal);
      const known = new Set(server.map((b) => b.key));
      return blockDefinitions.filter((b) => known.has(b.key)).map((b) => ({
        ...b, implemented: server.find((s) => s.key === b.key)?.implemented ?? true,
      }));
    }
    return blockDefinitions;
  },
  async crops(signal?: AbortSignal): Promise<Crop[]> {
    if (!USE_MOCKS) {
      const j = await request<{ items?: Crop[] } | Crop[]>("/api/knowledge/crops", signal);
      return Array.isArray(j) ? j : (j.items ?? []);
    }
    return [
      { id: "wheat", name_pl: "Pszenica ozima", type: "zboże", sowing: "Wrzesień–październik", harvest: "Lipiec–sierpień" },
      { id: "maize", name_pl: "Kukurydza", type: "zboże", sowing: "Kwiecień–maj", harvest: "Wrzesień–październik" },
      { id: "potato", name_pl: "Ziemniaki", type: "okopowe", sowing: "Kwiecień", harvest: "Wrzesień" },
    ];
  },
  async block(key: string, id: string, date: string, crop: string, signal?: AbortSignal): Promise<DataBlock> {
    if (!USE_MOCKS) {
      const q = new URLSearchParams({ id, date });
      if (crop) q.set("crop", crop);
      const raw = await request<Omit<DataBlock, "data"> & { data: unknown }>(`/api/parcel/block/${encodeURIComponent(key)}?${q}`, signal);
      return adapt(raw, date);
    }
    const { mockBlock } = await import("./mocks");
    await wait(350 + (blockDefinitions.findIndex((b) => b.key === key) + 1) * 100, signal);
    return mockBlock(key, date, crop);
  },
};
