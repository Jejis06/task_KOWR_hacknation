import { lazy, Suspense, useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Check,
  Download,
  Droplets,
  FileText,
  Leaf,
  LockKeyhole,
  MapPin,
  Printer,
  Search,
  ShieldCheck,
  Sprout,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  api,
  dateBounds,
  DEMO_ID,
  USE_MOCKS,
  validDate,
  type Crop,
  type DataBlock,
  type ParcelRef,
} from "@/api/client";
import Report from "@/components/water/Report";
import Analyst from "@/components/water/Analyst";
import { formatDate, Term } from "@/components/water/shared";
import { groupParcels, looksLikeAddress, looksLikeParcelId } from "@/lib/groups";
const MAX_SELECTION = 25;
/** „Działka 7” albo „3 działki: 7, 8, 9” / „25 działek: 101, 110/74, 110/81…” */
function parcelTitle(p: ParcelRef): string {
  const n = p.id.split("+").length;
  if (n === 1) return `Działka ${p.parcel_number ?? p.id}`;
  const nums = (p.parcel_number ?? "").split(", ");
  const word = n < 5 ? "działki" : "działek";
  return `${n} ${word}: ${nums.slice(0, 3).join(", ")}${nums.length > 3 ? "…" : ""}`;
}
const ParcelMap = lazy(() => import("@/components/water/ParcelMap"));
const today = new Date().toISOString().slice(0, 10);
const sampleDate = USE_MOCKS ? "2026-07-15" : today;
function Brand() {
  return (
    <div className="brand">
      <svg className="brand-symbol" viewBox="0 0 40 48" fill="none" aria-hidden="true">
        <path d="M20 3C14 12 4 23 4 31a16 16 0 0 0 32 0C36 23 26 12 20 3Z" fill="var(--primary)" />
        <path d="M12 34c2-12 10-16 19-16-1 10-7 17-19 16Z" fill="var(--secondary)" />
        <path
          d="m12 38 13-14"
          stroke="var(--primary-foreground)"
          strokeWidth="1.7"
          strokeLinecap="round"
        />
      </svg>
      <div>
        <div className="brand-name">Zatrzymaj wodę</div>
        <div className="brand-caption">Dobra woda. Dobra ziemia.</div>
      </div>
    </div>
  );
}
export function ParcelPage() {
  const [id, setId] = useState(USE_MOCKS ? DEMO_ID : "");
  const [date, setDate] = useState(sampleDate);
  const [crop, setCrop] = useState(USE_MOCKS ? "wheat" : "");
  const [crops, setCrops] = useState<Crop[]>([]);
  const [selected, setSelected] = useState<ParcelRef | null>(null);
  /** zaznaczenie: działki z kliknięcia, trybu „wiele”, obrysu i wyszukiwarki – jedna wspólna lista (maks. 25) */
  const [selection, setSelection] = useState<ParcelRef[]>([]);
  const [multi, setMulti] = useState(false);
  const [groups, setGroups] = useState<ParcelRef[][]>([]);
  const [groupIdx, setGroupIdx] = useState(0);
  const [flyTo, setFlyTo] = useState<{ lon: number; lat: number; zoom: number; n: number } | null>(null);
  const [searching, setSearching] = useState(false);
  const [lassoBusy, setLassoBusy] = useState(false);
  const [context, setContext] = useState<{ date: string; crop: string; parcel: ParcelRef | null }>({ date: sampleDate, crop: "", parcel: null });
  const [blocks, setBlocks] = useState<Record<string, DataBlock>>({});
  const [tab, setTab] = useState<"report" | "data">("report");
  const [loading, setLoading] = useState(false);
  const [count, setCount] = useState(0);
  const [total, setTotal] = useState(13);
  const [error, setError] = useState("");
  const [selectionMessage, setSelectionMessage] = useState("");
  const [fullscreen, setFullscreen] = useState(false);
  const [highlight, setHighlight] = useState<{ id: string; n: number } | null>(null);
  const [help, setHelp] = useState(false);
  const [focusBlock, setFocusBlock] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);
  const mapContainer = useRef<HTMLDivElement>(null);
  const idInput = useRef<HTMLInputElement>(null);
  const bounds = dateBounds();
  /** ekran startowy = sam formularz; mapa i raport dopiero po „Sprawdź działkę” */
  const started = loading || !!context.parcel;
  useEffect(() => {
    const ctrl = new AbortController();
    api
      .crops(ctrl.signal)
      .then(setCrops)
      .catch(() => setCrops([]));
    return () => {
      ctrl.abort();
      controller.current?.abort();
    };
  }, []);
  useEffect(() => {
    if (!fullscreen) return;
    const before = document.activeElement;
    const oldOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const container = mapContainer.current;
    container?.querySelector<HTMLButtonElement>("button")?.focus();
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setFullscreen(false);
        return;
      }
      if (e.key === "Tab" && container) {
        const items = Array.from(
          container.querySelectorAll<HTMLElement>('button,a[href],input,[tabindex="0"]'),
        ).filter((el) => el.getClientRects().length > 0);
        const first = items[0],
          last = items.at(-1);
        if (e.shiftKey && document.activeElement === first && last) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last && first) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", key);
    return () => {
      document.body.style.overflow = oldOverflow;
      document.removeEventListener("keydown", key);
      if (before instanceof HTMLElement) before.focus();
    };
  }, [fullscreen]);
  useEffect(() => {
    if (tab === "data" && focusBlock) {
      const t = setTimeout(
        () =>
          document
            .getElementById(`block-${focusBlock}`)
            ?.scrollIntoView({ behavior: "smooth", block: "start" }),
        150,
      );
      return () => clearTimeout(t);
    }
    return undefined;
  }, [tab, focusBlock]);
  /** Dodaj działki do zaznaczenia: w trybie „wiele” dopisujemy (klik na zaznaczonej = odznaczenie), inaczej zastępujemy. */
  function addToSelection(ps: ParcelRef[], toggle = false) {
    setSelection((prev) => {
      if (!multi && !toggle) return ps.slice(0, MAX_SELECTION);
      let next = [...prev];
      for (const p of ps) {
        const has = next.some((x) => x.id === p.id);
        next = has ? (toggle ? next.filter((x) => x.id !== p.id) : next) : [...next, p];
      }
      if (next.length > MAX_SELECTION) setError(`Można zaznaczyć maksymalnie ${MAX_SELECTION} działek naraz.`);
      return next.slice(0, MAX_SELECTION);
    });
  }
  /** Wyszukiwarka: numer działki, „obręb numer” albo adres. Zwraca znalezione działki (do natychmiastowej analizy). */
  async function search(q: string): Promise<ParcelRef[]> {
    const text = q.trim();
    if (!text) return [];
    setSearching(true);
    setError("");
    try {
      if (looksLikeParcelId(text) || !looksLikeAddress(text)) {
        try {
          const p = await api.resolve({ id: text });
          addToSelection([p]);
          return [p];
        } catch (err) {
          if (looksLikeParcelId(text)) throw err;      // pełny numer działki – nie ma sensu szukać adresu
        }
      }
      const g = await api.geocode(text);
      if (g.has_house_number) {
        const p = await api.resolve({ lon: g.lon, lat: g.lat });
        addToSelection([p]);
        setFlyTo({ lon: g.lon, lat: g.lat, zoom: 16, n: Date.now() });
        setSelectionMessage(`Znaleziono adres: ${g.label}. Zaznaczono działkę ${p.parcel_number ?? p.id}.`);
        return [p];
      }
      setFlyTo({ lon: g.lon, lat: g.lat, zoom: 14, n: Date.now() });
      setSelectionMessage(`Znaleziono: ${g.label}. Kliknij działkę na mapie, aby ją zaznaczyć.`);
      return [];
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się wyszukać.");
      return [];
    } finally {
      setSearching(false);
    }
  }
  async function analyze(e: React.FormEvent) {
    e.preventDefault();
    // zaznaczone działki mają pierwszeństwo; pole wyszukiwania liczy się tylko, gdy nic nie zaznaczono
    let chosen = selection;
    const typed = id.trim();
    if (!chosen.length && typed) chosen = await search(typed);
    if (!chosen.length) {
      if (!typed) setError("Wpisz adres albo numer działki, albo kliknij działkę na mapie.");
      return;
    }
    const gs = groupParcels(chosen);
    setGroups(gs);
    setGroupIdx(0);
    await runAnalysis(gs[0]!.map((p) => p.id).join("+"));
  }
  async function nextGroup() {
    const i = groupIdx + 1;
    if (i >= groups.length) return;
    setGroupIdx(i);
    await runAnalysis(groups[i]!.map((p) => p.id).join("+"));
  }
  async function runAnalysis(parcelId: string) {
    setError("");
    if (!validDate(date)) {
      setError(
        "Wybierz dzień od " + formatDate(bounds.min) + " do " + formatDate(bounds.max) + ".",
      );
      return;
    }
    controller.current?.abort();
    const ctrl = new AbortController();
    controller.current = ctrl;
    setLoading(true);
    setCount(0);
    setBlocks({});
    setTab("report");
    setHighlight(null);
    try {
      const p = await api.resolve({ id: parcelId.trim() }, ctrl.signal);
      const definitions = await api.blocks(ctrl.signal);
      if (ctrl.signal.aborted) return;
      setSelected(p);
      setContext({ date, crop, parcel: p });
      setTotal(definitions.length);
      await Promise.all(
        definitions.map(async (def) => {
          let block: DataBlock;
          try {
            block = def.implemented
              ? await api.block(def.key, p.id, date, crop, ctrl.signal)
              : {
                  key: def.key,
                  title: def.title,
                  status: "not_implemented",
                  data: {},
                  provenance: [],
                  uncertainty: [],
                  messages: ["Ten rodzaj danych jest w przygotowaniu."],
                  elapsed_ms: 0,
                };
          } catch (err) {
            if (ctrl.signal.aborted) return;
            block = {
              key: def.key,
              title: def.title,
              status: "error",
              data: {},
              provenance: [],
              uncertainty: [],
              messages: [err instanceof Error ? err.message : "Nie udało się pobrać danych."],
              elapsed_ms: 0,
            };
          }
          if (ctrl.signal.aborted) return;
          setBlocks((prev) => ({ ...prev, [def.key]: block }));
          setCount((prev) => prev + 1);
        }),
      );
    } catch (err) {
      if (!ctrl.signal.aborted)
        setError(err instanceof Error ? err.message : "Nie udało się sprawdzić działki.");
    } finally {
      if (!ctrl.signal.aborted) setLoading(false);
    }
  }
  async function selectMap(lon: number, lat: number) {
    try {
      const p = await api.resolve({ lon, lat });
      addToSelection([p], multi);
      setSelectionMessage(`Działka ${p.parcel_number ?? p.id}, ${p.area_ha.toLocaleString("pl-PL", { maximumFractionDigits: 2 })} ha.`);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się wybrać działki.");
    }
  }
  async function lassoSelect(ring: [number, number][]) {
    setLassoBusy(true);
    setError("");
    try {
      const { parcels: ps, total } = await api.inArea(ring);
      if (!ps.length) setError("W obrysie nie ma działek ewidencyjnych.");
      else if (total > ps.length)
        setError(`W obrysie jest ${total} działek – zaznaczyłem ${ps.length} największych (limit). Zaznacz mniejszy obszar, jeśli chodzi o inne działki.`);
      // obrys zawsze dopisuje do zaznaczenia (łączy się z kliknięciami i trybem „wiele”)
      setSelection((prev) => [...prev, ...ps.filter((p) => !prev.some((x) => x.id === p.id))].slice(0, MAX_SELECTION));
      setSelectionMessage(`Obrys: zaznaczono ${ps.length} działek.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się zaznaczyć działek obrysem.");
    } finally {
      setLassoBusy(false);
    }
  }
  /** Pokaż obiekt na mapie: wycentruj go na małej mapie obok (bez otwierania pełnego ekranu). */
  function showMap(feature: string) {
    setHighlight((h) => ({ id: feature, n: (h?.n ?? 0) + 1 }));
  }
  function showData(key: string) {
    setFullscreen(false);
    setTab("data");
    setFocusBlock(key);
  }
  function exportJson() {
    const content = {
      demo: USE_MOCKS,
      parcel: context.parcel,
      date: context.date,
      crop: context.crop,
      blocks: Object.values(blocks),
    };
    const blob = new Blob([JSON.stringify(content, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `zatrzymaj-wode-${(context.parcel?.id ?? "dzialka").replace(/[^\w.-]/g, "_")}-${context.date}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function printReport() {
    const details = Array.from(document.querySelectorAll("details"));
    const states = details.map((d) => d.open);
    details.forEach((d) => {
      d.open = true;
    });
    const restore = () => {
      details.forEach((d, i) => {
        d.open = states[i] ?? false;
      });
      window.removeEventListener("afterprint", restore);
    };
    window.addEventListener("afterprint", restore);
    window.print();
  }
  return (
    <>
      <header className="site-header">
        <div className="header-inner">
          <Brand />
          <nav className="header-nav" aria-label="Nawigacja główna">
            <Button
              variant="ghost"
              className="active"
              onClick={() => {
                idInput.current?.focus();
                idInput.current?.scrollIntoView({ behavior: "smooth", block: "center" });
              }}
            >
              Moja działka
            </Button>
            <Button variant="ghost" onClick={() => setHelp(true)}>
              O raporcie
            </Button>
            <span className="privacy">
              <LockKeyhole size={13} />
              Bez logowania. Bez danych osobowych.
            </span>
          </nav>
        </div>
      </header>
      <main className="page">
        <div className="intro">
          <div>
            <div className="eyebrow">
              <Sprout size={14} />Z myślą o Twoim polu
            </div>
            <h1>
              Sprawdź wodę. <span>Zadbaj o swoje pole.</span>
            </h1>
            <p>Dowiedz się, co dzieje się z wodą i jak zatrzymać ją na swojej ziemi.</p>
          </div>
          {USE_MOCKS && (
            <span className="demo-badge">
              <span className="status-dot" />
              Wersja demonstracyjna
            </span>
          )}
        </div>
        <div className={started ? "workspace" : "workspace landing"}>
          <aside className="field-column" aria-label="Wybór działki">
            <form className="form-section" onSubmit={analyze}>
              <h2 className="section-title">
                <MapPin />
                Twoja działka
              </h2>
              <label className="form-label" htmlFor="parcel-id">
                Adres albo numer działki
              </label>
              <div className="search-row">
                <input
                  ref={idInput}
                  id="parcel-id"
                  name="parcel"
                  className="parcel-input"
                  value={id}
                  placeholder="np. Środa Wielkopolska, Kosynierów 1"
                  onChange={(e) => {
                    setId(e.target.value);
                    setError("");
                  }}
                  aria-describedby="parcel-hint"
                  autoComplete="off"
                  spellCheck={false}
                />
                <Button type="button" variant="secondary" className="search-button" disabled={searching || !id.trim()}
                  aria-label="Szukaj na mapie" title="Szukaj na mapie" onClick={() => void search(id)}>
                  <Search />
                </Button>
              </div>
              <div id="parcel-hint" className="form-hint">
                Numer działki (np. {DEMO_ID}), „obręb numer” (np. Słupia Wielka 7) albo adres. Możesz też kliknąć działkę na mapie.
              </div>
              <label className="multi-toggle">
                <input type="checkbox" checked={multi} onChange={(e) => setMulti(e.target.checked)} />
                Zaznaczaj wiele działek (kliknięcie dodaje lub usuwa działkę)
              </label>
              {selection.length > 0 && (
                <div className="selection-box" aria-label="Zaznaczone działki">
                  <div className="selection-head">
                    <strong>Zaznaczone: {selection.length} {selection.length === 1 ? "działka" : selection.length < 5 ? "działki" : "działek"}</strong>
                    <span>{selection.reduce((a, p) => a + p.area_ha, 0).toLocaleString("pl-PL", { maximumFractionDigits: 2 })} ha</span>
                    <Button type="button" variant="link" className="h-auto p-0 text-xs" onClick={() => { setSelection([]); setGroups([]); }}>
                      Wyczyść
                    </Button>
                  </div>
                  <ul className="selection-chips">
                    {selection.map((p) => (
                      <li key={p.id}>
                        {p.parcel_number ?? p.id}{p.region_name ? ` · ${p.region_name}` : ""}
                        <button type="button" aria-label={`Usuń działkę ${p.parcel_number ?? p.id}`}
                          onClick={() => setSelection((prev) => prev.filter((x) => x.id !== p.id))}>
                          <X size={12} />
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="form-row">
                <div>
                  <label className="form-label" htmlFor="report-date">
                    Dzień oceny
                  </label>
                  <input
                    type="date"
                    id="report-date"
                    value={date}
                    min={bounds.min}
                    max={bounds.max}
                    onChange={(e) => setDate(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <label className="form-label" htmlFor="crop">
                    Co uprawiasz? <Term name="Wybór uprawy" />
                  </label>
                  <select id="crop" value={crop} onChange={(e) => setCrop(e.target.value)}>
                    <option value="">Bez wyboru uprawy</option>
                    {crops.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name_pl}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <Button type="submit" className="analyze-button" disabled={loading}>
                {loading ? (
                  <>
                    <Droplets className="animate-pulse" />
                    Pobieram dane…
                  </>
                ) : (
                  <>
                    <Droplets />
                    {selection.length > 1 ? `Sprawdź działki (${selection.length})` : "Sprawdź działkę"}
                    <ArrowRight className="ml-auto" />
                  </>
                )}
              </Button>
              <div className="form-footer">
                <ShieldCheck size={12} />
                Bez logowania i zapisywania Twoich danych
              </div>
              {error && (
                <div className="error-notice" role="alert">
                  {error}
                  {USE_MOCKS && (
                    <Button
                      type="button"
                      variant="link"
                      className="mt-1 h-auto p-0 text-xs"
                      onClick={() => {
                        setId(DEMO_ID);
                        setError("");
                      }}
                    >
                      Użyj przykładowej działki
                    </Button>
                  )}
                </div>
              )}
            </form>
            <div
              ref={mapContainer}
              className={fullscreen ? "map-fullscreen" : ""}
              role={fullscreen ? "dialog" : undefined}
              aria-modal={fullscreen ? true : undefined}
              aria-label={fullscreen ? "Powiększona mapa działki" : undefined}
            >
              {fullscreen && (
                <div className="fullscreen-title">
                  <div>
                    <strong>{selected ? parcelTitle(selected) : "Mapa"}</strong>
                    <span className="ml-3 text-xs text-muted-foreground">
                      {USE_MOCKS ? "Lokalizacje demonstracyjne" : ""}
                    </span>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Zamknij powiększoną mapę"
                    onClick={() => setFullscreen(false)}
                  >
                    <X />
                  </Button>
                </div>
              )}
              <Suspense fallback={<div className="map-shell skeleton" aria-label="Wczytywanie mapy" />}>
                  <ParcelMap
                    selection={selection}
                    flyTo={flyTo}
                    onLasso={lassoSelect}
                    lassoBusy={lassoBusy}
                    onAnalyze={(pid) => {
                      setGroups([selection.filter((p) => p.id === pid)]);
                      setGroupIdx(0);
                      void runAnalysis(pid);
                    }}
                    parcel={selected}
                    blocks={blocks}
                    showAnalysis={!!context.parcel && selected?.id === context.parcel.id}
                    onSelect={selectMap}
                    highlight={highlight}
                    onMore={showData}
                    fullscreen={fullscreen}
                    onFullscreen={() => setFullscreen((v) => !v)}
                  />
              </Suspense>
            </div>
            {started && selected && <div className="parcel-details">
              <div className="parcel-details-top">
                <strong title={selected.parcel_number ?? selected.id}>{parcelTitle(selected)}</strong>
                <span className="area-label">{selected.area_ha.toLocaleString("pl-PL", { maximumFractionDigits: 2 })} ha</span>
              </div>
              <div className="parcel-location">
                {selected.region_name ? `Obręb ${selected.region_name} · ` : ""}gmina {selected.commune} · {selected.county}
              </div>
              <div className="source-line">
                {USE_MOCKS
                  ? "Przykładowa działka · obliczenia własne"
                  : "Granice: GUGiK ULDK (ewidencja gruntów)"}{" "}
                · {context.parcel?.id === selected.id ? `analiza na ${formatDate(context.date)}` : "nie sprawdzono jeszcze"}
              </div>
            </div>}
            {started && <div className="field-note">
              <Leaf size={20} />
              <div>
                <strong className="text-foreground font-medium">Każda kropla ma znaczenie.</strong>
                <br />
                Najpierw zatrzymujemy wodę na polu.
                <br />
                Nawadnianie rozważamy na końcu.
              </div>
            </div>}
            <div className="sr-only" role="status" aria-live="polite">
              {selectionMessage}
            </div>
          </aside>
          {started && <div className="report-column">
            <div className="report-toolbar">
              <div
                className="report-tabs"
                role="tablist"
                aria-label="Widok raportu"
                onKeyDown={(e) => {
                  if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
                    e.preventDefault();
                    const next = tab === "report" ? "data" : "report";
                    setTab(next);
                    document.getElementById(next === "report" ? "report-tab" : "data-tab")?.focus();
                  }
                }}
              >
                <Button
                  variant="ghost"
                  className="report-tab"
                  id="report-tab"
                  role="tab"
                  aria-selected={tab === "report"}
                  aria-controls="report-content"
                  tabIndex={tab === "report" ? 0 : -1}
                  onClick={() => setTab("report")}
                >
                  <FileText />
                  Raport
                </Button>
                <Button
                  variant="ghost"
                  className="report-tab"
                  id="data-tab"
                  role="tab"
                  aria-selected={tab === "data"}
                  aria-controls="data-content"
                  tabIndex={tab === "data" ? 0 : -1}
                  onClick={() => {
                    setTab("data");
                    setFocusBlock(null);
                  }}
                >
                  Wszystkie dane
                </Button>
              </div>
              <div className="export-actions">
                <Button
                  variant="ghost"
                  className="export-button"
                  disabled={!Object.keys(blocks).length || loading}
                  aria-label="Drukuj raport lub zapisz PDF"
                  title="Drukuj lub zapisz PDF"
                  onClick={printReport}
                >
                  <Printer />
                  <span className="export-label">Drukuj</span>
                </Button>
                <Button
                  variant="ghost"
                  className="export-button"
                  disabled={!Object.keys(blocks).length || loading}
                  aria-label="Pobierz dane JSON"
                  title="Pobierz dane JSON"
                  onClick={exportJson}
                >
                  <Download />
                  <span className="export-label">Dane</span>
                </Button>
              </div>
            </div>
            {USE_MOCKS && (
              <div className="source-line mb-3">
                Przykładowy raport · {formatDate(context.date)} ·{" "}
                {crops.find((c) => c.id === context.crop)?.name_pl ??
                  (context.crop ? "Pszenica ozima" : "Bez wyboru uprawy")}
              </div>
            )}
            {loading && (
              <div className="loading-progress" role="status" aria-live="polite">
                Pobieram dane: {count} z {total}…
                <div
                  className="loading-track"
                  role="progressbar"
                  aria-label="Postęp pobierania danych"
                  aria-valuenow={count}
                  aria-valuemin={0}
                  aria-valuemax={total}
                >
                  <div
                    className="loading-fill"
                    style={{ width: `${total ? (count / total) * 100 : 0}%` }}
                  />
                </div>
              </div>
            )}
            {groups.length > 1 && context.parcel && (
              <div className="group-notice" role="status">
                <strong>Grupa {groupIdx + 1} z {groups.length}.</strong> Zaznaczone działki leżą w {groups.length} oddalonych
                miejscach (ponad 500 m od siebie), więc każde miejsce liczymy osobno – pogoda i gleba mogą się tam różnić.
                {groupIdx + 1 < groups.length && (
                  <Button variant="secondary" size="sm" className="ml-2" disabled={loading} onClick={() => void nextGroup()}>
                    Policz następną grupę ({groups[groupIdx + 1]!.length} {groups[groupIdx + 1]!.length === 1 ? "działka" : "działki"})
                  </Button>
                )}
              </div>
            )}
            {tab === "report" ? (
              <Report
                blocks={blocks}
                date={context.date}
                onMap={showMap}
                onData={showData}
                loading={loading}
              />
            ) : (
              <Analyst blocks={blocks} onMap={showMap} loading={loading} date={context.date} />
            )}
          </div>}
        </div>
        <footer className="site-footer">
          <span className="footer-brand">
            <Droplets size={14} />
            Zatrzymaj wodę
          </span>
          <span>Dla rolników. Dla ziemi. Dla przyszłości.</span>
          <span>
            <LockKeyhole size={11} className="inline mr-1" />
            Nie zbieramy danych osobowych
          </span>
        </footer>
      </main>
      <Dialog open={help} onOpenChange={setHelp}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Woda na polu, krok po kroku</DialogTitle>
            <DialogDescription>
              „Zatrzymaj wodę” pomaga zrozumieć niedobór wody i wybrać kolejność działań.
            </DialogDescription>
          </DialogHeader>
          <div className="help-content">
            <p>
              <strong>Najpierw pole.</strong> Podaj numer działki, dzień oceny i uprawę. Możesz też
              wskazać pole na mapie.
            </p>
            <p>
              <strong>Potem czytelna ocena.</strong> Raport łączy pogodę, glebę i teren. Zalecenia
              zaczynają się od zatrzymania wody, potem poprawy gleby i dopiero na końcu nawadniania.
            </p>
            <p>
              <strong>Bez udawania pewności.</strong> Każdy zestaw danych ma źródło, datę i
              ograniczenia. Wersja demonstracyjna korzysta z wymyślonych wartości, nie z pomiarów
              Twojego pola.
            </p>
            <p>
              <strong>Bez konta i śledzenia.</strong> Nie zapisujemy Twoich wyborów. Podkłady mapy
              ładują się z Geoportalu i OpenStreetMap.
            </p>
            <p>
              Raport możesz wydrukować lub zapisać jako PDF w oknie drukowania. Przycisk ze strzałką
              pobiera komplet danych.
            </p>
          </div>
          <Button onClick={() => setHelp(false)}>
            <Check />
            Rozumiem
          </Button>
        </DialogContent>
      </Dialog>
    </>
  );
}
