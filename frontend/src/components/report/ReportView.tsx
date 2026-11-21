// Raport dla rolnika – kolejność wymagana przez KOWR:
// ocena sytuacji wodnej → przyczyny → retencja → agrotechnika → (opcjonalnie) nawadnianie, + daty, źródła, ograniczenia.
// Zasada: bez oceny (blok `analysis`) NIE pokazujemy przyczyn ani rekomendacji („system nie powinien generować
// rekomendacji bez uprzedniego rozpoznania warunków działki”).
import type {
  AnalysisResult, BlockInfo, Cause, CropCalendarInfo, DataBlock, DroughtHistory, Evidence, HydrologyInfo, LegalContextInfo,
  LegalHint, ParcelRef, Recommendation, RiskLevel, SoilInfo, VegetationInfo, WeatherHistory,
} from "../../api/types";
import { Fragment } from "react";
import { useKnowledge } from "../../api/knowledge";
import { dateStr, dateTimeStr, MONTHS_SHORT, num, signed, STATUS_LABEL } from "../../lib/format";
import { SourcesPanel } from "../SourcesPanel";
import { Term } from "../Term";

type Blocks = Record<string, DataBlock | "loading">;

const LEVEL_PL: Record<RiskLevel, string> = { none: "brak", low: "niski", moderate: "umiarkowany", high: "wysoki", very_high: "bardzo wysoki" };
const LEVEL_TONE: Record<RiskLevel, string> = { none: "good", low: "good", moderate: "warn", high: "bad", very_high: "bad" };
const CONF_PL = { low: "niska", medium: "średnia", high: "wysoka" } as const;
const GROUP_REQ: Record<string, string> = { none: "bez formalności", notification: "zgłoszenie wodnoprawne", permit: "pozwolenie wodnoprawne", depends: "zależy od sytuacji" };

function data<T>(b: DataBlock | "loading" | undefined): T | null {
  return typeof b === "object" && (b.status === "ok" || b.status === "partial") ? (b.data as T) : null;
}

/** Dowód = liczba + nazwa bloku + data danych (wymóg: żadnej liczby bez źródła i daty). */
function EvidenceList({ items, blocks, infos }: { items: Evidence[]; blocks: Blocks; infos: BlockInfo[] }) {
  if (!items.length) return null;
  return (
    <ul className="evidence">
      {items.map((e, i) => {
        const b = e.block ? blocks[e.block] : undefined;
        const p = typeof b === "object" ? b.provenance[0] : undefined;
        const title = infos.find((x) => x.key === e.block)?.title ?? e.block;
        return (
          <li key={i}><span className="ev-text">{e.text}</span>
            {title && <span className="ev-src"> · {title}{p ? `, ${p.data_as_of ? `dane do ${dateStr(p.data_as_of)}` : `pobrano ${dateStr(p.retrieved_at)}`}` : ""}</span>}</li>
        );
      })}
    </ul>
  );
}

function MonthsBar({ months }: { months: number[] }) {
  const set = new Set(months);
  return (
    <div className="months" role="img" aria-label={`Miesiące największego ryzyka: ${months.map((m) => MONTHS_SHORT[m - 1]).join(", ") || "brak"}`}>
      {MONTHS_SHORT.map((m, i) => <span key={m} className={set.has(i + 1) ? "on" : ""}>{m}</span>)}
    </div>
  );
}

/** Gdy oceny jeszcze nie ma: same wskaźniki z danych, wyraźnie opisane jako „bez oceny”. */
function KeyIndicators({ blocks }: { blocks: Blocks }) {
  const w = data<WeatherHistory>(blocks.weather_history);
  const dr = data<DroughtHistory>(blocks.drought);
  const soil = data<SoilInfo>(blocks.soil);
  const veg = data<VegetationInfo>(blocks.vegetation);
  const hyd = data<HydrologyInfo>(blocks.hydrology);
  const cat = soil?.drought_category ?? (soil?.drought_susceptibility ? soil.drought_susceptibility : null);
  const rows: [string, string][] = [];
  if (w) rows.push(["Bilans wodny (KBW) z 60 dni", `${signed(w.cwb_60d_mm, "mm")} (norma ${signed(w.cwb_60d_normal_mm, "mm")})`]);
  if (w) rows.push(["Opad z 30 dni", `${num(w.last_30d_precip_mm, "mm")} (norma ${num(w.last_30d_precip_normal_mm, "mm")})`]);
  if (dr) rows.push(["Susza teraz", dr.current.map((c) => `${c.class_label ?? c.value} (${c.source})`).join("; ") || "brak oceny"]);
  if (dr) rows.push(["Lata z suszą (10 lat)", dr.drought_years.length ? dr.drought_years.join(", ") : "brak"]);
  if (cat != null) rows.push(["Podatność gleby na suszę (SMSR)", `kategoria ${cat}`]);
  if (veg?.anomaly != null) rows.push(["Roślinność (NDVI) względem normy", signed(veg.anomaly, "", 2)]);
  if (hyd) rows.push(["Strefa powodziowa", hyd.in_flood_zone ? `tak (${hyd.in_flood_zone})` : hyd.flood_zone_checked ? "poza strefą" : "nie sprawdzono"]);
  if (!rows.length) return <p className="muted">Dane wciąż się pobierają albo są niedostępne.</p>;
  return <dl className="kv-grid">{rows.map(([k, v]) => <Fragment key={k}><dt>{k}</dt><dd>{v}</dd></Fragment>)}</dl>;
}

