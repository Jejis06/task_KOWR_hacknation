import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import { Expand, Layers, LocateFixed, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { DataBlock, ParcelRef } from "@/api/client";
import { dist, WATER_KIND } from "@/api/adapt";
type Props = {
  parcel: ParcelRef | null;
  blocks: Record<string, DataBlock>;
  /** pokazuj warstwy z analizy (po „Sprawdź działkę”); false = tylko wskazana działka */
  showAnalysis: boolean;
  onSelect: (lon: number, lat: number) => void;
  /** id obiektu do wycentrowania; `n` zmienia się przy każdym kliknięciu (ponowne centrowanie tego samego) */
  highlight: { id: string; n: number } | null;
  onMore: (key: string) => void;
  fullscreen: boolean;
  onFullscreen: () => void;
};
export default function ParcelMap({
  parcel,
  blocks,
  showAnalysis,
  onSelect,
  highlight,
  onMore,
  fullscreen,
  onFullscreen,
}: Props) {
  const host = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const features = useRef<Record<string, L.Layer>>({});
  const callbacks = useRef({ onSelect, onMore });
  callbacks.current = { onSelect, onMore };
  const [base, setBase] = useState<"ortho" | "osm">("ortho");
  const [menu, setMenu] = useState(false);
  const [visible, setVisible] = useState({ water: true, recommendations: true, boundaries: true });
  const [tileWarning, setTileWarning] = useState(false);
  useEffect(() => {
    if (!host.current) return;
    const m = L.map(host.current, { zoomControl: true, scrollWheelZoom: false }).setView([52.1, 19.4], 6);
    map.current = m;
    L.control.scale({ imperial: false, position: "bottomright" }).addTo(m);
    const click = (e: L.LeafletMouseEvent) =>
      callbacks.current.onSelect(e.latlng.lng, e.latlng.lat);
    m.on("click", click);
    return () => {
      m.remove();
      map.current = null;
    };
  }, []);
  // nowa działka → dopasuj widok (mapa zostaje ta sama, bez przeładowania podkładu)
  useEffect(() => {
    const m = map.current;
    if (!m || !parcel) return;
    m.fitBounds([[parcel.bbox[1], parcel.bbox[0]], [parcel.bbox[3], parcel.bbox[2]]], { padding: [42, 65], maxZoom: 17 });
  }, [parcel?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    setTileWarning(false);
    const layer =
      base === "osm"
        ? L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            updateWhenIdle: true,
            keepBuffer: 4,
            attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
          })
        : L.tileLayer.wms(
            "https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/StandardResolution",
            {
              layers: "Raster",
              format: "image/jpeg",
              transparent: false,
              maxZoom: 20,
              // kafle 512 px = 4× mniej zapytań WMS niż 256 px (GUGiK ogranicza liczbę zapytań z jednego IP)
              tileSize: 512,
              zoomOffset: -1,
              updateWhenIdle: true,
              keepBuffer: 4,
              attribution: "Ortofotomapa © GUGiK / Geoportal",
            },
          );
    let errors = 0;
    layer.on("tileerror", () => {
      errors++;
      if (errors >= 3) {
        setTileWarning(true);
      }
    });
    layer.addTo(m);
    layer.bringToBack();
    return () => {
      layer.remove();
    };
  }, [base]);
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const css = getComputedStyle(document.documentElement);
    const token = (name: string) => css.getPropertyValue(name).trim();
    const green = token("--primary"),
      blue = token("--water"),
      orange = token("--warning");
    const group = L.featureGroup().addTo(m);
    features.current = {};
    if (parcel) {
      const boundary = L.geoJSON(parcel.geometry as GeoJSON.GeoJsonObject, {
        style: { color: green, weight: 3, fillColor: green, fillOpacity: 0.06 },
      }).addTo(group);
      features.current["parcel"] = boundary;
      boundary.on("click", (e: L.LeafletMouseEvent) => {
        L.DomEvent.stopPropagation(e);
        callbacks.current.onSelect(e.latlng.lng, e.latlng.lat);
      });
    }
    const popup = (title: string, detail: string, key: string | null, note = "") => {
      const el = document.createElement("div");
      const strong = document.createElement("strong");
      strong.textContent = title;
      el.append(strong);
      const p = document.createElement("div");
      p.textContent = detail;
      el.append(p);
      if (note) {
        const n = document.createElement("small");
        n.textContent = note;
        el.append(n);
      }
      if (key) {
        const button = document.createElement("button");
        button.className = "map-popup-action";
        button.textContent = "Więcej danych →";
        button.addEventListener("click", () => callbacks.current.onMore(key));
        el.append(button);
      }
      return el;
    };
    const stop = (e: L.LeafletEvent) => L.DomEvent.stopPropagation(e as L.LeafletMouseEvent);
    const terrain = showAnalysis ? blocks["terrain"]?.data.raw : null;
    const hydro = showAnalysis ? blocks["hydrology"]?.data.raw : null;
    const recs = showAnalysis ? blocks["analysis"]?.data.recommendations ?? [] : [];
    if (visible.water) {
      (terrain?.flow_lines_geojson?.features ?? []).forEach((f: GeoJSON.Feature) =>
        L.geoJSON(f, { style: { color: blue, weight: 2, dashArray: "6 7" }, interactive: false }).addTo(group));
      (terrain?.depressions_geojson?.features ?? []).forEach((f: GeoJSON.Feature<GeoJSON.Geometry, Record<string, number>>, i: number) => {
        const pr = f.properties ?? {};
        const l = L.geoJSON(f, { style: { color: blue, weight: 2, fillColor: blue, fillOpacity: 0.35 } })
          .bindPopup(popup("Zagłębienie terenu – zbiera się tu woda",
            `${(pr.area_m2 ?? 0).toLocaleString("pl-PL")} m² · do ${(pr.max_depth_m ?? 0).toLocaleString("pl-PL")} m · ok. ${(pr.volume_m3 ?? 0).toLocaleString("pl-PL")} m³`,
            "terrain", pr.catchment_ha != null ? `Woda spływa tu z ok. ${pr.catchment_ha.toLocaleString("pl-PL")} ha` : ""))
          .on("click", stop).addTo(group);
        features.current[`dep-${i}`] = l;
        if (!features.current["depression"] && (f.properties as unknown as { touches_parcel?: boolean })?.touches_parcel) features.current["depression"] = l;
      });
      (terrain?.runoff_exits_geojson?.features ?? []).forEach((f: GeoJSON.Feature<GeoJSON.Geometry, Record<string, number>>, i: number) => {
        const l = L.geoJSON(f, { style: { color: orange, weight: 6, opacity: 0.9, lineCap: "round" } })
          .bindPopup(popup("Tu woda ucieka z pola", `ok. ${f.properties?.length_m ?? "?"} m granicy · spływ z ${f.properties?.catchment_ha?.toLocaleString("pl-PL") ?? "?"} ha`,
            "terrain", "Dobre miejsce na pas zieleni lub zadrzewienie"))
          .on("click", stop).addTo(group);
        features.current[`exit-${i}`] = l;
      });
      (hydro?.nearest_water ?? []).forEach((w: { kind: string; name: string | null; distance_m: number; geometry: GeoJSON.Geometry | null }, i: number) => {
        if (!w.geometry) return;
        const kind = WATER_KIND[w.kind] ?? "Woda";
        const l = L.geoJSON(w.geometry, { style: { color: w.kind === "ditch" ? "#0e7490" : blue, weight: 4, fillColor: blue, fillOpacity: 0.55 } })
          .bindPopup(popup(w.name && !kind.toLowerCase().includes(w.name.toLowerCase()) ? `${kind}: ${w.name}` : kind, `${dist(w.distance_m)} od działki`, "hydrology", "BDOT10k (GUGiK)"))
          .bindTooltip(`${kind} · ${dist(w.distance_m)}`)
          .on("click", stop).addTo(group);
        features.current[`water-${i}`] = l;
      });
    }
    if (visible.recommendations) {
      recs.filter((r) => r.where_geojson).forEach((r) => {
        const l = L.geoJSON(r.where_geojson as GeoJSON.GeoJsonObject, {
          style: { color: orange, weight: 4, fillColor: orange, fillOpacity: 0.45 },
        })
          .bindPopup(popup(r.title, r.when ?? "", null, "Miejsce z zalecenia – sprawdź w terenie"))
          .on("click", stop).addTo(group);
        features.current[`rec-${r.measure_id}`] = l;
        if (!features.current["recommendation"]) features.current["recommendation"] = l;
      });
    }
    let wms: L.TileLayer.WMS | null = null;
    if (visible.boundaries) {
      wms = L.tileLayer
        .wms("https://integracja.gugik.gov.pl/cgi-bin/KrajowaIntegracjaEwidencjiGruntow", {
          layers: "dzialki,numery_dzialek",
          format: "image/png",
          transparent: true,
          minZoom: 15,
          maxZoom: 20,
          tileSize: 512,
          zoomOffset: -1,
          updateWhenIdle: true,
          attribution: "Granice ewidencyjne © GUGiK",
        })
        .addTo(m);
    }
    return () => {
      group.remove();
      wms?.remove();
    };
  }, [parcel, visible, blocks, showAnalysis]);
  // wycentruj wskazany obiekt (z tabeli analityka lub przycisku w raporcie) na mapie – bez powiększania
  useEffect(() => {
    const m = map.current;
    const f = highlight ? features.current[highlight.id] : null;
    if (!m || !f) return;
    host.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    if (f instanceof L.Marker || f instanceof L.CircleMarker) {
      m.setView(f.getLatLng(), Math.max(m.getZoom(), 16));
    } else if (f instanceof L.FeatureGroup) {
      const b = f.getBounds();
      if (b.isValid()) {
        m.flyToBounds(b, { padding: [40, 40], maxZoom: 17, duration: 0.6 });
        if (f instanceof L.GeoJSON) {
          f.setStyle({ weight: 7 });
          setTimeout(() => f.resetStyle(), 2200);
        }
      }
    }
    setTimeout(() => (f as L.Layer & { openPopup?: () => void }).openPopup?.(), 650);
  }, [highlight, parcel, visible, blocks]);
  useEffect(() => {
    const t = setTimeout(() => map.current?.invalidateSize(), 100);
    return () => clearTimeout(t);
  }, [fullscreen]);
  return (
    <div className="map-shell">
      <div
        className="map-canvas"
        ref={host}
        role="region"
        aria-label="Mapa działki, obniżeń terenu i wody w okolicy"
      />
      <div className="map-top">
        <div className="map-base-switch" aria-label="Podkład mapy">
          <Button
            variant={base === "ortho" ? "secondary" : "ghost"}
            className="map-choice"
            onClick={() => setBase("ortho")}
            aria-pressed={base === "ortho"}
          >
            Zdjęcie lotnicze
          </Button>
          <Button
            variant={base === "osm" ? "secondary" : "ghost"}
            className="map-choice"
            onClick={() => setBase("osm")}
            aria-pressed={base === "osm"}
          >
            Mapa
          </Button>
        </div>
        <div className="map-toolbar">
          <Button
            variant="ghost"
            className="map-tool"
            aria-label="Warstwy mapy"
            title="Warstwy mapy"
            onClick={() => setMenu(!menu)}
            aria-expanded={menu}
          >
            <Layers />
          </Button>
          <Button
            variant="ghost"
            className="map-tool"
            aria-label={fullscreen ? "Zamknij dużą mapę" : "Powiększ mapę"}
            title={fullscreen ? "Zamknij mapę" : "Powiększ mapę"}
            onClick={onFullscreen}
          >
            {fullscreen ? <X /> : <Expand />}
          </Button>
        </div>
      </div>
      {menu && (
        <div className="map-layer-menu">
          <strong>Widoczne na mapie</strong>
          {(
            [
              ["water", "Woda i kierunek odpływu"],
              ["recommendations", "Miejsca zatrzymania wody"],
              ["boundaries", "Granice z Geoportalu"],
            ] as const
          ).map(([key, label]) => (
            <label key={key}>
              <input
                type="checkbox"
                checked={visible[key]}
                onChange={(e) => setVisible((v) => ({ ...v, [key]: e.target.checked }))}
              />
              {label}
            </label>
          ))}
          <Button
            variant="ghost"
            className="w-full mt-2"
            onClick={() => {
              if (parcel) map.current?.fitBounds(
                [
                  [parcel.bbox[1], parcel.bbox[0]],
                  [parcel.bbox[3], parcel.bbox[2]],
                ],
                { padding: [45, 65] },
              );
              setMenu(false);
            }}
          >
            <LocateFixed />
            Wróć do działki
          </Button>
        </div>
      )}
      <div className="map-legend">
        <div className="legend-row">
          <span className="legend-sample" />
          Twoja działka
        </div>
        <div className="legend-row">
          <span className="legend-sample blue" />
          Miejsce zbierania wody
        </div>
        <div className="legend-row">
          <span className="legend-sample flow" />
          Kierunek odpływu
        </div>
        <div className="legend-row">
          <span className="legend-sample orange" />
          Tu zatrzymaj wodę / tu woda ucieka
        </div>
        {tileWarning && (
          <Button
            variant="link"
            className="h-auto p-0 text-xs"
            onClick={() => setBase(base === "ortho" ? "osm" : "ortho")}
          >
            Nie wczytano podkładu. Zmień widok.
          </Button>
        )}
      </div>
    </div>
  );
}
