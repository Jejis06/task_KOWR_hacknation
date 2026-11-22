import type { ParcelRef } from "@/api/client";

/** Odstęp [m] między prostokątami dwóch działek (przybliżenie płaskie – wystarcza dla odległości do kilku km). */
function gapM(a: ParcelRef, b: ParcelRef): number {
  const lat = ((a.bbox[1] + a.bbox[3] + b.bbox[1] + b.bbox[3]) / 4) * (Math.PI / 180);
  const mx = 111_320 * Math.cos(lat), my = 110_540;
  const dx = Math.max(0, Math.max(a.bbox[0], b.bbox[0]) - Math.min(a.bbox[2], b.bbox[2])) * mx;
  const dy = Math.max(0, Math.max(a.bbox[1], b.bbox[1]) - Math.min(a.bbox[3], b.bbox[3])) * my;
  return Math.hypot(dx, dy);
}

/**
 * Grupy działek analizowanych razem: działki stykające się lub oddalone o nie więcej niż `maxGapM` tworzą jedną grupę
 * (łańcuchowo). Oddalone grupy liczymy osobno, po kolei. Kolejność: największa łączna powierzchnia najpierw.
 */
export function groupParcels(parcels: ParcelRef[], maxGapM = 500): ParcelRef[][] {
  const parent = parcels.map((_, i) => i);
  const find = (i: number): number => (parent[i] === i ? i : (parent[i] = find(parent[i]!)));
  for (let i = 0; i < parcels.length; i++)
    for (let j = i + 1; j < parcels.length; j++)
      if (gapM(parcels[i]!, parcels[j]!) <= maxGapM) parent[find(i)] = find(j);
  const groups = new Map<number, ParcelRef[]>();
  parcels.forEach((p, i) => groups.set(find(i), [...(groups.get(find(i)) ?? []), p]));
  const area = (g: ParcelRef[]) => g.reduce((s, p) => s + p.area_ha, 0);
  return [...groups.values()].sort((a, b) => area(b) - area(a));
}

/** Pełny identyfikator działki (np. 302504_5.0024.7, z arkuszem …AR_1.12) – inaczej to adres albo „obręb numer”. */
export const looksLikeParcelId = (q: string) => /^\d{6}_\d\.\d{4}(\.AR_\d+)?\.[\w/]+$/.test(q.trim());
/** Adres: przecinek albo skrót ulicy/osiedla – wtedy od razu geokoder, bez próby „obręb numer”. */
export const looksLikeAddress = (q: string) => /,|\b(ul|al|os|pl)\.\s/i.test(q);
