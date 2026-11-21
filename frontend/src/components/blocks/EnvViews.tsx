import { useMemo } from "react";
import type { ChartConfiguration } from "chart.js";
import type {
  DroughtHistory, HydrologyInfo, LandCoverInfo, ProtectedAreasInfo, SoilInfo, TerrainInfo, VegetationInfo, WaterKind,
  YieldInfo,
} from "../../api/types";
import { ChartBox, COLORS } from "../Chart";
import { Term } from "../Term";
import { dateStr, num, signed } from "../../lib/format";
import { emit, fmtDist } from "../../lib/events";

// ───────────── susza ─────────────
export function DroughtView({ d, asOf }: { d: DroughtHistory; asOf: string }) {
  const end = Number(asOf.slice(0, 4));
  const years = Array.from({ length: 11 }, (_, i) => end - 10 + i);
  const dry = new Set(d.drought_years);
  return (
    <div className="view">
      <h4>Teraz</h4>
      {d.current.length ? (
        <ul className="list">
          {d.current.map((c, i) => (
            <li key={i}><b>{c.class_label ?? String(c.value ?? "brak oceny")}</b>
              <span className="muted"> – {c.source}{c.level === "commune" ? " (gmina)" : c.level === "pixel" ? " (piksel ok. 5 km)" : ""},
                stan na {dateStr(c.date)}{typeof c.value === "number" ? `, wartość ${c.value}` : ""}</span></li>
          ))}
        </ul>
      ) : <p className="muted">Brak bieżącej oceny suszy dla tej daty.</p>}
      <h4>Lata z suszą w sezonie ({years[0]}–{end})</h4>
      <div className="timeline" role="list" aria-label="Oś czasu lat z suszą">
        {years.map((y) => (
          <div key={y} role="listitem" className={`tl-year ${dry.has(y) ? "dry" : "ok"}`} title={dry.has(y) ? `${y}: susza` : `${y}: bez suszy`}>
            <span className="tl-bar" /><span className="tl-label">{String(y).slice(2)}</span>
          </div>
        ))}
      </div>
      <p className="small"><span className="dot dry" /> susza w sezonie · <span className="dot ok" /> bez suszy
        {" "}· susza w {d.drought_years.length} z {years.length} lat</p>
      {d.history.length > 0 && (
        <details><summary>Epizody suszy ({d.history.length})</summary>
          <ul className="list small">{d.history.map((h, i) => <li key={i}>{dateStr(h.date)} – {h.class_label ?? String(h.value)} ({h.source})</li>)}</ul>
        </details>
      )}
    </div>
  );
}

// ───────────── gleba ─────────────
const SMSR_CAT: Record<string, string> = {
  I: "kategoria I – gleby bardzo lekkie (piaski): bardzo podatne na suszę, szybko przesychają",
  II: "kategoria II – gleby lekkie: podatne na suszę",
  III: "kategoria III – gleby średnie: średnio podatne na suszę",
  IV: "kategoria IV – gleby ciężkie: mało podatne na suszę, długo trzymają wodę",
};
const ROMAN = ["I", "II", "III", "IV"];

export function SoilView({ d }: { d: SoilInfo }) {
  const raw = (d.drought_category != null ? String(d.drought_category) : d.drought_susceptibility ?? "").trim();
  const cat = ROMAN.includes(raw) ? raw : ROMAN[Number(raw) - 1];
  return (
    <div className="view">
      {cat && SMSR_CAT[cat] && (
        <div className={`stat ${cat === "I" ? "bad" : cat === "II" ? "warn" : "good"}`}>
          <div className="stat-label">Podatność gleby na suszę (<Term k="SMSR" />)</div>
          <div className="stat-value">kat. {cat}</div>
          <div className="stat-sub">{SMSR_CAT[cat]}</div>
        </div>
      )}
      <dl className="kv-grid">
        <dt>Kompleks przydatności</dt><dd>{d.agri_complex ?? "brak danych"}</dd>
        <dt>Typ gleby</dt><dd>{d.soil_type ?? "brak danych"}</dd>
        <dt>Uziarnienie</dt><dd>{d.texture_class ?? "brak danych"}</dd>
        {!cat && <><dt>Podatność na suszę</dt><dd>{raw || "brak danych"}</dd></>}
        <dt>Klasy bonitacyjne (<Term k="EGiB" />)</dt><dd>{d.bonitation_classes.length ? d.bonitation_classes.join(", ") : "brak danych"}</dd>
        <dt>Zapas wody dostępnej (1 m gleby)</dt><dd>{num(d.awc_mm, "mm")}{d.awc_mm != null && <span className="muted"> – szacunek</span>}</dd>
        <dt>Skład: piasek / pył / ił</dt><dd>{d.sand_pct != null ? `${num(d.sand_pct, "%")} / ${num(d.silt_pct, "%")} / ${num(d.clay_pct, "%")}` : "brak danych"}</dd>
        <dt>Węgiel organiczny</dt><dd>{num(d.soc_g_kg, "g/kg")}</dd>
      </dl>
      {d.source_used && <p className="muted small">Źródło danych glebowych: {d.source_used}</p>}
    </div>
  );
}

