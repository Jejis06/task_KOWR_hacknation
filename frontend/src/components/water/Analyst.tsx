import {
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ChevronDown, ChevronsDownUp, ChevronsUpDown, MapPin, Scale } from "lucide-react";
import { useRef } from "react";
import { Button } from "@/components/ui/button";
import { blockDefinitions, canShowAdvice, type DataBlock } from "@/api/client";
import { seasonRows, seasonWindow } from "@/api/adapt";
import { CropCalendarView, ForecastChart, SourceStrip, Sources, Term } from "./shared";
type Props = { blocks: Record<string, DataBlock>; onMap: (id: string) => void; loading: boolean; date: string };
const STATUS: Record<string, string> = {
  ok: "Dane kompletne", partial: "Dane częściowe", error: "Błąd źródła", no_data: "Brak danych",
  not_implemented: "W przygotowaniu", not_applicable: "Nie dotyczy",
};
function DataChart({ block }: { block: DataBlock }) {
  const vegetation = block.key === "vegetation";
  const yields = false;
  const drought = block.key === "drought";
  const forecast = block.key === "weather_forecast";
  const data = block.data.series ?? [];
  return (
    <>
      {forecast ? <ForecastChart rows={data} /> : (<>
      <div
        className="chart-box"
        role="img"
        aria-label={`${block.title}: wykres ${vegetation ? "wskaźnika zieloności" : yields ? "plonów w tonach na hektar" : "opadów i parowania w milimetrach"}. Dokładne wartości w tabeli poniżej.`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 10, right: 8, bottom: 0, left: -25 }}>
            <CartesianGrid stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              contentStyle={{
                background: "var(--card)",
                border: "1px solid var(--border)",
                borderRadius: 5,
                fontSize: 11,
              }}
            />
            {vegetation ? (
              <>
                <Line type="monotone" dataKey="value" name="Zieloność (NDVI)" stroke="var(--primary)" strokeWidth={2}
                  dot={false} isAnimationActive={false} />
                <Line type="monotone" dataKey="value2" name="Woda w liściach (NDMI)" stroke="var(--water)" strokeWidth={2}
                  strokeDasharray="5 3" dot={false} isAnimationActive={false} connectNulls />
              </>
            ) : yields ? (
              <Bar
                dataKey="value"
                name="Plon (t/ha)"
                fill="var(--primary)"
                radius={[3, 3, 0, 0]}
                isAnimationActive={false}
              >
                {data.map((r, ri) => (
                  <Cell key={`${r.label}-${ri}`} fill={r.value < 5 ? "var(--danger)" : "var(--primary)"} />
                ))}
              </Bar>
            ) : (
              <>
                <Bar
                  dataKey="rain"
                  name="Opady (mm)"
                  fill="var(--water)"
                  radius={[3, 3, 0, 0]}
                  maxBarSize={22}
                  isAnimationActive={false}
                >
                  {data.map((r, ri) => (
                    <Cell
                      key={`${r.label}-${ri}`}
                      fill={drought && r.rain < r.normal ? "var(--danger)" : "var(--water)"}
                    />
                  ))}
                </Bar>
                {forecast ? (
                  <Line
                    type="monotone"
                    dataKey="evaporation"
                    name="Parowanie (mm)"
                    stroke="var(--evaporation)"
                    strokeWidth={3.5}
                    dot={{ r: 3, fill: "var(--card)", strokeWidth: 2 }}
                    isAnimationActive={false}
                  />
                ) : (
                  <Line
                    type="monotone"
                    dataKey="normal"
                    name="Zwykłe opady (mm)"
                    stroke="var(--warning)"
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                  />
                )}
              </>
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="chart-legend">
        {vegetation ? (
          <>
            <span><i className="good" />Zieloność <Term name="NDVI" /></span>
            <span><i className="water" />Woda w liściach <Term name="NDMI" /></span>
          </>
        ) : (
          <>
            <span>
              <i />
              Deszcz
            </span>
            <span>
              <i className={forecast ? "evaporation" : "normal"} />
              {forecast ? (
                <>
                  Parowanie <Term name="ET₀" />
                </>
              ) : (
                "Zwykle"
              )}
            </span>
          </>
        )}
      </div>
      </>)}
      <details className="details-box">
        <summary>Wartości na wykresie</summary>
        <div className="details-content">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">{forecast ? "Dzień prognozy" : "Okres"}</th>
                <th scope="col">
                  {vegetation ? "Zieloność" : yields ? "Plon (t/ha)" : "Deszcz (mm)"}
                </th>
                {!vegetation && !yields && (
                  <th scope="col">{forecast ? "Parowanie (mm)" : "Zwykle (mm)"}</th>
                )}
              </tr>
            </thead>
            <tbody>
              {data.map((r, ri) => (
                <tr key={`${r.label}-${ri}`}>
                  <td>{r.label}</td>
                  <td>{vegetation || yields ? r.value : r.rain}</td>
                  {!vegetation && !yields && <td>{forecast ? r.evaporation : r.normal}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  );
}
const fmt = (v: number | null, signed = false) =>
  v == null ? "brak" : `${signed && v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toLocaleString("pl-PL")}`;

/** Sezony wegetacyjne jak arkusz: kolumny z liczbami wyrównanymi do prawej, okno = okres wegetacji uprawy. */
function SeasonTable({ weather, cal, date }: { weather: DataBlock; cal: DataBlock | undefined; date: string }) {
  const w = seasonWindow(cal?.data.raw);
  const rows = seasonRows(weather.data.raw, w, date);
  const full = rows.filter((r) => !r.partial && r.cwb != null);
  const mean = full.length ? Math.round(full.reduce((a, r) => a + (r.cwb as number), 0) / full.length) : null;
  if (!rows.length) return <p className="text-xs text-muted-foreground">Brak dziennej serii pogody – tabela sezonów niedostępna.</p>;
  return (
    <>
      <h3 className="text-xs font-semibold mt-4">Sezony wegetacyjne · {w.label}</h3>
      <div className="sheet-wrap">
        <table className="sheet-table">
          <thead>
            <tr>
              <th scope="col">Rok</th>
              <th scope="col" className="num">Opad [mm]</th>
              <th scope="col" className="num">Parowanie <Term name="ET₀" /> [mm]</th>
              <th scope="col" className="num">Bilans <Term name="KBW" /> [mm]</th>
              <th scope="col" className="num">Najdłużej bez deszczu [dni]</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.year} className={[r.dry ? "dry" : "", r.partial ? "partial" : ""].join(" ").trim()}>
                <th scope="row">{w.crossYear ? `${r.year - 1}/${String(r.year).slice(2)}` : r.year}{r.partial ? "*" : ""}</th>
                <td className="num">{fmt(r.precip)}</td>
                <td className="num">{fmt(r.et0)}</td>
                <td className={`num strong ${r.cwb != null && r.cwb < 0 ? "neg" : "pos"}`}>{fmt(r.cwb, true)}</td>
                <td className="num">{fmt(r.drySpell)}</td>
              </tr>
            ))}
          </tbody>
          {mean != null && (
            <tfoot>
              <tr><th scope="row">Średnio</th><td className="num" /><td className="num" />
                <td className="num strong">{fmt(mean, true)}</td><td className="num" /></tr>
            </tfoot>
          )}
        </table>
      </div>
      <p className="legend-note">
        <span className="swatch-dry" /> <strong>Czerwony wiersz</strong> = sezon wyraźnie suchszy niż zwykle (bilans niższy o ponad
        max(30 mm, ½ odchylenia standardowego) od średniej).
        {rows.some((r) => r.partial) && <> * sezon trwa – liczony do daty analizy.</>}
        {" "}„Najdłużej bez deszczu” = najdłuższy ciąg dni z opadem poniżej 1 mm.
        {!w.crop && " Wybierz uprawę, aby policzyć sezon dla jej okresu wegetacji."}
      </p>
    </>
  );
}

/** Formalności (prawo wodne) na górze – dla nas najważniejsze; reszta w kolejności bloków. */
const ORDER = [...blockDefinitions].sort((a, b) => Number(b.key === "legal_context") - Number(a.key === "legal_context"));

export default function Analyst({ blocks, onMap, loading, date }: Props) {
  const root = useRef<HTMLDivElement>(null);
  const setAll = (open: boolean) =>
    root.current?.querySelectorAll<HTMLDetailsElement>("details.data-acc").forEach((d) => { d.open = open; });
  return (
    <div id="data-content" role="tabpanel" aria-labelledby="data-tab" ref={root}>
    <div className="analyst-toolbar">
      <p>Kliknij kafelek, żeby zobaczyć szczegóły, wykresy i źródła.</p>
      <div>
        <Button variant="ghost" size="sm" onClick={() => setAll(true)}><ChevronsUpDown />Rozwiń wszystkie</Button>
        <Button variant="ghost" size="sm" onClick={() => setAll(false)}><ChevronsDownUp />Zwiń wszystkie</Button>
      </div>
    </div>
    <div className="analyst-grid">
      {ORDER.map((def) => {
        const b = blocks[def.key];
        if (!b)
          return loading ? (
            <div key={def.key} className="skeleton" aria-label={`Pobieranie: ${def.title}`} />
          ) : null;
        if (def.key === "analysis" && !canShowAdvice(b)) return null;
        return (
          <details
            id={`block-${def.key}`}
            key={def.key}
            className={`data-card data-acc ${def.key === "legal_context" ? "legal-highlight" : ""}`}
          >
            <summary className="data-acc-summary">
              {def.key === "legal_context" && <span className="legal-icon" aria-hidden="true"><Scale /></span>}
              <span className="data-acc-text">
                {def.key === "legal_context" && <span className="legal-kicker">Prawo wodne · ważne przed każdą budową</span>}
                <span className="data-acc-head">
                  <h2>{b.title}</h2>
                  <span className={`status-tag ${b.status === "ok" ? "" : "partial"}`}>{STATUS[b.status] ?? b.status}</span>
                </span>
                <span className="data-acc-teaser">{b.data.summary ?? b.data.assessment?.current_summary ?? b.messages.join(" ")}</span>
              </span>
              <ChevronDown size={22} aria-hidden="true" className="acc-chevron" />
            </summary>
            <div className="data-acc-body">
            {b.data.metrics && (
              <div className="metrics">
                {b.data.metrics.map((m) => (
                  <div key={m.label} className="metric">
                    <strong>{m.value}</strong>
                    <span>
                      {m.label} {m.term && <Term name={m.term} />}
                    </span>
                  </div>
                ))}
              </div>
            )}
            <SourceStrip block={b} />
            {b.data.series && <DataChart block={b} />}{" "}
            {b.key === "land_cover" &&
              b.data.rows?.map((r, ri) => (
                <div className="cause-row mt-3" key={`${r.label}-${ri}`}>
                  <div className="cause-label">
                    <span>{r.label}</span>
                    <span>{r.value}</span>
                  </div>
                  <div className="cause-bar">
                    <div className="cause-fill" style={{ width: r.value }} />
                  </div>
                </div>
              ))}
            {b.key === "crop_calendar" && <CropCalendarView block={b} asOf={date} />}
            {b.key === "weather_history" && <SeasonTable weather={b} cal={blocks["crop_calendar"]} date={date} />}
            {b.data.rows && b.key !== "land_cover" && b.key !== "crop_calendar" && b.key !== "weather_history" && (
              <>
                <h3 className="text-xs font-semibold mt-4">
                  {b.key === "hydrology" ? "Wody w okolicy – kliknij, aby wycentrować na mapie" : "Szczegóły"}
                </h3>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th scope="col">Informacja</th>
                      <th scope="col">Wartość</th>
                    </tr>
                  </thead>
                  <tbody>
                    {b.data.rows.map((r, ri) => (
                      <tr key={`${r.label}-${ri}`} className={r.dry ? "dry" : undefined}>
                        <td>
                          {r.mapId ? (
                            <Button
                              variant="link"
                              className="table-map-button"
                              onClick={() => onMap(r.mapId ?? "parcel")}
                            >
                              <MapPin />
                              {r.label}
                            </Button>
                          ) : (
                            r.label
                          )}
                        </td>
                        <td>
                          {r.value}
                          <small>{r.detail}</small>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
            {b.key === "analysis" &&
              b.data.causes?.map((c) => (
                <div key={c.key} className="cause-row mt-3">
                  <div className="cause-label">
                    <span>{c.label_pl}</span>
                    <span>{c.share}%</span>
                  </div>
                  <div className="cause-bar">
                    <div className="cause-fill" style={{ width: `${c.share}%` }} />
                  </div>
                </div>
              ))}
            <Sources block={b} />
            </div>
          </details>
        );
      })}
    </div>
    </div>
  );
}
