import type { BlockInfo, CropItem, DataBlock, ParcelRef } from "./types";
import { byId, type EuAct, type FundingProgram, type Knowledge, type LegalRule, type Procedure } from "./knowledge";
import { mockBlock, mockBlocks, mockCrops, mockKnowledge, mockParcel } from "../mocks/fixtures";

export const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === "true";

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

/** Błędy po polsku, bez technicznego żargonu. */
async function get<T>(path: string): Promise<T> {
  let r: Response;
  try {
    r = await fetch(path);
  } catch {
    throw new Error("Brak połączenia z serwerem aplikacji. Sprawdź internet albo spróbuj za chwilę.");
  }
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : null;
    if (r.status === 404) throw new Error(detail ?? "Nie znaleziono.");
    if (r.status === 422) throw new Error(detail ?? "Niepoprawne dane wejściowe.");
    if (r.status >= 500) throw new Error("Serwer aplikacji ma chwilowy problem. Spróbuj ponownie za chwilę.");
    throw new Error(detail ?? `Błąd ${r.status}`);
  }
  return r.json() as Promise<T>;
}

const delay = <T,>(v: T, ms = 300) => new Promise<T>((res) => setTimeout(() => res(v), ms));

export const api = {
  resolve: (q: Query) => (USE_MOCKS ? delay(mockParcel) : get<ParcelRef>(`/api/parcel/resolve?${qs(q)}`)),
  blocks: () => (USE_MOCKS ? delay(mockBlocks, 50) : get<BlockInfo[]>("/api/parcel/blocks")),
  block: (key: string, q: Query) =>
    USE_MOCKS ? delay(mockBlock(key, q), 200 + Math.random() * 900) : get<DataBlock>(`/api/parcel/block/${key}?${qs(q)}`),
  crops: async (): Promise<CropItem[]> =>
    USE_MOCKS ? mockCrops : (await get<{ items: CropItem[] }>("/api/knowledge/crops")).items,
  knowledge: async (): Promise<Knowledge> => {
    if (USE_MOCKS) return mockKnowledge;
    const [proc, fund, legal, eu] = await Promise.all([
      get<{ items: Procedure[]; meta: Record<string, unknown> }>("/api/knowledge/procedures"),
      get<{ items: FundingProgram[] }>("/api/knowledge/funding"),
      get<{ items: LegalRule[]; meta: { disclaimer?: string } }>("/api/knowledge/legal_pl"),
      get<{ items: EuAct[]; meta: { eurlex_pattern?: string } }>("/api/knowledge/eu_law"),
    ]);
    return {
      procedures: byId(proc.items), funding: byId(fund.items), legal: byId(legal.items), eu: eu.items,
      eurlexPattern: eu.meta?.eurlex_pattern, disclaimer: legal.meta?.disclaimer, loaded: true,
    };
  },
};
