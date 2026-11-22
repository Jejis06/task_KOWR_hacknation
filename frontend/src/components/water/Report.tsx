import {
  ArrowRight,
  Check,
  ChevronDown,
  CloudRain,
  Droplets,
  Eye,
  Leaf,
  MapPin,
  ShieldCheck,
  Sun,
  Waves,
  Wind,
} from "lucide-react";
import type React from "react";
import { CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Button } from "@/components/ui/button";
import { canShowAdvice, doseToVolume, USE_MOCKS, type DataBlock, type Irrigation, type Recommendation, type WaterBalance } from "@/api/client";
import { smm } from "@/api/adapt";
import { FormalityBadge, FundingList, LegalDetails, LegalPlan, PondCalculator } from "./LegalPlan";
import { AskAgroLegal } from "./AskAgroLegal";
import { CropCalendarView, FlipCard, formatDate, SourceLine, Sources, Term } from "./shared";
type Props = {
  blocks: Record<string, DataBlock>;
  date: string;
  /** Numer działki – do karty „Wytłumacz mi prosto” */
  parcelId?: string;
  crop?: string;
  onMap: (id: string) => void;
  onData: (key: string) => void;
  loading: boolean;
  /** AgroLegal: otwiera wypełnione zgłoszenie wodnoprawne dla działania */
  onPrepare?: (r: Recommendation) => void;
};
const months = ["Sty", "Lut", "Mar", "Kwi", "Maj", "Cze", "Lip", "Sie", "Wrz", "Paź", "Lis", "Gru"];
/** Rozwijany temat raportu: nagłówek + jedno zdanie widoczne bez rozwijania. Natywne <details> – działa z klawiatury
 *  i czytnikiem ekranu; name="raport" → otwarty jest tylko jeden temat naraz (mniej przewijania). */
