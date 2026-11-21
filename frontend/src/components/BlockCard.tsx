import { Component, type ReactNode } from "react";
import type {
  BlockInfo, CropCalendarInfo, DataBlock, DroughtHistory, HydrologyInfo, LandCoverInfo, LegalContextInfo,
  ProtectedAreasInfo, SoilInfo, TerrainInfo, VegetationInfo, WeatherForecast, WeatherHistory, YieldInfo,
} from "../api/types";
import { dateStr, STATUS_LABEL } from "../lib/format";
import { SourceList } from "./SourceList";
import { ForecastView, WeatherView } from "./blocks/WeatherView";
import {
  DroughtView, HydrologyView, LandCoverView, ProtectedView, SoilView, TerrainView, VegetationView, YieldsView,
} from "./blocks/EnvViews";
import { CalendarView } from "./blocks/CalendarView";
import { LegalView } from "./blocks/LegalView";

// Prognoza: ograniczenia są w panelu „Skąd te dane” – na karcie tylko zaśmiecały widok.
const HIDE_UNCERTAINTY = new Set(["weather_forecast"]);
/** Krótka nazwa źródła do jednej linii (pełna lista po rozwinięciu). */
const shortName = (n: string) => (n.length > 60 ? `${n.slice(0, 57).trimEnd()}…` : n);

const EMPTY_TEXT: Record<string, string> = {
  not_implemented: "Ten blok jest jeszcze w przygotowaniu – dane pojawią się w kolejnej wersji aplikacji.",
  no_data: "Źródło odpowiedziało, ale nie ma danych dla tej działki lub daty.",
  not_applicable: "Te dane nie dotyczą tej działki lub tej pory roku.",
  error: "Nie udało się pobrać danych ze źródła. Pozostałe bloki działają – spróbuj ponownie później.",
};

/** Dedykowany widok bloku. */
function View({ b, asOf }: { b: DataBlock; asOf: string }) {
  const d = b.data as never;
  switch (b.key) {
    case "weather_history": return <WeatherView d={d as WeatherHistory} asOf={asOf} />;
    case "weather_forecast": return <ForecastView d={d as WeatherForecast} />;
    case "drought": return <DroughtView d={d as DroughtHistory} asOf={asOf} />;
    case "soil": return <SoilView d={d as SoilInfo} />;
    case "terrain": return <TerrainView d={d as TerrainInfo} />;
    case "hydrology": return <HydrologyView d={d as HydrologyInfo} />;
    case "vegetation": return <VegetationView d={d as VegetationInfo} />;
    case "land_cover": return <LandCoverView d={d as LandCoverInfo} />;
    case "yields": return <YieldsView d={d as YieldInfo} />;
    case "protected_areas": return <ProtectedView d={d as ProtectedAreasInfo} />;
    case "crop_calendar": return <CalendarView d={d as CropCalendarInfo} asOf={asOf} />;
    case "legal_context": return <LegalView d={d as LegalContextInfo} asOf={asOf} />;
    default: return null;
  }
}

export function BlockCard({ info, block, asOf, wide }: { info: BlockInfo; block?: DataBlock | "loading"; asOf: string; wide?: boolean }) {
  const status = block === undefined ? "idle" : block === "loading" ? "loading" : block.status;
  const b = typeof block === "object" ? block : null;
  return (
    <article className={`card status-${status}${wide ? " wide" : ""}`} id={`blk-${info.key}`} aria-busy={status === "loading"}>
      <header>
        <div>
          <h3>{info.title}</h3>
        </div>
        {status !== "idle" && <span className={`badge b-${status}`}>{STATUS_LABEL[status] ?? status}</span>}
      </header>

      {status === "idle" && <p className="muted">Wybierz działkę, aby zobaczyć dane.</p>}
      {status === "loading" && <div className="skeleton" aria-label="Pobieram dane"><span /><span /><span /></div>}

      {b && b.data != null && <ErrorBoundaryView b={b} asOf={asOf} />}
      {b && b.data == null && <p className="empty">{EMPTY_TEXT[b.status] ?? "Brak danych."}</p>}
      {b && b.status === "error" && b.messages[0] && <p className="small muted">Powód: {b.messages[0]}</p>}

      {b && b.uncertainty.length > 0 && !HIDE_UNCERTAINTY.has(b.key) && (
        <details className="uncertainty">
          <summary>Ograniczenia i niepewność ({b.uncertainty.length})</summary>
          <ul>{b.uncertainty.map((u, i) => <li key={i}>{u}</li>)}</ul>
        </details>
      )}
      {b && b.provenance.length > 0 && (
        <details className="prov">
          <summary>
            Źródło: {shortName(b.provenance[0].source_name)}{b.provenance.length > 1 ? ` (+${b.provenance.length - 1})` : ""}
            {" · "}{b.provenance[0].data_as_of ? `dane do ${dateStr(b.provenance[0].data_as_of)}` : `pobrano ${dateStr(b.provenance[0].retrieved_at)}`}
          </summary>
          <SourceList items={b.provenance} />
        </details>
      )}
    </article>
  );
}

// Błąd w widoku jednego bloku (np. nieoczekiwany kształt danych) nie może wywrócić całej strony.
class Boundary extends Component<{ children: ReactNode }, { err: string | null }> {
  state = { err: null as string | null };
  static getDerivedStateFromError(e: Error) { return { err: e.message }; }
  render() {
    return this.state.err ? <p className="empty">Nie udało się wyświetlić tego bloku ({this.state.err}).</p> : this.props.children;
  }
}
function ErrorBoundaryView({ b, asOf }: { b: DataBlock; asOf: string }) {
  return <Boundary key={`${b.key}-${asOf}`}><View b={b} asOf={asOf} /></Boundary>;
}
