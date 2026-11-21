// Dane przykładowe zgodne z kontraktem – UI działa bez backendu (VITE_USE_MOCKS=true).
import type { BlockInfo, CropItem, DataBlock, ParcelRef } from "../api/types";

export const mockParcel: ParcelRef = {
  id: "146505_8.0116.5",
  teryt_unit: "146505_8",
  region_code: "0116",
  parcel_number: "5",
  voivodeship: "mazowieckie",
  county: "powiat Warszawa",
  commune: "Warszawa (miasto)",
  region_name: "1-01-16",
  geometry: {
    type: "Polygon",
    coordinates: [[[20.99998, 52.19988], [21.00041, 52.19949], [20.99996, 52.20106], [20.99966, 52.201], [20.99998, 52.19988]]],
  },
  centroid: [20.99995, 52.2002],
  bbox: [20.99966, 52.19949, 21.00041, 52.20106],
  area_ha: 0.42,
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
  { key: "crop_calendar", title: "Kalendarz uprawy i okres wegetacji", category: "knowledge", implemented: false },
  { key: "legal_context", title: "Pozwolenia, procedury i dofinansowania", category: "knowledge", implemented: false },
];

export const mockCrops: CropItem[] = [
  { id: "pszenica_ozima", name_pl: "Pszenica ozima", type: "ozima", sowing: "09-15..10-20", harvest: "07-20..08-20" },
  { id: "kukurydza_ziarno", name_pl: "Kukurydza na ziarno", type: "jara", sowing: "04-20..05-15", harvest: "09-25..11-15" },
  { id: "ziemniak", name_pl: "Ziemniak", type: "jara", sowing: "04-05..05-10", harvest: "08-15..10-10" },
];

export function mockBlock(key: string): DataBlock {
  const info = mockBlocks.find((b) => b.key === key);
  const now = new Date().toISOString();
  if (key === "weather_history") {
    return {
      key, title: info!.title, status: "ok",
      data: {
        provider: "nasa-power", grid_resolution_note: "MOCK", start: "2016-11-01", end: "2026-11-20",
        daily: { dates: [], precip_mm: [], tmax_c: [], tmin_c: [], et0_mm: [] },
        monthly_climatology: [], seasons: [
          { year: 2024, precip_apr_sep_mm: 310, et0_apr_sep_mm: 560, cwb_apr_sep_mm: -250, longest_dry_spell_days: 19, min_cwb_60d_mm: -142 },
        ],
        last_30d_precip_mm: 22.1, last_30d_precip_normal_mm: 38.4, cwb_60d_mm: -35, cwb_60d_normal_mm: -10,
      },
      provenance: [{ source_name: "MOCK", retrieved_at: now, mode: "local_snapshot" }],
      uncertainty: ["Dane przykładowe (tryb mock)."], messages: [], elapsed_ms: 5,
    };
  }
  return {
    key, title: info?.title ?? key, status: info?.implemented ? "no_data" : "not_implemented", data: null,
    provenance: [], uncertainty: [], messages: ["Tryb mock"], elapsed_ms: 1,
  };
}
