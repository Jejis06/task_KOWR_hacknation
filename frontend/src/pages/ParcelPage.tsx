import { useEffect, useMemo, useRef, useState } from "react";
import { api, USE_MOCKS, type Query } from "../api/client";
import type { AnalysisResult, BlockInfo, CropItem, DataBlock, HydrologyInfo, ParcelRef, TerrainInfo } from "../api/types";
import { emptyKnowledge, KnowledgeContext, type Knowledge } from "../api/knowledge";
import { type FormState, SearchForm } from "../components/SearchForm";
import { ParcelMap } from "../components/ParcelMap";
import { ParcelHeader } from "../components/ParcelHeader";
import { BlockCard } from "../components/BlockCard";
import { SourcesPanel } from "../components/SourcesPanel";
import { ReportView } from "../components/report/ReportView";
import { dateStr, dateTimeStr, todayIso } from "../lib/format";
import { on } from "../lib/events";

type BlockState = Record<string, DataBlock | "loading">;
const WIDE = new Set(["weather_history", "legal_context"]);
// Bloki liczone z innych bloków – pobieramy je po blokach danych (trafiają w cache zamiast dublować zapytania do źródeł).
const SECOND_PHASE = new Set(["legal_context", "analysis"]);

export function ParcelPage() {
  const [blocksInfo, setBlocksInfo] = useState<BlockInfo[]>([]);
  const [crops, setCrops] = useState<CropItem[]>([]);
  const [knowledge, setKnowledge] = useState<Knowledge>(emptyKnowledge);
  const [form, setForm] = useState<FormState>({ id: "", date: todayIso(), crop: "" });
  const [parcel, setParcel] = useState<ParcelRef | null>(null);
  const [analysed, setAnalysed] = useState<{ date: string; crop: string; at: string } | null>(null);
  const [blocks, setBlocks] = useState<BlockState>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState<number | null>(null);
  const [view, setView] = useState<"report" | "data">("report");
  const [picked, setPicked] = useState<ParcelRef | null>(null);   // działka wskazana na mapie (przed analizą)
  const run = useRef(0);

  useEffect(() => {
    api.blocks().then(setBlocksInfo).catch((e) => setError(`Nie mogę pobrać listy danych: ${e.message ?? e}`));
    api.crops().then(setCrops).catch(() => setCrops([]));
    api.knowledge().then(setKnowledge).catch(() => setKnowledge(emptyKnowledge));
    // zamknięte <details> nie drukują treści – przed drukiem rozwijamy procedury i listy (bez surowego JSON)
    const open = () => document.querySelectorAll<HTMLDetailsElement>("details:not(.raw)").forEach((d) => { d.open = true; });
    window.addEventListener("beforeprint", open);
    return () => window.removeEventListener("beforeprint", open);
  }, []);

  // „Więcej danych” z dymka zbiornika na mapie → widok analityka, przewiń i podświetl wiersz w karcie „Wody”
  useEffect(() => on("water:details", ({ index }) => {
    setView("data");
    setTimeout(() => {
      const row = document.getElementById(`water-${index}`);
      if (!row) return;
      row.scrollIntoView({ behavior: "smooth", block: "center" });
      row.classList.remove("flash"); void row.offsetWidth; row.classList.add("flash");
    }, 120);
  }), []);

  async function analyse(where: Query) {
    const token = ++run.current;
    const { date, crop } = form;
    setError(null); setBusy(true); setBlocks({}); setElapsed(null);
    const t0 = performance.now();
    try {
      const p = await api.resolve(where);
      if (token !== run.current) return;
      setParcel(p);
      setForm((f) => ({ ...f, id: p.id }));
      setAnalysed({ date, crop, at: new Date().toISOString() });
      const query: Query = { id: p.id, date, crop: crop || undefined };
      setBlocks(Object.fromEntries(blocksInfo.map((b) => [b.key, "loading" as const])));
      // bloki danych równolegle (render progresywny), potem bloki pochodne (prawo, analiza)
      const load = (list: BlockInfo[]) => Promise.all(list.map((b) =>
        api.block(b.key, query)
          .then((blk) => token === run.current && setBlocks((s) => ({ ...s, [b.key]: blk })))
          .catch((e) => token === run.current && setBlocks((s) => ({
            ...s, [b.key]: { key: b.key, title: b.title, status: "error", data: null, provenance: [], uncertainty: [],
              messages: [e instanceof Error ? e.message : String(e)] },
          }))),
      ));
      await load(blocksInfo.filter((b) => !SECOND_PHASE.has(b.key)));
      if (token === run.current) await load(blocksInfo.filter((b) => SECOND_PHASE.has(b.key)));
      if (token === run.current) setElapsed((performance.now() - t0) / 1000);
    } catch (e) {
      if (token !== run.current) return;
      const msg = e instanceof Error ? e.message : String(e);
      setError(/nie znaleziono/i.test(msg)
        ? `${msg} Sprawdź numer (wzór: 302504_5.0024.7) albo kliknij działkę na mapie.`
        : msg);
    } finally {
      if (token === run.current) setBusy(false);
    }
  }

  /** Kliknięcie mapy na ekranie startowym: tylko wskazanie działki (obrys + numer), analiza po przycisku. */
  async function pick(lon: number, lat: number) {
    if (busy) return;
    setError(null);
    try {
      const p = await api.resolve({ lon, lat });
      setPicked(p);
      setForm((f) => ({ ...f, id: p.id }));
    } catch (e) {
      setError(e instanceof Error ? `${e.message} Przybliż mapę i kliknij środek pola.` : String(e));
    }
  }

  const ready = Object.values(blocks).filter((b) => b !== "loading").length;
  const total = Object.keys(blocks).length;
  const asOf = analysed?.date ?? form.date;
  const overlays = useMemo(() => ({
    terrain: (typeof blocks.terrain === "object" ? blocks.terrain.data : null) as TerrainInfo | null,
    hydrology: (typeof blocks.hydrology === "object" ? blocks.hydrology.data : null) as HydrologyInfo | null,
    places: ((typeof blocks.analysis === "object" ? (blocks.analysis.data as AnalysisResult | null)?.recommendations : null) ?? [])
      .filter((r) => r.where_geojson).map((r) => ({ title: r.title, geojson: r.where_geojson! })),
  }), [blocks.terrain, blocks.hydrology, blocks.analysis]);
  const dataInfos = blocksInfo.filter((b) => b.key !== "analysis");

  function downloadJson() {
    if (!parcel || !analysed) return;
    const payload = { parcel, analysis_date: analysed.date, crop: analysed.crop || null, generated_at: analysed.at, blocks };
    const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 1)], { type: "application/json" }));
    const a = document.createElement("a");
    a.href = url; a.download = `raport_${parcel.id.replace(/[^\w.-]/g, "_")}_${analysed.date}.json`; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  const cropName = crops.find((c) => c.id === analysed?.crop)?.name_pl;

  return (
    <KnowledgeContext.Provider value={knowledge}>
      <div className={analysed ? "parcel-page" : "parcel-page landing"}>
        {USE_MOCKS && <div className="mock-banner no-print">Tryb demonstracyjny: dane przykładowe (MOCK), nie z prawdziwych źródeł.</div>}

        {parcel && analysed && view === "data" && (
          <header className="print-header print-only">
            <h1>Dane o działce {parcel.id}</h1>
            <p>{[parcel.region_name, parcel.commune, parcel.county, parcel.voivodeship].filter(Boolean).join(", ")} ·
              powierzchnia {parcel.area_ha.toFixed(2)} ha</p>
            <p>Data analizy: <b>{dateStr(analysed.date)}</b> · uprawa: <b>{cropName ?? "nie wybrano"}</b> ·
              wygenerowano: {dateTimeStr(analysed.at)}</p>
          </header>
        )}

        <section className="left">
          <SearchForm crops={crops} busy={busy} value={form} onChange={setForm}
            onSubmit={() => analyse({ id: form.id.trim() })} />
          {error && <div className="error" role="alert">{error}</div>}
          {!analysed && (
            <p className="landing-intro no-print">Wpisz numer działki albo kliknij swoje pole na mapie, wybierz datę i uprawę,
              a potem naciśnij <b>„Sprawdź działkę”</b>. Dostaniesz ocenę sytuacji wodnej, jej przyczyny i co możesz zrobić –
              z podaniem źródeł i dat. Nie zbieramy danych osobowych.</p>
          )}
          <ParcelMap parcel={picked && picked.id !== parcel?.id ? picked : parcel} overlays={picked && picked.id !== parcel?.id ? {} : overlays}
            expandable={!!(picked || parcel)} onPick={pick} />
          {picked && picked.id !== parcel?.id && (
            <p className="picked no-print" role="status">Wybrano działkę <b>{picked.id}</b> ({picked.region_name}, {picked.commune}) –
              naciśnij „Sprawdź działkę”.</p>
          )}
          {parcel && analysed && <ParcelHeader parcel={parcel} />}
        </section>

        {analysed && <section className="right">
          {total > 0 && (
            <div className="progress no-print" aria-live="polite">
              <span>{ready < total ? `Pobieram dane: ${ready} z ${total}…` : `Gotowe: ${total} bloków${elapsed ? ` w ${elapsed.toFixed(1)} s` : ""}`}</span>
              <span className="progress-track"><span className="progress-fill" style={{ width: `${(ready / Math.max(1, total)) * 100}%` }} /></span>
              <button type="button" className="btn-secondary" disabled={ready < total} onClick={() => window.print()}>
                🖨 {view === "report" ? "Drukuj raport / zapisz PDF" : "Drukuj dane / zapisz PDF"}</button>
              <button type="button" className="btn-secondary" disabled={ready < total} onClick={downloadJson}>⬇ Zapisz dane (JSON)</button>
            </div>
          )}
          {parcel && analysed && (
            <div className="tabs no-print" role="tablist" aria-label="Widok wyników">
              <button role="tab" aria-selected={view === "report"} className={view === "report" ? "tab on" : "tab"} onClick={() => setView("report")}>📋 Raport</button>
              <button role="tab" aria-selected={view === "data"} className={view === "data" ? "tab on" : "tab"} onClick={() => setView("data")}>📊 Wszystkie dane</button>
            </div>
          )}
          {parcel && analysed && view === "report" && (
            <ReportView parcel={parcel} asOf={analysed.date} cropName={cropName} generatedAt={analysed.at} infos={blocksInfo} blocks={blocks} />
          )}
          {view === "data" && (
            <>
              <div className="cards">
                {dataInfos.map((b) => (
                  <BlockCard key={b.key} info={b} block={blocks[b.key]} asOf={asOf} wide={WIDE.has(b.key)} />
                ))}
              </div>
              <SourcesPanel infos={dataInfos} blocks={blocks} />
            </>
          )}
          {parcel && view === "data" && (
            <p className="print-only small">Prototyp HackNation 2026 (KOWR). Informacja orientacyjna – nie zastępuje porady eksperta ani decyzji organów.
              Dane: GUGiK, IMGW-PIB, IUNG-PIB, Copernicus, Wody Polskie, PIG-PIB, GUS, Open-Meteo/ERA5, NASA POWER.</p>
          )}
        </section>}
      </div>
    </KnowledgeContext.Provider>
  );
}
