import { useEffect, useState } from "react";
import { api, type Query } from "../api/client";
import type { BlockInfo, CropItem, DataBlock, ParcelRef } from "../api/types";
import { SearchForm } from "../components/SearchForm";
import { ParcelMap } from "../components/ParcelMap";
import { ParcelHeader } from "../components/ParcelHeader";
import { BlockCard } from "../components/BlockCard";

type BlockState = Record<string, DataBlock | "loading">;

export function ParcelPage() {
  const [blocksInfo, setBlocksInfo] = useState<BlockInfo[]>([]);
  const [crops, setCrops] = useState<CropItem[]>([]);
  const [parcel, setParcel] = useState<ParcelRef | null>(null);
  const [blocks, setBlocks] = useState<BlockState>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.blocks().then(setBlocksInfo).catch((e) => setError(String(e)));
    api.crops().then(setCrops).catch(() => setCrops([]));
  }, []);

  async function analyse(q: Query) {
    setError(null);
    setBusy(true);
    setBlocks({});
    try {
      const p = await api.resolve(q);
      setParcel(p);
      const query: Query = { id: p.id, date: q.date, crop: q.crop };
      setBlocks(Object.fromEntries(blocksInfo.map((b) => [b.key, "loading" as const])));
      // wszystkie bloki równolegle, render progresywny (każdy blok niezależnie)
      await Promise.all(
        blocksInfo.map((b) =>
          api
            .block(b.key, query)
            .then((blk) => setBlocks((s) => ({ ...s, [b.key]: blk })))
            .catch((e) =>
              setBlocks((s) => ({
                ...s,
                [b.key]: { key: b.key, title: b.title, status: "error", data: null, provenance: [],
                  uncertainty: [], messages: [String(e)] },
              })),
            ),
        ),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="parcel-page">
      <section className="left">
        <SearchForm crops={crops} busy={busy} onSubmit={analyse} />
        {error && <div className="error">{error}</div>}
        <ParcelMap parcel={parcel} onPick={(lon, lat) => analyse({ lon, lat })} />
        {parcel && <ParcelHeader parcel={parcel} />}
      </section>
      <section className="right">
        {blocksInfo.map((b) => (
          <BlockCard key={b.key} info={b} block={blocks[b.key]} />
        ))}
      </section>
    </div>
  );
}
