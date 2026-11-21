import type { BlockInfo, CropItem, DataBlock, ParcelRef } from "./types";
import { mockBlock, mockBlocks, mockCrops, mockParcel } from "../mocks/fixtures";

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === "true";

export interface Query {
  id?: string;
  lon?: number;
  lat?: number;
  date?: string; // YYYY-MM-DD
  crop?: string;
}

function qs(q: Query): string {
  const p = new URLSearchParams();
  Object.entries(q).forEach(([k, v]) => v !== undefined && v !== "" && p.set(k, String(v)));
  return p.toString();
}

async function get<T>(path: string): Promise<T> {
  const r = await fetch(path);
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body.detail ?? `HTTP ${r.status}`);
  }
  return r.json() as Promise<T>;
}

export const api = {
  resolve: (q: Query) => (USE_MOCKS ? Promise.resolve(mockParcel) : get<ParcelRef>(`/api/parcel/resolve?${qs(q)}`)),
  blocks: () => (USE_MOCKS ? Promise.resolve(mockBlocks) : get<BlockInfo[]>("/api/parcel/blocks")),
  block: (key: string, q: Query) =>
    USE_MOCKS ? Promise.resolve(mockBlock(key)) : get<DataBlock>(`/api/parcel/block/${key}?${qs(q)}`),
  crops: async (): Promise<CropItem[]> =>
    USE_MOCKS ? mockCrops : (await get<{ items: CropItem[] }>("/api/knowledge/crops")).items,
};