function Gate({ short }: { short?: boolean }) {
  return short ? <p className="gate small">Pojawi się po ocenie sytuacji wodnej (krok 1).</p> : (
    <p className="gate">Przyczyny i rekomendacje pokażemy dopiero wtedy, gdy aplikacja oceni sytuację wodną tej działki –
      rekomendacje muszą wynikać z rozpoznania warunków na Twoim polu, a nie z ogólnych porad.</p>
  );
}

function CauseRow({ c, blocks, infos }: { c: Cause; blocks: Blocks; infos: BlockInfo[] }) {
  const pct = c.share != null ? Math.round(c.share * 100) : null;
  return (
    <div className="cause">
      <div className="cause-head"><b>{c.label_pl}</b>{pct != null && <span className="muted"> · udział ok. {pct}% (szacunek)</span>}</div>
      {pct != null && <span className="bar-track"><span className="bar-fill" style={{ width: `${pct}%` }} /></span>}
      {c.explanation && <p>{c.explanation}</p>}
      <EvidenceList items={c.evidence} blocks={blocks} infos={infos} />
    </div>
  );
}

function RecCard({ r, i, legal, blocks, infos }: { r: Recommendation; i: number; legal: LegalHint[]; blocks: Blocks; infos: BlockInfo[] }) {
  const k = useKnowledge();
  const hint = legal.find((h) => (h.legal_ids ?? []).some((id) => r.legal_ids.includes(id)));
  const funding = r.funding_ids.map((id) => k.funding[id]?.name ?? id);
  return (
    <article className="rec">
      <header><span className="rec-no" aria-hidden>{i + 1}</span><h4>{r.title}</h4></header>
      <p>{r.why}</p>
      {r.when && <p className="small"><b>Kiedy:</b> {r.when}</p>}
      {r.where_geojson && <p className="small"><b>Gdzie:</b> miejsce zaznaczone na mapie na pomarańczowo.</p>}
      <EvidenceList items={r.evidence} blocks={blocks} infos={infos} />
      {(hint || r.legal_ids.length > 0) && (
        <p className="small rec-legal"><b>Formalności:</b>{" "}
          {hint ? <>{GROUP_REQ[hint.group ?? "depends"]} – {hint.title ?? hint.topic}
            {hint.fee_pln != null && ` (opłata ${num(hint.fee_pln, "zł", 2)}${hint.fee_year ? `, stawka ${hint.fee_year}` : ""})`}
            {hint.caution && <span className="warn-text"> · ⚠ {hint.caution}</span>}</>
            : "sprawdź w sekcji „Pozwolenia” w zakładce Wszystkie dane."}</p>
      )}
      {funding.length > 0 && <p className="small"><b>Możliwe dofinansowanie:</b> {funding.join("; ")}</p>}
    </article>
  );
}

