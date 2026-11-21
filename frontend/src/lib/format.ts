// Formatowanie liczb, dat i trybów danych – po polsku, zawsze z jednostką.
import type { Provenance } from "../api/types";

const nf = (digits: number) => new Intl.NumberFormat("pl-PL", { maximumFractionDigits: digits, minimumFractionDigits: 0 });

/** Liczba z jednostką; brak wartości → „brak danych” (nigdy samo „–” bez wyjaśnienia). */
export function num(v: number | null | undefined, unit: string, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "brak danych";
  return `${nf(digits).format(v)}${unit ? ` ${unit}` : ""}`;
}

/** Liczba ze znakiem (+12 mm / −30 mm). */
export function signed(v: number | null | undefined, unit: string, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "brak danych";
  const s = nf(digits).format(Math.abs(v));
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}${s} ${unit}`;
}

export function dateStr(iso: string | null | undefined): string {
  if (!iso) return "brak daty";
  const d = new Date(iso.length <= 10 ? `${iso}T12:00:00` : iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("pl-PL", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export function dateTimeStr(iso: string | null | undefined): string {
  if (!iso) return "brak daty";
  const d = new Date(iso);
  return d.toLocaleString("pl-PL", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export const MONTHS_SHORT = ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"];

export function modeLabel(p: Provenance): string {
  if (p.mode === "live") return "pobrane na żywo";
  if (p.mode === "cached") return "z pamięci podręcznej (wcześniej pobrane na żywo)";
  return `kopia lokalna${p.snapshot_date ? ` z ${dateStr(p.snapshot_date)}` : ""}`;
}

export const STATUS_LABEL: Record<string, string> = {
  ok: "dane kompletne", partial: "dane częściowe", no_data: "brak danych", not_applicable: "nie dotyczy",
  error: "błąd źródła", not_implemented: "w przygotowaniu", loading: "pobieram…", idle: "",
};

export const KNOWLEDGE_STATUS_LABEL: Record<string, string> = {
  OK: "potwierdzone w źródle", DO_WERYFIKACJI: "do weryfikacji", SZACUNEK: "szacunek",
};

/** Data analizy w formacie YYYY-MM-DD w lokalnej strefie (nie UTC – inaczej po 23:00 skacze dzień). */
export function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
