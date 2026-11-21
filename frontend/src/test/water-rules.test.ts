import { describe, expect, it } from "vitest";
import { canShowAdvice, dateBounds, doseToVolume, validDate } from "@/api/client";
import { mockBlock, parcel } from "@/api/mocks";
import { adapt } from "@/api/adapt";
describe("Parcel water rules", () => {
  it("allows today and exactly ten years back, not the future or older dates", () => {
    const today = new Date("2026-11-21T18:08:00Z");
    expect(dateBounds(today)).toEqual({ min: "2016-11-21", max: "2026-11-21" });
    expect(validDate("2016-11-21", today)).toBe(true);
    expect(validDate("2026-11-21", today)).toBe(true);
    expect(validDate("2016-11-20", today)).toBe(false);
    expect(validDate("2026-11-22", today)).toBe(false);
  });
  it("never exposes advice without assessment", () => {
    expect(canShowAdvice()).toBe(false);
    expect(
      canShowAdvice({ ...mockBlock("analysis", "2026-07-15"), data: { recommendations: [] } }),
    ).toBe(false);
    expect(canShowAdvice(mockBlock("analysis", "2026-07-15"))).toBe(true);
  });
  it("converts 20 mm to 200 cubic metres per hectare", () => expect(doseToVolume(20)).toBe(200));
  it("includes dry seasons 2018, 2019, 2022 and 2023 in the ten-year sample", () =>
    expect(mockBlock("analysis", "2026-07-15").data.assessment?.drought_years).toEqual([
      2018, 2019, 2022, 2023,
    ]));
  it("cause shares total one hundred percent", () =>
    expect(
      mockBlock("analysis", "2026-07-15").data.causes?.reduce((sum, c) => sum + c.share, 0),
    ).toBe(100));
  it("prioritizes retention, soil care, then irrigation", () =>
    expect(mockBlock("analysis", "2026-07-15").data.recommendations?.map((r) => r.group)).toEqual([
      "retencja_krajobrazowa",
      "retencja_krajobrazowa",
      "agrotechnika",
      "nawadnianie",
    ]));
  it("preserves the requested depression and nearby ditch scenario", () => {
    expect(mockBlock("terrain", "2026-07-15").data.metrics?.map((m) => m.value)).toContain(
      "2 400 m²",
    );
    expect(mockBlock("terrain", "2026-07-15").data.metrics?.map((m) => m.value)).toContain("0,6 m");
    expect(mockBlock("hydrology", "2026-07-15").data.metrics?.map((m) => m.value)).toContain(
      "140 m",
    );
    expect(parcel.voivodeship).toBe("wielkopolskie");
  });
  it("does not invent linked sources", () =>
    expect(
      mockBlock("drought", "2026-07-15").provenance.every(
        (p) => p.source_url === null && p.query_url === null,
      ),
    ).toBe(true));
  it("adapts a real analysis block: shares in %, zero drought seasons wording kept from backend", () => {
    const b = adapt({ key: "analysis", title: "Ocena", status: "ok", provenance: [], uncertainty: [], messages: [], elapsed_ms: 1,
      data: { assessment: { current_level: "low", confidence: "high", historical_summary: "W ostatnich 10 latach susza rolnicza nie wystąpiła tu w żadnym sezonie.",
        drought_years: [], critical_months: [6], evidence: [] }, causes: [{ key: "opady_deficyt", label_pl: "x", share: 0.42, evidence: [] }],
        recommendations: [], irrigation: null, limitations: [], method: [] } }, "2024-07-15");
    expect(b.data.causes?.[0]?.share).toBe(42);
    expect(b.data.assessment?.confidence).toBe("Wysoka");
    expect(b.data.assessment?.historical_summary).toContain("w żadnym sezonie");
  });
  it("adapts hydrology waters into map-linked rows", () => {
    const b = adapt({ key: "hydrology", title: "Wody", status: "ok", provenance: [], uncertainty: [], messages: [], elapsed_ms: 1,
      data: { nearest_water: [{ kind: "ditch", name: null, distance_m: 140, geometry: { type: "LineString", coordinates: [[17, 52], [17.01, 52]] } }],
        flood_zone_checked: true, in_flood_zone: null, nearest_boreholes: [] } }, "2024-07-15");
    expect(b.data.rows?.[0]?.mapId).toBe("water-0");
    expect(b.data.summary).toContain("140 m");
  });
});
