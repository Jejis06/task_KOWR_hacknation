/**
 * AgroLegal: „co zrobić, czy wolno, za ile”.
 * - FormalityBadge – plakietka na każdej karcie działania (widoczna bez rozwijania).
 * - LegalPlan – sekcja „Twój plan”: te same działania co w raporcie (kolejność KOWR zostaje w raporcie),
 *   pogrupowane od najłatwiejszego: od razu → po zgłoszeniu → po pozwoleniu.
 * - FundingBadge – status naboru; nigdy nie pokazujemy programu bez informacji, czy dziś można złożyć wniosek.
 * - PondCalculator – ile wody zatrzyma oczko, ile kosztuje (widełki), ile może wrócić z dotacji.
 */
import { CalendarClock, FileText, Hammer, ShieldAlert, ShieldCheck } from "lucide-react";
import type { Formality, FundingRef, Pond, Recommendation } from "@/api/client";

const zl = (v: number | null | undefined, frac = 0) =>
  v == null ? "—" : `${v.toLocaleString("pl-PL", { minimumFractionDigits: frac, maximumFractionDigits: frac })} zł`;
const num = (v: number | null | undefined) => (v == null ? "—" : Math.round(v).toLocaleString("pl-PL"));

const FORMALITY: Record<Formality, { label: string; short: string; cls: string; Icon: typeof ShieldCheck }> = {
  none: { label: "Bez formalności", short: "Możesz zrobić od razu", cls: "f-none", Icon: ShieldCheck },
  notification: { label: "Zgłoszenie wodnoprawne", short: "Najpierw zgłoszenie (ok. 30 dni)", cls: "f-notice", Icon: FileText },
  permit: { label: "Pozwolenie wodnoprawne", short: "Najpierw pozwolenie (miesiące)", cls: "f-permit", Icon: ShieldAlert },
  depends: { label: "Zależy od wykonania", short: "Sprawdź w urzędzie", cls: "f-permit", Icon: ShieldAlert },
};

/** Plakietka formalności – działa też dla pozycji z LLM (tylko formality). */
export type FormalityBadgeProps = {
  formality?: Formality;
  formality_label?: string | null;
  formality_note?: string | null;
  fee_pln?: number | null;
};
export function FormalityBadge({ r }: { r: FormalityBadgeProps }) {
  const f = FORMALITY[r.formality ?? "none"];
  return (
    <span className={`formality-badge ${f.cls}`} title={r.formality_note ?? f.label}>
      <f.Icon size={12} aria-hidden="true" />
      {r.formality_label ?? f.label}
      {r.fee_pln != null && <> · {zl(r.fee_pln, 2)}</>}
    </span>
  );
}

export function FundingBadge({ f }: { f: FundingRef }) {
  const cls = f.call_kind === "closed" ? "c-closed" : f.call_kind === "unknown" ? "c-unknown" : "c-open";
  return <span className={`call-badge ${cls}`}>{f.call_label ?? "termin naboru do sprawdzenia"}</span>;
}

/** Szczegóły prawne pod kartą działania – zastępują ogólnik „sprawdź, czy potrzebne jest zgłoszenie”. */
export function LegalDetails({ r }: { r: Recommendation }) {
  return (
    <>
      <p className="mt-2">
        <strong>Czy wolno?</strong> {r.formality_label ?? "Bez formalności wodnych"}.
        {r.formality_note && <> {r.formality_note}</>}
      </p>
      {r.office && <p><strong>Gdzie złożyć:</strong> {r.office}.</p>}
      {(r.fee_pln != null || r.wait) && (
        <p>
          {r.fee_pln != null && <><strong>Opłata urzędowa:</strong> {zl(r.fee_pln, 2)}. </>}
          {r.wait && <><strong>Ile czekasz:</strong> {r.wait}.</>}
        </p>
      )}
    </>
  );
}

export function FundingList({ funding }: { funding?: FundingRef[] }) {
  if (!funding?.length) return <p className="mt-2"><strong>Pieniądze:</strong> brak programu dla tego działania.</p>;
  return (
    <div className="mt-2">
      <strong>Pieniądze:</strong>
      <ul className="funding-list">
        {funding.map((f) => (
          <li key={f.name}>
            {f.url ? <a href={f.url} target="_blank" rel="noreferrer" className="underline">{f.name}</a> : f.name}{" "}
            <FundingBadge f={f} />
            {f.scope && <div className="funding-scope">{f.scope}</div>}
          </li>
        ))}
      </ul>
    </div>
  );
}