function Panel({ n, icon, title, teaser, open, children }: {
  n?: number; icon?: React.ReactNode; title: string; teaser?: React.ReactNode; open?: boolean; children: React.ReactNode;
}) {
  return (
    <details className="acc" {...{ name: "raport" }} open={open}>
      <summary className="acc-summary">
        {n != null ? <span className="acc-num" aria-hidden="true">{n}</span> : <span className="acc-num acc-icon">{icon}</span>}
        <span className="acc-text">
          <h2 className="acc-title">{n != null && <span className="sr-only">Krok {n}: </span>}{title}</h2>
          {teaser && <span className="acc-teaser">{teaser}</span>}
        </span>
        <ChevronDown size={22} aria-hidden="true" className="acc-chevron" />
      </summary>
      <div className="acc-body">{children}</div>
    </details>
  );
}
function Measure({
  recommendation: r,
  index,
  blocks,
  onMap,
}: {
  recommendation: Recommendation;
  index: number;
  blocks: Record<string, DataBlock>;
  onMap: (id: string) => void;
}) {
  const hints = (blocks["legal_context"]?.data.raw?.hints ?? []) as {
    title?: string; topic: string; requirement: string; fee_pln?: number | null; fee_year?: number | null;
    legal_ids?: string[]; caution?: string | null;
  }[];
  const hint = hints.find((h) => (h.legal_ids ?? []).some((id) => r.legal_ids.includes(id)));
  const agro = r.group === "agrotechnika";
  const hasMore = agro ? !!(r.sowing?.length || r.when || r.funding?.length) : true;
  return (
    <FlipCard items={r.evidence} blocks={blocks} label="Skąd to wiemy?" className="boxed">
      <article className="rec-simple">
        <div className="rec-head">
          <span className="rec-num" aria-hidden="true">{index}</span>
          <h3>{r.title}</h3>
        </div>
        <p className="rec-why">{r.why}</p>
        <div className="rec-tags">
          <FormalityBadge r={r} />
          <span className="priority-tag">
            {r.priority === 1 ? "Zacznij od tego" : agro ? "Dobre dla gleby" : "Warto rozważyć"}
          </span>
          {r.where_geojson && (
            <Button variant="outline" size="sm" className="rec-map-btn" onClick={() => onMap(`rec-${r.measure_id}`)}>
              <MapPin />
              Pokaż na mapie
            </Button>
          )}
        </div>
        {hasMore && (
          <details className="details-box rec-more" open={agro && !!r.sowing?.length}>
            <summary>
              {agro
                ? r.measure_id === "miedzyplony" ? "Co i kiedy siać" : r.sowing?.length ? "Co i kiedy zrobić" : "Kiedy"
                : "Kiedy, formalności i wsparcie"}
            </summary>
            <div className="details-content">
              {agro && r.sowing?.length ? (
                <ul className="sowing-list">
                  {r.sowing.map((o) => (
                    <li key={o.name}>
                      <strong>{o.name}</strong>
                      <span className="sowing-when">{o.when}</span>
                      <span>{o.why}</span>
                      {o.source_url && (
                        <a href={o.source_url} target="_blank" rel="noreferrer" className="sowing-src">
                          Źródło: {o.source_title ?? "dokument"}
                        </a>
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <p><strong>Kiedy:</strong> {r.when ?? "w dogodnym terminie agrotechnicznym"}</p>
              )}
              {!agro && (r.formality_label ? <LegalDetails r={r} /> : (
                <p className="mt-2">
                  <strong>Formalności:</strong> {hint ? `${hint.requirement} – ${hint.title ?? hint.topic}` : "Bez formalności wodnych."}
                </p>
              ))}
              {!agro && r.legal_ids.length > 0 && <p><Term name="Pozwolenie wodnoprawne" /></p>}
              {!agro && hint?.caution && <p className="text-warning">⚠ {hint.caution}</p>}
              {r.funding?.length ? <FundingList funding={r.funding} /> : null}
              {r.measure_id === "miedzyplony" && (
                <p className="text-muted-foreground mt-2">
                  Gatunki dobrane do uprawy głównej (termin zbioru, wspólne choroby) i gleby. Terminy orientacyjne – lokalnie ±1–2 tygodnie.
                </p>
              )}
              {!agro && <SourceLine block={blocks["legal_context"]} />}
            </div>
          </details>
        )}
      </article>
    </FlipCard>
  );
}

const MON = ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"];
/** [5,6,7,9] → „maj–lip, wrz” */
function monthsText(ms: number[]): string {
  const xs = [...new Set(ms)].sort((a, b) => a - b);
  const parts: string[] = [];
  for (let i = 0; i < xs.length; ) {
    let j = i;
    while (j + 1 < xs.length && xs[j + 1] === xs[j]! + 1) j++;
    parts.push(i === j ? MON[xs[i]! - 1]! : `${MON[xs[i]! - 1]}–${MON[xs[j]! - 1]}`);
    i = j + 1;
  }
  return parts.join(", ");
}
const nf = (v: number | null | undefined, d = 0) => (v == null ? "–" : v.toLocaleString("pl-PL", { maximumFractionDigits: d }));
const sezony = (n: number) => (n === 0 ? "brak suchych sezonów na 10" : n === 1 ? "1 suchy sezon na 10" : n < 5 ? `${n} suche sezony na 10` : `${n} suchych sezonów na 10`);

/**
 * Miarka bilansu wody (KBW z 60 dni) w prawdziwej skali mm: linia zera = opad równy parowaniu, słupki od zera
 * w dół (niedobór) lub w górę (nadwyżka), podziałka co „ładny” krok dobrany do wartości.
 */
function WaterGauge({ cur, norm }: { cur: number | null; norm: number | null }) {
  const vals = [cur ?? 0, norm ?? 0, 0];
  const rawMin = Math.min(...vals), rawMax = Math.max(...vals);
  const span = Math.max(40, rawMax - rawMin);
  const step = [10, 20, 25, 50, 100].find((s) => span / s <= 5) ?? 100;
  const lo = Math.floor((rawMin - span * 0.1) / step) * step, hi = Math.ceil((rawMax + span * 0.1) / step) * step;
  // współrzędne w jednostkach viewBox; SVG skaluje się do szerokości kolumny, tekst rośnie razem z nim
  const W = 200, H = 170, top = 22, axisX = 44, barW = 46;
  const y = (v: number) => top + ((hi - v) / (hi - lo)) * H;
  const ticks: number[] = [];
  for (let t = lo; t <= hi; t += step) ticks.push(t);
  const fmt = (v: number) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(Math.round(v))}`;
  const bar = (v: number | null, x: number, cls: string, label: string) => {
    if (v == null) return null;
    const y0 = y(0), y1 = y(v);
    return (
      <g>
        <rect x={x} y={Math.min(y0, y1)} width={barW} height={Math.max(2, Math.abs(y1 - y0))} rx={3}
          className={`wg-bar ${cls} ${v < 0 ? "neg" : "pos"}`} />
        <text x={x + barW / 2} y={v < 0 ? Math.min(y1 + 17, top + H + 2) : y1 - 6} textAnchor="middle" className={`wg-val ${cls}`}>
          {fmt(v)}
        </text>
        <text x={x + barW / 2} y={top + H + 20} textAnchor="middle" className="wg-lbl">{label}</text>
      </g>
    );
  };
  return (
    <figure className="water-gauge" role="img" aria-label={`Bilans wody z 60 dni: teraz ${smm(cur)}, zwykle ${smm(norm)}. Zero oznacza opad równy parowaniu.`}>
      <svg viewBox={`0 0 ${W} ${top + H + 28}`} preserveAspectRatio="xMidYMid meet">
        <text x={axisX - 8} y={12} textAnchor="end" className="wg-unit">mm</text>
        <rect x={axisX} y={top} width={W - axisX - 4} height={H} rx={4} className="wg-frame" />
        {ticks.map((t) => (
          <g key={t}>
            <line x1={axisX - 5} x2={t === 0 ? W - 4 : axisX} y1={y(t)} y2={y(t)} className={t === 0 ? "wg-zero" : "wg-tick"} />
            <text x={axisX - 9} y={y(t) + 4} textAnchor="end" className="wg-tick-lbl">{fmt(t)}</text>
          </g>
        ))}
        {bar(cur, axisX + 22, "cur", "teraz")}
        {bar(norm, axisX + 22 + barW + 18, "norm", "zwykle")}
      </svg>
      <figcaption className="gauge-caption">
        <span>Bilans wody z 60 dni <Term name="KBW" /></span>
        <small>0 = opad równy parowaniu</small>
      </figcaption>
    </figure>
  );
}

/** Bilans ilościowy: niedobór wody na całej działce [m³] vs pojemność i napływ do zagłębienia. */
function WaterBalancePanel({ wb, onMap }: { wb: WaterBalance; onMap: (id: string) => void }) {
  const need = wb.season_deficit_m3 ?? 0;
  // jeśli zagłębienie > 5000 m², liczymy oczko do 5000 m² (zgłoszenie) – te same liczby co w kalkulatorze oczka
  const capped = !!wb.pond?.capped;
  const cap = (capped ? wb.pond?.volume_m3 : wb.depression_volume_m3) ?? 0;
  const coverage = capped ? wb.pond?.covers_season_pct : wb.coverage_season_pct;
  const capLabel = capped ? "Oczko do 5000 m²" : "Zagłębienie na polu";
  const max = Math.max(need, cap, 1);
  return (
    <div className="balance-panel">
      <h3>Ile wody brakuje Twojemu polu?</h3>
      <p>Średnio w sezonie (kwiecień–wrzesień) parowanie przewyższa opady o <strong>{nf(wb.season_deficit_mm)} mm</strong>.
        Na {nf(wb.area_ha, 2)} ha to około <strong>{nf(wb.season_deficit_m3)} m³</strong> wody
        {wb.worst_season_deficit_m3 ? <> (w najsuchszym roku {nf(wb.worst_season_deficit_m3)} m³)</> : null}.
        {wb.deficit_60d_m3 ? <> Z ostatnich 60 dni brakuje {nf(wb.deficit_60d_m3)} m³.</> : null}</p>
      <div className="balance-bars" role="img" aria-label={`Niedobór ${nf(need)} m³, ${capLabel.toLowerCase()}: ${nf(cap)} m³`}>
        <div className="balance-row"><span>Niedobór w sezonie</span>
          <span className="balance-track"><span className="balance-fill need" style={{ width: `${(need / max) * 100}%` }} /></span>
          <strong>{nf(need)} m³</strong></div>
        {cap > 0 && (
          <div className="balance-row"><span>{capLabel}</span>
            <span className="balance-track"><span className="balance-fill cap" style={{ width: `${Math.max(1, (cap / max) * 100)}%` }} /></span>
            <strong>{nf(cap)} m³</strong></div>
        )}
      </div>
      {cap > 0 && (
        <p className="text-xs">{capped ? "Oczko" : "Zagłębienie"} pokryje ok. <strong>{nf(coverage, 1)}%</strong> sezonowego niedoboru.
          {wb.depression_catchment_ha != null && <> Woda spływa do niego z ok. <strong>{nf(wb.depression_catchment_ha, 1)} ha</strong>;
          zimą może dopłynąć do {nf(wb.depression_inflow_m3)} m³ ({(wb.depression_fill_pct ?? 0) >= 100 ? "wystarczy, by je napełnić" :
            `ok. ${nf(wb.depression_fill_pct)}% pojemności – oczko może być okresowo suche`}).</>}
          {" "}<Button variant="link" className="location-link" onClick={() => onMap("depression")}><MapPin />Pokaż zagłębienie</Button></p>
      )}
      <p className="text-xs text-muted-foreground">1 mm wody na 1 ha = 10 m³. Napływ to górny szacunek (część wody wsiąknie po drodze).</p>
    </div>
  );
}

/** Woda w strefie korzeni z dobowego bilansu FAO-56: ubytek vs woda łatwo dostępna (RAW) i cała dostępna (TAW). */
function SoilWaterChart({ irr }: { irr: Irrigation }) {
  const data = (irr.soil_water ?? []).map((d) => ({ label: `${d.date.slice(8, 10)}.${d.date.slice(5, 7)}`, dr: d.dr_mm, raw: d.raw_mm,
    taw: d.taw_mm, fc: d.forecast }));
  if (data.length < 3) return null;
  const firstFc = data.find((d) => d.fc)?.label;
  return (
    <>
      <div className="chart-box" role="img" aria-label="Ubytek wody w strefie korzeni w ostatnich 60 dniach i w prognozie">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 10, right: 8, bottom: 0, left: -20 }}>
            <CartesianGrid stroke="var(--border)" vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} interval="preserveStartEnd" minTickGap={18} />
            <YAxis reversed tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} />
            <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 5, fontSize: 11 }} />
            <Line dataKey="raw" name="Granica stresu (RAW, mm)" stroke="var(--warning)" strokeDasharray="5 4" dot={false} isAnimationActive={false} />
            <Line dataKey="taw" name="Cała woda dostępna (TAW, mm)" stroke="var(--danger)" strokeDasharray="2 3" dot={false} isAnimationActive={false} />
            <Line dataKey="dr" name="Ubytek wody z gleby (mm)" stroke="var(--water)" strokeWidth={2.5} dot={false} isAnimationActive={false} />
            {firstFc && <ReferenceLine x={firstFc} stroke="var(--muted-foreground)" label={{ value: "prognoza →", fontSize: 10, position: "insideTopLeft" }} />}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="chart-legend">
        <span><i />Ubytek wody</span><span><i className="normal" />Granica stresu</span><span><i className="danger" />Gleba wyschnięta</span>
        <span><Term name="Bilans FAO-56" /></span>
      </div>
    </>
  );
}
export default function Report({ blocks, date, parcelId, crop, onMap, onData, loading, onPrepare }: Props) {
  const analysis = blocks["analysis"];
  const a = analysis?.data.assessment;
  const drought = blocks["drought"];
  const weather = blocks["weather_history"];
  const forecast = blocks["weather_forecast"];
  const cur = weather?.data.balance_mm ?? null, norm = weather?.data.normal_mm ?? null;
  const years = Array.from({ length: 10 }, (_, i) => Number(date.slice(0, 4)) - 9 + i);
  if (!canShowAdvice(analysis) || !a)
    return (
      <div>
        {loading ? (
          <>
            <div className="skeleton" />
            <div className="skeleton" />
          </>
        ) : (
          <div className="report-empty">
            <Droplets size={40} />
            <h2>Najpierw sprawdź swoje pole</h2>
            <p>Wpisz numer działki lub wybierz ją na mapie. Ocena pojawi się po pobraniu danych.</p>
            {analysis?.status === "error" && (
              <p className="text-danger">Nie udało się przygotować oceny. Spróbuj ponownie.</p>
            )}
          </div>
        )}
      </div>
    );
  const data = analysis?.data;
  const irrigation = data?.irrigation;
  const firstRet = data?.recommendations?.filter((r) => r.group === "retencja_krajobrazowa").sort((x, y) => x.priority - y.priority)[0];
  const fc = a.field_check;
  const nDry = years.filter((y) => a.drought_years.includes(y)).length;
  const recs = [
    ...(data?.recommendations ?? []).filter((r) => r.group === "retencja_krajobrazowa").sort((x, y) => x.priority - y.priority),
    ...(data?.recommendations ?? []).filter((r) => r.group === "agrotechnika").sort((x, y) => x.priority - y.priority),
  ];
  const protectedHit = (blocks["protected_areas"]?.data.raw?.hits ?? []).length > 0;
  const deficit = data?.water_balance?.season_deficit_m3;
  const veg = blocks["vegetation"];
  const cal = blocks["crop_calendar"];
  const topCause = data?.causes?.[0];
  const missing = data?.missing_blocks ?? [];
  const severity = a.current_level === "high" || a.current_level === "very_high" ? "Duże zagrożenie suszą"
    : a.current_level === "moderate" ? "Umiarkowane zagrożenie suszą" : "Małe zagrożenie suszą";
  const irrLabel = !irrigation ? "Brak oceny nawadniania" : irrigation.recommended === "monitor" ? "Obserwuj, zanim zaczniesz"
    : irrigation.recommended === "yes" ? "Rozważ nawadnianie" : irrigation.recommended === "no" ? "Teraz nie nawadniaj" : "Brak oceny nawadniania";
  const nForms = recs.filter((r) => r.formality === "notification" || r.formality === "permit").length;
  return (
    <div id="report-content" role="tabpanel" aria-labelledby="report-tab">
      {parcelId && <AskAgroLegal parcelId={parcelId} date={date} crop={crop}
        onOpenChat={() => window.dispatchEvent(new Event("agrolegal:open-chat"))} />}
      <div className="report-intro">
        <h2>Raport dla Twojego pola</h2>
        <p>Policzony z danych pobranych dla tej działki (pogoda z 10 lat, satelita, gleba, teren, wody) na dzień{" "}
          <strong>{formatDate(date)}</strong> – bez AI. Kliknij temat, żeby go rozwinąć.</p>
      </div>
      {protectedHit && (
        <div className="protected-notice">
          <ShieldCheck size={15} aria-hidden="true" />
          <div>
            {blocks["protected_areas"]!.data.summary}
            <SourceLine block={blocks["protected_areas"]} />
          </div>
        </div>
      )}
      <div className="report-accordion">
        <Panel n={1} title="Jak jest z wodą?" open
          teaser={<><span className={`acc-pill lvl-${a.current_level ?? "none"}`}>{severity}</span> {a.current_label_pl} · susza w {nDry} z 10 lat</>}>
        <FlipCard items={a.evidence} blocks={blocks} label="Skąd to wiemy?">
        <div className="verdict-panel">
          <div className="verdict-main">
            <div>
              <div className="severity-label">
                <span className="status-dot" />
                {a.current_level === "high" || a.current_level === "very_high"
                  ? "Duże zagrożenie suszą"
                  : a.current_level === "moderate"
                    ? "Umiarkowane zagrożenie suszą"
                    : "Małe zagrożenie suszą"}
              </div>
              <h3 className="verdict-title">{a.current_label_pl}</h3>
              <p className="verdict-text">{a.current_summary}</p>
              <div className="confidence">
                <ShieldCheck size={12} />
                Pewność oceny: {a.confidence.toLowerCase()}
                <Term name="Pewność oceny" />
              </div>
            </div>
            <WaterGauge cur={cur} norm={norm} />
          </div>
          <div className="verdict-bottom">
            <Droplets size={18} />
            <span>
              <strong>Najpierw zatrzymaj wodę.</strong>{" "}
              {firstRet ? `Zacznij od: ${firstRet.title.charAt(0).toLowerCase()}${firstRet.title.slice(1)}.` : "Zatrzymuj wodę w glebie – międzyplony, mulcz, próchnica."}
            </span>
          </div>
        </div>
        </FlipCard>
        <ul className="key-facts">
          <li className={nDry >= 3 ? "bad" : ""}>
            <Sun size={16} aria-hidden="true" />
            <span><strong>Susza w {nDry} z 10</strong> ostatnich sezonów</span>
          </li>
          {a.critical_months.length > 0 && (
            <li>
              <CloudRain size={16} aria-hidden="true" />
              <span>Wody brakuje najczęściej: <strong>{monthsText(a.critical_months)}</strong></span>
            </li>
          )}
          {deficit ? (
            <li>
              <Waves size={16} aria-hidden="true" />
              <span>W sezonie brakuje ok. <strong>{nf(deficit)} m³</strong> wody na całym polu</span>
            </li>
          ) : null}
        </ul>
        <details className="details-box">
          <summary>Pokaż lata, miesiące i porównanie z satelitą</summary>
          <div className="details-content">
            {fc && (
              <div className={`field-check ${fc.case}`}>
                <div className="field-check-icons" aria-hidden="true">
                  <span className={fc.kbw === "dry" ? "bad" : "ok"}>Pogoda: {fc.kbw === "dry" ? "sucho" : "w normie"}</span>
                  <span>+</span>
                  <span className={fc.ndmi === "low" ? "bad" : "ok"}>Rośliny: {fc.ndmi === "low" ? "mniej wody" : "w normie"}</span>
                </div>
                <div>
                  <strong>{fc.label_pl}</strong> <Term name="KBW × NDMI" />
                  <p>{fc.text}</p>
                </div>
              </div>
            )}
            <div className="timeline-label">
              Susza na przestrzeni lat
              <span><span className="status-dot text-danger" />suchy sezon</span>
            </div>
            <div className="timeline" aria-label="Susza w ostatnich dziesięciu latach">
              {years.map((y) => (
                <div key={y} className={`year-tile ${a.drought_years.includes(y) ? "dry" : ""}`}
                  title={`${y}: ${a.drought_years.includes(y) ? "suchy sezon" : "bez suszy rolniczej"}`}>
                  {a.drought_years.includes(y) ? <Sun /> : <CloudRain />}
                  <span>{y}</span>
                </div>
              ))}
            </div>
            <SourceLine block={drought} label={sezony(nDry)} />
            <div className="timeline-label">
              Kiedy najbardziej brakuje wody?
              <span><span className="status-dot text-warning" />większe ryzyko</span>
            </div>
            <div className="month-ribbon" aria-label="Miesiące podwyższonego ryzyka suszy">
              {months.map((m, i) => (
                <div key={m} className={`month-tile ${a.critical_months.includes(i + 1) ? "risk" : ""}`}
                  title={`${m}: ${a.critical_months.includes(i + 1) ? "większe ryzyko" : "niższe ryzyko"}`}>
                  {m}
                </div>
              ))}
            </div>
            <SourceLine block={weather} />
          </div>
        </details>
        </Panel>
        <Panel n={2} title="Dlaczego brakuje wody?"
          teaser={topCause ? <>Najważniejsza przyczyna: {topCause.label_pl.toLowerCase()} (~{topCause.share}%)</> : "Brak danych o przyczynach"}>
        <p className="panel-lead">Dlaczego na tym polu brakuje wody – od najważniejszej przyczyny. Procent to udział w niedoborze.</p>
        <ol className="cause-list">
          {data?.causes?.map((cause, i) => (
            <li key={cause.key}>
              <FlipCard items={cause.evidence} blocks={blocks} label="Skąd to wiemy?" className="boxed">
                <div className="cause-card">
                  <div className="cause-card-pct" aria-hidden="true">{cause.share}<small>%</small></div>
                  <div className="cause-card-body">
                    <h3>
                      {i === 0 ? <CloudRain aria-hidden="true" /> : i === 1 ? <Leaf aria-hidden="true" /> : <Waves aria-hidden="true" />}
                      {cause.label_pl}
                      <span className="sr-only"> – około {cause.share}%</span>
                    </h3>
                    <p>{cause.explanation}</p>
                    <div className="cause-bar" aria-hidden="true">
                      <div className="cause-fill" style={{ width: `${cause.share}%` }} />
                    </div>
                  </div>
                </div>
              </FlipCard>
            </li>
          ))}
        </ol>
        </Panel>
        <Panel n={3} title="Co zrobić, żeby zatrzymać wodę?"
          teaser={recs[0] ? <>Zacznij od: {recs[0].title.charAt(0).toLowerCase()}{recs[0].title.slice(1)}</> : "Brak zaleceń"}>
        <div className="recommendation-list">
          {recs.map((r, i) => (
            <Measure key={r.measure_id} index={i + 1} recommendation={r} blocks={blocks} onMap={onMap} />
          ))}
        </div>
        {data?.water_balance && (
          <details className="details-box">
            <summary>Ile wody brakuje i ile zmieści zbiornik?</summary>
            <div className="details-content">
              <WaterBalancePanel wb={data.water_balance} onMap={onMap} />
              {data.water_balance.pond && <PondCalculator pond={data.water_balance.pond} />}
            </div>
          </details>
        )}
        </Panel>
        <Panel n={4} title="Czy to wymaga formalności i ile kosztuje?"
          teaser={nForms ? `${nForms} ${nForms === 1 ? "działanie wymaga" : "działania wymagają"} zgłoszenia lub pozwolenia – reszta od razu` : "Wszystko możesz zrobić bez urzędu"}>
          <LegalPlan recs={recs} onPrepare={onPrepare} bare />
        </Panel>
        {irrigation && (
          <Panel n={5} title="Czy podlewać?" teaser={<>{irrLabel}{irrigation.dose_mm != null ? ` · dawka ${irrigation.dose_mm} mm` : ""}</>}>
          <FlipCard items={irrigation.evidence} blocks={blocks} label="Skąd to wiemy?" className="boxed">
          <div className={`irr-card irr-${irrigation.recommended ?? "none"}`}>
            <div className="irr-verdict">
              <span className="irr-icon" aria-hidden="true">
                {irrigation.recommended === "yes" ? <Droplets /> : irrigation.recommended === "no" ? <Check /> : <Eye />}
              </span>
              <div>
                <span className="irr-kicker">Nasza ocena na {formatDate(date)}</span>
                <h3>{irrLabel}</h3>
              </div>
            </div>
            {irrigation.summary && <p className="irr-summary">{irrigation.summary}</p>}
            <div className="irr-stats">
              {irrigation.dose_mm != null && (
                <div>
                  <span>Dawka, jeśli podlewasz</span>
                  <strong>{irrigation.dose_mm} mm</strong>
                  <small>= {doseToVolume(irrigation.dose_mm)} m³ wody na hektar</small>
                </div>
              )}
              {irrigation.depletion_mm != null && (
                <div>
                  <span>Ubyło wody z gleby</span>
                  <strong>{nf(irrigation.depletion_mm)} mm</strong>
                  <small>z {nf(irrigation.taw_mm)} mm, które roślina może pobrać</small>
                </div>
              )}
              {irrigation.depletion_mm != null && (
                <div>
                  <span>Do stresu wodnego</span>
                  <strong>{irrigation.days_to_stress != null ? `${irrigation.days_to_stress} ${irrigation.days_to_stress === 1 ? "dzień" : "dni"}` : "brak"}</strong>
                  <small>{irrigation.stress_date ? `około ${formatDate(irrigation.stress_date)}` : "w prognozie nie przewidujemy"}</small>
                </div>
              )}
              {irrigation.yield_loss_pct != null && irrigation.yield_loss_pct >= 1 && (
                <div>
                  <span>Możliwy spadek plonu</span>
                  <strong>~{nf(irrigation.yield_loss_pct)}%</strong>
                  <small>przez niedobór wody od początku sezonu</small>
                </div>
              )}
            </div>
            {irrigation.timing && (
              <p className="irr-timing"><strong>Kiedy:</strong> {irrigation.timing}</p>
            )}
            {(irrigation.soil_water?.length ?? 0) >= 3 && (
              <details className="details-box">
                <summary>Wykres: woda w glebie z 60 dni i prognoza</summary>
                <div className="details-content">
                  <SoilWaterChart irr={irrigation} />
                </div>
              </details>
            )}
            <SourceLine block={analysis} />
          </div>
          </FlipCard>
          </Panel>
        )}
        {forecast && forecast.data.series && (
          <Panel icon={<CloudRain size={18} aria-hidden="true" />} title="Pogoda na 16 dni" teaser={forecast.data.summary ?? ""}>
              <div className="forecast-preview">
                <div>
                  <p>{forecast.data.summary}</p>
                  <SourceLine block={forecast} />
                </div>
                <div className="forecast-mini" aria-hidden="true">
                  {forecast.data.series.map((row, i) => <span key={i} style={{ height: `${Math.max(row.rain * 4, 3)}px` }} />)}
                </div>
                <Button variant="ghost" size="icon" title="Zobacz prognozę" aria-label="Zobacz szczegółową prognozę"
                  onClick={() => onData("weather_forecast")}>
                  <ArrowRight />
                </Button>
              </div>
          </Panel>
        )}
        {(veg || cal) && (
          <Panel icon={<Leaf size={18} aria-hidden="true" />} title="Rośliny i kalendarz uprawy"
            teaser={veg?.data.summary ?? "Fazy rozwoju i okresy, w których woda jest najważniejsza"}>
            {veg && (
              <div className="veg-panel">
                <p>{veg.data.summary}</p>
                {veg.data.metrics && (
                  <dl className="veg-metrics">
                    {veg.data.metrics.map((m) => (
                      <div key={m.label}><dt>{m.label}{m.term && <> <Term name={m.term} /></>}</dt><dd>{m.value}</dd></div>
                    ))}
                  </dl>
                )}
                <SourceLine block={veg} />
              </div>
            )}
            {cal && (
              <>
                <h3 className="veg-sub">Kalendarz uprawy – kiedy woda jest najważniejsza</h3>
                <CropCalendarView block={cal} asOf={date} />
                <SourceLine block={cal} />
              </>
            )}
          </Panel>
        )}
        <Panel icon={<Wind size={18} aria-hidden="true" />} title="Czego nie wiemy – ograniczenia i brakujące dane"
          teaser={missing.length ? `Brak danych: ${missing.join(", ")}` : `${data?.limitations?.length ?? 0} rzeczy, które warto sprawdzić w terenie`}>
          {missing.length > 0 && (
            <p className="missing-note"><strong>Brakujące dane:</strong> {missing.join(", ")} – tych czynników nie uwzględniliśmy.</p>
          )}
          <ul className="limits-list">{data?.limitations?.map((t) => <li key={t}>{t}</li>)}</ul>
          <p className="text-xs text-muted-foreground">Pewność oceny: {a.confidence?.toLowerCase()}. Wyniki to szacunki z danych publicznych, nie pomiar na polu.</p>
        </Panel>
        <Panel icon={<Check size={18} aria-hidden="true" />} title="Skąd są dane – źródła i metoda"
          teaser={`Data analizy ${formatDate(date)} · ${analysis?.provenance?.length ?? 0} źródeł z datami`}>
          <h3 className="veg-sub">Jak powstała ocena</h3>
          <ul className="limits-list">{data?.method?.map((t) => <li key={t}>{t}</li>)}</ul>
          <Sources block={analysis} />
        </Panel>
      </div>
      <div className="report-footer">
        {USE_MOCKS
          ? "Ten raport pokazuje przykładowy scenariusz (dane demonstracyjne). "
          : "Raport liczony z publicznych danych dla tej działki i daty – źródła i daty przy każdym bloku. "}
        Nie zastępuje pomiarów w polu, projektu technicznego ani decyzji organów (Wody Polskie, starostwo, ARiMR).
        Informacja orientacyjna, nie porada prawna.
      </div>
    </div>
  );
}
