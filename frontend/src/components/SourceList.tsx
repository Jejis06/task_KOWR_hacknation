// Lista źródeł jednego bloku – wspólna dla karty bloku i panelu „Skąd te dane”.
// Zasada: linkujemy tylko adresy, które się otwierają (strona zbioru) + osobno „surowe dane” = dokładne zapytanie dla tej działki.
import type { Provenance } from "../api/types";
import { dateStr, dateTimeStr, modeLabel } from "../lib/format";

export function SourceList({ items }: { items: Provenance[] }) {
  return (
    <ul className="source-list">
      {items.map((p, i) => (
        <li key={i}>
          {p.source_url ? <a href={p.source_url} target="_blank" rel="noreferrer noopener">{p.source_name}</a> : <b>{p.source_name}</b>}
          {p.query_url && <> · <a href={p.query_url} target="_blank" rel="noreferrer noopener" title="Dokładne zapytanie, którym pobraliśmy dane dla tej działki">surowe dane dla tej działki</a></>}
          <div className="small muted">
            {modeLabel(p)} · {p.data_as_of ? `dane do ${dateStr(p.data_as_of)}` : `pobrano ${dateTimeStr(p.retrieved_at)}`}
            {p.licence ? ` · licencja: ${p.licence}` : ""}
            {!p.source_url && !p.query_url ? " · obliczenia własne lub opracowanie zespołu (bez linku)" : ""}
          </div>
          {p.notes && <div className="small">{p.notes}</div>}
        </li>
      ))}
    </ul>
  );
}
