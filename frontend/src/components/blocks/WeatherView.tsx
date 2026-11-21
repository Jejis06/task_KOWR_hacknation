import { useMemo } from "react";
import type { ChartConfiguration } from "chart.js";
import type { WeatherForecast, WeatherHistory } from "../../api/types";
import { ChartBox, COLORS } from "../Chart";
import { Term } from "../Term";
import { dateStr, MONTHS_SHORT, num, signed } from "../../lib/format";

/** Miesięczne sumy opadu z serii dziennej (tylko miesiące z danymi). */
function monthlySums(d: WeatherHistory) {
  const map = new Map<string, { p: number; e: number; n: number }>();
  d.daily.dates.forEach((date, i) => {
    const k = date.slice(0, 7);
    const m = map.get(k) ?? { p: 0, e: 0, n: 0 };
    const p = d.daily.precip_mm[i], e = d.daily.et0_mm[i];
    if (p != null) { m.p += p; m.n += 1; }
    if (e != null) m.e += e;
    map.set(k, m);
  });
  return [...map.entries()].map(([k, v]) => ({ month: k, p: Math.round(v.p), e: Math.round(v.e), n: v.n }));
}

function Kbw60({ d }: { d: WeatherHistory }) {
  if (d.cwb_60d_mm == null) return <p className="muted">Bilans wodny z 60 dni: brak danych.</p>;
  const diff = d.cwb_60d_normal_mm != null ? d.cwb_60d_mm - d.cwb_60d_normal_mm : null;
  const tone = diff == null ? "" : diff < -40 ? "bad" : diff < -15 ? "warn" : "good";
  return (
    <div className={`stat ${tone}`}>
      <div className="stat-label"><Term k="KBW" /> – ostatnie 60 dni do {dateStr(d.end)}</div>
      <div className="stat-value">{signed(d.cwb_60d_mm, "mm")}</div>
      <div className="stat-sub">
        norma dla tego okresu: {signed(d.cwb_60d_normal_mm, "mm")}
        {diff != null && <> · {diff < 0 ? "sucho: " : "wilgotniej niż zwykle: "}<b>{signed(diff, "mm")}</b> względem normy</>}
      </div>
    </div>
  );
}

