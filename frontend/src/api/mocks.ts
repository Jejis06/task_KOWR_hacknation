// Dane demonstracyjne (VITE_USE_MOCKS=true) – syntetyczne, oznaczone w UI jako „Wersja demonstracyjna”.
import { blockDefinitions, DEMO_ID, type DataBlock, type DataPayload, type Evidence, type ParcelRef, type Polygon,
  type SeriesRow } from "./client";

export const parcel: ParcelRef = {
  id: DEMO_ID,
  region_name: "Wielkopolska",
  commune: "Kórnik",
  county: "poznański",
  voivodeship: "wielkopolskie",
  parcel_number: "52/16",
  area_ha: 8.42,
  centroid: [17.0921, 52.2095],
  bbox: [17.0895, 52.2078, 17.0947, 52.2112],
  geometry: {
    type: "Polygon",
    coordinates: [
      [
        [17.0895, 52.2108],
        [17.0937, 52.2112],
        [17.0947, 52.2083],
        [17.091, 52.2078],
        [17.0895, 52.2108],
      ],
    ],
  },
};
export const depression: Polygon = {
  type: "Polygon",
  coordinates: [
    [
      [17.0916, 52.2092],
      [17.0923, 52.2093],
      [17.0926, 52.2089],
      [17.0919, 52.2087],
      [17.0916, 52.2092],
    ],
  ],
};