const COLUMNS: { key: string; title: string; match: (f: Formality) => boolean; cls: string; Icon: typeof ShieldCheck }[] = [
  { key: "now", title: "Możesz zrobić od razu", match: (f) => f === "none", cls: "f-none", Icon: ShieldCheck },
  { key: "notice", title: "Po zgłoszeniu (ok. 30 dni)", match: (f) => f === "notification", cls: "f-notice", Icon: FileText },
  { key: "permit", title: "Po pozwoleniu lub uzgodnieniu", match: (f) => f === "permit" || f === "depends", cls: "f-permit", Icon: ShieldAlert },
];

export function LegalPlan({ recs, onPrepare, bare }: { recs: Recommendation[]; onPrepare?: (r: Recommendation) => void; bare?: boolean }) {
  if (!recs.length) return null;
  return (
    <section className={bare ? "legal-plan" : "story-section legal-plan"} aria-labelledby={bare ? undefined : "legal-plan-title"}>
      {!bare && (
        <div className="story-heading">
          <ShieldCheck size={19} className="text-primary" />
          <h2 id="legal-plan-title">Twój plan: co wolno i za ile</h2>
          <span className="step-subtitle">od najłatwiejszego</span>
        </div>
      )}
      <div className="plan-columns">
        {COLUMNS.map((c) => {
          const items = recs.filter((r) => c.match(r.formality ?? "none"));
          return (
            <div key={c.key} className={`plan-col ${c.cls}`}>
              <h3><c.Icon size={16} aria-hidden="true" />{c.title}</h3>
              {items.length === 0 ? (
                <p className="plan-empty">Nic w tej grupie.</p>
              ) : (
                <ul>
                  {items.map((r) => {
                    const money = r.funding?.find((f) => f.call_kind !== "closed") ?? r.funding?.[0];
                    return (
                      <li key={r.measure_id}>
                        <strong>{r.title}</strong>
                        {r.fee_pln != null && <span className="plan-meta">opłata {zl(r.fee_pln, 2)}</span>}
                        {money && (
                          <span className="plan-meta">
                            💰 {money.name.replace(/^Ekoschemat /, "ekoschemat ")} – <FundingBadge f={money} />
                          </span>
                        )}
                        {r.formality === "notification" && onPrepare && (
                          <button type="button" className="plan-action" onClick={() => onPrepare(r)}>
                            <FileText size={14} aria-hidden="true" /> Przygotuj zgłoszenie
                          </button>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          );
        })}
      </div>
      <p className="plan-note">
        <CalendarClock size={13} aria-hidden="true" /> Zgłoszenie lub pozwolenie złóż <strong>przed</strong> rozpoczęciem prac.
        Kwalifikację potwierdza Nadzór Wodny lub Zarząd Zlewni Wód Polskich – to informacja orientacyjna, nie porada prawna.
      </p>
    </section>
  );
}

export function PondCalculator({ pond }: { pond: Pond }) {
  return (
    <div className="pond-calc">
      <h3><Hammer size={17} aria-hidden="true" /> Oczko w zagłębieniu – ile wody i za ile?</h3>
      <div className="pond-grid">
        <div><strong>{num(pond.volume_m3)} m³</strong><span>{pond.capped ? "pojemność oczka" : "pojemność zagłębienia"}{pond.area_m2 ? ` (ok. ${num(pond.area_m2)} m²)` : ""}</span></div>
        <div><strong>{num(pond.stored_per_year_m3)} m³</strong><span>wody zatrzymanej w roku (górny szacunek)</span></div>
        <div><strong>{zl(pond.cost_pln_min)} – {zl(pond.cost_pln_max)}</strong><span>koszt wykopu (szacunek)</span></div>
        <div><strong>do {zl(pond.subsidy_pln_max)}</strong><span>możliwy zwrot z dotacji</span></div>
      </div>
      <p className="text-xs">
        {pond.capped && (
          <>Całe zagłębienie ma ok. {num(pond.depression_area_m2)} m² – liczymy oczko <strong>do 5000 m²</strong> w jego najniższej
          części, bo takie wymaga tylko zgłoszenia. Oczko na całym zagłębieniu potrzebowałoby pozwolenia wodnoprawnego (miesiące). </>
        )}
        {pond.needs_permit
          ? "W tej wielkości potrzebne jest pozwolenie wodnoprawne."
          : `Do 5000 m² i 3 m głębokości wystarczy zgłoszenie wodnoprawne${pond.fee_pln != null ? ` (opłata ${zl(pond.fee_pln, 2)})` : ""}.`}{" "}
        {pond.covers_season_pct != null && <>Pokryje ok. {pond.covers_season_pct.toLocaleString("pl-PL")}% sezonowego niedoboru wody na działce. </>}
      </p>
      <p className="text-xs text-muted-foreground">
        Koszt: {pond.cost_basis}. Dotacja: {pond.subsidy_note}. Nie wyceniamy plonu – to zależy od ceny i pogody.
      </p>
    </div>
  );
}