// ───────────── teren ─────────────
// Mała ilustracja przekroju terenu: brązowy grunt, żółty znacznik = działka, niebieskie strzałki/woda = gdzie płynie woda.
const POS_SHAPE: Record<string, { ground: string; at: [number, number]; water?: string; arrows?: string }> = {
  hilltop: { ground: "M0 46 C20 46 34 10 48 10 C62 10 76 46 96 46 L96 52 L0 52Z", at: [48, 10], arrows: "M40 18 l-8 10 M56 18 l8 10" },
  upper_slope: { ground: "M0 48 C30 48 50 14 96 10 L96 52 L0 52Z", at: [76, 12], arrows: "M66 18 l-10 8" },
  mid_slope: { ground: "M0 48 C30 48 50 14 96 10 L96 52 L0 52Z", at: [46, 30], arrows: "M38 36 l-10 6" },
  flat: { ground: "M0 34 L96 34 L96 52 L0 52Z", at: [48, 34] },
  valley: { ground: "M0 12 C30 14 38 44 48 44 C58 44 66 14 96 12 L96 52 L0 52Z", at: [48, 44], water: "M42 44 Q48 46 54 44", arrows: "M24 20 l8 10 M72 20 l-8 10" },
  depression: { ground: "M0 26 L30 26 C38 26 40 42 48 42 C56 42 58 26 66 26 L96 26 L96 52 L0 52Z", at: [48, 37], water: "M38 35 C42 42 54 42 58 35Z", arrows: "M22 20 l8 4 M74 20 l-8 4" },
};
function TerrainIllustration({ pos }: { pos: string }) {
  const sh = POS_SHAPE[pos];
  if (!sh) return null;
  const [x, y] = sh.at;
  return (
    <svg className="pos-illu" viewBox="0 0 96 52" aria-hidden>
      <path d={sh.ground} fill="#c8b48a" stroke="#8a6d3b" strokeWidth="1.5" />
      {sh.water && <path d={sh.water} fill="#3b82f6" stroke="#1d4ed8" strokeWidth="1.5" />}
      {sh.arrows && <path d={sh.arrows} stroke="#2563eb" strokeWidth="2" strokeLinecap="round" fill="none" />}
      <rect x={x - 9} y={y - 3} width="18" height="6" rx="1.5" fill="#d4a017" stroke="#7a5a00" strokeWidth="1" />
      <path d={`M${x} ${y - 4} l0 -8`} stroke="#7a5a00" strokeWidth="1.5" /><circle cx={x} cy={y - 13} r="3" fill="#d4a017" stroke="#7a5a00" />
    </svg>
  );
}
const POS_TEXT: Record<string, string> = {
  hilltop: "Działka na wzniesieniu – woda szybko z niej spływa, gleba prędzej przesycha.",
  upper_slope: "Górna część stoku – woda spływa w dół, warto ją spowalniać.",
  mid_slope: "Stok – ryzyko spływu powierzchniowego i erozji przy ulewach.",
  flat: "Teren płaski – woda spływa powoli, decydują gleba i opady.",
  valley: "Dolina – tu spływa woda z okolicy; wilgotniej, ale możliwe podtopienia.",
  depression: "Zagłębienie (dołek) – naturalne miejsce gromadzenia wody; dobre miejsce na oczko lub zbiornik.",
};

