/* eslint-disable @typescript-eslint/no-explicit-any */
// Tłumaczy bloki z backendu (backend/app/contracts/models.py) na format prezentacji nowego UI.
// Zasada: żadnych zmyślonych liczb – wszystko liczone z `raw`; brak danych → „brak danych”.
import type { DataBlock, DataPayload, Row, SeriesRow } from "./client";

const MONTHS = ["Sty", "Lut", "Mar", "Kwi", "Maj", "Cze", "Lip", "Sie", "Wrz", "Paź", "Lis", "Gru"];
const nf = (v: number, d = 0) => v.toLocaleString("pl-PL", { maximumFractionDigits: d, minimumFractionDigits: d });
export const mm = (v: number | null | undefined, d = 0) => (v == null ? "brak danych" : `${nf(v, d)} mm`);
export const smm = (v: number | null | undefined, d = 0) =>
  v == null ? "brak danych" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${nf(Math.abs(v), d)} mm`;
export const dist = (m: number) => (m >= 1000 ? `${nf(m / 1000, 1)} km` : `${nf(m)} m`);
const pct = (v: number | null | undefined, d = 0) => (v == null ? "brak danych" : `${nf(v, d)}%`);
const dstr = (s: string | null | undefined) => (s ? `${s.slice(8, 10)}.${s.slice(5, 7)}.${s.slice(0, 4)}` : "brak daty");

export const WATER_KIND: Record<string, string> = {
  river: "Rzeka", stream: "Ciek / strumień", ditch: "Rów melioracyjny", lake: "Jezioro", pond: "Staw / oczko",
  reservoir: "Zbiornik", spring: "Źródło", other: "Woda",
};
const FLOOD: Record<string, string> = { "10%": "raz na 10 lat", "1%": "raz na 100 lat", "0.2%": "raz na 500 lat" };
const SMSR_CAT: Record<number, string> = {
  1: "kat. I – bardzo podatna na suszę", 2: "kat. II – podatna", 3: "kat. III – średnio podatna", 4: "kat. IV – mało podatna",
};
const CONF: Record<string, string> = { low: "Niska", medium: "Średnia", high: "Wysoka" };

function weatherHistory(d: any): DataPayload {
  const daily = d.daily ?? { dates: [], precip_mm: [], et0_mm: [] };
  const clim = new Map<number, any>((d.monthly_climatology ?? []).map((m: any) => [m.month, m]));
  // 12 ostatnich miesięcy do daty analizy: opad i parowanie w miesiącu vs norma z 10 lat
  const sums = new Map<string, { p: number; e: number }>();
  daily.dates.forEach((x: string, i: number) => {
    const k = x.slice(0, 7);
    const s = sums.get(k) ?? { p: 0, e: 0 };
    s.p += daily.precip_mm[i] ?? 0;
    s.e += daily.et0_mm[i] ?? 0;
    sums.set(k, s);
  });
  const keys = [...sums.keys()].sort().slice(-12);
  const series: SeriesRow[] = keys.map((k) => {
    const m = Number(k.slice(5, 7));
    return { label: `${MONTHS[m - 1]} ${k.slice(2, 4)}`, rain: Math.round(sums.get(k)!.p),
      normal: Math.round(clim.get(m)?.precip_mean_mm ?? 0), evaporation: Math.round(sums.get(k)!.e), value: 0 };
  });
  const seasons = [...(d.seasons ?? [])];
  const after = new Set((d.seasons_after_as_of ?? []).map((s: any) => s.year));
  const cwbs = seasons.map((s: any) => s.cwb_apr_sep_mm).filter((v: any) => v != null) as number[];
  const mean = cwbs.length ? cwbs.reduce((a, b) => a + b, 0) / cwbs.length : null;
  const sd = mean != null && cwbs.length > 1 ? Math.sqrt(cwbs.reduce((a, b) => a + (b - mean) ** 2, 0) / cwbs.length) : null;
  const limit = mean != null && sd != null ? Math.max(30, 0.5 * sd) : null;
  const rows: Row[] = [...seasons, ...(d.seasons_after_as_of ?? [])].sort((a: any, b: any) => b.year - a.year).map((s: any) => ({
    label: String(s.year),
    value: mm(s.precip_apr_sep_mm),
    detail: `Parowanie ${mm(s.et0_apr_sep_mm)} · bilans ${smm(s.cwb_apr_sep_mm)} · najdłużej bez deszczu ${s.longest_dry_spell_days ?? "–"} dni`
      + (after.has(s.year) ? " · po dacie analizy (tylko porównanie)" : ""),
    dry: !after.has(s.year) && s.cwb_apr_sep_mm != null && mean != null && limit != null && s.cwb_apr_sep_mm < mean - limit,
    after: after.has(s.year),
  }));
  const diff = d.cwb_60d_mm != null && d.cwb_60d_normal_mm != null ? d.cwb_60d_mm - d.cwb_60d_normal_mm : null;
  const summary = diff == null ? "Bilans wody z 60 dni: brak danych."
    : Math.abs(diff) < 10 ? "Bilans wody z ostatnich 60 dni jest w normie dla tej pory roku."
    : diff < 0 ? `Sucho: w ostatnich 60 dniach o ${mm(-diff)} wody mniej niż zwykle o tej porze roku.`
    : `Wilgotniej niż zwykle: o ${mm(diff)} wody więcej niż zwykle o tej porze roku.`;
  return {
    summary, series, rows, raw: d, balance_mm: d.cwb_60d_mm, normal_mm: d.cwb_60d_normal_mm,
    metrics: [
      { label: `Bilans wody z 60 dni (do ${dstr(d.end)})`, value: smm(d.cwb_60d_mm), term: "KBW" },
      { label: "Zwykle o tej porze", value: smm(d.cwb_60d_normal_mm) },
      { label: "Opad z 30 dni", value: mm(d.last_30d_precip_mm) },
      { label: "Zwykle w 30 dni", value: mm(d.last_30d_precip_normal_mm) },
    ],
  };

}

const MON_ABBR = ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"];
const MON_FULL = ["styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec", "lipiec", "sierpień", "wrzesień",
  "październik", "listopad", "grudzień"];
export type SeasonWindow = { start: string; end: string; crossYear: boolean; label: string; crop: string | null };
export type SeasonRow = {
  year: number; precip: number | null; et0: number | null; cwb: number | null; drySpell: number | null;
  days: number; partial: boolean; dry: boolean;
};

/** Okno sezonu: okres wegetacji wybranej uprawy (z kalendarza uprawy) albo domyślnie marzec–wrzesień. */
export function seasonWindow(cal: any): SeasonWindow {
  const stages = (cal?.stages ?? []) as { start: string; end: string }[];
  if (cal?.crop && stages.length) {
    const s = stages[0]!.start.slice(5, 10), e = stages[stages.length - 1]!.end.slice(5, 10);
    const crossYear = stages[0]!.start.slice(0, 4) !== stages[stages.length - 1]!.end.slice(0, 4);
    const label = `${Number(s.slice(3))} ${MON_ABBR[Number(s.slice(0, 2)) - 1]} – ${Number(e.slice(3))} ${MON_ABBR[Number(e.slice(0, 2)) - 1]}`;
    return { start: s, end: e, crossYear, label: `okres wegetacji: ${cal.crop_name_pl} (${label}${crossYear ? " następnego roku" : ""})`, crop: cal.crop_name_pl };
  }
  return { start: "03-01", end: "09-30", crossYear: false, label: `${MON_FULL[2]} – ${MON_FULL[8]} (nie wybrano uprawy)`, crop: null };
}

/** Sezony z dziennej serii meteo w oknie `w` – rok = rok końca sezonu; sezon bieżący liczony do daty analizy. */
export function seasonRows(weather: any, w: SeasonWindow, asOf: string): SeasonRow[] {
  const daily = weather?.daily;
  if (!daily?.dates?.length) return [];
  const first = daily.dates[0] as string, last = daily.dates[daily.dates.length - 1] as string;
  const endYear = Number(asOf.slice(0, 4));
  const rows: SeasonRow[] = [];
  for (let y = w.crossYear ? endYear + 1 : endYear; y >= endYear - 10; y--) {
    const from = `${w.crossYear ? y - 1 : y}-${w.start}`, to = `${y}-${w.end}`;
    if (from > last) continue;                       // sezon jeszcze się nie zaczął
    if (from < first) break;                         // brak pełnych danych na początku sezonu
    let p = 0, e = 0, n = 0, run = 0, best = 0, pn = 0, en = 0;
    daily.dates.forEach((d: string, i: number) => {
      if (d < from || d > to) return;
      n++;
      const pr = daily.precip_mm[i], et = daily.et0_mm[i];
      if (pr != null) { p += pr; pn++; }
      if (et != null) { e += et; en++; }
      run = pr != null && pr < 1 ? run + 1 : 0;
      best = Math.max(best, run);
    });
    if (!n) continue;
    rows.push({ year: y, precip: pn ? Math.round(p) : null, et0: en ? Math.round(e) : null,
      cwb: pn && en ? Math.round(p - e) : null, drySpell: best, days: n, partial: to > last, dry: false });
  }
  const full = rows.filter((r) => !r.partial && r.cwb != null).map((r) => r.cwb as number);
  if (full.length > 1) {
    const mean = full.reduce((a, b) => a + b, 0) / full.length;
    const sd = Math.sqrt(full.reduce((a, b) => a + (b - mean) ** 2, 0) / full.length);
    const limit = Math.max(30, 0.5 * sd);
    rows.forEach((r) => { r.dry = !r.partial && r.cwb != null && r.cwb < mean - limit; });
  }
  return rows;
}

function forecast(d: any): DataPayload {
  const p = (d.precip_mm ?? []).map((v: any) => v ?? 0) as number[];
  const e = (d.et0_mm ?? []).map((v: any) => v ?? 0) as number[];
  const sp = p.reduce((a, b) => a + b, 0), se = e.reduce((a, b) => a + b, 0);
  return {
    raw: d,
    summary: sp >= se ? `W ciągu ${p.length} dni spadnie więcej wody (${mm(sp)}), niż wyparuje (${mm(se)}).`
      : `Najbliższe ${p.length} dni: opad ${mm(sp)} nie pokryje parowania ${mm(se)} – bilans ${smm(sp - se)}.`,
    series: (d.dates ?? []).map((x: string, i: number) => ({ label: `${x.slice(8, 10)}.${x.slice(5, 7)}`, rain: Math.round((p[i] ?? 0) * 10) / 10,
      normal: 0, evaporation: Math.round((e[i] ?? 0) * 10) / 10, value: 0 })),
    metrics: [
      { label: "Suma opadów", value: mm(sp, 1) },
      { label: "Parowanie", value: mm(se, 1), term: "ET₀" },
      { label: "Zmiana bilansu", value: smm(sp - se, 1) },
    ],
  };
}

function drought(d: any, asOf: string): DataPayload {
  const end = Number(asOf.slice(0, 4));
  const dry = new Set<number>(d.drought_years ?? []);
  const years = Array.from({ length: 10 }, (_, i) => end - 9 + i);
  const n = years.filter((y) => dry.has(y)).length;
  return {
    raw: d,
    summary: n === 0 ? "W ostatnich 10 sezonach nie było suszy rolniczej na tej działce (wg progów SMSR)."
      : `Susza rolnicza w ${n} z 10 ostatnich sezonów.`,
    rows: [
      ...(d.current ?? []).map((c: any) => ({ label: `${c.source}${c.level === "commune" ? " (gmina)" : c.level === "pixel" ? " (okolica ~5 km)" : " (działka)"}`,
        value: String(c.class_label ?? c.value ?? "brak oceny"), detail: `stan na ${dstr(c.date)}` })),
      ...years.slice().reverse().map((y) => ({ label: String(y), value: dry.has(y) ? "susza" : "bez suszy",
        detail: (d.drought_years_smsr ?? []).includes(y) ? "SMSR IUNG – gmina" : (d.drought_years_computed ?? []).includes(y) ? "KBW działki wg progów SMSR" : "", dry: dry.has(y) })),
    ],
    metrics: [
      { label: "Suche sezony (10 lat)", value: `${n} z 10` },
      { label: "Kategoria gleby SMSR", value: d.soil_category ? `kat. ${["I", "II", "III", "IV"][d.soil_category - 1]}` : "brak danych", term: "SMSR" },
      { label: "Gmina", value: d.commune_name ?? "brak danych" },
    ],
  };
}

function soil(d: any): DataPayload {
  const cat = d.drought_category as number | null;
  return {
    raw: d,
    summary: [cat ? `Gleba ${SMSR_CAT[cat]}.` : "", d.awc_mm != null ? `Zapas wody dla roślin ok. ${mm(d.awc_mm)} w 1 m gleby.` : ""].join(" ").trim()
      || "Brak danych glebowych.",
    metrics: [
      { label: "Podatność na suszę", value: cat ? `kat. ${["I", "II", "III", "IV"][cat - 1]}` : "brak danych", term: "SMSR" },
      { label: "Woda dostępna dla roślin (1 m)", value: mm(d.awc_mm) },
      { label: "Węgiel organiczny", value: d.soc_g_kg != null ? `${nf(d.soc_g_kg)} g/kg` : "brak danych" },
    ],
    rows: [
      { label: "Kompleks przydatności", value: d.agri_complex ?? "brak danych", detail: "mapa glebowo-rolnicza" },
      { label: "Typ gleby", value: d.soil_type ?? "brak danych", detail: "" },
      { label: "Uziarnienie", value: d.texture_class ?? "brak danych", detail: (d.texture_profile ?? []).join(" · ") },
      { label: "Klasy bonitacyjne", value: (d.bonitation_classes ?? []).join(", ") || "brak danych", detail: "ewidencja gruntów" },
      { label: "Piasek / pył / ił", value: d.sand_pct != null ? `${pct(d.sand_pct)} / ${pct(d.silt_pct)} / ${pct(d.clay_pct)}` : "brak danych", detail: d.source_used ?? "" },
    ],
  };
}

function terrain(d: any): DataPayload {
  const deps = (d.depressions_geojson?.features ?? []) as any[];
  const exits = (d.runoff_exits_geojson?.features ?? []) as any[];
  const slopePct = d.slope_mean_deg != null ? Math.tan((d.slope_mean_deg * Math.PI) / 180) * 100 : null;
  return {
    raw: d,
    summary: `${d.position_label_pl ? `${d.position_label_pl[0].toUpperCase()}${d.position_label_pl.slice(1)}` : "Położenie nieznane"}`
      + (deps.length ? `; ${deps.filter((f) => f.properties?.touches_parcel).length} zagłębień przy działce, w których zbiera się woda.` : "."),
    metrics: [
      { label: "Spadek średni", value: slopePct != null ? `${nf(slopePct, 1)}%` : "brak danych" },
      { label: "Wysokość", value: d.elevation_min_m != null ? `${nf(d.elevation_min_m)}–${nf(d.elevation_max_m)} m n.p.m.` : "brak danych" },
      { label: "Miejsca odpływu z pola", value: String(exits.length) },
    ],
    rows: [
      ...deps.slice(0, 6).map((f, i) => ({ label: `Zagłębienie ${i + 1}`, mapId: `dep-${i}`,
        value: `${nf(f.properties?.area_m2 ?? 0)} m² · do ${nf(f.properties?.max_depth_m ?? 0, 1)} m`,
        detail: `pojemność ok. ${nf(f.properties?.volume_m3 ?? 0)} m³${f.properties?.catchment_ha != null ? ` · zlewnia ${nf(f.properties.catchment_ha, 1)} ha` : ""}${f.properties?.touches_parcel ? " · przy działce" : ""}` })),
      ...exits.slice(0, 6).map((f, i) => ({ label: `Odpływ z pola ${i + 1}`, mapId: `exit-${i}`,
        value: `${nf(f.properties?.length_m ?? 0)} m granicy`, detail: `spływa tędy woda z ok. ${nf(f.properties?.catchment_ha ?? 0, 1)} ha` })),
    ],
  };
}

function hydrology(d: any): DataPayload {
  const waters = (d.nearest_water ?? []).map((w: any, i: number) => ({ w, i })).sort((a: any, b: any) => a.w.distance_m - b.w.distance_m);
  const ditch = waters.find((x: any) => x.w.kind === "ditch");
  const flood = !d.flood_zone_checked ? "nie sprawdzono" : d.in_flood_zone ? `strefa „${FLOOD[d.in_flood_zone] ?? d.in_flood_zone}”` : d.in_flood_hazard_area ? "w zasięgu mapy zagrożenia" : "poza strefą";
  return {
    raw: d,
    summary: `${ditch ? `Najbliższy rów melioracyjny ${dist(ditch.w.distance_m)} od działki. ` : ""}Strefa powodziowa: ${flood}.`,
    metrics: [
      { label: "Strefa powodziowa (ISOK)", value: flood },
      { label: "Najbliższy rów", value: ditch ? dist(ditch.w.distance_m) : "brak w promieniu 1 km" },
      { label: "Wody podziemne (GZWP)", value: d.gzwp ? "tak" : "brak / poza GZWP" },
    ],
    rows: [
      ...waters.map(({ w, i }: any) => ({ label: w.name && !(WATER_KIND[w.kind] ?? "").toLowerCase().includes(w.name.toLowerCase()) ? `${WATER_KIND[w.kind] ?? w.kind}: ${w.name}` : WATER_KIND[w.kind] ?? w.kind,
        value: dist(w.distance_m), detail: w.geometry ? "kliknij – pokaż na mapie" : "bez geometrii", mapId: w.geometry ? `water-${i}` : undefined })),
      ...(d.gzwp ? [{ label: "GZWP", value: "pod działką", detail: d.gzwp }] : []),
      ...(d.water_management_board ? [{ label: "Właściwy urząd", value: "Wody Polskie", detail: d.water_management_board }] : []),
    ],
  };
}

function vegetation(d: any): DataPayload {
  const s = (d.series ?? []).filter((o: any) => o.ndvi != null).slice(-40);
  const a = d.anomaly as number | null, na = d.ndmi_anomaly as number | null;
  return {
    raw: d,
    summary: d.in_growing_season === false ? "Poza sezonem wegetacji – stan roślin z satelity pokazujemy tylko jako historię."
      : a == null ? "Brak czystego zdjęcia satelitarnego z ostatnich tygodni."
      : a < -0.1 ? "Rośliny wyraźnie słabsze niż zwykle o tej porze roku." : a < -0.03 ? "Rośliny nieco słabsze niż zwykle." : "Rośliny w typowej kondycji dla tej pory roku.",
    series: s.map((o: any) => ({ label: dstr(o.date).slice(3), rain: 0, normal: 0, evaporation: 0, value: o.ndvi, value2: o.ndmi ?? null })),
    metrics: [
      { label: `Zieloność teraz${d.latest ? ` (${dstr(d.latest.date)})` : ""}`, value: d.latest?.ndvi != null ? nf(d.latest.ndvi, 2) : "brak", term: "NDVI" },
      { label: "Zwykle o tej porze", value: d.baseline_same_doy != null ? nf(d.baseline_same_doy, 2) : "brak" },
      { label: "Woda w liściach teraz", value: d.latest?.ndmi != null ? nf(d.latest.ndmi, 2) : "brak", term: "NDMI" },
      { label: "Woda w liściach vs norma", value: na != null ? `${na > 0 ? "+" : na < 0 ? "−" : ""}${nf(Math.abs(na), 2)}` : "brak" },
    ],
  };
}

function landCover(d: any): DataPayload {
  return {
    raw: d,
    summary: d.agricultural_share_pct != null ? `Grunty rolne: ${pct(d.agricultural_share_pct, 1)} powierzchni działki.` : "Brak danych o pokryciu terenu.",
    rows: Object.entries(d.classes ?? {}).sort((a: any, b: any) => b[1] - a[1]).map(([k, v]: any) => ({ label: k, value: `${Math.round(v)}%`, detail: "" })),
  };
}

function protectedAreas(d: any): DataPayload {
  const hits = d.hits ?? [], near = d.nearby ?? [];
  const name = (h: any) => `${h.kind}${h.name ? ` „${h.name}”` : ""}`;
  return {
    raw: d,
    summary: hits.length ? `Działka leży na obszarze chronionym: ${hits.map(name).join("; ")}. Staw, rowy czy studnia mogą wymagać uzgodnień z RDOŚ.`
      : near.length ? `Działka nie leży na obszarze chronionym. W promieniu 1 km: ${near.slice(0, 3).map((h: any) => `${name(h)}${h.distance_m != null ? ` (${dist(h.distance_m)})` : ""}`).join("; ")}.`
      : `Działka nie leży na obszarze chronionym (sprawdzono ${(d.checked_layers ?? []).length} rodzajów form ochrony przyrody).`,
    metrics: [{ label: "Na działce", value: hits.length ? `${hits.length}` : "brak" }, { label: "W promieniu 1 km", value: near.length ? `${near.length}` : "brak" }],
    rows: [...hits.map((h: any) => ({ label: h.kind, value: h.name ?? "", detail: h.code ?? "" })),
      ...near.map((h: any) => ({ label: `${h.kind} (w pobliżu)`, value: h.name ?? "", detail: h.distance_m != null ? dist(h.distance_m) : "" }))],
  };
}

function cropCalendar(d: any): DataPayload {
  return {
    raw: d,
    summary: d.crop ? `${d.crop_name_pl}: ${d.current_stage ?? "brak danych"} (${d.in_season_on_as_of ? "w sezonie" : "poza sezonem"}).`
      : "Wybierz uprawę, aby zobaczyć jej kalendarz.",
    rows: (d.stages ?? []).map((s: any) => ({ label: s.name, value: `${dstr(s.start).slice(0, 5)} – ${dstr(s.end).slice(0, 5)}`,
      detail: s.kc != null ? `Kc ${nf(s.kc, 2)}` : "" })),
  };
}

function legal(d: any): DataPayload {
  return {
    raw: d,
    summary: d.disclaimer ?? "Informacja orientacyjna, nie porada prawna.",
    rows: (d.hints ?? []).map((h: any) => ({ label: h.title ?? h.topic, value: h.requirement,
      detail: `${h.fee_pln != null ? `opłata ${nf(h.fee_pln, 2)} zł (${h.fee_year}) · ` : ""}${h.why}` })),
  };
}

function analysis(d: any): DataPayload {
  const a = d.assessment;
  return {
    raw: d,
    assessment: a ? { ...a, confidence: CONF[a.confidence] ?? a.confidence ?? "brak", field_check: a.field_check ?? null } : undefined,
    causes: (d.causes ?? []).map((c: any) => ({ ...c, share: Math.round((c.share ?? 0) * 100), explanation: c.explanation ?? "" })),
    recommendations: d.recommendations ?? [],
    irrigation: d.irrigation ?? undefined,
    water_balance: d.water_balance ?? null,
    limitations: d.limitations ?? [],
    method: d.method ?? [],
  };
}

export function adapt(b: Omit<DataBlock, "data"> & { data: any }, asOf: string): DataBlock {
  const d = b.data;
  let data: DataPayload = {};
  if (d != null) {
    switch (b.key) {
      case "weather_history": data = weatherHistory(d); break;
      case "weather_forecast": data = forecast(d); break;
      case "drought": data = drought(d, asOf); break;
      case "soil": data = soil(d); break;
      case "terrain": data = terrain(d); break;
      case "hydrology": data = hydrology(d); break;
      case "vegetation": data = vegetation(d); break;
      case "land_cover": data = landCover(d); break;
      case "protected_areas": data = protectedAreas(d); break;
      case "crop_calendar": data = cropCalendar(d); break;
      case "legal_context": data = legal(d); break;
      case "analysis": data = analysis(d); break;
      default: data = { raw: d };
    }
  }
  if (d == null || b.status === "error" || b.status === "no_data" || b.status === "not_applicable")
    data.summary = data.summary ?? (b.messages[0] ?? {
      error: "Nie udało się pobrać danych ze źródła. Pozostałe bloki działają.",
      no_data: "Źródło nie ma danych dla tej działki lub daty.",
      not_applicable: "Te dane nie dotyczą wybranej daty.",
    }[b.status as string] ?? "Brak danych.");
  return { ...b, data, provenance: b.provenance ?? [], uncertainty: b.uncertainty ?? [], messages: b.messages ?? [] };
}
