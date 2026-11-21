import { useState, type ReactNode } from "react";
import { CircleHelp, FileText, Info, RotateCcw, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { DataBlock, Evidence } from "@/api/client";
export const formatDate = (date: string | null | undefined) =>
  date
    ? new Intl.DateTimeFormat("pl-PL", { day: "2-digit", month: "2-digit", year: "numeric" }).format(
        new Date(`${date.slice(0, 10)}T12:00:00Z`),
      )
    : "brak daty";
const definitions: Record<string, string> = {
  "Pewność oceny":
    "Średnia pewność oznacza, że dane wskazują możliwy problem, ale brakuje pomiarów z Twojego pola. Sprawdź wilgotność gleby i stan rowu przed podjęciem decyzji.",
  "Wybór uprawy":
    "Wybierz roślinę, aby zobaczyć jej kalendarz i okres największej potrzeby wody. Możesz pozostawić pole bez wyboru.",
  KBW: "Klimatyczny bilans wodny: deszcz minus woda tracona przez parowanie. Wynik ujemny oznacza, że więcej wody ubywa, niż przybywa. To nie jest bezpośredni pomiar wilgotności gleby.",
  NDVI: "Wskaźnik zieloności roślin na zdjęciu satelitarnym. Wyższy wynik zwykle oznacza bujniejszą roślinność. Sam wynik nie wyjaśnia przyczyny słabszego wzrostu.",
  "ET₀":
    "Szacowana ilość wody, którą pogoda może odebrać glebie i roślinom przez parowanie. Rzeczywista utrata zależy też od uprawy.",
  SMSR: "System Monitoringu Suszy Rolniczej: ocenia zagrożenie suszą na podstawie pogody, gleby i uprawy.",
  Retencja:
    "Zatrzymywanie wody tam, gdzie spadła: w glebie, obniżeniach pola, rowach i zbiornikach.",
  NDMI: "Wskaźnik wody w liściach z satelity Sentinel-2 (pasma bliskiej i krótkofalowej podczerwieni). Spada, zanim rośliny zżółkną – to pomiar z Twojego pola, a nie z modelu pogody.",
  "KBW × NDMI":
    "Porównujemy przyczynę ze skutkiem: bilans wody z pogody (siatka ok. 10 km) z wodą w liściach na Twoim polu (20 m). Zgodność podnosi pewność oceny, rozbieżność wskazuje problem lokalny albo pole, które dobrze trzyma wodę.",
  "Bilans FAO-56":
    "Codzienny rachunek wody w strefie korzeni wg FAO-56 (Organizacja Narodów Zjednoczonych ds. Wyżywienia i Rolnictwa): ile wody ubyło z gleby przez parowanie uprawy i ile dopłynęło z deszczem. Gdy ubytek przekroczy wodę łatwo dostępną, roślina ogranicza parowanie i plon.",
  "Pozwolenie wodnoprawne":
    "Zgoda urzędu na określone prace lub korzystanie z wody. To, czy jest potrzebna, zależy od miejsca i rodzaju działania.",
};
export function Term({ name }: { name: string }) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          className="term-trigger"
          aria-label={`Wyjaśnienie: ${name}`}
          title={`Co oznacza ${name}?`}
        >
          <CircleHelp />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="popover-content">
        <strong>{name}</strong>
        <p className="mt-2">
          {definitions[name] ??
            "Wartość szacunkowa. Szczegóły i ograniczenia znajdziesz w źródłach tego bloku."}
        </p>
      </PopoverContent>
    </Popover>
  );
}
function srcLabel(block: DataBlock | undefined) {
  const p = block?.provenance[0];
  if (!p) return null;
  return { name: p.source_name, url: p.source_url, date: p.data_as_of ?? p.snapshot_date ?? p.retrieved_at };
}
export function SourceLine({ block, label }: { block: DataBlock | undefined; label?: string }) {
  const s = srcLabel(block);
  if (!s) return null;
  return (
    <div className="source-line">
      <Info size={10} />
      <span>
        {label ? `${label} · ` : ""}
        {s.url ? (
          <a href={s.url} target="_blank" rel="noreferrer" className="underline">{s.name}</a>
        ) : (
          s.name
        )}{" "}
        · dane: {formatDate(s.date)}
      </span>
    </div>
  );
}
export function Sources({ block }: { block: DataBlock | undefined }) {
  if (!block || (!block.provenance.length && !block.uncertainty.length)) return null;
  return (
    <details className="details-box">
      <summary>
        <FileText size={13} /> Źródła i niepewność
      </summary>
      <div className="details-content">
        {block.provenance.map((p, i) => (
          <div key={i} className="mb-3">
            <strong>
              {p.source_url ? (
                <a href={p.source_url} target="_blank" rel="noreferrer" className="underline">{p.source_name}</a>
              ) : (
                p.source_name
              )}
            </strong>
            <p>
              Dane na dzień: {formatDate(p.data_as_of ?? p.snapshot_date)}. Pobranie: {formatDate(p.retrieved_at)}.
            </p>
            <p>
              {p.licence ?? "licencja: brak informacji"} ·{" "}
              {p.mode === "local_snapshot" ? "Baza wiedzy zespołu" : p.mode === "live" ? "Dane pobrane teraz" : "Dane pobrane wcześniej (pamięć podręczna)"}
            </p>
            {p.notes && <p>{p.notes}</p>}
            {p.query_url && (
              <a href={p.query_url} target="_blank" rel="noreferrer" className="underline">Surowe dane dla tej działki</a>
            )}
          </div>
        ))}
        {block.uncertainty.length > 0 && (
          <ul>
            {block.uncertainty.map((s) => <li key={s}>{s}</li>)}
          </ul>
        )}
      </div>
    </details>
  );
}

