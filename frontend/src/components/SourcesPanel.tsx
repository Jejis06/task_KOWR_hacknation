// „Skąd te dane” – wymóg KOWR: daty, źródła, co na żywo, a co z kopii lokalnej, licencje, ograniczenia.
// Wszystko domyślnie zwinięte: cały panel i każdy blok osobno (rozwijane przed drukiem – patrz ParcelPage).
import type { BlockInfo, DataBlock } from "../api/types";
import { STATUS_LABEL } from "../lib/format";
import { SourceList } from "./SourceList";

export function SourcesPanel({ infos, blocks }: { infos: BlockInfo[]; blocks: Record<string, DataBlock | "loading"> }) {
  const rows = infos.map((i) => ({ info: i, b: blocks[i.key] })).filter((r) => r.b !== undefined);
  if (!rows.length) return null;
  const nSources = rows.reduce((a, r) => a + (typeof r.b === "object" ? r.b.provenance.length : 0), 0);
  const limits = rows.flatMap((r) => (typeof r.b === "object" ? r.b.uncertainty.map((u) => ({ title: r.info.title, u })) : []));
  return (
    <details className="sources-panel" id="zrodla">
      <summary><h2>Skąd te dane</h2> <span className="muted small">({nSources} źródeł w {rows.length} blokach – kliknij, aby rozwinąć)</span></summary>
      <p className="small">Każdy wynik liczymy z danych pobranych dla tej działki. Nazwa źródła prowadzi do strony zbioru danych;
        „surowe dane dla tej działki” otwiera dokładnie to zapytanie, którym pobraliśmy dane (tam, gdzie źródło na to pozwala).
        „Na żywo” = pobrane teraz; „pamięć podręczna” = pobrane wcześniej z tego samego źródła; „kopia lokalna” = treści
        przygotowane przez zespół (prawo, procedury, kalendarz upraw) z datą opracowania.</p>
      {rows.map(({ info, b }) => (
        <details key={info.key} className="source-block">
          <summary>
            <b>{info.title}</b>{" "}
            {b === "loading" ? <span className="muted">pobieram…</span> : <>
              <span className={`badge b-${b!.status}`}>{STATUS_LABEL[b!.status]}</span>
              <span className="muted small"> · {b!.provenance.length ? `${b!.provenance.length} źr.` : "bez źródła"}
                {b!.elapsed_ms != null ? ` · ${(b!.elapsed_ms / 1000).toFixed(1)} s` : ""}</span>
            </>}
          </summary>
          {typeof b === "object" && (b.provenance.length ? <SourceList items={b.provenance} /> : <p className="small muted">Brak danych ze źródła.</p>)}
        </details>
      ))}
      {limits.length > 0 && (
        <details className="source-block">
          <summary><b>Ograniczenia analizy</b> <span className="muted small">({limits.length})</span></summary>
          <ul className="small">{limits.map((l, i) => <li key={i}><b>{l.title}:</b> {l.u}</li>)}</ul>
        </details>
      )}
    </details>
  );
}
