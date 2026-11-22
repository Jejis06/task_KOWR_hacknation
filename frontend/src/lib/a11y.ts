import { useEffect, useState } from "react";

/** Ustawienia dostępności (lupa, wysoki kontrast) – zapamiętywane w przeglądarce; bez dostępu do pamięci działają do końca wizyty. */
export type A11y = { zoom: 100 | 125 | 150; contrast: boolean };
const KEY = "zatrzymaj-wode-a11y";

function load(): A11y {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? "null") as Partial<A11y> | null;
    return { zoom: v?.zoom === 125 || v?.zoom === 150 ? v.zoom : 100, contrast: !!v?.contrast };
  } catch {
    return { zoom: 100, contrast: false };
  }
}

export function useA11y() {
  const [a11y, setA11y] = useState<A11y>(load);
  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("a11y-zoom-125", a11y.zoom === 125);
    root.classList.toggle("a11y-zoom-150", a11y.zoom === 150);
    root.classList.toggle("a11y-contrast", a11y.contrast);
    try {
      localStorage.setItem(KEY, JSON.stringify(a11y));
    } catch {
      /* prywatne okno / blokada pamięci – ustawienie działa tylko w tej wizycie */
    }
  }, [a11y]);
  const cycleZoom = () => setA11y((s) => ({ ...s, zoom: s.zoom === 100 ? 125 : s.zoom === 125 ? 150 : 100 }));
  const toggleContrast = () => setA11y((s) => ({ ...s, contrast: !s.contrast }));
  return { a11y, cycleZoom, toggleContrast };
}
