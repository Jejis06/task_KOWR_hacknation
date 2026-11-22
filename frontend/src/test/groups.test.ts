import { describe, expect, it } from "vitest";
import { groupParcels, looksLikeAddress, looksLikeParcelId } from "@/lib/groups";
import type { ParcelRef } from "@/api/client";

const p = (id: string, x: number, y: number, size = 0.002): ParcelRef => ({
  id, geometry: { type: "Point", coordinates: [x, y] } as never, centroid: [x, y], bbox: [x, y, x + size, y + size], area_ha: 1,
} as unknown as ParcelRef);

describe("groupParcels", () => {
  it("łączy sąsiednie, rozdziela oddalone o kilka km", () => {
    const g = groupParcels([p("a", 17.2, 52.2), p("b", 17.2022, 52.2), p("c", 17.3, 52.2)]);
    expect(g.map((x) => x.map((y) => y.id).sort())).toEqual([["a", "b"], ["c"]]);
  });
});

describe("rozpoznawanie wpisu", () => {
  it("numer działki vs adres", () => {
    expect(looksLikeParcelId("302504_5.0024.7")).toBe(true);
    expect(looksLikeParcelId("Słupia Wielka 7")).toBe(false);
    expect(looksLikeAddress("Środa Wielkopolska, Kosynierów 1")).toBe(true);
    expect(looksLikeAddress("Słupia Wielka 7")).toBe(false);
  });
});
