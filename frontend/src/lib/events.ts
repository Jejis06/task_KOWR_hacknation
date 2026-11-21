// Lekka szyna zdarzeń między mapą, kartą „Wody” i stroną (bez globalnego store).
// water:focus   – pokaż zbiornik/ciek o indeksie `index` (indeks w hydrology.nearest_water) na mapie
// water:details – przejdź do widoku analityka i podświetl wiersz tego zbiornika
export type WaterEvent = { index: number };
export const emit = (name: "water:focus" | "water:details", detail: WaterEvent) =>
  window.dispatchEvent(new CustomEvent<WaterEvent>(name, { detail }));
export function on(name: "water:focus" | "water:details", fn: (d: WaterEvent) => void) {
  const h = (e: Event) => fn((e as CustomEvent<WaterEvent>).detail);
  window.addEventListener(name, h);
  return () => window.removeEventListener(name, h);
}
export const fmtDist = (m: number) => (m >= 1000 ? `${(m / 1000).toFixed(1).replace(".", ",")} km` : `${Math.round(m)} m`);
