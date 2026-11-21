import { useState } from "react";
import type { CropItem } from "../api/types";
import { todayIso } from "../lib/format";

// 146505_8.0116.5 | 141201_1.0001.123/4 | 060406_2.0136.AR_5.1077/6
export const PARCEL_ID_RE = /^\d{6}_\d\.\d{4}(\.AR_\d+)?\.[\w/]+$/;
// „Słupia Wielka 7”, „Mokotów 123/4” – nazwa obrębu + numer (ULDK GetParcelByIdOrNr)
export const REGION_NUMBER_RE = /^\p{L}[\p{L}\s.\-]*\s+\d+[\w/]*$/u;

export function validateParcel(text: string): string | null {
  const t = text.trim();
  if (!t) return "Wpisz numer działki albo kliknij działkę na mapie.";
  if (PARCEL_ID_RE.test(t) || REGION_NUMBER_RE.test(t)) return null;
  if (/^\d{6}_\d/.test(t)) return "Identyfikator wygląda na niepełny. Wzór: 302504_5.0024.7 (gmina_typ.obręb.numer).";
  return "Nie rozpoznaję formatu. Wpisz pełny identyfikator (np. 302504_5.0024.7) albo nazwę obrębu i numer (np. Słupia Wielka 7).";
}

export const minDate = () => `${new Date().getFullYear() - 10}-01-01`;

export interface FormState { id: string; date: string; crop: string }

export function SearchForm(props: {
  crops: CropItem[]; busy: boolean; value: FormState; onChange: (v: FormState) => void; onSubmit: () => void;
}) {
  const [touched, setTouched] = useState(false);
  const { value: v, onChange } = props;
  const err = touched ? validateParcel(v.id) : null;
  const dateErr = v.date > todayIso() ? "Data nie może być z przyszłości." : v.date < minDate() ? "Analiza obejmuje ostatnie 10 lat." : null;

  return (
    <form className="search no-print" noValidate onSubmit={(e) => {
      e.preventDefault(); setTouched(true);
      if (!validateParcel(v.id) && !dateErr) props.onSubmit();
    }}>
      <label htmlFor="pid">Numer działki</label>
      <input id="pid" value={v.id} inputMode="text" autoComplete="off" spellCheck={false}
        aria-invalid={!!err} aria-describedby="pid-hint"
        onChange={(e) => onChange({ ...v, id: e.target.value })} onBlur={() => v.id && setTouched(true)}
        placeholder="np. 302504_5.0024.7 lub Słupia Wielka 7" />
      <p id="pid-hint" className={err ? "field-error" : "hint"}>
        {err ?? "Identyfikator znajdziesz w wypisie z rejestru gruntów albo na geoportal.gov.pl. Możesz też kliknąć pole na mapie."}
      </p>

      <div className="row2">
        <div>
          <label htmlFor="date">Data analizy</label>
          <input id="date" type="date" value={v.date} min={minDate()} max={todayIso()} aria-invalid={!!dateErr}
            onChange={(e) => onChange({ ...v, date: e.target.value })} />
          {dateErr ? <p className="field-error">{dateErr}</p> : <p className="hint">Dziś albo dowolny dzień z ostatnich 10 lat.</p>}
        </div>
        <div>
          <label htmlFor="crop">Uprawa</label>
          <select id="crop" value={v.crop} onChange={(e) => onChange({ ...v, crop: e.target.value })}>
            <option value="">— bez uprawy —</option>
            {props.crops.map((c) => <option key={c.id} value={c.id}>{c.name_pl}</option>)}
          </select>
          <p className="hint">Najlepiej ta, której najbardziej brakuje wody.</p>
        </div>
      </div>
      <button type="submit" className="btn-primary" disabled={props.busy}>{props.busy ? "Pobieram dane…" : "Sprawdź działkę"}</button>
    </form>
  );
}
