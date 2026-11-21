import {
  ArrowRight,
  Check,
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
import { CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Button } from "@/components/ui/button";
import { canShowAdvice, doseToVolume, USE_MOCKS, type DataBlock, type Irrigation, type Recommendation, type WaterBalance } from "@/api/client";
import { smm } from "@/api/adapt";
import { CropCalendarView, FlipCard, formatDate, LandscapeIllustration, SourceLine, Sources, Term } from "./shared";
type Props = {
  blocks: Record<string, DataBlock>;
  date: string;
  onMap: (id: string) => void;
  onData: (key: string) => void;
  loading: boolean;
};
const months = ["Sty", "Lut", "Mar", "Kwi", "Maj", "Cze", "Lip", "Sie", "Wrz", "Paź", "Lis", "Gru"];
function StoryHeading({ number, title, extra }: { number: number; title: string; extra?: string }) {
  return (
    <div className="story-heading">
      <span className="step-number">{number}</span>
      <h2>{title}</h2>
      {extra && <span className="step-subtitle">{extra}</span>}
    </div>
  );
}
function Measure({
  recommendation: r,
  blocks,
  onMap,
}: {
  recommendation: Recommendation;
  blocks: Record<string, DataBlock>;
  onMap: (id: string) => void;
}) {
  const hints = (blocks["legal_context"]?.data.raw?.hints ?? []) as {
    title?: string; topic: string; requirement: string; fee_pln?: number | null; fee_year?: number | null;
    legal_ids?: string[]; caution?: string | null;
  }[];
  const hint = hints.find((h) => (h.legal_ids ?? []).some((id) => r.legal_ids.includes(id)));
  return (
    <FlipCard items={r.evidence} blocks={blocks} label="Skąd to zalecenie?">
    <article className="recommendation">
      <LandscapeIllustration kind={ILLU[r.measure_id] ?? (r.group === "agrotechnika" ? "soil" : r.group === "nawadnianie" ? "irrigation" : "terrain")} />
      <div>
        <h3>{r.title}</h3>
        <p>{r.why}</p>
        <div className="recommendation-tags">
          <span className="priority-tag">
            {r.priority === 1
              ? "Zacznij od tego"
              : r.group === "agrotechnika"
                ? "Dobre dla gleby"
                : "Warto rozważyć"}
          </span>
          {r.where_geojson && (
            <Button
              variant="link"
              className="location-link"
              onClick={() => onMap(`rec-${r.measure_id}`)}
            >
              <MapPin />
              Pokaż na mapie
            </Button>
          )}
        </div>
        <details className="details-box">
          <summary>Kiedy, formalności i wsparcie</summary>
          <div className="details-content">
            <p>
              <strong>Kiedy:</strong> {r.when}
            </p>
            <p className="mt-2">
              <strong>Formalności:</strong>{" "}
              {hint
                ? `${hint.requirement} – ${hint.title ?? hint.topic}`
                : r.group === "agrotechnika" || !r.legal_ids.length
                  ? "Bez formalności wodnych."
                  : "Przed pracami sprawdź, czy potrzebne jest zgłoszenie lub pozwolenie wodnoprawne."}{" "}
              {r.legal_ids.length > 0 && <Term name="Pozwolenie wodnoprawne" />}
            </p>
            {hint?.fee_pln != null && <p>Opłata urzędowa: {hint.fee_pln.toLocaleString("pl-PL", { minimumFractionDigits: 2 })} zł (stawka {hint.fee_year}).</p>}
            {hint?.caution && <p className="text-warning">⚠ {hint.caution}</p>}
            <p className="mt-2">
              <strong>Wsparcie:</strong>{" "}
              {r.funding_ids.length
                ? `Możliwe programy (sprawdź aktualne nabory): ${r.funding_ids.join(", ")}.`
                : "Brak przypisanego programu dofinansowania."}
            </p>
            <SourceLine block={blocks["legal_context"]} />
          </div>
        </details>
      </div>
    </article>
    </FlipCard>
  );
}

const ILLU: Record<string, "pond" | "weir" | "soil" | "irrigation" | "terrain"> = {
  oczko_zbiornik: "pond", mokradlo: "pond", zastawka_row: "weir", pas_buforowy: "terrain", uprawa_w_poprzek_stoku: "terrain",
  miedzyplony: "soil", resztki_mulcz: "soil", materia_organiczna: "soil", uprawa_uproszczona: "soil",
};
const nf = (v: number | null | undefined, d = 0) => (v == null ? "–" : v.toLocaleString("pl-PL", { maximumFractionDigits: d }));
const sezony = (n: number) => (n === 0 ? "brak suchych sezonów na 10" : n === 1 ? "1 suchy sezon na 10" : n < 5 ? `${n} suche sezony na 10` : `${n} suchych sezonów na 10`);

/** Bilans ilościowy: niedobór wody na całej działce [m³] vs pojemność i napływ do zagłębienia. */
function WaterBalancePanel({ wb, onMap }: { wb: WaterBalance; onMap: (id: string) => void }) {
  const need = wb.season_deficit_m3 ?? 0;
  const cap = wb.depression_volume_m3 ?? 0;
  const max = Math.max(need, cap, 1);
  return (
    <div className="balance-panel">
      <h3>Ile wody brakuje Twojemu polu?</h3>
      <p>Średnio w sezonie (kwiecień–wrzesień) parowanie przewyższa opady o <strong>{nf(wb.season_deficit_mm)} mm</strong>.
        Na {nf(wb.area_ha, 2)} ha to około <strong>{nf(wb.season_deficit_m3)} m³</strong> wody
        {wb.worst_season_deficit_m3 ? <> (w najsuchszym roku {nf(wb.worst_season_deficit_m3)} m³)</> : null}.
        {wb.deficit_60d_m3 ? <> Z ostatnich 60 dni brakuje {nf(wb.deficit_60d_m3)} m³.</> : null}</p>
      <div className="balance-bars" role="img" aria-label={`Niedobór ${nf(need)} m³, pojemność zagłębienia ${nf(cap)} m³`}>
        <div className="balance-row"><span>Niedobór w sezonie</span>
          <span className="balance-track"><span className="balance-fill need" style={{ width: `${(need / max) * 100}%` }} /></span>
          <strong>{nf(need)} m³</strong></div>
        {cap > 0 && (
          <div className="balance-row"><span>Zagłębienie na polu</span>
            <span className="balance-track"><span className="balance-fill cap" style={{ width: `${Math.max(1, (cap / max) * 100)}%` }} /></span>
            <strong>{nf(cap)} m³</strong></div>
        )}
      </div>
      {cap > 0 && (
        <p className="text-xs">Zagłębienie pokryje ok. <strong>{nf(wb.coverage_season_pct, 1)}%</strong> sezonowego niedoboru.
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
export default function Report({ blocks, date, onMap, onData, loading }: Props) {
  const analysis = blocks["analysis"];
  const a = analysis?.data.assessment;
  const drought = blocks["drought"];
  const weather = blocks["weather_history"];
  const forecast = blocks["weather_forecast"];
  const cur = weather?.data.balance_mm ?? null, norm = weather?.data.normal_mm ?? null;
  const lo = Math.min(-200, cur ?? 0, norm ?? 0), hi = Math.max(60, cur ?? 0, norm ?? 0);
  const lvl = (v: number | null) => (v == null ? 0 : ((v - lo) / (hi - lo)) * 100);
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
  return (
    <div id="report-content" role="tabpanel" aria-labelledby="report-tab">
      {blocks["protected_areas"] && (
        <div className="protected-notice">
          <ShieldCheck size={15} />
          <div>
            {blocks["protected_areas"].data.summary}
            <SourceLine block={blocks["protected_areas"]} />
          </div>
        </div>
      )}
      <section className="story-section">
        <StoryHeading number={1} title="Jak jest z wodą?" extra="Teraz i w ostatnich 10 latach" />
        <FlipCard items={a.evidence} blocks={blocks} label="Skąd ta ocena?">
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
            <div
              className="gauge"
              role="img"
              aria-label={`Bilans wody: ${smm(cur)}. Zwykle ${smm(norm)}.`}
            >
              <div className="gauge-track">
                <div className="gauge-water" style={{ height: `${lvl(cur)}%` }} />
                <div className="gauge-normal" style={{ top: "auto", bottom: `${lvl(norm)}%` }} />
                <div className="gauge-current" style={{ bottom: `${lvl(cur)}%` }} />
              </div>
              <div className="gauge-labels" style={{ display: "flex", flexDirection: (cur ?? 0) >= (norm ?? 0) ? "column-reverse" : "column" }}>
                <div className="normal">
                  Zwykle
                  <strong>
                    {norm != null ? Math.round(norm) : "—"}{" "}
                    <small className="text-xs font-normal">mm</small>
                  </strong>
                </div>
                <div className="current">
                  Teraz
                  <strong>
                    {cur != null ? Math.round(cur) : "—"}{" "}
                    <small className="text-xs font-normal">mm</small>
                  </strong>
                </div>
              </div>
              <div className="gauge-caption">
                Bilans wody z 60 dni <Term name="KBW" />
              </div>
            </div>
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
        <SourceLine block={weather} />
        <div className="timeline-label">
          Susza na przestrzeni lat
          <span>
            <span className="status-dot text-danger" />
            suchy sezon
          </span>
        </div>
        <div className="timeline" aria-label="Susza w ostatnich dziesięciu latach">
          {years.map((y) => (
            <div
              key={y}
              className={`year-tile ${a.drought_years.includes(y) ? "dry" : ""}`}
              title={`${y}: ${a.drought_years.includes(y) ? "suchy sezon" : "bez suszy rolniczej"}`}
            >
              {a.drought_years.includes(y) ? <Sun /> : <CloudRain />}
              <span>{y}</span>
            </div>
          ))}
        </div>
        <SourceLine block={drought} label={sezony(nDry)} />
        <div className="timeline-label">
          Kiedy najbardziej brakuje wody?
          <span>
            <span className="status-dot text-warning" />
            większe ryzyko
          </span>
        </div>
        <div className="month-ribbon" aria-label="Miesiące podwyższonego ryzyka suszy">
          {months.map((m, i) => (
            <div
              key={m}
              className={`month-tile ${a.critical_months.includes(i + 1) ? "risk" : ""}`}
              title={`${m}: ${a.critical_months.includes(i + 1) ? "większe ryzyko" : "niższe ryzyko"}`}
            >
              {m}
            </div>
          ))}
        </div>
        <SourceLine block={analysis} />
      </section>
      {forecast && forecast.data.series && (
        <div className="forecast-preview">
          <CloudRain size={24} />
          <div>
            <h3>Co przyniosą najbliższe 16 dni?</h3>
            <p>{forecast.data.summary}</p>
            <SourceLine block={forecast} />
          </div>
          <div className="forecast-mini" aria-hidden="true">
            {forecast.data.series?.map((r, i) => (
              <span key={i} style={{ height: `${Math.max(r.rain * 4, 3)}px` }} />
            ))}
          </div>
          <div className="forecast-rain">
            {forecast.data.series ? nf(forecast.data.series.reduce((sum, row) => sum + row.rain, 0), 1) : "—"}{" "}
            <small className="text-xs font-normal">mm</small>
            <p className="text-right">opadów</p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            title="Zobacz prognozę"
            aria-label="Zobacz szczegółową prognozę"
            onClick={() => onData("weather_forecast")}
          >
            <ArrowRight />
          </Button>
        </div>
      )}
      {blocks["crop_calendar"] && (
        <section className="story-section calendar-section">
          <div className="story-heading">
            <Leaf size={19} className="text-primary" />
            <h2>Kalendarz Twojej uprawy</h2>
            <span className="step-subtitle">okres wegetacji i kiedy woda jest najważniejsza</span>
          </div>
          <CropCalendarView block={blocks["crop_calendar"]} asOf={date} />
          <SourceLine block={blocks["crop_calendar"]} />
        </section>
      )}
      <section className="story-section">
        <StoryHeading number={2} title="Dlaczego brakuje wody?" />
        {data?.causes?.map((cause, i) => (
          <FlipCard key={cause.key} items={cause.evidence} blocks={blocks} label="Skąd to wiemy?">
          <div className="cause-row">
            <div className="cause-label">
              <span>
                {i === 0 ? <CloudRain /> : i === 1 ? <Leaf /> : <Waves />}
                {cause.label_pl}
              </span>
              <span className="percent">{cause.share}%</span>
            </div>
            <div
              className="cause-bar"
              role="img"
              aria-label={`${cause.label_pl}: około ${cause.share} procent`}
            >
              <div className="cause-fill" style={{ width: `${cause.share}%` }} />
            </div>
            <p>{cause.explanation}</p>
          </div>
          </FlipCard>
        ))}
        <SourceLine block={analysis} label="Przybliżony udział przyczyn" />
      </section>
      <section className="story-section">
        <StoryHeading number={3} title="Zatrzymaj wodę na polu" extra="Najważniejszy krok" />
        {data?.water_balance && <WaterBalancePanel wb={data.water_balance} onMap={onMap} />}
        <div className="recommendation-list">
          {data?.recommendations
            ?.filter((r) => r.group === "retencja_krajobrazowa")
            .sort((x, y) => x.priority - y.priority)
            .map((r) => (
              <Measure key={r.measure_id} recommendation={r} blocks={blocks} onMap={onMap} />
            ))}
        </div>
      </section>
      <section className="story-section">
        <StoryHeading number={4} title="Zadbaj o glebę" />
        <div className="recommendation-list">
          {data?.recommendations
            ?.filter((r) => r.group === "agrotechnika")
            .sort((x, y) => x.priority - y.priority)
            .map((r) => (
              <Measure key={r.measure_id} recommendation={r} blocks={blocks} onMap={onMap} />
            ))}
        </div>
      </section>
      {irrigation && (
        <section className="story-section">
          <StoryHeading number={5} title="A co z nawadnianiem?" extra="Dopiero na końcu" />
          <FlipCard items={irrigation.evidence} blocks={blocks} label="Skąd to wyliczenie?">
          <div className="irrigation-panel">
            <h3>
              <Eye size={20} />
              {irrigation.recommended === "monitor"
                ? "Obserwuj, zanim zaczniesz"
                : irrigation.recommended === "yes"
                  ? "Rozważ nawadnianie"
                  : irrigation.recommended === "no"
                    ? "Teraz nie nawadniaj"
                    : "Brak oceny nawadniania"}
            </h3>
            <p>{irrigation.summary}</p>
            {irrigation.depletion_mm != null && (
              <div className="irrigation-values">
                <div>
                  <strong>{nf(irrigation.depletion_mm)} mm</strong>
                  <span>Ubyło wody z gleby (z {nf(irrigation.taw_mm)} mm dostępnych)</span>
                </div>
                <div>
                  <strong>{irrigation.days_to_stress != null ? `${irrigation.days_to_stress} dni` : "—"}</strong>
                  <span>{irrigation.stress_date ? `Do stresu wodnego (${formatDate(irrigation.stress_date)})` : "Stresu w horyzoncie nie przewidujemy"}</span>
                </div>
                {irrigation.dose_mm != null && (
                  <div>
                    <strong>{irrigation.dose_mm} mm</strong>
                    <span>Dawka = {doseToVolume(irrigation.dose_mm)} m³/ha</span>
                  </div>
                )}
                {irrigation.yield_loss_pct != null && irrigation.yield_loss_pct >= 1 && (
                  <div>
                    <strong>~{nf(irrigation.yield_loss_pct)}%</strong>
                    <span>Szacowany spadek plonu przez niedobór wody od początku sezonu</span>
                  </div>
                )}
              </div>
            )}
            <SoilWaterChart irr={irrigation} />
            {irrigation.timing && <p>{irrigation.timing}.{irrigation.horizon_days ? ` Horyzont: ${irrigation.horizon_days} dni.` : ""}</p>}
            <SourceLine block={analysis} />
          </div>
          </FlipCard>

        </section>
      )}
      <details className="details-box">
        <summary>
          <Wind size={14} />
          Ograniczenia — co warto sprawdzić w terenie?
        </summary>
        <div className="details-content">
          <ul>
            {data?.limitations?.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        </div>
      </details>
      <details className="details-box">
        <summary>
          <Check size={14} />
          Jak powstała ocena?
        </summary>
        <div className="details-content">
          <ul>
            {data?.method?.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        </div>
      </details>
      <Sources block={analysis} />
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