/**
 * Karta, która po kliknięciu wyraźnego przycisku „Skąd to wiemy?” obraca się wokół osi poziomej (OX)
 * i na odwrocie pokazuje dane, na których opiera się stwierdzenie (liczba + blok + data + źródło).
 */
export function FlipCard({
  children,
  items,
  blocks,
  className = "",
  label = "Skąd to wiemy?",
}: {
  children: ReactNode;
  items: Evidence[];
  blocks: Record<string, DataBlock>;
  className?: string;
  label?: string;
}) {
  const [flipped, setFlipped] = useState(false);
  if (!items.length) return <div className={className}>{children}</div>;
  return (
    <div className={`flip ${flipped ? "is-flipped" : ""} ${className}`}>
      <div className="flip-inner">
        <div className="flip-face flip-front" aria-hidden={flipped}>
          {children}
          <button type="button" className="source-chip" onClick={() => setFlipped(true)} tabIndex={flipped ? -1 : 0}
            aria-label={`${label} – pokaż dane i źródła`}>
            <Search size={13} /> {label}
          </button>
        </div>
        <div className="flip-face flip-back" aria-hidden={!flipped}>
          <div className="flip-back-head">
            <span className="flip-back-title"><FileText size={14} /> Na czym to opieramy</span>
            <button type="button" className="source-chip back" onClick={() => setFlipped(false)} tabIndex={flipped ? 0 : -1}>
              <RotateCcw size={13} /> Wróć
            </button>
          </div>
          <ul className="flip-evidence">
            {items.map((e, i) => {
              const b = e.block ? blocks[e.block] : undefined;
              const s = srcLabel(b);
              return (
                <li key={i}>
                  <span className="ev-text">{e.text}</span>
                  <span className="ev-meta">
                    {b?.title ?? e.block ?? "obliczenia własne"} · dane: {formatDate(s?.date)}
                    {s && <> · {s.url ? <a href={s.url} target="_blank" rel="noreferrer">{s.name}</a> : s.name}</>}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    </div>
  );
}

export function EvidenceList({
  items,
  blocks,
  title = "Na czym opieramy tę ocenę?",
}: {
  items: Evidence[];
  blocks: Record<string, DataBlock>;
  title?: string;
}) {
  if (!items.length) return null;
  return (
    <details className="details-box">
      <summary>
        <FileText size={13} />
        {title}
      </summary>
      <div className="details-content">
        <ul>
          {items.map((e, i) => {
            const b = e.block ? blocks[e.block] : undefined;
            return (
              <li className="evidence-item" key={i}>
                {e.text}
                <small>
                  {b?.title ?? e.block ?? "obliczenia własne"} · {formatDate(srcLabel(b)?.date)}
                </small>
              </li>
            );
          })}
        </ul>
      </div>
    </details>
  );
}

const MON = ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"];
/** Kalendarz uprawy jako oś czasu (fazy, Kc, dzień analizy, okresy krytyczne) – ten sam w raporcie i u analityka. */
export function CropCalendarView({ block, asOf }: { block: DataBlock | undefined; asOf: string }) {
  const d = block?.data.raw;
  if (!d) return <p className="text-xs text-muted-foreground">{block?.data.summary ?? "Brak kalendarza uprawy."}</p>;
  const stages = (d.stages ?? []) as { name: string; start: string; end: string; kc: number | null }[];
  if (!d.crop || !stages.length)
    return (
      <div className="calendar-empty">
        <p>{d.general_season_note ?? block?.data.summary ?? "Wybierz uprawę, aby zobaczyć jej kalendarz."}</p>
      </div>
    );
  const t0 = new Date(`${stages[0]!.start}T12:00:00Z`).getTime();
  const t1 = new Date(`${stages[stages.length - 1]!.end}T12:00:00Z`).getTime();
  const span = Math.max(1, t1 - t0);
  const x = (s: string) => ((new Date(`${s.slice(0, 10)}T12:00:00Z`).getTime() - t0) / span) * 100;
  const now = x(asOf);
  const months: { label: string; left: number }[] = [];
  for (let t = new Date(t0); t.getTime() <= t1; t.setUTCMonth(t.getUTCMonth() + 1, 1)) {
    const left = ((t.getTime() - t0) / span) * 100;
    if (left >= 0) months.push({ label: MON[t.getUTCMonth()] ?? "", left });
  }
  const current = stages.find((s) => s.start <= asOf && asOf <= s.end);
  return (
    <div className="crop-calendar">
      <div className="cal-head">
        <strong>{d.crop_name_pl}</strong>
        <span className={`cal-state ${d.in_season_on_as_of ? "on" : ""}`}>
          {d.in_season_on_as_of ? `w sezonie · ${d.current_stage ?? ""}` : `poza sezonem · ${d.current_stage ?? ""}`}
        </span>
      </div>
      <div className="cal-track" role="img" aria-label={`Fazy uprawy ${d.crop_name_pl}; dzień analizy ${formatDate(asOf)}`}>
        {stages.map((s, i) => (
          <div key={s.name + i} className={`cal-stage s${i % 6} ${current === s ? "current" : ""}`}
            style={{ left: `${Math.max(0, x(s.start))}%`, width: `${Math.max(1.5, x(s.end) - x(s.start))}%` }}
            title={`${s.name}: ${formatDate(s.start)} – ${formatDate(s.end)}${s.kc != null ? ` · Kc ${s.kc}` : ""}`}>
            <span>{s.name}</span>
          </div>
        ))}
        {now >= 0 && now <= 100 && (
          <div className="cal-now" style={{ left: `${now}%` }}><span>{formatDate(asOf).slice(0, 5)}</span></div>
        )}
      </div>
      <div className="cal-months">
        {months.map((m, i) => <span key={i} style={{ left: `${m.left}%` }}>{m.label}</span>)}
      </div>
      <table className="data-table cal-table">
        <thead><tr><th scope="col">Faza</th><th scope="col">Termin</th><th scope="col">Zużycie wody (Kc)</th></tr></thead>
        <tbody>
          {stages.map((s, i) => (
            <tr key={i} className={current === s ? "current" : ""}>
              <td>{s.name}</td><td>{formatDate(s.start).slice(0, 5)} – {formatDate(s.end).slice(0, 5)}</td>
              <td>{s.kc != null ? s.kc.toLocaleString("pl-PL") : "–"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {(d.critical_water_periods ?? []).length > 0 && (
        <p className="cal-critical"><strong>Kiedy woda jest najważniejsza:</strong> {(d.critical_water_periods as string[]).join("; ")}.</p>
      )}
      {(d.warnings ?? []).map((w: string, i: number) => <p key={i} className="cal-warning">{w}</p>)}
    </div>
  );
}

export function LandscapeIllustration({
  kind,
}: {
  kind: "pond" | "weir" | "soil" | "irrigation" | "terrain";
}) {
  return (
    <svg
      className="measure-illustration"
      viewBox="0 0 90 70"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M4 47c12-4 20-3 30 3s23 8 51-4M5 59c25-4 50 7 78 0" />
      {kind === "pond" ? (
        <>
          <path d="M23 45c6 0 8 13 23 14s18-12 25-13" />
          <path d="M32 49c7-2 17 4 30 0m-28 6c9-2 16 3 25 0" stroke="var(--water)" />
          <path d="M13 43V30m0 7-5-5m5 1 5-6M74 43V28m0 9 5-5" />
          <path d="M48 13c0 0-7 9-7 13a7 7 0 0014 0c0-4-7-13-7-13z" stroke="var(--water)" />
        </>
      ) : kind === "weir" ? (
        <>
          <path d="M15 47l17 13h19l18-12M32 36v24m18-24v24M30 40h22m-22 6h22m-22 6h22" />
          <path d="M6 51h20m29 2h26m-70 4h15" stroke="var(--water)" />
        </>
      ) : kind === "soil" ? (
        <>
          <path d="M19 45V25m0 7c-10 0-9-9-9-9 11 0 9 9 9 9zm0 5c11 0 11-9 11-9-11 0-11 9-11 9zM46 49V17m0 12c-12 0-12-11-12-11 12 0 12 11 12 11zm0 6c12 0 12-11 12-11-12 0-12 11-12 11zM72 46V27m0 9c9 0 10-9 10-9-10 0-10 9-10 9z" />
          <path d="M16 55l5 2m19 5 9-3m20-5 4 3" stroke="var(--earth)" />
        </>
      ) : kind === "irrigation" ? (
        <>
          <path d="M16 46V28h39v-7M50 21h10m-5-4v5" />
          <path d="M51 29l-4 5m8-5v7m4-7 4 5M43 38l-3 5m15-4v6m12-7 3 5" stroke="var(--water)" />
        </>
      ) : (
        <>
          <path d="M6 46l22-23 24 22 16-9 17 10" />
          <path d="M40 35l10 10 8-4" stroke="var(--warning)" />
        </>
      )}
    </svg>
  );
}
