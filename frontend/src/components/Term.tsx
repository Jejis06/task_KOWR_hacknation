// Skróty z objaśnieniem: <Term k="KBW" /> → „KBW” z dymkiem (hover / fokus / dotyk).
import { useState } from "react";

export const GLOSSARY: Record<string, string> = {
  KBW: "Klimatyczny bilans wodny = opad minus parowanie (ET₀). Wartość ujemna oznacza, że roślinom ubywa wody.",
  NDVI: "Wskaźnik zieleni roślin z satelity (0 = goła ziemia, ok. 0,8 = gęste, zdrowe rośliny).",
  NDMI: "Wskaźnik wilgotności roślin z satelity – im niższy, tym bardziej przesuszone liście.",
  "ET₀": "Parowanie wskaźnikowe – ile wody w mm odparowałoby z trawnika przy danej pogodzie (metoda FAO-56).",
  Kc: "Współczynnik uprawy – mnożnik ET₀; mówi, ile wody zużywa dana uprawa w danej fazie.",
  TUZ: "Trwałe użytki zielone – łąki i pastwiska.",
  SMSR: "System Monitoringu Suszy Rolniczej IUNG-PIB w Puławach – oficjalna ocena suszy w gminach.",
  "IUNG-PIB": "Instytut Uprawy Nawożenia i Gleboznawstwa – Państwowy Instytut Badawczy w Puławach.",
  EDO: "Europejskie Obserwatorium Suszy (Copernicus).",
  NMT: "Numeryczny model terenu – dokładna mapa wysokości z pomiaru laserowego (GUGiK).",
  TWI: "Wskaźnik wilgotności terenu – im wyższy, tym chętniej zbiera się tam woda.",
  TPI: "Wskaźnik położenia – czy miejsce jest wyżej (górka) czy niżej (dołek) niż okolica.",
  GZWP: "Główny Zbiornik Wód Podziemnych – duże, chronione zasoby wody pod ziemią.",
  MHP: "Mapa hydrogeologiczna Polski (PIG-PIB).",
  JCWP: "Jednolita część wód powierzchniowych – jednostka, w której Wody Polskie oceniają stan rzek.",
  ISOK: "Informatyczny System Osłony Kraju – mapy zagrożenia powodziowego Wód Polskich.",
  RDOŚ: "Regionalna Dyrekcja Ochrony Środowiska.",
  EGiB: "Ewidencja gruntów i budynków (starostwo).",
  OChK: "Obszar chronionego krajobrazu.",
  "FAO-56": "Międzynarodowa metoda liczenia potrzeb wodnych roślin (FAO, Allen i in.).",
  ARiMR: "Agencja Restrukturyzacji i Modernizacji Rolnictwa.",
  ULDK: "Usługa lokalizacji działek katastralnych GUGiK.",
  GUS: "Główny Urząd Statystyczny – plony średnie dla powiatu, nie dla Twojego pola.",
};

export function Term({ k, children }: { k: keyof typeof GLOSSARY | string; children?: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const text = GLOSSARY[k];
  if (!text) return <>{children ?? k}</>;
  return (
    <span className="term">
      <button type="button" className="term-btn" aria-expanded={open} aria-label={`${k}: ${text}`}
        onClick={() => setOpen((o) => !o)} onBlur={() => setOpen(false)}>
        {children ?? k}
      </button>
      <span role="tooltip" className={`term-tip${open ? " open" : ""}`}>{text}</span>
    </span>
  );
}
