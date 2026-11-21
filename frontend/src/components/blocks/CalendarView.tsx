import type { CropCalendarInfo } from "../../api/types";
import { Term } from "../Term";
import { dateStr, num } from "../../lib/format";

const STAGE_COLORS = ["#c9b27c", "#9dc183", "#5aa469", "#2f7d4a", "#b08a3e", "#8c6d3f", "#c7a76b"];
const day = (iso: string) => new Date(`${iso}T12:00:00`).getTime();

export function CalendarView({ d, asOf }: { d: CropCalendarInfo; asOf: string }) {
  const stages = d.stages;
  const t0 = stages.length ? Math.min(...stages.map((s) => day(s.start))) : 0;
  const t1 = stages.length ? Math.max(...stages.map((s) => day(s.end))) : 1;
  const span = Math.max(1, t1 - t0);
  const now = day(asOf);
  const markerPct = ((now - t0) / span) * 100;
  const markerInside = markerPct >= 0 && markerPct <= 100;

  return (
    <div className="view">
      <div className={`stat ${d.in_season_on_as_of ? "good" : ""}`}>
        <div className="stat-label">{d.crop ? d.crop_name_pl : "Okres wegetacji"} – stan na {dateStr(asOf)}</div>
        <div className="stat-value">{d.current_stage ?? "brak danych"}</div>
        <div className="stat-sub">{d.in_season_on_as_of ? "uprawa w sezonie" : "poza sezonem uprawy"}
          {d.sowing_ok_now != null && <> · {d.sowing_ok_now ? "teraz jest termin siewu" : "teraz nie jest termin siewu"}</>}</div>
      </div>

      {stages.length > 0 && (
        <>
          <h4>Pasek sezonu {dateStr(stages[0].start)} – {dateStr(stages[stages.length - 1].end)}</h4>
          <div className="season-bar" role="img"
            aria-label={`Fazy uprawy; dzień analizy ${dateStr(asOf)} ${markerInside ? "zaznaczony na pasku" : "poza zakresem paska"}`}>
            {stages.map((s, i) => {
              const left = ((day(s.start) - t0) / span) * 100;
              const width = Math.max(0.8, ((day(s.end) - day(s.start)) / span) * 100);
              return <span key={i} className="seg" title={`${s.name}: ${dateStr(s.start)} – ${dateStr(s.end)}`}
                style={{ left: `${left}%`, width: `${width}%`, background: STAGE_COLORS[i % STAGE_COLORS.length] }} />;
            })}
            {markerInside && <span className="marker" style={{ left: `${markerPct}%` }}><span className="marker-label">dzień analizy</span></span>}
          </div>
          {!markerInside && <p className="small muted">Dzień analizy ({dateStr(asOf)}) jest {now < t0 ? "przed" : "po"} pokazanym sezonem.</p>}
          <div className="table-wrap">
            <table className="tbl">
              <thead><tr><th>Faza</th><th>Od</th><th>Do</th><th><Term k="Kc" /></th></tr></thead>
              <tbody>{stages.map((s, i) => (
                <tr key={i} className={day(s.start) <= now && now <= day(s.end) ? "row-now" : ""}>
                  <td><span className="swatch" style={{ background: STAGE_COLORS[i % STAGE_COLORS.length] }} /> {s.name}</td>
                  <td>{dateStr(s.start)}</td><td>{dateStr(s.end)}</td><td>{s.kc != null ? num(s.kc, "", 2) : "nie dotyczy"}</td>
                </tr>))}</tbody>
            </table>
          </div>
          <p className="muted small">Fazy według <Term k="FAO-56" /> (szacunek, ±2 tygodnie); Kc mówi, ile wody zużywa uprawa w danej fazie względem parowania <Term k="ET₀" />.</p>
        </>
      )}

      {d.warnings.length > 0 && (
        <ul className="notes">{d.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
      )}
      {d.critical_water_periods.length > 0 && (
        <>
          <h4>Kiedy woda jest najważniejsza</h4>
          <ul className="list">{d.critical_water_periods.map((c, i) => <li key={i}>{c}</li>)}</ul>
        </>
      )}
      <h4>Co można siać w tym terminie</h4>
      {d.suggested_crops_now.length ? <ul className="list">{d.suggested_crops_now.map((c, i) => <li key={i}>{c}</li>)}</ul>
        : <p className="muted">Żadna z upraw w bazie nie ma teraz terminu siewu.</p>}
    </div>
  );
}
