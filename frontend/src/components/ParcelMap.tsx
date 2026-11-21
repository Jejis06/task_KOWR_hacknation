// Czysty Leaflet (BSD-2) – bez react-leaflet (licencja Hippocratic, niezgodna z przeniesieniem praw na KOWR).
import { useEffect, useRef } from "react";
import L from "leaflet";
import type { HydrologyInfo, ParcelRef, TerrainInfo } from "../api/types";

export interface MapOverlays { terrain?: TerrainInfo | null; hydrology?: HydrologyInfo | null }

export function ParcelMap(props: { parcel: ParcelRef | null; overlays?: MapOverlays; onPick: (lon: number, lat: number) => void }) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const parcelLayer = useRef<L.GeoJSON | null>(null);
  const overlayGroup = useRef<L.LayerGroup | null>(null);
  const control = useRef<L.Control.Layers | null>(null);
  const onPick = useRef(props.onPick);
  onPick.current = props.onPick;

  useEffect(() => {
    if (!el.current || map.current) return;
    const m = L.map(el.current, { tap: true } as L.MapOptions).setView([52.1, 19.4], 6);
    const osm = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "&copy; OpenStreetMap", maxZoom: 19 });
    const orto = L.tileLayer.wms("https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/StandardResolution", {
      layers: "Raster", format: "image/jpeg", attribution: "Ortofotomapa GUGiK", maxZoom: 19,
    });
    osm.addTo(m);
    // granice i numery działek – KIEG GUGiK (od dużych zoomów)
    const kieg = L.tileLayer.wms("https://integracja.gugik.gov.pl/cgi-bin/KrajowaIntegracjaEwidencjiGruntow", {
      layers: "dzialki,numery_dzialek", format: "image/png", transparent: true, minZoom: 15, attribution: "GUGiK KIEG",
    }).addTo(m);
    control.current = L.control.layers({ "Mapa": osm, "Zdjęcie lotnicze": orto }, { "Granice działek": kieg }, { collapsed: true }).addTo(m);
    overlayGroup.current = L.layerGroup().addTo(m);
    m.on("click", (e: L.LeafletMouseEvent) => onPick.current(e.latlng.lng, e.latlng.lat));
    map.current = m;
    return () => { m.remove(); map.current = null; };
  }, []);

  useEffect(() => {
    const m = map.current;
    if (!m) return;
    parcelLayer.current?.remove();
    if (!props.parcel) return;
    parcelLayer.current = L.geoJSON(props.parcel.geometry as never, { style: { color: "#d4a017", weight: 3, fillOpacity: 0.08 } }).addTo(m);
    const [x1, y1, x2, y2] = props.parcel.bbox;
    m.fitBounds([[y1, x1], [y2, x2]], { padding: [40, 40], maxZoom: 17 });
  }, [props.parcel]);

  // warstwy z bloków: zagłębienia i linie spływu (teren), wody w pobliżu (hydrologia)
  useEffect(() => {
    const g = overlayGroup.current;
    if (!g) return;
    g.clearLayers();
    const t = props.overlays?.terrain;
    if (t?.depressions_geojson) {
      L.geoJSON(t.depressions_geojson as never, { style: { color: "#1d4ed8", weight: 1, fillColor: "#3b82f6", fillOpacity: 0.45 } })
        .bindTooltip("Zagłębienie terenu – tu zbiera się woda").addTo(g);
    }
    if (t?.flow_lines_geojson) {
      L.geoJSON(t.flow_lines_geojson as never, { style: { color: "#0ea5e9", weight: 2.5, dashArray: "6 4" } })
        .bindTooltip("Linia spływu wody").addTo(g);
    }
    for (const w of props.overlays?.hydrology?.nearest_water ?? []) {
      if (!w.geometry) continue;
      L.geoJSON(w.geometry as never, { style: { color: w.kind === "ditch" ? "#0891b2" : "#1e40af", weight: 3 } })
        .bindTooltip(`${w.name ?? w.kind} – ${Math.round(w.distance_m)} m`).addTo(g);
    }
  }, [props.overlays?.terrain, props.overlays?.hydrology]);

  return (
    <div className="map-wrap">
      <div className="map" ref={el} role="application" aria-label="Mapa – kliknij pole, aby wybrać działkę" />
      <p className="hint no-print">Przybliż mapę i kliknij swoje pole – granice działek widać od dużego przybliżenia. Zmień podkład na „Zdjęcie lotnicze” w prawym górnym rogu.</p>
    </div>
  );
}