export function WeatherView({ d, asOf }: { d: WeatherHistory; asOf: string }) {
  const sums = useMemo(() => monthlySums(d), [d]);
  const normal = useMemo(() => new Map(d.monthly_climatology.map((m) => [m.month, m])), [d]);

  const tenYears = useMemo<ChartConfiguration>(() => ({
    type: "bar",
    data: {
      labels: sums.map((s) => `${MONTHS_SHORT[+s.month.slice(5) - 1]} ${s.month.slice(0, 4)}`),
      datasets: [
        { type: "bar", label: "opad w miesiącu [mm]", data: sums.map((s) => s.p), backgroundColor: COLORS.rain, borderWidth: 0 },
        { type: "line", label: "norma 10-letnia [mm]", data: sums.map((s) => normal.get(+s.month.slice(5))?.precip_mean_mm ?? null),
          borderColor: COLORS.normal, borderWidth: 1.5, pointRadius: 0, tension: 0.3 },
      ],
    },
    options: { plugins: { legend: { position: "bottom" } }, scales: { x: { ticks: { maxTicksLimit: 11, autoSkip: true } }, y: { title: { display: true, text: "mm" } } } },
  }), [sums, normal]);

  const year = asOf.slice(0, 4);
  const thisYear = sums.filter((s) => s.month.startsWith(year));
  const season = useMemo<ChartConfiguration>(() => ({
    type: "bar",
    data: {
      labels: thisYear.map((s) => MONTHS_SHORT[+s.month.slice(5) - 1]),
      datasets: [
        { label: `opad ${year} [mm]`, data: thisYear.map((s) => s.p), backgroundColor: COLORS.rain },
        { label: "norma [mm]", data: thisYear.map((s) => normal.get(+s.month.slice(5))?.precip_mean_mm ?? null), backgroundColor: COLORS.rainLight },
        { label: `parowanie ET₀ ${year} [mm]`, data: thisYear.map((s) => s.e), backgroundColor: "rgba(194,65,12,.55)" },
      ],
    },
    options: { plugins: { legend: { position: "bottom" } }, scales: { y: { title: { display: true, text: "mm" } } } },
  }), [thisYear, normal, year]);

  const seasons = [...d.seasons].sort((a, b) => b.year - a.year);
  const worst = d.seasons.reduce<number | null>((m, s) => (s.cwb_apr_sep_mm != null && (m == null || s.cwb_apr_sep_mm < m) ? s.cwb_apr_sep_mm : m), null);

  return (
    <div className="view">
      <div className="stats">
        <Kbw60 d={d} />
        <div className="stat">
          <div className="stat-label">Opad – ostatnie 30 dni</div>
          <div className="stat-value">{num(d.last_30d_precip_mm, "mm")}</div>
          <div className="stat-sub">norma: {num(d.last_30d_precip_normal_mm, "mm")}</div>
        </div>
      </div>

      <h4>Opady miesięczne – 10 lat ({dateStr(d.start)} – {dateStr(d.end)})</h4>
      {sums.length ? <ChartBox config={tenYears} height={220} label="Miesięczne sumy opadu z 10 lat na tle normy" />
        : <p className="muted">Brak serii dziennej – wykres niedostępny.</p>}

      <h4>Rok {year} na tle normy</h4>
      {thisYear.length ? <ChartBox config={season} height={200} label={`Opad i parowanie w ${year} na tle normy`} />
        : <p className="muted">Brak danych dla roku {year}.</p>}

      <h4>Sezony wegetacyjne (kwiecień–wrzesień)</h4>
      <div className="table-wrap">
        <table className="tbl">
          <thead><tr><th>Rok</th><th>Opad</th><th>Parowanie <Term k="ET₀" /></th><th><Term k="KBW" /></th><th>Najdłużej bez deszczu</th></tr></thead>
          <tbody>
            {seasons.map((s) => (
              <tr key={s.year} className={s.cwb_apr_sep_mm != null && s.cwb_apr_sep_mm === worst ? "row-bad" : ""}>
                <td>{s.year}</td><td>{num(s.precip_apr_sep_mm, "mm")}</td><td>{num(s.et0_apr_sep_mm, "mm")}</td>
                <td>{signed(s.cwb_apr_sep_mm, "mm")}</td><td>{num(s.longest_dry_spell_days, "dni")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small">Najsuchszy sezon wyróżniony. „Bez deszczu” = kolejne dni z opadem poniżej 1 mm.
        Dane pogodowe: {d.provider}; {d.grid_resolution_note}.</p>
    </div>
  );
}

export function ForecastView({ d }: { d: WeatherForecast }) {
  const sumP = d.precip_mm.reduce<number>((a, v) => a + (v ?? 0), 0);
  const sumE = d.et0_mm.reduce<number>((a, v) => a + (v ?? 0), 0);
  const config = useMemo<ChartConfiguration>(() => ({
    type: "bar",
    data: {
      labels: d.dates.map((x) => dateStr(x).slice(0, 5)),
      datasets: [
        { type: "bar", label: "opad [mm]", data: d.precip_mm, backgroundColor: COLORS.rain },
        { type: "line", label: "parowanie ET₀ [mm]", data: d.et0_mm, borderColor: COLORS.et0, pointRadius: 2 },
      ],
    },
    options: { plugins: { legend: { position: "bottom" } }, scales: { y: { title: { display: true, text: "mm/dzień" } } } },
  }), [d]);
  return (
    <div className="view">
      <div className="stats">
        <div className="stat"><div className="stat-label">Opad w prognozie ({d.dates.length} dni)</div><div className="stat-value">{num(sumP, "mm", 1)}</div></div>
        <div className="stat"><div className="stat-label">Parowanie <Term k="ET₀" /></div><div className="stat-value">{num(sumE, "mm", 1)}</div>
          <div className="stat-sub">bilans: {signed(sumP - sumE, "mm", 1)}</div></div>
      </div>
      <ChartBox config={config} height={180} label="Prognoza opadu i parowania" />
      <p className="muted small">Prognoza od {dateStr(d.dates[0])} do {dateStr(d.dates[d.dates.length - 1])} ({d.provider}).</p>
    </div>
  );
}
