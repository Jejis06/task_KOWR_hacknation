import type { LegalContextInfo, LegalHint } from "../../api/types";
import { useKnowledge, type Procedure } from "../../api/knowledge";
import { KNOWLEDGE_STATUS_LABEL, num } from "../../lib/format";
import { Term } from "../Term";

const GROUPS: { key: NonNullable<LegalHint["group"]>; title: string; icon: string; cls: string }[] = [
  { key: "none", title: "Co możesz zrobić bez formalności", icon: "✓", cls: "g-none" },
  { key: "notification", title: "Co wymaga zgłoszenia wodnoprawnego", icon: "✉", cls: "g-notif" },
  { key: "permit", title: "Co wymaga pozwolenia wodnoprawnego", icon: "§", cls: "g-permit" },
  { key: "depends", title: "Zależy od sytuacji – sprawdź przed robotami", icon: "?", cls: "g-dep" },
];

function KStatus({ s }: { s: string }) {
  return <span className={`kstatus ks-${s}`} title="Status wiedzy w naszej bazie">{KNOWLEDGE_STATUS_LABEL[s] ?? s}</span>;
}

function Sources({ urls }: { urls: string[] }) {
  if (!urls.length) return null;
  return (
    <p className="small sources">Źródła: {urls.map((u, i) => (
      <span key={u}>{i > 0 && ", "}{/^https?:/.test(u) ? <a href={u} target="_blank" rel="noreferrer noopener">{new URL(u).hostname}</a> : u}</span>
    ))}</p>
  );
}

function ProcedureSteps({ p }: { p: Procedure }) {
  return (
    <details className="procedure">
      <summary>Krok po kroku: {p.title}</summary>
      {p.organ && <p><b>Gdzie:</b> {p.organ}</p>}
      {p.when && <p><b>Kiedy:</b> {p.when}</p>}
      {p.how_to_submit && <p><b>Jak złożyć:</b> {p.how_to_submit}</p>}
      {p.steps && p.steps.length > 0 && <ol>{p.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>}
      {p.attachments && p.attachments.length > 0 && <><b>Załączniki:</b><ul>{p.attachments.map((a, i) => <li key={i}>{a}</li>)}</ul></>}
      {p.typical_duration && <p><b>Ile trwa:</b> {p.typical_duration} {p.typical_duration_status && <KStatus s={p.typical_duration_status} />}</p>}
      {p.notes && <p className="small">{p.notes}</p>}
      {p.form_url && <p><a className="btn-link" href={p.form_url} target="_blank" rel="noreferrer noopener">📄 {p.form_title ?? "Wzór wniosku"}</a></p>}
      <Sources urls={p.sources ?? []} />
    </details>
  );
}

function HintCard({ h }: { h: LegalHint }) {
  const k = useKnowledge();
  const proc = h.procedure_id ? k.procedures[h.procedure_id] : undefined;
  return (
    <article className="lhint">
      <header><h5>{h.title ?? h.topic}</h5><KStatus s={h.status} /></header>
      <p className="req">Wymóg: <b>{h.requirement}</b>{h.fee_pln != null && <> · opłata {num(h.fee_pln, "zł", 2)}{h.fee_year ? ` (stawka ${h.fee_year})` : ""}</>}</p>
      {h.caution && <p className="caution">⚠ {h.caution}</p>}
      <p>{h.why}</p>
      {h.facts_used && h.facts_used.length > 0 && (
        <ul className="facts">{h.facts_used.map((f, i) => <li key={i}>📍 {f}</li>)}</ul>
      )}
      {h.unchecked && h.unchecked.length > 0 && (
        <p className="small warn-text">Nie sprawdziliśmy: {h.unchecked.join("; ")}.</p>
      )}
      {proc && <ProcedureSteps p={proc} />}
      <Sources urls={h.sources} />
    </article>
  );
}

export function LegalView({ d, asOf }: { d: LegalContextInfo; asOf: string }) {
  const k = useKnowledge();
  const year = Number(asOf.slice(0, 4));
  const groups = GROUPS.map((g) => ({ ...g, hints: d.hints.filter((h) => (h.group ?? "depends") === g.key) })).filter((g) => g.hints.length);
  return (
    <div className="view">
      <p className="callout">{d.disclaimer ?? k.disclaimer ?? "Informacja orientacyjna, nie porada prawna."}{" "}
        Nigdy nie zakładaj, że zgoda „na pewno” nie jest potrzebna – w razie wątpliwości zapytaj Nadzór Wodny Wód Polskich.</p>
      {d.facts_checked && Object.keys(d.facts_checked).length > 0 && (
        <p className="small">Sprawdzone fakty o działce: {Object.entries(d.facts_checked).map(([kk, v]) => `${kk} – ${v}`).join("; ")}.</p>
      )}
      {groups.map((g) => (
        <section key={g.key} className={`legal-group ${g.cls}`}>
          <h4><span className="gicon" aria-hidden>{g.icon}</span> {g.title}</h4>
          {g.hints.map((h, i) => <HintCard key={i} h={h} />)}
        </section>
      ))}

      <section className="legal-group g-fund">
        <h4><span className="gicon" aria-hidden>zł</span> Dofinansowania dla rolnika</h4>
        {d.funding_ids.length ? (
          <ul className="funding">
            {d.funding_ids.map((id) => {
              const f = k.funding[id];
              return (
                <li key={id}>
                  <b>{f?.name ?? id}</b> {f && <KStatus s={f.status} />}
                  {f?.scope && <div>{f.scope}</div>}
                  {f?.call && <div className="small">Nabór: {f.call}</div>}
                  {f?.open_question && <div className="small warn-text">Do sprawdzenia: {f.open_question}</div>}
                  <Sources urls={f?.sources ?? []} />
                </li>
              );
            })}
          </ul>
        ) : <p className="muted">Brak programów w bazie.</p>}
        <p className="small muted">Większość dotacji <Term k="ARiMR" /> to refundacja: najpierw płacisz sam, zwrot po rozliczeniu. Inwestycja trwale związana z gruntem – tylko na własnym gruncie.</p>
      </section>

      {k.eu.length > 0 && (
        <details className="legal-group">
          <summary><b>Skąd te przepisy – prawo UE ({k.eu.length})</b></summary>
          <ul className="list small">{k.eu.map((e) => (
            <li key={e.id}><b>{e.short}</b> ({e.celex && k.eurlexPattern ?
              <a href={k.eurlexPattern.replace("{celex}", e.celex)} target="_blank" rel="noreferrer noopener">{e.act}</a> : e.act})
              {e.farmer_impact ? ` – ${e.farmer_impact}` : e.relevance ? ` – ${e.relevance}` : ""}</li>))}</ul>
        </details>
      )}
      <p className="muted small">Opłaty administracyjne pokazujemy według stawek na rok daty analizy ({year}); jeśli brak stawki na ten rok – najbliższa znana z podanym rokiem.</p>
    </div>
  );
}