export function ReportView(props: {
  parcel: ParcelRef; asOf: string; cropName?: string; generatedAt: string; infos: BlockInfo[]; blocks: Blocks;
}) {
  const { parcel, asOf, blocks, infos } = props;
  const k = useKnowledge();
  const analysisBlock = blocks.analysis;
  const analysisAvailable = infos.some((b) => b.key === "analysis");
  const a = data<AnalysisResult>(analysisBlock);
  const assessed = !!a?.assessment;
  const legal = data<LegalContextInfo>(blocks.legal_context)?.hints ?? [];
  const cal = data<CropCalendarInfo>(blocks.crop_calendar);
  const loading = Object.values(blocks).filter((b) => b === "loading").length;
  const recs = (g: Recommendation["group"]) => (a?.recommendations ?? []).filter((r) => r.group === g).sort((x, y) => x.priority - y.priority);
  const missing = infos.filter((i) => i.key !== "analysis").map((i) => ({ i, b: blocks[i.key] }))
    .filter(({ b }) => typeof b === "object" && b.status !== "ok" && b.status !== "partial");
  const as = a?.assessment;
  const irrigationHints = legal.filter((h) => h.topic === "nawadnianie");

  return (
    <article className="report">
      <header className="report-head">
        <h2>Raport: woda na działce {parcel.parcel_number ?? parcel.id}</h2>
        <p>{parcel.id} · {[parcel.region_name, parcel.commune, parcel.county, parcel.voivodeship].filter(Boolean).join(", ")} · {num(parcel.area_ha, "ha", 2)}</p>
        <p>Data analizy: <b>{dateStr(asOf)}</b> · uprawa: <b>{props.cropName ?? "nie wybrano"}</b> · wygenerowano: {dateTimeStr(props.generatedAt)}</p>
        {loading > 0 && <p className="no-print warn-text" aria-live="polite">Raport się kompletuje – czekam na {loading} bloków danych…</p>}
      </header>

      {/* 1. OCENA */}
      <section className="rsec">
        <h3><span className="step">1</span> Ocena sytuacji wodnej</h3>
        {assessed && as ? (
          <>
            <div className="stats">
              <div className={`stat ${as.current_level ? LEVEL_TONE[as.current_level] : ""}`}>
                <div className="stat-label">Teraz ({dateStr(asOf)})</div>
                <div className="stat-value">{as.current_label_pl ?? (as.current_level ? `niedobór ${LEVEL_PL[as.current_level]}` : "brak oceny")}</div>
                {as.current_summary && <div className="stat-sub">{as.current_summary}</div>}
              </div>
              <div className={`stat ${as.historical_level ? LEVEL_TONE[as.historical_level] : ""}`}>
                <div className="stat-label">W ostatnich 10 latach</div>
                <div className="stat-value">{as.historical_label_pl ?? (as.historical_level ? `ryzyko ${LEVEL_PL[as.historical_level]}` : "brak oceny")}</div>
                {as.historical_summary && <div className="stat-sub">{as.historical_summary}</div>}
              </div>
            </div>
            {as.critical_months.length > 0 && <><h4>Kiedy ryzyko niedoboru wody jest największe</h4><MonthsBar months={as.critical_months} /></>}
            {as.drought_years.length > 0 && <p className="small">Lata z suszą rolniczą: <b>{as.drought_years.join(", ")}</b></p>}
            <h4>Na podstawie</h4>
            <EvidenceList items={as.evidence} blocks={blocks} infos={infos} />
            {as.confidence && <p className="small">Pewność oceny: <b>{CONF_PL[as.confidence]}</b></p>}
          </>
        ) : (
          <>
            <p className="gate">{!analysisAvailable
              ? "Automatyczna ocena sytuacji wodnej jest jeszcze w przygotowaniu. Poniżej najważniejsze wskaźniki z pobranych danych – bez oceny i bez rekomendacji."
              : analysisBlock === "loading" ? "Liczę ocenę sytuacji wodnej…"
              : `Nie udało się policzyć oceny (${typeof analysisBlock === "object" ? STATUS_LABEL[analysisBlock.status] : "brak danych"}). Poniżej wskaźniki z pobranych danych.`}</p>
            <h4>Kluczowe wskaźniki z danych</h4>
            <KeyIndicators blocks={blocks} />
          </>
        )}
      </section>

      {/* 2. PRZYCZYNY */}
      <section className="rsec">
        <h3><span className="step">2</span> Dlaczego brakuje wody – przyczyny</h3>
        {!assessed ? <Gate /> : a!.causes.length ? [...a!.causes].sort((x, y) => (y.share ?? 0) - (x.share ?? 0))
          .map((c) => <CauseRow key={c.key} c={c} blocks={blocks} infos={infos} />)
          : <p className="muted">Nie stwierdzono wyraźnych przyczyn niedoboru wody.</p>}
      </section>

      {/* 3. RETENCJA */}
      <section className="rsec">
        <h3><span className="step">3</span> Jak zatrzymać wodę – retencja na działce i w okolicy</h3>
        {!assessed ? <Gate short /> : recs("retencja_krajobrazowa").length
          ? recs("retencja_krajobrazowa").map((r, i) => <RecCard key={r.measure_id} r={r} i={i} legal={legal} blocks={blocks} infos={infos} />)
          : <p className="muted">Dla tej działki dane nie wskazują dobrego miejsca na zatrzymanie wody w terenie.</p>}
      </section>

      {/* 4. AGROTECHNIKA */}
      <section className="rsec">
        <h3><span className="step">4</span> Zabiegi agrotechniczne – więcej wody w glebie</h3>
        {!assessed ? <Gate short /> : recs("agrotechnika").length
          ? recs("agrotechnika").map((r, i) => <RecCard key={r.measure_id} r={r} i={i} legal={legal} blocks={blocks} infos={infos} />)
          : <p className="muted">Brak dodatkowych zaleceń agrotechnicznych.</p>}
      </section>

      {/* 5. NAWADNIANIE */}
      <section className="rsec">
        <h3><span className="step">5</span> Nawadnianie <span className="muted small">(ostatni krok – po retencji)</span></h3>
        {!assessed ? <Gate short /> : a!.irrigation ? (
          <>
            <div className={`stat ${a!.irrigation.recommended === "yes" ? "warn" : a!.irrigation.recommended === "no" ? "good" : ""}`}>
              <div className="stat-label">Czy nawadniać{a!.irrigation.horizon_days ? ` (najbliższe ${a!.irrigation.horizon_days} dni)` : ""}</div>
              <div className="stat-value">{a!.irrigation.recommended === "yes" ? "tak" : a!.irrigation.recommended === "monitor" ? "obserwuj" : a!.irrigation.recommended === "no" ? "nie" : "brak oceny"}</div>
              {a!.irrigation.summary && <div className="stat-sub">{a!.irrigation.summary}</div>}
            </div>
            <dl className="kv-grid">
              {a!.irrigation.deficit_mm != null && <><dt>Niedobór wody w prognozie</dt><dd>{signed(a!.irrigation.deficit_mm, "mm", 1)}</dd></>}
              {a!.irrigation.dose_mm != null && <><dt>Dawka</dt><dd>{num(a!.irrigation.dose_mm, "mm", 0)} (= {num(a!.irrigation.dose_mm * 10, "m³/ha")})</dd></>}
              {a!.irrigation.timing && <><dt>Kiedy</dt><dd>{a!.irrigation.timing}</dd></>}
            </dl>
            <EvidenceList items={a!.irrigation.evidence} blocks={blocks} infos={infos} />
            {irrigationHints.length > 0 && (
              <p className="small rec-legal"><b>Formalności:</b> {irrigationHints.map((h) => `${h.title ?? h.topic} – ${h.requirement}`).join("; ")}.</p>
            )}
          </>
        ) : recs("nawadnianie").length ? recs("nawadnianie").map((r, i) => <RecCard key={r.measure_id} r={r} i={i} legal={legal} blocks={blocks} infos={infos} />)
          : <p className="muted">Brak oceny potrzeb nawadniania dla tej daty.</p>}
      </section>

      {/* KALENDARZ */}
      {cal && (
        <section className="rsec">
          <h3>Kalendarz uprawy</h3>
          <p>{cal.crop ? cal.crop_name_pl : "Okres wegetacji"}: <b>{cal.current_stage ?? "brak danych"}</b> ({cal.in_season_on_as_of ? "w sezonie" : "poza sezonem"}).</p>
          {cal.critical_water_periods.length > 0 && <p className="small">Okresy krytyczne dla wody: {cal.critical_water_periods.join("; ")}.</p>}
          {cal.warnings.length > 0 && <ul className="notes">{cal.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>}
        </section>
      )}

      {/* DANE, ŹRÓDŁA, OGRANICZENIA */}
      <section className="rsec">
        <h3>Ograniczenia i niepewność</h3>
        {missing.length > 0 && (
          <>
            <h4>Brakujące dane (pominięte w analizie)</h4>
            <ul className="small">{missing.map(({ i, b }) => (
              <li key={i.key}><b>{i.title}:</b> {STATUS_LABEL[(b as DataBlock).status]}{(b as DataBlock).messages[0] ? ` – ${(b as DataBlock).messages[0]}` : ""}</li>))}</ul>
          </>
        )}
        {a && a.limitations.length > 0 && <><h4>Czego analiza nie uwzględnia</h4><ul className="small">{a.limitations.map((l, i) => <li key={i}>{l}</li>)}</ul></>}
        {a && a.method.length > 0 && <><h4>Metoda</h4><ul className="small">{a.method.map((m, i) => <li key={i}>{m}</li>)}</ul></>}
        <p className="small">Skróty: <Term k="KBW" />, <Term k="NDVI" />, <Term k="SMSR" />, <Term k="ET₀" /> – najedź lub dotknij, aby zobaczyć objaśnienie.</p>
      </section>

      <SourcesPanel infos={infos} blocks={blocks} />

      <p className="small disclaimer">{k.disclaimer ?? "Informacja orientacyjna, nie porada prawna."} Raport nie zastępuje porady doradcy rolniczego ani decyzji
        organów (Wody Polskie, starostwo, ARiMR). Prototyp HackNation 2026 (zadanie KOWR).</p>
    </article>
  );
}
