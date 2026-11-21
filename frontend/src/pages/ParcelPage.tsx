import { useEffect, useMemo, useRef, useState } from "react";
import { api, USE_MOCKS, type Query } from "../api/client";
import type { BlockInfo, CropItem, DataBlock, HydrologyInfo, ParcelRef, TerrainInfo } from "../api/types";
import { emptyKnowledge, KnowledgeContext, type Knowledge } from "../api/knowledge";
import { type FormState, SearchForm } from "../components/SearchForm";
import { ParcelMap } from "../components/ParcelMap";
import { ParcelHeader } from "../components/ParcelHeader";
import { BlockCard } from "../components/BlockCard";
import { SourcesPanel } from "../components/SourcesPanel";
import { dateStr, dateTimeStr, todayIso } from "../lib/format";

type BlockState = Record<string, DataBlock | "loading">;
const WIDE = new Set(["weather_history", "legal_context"]);

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
      // wszystkie bloki równolegle, render progresywny (każdy blok niezależnie)
      await Promise.all(blocksInfo.map((b) =>
        api.block(b.key, query)
          .then((blk) => token === run.current && setBlocks((s) => ({ ...s, [b.key]: blk })))
          .catch((e) => token === run.current && setBlocks((s) => ({
            ...s, [b.key]: { key: b.key, title: b.title, status: "error", data: null, provenance: [], uncertainty: [],
              messages: [e instanceof Error ? e.message : String(e)] },
          }))),
      ));
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

  const ready = Object.values(blocks).filter((b) => b !== "loading").length;
  const total = Object.keys(blocks).length;
  const asOf = analysed?.date ?? form.date;
  const overlays = useMemo(() => ({
    terrain: (typeof blocks.terrain === "object" ? blocks.terrain.data : null) as TerrainInfo | null,
    hydrology: (typeof blocks.hydrology === "object" ? blocks.hydrology.data : null) as HydrologyInfo | null,
  }), [blocks.terrain, blocks.hydrology]);
  const cropName = crops.find((c) => c.id === analysed?.crop)?.name_pl;

  return (
    <KnowledgeContext.Provider value={knowledge}>
      <div className="parcel-page">
        {USE_MOCKS && <div className="mock-banner no-print">Tryb demonstracyjny: dane przykładowe (MOCK), nie z prawdziwych źródeł.</div>}

        {parcel && analysed && (
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
          <ParcelMap parcel={parcel} overlays={overlays} onPick={(lon, lat) => !busy && analyse({ lon, lat })} />
          {parcel && <ParcelHeader parcel={parcel} />}
        </section>

        <section className="right">
          {total > 0 && (
            <div className="progress no-print" aria-live="polite">
              <span>{ready < total ? `Pobieram dane: ${ready} z ${total}…` : `Gotowe: ${total} bloków${elapsed ? ` w ${elapsed.toFixed(1)} s` : ""}`}</span>
              <span className="progress-track"><span className="progress-fill" style={{ width: `${(ready / Math.max(1, total)) * 100}%` }} /></span>
              <button type="button" className="btn-secondary" disabled={ready < total} onClick={() => window.print()}>🖨 Drukuj / zapisz PDF</button>
            </div>
          )}
          {!parcel && !busy && (
            <div className="welcome">
              <h2>Jak to działa</h2>
              <ol>
                <li>Wpisz numer działki albo kliknij swoje pole na mapie.</li>
                <li>Wybierz datę (dziś albo dowolny dzień z 10 lat) i uprawę.</li>
                <li>Zobaczysz w jednym miejscu: opady i suszę z 10 lat, glebę, ukształtowanie terenu, wody w pobliżu,
                  stan roślin z satelity, kalendarz uprawy oraz jakie zgody są potrzebne na staw, studnię czy nawadnianie.</li>
              </ol>
              <p className="small">Przy każdej informacji podajemy źródło, datę i ograniczenia. Nie zbieramy żadnych danych osobowych.</p>
            </div>
          )}
          <div className="cards">
            {blocksInfo.map((b) => (
              <BlockCard key={b.key} info={b} block={blocks[b.key]} asOf={asOf} wide={WIDE.has(b.key)} />
            ))}
          </div>
          <SourcesPanel infos={blocksInfo} blocks={blocks} />
          {parcel && (
            <p className="print-only small">Prototyp HackNation 2026 (KOWR). Informacja orientacyjna – nie zastępuje porady eksperta ani decyzji organów.
              Dane: GUGiK, IMGW-PIB, IUNG-PIB, Copernicus, Wody Polskie, PIG-PIB, GUS, Open-Meteo/ERA5, NASA POWER.</p>
          )}
        </section>
      </div>
    </KnowledgeContext.Provider>
  );
}
