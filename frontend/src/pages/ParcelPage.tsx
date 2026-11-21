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
  /** działka kliknięta na mapie po analizie – pokazujemy jej dane, analiza dopiero po „Sprawdź tę działkę” */
  const [picked, setPicked] = useState<ParcelRef | null>(null);
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
  async function analyze(e: React.FormEvent) {
    e.preventDefault();
    await runAnalysis(id);
  }
  async function runAnalysis(parcelId: string) {
    setError("");
    setPicked(null);
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
      setPicked(p.id === selected?.id ? null : p);
      setSelectionMessage(
        p.id === selected?.id
          ? `To analizowana działka ${p.parcel_number}.`
          : `Działka ${p.parcel_number}, ${p.area_ha.toLocaleString("pl-PL", { maximumFractionDigits: 2 })} ha. Aby ją ocenić, wybierz „Sprawdź tę działkę” na mapie.`,
      );
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się wybrać działki.");
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
                Numer działki
              </label>
              <input
                ref={idInput}
                id="parcel-id"
                name="parcel"
                className="parcel-input"
                value={id}
                onChange={(e) => {
                  setId(e.target.value);
                  setError("");
                }}
                required
                aria-describedby="parcel-hint"
                autoComplete="off"
                spellCheck={false}
              />
              <div id="parcel-hint" className="form-hint">
                Np. {DEMO_ID} albo „obręb numer”, np. Słupia Wielka 7
              </div>
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
                    Sprawdź działkę
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
            {started && <div
              ref={mapContainer}
              className={fullscreen ? "map-fullscreen" : ""}
              role={fullscreen ? "dialog" : undefined}
              aria-modal={fullscreen ? true : undefined}
              aria-label={fullscreen ? "Powiększona mapa działki" : undefined}
            >
              {fullscreen && (
                <div className="fullscreen-title">
                  <div>
                    <strong>{selected ? `Działka ${selected.parcel_number ?? selected.id}` : "Mapa"}</strong>
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
              {selected ? (
              <Suspense fallback={<div className="map-shell skeleton" aria-label="Wczytywanie mapy" />}>
                  <ParcelMap
                    picked={picked}
                    onAnalyze={(pid) => {
                      setId(pid);
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
              ) : (
                <div className="map-shell skeleton" aria-label="Wyszukuję działkę na mapie" />
              )}
            </div>}
            {started && selected && <div className="parcel-details">
              <div className="parcel-details-top">
                <strong>Działka {selected.parcel_number ?? selected.id}</strong>
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