const months = ["Sty", "Lut", "Mar", "Kwi", "Maj", "Cze", "Lip", "Sie", "Wrz", "Paź", "Lis", "Gru"];
const rain = [32, 24, 35, 28, 41, 32, 36, 48, 42, 38, 37, 34];
const normal = [35, 28, 38, 42, 57, 65, 76, 63, 49, 42, 39, 39];
function monthly(): SeriesRow[] {
  return months.map((label, i) => ({
    label,
    rain: rain[i] ?? 0,
    normal: normal[i] ?? 0,
    evaporation: [10, 16, 34, 57, 90, 109, 116, 96, 61, 32, 14, 9][i] ?? 0,
    value: [0.21, 0.22, 0.28, 0.45, 0.67, 0.61, 0.48, 0.42, 0.35, 0.3, 0.24, 0.22][i] ?? 0,
  }));
}
export function mockBlock(key: string, date: string, crop = "wheat"): DataBlock {
  const year = Number(date.slice(0, 4));
  const years = Array.from({ length: 10 }, (_, i) => year - 9 + i);
  const dryYears = [2018, 2019, 2022, 2023];
  const history = years.map((y) => ({
    label: String(y),
    rain: dryYears.includes(y) ? 235 : 365,
    normal: 360,
    evaporation: 475,
    value: dryYears.includes(y) ? 4.1 : 6.3,
  }));
  const ev = (text: string, block: string): Evidence => ({ text, block });
  const dataByKey: Record<string, DataPayload> = {
    weather_history: {
      summary: "W sezonie wegetacyjnym opadów jest mniej niż zwykle.",
      series: monthly(),
      rows: history.map((r) => ({
        label: r.label,
        value: `${r.rain} mm`,
        detail: `Zwykle ${r.normal} mm · kwiecień–wrzesień`,
        dry: dryYears.includes(Number(r.label)),
      })),
      metrics: [
        { label: "Opady w ostatnich 60 dniach", value: "76 mm" },
        { label: "Zwykle w tym okresie", value: "138 mm" },
        { label: "Parowanie", value: "188 mm", term: "ET₀" },
      ],
    },
    weather_forecast: {
      summary: "Najbliższe opady nie uzupełnią całego niedoboru wody.",
      series: Array.from({ length: 16 }, (_, i) => ({
        label: `${i + 1}`,
        rain: [0, 0, 2, 6, 3, 0, 0, 0, 4, 8, 1, 0, 0, 2, 0, 0][i] ?? 0,
        normal: 0,
        evaporation: 3.5 + (i % 3) * 0.7,
        value: 0,
      })),
      metrics: [
        { label: "Suma opadów", value: "26 mm" },
        { label: "Parowanie", value: "67 mm", term: "ET₀" },
        { label: "Zmiana bilansu", value: "−41 mm" },
      ],
    },
    drought: {
      summary: "Duży niedobór wody. Gleba lekka szybko traci wilgoć.",
      balance_mm: -112,
      normal_mm: -38,
      series: history,
      metrics: [
        { label: "Bilans wody z 60 dni", value: "−112 mm", term: "KBW" },
        { label: "Zwykły bilans", value: "−38 mm" },
        {
          label: "Suche sezony",
          value: `${years.filter((y) => dryYears.includes(y)).length} z 10`,
        },
      ],
    },
    soil: {
      summary: "Gleba piaszczysto-gliniasta. Niewielki zapas wody dla roślin.",
      metrics: [
        { label: "Woda dostępna dla roślin", value: "85 mm" },
        { label: "Materia organiczna", value: "1,6%" },
        { label: "Głębokość oceny", value: "0–100 cm" },
      ],
      rows: [
        { label: "Piasek", value: "64%", detail: "Woda szybko przesiąka" },
        { label: "Pył", value: "24%", detail: "Pomaga zatrzymać wilgoć" },
        { label: "Glina", value: "12%", detail: "Niewielki udział" },
      ],
    },
    terrain: {
      summary: "Łagodny stok z naturalnym obniżeniem w południowej części pola.",
      metrics: [
        { label: "Spadek terenu", value: "2,4%" },
        { label: "Powierzchnia obniżenia", value: "2 400 m²" },
        { label: "Głębokość obniżenia", value: "0,6 m" },
      ],
      rows: [
        { label: "Położenie", value: "Łagodny stok", detail: "Woda spływa ku południu" },
        {
          label: "Obniżenie terenu",
          value: "Do sprawdzenia",
          detail: "Możliwe miejsce zatrzymania wody",
          mapId: "depression",
        },
      ],
    },
    hydrology: {
      summary: "Rów odwadniający może przyspieszać odpływ. Pole poza strefą zalewową.",
      metrics: [
        { label: "Odległość do rowu", value: "140 m" },
        { label: "Odległość do stawu", value: "380 m" },
        { label: "Strefa zalewowa", value: "Poza strefą" },
      ],
      rows: [
        {
          label: "Rów odwadniający",
          value: "140 m",
          detail: "Odpływ w kierunku południowym",
          mapId: "ditch",
        },
        {
          label: "Niewielki staw",
          value: "380 m",
          detail: "Zbiornik poza granicą działki",
          mapId: "pond",
        },
      ],
    },
    vegetation: {
      summary: "Rośliny słabiej rosną w wyższej, suchej części pola.",
      series: monthly(),
      metrics: [
        { label: "Wskaźnik zieloności", value: "0,48", term: "NDVI" },
        { label: "Zwykle w tym okresie", value: "0,65" },
      ],
    },
    land_cover: {
      summary: "Pole otwarte, z niewielką ilością trwałej roślinności.",
      rows: [
        { label: "Grunty orne", value: "92%", detail: "Dominująca powierzchnia" },
        { label: "Trawy i miedze", value: "6%", detail: "Wzdłuż granic" },
        { label: "Drzewa i krzewy", value: "2%", detail: "W otoczeniu rowu" },
      ],
    },
    yields: {
      summary: "Przykładowe plony pokazują wpływ suchych sezonów. To nie są dane gospodarstwa.",
      series: history,
      metrics: [
        { label: "Przeciętny plon", value: "5,4 t/ha" },
        { label: "Przykład dla suchego roku", value: "4,1 t/ha" },
      ],
    },
    protected_areas: {
      summary:
        "Działka poza obszarem chronionym. W przykładzie brak obszarów chronionych w promieniu 1 km.",
      metrics: [
        { label: "Na działce", value: "Brak" },
        { label: "W promieniu 1 km", value: "Brak" },
      ],
    },
    crop_calendar: !crop
      ? { summary: "Wybierz uprawę, aby zobaczyć jej kalendarz.", rows: [] }
      : {
          summary:
            crop === "maize"
              ? "Kukurydza najbardziej potrzebuje wody w czasie kwitnienia."
              : crop === "potato"
                ? "Ziemniaki najbardziej potrzebują wody w czasie tworzenia i wzrostu bulw."
                : "Pszenica najbardziej potrzebuje wody w czasie kłoszenia i nalewania ziarna.",
          rows: [
            {
              label: "Siew",
              value:
                crop === "maize"
                  ? "Kwiecień–maj"
                  : crop === "potato"
                    ? "Kwiecień"
                    : "Wrzesień–październik",
              detail: "Termin zależy od odmiany i pogody",
            },
            {
              label: "Największa potrzeba wody",
              value:
                crop === "maize"
                  ? "Lipiec–sierpień"
                  : crop === "potato"
                    ? "Czerwiec–sierpień"
                    : "Maj–czerwiec",
              detail: "Regularnie sprawdzaj wilgotność gleby",
            },
            {
              label: "Zbiór",
              value:
                crop === "maize"
                  ? "Wrzesień–październik"
                  : crop === "potato"
                    ? "Wrzesień"
                    : "Lipiec–sierpień",
              detail: "Po zbiorze rozważ międzyplon",
            },
          ],
        },
    legal_context: {
      summary:
        "Formalności zależą od rozmiaru i miejsca prac. Poniższe warianty są przykładem, nie poradą prawną.",
      rows: [
        {
          label: "Międzyplon i ściółkowanie",
          value: "Bez formalności wodnych",
          detail: "Przykładowy koszt urzędowy: 0 zł",
        },
        {
          label: "Zatrzymanie wody w obniżeniu",
          value: "Do ustalenia",
          detail: "Możliwe zgłoszenie lub pozwolenie; opłata wymaga sprawdzenia",
        },
        {
          label: "Zastawka na rowie",
          value: "Do ustalenia",
          detail: "Potrzebna zgoda właściciela i weryfikacja formalności",
        },
        {
          label: "Pobór wody do nawadniania",
          value: "Do ustalenia",
          detail: "Możliwe pozwolenie wodnoprawne; opłata wymaga sprawdzenia",
        },
        {
          label: "Wsparcie na zatrzymanie wody",
          value: "Sprawdź nabory",
          detail: "Brak potwierdzonego otwartego naboru w danych demonstracyjnych",
        },
        {
          label: "Wsparcie na praktyki glebowe",
          value: "Sprawdź warunki",
          detail: "Brak potwierdzonej kwoty i kwalifikowalności",
        },
      ],
    },
    analysis: {
      assessment: {
        current_level: "high",
        current_label_pl: "Twoje pole potrzebuje wody",
        current_summary:
          "Opadów jest za mało, a woda szybko ucieka z pola. Najpierw zatrzymaj tę, która już na nie trafia.",
        historical_level: "high",
        historical_label_pl: "Susza wraca na to pole",
        historical_summary: "Najtrudniejsze były sezony 2018, 2019, 2022 i 2023.",
        drought_years: years.filter((y) => dryYears.includes(y)),
        critical_months: [5, 6, 7, 8],
        confidence: "Średnia",
        evidence: [
          ev("Bilans wody: −112 mm w ostatnich 60 dniach.", "drought"),
          ev("Lekka gleba magazynuje około 85 mm wody.", "soil"),
          ev("Rów może przyspieszać odpływ z pola.", "hydrology"),
        ],
      },
      causes: [
        {
          key: "weather",
          label_pl: "Za mało deszczu",
          share: 45,
          explanation: "Opady nie wyrównują strat przez parowanie.",
          evidence: [ev("76 mm opadów wobec zwykłych 138 mm.", "weather_history")],
        },
        {
          key: "soil",
          label_pl: "Gleba słabo zatrzymuje wodę",
          share: 30,
          explanation: "Dużo piasku, mało materii organicznej.",
          evidence: [ev("64% piasku i 1,6% materii organicznej.", "soil")],
        },
        {
          key: "runoff",
          label_pl: "Woda odpływa z pola",
          share: 25,
          explanation: "Łagodny stok i pobliski rów ułatwiają odpływ.",
          evidence: [ev("Spadek 2,4%; rów w odległości 140 m.", "terrain")],
        },
      ],
      recommendations: [
        {
          measure_id: "pond",
          group: "retencja_krajobrazowa",
          title: "Zatrzymaj wodę w obniżeniu pola",
          why: "Masz naturalne miejsce, w którym zbiera się woda. Sprawdź możliwość utworzenia niewielkiego zbiornika.",
          priority: 1,
          when: "Po zbiorach, po oględzinach terenu",
          where_geojson: depression,
          legal_ids: ["depression"],
          funding_ids: ["retention"],
          evidence: [ev("Obniżenie około 2 400 m², głębokość 0,6 m.", "terrain")],
        },
        {
          measure_id: "weir",
          group: "retencja_krajobrazowa",
          title: "Rozważ zastawkę na rowie",
          why: "Spowolnienie odpływu może utrzymać wodę dłużej w okolicy pola.",
          priority: 2,
          when: "Po uzgodnieniu z właścicielem rowu",
          where_geojson: null,
          legal_ids: ["ditch"],
          funding_ids: ["retention"],
          evidence: [ev("Rów odwadniający w odległości 140 m.", "hydrology")],
        },
        {
          measure_id: "cover",
          group: "agrotechnika",
          title: "Okryj glebę po zbiorach",
          why: "Międzyplon i resztki pożniwne ograniczają parowanie i poprawiają strukturę gleby.",
          priority: 3,
          when: "Po zbiorze; dobierz gatunki do zapasu wilgoci",
          where_geojson: null,
          legal_ids: ["soil"],
          funding_ids: ["soil"],
          evidence: [ev("Mały udział materii organicznej: 1,6%.", "soil")],
        },
        {
          measure_id: "irrigation",
          group: "nawadnianie",
          title: "Nawadniaj tylko po sprawdzeniu gleby",
          why: "Nawadnianie uzupełnia niedobór, ale nie usuwa przyczyn utraty wody.",
          priority: 4,
          when: "Po pomiarze wilgotności i sprawdzeniu prognozy",
          where_geojson: null,
          legal_ids: ["irrigation"],
          funding_ids: [],
          evidence: [ev("Prognozowany bilans: −41 mm.", "weather_forecast")],
        },
      ],
      irrigation: {
        recommended: "monitor",
        summary: "Obserwuj glebę. Nie uruchamiaj nawadniania wyłącznie na podstawie tego raportu.",
        deficit_mm: 35,
        dose_mm: 20,
        horizon_days: 7,
        timing: "Rano lub wieczorem, tylko gdy pomiar potwierdzi niedobór.",
        evidence: [ev("Przykładowy niedobór w strefie korzeni: 35 mm.", "soil")],
      },
      limitations: [
        "To scenariusz demonstracyjny, nie ocena rzeczywistej działki.",
        "Udziały przyczyn są przybliżeniem modelu, nie wynikiem bezpośredniego pomiaru.",
        "Brak pomiarów wilgotności z pola i potwierdzenia stanu rowu.",
        "Formalności, opłaty i dostępność wsparcia wymagają aktualnej weryfikacji.",
      ],
      method: [
        "Porównanie opadów i parowania w ostatnich 60 dniach.",
        "Porównanie dziesięciu sezonów wegetacyjnych.",
        "Łączna ocena gleby, ukształtowania terenu i odpływu.",
      ],
    },
  };
  return {
    key,
    title: blockDefinitions.find((b) => b.key === key)?.title ?? key,
    status: key === "yields" || key === "legal_context" ? "partial" : "ok",
    data: dataByKey[key] ?? {},
    provenance: [
      {
        source_name: "Scenariusz demonstracyjny — obliczenia własne",
        source_url: null,
        query_url: null,
        licence: "Dane syntetyczne, CC0",
        retrieved_at: `${date}T12:00:00Z`,
        mode: "local_snapshot",
        data_as_of: date,
        notes: "Wartości syntetyczne. Nie pochodzą z pomiarów ani z urzędowych rejestrów.",
      },
    ],
    uncertainty:
      key === "legal_context"
        ? ["Nie potwierdzono aktualnych opłat ani naborów."]
        : ["Przykładowe wartości; przed działaniem potrzebne pomiary i oględziny."],
    messages: [],
    elapsed_ms: 150,
  };
}