export function TerrainView({ d }: { d: TerrainInfo }) {
  const pos = d.position ?? "";
  const slopePct = d.slope_mean_deg != null ? Math.tan((d.slope_mean_deg * Math.PI) / 180) * 100 : null;
  const nDep = d.depressions_geojson?.features?.length ?? 0;
  return (
    <div className="view">
      {pos && (
        <div className="pos">
          <TerrainIllustration pos={pos} />
          <div><b className="pos-label">{d.position_label_pl ?? pos}</b><p>{POS_TEXT[pos]}</p></div>
        </div>
      )}
      <dl className="kv-grid">
        <dt>Spadek średni</dt><dd>{num(d.slope_mean_deg, "°", 1)}{slopePct != null && ` (${num(slopePct, "%", 1)})`}</dd>
        <dt>Spadek największy</dt><dd>{num(d.slope_max_deg, "°", 1)}</dd>
        <dt>Wysokość</dt><dd>{num(d.elevation_min_m, "m n.p.m.", 1)} – {num(d.elevation_max_m, "m n.p.m.", 1)}</dd>
        <dt>Wystawa stoku</dt><dd>{d.aspect_dominant ?? "brak danych"}</dd>
        <dt>Wilgotność terenu (<Term k="TWI" />)</dt><dd>{num(d.twi_mean, "", 1)}</dd>
        <dt>Zagłębienia bezodpływowe</dt><dd>{d.depressions_geojson ? `${nDep} (pokazane na mapie)` : "brak danych"}</dd>
      </dl>
      {(nDep > 0 || (d.flow_lines_geojson?.features?.length ?? 0) > 0) && (
        <p className="small">Na mapie: <span className="swatch dep" /> zagłębienia · <span className="swatch flow" /> główne linie spływu wody.</p>
      )}
      <p className="muted small">Model terenu <Term k="NMT" /> {d.dem_resolution_m ? `${d.dem_resolution_m} m` : ""} (GUGiK).</p>
    </div>
  );
}

// ───────────── wody ─────────────
const FLOOD_TEXT: Record<string, string> = {
  "10%": "„raz na 10 lat” (10%)", "1%": "„raz na 100 lat” (1%)", "0.2%": "„raz na 500 lat” (0,2%)",
};
export const KIND: Record<WaterKind, string> = { river: "rzeka", stream: "ciek / strumień", ditch: "rów melioracyjny", lake: "jezioro",
  pond: "staw / oczko", reservoir: "zbiornik", spring: "źródło", other: "inne" };

