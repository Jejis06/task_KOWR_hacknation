// „Skąd te dane” – wymóg KOWR: daty, źródła, co na żywo, a co z kopii lokalnej, licencje, ograniczenia.
import type { BlockInfo, DataBlock } from "../api/types";
import { dateStr, dateTimeStr, modeLabel, STATUS_LABEL } from "../lib/format";

export function SourcesPanel({ infos, blocks }: { infos: BlockInfo[]; blocks: Record<string, DataBlock | "loading"> }) {
  const rows = infos.map((i) => ({ info: i, b: blocks[i.key] })).filter((r) => r.b !== undefined);
  if (!rows.length) return null;
  const limits = rows.flatMap((r) => (typeof r.b === "object" ? r.b.uncertainty.map((u) => ({ title: r.info.title, u })) : []));
  return (
    <section className="sources-panel" id="zrodla">
      <h2>Skąd te dane</h2>
      <p className="small">Każdy wynik liczymy z danych pobranych dla tej działki. „Na żywo” = pobrane teraz ze źródła;
        „pamięć podręczna” = pobrane wcześniej z tego samego źródła (do 30 dni dla dat historycznych);
        „kopia lokalna” = treści przygotowane przez zespół (prawo, procedury, kalendarz upraw) z datą opracowania.</p>
      <div className="table-wrap">
        <table className="tbl sources-tbl">
          <thead><tr><th>Blok</th><th>Stan</th><th>Źródło</th><th>Tryb</th><th>Dane z dnia</th><th>Licencja</th><th>Czas</th></tr></thead>
          <tbody>
            {rows.map(({ info, b }) => {
              if (b === "loading") return <tr key={info.key}><td>{info.title}</td><td colSpan={6} className="muted">pobieram…</td></tr>;
              const provs = b!.provenance.length ? b!.provenance : [null];
              return provs.map((p, i) => (
                <tr key={`${info.key}-${i}`}>
                  {i === 0 && <td rowSpan={provs.length}>{info.title}</td>}
                  {i === 0 && <td rowSpan={provs.length}><span className={`badge b-${b!.status}`}>{STATUS_LABEL[b!.status]}</span></td>}
                  <td>{p ? (p.source_url ? <a href={p.source_url} target="_blank" rel="noreferrer noopener">{p.source_name}</a> : p.source_name) : "—"}</td>
                  <td>{p ? modeLabel(p) : "—"}</td>
                  <td>{p ? (p.data_as_of ? dateStr(p.data_as_of) : `pobrano ${dateTimeStr(p.retrieved_at)}`) : "—"}</td>
                  <td>{p?.licence ?? "—"}</td>
                  {i === 0 && <td rowSpan={provs.length}>{b!.elapsed_ms != null ? `${(b!.elapsed_ms / 1000).toFixed(1)} s` : "—"}</td>}
                </tr>
              ));
            })}
          </tbody>
        </table>
      </div>
      {limits.length > 0 && (
        <>
          <h3>Ograniczenia analizy</h3>
          <ul className="small">{limits.map((l, i) => <li key={i}><b>{l.title}:</b> {l.u}</li>)}</ul>
        </>
      )}
    </section>
  );
}
