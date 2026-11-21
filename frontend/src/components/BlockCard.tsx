import type { BlockInfo, DataBlock, WeatherHistory } from "../api/types";

const STATUS_LABEL: Record<string, string> = {
  ok: "dane kompletne", partial: "dane częściowe", no_data: "brak danych", not_applicable: "nie dotyczy",
  error: "błąd źródła", not_implemented: "w przygotowaniu", loading: "pobieram…",
};

function WeatherSummary({ d }: { d: WeatherHistory }) {
  const last = d.seasons[d.seasons.length - 1];
  return (
    <ul className="kv">
      <li>Opad ostatnie 30 dni: <b>{d.last_30d_precip_mm ?? "–"} mm</b> (norma {d.last_30d_precip_normal_mm ?? "–"} mm)</li>
      <li>Bilans wodny 60 dni (opad − parowanie): <b>{d.cwb_60d_mm ?? "–"} mm</b> (norma {d.cwb_60d_normal_mm ?? "–"} mm)</li>
      {last && <li>Sezon {last.year}: opad IV–IX {last.precip_apr_sep_mm} mm, najdłuższa susza {last.longest_dry_spell_days} dni</li>}
      <li className="muted">Źródło: {d.provider}, {d.grid_resolution_note}, {d.start} → {d.end}</li>
    </ul>
  );
}

export function BlockCard({ info, block }: { info: BlockInfo; block?: DataBlock | "loading" }) {
  const status = block === undefined ? "idle" : block === "loading" ? "loading" : block.status;
  const b = typeof block === "object" ? block : null;
  return (
    <article className={`card status-${status}`}>
      <header>
        <h3>{info.title}</h3>
        {status !== "idle" && <span className="badge">{STATUS_LABEL[status] ?? status}</span>}
      </header>
      {b?.data != null && b.key === "weather_history" && <WeatherSummary d={b.data as WeatherHistory} />}
      {b?.data != null && (
        <details>
          <summary>Wszystkie dane (JSON)</summary>
          <pre>{JSON.stringify(b.data, null, 1).slice(0, 20000)}</pre>
        </details>
      )}
      {b && b.uncertainty.length > 0 && (
        <ul className="uncertainty">{b.uncertainty.map((u, i) => <li key={i}>⚠ {u}</li>)}</ul>
      )}
      {b && b.messages.length > 0 && <ul className="messages">{b.messages.map((m, i) => <li key={i}>{m}</li>)}</ul>}
      {b && b.provenance.length > 0 && (
        <footer className="prov">
          {b.provenance.map((p, i) => (
            <span key={i}>
              {p.source_name} · {p.mode === "live" ? "na żywo" : p.mode === "cached" ? "z pamięci podręcznej" : `kopia lokalna ${p.snapshot_date ?? ""}`}
              {p.data_as_of ? ` · dane do ${p.data_as_of}` : ""}{p.licence ? ` · ${p.licence}` : ""}
            </span>
          ))}
          {b.elapsed_ms != null && <span className="muted"> · {b.elapsed_ms} ms</span>}
        </footer>
      )}
    </article>
  );
}