export function HydrologyView({ d }: { d: HydrologyInfo }) {
  return (
    <div className="view">
      {/* Spokojny ton: strefa powodziowa to informacja do planowania, nie alarm (scenariusz 1% = średnio raz na 100 lat). */}
      <div className={`stat ${d.in_flood_zone || d.in_flood_hazard_area ? "info" : d.flood_zone_checked ? "good" : ""}`}>
        <div className="stat-label">Zagrożenie powodziowe z rzek (<Term k="ISOK" />)</div>
        <div className="stat-value">{!d.flood_zone_checked ? "nie sprawdzono"
          : d.in_flood_zone ? `strefa ${FLOOD_TEXT[d.in_flood_zone]}` : d.in_flood_hazard_area ? "w zasięgu mapy zagrożenia" : "poza strefą"}</div>
        <div className="stat-sub">{d.in_flood_zone || d.in_flood_hazard_area
          ? "Wynik modelu dla rzadkiej, dużej powodzi – nie bieżące zagrożenie. Ma znaczenie przy planowaniu stawu lub zbiornika (sprawdź w Wodach Polskich)."
          : d.flood_zone_checked ? "Mapy obejmują wybrane rzeki i nie pokazują podtopień po ulewach." : "Warstwa była niedostępna."}</div>
      </div>
      {d.in_groundwater_flood_area && (
        <p className="small">Teren w obszarze możliwych podtopień wodami gruntowymi (PIG-PIB) – woda gruntowa bywa tu płytko.</p>
      )}
      <h4>Wody w pobliżu</h4>
      {d.nearest_water.length ? (<>
        <div className="table-wrap"><table className="tbl"><thead><tr><th>Co</th><th>Nazwa</th><th>Odległość</th><th></th></tr></thead><tbody>
          {d.nearest_water.map((w, i) => ({ w, i })).sort((a, b) => a.w.distance_m - b.w.distance_m).map(({ w, i }) => (
            <tr key={i} id={`water-${i}`} className={w.geometry ? "clickable" : ""} tabIndex={w.geometry ? 0 : undefined}
              title={w.geometry ? "Pokaż na mapie" : "Brak geometrii – nie można pokazać na mapie"}
              onClick={() => w.geometry && emit("water:focus", { index: i })}
              onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && w.geometry && (e.preventDefault(), emit("water:focus", { index: i }))}>
              <td>{KIND[w.kind] ?? w.kind}</td><td>{w.name ?? "bez nazwy"}</td><td>{fmtDist(w.distance_m)}</td>
              <td className="small">{w.geometry ? "📍 mapa" : ""}</td></tr>
          ))}
        </tbody></table></div>
        <p className="small muted">Kliknij wiersz, aby pokazać ciek lub zbiornik na mapie.</p>
      </>) : <p className="muted">Nie znaleziono wód w promieniu analizy.</p>}
      <dl className="kv-grid">
        <dt>Woda gruntowa (pierwszy poziom, <Term k="MHP" />)</dt><dd>{d.groundwater_depth_m ?? "brak danych"}</dd>
        <dt><Term k="GZWP" /></dt><dd>{d.gzwp ?? "działka poza GZWP lub brak danych"}</dd>
        <dt>Zlewnia / <Term k="JCWP" /></dt><dd>{[d.catchment_name, d.jcwp_code].filter(Boolean).join(" · ") || "brak danych"}</dd>
        <dt>Właściwy urząd (Wody Polskie)</dt><dd>{d.water_management_board ?? "brak danych"}</dd>
      </dl>
      {d.nearest_boreholes.length > 0 && (
        <details><summary>Najbliższe otwory hydrogeologiczne ({d.nearest_boreholes.length})</summary>
          <ul className="list small">{d.nearest_boreholes.map((b, i) => (
            <li key={i}>{Object.entries(b).map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`).join(" · ")}</li>))}</ul>
        </details>
      )}
    </div>
  );
}

// ───────────── roślinność ─────────────
export function VegetationView({ d }: { d: VegetationInfo }) {
  const series = d.series.filter((s) => s.ndvi != null).slice(-60);
  const config = useMemo<ChartConfiguration>(() => ({
    type: "line",
    data: { labels: series.map((s) => dateStr(s.date)), datasets: [
      { label: "NDVI", data: series.map((s) => s.ndvi), borderColor: COLORS.green, backgroundColor: "rgba(10,125,50,.15)", fill: true, pointRadius: 1.5, tension: 0.3 },
    ] },
    options: { plugins: { legend: { display: false } }, scales: { y: { min: 0, max: 1, title: { display: true, text: "NDVI (0–1)" } }, x: { ticks: { maxTicksLimit: 6 } } } },
  }), [series]);
  const a = d.anomaly;
  return (
    <div className="view">
      <div className="stats">
        <div className={`stat ${a == null ? "" : a < -0.1 ? "bad" : a < -0.03 ? "warn" : "good"}`}>
          <div className="stat-label"><Term k="NDVI" /> teraz</div>
          <div className="stat-value">{d.latest?.ndvi != null ? num(d.latest.ndvi, "", 2) : "brak danych"}</div>
          <div className="stat-sub">{d.latest ? `zdjęcie z ${dateStr(d.latest.date)}${d.latest_age_days != null ? ` (${d.latest_age_days} dni temu)` : ""}` : "brak czystego zdjęcia"}</div>
        </div>
        <div className="stat">
          <div className="stat-label">Zwykle o tej porze (10 lat)</div>
          <div className="stat-value">{num(d.baseline_same_doy, "", 2)}</div>
          <div className="stat-sub">różnica: {a != null ? signed(a, "", 2) : "brak danych"}{a != null && a < -0.03 ? " – rośliny słabsze niż zwykle" : ""}</div>
        </div>
      </div>
      {series.length > 1 && <ChartBox config={config} height={160} label="Przebieg NDVI z satelity Sentinel-2" />}
      {d.in_growing_season === false && <p className="small warn-text">Poza sezonem wegetacji NDVI słabo opisuje stan upraw.</p>}
    </div>
  );
}

// ───────────── użytkowanie terenu ─────────────
export function LandCoverView({ d }: { d: LandCoverInfo }) {
  const entries = Object.entries(d.classes).sort((a, b) => b[1] - a[1]);
  return (
    <div className="view">
      <p>Grunty rolne: <b>{num(d.agricultural_share_pct, "%", 1)}</b> powierzchni działki</p>
      <div className="bars">
        {entries.map(([k, v]) => (
          <div key={k} className="bar-row"><span className="bar-label">{k}</span>
            <span className="bar-track"><span className="bar-fill" style={{ width: `${Math.min(100, v)}%` }} /></span>
            <span className="bar-val">{num(v, "%", 1)}</span></div>
        ))}
      </div>
      {d.source_used && <p className="muted small">Źródło: {d.source_used}</p>}
    </div>
  );
}

// ───────────── plony ─────────────
export function YieldsView({ d }: { d: YieldInfo }) {
  const rows = [...d.official].sort((a, b) => a.year - b.year);
  const unit = rows[0]?.unit_name ?? rows[0]?.level;
  const config = useMemo<ChartConfiguration>(() => ({
    type: "bar",
    data: { labels: rows.map((r) => String(r.year)), datasets: [{ label: `${rows[0]?.crop ?? ""} [t/ha]`, data: rows.map((r) => r.yield_t_ha), backgroundColor: COLORS.green }] },
    options: { plugins: { legend: { position: "bottom" } }, scales: { y: { title: { display: true, text: "t/ha" } } } },
  }), [rows]);
  return (
    <div className="view">
      <p className="callout">Uwaga: to średnie plony <Term k="GUS" /> – {rows[0]?.level === "voivodeship" ? "województwo" : "powiat"}{unit ? ` (${unit})` : ""}, <b>nie Twoje pole</b>.</p>
      {rows.length ? <ChartBox config={config} height={180} label="Plony średnie w powiecie" /> : <p className="muted">Brak danych GUS dla tej uprawy.</p>}
      {d.parcel_productivity_index.length > 0 && (
        <p className="small">Wskaźnik z satelity dla działki (szczyt NDVI w sezonie): {d.parcel_productivity_index.map((p) => `${p.year}: ${p.peak_ndvi ?? "–"}`).join(" · ")}</p>
      )}
      {d.note && <p className="muted small">{d.note}</p>}
    </div>
  );
}

// ───────────── obszary chronione ─────────────
export function ProtectedView({ d }: { d: ProtectedAreasInfo }) {
  return (
    <div className="view">
      {d.hits.length ? (
        <ul className="list">{d.hits.map((h, i) => <li key={i}><b>{h.kind}</b>{h.name ? ` – ${h.name}` : ""}{h.code ? ` (${h.code})` : ""}</li>)}</ul>
      ) : <p className="good-text">Działka nie leży na żadnym ze sprawdzonych obszarów chronionych.</p>}
      {(d.nearby ?? []).length > 0 && (
        <><h4>W pobliżu (do 1 km)</h4>
          <ul className="list small">{d.nearby!.map((h, i) => <li key={i}><b>{h.kind}</b>{h.name ? ` – ${h.name}` : ""}{h.code ? ` (${h.code})` : ""}
            {h.distance_m != null ? ` · ${fmtDist(h.distance_m)}` : ""}</li>)}</ul></>
      )}
      {d.hits.some((h) => /natura/i.test(h.kind)) && <p className="small">Natura 2000 nie zakazuje inwestycji, ale zbiornik czy melioracje mogą wymagać uzgodnień z <Term k="RDOŚ" />.</p>}
      <p className="muted small">Sprawdzone warstwy: {d.checked_layers.join(", ") || "brak informacji"}.</p>
    </div>
  );
}
