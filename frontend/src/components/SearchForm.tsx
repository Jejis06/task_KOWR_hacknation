import { useState } from "react";
import type { Query } from "../api/client";
import type { CropItem } from "../api/types";

const today = () => new Date().toISOString().slice(0, 10);
const minDate = () => `${new Date().getFullYear() - 10}-01-01`;

export function SearchForm(props: { crops: CropItem[]; busy: boolean; onSubmit: (q: Query) => void }) {
  const [id, setId] = useState("");
  const [date, setDate] = useState(today());
  const [crop, setCrop] = useState("");

  return (
    <form
      className="search"
      onSubmit={(e) => {
        e.preventDefault();
        if (id.trim()) props.onSubmit({ id: id.trim(), date, crop: crop || undefined });
      }}
    >
      <label>
        Numer działki
        <input value={id} onChange={(e) => setId(e.target.value)} placeholder="np. 146505_8.0116.5 lub „Mokotów 5”" />
      </label>
      <label>
        Data analizy
        <input type="date" value={date} min={minDate()} max={today()} onChange={(e) => setDate(e.target.value)} />
      </label>
      <label>
        Uprawa
        <select value={crop} onChange={(e) => setCrop(e.target.value)}>
          <option value="">— wybierz —</option>
          {props.crops.map((c) => (
            <option key={c.id} value={c.id}>{c.name_pl}</option>
          ))}
        </select>
      </label>
      <button type="submit" disabled={props.busy || !id.trim()}>{props.busy ? "Analizuję…" : "Sprawdź działkę"}</button>
      <p className="hint">…albo kliknij działkę na mapie.</p>
    </form>
  );
}
